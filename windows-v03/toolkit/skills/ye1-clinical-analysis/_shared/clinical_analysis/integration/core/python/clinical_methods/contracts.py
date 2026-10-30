"""Strict local synthetic input validation for clinanalysis' shared task branch.

This module validates and maps one selected view. It is not a task runner and
does not perform estimation, retry, method selection, or export approval.
"""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import gzip
import json
import math
from pathlib import Path
import sys
import importlib.util

INPUT_VERSION = "clinical-study-input@0.1.0-candidate1"
RESULT_VERSION = "clinical-analysis-result@0.1.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-b1a-20261023"
METHODS = {"baseline.table1", "association.linear", "association.logistic"}
MAX_BYTES = 2097152
MAX_ROWS = 200
REQUIRED_CODE = {"src/clinanalysis/R/" + name for name in ("run.R", "contracts.R", "registry.R", "clinical_common.R")} | {
    "python/clinical_methods/" + name for name in ("association.py", "bridge.py", "contracts.py", "resource_budget.py")
} | {"schemas/input.schema.json", "tools/run_core.R", "config/resource-budget-profiles.json", "src/clinanalysis/R/clinical_resource_budget.R"}


class ContractBlocked(ValueError):
    def __init__(self, code, stage="input_contract", missing=None):
        super().__init__(code)
        self.code, self.stage, self.missing = code, stage, missing or []


def need(condition, code, stage="input_contract", missing=None):
    if not condition:
        raise ContractBlocked(code, stage, missing)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan_hash(task):
    value = copy.deepcopy(task)
    value.pop("plan_hash", None)
    value.get("execution", {}).pop("output_dir", None)
    return canonical_hash(value)


def object_schema(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


S = {"type": "string", "minLength": 1}
N = {"type": "number"}
BOOL = {"type": "boolean"}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
NAME = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
NULLSTR = {"type": ["string", "null"]}
SCALAR = {"type": ["string", "number", "boolean", "null"]}


def arr(schema, minimum=0):
    return {"type": "array", "items": schema, "minItems": minimum}


def dictionary(values):
    return {"type": "object", "additionalProperties": values}


CATEGORY = object_schema({"levels": arr(S, 2), "reference": S})
SPLINE = object_schema({"method": {"const": "restricted_cubic"}, "knots": arr(N, 3)})
SENSITIVITY = object_schema({
    "label": S, "rationale": S,
    "where": arr(object_schema({"field": NAME, "op": {"enum": ["eq", "ne", "lt", "le", "gt", "ge", "in"]},
                              "value": {"type": ["string", "number", "boolean", "array"]}}), 1),
    "covariates": arr(NAME), "nonlinear": {"anyOf": [SPLINE, {"type": "null"}]},
    "covariance": {"enum": ["HC3", "classical", "model", "HC0"]}}, ["label", "rationale", "where"])
SPEC = object_schema({
    "model": {"enum": ["linear", "logistic"]}, "outcome": NAME, "exposure": NAME,
    "covariates": arr(NAME), "missing": {"const": "complete_case"},
    "covariance": {"enum": ["HC3", "classical", "model", "HC0"]},
    "categorical": dictionary(CATEGORY), "row_unit": {"enum": ["subject", "encounter"]},
    "independent": {"const": True}, "key": arr(NAME, 1), "subject_id": NAME,
    "event": SCALAR, "non_event": SCALAR,
    "nonlinear": {"anyOf": [SPLINE, {"type": "null"}]},
    "subgroup": {"anyOf": [object_schema({"field": NAME, "levels": arr(S, 2), "reference": S}), {"type": "null"}]},
    "sensitivity": arr(SENSITIVITY)},
    ["model", "outcome", "exposure", "covariates", "missing", "covariance", "categorical",
     "row_unit", "independent", "key", "subject_id"])
BASELINE = object_schema({
    "group": NAME,
    "variables": arr(object_schema({"name": NAME, "type": {"enum": ["continuous", "categorical", "binary"]},
                                  "summary": {"enum": ["mean_sd", "median_iqr", None]}, "levels": arr(S)}), 1),
    "categorical_denominator": {"enum": ["nonmissing", "all"]}, "include_overall": BOOL})
VARIABLE = object_schema({
    "name": NAME, "dtype": {"enum": ["id", "number", "category"]},
    "role": {"enum": ["id", "exposure", "covariate", "group", "outcome", "split", "time"]},
    "unit": S, "source_unit": S, "dimension": S,
    "conversion": object_schema({"scale": N, "offset": N}),
    "levels": arr(S), "reference": NULLSTR, "codes": dictionary(S),
    "missing_codes": arr({"type": "string"}), "occurred_at": N, "available_at": N,
    "concept": S, "codebook_version": S, "aggregation": {"const": "already_one_value_per_row"}})
VIEW = object_schema({
    "view_id": NAME, "kind": S, "source_ids": arr(NAME, 1), "local_ref": S,
    "content_hash": HASH, "column_map": dictionary(NAME), "grain": S,
    "keys": arr(NAME, 1),
    "joins": arr(object_schema({"cardinality": S, "left_unique": BOOL, "right_unique": BOOL,
                              "rows_before": {"type": "integer", "minimum": 0},
                              "rows_after": {"type": "integer", "minimum": 0}, "evidence_ref": S})),
    "transformation_hash": HASH, "counts_ref": S})
INPUT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": INPUT_VERSION,
    **object_schema({
        "schema_version": {"const": INPUT_VERSION}, "study_id": S, "plan_hash": HASH,
        "purpose": S, "estimand": S, "protocol_revision": S,
        "sources": arr(object_schema({"source_id": NAME, "database": S, "snapshot": S,
                   "period": S, "recipe_version": S, "recipe_hash": HASH,
                   "source_fingerprint": HASH, "evidence_refs": arr(S, 1),
                   "verification_status": {"enum": ["declared", "verified_synthetic_bytes"]}}), 1),
        "identity": object_schema({"subject_key": NAME, "record_keys": arr(NAME, 1), "scope": S,
                   "analysis_unit": {"enum": ["subject", "encounter"]}, "repeated_policy": S,
                   "encounter_key": NULLSTR, "cluster_key": NULLSTR}),
        "variables": arr(VARIABLE, 1),
        "cohort": object_schema({"target_population": S, "inclusion": arr(S, 1), "exclusion": arr(S),
                   "index_event": S, "selection_order": arr(S, 1)}),
        "time": object_schema({"unit": S, "timezone": S, "index": N, "feature_cutoff": N,
                   "outcome_window": {"type": "array", "items": N, "minItems": 2, "maxItems": 2},
                   "label_mature_at": N, "analysis_as_of": N, "boundary": S, "delayed_entry": BOOL}),
        "outcome": object_schema({"field": NAME, "type": S, "event": SCALAR, "non_event": SCALAR,
                   "definition": S, "censoring": S}),
        "design": object_schema({"kind": S, "inference_unit": S, "variance_unit": S,
                   "strata": NULLSTR, "psu": NULLSTR, "domain": NULLSTR}),
        "weights": object_schema({"kind": S, "field": NULLSTR, "target": NULLSTR,
                   "construction": NULLSTR, "variance_semantics": NULLSTR}),
        "views": arr(VIEW, 1),
        "analysis": object_schema({"method_id": S, "required_view_ids": arr(NAME, 1),
                   "spec": {"anyOf": [SPEC, {"type": "null"}]},
                   "baseline": {"anyOf": [BASELINE, {"type": "null"}]},
                   "effect_scale": S, "variance": S, "ci_level": N, "assumptions": arr(S, 1)}),
        "missingness": object_schema({"strategy": S, "fit_scope": S, "exclusion_denominator": S}),
        "derivation": object_schema({"strategy": S, "version": S}),
        "split": object_schema({"strategy": S, "group_key": NAME, "fold_field": NULLSTR,
                   "seed": {"type": "integer"}, "fit_scope": S}),
        "validation": object_schema({"kind": S, "overlap_status": S, "transportability": S}),
        "compatibility": object_schema({"pooling": BOOL, "identity_overlap": S, "status": S,
                   "reason": S}),
        "execution": object_schema({"mode": S, "authorization_ref": S, "output_dir": S,
                   "max_rows": {"type": "integer", "minimum": 1, "maximum": MAX_ROWS},
                   "max_bytes": {"type": "integer", "minimum": 1, "maximum": MAX_BYTES},
                   "expected_source_hashes": dictionary(HASH), "expected_code_hashes": dictionary(HASH)}),
        "export_policy": object_schema({"mode": S, "small_cell_policy": S})})}

_budget_loader = importlib.util.spec_from_file_location("clinical_project_resource_budget", Path(__file__).with_name("resource_budget.py"))
_resource_budget = importlib.util.module_from_spec(_budget_loader)
_budget_loader.loader.exec_module(_resource_budget)

_study_loader = importlib.util.spec_from_file_location("clinical_study_origin_contract", Path(__file__).with_name("study_input.py"))
_study_input = importlib.util.module_from_spec(_study_loader)
_study_loader.loader.exec_module(_study_input)
STUDY_INPUT_VERSION = _study_input.INPUT_VERSION
STUDY_SCHEMA = _study_input.make_schema(INPUT_SCHEMA)
_family_loader = importlib.util.spec_from_file_location("clinical_v1_real_families", Path(__file__).with_name("real_family_admission.py"))
_real_family_admission = importlib.util.module_from_spec(_family_loader)
_family_loader.loader.exec_module(_real_family_admission)
STUDY_READY_FAMILIES = frozenset({"prediction", "survival", "survival_v05", "survival_v06",
                                  "penalized_v08", "interpretation_v09", "cox_penalized_v10"})

_prediction_loader = importlib.util.spec_from_file_location(
    "clinical_prediction_contract_extensions", Path(__file__).with_name("prediction_contracts.py"))
_prediction_contracts = importlib.util.module_from_spec(_prediction_loader)
_prediction_loader.loader.exec_module(_prediction_contracts)
PREDICTION_INPUT_VERSION = _prediction_contracts.INPUT_VERSION
PREDICTION_SCHEMA = _prediction_contracts.make_schema(INPUT_SCHEMA)

_association_plan_loader = importlib.util.spec_from_file_location(
    "clinical_association_plan_contract_extensions", Path(__file__).with_name("association_plan_contracts.py"))
_association_plan_contracts = importlib.util.module_from_spec(_association_plan_loader)
_association_plan_loader.loader.exec_module(_association_plan_contracts)
ASSOCIATION_PLAN_INPUT_VERSION = _association_plan_contracts.INPUT_VERSION
ASSOCIATION_PLAN_SCHEMA = _association_plan_contracts.make_schema(INPUT_SCHEMA, SPEC)
_plan_admission_loader = importlib.util.spec_from_file_location(
    "clinical_v1_association_plan", Path(__file__).with_name("association_plan_admission.py"))
_association_plan_admission = importlib.util.module_from_spec(_plan_admission_loader)
_plan_admission_loader.loader.exec_module(_association_plan_admission)
_psm_admission_loader = importlib.util.spec_from_file_location(
    "clinical_v1_continuous_psm", Path(__file__).with_name("psm_v07_admission.py"))
_psm_v07_admission = importlib.util.module_from_spec(_psm_admission_loader)
_psm_admission_loader.loader.exec_module(_psm_v07_admission)

_survival_loader = importlib.util.spec_from_file_location(
    "clinical_survival_contract_extensions", Path(__file__).with_name("survival_contracts.py"))
_survival_contracts = importlib.util.module_from_spec(_survival_loader)
_survival_loader.loader.exec_module(_survival_contracts)
SURVIVAL_INPUT_VERSION = _survival_contracts.INPUT_VERSION
SURVIVAL_SCHEMA = _survival_contracts.make_schema(INPUT_SCHEMA)

_survival_v05_loader = importlib.util.spec_from_file_location(
    "clinical_survival_v05_contract_extensions", Path(__file__).with_name("survival_v05_contracts.py"))
_survival_v05_contracts = importlib.util.module_from_spec(_survival_v05_loader)
_survival_v05_loader.loader.exec_module(_survival_v05_contracts)
SURVIVAL_V05_INPUT_VERSION = _survival_v05_contracts.INPUT_VERSION
SURVIVAL_V05_SCHEMA = _survival_v05_contracts.make_schema(SURVIVAL_SCHEMA)

_survival_v06_loader = importlib.util.spec_from_file_location(
    "clinical_survival_v06_contract_extensions", Path(__file__).with_name("survival_v06_contracts.py"))
_survival_v06_contracts = importlib.util.module_from_spec(_survival_v06_loader)
_survival_v06_loader.loader.exec_module(_survival_v06_contracts)
SURVIVAL_V06_INPUT_VERSION = _survival_v06_contracts.INPUT_VERSION
SURVIVAL_V06_SCHEMA = _survival_v06_contracts.make_schema(SURVIVAL_V05_SCHEMA)

_psm_v07_loader = importlib.util.spec_from_file_location(
    "clinical_psm_v07_contract_extensions", Path(__file__).with_name("psm_v07_contracts.py"))
_psm_v07_contracts = importlib.util.module_from_spec(_psm_v07_loader)
_psm_v07_loader.loader.exec_module(_psm_v07_contracts)
PSM_V07_INPUT_VERSION = _psm_v07_contracts.INPUT_VERSION
PSM_V07_SCHEMA = _psm_v07_contracts.make_schema(INPUT_SCHEMA)

_penalized_v08_loader = importlib.util.spec_from_file_location(
    "clinical_penalized_v08_contract_extensions", Path(__file__).with_name("penalized_v08_contracts.py"))
_penalized_v08_contracts = importlib.util.module_from_spec(_penalized_v08_loader)
_penalized_v08_loader.loader.exec_module(_penalized_v08_contracts)
PENALIZED_V08_INPUT_VERSION = _penalized_v08_contracts.INPUT_VERSION
PENALIZED_V08_SCHEMA = _penalized_v08_contracts.make_schema(INPUT_SCHEMA)

_interpretation_v09_loader = importlib.util.spec_from_file_location(
    "clinical_interpretation_v09_contract_extensions", Path(__file__).with_name("interpretation_v09_contracts.py"))
_interpretation_v09_contracts = importlib.util.module_from_spec(_interpretation_v09_loader)
_interpretation_v09_loader.loader.exec_module(_interpretation_v09_contracts)
INTERPRETATION_V09_INPUT_VERSION = _interpretation_v09_contracts.INPUT_VERSION
INTERPRETATION_V09_SCHEMA = _interpretation_v09_contracts.make_schema(INPUT_SCHEMA, _penalized_v08_contracts)

_cox_penalized_v10_loader = importlib.util.spec_from_file_location(
    "clinical_cox_penalized_v10_contract_extensions", Path(__file__).with_name("cox_penalized_v10_contracts.py"))
_cox_penalized_v10_contracts = importlib.util.module_from_spec(_cox_penalized_v10_loader)
_cox_penalized_v10_loader.loader.exec_module(_cox_penalized_v10_contracts)
COX_PENALIZED_V10_INPUT_VERSION = _cox_penalized_v10_contracts.INPUT_VERSION
COX_PENALIZED_V10_SCHEMA = _cox_penalized_v10_contracts.make_schema(INPUT_SCHEMA)


def input_union_schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "clinical-study-input-union@0.10.0-candidate1",
            "anyOf": [INPUT_SCHEMA, PREDICTION_SCHEMA, ASSOCIATION_PLAN_SCHEMA, SURVIVAL_SCHEMA, SURVIVAL_V05_SCHEMA,
                      SURVIVAL_V06_SCHEMA, PSM_V07_SCHEMA, PENALIZED_V08_SCHEMA, INTERPRETATION_V09_SCHEMA,
                      COX_PENALIZED_V10_SCHEMA]}

def required_code_for_task(task):
    if task.get("schema_version") == STUDY_INPUT_VERSION:
        common = set(REQUIRED_CODE) | {"python/clinical_methods/study_input.py", "python/clinical_methods/study_artifacts.py", "schemas/study-input.schema.json", "schemas/study-result.schema.json", "src/clinanalysis/R/clinical_study.R", "src/clinanalysis/R/clinical_study_contract.R", _real_family_admission.SELF_CODE}
        if task.get("analysis", {}).get("method_id") in _association_plan_admission.METHODS:
            return _association_plan_admission.code_requirements(common, _association_plan_contracts)
        if task.get("analysis", {}).get("method_id") in _psm_v07_admission.METHODS:
            return _psm_v07_admission.code_requirements(common, _psm_v07_contracts)
        return _real_family_admission.code_requirements(task, common, globals())
    if task.get("schema_version") == COX_PENALIZED_V10_INPUT_VERSION:
        return _cox_penalized_v10_contracts.code_requirements(REQUIRED_CODE)
    if task.get("schema_version") == INTERPRETATION_V09_INPUT_VERSION:
        return _interpretation_v09_contracts.code_requirements(
            _penalized_v08_contracts.code_requirements(REQUIRED_CODE))
    if task.get("schema_version") == PENALIZED_V08_INPUT_VERSION:
        return _penalized_v08_contracts.code_requirements(REQUIRED_CODE)
    if task.get("schema_version") == PSM_V07_INPUT_VERSION:
        return _psm_v07_contracts.code_requirements(REQUIRED_CODE)
    if task.get("schema_version") == SURVIVAL_V06_INPUT_VERSION:
        return _survival_v06_contracts.code_requirements(
            _survival_v05_contracts.code_requirements(_survival_contracts.code_requirements(REQUIRED_CODE)))
    if task.get("schema_version") == SURVIVAL_V05_INPUT_VERSION:
        return _survival_v05_contracts.code_requirements(_survival_contracts.code_requirements(REQUIRED_CODE))
    if task.get("schema_version") == SURVIVAL_INPUT_VERSION:
        return _survival_contracts.code_requirements(REQUIRED_CODE)
    if task.get("schema_version") == ASSOCIATION_PLAN_INPUT_VERSION:
        return _association_plan_contracts.code_requirements(REQUIRED_CODE)
    return (_prediction_contracts.code_requirements(REQUIRED_CODE)
            if task.get("schema_version") == PREDICTION_INPUT_VERSION else set(REQUIRED_CODE))


def validate_schema(value, schema, field="input"):
    """Validate the deliberately small JSON Schema vocabulary used here.

    The exported schema is standard JSON Schema. This stdlib implementation
    avoids installing a validator and is tested against closed nested objects.
    """
    supported = {"$schema", "$id", "title", "description", "$comment", "type", "anyOf", "const", "enum",
                 "properties", "required", "additionalProperties", "items", "minItems", "maxItems",
                 "minLength", "maxLength", "pattern", "minimum", "maximum", "uniqueItems",
                 "allOf", "if", "then", "else"}
    need(not set(schema) - supported, "SCHEMA_KEYWORD_NOT_IMPLEMENTED")
    for option in schema.get("allOf", []):
        validate_schema(value, option, field)
    if "if" in schema:
        try:
            validate_schema(value, schema["if"], field)
            condition = True
        except ContractBlocked:
            condition = False
        branch = "then" if condition else "else"
        if branch in schema:
            validate_schema(value, schema[branch], field)
    if "anyOf" in schema:
        matched = False
        for option in schema["anyOf"]:
            try:
                validate_schema(value, option, field)
                matched = True
                break
            except ContractBlocked:
                pass
        need(matched, "SCHEMA_TYPE_OR_FIELDS_INVALID", missing=[field])
    types = schema.get("type")
    if types:
        types = types if isinstance(types, list) else [types]
        checks = {"object": isinstance(value, dict), "array": isinstance(value, list),
                  "string": isinstance(value, str), "number": type(value) in (int, float),
                  "integer": type(value) is int, "boolean": type(value) is bool, "null": value is None}
        need(any(checks[t] for t in types), "SCHEMA_TYPE_INVALID", missing=[field])
    if "const" in schema:
        need(value == schema["const"] and type(value) is type(schema["const"]), "SCHEMA_VALUE_INVALID", missing=[field])
    if "enum" in schema:
        need(any(value == x and type(value) is type(x) for x in schema["enum"]), "SCHEMA_VALUE_INVALID", missing=[field])
    if type(value) in (int, float):
        need(math.isfinite(value), "NONFINITE_VALUE", missing=[field])
        need(value >= schema.get("minimum", -math.inf) and value <= schema.get("maximum", math.inf),
             "SCHEMA_RANGE_INVALID", missing=[field])
    if isinstance(value, str):
        import re
        need(len(value) >= schema.get("minLength", 0), "SCHEMA_EMPTY_STRING", missing=[field])
        need(len(value) <= schema.get("maxLength", math.inf), "SCHEMA_STRING_LENGTH", missing=[field])
        if "pattern" in schema:
            need(re.fullmatch(schema["pattern"], value) is not None, "SCHEMA_VALUE_INVALID", missing=[field])
    if isinstance(value, list):
        if schema.get("uniqueItems", False):
            # JSON equality distinguishes booleans from numbers; 1 and 1.0 are equal.
            def equal(a, b):
                if type(a) is bool or type(b) is bool:
                    return type(a) is type(b) and a == b
                if isinstance(a, dict) and isinstance(b, dict):
                    return a.keys() == b.keys() and all(equal(a[k], b[k]) for k in a)
                if isinstance(a, list) and isinstance(b, list):
                    return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b))
                return a == b
            need(not any(equal(value[i], value[j]) for i in range(len(value)) for j in range(i)),
                 "SCHEMA_ARRAY_DUPLICATE", missing=[field])
        need(len(value) >= schema.get("minItems", 0) and len(value) <= schema.get("maxItems", math.inf),
             "SCHEMA_ARRAY_LENGTH", missing=[field])
        for item in value:
            validate_schema(item, schema.get("items", {}), field + "[]")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        missing = [field + "." + x for x in schema.get("required", []) if x not in value]
        need(not missing, "SCHEMA_REQUIRED_FIELD", missing=missing)
        extra = set(value) - set(props)
        additional = schema.get("additionalProperties", True)
        need(additional is not False or not extra, "SCHEMA_UNKNOWN_FIELD", missing=[field])
        for key, item in value.items():
            validate_schema(item, props.get(key, additional if isinstance(additional, dict) else {}),
                            field + "." + key if key in props else field + ".<entry>")


UNIT_CONVERSIONS = {
    ("1", "1"): (1, 0), ("percent", "1"): (0.01, 0),
    ("year", "year"): (1, 0), ("month", "year"): (1 / 12, 0),
    ("kg", "kg"): (1, 0), ("lb", "kg"): (0.45359237, 0),
    ("cm", "cm"): (1, 0), ("m", "cm"): (100, 0),
    ("mg/dL", "mg/dL"): (1, 0), ("umol/L", "mg/dL"): (1 / 88.4, 0),
    ("mmol/L", "mmol/L"): (1, 0), ("mmHg", "mmHg"): (1, 0),
    ("hour", "hour"): (1, 0), ("minute", "hour"): (1 / 60, 0),
    ("day", "day"): (1, 0), ("hour", "day"): (1 / 24, 0)}
UNIT_DIMENSIONS = {"1": "dimensionless", "year": "time", "kg": "mass", "cm": "length",
                   "mg/dL": "creatinine_concentration", "mmol/L": "concentration",
                   "mmHg": "pressure", "hour": "time", "day": "time"}


def confined(path, root, code):
    p = Path(path).resolve()
    need(p.is_relative_to(root), code, "binding")
    return p


def transformation_hash(task, view):
    value = {"variables": task["variables"], "column_map": view["column_map"], "identity": task["identity"], "time": task["time"]}
    if task.get("schema_version") == STUDY_INPUT_VERSION:
        value["view_protocol"] = {k:view.get(k) for k in ("format","unselected_columns","selection","location_policy")}
    return canonical_hash(value)


def _validate_task(task, core_root):
    study_task = isinstance(task, dict) and task.get("schema_version") == STUDY_INPUT_VERSION
    study_plan = study_task and task.get("analysis", {}).get("method_id") in _association_plan_admission.METHODS
    study_psm = study_task and task.get("analysis", {}).get("method_id") in _psm_v07_admission.METHODS
    study_family = _real_family_admission.family_for_task(task) if study_task else None
    cox_penalized_v10_task = isinstance(task, dict) and task.get("schema_version") == COX_PENALIZED_V10_INPUT_VERSION
    interpretation_v09_task = isinstance(task, dict) and task.get("schema_version") == INTERPRETATION_V09_INPUT_VERSION
    penalized_v08_task = isinstance(task, dict) and task.get("schema_version") == PENALIZED_V08_INPUT_VERSION
    psm_v07_task = study_psm or (isinstance(task, dict) and task.get("schema_version") == PSM_V07_INPUT_VERSION)
    prediction_task = isinstance(task, dict) and task.get("schema_version") == PREDICTION_INPUT_VERSION
    association_plan_task = study_plan or (isinstance(task, dict) and task.get("schema_version") == ASSOCIATION_PLAN_INPUT_VERSION)
    survival_v05_task = isinstance(task, dict) and task.get("schema_version") == SURVIVAL_V05_INPUT_VERSION
    survival_v06_task = isinstance(task, dict) and task.get("schema_version") == SURVIVAL_V06_INPUT_VERSION
    survival_task = isinstance(task, dict) and task.get("schema_version") in (
        SURVIVAL_INPUT_VERSION, SURVIVAL_V05_INPUT_VERSION, SURVIVAL_V06_INPUT_VERSION)
    if study_family is not None:
        need(study_family["family"] in STUDY_READY_FAMILIES, "REAL_FAMILY_NOT_INTEGRATED", "input_contract")
        prediction_task = study_family["flags"]["prediction_task"]
        survival_task = study_family["flags"]["survival_task"]
        survival_v05_task = study_family["flags"]["survival_v05_task"]
        survival_v06_task = study_family["flags"]["survival_v06_task"]
        penalized_v08_task = study_family["flags"]["penalized_v08_task"]
        interpretation_v09_task = study_family["flags"]["interpretation_v09_task"]
        cox_penalized_v10_task = study_family["flags"]["cox_penalized_v10_task"]
    study_schema = (_association_plan_admission.make_schema(STUDY_SCHEMA, ASSOCIATION_PLAN_SCHEMA) if study_plan else
                    _psm_v07_admission.make_schema(STUDY_SCHEMA, PSM_V07_SCHEMA) if study_psm else
                    _real_family_admission.schema_for_task(task, STUDY_SCHEMA, globals())
                    if study_family is not None else STUDY_SCHEMA)
    validate_schema(task, study_schema if study_task else COX_PENALIZED_V10_SCHEMA if cox_penalized_v10_task else INTERPRETATION_V09_SCHEMA if interpretation_v09_task else PENALIZED_V08_SCHEMA if penalized_v08_task else PSM_V07_SCHEMA if psm_v07_task else PREDICTION_SCHEMA if prediction_task else ASSOCIATION_PLAN_SCHEMA if association_plan_task else SURVIVAL_V06_SCHEMA if survival_v06_task else SURVIVAL_V05_SCHEMA if survival_v05_task else SURVIVAL_SCHEMA if survival_task else INPUT_SCHEMA)
    if study_task:
        try:
            _resource_budget.resolve(task["execution"], _resource_budget.method(task))
        except _resource_budget.BudgetError as exc:
            raise ContractBlocked(exc.code, "resource_budget", [json.dumps(exc.detail, sort_keys=True)]) from None
    cox_prediction_task = survival_v06_task or (
        survival_v05_task and task["analysis"]["method_id"] == _survival_v05_contracts.PREDICTION_METHOD)
    operation = (task["analysis"]["cox_penalized_prediction"]["operation"] if cox_penalized_v10_task
                 else "infer" if interpretation_v09_task else task["analysis"]["penalized_prediction"]["operation"] if penalized_v08_task
                 else task["analysis"]["prediction"]["operation"] if prediction_task else None)
    if study_family is not None and cox_prediction_task:
        operation = study_family["operation"]
    root = Path(core_root).resolve()
    stage = "binding"
    admission = _study_input.admit(task, root, globals()) if study_task else None
    if study_task:
        expected_purpose = ("prediction" if study_family is not None and study_family["family"] in {"prediction", "penalized_v08"}
                            else "interpretation" if study_family is not None and study_family["family"] == "interpretation_v09"
                            else "survival" if study_family is not None else
                            "descriptive" if task["analysis"]["method_id"] == "baseline.table1" else "association")
        need(task["purpose"] == expected_purpose, "ANALYSIS_PURPOSE_MISMATCH", stage)
        auth_ref = admission["authorization_ref"]
    else:
        need(task["purpose"] == "SYNTHETIC_TEST_ONLY" and task["execution"]["mode"] == "synthetic",
             "REAL_DATA_NOT_ENABLED", stage)
        auth_ref = (_cox_penalized_v10_contracts.AUTHORIZATION_REF if cox_penalized_v10_task else
                    _interpretation_v09_contracts.AUTHORIZATION_REF if interpretation_v09_task else
                    _penalized_v08_contracts.AUTHORIZATION_REF if penalized_v08_task else
                    _psm_v07_contracts.AUTHORIZATION_REF if psm_v07_task else
                    _prediction_contracts.AUTHORIZATION_REF if prediction_task else
                    _association_plan_contracts.AUTHORIZATION_REF if association_plan_task else
                    _survival_v06_contracts.AUTHORIZATION_REF if survival_v06_task else
                    _survival_v05_contracts.AUTHORIZATION_REF if survival_v05_task else
                    _survival_contracts.AUTHORIZATION_REF if survival_task else AUTHORIZATION_REF)
        need(task["execution"]["authorization_ref"] == auth_ref, "AUTHORIZATION_REF_REQUIRED", stage)
    need(task["plan_hash"] == plan_hash(task), "PLAN_HASH_MISMATCH", stage)
    confined(task["execution"]["output_dir"], admission["project"] if study_task else root, "OUTPUT_OUTSIDE_ISOLATED_ROOT")
    need(task["export_policy"] == {"mode": "local_only", "small_cell_policy": "review_required"},
         "EXPORT_POLICY_UNSUPPORTED", stage)
    codes = task["execution"]["expected_code_hashes"]
    need(set(codes) == required_code_for_task(task), "CODE_BINDING_INCOMPLETE", stage)
    for relative, expected in codes.items():
        code_file = confined(root / relative, root, "CODE_OUTSIDE_ISOLATED_ROOT")
        need(code_file.is_file() and file_hash(code_file) == expected, "CODE_HASH_MISMATCH", stage)
    sources = {x["source_id"]: x for x in task["sources"]}
    need(len(sources) == len(task["sources"]), "DUPLICATE_SOURCE_ID", stage)
    need(set(task["execution"]["expected_source_hashes"]) == set(sources), "SOURCE_BINDING_INCOMPLETE", stage)
    for sid, source in sources.items():
        need(source["source_fingerprint"] == task["execution"]["expected_source_hashes"][sid], "SOURCE_HASH_MISMATCH", stage)
        need(source["verification_status"] == ("local_bytes_bound" if study_task else "verified_synthetic_bytes"), "SOURCE_NOT_VERIFIED", stage)
    stage = "view_semantics"
    views = {v["view_id"]: v for v in task["views"]}
    need(len(views) == len(task["views"]), "DUPLICATE_VIEW_ID", stage)
    selected = task["analysis"]["required_view_ids"]
    need(len(selected) == 1 and len(set(selected)) == 1, "SINGLE_SELECTED_VIEW_REQUIRED", stage)
    need(selected[0] in views, "REQUIRED_VIEW_MISSING", stage)
    view = views[selected[0]]
    need(len(view["source_ids"]) == 1 and view["source_ids"][0] in sources, "SOURCE_VIEW_LINK_INVALID", stage)
    source = sources[view["source_ids"][0]]
    database = source["database"].upper()
    need(database not in {"JADER"}, "ADAPTER_NOT_VALIDATED", stage)
    need(database not in {"FAERS"}, "REPORT_DATA_NOT_CLINICAL_PATIENTS", stage)
    need(database not in {"NHANES", "CHARLS"}, "SURVEY_PROVIDER_INTEGRATION_PENDING", stage)
    need(database in ({"MIMIC", "EICU", "SELF_FILE", "VITALDB", "USER_CLINICAL"} if study_task else {"MIMIC", "EICU", "SELF_FILE"}), "ADAPTER_NOT_VALIDATED", stage)
    need(view["kind"] in ({"survival_subject"} if survival_task else {"subject_wide", "encounter_wide"}), "VIEW_KIND_UNSUPPORTED", stage)
    need(not task["compatibility"]["pooling"], "CROSS_SOURCE_POOLING_NOT_ENABLED", stage)
    if not prediction_task and not cox_prediction_task and not penalized_v08_task and not interpretation_v09_task and not cox_penalized_v10_task:
        need(task["validation"]["kind"] == "none", "VALIDATION_METHOD_NOT_ENABLED", stage)
    design = task["design"]
    if design["kind"] == "survey":
        need(all(design[k] for k in ("strata", "psu", "domain")), "SURVEY_DESIGN_FIELDS_REQUIRED", stage)
    descriptive_repeats = study_task and task["analysis"]["method_id"] == "baseline.table1" and design["kind"] == "descriptive"
    need((design["kind"] == "iid" or descriptive_repeats) and all(design[k] is None for k in ("strata", "psu", "domain")),
         "DESIGN_UNSUPPORTED", stage)
    need(task["weights"] == {"kind": "none", "field": None, "target": None, "construction": None,
                             "variance_semantics": None}, "WEIGHTS_UNSUPPORTED", stage)
    identity = task["identity"]
    need(identity["repeated_policy"] == ("descriptive_only" if descriptive_repeats else "reject") and identity["scope"] == "within_source",
         "IDENTITY_POLICY_UNSUPPORTED", stage)
    need(identity["cluster_key"] is None, "CLUSTERED_IDENTITY_UNSUPPORTED", stage)
    if descriptive_repeats:
        need(identity["analysis_unit"] == view["grain"] == design["inference_unit"] == "encounter" and design["variance_unit"] == "not_applicable", "GRAIN_UNIT_MISMATCH", stage)
    elif psm_v07_task:
        need(identity["analysis_unit"] == view["grain"] == design["inference_unit"] == "subject"
             and design["variance_unit"] == "matched_pair", "GRAIN_UNIT_MISMATCH", stage)
    else:
        need(identity["analysis_unit"] == view["grain"] == design["inference_unit"] == design["variance_unit"],
             "GRAIN_UNIT_MISMATCH", stage)
    need(identity["record_keys"] == view["keys"], "RECORD_KEY_MISMATCH", stage)
    for join in view["joins"]:
        need(join["cardinality"] == "one_to_one" and join["left_unique"] and join["right_unique"]
             and join["rows_before"] == join["rows_after"], "JOIN_CARDINALITY_INVALID", stage)
    variables = {v["name"]: v for v in task["variables"]}
    need(len(variables) == len(task["variables"]), "DUPLICATE_VARIABLE", stage)
    need(set(variables) == set(view["column_map"]) and len(set(view["column_map"].values())) == len(variables),
         "COLUMN_MAP_INVALID", stage)
    need(identity["subject_key"] in variables and variables[identity["subject_key"]]["dtype"] == "id",
         "SUBJECT_ID_CHARACTER_REQUIRED", stage)
    need(all(k in variables and variables[k]["dtype"] == "id" for k in identity["record_keys"]),
         "RECORD_ID_CHARACTER_REQUIRED", stage)
    need(view["transformation_hash"] == transformation_hash(task, view), "TRANSFORMATION_HASH_MISMATCH", stage)
    tm = task["time"]
    if study_plan:
        _association_plan_admission.validate_time(task, need, stage)
    elif study_psm:
        _psm_v07_admission.validate_time(task, need, stage)
    elif study_task and study_family is not None:
        _real_family_admission.validate_time(task, need, globals(), stage)
    elif study_task:
        _study_input.validate_time(task, need)
    elif cox_penalized_v10_task:
        _cox_penalized_v10_contracts.validate_time(task, need, stage)
    elif interpretation_v09_task:
        _interpretation_v09_contracts.validate_time(task, need, stage, _penalized_v08_contracts)
    elif penalized_v08_task:
        _penalized_v08_contracts.validate_time(task, need, stage)
    elif psm_v07_task:
        _psm_v07_contracts.validate_time(task, need, stage)
    elif survival_task:
        _survival_contracts.validate_time(task, need, stage)
    else:
        need(tm["unit"] == "hour" and tm["timezone"] == "relative" and tm["boundary"] == "[start,end]"
             and not tm["delayed_entry"], "TIME_SEMANTICS_UNSUPPORTED", stage)
        need(tm["index"] <= tm["feature_cutoff"] <= tm["outcome_window"][0] < tm["outcome_window"][1]
             <= tm["label_mature_at"], "OUTCOME_LABEL_NOT_MATURE", stage)
        if operation != "infer":
            need(tm["label_mature_at"] <= tm["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", stage)
    for variable in variables.values():
        if psm_v07_task and variable["name"] == task["analysis"]["psm"]["treatment"]:
            need(variable["occurred_at"] == variable["available_at"] == tm["index"],
                 "PSM_TREATMENT_TIMING_INVALID", stage)
        if (psm_v07_task and variable["name"] in task["analysis"]["psm"]["covariates"]
                and variable["name"] not in {identity["subject_key"], task["analysis"]["psm"]["treatment"],
                                             task["analysis"]["psm"]["outcome"]}):
            need(variable["occurred_at"] <= variable["available_at"] <= tm["index"],
                 "PSM_POST_TREATMENT_COVARIATE", stage)
        if study_task:
            _study_input.validate_variable_time(task, variable, need)
        elif variable["role"] in {"exposure", "covariate", "group"}:
            feature_limit = (tm["index"] if psm_v07_task and variable["name"] == task["analysis"]["psm"]["treatment"]
                             else tm["feature_cutoff"])
            need(variable["occurred_at"] <= variable["available_at"] <= feature_limit, "FUTURE_INFORMATION", stage)
        if not study_task:
            need(variable["available_at"] >= variable["occurred_at"], "AVAILABILITY_BEFORE_MEASUREMENT", stage)
        expected = UNIT_CONVERSIONS.get((variable["source_unit"], variable["unit"]))
        declared_identity_unit = study_task and variable["unit"] == variable["source_unit"] and variable["unit"].lower() not in {"unknown", "unverified", "na", "n/a"} and bool(variable["dimension"].strip())
        if expected is None and declared_identity_unit:
            expected = (1, 0)
        need(expected is not None, "UNIT_UNKNOWN_OR_INCOMPATIBLE", stage)
        need(variable["dimension"] == UNIT_DIMENSIONS.get(variable["unit"], variable["dimension"] if declared_identity_unit else None), "UNIT_DIMENSION_MISMATCH", stage)
        psm_treatment = (psm_v07_task and variable["name"] == task["analysis"]["psm"]["treatment"]
                         and variable["dtype"] == "number" and variable["source_unit"] == variable["unit"] == "1")
        if psm_treatment:
            # A declared numeric treatment code may use an explicit affine
            # recoding. Its canonical result must still be exactly 0 or 1.
            need(variable["conversion"]["scale"] != 0, "UNIT_CONVERSION_INVALID", stage)
        else:
            need(math.isclose(variable["conversion"]["scale"], expected[0], rel_tol=1e-12, abs_tol=1e-15)
                 and variable["conversion"]["offset"] == expected[1], "UNIT_CONVERSION_INVALID", stage)
        if variable["dtype"] in {"id", "category"}:
            need(variable["unit"] == variable["source_unit"] == "1", "CATEGORY_OR_ID_UNIT_INVALID", stage)
        if variable["dtype"] == "category":
            need(len(variable["levels"]) >= 2 and len(set(variable["levels"])) == len(variable["levels"])
                 and variable["reference"] in variable["levels"]
                 and set(variable["codes"].values()) == set(variable["levels"]), "CATEGORY_MAPPING_INVALID", stage)
        else:
            need(not variable["levels"] and not variable["codes"] and variable["reference"] is None,
                 "NONCATEGORY_LEVELS_INVALID", stage)
    file = _study_input.resolve_view(task, view, admission, globals()) if study_task else confined(view["local_ref"], root, "VIEW_OUTSIDE_ISOLATED_ROOT")
    need(file.is_file() and (view["format"] in {"csv", "csv_gzip"} if study_task else file.suffix.lower() == ".csv"), "CSV_VIEW_REQUIRED", stage)
    need(file.stat().st_size <= task["execution"]["max_bytes"], "INPUT_BYTE_LIMIT", stage)
    raw = file.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == view["content_hash"] == source["source_fingerprint"], "VIEW_CONTENT_HASH_MISMATCH", stage)
    ignored_endpoints = set()
    if cox_penalized_v10_task and operation == "infer":
        cox_spec = task["analysis"]["cox_penalized_prediction"]["spec"]
        ignored_endpoints = {cox_spec["duration"], cox_spec["event"]}
        need(ignored_endpoints <= set(variables), "SURVIVAL_FIELD_MISSING", stage)
    try:
        if study_task and view["format"] == "csv_gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
                decoded = compressed.read(task["execution"]["max_decoded_bytes"] + 1)
        else:
            decoded = raw
        if study_task:
            need(len(decoded) <= task["execution"]["max_decoded_bytes"], "DECODED_INPUT_BYTE_LIMIT", stage)
        text = decoded.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        need(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)), "CSV_HEADER_INVALID", stage)
        mapped_columns = set(view["column_map"].values())
        optional_columns = {view["column_map"][name] for name in ignored_endpoints}
        if study_task:
            unselected = view["unselected_columns"]
            need(len(unselected) == len(set(unselected)) and not mapped_columns.intersection(unselected), "COLUMN_PROJECTION_CONFLICT", stage)
            need(set(reader.fieldnames) == mapped_columns.union(unselected), "CSV_UNDECLARED_OR_MISSING_COLUMN", stage)
        else:
            need(set(reader.fieldnames) <= mapped_columns
                 and mapped_columns - optional_columns <= set(reader.fieldnames), "CSV_UNDECLARED_OR_MISSING_COLUMN", stage)
        raw_rows = []
        for raw_row in reader:
            need(len(raw_rows) < task["execution"]["max_rows"], "INPUT_ROW_LIMIT", stage,
                 ["max_rows=" + str(task["execution"]["max_rows"]) + "; actual_rows_at_least=" + str(len(raw_rows)+1)])
            raw_rows.append(raw_row)
    except (UnicodeError, csv.Error, gzip.BadGzipFile, EOFError):
        raise ContractBlocked("CSV_ENCODING_OR_FORMAT_INVALID", stage) from None
    need(0 < len(raw_rows) <= task["execution"]["max_rows"], "INPUT_ROW_LIMIT", stage)
    need(all(join["rows_after"] == len(raw_rows) for join in view["joins"]), "JOIN_ROW_COUNT_MISMATCH", stage)
    rows = []
    for raw_row in raw_rows:
        need(None not in raw_row and all(v is not None for v in raw_row.values()), "CSV_ROW_WIDTH_INVALID", stage)
        row = {}
        for name, variable in variables.items():
            if name in ignored_endpoints:
                # Inference binds endpoint definitions but never parses labels,
                # even if the optional endpoint columns are present in the CSV.
                row[name] = None
                continue
            value = raw_row[view["column_map"][name]]
            if value in variable["missing_codes"]:
                row[name] = None
            elif variable["dtype"] == "id":
                need(bool(value) and value == value.strip(), "ID_MISSING_OR_WHITESPACE", stage)
                row[name] = value
            elif variable["dtype"] == "category":
                need(value in variable["codes"], "UNDECLARED_CATEGORY", stage)
                row[name] = variable["codes"][value]
            else:
                try:
                    number = float(value)
                except (ValueError, OverflowError):
                    raise ContractBlocked("NUMERIC_VALUE_REQUIRED", stage) from None
                need(math.isfinite(number), "NONFINITE_VALUE", stage)
                row[name] = number * variable["conversion"]["scale"] + variable["conversion"]["offset"]
                need(math.isfinite(row[name]), "NONFINITE_CONVERTED_VALUE", stage)
        rows.append(row)
    if study_task:
        try:
            limits = _resource_budget.resolve(task["execution"], _resource_budget.method(task))
            _resource_budget.check_task(task, len(rows), limits)
            _resource_budget.check_owner_capacity(task, len(rows))
        except _resource_budget.BudgetError as exc:
            raise ContractBlocked(exc.code, "resource_budget", [json.dumps(exc.detail, sort_keys=True)]) from None
    input_view_rows = len(rows)
    if study_task and view.get("selection") is not None:
        need(len({tuple(r[k] for k in identity["record_keys"]) for r in rows}) == len(rows), "DUPLICATE_RECORD_KEY", "view_semantics")
    if study_task:
        rows = _study_input.select_engineering_records(task, view, rows, globals())
    subject = identity["subject_key"]
    need(all(r[subject] is not None for r in rows), "SUBJECT_ID_MISSING", stage)
    folds = task["split"]["fold_field"]
    if folds:
        need(folds in variables, "SPLIT_FIELD_MISSING", stage)
        memberships = {}
        for row in rows:
            memberships.setdefault(row[subject], set()).add(row[folds])
        need(all(len(values) == 1 for values in memberships.values()), "SUBJECT_CROSSES_FOLDS", stage)
    if not descriptive_repeats:
        need(len({r[subject] for r in rows}) == len(rows), "REPEATED_SUBJECT_REQUIRES_OTHER_METHOD", stage)
    need(len({tuple(r[k] for k in identity["record_keys"]) for r in rows}) == len(rows), "DUPLICATE_RECORD_KEY", stage)
    need(not view["joins"], "JOIN_EVIDENCE_NOT_VERIFIED", stage)
    if not prediction_task and not cox_prediction_task and not penalized_v08_task and not interpretation_v09_task and not cox_penalized_v10_task:
        need(task["split"]["strategy"] == "none" and folds is None and task["split"]["fit_scope"] == "not_applicable",
             "SPLIT_METHOD_NOT_ENABLED", stage)
    stage = "method_applicability"
    analysis = task["analysis"]
    if cox_penalized_v10_task:
        family_checked = _real_family_admission.validate_options(task, rows, variables, root, globals()) if study_family is not None else None
        if family_checked is not None:
            cox_flow, cox_semantics, frozen_cox_model = family_checked["flow"], family_checked["semantics"], family_checked["frozen_model"]
        else:
            cox_flow, cox_semantics, frozen_cox_model = _cox_penalized_v10_contracts.validate_options(task, rows, variables, root, globals())
        ledger = {"source_rows": len(rows), "view_rows": len(rows), "subjects": len(rows), "encounters": None,
            "missing_by_variable": {key: None if key in ignored_endpoints else sum(row[key] is None for row in rows)
                                    for key in variables},
            "conversions": [{"variable": key, "from": value["source_unit"], "to": value["unit"], **value["conversion"]}
                            for key, value in variables.items() if key not in ignored_endpoints],
            "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True,
            "cox_penalized_prediction": cox_flow}
        return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            **({"origin_context": family_checked["context"], "core_family": {"name": study_family["family"], "method_id": analysis["method_id"], "operation": operation},
                "frozen_model_origin": family_checked["frozen_origin"]} if family_checked is not None else {}),
            "cox_penalized_options": copy.deepcopy(analysis["cox_penalized_prediction"]),
            "cox_penalized_semantics": cox_semantics, "frozen_cox_penalized_model": frozen_cox_model,
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                "code_hashes": codes, "authorization_ref": auth_ref,
                "model_ref_hash": (analysis["cox_penalized_prediction"]["model_ref"]["content_hash"]
                    if frozen_cox_model is not None else None)}}
    if interpretation_v09_task:
        family_checked = _real_family_admission.validate_options(task, rows, variables, root, globals()) if study_family is not None else None
        if family_checked is not None:
            interpretation_flow, interpretation_semantics, frozen_model, frozen_explainer = (family_checked["flow"], family_checked["semantics"], family_checked["frozen_model"], family_checked["frozen_explainer"])
        else:
            interpretation_flow, interpretation_semantics, frozen_model, frozen_explainer = (
                _interpretation_v09_contracts.validate_options(task, rows, variables, root, globals(), _penalized_v08_contracts))
        ledger = {"source_rows": len(rows), "view_rows": len(rows), "subjects": len(rows), "encounters": None,
            "missing_by_variable": {key: sum(row[key] is None for row in rows) for key in variables},
            "conversions": [{"variable": key, "from": value["source_unit"], "to": value["unit"], **value["conversion"]}
                            for key, value in variables.items()],
            "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True,
            "interpretation": interpretation_flow}
        return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            **({"origin_context": family_checked["context"], "core_family": {"name": study_family["family"], "method_id": analysis["method_id"], "operation": operation},
                "frozen_model_origin": family_checked["frozen_origin"]} if family_checked is not None else {}),
            "interpretation_options": copy.deepcopy(analysis["interpretation"]),
            "interpretation_semantics": interpretation_semantics,
            "frozen_interpretation_model": frozen_model, "frozen_explainer": frozen_explainer,
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                "code_hashes": codes, "authorization_ref": auth_ref,
                "model_ref_hash": analysis["interpretation"]["model_ref"]["content_hash"],
                "explainer_ref_hash": analysis["interpretation"]["explainer_ref"]["content_hash"]}}
    if penalized_v08_task:
        family_checked = _real_family_admission.validate_options(task, rows, variables, root, globals()) if study_family is not None else None
        if family_checked is not None:
            penalized_flow, penalized_semantics, frozen_penalized_model = (family_checked["flow"], family_checked["semantics"], family_checked["frozen_model"])
        else:
            penalized_flow, penalized_semantics, frozen_penalized_model = _penalized_v08_contracts.validate_options(task, rows, variables, root, globals())
        ledger = {"source_rows": len(rows), "view_rows": len(rows), "subjects": len(rows), "encounters": None,
            "missing_by_variable": {key: sum(row[key] is None for row in rows) for key in variables},
            "conversions": [{"variable": key, "from": value["source_unit"], "to": value["unit"], **value["conversion"]}
                            for key, value in variables.items()],
            "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True,
            "penalized_prediction": penalized_flow}
        return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            **({"origin_context": family_checked["context"], "core_family": {"name": study_family["family"], "method_id": analysis["method_id"], "operation": operation},
                "frozen_model_origin": family_checked["frozen_origin"]} if family_checked is not None else {}),
            "penalized_options": copy.deepcopy(analysis["penalized_prediction"]),
            "penalized_semantics": penalized_semantics, "frozen_penalized_model": frozen_penalized_model,
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                "code_hashes": codes, "authorization_ref": auth_ref,
                "model_ref_hash": (analysis["penalized_prediction"]["model_ref"]["content_hash"]
                    if frozen_penalized_model is not None else None)}}
    if psm_v07_task:
        psm_flow, psm_semantics = (_psm_v07_admission.validate_options(task, rows, variables, root, globals(), _psm_v07_contracts)
                                 if study_psm else _psm_v07_contracts.validate_options(task, rows, variables, root, globals()))
        ledger = {"source_rows": len(rows), "view_rows": len(rows), "subjects": len(rows), "encounters": None,
            "missing_by_variable": {key: sum(row[key] is None for row in rows) for key in variables},
            "conversions": [{"variable": key, "from": value["source_unit"], "to": value["unit"], **value["conversion"]}
                            for key, value in variables.items()],
            "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True,
            "psm": psm_flow}
        return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            **({"origin_context": _psm_v07_admission.result_context(task),
                "core_family": {"name": "psm_v07", "method_id": analysis["method_id"], "operation": "analyze"}} if study_psm else {}),
            "psm_options": copy.deepcopy(analysis["psm"]), "psm_semantics": psm_semantics,
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                "code_hashes": codes, "authorization_ref": auth_ref}}
    if survival_task:
        model_bundle = None
        model_json = None
        if study_family is not None:
            family_checked = _real_family_admission.validate_options(task, rows, variables, root, globals())
            survival_semantics = family_checked["semantics"]
            model_bundle = family_checked["frozen_model"]
            model_json = family_checked["frozen_model_json"]
        elif survival_v06_task:
            survival_semantics, model_bundle, model_json = _survival_v06_contracts.validate_options(
                task, rows, variables, root, globals(), _survival_v05_contracts, _survival_contracts)
        elif survival_v05_task:
            survival_semantics, model_bundle, model_json = _survival_v05_contracts.validate_options(
                task, rows, variables, root, globals(), _survival_contracts)
        else:
            survival_semantics = _survival_contracts.validate_options(task, rows, variables, root, globals())
        ledger = {"source_rows":len(rows), "view_rows":len(rows), "subjects":len(rows), "encounters":None,
            "missing_by_variable":{key:sum(row[key] is None for row in rows) for key in variables},
            "conversions":[{"variable":key,"from":value["source_unit"],"to":value["unit"],**value["conversion"]} for key,value in variables.items()],
            "join_declarations_checked":0,"join_reconstruction":"not_performed","selected_view_only":True,
            "survival":survival_semantics}
        result = {"ok":True,"task":task,"rows":rows,"selected_view":view,"ledger":ledger,
            "binding":{"input_hash":canonical_hash(task),"plan_hash":task["plan_hash"],"view_hash":view["content_hash"],
                "transformation_hash":view["transformation_hash"],"code_hashes":codes,"authorization_ref":auth_ref}}
        if study_family is not None:
            result["core_family"] = {"name": study_family["family"], "method_id": analysis["method_id"],
                                     "operation": study_family["operation"]}
            result["origin_context"] = {**_real_family_admission.result_context(task),
                "source_verification": admission["source_verification"]}
            result["frozen_model_origin"] = family_checked["frozen_origin"]
        if cox_prediction_task:
            result["model_bundle"] = model_bundle
            result["model_json"] = model_json
            result["cox_feature_semantics"] = _survival_v05_contracts.canonical_feature_semantics(task)
            result["canonical_semantics"] = _survival_v05_contracts.canonical_survival_semantics(analysis["survival"])
            result["binding"]["model_ref_hash"] = analysis["cox_prediction"].get("model_sha256")
            if survival_v06_task:
                result["survival_evaluation_options"] = copy.deepcopy(analysis["survival_evaluation"])
                result["binding"]["frozen_model_provider_version"] = model_bundle["provider_version"]
        return result
    if association_plan_task:
        plan_semantics = (_association_plan_admission.validate_options(task, rows, variables, root, globals(), _association_plan_contracts)
                          if study_plan else _association_plan_contracts.validate_options(task, rows, variables, root, globals()))
        ledger = {"source_rows": len(rows), "view_rows": len(rows), "subjects": len(rows),
            "encounters": len(rows) if identity["analysis_unit"] == "encounter" else None,
            "missing_by_variable": {k: sum(r[k] is None for r in rows) for k in variables},
            "conversions": [{"variable": k, "from": v["source_unit"], "to": v["unit"], **v["conversion"]} for k, v in variables.items()],
            "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True,
            "association_plan": plan_semantics}
        return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            **({"origin_context": _association_plan_admission.result_context(task),
                "core_family": {"name": "association_plan", "method_id": analysis["method_id"], "operation": "analyze"}} if study_plan else {}),
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                "code_hashes": codes, "authorization_ref": auth_ref}}
    if prediction_task:
        family_checked = None
        if study_family is not None:
            family_checked = _real_family_admission.validate_options(task, rows, variables, root, globals())
            model_bundle = family_checked["frozen_model"]
        else:
            model_bundle = _prediction_contracts.validate_options(task, rows, variables, root, globals())
        ledger = {"source_rows": len(rows), "view_rows": len(rows), "subjects": len(rows),
            "encounters": None, "missing_by_variable": {k: sum(r[k] is None for r in rows) for k in variables},
            "conversions": [{"variable": k, "from": v["source_unit"], "to": v["unit"], **v["conversion"]} for k, v in variables.items()],
            "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True,
            "fit_scope": "training_only" if operation == "train" else "frozen_only"}
        return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            "model_bundle": model_bundle,
            "canonical_semantics": _prediction_contracts.canonical_semantics(task),
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                "code_hashes": codes, "authorization_ref": auth_ref,
                "model_ref_hash": analysis["prediction"]["model_ref"]["content_hash"] if operation != "train" else None},
            **({"core_family": {"name": study_family["family"], "method_id": analysis["method_id"], "operation": operation},
                "origin_context": {**family_checked["context"], "source_verification": admission["source_verification"]},
                "frozen_model_origin": family_checked["frozen_origin"]} if study_family is not None else {})}
    need(analysis["method_id"] in METHODS, "METHOD_NOT_INTEGRATED", stage)
    need(task["missingness"] == {"strategy": "complete_case", "fit_scope": "not_applicable", "exclusion_denominator": "selected_view"},
         "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    need(task["derivation"] == {"strategy": "declared_unit_conversion_only", "version": "1"}, "DERIVATION_NOT_ENABLED", stage)
    need(analysis["ci_level"] == 0.95, "CI_LEVEL_UNSUPPORTED", stage)
    need(analysis["effect_scale"] == {"baseline.table1": "descriptive", "association.linear": "outcome units",
                                     "association.logistic": "odds_ratio"}[analysis["method_id"]],
         "EFFECT_SCALE_MISMATCH", stage)
    baseline = analysis["baseline"]
    if baseline is not None:
        need((study_task and baseline["group"] is None and baseline["include_overall"]) or (baseline["group"] in variables and variables[baseline["group"]]["dtype"] == "category"
             and variables[baseline["group"]]["role"] in ({"group", "covariate", "stratification_label", "outcome_summary"} if study_task else {"group", "covariate"})), "BASELINE_GROUP_INVALID", stage)
        for var in baseline["variables"]:
            need(var["name"] in variables, "BASELINE_VARIABLE_MISSING", stage)
            need((study_task and variables[var["name"]]["role"] in {"exposure", "covariate", "group", "descriptive_measure", "stratification_label", "outcome_summary", "outcome"}) or (not study_task and variables[var["name"]]["role"] in {"exposure", "covariate", "group"}
                 and variables[var["name"]]["available_at"] <= tm["feature_cutoff"]),
                 "BASELINE_DESCRIPTIVE_ROLE_INTEGRATION_PENDING", stage)
            expected_type = "continuous" if variables[var["name"]]["dtype"] == "number" else "categorical"
            need(var["type"] == expected_type or var["type"] == "binary" and expected_type == "categorical", "BASELINE_TYPE_MISMATCH", stage)
            need(variables[var["name"]]["dtype"] != "id", "BASELINE_ID_SUMMARY_FORBIDDEN", stage)
            need(var["levels"] == variables[var["name"]]["levels"], "BASELINE_LEVELS_MISMATCH", stage)
            need(var["summary"] in {"mean_sd", "median_iqr"} if expected_type == "continuous" else var["summary"] is None,
                 "BASELINE_SUMMARY_MISMATCH", stage)
    if analysis["method_id"] == "baseline.table1":
        need(baseline is not None and analysis["spec"] is None, "BASELINE_SPEC_REQUIRED", stage)
    else:
        spec = analysis["spec"]
        need(spec is not None, "ASSOCIATION_SPEC_REQUIRED", stage)
        need(spec["model"] == analysis["method_id"].split(".")[-1], "METHOD_MODEL_MISMATCH", stage)
        need(spec["key"] == identity["record_keys"] and spec["subject_id"] == subject
             and spec["row_unit"] == identity["analysis_unit"] and spec["independent"], "METHOD_IDENTITY_MISMATCH", stage)
        used = [spec["outcome"], spec["exposure"]] + spec["covariates"]
        need(all(x in variables for x in used), "MODEL_FIELD_MISSING", stage)
        # Identity text is never a numerical predictor, even when a caller
        # removes the optional baseline table or gives it a numeric-looking ID.
        candidate_predictors = used[1:] + ([spec["subgroup"]["field"]] if spec.get("subgroup") else [])
        for sensitivity in spec.get("sensitivity", []):
            candidate_predictors.extend(sensitivity.get("covariates", []))
        need(not any(x in variables and variables[x]["dtype"] == "id" for x in candidate_predictors),
             "ID_MODEL_FIELD_FORBIDDEN", stage)
        need(all(variables[x]["dtype"] in {"number", "category"} for x in used[1:]),
             "MODEL_FIELD_TYPE_UNSUPPORTED", stage)
        need(spec["outcome"] == task["outcome"]["field"], "OUTCOME_CONTRACT_MISMATCH", stage)
        need(variables[spec["outcome"]]["role"] == "outcome", "OUTCOME_ROLE_INVALID", stage)
        need((study_task and tm["policy"] == "cross_sectional_association") or (variables[spec["outcome"]]["available_at"] <= tm["analysis_as_of"]
             and tm["outcome_window"][0] <= variables[spec["outcome"]]["occurred_at"] <= tm["outcome_window"][1]),
             "OUTCOME_LABEL_NOT_MATURE", stage)
        need(variables[spec["exposure"]]["role"] == "exposure", "EXPOSURE_ROLE_INVALID", stage)
        need(all(variables[x]["role"] in {"covariate", "group"} for x in spec["covariates"]), "COVARIATE_ROLE_INVALID", stage)
        need(analysis["variance"] == spec["covariance"], "VARIANCE_CONTRACT_MISMATCH", stage)
        need(set(spec["categorical"]) == {x for x in used[1:] if variables[x]["dtype"] == "category"}, "CATEGORY_SPEC_MISMATCH", stage)
        for key, contract in spec["categorical"].items():
            need(contract == {"levels": variables[key]["levels"], "reference": variables[key]["reference"]}, "CATEGORY_SPEC_MISMATCH", stage)
        if spec.get("subgroup") is not None:
            subgroup = spec["subgroup"]
            name = subgroup["field"]
            need(name in variables and variables[name]["dtype"] == "category"
                 and variables[name]["role"] in {"group", "covariate"}, "SUBGROUP_CONTRACT_MISMATCH", stage)
            need({"levels": subgroup["levels"], "reference": subgroup["reference"]} ==
                 {"levels": variables[name]["levels"], "reference": variables[name]["reference"]}, "SUBGROUP_CONTRACT_MISMATCH", stage)
        for sensitivity in spec.get("sensitivity", []):
            for condition in sensitivity["where"]:
                need(condition["field"] in variables and variables[condition["field"]]["role"] in {"exposure", "covariate", "group"},
                     "SENSITIVITY_FUTURE_OR_UNDECLARED_FIELD", stage)
            need(all(x in variables and variables[x]["role"] in {"covariate", "group"}
                     for x in sensitivity.get("covariates", spec["covariates"])), "SENSITIVITY_COVARIATE_INVALID", stage)
        if spec["model"] == "logistic":
            need(task["outcome"]["type"] == "binary" and task["outcome"]["event"] == spec.get("event")
                 and task["outcome"]["non_event"] == spec.get("non_event"), "BINARY_CODING_MISMATCH", stage)
        else:
            need(task["outcome"]["type"] == "continuous" and variables[spec["outcome"]]["dtype"] == "number", "CONTINUOUS_OUTCOME_REQUIRED", stage)
        need(spec["covariance"] == {"linear": "HC3", "logistic": "model"}[spec["model"]],
             "VARIANCE_OPTION_INTEGRATION_PENDING", stage)
        need(spec.get("nonlinear") is None and spec.get("subgroup") is None and not spec.get("sensitivity"),
             "ASSOCIATION_OPTION_INTEGRATION_PENDING", stage)
    ledger = {"source_rows": input_view_rows, "view_rows": len(rows), "subjects": len({r[subject] for r in rows}),
              "encounters": len(rows) if identity["analysis_unit"] == "encounter" else None,
              "missing_by_variable": {k: sum(r[k] is None for r in rows) for k in variables},
              "conversions": [{"variable": k, "from": v["source_unit"], "to": v["unit"], **v["conversion"]} for k, v in variables.items()],
              "join_declarations_checked": 0, "join_reconstruction": "not_performed", "selected_view_only": True}
    return {"ok": True, "task": task, "rows": rows, "selected_view": view, "ledger": ledger,
            "binding": {"input_hash": canonical_hash(task), "plan_hash": task["plan_hash"],
                        "view_hash": view["content_hash"], "transformation_hash": view["transformation_hash"],
                        "code_hashes": codes, "authorization_ref": auth_ref},
            **({"origin_context": {"data_origin": task["data_origin"], "task_purpose": task["task_purpose"], "source_verification": admission["source_verification"]}} if study_task else {})}


def validate_task(task, core_root):
    result = _validate_task(task, core_root)
    if task.get("schema_version") == STUDY_INPUT_VERSION:
        result["resource_limits"] = _resource_budget.request_limits(task["execution"], _resource_budget.method(task))
        result["resource_observation"] = _resource_budget.check_task(task, len(result["rows"]), result["resource_limits"])
    return result


def seal_task(task, core_root):
    """Bind a local synthetic fixture after deliberate edits; no execution."""
    if task.get("schema_version") == STUDY_INPUT_VERSION:
        return _study_input.seal(task, core_root, globals())
    root = Path(core_root).resolve()
    sources = {x["source_id"]: x for x in task["sources"]}
    for view in task["views"]:
        file = Path(view["local_ref"])
        if file.is_file():
            view["content_hash"] = file_hash(file)
            if len(view["source_ids"]) == 1:
                sources[view["source_ids"][0]]["source_fingerprint"] = view["content_hash"]
        view["transformation_hash"] = transformation_hash(task, view)
    task["execution"]["expected_source_hashes"] = {key: val["source_fingerprint"] for key, val in sources.items()}
    task["execution"]["expected_code_hashes"] = {
        rel: file_hash(root / rel) for rel in sorted(required_code_for_task(task)) if (root / rel).is_file()}
    task["plan_hash"] = plan_hash(task)
    return task


def make_example_task(csv_path, output_dir, core_root, database="MIMIC"):
    variables = []
    for name, dtype, role in [("id", "id", "id"), ("x", "number", "exposure"), ("z", "number", "covariate"),
                              ("group", "category", "group"), ("y", "number", "outcome"), ("binary", "category", "outcome")]:
        levels = ["A", "B"] if name == "group" else ["0", "1"] if name == "binary" else []
        variables.append({"name": name, "dtype": dtype, "role": role, "unit": "1", "source_unit": "1",
            "dimension": "dimensionless", "conversion": {"scale": 1, "offset": 0}, "levels": levels,
            "reference": levels[0] if levels else None, "codes": {x: x for x in levels}, "missing_codes": ["", "NA"],
            "occurred_at": 24 if role == "outcome" else 0, "available_at": 24 if role == "outcome" else 0,
            "concept": "synthetic_" + name, "codebook_version": "fixture-v1", "aggregation": "already_one_value_per_row"})
    task = {"schema_version": INPUT_VERSION, "study_id": "synthetic_core_b1a", "plan_hash": "0" * 64,
        "purpose": "SYNTHETIC_TEST_ONLY", "estimand": "Prespecified synthetic conditional association",
        "protocol_revision": "1", "sources": [{"source_id": "synthetic_source", "database": database,
            "snapshot": "synthetic-v1", "period": "synthetic-only", "recipe_version": "adapter-1",
            "recipe_hash": canonical_hash({"adapter": "synthetic-1"}), "source_fingerprint": "0" * 64,
            "evidence_refs": ["synthetic_fixture_generator"], "verification_status": "verified_synthetic_bytes"}],
        "identity": {"subject_key": "id", "record_keys": ["id"], "scope": "within_source", "analysis_unit": "subject",
            "repeated_policy": "reject", "encounter_key": None, "cluster_key": None},
        "variables": variables,
        "cohort": {"target_population": "Synthetic records only", "inclusion": ["all synthetic rows"], "exclusion": [],
            "index_event": "synthetic time zero", "selection_order": ["synthetic input"]},
        "time": {"unit": "hour", "timezone": "relative", "index": 0, "feature_cutoff": 0,
            "outcome_window": [0, 24], "label_mature_at": 24, "analysis_as_of": 24, "boundary": "[start,end]", "delayed_entry": False},
        "outcome": {"field": "y", "type": "continuous", "event": None, "non_event": None,
            "definition": "synthetic continuous endpoint", "censoring": "none"},
        "design": {"kind": "iid", "inference_unit": "subject", "variance_unit": "subject", "strata": None, "psu": None, "domain": None},
        "weights": {"kind": "none", "field": None, "target": None, "construction": None, "variance_semantics": None},
        "views": [{"view_id": "wide", "kind": "subject_wide", "source_ids": ["synthetic_source"],
            "local_ref": str(Path(csv_path).resolve()), "content_hash": "0" * 64,
            "column_map": {v["name"]: v["name"] for v in variables}, "grain": "subject", "keys": ["id"],
            "joins": [], "transformation_hash": "0" * 64, "counts_ref": "synthetic_csv_row_count"}],
        "analysis": {"method_id": "association.linear", "required_view_ids": ["wide"],
            "spec": {"model": "linear", "outcome": "y", "exposure": "x", "covariates": ["z", "group"],
                "missing": "complete_case", "covariance": "HC3", "categorical": {"group": {"levels": ["A", "B"], "reference": "A"}},
                "row_unit": "subject", "independent": True, "key": ["id"], "subject_id": "id", "sensitivity": []},
            "baseline": {"group": "group", "variables": [{"name": "x", "type": "continuous", "summary": "median_iqr", "levels": []},
                {"name": "group", "type": "categorical", "summary": None, "levels": ["A", "B"]}],
                "categorical_denominator": "nonmissing", "include_overall": True},
            "effect_scale": "outcome units", "variance": "HC3", "ci_level": 0.95,
            "assumptions": ["iid complete-case assumptions require scientific review"]},
        "missingness": {"strategy": "complete_case", "fit_scope": "not_applicable", "exclusion_denominator": "selected_view"},
        "derivation": {"strategy": "declared_unit_conversion_only", "version": "1"},
        "split": {"strategy": "none", "group_key": "id", "fold_field": None, "seed": 20261023, "fit_scope": "not_applicable"},
        "validation": {"kind": "none", "overlap_status": "not_applicable", "transportability": "not_evaluated"},
        "compatibility": {"pooling": False, "identity_overlap": "not_evaluated", "status": "limited", "reason": "synthetic contract test only"},
        "execution": {"mode": "synthetic", "authorization_ref": AUTHORIZATION_REF, "output_dir": str(Path(output_dir).resolve()),
            "max_rows": MAX_ROWS, "max_bytes": MAX_BYTES, "expected_source_hashes": {}, "expected_code_hashes": {}},
        "export_policy": {"mode": "local_only", "small_cell_policy": "review_required"}}
    return seal_task(task, core_root)


def make_penalized_task(csv_path, output_dir, core_root, database="MIMIC", *,
                        method_id="prediction.continuous.signed.lasso", penalized_options=None):
    """Build a synthetic v0.8 plan without deriving any choices from its rows.

    Callers supply partition and fold columns. Defaults are prespecified, and
    custom category metadata must be declared explicitly before sealing again.
    ``penalized_options`` replaces the complete options object, not a partial
    merge. This helper never reads rows to choose categories, folds or features.
    """
    need(method_id in _penalized_v08_contracts.METHODS, "METHOD_NOT_INTEGRATED")
    options = (copy.deepcopy(penalized_options) if penalized_options is not None
               else _penalized_v08_contracts.default_options(method_id))
    validate_schema(options, _penalized_v08_contracts.options_schema())
    spec, operation = options["spec"], options["operation"]
    split = spec["split"]
    binary = method_id.startswith("prediction.binary.")
    task = make_example_task(csv_path, output_dir, core_root, database)
    task["schema_version"] = PENALIZED_V08_INPUT_VERSION
    task["study_id"] = "synthetic_penalized_v08"
    task["execution"].update(authorization_ref=_penalized_v08_contracts.AUTHORIZATION_REF,
                             max_rows=_penalized_v08_contracts.MAX_ROWS)
    definitions = [(spec["id"], "id", "id", "1", []),
        (split["partition_field"], "category", "split", "1", ["train", "holdout"]),
        (split["fold_field"], "number", "split", "1", [])]
    if split["group_field"] is not None:
        definitions.append((split["group_field"], "id", "group", "1", []))
    for feature in spec["features"]:
        name, dtype = feature["name"], feature["type"]
        levels = (["F", "M"] if name == "sex" else ["0", "1"]) if dtype == "category" else []
        definitions.append((name, dtype, "covariate", "year" if name == "age" and dtype == "number" else "1", levels))
    definitions.append((spec["outcome"], "number", "outcome", "1", []))
    need(len({definition[0] for definition in definitions}) == len(definitions), "PENALIZED_FIELD_ROLES_COLLIDE")
    variables = []
    for name, dtype, role, unit, levels in definitions:
        variables.append({"name": name, "dtype": dtype, "role": role, "unit": unit, "source_unit": unit,
            "dimension": UNIT_DIMENSIONS[unit], "conversion": {"scale": 1, "offset": 0}, "levels": levels,
            "reference": levels[0] if levels else None, "codes": {level: level for level in levels},
            "missing_codes": ["", "NA"], "occurred_at": 24 if role == "outcome" else 0,
            "available_at": 24 if role == "outcome" else 0, "concept": "synthetic_" + name,
            "codebook_version": "penalized-fixture-v1", "aggregation": "already_one_value_per_row"})
    task["variables"] = variables
    task["identity"].update(subject_key=spec["id"], record_keys=[spec["id"]])
    task["views"][0].update(column_map={variable["name"]: variable["name"] for variable in variables},
                              keys=[spec["id"]])
    task["outcome"] = {"field": spec["outcome"], "type": "binary" if binary else "continuous",
        "event": 1 if binary else None, "non_event": 0 if binary else None,
        "definition": "Synthetic binary endpoint" if binary else "Synthetic signed continuous endpoint", "censoring": "none"}
    task["analysis"] = {"method_id": method_id, "required_view_ids": ["wide"], "spec": None, "baseline": None,
        "penalized_prediction": options, "effect_scale": "probability" if binary else "outcome units",
        "variance": "not_applicable", "ci_level": .95,
        "assumptions": ["Synthetic prespecified penalized prediction; scientific review pending; no postselection or causal inference"]}
    task["estimand"] = "Prespecified synthetic binary event probability" if binary else "Prespecified synthetic signed continuous prediction"
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    task["split"] = {"strategy": split["method"] if operation == "train" else "none",
        "group_key": split["group_field"] or spec["id"], "fold_field": split["fold_field"], "seed": 0, "fit_scope": fit_scope}
    task["missingness"] = {"strategy": "training_median_mode", "fit_scope": fit_scope, "exclusion_denominator": "selected_view"}
    task["validation"] = {"kind": "internal_holdout" if operation == "train"
        else "synthetic_frozen_application" if operation == "evaluate" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint",
        "transportability": "not_evaluated"}
    if operation == "infer":
        task["time"]["analysis_as_of"] = task["time"]["index"]
    return seal_task(task, core_root)


def make_cox_penalized_task(csv_path, output_dir, core_root, database="MIMIC", *,
                            method_id="prediction.survival.cox.lasso", cox_penalized_options=None):
    """Build a prespecified synthetic v0.10 plan without learning from its rows.

    The complete options object may be replaced by the caller. Category metadata,
    partitions, folds, horizons and the outer observation window are declared,
    never chosen by this helper from outcome values or fitting results.
    """
    need(method_id in _cox_penalized_v10_contracts.METHODS, "METHOD_NOT_INTEGRATED")
    options = (copy.deepcopy(cox_penalized_options) if cox_penalized_options is not None
               else _cox_penalized_v10_contracts.default_options(method_id))
    validate_schema(options, _cox_penalized_v10_contracts.options_schema())
    spec, operation = options["spec"], options["operation"]
    split, survival = spec["split"], spec["survival"]
    task = make_example_task(csv_path, output_dir, core_root, database)
    task["schema_version"] = COX_PENALIZED_V10_INPUT_VERSION
    task["study_id"] = "synthetic_cox_penalized_v10"
    task["execution"].update(authorization_ref=_cox_penalized_v10_contracts.AUTHORIZATION_REF,
                             max_rows=_cox_penalized_v10_contracts.MAX_ROWS)
    definitions = [(spec["id"], "id", "id", "1", []),
        (split["partition_field"], "category", "split", "1", ["train", "holdout"]),
        (split["fold_field"], "number", "split", "1", [])]
    if split["group_field"] is not None:
        definitions.append((split["group_field"], "id", "group", "1", []))
    for feature in spec["features"]:
        name, dtype = feature["name"], feature["type"]
        levels = (["F", "M"] if name == "sex" else ["A", "B"]) if dtype == "category" else []
        definitions.append((name, dtype, "covariate", "year" if name == "age" and dtype == "number" else "1", levels))
    definitions.extend([(spec["duration"], "number", "time", survival["time_unit"], []),
                        (spec["event"], "number", "outcome", "1", [])])
    need(len({definition[0] for definition in definitions}) == len(definitions), "COX_PENALIZED_FIELD_ROLES_COLLIDE")
    variables = []
    for name, dtype, role, unit, levels in definitions:
        endpoint = name in {spec["duration"], spec["event"]}
        variables.append({"name": name, "dtype": dtype, "role": role, "unit": unit, "source_unit": unit,
            "dimension": UNIT_DIMENSIONS[unit], "conversion": {"scale": 1, "offset": 0}, "levels": levels,
            "reference": levels[0] if levels else None, "codes": {level: level for level in levels},
            "missing_codes": ["", "NA"], "occurred_at": 365 if endpoint else 0,
            "available_at": 365 if endpoint else 0, "concept": "synthetic_" + name,
            "codebook_version": "cox-penalized-fixture-v1", "aggregation": "already_one_value_per_row"})
    task["variables"] = variables
    task["identity"].update(subject_key=spec["id"], record_keys=[spec["id"]])
    task["views"][0].update(column_map={variable["name"]: variable["name"] for variable in variables}, keys=[spec["id"]])
    task["time"] = {"unit": survival["time_unit"], "timezone": "relative", "index": 0, "feature_cutoff": 0,
        "outcome_window": [0, 365], "label_mature_at": 365, "analysis_as_of": 365 if operation == "train" else 0,
        "boundary": "(0,end]", "delayed_entry": False}
    task["cohort"]["index_event"] = survival["time_zero_definition"]
    task["outcome"] = {"field": spec["event"], "type": "time_to_event", "event": 1, "non_event": 0,
        "definition": survival["event_definition"], "censoring": "right"}
    task["analysis"] = {"method_id": method_id, "required_view_ids": ["wide"], "spec": None, "baseline": None,
        "cox_penalized_prediction": options, "effect_scale": "cumulative_event_probability",
        "variance": "not_applicable", "ci_level": .95,
        "assumptions": ["Synthetic single-event right-censored prediction; prespecified training CV; scientific review pending",
                        "No coefficient inference, PH test, IPCW evaluation, nomogram or causal interpretation"]}
    task["estimand"] = "Prespecified synthetic cumulative single-event probability conditional on baseline features"
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    task["split"] = {"strategy": split["method"] if operation == "train" else "none",
        "group_key": split["group_field"] or spec["id"], "fold_field": split["fold_field"], "seed": 0, "fit_scope": fit_scope}
    task["missingness"] = {"strategy": "training_median_mode", "fit_scope": fit_scope, "exclusion_denominator": "selected_view"}
    task["validation"] = {"kind": "internal_holdout" if operation == "train" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint",
        "transportability": "not_evaluated"}
    return seal_task(task, core_root)


def make_interpretation_task(csv_path, output_dir, core_root, database="MIMIC", *, interpretation_options):
    """Build a v0.9 external explanation plan from explicit frozen references."""
    options = copy.deepcopy(interpretation_options)
    validate_schema(options, _interpretation_v09_contracts.options_schema(_penalized_v08_contracts))
    task = make_penalized_task(csv_path, output_dir, core_root, database,
        method_id=options["model_method_id"], penalized_options=_interpretation_v09_contracts.inference_options(options))
    task["schema_version"] = INTERPRETATION_V09_INPUT_VERSION
    task["study_id"] = "synthetic_interpretation_v09"
    task["execution"].update(authorization_ref=_interpretation_v09_contracts.AUTHORIZATION_REF,
                             max_rows=_interpretation_v09_contracts.MAX_ROWS)
    task["analysis"].pop("penalized_prediction")
    task["analysis"].update(method_id=_interpretation_v09_contracts.METHOD, interpretation=options,
        effect_scale="log_odds" if options["model_method_id"].startswith("prediction.binary.") else "outcome units",
        ci_level=None,
        assumptions=["Exact affine interventional explanations use the entire frozen training background",
                     "External synthetic disjoint subjects only; no causal, conditional or clinical interpretation"])
    task["estimand"] = "Raw-feature contributions to a frozen synthetic score relative to its full training background"
    return seal_task(task, core_root)


def make_psm_task(csv_path, output_dir, core_root, database="MIMIC", *, psm_options=None):
    """Build the fixed synthetic v0.7 protocol; no outcome-dependent choices."""
    task = make_example_task(csv_path, output_dir, core_root, database)
    task["schema_version"] = PSM_V07_INPUT_VERSION
    task["study_id"] = "synthetic_psm_v07"
    task["execution"].update(authorization_ref=_psm_v07_contracts.AUTHORIZATION_REF,
                             max_rows=_psm_v07_contracts.MAX_ROWS)
    definitions = [("patient_id", "id", "id", "1", "dimensionless", []),
        ("treatment", "number", "exposure", "1", "dimensionless", []),
        ("age", "number", "covariate", "year", "time", []),
        ("severity", "number", "covariate", "1", "dimensionless", []),
        ("sex", "category", "covariate", "1", "dimensionless", ["F", "M"]),
        ("outcome", "number", "outcome", "1", "dimensionless", [])]
    variables = []
    for name, dtype, role, unit, dimension, levels in definitions:
        variables.append({"name": name, "dtype": dtype, "role": role, "unit": unit, "source_unit": unit,
            "dimension": dimension, "conversion": {"scale": 1, "offset": 0}, "levels": levels,
            "reference": levels[0] if levels else None, "codes": {value: value for value in levels},
            "missing_codes": ["", "NA"], "occurred_at": 24 if role == "outcome" else 0,
            "available_at": 24 if role == "outcome" else 0, "concept": "synthetic_" + name,
            "codebook_version": "psm-fixture-v1", "aggregation": "already_one_value_per_row"})
    task["variables"] = variables
    task["identity"].update(subject_key="patient_id", record_keys=["patient_id"])
    task["views"][0].update(column_map={variable["name"]: variable["name"] for variable in variables}, keys=["patient_id"])
    task["split"]["group_key"] = "patient_id"
    task["design"]["variance_unit"] = "matched_pair"
    task["time"]["outcome_window"] = [1, 24]
    task["outcome"].update(field="outcome", type="continuous", event=None, non_event=None,
                           definition="Synthetic signed continuous endpoint", censoring="none")
    task["missingness"] = copy.deepcopy(_psm_v07_contracts.MISSINGNESS)
    options = copy.deepcopy(_psm_v07_contracts.DEFAULT_OPTIONS if psm_options is None else psm_options)
    task["analysis"].update(method_id=_psm_v07_contracts.METHOD, spec=None, baseline=None, psm=options,
        effect_scale="matched_mean_difference", variance="paired_t", ci_level=.95,
        assumptions=["Prespecified 1:1 matching without replacement; paired inference conditions on formed matches",
                     "Consistency, no unmeasured confounding and positivity remain unverified; scientific review pending"])
    task["estimand"] = "Matched treated-minus-control mean difference for retained matched treated subjects; no automatic causal claim"
    return seal_task(task, core_root)


def make_association_plan_task(csv_path, output_dir, core_root,
                               method_id="association.linear.plan", database="MIMIC"):
    """Canonical small synthetic plan builder; not a clinical defaults policy."""
    need(method_id in _association_plan_contracts.METHODS, "METHOD_NOT_INTEGRATED")
    task = make_example_task(csv_path, output_dir, core_root, database)
    task["schema_version"] = ASSOCIATION_PLAN_INPUT_VERSION
    task["study_id"] = "synthetic_association_plan_v03"
    task["execution"]["authorization_ref"] = _association_plan_contracts.AUTHORIZATION_REF
    spec = copy.deepcopy(task["analysis"]["spec"])
    if method_id == "association.logistic.plan":
        spec.update(model="logistic", outcome="binary", covariance="model", event="1", non_event="0")
        task["outcome"].update(field="binary", type="binary", event="1", non_event="0",
                              definition="synthetic binary endpoint")
        task["analysis"].update(effect_scale="odds_ratio", variance="model")
    task["analysis"].update(method_id=method_id, spec=None, baseline=None,
        association={"sample_strategy":"per_model_complete_case", "multiplicity":"unadjusted_prespecified",
            "models":[{"model_id":"primary", "label":"Prespecified primary association",
                "rationale":"Synthetic contract verification; no causal claim", "role":"primary", "where":[],
                "spec":spec, "curve":None, "subgroup_min_n":None}]})
    return seal_task(task, core_root)


def make_survival_task(csv_path, output_dir, core_root, method_id="survival.kaplan_meier", database="MIMIC"):
    """Fixed small synthetic protocol builder; never chooses time grids from outcomes."""
    need(method_id in _survival_contracts.METHODS,"METHOD_NOT_INTEGRATED")
    task=make_example_task(csv_path,output_dir,core_root,database)
    task["schema_version"]=SURVIVAL_INPUT_VERSION
    task["study_id"]="synthetic_survival_v04"
    task["execution"]["authorization_ref"]=_survival_contracts.AUTHORIZATION_REF
    definitions=[("id","id","id","1","dimensionless",[]),
        ("time","number","survival_time","day","time",[]),
        ("status","category","survival_status","1","dimensionless",["0","1"]),
        ("x","number","exposure","1","dimensionless",[]),
        ("z","number","covariate","1","dimensionless",[]),
        ("group","category","group","1","dimensionless",["A","B"])]
    variables=[]
    for name,dtype,role,unit,dimension,levels in definitions:
        endpoint=role in {"survival_time","survival_status"}
        variables.append({"name":name,"dtype":dtype,"role":role,"unit":unit,"source_unit":unit,"dimension":dimension,
            "conversion":{"scale":1,"offset":0},"levels":levels,"reference":levels[0] if levels else None,
            "codes":{value:value for value in levels},"missing_codes":["","NA"],
            "occurred_at":30 if endpoint else 0,"available_at":30 if endpoint else 0,
            "concept":"synthetic_"+name,"codebook_version":"survival-fixture-v1","aggregation":"already_one_value_per_row"})
    task["variables"]=variables
    task["views"][0].update(kind="survival_subject",column_map={v["name"]:v["name"] for v in variables})
    zero="synthetic cohort eligibility and observation start at time zero"
    event="synthetic single endpoint observed by end of follow-up"
    task["cohort"]["index_event"]=zero
    task["cohort"]["inclusion"]=["eligible at time zero; one synthetic independent subject per row"]
    task["time"].update(unit="day",index=0,feature_cutoff=0,eligibility_window=[-1,0],observation_end=30,
        outcome_window=[0,30],label_mature_at=30,analysis_as_of=30,boundary="(0,end]")
    task["outcome"].update(field="status",type="time_to_event",event="1",non_event="0",definition=event,censoring="right")
    cox=method_id=="survival.cox.association"
    spec={"method":"cox_ph" if cox else "kaplan_meier","subject_id":"id","time":"time","status":"status", 
        "time_unit":"day","time_zero_definition":zero,"event_definition":event,
        "censoring_definition":"right censor at last known observation or prespecified observation end; no event observed before censoring",
        "event_code":"1","censor_code":"0","independent_subjects":True,"missing_policy":"complete_case",
        "evaluation_times":[0,5,10,20],"covariates":[],"competing_codes":[],"competing_event_definitions":[],
        "left_truncation":False,"time_varying_covariates":False,"recurrent_events":False,"interval_censoring":False,
        "weights":False,"strata":False,"cluster":False}
    if cox:
        spec.update(ties="breslow",min_events_per_parameter=10,covariates=[
            {"name":"x","type":"numeric","available_at_time_zero":True},
            {"name":"z","type":"numeric","available_at_time_zero":True},
            {"name":"group","type":"category","available_at_time_zero":True,"levels":["A","B"],"reference":"A"}])
    task["analysis"].update(method_id=method_id,spec=None,baseline=None,survival=spec,
        effect_scale="hazard_ratio" if cox else "survival_probability",variance="model" if cox else "greenwood",
        assumptions=["right censoring; independent subjects; event ascertainment and noninformative censoring require scientific review"])
    task["estimand"]="Prespecified conditional hazard ratio; no causal claim" if cox else "Descriptive event-free survival on a prespecified grid"
    return seal_task(task,core_root)


def make_formal_ph_task(csv_path, output_dir, core_root, database="MIMIC", *, transform="km"):
    """Build an explicit synthetic v0.5 formal PH task; legacy builders stay v0.4."""
    need(transform in {"km", "identity"}, "FORMAL_PH_TRANSFORM_UNSUPPORTED")
    task = make_survival_task(csv_path, output_dir, core_root, "survival.cox.association", database)
    task["schema_version"] = SURVIVAL_V05_INPUT_VERSION
    task["study_id"] = "synthetic_formal_ph_v05"
    task["execution"].update(authorization_ref=_survival_v05_contracts.AUTHORIZATION_REF,
                             max_rows=_survival_v05_contracts.MAX_ROWS)
    task["analysis"]["survival"]["ph_test"] = {
        "transform": transform, "terms": True, "singledf": False, "global": True}
    return seal_task(task, core_root)


def make_cox_prediction_task(csv_path, output_dir, core_root, database="MIMIC", *,
                             operation="train", training_subjects=None, holdout_subjects=None,
                             horizons=None, canonical_identity_namespace="synthetic_survival_v05",
                             model_ref=None, model_sha256=None):
    """Build a synthetic task with a caller-declared partition or frozen model.

    No split, feature, category, preprocessing statistic or prediction horizon
    is selected from outcomes. Train and holdout IDs must be supplied explicitly.
    """
    need(operation in {"train", "infer"}, "PREDICTION_OPERATION_INVALID")
    if operation == "train":
        need(training_subjects is not None and holdout_subjects is not None,
             "TRAINING_SUBJECT_PARTITION_REQUIRED")
        need(model_ref is None and model_sha256 is None, "TRAINING_MODEL_REF_NOT_ALLOWED")
    else:
        need(model_ref is not None and model_sha256 is not None, "FROZEN_MODEL_REF_REQUIRED", "binding")
    task = make_survival_task(csv_path, output_dir, core_root, "survival.cox.association", database)
    task["schema_version"] = SURVIVAL_V05_INPUT_VERSION
    task["study_id"] = "synthetic_cox_prediction_v05"
    task["execution"].update(authorization_ref=_survival_v05_contracts.AUTHORIZATION_REF,
                             max_rows=_survival_v05_contracts.MAX_ROWS)
    prediction = {"operation": operation,
        "training_subjects": copy.deepcopy(training_subjects) if training_subjects is not None else [],
        "holdout_subjects": copy.deepcopy(holdout_subjects) if holdout_subjects is not None else [],
        "horizons": copy.deepcopy(horizons) if horizons is not None else [0, 5, 10, 20],
        "canonical_identity_namespace": canonical_identity_namespace,
        "feature_missing_policy": "complete_case"}
    if operation == "infer":
        prediction.update(model_ref=str(model_ref), model_sha256=model_sha256)
    task["analysis"].update(method_id=_survival_v05_contracts.PREDICTION_METHOD,
                             cox_prediction=prediction, effect_scale="absolute_event_risk",
                             variance="not_applicable")
    task["analysis"]["survival"]["evaluation_times"] = copy.deepcopy(prediction["horizons"])
    task["analysis"]["assumptions"] = [
        "Frozen Cox prediction on declared horizons within training event support; no automatic formal PH test or calibration"]
    task["estimand"] = "Synthetic event risk 1-S(t) from a frozen Cox model; scientific review pending"
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    task["split"].update(strategy="explicit_subject_partition" if operation == "train" else "none",
                          fit_scope=fit_scope)
    task["missingness"]["fit_scope"] = fit_scope
    task["validation"] = {"kind": "internal_holdout" if operation == "train" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint",
        "transportability": "not_evaluated"}
    return seal_task(task, core_root)


def make_survival_evaluation_task(csv_path, output_dir, core_root, database="MIMIC", *,
                                  model_ref, model_sha256, horizons, canonical_identity_namespace,
                                  evaluation_options):
    """Build a synthetic v0.6 evaluation with explicitly prespecified options.

    The caller supplies every evaluation option and horizon. This helper never
    derives thresholds, bins, labels, partitions or a risk model from the data.
    """
    need(horizons is not None, "SURVIVAL_EVALUATION_HORIZONS_REQUIRED")
    task = make_cox_prediction_task(csv_path, output_dir, core_root, database,
        operation="infer", model_ref=model_ref, model_sha256=model_sha256,
        horizons=horizons, canonical_identity_namespace=canonical_identity_namespace)
    task["schema_version"] = SURVIVAL_V06_INPUT_VERSION
    task["study_id"] = "synthetic_survival_evaluation_v06"
    task["execution"].update(authorization_ref=_survival_v06_contracts.AUTHORIZATION_REF,
                             max_rows=_survival_v06_contracts.MAX_ROWS)
    task["analysis"].update(method_id=_survival_v06_contracts.EVALUATION_METHOD,
                             survival_evaluation=copy.deepcopy(evaluation_options))
    task["analysis"]["assumptions"] = [
        "Evaluation-cohort marginal reverse-KM IPCW assumes censoring independent of event time and model features; scientific review pending",
        "Frozen Cox risk and baseline remain unchanged; fixed horizons, thresholds and bins; no uncertainty intervals"]
    task["estimand"] = "Prespecified synthetic IPCW evaluation of frozen Cox event risk; scientific review pending"
    return seal_task(task, core_root)


def make_prediction_task(csv_path, output_dir, core_root, method_id="prediction.binary.ridge",
                         operation="train", model_ref=None, database="MIMIC"):
    """Small canonical synthetic fixture builder, never a real-data recipe."""
    need(method_id in _prediction_contracts.METHODS, "METHOD_NOT_INTEGRATED")
    need(operation in {"train", "evaluate", "infer"}, "PREDICTION_OPERATION_INVALID")
    task = make_example_task(csv_path, output_dir, core_root, database)
    task["schema_version"] = PREDICTION_INPUT_VERSION
    task["study_id"] = "synthetic_prediction_v02"
    task["execution"]["authorization_ref"] = _prediction_contracts.AUTHORIZATION_REF
    with Path(csv_path).open(encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))
    site_levels = sorted({r["site"] for r in records if r["site"] not in {"", "NA"}})
    variables = []
    defs = [("id", "id", "id", "1", "dimensionless", []),
            ("x", "number", "exposure", "1", "dimensionless", []),
            ("z", "number", "covariate", "year", "time", []),
            ("category", "category", "covariate", "1", "dimensionless", ["0", "1"]),
            ("y", "number", "outcome", "1", "dimensionless", []),
            ("binary", "category", "outcome", "1", "dimensionless", ["0", "1"]),
            ("site", "category", "split", "1", "dimensionless", site_levels),
            ("time", "number", "time", "hour", "time", []),
            ("label_ready", "number", "time", "hour", "time", [])]
    for name, dtype, role, unit, dimension, levels in defs:
        variables.append({"name": name, "dtype": dtype, "role": role, "unit": unit, "source_unit": unit,
            "dimension": dimension, "conversion": {"scale": 1, "offset": 0}, "levels": levels,
            "reference": levels[0] if levels else None, "codes": {x: x for x in levels},
            "missing_codes": ["", "NA"], "occurred_at": 24 if role == "outcome" else 0,
            "available_at": 24 if role == "outcome" else 0, "concept": "synthetic_" + name,
            "codebook_version": "prediction-fixture-v1", "aggregation": "already_one_value_per_row"})
    task["variables"] = variables
    task["views"][0]["column_map"] = {v["name"]: v["name"] for v in variables}
    binary = method_id == "prediction.binary.ridge"
    outcome_name = "binary" if binary else "y"
    task["outcome"] = {"field": outcome_name, "type": "binary" if binary else "continuous",
        "event": "1" if binary else None, "non_event": "0" if binary else None,
        "definition": "synthetic endpoint only", "censoring": "none"}
    cohort_id = "synthetic-development" if operation == "train" else "synthetic-application"
    if binary:
        spec = {"id": "id", "outcome": outcome_name, "event": "1", "non_event": "0",
            "cohort_id": cohort_id, "prediction_time": "synthetic baseline", "outcome_window": "synthetic 24-hour endpoint",
            "features": [{"name": "x", "type": "number", "available_at_prediction": True},
                         {"name": "z", "type": "number", "available_at_prediction": True},
                         {"name": "category", "type": "category", "levels": ["0", "1"], "available_at_prediction": True}],
            "split": {"method": "random", "seed": 1729, "test_fraction": .2},
            "missing": "train_median_mode", "C": 1., "min_epv": 10, "cv_folds": 3,
            "bootstrap": 0, "independent_subjects": True, "selection": "none",
            "dca_thresholds": [.1, .2, .5], "clinical_decision_threshold": .5}
    else:
        spec = {"id": "id", "outcome": outcome_name, "cohort_id": cohort_id,
            "prediction_time": "synthetic baseline", "outcome_window": "synthetic 24-hour endpoint",
            "task": "continuous", "outcome_domain": "nonnegative", "outcome_transform": "identity",
            "target_policy": copy.deepcopy(_prediction_contracts.TARGET_POLICY),
            "features": [{"variable": "x", "kind": "continuous", "step": 1, "available_at_prediction": True},
                         {"variable": "z", "kind": "continuous", "step": 1, "available_at_prediction": True},
                         {"variable": "category", "kind": "categorical", "levels": [0, 1], "reference": 0, "available_at_prediction": True}],
            "split": {"method": "group", "group": "id", "seed": 1729, "test_fraction": .2, "cv_folds": 3},
            "tuning": {"ridge_grid": [.1, 1.]}, "evaluation": {"threshold": .5, "bootstrap_repetitions": 0}}
    fit_scope = "training_only" if operation == "train" else "frozen_only"
    task["analysis"] = {"method_id": method_id, "required_view_ids": ["wide"], "spec": None, "baseline": None,
        "prediction": {"operation": operation, "spec": spec, "model_ref": model_ref, "unknown_category_policy": "reject"},
        "effect_scale": "probability" if binary else "outcome units", "variance": "not_applicable", "ci_level": .95,
        "assumptions": ["Synthetic software verification only; clinical scientific review pending"]}
    task["split"] = {"strategy": spec["split"]["method"] if operation == "train" else "none",
        "group_key": spec["split"].get("group", "id"), "fold_field": None, "seed": 1729, "fit_scope": fit_scope}
    task["missingness"] = {"strategy": "train_median_mode", "fit_scope": fit_scope, "exclusion_denominator": "selected_view"}
    task["validation"] = {"kind": "internal_holdout" if operation == "train" else "synthetic_frozen_application" if operation == "evaluate" else "new_data_inference",
        "overlap_status": "not_applicable" if operation == "train" else "verified_synthetic_disjoint", "transportability": "not_evaluated"}
    if operation == "infer":
        task["time"]["analysis_as_of"] = 0
    return seal_task(task, core_root)


def failure(exc):
    return {"ok": False, "reason_code": exc.code, "stage": exc.stage,
            "missing_requirements": exc.missing, "completed_parts": []}


def read_json_bytes(raw):
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "JSON_DUPLICATE_KEY")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ContractBlocked("NONFINITE_JSON")))


def read_json(path):
    return read_json_bytes(Path(path).read_bytes())


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) not in {4, 5} or argv[0] not in {"validate", "validate-result"}:
        return 2
    _, task_path, output_path, root = argv[:4]
    project = Path(argv[4]).resolve() if len(argv) == 5 else Path(root).resolve()
    try:
        path = confined(task_path, project, "TASK_OUTSIDE_ISOLATED_ROOT")
        need(path.stat().st_size <= MAX_BYTES, "TASK_BYTE_LIMIT", "binding")
        task = read_json(path)
        if len(argv) == 5:
            need(task.get("schema_version") in {STUDY_INPUT_VERSION, _study_input.RESULT_VERSION}, "PROJECT_INPUT_SCHEMA_UNSUPPORTED")
            if argv[0] == "validate":
                need(Path(task["project_root"]).resolve() == project, "PROJECT_CHOICE_CONTEXT_MISMATCH")
        if argv[0] == "validate-result":
            schema = read_json(Path(root) / "schemas/result.schema.json")
            validate_schema(task, schema)
            result = {"ok": True}
        else:
            result = validate_task(task, root)
    except ContractBlocked as exc:
        result = failure(exc)
    except (OSError, ValueError, TypeError, KeyError):
        result = failure(ContractBlocked("INPUT_READ_OR_CONTRACT_FAILED"))
    try:
        target = confined(output_path, project, "PRIVATE_OUTPUT_OUTSIDE_ISOLATED_ROOT")
        with target.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(result, handle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    except (OSError, ContractBlocked):
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
