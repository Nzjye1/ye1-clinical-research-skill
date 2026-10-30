"""Strict semantics for local single-subject, single-event right-censored data.

No risk sets, censoring imputations, models or event-driven grids are built here.
The original survival.py numerical owner receives one validated rows/spec pair.
"""
from __future__ import annotations
import copy

INPUT_VERSION = "clinical-study-input@0.4.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-survival-v04-20261024"
METHODS = {"survival.kaplan_meier", "survival.cox.association"}
S = {"type":"string", "minLength":1}
NAME = {"type":"string", "pattern":"^[A-Za-z][A-Za-z0-9_]*$"}
N = {"type":"number"}


def obj(properties, required=None):
    return {"type":"object", "properties":properties,
            "required":list(properties) if required is None else required, "additionalProperties":False}


def arr(schema, minimum=0, maximum=None):
    result={"type":"array", "items":schema, "minItems":minimum}
    if maximum is not None:result["maxItems"]=maximum
    return result


COVARIATE = {"anyOf":[
    obj({"name":NAME, "type":{"const":"numeric"}, "available_at_time_zero":{"const":True}}),
    obj({"name":NAME, "type":{"const":"category"}, "available_at_time_zero":{"const":True},
         "levels":arr(S,2), "reference":S})]}
SPEC = obj({
    "method":{"enum":["kaplan_meier","cox_ph"]}, "subject_id":NAME, "time":NAME, "status":NAME,
    "time_unit":{"enum":["day","hour"]}, "time_zero_definition":S, "event_definition":S,
    "censoring_definition":S, "event_code":S, "censor_code":S,
    "independent_subjects":{"const":True}, "missing_policy":{"const":"complete_case"},
    "evaluation_times":arr(N,1,101), "covariates":arr(COVARIATE,0,10),
    "competing_codes":arr(S,0,0), "competing_event_definitions":arr(S,0,0),
    "left_truncation":{"const":False}, "time_varying_covariates":{"const":False},
    "recurrent_events":{"const":False}, "interval_censoring":{"const":False},
    "weights":{"const":False}, "strata":{"const":False}, "cluster":{"const":False},
    "ties":{"const":"breslow"}, "min_events_per_parameter":{"type":"number","minimum":10}},
    ["method","subject_id","time","status","time_unit","time_zero_definition","event_definition",
     "censoring_definition","event_code","censor_code","independent_subjects","missing_policy",
     "evaluation_times","covariates","competing_codes","competing_event_definitions","left_truncation",
     "time_varying_covariates","recurrent_events","interval_censoring","weights","strata","cluster"])


def make_schema(legacy_schema):
    schema=copy.deepcopy(legacy_schema)
    schema["$id"]=INPUT_VERSION
    schema["properties"]["schema_version"]={"const":INPUT_VERSION}
    analysis=schema["properties"]["analysis"]
    analysis["properties"].update(method_id={"enum":sorted(METHODS)},spec={"type":"null"},
                                  baseline={"type":"null"},survival=SPEC)
    analysis["required"].append("survival")
    roles=schema["properties"]["variables"]["items"]["properties"]["role"]["enum"]
    roles.extend(["survival_time","survival_status"])
    time=schema["properties"]["time"]
    time["properties"].update(eligibility_window=arr(N,2,2),observation_end=N)
    time["required"].extend(["eligibility_window","observation_end"])
    return schema


def code_requirements(legacy):
    return set(legacy) | {"python/clinical_methods/survival.py", "python/clinical_methods/survival_bridge.py",
        "python/clinical_methods/survival_contracts.py", "src/clinanalysis/R/clinical_survival.R"}


def validate_time(task, need, stage="view_semantics"):
    tm=task["time"]
    need(tm["unit"] in {"day","hour"} and tm["timezone"]=="relative" and tm["boundary"]=="(0,end]",
         "SURVIVAL_TIME_SEMANTICS_UNSUPPORTED",stage)
    need(not tm["delayed_entry"],"SURVIVAL_DELAYED_ENTRY_UNSUPPORTED",stage)
    need(tm["index"]==0 and tm["feature_cutoff"]==0,"SURVIVAL_FIXED_TIME_ZERO_REQUIRED",stage)
    start,end=tm["eligibility_window"]
    need(start<=end==0,"SURVIVAL_ELIGIBILITY_WINDOW_INVALID",stage)
    need(tm["observation_end"]>0 and tm["outcome_window"]==[0,tm["observation_end"]]
         and tm["label_mature_at"]==tm["observation_end"] and tm["analysis_as_of"]>=tm["observation_end"],
         "SURVIVAL_OBSERVATION_WINDOW_INVALID",stage)


def validate_options(task,rows,variables,root,helpers):
    need=helpers["need"];stage="method_applicability"
    analysis,tm,identity,outcome=task["analysis"],task["time"],task["identity"],task["outcome"]
    method=analysis["method_id"];spec=analysis["survival"]
    cox=method=="survival.cox.association"
    need(method in METHODS,"METHOD_NOT_INTEGRATED",stage)
    need(spec["method"]==("cox_ph" if cox else "kaplan_meier"),"SURVIVAL_METHOD_SPEC_MISMATCH",stage)
    need(analysis["effect_scale"]==("hazard_ratio" if cox else "survival_probability"),"EFFECT_SCALE_MISMATCH",stage)
    need(analysis["variance"]==("model" if cox else "greenwood") and analysis["ci_level"]==.95,
         "SURVIVAL_INFERENCE_OPTIONS_UNSUPPORTED",stage)
    need(task["missingness"]=={"strategy":"complete_case","fit_scope":"not_applicable","exclusion_denominator":"selected_view"},
         "MISSINGNESS_POLICY_UNSUPPORTED",stage)
    need(task["derivation"]=={"strategy":"declared_unit_conversion_only","version":"1"},"DERIVATION_NOT_ENABLED",stage)
    selected=next(v for v in task["views"] if v["view_id"]==analysis["required_view_ids"][0])
    need(selected["kind"]=="survival_subject" and selected["grain"]=="subject" and identity["analysis_unit"]=="subject"
         and identity["encounter_key"] is None,"SURVIVAL_SUBJECT_VIEW_REQUIRED",stage)
    need(spec["subject_id"]==identity["subject_key"] and identity["record_keys"]==[spec["subject_id"]],
         "SURVIVAL_IDENTITY_MISMATCH",stage)
    names=[spec["subject_id"],spec["time"],spec["status"]]
    need(len(set(names))==3,"TIME_STATUS_AND_ID_MUST_DIFFER",stage)
    need(all(name in variables for name in names),"SURVIVAL_FIELD_MISSING",stage)
    tvar,svar=variables[spec["time"]],variables[spec["status"]]
    need(tvar["dtype"]=="number" and tvar["role"]=="survival_time","SURVIVAL_TIME_FIELD_INVALID",stage)
    need(svar["dtype"]=="category" and svar["role"]=="survival_status","SURVIVAL_STATUS_FIELD_INVALID",stage)
    need(tvar["unit"]==tm["unit"]==spec["time_unit"] and tvar["dimension"]=="time","SURVIVAL_TIME_UNIT_MISMATCH",stage)
    need(outcome["type"]=="time_to_event" and outcome["field"]==spec["status"] and outcome["censoring"]=="right",
         "SURVIVAL_OUTCOME_CONTRACT_MISMATCH",stage)
    need(spec["event_code"]!=spec["censor_code"] and set(svar["levels"])=={spec["event_code"],spec["censor_code"]}
         and outcome["event"]==spec["event_code"] and outcome["non_event"]==spec["censor_code"],
         "SURVIVAL_EVENT_CODING_MISMATCH",stage)
    need(task["cohort"]["index_event"]==spec["time_zero_definition"] and outcome["definition"]==spec["event_definition"]
         and all(spec[key].strip() for key in ("time_zero_definition","event_definition","censoring_definition")),
         "SURVIVAL_DEFINITION_MISMATCH",stage)
    for variable in (tvar,svar):
        need(variable["available_at"]<=tm["analysis_as_of"] and variable["occurred_at"]<=tm["observation_end"],
             "SURVIVAL_ENDPOINT_NOT_OBSERVED",stage)
    # Check every observed duration before any complete-case deletion. The
    # provider repeats positive-time/status validation and owns actual support.
    need(all(row[spec["time"]] is None or row[spec["time"]]>0 for row in rows),"FOLLOWUP_MUST_BE_POSITIVE",stage)
    need(all(row[spec["time"]] is None or row[spec["time"]]<=tm["observation_end"] for row in rows),
         "FOLLOWUP_EXCEEDS_OBSERVATION_END",stage)
    grid=spec["evaluation_times"]
    need(all(0<=value<=tm["observation_end"] for value in grid) and all(a<b for a,b in zip(grid,grid[1:])),
         "SURVIVAL_EVALUATION_GRID_INVALID",stage)
    covariates=spec["covariates"]
    cov_names=[cov["name"] for cov in covariates]
    need(len(set(cov_names))==len(cov_names),"DUPLICATE_COVARIATE",stage)
    need(not set(cov_names).intersection(names),"OUTCOME_TIME_OR_ID_AS_COVARIATE",stage)
    if cox:
        need(bool(covariates),"COX_COVARIATES_REQUIRED",stage)
        need(spec.get("ties")=="breslow","ONLY_BRESLOW_TIES_SUPPORTED",stage)
        need("min_events_per_parameter" in spec,"COX_EVENT_GUARD_REQUIRED",stage)
    else:
        need(not covariates,"COVARIATES_REQUIRE_COX_METHOD",stage)
        need("ties" not in spec and "min_events_per_parameter" not in spec,"COX_OPTIONS_REQUIRE_COX_METHOD",stage)
    for cov in covariates:
        name=cov["name"]
        need(name in variables,"MODEL_FIELD_MISSING",stage)
        variable=variables[name]
        need(variable["dtype"]!="id","ID_MODEL_FIELD_FORBIDDEN",stage)
        need(variable["role"] in {"exposure","covariate","group"},"SURVIVAL_COVARIATE_ROLE_INVALID",stage)
        need(variable["occurred_at"]<=variable["available_at"]<=tm["index"],"FUTURE_INFORMATION",stage)
        need(variable["dtype"]==("number" if cov["type"]=="numeric" else "category"),"SURVIVAL_COVARIATE_TYPE_MISMATCH",stage)
        if cov["type"]=="category":
            need(cov["levels"]==variable["levels"] and cov["reference"]==variable["reference"],"SURVIVAL_CATEGORY_CONTRACT_MISMATCH",stage)
    return {"analysis_purpose":"conditional_survival_association" if cox else "descriptive_survival",
            "time_zero":0,"eligibility_window":tm["eligibility_window"],"observation_end":tm["observation_end"],
            "time_unit":spec["time_unit"],"censoring":"right","events":"single_endpoint",
            "evaluation_grid":"prespecified; actual complete-case support checked by provider",
            "ph_diagnostic_scope":"descriptive_Spearman_only_not_formal_PH_test" if cox else "not_applicable"}
