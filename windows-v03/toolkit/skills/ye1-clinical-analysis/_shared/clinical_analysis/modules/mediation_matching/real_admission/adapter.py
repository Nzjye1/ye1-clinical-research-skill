"""Root-admitted V1 inputs to unchanged numerical owners; no public projection.

The root creates the context and binds the normalized payload. A JSON caller
cannot provide this context. It is not an operating-system isolation boundary.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
CORE = MODULE.parents[1] / "integration/core"
METHODS = ("mediation.linear.binary_exposure", "causal.psm.att.binary", "causal.psm.matched.survival")


class AdmissionError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def need(value, code):
    if not value:
        raise AdmissionError(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _resource_limits(context, method):
    callback = getattr(context, "resource_limits", None)
    need(callable(callback), "MM_REAL_RESOURCE_CONTEXT_REQUIRED")
    sys.path.insert(0, str(CORE / "python"))
    from clinical_methods import resource_budget as budgets
    try:
        return budgets.validate_limits(callback(), method)
    except budgets.BudgetError as error:
        raise AdmissionError(error.code) from None


def _schema(name):
    path = HERE / "contracts" / name
    need(path.is_file(), "MM_REAL_SCHEMA_MISSING")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _validate(value, name, code):
    sys.path.insert(0, str(CORE / "python"))
    from clinical_methods.contracts import validate_schema
    try:
        validate_schema(value, _schema(name))
    except AdmissionError:
        raise
    except (ValueError, TypeError, KeyError):
        raise AdmissionError(code) from None


def _context(request, context):
    check = getattr(context, "require_request", None)
    need(callable(check), "MM_REAL_CONTEXT_REQUIRED")
    need(isinstance(request, dict), "MM_REAL_REQUEST_INVALID")
    # The root's sealed binding is checked before walking any variable or row.
    accepted = check(request.get("method_id"), request.get("operation"), request.get("payload"))
    need(accepted is not False, "MM_REAL_CONTEXT_REJECTED")
    metadata = {name: getattr(context, name, None) for name in ("data_origin", "task_purpose", "scientific_review", "test_only")}
    need(metadata["data_origin"] in ("real", "synthetic") and metadata["task_purpose"] in ("engineering_test", "research_analysis") and
         metadata["scientific_review"] == "pending" and type(metadata["test_only"]) is bool, "MM_REAL_CONTEXT_METADATA_INVALID")
    root = getattr(context, "project_root", None)
    need(isinstance(root, (str, Path)), "MM_REAL_PROJECT_CONTEXT_REQUIRED")
    root = Path(root).resolve()
    need(root.is_dir(), "MM_REAL_PROJECT_CONTEXT_REQUIRED")
    return metadata, root


def validate_request(request, context):
    metadata, project = _context(request, context)
    _validate(request, "request.schema.json", "MM_REAL_REQUEST_INVALID")
    method, payload = request["method_id"], request["payload"]
    s, st, rows = payload["spec"], payload["structure"], payload["rows"]
    fs, cv, z, options = s["fields"], s["covariates"], s["semantics"], s["options"]
    need(s["method_id"] == method, "MM_REAL_METHOD_MISMATCH")
    fields = [name for name in fs.values() if name is not None] + cv
    need(len(fields) == len(set(fields)) and len(cv) == len(set(cv)) and not any(name.startswith("mm_") for name in fields), "MM_REAL_FIELDS_INVALID")
    need(st["grain"] == "subject_wide" and st["subject_key"] == fs["subject"] and st["record_keys"] == [fs["subject"]] and st["cluster_key"] is None and
         st["weights"] == "none" and st["missingness"] == options["missingness"], "MM_REAL_STRUCTURE_UNSUPPORTED")
    need(st["time_origin"] == z["exposure_time"] and st["time_unit"] == z["time_unit"] and
         number(st["analysis_as_of"]) and st["analysis_as_of"] > st["time_origin"] and z["covariate_latest_time"] <= z["exposure_time"], "MM_REAL_CAUSAL_TIME_REQUIRED")
    if method == METHODS[0]:
        need(z["exposure_time"] < z["mediator_time"] < z["outcome_time"] <= st["analysis_as_of"], "MM_REAL_MEDIATION_ORDER_REQUIRED")
    elif method == METHODS[1]:
        need(z["exposure_time"] < z["outcome_time"] <= st["analysis_as_of"] and z["binary_horizon_complete"] is True, "MM_REAL_BINARY_HORIZON_INCOMPLETE")
    limits = _resource_limits(context, method)
    need(0 < len(rows) <= limits["max_rows"], "RESOURCE_ROW_BUDGET_EXCEEDED")
    if method != METHODS[0]:
        need(sum(row["exposure"] == 1 for row in rows) * sum(row["exposure"] == 0 for row in rows)
             <= limits["max_candidate_pairs"], "RESOURCE_CANDIDATE_PAIR_BUDGET_EXCEEDED")
    categories = options.get("categorical", {})
    need(set(categories) <= set(cv), "MM_REAL_CATEGORIES_INVALID")
    for category in categories.values():
        need(len(category["levels"]) == len(set(category["levels"])) and category["reference"] in category["levels"], "MM_REAL_CATEGORIES_INVALID")
    variables = payload["variables"]
    names = [variable["name"] for variable in variables]
    need(len(names) == len(set(names)) and set(names) == set(fields), "MM_REAL_VARIABLE_SET_MISMATCH")
    roles = {name: role for role, name in fs.items() if name is not None} | {name: "covariate" for name in cv}
    for variable in variables:
        name, role = variable["name"], roles[variable["name"]]
        dtype = "id" if role == "subject" else "category" if name in categories else "number"
        tr = {"subject": "identifier", "exposure": "exposure", "covariate": "baseline", "mediator": "mediator", "outcome": "outcome", "time": "followup_duration", "event": "event_at_followup"}[role]
        need(variable["role"] == role and variable["dtype"] == dtype and variable["time_role"] == tr, "MM_REAL_VARIABLE_ROLE_TYPE_MISMATCH")
        if role in ("exposure", "event") or role == "outcome" and method == METHODS[1]:
            need(variable["unit"] == "1", "MM_REAL_VARIABLE_UNIT_MISMATCH")
        if role == "outcome":
            need(variable["unit"] == z["outcome_unit"], "MM_REAL_VARIABLE_UNIT_MISMATCH")
        if role == "time":
            need(variable["unit"] == z["time_unit"], "MM_REAL_VARIABLE_UNIT_MISMATCH")
        measured, available = variable["measured_at"], variable["available_at"]
        if role in ("subject", "time", "event"):
            need(measured is None and available is None, "MM_REAL_VARIABLE_TIME_INVALID")
        else:
            need(number(measured) and number(available) and measured <= available <= st["analysis_as_of"], "MM_REAL_VARIABLE_AVAILABILITY_REQUIRED")
            if role == "covariate":
                need(available <= z["covariate_latest_time"], "MM_REAL_PRETREATMENT_COVARIATES_REQUIRED")
            else:
                target = z[{"exposure": "exposure_time", "mediator": "mediator_time", "outcome": "outcome_time"}[role]]
                need(measured == target and (role != "exposure" or available == target), "MM_REAL_VARIABLE_TIME_INVALID")
                if role == "mediator":
                    need(available < z["outcome_time"], "MM_REAL_MEDIATOR_AVAILABILITY_INVALID")
    ids = [row["subject_id"] for row in rows]
    need(len(ids) == len(set(ids)) and all(value.strip() for value in ids), "MM_REAL_UNIQUE_SUBJECTS_REQUIRED")
    for value in ids:
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError:
            raise AdmissionError("MM_REAL_UNIQUE_SUBJECTS_REQUIRED") from None
    need({row["exposure"] for row in rows} == {0, 1}, "MM_REAL_BOTH_BINARY_ARMS_REQUIRED")
    for row in rows:
        need(number(row["exposure"]) and row["exposure"] in (0, 1), "MM_REAL_BINARY_EXPOSURE_REQUIRED")
        need(len(row["covariates"]) == len(cv), "MM_REAL_COVARIATE_WIDTH_INVALID")
        for role in ("mediator", "outcome", "time", "event"):
            value = row[role]
            need(value is None if fs[role] is None else value is None or number(value), "MM_REAL_ENDPOINT_TYPE_INVALID")
        for name, value in zip(cv, row["covariates"]):
            need(value is None or isinstance(value, str) and value in categories[name]["levels"] if name in categories else value is None or number(value), "MM_REAL_COVARIATE_TYPE_OR_LEVEL_INVALID")
        if method == METHODS[1]:
            need(number(row["outcome"]) and row["outcome"] in (0, 1), "MM_REAL_BINARY_ENDPOINT_REQUIRED")
        if method == METHODS[2]:
            need(number(row["time"]) and row["time"] > 0 and row["time"] + st["time_origin"] <= st["analysis_as_of"] and
                 number(row["event"]) and row["event"] in (0, 1), "MM_REAL_SURVIVAL_ENDPOINT_INVALID")
    if method == METHODS[2]:
        need(any(row["event"] == 1 for row in rows), "MM_REAL_NO_EVENTS")
        times = options["risk_times"]
        need(times[0] == 0 and all(a < b for a, b in zip(times, times[1:])), "MM_REAL_RISK_TIMES_INVALID")
    return metadata, project


def _transport(request, project, resource_budget):
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8-sig"))
    for relative, digest in manifest["unchanged_numerical_sources_sha256"].items():
        path = (HERE / relative).resolve()
        need(path.is_relative_to(CORE.parent.parent) and sha(path) == digest, "MM_REAL_NUMERICAL_SOURCE_DRIFT")
    lock = json.loads((CORE / "runtime-lock.json").read_text(encoding="utf-8-sig"))
    base = (project / ".ye1-privacy/private/module-runs/mediation_matching").resolve()
    need(base.is_relative_to(project), "MM_REAL_PRIVATE_WORK_OUTSIDE_PROJECT")
    base.mkdir(parents=True, exist_ok=True)
    work = base / uuid.uuid4().hex
    work.mkdir()
    input_path, output = work / "request.json", work / "response.json"
    private_request = {**request, "resource_budget": resource_budget}
    raw = (json.dumps(private_request, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    need(len(raw) <= resource_budget["max_input_bytes"], "RESOURCE_INPUT_BYTES_BUDGET_EXCEEDED")
    input_path.write_bytes(raw)
    env = {**os.environ, "R_LIBS": os.pathsep.join(lock["r_libraries"]), "R_LIBS_USER": os.pathsep.join(lock["r_libraries"])}
    with (work / "transport.log").open("xb") as stream:
        run = subprocess.run([lock["rscript"], "--vanilla", str(HERE / "worker.R"), str(CORE), str(input_path), str(output), sha(input_path)],
                             cwd=work, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
    need(run.returncode == 0 and output.is_file() and output.stat().st_size <= 32 * 1024 * 1024, "MM_REAL_TRANSPORT_FAILED")
    value = json.loads(output.read_text(encoding="utf-8-sig"))
    need(sha(input_path) == hashlib.sha256(raw).hexdigest(), "MM_REAL_REQUEST_BYTES_CHANGED")
    return value


def analyze(request, context):
    stage, metadata = "context", None
    try:
        metadata, project = validate_request(request, context)
        stage = "transport"
        value = _transport(request, project, _resource_limits(context, request["method_id"]))
        need(set(value) == {"public_record", "private_record"}, "MM_REAL_TRANSPORT_RESPONSE_INVALID")
        stage = "analysis"
        record = value["public_record"]
        need(record["method_id"] == request["method_id"], "MM_REAL_RESPONSE_METHOD_MISMATCH")
        ok = record["status"] != "unavailable"
        response = {"api_version": "clinical-admitted-module-response@1.0", "ok": ok,
                    "reason_code": None if ok else record["reason_code"], "provenance": metadata,
                    "diagnostics": {"module_id": "mediation_matching", "stage": stage,
                                    "numerical_owner": "unchanged mediation_matching/R/provider.R", "causal_assumptions_verified": False},
                    **value}
        _validate(response, "response.schema.json", "MM_REAL_RESPONSE_INVALID")
        return response
    except Exception as error:
        code = getattr(error, "code", "MM_REAL_EXECUTION_REJECTED")
        if not isinstance(code, str) or re.fullmatch(r"[A-Z][A-Z0-9_]+", code) is None:
            code = "MM_REAL_EXECUTION_REJECTED"
        return {"api_version": "clinical-admitted-module-response@1.0", "ok": False, "reason_code": code,
                "provenance": metadata, "diagnostics": {"module_id": "mediation_matching", "stage": stage,
                "numerical_owner": "unchanged mediation_matching/R/provider.R", "causal_assumptions_verified": False},
                "public_record": None, "private_record": None}


def project(response, output_dir, context, request=None):
    """Native private tables/figures only; root publishes global provenance.

    The original bound request is required explicitly. Context private fields are
    never inspected, and no model/private R object is decoded for plotting.
    """
    need(request is not None, "MM_REAL_PROJECTION_REQUEST_REQUIRED")
    metadata, project_root = validate_request(request, context)
    _validate(response, "response.schema.json", "MM_REAL_RESPONSE_INVALID")
    need(response["ok"] is True and response["public_record"] is not None and
         response["public_record"]["status"] in ("completed", "partial"), "MM_REAL_PROJECTION_REQUIRES_COMPUTED_RESULT")
    record = response["public_record"]
    need(record["method_id"] == request["method_id"] and response["provenance"] == metadata and
         record["semantics"] == request["payload"]["spec"]["semantics"] and record["options"] == request["payload"]["spec"]["options"],
         "MM_REAL_PROJECTION_BINDING_MISMATCH")
    output = Path(output_dir).resolve()
    need(output != project_root and output.is_relative_to(project_root) and not output.exists() and output.parent.is_dir(),
         "MM_REAL_FRESH_PROJECTION_REQUIRED")
    need(any(part in ("private", ".ye1-privacy") for part in output.relative_to(project_root).parts[:-1]),
         "MM_REAL_PRIVATE_PROJECTION_REQUIRED")
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8-sig"))
    for relative, digest in manifest["projection_sources_sha256"].items():
        path = (HERE / relative).resolve()
        need(path.is_relative_to(CORE.parent.parent) and sha(path) == digest, "MM_REAL_PROJECTION_SOURCE_DRIFT")
    lock = json.loads((CORE / "runtime-lock.json").read_text(encoding="utf-8-sig"))
    work_base = (project_root / ".ye1-privacy/private/mm-proj").resolve()
    need(work_base.is_relative_to(project_root), "MM_REAL_PRIVATE_WORK_OUTSIDE_PROJECT")
    work_base.mkdir(parents=True, exist_ok=True)
    work = work_base / uuid.uuid4().hex
    work.mkdir()
    wire = {"public_record": record, "provenance": metadata,
            "disclosure_label": metadata["data_origin"].upper() + " | " + metadata["task_purpose"] + " | review=pending",
            "source_public_record_sha256": hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()}
    request_path = work / "projection-request.json"
    request_path.write_text(json.dumps(wire, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    env = {**os.environ, "R_LIBS": os.pathsep.join(lock["r_libraries"]), "R_LIBS_USER": os.pathsep.join(lock["r_libraries"])}
    with (work / "projection.log").open("xb") as log:
        done = subprocess.run([lock["rscript"], "--vanilla", str(HERE / "project_worker.R"), str(CORE), str(request_path), str(output), sha(request_path)],
                              cwd=CORE, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    need(done.returncode == 0 and (output / "projection-manifest.json").is_file(), "MM_REAL_PROJECTION_FAILED")
    result = json.loads((output / "projection-manifest.json").read_text(encoding="utf-8-sig"))
    need(result["provenance"] == metadata and result["numerical_execution_count"] == 0 and
         result["source_public_record_sha256"] == hashlib.sha256(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
         "MM_REAL_PROJECTION_BINDING_MISMATCH")
    for item in result["artifacts"]:
        path = (output / item["relative_path"]).resolve()
        need(path.is_relative_to(output) and "private" not in path.relative_to(output).parts and path.is_file() and sha(path) == item["sha256"],
             "MM_REAL_PROJECTED_ARTIFACT_HASH_MISMATCH")
    return result
