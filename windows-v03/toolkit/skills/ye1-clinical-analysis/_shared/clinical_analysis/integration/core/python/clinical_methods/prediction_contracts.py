"""Pure contract extensions for the two fixed local prediction providers.

No estimator, splitter, preprocessing learner or execution loop lives here.
The source providers own numerical behavior and their original prerequisites.
"""
from __future__ import annotations
import copy
import hashlib

INPUT_VERSION = "clinical-study-input@0.2.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-b1b-20261023"
METHODS = {"prediction.continuous.nonnegative.ridge", "prediction.binary.ridge"}
TARGET_POLICY = {"domain": "nonnegative", "transform": "identity", "inverse_transform": "identity",
                 "output_policy": "clip_lower_zero", "lower_bound": 0}
S = {"type": "string", "minLength": 1}
NAME = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
N = {"type": "number"}
BOOL = {"type": "boolean"}
SCALAR = {"type": ["string", "number", "boolean"]}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}

def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required, "additionalProperties": False}

def arr(schema, minimum=0):
    return {"type": "array", "items": schema, "minItems": minimum}

BINARY_FEATURE = {"anyOf": [
    obj({"name": NAME, "type": {"const": "number"}, "available_at_prediction": {"const": True}}),
    obj({"name": NAME, "type": {"const": "category"}, "levels": arr(SCALAR, 2),
         "available_at_prediction": {"const": True}})]}
BINARY_SPLIT = obj({"method": {"enum": ["random", "group", "temporal"]},
    "seed": {"type": "integer", "minimum": 0, "maximum": 4294967295},
    "test_fraction": {"type": "number", "minimum": .2, "maximum": .5},
    "group": NAME, "time": NAME, "label_available_time": NAME}, ["method", "seed", "test_fraction"])
BINARY_SPEC = obj({"id": NAME, "outcome": NAME, "event": SCALAR, "non_event": SCALAR,
    "cohort_id": S, "prediction_time": S, "outcome_window": S, "features": arr(BINARY_FEATURE, 1),
    "split": BINARY_SPLIT, "missing": {"const": "train_median_mode"},
    "C": {"type": "number", "minimum": 1e-6, "maximum": 1e6},
    "cv_folds": {"type": "integer", "minimum": 2, "maximum": 5},
    "bootstrap": {"type": "integer", "minimum": 0, "maximum": 100},
    "min_epv": {"type": "number", "minimum": 10}, "independent_subjects": {"const": True},
    "dca_thresholds": arr(N, 1), "clinical_decision_threshold": {"type": ["number", "null"]},
    "selection": {"const": "none"}, "post_outcome_fields": arr(NAME),
    "evaluation_seed": {"type": "integer", "minimum": 0, "maximum": 4294967295}},
    ["id", "outcome", "event", "non_event", "cohort_id", "prediction_time", "outcome_window", "features",
     "split", "missing", "C", "cv_folds", "bootstrap", "min_epv", "independent_subjects",
     "dca_thresholds", "clinical_decision_threshold"])
CONTINUOUS_FEATURE = obj({"variable": NAME, "kind": {"enum": ["continuous", "binary", "categorical"]},
    "step": {"type": "number", "minimum": 1e-12}, "levels": arr(N, 2), "reference": N,
    "available_at_prediction": {"const": True}}, ["variable", "kind", "available_at_prediction"])
CONTINUOUS_SPEC = obj({"id": NAME, "outcome": NAME, "cohort_id": S, "prediction_time": S, "outcome_window": S,
    "task": {"const": "continuous"}, "outcome_domain": {"const": "nonnegative"},
    "outcome_transform": {"const": "identity"}, "features": arr(CONTINUOUS_FEATURE, 1),
    "split": obj({"method": {"const": "group"}, "group": NAME,
        "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
        "test_fraction": {"type": "number", "minimum": .15, "maximum": .4},
        "cv_folds": {"type": "integer", "minimum": 3, "maximum": 5}}),
    "tuning": obj({"ridge_grid": {"type": "array", "items": {"type": "number", "minimum": 1e-6, "maximum": 100},
                                  "minItems": 1, "maxItems": 5}}),
    "evaluation": obj({"threshold": {"type": "number", "minimum": 0, "maximum": 1},
                       "bootstrap_repetitions": {"type": "integer", "minimum": 0, "maximum": 100}})})
CONTINUOUS_SPEC["properties"]["target_policy"] = {"const": TARGET_POLICY}
PREDICTION = obj({"operation": {"enum": ["train", "evaluate", "infer"]},
    "spec": {"anyOf": [BINARY_SPEC, CONTINUOUS_SPEC]},
    "model_ref": {"anyOf": [obj({"local_ref": S, "content_hash": HASH}), {"type": "null"}]},
    "unknown_category_policy": {"const": "reject"}})

def make_schema(legacy_schema):
    schema = copy.deepcopy(legacy_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    analysis = schema["properties"]["analysis"]
    analysis["properties"]["method_id"] = {"enum": sorted(METHODS)}
    analysis["properties"]["spec"] = {"type": "null"}
    analysis["properties"]["baseline"] = {"type": "null"}
    analysis["properties"]["prediction"] = PREDICTION
    analysis["required"].append("prediction")
    return schema

def _token(value):
    if type(value) in (int, float):
        return format(float(value), ".15g")
    return str(value)

def code_requirements(legacy):
    return set(legacy) | {
        "python/clinical_methods/prediction.py", "python/clinical_methods/prediction_bridge.py",
        "python/clinical_methods/prediction_contracts.py",
        "python/clinical_methods/continuous_ridge/__init__.py",
        "python/clinical_methods/continuous_ridge/core.py",
        "python/clinical_methods/continuous_ridge/prediction_engine.py",
        "python/clinical_methods/continuous_ridge/prediction_metrics.py",
        "src/clinanalysis/R/clinical_prediction_common.R"}

def canonical_semantics(task):
    """Freeze post-mapping semantics, never source column/encoding choices."""
    prediction = task["analysis"]["prediction"]
    binary = task["analysis"]["method_id"] == "prediction.binary.ridge"
    spec = prediction["spec"]
    names = [feature["name" if binary else "variable"] for feature in spec["features"]] + [spec["outcome"]]
    variables = {v["name"]: v for v in task["variables"]}
    fields = ("name", "dtype", "unit", "dimension", "levels", "reference", "concept", "codebook_version")
    time_fields = ("unit", "timezone", "index", "feature_cutoff", "outcome_window", "boundary", "delayed_entry")
    return {"variables": [{key: copy.deepcopy(variables[name][key]) for key in fields} for name in names],
            "time": {key: copy.deepcopy(task["time"][key]) for key in time_fields}}

def validate_options(task, rows, variables, root, helpers):
    """Validate method-specific roles/definitions and read one private model once."""
    need, read_json, confined = helpers["need"], helpers["read_json"], helpers["confined"]
    file_hash, canonical_hash = helpers["file_hash"], helpers["canonical_hash"]
    stage = "method_applicability"
    analysis = task["analysis"]
    need(analysis["method_id"] in METHODS, "METHOD_NOT_INTEGRATED", stage)
    prediction = analysis["prediction"]
    operation, spec = prediction["operation"], prediction["spec"]
    binary = analysis["method_id"] == "prediction.binary.ridge"
    need(("task" not in spec) if binary else spec.get("task") == "continuous", "PREDICTION_PROVIDER_SPEC_MISMATCH", stage)
    need(analysis["variance"] == "not_applicable" and analysis["ci_level"] == .95, "PREDICTION_INFERENCE_OPTIONS_UNSUPPORTED", stage)
    need(analysis["effect_scale"] == ("probability" if binary else "outcome units"), "EFFECT_SCALE_MISMATCH", stage)
    selected = next(v for v in task["views"] if v["view_id"] == analysis["required_view_ids"][0])
    need(task["identity"]["analysis_unit"] == "subject" and selected["kind"] == "subject_wide",
         "PREDICTION_SUBJECT_VIEW_REQUIRED", stage)
    identity = task["identity"]
    need(spec["id"] == identity["subject_key"], "PREDICTION_IDENTITY_MISMATCH", stage)
    need(spec["outcome"] == task["outcome"]["field"] and spec["outcome"] in variables,
         "OUTCOME_CONTRACT_MISMATCH", stage)
    outcome = variables[spec["outcome"]]
    need(outcome["role"] == "outcome", "OUTCOME_ROLE_INVALID", stage)
    if operation != "infer":
        tm = task["time"]
        need(outcome["available_at"] <= tm["analysis_as_of"]
             and tm["outcome_window"][0] <= outcome["occurred_at"] <= tm["outcome_window"][1],
             "OUTCOME_LABEL_NOT_MATURE", stage)
    if binary:
        need(task["outcome"]["type"] == "binary" and outcome["dtype"] == "category"
             and _token(task["outcome"]["event"]) == _token(spec["event"])
             and _token(task["outcome"]["non_event"]) == _token(spec["non_event"]), "BINARY_CODING_MISMATCH", stage)
        need({_token(spec["event"]), _token(spec["non_event"])} == set(outcome["levels"]), "BINARY_CODING_MISMATCH", stage)
        need(spec.get("selection", "none") == "none", "SELECTION_OPTION_NOT_INTEGRATED", stage)
        need(spec["bootstrap"] == 0 or 50 <= spec["bootstrap"] <= 100, "BOOTSTRAP_REPS_INVALID", stage)
        thresholds = spec["dca_thresholds"]
        need(len(set(thresholds)) == len(thresholds) and thresholds == sorted(thresholds)
             and all(0 < x < 1 for x in thresholds), "DCA_THRESHOLDS_INVALID", stage)
        threshold = spec["clinical_decision_threshold"]
        need(threshold is None or 0 < threshold < 1, "CLINICAL_THRESHOLD_INVALID", stage)
    else:
        need(task["outcome"]["type"] == "continuous" and outcome["dtype"] == "number", "CONTINUOUS_OUTCOME_REQUIRED", stage)
        need(all(r[spec["outcome"]] is None or r[spec["outcome"]] >= 0 for r in rows), "NEGATIVE_OUTCOME_NOT_SUPPORTED", stage)
        grid = spec["tuning"]["ridge_grid"]
        need(len(set(grid)) == len(grid) and grid == sorted(grid), "FIXED_RIDGE_GRID_REQUIRED", stage)
        reps = spec["evaluation"]["bootstrap_repetitions"]
        need(reps == 0 or reps >= 50, "BOOTSTRAP_REPS_INVALID", stage)
    names = [f["name" if binary else "variable"] for f in spec["features"]]
    need(len(names) == len(set(names)), "UNIQUE_FEATURE_NAMES_REQUIRED", stage)
    need(not any(name in variables and variables[name]["dtype"] == "id" for name in names),
         "ID_MODEL_FIELD_FORBIDDEN", stage)
    prohibited = {spec["id"], spec["outcome"]}
    split = spec["split"]
    prohibited.update(split[k] for k in ("group", "time", "label_available_time") if k in split)
    prohibited.update(spec.get("post_outcome_fields", []))
    need(not set(names) & prohibited, "LEAKAGE_ROLE_IN_FEATURES", stage)
    for feature, name in zip(spec["features"], names):
        need(name in variables, "MODEL_FIELD_MISSING", stage)
        variable = variables[name]
        need(variable["role"] in {"exposure", "covariate", "group"}, "PREDICTION_FEATURE_ROLE_INVALID", stage)
        need(variable["available_at"] <= task["time"]["feature_cutoff"] and feature["available_at_prediction"] is True,
             "FUTURE_INFORMATION", stage)
        kind = feature["type" if binary else "kind"]
        if kind in {"number", "continuous"}:
            need(variable["dtype"] == "number", "PREDICTION_FEATURE_TYPE_MISMATCH", stage)
            need(not any(k in feature for k in ("levels", "reference")), "NUMERIC_FEATURE_CATEGORY_FIELDS", stage)
        else:
            need(variable["dtype"] == "category", "PREDICTION_FEATURE_TYPE_MISMATCH", stage)
            if not binary and kind == "binary":
                levels, reference = ["0", "1"], "0"
            else:
                need("levels" in feature, "PREDECLARED_CATEGORY_LEVELS_REQUIRED", stage)
                levels = [_token(x) for x in feature["levels"]]
                reference = levels[0] if binary else _token(feature.get("reference"))
            need(levels == variable["levels"] and reference == variable["reference"], "PREDICTION_CATEGORY_CONTRACT_MISMATCH", stage)
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    need(task["missingness"] == {"strategy": "train_median_mode", "fit_scope": fit_scope, "exclusion_denominator": "selected_view"},
         "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    need(task["derivation"] == {"strategy": "declared_unit_conversion_only", "version": "1"}, "DERIVATION_NOT_ENABLED", stage)
    declared_split = task["split"]
    need(declared_split["fit_scope"] == fit_scope and declared_split["fold_field"] is None, "PREASSIGNED_FOLDS_NOT_SUPPORTED", stage)
    expected_group = split.get("group", identity["subject_key"])
    need(declared_split["group_key"] == expected_group and declared_split["seed"] == split["seed"], "SPLIT_CONTRACT_MISMATCH", stage)
    need(declared_split["strategy"] == (split["method"] if operation == "train" else "none"), "SPLIT_CONTRACT_MISMATCH", stage)
    for role in ("group", "time", "label_available_time"):
        if role in split:
            name = split[role]
            need(name in variables and all(r[name] is not None for r in rows), "SPLIT_FIELD_MISSING", stage)
            need(variables[name]["role"] in {"id", "split", "time", "group"}, "SPLIT_FIELD_ROLE_INVALID", stage)
    if binary and split["method"] == "group":
        need("group" in split, "GROUP_DEFINITION_REQUIRED", stage)
    if binary and split["method"] == "temporal":
        need("time" in split and "label_available_time" in split, "TEMPORAL_LABEL_AVAILABILITY_COLUMN_REQUIRED", stage)
        need(all(r[split["label_available_time"]] >= r[split["time"]] for r in rows), "LABEL_AVAILABILITY_PRECEDES_PREDICTION_TIME", stage)
    model_ref = prediction["model_ref"]
    if operation == "train":
        need(model_ref is None, "TRAINING_MODEL_REF_NOT_ALLOWED", stage)
        need(task["validation"] == {"kind": "internal_holdout", "overlap_status": "not_applicable", "transportability": "not_evaluated"},
             "PREDICTION_VALIDATION_SCOPE_INVALID", stage)
        return None
    need(model_ref is not None, "FROZEN_MODEL_REF_REQUIRED", "binding")
    expected_validation = {"kind": "synthetic_frozen_application" if operation == "evaluate" else "new_data_inference",
        "overlap_status": "verified_synthetic_disjoint", "transportability": "not_evaluated"}
    if task.get("schema_version") == "clinical-study-input@1.0":
        expected_validation = helpers["_real_family_admission"].external_validation(task, kind=expected_validation["kind"])
    need(task["validation"] == expected_validation, "PREDICTION_VALIDATION_SCOPE_INVALID", stage)
    model_path = confined(model_ref["local_ref"], root, "MODEL_OUTSIDE_ISOLATED_ROOT")
    need(model_path.is_file() and model_path.stat().st_size <= helpers["MAX_BYTES"], "FROZEN_MODEL_FILE_REQUIRED", "binding")
    raw = model_path.read_bytes()
    need(len(raw) <= helpers["MAX_BYTES"], "FROZEN_MODEL_FILE_REQUIRED", "binding")
    need(hashlib.sha256(raw).hexdigest() == model_ref["content_hash"], "MODEL_CONTENT_HASH_MISMATCH", "binding")
    bundle = helpers["read_json_bytes"](raw)
    need(isinstance(bundle, dict) and isinstance(bundle.get("sha256"), str), "UNSUPPORTED_MODEL_BUNDLE", "binding")
    value = copy.deepcopy(bundle)
    expected = value.pop("sha256")
    need(canonical_hash(value) == expected, "MODEL_BUNDLE_HASH_MISMATCH", "binding")
    if task.get("schema_version") == "clinical-study-input@1.0":
        helpers["_real_family_admission"].frozen_context(task, bundle, need)
    else:
        need(bundle.get("test_only") is True and bundle.get("scientific_review") == "pending"
             and bundle.get("export_status") == "local_only", "MODEL_CLASSIFICATION_MISMATCH", "binding")
    need(bundle.get("schema_version") == "clinical-frozen-prediction/0.2.0"
         and bundle.get("method_id") == analysis["method_id"]
         and isinstance(bundle.get("provider_version"), str) and len(bundle["provider_version"]) == 64
         and isinstance(bundle.get("bundle"), dict),
         "MODEL_PROVIDER_BINDING_REQUIRED", "binding")
    need(bundle.get("target_policy") == (None if binary else TARGET_POLICY), "FROZEN_TARGET_POLICY_MISMATCH", "binding")
    need(bundle.get("canonical_semantics") == canonical_semantics(task),
         "FROZEN_CANONICAL_SEMANTICS_MISMATCH", "binding")
    runtime_path = root / "runtime-lock.json"
    need(runtime_path.is_file(), "MODEL_PROVIDER_BINDING_REQUIRED", "binding")
    expected_versions = read_json(runtime_path).get("prediction_provider_versions", {})
    need(analysis["method_id"] in expected_versions, "MODEL_PROVIDER_BINDING_REQUIRED", "binding")
    need(bundle["provider_version"] == expected_versions[analysis["method_id"]], "MODEL_PROVIDER_VERSION_MISMATCH", "binding")
    need(spec["cohort_id"] != bundle["bundle"].get("development_cohort_id"), "EXTERNAL_COHORT_MUST_DIFFER", stage)
    return bundle
