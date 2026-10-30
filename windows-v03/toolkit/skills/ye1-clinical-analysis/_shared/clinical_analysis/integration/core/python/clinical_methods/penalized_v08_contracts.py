"""Closed v0.8 penalized-prediction input contracts; no fitting occurs here."""
from __future__ import annotations

import copy
import hashlib
import json


INPUT_VERSION = "clinical-study-input@0.8.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-penalized-v08-20261024"
MODEL_VERSION = "clinical-frozen-penalized@0.8.0-candidate1"
PAYLOAD_VERSION = "clinical-penalized-model@0.8.0-candidate1"
MAX_ROWS = 200
MAX_FEATURES = 12
METHODS = {
    "prediction.continuous.signed.lasso", "prediction.continuous.signed.elasticnet",
    "prediction.binary.lasso", "prediction.binary.elasticnet"}
SEMANTIC_FIELDS = ("name", "dtype", "unit", "dimension", "levels", "reference", "concept", "codebook_version")
MODEL_FIELDS = {"schema_version", "method_id", "spec", "semantics", "engine", "preprocessor",
    "response_transform", "selected_lambda", "selected_engine_lambda", "selected_lambda_index", "intercept", "coefficients",
    "training_outcome_mean", "training_subject_ids", "training_group_ids"}


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def options_schema():
    name = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
    string = {"type": "string", "minLength": 1}
    number = {"type": "number"}
    spec = obj({
        "id": name, "outcome": name, "family": {"enum": ["gaussian", "binomial"]},
        "alpha": number,
        "lambda_grid": {"type": "array", "items": number, "minItems": 2, "maxItems": 30},
        "features": {"type": "array", "minItems": 1, "maxItems": MAX_FEATURES,
            "items": obj({"name": name, "type": {"enum": ["number", "category"]}})},
        "split": obj({"method": {"enum": ["prespecified_patient", "prespecified_group"]},
            "partition_field": name, "fold_field": name,
            "group_field": {"anyOf": [name, {"type": "null"}]},
            "training_value": {"const": "train"}, "holdout_value": {"const": "holdout"},
            "cv_folds": {"type": "integer", "minimum": 3, "maximum": 5}}),
        "selection_rule": {"const": "min_mean_loss_largest_lambda_tie"},
        "missing": {"const": "training_median_mode"},
        "standardization": {"const": "training_population_sd"},
        "response_transform": {"enum": ["training_center_scale", "identity"]},
        "clinical_threshold": {"type": ["number", "null"]},
        "cohort_id": string, "canonical_identity_namespace": string})
    return obj({"operation": {"enum": ["train", "evaluate", "infer"]}, "spec": spec,
        "model_ref": {"anyOf": [obj({"local_ref": string,
            "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}), {"type": "null"}]},
        "unknown_category_policy": {"const": "reject"}})


def make_schema(base_schema):
    schema = copy.deepcopy(base_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    analysis = schema["properties"]["analysis"]
    analysis["properties"].update(method_id={"enum": sorted(METHODS)},
        spec={"type": "null"}, baseline={"type": "null"}, penalized_prediction=options_schema())
    analysis["required"].append("penalized_prediction")
    return schema


def code_requirements(base):
    return set(base) | {"python/clinical_methods/penalized_v08_contracts.py",
        "src/clinanalysis/R/penalized_v08.R", "src/clinanalysis/R/clinical_penalized_v08.R"}


def default_options(method_id):
    binary = method_id.startswith("prediction.binary.")
    return {"operation": "train", "spec": {
        "id": "patient_id", "outcome": "outcome", "family": "binomial" if binary else "gaussian",
        "alpha": 1 if method_id.endswith(".lasso") else .5,
        "lambda_grid": [1., .3, .1, .03],
        "features": [{"name": "age", "type": "number"}, {"name": "severity", "type": "number"},
                     {"name": "sex", "type": "category"}],
        "split": {"method": "prespecified_patient", "partition_field": "partition", "fold_field": "fold",
            "group_field": None, "training_value": "train", "holdout_value": "holdout", "cv_folds": 3},
        "selection_rule": "min_mean_loss_largest_lambda_tie", "missing": "training_median_mode",
        "standardization": "training_population_sd",
        "response_transform": "identity" if binary else "training_center_scale",
        "clinical_threshold": .5 if binary else None, "cohort_id": "synthetic_penalized_development",
        "canonical_identity_namespace": "synthetic_penalized_v08"},
        "model_ref": None, "unknown_category_policy": "reject"}


def canonical_semantics(task):
    spec = task["analysis"]["penalized_prediction"]["spec"]
    variables = {v["name"]: v for v in task["variables"]}
    outcome = {key: copy.deepcopy(variables[spec["outcome"]][key]) for key in SEMANTIC_FIELDS}
    outcome.update({key: copy.deepcopy(task["outcome"][key])
                    for key in ("type", "definition", "event", "non_event")})
    return {"identity": {"subject_id": spec["id"], "group_id": spec["split"]["group_field"],
            "canonical_identity_namespace": spec["canonical_identity_namespace"]},
        "features": [{key: copy.deepcopy(variables[feature["name"]][key]) for key in SEMANTIC_FIELDS}
                     for feature in spec["features"]],
        "outcome": outcome, "time": {key: copy.deepcopy(task["time"][key])
            for key in ("unit", "timezone", "index", "feature_cutoff", "outcome_window", "boundary", "delayed_entry")}}


def validate_time(task, need, stage):
    tm = task["time"]
    need(tm["unit"] == "hour" and tm["timezone"] == "relative" and tm["boundary"] == "[start,end]"
         and not tm["delayed_entry"], "TIME_SEMANTICS_UNSUPPORTED", stage)
    need(tm["feature_cutoff"] <= tm["index"] <= tm["outcome_window"][0] < tm["outcome_window"][1]
         <= tm["label_mature_at"], "PENALIZED_TIME_ORDER_INVALID", stage)
    if task["analysis"]["penalized_prediction"]["operation"] != "infer":
        need(tm["label_mature_at"] <= tm["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", stage)


def _same_spec(left, right):
    a, b = copy.deepcopy(left), copy.deepcopy(right)
    a.pop("cohort_id", None)
    b.pop("cohort_id", None)
    return a == b


def expected_runtime_binding(lock):
    """Copy the exact execution-lock snapshot required by a frozen wrapper.

    The runtime-lock checker owns installed paths and pinned versions. This
    helper requires a complete snapshot, including all ten dependency hashes;
    it never substitutes the currently loaded package version for file hashes.
    An incomplete snapshot raises ValueError for the caller to report.
    """
    try:
        binding = {"versions": lock["penalized_runtime"],
            "package_paths": lock["penalized_package_paths"],
            "dependency_hashes": lock["penalized_dependency_hashes"],
            "rscript_engine": lock["rscript_engine"],
            "rscript_sha256": lock["executable_hashes"][lock["rscript_engine"]]}
    except (KeyError, TypeError):
        raise ValueError("FROZEN_RUNTIME_BINDING_MISMATCH") from None
    for key in ("versions", "package_paths", "dependency_hashes"):
        value = binding[key]
        if not isinstance(value, dict) or not value or not all(
                isinstance(name, str) and name and isinstance(item, str) and item for name, item in value.items()):
            raise ValueError("FROZEN_RUNTIME_BINDING_MISMATCH")
    hashes = list(binding["dependency_hashes"].values()) + [binding["rscript_sha256"]]
    if (len(binding["dependency_hashes"]) != 10
            or not isinstance(binding["rscript_engine"], str) or not binding["rscript_engine"]
            or not all(isinstance(value, str) and len(value) == 64
                       and all(char in "0123456789abcdef" for char in value) for value in hashes)):
        raise ValueError("FROZEN_RUNTIME_BINDING_MISMATCH")
    return copy.deepcopy(binding)


def _bound_model(task, rows, semantics, root, helpers):
    need = helpers["need"]
    prediction = task["analysis"]["penalized_prediction"]
    spec, reference = prediction["spec"], prediction["model_ref"]
    stage = "binding"
    need(reference is not None, "FROZEN_MODEL_REF_REQUIRED", stage)
    limits = (helpers["_resource_budget"].resolve(task["execution"], task["analysis"]["method_id"])
              if task.get("schema_version") == "clinical-study-input@1.0" else None)
    artifact_max_bytes = limits["max_input_bytes"] if limits else helpers["MAX_BYTES"]
    path = helpers["confined"](reference["local_ref"], root, "MODEL_OUTSIDE_ISOLATED_ROOT")
    need(path.is_file() and path.suffix.lower() == ".json" and path.stat().st_size <= artifact_max_bytes,
         "FROZEN_MODEL_FILE_REQUIRED", stage)
    raw = path.read_bytes()
    need(len(raw) <= artifact_max_bytes, "FROZEN_MODEL_FILE_REQUIRED", stage)
    need(hashlib.sha256(raw).hexdigest() == reference["content_hash"], "MODEL_CONTENT_HASH_MISMATCH", stage)
    try:
        bundle = helpers["read_json_bytes"](raw)
    except (UnicodeError, json.JSONDecodeError):
        raise helpers["ContractBlocked"]("FROZEN_MODEL_JSON_INVALID", stage) from None
    wrapper = obj({"schema_version": {"const": MODEL_VERSION}, "method_id": {"enum": sorted(METHODS)},
        "provider_version": helpers["HASH"], "runtime_binding": {"type": "object"},
        "canonical_semantics": {"type": "object"},
        "model": {"type": "object"}, "test_only": {"const": True},
        "scientific_review": {"const": "pending"}, "export_status": {"const": "local_only"}})
    need(isinstance(bundle, dict) and isinstance(bundle.get("runtime_binding"), dict),
         "FROZEN_RUNTIME_BINDING_MISMATCH", stage)
    if task.get("schema_version") == "clinical-study-input@1.0":
        wrapper = helpers["_real_family_admission"].wrapper_schema(task, wrapper)
    helpers["validate_schema"](bundle, wrapper, "model")
    if task.get("schema_version") == "clinical-study-input@1.0":
        helpers["_real_family_admission"].frozen_context(task, bundle, need, stage)
    need(bundle["method_id"] == task["analysis"]["method_id"], "MODEL_METHOD_MISMATCH", stage)
    need(bundle["canonical_semantics"] == semantics, "FROZEN_CANONICAL_SEMANTICS_MISMATCH", stage)
    lock_path = root / "runtime-lock.json"
    need(lock_path.is_file(), "MODEL_PROVIDER_BINDING_REQUIRED", stage)
    runtime_lock = helpers["read_json"](lock_path)
    expected = runtime_lock.get("penalized_provider_version")
    need(isinstance(expected, str) and len(expected) == 64, "MODEL_PROVIDER_BINDING_REQUIRED", stage)
    need(bundle["provider_version"] == expected, "MODEL_PROVIDER_VERSION_MISMATCH", stage)
    need(expected == helpers["file_hash"](root / "src/clinanalysis/R/penalized_v08.R"),
         "MODEL_PROVIDER_VERSION_MISMATCH", stage)
    try:
        runtime_binding = expected_runtime_binding(runtime_lock)
    except ValueError:
        raise helpers["ContractBlocked"]("FROZEN_RUNTIME_BINDING_MISMATCH", stage) from None
    need(bundle["runtime_binding"] == runtime_binding, "FROZEN_RUNTIME_BINDING_MISMATCH", stage)
    model = bundle["model"]
    need(set(model) == MODEL_FIELDS, "FROZEN_MODEL_FIELDS_INVALID", stage)
    need(model["schema_version"] == PAYLOAD_VERSION and model["method_id"] == bundle["method_id"],
         "FROZEN_MODEL_PAYLOAD_VERSION_MISMATCH", stage)
    need(model["semantics"] == semantics, "FROZEN_CANONICAL_SEMANTICS_MISMATCH", stage)
    helpers["validate_schema"](model["spec"], options_schema()["properties"]["spec"], "model.spec")
    need(_same_spec(spec, model["spec"]), "FROZEN_SPEC_MISMATCH", stage)
    need(spec["cohort_id"] != model["spec"]["cohort_id"], "EXTERNAL_COHORT_MUST_DIFFER", stage)
    for key in ("training_subject_ids", "training_group_ids"):
        values = model[key]
        if limits:
            need(isinstance(values, list) and len(values) <= limits["max_history_rows"],
                 "RESOURCE_HISTORY_BUDGET_EXCEEDED", stage)
        need(isinstance(values, list) and all(isinstance(x, str) and x and x == x.strip() for x in values)
             and len(set(values)) == len(values), "FROZEN_MODEL_IDENTITY_INVALID", stage)
    need(bool(model["training_subject_ids"]), "FROZEN_MODEL_IDENTITY_INVALID", stage)
    need(not set(row[spec["id"]] for row in rows) & set(model["training_subject_ids"]),
         "TRAINING_SUBJECT_OVERLAP", stage)
    group = spec["split"]["group_field"]
    need(bool(model["training_group_ids"]) if group else not model["training_group_ids"],
         "FROZEN_MODEL_IDENTITY_INVALID", stage)
    if group:
        need(not set(row[group] for row in rows) & set(model["training_group_ids"]),
             "TRAINING_GROUP_OVERLAP", stage)
    # The numerical owner validates every learned transform, coefficient and
    # engine control before frozen application; none are recomputed here.
    return bundle


def validate_options(task, rows, variables, root, helpers):
    need = helpers["need"]
    stage = "method_applicability"
    analysis = task["analysis"]
    method = analysis["method_id"]
    options = analysis["penalized_prediction"]
    spec, operation = options["spec"], options["operation"]
    binary = method.startswith("prediction.binary.")
    need(spec["family"] == ("binomial" if binary else "gaussian"), "PENALIZED_FAMILY_MISMATCH", stage)
    need(spec["alpha"] == 1 if method.endswith(".lasso") else 0 < spec["alpha"] < 1,
         "PENALIZED_ALPHA_INVALID", stage)
    grid = spec["lambda_grid"]
    need(all(value > 0 for value in grid) and all(left > right for left, right in zip(grid, grid[1:])),
         "PENALIZED_LAMBDA_GRID_INVALID", stage)
    need(spec["response_transform"] == ("identity" if binary else "training_center_scale"),
         "PENALIZED_RESPONSE_TRANSFORM_INVALID", stage)
    threshold = spec["clinical_threshold"]
    need((threshold is None or 0 < threshold < 1) if binary else threshold is None,
         "CLINICAL_THRESHOLD_INVALID", stage)
    need(analysis["effect_scale"] == ("probability" if binary else "outcome units")
         and analysis["variance"] == "not_applicable" and analysis["ci_level"] == .95,
         "PREDICTION_INFERENCE_OPTIONS_UNSUPPORTED", stage)
    view = next(v for v in task["views"] if v["view_id"] == analysis["required_view_ids"][0])
    identity = task["identity"]
    need(identity["analysis_unit"] == "subject" and view["kind"] == "subject_wide"
         and identity["encounter_key"] is None, "PREDICTION_SUBJECT_VIEW_REQUIRED", stage)
    need(spec["id"] == identity["subject_key"] and identity["record_keys"] == [spec["id"]]
         and variables[spec["id"]]["role"] == "id", "PREDICTION_IDENTITY_MISMATCH", stage)
    need(spec["outcome"] == task["outcome"]["field"] and spec["outcome"] in variables,
         "OUTCOME_CONTRACT_MISMATCH", stage)
    outcome = variables[spec["outcome"]]
    need(outcome["role"] == "outcome", "OUTCOME_ROLE_INVALID", stage)
    need(outcome["dtype"] == "number" and task["outcome"]["censoring"] == "none",
         "PENALIZED_NUMERIC_OUTCOME_REQUIRED", stage)
    if binary:
        need(task["outcome"]["type"] == "binary" and outcome["unit"] == outcome["source_unit"] == "1"
             and type(task["outcome"]["event"]) in (int, float) and task["outcome"]["event"] == 1
             and type(task["outcome"]["non_event"]) in (int, float) and task["outcome"]["non_event"] == 0,
             "BINARY_CODING_MISMATCH", stage)
    else:
        need(task["outcome"]["type"] == "continuous" and task["outcome"]["event"] is None
             and task["outcome"]["non_event"] is None, "CONTINUOUS_OUTCOME_REQUIRED", stage)
    if operation != "infer":
        tm = task["time"]
        need(outcome["available_at"] <= tm["analysis_as_of"]
             and tm["outcome_window"][0] <= outcome["occurred_at"] <= tm["outcome_window"][1],
             "OUTCOME_LABEL_NOT_MATURE", stage)
        need(all(row[spec["outcome"]] is not None for row in rows), "PENALIZED_OUTCOME_MISSING", stage)
        if binary:
            need(all(row[spec["outcome"]] in (0, 1) for row in rows), "BINARY_CODING_MISMATCH", stage)
    names = [feature["name"] for feature in spec["features"]]
    need(1 <= len(names) <= MAX_FEATURES, "PENALIZED_FEATURE_LIMIT", stage)
    need(len(set(names)) == len(names), "UNIQUE_FEATURE_NAMES_REQUIRED", stage)
    split = spec["split"]
    group = split["group_field"]
    fields = [spec["id"], spec["outcome"], split["partition_field"], split["fold_field"]] + ([group] if group else [])
    need(len(set(fields)) == len(fields), "PENALIZED_FIELD_ROLES_COLLIDE", stage)
    need(not set(names) & set(fields), "LEAKAGE_ROLE_IN_FEATURES", stage)
    need(all(name in variables for name in names), "MODEL_FIELD_MISSING", stage)
    need(not any(variables[name]["dtype"] == "id" for name in names), "ID_MODEL_FIELD_FORBIDDEN", stage)
    for feature in spec["features"]:
        variable = variables[feature["name"]]
        need(variable["role"] in {"covariate", "exposure"}, "PREDICTION_FEATURE_ROLE_INVALID", stage)
        need(variable["dtype"] == feature["type"], "PREDICTION_FEATURE_TYPE_MISMATCH", stage)
        need(variable["occurred_at"] <= variable["available_at"] <= task["time"]["feature_cutoff"],
             "FUTURE_INFORMATION", stage)
    need((group is None) if split["method"] == "prespecified_patient" else group is not None,
         "PENALIZED_GROUP_DEFINITION_INVALID", stage)
    split_names = [split["partition_field"], split["fold_field"]] + ([group] if group else [])
    need(all(name in variables for name in split_names), "SPLIT_FIELD_MISSING", stage)
    partition_var, fold_var = (variables[split[key]] for key in ("partition_field", "fold_field"))
    need(partition_var["dtype"] == "category" and partition_var["role"] == "split"
         and set(partition_var["levels"]) == {"train", "holdout"}
         and fold_var["dtype"] == "number" and fold_var["role"] == "split" and fold_var["unit"] == "1",
         "PENALIZED_SPLIT_FIELDS_INVALID", stage)
    if group:
        need(variables[group]["dtype"] == "id" and variables[group]["role"] == "group",
             "PENALIZED_GROUP_DEFINITION_INVALID", stage)
    need(all(variables[name]["available_at"] <= task["time"]["index"] for name in split_names),
         "PENALIZED_SPLIT_NOT_PRESPECIFIED", stage)
    need(all(row[name] is not None for row in rows for name in split_names), "PENALIZED_SPLIT_VALUE_MISSING", stage)
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    need(task["missingness"] == {"strategy": "training_median_mode", "fit_scope": fit_scope,
        "exclusion_denominator": "selected_view"}, "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    need(task["derivation"] == {"strategy": "declared_unit_conversion_only", "version": "1"},
         "DERIVATION_NOT_ENABLED", stage)
    need(task["split"] == {"strategy": split["method"] if operation == "train" else "none",
        "group_key": group or spec["id"], "fold_field": split["fold_field"], "seed": 0, "fit_scope": fit_scope},
        "SPLIT_CONTRACT_MISMATCH", stage)
    expected_validation = {"kind": "internal_holdout" if operation == "train"
        else "synthetic_frozen_application" if operation == "evaluate" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint",
        "transportability": "not_evaluated"}
    if task.get("schema_version") == "clinical-study-input@1.0" and operation != "train":
        expected_validation = helpers["_real_family_admission"].external_validation(task, kind=expected_validation["kind"])
    need(task["validation"] == expected_validation, "PREDICTION_VALIDATION_SCOPE_INVALID", stage)
    partition, fold = split["partition_field"], split["fold_field"]
    train = [row for row in rows if row[partition] == "train"]
    holdout = [row for row in rows if row[partition] == "holdout"]
    need(len(train) + len(holdout) == len(rows), "PENALIZED_PARTITION_VALUE_INVALID", stage)
    need(all(row[fold] == 0 for row in holdout), "PENALIZED_HOLDOUT_FOLD_INVALID", stage)
    if operation == "train":
        need(options["model_ref"] is None, "TRAINING_MODEL_REF_NOT_ALLOWED", stage)
        need(bool(train) and bool(holdout), "PENALIZED_PARTITION_EMPTY", stage)
        need(all(row[fold].is_integer() and 1 <= row[fold] <= split["cv_folds"] for row in train),
             "PENALIZED_TRAINING_FOLD_INVALID", stage)
        need({row[fold] for row in train} == set(range(1, split["cv_folds"] + 1)),
             "PENALIZED_CV_FOLD_EMPTY", stage)
    else:
        need(not train and len(holdout) == len(rows), "PENALIZED_EXTERNAL_PARTITION_INVALID", stage)
    if group:
        group_partitions, group_folds = {}, {}
        for row in rows:
            group_partitions.setdefault(row[group], set()).add(row[partition])
        need(all(len(values) == 1 for values in group_partitions.values()), "GROUP_CROSSES_PARTITIONS", stage)
        for row in train:
            group_folds.setdefault(row[group], set()).add(row[fold])
        need(all(len(values) == 1 for values in group_folds.values()), "GROUP_CROSSES_FOLDS", stage)
    semantics = canonical_semantics(task)
    bundle = None if operation == "train" else _bound_model(task, rows, semantics, root, helpers)
    flow = {"operation": operation, "n_input": len(rows), "n_train": len(train), "n_holdout": len(holdout),
        "cv_fold_counts": [{"fold": fold_id, "n": sum(row[fold] == fold_id for row in train)}
                           for fold_id in range(1, split["cv_folds"] + 1)] if operation == "train" else [],
        "outcome_evaluated": operation != "infer"}
    return flow, semantics, bundle
