"""Closed v0.10 Cox penalized prediction contracts; no estimation occurs here."""
from __future__ import annotations

import copy
import hashlib
import json

INPUT_VERSION = "clinical-study-input@0.10.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-cox-penalized-v10-20261024"
MODEL_VERSION = "clinical-frozen-cox-penalized@0.10.0-candidate1"
PAYLOAD_VERSION = "clinical-cox-penalized-model@0.10.0-candidate1"
MAX_ROWS = 200
MAX_FEATURES = 12
METHODS = {"prediction.survival.cox.lasso", "prediction.survival.cox.elasticnet"}
SEMANTIC_FIELDS = ("name", "dtype", "unit", "dimension", "levels", "reference", "concept", "codebook_version")
MODEL_FIELDS = {"schema_version", "method_id", "spec", "semantics", "engine", "source", "preprocessor",
    "cv", "selected_lambda", "selected_engine_lambda", "selected_lambda_index", "coefficients", "baseline",
    "training_support", "training_subject_ids", "training_group_ids"}
MODEL_SOURCE = {"coefficient_owner": "glmnet::glmnet",
    "baseline_owner": "survival::coxph_offset_and_survfit", "preprocessing_owner": "penalized_v08_prepare"}


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def options_schema():
    name = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
    string, number = {"type": "string", "minLength": 1}, {"type": "number"}
    spec = obj({"id": name, "duration": name, "event": name, "alpha": number,
        "lambda_grid": {"type": "array", "items": number, "minItems": 2, "maxItems": 30},
        "features": {"type": "array", "minItems": 1, "maxItems": MAX_FEATURES,
            "items": obj({"name": name, "type": {"enum": ["number", "category"]}})},
        "split": obj({"method": {"enum": ["prespecified_patient", "prespecified_group"]},
            "partition_field": name, "fold_field": name, "group_field": {"anyOf": [name, {"type": "null"}]},
            "training_value": {"const": "train"}, "holdout_value": {"const": "holdout"},
            "cv_folds": {"type": "integer", "minimum": 3, "maximum": 5}}),
        "selection_rule": {"const": "min_deviance_per_event_largest_lambda_tie"},
        "missing": {"const": "training_median_mode"},
        "standardization": {"const": "training_population_sd"},
        "cohort_id": string, "canonical_identity_namespace": string,
        "survival": obj({"outcome_type": {"const": "single_event_right_censored"},
            "time_unit": {"enum": ["day", "hour"]}, "time_zero_definition": string,
            "event_definition": string, "censoring_definition": string,
            "event_code": {"type": "number", "minimum": 1, "maximum": 1},
            "censor_code": {"type": "number", "minimum": 0, "maximum": 0}, "ties": {"const": "breslow"}}),
        "horizons": {"type": "array", "items": number, "minItems": 1, "maxItems": 8}})
    return obj({"operation": {"enum": ["train", "infer"]}, "spec": spec,
        "model_ref": {"anyOf": [obj({"local_ref": string,
            "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}}), {"type": "null"}]},
        "unknown_category_policy": {"const": "reject"}})


def make_schema(base_schema):
    schema = copy.deepcopy(base_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    analysis = schema["properties"]["analysis"]
    analysis["properties"].update(method_id={"enum": sorted(METHODS)}, spec={"type": "null"},
        baseline={"type": "null"}, cox_penalized_prediction=options_schema())
    analysis["required"].append("cox_penalized_prediction")
    return schema


def code_requirements(base):
    return set(base) | {"python/clinical_methods/cox_penalized_v10_contracts.py",
        "src/clinanalysis/R/penalized_v08.R", "src/clinanalysis/R/cox_penalized_v10.R",
        "src/clinanalysis/R/clinical_cox_penalized_v10.R"}


def default_options(method_id):
    return {"operation": "train", "spec": {"id": "patient_id", "duration": "duration", "event": "event",
        "alpha": 1 if method_id.endswith(".lasso") else .5, "lambda_grid": [1., .3, .1, .03],
        "features": [{"name": "age", "type": "number"}, {"name": "severity", "type": "number"},
                     {"name": "sex", "type": "category"}],
        "split": {"method": "prespecified_patient", "partition_field": "partition", "fold_field": "fold",
            "group_field": None, "training_value": "train", "holdout_value": "holdout", "cv_folds": 3},
        "selection_rule": "min_deviance_per_event_largest_lambda_tie", "missing": "training_median_mode",
        "standardization": "training_population_sd", "cohort_id": "synthetic_cox_penalized_development",
        "canonical_identity_namespace": "synthetic_cox_penalized_v10",
        "survival": {"outcome_type": "single_event_right_censored", "time_unit": "day",
            "time_zero_definition": "Synthetic baseline at time zero",
            "event_definition": "Synthetic single terminal event",
            "censoring_definition": "Synthetic right censoring at last observation",
            "event_code": 1, "censor_code": 0, "ties": "breslow"}, "horizons": [0., 7., 14.]},
        "model_ref": None, "unknown_category_policy": "reject"}


def canonical_semantics(task):
    spec = task["analysis"]["cox_penalized_prediction"]["spec"]
    variables = {v["name"]: v for v in task["variables"]}
    def semantic(name):
        return {key: copy.deepcopy(variables[name][key]) for key in SEMANTIC_FIELDS}
    event = semantic(spec["event"])
    event.update({key: copy.deepcopy(task["outcome"][key]) for key in ("type", "definition", "event", "non_event")})
    return {"identity": {"subject_id": spec["id"], "group_id": spec["split"]["group_field"],
            "canonical_identity_namespace": spec["canonical_identity_namespace"]},
        "features": [semantic(feature["name"]) for feature in spec["features"]],
        "duration": semantic(spec["duration"]), "event": event,
        "time": {key: copy.deepcopy(task["time"][key]) for key in
            ("unit", "timezone", "index", "feature_cutoff", "outcome_window", "boundary", "delayed_entry")},
        "survival": copy.deepcopy(spec["survival"])}


def validate_time(task, need, stage):
    tm = task["time"]
    need(tm["unit"] in {"day", "hour"} and tm["timezone"] == "relative"
         and tm["boundary"] == "(0,end]" and not tm["delayed_entry"], "TIME_SEMANTICS_UNSUPPORTED", stage)
    need(tm["index"] == 0 and tm["feature_cutoff"] <= tm["index"]
         and tm["outcome_window"][0] == 0 < tm["outcome_window"][1] <= tm["label_mature_at"],
         "COX_PENALIZED_TIME_ORDER_INVALID", stage)
    if task["analysis"]["cox_penalized_prediction"]["operation"] == "train":
        need(tm["label_mature_at"] <= tm["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", stage)


def _same_spec(left, right):
    a, b = copy.deepcopy(left), copy.deepcopy(right)
    for value in (a, b):
        value.pop("cohort_id", None)
        value.pop("horizons", None)
    return a == b


def expected_runtime_binding(lock):
    """Require the exact pinned versions, paths, 15 dependency and source hashes."""
    try:
        binding = {"versions": lock["cox_penalized_runtime"],
            "package_paths": lock["cox_penalized_package_paths"],
            "dependency_hashes": lock["cox_penalized_dependency_hashes"],
            "rscript_engine": lock["rscript_engine"],
            "rscript_sha256": lock["executable_hashes"][lock["rscript_engine"]],
            "preprocessing_version": lock["cox_penalized_preprocessing_version"]}
    except (KeyError, TypeError):
        raise ValueError("FROZEN_RUNTIME_BINDING_MISMATCH") from None
    for key in ("versions", "package_paths", "dependency_hashes"):
        value = binding[key]
        if not isinstance(value, dict) or not value or not all(
                isinstance(name, str) and name and isinstance(item, str) and item for name, item in value.items()):
            raise ValueError("FROZEN_RUNTIME_BINDING_MISMATCH")
    hashes = list(binding["dependency_hashes"].values()) + [binding["rscript_sha256"], binding["preprocessing_version"]]
    if (len(binding["dependency_hashes"]) != 15
            or not isinstance(binding["rscript_engine"], str) or not binding["rscript_engine"]
            or not all(isinstance(value, str) and len(value) == 64
                       and all(char in "0123456789abcdef" for char in value) for value in hashes)):
        raise ValueError("FROZEN_RUNTIME_BINDING_MISMATCH")
    return copy.deepcopy(binding)


def _bound_model(task, rows, semantics, root, helpers):
    need, stage = helpers["need"], "binding"
    options = task["analysis"]["cox_penalized_prediction"]
    spec, reference = options["spec"], options["model_ref"]
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
        "canonical_semantics": {"type": "object"}, "model": {"type": "object"}, "test_only": {"const": True},
        "scientific_review": {"const": "pending"}, "export_status": {"const": "local_only"}})
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
    expected = runtime_lock.get("cox_penalized_provider_version")
    need(isinstance(expected, str) and len(expected) == 64, "MODEL_PROVIDER_BINDING_REQUIRED", stage)
    need(bundle["provider_version"] == expected
         and expected == helpers["file_hash"](root / "src/clinanalysis/R/cox_penalized_v10.R"),
         "MODEL_PROVIDER_VERSION_MISMATCH", stage)
    try:
        runtime_binding = expected_runtime_binding(runtime_lock)
    except ValueError:
        raise helpers["ContractBlocked"]("FROZEN_RUNTIME_BINDING_MISMATCH", stage) from None
    need(bundle["runtime_binding"] == runtime_binding, "FROZEN_RUNTIME_BINDING_MISMATCH", stage)
    need(runtime_binding["preprocessing_version"] == helpers["file_hash"](root / "src/clinanalysis/R/penalized_v08.R"),
         "MODEL_PREPROCESSING_VERSION_MISMATCH", stage)
    model = bundle["model"]
    need(set(model) == MODEL_FIELDS, "FROZEN_MODEL_FIELDS_INVALID", stage)
    need(model["schema_version"] == PAYLOAD_VERSION and model["method_id"] == bundle["method_id"],
         "FROZEN_MODEL_PAYLOAD_VERSION_MISMATCH", stage)
    need(model["semantics"] == semantics, "FROZEN_CANONICAL_SEMANTICS_MISMATCH", stage)
    need(model["source"] == MODEL_SOURCE, "FROZEN_MODEL_SOURCE_MISMATCH", stage)
    helpers["validate_schema"](model["spec"], options_schema()["properties"]["spec"], "model.spec")
    need(_same_spec(spec, model["spec"]), "FROZEN_SPEC_MISMATCH", stage)
    need(spec["cohort_id"] != model["spec"]["cohort_id"], "EXTERNAL_COHORT_MUST_DIFFER", stage)
    history_max_rows = limits["max_history_rows"] if limits else MAX_ROWS
    support = model["training_support"]
    support_fields = {"n_training", "events", "censored", "min_time", "max_followup", "last_event_time", "horizon_min", "horizon_max"}
    need(isinstance(support, dict) and set(support) == support_fields, "FROZEN_TRAINING_SUPPORT_INVALID", stage)
    helpers["validate_schema"](support, obj({key: {"type": "integer", "minimum": 0, "maximum": history_max_rows}
        if key in {"n_training", "events", "censored"} else {"type": "number", "minimum": 0}
        for key in support_fields}), "model.training_support")
    need(0 < support["min_time"] <= support["last_event_time"] <= support["max_followup"]
         and support["horizon_min"] == 0 and support["horizon_max"] == support["max_followup"]
         and support["events"] >= 8 and support["n_training"] == support["events"] + support["censored"],
         "FROZEN_TRAINING_SUPPORT_INVALID", stage)
    need(all(0 <= horizon <= support["max_followup"] for horizon in spec["horizons"]),
         "COX_PENALIZED_HORIZON_OUT_OF_SUPPORT", stage)
    for key in ("training_subject_ids", "training_group_ids"):
        values = model[key]
        need(isinstance(values, list) and len(values) <= history_max_rows
             and all(isinstance(x, str) and x and x == x.strip() for x in values)
             and len(set(values)) == len(values), "FROZEN_MODEL_IDENTITY_INVALID", stage)
    need(len(model["training_subject_ids"]) == support["n_training"], "FROZEN_MODEL_IDENTITY_INVALID", stage)
    need(not {row[spec["id"]] for row in rows} & set(model["training_subject_ids"]), "TRAINING_SUBJECT_OVERLAP", stage)
    group = spec["split"]["group_field"]
    need(bool(model["training_group_ids"]) if group else not model["training_group_ids"], "FROZEN_MODEL_IDENTITY_INVALID", stage)
    if group:
        need(not {row[group] for row in rows} & set(model["training_group_ids"]), "TRAINING_GROUP_OVERLAP", stage)
    # The sole R provider validates learned transforms, CV, coefficients, engine
    # controls and every baseline value before frozen application, without refit.
    return bundle


def validate_options(task, rows, variables, root, helpers):
    need, stage = helpers["need"], "method_applicability"
    analysis, identity, tm, outcome = task["analysis"], task["identity"], task["time"], task["outcome"]
    method, options = analysis["method_id"], analysis["cox_penalized_prediction"]
    spec, operation = options["spec"], options["operation"]
    need(spec["alpha"] == 1 if method.endswith(".lasso") else 0 < spec["alpha"] < 1, "COX_PENALIZED_ALPHA_INVALID", stage)
    grid, horizons = spec["lambda_grid"], spec["horizons"]
    need(all(value > 0 for value in grid) and all(a > b for a, b in zip(grid, grid[1:])), "COX_PENALIZED_LAMBDA_GRID_INVALID", stage)
    need(all(value >= 0 for value in horizons) and all(a < b for a, b in zip(horizons, horizons[1:])),
         "COX_PENALIZED_HORIZONS_INVALID", stage)
    need(all(spec[key].strip() == spec[key] and spec[key] for key in ("cohort_id", "canonical_identity_namespace")),
         "COX_PENALIZED_IDENTITY_NAMESPACE_INVALID", stage)
    need(analysis["effect_scale"] == "cumulative_event_probability" and analysis["variance"] == "not_applicable"
         and analysis["ci_level"] == .95, "PREDICTION_INFERENCE_OPTIONS_UNSUPPORTED", stage)
    view = next(v for v in task["views"] if v["view_id"] == analysis["required_view_ids"][0])
    need(identity["analysis_unit"] == "subject" and view["kind"] == "subject_wide"
         and identity["encounter_key"] is None, "PREDICTION_SUBJECT_VIEW_REQUIRED", stage)
    need(spec["id"] == identity["subject_key"] and identity["record_keys"] == [spec["id"]]
         and variables[spec["id"]]["role"] == "id", "PREDICTION_IDENTITY_MISMATCH", stage)
    need(all(spec[key] in variables for key in ("duration", "event")), "SURVIVAL_FIELD_MISSING", stage)
    duration, event, survival = variables[spec["duration"]], variables[spec["event"]], spec["survival"]
    need(duration["dtype"] == "number" and duration["role"] == "time"
         and duration["unit"] == tm["unit"] == survival["time_unit"], "SURVIVAL_TIME_UNIT_MISMATCH", stage)
    need(event["dtype"] == "number" and event["role"] == "outcome" and event["unit"] == event["source_unit"] == "1"
         and outcome["field"] == spec["event"] and outcome["type"] == "time_to_event" and outcome["censoring"] == "right",
         "SURVIVAL_OUTCOME_CONTRACT_MISMATCH", stage)
    need(type(outcome["event"]) in (int, float) and outcome["event"] == 1
         and type(outcome["non_event"]) in (int, float) and outcome["non_event"] == 0,
         "SURVIVAL_EVENT_CODING_MISMATCH", stage)
    need(task["cohort"]["index_event"] == survival["time_zero_definition"]
         and outcome["definition"] == survival["event_definition"]
         and all(survival[key].strip() for key in ("time_zero_definition", "event_definition", "censoring_definition")),
         "SURVIVAL_DEFINITION_MISMATCH", stage)
    if operation == "train":
        need(all(variable["available_at"] <= tm["analysis_as_of"]
                 and 0 <= variable["occurred_at"] <= tm["outcome_window"][1] for variable in (duration, event)),
             "OUTCOME_LABEL_NOT_MATURE", stage)
        need(all(row[spec[key]] is not None for row in rows for key in ("duration", "event")), "COX_PENALIZED_OUTCOME_MISSING", stage)
        need(all(0 < row[spec["duration"]] <= tm["outcome_window"][1] for row in rows), "COX_PENALIZED_DURATION_INVALID", stage)
        need(all(row[spec["event"]] in (0, 1) for row in rows), "COX_PENALIZED_EVENT_INVALID", stage)
    names = [feature["name"] for feature in spec["features"]]
    need(len(set(names)) == len(names), "UNIQUE_FEATURE_NAMES_REQUIRED", stage)
    split, group = spec["split"], spec["split"]["group_field"]
    fields = [spec["id"], spec["duration"], spec["event"], split["partition_field"], split["fold_field"]] + ([group] if group else [])
    need(len(set(fields)) == len(fields), "COX_PENALIZED_FIELD_ROLES_COLLIDE", stage)
    need(not set(names) & set(fields), "LEAKAGE_ROLE_IN_FEATURES", stage)
    need(all(name in variables for name in names), "MODEL_FIELD_MISSING", stage)
    need(not any(variables[name]["dtype"] == "id" for name in names), "ID_MODEL_FIELD_FORBIDDEN", stage)
    for feature in spec["features"]:
        variable = variables[feature["name"]]
        need(variable["role"] in {"covariate", "exposure"}, "PREDICTION_FEATURE_ROLE_INVALID", stage)
        need(variable["dtype"] == feature["type"], "PREDICTION_FEATURE_TYPE_MISMATCH", stage)
        need(variable["occurred_at"] <= variable["available_at"] <= tm["feature_cutoff"], "FUTURE_INFORMATION", stage)
    need((group is None) if split["method"] == "prespecified_patient" else group is not None,
         "COX_PENALIZED_GROUP_DEFINITION_INVALID", stage)
    split_names = [split["partition_field"], split["fold_field"]] + ([group] if group else [])
    need(all(name in variables for name in split_names), "SPLIT_FIELD_MISSING", stage)
    partition_var, fold_var = (variables[split[key]] for key in ("partition_field", "fold_field"))
    need(partition_var["dtype"] == "category" and partition_var["role"] == "split"
         and set(partition_var["levels"]) == {"train", "holdout"}
         and fold_var["dtype"] == "number" and fold_var["role"] == "split" and fold_var["unit"] == "1",
         "COX_PENALIZED_SPLIT_FIELDS_INVALID", stage)
    if group:
        need(variables[group]["dtype"] == "id" and variables[group]["role"] == "group", "COX_PENALIZED_GROUP_DEFINITION_INVALID", stage)
    need(all(variables[name]["available_at"] <= tm["index"] for name in split_names), "COX_PENALIZED_SPLIT_NOT_PRESPECIFIED", stage)
    need(all(row[name] is not None for row in rows for name in split_names), "COX_PENALIZED_SPLIT_VALUE_MISSING", stage)
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    need(task["missingness"] == {"strategy": "training_median_mode", "fit_scope": fit_scope, "exclusion_denominator": "selected_view"},
         "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    need(task["derivation"] == {"strategy": "declared_unit_conversion_only", "version": "1"}, "DERIVATION_NOT_ENABLED", stage)
    need(task["split"] == {"strategy": split["method"] if operation == "train" else "none", "group_key": group or spec["id"],
        "fold_field": split["fold_field"], "seed": 0, "fit_scope": fit_scope}, "SPLIT_CONTRACT_MISMATCH", stage)
    expected_validation = {"kind": "internal_holdout" if operation == "train" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint", "transportability": "not_evaluated"}
    if task.get("schema_version") == "clinical-study-input@1.0" and operation != "train":
        expected_validation = helpers["_real_family_admission"].external_validation(task, kind=expected_validation["kind"])
    need(task["validation"] == expected_validation,
         "PREDICTION_VALIDATION_SCOPE_INVALID", stage)
    partition, fold = split["partition_field"], split["fold_field"]
    train, holdout = [row for row in rows if row[partition] == "train"], [row for row in rows if row[partition] == "holdout"]
    need(len(train) + len(holdout) == len(rows), "COX_PENALIZED_PARTITION_VALUE_INVALID", stage)
    need(all(row[fold] == 0 for row in holdout), "COX_PENALIZED_HOLDOUT_FOLD_INVALID", stage)
    if operation == "train":
        need(options["model_ref"] is None, "TRAINING_MODEL_REF_NOT_ALLOWED", stage)
        need(bool(train) and bool(holdout), "COX_PENALIZED_PARTITION_EMPTY", stage)
        need(all(float(row[fold]).is_integer() and 1 <= row[fold] <= split["cv_folds"] for row in train), "COX_PENALIZED_TRAINING_FOLD_INVALID", stage)
        need({row[fold] for row in train} == set(range(1, split["cv_folds"] + 1)), "COX_PENALIZED_CV_FOLD_EMPTY", stage)
        need(max(horizons) <= max(row[spec["duration"]] for row in train), "COX_PENALIZED_HORIZON_OUT_OF_SUPPORT", stage)
    else:
        need(not train and len(holdout) == len(rows), "COX_PENALIZED_EXTERNAL_PARTITION_INVALID", stage)
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
        "cv_fold_counts": [{"fold": i, "n": sum(row[fold] == i for row in train)} for i in range(1, split["cv_folds"] + 1)]
                          if operation == "train" else [], "outcome_evaluated": operation == "train"}
    return flow, semantics, bundle
