"""Closed schemas for the private Cox module; no numerical implementation."""
from __future__ import annotations
import copy
import importlib.util
from pathlib import Path
_budget_path = Path(__file__).resolve().parents[2] / "integration/core/python/clinical_methods/resource_budget.py"
_budget_spec = importlib.util.spec_from_file_location("cox_module_resource_budget", _budget_path)
budget_rules = importlib.util.module_from_spec(_budget_spec)
_budget_spec.loader.exec_module(budget_rules)

EVALUATE = "evaluation.survival.cox.penalized.ipcw"
EXPLAIN = "interpretation.survival.cox.penalized.interventional"
MAX_ROWS = budget_rules.profile(EVALUATE)["ceiling_rows"]
MODEL_METHODS = ["prediction.survival.cox.lasso", "prediction.survival.cox.elasticnet"]
S = {"type": "string", "minLength": 1}
N = {"type": "number"}
I = {"type": "integer", "minimum": 0}
B = {"type": "boolean"}
H = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
STATUS = {"enum": ["completed", "partial", "unavailable"]}
def obj(fields):
    return {"type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}
def arr(item, lo=0, hi=10000):
    return {"type": "array", "items": item, "minItems": lo, "maxItems": hi}
def null(value):
    return {"anyOf": [value, {"type": "null"}]}
def const(value):
    return {"const": value}
NN, NS = null(N), null(S)
SCALAR = {"type": ["number", "string", "null"]}

DOMAIN = obj({"feature": S, "type": {"enum": ["number", "category"]}, "unit": S,
    "minimum": NN, "maximum": NN, "levels": arr(S, 0, 60),
    "prespecified": const(True), "source_note": S})
VARIABLE = obj({"name": S, "dtype": {"enum": ["id", "number", "category"]},
    "role": {"enum": ["subject", "group", "feature", "duration", "event"]}, "unit": S,
    "measured_at": NN, "available_at": NN})
ROW = obj({"subject_id": S, "group_id": NS, "values": arr(SCALAR, 1, 12),
    "duration": NN, "event": null({"type": "number", "minimum": 0, "maximum": 1})})
EVAL_OPTIONS = obj({
    "estimator": const("marginal_reverse_km_ipcw"), "censoring_source": const("evaluation_cohort"),
    "censoring_assumption": const("independent_of_event_time_and_model_features"),
    "tie_order": const("events_before_censoring"), "min_censoring_survival": {"type":"number","minimum":.05,"maximum":.05},
    "max_ipcw_weight": {"type":"number","minimum":20,"maximum":20},
    "positivity_policy": const("reject_no_clipping"), "roc_thresholds": arr(N,2,51),
    "calibration": obj({"method":const("ipcw_hajek_fixed_bins"),"probability_edges":arr(N,2,11),
                        "min_bin_n":{"type":"integer","minimum":2,"maximum":budget_rules.ABSOLUTE_MAX_ROWS}}),
    "dca_thresholds":arr(N,1,51), "uncertainty":const("not_implemented"), "prespecified":const(True)})

def payload_schema():
    return obj({"model_json": {"type":"string","minLength":1,"maxLength":1500000},
        "explainer_json": null({"type":"string","minLength":1,"maxLength":1500000}),
        "model_method_id":{"enum":MODEL_METHODS}, "cohort_id":S, "horizons":arr(N,1,8),
        "structure":obj({"grain":const("subject_wide"),"subject_key":S,"group_key":NS,
            "time_origin":{"type":"number","minimum":0,"maximum":0},"time_unit":{"enum":["day","hour"]},
            "independent_subjects":const(True),"weights":const("none"),"delayed_entry":const(False),
            "recurrent_events":const(False),"canonical_identity_namespace":S,
            "feature_cutoff":N,"analysis_as_of":N,"label_mature_at":NN}),
        "variables":arr(VARIABLE,4,17),"rows":arr(ROW,0,MAX_ROWS),"evaluation":null(EVAL_OPTIONS),
        "display_domains":arr(DOMAIN,0,12)})

METRIC = obj({"metric":{"enum":["auc","brier"]},"status":STATUS,"value":NN,"numerator":NN,
    "denominator":NN,"numerator_definition":S,"denominator_definition":S,"reason":NS,"uncertainty":const("not_implemented")})
ROC = obj({"threshold":NN,"boundary":{"enum":["above_all","fixed_grid"]},"status":STATUS,"reason":NS,
    "n_treated":I,"tp_weight":NN,"fp_weight":NN,"sensitivity":NN,"false_positive_rate":NN,"specificity":NN})
CALIBRATION = obj(dict({k:I for k in ("bin_index","n","n_cases","n_controls","n_censored_by_horizon")},
    **{k:N for k in ("lower","upper","predicted_risk_sum")},
    **{k:NN for k in ("mean_predicted_risk","sum_case_weights","sum_control_weights","sum_weights","ess","observed_risk")},
    right_inclusive=B,status=STATUS,reason=NS,uncertainty=const("not_implemented")))
DCA = obj(dict({k:I for k in ("n_treated","n_treated_cases","n_treated_controls","n_treated_censored_by_horizon","population_denominator")},
    **{k:N for k in ("threshold","threshold_odds")},
    **{k:NN for k in ("tp_weight","fp_weight","treated_weight_sum","treated_ess","numerator_model","numerator_all","net_benefit_model","net_benefit_all","net_benefit_none")},
    status=STATUS,reason=NS,uncertainty=const("not_implemented")))
HORIZON = obj({"horizon":N,"status":STATUS,"reason_codes":arr(S),
    "counts":obj({k:I for k in ("n","n_cases","n_controls","n_censored_by_horizon","n_at_risk_before_horizon","n_events_at_horizon","n_censored_at_horizon","n_case_control_score_ties")}),
    "weights":obj({k:NN for k in ("g_at_horizon","min_g_for_cases","sum_case_weights","sum_control_weights","sum_weights","max_weight","ess","case_ess","control_ess")}),
    "diagnostics":obj(dict({k:NN for k in ("weight_mass_minus_n","km_event_probability","weighted_case_probability","km_identity_difference")},
        weight_mass_identity_ok=null(B),km_identity_ok=null(B))),
    "metrics":arr(METRIC,2,2),"roc":arr(ROC,3,52),"calibration":arr(CALIBRATION,1,10),"dca":arr(DCA,1,51)})
EVALUATION = obj({"method_id":const("evaluation.survival.cox.ipcw"),"operation":const("evaluate"),
    "model_sha256":H,"frozen_model_provider_version":H,
    "population":obj({k:I for k in ("n_input","n_evaluable","n_dropped_missing","n_events","n_censored","n_horizons")}),
    "options":EVAL_OPTIONS,"censoring_metadata":obj({"estimator":S,"source":S,"assumption":S,
        "assumption_verified":const(False),"tie_order":S,"time_unit":S,"full_grid_location":const("private"),
        "weight_clipping":const(False),"uncertainty":const("not_implemented")}),
    "status":STATUS,"reason_codes":arr(S),"horizon_results":arr(HORIZON,1,8)})
DEFINITION = obj({"method":const("exact_affine_grouped_interventional_shap"),
    "background":const("frozen_training_centering_first_moments"),"encoded_expectation":const("analytic_zero_after_training_centering"),
    "coalition_unit":const("original_feature"),"missing_policy":const("frozen_training_median_mode"),
    "score_scale":const("centered_log_relative_hazard"),"score_unit":const("1"),
    "conditional":const(False),"probability_scale":const(False),"causal":const(False)})
NOM_DOMAIN = obj(dict(DOMAIN["properties"], impute_value=SCALAR,n_encoded_columns=I,
    score_min=N,score_max=N,score_range={"type":"number","minimum":0}))
AXIS = obj({"feature":S,"type":S,"unit":S,"input_kind":{"enum":["value","missing"]},
    "value":SCALAR,"resolved_value":SCALAR,"score_contribution":N,"points":N})
TOTAL = obj({"total_points":N,"score":N,"horizon":N,"survival_probability":N,"event_risk":N})
NOMOGRAM = obj({"domain_policy":const("prespecified_display_domains"),"training_feature_range_support":const("unknown"),
    "constant_on_display_domain":B,"score_at_zero":N,"score_per_point":NN,"points_denominator":N,"max_total_points":N,
    "domains":arr(NOM_DOMAIN,1,12),"axes":arr(AXIS,1,800),"total_axis":arr(TOTAL,1,40)})
IMPORTANCE = obj({"feature":S,"type":S,"n":I,"sum_abs_shap":N,"mean_abs_shap":N,"mean_shap":N,"min_shap":N,"max_shap":N})
CHECKS = obj({"atol":N,"rtol":N,"max_additivity_error":N,"max_score_backcheck_error":N,"max_risk_backcheck_error":N,"n_application_checked":I,"passed":B})
EXPLANATION = obj({"definition":DEFINITION,"base_value":N,"global_importance":arr(IMPORTANCE,0,12),
    "nomogram":NOMOGRAM,"checks":CHECKS})
SEMANTICS = obj({"time_unit":S,"time_zero_definition":S,"event_definition":S,"censoring_definition":S,"event_code":N,"censor_code":N})

def public_schema():
    return obj({"schema_version":const("cox-evaluation-explanation-public@1.0"),
        "method_id":{"enum":[EVALUATE,EXPLAIN]},"operation":{"enum":["evaluate","fit_explainer","explain"]},
        "status":STATUS,"model_method_id":{"enum":MODEL_METHODS},"model_sha256":H,"explainer_sha256":null(H),
        "n_application":I,"training_summary":obj({"n":I,"events":I,"censored":I,"horizon_max":N}),
        "semantics":SEMANTICS,"evaluation":null(EVALUATION),"explanation":null(EXPLANATION),
        "test_only":const(True),"scientific_review":const("pending"),"export_status":const("local_only"),"limitations":arr(S)})

GRID = obj({"time":N,"n_risk":I,"n_events":I,"n_censored":I,"censor_risk":I,"g_before":N,"g_after":N,"km_before":N,"km_after":N})
IPCW_ROW = obj(dict({"subject_id":S,"horizon":N,"observed_time":N,"event":I,"classification":S,"event_risk":N},
    **{k:NN for k in ("g_denominator","case_weight","control_weight","weight")},horizon_status=STATUS,horizon_reason_codes=arr(S)))
PREDICTION = obj({"subject_id":S,"horizon":N,"linear_predictor":N,"centered_linear_predictor":N,"survival_probability":N,"event_risk":N})
CONTRIBUTION = obj({"subject_id":S,"feature":S,"phi":N,"base_value":N,"score":N})
POINTS = obj({"subject_id":S,"feature":S,"score_contribution":N,"points":N,"total_points":N,"reconstructed_score":N})

def private_schema():
    return null(obj({"model_json":S,"explainer_json":NS,"predictions":arr(PREDICTION,0,MAX_ROWS*8),
        "encoded":arr(obj({"subject_id":S,"values":arr(N,2,60)}),0,MAX_ROWS),
        "contributions":arr(CONTRIBUTION,0,MAX_ROWS*12),"nomogram_rows":arr(POINTS,0,MAX_ROWS*12),
        "evaluation":null(obj({"censoring_grid":arr(GRID,1,MAX_ROWS),"individual_ipcw":arr(IPCW_ROW,1,MAX_ROWS*8)}))}))
def diagnostics_schema():
    return obj({"module_id":const("cox_evaluation_explanation"),"stage":S,
        "risk_model_refitted":const(False),"preprocessing_fitted":const(False),"background_rows_used":const(False),
        "outcomes_used":B,"runtime_verified":B,
        "common_bindings":null(obj({k:H for k in ("input_sha256","plan_sha256","code_sha256","runtime_sha256","model_sha256")})),
        "rows_sha256":null(H),"payload_plan_sha256":null(H),"numerical_code_sha256":null(H),"runtime_binding_sha256":null(H),
        "record_sha256":null(H),"numerical_owners":arr(S,0,10)})

def explainer_schema():
    return obj({"schema_version":const("frozen-cox-affine-explainer@1.0"),"model_sha256":H,
        "numerical_code_sha256":H,"runtime_binding_sha256":H,"model_method_id":{"enum":MODEL_METHODS},
        "horizons":arr(N,1,8),"display_domains":arr(DOMAIN,1,12),"definition":DEFINITION,
        "background":obj({"scope":const("frozen_training_centering_summary"),"n_training":I,
            "encoded_means":arr(obj({"term":S,"mean":{"type":"number","minimum":0,"maximum":0}}),2,60)}),
        "derived":obj({"base_value":N,"nomogram":NOMOGRAM})})

def all_schemas():
    return {name:dict({"$schema":"https://json-schema.org/draft/2020-12/schema"},**schema)
        for name,schema in {"payload":payload_schema(),"diagnostics":diagnostics_schema(),
            "public_record":public_schema(),"private_record":private_schema(),"explainer":explainer_schema()}.items()}
