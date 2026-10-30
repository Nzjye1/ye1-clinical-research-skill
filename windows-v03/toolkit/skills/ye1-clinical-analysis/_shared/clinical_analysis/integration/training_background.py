"""Common-owner training artifact lineage; no estimation or caller attestation.

The registry is local integrity evidence, not an access-control or host-authenticity
claim. Only this completion hook creates entries from a validated successful run.
Individual rows and partition identities are confined to private artifacts.
"""
from pathlib import Path
import hashlib,importlib,json,re,sys
from module_contract import read_json,_pairs,_finite,_fail,_validator,_check
from module_task import ROOT,CORE,sha,canonical,obj,HASH,NULL,TEXT

METHODS={"prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"}
REGISTRY=CORE/"private/module-background-registry"
POLICY="model_fit_uniform_without_replacement_n_min_100_seed_1729_v1"

def metadata_schema():
    return obj({"schema_version":{"const":"clinical-training-background-lineage@1.0"},
      "artifact_sha256":HASH,"artifact_file_sha256":HASH,"model_sha256":HASH,
      "training_run_id":TEXT,"training_input_sha256":HASH,"training_plan_sha256":HASH,
      "training_request_sha256":HASH,"training_response_sha256":HASH,
      "capture_code_sha256":HASH,"sampling_policy":{"const":POLICY},
      "sampling_n":{"type":"integer","minimum":10,"maximum":100},"sampling_seed":{"const":1729},
      "partition":{"const":"model_fit"},"classification":{"const":"local_private"},
      "authenticity":{"const":"local_saved_run_integrity_not_host_access_control"}})

def _write(path,value):
    with Path(path).open("x",encoding="utf-8") as handle:
        json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write("\n")

def _file(path):
    p=Path(path).resolve()
    if not p.is_relative_to(CORE) or not p.is_file():_fail("MODULE_BACKGROUND_SOURCE_PATH_INVALID")
    return {"path":p.relative_to(CORE).as_posix(),"sha256":sha(p)}

def _read_file(ref):
    if not isinstance(ref,dict) or set(ref)!={"path","sha256"}:_fail("MODULE_BACKGROUND_REGISTRY_INVALID")
    rel=Path(ref["path"])
    p=(CORE/rel).resolve()
    if rel.is_absolute() or ".." in rel.parts or not p.is_relative_to(CORE) or not p.is_file():_fail("MODULE_BACKGROUND_SOURCE_PATH_INVALID")
    if sha(p)!=ref["sha256"]:_fail("MODULE_BACKGROUND_SOURCE_DRIFT")
    return p,read_json(p)

def capture(request_path,response_path,task_path,output,run_id):
    """Read the actual saved artifacts, then call the sole background provider."""
    from module_task import load_registry
    q=read_json(request_path);r=read_json(response_path)
    if q["operation"]!="train" or q["method_id"] not in METHODS or not r["ok"]:_fail("MODULE_BACKGROUND_REQUIRES_TRAINING")
    method=q["method_id"].replace("prediction.","explanation.",1)+".tree_shap"
    registry,meta,_=load_registry(method)
    # The extension's dependency lock also verifies the handed prediction facade.
    registry.validate_request(q,q["bindings"]);registry.validate_response(q,r)
    info=meta[method]
    sys.path.insert(0,str(info["root"]))
    provider=importlib.import_module("tree_shap.background")
    if not Path(provider.__file__).resolve().is_relative_to(info["root"]):_fail("MODULE_BACKGROUND_IMPORT_COLLISION")
    size=min(100,r["diagnostics"]["counts"]["model_fit_n"])
    background=provider.capture_training_background(q,r,trusted_run_hashes={"request_sha256":canonical(q),"response_sha256":canonical(r)},size=size,seed=1729)
    path=Path(output)/"private/training-background.json";_write(path,background)
    metadata={"schema_version":"clinical-training-background-lineage@1.0","artifact_sha256":background["sha256"],
      "artifact_file_sha256":sha(path),"model_sha256":background["model_sha256"],"training_run_id":run_id,
      "training_input_sha256":q["bindings"]["input_sha256"],"training_plan_sha256":q["bindings"]["plan_sha256"],
      "training_request_sha256":canonical(q),"training_response_sha256":canonical(r),
      "capture_code_sha256":canonical(info["entry"]),"sampling_policy":POLICY,"sampling_n":size,"sampling_seed":1729,
      "partition":"model_fit","classification":"local_private","authenticity":"local_saved_run_integrity_not_host_access_control"}
    _check(_validator(metadata_schema()),metadata,"MODULE_BACKGROUND_METADATA_INVALID")
    pending={"schema_version":"clinical-private-background-registration@1.0","metadata":metadata,
       "files":{"task":_file(task_path),"request":_file(request_path),"response":_file(response_path),"background":_file(path)}}
    return metadata,pending

def publish(pending,result_path):
    """Publish only after the complete common result is validated and saved."""
    result=read_json(result_path)
    if result.get("execution_status")!="complete" or result.get("training_background")!=pending["metadata"]:_fail("MODULE_BACKGROUND_PRODUCER_INCOMPLETE")
    record={**pending,"files":{**pending["files"],"result":_file(result_path)}}
    REGISTRY.mkdir(parents=True,exist_ok=True)
    _write(REGISTRY/(pending["metadata"]["artifact_sha256"]+".json"),record)

def verify_registered_background(payload,model_hash):
    digest=payload.get("background_sha256")
    if not isinstance(digest,str) or re.fullmatch("[0-9a-f]{64}",digest) is None:_fail("MODULE_BACKGROUND_HASH_INVALID")
    path=REGISTRY/(digest+".json")
    if not path.is_file():_fail("MODULE_BACKGROUND_NOT_REGISTERED")
    record=read_json(path)
    if set(record)!={"schema_version","metadata","files"} or record["schema_version"]!="clinical-private-background-registration@1.0":_fail("MODULE_BACKGROUND_REGISTRY_INVALID")
    metadata=record["metadata"];_check(_validator(metadata_schema()),metadata,"MODULE_BACKGROUND_METADATA_INVALID")
    if set(record["files"])!={"task","request","response","background","result"}:_fail("MODULE_BACKGROUND_REGISTRY_INVALID")
    values={name:_read_file(ref)[1] for name,ref in record["files"].items()}
    task,q,r,background,result=(values[name] for name in ("task","request","response","background","result"))
    from module_task import plan_hash
    if (q.get("operation")!="train" or q.get("method_id") not in METHODS or not r.get("ok") or
        result.get("execution_status")!="complete" or result.get("training_background")!=metadata or
        result.get("bindings")!=q.get("bindings") or result.get("run_id")!=metadata["training_run_id"] or
        task.get("operation")!="train" or task.get("method_id")!=q["method_id"] or task.get("payload")!=q["payload"] or
        task.get("plan_sha256")!=plan_hash(task) or result.get("method_id")!=q["method_id"]):
        _fail("MODULE_BACKGROUND_PRODUCER_INVALID")
    if (metadata["artifact_sha256"]!=digest or metadata["artifact_file_sha256"]!=record["files"]["background"]["sha256"] or
        metadata["training_input_sha256"]!=record["files"]["task"]["sha256"] or
        metadata["training_input_sha256"]!=q["bindings"]["input_sha256"] or
        metadata["training_plan_sha256"]!=task["plan_sha256"] or
        metadata["training_request_sha256"]!=canonical(q) or metadata["training_response_sha256"]!=canonical(r)):
        _fail("MODULE_BACKGROUND_PRODUCER_BINDING_MISMATCH")
    try:
        supplied=json.loads(payload["background_artifact_json"],object_pairs_hook=_pairs,parse_constant=lambda _: _fail("MODULE_NONFINITE_JSON"))
    except (TypeError,ValueError):_fail("MODULE_BACKGROUND_FORMAT_INVALID")
    _finite(supplied)
    if supplied!=background:_fail("MODULE_BACKGROUND_REGISTERED_CONTENT_MISMATCH")
    if metadata["model_sha256"]!=model_hash or background.get("model_sha256")!=model_hash:_fail("MODULE_BACKGROUND_MODEL_MISMATCH")
    if background.get("sha256")!=digest or canonical({k:v for k,v in background.items() if k!="sha256"})!=digest:_fail("MODULE_BACKGROUND_HASH_MISMATCH")
    return metadata
