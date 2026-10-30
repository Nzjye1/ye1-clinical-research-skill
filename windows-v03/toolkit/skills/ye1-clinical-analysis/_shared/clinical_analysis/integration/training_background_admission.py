"""Admitted project-local training background lineage; no fitting or grants.

Only the successful common-owner completion hook calls capture/publish. Local
saved-file integrity is not hostile-host authentication or OS access control.
The sole admitted prediction adapter replays partitions and predictions before
capturing background; callers cannot nominate background rows themselves.
"""
from pathlib import Path
import json,re
from module_contract import read_json,_pairs,_finite,_fail,_validator,_check
from module_task import sha,canonical,obj,HASH,TEXT
from training_background import metadata_schema,POLICY,METHODS

REGISTRY_VERSION="clinical-admitted-background-registration@1.0"

def need(ok,code):
    if not ok:_fail(code)

def origin(value):
    v={k:(value[k] if isinstance(value,dict) else getattr(value,k)) for k in
       ("data_origin","task_purpose","test_only","scientific_review")}
    need(v["data_origin"] in {"real","synthetic"} and
         v["task_purpose"] in {"engineering_test","research_analysis"} and
         type(v["test_only"]) is bool and v["test_only"]==(v["task_purpose"]=="engineering_test") and
         v["scientific_review"]=="pending" and
         (v["data_origin"]!="synthetic" or v["task_purpose"]=="engineering_test"),
         "ADMITTED_BACKGROUND_ORIGIN_INVALID")
    return v

def record_schema():
    ref=obj({"path":TEXT,"sha256":HASH})
    context=obj({"data_origin":{"enum":["real","synthetic"]},
      "task_purpose":{"enum":["engineering_test","research_analysis"]},
      "test_only":{"type":"boolean"},"scientific_review":{"const":"pending"}})
    return obj({"schema_version":{"const":REGISTRY_VERSION},"metadata":metadata_schema(),
                "origin_context":context,"files":obj({k:ref for k in
                ("task","request","response","background","result")})})

def registry(project):
    return Path(project).resolve()/".ye1-privacy/private/module-background-registry"

def _path(project,path):
    project=Path(project).resolve();p=Path(path).resolve()
    need(project.is_dir() and p.is_relative_to(project) and p.is_file(),
         "ADMITTED_BACKGROUND_SOURCE_PATH_INVALID")
    return p

def _file(project,path):
    p=_path(project,path)
    return {"path":p.relative_to(Path(project).resolve()).as_posix(),"sha256":sha(p)}

def _read(project,ref):
    need(isinstance(ref,dict) and set(ref)=={"path","sha256"},"ADMITTED_BACKGROUND_REFERENCE_INVALID")
    rel=Path(ref["path"])
    need(not rel.is_absolute() and ".." not in rel.parts,"ADMITTED_BACKGROUND_SOURCE_PATH_INVALID")
    p=_path(project,Path(project)/rel)
    need(sha(p)==ref["sha256"],"ADMITTED_BACKGROUND_SOURCE_DRIFT")
    return read_json(p)

def _write(path,value):
    with Path(path).open("x",encoding="utf8") as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write("\n")

def _producer(task,q,response,metadata,classification):
    from module_task import plan_hash
    need(task.get("schema_version")=="clinical-module-task@1.1" and
         task.get("method_id")==q.get("method_id") in METHODS and
         task.get("operation")==q.get("operation")=="train" and response.get("ok") is True and
         task.get("payload")==q.get("payload") and task.get("plan_sha256")==plan_hash(task),
         "ADMITTED_BACKGROUND_PRODUCER_INVALID")
    task_origin={"data_origin":task["data_origin"],"task_purpose":task["task_purpose"],
                 "test_only":task["task_purpose"]=="engineering_test","scientific_review":"pending"}
    need(origin(task_origin)==classification,"ADMITTED_BACKGROUND_ORIGIN_MISMATCH")
    need(metadata["training_plan_sha256"]==task["plan_sha256"]==q["bindings"]["plan_sha256"] and
         metadata["training_request_sha256"]==canonical(q) and
         metadata["training_response_sha256"]==canonical(response),"ADMITTED_BACKGROUND_PRODUCER_BINDING_MISMATCH")
    model=json.loads(response["private_record"]["frozen_model_json"],object_pairs_hook=_pairs)
    _finite(model)
    need(model.get("sha256")==metadata["model_sha256"] and
         origin(model["origin_context"])==classification,"ADMITTED_BACKGROUND_MODEL_ORIGIN_MISMATCH")

def capture(packet,output,run_id,*,task_path=None):
    """Called after saved successful train request/response, before result save."""
    output=Path(output).resolve();project=Path(packet["task"]["project_root"]).resolve()
    need(Path(packet["context"].project_root).resolve()==project,"ADMITTED_BACKGROUND_PROJECT_MISMATCH")
    need(output.is_relative_to(project),"ADMITTED_BACKGROUND_OUTPUT_OUTSIDE_PROJECT")
    qpath=output/"private/module-request.json";rpath=output/"private/module-response.json"
    tpath=Path(task_path or packet.get("task_path") or output/"private/task-snapshot.json")
    q=_read(project,_file(project,qpath));response=_read(project,_file(project,rpath));task=_read(project,_file(project,tpath))
    need(q==packet["request"] and response==packet["response"] and task==packet["task"] and
         sha(tpath)==q["bindings"]["input_sha256"],"ADMITTED_BACKGROUND_SAVED_RUN_MISMATCH")
    classification=origin(packet["context"])
    need(q.get("operation")=="train" and q.get("method_id") in METHODS and response.get("ok") is True,
         "ADMITTED_BACKGROUND_REQUIRES_SUCCESSFUL_TRAINING")
    size=min(100,response["diagnostics"]["counts"]["model_fit_n"])
    background=packet["api"].capture_training_background(q,response,packet["context"],
        trusted_run_hashes={"request_sha256":canonical(q),"response_sha256":canonical(response)},size=size,seed=1729)
    target=output/"private/training-background.json";_write(target,background)
    metadata={"schema_version":"clinical-training-background-lineage@1.0","artifact_sha256":background["sha256"],
      "artifact_file_sha256":sha(target),"model_sha256":background["model_sha256"],"training_run_id":run_id,
      "training_input_sha256":q["bindings"]["input_sha256"],"training_plan_sha256":q["bindings"]["plan_sha256"],
      "training_request_sha256":canonical(q),"training_response_sha256":canonical(response),
      "capture_code_sha256":canonical(packet["info"]["admitted"]["selection"]),"sampling_policy":POLICY,
      "sampling_n":size,"sampling_seed":1729,"partition":"model_fit","classification":"local_private",
      "authenticity":"local_saved_run_integrity_not_host_access_control"}
    _check(_validator(metadata_schema()),metadata,"ADMITTED_BACKGROUND_METADATA_INVALID")
    _producer(task,q,response,metadata,classification)
    pending={"schema_version":REGISTRY_VERSION,"metadata":metadata,"origin_context":classification,
             "files":{"task":_file(project,tpath),"request":_file(project,qpath),"response":_file(project,rpath),"background":_file(project,target)}}
    return metadata,pending

def publish(pending,result_path,*,project):
    """Register only a complete saved result that includes capture metadata."""
    result=read_json(_path(project,result_path));metadata=pending["metadata"]
    need(result.get("schema_version")=="clinical-modular-result@1.1" and
         result.get("execution_status")=="complete" and result.get("training_background")==metadata and
         result.get("run_id")==metadata["training_run_id"] and origin(result)==pending["origin_context"],
         "ADMITTED_BACKGROUND_PRODUCER_INCOMPLETE")
    record={**pending,"files":{**pending["files"],"result":_file(project,result_path)}}
    _check(_validator(record_schema()),record,"ADMITTED_BACKGROUND_REGISTRY_INVALID")
    dest=registry(project);dest.mkdir(parents=True,exist_ok=True)
    target=dest/(metadata["artifact_sha256"]+".json")
    if target.exists():
        need(read_json(target)==record,"ADMITTED_BACKGROUND_REGISTRATION_CONFLICT")
        return
    _write(target,record)

def verify_registered_background(project,payload,model_hash,classification):
    digest=payload.get("background_sha256")
    need(isinstance(digest,str) and re.fullmatch('[0-9a-f]{64}',digest),"ADMITTED_BACKGROUND_HASH_INVALID")
    path=registry(project)/(digest+".json")
    need(path.is_file(),"ADMITTED_BACKGROUND_NOT_REGISTERED")
    record=read_json(path);_check(_validator(record_schema()),record,"ADMITTED_BACKGROUND_REGISTRY_INVALID")
    classification=origin(classification)
    need(record["origin_context"]==classification,"ADMITTED_BACKGROUND_ORIGIN_MISMATCH")
    values={k:_read(project,v) for k,v in record["files"].items()}
    task,q,response,background,result=(values[k] for k in ("task","request","response","background","result"));m=record["metadata"]
    need(Path(task["project_root"]).resolve()==Path(project).resolve(),"ADMITTED_BACKGROUND_PROJECT_MISMATCH")
    _producer(task,q,response,m,classification)
    need(result.get("execution_status")=="complete" and result.get("training_background")==m and
         result.get("run_id")==m["training_run_id"] and result.get("bindings")==q["bindings"] and
         origin(result)==classification,"ADMITTED_BACKGROUND_PRODUCER_INCOMPLETE")
    need(m["artifact_sha256"]==digest and m["artifact_file_sha256"]==record["files"]["background"]["sha256"] and
         m["training_input_sha256"]==record["files"]["task"]["sha256"]==q["bindings"]["input_sha256"] and
         m["model_sha256"]==model_hash==background.get("model_sha256"),"ADMITTED_BACKGROUND_MODEL_OR_BINDING_MISMATCH")
    try:supplied=json.loads(payload["background_artifact_json"],object_pairs_hook=_pairs)
    except (ValueError,TypeError,KeyError):_fail("ADMITTED_BACKGROUND_FORMAT_INVALID")
    _finite(supplied)
    need(supplied==background and background.get("sha256")==digest and
         canonical({k:v for k,v in background.items() if k!='sha256'})==digest,
         "ADMITTED_BACKGROUND_REGISTERED_CONTENT_MISMATCH")
    return m

def guard(project,payload,model_hash,classification):
    """Inject into root context; the adapter still validates actual artifact."""
    def check(artifact):
        need(canonical(artifact)==canonical(json.loads(payload["background_artifact_json"],object_pairs_hook=_pairs)),
             "ADMITTED_BACKGROUND_CALLBACK_CONTENT_MISMATCH")
        return verify_registered_background(project,payload,model_hash,classification)
    return check
