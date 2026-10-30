"""V1 source-admission glue for the sole continuous-outcome PSM owner.

The shared caller must first admit the project and validate bound source rows,
identity, units and views.  These helpers grant no permission, choose no rows,
fit no score, and never select matches or alter the paired inference.
"""
from __future__ import annotations

import copy
import math

INPUT_VERSION = "clinical-study-input@1.0"
METHOD = "causal.psm.att.continuous"
METHODS = frozenset({METHOD})
SELF_CODE = "python/clinical_methods/psm_v07_admission.py"


def make_schema(study_schema, legacy_psm_schema):
    """Preserve the V1 envelope and the existing closed PSM parameter schema."""
    value = copy.deepcopy(study_schema)
    value["$id"] = INPUT_VERSION
    value["properties"]["schema_version"] = {"const": INPUT_VERSION}
    value["properties"]["analysis"] = copy.deepcopy(
        legacy_psm_schema["properties"]["analysis"])
    return value


def code_requirements(base, psm_contracts):
    return set(psm_contracts.code_requirements(base)) | {SELF_CODE}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_time(task, need, stage="view_semantics"):
    """PSM needs declared treatment ordering; unknown clocks cannot be zeroed."""
    tm = task["time"]
    need(task["analysis"]["method_id"] == METHOD, "METHOD_NOT_INTEGRATED", stage)
    need(tm.get("policy") == "ordered_observation",
         "PSM_ORDERED_TIME_REQUIRED", stage)
    need(tm["unit"] == "hour" and tm["timezone"] == "relative"
         and tm["boundary"] == "[start,end]" and not tm["delayed_entry"],
         "TIME_SEMANTICS_UNSUPPORTED", stage)
    window = tm["outcome_window"]
    need(all(_finite(tm[k]) for k in (
        "index", "feature_cutoff", "label_mature_at", "analysis_as_of"))
        and isinstance(window, list) and len(window) == 2
        and all(_finite(value) for value in window),
        "PSM_FINITE_ORDERED_TIME_REQUIRED", stage)
    need(tm["feature_cutoff"] <= tm["index"],
         "PSM_FEATURE_CUTOFF_AFTER_INDEX", stage)
    need(window[0] > tm["index"], "PSM_OUTCOME_WINDOW_NOT_POST_TREATMENT", stage)
    need(window[0] < window[1] <= tm["label_mature_at"] <= tm["analysis_as_of"],
         "OUTCOME_LABEL_NOT_MATURE", stage)
    options = task["analysis"]["psm"]
    variables = {v["name"]: v for v in task["variables"]}
    for name in [options["treatment"], options["outcome"], *options["covariates"]]:
        need(name in variables, "MODEL_FIELD_MISSING", stage)
        variable = variables[name]
        need(_finite(variable["occurred_at"]) and _finite(variable["available_at"]),
             "PSM_VARIABLE_TIMING_REQUIRED", stage)
        need(variable["occurred_at"] <= variable["available_at"],
             "AVAILABILITY_BEFORE_MEASUREMENT", stage)


def result_context(task):
    return {"data_origin": task["data_origin"],
            "task_purpose": task["task_purpose"],
            "test_only": task["task_purpose"] == "engineering_test",
            "scientific_review": "pending"}


def validate_options(task, rows, variables, root, helpers, psm_contracts):
    """Use unchanged PSM design, variable, missingness and flow validation."""
    need = helpers["need"]
    need(task.get("schema_version") == INPUT_VERSION,
         "PSM_ORIGIN_VERSION_REQUIRED", "input_contract")
    need(task.get("data_origin") in {"real", "synthetic"}
         and task.get("task_purpose") in {"engineering_test", "research_analysis"},
         "PSM_ORIGIN_CONTEXT_REQUIRED", "input_contract")
    need(task["data_origin"] != "synthetic"
         or task["task_purpose"] == "engineering_test",
         "SYNTHETIC_ENGINEERING_SCOPE_REQUIRED", "input_contract")
    budget = helpers["_resource_budget"]
    try:
        limits = budget.resolve(task["execution"], task["analysis"]["method_id"])
    except budget.BudgetError as exc:
        need(False, exc.code, "method_applicability")
    need(0 < len(rows) <= limits["max_rows"],
         "RESOURCE_ROW_BUDGET_EXCEEDED", "method_applicability")
    validate_time(task, need)
    flow, semantics = psm_contracts.validate_options(task, rows, variables, root, helpers)
    need(flow["n_treated"] * flow["n_control"] <= limits["max_candidate_pairs"],
         "RESOURCE_CANDIDATE_PAIR_BUDGET_EXCEEDED", "method_applicability")
    return flow, semantics
