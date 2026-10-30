"""Private, bound module interface. Prediction and IPCW retain their existing owners."""
from __future__ import annotations
import copy
import csv
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
CORE = ROOT.parents[1] / "integration" / "core"
sys.path.insert(0, str(CORE / "python"))
sys.path.insert(0, str(ROOT))
from clinical_methods import contracts as core_contracts
from clinical_methods import cox_penalized_v10_contracts as cox_contracts
from clinical_methods import survival_evaluation
import schema_defs as sd

MODULE_FILES = ["module_api.py", "schema_defs.py", "adapters.py", "R/worker.R", "R/provider.R", "R/projection.R"]
FIXED_SOURCES = {
    "config/resource-budget-profiles.json": "6688d9dda381512a3687a8367fa39432b0224e06b1f4e6906abced983378d809",
    "python/clinical_methods/cox_penalized_v10_contracts.py": "60f1fb8baf5469a5db38f122a7538ba5b8dcfa41c6e0e268ab4907223a419fea",
    "python/clinical_methods/resource_budget.py": "8fdc878ab11114e07ff0a86f41afd2ab755424c1fa0f3852cbb0ba25d7bac1bc",
    "python/clinical_methods/survival.py": "c2742f940e44f440b2d064ae1cd51c300c8e35e1a54253620b074b2b4239684d",
    "python/clinical_methods/survival_evaluation.py": "793df575d9d4935dda82b20a8a7daee738973ab43ac11b2378be12f58764bc44",
    "src/clinanalysis/R/clinical_cox_penalized_v10.R": "776b43386c531f35d8dbfb6e58194d5fc74a371d0287e1f561d917cdb01eb948",
    "src/clinanalysis/R/clinical_interpretation_v09.R": "a2edfde2f6865077e4496e6154bb7d9603cea472cc70d06272354ec067d7a332",
    "src/clinanalysis/R/clinical_resource_budget.R": "3dde3dbbed5f9a36dbdc22f0bca46294aa1bcf345536bcaf385d6da43a7c95c4",
    "src/clinanalysis/R/clinical_survival_v06.R": "5d19beb5750d8dcf91bfcb65e9ee038d2bf24128c35cecb7bacb204a4322449c",
    "src/clinanalysis/R/interpretation_v09.R": "dc64253ecf46a944b79e2a9ebf40dffe916f3828e3d513b0e0bca030bba3349c"
}
OWNERS = ["cox_penalized_v10_analyze:infer", "penalized_v08_prepare:frozen", "survival_evaluation.evaluate",
          "interpretation_v09_group_scores", "R/provider.R:affine_explanation_and_nomogram_display"]

class Blocked(ValueError):
    pass
def need(ok, code):
    if not ok:
        raise Blocked(code)
def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def _pairs(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value, "CE_JSON_DUPLICATE_KEY")
        value[key] = item
    return value
def parse(text):
    try:
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda _: (_ for _ in ()).throw(Blocked("CE_NONFINITE_JSON")))
        finite(value)
        return value
    except (json.JSONDecodeError, UnicodeError):
        raise Blocked("CE_JSON_INVALID") from None
def finite(value):
    if isinstance(value, float):
        need(math.isfinite(value), "CE_NONFINITE_VALUE")
    elif isinstance(value, dict):
        need(all(isinstance(k, str) for k in value), "CE_OBJECT_KEY_INVALID")
        for item in value.values(): finite(item)
    elif isinstance(value, list):
        for item in value: finite(item)
    else:
        need(value is None or type(value) in (str, int, bool), "CE_JSON_TYPE_INVALID")
def validate(value, schema, code):
    try:
        finite(value)
        core_contracts.validate_schema(value, schema)
    except core_contracts.ContractBlocked:
        raise Blocked(code) from None
def closed(value, keys, code):
    need(isinstance(value, dict) and set(value) == set(keys), code)

def source_manifest(origin_context=None):
    lock = parse((CORE / "runtime-lock.json").read_text(encoding="utf-8"))
    expected = dict(FIXED_SOURCES)
    if origin_context is not None:
        admitted = parse((ROOT/"real_admission/manifest.json").read_text(encoding="utf-8"))
        expected = dict(admitted["shared_sources_sha256"])
        for name,wanted in admitted["numerical_owner_files_sha256"].items():
            need((ROOT/name).is_file() and sha(ROOT/name)==wanted,"CE_NUMERICAL_OWNER_DRIFT")
    expected.update({"src/clinanalysis/R/cox_penalized_v10.R": lock["cox_penalized_provider_version"],
                     "src/clinanalysis/R/penalized_v08.R": lock["cox_penalized_preprocessing_version"]})
    for name, wanted in expected.items():
        need((CORE / name).is_file() and sha(CORE / name) == wanted, "CE_SHARED_SOURCE_DRIFT")
    for module in (core_contracts, cox_contracts, survival_evaluation):
        need(Path(module.__file__).resolve().is_relative_to(CORE.resolve()), "CE_IMPORT_SOURCE_MISMATCH")
    own = {name: sha(ROOT / name) for name in MODULE_FILES}
    own.update({"contracts/"+p.name:sha(p) for p in sorted((ROOT/"contracts").glob("*.schema.json"))})
    support={"src/clinanalysis/R/clinical_common.R":sha(CORE/"src/clinanalysis/R/clinical_common.R"),
             "python/clinical_methods/contracts.py":sha(CORE/"python/clinical_methods/contracts.py")}
    return {"module": own, "shared": expected,"support":support}, lock

def runtime_descriptor(lock):
    expected = cox_contracts.expected_runtime_binding(lock)
    python = Path(lock["python"])
    need(Path(sys.executable).resolve() == python.resolve() and sha(python) == lock["executable_hashes"][lock["python"]], "CE_PYTHON_RUNTIME_MISMATCH")
    for path, wanted in expected["dependency_hashes"].items():
        need(Path(path).is_file() and sha(path) == wanted, "CE_RUNTIME_DEPENDENCY_DRIFT")
    need(sha(expected["rscript_engine"]) == expected["rscript_sha256"], "CE_RSCRIPT_DRIFT")
    return {"cox_runtime_binding":expected,"python_executable_sha256":sha(python),
            "python_version":platform.python_version(),"jsonlite":"2.0.0","digest":"0.6.39"}

def numerical_bindings(method_id, operation, payload, origin_context=None):
    """Module scientific provenance; these are NOT the common five bindings."""
    manifest, lock = source_manifest(origin_context)
    plan = {k:v for k,v in payload.items() if k not in ("rows","model_json","explainer_json")}
    model_hash = hashlib.sha256(payload["model_json"].encode("utf-8")).hexdigest()
    plan.update(method_id=method_id, operation=operation, model_sha256=model_hash,
        explainer_sha256=None if payload["explainer_json"] is None else hashlib.sha256(payload["explainer_json"].encode("utf-8")).hexdigest())
    return {"rows_sha256":digest(payload["rows"]),"payload_plan_sha256":digest(plan),
        "numerical_code_sha256":digest(manifest),"runtime_binding_sha256":digest(runtime_descriptor(lock)),"model_sha256":model_hash}

def make_request(method_id, operation, payload, bindings):
    """Envelope convenience only; bindings must come from the trusted common prepare."""
    return {"api_version":"clinical-module-request@1.0","method_id":method_id,"operation":operation,
            "payload":copy.deepcopy(payload),"bindings":copy.deepcopy(bindings)}

def model_binding(p, bn, lock, origin_context=None):
    wrapper = parse(p["model_json"])
    fields={"schema_version","method_id","provider_version","runtime_binding","canonical_semantics","model","test_only","scientific_review","export_status"}
    if origin_context is not None: fields.update({"provenance_version","data_origin","task_purpose"})
    closed(wrapper, fields, "CE_MODEL_WRAPPER_FIELDS_INVALID")
    need(wrapper["schema_version"] == cox_contracts.MODEL_VERSION and wrapper["method_id"] == p["model_method_id"], "CE_MODEL_VERSION_OR_METHOD_MISMATCH")
    need(wrapper["provider_version"] == lock["cox_penalized_provider_version"], "CE_MODEL_PROVIDER_MISMATCH")
    need(wrapper["runtime_binding"] == cox_contracts.expected_runtime_binding(lock), "CE_MODEL_RUNTIME_MISMATCH")
    need(wrapper["scientific_review"] == "pending" and wrapper["export_status"] == "local_only", "CE_MODEL_REVIEW_STATUS_INVALID")
    if origin_context is None: need(wrapper["test_only"] is True,"CE_MODEL_REVIEW_STATUS_INVALID")
    else:
        need(type(wrapper["test_only"]) is bool and wrapper["provenance_version"]=="clinical-frozen-provenance@1.0" and
             all(wrapper[k]==origin_context[k] for k in ("data_origin","task_purpose","test_only","scientific_review")),"CE_MODEL_ORIGIN_CONTEXT_MISMATCH")
    model=wrapper["model"]
    closed(model,cox_contracts.MODEL_FIELDS,"CE_MODEL_PAYLOAD_FIELDS_INVALID")
    need(model["schema_version"]==cox_contracts.PAYLOAD_VERSION and model["method_id"]==p["model_method_id"] and model["source"]==cox_contracts.MODEL_SOURCE,"CE_MODEL_PAYLOAD_BINDING_INVALID")
    validate(model["spec"],cox_contracts.options_schema()["properties"]["spec"],"CE_MODEL_SPEC_INVALID")
    need(model["semantics"]==wrapper["canonical_semantics"],"CE_CANONICAL_SEMANTICS_MISMATCH")
    sem=model["semantics"]
    closed(sem,("identity","features","duration","event","time","survival"),"CE_SEMANTIC_FIELDS_INVALID")
    semantic_fields=set(cox_contracts.SEMANTIC_FIELDS)
    for f in sem["features"]+[sem["duration"]]: closed(f,semantic_fields,"CE_SEMANTIC_FIELDS_INVALID")
    closed(sem["event"],semantic_fields|{"type","definition","event","non_event"},"CE_SEMANTIC_FIELDS_INVALID")
    closed(sem["identity"],("subject_id","group_id","canonical_identity_namespace"),"CE_SEMANTIC_FIELDS_INVALID")
    closed(sem["time"],("unit","timezone","index","feature_cutoff","outcome_window","boundary","delayed_entry"),"CE_SEMANTIC_FIELDS_INVALID")
    need(sem["time"]["timezone"]=="relative" and sem["time"]["boundary"]=="(0,end]" and sem["time"]["delayed_entry"] is False,"CE_TIME_SEMANTICS_UNSUPPORTED")
    need(p["cohort_id"]!=model["spec"]["cohort_id"],"CE_DISTINCT_COHORT_REQUIRED")
    horizons=p["horizons"]
    need(all(0<=t<=model["training_support"]["max_followup"] for t in horizons) and all(a<b for a,b in zip(horizons,horizons[1:])),"CE_HORIZON_OUTSIDE_SUPPORT")
    return wrapper

def validate_payload(p, operation, method, wrapper, resource_budget=None):
    m=wrapper["model"];s=m["spec"];sem=m["semantics"];st=p["structure"]
    need((method==sd.EVALUATE and operation=="evaluate") or (method==sd.EXPLAIN and operation in ("fit_explainer","explain")),"CE_METHOD_OPERATION_INVALID")
    need(st["subject_key"]==s["id"] and st["group_key"]==s["split"]["group_field"] and st["canonical_identity_namespace"]==s["canonical_identity_namespace"],"CE_IDENTITY_SEMANTICS_MISMATCH")
    need(st["time_unit"]==s["survival"]["time_unit"]==sem["time"]["unit"] and st["feature_cutoff"]==sem["time"]["feature_cutoff"]<=0 and st["analysis_as_of"]>=0,"CE_TIME_SEMANTICS_MISMATCH")
    expected=[(s["id"],"id","subject","1",None)]
    if st["group_key"] is not None: expected.append((st["group_key"],"id","group","1",None))
    expected += [(f["name"],f["type"],"feature",sem["features"][i]["unit"],st["feature_cutoff"]) for i,f in enumerate(s["features"])]
    expected += [(s["duration"],"number","duration",s["survival"]["time_unit"],None),(s["event"],"number","event","1",None)]
    variables={v["name"]:v for v in p["variables"]}
    need(len(variables)==len(p["variables"])==len(expected) and set(variables)=={x[0] for x in expected},"CE_VARIABLE_SET_INVALID")
    for name,dtype,role,unit,cutoff in expected:
        v=variables[name]
        need((v["dtype"],v["role"],v["unit"])==(dtype,role,unit),"CE_VARIABLE_ROLE_UNIT_MISMATCH")
        if role=="feature": need(type(v["measured_at"]) in (int,float) and type(v["available_at"]) in (int,float) and v["measured_at"]<=v["available_at"]<=cutoff,"CE_FEATURE_TIMING_LEAKAGE")
        else: need(v["measured_at"] is None and v["available_at"] is None,"CE_VARIABLE_TIME_INVALID")
    rows=p["rows"]
    need(len({r["subject_id"] for r in rows})==len(rows),"CE_DUPLICATE_SUBJECT")
    need(not {r["subject_id"] for r in rows}&set(m["training_subject_ids"]),"CE_TRAINING_SUBJECT_OVERLAP")
    for r in rows:
        need(r["subject_id"]==r["subject_id"].strip(),"CE_ID_INVALID")
        need((r["group_id"] is None) if st["group_key"] is None else isinstance(r["group_id"],str) and bool(r["group_id"].strip()),"CE_GROUP_ID_INVALID")
        need(r["group_id"] not in m["training_group_ids"],"CE_TRAINING_GROUP_OVERLAP")
        need(len(r["values"])==len(s["features"]),"CE_FEATURE_WIDTH_INVALID")
        for f,fm,value in zip(s["features"],m["preprocessor"]["features"],r["values"]):
            if value is None: continue
            if f["type"]=="number": need(type(value) in (int,float),"CE_FEATURE_TYPE_INVALID")
            else: need(isinstance(value,str) and value in fm["levels"],"CE_UNKNOWN_CATEGORY")
    if operation=="fit_explainer":
        need(not rows and p["explainer_json"] is None and p["evaluation"] is None and bool(p["display_domains"]),"CE_FREEZE_INPUT_INVALID")
    elif operation=="explain":
        need(bool(rows) and p["explainer_json"] is not None and p["evaluation"] is None and not p["display_domains"],"CE_EXPLAIN_INPUT_INVALID")
    else:
        need(bool(rows) and p["explainer_json"] is None and p["evaluation"] is not None and not p["display_domains"],"CE_EVALUATE_INPUT_INVALID")
        need(type(st["label_mature_at"]) in (int,float) and st["label_mature_at"]<=st["analysis_as_of"],"CE_LABELS_NOT_MATURE")
        for r in rows:
            need(type(r["duration"]) in (int,float) and 0<r["duration"]<=st["label_mature_at"] and type(r["event"]) in (int,float) and r["event"] in (0,1),"CE_COMPLETE_MATURE_ENDPOINT_REQUIRED")
        survival_evaluation.validate_evaluation(p["evaluation"], resource_budget)
    if operation!="evaluate":
        need(st["label_mature_at"] is None and all(r["duration"] is None and r["event"] is None for r in rows),"CE_EXPLANATION_OUTCOMES_FORBIDDEN")

def run_r(value, script="worker.R", output_dir=None, project_root=None):
    lock=parse((CORE/"runtime-lock.json").read_text(encoding="utf-8"))
    scratch=ROOT/".private-transport" if project_root is None else Path(project_root)/".ye1-privacy/private/ce-transport"
    scratch.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cox-module-",dir=scratch) as folder:
        need(Path(folder).resolve().is_relative_to(scratch.resolve()),"CE_TEMP_PATH_OUTSIDE_MODULE")
        src=Path(folder)/"request.json";dst=Path(folder)/"response.json"
        serialized = canonical(value)
        limits = value.get("resource_limits") if script == "worker.R" else None
        if limits is not None:
            need(len(serialized) <= limits["max_input_bytes"], "RESOURCE_INPUT_BUDGET_EXCEEDED")
        src.write_bytes(serialized)
        args=[lock["rscript_engine"],"--vanilla",str(ROOT/"R"/script),str(CORE),str(src),str(dst)]
        if limits is not None:
            args.append(str(limits["max_input_bytes"]))
        if output_dir is not None: args.append(str(output_dir))
        result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90,check=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        need(result.returncode==0 and dst.is_file(),"CE_R_WORKER_FAILED")
        response=parse(dst.read_text(encoding="utf-8"))
        need(response.get("ok") is True,response.get("reason_code","CE_R_WORKER_FAILED"))
        return response

def evaluation_view(p,wrapper,encoded):
    spec=wrapper["model"]["spec"];by_id={r["subject_id"]:r for r in p["rows"]}
    terms=[c["term"] for c in wrapper["model"]["preprocessor"]["columns"]]
    # These are actual retained frozen design columns, not dummy variables or another model.
    rows=[{"CE_SUBJECT":r["subject_id"],"CE_TIME":by_id[r["subject_id"]]["duration"],
           "CE_EVENT":by_id[r["subject_id"]]["event"],**dict(zip(terms,r["values"]))} for r in encoded]
    view={"method":"cox_ph","subject_id":"CE_SUBJECT","time":"CE_TIME","status":"CE_EVENT",
        **{k:spec["survival"][k] for k in ("time_unit","time_zero_definition","event_definition","censoring_definition","event_code","censor_code","ties")},
        "independent_subjects":True,"missing_policy":"complete_case","evaluation_times":p["horizons"],
        "covariates":[{"name":t,"type":"numeric","available_at_time_zero":True} for t in terms]}
    return rows,view

def diagnostics(stage):
    return {"module_id":"cox_evaluation_explanation","stage":stage,"risk_model_refitted":False,
        "preprocessing_fitted":False,"background_rows_used":False,"outcomes_used":False,"runtime_verified":False,
        "common_bindings":None,"rows_sha256":None,"payload_plan_sha256":None,
        "numerical_code_sha256":None,"runtime_binding_sha256":None,"record_sha256":None,"numerical_owners":OWNERS}

def analyze(request, *, origin_context=None, project_root=None, resource_budget=None):
    d=diagnostics("request_validation")
    try:
        envelope=parse((CORE.parent/"contracts/module-request.schema.json").read_text(encoding="utf-8"))
        validate(request,envelope,"CE_REQUEST_SCHEMA_INVALID")
        p=request["payload"];op=request["operation"];method=request["method_id"]
        validate(p,sd.payload_schema(),"CE_PAYLOAD_SCHEMA_INVALID")
        limits = survival_evaluation.survival._resource_limits(resource_budget, method)
        need(len(canonical(request)) <= limits["max_input_bytes"], "RESOURCE_INPUT_BUDGET_EXCEEDED")
        expected=numerical_bindings(method,op,p,origin_context)
        need(request["bindings"]["model_sha256"]==expected["model_sha256"],"CE_MODEL_BYTES_BINDING_MISMATCH")
        # The common entry point validates the first four bindings against its
        # trusted task/registry/runtime context before invoking analyze().
        d["common_bindings"]=copy.deepcopy(request["bindings"])
        d.update({k:expected[k] for k in ("rows_sha256","payload_plan_sha256","numerical_code_sha256","runtime_binding_sha256")})
        _,lock=source_manifest(origin_context);d["stage"]="model_binding"
        wrapper=model_binding(p,expected,lock,origin_context)
        validate_payload(p,op,method,wrapper,limits)
        if op != "fit_explainer":
            guard_spec = {"covariates": [{"type":"numeric"} for _ in wrapper["model"]["preprocessor"]["columns"]]}
            survival_evaluation.survival._check_resource_budget(p["rows"],guard_spec,p["horizons"],limits,method,
                "evaluate" if op=="evaluate" else "infer")
        explainer=None
        domains=p["display_domains"]
        if op=="explain":
            explainer=parse(p["explainer_json"])
            validate(explainer,admitted_schema(sd.explainer_schema(),origin_context,frozen=True),"CE_EXPLAINER_SCHEMA_INVALID")
            need(all(explainer[k]==expected[k] for k in ("model_sha256","numerical_code_sha256","runtime_binding_sha256")) and
                 explainer["model_method_id"]==p["model_method_id"] and explainer["horizons"]==p["horizons"],"CE_EXPLAINER_BINDING_MISMATCH")
            domains=explainer["display_domains"]
        d["stage"]="frozen_numerical_owner"
        calculated=run_r({"operation":op,"payload":p,"wrapper":wrapper,"domains":domains,"bindings":expected,"resource_limits":limits},project_root=project_root)
        d["runtime_verified"]=True
        private={"model_json":p["model_json"],"explainer_json":None,"predictions":calculated["predictions"],
            "encoded":calculated["encoded"],"contributions":calculated["contributions"],"nomogram_rows":calculated["nomogram_rows"],"evaluation":None}
        model=wrapper["model"];support=model["training_support"];sv=model["spec"]["survival"]
        public={"schema_version":"cox-evaluation-explanation-public@1.0","method_id":method,"operation":op,"status":"completed",
            "model_method_id":p["model_method_id"],"model_sha256":expected["model_sha256"],"explainer_sha256":None,
            "n_application":len(p["rows"]),"training_summary":{"n":support["n_training"],"events":support["events"],"censored":support["censored"],"horizon_max":support["max_followup"]},
            "semantics":{k:sv[k] for k in ("time_unit","time_zero_definition","event_definition","censoring_definition","event_code","censor_code")},
            "evaluation":None,"explanation":None,"test_only":True,"scientific_review":"pending","export_status":"local_only",
            "limitations":["SYNTHETIC_ENGINEERING_ONLY","NO_CLINICAL_VALIDATION","FROZEN_MODEL_NO_REFIT","NO_CAUSAL_INTERPRETATION"]}
        if origin_context is not None:
            public.update(schema_version="cox-evaluation-explanation-public@1.1",**{k:origin_context[k] for k in ("data_origin","task_purpose","test_only","scientific_review")})
            public["limitations"]=[x for x in public["limitations"] if x!="SYNTHETIC_ENGINEERING_ONLY"]
        if op=="evaluate":
            d["stage"]="ipcw_evaluation";d["outcomes_used"]=True
            rows,spec=evaluation_view(p,wrapper,calculated["encoded"])
            predictions=[{k:r[k] for k in ("subject_id","horizon","survival_probability","event_risk")} for r in calculated["predictions"]]
            result=survival_evaluation.evaluate(rows,spec,p["horizons"],predictions,p["evaluation"],expected["model_sha256"],wrapper["provider_version"],resource_budget=limits)
            need(result.get("ok") is True,result.get("reason_code","CE_EVALUATION_FAILED"))
            public["evaluation"]=result["record"];public["status"]=result["record"]["status"]
            private["evaluation"]=result["private_evaluation"]
            public["limitations"] += ["MARGINAL_CENSORING_INDEPENDENCE_UNVERIFIED","NO_UNCERTAINTY_INTERVALS","NO_WEIGHT_CLIPPING","NO_CONDITIONAL_CENSORING_MODEL"]
        else:
            definition=calculated["explanation"]["definition"]
            frozen={"schema_version":"frozen-cox-affine-explainer@1.0",**{k:expected[k] for k in ("model_sha256","numerical_code_sha256","runtime_binding_sha256")},
                "model_method_id":p["model_method_id"],"horizons":p["horizons"],"display_domains":domains,"definition":definition,
                "background":{"scope":"frozen_training_centering_summary","n_training":support["n_training"],
                    "encoded_means":[{"term":c["term"],"mean":0} for c in model["preprocessor"]["columns"]]},
                "derived":{"base_value":calculated["explanation"]["base_value"],"nomogram":calculated["explanation"]["nomogram"]}}
            if origin_context is not None: frozen.update(provenance_version="clinical-frozen-provenance@1.0",export_status="local_only",**{k:origin_context[k] for k in ("data_origin","task_purpose","test_only","scientific_review")})
            validate(frozen,admitted_schema(sd.explainer_schema(),origin_context,frozen=True),"CE_EXPLAINER_OUTPUT_INVALID")
            if explainer is not None: need(explainer==frozen,"CE_EXPLAINER_DERIVED_CONTENT_MISMATCH")
            private["explainer_json"]=canonical(frozen).decode("utf-8") if op=="fit_explainer" else p["explainer_json"]
            public["explainer_sha256"]=hashlib.sha256(private["explainer_json"].encode("utf-8")).hexdigest()
            public["explanation"]=calculated["explanation"]
            public["limitations"] += ["INTERVENTIONAL_NOT_CONDITIONAL_SHAP","NOT_PROBABILITY_SCALE_SHAP","TRAINING_FEATURE_RANGES_UNKNOWN","PRESPECIFIED_DISPLAY_DOMAINS_ONLY","JOINT_DOMAIN_COMBINATIONS_NOT_OBSERVED_POPULATION_SUPPORT"]
        d["stage"]="complete";d["record_sha256"]=digest({"public":public,"private":private})
        response={"api_version":"clinical-module-response@1.0","ok":True,"reason_code":None,"diagnostics":d,"public_record":public,"private_record":private}
        validate_response(response,origin_context)
        return response
    except (Blocked,survival_evaluation.EvaluationBlocked,survival_evaluation.survival.SurvivalBlocked) as exc:
        reason=str(exc)
        if not re.fullmatch("[A-Z][A-Z0-9_]{0,159}",reason): reason="CE_EXECUTION_FAILED"
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        reason="CE_EXECUTION_FAILED"
    return {"api_version":"clinical-module-response@1.0","ok":False,"reason_code":reason,"diagnostics":d,"public_record":None,"private_record":None}

def admitted_schema(schema, origin_context=None, *, frozen=False):
    schema=copy.deepcopy(schema)
    if origin_context is None:return schema
    props=schema["properties"]
    for name in ("data_origin","task_purpose","test_only","scientific_review"):
        props[name]={"const":origin_context[name]}
        if name not in schema["required"]:schema["required"].append(name)
    if frozen:
        props.update(provenance_version={"const":"clinical-frozen-provenance@1.0"},export_status={"const":"local_only"})
        schema["required"]=list(dict.fromkeys(schema["required"]+["provenance_version","export_status"]))
    else:props["schema_version"]={"const":"cox-evaluation-explanation-public@1.1"}
    return schema

def validate_response(response, origin_context=None):
    envelope=parse((CORE.parent/"contracts/module-response.schema.json").read_text(encoding="utf-8"))
    validate(response,envelope,"CE_RESPONSE_SCHEMA_INVALID")
    validate(response["diagnostics"],sd.diagnostics_schema(),"CE_DIAGNOSTIC_SCHEMA_INVALID")
    validate(response["private_record"],sd.private_schema(),"CE_PRIVATE_SCHEMA_INVALID")
    if response["ok"]:
        p=response["public_record"];v=response["private_record"]
        validate(p,admitted_schema(sd.public_schema(),origin_context),"CE_PUBLIC_SCHEMA_INVALID")
        need(v is not None and response["diagnostics"]["record_sha256"]==digest({"public":p,"private":v}),"CE_RESULT_INTEGRITY_MISMATCH")
        need(hashlib.sha256(v["model_json"].encode("utf-8")).hexdigest()==p["model_sha256"]==response["diagnostics"]["common_bindings"]["model_sha256"],"CE_RESULT_MODEL_BINDING_MISMATCH")
        model=parse(v["model_json"])["model"]
        need(model["method_id"]==p["model_method_id"],"CE_RESULT_MODEL_METHOD_MISMATCH")
        need(len(v["encoded"])==p["n_application"] and len({r["subject_id"] for r in v["encoded"]})==p["n_application"],"CE_RESULT_POPULATION_MISMATCH")
        if p["operation"]=="fit_explainer":
            need(p["n_application"]==0 and not v["predictions"] and not v["contributions"] and not v["nomogram_rows"],"CE_FREEZE_RESULT_HAS_INDIVIDUALS")
        else:
            horizons=sorted({r["horizon"] for r in v["predictions"]})
            identifiers=[r["subject_id"] for r in v["encoded"]]
            prediction_view=[{k:r[k] for k in ("subject_id","horizon","survival_probability","event_risk")} for r in v["predictions"]]
            survival_evaluation._predicted_risks(prediction_view,identifiers,horizons)
        need((p["operation"]=="evaluate" and p["evaluation"] is not None and p["explanation"] is None) or
             (p["operation"] in ("fit_explainer","explain") and p["evaluation"] is None and p["explanation"] is not None),"CE_RESULT_OPERATION_MISMATCH")
        if p["evaluation"] is not None:
            need(p["evaluation"]["model_sha256"]==p["model_sha256"] and p["evaluation"]["population"]["n_input"]==p["n_application"] and v["evaluation"] is not None,"CE_EVALUATION_RESULT_BINDING_MISMATCH")
        else:
            need(v["explainer_json"] is not None and hashlib.sha256(v["explainer_json"].encode("utf-8")).hexdigest()==p["explainer_sha256"],"CE_RESULT_EXPLAINER_BINDING_MISMATCH")
            frozen=parse(v["explainer_json"])
            validate(frozen,admitted_schema(sd.explainer_schema(),origin_context,frozen=True),"CE_EXPLAINER_OUTPUT_INVALID")
            need(frozen["derived"]=={k:p["explanation"][k] for k in ("base_value","nomogram")} and
                p["explanation"]["checks"]["passed"] is True and p["explanation"]["checks"]["n_application_checked"]==p["n_application"],"CE_EXPLANATION_RESULT_BINDING_MISMATCH")
            count=p["n_application"]*len(model["spec"]["features"])
            need(len(v["contributions"])==count==len(v["nomogram_rows"]),"CE_EXPLANATION_RESULT_ROWS_MISMATCH")

def project(response, output_dir, context, *, origin_context=None, project_root=None):
    validate_response(response,origin_context)
    need(response["ok"],"CE_PROJECTION_REQUIRES_SUCCESS")
    closed(context,("result_id","binding"),"CE_PROJECTION_CONTEXT_INVALID")
    need(isinstance(context["result_id"],str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,120}",context["result_id"]),"CE_RESULT_ID_INVALID")
    need(context["binding"]==response["diagnostics"]["common_bindings"],"CE_PROJECTION_BINDING_INVALID")
    target=Path(output_dir).resolve()
    need(not target.exists(),"CE_OUTPUT_ALREADY_EXISTS")
    target.mkdir(parents=True)
    (target/"private").mkdir();(target/"tables").mkdir();(target/"figures").mkdir()
    (target/"public.json").write_bytes(canonical({"result_id":context["result_id"],"binding":context["binding"],"record":response["public_record"]}))
    (target/"private"/"record.json").write_bytes(canonical(response["private_record"]))
    rendered=run_r({"record":response["public_record"],"context":context,"origin_context":origin_context},"projection.R",target,project_root=project_root)
    label="Synthetic engineering evidence" if origin_context is None else origin_context["data_origin"].upper()+" | "+origin_context["task_purpose"]
    (target/"METHODS.txt").write_text("Frozen penalized Cox predictions. IPCW uses the unchanged survival_evaluation owner.\nExplanations are grouped interventional contributions on centered log-relative-hazard.\nNomogram bounds are prespecified display domains; observed training feature support is unknown.\nRisk conversion is separate from SHAP. "+label+"; scientific review pending.\n",encoding="utf-8")
    return {"ok":True,"output_dir":str(target),"result_id":context["result_id"],"artifacts":rendered["artifacts"],"public_record_sha256":sha(target/"public.json")}
