"""Integration envelope adapter. Calls the same owners; never registers a method."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
if __package__:
    from . import module
    from .contracts import CLUSTER,GROWTH,FORMAL,METHODS,VERSION,Blocked,need,exact,validate_request
    from .schema_tools import file_validate
else:
    import module
    from contracts import CLUSTER,GROWTH,FORMAL,METHODS,VERSION,Blocked,need,exact,validate_request
    from schema_tools import file_validate


def schema_name(method):
    return ("cluster" if method in CLUSTER else "growth" if method in GROWTH else
            "profile" if method=="latent.profile.gaussian" else "trajectory")+".payload.schema.json"


def check_semantics(payload, method, operation):
    s=payload["spec"];sem=payload["semantics"]
    need(sem["subject_key"]==s["subject_id"] and sem["group_key"] is None
         and sem["weights"]=={"kind":"none","field":None},"SEMANTIC_IDENTITY_OR_WEIGHT_MISMATCH")
    need(sem["missing_policy"]==(s["missing"] if method in CLUSTER|GROWTH else s["definition"]["missing"]),
         "SEMANTIC_MISSINGNESS_MISMATCH")
    expected={s["subject_id"]:("id","subject_id","1")}
    if method in CLUSTER or method=="latent.profile.gaussian":
        fields=s["features"] if method in CLUSTER else s["definition"]["indicators"]
        expected.update({f["name"]:("number","indicator",f["unit"]) for f in fields})
        need(sem["grain"]=="subject" and sem["record_keys"]==[s["subject_id"]]
             and sem["time"]=={"unit":None,"origin":None,"scale":None,"measurement_time_field":None,
                                  "availability":"declared_per_field"},"CROSS_SECTIONAL_GRAIN_MISMATCH")
        if method in CLUSTER and operation=="train":
            expected[s["split"]["field"]]=("category","partition","1")
    else:
        d=s if method in GROWTH else s["definition"]
        time=d["time"];outcome=d["outcome"]
        need(sem["grain"]=="subject_time" and sem["record_keys"]==[s["subject_id"],time["name"]],
             "LONGITUDINAL_GRAIN_MISMATCH")
        expected[time["name"]]=("number","time",time["unit"])
        if operation=="train" or method in FORMAL:
            expected[outcome["name"]]=("number","outcome",outcome["unit"])
        for f in d.get("covariates",[]):expected[f["name"]]=("number","covariate",f["unit"])
        need(sem["time"]=={"unit":time["unit"],"origin":time.get("origin",0),"scale":time.get("scale",1),
                            "measurement_time_field":time["name"],"availability":"row_time"},"TIME_SEMANTICS_MISMATCH")
    observed=sem["fields"]
    need(len(observed)==len(expected) and len({f["name"] for f in observed})==len(observed),"FIELD_ROLE_DECLARATION_MISMATCH")
    for f in observed:
        need(expected.get(f["name"])==(f["dtype"],f["role"],f["unit"]),"FIELD_ROLE_DECLARATION_MISMATCH")
        if f["role"] in {"subject_id","partition"}:
            need(f["measured_at"] is None and f["available_at"] is None,"IDENTITY_TIME_NOT_APPLICABLE")
        elif sem["grain"]=="subject_time":
            need(f["measured_at"]=="row_time" and f["available_at"]=="row_time","LONGITUDINAL_FIELD_TIMING_MISMATCH")
        else:
            need(type(f["measured_at"]) in [int,float] and type(f["available_at"]) in [int,float]
                 and f["available_at"]>=f["measured_at"],"CROSS_SECTIONAL_FIELD_TIMING_INVALID")
    need(all(set(row)==set(expected) for row in payload["data"]),"UNDECLARED_OR_MISSING_DATA_COLUMN")


def analyze(request):
    response={"api_version":"clinical-module-response@1.0","ok":False,"reason_code":None,
              "diagnostics":{"stage":"validation","details":{}},"public_record":None,"private_record":None}
    try:
        exact(request,["api_version","method_id","operation","payload","bindings"])
        need(request["api_version"]=="clinical-module-request@1.0","MODULE_API_VERSION_UNSUPPORTED")
        method=request["method_id"];operation=request["operation"]
        need(method in METHODS,"MODULE_METHOD_NOT_REGISTERED")
        bindings=request["bindings"]
        exact(bindings,["input_sha256","plan_sha256","code_sha256","runtime_sha256","model_sha256"])
        for name,value in bindings.items():
            need((name=="model_sha256" and value is None) or isinstance(value,str)
                 and re.fullmatch(r"[0-9a-f]{64}",value) is not None,"MODULE_BINDING_INVALID")
        p=request["payload"]
        file_validate(p,schema_name(method))
        need(bindings["model_sha256"]==(p["model_ref"]["sha256"] if p["model_ref"] else None),
             "MODULE_MODEL_BINDING_MISMATCH")
        if operation!="train":need(bindings["model_sha256"] is not None,"MODULE_FROZEN_MODEL_BINDING_REQUIRED")
        local={"schema_version":VERSION,"method_id":method,"operation":operation,"spec":p["spec"],
               "rows":p["data"],"test_only":p["test_only"]}
        if p["model_ref"] is not None:local["model_ref"]=p["model_ref"]
        validate_request(local)
        check_semantics(p,method,operation)
        result=module.compute_local(local,p["work_dir"])
        response["diagnostics"]={"stage":"complete" if result["status"]=="complete" else "analysis",
             "provider_hash":result["provider"]["code_hash"],"runtime_hash":result["binding"]["runtime_hash"],
             "details":result["analysis"].get("diagnostics",{}) if result["status"]=="complete" else result["analysis"]}
        if result["status"]!="complete":
            response["reason_code"]=result["reason_code"]
        else:
            analysis=copy.deepcopy(result["analysis"]);analysis.pop("diagnostics",None)
            response["public_record"]={"method_id":method,"operation":operation,"test_only":True,
                "scientific_review":"pending","export_status":"local_only","definition":result["definition"],
                "analysis":analysis,"warnings":result["warnings"]}
            work=Path(p["work_dir"])
            frozen=work/"model.json";individual=work/"individual-results.json"
            response["private_record"]={"model_json":frozen.read_text(encoding="utf-8") if frozen.exists() else None,
                "model_sha256":module.sha_file(frozen) if frozen.exists() else None,
                "individual_results":json.loads(individual.read_text(encoding="utf-8")) if individual.exists() else []}
            response["ok"]=True
        file_validate(response["diagnostics"],"diagnostics.schema.json")
        if response["public_record"] is not None:file_validate(response["public_record"],"public_record.schema.json")
        if response["private_record"] is not None:file_validate(response["private_record"],"private_record.schema.json")
    except Blocked as e:
        response.update(ok=False,reason_code=e.code,public_record=None,private_record=None)
        response["diagnostics"]={"stage":"validation","details":{}}
    except (KeyError,TypeError,ValueError,OSError):
        response.update(ok=False,reason_code="MODULE_API_EXECUTION_ERROR",public_record=None,private_record=None)
        response["diagnostics"]={"stage":"execution","details":{}}
    return response


def project(response, output_dir):
    """Called only by common projection; consumes validated records, never fits."""
    need(response.get("ok") is True,"CANNOT_PROJECT_BLOCKED_MODULE")
    file_validate(response["public_record"],"public_record.schema.json")
    public=copy.deepcopy(response["public_record"])
    public.update(status="complete",reason_code=None,tables=[],figures=[])
    output=Path(output_dir)
    need(not output.exists(),"OUTPUT_ALREADY_EXISTS")
    output.mkdir(parents=True)
    if __package__:
        from .artifacts import write_artifacts
    else:
        from artifacts import write_artifacts
    return write_artifacts(output,public)
