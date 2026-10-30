"""Explicit, independent-subject right-censored survival and competing risks.

Only aggregate curves on a prespecified grid and aggregate model summaries leave
this module. Data access, project consent and protected artifacts belong to the
calling adapter. A successful computation is not scientific or clinical approval.
"""
from __future__ import annotations

import math
import warnings
from collections import Counter


class SurvivalBlocked(ValueError):
    """A stable applicability code, never a patient value or row."""


def _need(condition, code):
    if not condition:
        raise SurvivalBlocked(code)


def _missing(value):
    return value is None or value == ""


def _number(value):
    _need(not isinstance(value, bool), "INVALID_FINITE_NUMBER")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise SurvivalBlocked("INVALID_FINITE_NUMBER") from None
    _need(math.isfinite(number), "INVALID_FINITE_NUMBER")
    return number


def _code(value):
    # CSV strings and JSON numeric codes are intentionally distinct. This avoids
    # silently merging "01" and 1 or true and 1; exact protocol coding is required.
    _need(isinstance(value, (str, int, float)) and not isinstance(value, bool), "INVALID_EVENT_CODE")
    if isinstance(value, float):
        _need(math.isfinite(value), "INVALID_EVENT_CODE")
    return ("str" if isinstance(value, str) else "number", value)


def _coefficient_term(covariate, level=None):
    """Display labels share one checked namespace; never use them as row keys."""
    if covariate["type"] == "numeric":
        return covariate["name"]
    return covariate["name"] + "[" + str(level) + " vs " + str(covariate["reference"]) + "]"


def _validate(rows, spec):
    _need(isinstance(spec, dict), "SPEC_REQUIRED")
    method = spec.get("method")
    _need(method in {"kaplan_meier", "cox_ph", "aalen_johansen", "cause_specific_cox"}, "UNSUPPORTED_SURVIVAL_METHOD")
    for unsupported in ("left_truncation", "time_varying_covariates", "recurrent_events", "interval_censoring", "weights", "strata", "cluster"):
        _need(not spec.get(unsupported), "UNSUPPORTED_" + unsupported.upper())
    _need(spec.get("independent_subjects") is True, "INDEPENDENT_SUBJECTS_REQUIRED")
    _need(spec.get("missing_policy") == "complete_case", "EXPLICIT_COMPLETE_CASE_REQUIRED")
    for field in ("subject_id", "time", "status", "time_unit", "time_zero_definition", "event_definition", "censoring_definition"):
        _need(isinstance(spec.get(field), str) and bool(spec[field].strip()), "MISSING_" + field.upper())
    keys = [spec["subject_id"], spec["time"], spec["status"]]
    _need(len(set(keys)) == 3, "TIME_STATUS_AND_ID_MUST_DIFFER")
    _need("event_code" in spec and "censor_code" in spec, "EVENT_AND_CENSOR_CODES_REQUIRED")
    target = _code(spec["event_code"])
    censor = _code(spec["censor_code"])
    _need(target != censor, "EVENT_CENSOR_CODE_COLLISION")
    competing = spec.get("competing_codes", [])
    _need(isinstance(competing, list), "COMPETING_CODES_LIST_REQUIRED")
    competing = [_code(v) for v in competing]
    _need(len(set(competing)) == len(competing) and target not in competing and censor not in competing, "COMPETING_CODE_COLLISION")
    if method in {"aalen_johansen", "cause_specific_cox"}:
        _need(bool(competing), "COMPETING_EVENT_CODES_REQUIRED")
        definitions = spec.get("competing_event_definitions")
        _need(isinstance(definitions, list) and len(definitions) == len(competing), "COMPETING_EVENT_DEFINITIONS_REQUIRED")
        _need(all(isinstance(v, str) and v.strip() for v in definitions), "COMPETING_EVENT_DEFINITIONS_REQUIRED")
    else:
        _need(not competing, "USE_COMPETING_RISK_METHOD_FOR_COMPETING_EVENTS")
    covariates = spec.get("covariates", [])
    _need(isinstance(covariates, list), "COVARIATE_LIST_REQUIRED")
    if method in {"cox_ph", "cause_specific_cox"}:
        _need(bool(covariates), "COX_COVARIATES_REQUIRED")
        _need(spec.get("ties", "breslow") == "breslow", "ONLY_BRESLOW_TIES_SUPPORTED")
    else:
        _need(not covariates, "COVARIATES_REQUIRE_COX_METHOD")
    covariate_names = []
    for cov in covariates:
        _need(isinstance(cov, dict) and isinstance(cov.get("name"), str) and cov["name"].strip(), "COVARIATE_SPEC_REQUIRED")
        _need(cov.get("type") in {"numeric", "category"}, "UNSUPPORTED_COVARIATE_TYPE")
        _need(cov.get("available_at_time_zero") is True, "COVARIATE_TIMING_UNCONFIRMED")
        covariate_names.append(cov["name"])
        if cov["type"] == "category":
            levels = cov.get("levels")
            _need(isinstance(levels, list) and len(levels) >= 2, "CATEGORY_LEVELS_REQUIRED")
            encoded_levels = [_code(v) for v in levels]
            _need(len(set(encoded_levels)) == len(levels), "DUPLICATE_CATEGORY_LEVEL")
            _need("reference" in cov and _code(cov["reference"]) in encoded_levels, "CATEGORY_REFERENCE_REQUIRED")
    _need(len(set(covariate_names)) == len(covariate_names), "DUPLICATE_COVARIATE")
    _need(not set(covariate_names).intersection(keys), "OUTCOME_TIME_OR_ID_AS_COVARIATE")
    # User names and category values can contain our display punctuation. Also,
    # declared numeric and string levels remain distinct but may render alike.
    # Reject ambiguous coefficient labels before reading data or fitting; never
    # overwrite a caller column or silently merge two design columns by name.
    coefficient_terms = []
    for cov in covariates:
        if cov["type"] == "numeric":
            coefficient_terms.append(_coefficient_term(cov))
        else:
            coefficient_terms.extend(_coefficient_term(cov, level) for level in cov["levels"] if _code(level) != _code(cov["reference"]))
    _need(len(set(coefficient_terms)) == len(coefficient_terms), "AMBIGUOUS_COEFFICIENT_TERM_NAMES")
    columns = keys + covariate_names
    _need(isinstance(rows, list) and bool(rows), "EMPTY_DATA")
    _need(all(isinstance(row, dict) and all(k in row for k in columns) for row in rows), "REQUIRED_COLUMN_ABSENT")
    identifiers = [row[spec["subject_id"]] for row in rows]
    _need(all(not _missing(v) for v in identifiers), "MISSING_SUBJECT_ID")
    try:
        _need(len(set((_code(v)) for v in identifiers)) == len(rows), "REPEATED_SUBJECT_UNSUPPORTED")
    except TypeError:
        raise SurvivalBlocked("INVALID_SUBJECT_ID") from None
    kept, missing_by_field = [], Counter()
    allowed_codes = {target, censor, *competing}
    for row in rows:
        absent = [k for k in columns[1:] if _missing(row[k])]
        # Validate every observed event/time/category even on an otherwise
        # incomplete row; malformed source values are not silently deleted.
        if not _missing(row[spec["time"]]):
            _need(_number(row[spec["time"]]) > 0, "FOLLOWUP_MUST_BE_POSITIVE")
        if not _missing(row[spec["status"]]):
            _need(_code(row[spec["status"]]) in allowed_codes, "UNDECLARED_EVENT_STATUS")
        for cov in covariates:
            value = row[cov["name"]]
            if not _missing(value):
                if cov["type"] == "numeric":
                    _number(value)
                else:
                    _need(_code(value) in {_code(v) for v in cov["levels"]}, "UNDECLARED_CATEGORY")
        missing_by_field.update(absent)
        if not absent:
            kept.append(row)
    _need(bool(kept), "NO_COMPLETE_OBSERVATIONS")
    time = [_number(row[spec["time"]]) for row in kept]
    status = [0 if _code(row[spec["status"]]) == censor else 1 if _code(row[spec["status"]]) == target else 2 + competing.index(_code(row[spec["status"]])) for row in kept]
    grid = spec.get("evaluation_times")
    _need(isinstance(grid, list) and bool(grid), "PRESPECIFIED_EVALUATION_TIMES_REQUIRED")
    grid = [_number(t) for t in grid]
    _need(grid == sorted(set(grid)) and all(0 <= t <= max(time) for t in grid), "EVALUATION_GRID_OUTSIDE_OBSERVED_SUPPORT")
    return method, kept, time, status, grid, covariates, dict(missing_by_field)


def _curve(time, status, grid, cause_count, confidence=0.95):
    """KM/AJ event-before-censor convention at tied observed times."""
    import numpy as np
    from scipy.stats import norm

    time = np.asarray(time, dtype=float)
    status = np.asarray(status, dtype=int)
    event_times = np.unique(time[status > 0])
    survival, greenwood = 1.0, 0.0
    cif = np.zeros(cause_count)
    points = []
    critical = float(norm.ppf((1 + confidence) / 2))
    for current in event_times:
        at_risk = int(np.sum(time >= current))
        counts = np.array([np.sum((time == current) & (status == cause)) for cause in range(1, cause_count + 1)], dtype=float)
        all_events = float(counts.sum())
        before = survival
        cif += before * counts / at_risk
        survival *= 1.0 - all_events / at_risk
        if at_risk > all_events:
            greenwood += all_events / (at_risk * (at_risk - all_events))
        points.append((float(current), survival, cif.copy(), greenwood))
    result = []
    cursor = -1
    for current in grid:
        while cursor + 1 < len(points) and points[cursor + 1][0] <= current:
            cursor += 1
        if cursor < 0:
            value, cumulative, variance_term = 1.0, np.zeros(cause_count), 0.0
        else:
            _, value, cumulative, variance_term = points[cursor]
        if value <= 0 or value >= 1:
            interval = [float(value), float(value)]
        else:
            loglog = math.log(-math.log(value))
            se = math.sqrt(variance_term) / abs(math.log(value))
            interval = [math.exp(-math.exp(loglog + critical * se)), math.exp(-math.exp(loglog - critical * se))]
        result.append({
            "time": float(current), "at_risk_before_time": int(np.sum(time >= current)),
            "event_free_probability": float(value),
            "event_free_ci95": interval,
            "cumulative_incidence": [float(v) for v in cumulative],
        })
    return result


def _aj_bootstrap(time, status, grid, cause_count, spec):
    import numpy as np

    repeats = spec.get("bootstrap_replicates", 0)
    _need(isinstance(repeats, int) and not isinstance(repeats, bool) and (repeats == 0 or 20 <= repeats <= 2000), "BOOTSTRAP_REPLICATES_MUST_BE_ZERO_OR_20_TO_2000")
    if not repeats:
        return {"method": "none", "requested": 0, "attempted": 0, "valid": 0, "intervals": None}
    _need(isinstance(spec.get("seed"), int) and not isinstance(spec.get("seed"), bool) and spec["seed"] >= 0, "BOOTSTRAP_SEED_REQUIRED")
    _need(len(time) >= 2, "BOOTSTRAP_REQUIRES_TWO_INDEPENDENT_SUBJECTS")
    rng = np.random.default_rng(spec["seed"])
    time, status = np.asarray(time), np.asarray(status)
    values = []
    for _ in range(repeats):
        selected = rng.integers(0, len(time), size=len(time))
        curves = _curve(time[selected], status[selected], grid, cause_count)
        values.append([point["cumulative_incidence"] for point in curves])
    intervals = np.quantile(np.asarray(values), [0.025, 0.975], axis=0)
    return {
        "method": "independent_subject_percentile_bootstrap_pointwise_95pct",
        "requested": repeats, "attempted": repeats, "valid": repeats,
        "seed": spec["seed"], "intervals": intervals.tolist(),
        "limitations": "Exploratory pointwise percentile intervals; no simultaneous coverage or sparse-event reliability guarantee. No resampling until success.",
    }


def _cox(kept, time, status, covariates, spec):
    import numpy as np
    from scipy.optimize import linprog
    from scipy.stats import spearmanr
    from statsmodels.duration.hazard_regression import PHReg

    events = int(sum(v == 1 for v in status))
    columns, names = [], []
    for cov in covariates:
        if cov["type"] == "numeric":
            columns.append([_number(row[cov["name"]]) for row in kept])
            names.append(_coefficient_term(cov))
        else:
            reference = _code(cov["reference"])
            for level in cov["levels"]:
                if _code(level) != reference:
                    columns.append([float(_code(row[cov["name"]]) == _code(level)) for row in kept])
                    names.append(_coefficient_term(cov, level))
    x = np.asarray(columns, dtype=float).T
    parameters = x.shape[1]
    counts = {"n_used": len(kept), "target_events": events, "parameters": parameters,
              "events_per_parameter": events / parameters, "event_per_parameter_formula": "target_events / non_intercept_design_parameters"}

    def blocked(reason):
        return {**counts, "status": "NON_ESTIMABLE", "reason": reason, "terms": [], "ph_assumption_verified": False}

    guard = spec.get("min_events_per_parameter", 10)
    _need(isinstance(guard, (int, float)) and not isinstance(guard, bool) and math.isfinite(guard) and guard >= 10, "COX_EVENT_GUARD_AT_LEAST_10_REQUIRED")
    if len(kept) <= parameters + 2 or events < max(20, guard * parameters):
        return blocked("INSUFFICIENT_EVENTS_OR_RESIDUAL_INFORMATION")
    scale = x.std(axis=0)
    if np.any(scale <= 0):
        return blocked("CONSTANT_OR_UNOBSERVED_COVARIATE_LEVEL")
    x = (x - x.mean(axis=0)) / scale
    if np.linalg.matrix_rank(x) != parameters:
        return blocked("RANK_DEFICIENT_DESIGN")
    t, event = np.asarray(time), (np.asarray(status) == 1).astype(int)
    # Cox finite-MLE existence: a nonzero bounded direction with every
    # event-minus-risk-set contrast >= 0 and some > 0 gives monotone likelihood.
    # Use exact contrasts for moderate clinical tables; larger problems require
    # another checked solver rather than trusting convergence alone.
    event_indices = np.flatnonzero(event)
    contrast_n = sum(int(np.sum(t >= t[i])) for i in event_indices)
    if contrast_n > 2_000_000:
        return blocked("MLE_EXISTENCE_CHECK_RESOURCE_LIMIT")
    contrasts = np.vstack([x[i] - x[t >= t[i]] for i in event_indices])
    objective = contrasts.sum(axis=0)
    norm = float(np.max(np.abs(objective)))
    if norm > 1e-10:
        existence = linprog(-objective / norm, A_ub=-contrasts, b_ub=np.zeros(len(contrasts)), bounds=[(-1, 1)] * parameters, method="highs")
        if not existence.success:
            return blocked("MLE_EXISTENCE_CHECK_INCONCLUSIVE")
        if -float(existence.fun) > 1e-7:
            return blocked("MONOTONE_LIKELIHOOD")
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = PHReg(t, x, status=event, ties="breslow", missing="raise")
            fit = model.fit(disp=0, maxiter=200, tol=1e-9)
        if caught:
            return blocked("COX_FIT_WARNING")
        beta, se = np.asarray(fit.params), np.asarray(fit.bse)
        information = -model.hessian(beta)
        score = model.score(beta)
        if not np.isfinite(beta).all() or not np.isfinite(se).all() or np.any(se <= 0) or np.linalg.cond(information) > 1e10 or np.max(np.abs(score)) > 1e-5:
            return blocked("UNSTABLE_INFORMATION_OR_NONCONVERGENCE")
        beta, se = beta / scale, se / scale
        if np.any(np.abs(beta) + 1.959963984540054 * se > 700):
            return blocked("HAZARD_RATIO_INTERVAL_OVERFLOW")
        terms = []
        for name, coefficient, standard_error, pvalue in zip(names, beta, se, fit.pvalues):
            terms.append({"term": name, "log_hazard_ratio": float(coefficient), "standard_error": float(standard_error),
                          "hazard_ratio": float(np.exp(coefficient)), "hr_ci95": [float(np.exp(coefficient - 1.959963984540054 * standard_error)), float(np.exp(coefficient + 1.959963984540054 * standard_error))],
                          "p": float(pvalue), "unit": "per original covariate unit or declared category contrast"})
        residuals = np.asarray(fit.schoenfeld_residuals)
        trends = []
        for j, name in enumerate(names):
            observed = np.isfinite(residuals[:, j]) & (event == 1)
            rho = None
            if observed.sum() >= 3 and len(np.unique(t[observed])) >= 2 and np.std(residuals[observed, j]) > 0:
                rho = float(spearmanr(np.log(t[observed]), residuals[observed, j]).statistic)
                if not math.isfinite(rho):
                    rho = None
            trends.append({"term": name, "schoenfeld_log_time_spearman": rho})
        return {**counts, "status": "ESTIMABLE_REVIEW_PENDING", "ties": "breslow", "covariance": "model_based_observed_information_independent_subjects",
                "terms": terms, "max_abs_score": float(np.max(np.abs(score))), "finite_mle_check": "exact_event_risk_set_contrast_linear_program",
                "ph_trend_diagnostics": trends, "ph_assumption_verified": False,
                "ph_diagnostic_note": "Descriptive correlation only, not a formal PH test or proof of proportional hazards. Inspect scientific time patterns and residual plots; prespecify alternatives when PH is doubtful.",
                "estimand": "cause_specific_hazard_ratio" if spec["method"] == "cause_specific_cox" else "hazard_ratio",
                "limitations": "HR is conditional association, not a risk ratio, CIF ratio, treatment effect, or causal effect. Functional form and independent noninformative censoring remain assumptions."}
    except (ValueError, ArithmeticError, np.linalg.LinAlgError, RuntimeError):
        return blocked("COX_FIT_FAILED")


def analyze(rows: list[dict], spec: dict) -> dict:
    """Compute reviewed protocol-defined right-censored survival aggregates.

    Invalid design/data returns BLOCKED_METHOD with a stable reason. Unestimable
    Cox inference keeps valid nonparametric descriptions and exact event counts.
    No identifiers, raw records, per-person residuals or model predictions return.
    """
    try:
        method, kept, time, status, grid, covariates, missing = _validate(rows, spec)
        competing_count = len(spec.get("competing_codes", []))
        cause_count = 1 + competing_count
        counts = Counter(status)
        result = {
            "status": "COMPUTED_REVIEW_PENDING", "method": method,
            "n_total": len(rows), "n_used": len(kept), "n_excluded_missing": len(rows) - len(kept), "missing_by_field": missing,
            "target_events": counts[1], "censored": counts[0],
            "competing_events": [{"code": code, "definition": definition, "n": counts[i + 2]} for i, (code, definition) in enumerate(zip(spec.get("competing_codes", []), spec.get("competing_event_definitions", [])))],
            "time_unit": spec["time_unit"], "time_zero_definition": spec["time_zero_definition"],
            "event_definition": spec["event_definition"], "censoring_definition": spec["censoring_definition"],
            "missing_method": "complete_case_for_all_selected_analysis_fields_no_imputation",
            "curves": _curve(time, status, grid, cause_count),
            "curve_method": "Aalen-Johansen cumulative incidence and event-free probability" if competing_count else "Kaplan-Meier survival with Greenwood log-log pointwise 95% intervals",
            "ties": "events_processed_before_censoring_at_same_time_risk_set_includes_both",
            "curve_support": "prespecified_grid_within_observed_followup_no_extrapolation",
            "event_free_interval_note": "Pointwise log-log Greenwood interval for freedom from any declared event; boundary values give descriptive zero-width endpoints, not certainty.",
            "assumptions": ["one independent subject per row", "time zero and eligibility aligned", "right censoring only", "independent censoring conditional on modeled covariates when applicable", "event ascertainment and competing event definitions require clinical review"],
            "unsupported": ["Fine-Gray subdistribution hazards", "left truncation", "time-varying covariates", "recurrent events", "interval censoring", "survey or sampling weights", "patient or site clustered inference", "automatic causal interpretation"],
        }
        if competing_count:
            result["cumulative_incidence_order"] = [{"code": spec["event_code"], "definition": spec["event_definition"]}] + [{"code": code, "definition": definition} for code, definition in zip(spec["competing_codes"], spec["competing_event_definitions"])]
            result["cif_uncertainty"] = _aj_bootstrap(time, status, grid, cause_count, spec)
            result["competing_risk_note"] = "CIF accounts for all declared competing events; 1 minus a target-only KM is not reported as cumulative incidence. Cause-specific Cox removes competing events after their time and is not Fine-Gray."
        else:
            for point in result["curves"]:
                point.pop("cumulative_incidence")
        if method in {"cox_ph", "cause_specific_cox"}:
            result["cox"] = _cox(kept, time, status, covariates, spec)
            if result["cox"]["status"] == "NON_ESTIMABLE":
                result["status"] = "DESCRIPTIVE_ONLY_MODEL_NOT_ESTIMABLE"
        if counts[1] == 0:
            result["target_event_note"] = "No target events observed; do not interpret the curve as proof of no future risk."
        return result
    except SurvivalBlocked as exc:
        return {"status": "BLOCKED_METHOD", "reason": str(exc), "computed": False, "patient_rows_returned": False}

