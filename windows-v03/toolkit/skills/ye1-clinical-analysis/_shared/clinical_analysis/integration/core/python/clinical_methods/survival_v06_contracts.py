"""Closed v0.6 contracts for evaluation of an unchanged frozen Cox model.

The existing v0.5 contracts own model and canonical feature bindings. This
module adds prespecified evaluation options, complete evaluation labels and
an early check of the declared frozen support. It never estimates censoring,
changes a risk model or computes an evaluation statistic.
"""
from __future__ import annotations

import copy
import hashlib
if __package__:
    from . import resource_budget as budget_rules
else:
    import importlib.util
    from pathlib import Path
    _budget_spec = importlib.util.spec_from_file_location("survival_v06_budget", Path(__file__).with_name("resource_budget.py"))
    budget_rules = importlib.util.module_from_spec(_budget_spec)
    _budget_spec.loader.exec_module(budget_rules)

INPUT_VERSION = "clinical-study-input@0.6.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-survival-evaluation-v06-20261024"
EVALUATION_METHOD = "evaluation.survival.cox.ipcw"
METHODS = {EVALUATION_METHOD}
# Preserve the historical candidate branch; V1 widens a private schema copy.
MAX_ROWS = 500
MAX_HORIZONS = 12
N = {"type": "number"}
PROBABILITY = {"type": "number", "minimum": 0, "maximum": 1}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def arr(schema, minimum, maximum):
    return {"type": "array", "items": schema,
            "minItems": minimum, "maxItems": maximum}


SURVIVAL_EVALUATION = obj({
    "estimator": {"const": "marginal_reverse_km_ipcw"},
    "censoring_source": {"const": "evaluation_cohort"},
    "censoring_assumption": {"const": "independent_of_event_time_and_model_features"},
    "tie_order": {"const": "events_before_censoring"},
    "min_censoring_survival": {"const": 0.05},
    # JSON numbers 20 and 20.0 have the same meaning. The common validator's
    # strict const typing still rejects booleans through these two branches.
    "max_ipcw_weight": {"anyOf": [{"const": 20}, {"const": 20.0}]},
    "positivity_policy": {"const": "reject_no_clipping"},
    "roc_thresholds": arr(PROBABILITY, 2, 51),
    "calibration": obj({
        "method": {"const": "ipcw_hajek_fixed_bins"},
        "probability_edges": arr(PROBABILITY, 2, 11),
        "min_bin_n": {"type": "integer", "minimum": 2, "maximum": MAX_ROWS}}),
    "dca_thresholds": arr(PROBABILITY, 1, 51),
    "uncertainty": {"const": "not_implemented"},
    "prespecified": {"const": True}})
FROZEN_SUPPORT = obj({
    "last_event_time": N, "max_observed_time": N,
    "time_unit": {"enum": ["day", "hour"]}})


def make_schema(frozen_schema):
    """Append a separate closed schema without mutating earlier versions."""
    schema = copy.deepcopy(frozen_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    analysis = schema["properties"]["analysis"]
    analysis["properties"]["method_id"] = {"const": EVALUATION_METHOD}
    analysis["properties"]["survival_evaluation"] = copy.deepcopy(SURVIVAL_EVALUATION)
    analysis["required"].extend(["cox_prediction", "survival_evaluation"])
    prediction = analysis["properties"]["cox_prediction"]
    prediction["properties"]["operation"] = {"const": "infer"}
    prediction["properties"]["horizons"]["maxItems"] = MAX_HORIZONS
    analysis["properties"]["survival"]["properties"]["evaluation_times"]["maxItems"] = MAX_HORIZONS
    schema["properties"]["execution"]["properties"]["max_rows"]["maximum"] = MAX_ROWS
    return schema


def code_requirements(frozen_code):
    return set(frozen_code) | {
        "python/clinical_methods/survival_v06_contracts.py",
        "python/clinical_methods/survival_evaluation.py",
        "python/clinical_methods/survival_evaluation_bridge.py",
        "src/clinanalysis/R/clinical_survival_v06.R"}


def _strictly_ascending(values):
    return all(left < right for left, right in zip(values, values[1:]))


def validate_options(task, rows, variables, root, helpers, frozen_contracts, survival_contracts):
    """Validate evaluation scope, then reuse the unchanged frozen-infer checks."""
    need = helpers["need"]
    stage = "method_applicability"
    analysis = task["analysis"]
    need(analysis["method_id"] == EVALUATION_METHOD, "METHOD_NOT_INTEGRATED", stage)
    need(analysis["cox_prediction"]["operation"] == "infer",
         "SURVIVAL_EVALUATION_REQUIRES_FROZEN_INFER", stage)
    options = analysis["survival_evaluation"]
    # Also close this standalone validator when called outside validate_task.
    options_schema = copy.deepcopy(SURVIVAL_EVALUATION)
    if task.get("schema_version") == "clinical-study-input@1.0":
        options_schema["properties"]["calibration"]["properties"]["min_bin_n"]["maximum"] = budget_rules.ABSOLUTE_MAX_ROWS
    helpers["validate_schema"](options, options_schema, "analysis.survival_evaluation")
    roc = options["roc_thresholds"]
    need(_strictly_ascending(roc) and roc[0] == 0 and roc[-1] == 1,
         "SURVIVAL_EVALUATION_ROC_GRID_INVALID", stage)
    dca = options["dca_thresholds"]
    need(_strictly_ascending(dca) and all(0 < value < 1 for value in dca),
         "SURVIVAL_EVALUATION_DCA_GRID_INVALID", stage)
    edges = options["calibration"]["probability_edges"]
    need(_strictly_ascending(edges) and edges[0] == 0 and edges[-1] == 1,
         "SURVIVAL_EVALUATION_CALIBRATION_GRID_INVALID", stage)

    # Translation is confined to an in-memory contract-checking copy. The
    # returned task keeps the v0.6 method/options and original model JSON text.
    common = copy.deepcopy(task)
    common["analysis"]["method_id"] = frozen_contracts.PREDICTION_METHOD
    common["analysis"].pop("survival_evaluation")
    semantics, model, model_json = frozen_contracts.validate_options(
        common, rows, variables, root, helpers, survival_contracts)
    # v0.5 decodes with utf-8-sig. A leading BOM would be removed from the
    # preserved transport text, so refuse it before promising byte identity.
    # The existing loader has already verified the original file digest; no
    # second file read is needed. CRLF and all other UTF-8 bytes stay intact.
    need(hashlib.sha256(model_json.encode("utf-8")).hexdigest()
         == analysis["cox_prediction"]["model_sha256"],
         "FROZEN_MODEL_UTF8_BOM_UNSUPPORTED", "binding")
    spec = analysis["survival"]
    need(all(row[spec["time"]] is not None and row[spec["status"]] is not None for row in rows),
         "SURVIVAL_EVALUATION_LABEL_MISSING", stage)
    support = model.get("support")
    helpers["validate_schema"](support, FROZEN_SUPPORT, "model.support")
    need(0 < support["last_event_time"] <= support["max_observed_time"]
         and support["time_unit"] == spec["time_unit"], "MODEL_SUPPORT_INVALID", "binding")
    need(all(horizon <= support["last_event_time"] for horizon in analysis["cox_prediction"]["horizons"]),
         "PREDICTION_HORIZON_BEYOND_LAST_TRAINING_EVENT", stage)
    semantics.update(
        analysis_purpose="frozen_cox_ipcw_evaluation",
        evaluation_grid="prespecified horizons within frozen training event support",
        risk_model_fit_scope="frozen_only",
        evaluation_censoring_fit_scope="evaluation_cohort_only",
        label_missing_policy="reject_missing_evaluation_labels",
        evaluation_options=copy.deepcopy(options))
    return semantics, model, model_json
