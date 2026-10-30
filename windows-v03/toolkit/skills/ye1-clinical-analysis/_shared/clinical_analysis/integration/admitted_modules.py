"""Bound V1.1 module transport; root-owned integration of reviewed adapters.

Only ordinary nonlinear RF/HGB operations are enabled here. Root publishes the
V1.1 schemas/lock and owns final result/projection. There is no CLI, R invocation,
synthetic relabel, source-file reconstruction, installation or external sending.
"""
from pathlib import Path
import copy
import json
import re

import module_task as legacy
from module_contract import read_json, bounded_file, _validator, _check, _fail
from origin_context import AdmittedOriginContext, _contracts

ROOT, CORE = legacy.ROOT, legacy.CORE
TASK_VERSION = "clinical-module-task@1.1"
LOCK_VERSION = "clinical-admitted-module-lock@1.0"
METHODS = frozenset({"prediction.binary.random_forest", "prediction.binary.hist_gradient_boosting"})
SHAP_METHODS = frozenset({"explanation.binary.random_forest.tree_shap", "explanation.binary.hist_gradient_boosting.tree_shap"})
OPERATIONS = frozenset({"train", "evaluate", "infer", "explain"})
MODULE_METHODS = {
    "nonlinear_prediction": METHODS | SHAP_METHODS,
    "tree_shap": SHAP_METHODS,
    "cox_evaluation_explanation": frozenset({"evaluation.survival.cox.penalized.ipcw", "interpretation.survival.cox.penalized.interventional"}),
    "latent_longitudinal": frozenset({"exploration.cluster.kmeans","exploration.cluster.gmm","longitudinal.growth.gaussian","latent.profile.gaussian","latent.trajectory.gaussian"}),
    "mediation_matching": frozenset({"mediation.linear.binary_exposure","causal.psm.att.binary","causal.psm.matched.survival"}),
}
SCHEMA_PATH = "contracts/module-task-origin.schema.json"
LOCK_PATH = "admitted-module-lock.json"
MIN_INTEGRATION_FILES = frozenset({
    "admitted_modules.py", "origin_context.py", "module_task.py", "module_worker.py",
    "contracts/module-request.schema.json", "contracts/module-response.schema.json", SCHEMA_PATH,
    "core/python/clinical_methods/study_input.py", "core/python/clinical_methods/contracts.py",
    "core/python/clinical_methods/resource_budget.py", "core/config/resource-budget-profiles.json",
    "core/src/clinanalysis/R/clinical_resource_budget.R",
})
MIN_MODULE_FILES = frozenset({"real_admission/adapter.py", "real_admission/manifest.json",
                              "real_admission/frozen-model.schema.json", "real_admission/failure-diagnostics.schema.json"})
BLOCKED_DIAGNOSTICS_SCHEMA = read_json(
    ROOT.parent / "modules/nonlinear_prediction/real_admission/failure-diagnostics.schema.json")


def require(ok, code):
    if not ok:
        _fail(code)


def make_task_schema(base, study_schema):
    """Root publication helper; copies the current shared auth/source definitions."""
    result = copy.deepcopy(base)
    props = result["properties"]
    props["schema_version"] = {"const": TASK_VERSION}
    props["data_origin"] = {"enum": ["real", "synthetic"]}
    props["task_purpose"] = {"enum": ["engineering_test", "research_analysis"]}
    props["project_root"] = {"type": "string", "minLength": 1}
    for key in ("authorization", "sources"):
        props[key] = copy.deepcopy(study_schema["properties"][key])
    props["sources"].update(minItems=1, maxItems=1)
    props["execution"] = legacy.obj({
        "output_dir": {"type": "string", "minLength": 1}, "mode": {"const": "local"},
        "privacy_profile": {"const": "captured_local_process"},
        "authorization_ref": {"anyOf": [copy.deepcopy(legacy.HASH), {"type": "null"}]},
        "export_policy": {"const": "local_only"},
    })
    for key in ("max_rows", "max_bytes", "max_decoded_bytes", "resource_budget"):
        props["execution"]["properties"][key] = copy.deepcopy(study_schema["properties"]["execution"]["properties"][key])
    result["required"] = list(dict.fromkeys(result["required"] +
                              ["task_purpose", "project_root", "authorization", "sources"]))
    return result


def _hash_map(root, values, required, code):
    require(isinstance(values, dict) and required <= set(values), code)
    for relative, expected in values.items():
        require(isinstance(expected, str) and re.fullmatch("[0-9a-f]{64}", expected), code)
        require(legacy.sha(bounded_file(root, relative)) == expected, code)


def load_selection(info, method):
    """Bind the separate admitted adapter to the frozen original registration."""
    module_id=info["manifest"]["module_id"]
    require(module_id in MODULE_METHODS and method in MODULE_METHODS[module_id],
            "ADMITTED_METHOD_NOT_REGISTERED")
    from runtime_registry import read_lock
    lock = read_lock(LOCK_PATH)
    require(set(lock) == {"schema_version", "integration_files_sha256", "modules"} and
            lock["schema_version"] == LOCK_VERSION, "ADMITTED_LOCK_INVALID")
    _hash_map(ROOT, lock["integration_files_sha256"], MIN_INTEGRATION_FILES, "ADMITTED_INTEGRATION_CODE_DRIFT")
    registration = info["entry"].get("registration_id", module_id)
    require(isinstance(lock["modules"], dict) and set(lock["modules"]) <= set(MODULE_METHODS) and registration in lock["modules"],
            "ADMITTED_LOCK_MODULES_UNSUPPORTED")
    selected = lock["modules"][registration]
    require(set(selected) == {"module_id", "manifest_path", "manifest_sha256", "entrypoint",
                             "files_sha256", "legacy_registration_sha256", "methods"}, "ADMITTED_DESCRIPTOR_INVALID")
    require(selected["module_id"] == module_id and
            selected["entrypoint"] == {"path": "real_admission/adapter.py", "function": "analyze"} and
            selected["manifest_path"] == "real_admission/manifest.json", "ADMITTED_DESCRIPTOR_INVALID")
    require(selected["legacy_registration_sha256"] == legacy.canonical(info["entry"]),
            "ADMITTED_LEGACY_REGISTRATION_DRIFT")
    minimum=MIN_MODULE_FILES if module_id=="nonlinear_prediction" else {"real_admission/adapter.py","real_admission/manifest.json","real_admission/root-registration-fragment.json"}
    _hash_map(info["root"], selected["files_sha256"], minimum, "ADMITTED_MODULE_SOURCE_OR_SCHEMA_DRIFT")
    manifest_path = bounded_file(info["root"], selected["manifest_path"])
    require(legacy.sha(manifest_path) == selected["manifest_sha256"], "ADMITTED_MANIFEST_DRIFT")
    require(method in selected["methods"] and set(selected["methods"]) <= MODULE_METHODS[module_id],"ADMITTED_MANIFEST_SCOPE_MISMATCH")
    for definition in selected["methods"].values():
        require(set(definition)=={"operations","schemas"} and bool(definition["operations"]),"ADMITTED_DESCRIPTOR_INVALID")
        require(set(definition["schemas"]) <= {"payload","public_record","private_record","diagnostics","request","response"},"ADMITTED_DESCRIPTOR_INVALID")
        require(all(path in selected["files_sha256"] for path in definition["schemas"].values()),"ADMITTED_SCHEMA_BINDING_MISSING")
    from runtime_registry import lock_digest
    return copy.deepcopy(selected), lock_digest(LOCK_PATH)


def _apply_schemas(registry, definition, info, selected, method):
    """Only V1 changes its validators; the legacy registry remains unmodified on disk."""
    for name,path in selected["methods"][method]["schemas"].items():
        validator=_validator(read_json(bounded_file(info["root"],path)),owned=name not in {"request","response"})
        if name in {"request","response"}:setattr(registry,name+"_validator",validator)
        else:definition["validators"][name]=validator
    definition["operations"]=frozenset(selected["methods"][method]["operations"])


def _model_binding(payload,module_id,project):
    if module_id in {"nonlinear_prediction","cox_evaluation_explanation"}:return legacy.model_binding(payload,module_id)
    reference=payload.get("model_ref")
    if reference is None:return None,None,"no_frozen_model"
    path=Path(reference.get("path",reference.get("local_ref",""))).resolve()
    require(path.is_relative_to(project) and path.is_file() and path.stat().st_size<=8*1024*1024,"MODULE_MODEL_OUTSIDE_PROJECT")
    digest=legacy.sha(path)
    require(digest==reference.get("sha256",reference.get("content_hash")),"MODULE_MODEL_CHECKSUM_MISMATCH")
    return digest,digest,"original_project_model_file_bytes"


def prepare(taskpath, output):
    """The proposed V1.1 branch of legacy.prepare; return its same six-tuple."""
    task = read_json(taskpath)
    common = _contracts(CORE)
    published = read_json(ROOT / SCHEMA_PATH)
    require(published == make_task_schema(legacy.TASK_SCHEMA, common.STUDY_SCHEMA), "ADMITTED_TASK_SCHEMA_DRIFT")
    _check(_validator(published), task, "ADMITTED_MODULE_TASK_INVALID")
    require(task["plan_sha256"] == legacy.plan_hash(task), "MODULE_TASK_PLAN_MISMATCH")
    output = Path(output).resolve()
    require(output.is_relative_to(Path(task["project_root"]).resolve()) and output == Path(task["execution"]["output_dir"]).resolve(),
            "MODULE_OUTPUT_BINDING_MISMATCH")
    registry, meta, _ = legacy.load_registry(task["method_id"])
    require(task["method_id"] in meta, "MODULE_METHOD_NOT_REGISTERED")
    info = copy.deepcopy(meta[task["method_id"]])
    selection, lock_hash = load_selection(info, task["method_id"])
    definition=registry.methods[task["method_id"]]
    _apply_schemas(registry,definition,info,selection,task["method_id"])
    require(task["operation"] in definition["operations"], "ADMITTED_OPERATION_UNSUPPORTED")
    model_hash, model_bytes, model_semantics = _model_binding(task["payload"],info["manifest"]["module_id"],Path(task["project_root"]).resolve())
    background_guard = None
    if task["method_id"] in SHAP_METHODS:
        from training_background_admission import guard
        background_guard = guard(task["project_root"],task["payload"],model_hash,
                                 {"data_origin":task["data_origin"],"task_purpose":task["task_purpose"],
                                  "test_only":task["task_purpose"]=="engineering_test","scientific_review":"pending"})
    context = AdmittedOriginContext(task, CORE, allowed_methods=MODULE_METHODS[info["manifest"]["module_id"]],
                                   training_background_guard=background_guard)
    _check(definition["validators"]["payload"],task["payload"],"ADMITTED_MODULE_PAYLOAD_INVALID")
    try:
        limits = context.resource_limits()
        candidate_rows = task["payload"].get("rows", task["payload"].get("data"))
        if isinstance(candidate_rows, dict): candidate_rows = candidate_rows.get("rows")
        if isinstance(candidate_rows, list) and candidate_rows:
            common._resource_budget.check_rows(len(candidate_rows), limits)
        payload_bytes = len(json.dumps(task["payload"], ensure_ascii=False, separators=(",",":"), allow_nan=False).encode("utf-8"))
        require(payload_bytes <= limits["max_input_bytes"], "RESOURCE_INPUT_BYTE_BUDGET_EXCEEDED")
    except common._resource_budget.BudgetError as exc:
        require(False, exc.code)

    for key in ("work_dir","workdir"):
        if key in task["payload"]:
            work=Path(task["payload"][key]).resolve()
            require(work.is_relative_to(output/"private") and not work.exists(),"MODULE_PRIVATE_WORK_DIRECTORY_INVALID")
    bindings = {"input_sha256": legacy.sha(taskpath), "plan_sha256": task["plan_sha256"],
                "code_sha256": legacy.canonical(selection), "runtime_sha256": legacy.sha(CORE / "runtime-lock.json"),
                "model_sha256": model_hash}
    request_api=registry.request_validator.schema["properties"]["api_version"]["const"]
    request = {"api_version": request_api, "method_id": task["method_id"],
               "operation": task["operation"], "payload": task["payload"], "bindings": bindings}
    # Old validators check registered payload, method/operation and all binding
    # fields; the new transport is used only after the root context re-admits.
    definition = registry.validate_request(request, bindings)
    context.require_request(request["method_id"], request["operation"], request["payload"])
    require(legacy.sha(taskpath) == bindings["input_sha256"], "MODULE_TASK_CHANGED_DURING_PREPARE")
    info["admitted"] = {"selection": selection, "lock_sha256": lock_hash, "context": context}
    model_meta = {"model_bytes_sha256": model_bytes, "model_binding_semantics": model_semantics,
                  "training_background": None}
    return task, request, registry, info, definition, model_meta


def validate_response(registry, request, response):
    """Success retains all owner schemas; blocked diagnostics have one closed form."""
    if isinstance(response, dict) and response.get("ok") is True:
        registry.validate_response(request, response)
        return "registered_success_schemas"
    if request["method_id"] not in METHODS | SHAP_METHODS:
        registry.validate_response(request,response)
        return "registered_failure_schemas"
    _check(registry.response_validator, response, "MODULE_RESPONSE_INVALID")
    require(response["ok"] is False and response["public_record"] is None and response["private_record"] is None,
            "ADMITTED_BLOCKED_RESPONSE_INVALID")
    _check(_validator(BLOCKED_DIAGNOSTICS_SCHEMA), response["diagnostics"], "ADMITTED_BLOCKED_DIAGNOSTICS_INVALID")
    if response["diagnostics"]["counts_status"] == "computed":
        counts = response["diagnostics"]["counts"]
        require(counts["source_rows"] == counts["total_n"] ==
                counts["total_events"] + counts["total_nonevents"] + counts["missing_outcome_n"],
                "ADMITTED_FAILURE_DENOMINATORS_INCONSISTENT")
    return "closed_admission_failure_schema"


def execute_private(taskpath, output):
    """PRIVATE packet only. Root finalizer must validate/publish result + projection.

    Never fall through to old synthetic result/projection/background functions.
    This function writes only local private request/response. It emits no stdout.
    """
    import module_worker
    task, request, registry, info, definition, model_meta = prepare(taskpath, output)
    private = Path(output).resolve() / "private"
    require(private.is_dir(), "MODULE_WORKER_OUTPUT_INVALID")
    context = info["admitted"]["context"]
    expected = copy.deepcopy(request)
    api = module_worker.load_python(info, info["admitted"]["selection"]["entrypoint"])
    with (private / "module-request.json").open("x", encoding="utf-8") as stream:
        json.dump(request, stream, ensure_ascii=False, allow_nan=False, indent=2)
    response = api.analyze(request, context)
    # Retain the untrusted owner response privately even when its schema fails;
    # only the validated root projection can become a public result.
    with (private / "module-response.json").open("x", encoding="utf-8") as stream:
        json.dump(response, stream, ensure_ascii=False, allow_nan=False, indent=2)
    checked = validate_response(registry, request, response)
    require(request == expected, "MODULE_REQUEST_MUTATED_BY_OWNER")
    context.require_request(request["method_id"], request["operation"], request["payload"])
    legacy.load_registry(request["method_id"])
    current, lock_hash = load_selection(info, request["method_id"])
    require(current == info["admitted"]["selection"] and lock_hash == info["admitted"]["lock_sha256"],
            "ADMITTED_LOCK_CHANGED_DURING_EXECUTION")
    require(legacy.sha(taskpath) == request["bindings"]["input_sha256"], "MODULE_TASK_CHANGED_DURING_EXECUTION")
    require(legacy.sha(CORE/"runtime-lock.json") == request["bindings"]["runtime_sha256"], "MODULE_RUNTIME_CHANGED_DURING_EXECUTION")
    return {"task": task, "request": request, "response": response, "registry": registry,
            "task_path": str(taskpath),
            "info": info, "definition": definition, "model_meta": model_meta, "api": api,
            "context": context, "origin_context": context.public_metadata(), "response_check": checked,
            "admitted_lock_sha256": lock_hash, "projection_status": "pending_root_source_aware_projection"}
