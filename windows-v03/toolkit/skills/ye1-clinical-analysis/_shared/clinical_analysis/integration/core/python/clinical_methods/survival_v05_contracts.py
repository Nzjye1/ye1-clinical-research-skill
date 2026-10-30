"""Closed v0.5 contracts for formal Cox PH tests and frozen Cox prediction.

This module only validates local synthetic inputs and model bindings. The
survival provider owns complete-case estimation, formal PH statistics, frozen
design construction, Breslow hazards and prediction support.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
if __package__:
    from . import resource_budget as budget_rules
else:
    import importlib.util
    _budget_spec = importlib.util.spec_from_file_location("survival_v05_budget", Path(__file__).with_name("resource_budget.py"))
    budget_rules = importlib.util.module_from_spec(_budget_spec)
    _budget_spec.loader.exec_module(budget_rules)

INPUT_VERSION = "clinical-study-input@0.5.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-survival-v05-20261024"
MODEL_VERSION = "clinical-frozen-survival-cox@0.5.0-candidate1"
CORE_VERSION = "0.5.0-candidate1"
PREDICTION_METHOD = "prediction.survival.cox"
METHODS = {"survival.cox.association", PREDICTION_METHOD}
# Historical candidate schemas/builders remain byte-for-byte schema compatible.
# V1 request and frozen-history limits are widened only in their scoped adapters.
MAX_ROWS = 500
S = {"type": "string", "minLength": 1}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
N = {"type": "number"}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def arr(schema, minimum=0, maximum=None):
    value = {"type": "array", "items": schema, "minItems": minimum}
    if maximum is not None:
        value["maxItems"] = maximum
    return value


PH_TEST = obj({"transform": {"enum": ["km", "identity"]},
               "terms": {"const": True}, "singledf": {"const": False},
               "global": {"const": True}})
COX_PREDICTION = obj({
    "operation": {"enum": ["train", "infer"]},
    "training_subjects": arr(S, 0, MAX_ROWS),
    "holdout_subjects": arr(S, 0, MAX_ROWS),
    "horizons": arr(N, 1, 101),
    "canonical_identity_namespace": S,
    "feature_missing_policy": {"const": "complete_case"},
    "model_ref": S, "model_sha256": HASH},
    ["operation", "training_subjects", "holdout_subjects", "horizons",
     "canonical_identity_namespace", "feature_missing_policy"])
IDENTITY = obj({"canonical_identity_namespace": S,
                "training_subjects": arr(S, 1, MAX_ROWS)})
SEMANTIC_KEYS = ("time_unit", "time_zero_definition", "event_definition",
                 "censoring_definition", "event_code", "censor_code")
SURVIVAL_SEMANTICS = obj({key: S for key in SEMANTIC_KEYS})
FEATURE_SEMANTICS = arr(obj({
    "name": S, "dtype": {"enum": ["number", "category"]},
    "role": {"enum": ["exposure", "covariate", "group"]},
    "unit": S, "dimension": S, "concept": S, "occurred_at": N, "available_at": N,
    "levels": arr(S), "reference": {"type": ["string", "null"]}}), 1, 10)


def make_schema(survival_schema):
    schema = copy.deepcopy(survival_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    analysis = schema["properties"]["analysis"]
    analysis["properties"]["method_id"] = {"enum": sorted(METHODS)}
    analysis["properties"]["survival"]["properties"]["ph_test"] = PH_TEST
    analysis["properties"]["cox_prediction"] = COX_PREDICTION
    schema["properties"]["execution"]["properties"]["max_rows"]["maximum"] = MAX_ROWS
    return schema


def code_requirements(survival_code):
    return set(survival_code) | {
        "python/clinical_methods/survival_v05_contracts.py",
        "python/clinical_methods/cox_prediction_bridge.py",
        "src/clinanalysis/R/clinical_survival_v05.R"}


def canonical_survival_semantics(spec):
    return {key: spec[key] for key in SEMANTIC_KEYS}


def canonical_feature_semantics(task):
    """Freeze canonical meaning, allowing source names/units to be adapted."""
    variables = {variable["name"]: variable for variable in task["variables"]}
    fields = ("name", "dtype", "role", "unit", "dimension", "concept",
              "occurred_at", "available_at", "levels", "reference")
    return [{key: copy.deepcopy(variables[covariate["name"]][key]) for key in fields}
            for covariate in task["analysis"]["survival"]["covariates"]]


def _valid_ids(values):
    return (all(isinstance(value, str) and bool(value.strip()) and value == value.strip()
                for value in values) and len(values) == len(set(values)))


def _load_bound_model(task, rows, root, helpers):
    """Read only the selected, hash-bound local JSON model before provider use."""
    need = helpers["need"]
    prediction = task["analysis"]["cox_prediction"]
    spec = task["analysis"]["survival"]
    stage = "binding"
    modern = task.get("schema_version") == "clinical-study-input@1.0"
    model_limit = (budget_rules.request_limits(task.get("execution", {}), PREDICTION_METHOD)["max_input_bytes"]
                   if modern else helpers["MAX_BYTES"])
    need("model_ref" in prediction and "model_sha256" in prediction,
         "FROZEN_MODEL_REF_REQUIRED", stage)
    need(Path(prediction["model_ref"]).is_absolute(), "ABSOLUTE_MODEL_REF_REQUIRED", stage)
    path = helpers["confined"](prediction["model_ref"], root, "MODEL_OUTSIDE_ISOLATED_ROOT")
    need(path.is_file() and path.suffix.lower() == ".json"
         and path.stat().st_size <= model_limit, "FROZEN_MODEL_FILE_REQUIRED", stage)
    raw = path.read_bytes()
    need(len(raw) <= model_limit, "FROZEN_MODEL_FILE_REQUIRED", stage)
    need(hashlib.sha256(raw).hexdigest() == prediction["model_sha256"],
         "MODEL_CONTENT_HASH_MISMATCH", stage)
    try:
        model = helpers["read_json_bytes"](raw)
    except (UnicodeError, json.JSONDecodeError):
        raise helpers["ContractBlocked"]("FROZEN_MODEL_JSON_INVALID", stage) from None
    need(isinstance(model, dict), "UNSUPPORTED_MODEL_BUNDLE", stage)
    # Includes JSON numeric overflow (for example 1e999), not just named NaN.
    helpers["validate_schema"](model, {}, "model")
    need(model.get("schema_version") == MODEL_VERSION and model.get("core_version") == CORE_VERSION
         and model.get("method_id") == PREDICTION_METHOD, "MODEL_VERSION_MISMATCH", stage)
    if task.get("schema_version") == "clinical-study-input@1.0":
        helpers["_real_family_admission"].frozen_context(task, model, need, stage)
    else:
        need(model.get("test_only") is True and model.get("scientific_review") == "pending"
             and model.get("export_status") == "local_only", "MODEL_CLASSIFICATION_MISMATCH", stage)
    helpers["validate_schema"](model.get("model_sha256"), HASH, "model.model_sha256")
    content = copy.deepcopy(model)
    expected = content.pop("model_sha256")
    need(helpers["canonical_hash"](content) == expected, "MODEL_BUNDLE_HASH_MISMATCH", stage)
    lock_path = root / "runtime-lock.json"
    need(lock_path.is_file(), "MODEL_PROVIDER_BINDING_REQUIRED", stage)
    lock = helpers["read_json"](lock_path)
    need(isinstance(lock, dict), "MODEL_PROVIDER_BINDING_REQUIRED", stage)
    expected_provider = lock.get("cox_prediction_provider_version")
    helpers["validate_schema"](expected_provider, HASH, "runtime.cox_prediction_provider_version")
    need(model.get("provider_version") == expected_provider, "MODEL_PROVIDER_VERSION_MISMATCH", stage)
    identity_schema = copy.deepcopy(IDENTITY)
    if modern:
        identity_schema["properties"]["training_subjects"]["maxItems"] = budget_rules.ABSOLUTE_MAX_ROWS
    helpers["validate_schema"](model.get("identity"), identity_schema, "model.identity")
    identity = model["identity"]
    need(_valid_ids(identity["training_subjects"]), "MODEL_TRAINING_IDENTITY_INVALID", stage)
    need(identity["canonical_identity_namespace"] == prediction["canonical_identity_namespace"],
         "CANONICAL_IDENTITY_NAMESPACE_MISMATCH", "method_applicability")
    need(not {row[spec["subject_id"]] for row in rows}.intersection(identity["training_subjects"]),
         "INFERENCE_TRAINING_SUBJECT_OVERLAP", "method_applicability")
    helpers["validate_schema"](model.get("survival_semantics"), SURVIVAL_SEMANTICS,
                               "model.survival_semantics")
    need(model["survival_semantics"] == canonical_survival_semantics(spec),
         "FROZEN_SURVIVAL_SEMANTICS_MISMATCH", stage)
    helpers["validate_schema"](model.get("covariates"),
        helpers["_survival_contracts"].SPEC["properties"]["covariates"], "model.covariates")
    need(model.get("covariates") == spec["covariates"], "FROZEN_COVARIATES_MISMATCH", stage)
    helpers["validate_schema"](model.get("feature_semantics"), FEATURE_SEMANTICS, "model.feature_semantics")
    need(model["feature_semantics"] == canonical_feature_semantics(task),
         "FROZEN_FEATURE_SEMANTICS_MISMATCH", stage)
    # Passing the exact JSON text avoids a host language changing 1.0 to 1
    # during a parse/reserialize hop and invalidating the canonical model hash.
    text = raw.decode("utf-8-sig")
    if task.get("schema_version") == "clinical-study-input@1.0":
        need(hashlib.sha256(text.encode("utf-8")).hexdigest() == prediction["model_sha256"],
             "FROZEN_MODEL_UTF8_BOM_UNSUPPORTED", stage)
    return model, text


def validate_options(task, rows, variables, root, helpers, legacy):
    """Preserve v0.4 row semantics and add a separate v0.5 capability scope."""
    need = helpers["need"]
    stage = "method_applicability"
    analysis = task["analysis"]
    spec = analysis["survival"]
    method = analysis["method_id"]
    try:
        limits = budget_rules.request_limits(task.get("execution", {}), method)
        budget_rules.check_rows(len(rows), limits)
    except budget_rules.BudgetError as exc:
        need(False, exc.code, stage)
    need(method in METHODS, "METHOD_NOT_INTEGRATED", stage)
    need(spec["method"] == "cox_ph", "SURVIVAL_METHOD_SPEC_MISMATCH", stage)
    prediction_task = method == PREDICTION_METHOD
    model = None
    model_json = None
    if not prediction_task:
        need("ph_test" in spec, "FORMAL_PH_OPTIONS_REQUIRED", stage)
        need("cox_prediction" not in analysis, "PREDICTION_OPTIONS_REQUIRE_PREDICTION_METHOD", stage)
        need(not any(covariate["name"] == "GLOBAL" for covariate in spec["covariates"]),
             "PH_RESERVED_TERM_NAME", stage)
        semantics = legacy.validate_options(task, rows, variables, root, helpers)
        semantics["ph_diagnostic_scope"] = "formal_scaled_Schoenfeld_score_test"
        semantics["ph_test"] = copy.deepcopy(spec["ph_test"])
        return semantics, model, model_json

    need("cox_prediction" in analysis, "COX_PREDICTION_OPTIONS_REQUIRED", stage)
    need("ph_test" not in spec, "PH_TEST_REQUIRES_ASSOCIATION_METHOD", stage)
    prediction = analysis["cox_prediction"]
    operation = prediction["operation"]
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    need(analysis["effect_scale"] == "absolute_event_risk", "EFFECT_SCALE_MISMATCH", stage)
    need(analysis["variance"] == "not_applicable" and analysis["ci_level"] == .95,
         "SURVIVAL_PREDICTION_INFERENCE_OPTIONS_UNSUPPORTED", stage)
    need(task["missingness"] == {"strategy": "complete_case", "fit_scope": fit_scope,
                                 "exclusion_denominator": "selected_view"},
         "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    declared_split = task["split"]
    need(declared_split["strategy"] == ("explicit_subject_partition" if operation == "train" else "none")
         and declared_split["group_key"] == spec["subject_id"] and declared_split["fold_field"] is None
         and declared_split["fit_scope"] == fit_scope, "SPLIT_CONTRACT_MISMATCH", stage)
    expected_validation = {
        "kind": "internal_holdout" if operation == "train" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint",
        "transportability": "not_evaluated"}
    if task.get("schema_version") == "clinical-study-input@1.0" and operation != "train":
        expected_validation = helpers["_real_family_admission"].external_validation(task, kind=expected_validation["kind"])
    need(task["validation"] == expected_validation, "PREDICTION_VALIDATION_SCOPE_INVALID", stage)
    need(prediction["canonical_identity_namespace"].strip() == prediction["canonical_identity_namespace"]
         and bool(prediction["canonical_identity_namespace"].strip()), "CANONICAL_IDENTITY_NAMESPACE_REQUIRED", stage)
    need(spec["evaluation_times"] == prediction["horizons"], "SURVIVAL_PREDICTION_HORIZON_MISMATCH", stage)

    # The already-validated v0.5 scope is translated only for reuse of the
    # unchanged v0.4 time/event/feature contract; no estimation happens here.
    common = copy.deepcopy(task)
    common["analysis"].update(method_id="survival.cox.association", effect_scale="hazard_ratio", variance="model")
    common["missingness"]["fit_scope"] = "not_applicable"
    semantics = legacy.validate_options(common, rows, variables, root, helpers)
    training = prediction["training_subjects"]
    holdout = prediction["holdout_subjects"]
    need(_valid_ids(training) and _valid_ids(holdout), "SUBJECT_PARTITION_IDS_INVALID", stage)
    subjects = {row[spec["subject_id"]] for row in rows}
    features = [covariate["name"] for covariate in spec["covariates"]]
    if operation == "train":
        need("model_ref" not in prediction and "model_sha256" not in prediction,
             "TRAINING_MODEL_REF_NOT_ALLOWED", stage)
        need(bool(training) and bool(holdout), "TRAINING_SUBJECT_PARTITION_REQUIRED", stage)
        need(not set(training).intersection(holdout), "TRAINING_HOLDOUT_SUBJECT_OVERLAP", stage)
        need(set(training).union(holdout) == subjects, "SUBJECT_PARTITION_INCOMPLETE", stage)
        holdout_ids = set(holdout)
        need(all(all(row[name] is not None for name in features) for row in rows
                 if row[spec["subject_id"]] in holdout_ids), "HOLDOUT_FEATURE_MISSING", stage)
    else:
        need(not training and not holdout, "INFERENCE_PARTITION_MUST_BE_EMPTY", stage)
        need(all(all(row[name] is not None for name in features) for row in rows),
             "INFERENCE_FEATURE_MISSING", stage)
        model, model_json = _load_bound_model(task, rows, root, helpers)
    semantics.update(analysis_purpose="frozen_cox_absolute_event_risk_prediction",
                     ph_diagnostic_scope="not_requested", fit_scope=fit_scope,
                     feature_missing_policy="complete_case_training_reject_missing_application_features",
                     evaluation_grid="prespecified horizons; last training event support checked by provider")
    return semantics, model, model_json
