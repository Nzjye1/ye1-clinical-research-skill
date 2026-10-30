"""Sole v0.6 IPCW numerical owner for a frozen Cox model's supplied risks.

This module never fits or updates a risk model. The evaluation-cohort marginal
reverse Kaplan-Meier estimate is a distinct nuisance estimate. Only ``record``
is public aggregate material; the complete grid and contributions are private.
"""
from __future__ import annotations

import copy
import math
from fractions import Fraction
import re

if __package__:
    from . import survival
else:
    import survival

METHOD_ID = "evaluation.survival.cox.ipcw"
MIN_G = Fraction(1, 20)
MAX_WEIGHT = 20
MAX_ROWS = survival.budget_rules.ABSOLUTE_MAX_ROWS
MAX_HORIZONS = 12
IDENTITY_ATOL = 1e-10
IDENTITY_RTOL = 1e-10
OPTION_FIELDS = {
    "estimator", "censoring_source", "censoring_assumption", "tie_order",
    "min_censoring_survival", "max_ipcw_weight", "positivity_policy",
    "roc_thresholds", "calibration", "dca_thresholds", "uncertainty", "prespecified",
}


class EvaluationBlocked(ValueError):
    """Stable, value-free reason suitable for the transport boundary."""


def _need(condition, reason):
    if not condition:
        raise EvaluationBlocked(reason)


def _number(value, reason):
    _need(type(value) in (int, float), reason)
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise EvaluationBlocked(reason) from None
    _need(math.isfinite(result), reason)
    return result


def _grid(value, minimum, maximum, reason, endpoints=False, interior=False):
    _need(isinstance(value, list) and minimum <= len(value) <= maximum, reason)
    numbers = [_number(item, reason) for item in value]
    _need(all(a < b for a, b in zip(numbers, numbers[1:])), reason)
    _need(all(0 < item < 1 if interior else 0 <= item <= 1 for item in numbers), reason)
    if endpoints:
        _need(numbers[0] == 0 and numbers[-1] == 1, reason)
    return numbers


def validate_evaluation(options, resource_budget=None):
    """Closed, prespecified options; JSON booleans are never numeric options."""
    _need(isinstance(options, dict) and set(options) == OPTION_FIELDS,
          "SURVIVAL_EVALUATION_OPTIONS_INVALID")
    expected = {
        "estimator": "marginal_reverse_km_ipcw",
        "censoring_source": "evaluation_cohort",
        "censoring_assumption": "independent_of_event_time_and_model_features",
        "tie_order": "events_before_censoring",
        "positivity_policy": "reject_no_clipping", "uncertainty": "not_implemented",
    }
    _need(all(options[key] == value for key, value in expected.items())
          and options["prespecified"] is True, "SURVIVAL_EVALUATION_OPTIONS_INVALID")
    _need(_number(options["min_censoring_survival"], "IPCW_GUARDS_INVALID") == float(MIN_G)
          and _number(options["max_ipcw_weight"], "IPCW_GUARDS_INVALID") == MAX_WEIGHT,
          "IPCW_GUARDS_INVALID")
    _grid(options["roc_thresholds"], 2, 51, "ROC_THRESHOLDS_INVALID", endpoints=True)
    _grid(options["dca_thresholds"], 1, 51, "DCA_THRESHOLDS_INVALID", interior=True)
    calibration = options["calibration"]
    _need(isinstance(calibration, dict)
          and set(calibration) == {"method", "probability_edges", "min_bin_n"}
          and calibration["method"] == "ipcw_hajek_fixed_bins",
          "CALIBRATION_OPTIONS_INVALID")
    _grid(calibration["probability_edges"], 2, 11, "CALIBRATION_EDGES_INVALID", endpoints=True)
    limits = survival._resource_limits(resource_budget, METHOD_ID)
    _need(type(calibration["min_bin_n"]) is int and 2 <= calibration["min_bin_n"] <= limits["max_rows"],
          "CALIBRATION_MIN_BIN_N_INVALID")
    return copy.deepcopy(options)


def validate_labels(rows, spec, resource_budget=None):
    """Reuse old feature/identity/coding rules, then require every outcome label."""
    _need(isinstance(rows, list) and bool(rows), "EVALUATION_ROWS_INVALID")
    limits = survival._resource_limits(resource_budget, METHOD_ID)
    try:
        survival.budget_rules.check_rows(len(rows), limits)
    except survival.budget_rules.BudgetError as exc:
        raise EvaluationBlocked(exc.code) from None
    survival._prediction_data(rows, spec, require_features=True)
    target = survival._code(spec["event_code"])
    times, events, identifiers = [], [], []
    for row in rows:
        _need(not survival._missing(row[spec["time"]]), "EVALUATION_FOLLOWUP_MISSING")
        _need(not survival._missing(row[spec["status"]]), "EVALUATION_STATUS_MISSING")
        times.append(survival._number(row[spec["time"]]))
        events.append(int(survival._code(row[spec["status"]]) == target))
        identifiers.append(row[spec["subject_id"]])
    return times, events, identifiers


def validate_horizons(horizons, spec):
    _need(isinstance(horizons, list) and 0 < len(horizons) <= MAX_HORIZONS,
          "EVALUATION_HORIZONS_INVALID")
    result = [_number(value, "EVALUATION_HORIZONS_INVALID") for value in horizons]
    _need(result[0] >= 0 and all(a < b for a, b in zip(result, result[1:])),
          "EVALUATION_HORIZONS_INVALID")
    _need(isinstance(spec.get("evaluation_times"), list)
          and all(type(value) in (int, float) for value in spec["evaluation_times"])
          and spec["evaluation_times"] == horizons, "PREDICTION_HORIZONS_SPEC_MISMATCH")
    return result


def _predicted_risks(individual, identifiers, horizons):
    reason = "EVALUATION_PREDICTIONS_INVALID"
    _need(isinstance(individual, list) and len(individual) == len(identifiers) * len(horizons), reason)
    expected_ids, expected_horizons = set(identifiers), set(horizons)
    lookup = {}
    for row in individual:
        _need(isinstance(row, dict) and set(row) == {
            "subject_id", "horizon", "survival_probability", "event_risk"}, reason)
        _need(isinstance(row["subject_id"], str) and row["subject_id"] in expected_ids, reason)
        horizon = _number(row["horizon"], reason)
        risk = _number(row["event_risk"], reason)
        survival_probability = _number(row["survival_probability"], reason)
        _need(horizon in expected_horizons and 0 <= risk <= 1 and 0 <= survival_probability <= 1
              and math.isclose(risk + survival_probability, 1, rel_tol=0, abs_tol=1e-14), reason)
        key = row["subject_id"], horizon
        _need(key not in lookup, reason)
        lookup[key] = risk
    _need(len(lookup) == len(identifiers) * len(horizons), reason)
    return {horizon: [lookup[subject, horizon] for subject in identifiers] for horizon in horizons}


def _censoring_grid(times, events):
    """Exact rational products make the declared G=.05 boundary unambiguous."""
    groups = {}
    for time, event in zip(times, events):
        group = groups.setdefault(time, [0, 0])
        group[0 if event else 1] += 1
    risk = len(times)
    g, km = Fraction(1), Fraction(1)
    grid, internal = [], []
    for time in sorted(groups):
        deaths, censors = groups[time]
        before_g, before_km = g, km
        km *= Fraction(risk - deaths, risk)
        # Event-only terminal times have risk-deaths=0: there is no censoring
        # jump, so no division is attempted. Exact near ties remain distinct.
        if censors:
            g *= Fraction(risk - deaths - censors, risk - deaths)
        row = {"time": time, "n_risk": risk, "n_events": deaths, "n_censored": censors,
               "censor_risk": risk - deaths, "g_before": float(before_g), "g_after": float(g),
               "km_before": float(before_km), "km_after": float(km)}
        grid.append(row)
        internal.append((time, before_g, g, km))
        risk -= deaths + censors
    return grid, internal


def _ess(weights):
    if weights is None:
        return None
    total = sum(weights, Fraction(0))
    return float(total * total / sum(value * value for value in weights)) if total else None


def _float_or_none(value):
    """Only the serialization boundary rounds exact IPCW moments to floats."""
    return None if value is None else float(value)


def _weights(times, events, horizon, internal):
    before = {time: left for time, left, _, _ in internal}
    g, km = Fraction(1), Fraction(1)
    for time, _, after, after_km in internal:
        if time > horizon:
            break
        g, km = after, after_km
    case_indices = [i for i, (time, event) in enumerate(zip(times, events)) if event and time <= horizon]
    control_indices = [i for i, time in enumerate(times) if time > horizon]
    case_g = [before[times[i]] for i in case_indices]
    reasons = []
    if g <= 0:
        reasons.append("CENSORING_SURVIVAL_NONPOSITIVE_AT_HORIZON")
    elif g < MIN_G:
        reasons.append("CENSORING_SURVIVAL_BELOW_MIN_AT_HORIZON")
    if any(value <= 0 for value in case_g):
        reasons.append("CASE_CENSORING_SURVIVAL_NONPOSITIVE")
    elif any(value < MIN_G for value in case_g):
        reasons.append("CASE_CENSORING_SURVIVAL_BELOW_MIN")
    computable = all(value > 0 for value in case_g) and (not control_indices or g > 0)
    a = b = weights = None
    if computable:
        exact_a, exact_b = [Fraction(0) for _ in times], [Fraction(0) for _ in times]
        for i in case_indices:
            exact_a[i] = 1 / before[times[i]]
        for i in control_indices:
            exact_b[i] = 1 / g
        if any(value > MAX_WEIGHT for value in exact_a + exact_b):
            reasons.append("IPCW_WEIGHT_ABOVE_MAX")
        # Keep the same exact weights through every moment and ratio. Early
        # conversion can put a mathematically exact probability endpoint above
        # one when numerator and denominator accumulate different roundoff.
        a, b = exact_a, exact_b
        weights = [case + control for case, control in zip(a, b)]
        _need(all(math.isfinite(value) and value >= 0 for value in a + b + weights), "IPCW_WEIGHT_NONFINITE")
    summary = {
        "g_at_horizon": float(g), "min_g_for_cases": float(min(case_g)) if case_g else None,
        "sum_case_weights": float(sum(a)) if a is not None else None,
        "sum_control_weights": float(sum(b)) if b is not None else None,
        "sum_weights": float(sum(weights)) if weights is not None else None,
        "max_weight": float(max(weights)) if weights is not None else None,
        "ess": _ess(weights), "case_ess": _ess(a), "control_ess": _ess(b),
    }
    diagnostics = {"weight_mass_minus_n": None, "km_event_probability": float(1 - km),
                   "weighted_case_probability": None, "km_identity_difference": None,
                   "weight_mass_identity_ok": None, "km_identity_ok": None}
    # The same-cohort identities are applicable only when G(t)>0.
    if weights is not None and g > 0:
        case_probability = float(sum(a) / len(times))
        mass_ok = math.isclose(summary["sum_weights"], len(times), rel_tol=IDENTITY_RTOL, abs_tol=IDENTITY_ATOL)
        km_ok = math.isclose(case_probability, float(1 - km), rel_tol=IDENTITY_RTOL, abs_tol=IDENTITY_ATOL)
        diagnostics.update(weight_mass_minus_n=summary["sum_weights"] - len(times),
                           weighted_case_probability=case_probability,
                           km_identity_difference=case_probability - float(1 - km),
                           weight_mass_identity_ok=mass_ok, km_identity_ok=km_ok)
        _need(mass_ok, "IPCW_MASS_IDENTITY_FAILED")
        _need(km_ok, "IPCW_KM_IDENTITY_FAILED")
    return a, b, summary, diagnostics, reasons, case_indices, control_indices, before


def _metric(name, value, numerator, denominator, reason):
    definitions = {
        "auc": ("sum_case_control_weighted_concordance_with_half_exact_ties",
                "sum_case_weights_times_sum_control_weights"),
        "brier": ("sum_case_weight_times_one_minus_risk_squared_plus_control_weight_times_risk_squared",
                  "all_evaluation_subjects_including_early_censoring"),
    }
    return {"metric": name, "status": "unavailable" if reason else "completed", "value": value,
            "numerator": numerator, "denominator": denominator,
            "numerator_definition": definitions[name][0], "denominator_definition": definitions[name][1],
            "reason": reason, "uncertainty": "not_implemented"}


def _evaluate_horizon(times, events, risks, horizon, options, internal):
    n = len(times)
    a, b, weight_summary, diagnostics, reasons, cases, controls, before = _weights(times, events, horizon, internal)
    case_set, control_set = set(cases), set(controls)
    counts = {
        "n": n, "n_cases": len(cases), "n_controls": len(controls),
        "n_censored_by_horizon": n - len(cases) - len(controls),
        "n_at_risk_before_horizon": sum(time >= horizon for time in times),
        "n_events_at_horizon": sum(time == horizon and event == 1 for time, event in zip(times, events)),
        "n_censored_at_horizon": sum(time == horizon and event == 0 for time, event in zip(times, events)),
        "n_case_control_score_ties": sum(risks[i] == risks[j] for i in cases for j in controls),
    }
    positivity_reason = reasons[0] if reasons else None
    auc_reason = positivity_reason
    if auc_reason is None:
        if not cases and not controls:
            auc_reason = "NO_CASES_OR_CONTROLS_AT_HORIZON"
        elif not cases:
            auc_reason = "NO_CASES_AT_HORIZON"
        elif not controls:
            auc_reason = "NO_CONTROLS_AT_HORIZON"
    A = sum(a, Fraction(0)) if a is not None else None
    B = sum(b, Fraction(0)) if b is not None else None
    auc_numerator = auc_value = None
    auc_exact_denominator = A * B if A is not None and B is not None else None
    auc_denominator = _float_or_none(auc_exact_denominator)
    if not auc_reason:
        # This is the exact pairwise statistic, with the inner control sum
        # factored per case. Score comparisons and half ties remain exact;
        # neither a displayed ROC trapezoid nor probability clipping is used.
        exact_numerator = sum((a[i] * sum((b[j] if risks[i] > risks[j] else b[j] / 2
                                          if risks[i] == risks[j] else Fraction(0)
                                          for j in controls), Fraction(0))
                               for i in cases), Fraction(0))
        auc_numerator = float(exact_numerator)
        auc_value = float(exact_numerator / auc_exact_denominator)
    brier_numerator = brier_value = None
    if not positivity_reason:
        # Fraction(float) represents the already-frozen binary probability
        # exactly. Squared losses and the population denominator then preserve
        # both Brier endpoints without normalizing or clipping any weight.
        exact_risks = [Fraction(risk) for risk in risks]
        exact_numerator = sum((a[i] * (1 - exact_risks[i]) ** 2 + b[i] * exact_risks[i] ** 2
                               for i in range(n)), Fraction(0))
        brier_numerator = float(exact_numerator)
        brier_value = float(exact_numerator / n)
    metrics = [_metric("auc", auc_value, auc_numerator, auc_denominator, auc_reason),
               _metric("brier", brier_value, brier_numerator, n, positivity_reason)]

    roc = []
    for threshold in [None] + list(reversed(options["roc_thresholds"])):
        selected = [] if threshold is None else [i for i, risk in enumerate(risks) if risk >= threshold]
        tp = sum((a[i] for i in selected), Fraction(0)) if a is not None else None
        fp = sum((b[i] for i in selected), Fraction(0)) if b is not None else None
        roc.append({"threshold": threshold, "boundary": "above_all" if threshold is None else "fixed_grid",
                    "status": "unavailable" if auc_reason else "completed", "reason": auc_reason,
                    "n_treated": len(selected), "tp_weight": _float_or_none(tp), "fp_weight": _float_or_none(fp),
                    "sensitivity": None if auc_reason else float(tp / A),
                    "false_positive_rate": None if auc_reason else float(fp / B),
                    "specificity": None if auc_reason else float((B - fp) / B)})

    calibration = []
    edges = options["calibration"]["probability_edges"]
    for index, (left, right) in enumerate(zip(edges, edges[1:]), 1):
        inclusive = index == len(edges) - 1
        selected = [i for i, risk in enumerate(risks) if left <= risk and (risk <= right if inclusive else risk < right)]
        predicted_sum = math.fsum(risks[i] for i in selected)
        aa = sum((a[i] for i in selected), Fraction(0)) if a is not None else None
        bb = sum((b[i] for i in selected), Fraction(0)) if b is not None else None
        total = aa + bb if aa is not None and bb is not None else None
        reason = positivity_reason
        if reason is None:
            if not selected:
                reason = "CALIBRATION_BIN_EMPTY"
            elif len(selected) < options["calibration"]["min_bin_n"]:
                reason = "CALIBRATION_BIN_BELOW_MIN_N"
            elif total == 0:
                reason = "CALIBRATION_BIN_ZERO_WEIGHT"
        calibration.append({
            "bin_index": index, "lower": left, "upper": right, "right_inclusive": inclusive, "n": len(selected),
            "n_cases": sum(i in case_set for i in selected), "n_controls": sum(i in control_set for i in selected),
            "n_censored_by_horizon": sum(i not in case_set and i not in control_set for i in selected),
            "predicted_risk_sum": predicted_sum, "mean_predicted_risk": predicted_sum / len(selected) if selected else None,
            "sum_case_weights": _float_or_none(aa), "sum_control_weights": _float_or_none(bb), "sum_weights": _float_or_none(total),
            "ess": _ess([a[i] + b[i] for i in selected]) if a is not None else None,
            "observed_risk": None if reason else float(aa / total),
            "status": "unavailable" if reason else "completed", "reason": reason, "uncertainty": "not_implemented",
        })

    dca = []
    for threshold in options["dca_thresholds"]:
        selected = [i for i, risk in enumerate(risks) if risk >= threshold]
        tp = sum((a[i] for i in selected), Fraction(0)) if a is not None else None
        fp = sum((b[i] for i in selected), Fraction(0)) if b is not None else None
        exact_threshold = Fraction(threshold)
        odds = exact_threshold / (1 - exact_threshold)
        numerator = tp - odds * fp if not positivity_reason else None
        all_numerator = A - odds * B if not positivity_reason else None
        dca.append({
            "threshold": threshold, "status": "unavailable" if positivity_reason else "completed", "reason": positivity_reason,
            "n_treated": len(selected), "n_treated_cases": sum(i in case_set for i in selected),
            "n_treated_controls": sum(i in control_set for i in selected),
            "n_treated_censored_by_horizon": sum(i not in case_set and i not in control_set for i in selected),
            "tp_weight": _float_or_none(tp), "fp_weight": _float_or_none(fp),
            "treated_weight_sum": float(tp + fp) if tp is not None and fp is not None else None,
            "treated_ess": _ess([a[i] + b[i] for i in selected]) if a is not None else None,
            "threshold_odds": float(odds), "population_denominator": n,
            "numerator_model": _float_or_none(numerator), "numerator_all": _float_or_none(all_numerator),
            "net_benefit_model": float(numerator / n) if numerator is not None else None,
            "net_benefit_all": float(all_numerator / n) if all_numerator is not None else None,
            "net_benefit_none": 0.0 if not positivity_reason else None, "uncertainty": "not_implemented",
        })
    all_reasons = list(dict.fromkeys(reasons + [row["reason"] for row in metrics + calibration if row["reason"]]))
    status = "unavailable" if positivity_reason else "partial" if all_reasons else "completed"
    result = {"horizon": horizon, "status": status, "reason_codes": all_reasons, "counts": counts,
              "weights": weight_summary, "diagnostics": diagnostics, "metrics": metrics,
              "roc": roc, "calibration": calibration, "dca": dca}
    contributions = []
    for i, (time, event) in enumerate(zip(times, events)):
        classification = "case" if i in case_set else "control" if i in control_set else "censored_by_horizon"
        divisor = before[time] if i in case_set else None
        if i in control_set:
            divisor = Fraction(1)
            for grid_time, _, after, _ in internal:
                if grid_time > horizon:
                    break
                divisor = after
        contributions.append({
            "horizon": horizon, "observed_time": time, "event": event,
            "classification": classification, "event_risk": risks[i],
            "g_denominator": float(divisor) if divisor is not None else None,
            "case_weight": float(a[i]) if a is not None else None,
            "control_weight": float(b[i]) if b is not None else None,
            "weight": float(a[i] + b[i]) if a is not None else None,
            "horizon_status": status, "horizon_reason_codes": list(all_reasons),
        })
    return result, contributions


def evaluate(rows, spec, horizons, individual_predictions, evaluation,
             model_sha256, frozen_model_provider_version, resource_budget=None):
    """Evaluate validated frozen risks, returning public aggregates and private audit.

    Direct formula tests may supply their own prespecified risk vectors. The
    production bridge must obtain these vectors from unchanged frozen ``infer``.
    No other prediction path or model fitting is selected by this owner.
    """
    try:
        limits = survival._resource_limits(resource_budget, METHOD_ID)
        options = validate_evaluation(evaluation, limits)
        times, events, identifiers = validate_labels(rows, spec, limits)
        horizons = validate_horizons(horizons, spec)
        survival._check_resource_budget(rows, spec, horizons, limits, METHOD_ID, "evaluate")
        _need(all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                  for value in (model_sha256, frozen_model_provider_version)), "EVALUATION_MODEL_BINDING_INVALID")
        risks = _predicted_risks(individual_predictions, identifiers, horizons)
        grid, internal = _censoring_grid(times, events)
        results, contributions = [], []
        for horizon in horizons:
            result, private = _evaluate_horizon(times, events, risks[horizon], horizon, options, internal)
            results.append(result)
            contributions.extend({"subject_id": subject, **entry} for subject, entry in zip(identifiers, private))
        statuses = [entry["status"] for entry in results]
        status = "unavailable" if all(value == "unavailable" for value in statuses) else "completed" if all(value == "completed" for value in statuses) else "partial"
        record = {
            "method_id": METHOD_ID, "operation": "evaluate", "model_sha256": model_sha256,
            "frozen_model_provider_version": frozen_model_provider_version,
            "population": {"n_input": len(rows), "n_evaluable": len(rows), "n_dropped_missing": 0,
                           "n_events": sum(events), "n_censored": len(rows) - sum(events), "n_horizons": len(horizons)},
            "options": options,
            "censoring_metadata": {
                "estimator": options["estimator"], "source": options["censoring_source"],
                "assumption": options["censoring_assumption"], "assumption_verified": False,
                "tie_order": options["tie_order"], "time_unit": spec["time_unit"],
                "full_grid_location": "private", "weight_clipping": False, "uncertainty": "not_implemented",
            },
            "status": status, "reason_codes": list(dict.fromkeys(reason for result in results for reason in result["reason_codes"])),
            "horizon_results": results,
        }
        return {"ok": True, "record": record,
                "private_evaluation": {"censoring_grid": grid, "individual_ipcw": contributions}}
    except (EvaluationBlocked, survival.SurvivalBlocked) as exc:
        return {"ok": False, "reason_code": str(exc)}
