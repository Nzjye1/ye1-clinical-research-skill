"""Single clustering owner: sklearn fitting, training-only transforms, frozen scoring.

These are exploratory partitions. Neither GMM covariance option implements the
formal LPA acceptance contract; no trajectory model is fitted here.
"""
from __future__ import annotations

import math
import warnings
import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.special import logsumexp
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import silhouette_score, adjusted_rand_score
from threadpoolctl import threadpool_limits

if __package__:
    from .contracts import Blocked, need, number
else:
    from contracts import Blocked, need, number

REG_COVAR = 1e-6


def matrix(rows, spec):
    names = [f["name"] for f in spec["features"]]
    need(all(set(names) <= set(r) for r in rows), "FEATURE_COLUMN_ABSENT")
    for row in rows:
        need(all(row[n] is None or number(row[n]) for n in names), "NUMERIC_FEATURE_REQUIRED")
    x = np.array([[np.nan if r[n] is None else r[n] for n in names] for r in rows], dtype=float)
    if spec["missing"] == "error":
        need(not np.isnan(x).any(), "MISSING_FEATURE_REJECTED")
    return x


def fit_transform(x, spec):
    need(not np.isnan(x).all(axis=0).any(), "ALL_MISSING_TRAINING_FEATURE")
    med = np.nanmedian(x, axis=0)
    z = np.where(np.isnan(x), med, x)
    means, scales = np.mean(z, axis=0), np.std(z, axis=0, ddof=0)
    need(np.isfinite(scales).all() and np.isfinite(means).all()
         and np.all(scales > 1e-12), "CONSTANT_OR_INVALID_TRAINING_FEATURE")
    transform = {"median": med.tolist(), "mean": means.tolist(), "scale": scales.tolist(),
                 "ddof": 0, "fit_scope": "training_only", "missing": spec["missing"]}
    return apply_transform(x, transform), transform


def apply_transform(x, transform):
    z = (np.where(np.isnan(x), transform["median"], x) - transform["mean"]) / transform["scale"]
    need(np.isfinite(z).all(), "TRANSFORM_NONFINITE")
    return z


def score_frozen(x, model):
    """No provider.fit calls; density/nearest-centre assignment from frozen numbers."""
    centers = np.asarray(model["centers"], dtype=float)
    k, p = centers.shape
    if model["algorithm"] == "kmeans":
        distances = np.sum((x[:, None, :] - centers[None, :, :])**2, axis=2)
        need(np.isfinite(distances).all(), "SCORING_NONFINITE")
        return distances.argmin(axis=1), None, distances.min(axis=1)
    log_scores = []
    for c in range(k):
        cov = np.asarray(model["covariances"][c], dtype=float)
        if model["covariance"] == "diag":
            cov = np.diag(cov)
        chol = np.linalg.cholesky(cov)
        u = np.linalg.solve(chol, (x - centers[c]).T).T
        log_scores.append(np.log(model["weights"][c]) - .5 * (p*np.log(2*np.pi)
                          + 2*np.log(np.diag(chol)).sum() + np.sum(u*u, axis=1)))
    log_scores = np.asarray(log_scores).T
    log_density = logsumexp(log_scores, axis=1)
    probs = np.exp(log_scores - log_density[:, None])
    need(np.isfinite(probs).all() and np.isfinite(log_density).all(), "SCORING_NONFINITE")
    return probs.argmax(axis=1), probs, log_density


def check_solution(x, model, spec):
    labels, probs, _ = score_frozen(x, model)
    k = len(model["centers"])
    counts = np.bincount(labels, minlength=k)
    threshold = max(spec["min_class_n"], math.ceil(len(x)*spec["min_class_fraction"]))
    need(np.all(counts >= threshold), "DEGENERATE_OR_SMALL_CLASS")
    if k > 1:
        centers = np.array(model["centers"])
        sep = np.linalg.norm(centers[:, None] - centers[None], axis=2)
        need(np.min(sep[np.triu_indices(k, 1)]) > 1e-5, "COINCIDENT_CENTERS")
    if probs is not None:
        need(min(model["weights"]) >= spec["min_class_fraction"], "NEGLIGIBLE_COMPONENT_WEIGHT")
        for c in model["covariances"]:
            eig = np.asarray(c) if model["covariance"] == "diag" else np.linalg.eigvalsh(c)
            need(np.isfinite(eig).all() and min(eig) > 10*REG_COVAR
                 and max(eig)/min(eig) < 1e8, "COVARIANCE_DEGENERATE")
    return labels


def fit_candidate(x, spec, method, k, seed):
    starts, models = [], []
    for start in range(spec["starts"]):
        current_seed = int((seed + start*104729) % (2**31-1))
        diagnostic = {"k": k, "start": start+1, "seed": current_seed, "status": "rejected",
                      "reason_code": None, "objective": None, "iterations": None}
        try:
            with warnings.catch_warnings(record=True) as caught, threadpool_limits(limits=1):
                warnings.simplefilter("always")
                if method.endswith("kmeans"):
                    fit = KMeans(n_clusters=k, random_state=current_seed, n_init=1,
                                 max_iter=spec["max_iter"], tol=spec["tol"], algorithm="lloyd").fit(x)
                    diagnostic["iterations"] = int(fit.n_iter_)
                    need(fit.n_iter_ < spec["max_iter"], "ITERATION_LIMIT")
                    objective = float(fit.inertia_)
                    model = {"algorithm": "kmeans", "centers": fit.cluster_centers_.tolist(),
                             "covariance": "none", "covariances": None, "weights": None}
                else:
                    fit = GaussianMixture(n_components=k, covariance_type=spec["covariance"],
                        n_init=1, init_params="kmeans", random_state=current_seed,
                        max_iter=spec["max_iter"], tol=spec["tol"], reg_covar=REG_COVAR).fit(x)
                    diagnostic["iterations"] = int(fit.n_iter_)
                    need(fit.converged_ and fit.n_iter_ < spec["max_iter"], "EM_NOT_CONVERGED")
                    objective = -float(fit.score(x)*len(x))
                    model = {"algorithm": "gmm", "centers": fit.means_.tolist(),
                             "covariance": spec["covariance"], "covariances": fit.covariances_.tolist(),
                             "weights": fit.weights_.tolist()}
                need(not caught, "ENGINE_WARNING")
            need(math.isfinite(objective), "NONFINITE_OBJECTIVE")
            check_solution(x, model, spec)
            diagnostic.update(status="accepted", objective=objective)
            models.append((objective, current_seed, model))
        except Blocked as error:
            diagnostic["reason_code"] = error.code
        except (ValueError, np.linalg.LinAlgError, FloatingPointError):
            diagnostic["reason_code"] = "ENGINE_NUMERIC_FAILURE"
        starts.append(diagnostic)
    need(bool(models), "ALL_INITIALIZATIONS_REJECTED", {"starts": starts})
    models.sort(key=lambda item: (item[0], item[1]))
    objective, chosen_seed, model = models[0]
    replicated = sum(abs(value-objective) <= 1e-6*max(1, abs(objective)) for value, _, _ in models)
    need(replicated >= 2, "BEST_SOLUTION_NOT_REPLICATED", {"starts": starts})
    # Canonical labels are lexicographic centre order, never a severity ordering.
    order = sorted(range(k), key=lambda i: tuple(model["centers"][i]))
    for key in ["centers", "covariances", "weights"]:
        if model[key] is not None:
            model[key] = [model[key][i] for i in order]
    labels = check_solution(x, model, spec)
    p = x.shape[1]
    n_parameters = (k-1 + k*p + (k*p if spec["covariance"] == "diag" else k*p*(p+1)//2)
                    if model["algorithm"] == "gmm" else k*p)
    bic = 2*objective + n_parameters*np.log(len(x)) if model["algorithm"] == "gmm" else None
    with threadpool_limits(limits=1):
        silhouette = float(silhouette_score(x, labels)) if k > 1 else None
    summary = {"k": k, "status": "accepted", "reason_code": None, "objective": objective,
               "bic": float(bic) if bic is not None else None, "silhouette": silhouette,
               "n_parameters": n_parameters, "best_replicated_starts": replicated,
               "selected_seed": chosen_seed, "fit_scope": "training_only"}
    return model, summary, starts


def stability(raw, original_labels, k, spec, method):
    rng = np.random.default_rng(spec["seed"] + 2000003)
    values = []
    for rep in range(spec["stability_reps"]):
        sample = rng.integers(0, len(raw), size=len(raw))
        item = {"replicate": rep+1, "status": "rejected", "reason_code": None,
                "ari": None, "minimum_aligned_jaccard": None, "n_engine_fits": 0}
        try:
            z, transform = fit_transform(raw[sample], spec)
            item["n_engine_fits"] = spec["starts"]
            fitted, _, _ = fit_candidate(z, spec, method, k, int(rng.integers(0, 2**31-1)))
            predicted, _, _ = score_frozen(apply_transform(raw, transform), fitted)
            jaccard = np.zeros((k, k))
            for i in range(k):
                for j in range(k):
                    a, b = original_labels == i, predicted == j
                    jaccard[i, j] = np.sum(a & b)/max(1, np.sum(a | b))
            row, col = linear_sum_assignment(-jaccard)
            item.update(status="accepted", ari=float(adjusted_rand_score(original_labels, predicted)),
                        minimum_aligned_jaccard=float(jaccard[row, col].min()))
        except Blocked as error:
            item["reason_code"] = error.code
        values.append(item)
    valid = [v["ari"] for v in values if v["status"] == "accepted"]
    need(len(valid) >= math.ceil(.8*len(values)), "STABILITY_INSUFFICIENT_VALID_REPLICATES",
         {"stability": values})
    summary = {"requested": len(values), "valid": len(valid), "mean_ari": float(np.mean(valid)),
               "p10_ari": float(np.quantile(valid, .1)), "p90_ari": float(np.quantile(valid, .9)),
               "scope": "training_bootstrap_fixed_selected_k_refit_transform",
               "uncertainty": "descriptive_resampling_range_not_confidence_interval",
               "class_selection_repeated": False}
    return values, summary


def score_partition(x, rows, positions, partition, model, transform):
    z = apply_transform(x, transform)
    labels, probs, value = score_frozen(z, model)
    counts, private = [], []
    k = len(model["centers"])
    for c in range(k):
        mask = labels == c
        counts.append({"partition": partition, "class": c+1, "n": int(mask.sum()),
                       "denominator": len(rows), "fraction": float(mask.mean()),
                       "mean_max_posterior": float(probs[mask].max(axis=1).mean())
                           if probs is not None and mask.any() else None})
    for j, position in enumerate(positions):
        private.append({"row_index": int(position), "partition": partition, "class": int(labels[j]+1),
                        "posterior": probs[j].tolist() if probs is not None else None,
                        "score": float(value[j])})
    entropy = (float(1 + np.sum(probs*np.log(np.maximum(probs, 1e-300)))/(len(rows)*np.log(k)))
               if probs is not None and k > 1 else None)
    return counts, private, entropy


def analyze(rows, spec, method, frozen=None):
    ids = [r[spec["subject_id"]] for r in rows]
    need(len(ids) == len(set(ids)), "DUPLICATE_SUBJECT_IN_CROSS_SECTIONAL_INPUT")
    raw = matrix(rows, spec)
    if frozen is not None:
        model, transform = frozen["model"], frozen["transform"]
        counts, private, entropy = score_partition(raw, rows, list(range(len(rows))), "external", model, transform)
        return {"selected_k": len(model["centers"]), "class_counts": counts,
                "normalized_entropy": {"external": entropy}, "selection": [], "initializations": [],
                "stability": [], "stability_summary": None, "profiles": profiles(model, transform, spec),
                "counts": {"input_rows": len(rows), "training_rows": 0, "assigned_rows": len(rows)},
                "diagnostics": {"n_engine_fits": 0, "model_refitted": False, "transform_refitted": False},
                "warnings": ["FROZEN_ASSIGNMENT_IS_NOT_EXTERNAL_VALIDATION"]}, model, transform, private
    split = spec["split"]
    need(all(r.get(split["field"]) in {split["train"], split["holdout"]} for r in rows), "SPLIT_LABEL_INVALID")
    train = np.array([i for i, r in enumerate(rows) if r[split["field"]] == split["train"]], dtype=int)
    holdout = np.array([i for i, r in enumerate(rows) if r[split["field"]] == split["holdout"]], dtype=int)
    need(len(train) >= 20 and len(train) <= 3000, "TRAINING_SIZE_OUTSIDE_VALIDATED_LIMIT")
    x, transform = fit_transform(raw[train], spec)
    candidates, accepted, starts = [], [], []
    for k in sorted(spec["candidate_k"]):
        try:
            fitted, row, inits = fit_candidate(x, spec, method, k, spec["seed"] + k*7919)
            accepted.append((row["bic"] if method.endswith("gmm") else -row["silhouette"], k, fitted))
            candidates.append(row)
            starts.extend(inits)
        except Blocked as error:
            candidates.append({"k": k, "status": "rejected", "reason_code": error.code,
                               "bic": None, "silhouette": None, "objective": None,
                               "fit_scope": "training_only"})
            starts.extend(error.diagnostics.get("starts", []))
    need(bool(accepted), "NO_ADMISSIBLE_CLUSTER_MODEL", {"selection": candidates, "initializations": starts})
    _, k, model = min(accepted, key=lambda item: (item[0], item[1]))
    labels, _, _ = score_frozen(x, model)
    stability_rows, stability_summary = stability(raw[train], labels, k, spec, method)
    counts, private, entropies = [], [], {}
    for indices, partition in [(train, "training"), (holdout, "holdout")]:
        if len(indices):
            summary, individual, entropy = score_partition(raw[indices], [rows[i] for i in indices],
                                                           indices, partition, model, transform)
            counts += summary
            private += individual
            entropies[partition] = entropy
    warnings_out = ["EXPLORATORY_PARTITIONS_NOT_CLINICAL_SUBTYPES", "STABILITY_CONDITIONAL_ON_SELECTED_K"]
    if stability_summary["mean_ari"] < .6:
        warnings_out.append("LOW_BOOTSTRAP_STABILITY")
    if not len(holdout):
        warnings_out.append("NO_HOLDOUT_ASSIGNMENT_REQUESTED")
    return {"selected_k": k, "selection": candidates, "initializations": starts,
            "class_counts": counts, "normalized_entropy": entropies, "stability": stability_rows,
            "stability_summary": stability_summary, "profiles": profiles(model, transform, spec),
            "counts": {"input_rows": len(rows), "training_rows": len(train), "holdout_rows": len(holdout),
                       "assigned_rows": len(rows), "training_missing_cells": int(np.isnan(raw[train]).sum())},
            "diagnostics": {"model_refitted": True, "transform_refitted": True,
                            "n_engine_fits": len(starts) + sum(r["n_engine_fits"] for r in stability_rows),
                            "reg_covar": REG_COVAR if method.endswith("gmm") else None},
            "warnings": warnings_out}, model, transform, private


def profiles(model, transform, spec):
    result = []
    for i, center in enumerate(model["centers"]):
        for j, feature in enumerate(spec["features"]):
            result.append({"class": i+1, "feature": feature["name"], "unit": feature["unit"],
                           "standardized_center": center[j],
                           "original_center": center[j]*transform["scale"][j]+transform["mean"][j],
                           "scope": "frozen_training_model_center", "ci": None})
    return result
