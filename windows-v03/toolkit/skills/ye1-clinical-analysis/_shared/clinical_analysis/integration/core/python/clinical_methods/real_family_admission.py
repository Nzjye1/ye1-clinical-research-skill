"""V1 family dispatch and closed-schema adapters; no admission grant or fitting.

The caller must run study_input.admit and the shared row/unit/identity/design
checks. These hooks select the existing family contracts without replacing the
bound task, changing its origin, supplying times, or fabricating a model.
The registry arguments accept contracts.py globals (schema/module names below).
"""
from __future__ import annotations

import copy
import math

INPUT_VERSION = "clinical-study-input@1.0"
SELF_CODE = "python/clinical_methods/real_family_admission.py"
PROVENANCE_VERSION = "clinical-frozen-provenance@1.0"

_FAMILIES = {
    "prediction": ("PREDICTION_SCHEMA", "_prediction_contracts", "0.2.0", ("prediction",)),
    "survival": ("SURVIVAL_SCHEMA", "_survival_contracts", "0.4.0", ("survival",)),
    "survival_v05": ("SURVIVAL_V05_SCHEMA", "_survival_v05_contracts", "0.5.0", ("survival", "cox_prediction")),
    "survival_v06": ("SURVIVAL_V06_SCHEMA", "_survival_v06_contracts", "0.6.0", ("survival", "cox_prediction", "survival_evaluation")),
    "penalized_v08": ("PENALIZED_V08_SCHEMA", "_penalized_v08_contracts", "0.8.0", ("penalized_prediction",)),
    "interpretation_v09": ("INTERPRETATION_V09_SCHEMA", "_interpretation_v09_contracts", "0.9.0", ("interpretation",)),
    "cox_penalized_v10": ("COX_PENALIZED_V10_SCHEMA", "_cox_penalized_v10_contracts", "0.10.0", ("cox_penalized_prediction",)),
}
METHODS = frozenset({
    "prediction.continuous.nonnegative.ridge", "prediction.binary.ridge",
    "survival.kaplan_meier", "survival.cox.association", "prediction.survival.cox",
    "evaluation.survival.cox.ipcw", "prediction.continuous.signed.lasso",
    "prediction.continuous.signed.elasticnet", "prediction.binary.lasso", "prediction.binary.elasticnet",
    "interpretation.linear.interventional", "prediction.survival.cox.lasso", "prediction.survival.cox.elasticnet",
})


def family_for_task(task):
    """Return dispatch metadata/legacy-shaped flags, or None for other methods.

    The shared Cox association ID has two explicit capabilities: presence of
    survival.ph_test selects v0.5; its absence selects v0.4. No row is inspected.
    """
    analysis = task.get("analysis", {}) if isinstance(task, dict) else {}
    method = analysis.get("method_id") if isinstance(analysis, dict) else None
    if method not in METHODS:
        return None
    if method in {"prediction.continuous.nonnegative.ridge", "prediction.binary.ridge"}:
        key = "prediction"
    elif method == "survival.kaplan_meier":
        key = "survival"
    elif method == "survival.cox.association":
        spec = analysis.get("survival")
        key = "survival_v05" if isinstance(spec, dict) and "ph_test" in spec else "survival"
    elif method == "prediction.survival.cox":
        key = "survival_v05"
    elif method == "evaluation.survival.cox.ipcw":
        key = "survival_v06"
    elif method == "interpretation.linear.interventional":
        key = "interpretation_v09"
    elif method in {"prediction.survival.cox.lasso", "prediction.survival.cox.elasticnet"}:
        key = "cox_penalized_v10"
    else:
        key = "penalized_v08"
    schema, module, version, fields = _FAMILIES[key]
    operation_key = {"prediction": "prediction", "penalized_v08": "penalized_prediction",
        "cox_penalized_v10": "cox_penalized_prediction", "survival_v05": "cox_prediction",
        "survival_v06": "cox_prediction"}.get(key)
    options = analysis.get(operation_key) if operation_key else None
    operation = "infer" if key == "interpretation_v09" else options.get("operation") if isinstance(options, dict) else None
    flags = {name: key == name.removesuffix("_task") for name in (
        "prediction_task", "survival_v05_task", "survival_v06_task", "penalized_v08_task",
        "interpretation_v09_task", "cox_penalized_v10_task")}
    flags["survival_task"] = key in {"survival", "survival_v05", "survival_v06"}
    flags["cox_prediction_task"] = method in {"prediction.survival.cox", "evaluation.survival.cox.ipcw"}
    return {"family": key, "schema_key": schema, "module_key": module,
        "legacy_version": "clinical-study-input@" + version + "-candidate1",
        "option_fields": fields, "operation": operation, "flags": flags}


def _entry(registry, context, field):
    key = context[field]
    if key in registry:
        return registry[key]
    if context["family"] in registry:
        return registry[context["family"]]
    raise ValueError("FAMILY_REGISTRY_ENTRY_REQUIRED")


def schema_for_task(task, study_schema, legacy_schemas):
    """Overlay original closed family options on the V1 common envelope.

    V1 source/auth/view/execution fields stay intact, including caller resource
    bounds. Family variable clocks and outcome/time shapes remain as strict as
    the old schema; unknown clocks cannot be turned into invented zeroes.
    """
    context = family_for_task(task)
    result = copy.deepcopy(study_schema)
    if context is None:
        return result
    legacy = _entry(legacy_schemas, context, "schema_key")
    for name in ("analysis", "variables", "time", "outcome"):
        result["properties"][name] = copy.deepcopy(legacy["properties"][name])
    if context["family"] in {"survival_v05", "survival_v06"}:
        prediction = result["properties"]["analysis"]["properties"].get("cox_prediction", {})
        for name in ("training_subjects", "holdout_subjects"):
            field = prediction.get("properties", {}).get(name)
            if field is not None: field["maxItems"] = 100000
    if context["family"] == "survival_v06":
        evaluation = result["properties"]["analysis"]["properties"].get("survival_evaluation", {})
        calibration = evaluation.get("properties", {}).get("calibration", {})
        minimum = calibration.get("properties", {}).get("min_bin_n")
        if minimum is not None: minimum["maximum"] = 100000
    timing = result["properties"]["time"]
    timing["properties"]["policy"] = {"const": "ordered_observation"}
    if "policy" not in timing["required"]:
        timing["required"].append("policy")
    result["$id"] = INPUT_VERSION
    result["properties"]["schema_version"] = {"const": INPUT_VERSION}
    return result


def code_requirements(task, base, modules):
    """Reuse family dependency chains, adding only this dispatch source."""
    context = family_for_task(task)
    if context is None:
        return set(base)
    def extend(key, codes):
        child = dict(context, family=key, module_key=_FAMILIES[key][1])
        return _entry(modules, child, "module_key").code_requirements(codes)
    key = context["family"]
    codes = set(base) | {SELF_CODE}
    if key in {"survival_v05", "survival_v06"}:
        codes = extend("survival", codes)
    if key == "survival_v06":
        codes = extend("survival_v05", codes)
    if key == "interpretation_v09":
        codes = extend("penalized_v08", codes)
    return extend(key, codes)


def _module(modules, key):
    return _entry(modules, {"family": key, "module_key": _FAMILIES[key][1]}, "module_key")


def validate_time(task, need, modules, stage="view_semantics"):
    """Delegate the selected strict ordered-time contract, never generalize it."""
    context = family_for_task(task)
    need(context is not None, "REAL_FAMILY_METHOD_NOT_IMPLEMENTED", stage)
    tm = task["time"]
    need(tm.get("policy") == "ordered_observation", "ORDERED_OBSERVATION_REQUIRED", stage)
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    window = tm.get("outcome_window")
    need(all(finite(tm.get(k)) for k in ("index", "feature_cutoff", "label_mature_at", "analysis_as_of"))
         and isinstance(window, list) and len(window) == 2 and all(finite(v) for v in window),
         "ORDERED_TIME_VALUES_REQUIRED", stage)
    for variable in task["variables"]:
        a, b = variable.get("occurred_at"), variable.get("available_at")
        need(finite(a) and finite(b), "FAMILY_VARIABLE_TIMING_REQUIRED", stage)
        need(a <= b, "AVAILABILITY_BEFORE_MEASUREMENT", stage)
        if variable["role"] in {"exposure", "covariate", "group"}:
            need(b <= tm["feature_cutoff"], "FUTURE_INFORMATION", stage)
    key = context["family"]
    if key in {"survival", "survival_v05", "survival_v06"}:
        need(isinstance(tm.get("eligibility_window"), list) and len(tm["eligibility_window"]) == 2
             and all(finite(v) for v in tm["eligibility_window"]) and finite(tm.get("observation_end")),
             "SURVIVAL_OBSERVATION_WINDOW_INVALID", stage)
        return _module(modules, "survival").validate_time(task, need, stage)
    if key == "interpretation_v09":
        return _module(modules, key).validate_time(task, need, stage, _module(modules, "penalized_v08"))
    if key in {"penalized_v08", "cox_penalized_v10"}:
        return _module(modules, key).validate_time(task, need, stage)
    need(tm["unit"] == "hour" and tm["timezone"] == "relative" and tm["boundary"] == "[start,end]"
         and not tm["delayed_entry"], "TIME_SEMANTICS_UNSUPPORTED", stage)
    need(tm["index"] <= tm["feature_cutoff"] <= window[0] < window[1] <= tm["label_mature_at"],
         "OUTCOME_LABEL_NOT_MATURE", stage)
    if context["operation"] != "infer":
        need(tm["label_mature_at"] <= tm["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", stage)


def result_context(task):
    """Classification only; test_only is purpose, never a source-origin proxy."""
    return {"data_origin": task["data_origin"], "task_purpose": task["task_purpose"],
        "test_only": task["task_purpose"] == "engineering_test", "scientific_review": "pending",
        "export_status": "local_only"}


def frozen_context(task, bundle, need, stage="binding"):
    """Check explicit new provenance without rewriting old models or hashes.

    A legacy wrapper has unrecorded origin, regardless of test_only=True. It may
    retain its old synthetic-test compatibility; it cannot certify real origin.
    Real engineering models legitimately retain test_only=True. New research
    wrappers require explicit provenance and test_only=False.
    """
    need(isinstance(bundle, dict), "UNSUPPORTED_MODEL_BUNDLE", stage)
    need(bundle.get("scientific_review") == "pending" and bundle.get("export_status") == "local_only",
         "MODEL_CLASSIFICATION_MISMATCH", stage)
    recorded = bundle.get("provenance_version")
    if recorded is None:
        need(task["data_origin"] != "real", "FROZEN_MODEL_ORIGIN_REQUIRED", stage)
        need(bundle.get("test_only") is True, "MODEL_CLASSIFICATION_MISMATCH", stage)
        return {"provenance_version": None, "data_origin": "unrecorded_legacy",
                "task_purpose": "unrecorded_legacy", "test_only": True, "scientific_review": "pending"}
    need(recorded == PROVENANCE_VERSION, "FROZEN_MODEL_PROVENANCE_VERSION_UNSUPPORTED", stage)
    need(bundle.get("data_origin") in {"real", "synthetic"}
         and bundle.get("task_purpose") in {"engineering_test", "research_analysis"},
         "MODEL_CLASSIFICATION_MISMATCH", stage)
    need(bundle.get("test_only") is (bundle["task_purpose"] == "engineering_test"),
         "MODEL_CLASSIFICATION_MISMATCH", stage)
    need(bundle["data_origin"] != "synthetic" or bundle["task_purpose"] == "engineering_test",
         "MODEL_CLASSIFICATION_MISMATCH", stage)
    need(bundle["data_origin"] == task["data_origin"], "FROZEN_MODEL_ORIGIN_MISMATCH", stage)
    need(bundle["task_purpose"] == task["task_purpose"], "FROZEN_MODEL_PURPOSE_MISMATCH", stage)
    return {key: copy.deepcopy(bundle[key]) for key in
            ("provenance_version", "data_origin", "task_purpose", "test_only", "scientific_review", "export_status")}


def wrapper_schema(task, legacy):
    """Closed compatibility branches for the proposed frozen-origin patch."""
    if task.get("schema_version") != INPUT_VERSION:
        return copy.deepcopy(legacy)
    upgraded = copy.deepcopy(legacy)
    upgraded["properties"].update(provenance_version={"const": PROVENANCE_VERSION},
        data_origin={"enum": ["real", "synthetic"]}, task_purpose={"enum": ["engineering_test", "research_analysis"]},
        test_only={"type": "boolean"})
    upgraded["required"] = list(dict.fromkeys(upgraded["required"] +
        ["provenance_version", "data_origin", "task_purpose"]))
    return upgraded if task["data_origin"] == "real" else {"anyOf": [copy.deepcopy(legacy), upgraded]}


def external_validation(task, *, kind):
    """Declaration labels only; the original validators still check actual IDs."""
    real = task.get("schema_version") == INPUT_VERSION and task.get("data_origin") == "real"
    return {"kind": "frozen_application" if real and kind == "synthetic_frozen_application" else kind,
        "overlap_status": "verified_canonical_identity_disjoint" if real else "verified_synthetic_disjoint",
        "transportability": "not_evaluated"}


def interpretation_scope(task):
    return "external_canonical_identity_disjoint" if task.get("schema_version") == INPUT_VERSION and task.get("data_origin") == "real" else "external_synthetic_disjoint"


def validate_options(task, rows, variables, root, helpers, modules=None):
    """Delegate unchanged family semantics and normalize only return structure.

    The pending patch is required for real frozen applications with new scope/
    wrapper metadata. This function never substitutes synthetic scope strings.
    Model/explainer confinement uses the admitted project; code/runtime bindings
    continue to use core_root through the original validators.
    """
    modules = helpers if modules is None else modules
    context = family_for_task(task)
    helpers["need"](context is not None, "REAL_FAMILY_METHOD_NOT_IMPLEMENTED", "method_applicability")
    key = context["family"]
    local_helpers = dict(helpers)
    original_confined = helpers["confined"]
    def confined(path, bound, code):
        if code in {"MODEL_OUTSIDE_ISOLATED_ROOT", "EXPLAINER_OUTSIDE_ISOLATED_ROOT"}:
            return original_confined(path, task["project_root"], code)
        return original_confined(path, bound, code)
    local_helpers["confined"] = confined
    value = {"family": key, "context": result_context(task), "flow": None, "semantics": None,
        "frozen_model": None, "frozen_model_json": None, "frozen_explainer": None, "frozen_origin": None}
    module = _module(modules, key)
    if key == "prediction":
        value["frozen_model"] = module.validate_options(task, rows, variables, root, local_helpers)
        value["semantics"] = module.canonical_semantics(task)
    elif key == "survival":
        value["semantics"] = module.validate_options(task, rows, variables, root, local_helpers)
    elif key in {"survival_v05", "survival_v06"}:
        args = [_module(modules, "survival")]
        if key == "survival_v06":
            args.insert(0, _module(modules, "survival_v05"))
        value["semantics"], value["frozen_model"], value["frozen_model_json"] = module.validate_options(
            task, rows, variables, root, local_helpers, *args)
    elif key == "interpretation_v09":
        value["flow"], value["semantics"], value["frozen_model"], value["frozen_explainer"] = module.validate_options(
            task, rows, variables, root, local_helpers, _module(modules, "penalized_v08"))
    else:
        value["flow"], value["semantics"], value["frozen_model"] = module.validate_options(
            task, rows, variables, root, local_helpers)
    if value["frozen_model"] is not None:
        value["frozen_origin"] = frozen_context(task, value["frozen_model"], helpers["need"])
    return value
