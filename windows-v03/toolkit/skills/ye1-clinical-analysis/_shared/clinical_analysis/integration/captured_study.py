"""One fixed local statistical invocation with captured streams; no host sandbox.

The ``captured_local_process`` profile is new and deliberately narrower than
legacy host_check. It establishes consistency of one cooperating invocation,
not global identity, network isolation, protected state, or denial of other
tools' access to raw files. Environment values route descendants (Agent -> R ->
Python); they are not sandbox authentication. Core source and plan checks remain.
All outward artifacts still need the
legacy authorize/export gate. This module never sends data or installs tools.
"""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile


PROFILE = "captured_local_process"
ADAPTER_SCHEMA = "clinical-captured-study-adapter@1.0"
RECEIPT_SCHEMA = "clinical-captured-study-invocation@1.0"
TASK_SCHEMA = "clinical-study-input@1.0"
METHODS = frozenset({"baseline.table1", "association.linear", "association.logistic"})
VIEW_SCHEMA = "ye1-result-view-request@1.1"
MODULE_SCHEMA = "clinical-module-task@1.1"
COMPAT_SCHEMA = "ye1-compat-study@1.0"
COMPAT_METHODS = frozenset({"compat.test.welch_t","compat.test.paired_t","compat.test.wilcoxon_rank_sum","compat.test.fisher_2x2","compat.test.chi_square"})
VIEW_METHODS = frozenset({"result.baseline.table","result.association.effects","result.binary.roc","result.binary.calibration","result.binary.dca",
    "result.survival.roc","result.survival.calibration","result.survival.dca","result.survival.ph","result.nomogram","result.importance"})
MAX_METADATA_BYTES = 2 * 1024 * 1024
ENV_RECEIPT = "YE1_STUDY_CAPTURED_RECEIPT"
ENV_RECEIPT_HASH = "YE1_STUDY_CAPTURED_RECEIPT_SHA256"
ENV_TOKEN = "YE1_STUDY_CAPTURED_TOKEN"
ENV_ROOT_PID = "YE1_STUDY_CAPTURED_ROOT_PID"


class CapturedStudyError(ValueError):
    """Only fixed codes, never source paths, task values or exception text."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise CapturedStudyError(code)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _canonical(value):
    return _sha(json.dumps(value, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), allow_nan=False).encode("utf-8"))


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _pairs(items):
    value = {}
    for key, item in items:
        _need(key not in value, "CAPTURED_METADATA_DUPLICATE_KEY")
        value[key] = item
    return value


def _decode(raw):
    _need(len(raw) <= MAX_METADATA_BYTES, "CAPTURED_METADATA_BYTE_LIMIT")
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(
                               CapturedStudyError("CAPTURED_METADATA_NONFINITE")))
        _canonical(value)  # also rejects nonfinite float overflow
    except CapturedStudyError:
        raise
    except (ValueError, UnicodeError, TypeError, OverflowError):
        raise CapturedStudyError("CAPTURED_METADATA_INVALID") from None
    _need(isinstance(value, dict), "CAPTURED_METADATA_OBJECT_REQUIRED")
    return value


def _read(path):
    _need(path.is_file() and path.stat().st_size <= MAX_METADATA_BYTES,
          "CAPTURED_METADATA_FILE_REQUIRED")
    raw = path.read_bytes()
    return raw, _decode(raw)


def _read_history(path):
    _need(path.is_file() and path.stat().st_size <= MAX_METADATA_BYTES,
          "CAPTURED_METADATA_FILE_REQUIRED")
    raw = path.read_bytes()
    _need(len(raw) <= MAX_METADATA_BYTES, "CAPTURED_METADATA_BYTE_LIMIT")
    value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(
                           CapturedStudyError("CAPTURED_METADATA_NONFINITE")))
    _need(isinstance(value, list), "PROJECT_PRIVACY_CONTEXT_REQUIRED")
    return raw, value


def _unlinked(path):
    for item in (path, *path.parents):
        _need(not item.is_symlink() and not (
            hasattr(item, "is_junction") and item.is_junction()), "CAPTURED_UNSAFE_PATH")
    return path


def _project(project):
    path = _unlinked(Path(project)).resolve()
    _need(path.is_dir(), "PROJECT_DIRECTORY_REQUIRED")
    return path


def _state(project, *, create=False):
    state = _unlinked(project / ".ye1-privacy")
    if create:
        state.mkdir(exist_ok=True)
    _need(state.is_dir(), "PROJECT_PRIVACY_CONTEXT_REQUIRED")
    return state


def _layout(core_root):
    core = _unlinked(Path(core_root)).resolve()
    integration = Path(__file__).resolve().parent
    _need(core == integration / "core", "CAPTURED_CANONICAL_CORE_REQUIRED")
    backend = integration.parent
    files = {
        "adapter": integration / "captured_study.py",
        "agent_entry": backend / "agent/analysis_call.py",
        "agent_artifacts": backend / "agent/artifact_views.py",
        "agent_catalog": backend / "agent/catalog.json",
        "privacy": backend / "legacy/scripts/privacy_boundary.py",
        "study_admission": core / "python/clinical_methods/study_input.py",
        "core_contracts": core / "python/clinical_methods/contracts.py",
        "r_entry": core / "tools/run_core.R",
    }
    # Bind the v0.2 local presentation and user-facing adapters as well; this
    # strengthens invocation consistency and grants no new host capability.
    product = backend.parents[1]
    for name in ("presentation.py", "analyze.py", "km_display.py", "plot_km.R", "authorize_project.py",
                 "toolkit.py", "prepare_task.py", "ingestion.py", "runtime_toolkit.py", "method_groups.py"):
        files["windows_product_" + name] = product / "scripts" / name
    for name in ("frozen_display.py","plot_frozen.R","local_console.py"):
        files["windows_product_"+name]=product/"scripts"/name
    files["windows_legacy_analysis"] = product / "scripts/legacy_analysis.py"
    files["windows_compat_plot"] = product / "scripts/plot_compat.R"
    files["original_compat_worker"] = product / "_shared/compat/stats_worker.R"
    _need(all(_unlinked(p).is_file() for p in files.values()), "CAPTURED_ENTRY_UNAVAILABLE")
    return {"core": core, "integration": integration, "files": files}


def _bindings(layout):
    # macOS venv executables may be symlinks to the bound framework.
    executable = Path(sys.executable).resolve()
    _need(executable.is_file(), "CAPTURED_PYTHON_UNAVAILABLE")
    return {
        "code_sha256": {name: _sha(path.read_bytes()) for name, path in layout["files"].items()},
        "python_executable": str(executable),
        "python_sha256": _sha(executable.read_bytes()),
    }


def _capability():
    return {"profile": PROFILE, "enforcement_scope": "this_adapter_invocation",
            "global_host_isolation": "not_established", "streams_exposed": False,
            "no_network_action": True, "network_isolation": "not_provided"}


def _registration_fields(project, layout, reference):
    return {"schema_version": ADAPTER_SCHEMA, **_capability(),
            "project_root": str(project), "core_root": str(layout["core"]),
            "entry": str(layout["files"]["agent_entry"]),
            "catalog": str(layout["files"]["agent_catalog"]),
            "stdout_stderr": "merged_private_local_log",
            "assessment_reference": reference, **_bindings(layout)}


def _atomic(path, raw):
    _unlinked(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".captured-state-", suffix=".tmp")
    temporary = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _register(project, core_root, assessment_reference):
    """Record this new narrow profile only; create no A/B or user evidence.

    The supplied reference describes an actual local assessment. Recording it
    does not turn it into a strong-host declaration or authenticate its author.
    Re-registration explicitly updates this manifest and invalidates old runs.
    """
    _need(isinstance(assessment_reference, str) and assessment_reference.strip(),
          "CAPTURED_ASSESSMENT_REFERENCE_REQUIRED")
    project = _project(project)
    layout = _layout(core_root)
    expected = _registration_fields(project, layout, assessment_reference)
    path = _state(project, create=True) / "study-adapter.json"
    if path.exists():
        _, previous = _read(_unlinked(path))
        if {k: v for k, v in previous.items() if k != "registered_at"} == expected:
            return {"status": "CAPTURED_ADAPTER_UNCHANGED", **_capability()}
    _atomic(path, _encoded({**expected, "registered_at": _now()}))
    return {"status": "CAPTURED_ADAPTER_REGISTERED", **_capability()}


def register(project, core_root, assessment_reference):
    """Register only the new capture profile, never a choice or strong host."""
    try:
        return _register(project, core_root, assessment_reference)
    except CapturedStudyError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise CapturedStudyError("CAPTURED_REGISTRATION_FAILED") from None


def _registration(project, layout):
    # Bind actual executable and code bytes for this invocation without inventing
    # a human assessment, choice, or confirmation record.
    return _canonical(_bindings(layout))


def _privacy(layout):
    spec = importlib.util.spec_from_file_location(
        "clinical_captured_existing_project_privacy", layout["files"]["privacy"])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _choice(project, layout):
    # Preserve an existing explicit strict choice. New local tasks do not create
    # a choice or assert that a user made one.
    path = project / ".ye1-privacy/choice.json"
    if not path.exists():
        _need(not (project / ".ye1-privacy/history.json").exists(), "PROJECT_PRIVACY_CONTEXT_REQUIRED")
        return None
    try:
        raw, current = _read(_unlinked(path))
        _, history = _read_history(_unlinked(project / ".ye1-privacy/history.json"))
        privacy = _privacy(layout)
        privacy.validate_choice(current)
        _need(history and current == history[-1]["choice"], "PROJECT_CHOICE_CHANGED")
        previous = None
        for revision, item in enumerate(history, 1):
            body = {k: v for k, v in item.items() if k != "sha256"}
            _need(item["revision"] == revision and item["previous"] == previous and
                  item["sha256"] == privacy.digest(privacy.encoded(body)), "PROJECT_CHOICE_CHANGED")
            previous = item["sha256"]
        _need(history[-1]["test_only"] is False, "TEST_CONTEXT_CANNOT_AUTHORIZE_REAL_DATA")
        _need(current["mode"] == "B", "EXISTING_STRICT_MODE_REQUIRES_REVIEW")
        return {"sha256": _sha(raw), "revision": len(history), "mode": current["mode"]}
    except CapturedStudyError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise CapturedStudyError("PROJECT_PRIVACY_CONTEXT_REQUIRED") from None


def _task_metadata(task, project):
    view = task.get("schema_version") == VIEW_SCHEMA
    module = task.get("schema_version") == MODULE_SCHEMA
    compat = task.get("schema_version") == COMPAT_SCHEMA
    _need(task.get("schema_version") in {TASK_SCHEMA,MODULE_SCHEMA,VIEW_SCHEMA,COMPAT_SCHEMA} and task.get("data_origin") == "real",
          "CAPTURED_REAL_STUDY_TASK_REQUIRED")
    _need(isinstance(task.get("project_root"), str) and bool(task["project_root"].strip()) and
          Path(task["project_root"]).resolve() == project,
          "PROJECT_CHOICE_CONTEXT_MISMATCH")
    _need(task.get("task_purpose") in {"engineering_test", "research_analysis"},
          "CAPTURED_TASK_PURPOSE_REQUIRED")
    execution = task.get("execution")
    _need(isinstance(execution, dict) and execution.get("privacy_profile") == PROFILE,
          "CAPTURED_PROFILE_REQUIRED")
    if view:
        _need(task.get("method_id") in VIEW_METHODS,"CAPTURED_METHOD_NOT_SUPPORTED")
        return task["method_id"]
    if compat:
        _need(task.get("method_id") in COMPAT_METHODS,"CAPTURED_METHOD_NOT_SUPPORTED")
        return task["method_id"]
    if module:
        _, catalog = _read(Path(__file__).resolve().parent.parent/"agent/catalog.json")
        methods={m["backend_method_id"] for m in catalog["methods"] if m["task_family"]=="module" and
                 MODULE_SCHEMA in m.get("accepted_input_schema_versions",[m["input_schema_version"]])}
        _need(task.get("method_id") in methods,"CAPTURED_METHOD_NOT_SUPPORTED")
        return task["method_id"]
    analysis = task.get("analysis")
    _need(isinstance(analysis, dict),"CAPTURED_METHOD_NOT_SUPPORTED")
    if analysis.get("method_id") not in METHODS:
        _, catalog = _read(Path(__file__).resolve().parent.parent/"agent/catalog.json")
        methods={m["backend_method_id"] for m in catalog["methods"] if m["task_family"]=="core" and
                 TASK_SCHEMA in m.get("accepted_input_schema_versions",[m["input_schema_version"]])}
        _need(analysis.get("method_id") in methods,"CAPTURED_METHOD_NOT_SUPPORTED")
    # Source bytes, scientific schema, exact plan/instruction and user evidence
    # are validated by the canonical core; this capture layer cannot grant them.
    return analysis["method_id"]


def _runtime(path, layout):
    path = _unlinked(Path(path)).resolve()
    raw, value = _read(path)
    _need(set(value) == {"schema_version", "integration_root", "rscript"} and
          value["schema_version"] == "ye1-analysis-local-runtime@1.0" and
          Path(value["integration_root"]).resolve() == layout["integration"],
          "CAPTURED_RUNTIME_BINDING_INVALID")
    executable = _unlinked(Path(value["rscript"])).resolve()
    _need(executable.is_file(), "CAPTURED_RUNTIME_UNAVAILABLE")
    return {"path": str(path), "sha256": _sha(raw), "rscript_sha256": _sha(executable.read_bytes())}


def _pid_alive(pid):
    """Read-only liveness check, not ancestry or identity authentication."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except OSError:
            return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.GetExitCodeProcess.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


def _verify(project, task, core_root, env):
    project = _project(project)
    layout = _layout(core_root)
    method = _task_metadata(task, project)
    _need(env.get("YE1_PRIVACY_CONTROLLED_RUN") == "1" and env.get("YE1_PRIVACY_PROJECT") and
          Path(env["YE1_PRIVACY_PROJECT"]).resolve() == project, "CAPTURED_RUN_CONTEXT_REQUIRED")
    _need(env.get("YE1_PRIVACY_SYNTHETIC_TEST") != "1", "TEST_CONTEXT_CANNOT_AUTHORIZE_REAL_DATA")
    _need(all(isinstance(env.get(k), str) and env[k] for k in
              (ENV_RECEIPT, ENV_RECEIPT_HASH, ENV_TOKEN, ENV_ROOT_PID)), "CAPTURED_RUN_CONTEXT_REQUIRED")
    runs = _unlinked(_state(project) / "study-runs")
    receipt_path = _unlinked(Path(env[ENV_RECEIPT])).resolve()
    _need(receipt_path.is_relative_to(runs.resolve()), "CAPTURED_RECEIPT_OUTSIDE_PROJECT")
    relative = receipt_path.relative_to(runs.resolve()).parts
    _need(len(relative) == 2 and re.fullmatch("[0-9a-f]{32}", relative[0]) and
          relative[1] == "receipt.json", "CAPTURED_RECEIPT_INVALID")
    raw, receipt = _read(receipt_path)
    _need(_sha(raw) == env[ENV_RECEIPT_HASH], "CAPTURED_RECEIPT_CHANGED")
    _need(receipt.get("schema_version") == RECEIPT_SCHEMA and receipt.get("status") == "running" and
          receipt.get("profile") == PROFILE, "CAPTURED_INVOCATION_NOT_RUNNING")
    _need(receipt.get("token_sha256") == _sha(env[ENV_TOKEN].encode("utf-8")), "CAPTURED_TOKEN_MISMATCH")
    _need(str(receipt.get("root_pid")) == env[ENV_ROOT_PID] and _pid_alive(receipt.get("root_pid")),
          "CAPTURED_ROOT_PROCESS_UNAVAILABLE")
    _need(receipt.get("project_root") == str(project) and receipt.get("core_root") == str(layout["core"]),
          "CAPTURED_PROJECT_BINDING_CHANGED")
    _need(receipt.get("registration_sha256") == _registration(project, layout),
          "CAPTURED_REGISTRATION_CHANGED")
    choice = _choice(project, layout)
    _need(receipt.get("choice") == choice, "PROJECT_CHOICE_CHANGED")
    snapshot_raw, snapshot = _read(_unlinked(receipt_path.parent / "task.json"))
    _need(_sha(snapshot_raw) == receipt.get("task_sha256") and
          _canonical(snapshot) == receipt.get("task_canonical_sha256") and
          _canonical(task) == receipt.get("task_canonical_sha256") and
          receipt.get("method_id") == method, "CAPTURED_TASK_CHANGED")
    _need(receipt.get("runtime") == _runtime(receipt["runtime"]["path"], layout),
          "CAPTURED_RUNTIME_CHANGED")
    return {**_capability(), "choice_revision": choice["revision"] if choice else None, "choice_sha256": choice["sha256"] if choice else None}


def verify_context(project, task, core_root):
    """Check one running invocation for core admission, before source reads.

    A receipt/token plus live launcher binds cooperating descendants to captured
    metadata. Same-user arbitrary tools could forge local state; this API makes
    no claim to stop them or authenticate a globally isolated host.
    """
    try:
        return _verify(project, task, core_root, os.environ)
    except CapturedStudyError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise CapturedStudyError("CAPTURED_CONTEXT_INVALID") from None


def _append_status(log_path, value):
    try:
        with _unlinked(log_path).open("ab") as stream:
            stream.write(_encoded(value))
    except (OSError, CapturedStudyError):
        pass  # no local error text or traceback is allowed into the caller


def run(project, task_path, core_root, runtime_path, *, action="run"):
    """Run only the bound canonical Agent argv; return no result, path or stream.

    Invocation logs, metadata snapshots and receipts stay local. ``no_network_action``
    describes this adapter's actions, not a firewall. This grants no permission
    to upload raw A data or bypass legacy artifact authorize/export checks.
    """
    receipt_path = None
    receipt = None
    log_path = None
    code = 4
    status = "CAPTURED_LOCAL_BLOCKED"
    try:
        _need(action in {"run","validate"},"CAPTURED_ACTION_NOT_SUPPORTED")
        _need(not os.environ.get(ENV_RECEIPT), "CAPTURED_NESTED_RUN_FORBIDDEN")
        project = _project(project)
        layout = _layout(core_root)
        _state(project, create=True)
        registration_hash = _registration(project, layout)
        raw, task = _read(_unlinked(Path(task_path)).resolve())
        method = _task_metadata(task, project)
        choice = _choice(project, layout)
        runtime = _runtime(runtime_path, layout)
        runs = _unlinked(_state(project) / "study-runs")
        runs.mkdir(exist_ok=True)
        invocation = runs / secrets.token_hex(16)
        invocation.mkdir()
        snapshot = invocation / "task.json"
        with snapshot.open("xb") as stream:
            stream.write(raw)
        log_path = invocation / "streams.log"
        receipt_path = invocation / "receipt.json"
        token = secrets.token_urlsafe(32)
        receipt = {"schema_version": RECEIPT_SCHEMA, "status": "running", "profile": PROFILE,
                   "root_pid": os.getpid(), "project_root": str(project), "core_root": str(layout["core"]),
                   "registration_sha256": registration_hash, "choice": choice, "runtime": runtime,
                   "method_id": method, "task_sha256": _sha(raw), "task_canonical_sha256": _canonical(task),
                   "token_sha256": _sha(token.encode("utf-8")), "started_at": _now(), **_capability()}
        receipt_raw = _encoded(receipt)
        with receipt_path.open("xb") as stream:
            stream.write(receipt_raw)
        env = {**os.environ, "YE1_PRIVACY_CONTROLLED_RUN": "1", "YE1_PRIVACY_PROJECT": str(project),
               ENV_RECEIPT: str(receipt_path), ENV_RECEIPT_HASH: _sha(receipt_raw),
               ENV_TOKEN: token, ENV_ROOT_PID: str(os.getpid())}
        command = [str(Path(sys.executable).resolve()), "-B", "-X", "utf8",
                   str(layout["files"]["agent_entry"]), "--catalog", str(layout["files"]["agent_catalog"]),
                   "--runtime", runtime["path"], action, method, "--task", str(snapshot)]
        if task.get("schema_version") == COMPAT_SCHEMA:
            command = [str(Path(sys.executable).resolve()),"-I","-B","-X","utf8",
                       str(layout["files"]["windows_legacy_analysis"]),action,"--method",method,"--task",str(snapshot)]
        with log_path.open("xb") as stream:
            done = subprocess.run(command, cwd=layout["core"], env=env, stdin=subprocess.DEVNULL,
                                  stdout=stream, stderr=subprocess.STDOUT, shell=False, check=False,
                                  timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        code = int(done.returncode)
        _verify(project, task, core_root, env)  # changes during execution cannot report success
        status = "CAPTURED_LOCAL_COMPLETED" if code == 0 else "CAPTURED_LOCAL_FAILED"
    except KeyboardInterrupt:
        code, status = 130, "CAPTURED_LOCAL_FAILED"
    except Exception as error:
        code, status = 4, "CAPTURED_LOCAL_BLOCKED"
        if log_path is not None:
            safe_code = error.code if isinstance(error, CapturedStudyError) else "CAPTURED_PROCESS_FAILED"
            _append_status(log_path, {"adapter_status": status, "code": safe_code})
    finally:
        if receipt_path is not None and receipt is not None:
            receipt.update(status="complete" if status == "CAPTURED_LOCAL_COMPLETED" else "failed",
                           returncode=code, finished_at=_now())
            try:
                _atomic(receipt_path, _encoded(receipt))
            except (OSError, CapturedStudyError):
                code, status = 4, "CAPTURED_LOCAL_BLOCKED"
    return {"status": status, "returncode": code, "streams_exposed": False}
