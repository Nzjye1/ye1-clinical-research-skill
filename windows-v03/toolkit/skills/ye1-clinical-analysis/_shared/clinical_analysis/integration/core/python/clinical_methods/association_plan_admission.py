"""V1 admission glue for the existing prespecified association-plan owner.

This module never authorizes a project, reads rows from a source, changes a
task, selects cases, or estimates a model.  The shared study admission and
identity/unit/view validators must run first.  Only explicit time semantics
differ from the legacy synthetic envelope; all plan semantics are delegated.
"""
from __future__ import annotations

import copy
import math

INPUT_VERSION = "clinical-study-input@1.0"
SELF_CODE = "python/clinical_methods/association_plan_admission.py"
METHODS = frozenset({"association.linear.plan", "association.logistic.plan"})


def make_schema(study_schema, legacy_plan_schema):
    """Keep V1 source/authorization/variables/time and the closed owner plan."""
    result = copy.deepcopy(study_schema)
    result["$id"] = INPUT_VERSION
    result["properties"]["schema_version"] = {"const": INPUT_VERSION}
    result["properties"]["analysis"] = copy.deepcopy(
        legacy_plan_schema["properties"]["analysis"])
    return result


def code_requirements(base, plan_contracts):
    return set(plan_contracts.code_requirements(base)) | {SELF_CODE}


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_time(task, need, stage="view_semantics"):
    tm = task["time"]
    need(task["analysis"]["method_id"] in METHODS,
         "METHOD_NOT_INTEGRATED", stage)
    need(not tm["delayed_entry"], "DELAYED_ENTRY_UNSUPPORTED", stage)
    need(tm["timezone"] in {"relative", "not_applicable"},
         "TIMEZONE_UNSUPPORTED", stage)
    policy = tm["policy"]
    need(policy in {"cross_sectional_association", "ordered_observation"},
         "DESCRIPTIVE_TIME_CANNOT_SUPPORT_MODEL", stage)
    # A cross-sectional association may honestly have unknown clocks.  It
    # makes no prospective prediction or pre-outcome availability claim.
    if policy == "cross_sectional_association":
        return
    values = [tm[k] for k in ("index", "feature_cutoff", "label_mature_at",
                             "analysis_as_of")]
    window = tm["outcome_window"]
    need(all(_finite(v) for v in values) and isinstance(window, list)
         and len(window) == 2 and all(_finite(v) for v in window),
         "ORDERED_TIME_VALUES_REQUIRED", stage)
    need(tm["index"] <= tm["feature_cutoff"] <= window[0] < window[1]
         <= tm["label_mature_at"] <= tm["analysis_as_of"],
         "OUTCOME_LABEL_NOT_MATURE", stage)


def timing_guard(kind, task, variable, need, stage="method_applicability"):
    """Check real declared clocks, without manufacturing synthetic zeroes."""
    need(kind in {"outcome", "predictor", "filter"},
         "ASSOCIATION_PLAN_TIME_GUARD_INVALID", stage)
    tm = task["time"]
    occurred, available = variable["occurred_at"], variable["available_at"]
    need((occurred is None) == (available is None),
         "PARTIAL_VARIABLE_TIMING", stage)
    if occurred is not None:
        need(_finite(occurred) and _finite(available)
             and occurred <= available, "AVAILABILITY_BEFORE_MEASUREMENT", stage)
    if tm["policy"] == "ordered_observation":
        if kind == "outcome":
            need(occurred is not None and available <= tm["analysis_as_of"]
                 and tm["outcome_window"][0] <= occurred <= tm["outcome_window"][1],
                 "OUTCOME_LABEL_NOT_MATURE", stage)
        else:
            need(occurred is not None and available <= tm["feature_cutoff"],
                 "FUTURE_INFORMATION", stage)
    elif tm["policy"] == "cross_sectional_association":
        # Match the base V1 OLS/Logistic contract: missing clocks stay unknown;
        # known predictor/filter availability must respect a declared cutoff.
        if kind != "outcome" and available is not None and tm["feature_cutoff"] is not None:
            need(available <= tm["feature_cutoff"], "FUTURE_INFORMATION", stage)
        if kind == "outcome" and available is not None and tm["analysis_as_of"] is not None:
            need(available <= tm["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", stage)
    else:
        need(False, "DESCRIPTIVE_TIME_CANNOT_SUPPORT_MODEL", stage)


def result_context(task):
    return {"data_origin": task["data_origin"],
            "task_purpose": task["task_purpose"],
            "test_only": task["task_purpose"] == "engineering_test",
            "scientific_review": "pending"}


def validate_options(task, rows, variables, root, helpers, plan_contracts):
    """Delegate the sole existing plan validator with a V1 time callback."""
    need = helpers["need"]
    need(task.get("schema_version") == INPUT_VERSION,
         "ASSOCIATION_PLAN_ORIGIN_VERSION_REQUIRED", "input_contract")
    need(task.get("data_origin") in {"real", "synthetic"}
         and task.get("task_purpose") in {"engineering_test", "research_analysis"},
         "ASSOCIATION_PLAN_ORIGIN_CONTEXT_REQUIRED", "input_contract")
    need(task["data_origin"] != "synthetic" or task["task_purpose"] == "engineering_test",
         "SYNTHETIC_ENGINEERING_SCOPE_REQUIRED", "input_contract")
    budget = helpers["_resource_budget"]
    try:
        limits = budget.resolve(task["execution"], task["analysis"]["method_id"])
    except budget.BudgetError as exc:
        need(False, exc.code, "method_applicability")
    need(0 < len(rows) <= limits["max_rows"],
         "ASSOCIATION_PLAN_PROVIDER_ROW_LIMIT", "method_applicability")
    validate_time(task, need)
    return plan_contracts.validate_options(
        task, rows, variables, root, helpers, timing_guard=timing_guard)
