"""Agent-facing discovery and one-task routing. Numerical owners stay in the backend."""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_JSON_BYTES = 2 * 1024 * 1024


class CallError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def fail(code):
    raise CallError(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def view_api():
    # Same-folder, single maintained source; no external module discovery.
    location = Path(__file__).with_name("artifact_views.py")
    spec = importlib.util.spec_from_file_location("ye1_frozen_artifact_views", location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def read_document(path):
    path = Path(path)
    if path.stat().st_size > MAX_JSON_BYTES:
        fail("JSON_BYTE_LIMIT")
    raw = path.read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        fail("JSON_BYTE_LIMIT")
    def finite_float(token):
        value = float(token)
        if not math.isfinite(value):
            fail("NONFINITE_JSON")
        return value
    return raw, json.loads(raw.decode("utf-8-sig"), object_pairs_hook=pairs,
                           parse_float=finite_float, parse_constant=lambda _: fail("NONFINITE_JSON"))


def load(path):
    return read_document(path)[1]


def catalog(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[1] / "references/analysis/capabilities.json"
    value = load(path)
    if value.get("schema_version") != "ye1-agent-analysis-catalog@1.0":
        fail("CATALOG_VERSION_UNSUPPORTED")
    ids = [item["method_id"] for item in value["methods"]]
    if len(ids) != len(set(ids)):
        fail("CATALOG_DUPLICATE_METHOD")
    return value


def select(cat, method):
    matches = [item for item in cat["methods"] if item["method_id"] == method]
    if len(matches) != 1:
        fail("METHOD_NOT_SUPPORTED")
    return matches[0]


def runtime(config, cat):
    if config is None:
        config=Path(__file__).resolve().parents[3]/".clinical-local/agent-runtime.json"
        if not config.is_file():fail("LOCAL_RUNTIME_CONFIGURATION_REQUIRED")
    value = load(config)
    expected = {"schema_version", "integration_root", "rscript"}
    if not isinstance(value, dict) or set(value) != expected:
        fail("RUNTIME_CONFIGURATION_FIELDS_INVALID")
    if value["schema_version"] != "ye1-analysis-local-runtime@1.0":
        fail("RUNTIME_CONFIGURATION_VERSION_UNSUPPORTED")
    root = Path(value["integration_root"]).resolve()
    executable = Path(value["rscript"]).resolve()
    if not root.is_dir() or not executable.is_file():
        fail("LOCAL_RUNTIME_UNAVAILABLE")
    for rel, digest in cat["backend_bindings_sha256"].items():
        path = (root / rel).resolve()
        allowed = root.parent if rel=="../runtime-requirements.json" else root
        if not path.is_relative_to(allowed) or not path.is_file() or sha(path) != digest:
            fail("BACKEND_BINDING_DRIFT")
    # The original entry and contract validators enforce provider/model bindings.
    return root, executable


def operation(task, definition):
    path = definition["operation_path"]
    if path is None:
        return definition["operations"][0]
    value = task
    for key in path:
        if not isinstance(value, dict) or key not in value:
            fail("OPERATION_REQUIRED")
        value = value[key]
    if value not in definition["operations"]:
        fail("OPERATION_NOT_SUPPORTED")
    return value


def route(task, definition):
    """Check selection without changing/signing a study plan or choosing an algorithm."""
    if not isinstance(task, dict):
        fail("TASK_OBJECT_REQUIRED")
    if not isinstance(task.get("execution"), dict):
        fail("TASK_EXECUTION_OBJECT_REQUIRED")
    if definition["task_family"] == "core" and not isinstance(task.get("analysis"), dict):
        fail("TASK_ANALYSIS_OBJECT_REQUIRED")
    actual = task.get("method_id") if definition["task_family"] == "module" else task["analysis"].get("method_id")
    if actual != definition["backend_method_id"]:
        fail("SELECTED_METHOD_TASK_MISMATCH")
    if task.get("schema_version") not in definition.get("accepted_input_schema_versions", [definition["input_schema_version"]]):
        fail("TASK_SCHEMA_VERSION_MISMATCH")
    mode = task.get("execution", {}).get("mode")
    origin = task.get("data_origin")
    if task.get("schema_version") in {"clinical-study-input@1.0","clinical-module-task@1.1"}:
        if mode != "local" or task.get("data_origin") not in {"real", "synthetic"}:
            fail("STUDY_ORIGIN_MODE_INVALID")
    else:
        if mode != "synthetic" or (definition["task_family"] == "module" and origin != "synthetic_inline_normalized") or (
            definition["task_family"] == "core" and task.get("purpose") != "SYNTHETIC_TEST_ONLY"
        ):
            fail("REAL_SOURCE_CONTRACT_NOT_ENABLED")
    selected_operation = operation(task, definition)
    leaf = definition.get("leaf_constraint")
    if leaf:
        models = task.get("analysis", {}).get("association", {}).get("models", [])
        if not isinstance(models, list) or not models:
            fail("LEAF_PLAN_REQUIRED")
        if any(not isinstance(m, dict) or not isinstance(m.get("spec"), dict) for m in models):
            fail("LEAF_PLAN_INVALID")
        nonlinear = [bool(m.get("spec", {}).get("nonlinear")) for m in models]
        subgroup = [bool(m.get("spec", {}).get("subgroup")) for m in models]
        sensitivity = [m.get("role") == "sensitivity" for m in models]
        if leaf == "rcs":
            valid = sum(nonlinear) == 1 and len(models) <= 2 and not any(subgroup) and not any(sensitivity)
            if valid and len(models) == 2:
                specs = [{k: v for k, v in m["spec"].items() if k != "nonlinear"} for m in models]
                valid = specs[0] == specs[1]
        elif leaf == "subgroup":
            valid = len(models) == 1 and all(subgroup) and not any(nonlinear) and not any(sensitivity)
        elif leaf == "sensitivity":
            valid = any(sensitivity) and len(models) >= 2 and not any(nonlinear) and not any(subgroup)
        else:
            valid = any(m.get("spec", {}).get("covariates") for m in models) and not any(nonlinear + subgroup + sensitivity)
        if not valid:
            fail("LEAF_SCOPE_MISMATCH")
    # A baseline-only request cannot attach a regression/model task.
    if definition["backend_method_id"] == "baseline.table1" and task["analysis"].get("spec") is not None:
        fail("BASELINE_ONLY_SCOPE_MISMATCH")
    return selected_operation


def output_path(task, root):
    raw = task.get("execution", {}).get("output_dir")
    if not isinstance(raw, str) or not raw:
        fail("OUTPUT_REQUIRED")
    output = Path(raw).resolve()
    origin_task=task.get("schema_version") in {"clinical-study-input@1.0","clinical-module-task@1.1"}
    if origin_task and (not isinstance(task.get("project_root"),str) or not task["project_root"]):fail("PROJECT_DIRECTORY_REQUIRED")
    core = Path(task["project_root"]).resolve() if origin_task else (root / "core").resolve()
    if output == core or not output.is_relative_to(core) or output.exists() or not output.parent.is_dir():
        fail("FRESH_OUTPUT_INSIDE_BACKEND_CORE_REQUIRED")
    return output


def validate(task_path, task, root, definition, output):
    # Reuse the original strict schema + semantic validators; no permissive substitute.
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "core/python"))
    if definition["task_family"] == "real_engineering":
        importlib.import_module("real_engineering").inspect(task)
    elif definition["task_family"] == "module":
        provider = importlib.import_module("module_task")
        provider.prepare(task_path, output)
    else:
        provider = importlib.import_module("clinical_methods.contracts")
        provider.validate_task(task, root / "core")


def schema(root, definition):
    if definition["task_family"] == "real_engineering":
        document=load(root/"contracts/real-engineering-task.schema.json")
        return {"method_id":definition["method_id"],"backend_method_id":definition["backend_method_id"],"schema_kind":"explicit_local_engineering_request","parameters":document,"task_envelope":document,"validation_owner":"explicit scoped local source authorization + original table1 numerical owner"}
    if definition["task_family"] == "result_view":
        value = view_api().request_schema(definition["method_id"],definition["input_schema_version"])
        return {"method_id": definition["method_id"], "backend_method_id": definition["backend_method_id"],
                "schema_kind": "existing_result_export_request", "parameters": value, "task_envelope": value,
                "selection_constraints": {"operations": ["export_existing"], "no_fit_or_new_evaluation": True},
                "validation_owner": "original source result schema + bound artifact manifest", "result_schema": "clinical-result-view@1.0"}
    document = load(root / definition["schema_resource"])
    envelope = None
    if definition["task_family"] == "module":
        sys.path.insert(0, str(root))
        envelope = (load(root/"contracts/module-task-origin.schema.json") if definition["input_schema_version"]=="clinical-module-task@1.1"
                    else copy.deepcopy(importlib.import_module("module_task").TASK_SCHEMA))
        if definition["input_schema_version"]=="clinical-module-task@1.1":
            transport=importlib.import_module("module_task")
            admitted=importlib.import_module("admitted_modules")
            registry,metadata,_=transport.load_registry(definition["backend_method_id"])
            info=metadata[definition["backend_method_id"]]
            selection,_=admitted.load_selection(info,definition["backend_method_id"])
            registered=registry.methods[definition["backend_method_id"]]
            admitted._apply_schemas(registry,registered,info,selection,definition["backend_method_id"])
            document=copy.deepcopy(registered["validators"]["payload"].schema)
            envelope["properties"]["payload"]=copy.deepcopy(document)
        envelope["properties"]["method_id"] = {"const": definition["backend_method_id"]}
        envelope["properties"]["operation"] = {"enum": definition["operations"]}
    # Core envelope is an explicit version union. Return the requested existing branch.
    if definition["task_family"] == "core":
        candidates=[item for item in document["anyOf"] if item["properties"]["schema_version"].get("const")==definition["input_schema_version"]]
        if definition["input_schema_version"]=="clinical-study-input@1.0":
            def accepts(item):
                selector=item["properties"]["analysis"]["properties"]["method_id"]
                return selector.get("const")==definition["backend_method_id"] or definition["backend_method_id"] in selector.get("enum",[])
            candidates=[item for item in candidates if accepts(item)]
        if not candidates:
            fail("SCHEMA_RESOURCE_VERSION_MISMATCH")
        candidates=copy.deepcopy(candidates)
        for item in candidates:item["properties"]["analysis"]["properties"]["method_id"]={"const":definition["backend_method_id"]}
        document=candidates[0] if len(candidates)==1 else {"anyOf":candidates}
    return {"method_id": definition["method_id"], "backend_method_id": definition["backend_method_id"],
            "schema_kind": "module_payload" if definition["task_family"] == "module" else "complete_task_envelope",
            "parameters": document, "task_envelope": envelope, "selection_constraints": {"operations": definition["operations"],
            "operation_path": definition["operation_path"], "leaf_constraint": definition.get("leaf_constraint")},
            "validation_owner": definition["validation_owner"], "result_schema": definition["result_schema_resource"]}


def execute(root, executable, path, task, definition, selected_operation, output):
    private = output.parent / "private"
    private.mkdir(exist_ok=True)
    log = private / (output.name + ".console.log")
    receipt = private / (output.name + ".agent-call.json")
    if receipt.exists():
        fail("CALL_RECEIPT_ALREADY_EXISTS")
    command = [str(executable), "--vanilla", str(root / "core/tools/run_core.R"), str(path.resolve()), str(output)]
    with log.open("xb") as handle:
        run = subprocess.run(command, cwd=root / "core", stdout=handle, stderr=subprocess.STDOUT, check=False)
    result_path = output / "result.json"
    result = load(result_path) if result_path.is_file() else {}
    if result and result.get("method_id") != definition["backend_method_id"]:
        fail("BACKEND_RESULT_METHOD_MISMATCH")
    presentation_status = "not_computed"
    if result.get("execution_status") in ("complete", "partial"):
        product = Path(__file__).resolve().parents[3]
        helper = product / "scripts/presentation.py"
        try:
            spec = importlib.util.spec_from_file_location("ye1_local_presentation", helper)
            presenter = importlib.util.module_from_spec(spec); spec.loader.exec_module(presenter)
            presenter.render(task, output, root / "core")
            presentation_status = "written"
        except (OSError, ValueError, KeyError, TypeError, ImportError):
            presentation_status = "local_presentation_failed"
    published = None
    if result.get("execution_status") in ("complete", "partial"):
        published = view_api().publish(root, result, task, output)
    summary = {"selected_method_id": definition["method_id"], "backend_method_id": definition["backend_method_id"],
               "operation": selected_operation, "task_sha256": sha(path), "executed_task_count": 1,
               "single_entry": "clinanalysis::run_analysis_task", "returncode": run.returncode,
               "execution_status": result.get("execution_status", "no_public_result"),
               "presentation_status": presentation_status,
               "reason_code": result.get("reason_code"), "result": str(result_path) if result else None,
               "agent_artifact_manifest": str(published) if published else None,
               "console_log": str(log), "scientific_review": "pending", "data_scope": "REAL_DATA_LOCAL_ENGINEERING_ONLY" if definition["task_family"]=="real_engineering" else ("REAL_DATA_LOCAL_ONLY" if task.get("data_origin")=="real" else "SYNTHETIC_TEST_ONLY")}
    with receipt.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return summary, int(run.returncode != 0 or result.get("execution_status") != "complete" or presentation_status != "written")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--runtime", type=Path, help="Explicit local binding; never an automatically discovered machine path")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list").add_argument("--group")
    for action in ("describe", "schema", "validate", "run"):
        item = sub.add_parser(action)
        item.add_argument("method_id")
        item.add_argument("--input-version", help="Explicit accepted task contract version; schema selection does not authorize execution")
        if action in ("validate", "run"):
            item.add_argument("--task", type=Path, required=True)
    args = parser.parse_args(argv)
    cat = catalog(args.catalog)
    if args.action == "list":
        entries = [m for m in cat["methods"] if args.group is None or m["group"] == args.group]
        print(json.dumps({"methods": [{k: m[k] for k in ("method_id", "title", "group", "operations")} for m in entries],
                          "scope": cat["scope"], "runtime_required": False}, ensure_ascii=False))
        return 0
    definition = select(cat, args.method_id)
    if args.action == "describe":
        definition = copy.deepcopy(definition)
        backend = Path(__file__).resolve().parents[1]
        if not (backend / "integration/core/python/clinical_methods/resource_budget.py").is_file():
            backend = backend.parents[1] / "_shared/clinical_analysis"
        path = backend / "integration/core/python/clinical_methods/resource_budget.py"
        loader = importlib.util.spec_from_file_location("clinical_resource_discovery", path)
        budget = importlib.util.module_from_spec(loader); loader.loader.exec_module(budget)
        target = definition.get("backend_method_id", definition["method_id"])
        definition["resource_policy"] = {"defaults": budget.defaults(target), "profile": budget.profile(target),
            "numerical_owner_max_rows": budget.owner_capacity({"analysis":{"method_id":target}}),
            "configuration": "clinical-study-input@1.0 execution; explicit task bounds are never enlarged automatically",
            "no_silent_sampling": True, "memory_or_runtime_guarantee": False}
        if "clinical-study-input@1.0" not in definition.get("accepted_input_schema_versions", []):
            definition["resource_policy"] = {"configuration": "Existing module/view-specific limits remain; see docs/CLINICAL-RESOURCE-BUDGETS.md",
                "unified_execution_budget_supported": False, "no_silent_sampling": True}
        print(json.dumps(definition, ensure_ascii=False))
        return 0
    root, executable = runtime(args.runtime, cat)
    if getattr(args,"input_version",None):
        if args.input_version not in definition.get("accepted_input_schema_versions",[definition["input_schema_version"]]):
            fail("TASK_SCHEMA_VERSION_MISMATCH")
        definition=copy.deepcopy(definition);definition["input_schema_version"]=args.input_version
    if args.action == "schema":
        print(json.dumps(schema(root, definition), ensure_ascii=False))
        return 0
    raw, task = read_document(args.task)
    if (args.action in {"run","validate"} and task.get("schema_version") in {"clinical-study-input@1.0","clinical-module-task@1.1","ye1-result-view-request@1.1"} and
        task.get("data_origin") == "real" and task.get("execution",{}).get("privacy_profile") == "captured_local_process" and
        not os.environ.get("YE1_STUDY_CAPTURED_RECEIPT")):
        sys.path.insert(0,str(root))
        captured=importlib.import_module("captured_study")
        if not isinstance(task.get("project_root"),str) or not task["project_root"]:fail("PROJECT_DIRECTORY_REQUIRED")
        profile=args.runtime or Path(__file__).resolve().parents[3]/".clinical-local/agent-runtime.json"
        outcome=captured.run(task["project_root"],args.task,root/"core",profile,action=args.action)
        print(json.dumps(outcome,ensure_ascii=False))
        return int(outcome["returncode"]!=0)
    if definition["task_family"] == "result_view":
        value = view_api().project(root, task, definition, validate_only=args.action == "validate")
        print(json.dumps(value, ensure_ascii=False))
        return 0
    if definition["task_family"] == "real_engineering":
        if task.get("method_id")!=definition["method_id"]:fail("SELECTED_METHOD_TASK_MISMATCH")
        selected_operation=task.get("operation")
        if selected_operation!="describe":fail("OPERATION_NOT_SUPPORTED")
    else:
        selected_operation = route(task, definition)
    output = output_path(task, root)
    if args.action == "validate":
        validate(args.task, task, root, definition, output)
        if sha(args.task) != hashlib.sha256(raw).hexdigest():
            fail("TASK_CHANGED_DURING_VALIDATION")
        print(json.dumps({"status": "CONTRACT_VALIDATED_NOT_EXECUTED", "method_id": definition["method_id"],
                          "backend_method_id": definition["backend_method_id"], "operation": selected_operation,
                          "scientific_review": "pending"}))
        return 0
    # Capture the supplied bytes once. The selected method, validation and R entry
    # consume the same new private snapshot; no plan fields or seals are changed.
    private = output.parent / "private"
    private.mkdir(exist_ok=True)
    snapshot = private / (output.name + ".task.json")
    with snapshot.open("xb") as handle:
        handle.write(raw)
    validate(snapshot, task, root, definition, output)
    result, code = execute(root, executable, snapshot, task, definition, selected_operation, output)
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    # Process-local UTF-8 JSON also when the Windows caller omits -X utf8.
    # No console codepage, locale, registry or global environment is changed.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        code = getattr(error, "code", "CALL_FAILED")
        if not isinstance(code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]+", code) is None:
            code = "CALL_FAILED"
        print(json.dumps({"status": "blocked", "reason_code": code,
                          "stage": getattr(error,"stage",None), "missing_requirements": getattr(error,"missing",[]),
                          "detail": "Inspect local prerequisites/contracts; no fallback algorithm was executed."}))
        raise SystemExit(2)
