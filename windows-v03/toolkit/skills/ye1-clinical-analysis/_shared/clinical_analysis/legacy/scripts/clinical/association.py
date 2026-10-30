"""Independent-row clinical association; aggregate results, no I/O or clinical defaults.

Explicit plans only. Ordinary MLE is never silently replaced after separation.
Synthetic verification establishes software behavior, not research validity.
"""
from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
from scipy.optimize import linprog
from scipy.special import expit
from scipy.stats import chi2, f as f_distribution
import statsmodels.api as sm


class AssociationBlocked(ValueError):
    """Fixed diagnostic code; do not include input values or patient identifiers."""


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise AssociationBlocked(code)


def _missing(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value == "") or (
        isinstance(value, (float, np.floating)) and math.isnan(float(value))
    )


def _token(value: Any) -> str:
    _need(isinstance(value, (str, int, float, bool, np.number)), "CATEGORY_SCALAR_REQUIRED")
    if isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)):
        _need(math.isfinite(float(value)), "NONFINITE_VALUE")
        return format(float(value), ".15g")
    return str(value)


def _number(value: Any) -> float:
    _need(not isinstance(value, (bool, np.bool_)), "NUMERIC_VALUE_REQUIRED")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise AssociationBlocked("NUMERIC_VALUE_REQUIRED") from None
    _need(math.isfinite(result), "NONFINITE_VALUE")
    return result


def _declared_category(config: dict) -> tuple[list[str], str]:
    _need(isinstance(config, dict) and set(config) == {"levels", "reference"}, "CATEGORY_CONTRACT_REQUIRED")
    _need(isinstance(config["levels"], list) and len(config["levels"]) >= 2, "CATEGORY_LEVELS_REQUIRED")
    levels = [_token(v) for v in config["levels"]]
    reference = _token(config["reference"])
    _need(len(levels) == len(set(levels)) and reference in levels, "CATEGORY_LEVELS_OR_REFERENCE")
    return levels, reference


def _validate_units(rows: list[dict], spec: dict) -> None:
    _need(isinstance(rows, list) and len(rows) > 0 and all(isinstance(r, dict) for r in rows), "NONEMPTY_TABLE_REQUIRED")
    _need(isinstance(spec.get("row_unit"), str) and bool(spec["row_unit"].strip()), "ROW_UNIT_REQUIRED")
    _need(spec.get("independent") is True, "INDEPENDENT_OBSERVATIONS_REQUIRED")
    key = spec.get("key")
    key = [key] if isinstance(key, str) else key
    _need(isinstance(key, list) and key and all(isinstance(k, str) and k for k in key), "RECORD_KEY_REQUIRED")
    _need(len(key) == len(set(key)), "RECORD_KEY_REQUIRED")
    identities = []
    for row in rows:
        _need(all(k in row and not _missing(row[k]) for k in key), "KEY_MISSING")
        identities.append(tuple(_token(row[k]) for k in key))
    _need(len(identities) == len(set(identities)), "DUPLICATE_RECORD_KEY")
    subject = spec.get("subject_id")
    if subject is not None:
        _need(isinstance(subject, str) and subject, "SUBJECT_FIELD_REQUIRED")
        _need(all(subject in r and not _missing(r[subject]) for r in rows), "SUBJECT_KEY_MISSING")
        _need(len({_token(r[subject]) for r in rows}) == len(rows), "REPEATED_SUBJECT_REQUIRES_OTHER_METHOD")
    _need(not any(k in spec for k in ("weights", "weight", "cluster", "psu", "strata", "repeated")), "COMPLEX_DESIGN_UNSUPPORTED")


def _rcs(x: np.ndarray, config: dict) -> tuple[list[np.ndarray], list[str], dict]:
    _need(isinstance(config, dict) and set(config) == {"method", "knots"}, "SPLINE_CONTRACT_REQUIRED")
    _need(config["method"] == "restricted_cubic", "SPLINE_METHOD_UNSUPPORTED")
    _need(isinstance(config["knots"], list) and 3 <= len(config["knots"]) <= 7, "SPLINE_KNOTS_REQUIRED")
    knots = np.asarray([_number(v) for v in config["knots"]])
    _need(bool(np.all(np.diff(knots) > 0)), "SPLINE_KNOTS_ORDER")
    _need(len(np.unique(x)) >= len(knots), "SPLINE_INSUFFICIENT_DISTINCT_VALUES")
    scale = (knots[-1] - knots[0]) ** 2
    columns = [x]
    with np.errstate(over="ignore", invalid="ignore"):
        for knot in knots[:-2]:
            col = (
                np.maximum(x - knot, 0) ** 3
                - np.maximum(x - knots[-2], 0) ** 3 * (knots[-1] - knot) / (knots[-1] - knots[-2])
                + np.maximum(x - knots[-1], 0) ** 3 * (knots[-2] - knot) / (knots[-1] - knots[-2])
            ) / scale
            columns.append(col)
    _need(all(np.isfinite(v).all() for v in columns), "SPLINE_NONFINITE_DESIGN")
    return columns, ["linear"] + [f"rcs_{i + 1}" for i in range(len(knots) - 2)], {
        "method": "restricted cubic spline; linear tails",
        "knots": knots.tolist(), "nonlinear_parameters": len(knots) - 2,
        "knot_selection": "prespecified; no significance-driven search",
    }


def _separation_check(x: np.ndarray, y: np.ndarray) -> dict:
    # Full-rank affine rescaling preserves separation geometry and avoids unit dependence.
    scaled = x.copy()
    if x.shape[1] > 1:
        scaled[:, 1:] = (x[:, 1:] - x[:, 1:].mean(axis=0)) / x[:, 1:].std(axis=0)
    signed = (2 * y - 1)[:, None] * scaled
    signed /= np.linalg.norm(signed, axis=1, keepdims=True)
    signed = np.unique(signed, axis=0)
    k = signed.shape[1]
    complete = linprog(
        np.r_[np.zeros(k), -1.0],
        A_ub=np.column_stack([-signed, np.ones(len(signed))]), b_ub=np.zeros(len(signed)),
        bounds=[(-1.0, 1.0)] * k + [(0.0, None)], method="highs",
    )
    _need(complete.success, "SEPARATION_CHECK_FAILED")
    if complete.x[-1] > 1e-8:
        raise AssociationBlocked("COMPLETE_SEPARATION")
    quasi = linprog(-signed.mean(axis=0), A_ub=-signed, b_ub=np.zeros(len(signed)),
                    bounds=[(-1.0, 1.0)] * k, method="highs")
    _need(quasi.success, "SEPARATION_CHECK_FAILED")
    _need(-quasi.fun <= 1e-8, "QUASI_COMPLETE_SEPARATION")
    return {"status": "OVERLAP_WITHIN_NUMERICAL_TOLERANCE", "method": "scaled_signed_design_linear_programs", "tolerance": 1e-8}


def _joint_wald(beta: np.ndarray, covariance: np.ndarray, indices: list[int], model: str, residual_df: int) -> dict:
    if not indices:
        return {"status": "NOT_REQUESTED"}
    cov = covariance[np.ix_(indices, indices)]
    _need(np.linalg.matrix_rank(cov) == len(indices) and np.linalg.eigvalsh(cov).min() > 0, "WALD_COVARIANCE_SINGULAR")
    statistic = float(beta[indices] @ np.linalg.solve(cov, beta[indices]))
    _need(math.isfinite(statistic) and statistic >= 0, "WALD_STATISTIC_INVALID")
    q = len(indices)
    if model == "linear":
        return {"method": "joint Wald F (HC3 approximate when selected)", "statistic": statistic / q,
                "df_num": q, "df_denom": residual_df, "p": float(f_distribution.sf(statistic / q, q, residual_df))}
    return {"method": "joint Wald chi-square", "statistic": statistic, "df": q, "p": float(chi2.sf(statistic, q))}


def _fit(rows: list[dict], spec: dict) -> dict:
    counts: dict[str, Any] = {"n_total": len(rows)}
    try:
        model = spec.get("model")
        _need(isinstance(model, str) and model in {"linear", "logistic"}, "MODEL_REQUIRED")
        _need(spec.get("missing") == "complete_case", "EXPLICIT_COMPLETE_CASE_REQUIRED")
        outcome, exposure = spec.get("outcome"), spec.get("exposure")
        covariates = spec.get("covariates")
        _need(isinstance(outcome, str) and outcome and isinstance(exposure, str) and exposure, "OUTCOME_EXPOSURE_REQUIRED")
        _need(isinstance(covariates, list) and all(isinstance(v, str) and v for v in covariates), "COVARIATES_LIST_REQUIRED")
        predictors = [exposure] + list(covariates)
        _need(len(set(predictors)) == len(predictors) and outcome not in predictors, "DUPLICATE_OR_OUTCOME_PREDICTOR")
        categories = spec.get("categorical", {})
        _need(isinstance(categories, dict), "CATEGORY_CONTRACT_REQUIRED")
        category_contracts = {field: _declared_category(config) for field, config in categories.items()}
        subgroup = spec.get("subgroup")
        subgroup_field = None
        if subgroup is not None:
            _need(isinstance(subgroup, dict) and set(subgroup) == {"field", "levels", "reference"}, "SUBGROUP_CONTRACT_REQUIRED")
            subgroup_field = subgroup["field"]
            _need(isinstance(subgroup_field, str) and subgroup_field not in {outcome, exposure}, "SUBGROUP_FIELD_INVALID")
            contract = _declared_category({k: subgroup[k] for k in ("levels", "reference")})
            _need(subgroup_field not in category_contracts or category_contracts[subgroup_field] == contract, "SUBGROUP_CATEGORY_CONFLICT")
            category_contracts[subgroup_field] = contract
            if subgroup_field not in predictors:
                predictors.append(subgroup_field)
        # Source fields are never renamed or overwritten. Ambiguous model terms
        # must be resolved in a reviewed mapping before estimates reach plots.
        _need(all(field.strip().casefold() not in {"intercept", "(intercept)"} for field in predictors),
              "RESERVED_INTERCEPT_TERM_NAME")
        used = [outcome] + predictors
        _need(all(all(v in row for v in used) for row in rows), "MODEL_FIELD_MISSING")
        counts["missing_by_field"] = {v: sum(_missing(row[v]) for row in rows) for v in used}
        # Invalid observed values are not reclassified as missing or silently excluded.
        for row in rows:
            for field in predictors:
                if not _missing(row[field]):
                    if field in category_contracts:
                        _need(_token(row[field]) in category_contracts[field][0], "UNDECLARED_CATEGORY")
                    else:
                        _number(row[field])
        if model == "logistic":
            _need("event" in spec and "non_event" in spec, "BINARY_EVENT_CODING_REQUIRED")
            event, non_event = _token(spec["event"]), _token(spec["non_event"])
            _need(event != non_event, "BINARY_EVENT_CODING_REQUIRED")
            _need(all(_missing(r[outcome]) or _token(r[outcome]) in {event, non_event} for r in rows), "UNDECLARED_OUTCOME_CODE")
        else:
            for row in rows:
                if not _missing(row[outcome]):
                    _number(row[outcome])
        complete = [r for r in rows if all(not _missing(r[field]) for field in used)]
        n = len(complete)
        counts.update(n_used=n, n_excluded_missing=len(rows) - n,
                      missing_method="complete case; missingness assumptions remain unverified")
        _need(n >= 5, "INSUFFICIENT_COMPLETE_OBSERVATIONS")
        y = np.asarray([float(_token(r[outcome]) == event) if model == "logistic" else _number(r[outcome]) for r in complete])
        columns, names, ranges = [np.ones(n)], ["intercept"], {}
        exposure_indices, nonlinear_indices, subgroup_indices = [], [], []
        nonlinear = None
        for field in predictors:
            start = len(columns)
            if field in category_contracts:
                levels, reference = category_contracts[field]
                tokens = [_token(r[field]) for r in complete]
                _need(all(level in tokens for level in levels), "CATEGORY_LEVEL_ABSENT_FROM_ANALYSIS")
                for level in levels:
                    if level != reference:
                        columns.append(np.asarray([float(v == level) for v in tokens]))
                        names.append(f"{field}[{level} vs {reference}]")
            else:
                x = np.asarray([_number(r[field]) for r in complete])
                _need(float(np.ptp(x)) > 0, "CONSTANT_PREDICTOR")
                ranges[field] = {"min": float(x.min()), "max": float(x.max())}
                if field == exposure and spec.get("nonlinear") is not None:
                    new_columns, suffixes, nonlinear = _rcs(x, spec["nonlinear"])
                    columns.extend(new_columns)
                    names.extend([field if s == "linear" else f"{field}:{s}" for s in suffixes])
                    nonlinear_indices = list(range(start + 1, len(columns)))
                else:
                    columns.append(x)
                    names.append(field)
            if field == exposure:
                exposure_indices = list(range(start, len(columns)))
            if field == subgroup_field:
                subgroup_indices = list(range(start, len(columns)))
        _need(not (exposure in category_contracts and spec.get("nonlinear") is not None), "SPLINE_REQUIRES_NUMERIC_EXPOSURE")
        interaction_indices, nonlinear_interaction_indices = [], []
        for e in exposure_indices:
            for g in subgroup_indices:
                interaction_indices.append(len(columns))
                if e in nonlinear_indices:
                    nonlinear_interaction_indices.append(len(columns))
                columns.append(columns[e] * columns[g])
                names.append(names[e] + " * " + names[g])
        normalized_names = [name.strip().casefold() for name in names]
        _need(len(normalized_names) == len(set(normalized_names)), "DERIVED_TERM_NAME_COLLISION")
        x = np.column_stack(columns)
        p = x.shape[1]
        counts["predictor_parameters"] = p - 1
        if model == "logistic":
            counts.update(events=int(y.sum()), non_events=int(n - y.sum()),
                          effective_events_per_parameter=float(min(y.sum(), n - y.sum()) / (p - 1)))
        _need(n > p + 2, "INSUFFICIENT_RESIDUAL_DEGREES")
        scaled_design = x / np.linalg.norm(x, axis=0)
        _need(np.isfinite(x).all() and np.linalg.matrix_rank(scaled_design) == p, "RANK_DEFICIENT_DESIGN")
        _need(np.linalg.cond(scaled_design) < 1e8, "ILL_CONDITIONED_DESIGN")
        covariance_type = spec.get("covariance")
        separation = None
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if model == "linear":
                _need(isinstance(covariance_type, str) and covariance_type in {"classical", "HC3"}, "LINEAR_COVARIANCE_REQUIRED")
                _need(float(np.ptp(y)) > 0, "CONSTANT_OUTCOME")
                fit = sm.OLS(y, x).fit(cov_type="nonrobust" if covariance_type == "classical" else "HC3", use_t=True)
                _need(float(fit.ssr) > 64 * np.finfo(float).eps * float(np.sum((y - y.mean()) ** 2)), "ZERO_RESIDUAL_VARIANCE")
                diagnostics = {"r_squared": float(fit.rsquared), "residual_sd": float(math.sqrt(fit.ssr / (n - p)))}
            else:
                _need(isinstance(covariance_type, str) and covariance_type in {"model", "HC0"}, "LOGISTIC_COVARIANCE_REQUIRED")
                _need(len(np.unique(y)) == 2, "SINGLE_OUTCOME_CLASS")
                separation = _separation_check(x, y)
                _need(counts["effective_events_per_parameter"] >= 10, "SPARSE_EFFECTIVE_EVENTS_PER_PARAMETER")
                fit = sm.Logit(y, x, check_rank=False).fit(disp=False, maxiter=200, tol=1e-10,
                                                        cov_type="nonrobust" if covariance_type == "model" else "HC0")
                _need(bool(fit.mle_retvals.get("converged")), "LOGISTIC_NONCONVERGENCE")
                probabilities = expit(x @ np.asarray(fit.params))
                information = x.T @ ((probabilities * (1 - probabilities))[:, None] * x)
                _need(np.isfinite(information).all() and np.linalg.cond(information) < 1e12, "UNSTABLE_LOGISTIC_INFORMATION")
                _need(float(np.max(np.abs(x.T @ (probabilities - y)))) < 1e-4, "LOGISTIC_GRADIENT_NOT_CONVERGED")
                diagnostics = {"max_abs_gradient": float(np.max(np.abs(x.T @ (probabilities - y)))), "separation_check": separation}
        _need(not caught, "ESTIMATOR_WARNING_REQUIRES_REVIEW")
        beta, se, ci, pv = (np.asarray(fit.params), np.asarray(fit.bse), np.asarray(fit.conf_int()), np.asarray(fit.pvalues))
        covariance = np.asarray(fit.cov_params())
        _need(all(np.isfinite(z).all() for z in (beta, se, ci, pv, covariance)) and bool(np.all(se > 0)), "INVALID_INFERENCE")
        coefficients = []
        for i, name in enumerate(names):
            record = {"term": name, "estimate": float(beta[i]), "standard_error": float(se[i]),
                      "ci95": ci[i].tolist(), "p": float(pv[i]),
                      "scale": "log odds" if model == "logistic" else "outcome units"}
            if model == "logistic":
                _need(ci[i, 1] < 700 and ci[i, 0] > -700, "ODDS_RATIO_INTERVAL_OVERFLOW")
                record.update(odds_ratio=float(np.exp(beta[i])), or_ci95=np.exp(ci[i]).tolist())
            coefficients.append(record)
        result = {"status": "COMPUTED_REVIEW_PENDING", "model": model, **counts,
                  "method": "ordinary binomial logit MLE" if model == "logistic" else "ordinary least squares",
                  "covariance": covariance_type, "coefficients": coefficients, "diagnostics": diagnostics,
                  "nonlinear": nonlinear, "nonlinearity_test": _joint_wald(beta, covariance, nonlinear_indices + nonlinear_interaction_indices, model, n - p),
                  "interaction_test": _joint_wald(beta, covariance, interaction_indices, model, n - p),
                  "exposure_test": _joint_wald(beta, covariance, exposure_indices + interaction_indices, model, n - p),
                  "numeric_analysis_ranges": ranges,
                  "limitations": ["Conditional association; no causal or clinical-validity claim.",
                                  "Independent observations, prespecified model and complete-case assumptions require research review.",
                                  "No automatic variable selection, repeated-measure, complex-sample or missing-data correction."]}
        if subgroup_field:
            result["subgroup"] = {"field": subgroup_field, "n_used_by_level": {
                level: sum(_token(r[subgroup_field]) == level for r in complete) for level in category_contracts[subgroup_field][0]},
                "interpretation": "Use the joint interaction test; different within-group P values do not establish heterogeneity."}
        if nonlinear_indices:
            result["nonlinearity_test"]["scope"] = "all main nonlinear exposure terms and nonlinear exposure-by-subgroup interactions"
        if model == "logistic":
            result["event_coding"] = {"event": spec["event"], "non_event": spec["non_event"]}
        return result
    except AssociationBlocked as exc:
        return {"status": "BLOCKED_ESTIMATION", "reason": str(exc), **counts, "estimates": None,
                "method_not_silently_replaced": True}
    except (np.linalg.LinAlgError, ArithmeticError, RuntimeError, ValueError):
        return {"status": "BLOCKED_ESTIMATION", "reason": "NUMERICAL_ESTIMATION_FAILED", **counts,
                "estimates": None, "method_not_silently_replaced": True}


def _subset(rows: list[dict], conditions: list[dict]) -> list[dict]:
    _need(isinstance(conditions, list) and conditions, "SENSITIVITY_FILTER_REQUIRED")
    selected = list(rows)
    for condition in conditions:
        _need(isinstance(condition, dict) and set(condition) == {"field", "op", "value"}, "SENSITIVITY_FILTER_SCHEMA")
        field, op, value = condition["field"], condition["op"], condition["value"]
        _need(isinstance(field, str) and all(field in row for row in rows), "SENSITIVITY_FIELD_MISSING")
        _need(isinstance(op, str) and op in {"eq", "ne", "lt", "le", "gt", "ge", "in"}, "SENSITIVITY_OPERATOR_UNSUPPORTED")
        if op in {"lt", "le", "gt", "ge"}:
            threshold = _number(value)
        elif op == "in":
            _need(isinstance(value, list) and bool(value), "SENSITIVITY_VALUES_REQUIRED")
            allowed = {_token(v) for v in value}
        def keep(row: dict) -> bool:
            if _missing(row[field]):
                return False
            if op == "eq": return _token(row[field]) == _token(value)
            if op == "ne": return _token(row[field]) != _token(value)
            if op == "in": return _token(row[field]) in allowed
            observed = _number(row[field])
            return {"lt": observed < threshold, "le": observed <= threshold,
                    "gt": observed > threshold, "ge": observed >= threshold}[op]
        selected = [row for row in selected if keep(row)]
    return selected


def analyze(rows: list[dict], spec: dict) -> dict:
    """Run a prespecified association and optional sensitivities; never mutate inputs."""
    try:
        _need(isinstance(spec, dict), "SPEC_OBJECT_REQUIRED")
        _validate_units(rows, spec)
        sensitivities = spec.get("sensitivity", [])
        _need(isinstance(sensitivities, list), "SENSITIVITY_LIST_REQUIRED")
        labels = []
        for item in sensitivities:
            _need(isinstance(item, dict) and set(item) <= {"label", "rationale", "where", "covariates", "nonlinear", "covariance"}, "SENSITIVITY_SCHEMA")
            _need(isinstance(item.get("label"), str) and item["label"].strip() and isinstance(item.get("rationale"), str) and item["rationale"].strip(), "SENSITIVITY_PROVENANCE_REQUIRED")
            labels.append(item["label"])
        _need(len(labels) == len(set(labels)), "SENSITIVITY_LABEL_DUPLICATE")
    except (AssociationBlocked, TypeError) as exc:
        return {"status": "BLOCKED_INPUT", "reason": str(exc) if isinstance(exc, AssociationBlocked) else "INVALID_SPEC_TYPE", "estimates": None}
    result = _fit(rows, spec)
    result["family"] = "association"
    result["row_unit"] = spec["row_unit"]
    result["patient_rows_returned"] = False
    result["sensitivity"] = []
    for item in sensitivities:
        try:
            subset = _subset(rows, item.get("where"))
            alternate = {**spec, **{k: item[k] for k in ("covariates", "nonlinear", "covariance") if k in item}}
            record = _fit(subset, alternate)
            record.update(label=item["label"], rationale=item["rationale"], n_before_filter=len(rows), n_after_filter=len(subset))
        except AssociationBlocked as exc:
            record = {"status": "BLOCKED_INPUT", "reason": str(exc), "label": item["label"], "estimates": None}
        result["sensitivity"].append(record)
    return result
