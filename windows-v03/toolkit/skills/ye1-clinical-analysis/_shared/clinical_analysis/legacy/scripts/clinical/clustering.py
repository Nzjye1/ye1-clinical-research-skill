"""Reproducible exploratory clustering of explicitly selected numeric features.

The public API returns aggregates only. No labels, identifiers, fitted rows or
clinical names inferred from endpoints are included. No latent trajectory model
is implemented here. Model fits use deterministic multi-start initialization.
"""
from __future__ import annotations

import math
import warnings


def _need(condition, reason):
    if not condition:
        raise ValueError(reason)


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("NONNUMERIC_CLUSTER_FEATURE") from None
    _need(math.isfinite(number), "NONFINITE_CLUSTER_FEATURE")
    return number


def _finite_float(value):
    number = float(value)
    _need(math.isfinite(number), "NONFINITE_CLUSTER_DERIVED_VALUE")
    return number


def _validate_units(rows, spec):
    _need(isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows), "NONEMPTY_ROWS_REQUIRED")
    id_column = spec.get("id_column")
    _need(isinstance(id_column, str) and id_column and spec.get("row_unit"), "INDEPENDENT_ROW_UNIT_AND_ID_REQUIRED")
    _need(all(id_column in r and r[id_column] is not None and str(r[id_column]).strip() for r in rows), "MISSING_CLUSTER_UNIT_ID")
    values = [r[id_column] for r in rows]
    _need(all(type(v) in {str, int, float} and (type(v) is not float or math.isfinite(v)) for v in values), "INVALID_CLUSTER_UNIT_ID_ENCODING")
    _need(len({type(v) for v in values}) == 1, "MIXED_CLUSTER_ID_ENCODING")
    ids = [str(r[id_column]) for r in rows]
    _need(len(ids) == len(set(ids)), "REPEATED_CLUSTER_UNIT_REQUIRES_AGGREGATION")
    return id_column


def _fixed_rules(rows, spec):
    rules = spec.get("rules")
    _need(isinstance(rules, list) and rules, "FIXED_RULES_REQUIRED")
    _need(all(isinstance(r, dict) and isinstance(r.get("name"), str) and r["name"] and isinstance(r.get("conditions"), list) and r["conditions"] for r in rules), "INVALID_FIXED_RULE")
    _need(len({r["name"] for r in rules}) == len(rules), "DUPLICATE_RULE_NAME")
    operators = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "==": lambda a, b: a == b}
    counts = {r["name"]: 0 for r in rules}
    unclassified = 0
    for row in rows:
        matches = []
        for rule in rules:
            tests = []
            for condition in rule["conditions"]:
                _need(set(condition) == {"field", "op", "value"} and condition["op"] in operators, "INVALID_FIXED_RULE_CONDITION")
                _need(condition["field"] in row, "FIXED_RULE_FIELD_ABSENT")
                value = _number(row[condition["field"]])
                threshold = _number(condition["value"])
                _need(threshold is not None, "FIXED_RULE_THRESHOLD_REQUIRED")
                tests.append(value is not None and operators[condition["op"]](value, threshold))
            if all(tests):
                matches.append(rule["name"])
        _need(len(matches) <= 1, "OVERLAPPING_FIXED_RULES")
        if matches:
            counts[matches[0]] += 1
        else:
            unclassified += 1
    return {"status": "DESCRIPTIVE_ONLY", "method": "fixed_rules", "n_units": len(rows), "groups": counts, "unclassified_n": unclassified,
            "data_driven_clusters": False, "limitations": ["Prespecified classification; no clustering, latent classes, stability or disease phenotype validation is implied.", "Missing rule values remain unclassified unless another fully observed rule applies."]}


def _preprocess(matrix, policy, np):
    _need(not np.any(np.all(np.isnan(matrix), axis=0)), "ALL_MISSING_CLUSTER_FEATURE")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        medians = np.nanmedian(matrix, axis=0)
    filled = np.where(np.isnan(matrix), medians, matrix) if policy == "median" else matrix.copy()
    _need(np.isfinite(filled).all(), "UNRESOLVED_CLUSTER_MISSINGNESS")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        means = filled.mean(axis=0)
        scale = filled.std(axis=0, ddof=0)
    _need(np.isfinite(medians).all() and np.isfinite(means).all() and np.isfinite(scale).all(), "NONFINITE_CLUSTER_DERIVED_VALUE")
    _need(np.all(scale > 1e-12), "CONSTANT_CLUSTER_FEATURE")
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        standardized = (filled - means) / scale
    _need(np.isfinite(standardized).all(), "NONFINITE_CLUSTER_DERIVED_VALUE")
    return standardized, medians, means, scale


def _model(method, k, spec, seed):
    if method == "kmeans":
        from sklearn.cluster import KMeans
        return KMeans(n_clusters=k, random_state=seed, n_init=spec["n_init"], max_iter=spec["max_iter"], tol=1e-6)
    from sklearn.mixture import GaussianMixture
    covariance = spec.get("covariance_type", "full")
    _need(covariance in {"full", "diag", "tied", "spherical"}, "INVALID_GMM_COVARIANCE")
    return GaussianMixture(n_components=k, covariance_type=covariance, random_state=seed, n_init=spec["n_init"], max_iter=spec["max_iter"], tol=1e-5, reg_covar=1e-6)


def _fit_predict(method, matrix, k, spec, seed):
    model = _model(method, k, spec, seed)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        labels = model.fit_predict(matrix)
    if method == "kmeans":
        _need(model.n_iter_ < spec["max_iter"] and len(set(labels)) == k and not caught, "CLUSTER_FIT_NONCONVERGENCE")
    else:
        _need(model.converged_ and len(set(labels)) == k and not caught, "CLUSTER_FIT_NONCONVERGENCE")
    return model, labels


def _candidate(matrix, raw, features, method, k, spec, np):
    from sklearn.metrics import adjusted_rand_score, silhouette_score
    standardized, medians, means, scales = _preprocess(matrix, spec["missing"], np)
    _need(len(np.unique(standardized, axis=0)) >= k, "FEWER_DISTINCT_PROFILES_THAN_K")
    model, labels = _fit_predict(method, standardized, k, spec, spec["seed"])
    counts = np.bincount(labels, minlength=k)
    if int(counts.min()) < spec["min_cluster_size"]:
        return {"status": "BLOCKED_CLUSTER_SIZE", "k": k, "cluster_sizes": sorted(int(c) for c in counts), "minimum_required": spec["min_cluster_size"]}
    # Names have deterministic ordering by first feature, then the remaining
    # centers. They are display names, never comparable phenotype identities.
    centers = model.cluster_centers_ if method == "kmeans" else model.means_
    ordered = sorted(range(k), key=lambda i: tuple(float(x) for x in centers[i]))
    profiles = []
    for display, index in enumerate(ordered, 1):
        members = raw[labels == index]
        summaries = {}
        for j, name in enumerate(features):
            observed = members[:, j][~np.isnan(members[:, j])]
            with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
                summaries[name] = {"observed_n": int(len(observed)), "missing_n": int(len(members) - len(observed)),
                                   "median": _finite_float(np.median(observed)) if len(observed) else None,
                                   "q25": _finite_float(np.quantile(observed, .25)) if len(observed) else None,
                                   "q75": _finite_float(np.quantile(observed, .75)) if len(observed) else None}
        profiles.append({"cluster": "C" + str(display), "n": int(counts[index]), "features": summaries})
    rng = np.random.default_rng(spec["seed"])
    scores = []
    invalid = 0
    failure_counts = {}
    for b in range(spec["bootstrap"]):
        sample = rng.integers(0, len(matrix), size=len(matrix))
        try:
            z, bootstrap_medians, bootstrap_means, bootstrap_scales = _preprocess(matrix[sample], spec["missing"], np)
            child_seed = int(np.random.SeedSequence([spec["seed"], b + 1]).generate_state(1, dtype=np.uint32)[0])
            refit, resampled_labels = _fit_predict(method, z, k, spec, child_seed)
            _need(int(np.bincount(resampled_labels, minlength=k).min()) >= spec["min_cluster_size"], "SMALL_BOOTSTRAP_CLUSTER")
            target = np.where(np.isnan(matrix), bootstrap_medians, matrix)
            predicted = refit.predict((target - bootstrap_means) / bootstrap_scales)
            _need(len(set(predicted)) == k, "COLLAPSED_BOOTSTRAP_PREDICTIONS")
            scores.append(float(adjusted_rand_score(labels, predicted)))
        except (ValueError, FloatingPointError, ArithmeticError):
            invalid += 1
            # Keep controlled codes; never include caller feature values/errors.
            failure_counts["NON_ESTIMABLE_RESAMPLE"] = failure_counts.get("NON_ESTIMABLE_RESAMPLE", 0) + 1
    stability = {"requested": spec["bootstrap"], "attempted": spec["bootstrap"], "valid": len(scores), "invalid": invalid,
                 "failure_counts": failure_counts, "metric": "adjusted_rand_index_against_original_partition",
                 "evaluation_units": "all original units, including in-bag observations", "refit_preprocessing": True,
                 "median_ari": float(np.median(scores)) if scores else None,
                 "q025_ari": float(np.quantile(scores, .025)) if len(scores) >= 2 else None,
                 "q975_ari": float(np.quantile(scores, .975)) if len(scores) >= 2 else None,
                 "interval_interpretation": "Percentiles of valid refits; descriptive stability range, not a population confidence interval or external validation."}
    silhouette_n = min(len(matrix), spec.get("silhouette_max_units", 2000))
    try:
        silhouette = float(silhouette_score(standardized, labels, sample_size=silhouette_n, random_state=spec["seed"]))
    except ValueError:
        # A bounded random sample can contain only one group with extreme size
        # imbalance. Do not allocate an unbounded quadratic distance matrix.
        silhouette = None
    result = {"status": "EXPLORATORY_REVIEW_PENDING" if len(scores) >= 2 else "DESCRIPTIVE_ONLY_STABILITY_UNAVAILABLE", "k": k,
              "silhouette": silhouette, "silhouette_evaluated_n": silhouette_n, "silhouette_sampling": "all units" if silhouette_n == len(matrix) else "bounded deterministic random sample",
              "profiles": profiles, "stability": stability,
              "preprocessing": {"missing": spec["missing"], "scaling": "feature z scores; population standard deviation", "fit_scope": "all analyzed development units; re-fitted independently in each bootstrap"}}
    if method == "gaussian_mixture":
        probabilities = model.predict_proba(standardized)
        result.update(bic=_finite_float(model.bic(standardized)), aic=_finite_float(model.aic(standardized)), mean_max_membership_probability=_finite_float(probabilities.max(axis=1).mean()))
    else:
        result["inertia"] = _finite_float(model.inertia_)
    return result


def analyze(rows: list[dict], spec: dict) -> dict:
    """Analyze independent units with fixed k or report every prespecified k.

    Required for data-driven methods: id_column, row_unit, features,
    feature_window, missing (median/complete_case/reject), seed, n_init>=2,
    max_iter>=20, min_cluster_size>=2, bootstrap>=2, and k or candidate_k.
    Fixed rules require rules=[{name,conditions:[{field,op,value}]}].
    """
    id_column = _validate_units(rows, spec)
    method = spec.get("method")
    if method == "fixed_rules":
        return _fixed_rules(rows, spec)
    _need(method in {"kmeans", "gaussian_mixture"}, "UNSUPPORTED_CLUSTER_METHOD")
    features = spec.get("features")
    _need(isinstance(features, list) and features and all(isinstance(f, str) and f for f in features) and len(features) == len(set(features)), "UNIQUE_CLUSTER_FEATURES_REQUIRED")
    excluded = set(spec.get("outcome_columns", [])) | set(spec.get("excluded_features", [])) | {id_column}
    _need(not set(features) & excluded, "OUTCOME_OR_ID_IN_CLUSTER_FEATURES")
    _need(isinstance(spec.get("feature_window"), str) and spec["feature_window"].strip(), "CLUSTER_FEATURE_WINDOW_REQUIRED")
    _need(spec.get("missing") in {"median", "complete_case", "reject"}, "EXPLICIT_CLUSTER_MISSING_POLICY_REQUIRED")
    for key, minimum in [("seed", 0), ("n_init", 2), ("max_iter", 20), ("min_cluster_size", 2), ("bootstrap", 2)]:
        _need(type(spec.get(key)) is int and spec[key] >= minimum, "INVALID_CLUSTER_" + key.upper())
    _need(spec["seed"] <= 4294967295, "INVALID_CLUSTER_SEED")
    _need(spec["bootstrap"] <= 1000, "CLUSTER_BOOTSTRAP_BUDGET_EXCEEDED")
    _need(type(spec.get("silhouette_max_units", 2000)) is int and spec.get("silhouette_max_units", 2000) >= 3, "INVALID_SILHOUETTE_SAMPLE_BUDGET")
    _need(("k" in spec) != ("candidate_k" in spec), "DECLARE_K_OR_CANDIDATE_K")
    candidates = [spec["k"]] if "k" in spec else spec["candidate_k"]
    _need(isinstance(candidates, list) and candidates and len(candidates) <= 12 and len(set(candidates)) == len(candidates) and all(type(k) is int and k >= 2 for k in candidates), "INVALID_PREDECLARED_CLUSTER_K")
    _need(all(all(f in row for f in features) for row in rows), "CLUSTER_FEATURE_ABSENT")
    import numpy as np
    raw = np.array([[_number(row[f]) for f in features] for row in rows], dtype=float)
    missing_rows = np.any(np.isnan(raw), axis=1)
    _need(spec["missing"] != "reject" or not np.any(missing_rows), "CLUSTER_MISSINGNESS_REJECTED")
    matrix = raw[~missing_rows] if spec["missing"] == "complete_case" else raw
    _need(len(matrix) >= 3, "TOO_FEW_CLUSTER_UNITS")
    _need(all(k < len(matrix) and k * spec["min_cluster_size"] <= len(matrix) for k in candidates), "CLUSTER_K_SAMPLE_SIZE_INCOMPATIBLE")
    result = {"method": method, "analysis_kind": "data_driven_exploratory_clustering", "row_unit": spec["row_unit"],
              "n_input": len(rows), "n_analyzed": len(matrix), "missing_rows_n": int(missing_rows.sum()),
              "complete_case_excluded_n": int(missing_rows.sum()) if spec["missing"] == "complete_case" else 0,
              "features": features, "feature_window": spec["feature_window"], "seed": spec["seed"], "n_init": spec["n_init"],
              "endpoint_used_to_select_k": False, "selected_k": spec.get("k"),
              "candidates": [_candidate(matrix, matrix, features, method, k, spec, np) for k in candidates],
              "limitations": ["Exploratory statistical groups require clinical interpretation and independent replication; no disease phenotype validity is established.",
                              "K or its candidate range must be prespecified. Candidate metrics are reported without automatic endpoint-based selection.",
                              "Bootstrap ARI compares refits on the same observed cohort; it is not held-out or external validation.",
                              "Numeric feature distances, imputation, scaling and missingness can materially change the partition.",
                              "Neither KMeans nor Gaussian mixture of static features is a latent-class longitudinal trajectory model."]}
    result["status"] = "EXPLORATORY_REVIEW_PENDING" if any(c["status"] == "EXPLORATORY_REVIEW_PENDING" for c in result["candidates"]) else "PARTIAL_OR_BLOCKED"
    return result
