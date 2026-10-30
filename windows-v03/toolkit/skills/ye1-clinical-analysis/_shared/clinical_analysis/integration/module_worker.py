"""Thin module transport called only by clinanalysis run_analysis_task.

All estimation remains in registered providers. This process validates both
directions, binds actual local bytes, and projects validated aggregate records.
"""
from pathlib import Path
import csv,datetime,hashlib,importlib,importlib.util,json,os,subprocess,sys,traceback
from module_contract import ContractError,read_json,_validator,_check
from module_task import ROOT,CORE,prepare,sha,canonical,obj,arr,HASH,NULL,TEXT
from runtime_registry import lock_digest
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def result_schema(registry,definition):
    record=definition["validators"]["public_record"].schema
    diag=definition["validators"]["diagnostics"].schema
    return obj({"schema_version":{"const":"clinical-modular-result@1.0"},"core_version":{"const":"modular-development-1"},
      "study_id":TEXT,"run_id":TEXT,"method_id":TEXT,"method_version":TEXT,"module_id":TEXT,
      "execution_status":{"enum":["complete","partial","blocked"]},"reason_code":{"anyOf":[TEXT,NULL]},
      "scientific_review":{"const":"pending"},"export_status":{"const":"local_only"},"test_only":{"const":True},
      "bindings":read_json(ROOT/"contracts/module-request.schema.json")["properties"]["bindings"],
      "model_bytes_sha256":{"anyOf":[HASH,NULL]},"model_binding_semantics":TEXT,
      "training_background":{"anyOf":[__import__("training_background").metadata_schema(),NULL]},
      "provider":obj({"numerical_owner":TEXT,"registered_code_sha256":HASH,"module_manifest_sha256":HASH}),
      "module_record":{"anyOf":[record,NULL]},"diagnostics":diag,
      "provenance":obj({"data_origin":{"const":"synthetic_inline_normalized"},"normalized_payload_sha256":HASH,"integration_lock_sha256":HASH,
          "host_isolation_evidence":{"const":"not_established"},"clinical_applicability":{"const":"not_validated"}}),
      "artifacts":arr(obj({"relative_path":TEXT,"kind":{"enum":["table","figure","report"]},"sha256":HASH,"bytes":{"type":"integer","minimum":0},
          "source_result_id":TEXT,"input_sha256":HASH,"method_id":TEXT,"method_version":TEXT,"semantics_source":TEXT})),
      "limitations":arr(TEXT),"completed_parts":arr(TEXT)})
def load_python(info,entry=None):
    os.environ["CLINICAL_CORE_ROOT"]=str(CORE)
    os.environ["CLINICAL_MODULE_CONTRACTS"]=str(ROOT/"contracts")
    module=info["root"];entry=entry or info["manifest"]["entrypoint"]
    if info["manifest"]["module_id"]=="latent_longitudinal":
        sys.path.insert(0,str(module.parent));return importlib.import_module("latent_longitudinal."+Path(entry["path"]).with_suffix("").as_posix().replace("/","."))
    sys.path.insert(0,str(module))
    if entry["path"].startswith("tree_shap/"):
        return importlib.import_module(Path(entry["path"]).with_suffix("").as_posix().replace("/","."))
    spec=importlib.util.spec_from_file_location("registered_"+info["manifest"]["module_id"]+"_"+Path(entry["path"]).stem,module/entry["path"])
    api=importlib.util.module_from_spec(spec);sys.modules[spec.name]=api;spec.loader.exec_module(api);return api
def r_call(mode,info,request_path,response_path,output,context_path,log_path):
    runtime=read_json(CORE/"runtime-lock.json")
    args=[runtime["rscript"],"--vanilla",str(ROOT/"module_transport.R"),mode,str(info["root"]),str(CORE),
          str(request_path),str(response_path),str(output),str(context_path)]
    with Path(log_path).open("wb") as log:run=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,timeout=600)
    if run.returncode:raise ContractError("MODULE_R_TRANSPORT_FAILED")
def artifacts(output,request,run_id,definition,data_origin,projection=None,origin_context=None):
    from data_disclosure import disclosure,figure,table_envelope
    origin_meta,_=disclosure(data_origin)
    if origin_context is not None:
        origin_meta.update({"core_"+k:origin_context[k] for k in ("task_purpose","test_only","scientific_review")})
    projection=Path(projection) if projection is not None else output/"private/provider-projection";records=[]
    for path in sorted(projection.rglob("*")):
        if not path.is_file() or "private" in path.relative_to(projection).parts:continue
        suffix=path.suffix.lower();kind={".csv":"table",".png":"figure",".md":"report",".txt":"report"}.get(suffix)
        if kind is None:continue
        sidecar=None
        if kind=="table":
            with path.open(encoding="utf-8-sig",newline="") as h:reader=csv.DictReader(h);fields=reader.fieldnames;rows=list(reader)
            if fields is not None:
                meta={"core_result_id":run_id,"core_method_id":request["method_id"],"core_method_version":definition["method_version"],
                      "core_input_sha256":request["bindings"]["input_sha256"],"core_plan_sha256":request["bindings"]["plan_sha256"],**origin_meta}
                if set(meta)&set(fields):raise ContractError("MODULE_TABLE_METADATA_COLLISION")
                # Keep the provider projection and its own hashes intact. The
                # common table is a separately identified provenance projection.
                target=output/"tables"/("__".join(path.relative_to(projection).parts))
                target.parent.mkdir(exist_ok=True)
                with target.open("x",encoding="utf-8-sig",newline="") as h:
                    writer=csv.DictWriter(h,fields+list(meta));writer.writeheader();writer.writerows([{**r,**meta} for r in rows])
                path=target
                sidecar=table_envelope(path,data_origin,{"result_id":run_id,"method_id":request["method_id"],"method_version":definition["method_version"],
                    "input_sha256":request["bindings"]["input_sha256"],"plan_sha256":request["bindings"]["plan_sha256"]},
                    context={k:origin_context[k] for k in ("task_purpose","test_only")} if origin_context else None)
            else:raise ContractError("MODULE_TABLE_HEADER_REQUIRED")
        elif kind=="figure":
            target=output/"figures"/("__".join(path.relative_to(projection).parts))
            figure(path,target,data_origin);path=target
            if origin_context is not None:
                spec=importlib.util.spec_from_file_location("module_png_context",CORE/"python/clinical_methods/study_artifacts.py")
                stamp=importlib.util.module_from_spec(spec);spec.loader.exec_module(stamp)
                stamp.stamp_png(path,data_origin,origin_context["task_purpose"])
        else:
            target=output/"reports"/("__".join(path.relative_to(projection).parts));target.parent.mkdir(exist_ok=True)
            _,label=disclosure(data_origin)
            with target.open("x",encoding="utf-8") as handle:handle.write(label+"\nData origin: "+data_origin+"\n\n"+path.read_text(encoding="utf-8-sig"))
            path=target
        records.append({"relative_path":path.relative_to(output).as_posix(),"kind":kind,"sha256":sha(path),"bytes":path.stat().st_size,
          "source_result_id":run_id,"input_sha256":request["bindings"]["input_sha256"],"method_id":request["method_id"],
          "method_version":definition["method_version"],"semantics_source":"module_record: preserve each metric/effect denominator, scale and unavailable reason"})
        if sidecar is not None:
            records[-1]["semantics_source"]+="; share only with bound "+sidecar.name+" (clinical-csv-envelope@1.0)"
            records.append({"relative_path":sidecar.relative_to(output).as_posix(),"kind":"report","sha256":sha(sidecar),"bytes":sidecar.stat().st_size,
                "source_result_id":run_id,"input_sha256":request["bindings"]["input_sha256"],"method_id":request["method_id"],"method_version":definition["method_version"],
                "semantics_source":"Machine-readable clinical-csv-envelope@1.0 metadata report; mandatory companion of "+path.name+"; includes origin and row_count even at zero rows"})
    return records

def admitted_result_schema(packet):
    """Origin-aware result wrapper; the registered numerical record stays closed."""
    import copy
    schema=copy.deepcopy(result_schema(packet["registry"],packet["definition"]))
    props=schema["properties"];context=packet["origin_context"]
    props["schema_version"]={"const":"clinical-modular-result@1.1"}
    props["test_only"]={"const":context["test_only"]}
    props["provenance"]["properties"]["data_origin"]={"const":context["data_origin"]}
    for name in ("data_origin","task_purpose"):
        props[name]={"const":context[name]};schema["required"].append(name)
    props["origin_context"]=obj({k:{"const":v} for k,v in context.items()});schema["required"].append("origin_context")
    props["admitted_lock_sha256"]=HASH;schema["required"].append("admitted_lock_sha256")
    if not packet["response"]["ok"] and packet["info"]["manifest"]["module_id"]=="nonlinear_prediction":
        module_root=packet["info"]["root"]
        props["diagnostics"]=read_json(module_root/"real_admission/failure-diagnostics.schema.json")
    return schema

def finalize_admitted_module(packet,output):
    """Publish only a validated admitted record; never use the synthetic executor."""
    output=Path(output).resolve();private=output/"private"
    task,request,response=packet["task"],packet["request"],packet["response"]
    info,definition,context=packet["info"],packet["definition"],packet["context"]
    origin=packet["origin_context"]
    for record in (response.get("public_record"),response.get("private_record"),response.get("diagnostics")):
        if isinstance(record,dict):
            for key in ("data_origin","task_purpose","test_only","scientific_review"):
                if key in record and record[key]!=origin[key]:raise ContractError("ADMITTED_RECORD_ORIGIN_PURPOSE_MISMATCH")
    run_id="module-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    background_pending=None
    if response["ok"] and request["operation"]=="train" and request["method_id"] in {"prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"}:
        from training_background_admission import capture
        metadata,background_pending=capture(packet,output,run_id,task_path=packet["task_path"])
        packet["model_meta"]["training_background"]=metadata
    result={"schema_version":"clinical-modular-result@1.1","core_version":"modular-development-1",
      "study_id":task["study_id"],"run_id":run_id,"method_id":request["method_id"],
      "method_version":definition["method_version"],"module_id":definition["module_id"],
      "execution_status":"complete" if response["ok"] else "blocked","reason_code":response["reason_code"],
      "scientific_review":"pending","export_status":"local_only","test_only":origin["test_only"],
      "data_origin":origin["data_origin"],"task_purpose":origin["task_purpose"],"origin_context":origin,
      "bindings":request["bindings"],**packet["model_meta"],"admitted_lock_sha256":packet["admitted_lock_sha256"],
      "provider":{"numerical_owner":definition["numerical_owner"],"registered_code_sha256":request["bindings"]["code_sha256"],
                  "module_manifest_sha256":info["admitted"]["selection"]["manifest_sha256"]},
      "module_record":response["public_record"],"diagnostics":response["diagnostics"],
      "provenance":{"data_origin":origin["data_origin"],"normalized_payload_sha256":canonical(request["payload"]),
        "integration_lock_sha256":lock_digest("module-lock.json"),"host_isolation_evidence":"not_established","clinical_applicability":"not_validated"},
      "artifacts":[],"limitations":["Scientific review is pending; engineering execution is not clinical approval.",
        "Normalized payload bytes are bound; original source identity, deidentification and upstream joins are not authenticated.",
        "This invocation captures local process streams; global host/network isolation is not established."],
      "completed_parts":["V1_task_schema","project_origin_admission","trusted_byte_bindings",packet["response_check"]]}
    context_path=private/"projection-context.json"
    dump(context_path,{"result_id":run_id,"binding":request["bindings"],"task":task,"origin_context":origin})
    if response["ok"]:
        projection=private/"provider-projection"
        try:
            # The domain projection receives the actual origin before drawing;
            # the outer metadata layer cannot repair a false Synthetic title.
            if request["method_id"] in {"explanation.binary.random_forest.tree_shap","explanation.binary.hist_gradient_boosting.tree_shap"}:
                projection_api=load_python(info,info["manifest"]["projection_entrypoint"])
                projection_api.project(response,str(projection),origin_context=origin)
            elif info["manifest"]["module_id"] in {"latent_longitudinal","mediation_matching","cox_evaluation_explanation"}:
                packet["api"].project(response,str(projection),context,request=request)
            else:
                r_call("project",info,private/"module-request.json",private/"module-response.json",projection,context_path,private/"module-projection.log")
            result["artifacts"]=artifacts(output,request,run_id,definition,origin["data_origin"],projection,origin)
            result["completed_parts"].append("source_aware_aggregate_projection")
        except Exception:
            (private/"projection-error.log").write_text(traceback.format_exc(),encoding="utf-8")
            result.update(execution_status="partial",reason_code="ADMITTED_MODULE_PROJECTION_FAILED")
    context.require_request(request["method_id"],request["operation"],request["payload"])
    _check(_validator(admitted_result_schema(packet)),result,"ADMITTED_MODULE_RESULT_INVALID")
    dump(output/"result.json",result)
    if background_pending is not None and result["execution_status"]=="complete":
        from training_background_admission import publish
        publish(background_pending,output/"result.json",project=task["project_root"])
    dump(output/"artifact-manifest.json",{"schema_version":"clinical-module-artifacts@1.1","run_id":run_id,
      "data_origin":origin["data_origin"],"task_purpose":origin["task_purpose"],"scientific_review":"pending",
      "test_only":origin["test_only"],"artifacts":result["artifacts"],"local_only":True})
    return result
def execute(task_path,output):
    if read_json(task_path).get("schema_version")=="clinical-module-task@1.1":
        from admitted_modules import execute_private
        return finalize_admitted_module(execute_private(task_path,output),output)
    output=Path(output).resolve();private=output/"private"
    task,request,registry,info,definition,model_meta=prepare(task_path,output)
    run_id="module-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    request_path=private/"module-request.json";response_path=private/"module-response.json";context_path=private/"projection-context.json"
    dump(request_path,request)
    context={"result_id":run_id,"binding":request["bindings"],"task":task}
    dump(context_path,context)
    if info["manifest"]["language"]=="R":
        r_call("analyze",info,request_path,response_path,output,context_path,private/"module-engine.log")
        response=read_json(response_path);api=None
    else:
        api=load_python(info);response=getattr(api,info["manifest"]["entrypoint"]["function"])(request);dump(response_path,response)
    registry.validate_response(request,response)
    result={"schema_version":"clinical-modular-result@1.0","core_version":"modular-development-1","study_id":task["study_id"],"run_id":run_id,
      "method_id":request["method_id"],"method_version":definition["method_version"],"module_id":definition["module_id"],
      "execution_status":"complete" if response["ok"] else "blocked","reason_code":response["reason_code"],"scientific_review":"pending","export_status":"local_only","test_only":True,
      "bindings":request["bindings"],**model_meta,
      "provider":{"numerical_owner":definition["numerical_owner"],"registered_code_sha256":request["bindings"]["code_sha256"],"module_manifest_sha256":info["entry"]["manifest_sha256"]},
      "module_record":response["public_record"],"diagnostics":response["diagnostics"],
      "provenance":{"data_origin":task["data_origin"],"normalized_payload_sha256":canonical(request["payload"]),"integration_lock_sha256":lock_digest("module-lock.json"),
                    "host_isolation_evidence":"not_established","clinical_applicability":"not_validated"},
      "artifacts":[],"limitations":["Synthetic engineering execution only; scientific review pending.","Normalized inline payload is bound; no real-database adapter or clinical-source validation is asserted."],
      "completed_parts":["task_schema","trusted_byte_bindings","registered_payload_schema","registered_response_schema"]}
    if response["ok"]:
        projection=private/"provider-projection"
        try:
            target=info["manifest"]["projection_entrypoint"]
            if target is None:raise ContractError("MODULE_PROJECTION_UNAVAILABLE")
            if Path(target["path"]).suffix.lower()==".r":
                r_call("project",info,request_path,response_path,projection,context_path,private/"module-projection.log")
            else:
                projection_api=api if target["path"]==info["manifest"]["entrypoint"]["path"] else load_python(info,target)
                args=[response,str(projection)]
                if info["manifest"]["module_id"]=="cox_evaluation_explanation":args.append({"result_id":run_id,"binding":request["bindings"]})
                projected=getattr(projection_api,target["function"])(*args)
                dump(private/"projection-return.json",projected)
            result["artifacts"]=artifacts(output,request,run_id,definition,task["data_origin"])
            result["completed_parts"].append("aggregate_tables_figures_report")
        except Exception:
            (private/"projection-error.log").write_text(traceback.format_exc(),encoding="utf-8")
            result.update(execution_status="partial",reason_code="MODULE_PROJECTION_FAILED")
    pending_background=None
    if response["ok"] and request["operation"]=="train" and request["method_id"] in ("prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"):
        from training_background import capture
        try:
            metadata,pending_background=capture(request_path,response_path,task_path,output,run_id)
            result["training_background"]=metadata
            result["completed_parts"].append("trusted_private_training_background")
        except Exception:
            (private/"background-error.log").write_text(traceback.format_exc(),encoding="utf-8")
            result.update(execution_status="partial",reason_code="MODULE_TRAINING_BACKGROUND_FAILED")
    # Recheck the actual source/schema lock after execution, before accepting it.
    from module_task import load_registry
    load_registry(request["method_id"])
    _check(_validator(result_schema(registry,definition)),result,"MODULE_RESULT_INVALID")
    dump(output/"result.json",result)
    dump(output/"artifact-manifest.json",{"schema_version":"clinical-module-artifacts@1.0","run_id":run_id,"artifacts":result["artifacts"],"local_only":True})
    if pending_background is not None and result["execution_status"]=="complete":
        from training_background import publish
        publish(pending_background,output/"result.json")
    return result
def main():
    if len(sys.argv)!=3:raise SystemExit("MODULE_WORKER_ARGUMENTS_REQUIRED")
    output=Path(sys.argv[2]).resolve()
    metadata=read_json(sys.argv[1]);admitted=metadata.get("schema_version")=="clinical-module-task@1.1"
    boundary=Path(metadata["project_root"]).resolve() if admitted else CORE
    if not output.is_relative_to(boundary) or not (output/"private").is_dir():raise SystemExit("MODULE_WORKER_OUTPUT_INVALID")
    try:result=execute(sys.argv[1],output)
    except Exception as error:
        (output/"private/integration-error.log").write_text(traceback.format_exc(),encoding="utf-8")
        code=error.code if isinstance(error,ContractError) else "MODULE_INTEGRATION_EXECUTION_FAILED"
        result={"schema_version":"clinical-module-rejection@1.0","execution_status":"blocked","reason_code":code,"scientific_review":"pending","test_only":True,"export_status":"local_only"}
        if admitted:
            purpose=metadata.get("task_purpose")
            result.update(schema_version="clinical-module-rejection@1.1",data_origin=metadata.get("data_origin"),
                task_purpose=purpose,test_only=purpose=="engineering_test" if purpose in {"engineering_test","research_analysis"} else None,
                admission_completed=False)
        dump(output/"result.json",result)
    print(json.dumps({"execution_status":result["execution_status"],"reason_code":result["reason_code"]}))
if __name__=="__main__":main()
