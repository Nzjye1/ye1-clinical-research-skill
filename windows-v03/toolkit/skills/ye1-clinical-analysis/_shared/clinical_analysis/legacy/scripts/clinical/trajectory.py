"""Explicit-time rule trajectories, slope summaries and exploratory feature clusters.

Only aggregate outputs leave this API. Latent-class/GBTM and mixed longitudinal
models are deliberately unsupported: feature clustering does not estimate them.
"""
from __future__ import annotations

import math
from collections import defaultdict


def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _numeric(value, *, missing=False):
    if missing and (value is None or value == ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("INVALID_TRAJECTORY_NUMBER") from None
    _need(math.isfinite(number), "NONFINITE_TRAJECTORY_NUMBER")
    return number


def _finite_float(value):
    number = float(value)
    _need(math.isfinite(number), "NONFINITE_TRAJECTORY_DERIVED_VALUE")
    return number


def _quantiles(values, np):
    if not values:
        return {"n": 0, "median": None, "q25": None, "q75": None}
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        return {"n": len(values), "median": _finite_float(np.median(values)), "q25": _finite_float(np.quantile(values, .25)), "q75": _finite_float(np.quantile(values, .75))}


def _prepare(rows, spec):
    _need(isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows), "NONEMPTY_TRAJECTORY_ROWS_REQUIRED")
    role_names = ["subject_id", "time", "value", "availability_time"]
    _need(all(isinstance(spec.get(k), str) and spec[k] for k in role_names), "EXPLICIT_TRAJECTORY_ROLES_REQUIRED")
    _need(len({spec["subject_id"], spec["time"], spec["value"]}) == 3, "TRAJECTORY_ROLE_COLLISION")
    _need(spec["availability_time"] != spec["value"] and spec["availability_time"] != spec["subject_id"], "TRAJECTORY_ROLE_COLLISION")
    _need(all(isinstance(spec.get(k), str) and spec[k].strip() for k in ["time_zero", "time_unit", "value_unit"]), "TRAJECTORY_TIME_ZERO_AND_UNITS_REQUIRED")
    landmark = _numeric(spec.get("landmark"))
    windows = spec.get("windows")
    _need(isinstance(windows, list) and 2 <= len(windows) <= 24, "AT_LEAST_TWO_TRAJECTORY_WINDOWS_REQUIRED")
    parsed = []
    for window in windows:
        _need(isinstance(window, list) and len(window) == 2, "INVALID_TRAJECTORY_WINDOW")
        left, right = [_numeric(v) for v in window]
        _need(left < right and right <= landmark, "WINDOW_AFTER_LANDMARK_OR_EMPTY")
        if parsed:
            _need(math.isclose(parsed[-1][1], left, abs_tol=1e-10, rel_tol=0), "OVERLAPPING_OR_NONCONTIGUOUS_WINDOWS")
        parsed.append([left, right])
    _need(math.isclose(parsed[-1][1], landmark, abs_tol=1e-10, rel_tol=0), "WINDOWS_MUST_END_AT_LANDMARK")
    minimum = spec.get("min_observations_per_window")
    _need(type(minimum) is int and minimum >= 1, "MINIMUM_WINDOW_COVERAGE_REQUIRED")
    gap = _numeric(spec.get("min_time_gap"))
    _need(gap > 0, "POSITIVE_MINIMUM_TIME_GAP_REQUIRED")
    ids = [row.get(spec["subject_id"]) for row in rows]
    _need(all(type(v) in {str, int, float} and (type(v) is not float or math.isfinite(v)) for v in ids), "INVALID_TRAJECTORY_SUBJECT_ID_ENCODING")
    _need(len({type(v) for v in ids}) == 1, "MIXED_SUBJECT_ID_ENCODING")
    flow = {"input_rows_n": len(rows), "missing_value_rows_n": 0, "outside_observation_window_rows_n": 0,
            "unavailable_by_landmark_rows_n": 0, "exact_duplicate_rows_removed_n": 0}
    observations = defaultdict(dict)
    subjects = set()
    for row in rows:
        _need(all(spec[k] in row for k in role_names), "TRAJECTORY_FIELD_ABSENT")
        subject = row[spec["subject_id"]]
        _need(subject is not None and str(subject).strip(), "TRAJECTORY_SUBJECT_ID_MISSING")
        subject = str(subject)
        subjects.add(subject)
        time = _numeric(row[spec["time"]])
        availability = _numeric(row[spec["availability_time"]])
        _need(availability >= time, "AVAILABILITY_PRECEDES_MEASUREMENT")
        if not parsed[0][0] <= time <= landmark:
            flow["outside_observation_window_rows_n"] += 1
            continue
        if availability > landmark:
            flow["unavailable_by_landmark_rows_n"] += 1
            continue
        if spec.get("unit_column"):
            _need(row.get(spec["unit_column"]) == spec["value_unit"], "TRAJECTORY_UNIT_MISMATCH")
        value = _numeric(row[spec["value"]], missing=True)
        if value is None:
            flow["missing_value_rows_n"] += 1
            continue
        if time in observations[subject]:
            _need(observations[subject][time] == value, "CONFLICTING_DUPLICATE_SUBJECT_TIME")
            flow["exact_duplicate_rows_removed_n"] += 1
            continue
        observations[subject][time] = value
    flow["input_subjects_n"] = len(subjects)
    return observations, subjects, parsed, minimum, gap, flow


def analyze(rows: list[dict], spec: dict) -> dict:
    """Analyze long-form repeated measures without guessing a clinical endpoint.

    Methods: window_median_change, slope_summary, feature_clustering. All require
    explicit subject/time/value/availability roles, time zero, units, contiguous
    observation windows ending at landmark, window coverage and minimum gap.
    Rules additionally require positive change_threshold and round_decimals.
    Feature clustering requires features from baseline/slope/mean/variability and
    a clustering spec with numeric-method hyperparameters.
    """
    method = spec.get("method")
    if method in {"latent_class", "latent_class_trajectory", "gbtm", "lcga", "mixed_model", "latent_growth_mixture"}:
        return {"status": "UNSUPPORTED_METHOD", "method": method,
                "reason": "Latent-class/GBTM/growth-mixture or mixed longitudinal models need a separately validated estimator, time/distribution assumptions, convergence and class stability evidence.",
                "supported": ["window_median_change", "slope_summary", "feature_clustering"],
                "feature_clustering_is_latent_class_model": False}
    _need(method in {"window_median_change", "slope_summary", "feature_clustering"}, "UNSUPPORTED_TRAJECTORY_METHOD")
    if method == "window_median_change":
        threshold = _numeric(spec.get("change_threshold"))
        _need(threshold > 0, "POSITIVE_TRAJECTORY_THRESHOLD_REQUIRED")
        decimals = spec.get("round_decimals")
        _need(type(decimals) is int and 6 <= decimals <= 12, "TRAJECTORY_ROUND_DECIMALS_MUST_BE_6_TO_12")
        minimum_group = spec.get("min_group_size", 2)
        _need(type(minimum_group) is int and minimum_group >= 2, "INVALID_TRAJECTORY_MIN_GROUP_SIZE")
    else:
        min_points = spec.get("min_observations_for_slope")
        _need(type(min_points) is int and min_points >= 3, "SLOPE_REQUIRES_AT_LEAST_THREE_TIMES")
    observations, subjects, windows, minimum, gap, flow = _prepare(rows, spec)
    import numpy as np
    profiles = {}
    coverage_excluded = 0
    gap_excluded = 0
    too_few_for_slope = 0
    for subject in sorted(subjects):
        points = sorted(observations[subject].items())
        window_values, window_times = [], []
        for index, (left, right) in enumerate(windows):
            selected = [(t, v) for t, v in points if left <= t and (t < right or (index == len(windows) - 1 and t <= right))]
            if len(selected) < minimum:
                break
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                window_times.append(_finite_float(np.median([t for t, _ in selected])))
                window_values.append(_finite_float(np.median([v for _, v in selected])))
        if len(window_values) != len(windows):
            coverage_excluded += 1
            continue
        if _finite_float(window_times[-1] - window_times[0]) < gap:
            gap_excluded += 1
            continue
        times = np.asarray([t for t, _ in points], dtype=float)
        values = np.asarray([v for _, v in points], dtype=float)
        profile = {"windows": window_values, "delta": _finite_float(window_values[-1] - window_values[0])}
        if method != "window_median_change":
            if len(times) < min_points:
                too_few_for_slope += 1
                continue
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                centered_times = times - times.mean()
                slope = _finite_float(np.dot(centered_times, values - values.mean()) / np.dot(centered_times, centered_times))
                profile.update(baseline=_finite_float(values[0]), slope=slope, mean=_finite_float(values.mean()), variability=_finite_float(values.std(ddof=1)))
        profiles[subject] = profile
    flow.update(coverage_excluded_subjects_n=coverage_excluded, time_gap_excluded_subjects_n=gap_excluded,
                too_few_slope_observations_subjects_n=too_few_for_slope, analyzed_subjects_n=len(profiles))
    common = {"method": method, "time_zero": spec["time_zero"], "time_unit": spec["time_unit"], "value_unit": spec["value_unit"],
              "landmark": float(spec["landmark"]), "windows": windows, "flow": flow, "latent_class_model": False,
              "limitations": ["Time zero, measurement units, availability and clinical meanings must be verified for this project; no ICU-specific definitions are assumed.",
                              "Missing or unavailable observations are excluded, never replaced with zero or carried forward.",
                              "Coverage-based selection can bias summaries; excluded subjects and observation counts are reported.",
                              "Descriptive trajectories and feature clusters do not establish disease phenotype, causal effect or future predictive validity."]}
    if not profiles:
        return {**common, "status": "NON_ESTIMABLE_COVERAGE", "groups": {}, "profiles": []}
    if method == "window_median_change":
        groups = {name: [] for name in ["falling", "stable", "rising"]}
        for profile in profiles.values():
            delta = round(profile["delta"], decimals)
            groups["rising" if delta >= threshold else "falling" if delta <= -threshold else "stable"].append(profile)
        aggregate = []
        for label, members in groups.items():
            for index in range(len(windows)):
                values = [p["windows"][index] for p in members]
                aggregate.append({"group": label, "window_index": index, "n": len(members),
                                  "summary": _quantiles(values, np) if len(members) >= minimum_group else None,
                                  "suppressed_for_group_size": len(members) < minimum_group})
        return {**common, "status": "DESCRIPTIVE_REVIEW_PENDING", "classification_kind": "prespecified_net_change_rules",
                "change_threshold": threshold, "round_decimals": decimals, "groups": {k: len(v) for k, v in groups.items()}, "profiles": aggregate,
                "rule_interpretation": "Rising/falling/stable describe first-to-last window net change only; stable does not imply monotonicity, absence of peaks or clinical stability."}
    slope_summary = _quantiles([p["slope"] for p in profiles.values()], np)
    common["slope_unit"] = spec["value_unit"] + "/" + spec["time_unit"]
    common["slope_summary"] = slope_summary
    if method == "slope_summary":
        return {**common, "status": "DESCRIPTIVE_REVIEW_PENDING", "estimator": "individual OLS slope followed by cohort median/IQR",
                "inferential_model": None, "slope_model_limitation": "No mixed model, individual slope standard errors or population slope confidence interval; irregular informative visits and within-subject errors are not modeled."}
    requested_features = spec.get("features")
    _need(isinstance(requested_features, list) and requested_features and len(set(requested_features)) == len(requested_features) and set(requested_features) <= {"baseline", "slope", "mean", "variability"}, "INVALID_TRAJECTORY_CLUSTER_FEATURES")
    _need(isinstance(spec.get("clustering"), dict), "TRAJECTORY_CLUSTER_SPEC_REQUIRED")
    from .clustering import analyze as cluster
    cluster_spec = dict(spec["clustering"])
    _need(cluster_spec.get("method") in {"kmeans", "gaussian_mixture"}, "TRAJECTORY_REQUIRES_DATA_DRIVEN_FEATURE_CLUSTERING")
    cluster_spec.update(features=requested_features, id_column="_subject", row_unit="independent subject", feature_window="Prespecified repeated-measure windows ending at the declared landmark; no future measurements.")
    cluster_rows = [{"_subject": subject, **{f: profile[f] for f in requested_features}} for subject, profile in profiles.items()]
    result = cluster(cluster_rows, cluster_spec)
    return {**common, "status": result["status"], "analysis_kind": "exploratory_clustering_of_subject_summary_features", "clustering": result,
            "latent_class_boundary": "Static summary-feature clusters are not latent-class trajectories, GBTM, LCGA or growth mixture models; likelihood-based trajectory class inference is unsupported."}
