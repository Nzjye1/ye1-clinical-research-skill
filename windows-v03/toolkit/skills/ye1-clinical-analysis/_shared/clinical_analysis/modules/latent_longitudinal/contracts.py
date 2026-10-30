"""Module-private contract. Does not relax any v0.10 common contract."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re

VERSION = "latent-longitudinal-request/1"
CLUSTER = {"exploration.cluster.kmeans", "exploration.cluster.gmm"}
GROWTH = {"longitudinal.growth.gaussian"}
FORMAL = {"latent.profile.gaussian", "latent.trajectory.gaussian"}
METHODS = CLUSTER | GROWTH | FORMAL


class Blocked(Exception):
    def __init__(self, code, diagnostics=None):
        super().__init__(code)
        self.code = code
        self.diagnostics = diagnostics or {}


def need(condition, code, diagnostics=None):
    if not condition:
        raise Blocked(code, diagnostics)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False, ensure_ascii=True).encode()).hexdigest()


def exact(obj, required, optional=()):
    need(isinstance(obj, dict) and set(required) <= set(obj)
         and not set(obj) - set(required) - set(optional), "CONTRACT_FIELDS_INVALID")


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def integer(x, low, high):
    return isinstance(x, int) and not isinstance(x, bool) and low <= x <= high


def name(x):
    return isinstance(x, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", x) is not None


def fields(items):
    need(isinstance(items, list) and 1 <= len(items) <= 20, "FEATURES_INVALID")
    for item in items:
        exact(item, ["name", "unit"])
        need(name(item["name"]) and isinstance(item["unit"], str) and bool(item["unit"].strip()),
             "FEATURE_DEFINITION_INVALID")
    need(len({f["name"] for f in items}) == len(items), "DUPLICATE_FEATURE")


def validate_request(request):
    def finite_json(value):
        if isinstance(value, float):
            need(math.isfinite(value), "NONFINITE_INPUT_VALUE")
        elif isinstance(value, dict):
            for child in value.values():
                finite_json(child)
        elif isinstance(value, list):
            for child in value:
                finite_json(child)
    finite_json(request)
    exact(request, ["schema_version", "method_id", "operation", "spec", "rows", "test_only"],
          ["model_ref"])
    need(request["schema_version"] == VERSION, "REQUEST_VERSION_UNSUPPORTED")
    need(request["method_id"] in METHODS, "METHOD_UNSUPPORTED")
    need(request["test_only"] is True, "SYNTHETIC_ENGINEERING_SCOPE_ONLY")
    method, op, spec = request["method_id"], request["operation"], request["spec"]
    need(op in ({"train", "assign"} if method in CLUSTER or method == "latent.profile.gaussian"
                else {"train", "predict"}), "OPERATION_UNSUPPORTED")
    need(isinstance(spec, dict), "SPEC_REQUIRED")
    common = ["subject_id", "cohort_id"]
    if method in CLUSTER:
        exact(spec, common + ["features", "missing", "candidate_k", "selection", "seed", "starts",
                              "max_iter", "tol", "stability_reps", "min_class_n", "min_class_fraction",
                              "covariance", "split"])
        fields(spec["features"])
        need(spec["missing"] in {"error", "train_median"}, "MISSING_POLICY_UNSUPPORTED")
        ks = spec["candidate_k"]
        need(isinstance(ks, list) and 1 <= len(ks) <= 6 and len(set(ks)) == len(ks)
             and all(integer(k, 2 if method.endswith("kmeans") else 1, 6) for k in ks),
             "CANDIDATE_K_INVALID")
        need(spec["selection"] == ("silhouette" if method.endswith("kmeans") else "bic"),
             "SELECTION_MISMATCH")
        need(spec["covariance"] in ({"none"} if method.endswith("kmeans") else {"diag", "full"}),
             "COVARIANCE_UNSUPPORTED")
        for key, low, high in [("seed", 0, 2**31-1), ("starts", 3, 30), ("max_iter", 1, 3000),
                               ("stability_reps", 5, 50), ("min_class_n", 5, 10000)]:
            need(integer(spec[key], low, high), "OPTION_INVALID_" + key.upper())
        need(number(spec["tol"]) and 1e-8 <= spec["tol"] <= 1e-3, "TOLERANCE_INVALID")
        need(number(spec["min_class_fraction"]) and 0.01 <= spec["min_class_fraction"] <= .2,
             "MIN_CLASS_FRACTION_INVALID")
        exact(spec["split"], ["field", "train", "holdout"])
        need(name(spec["split"]["field"]) and all(isinstance(spec["split"][k], str)
             and bool(spec["split"][k]) for k in ["train", "holdout"])
             and spec["split"]["train"] != spec["split"]["holdout"], "SPLIT_INVALID")
        reserved = [spec["subject_id"], spec["split"]["field"]] + [f["name"] for f in spec["features"]]
        need(len(set(reserved)) == len(reserved), "ROLE_COLLISION")
    elif method in GROWTH:
        exact(spec, common + ["time", "outcome", "covariates", "degree", "random", "estimation",
                              "correlation", "missing", "seed", "max_iter"])
        exact(spec["time"], ["name", "unit", "origin", "scale"])
        fields([{"name": spec["time"]["name"], "unit": spec["time"]["unit"]}])
        fields([spec["outcome"]])
        need(isinstance(spec["covariates"], list) and len(spec["covariates"]) <= 10,
             "COVARIATES_INVALID")
        if spec["covariates"]:
            fields(spec["covariates"])
        need(number(spec["time"]["origin"]) and number(spec["time"]["scale"])
             and spec["time"]["scale"] > 0, "TIME_TRANSFORM_INVALID")
        need(integer(spec["degree"], 1, 2), "DEGREE_UNSUPPORTED")
        need(spec["random"] in {"intercept", "intercept_slope"}, "RANDOM_STRUCTURE_UNSUPPORTED")
        need(spec["estimation"] == "ML" and spec["correlation"] == "independent",
             "GROWTH_DEFINITION_UNSUPPORTED")
        need(spec["missing"] == "complete_case_rows", "MISSING_POLICY_UNSUPPORTED")
        need(integer(spec["max_iter"], 1, 2000) and integer(spec["seed"], 0, 2**31-1),
             "GROWTH_OPTION_INVALID")
        reserved = [spec["subject_id"], spec["time"]["name"], spec["outcome"]["name"]] + [
            f["name"] for f in spec["covariates"]]
        need(len(set(reserved)) == len(reserved), "ROLE_COLLISION")
    else:
        # Formal requests are validated and explicitly blocked; no optimizer fallback.
        exact(spec, common + ["definition", "candidate_k", "seed", "starts"])
        need(isinstance(spec["definition"], dict), "FORMAL_DEFINITION_REQUIRED")
        need(isinstance(spec["candidate_k"], list) and bool(spec["candidate_k"])
             and all(integer(k, 1, 6) for k in spec["candidate_k"])
             and len(set(spec["candidate_k"])) == len(spec["candidate_k"]), "CANDIDATE_K_INVALID")
        need(integer(spec["starts"], 20, 200) and integer(spec["seed"], 0, 2**31-1),
             "FORMAL_INITIALIZATIONS_INVALID")
        d = spec["definition"]
        if method == "latent.profile.gaussian":
            exact(d, ["indicators", "covariance_model", "missing"])
            fields(d["indicators"])
            need(len(d["indicators"]) >= 2 and d["covariance_model"] in {"EEI", "VVI"}
                 and d["missing"] == "complete_case", "FORMAL_PROFILE_DEFINITION_UNSUPPORTED")
        else:
            exact(d, ["family", "time", "outcome", "degree", "random", "missing"])
            fields([d["time"], d["outcome"]])
            need(d["family"] in {"lcga", "growth_mixture"} and integer(d["degree"], 1, 2)
                 and d["random"] in ({"none"} if d["family"] == "lcga" else {"intercept", "intercept_slope"})
                 and d["missing"] == "observed_likelihood_mar", "FORMAL_TRAJECTORY_DEFINITION_UNSUPPORTED")
    need(name(spec["subject_id"]) and isinstance(spec["cohort_id"], str)
         and bool(spec["cohort_id"].strip()), "IDENTITY_DEFINITION_INVALID")
    need(isinstance(request["rows"], list) and 1 <= len(request["rows"]) <= 20000
         and all(isinstance(r, dict) for r in request["rows"]), "ROWS_INVALID")
    for row in request["rows"]:
        need(isinstance(row.get(spec["subject_id"]), str) and bool(row[spec["subject_id"]].strip()),
             "SUBJECT_ID_INVALID")
    if op == "train":
        need(request.get("model_ref") is None, "UNEXPECTED_FROZEN_MODEL")
    else:
        exact(request.get("model_ref"), ["path", "sha256"])
        need(isinstance(request["model_ref"]["path"], str)
             and re.fullmatch(r"[0-9a-f]{64}", request["model_ref"]["sha256"] or "") is not None,
             "MODEL_REF_INVALID")
    return request


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    def constant(value):
        raise Blocked("NONFINITE_JSON_CONSTANT")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def frozen_definition(spec):
    value = copy.deepcopy(spec)
    value.pop("cohort_id")
    return value


def adapt_rows(source_rows, mapping):
    """Explicit canonical->source map with declared affine conversions; no inference."""
    need(isinstance(mapping, dict) and bool(mapping), "MAPPING_REQUIRED")
    for canonical, rule in mapping.items():
        need(name(canonical), "MAPPING_NAME_INVALID")
        exact(rule, ["source"], ["scale", "offset"])
        need(name(rule["source"]), "MAPPING_SOURCE_INVALID")
        if "scale" in rule or "offset" in rule:
            need(number(rule.get("scale", 1)) and rule.get("scale", 1) != 0
                 and number(rule.get("offset", 0)), "MAPPING_CONVERSION_INVALID")
    out = []
    for source in source_rows:
        row = {}
        for canonical, rule in mapping.items():
            need(rule["source"] in source, "MAPPING_COLUMN_ABSENT")
            value = source[rule["source"]]
            if value is not None and ("scale" in rule or "offset" in rule):
                need(number(value), "MAPPING_NUMERIC_VALUE_INVALID")
                value = value * rule.get("scale", 1) + rule.get("offset", 0)
                need(number(value), "MAPPING_NONFINITE_RESULT")
            row[canonical] = value
        out.append(row)
    return out
