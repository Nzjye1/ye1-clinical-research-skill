"""Shared bound task/result schemas and trusted module binding construction.

Private normalized synthetic payloads only at this development checkpoint. This
layer does not load a database, fit an estimator or grant external-data access.
"""
from pathlib import Path
import copy,hashlib,json,sys
from module_contract import ModuleRegistry,ContractError,read_json,bounded_file,_validator,_check,_fail
ROOT=Path(__file__).resolve().parent
CORE=ROOT/"core"
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()
def obj(properties):return {"type":"object","additionalProperties":False,"required":list(properties),"properties":properties}
def arr(items):return {"type":"array","items":items}
HASH={"type":"string","pattern":"^[0-9a-f]{64}$"}
NULL={"type":"null"}
TEXT={"type":"string"}
TASK_SCHEMA=obj({"schema_version":{"const":"clinical-module-task@1.0"},"study_id":{"type":"string","pattern":"^[A-Za-z][A-Za-z0-9_.-]{0,119}$"},
    "method_id":{"type":"string","pattern":"^[a-z][a-z0-9_.]{0,119}$"},"operation":{"type":"string","pattern":"^[a-z][a-z0-9_]{0,39}$"},
    "payload":{"type":"object"},"data_origin":{"const":"synthetic_inline_normalized"},"plan_sha256":HASH,
    "execution":obj({"output_dir":TEXT,"mode":{"const":"synthetic"},"export_policy":{"const":"local_only"}})})
def plan_hash(task):
    v=copy.deepcopy(task);v.pop("plan_sha256",None);v["execution"].pop("output_dir",None)
    return canonical(v)
def load_registry(method_id=None):
    from runtime_registry import read_lock
    lock=read_lock("module-lock.json");registry=ModuleRegistry();meta={}
    for rel,digest in lock["integration_files_sha256"].items():
        p=(ROOT/rel).resolve()
        if not p.is_relative_to(ROOT) or not p.is_file() or sha(p)!=digest:_fail("INTEGRATION_CODE_DRIFT")
    selected=[entry for entry in lock["modules"] if method_id is None or method_id in entry["methods"]]
    dependencies={key:digest for entry in selected for key,digest in entry.get("dependencies_sha256",{}).items()}
    for key,digest in dependencies.items():
        dependency=next((entry for entry in lock["modules"] if entry.get("registration_id",entry["directory"])==key),None)
        if dependency is None or canonical(dependency)!=digest:_fail("MODULE_DEPENDENCY_BINDING_DRIFT")
        if dependency not in selected:selected.append(dependency)
    for entry in selected:
        # During parallel module development an unrelated owner may be editing
        # its own tree. Only the requested method's registered snapshot can run;
        # final integration acceptance explicitly checks every module together.
        module=ROOT.parent/"modules"/entry["directory"]
        manifest_path=entry.get("manifest_path","integration-request.json")
        if sha(bounded_file(module,manifest_path))!=entry["manifest_sha256"]:_fail("MODULE_MANIFEST_DRIFT")
        receipt=registry.register_manifest(module,manifest_path)
        if receipt["files_sha256"]!=entry["files_sha256"]:_fail("MODULE_SOURCE_OR_SCHEMA_DRIFT")
        external_runtime=None
        if entry.get("registration_id")=="tree_shap":
            local=read_json(ROOT/"module-runtime.json")
            external_runtime=Path(local["shap_library"]).resolve()
        for rel,digest in entry.get("supplementary_files_sha256",{}).items():
            if external_runtime is not None and rel.startswith("tree_shap/_vendor/"):
                p=external_runtime/rel[len("tree_shap/_vendor/"):]
                if not p.resolve().is_relative_to(external_runtime) or not p.is_file() or sha(p)!=digest:_fail("MODULE_SUPPLEMENTARY_DEPENDENCY_DRIFT")
            elif sha(bounded_file(module,rel))!=digest:_fail("MODULE_SUPPLEMENTARY_DEPENDENCY_DRIFT")
        if "runtime_tree" in entry:
            tree=external_runtime if external_runtime is not None else (module/entry["runtime_tree"]).resolve()
            if external_runtime is None and not tree.is_relative_to(module.resolve()):_fail("MODULE_PATH_OUTSIDE_OWNER")
            actual={p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc",".pyo")}
            prefix=entry["runtime_tree"]+"/"
            expected={rel[len(prefix):] for rel in entry["supplementary_files_sha256"] if rel.startswith(prefix)}
            if actual!=expected:_fail("MODULE_RUNTIME_INVENTORY_DRIFT")
        manifest=read_json(module/manifest_path)
        for method in entry["methods"]:meta[method]={"root":module,"manifest":manifest,"entry":entry}
    return registry,meta,lock
def model_binding(payload,module_id):
    """Return model identity used by its provider plus original JSON byte hash.

    Some providers bind canonical bundle.sha256, others the file byte hash. The
    two are explicitly distinguished; arbitrary caller hash claims are not used.
    """
    if module_id=="cox_evaluation_explanation":
        raw=payload.get("model_json")
        if not isinstance(raw,str):_fail("MODULE_MODEL_FORMAT_INVALID")
        from module_contract import _pairs,_finite
        try:bundle=json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda x:_fail("MODULE_NONFINITE_JSON"))
        except (ValueError,TypeError):_fail("MODULE_MODEL_FORMAT_INVALID")
        if not isinstance(bundle,dict):_fail("MODULE_MODEL_FORMAT_INVALID")
        _finite(bundle)
        digest=hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return digest,digest,"original_model_utf8_bytes"
    if module_id=="nonlinear_prediction":
        raw=payload.get("frozen_model_json")
        if raw is None:return None,None,"no_frozen_model"
        if not isinstance(raw,str):_fail("MODULE_MODEL_FORMAT_INVALID")
        from module_contract import _pairs,_finite
        try:bundle=json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda x:_fail("MODULE_NONFINITE_JSON"))
        except (ValueError,TypeError):_fail("MODULE_MODEL_FORMAT_INVALID")
        if not isinstance(bundle,dict):_fail("MODULE_MODEL_FORMAT_INVALID")
        _finite(bundle)
        digest=bundle.get("sha256");body={k:v for k,v in bundle.items() if k!="sha256"}
        if digest!=canonical(body):_fail("MODULE_MODEL_CHECKSUM_MISMATCH")
        return digest,hashlib.sha256(raw.encode("utf-8")).hexdigest(),"canonical_bundle_checksum_and_original_utf8_bytes"
    reference=payload.get("model_ref")
    if reference is None:return None,None,"no_frozen_model"
    path=Path(reference.get("path",reference.get("local_ref",""))).resolve()
    if not path.is_relative_to(CORE) or not path.is_file() or path.stat().st_size>8*1024*1024:_fail("MODULE_MODEL_OUTSIDE_INTEGRATION_ROOT")
    digest=sha(path)
    if digest!=reference.get("sha256",reference.get("content_hash")):_fail("MODULE_MODEL_CHECKSUM_MISMATCH")
    return digest,digest,"original_model_file_bytes"
def prepare(taskpath,output):
    task=read_json(taskpath)
    if task.get("schema_version")=="clinical-module-task@1.1":
        from admitted_modules import prepare as prepare_admitted
        return prepare_admitted(taskpath,output)
    _check(_validator(TASK_SCHEMA),task,"MODULE_TASK_INVALID")
    if task["plan_sha256"]!=plan_hash(task):_fail("MODULE_TASK_PLAN_MISMATCH")
    output=Path(output).resolve()
    if not output.is_relative_to(CORE) or output!=Path(task["execution"]["output_dir"]).resolve():_fail("MODULE_OUTPUT_BINDING_MISMATCH")
    registry,meta,lock=load_registry(task["method_id"])
    if task["method_id"] not in meta:_fail("MODULE_METHOD_NOT_REGISTERED")
    info=meta[task["method_id"]];module_id=info["manifest"]["module_id"]
    model_hash,model_bytes_hash,model_semantics=model_binding(task["payload"],module_id)
    if "work_dir" in task["payload"]:
        work=Path(task["payload"]["work_dir"]).resolve()
        if not work.is_relative_to(output/"private") or work.exists():_fail("MODULE_PRIVATE_WORK_DIRECTORY_INVALID")
    bindings={"input_sha256":sha(taskpath),"plan_sha256":task["plan_sha256"],"code_sha256":canonical(info["entry"]),
              "runtime_sha256":sha(CORE/"runtime-lock.json"),"model_sha256":model_hash}
    request={"api_version":"clinical-module-request@1.0","method_id":task["method_id"],"operation":task["operation"],"payload":task["payload"],"bindings":bindings}
    definition=registry.validate_request(request,bindings)
    background=None
    if task["method_id"].startswith("explanation.binary.") and task["method_id"].endswith(".tree_shap"):
        from training_background import verify_registered_background
        background=verify_registered_background(task["payload"],model_hash)
    return task,request,registry,info,definition,{"model_bytes_sha256":model_bytes_hash,"model_binding_semantics":model_semantics,"training_background":background}
