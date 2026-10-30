"""Source-aware transport after the root has admitted a V1 request.

No registration, source discovery, consent decision, estimator or public export
lives here. The five existing numerical owners remain the only fit/score paths.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import subprocess

from .. import api, clustering, formal_provider, formal_runtime, growth, module
from ..contracts import CLUSTER, FORMAL, GROWTH, METHODS, Blocked, digest, exact, fields, need, strict_json
from ..schema_tools import validate

ROOT = Path(__file__).resolve().parent


def schema_validate(value, name):
    path = ROOT / "schemas" / (name + ".schema.json")
    need(path.is_file(), "ADMITTED_MODULE_SCHEMA_MISSING")
    validate(value, json.loads(path.read_text(encoding="utf-8")))


def context_metadata(context):
    """Copy the root's independent labels; never infer origin from purpose."""
    result = {name: getattr(context, name, None) for name in
              ["data_origin", "task_purpose", "test_only", "scientific_review"]}
    need(result["data_origin"] in {"real", "synthetic"}
         and result["task_purpose"] in {"engineering_test", "research_analysis"}
         and type(result["test_only"]) is bool and result["scientific_review"] == "pending",
         "ADMITTED_CONTEXT_METADATA_INVALID")
    return result


def validate_spec(method, operation, payload):
    spec = payload["spec"]
    need(bool(spec["cohort_id"].strip()), "IDENTITY_DEFINITION_INVALID")
    names = [spec["subject_id"]]
    if method in CLUSTER:
        fields(spec["features"])
        need(min(spec["candidate_k"]) >= (2 if method.endswith("kmeans") else 1), "CANDIDATE_K_INVALID")
        need(spec["selection"] == ("silhouette" if method.endswith("kmeans") else "bic"), "SELECTION_MISMATCH")
        need(spec["covariance"] in ({"none"} if method.endswith("kmeans") else {"diag", "full"}), "COVARIANCE_UNSUPPORTED")
        split = spec["split"]
        names += [split["field"]] + [f["name"] for f in spec["features"]]
    elif method in GROWTH:
        fields([{"name": spec["time"]["name"], "unit": spec["time"]["unit"]}, spec["outcome"]])
        names += [spec["time"]["name"], spec["outcome"]["name"]] + [f["name"] for f in spec["covariates"]]
        if spec["covariates"]:
            fields(spec["covariates"])
        need(spec["time"]["scale"] > 0, "TIME_TRANSFORM_INVALID")
    else:
        d = spec["definition"]
        split = spec["split"]
        need(1 in spec["candidate_k"], "FORMAL_ONE_CLASS_BASELINE_REQUIRED")
        names += [split["field"]]
        if method == "latent.profile.gaussian":
            fields(d["indicators"])
            names += [f["name"] for f in d["indicators"]]
        else:
            fields([{"name": d["time"]["name"], "unit": d["time"]["unit"]}, d["outcome"]])
            names += [d["time"]["name"], d["outcome"]["name"]]
            need(d["time"]["scale"] > 0, "TIME_TRANSFORM_INVALID")
            need((d["family"] == "lcga" and d["random"] == "none") or
                 (d["family"] == "growth_mixture" and d["random"] in {"intercept", "intercept_slope"}),
                 "FORMAL_TRAJECTORY_DEFINITION_UNSUPPORTED")
    if method not in GROWTH:
        need(bool(split["train"]) and bool(split["holdout"]) and split["train"] != split["holdout"], "SPLIT_INVALID")
    need(len(names) == len(set(names)), "ROLE_COLLISION")
    for row in payload["data"]:
        need(isinstance(row.get(spec["subject_id"]), str) and bool(row[spec["subject_id"]].strip()), "SUBJECT_ID_INVALID")


def formal_semantics(payload, method, operation):
    """The existing formal semantic guards, independent of its test-only shell."""
    spec = payload["spec"]
    d, sem, split = spec["definition"], payload["semantics"], spec["split"]
    profile = method == "latent.profile.gaussian"
    need(sem["subject_key"] == spec["subject_id"] and sem["missing_policy"] == d["missing"],
         "SEMANTIC_IDENTITY_OR_MISSINGNESS_MISMATCH")
    expected = {spec["subject_id"]: ("id", "subject_id", "1")}
    if operation == "train":
        expected[split["field"]] = ("category", "partition", "1")
    if profile:
        expected.update({f["name"]: ("number", "indicator", f["unit"]) for f in d["indicators"]})
        need(sem["grain"] == "subject" and sem["record_keys"] == [spec["subject_id"]], "CROSS_SECTIONAL_GRAIN_MISMATCH")
        time = {"unit": None, "origin": None, "scale": None, "measurement_time_field": None, "availability": "declared_per_field"}
    else:
        expected.update({d["time"]["name"]: ("number", "time", d["time"]["unit"]),
                         d["outcome"]["name"]: ("number", "outcome", d["outcome"]["unit"])})
        need(sem["grain"] == "subject_time" and sem["record_keys"] == [spec["subject_id"], d["time"]["name"]], "LONGITUDINAL_GRAIN_MISMATCH")
        time = {k: d["time"][k] for k in ["unit", "origin", "scale"]} | {"measurement_time_field": d["time"]["name"], "availability": "row_time"}
    need(sem["time"] == time, "TIME_SEMANTICS_MISMATCH")
    observed = sem["fields"]
    need(len(observed) == len(expected) and len({f["name"] for f in observed}) == len(observed), "FIELD_ROLE_DECLARATION_MISMATCH")
    for f in observed:
        need(expected.get(f["name"]) == (f["dtype"], f["role"], f["unit"]), "FIELD_ROLE_DECLARATION_MISMATCH")
        if f["role"] in {"subject_id", "partition"}:
            need(f["measured_at"] is None and f["available_at"] is None, "IDENTITY_TIME_NOT_APPLICABLE")
        elif profile:
            need(type(f["measured_at"]) in [int, float] and type(f["available_at"]) in [int, float]
                 and f["available_at"] >= f["measured_at"], "CROSS_SECTIONAL_FIELD_TIMING_INVALID")
        else:
            need(f["measured_at"] == "row_time" and f["available_at"] == "row_time", "LONGITUDINAL_FIELD_TIMING_MISMATCH")
    need(all(set(row) == set(expected) for row in payload["data"]), "UNDECLARED_OR_MISSING_DATA_COLUMN")


def validate_request(request, context):
    schema_validate(request, "request")
    method, operation, payload = (request[name] for name in ["method_id", "operation", "payload"])
    metadata = context_metadata(context)
    need(payload["test_only"] is metadata["test_only"], "PAYLOAD_CONTEXT_CLASSIFICATION_MISMATCH")
    reference = payload["model_ref"]
    need((reference is None) == (operation == "train"), "MODULE_FROZEN_MODEL_BINDING_REQUIRED")
    need(request["bindings"]["model_sha256"] == (reference["sha256"] if reference else None), "MODULE_MODEL_BINDING_MISMATCH")
    validate_spec(method, operation, payload)
    if method in FORMAL:
        formal_semantics(payload, method, operation)
    else:
        api.check_semantics(payload, method, operation)
    project = Path(context.project_root).resolve()
    work = Path(payload["work_dir"]).resolve()
    need(work != project and work.is_relative_to(project), "ADMITTED_WORK_DIRECTORY_OUTSIDE_PROJECT")
    need(not work.exists(), "OUTPUT_ALREADY_EXISTS")
    return metadata


def model_reference_metadata(payload):
    reference = payload["model_ref"]
    if reference is None:
        return None
    path = Path(reference["path"])
    need(path.is_file() and path.stat().st_size <= 8 * 1024 * 1024, "MODEL_FILE_UNAVAILABLE_OR_OVERSIZED")
    need(module.sha_file(path) == reference["sha256"], "MODEL_FILE_SHA256_MISMATCH")
    frozen = strict_json(path.read_text(encoding="utf-8"))
    schema_validate(frozen, "frozen")
    return {name: frozen[name] for name in ["data_origin", "task_purpose", "test_only", "scientific_review"]}


def legacy_compute(method, operation, payload, probe, context):
    work = Path(payload["work_dir"])
    work.mkdir(parents=True)
    rows, spec = payload["data"], payload["spec"]
    (work / "request.json").write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    frozen = module.load_frozen(payload["model_ref"], method, spec, rows, probe, admission=context) if operation != "train" else None
    if method in CLUSTER:
        record, model, transform, individual = clustering.analyze(rows, spec, method, frozen)
        record["preprocessing"] = [{"feature": f["name"], "unit": f["unit"], "median": transform["median"][i],
            "mean": transform["mean"][i], "scale": transform["scale"][i], "fit_scope": "training_only"}
            for i, f in enumerate(spec["features"])]
    else:
        need(probe["r_packages"].get("nlme") is not None and probe["r_packages"].get("jsonlite") is not None,
             "GROWTH_DEPENDENCY_UNAVAILABLE")
        record, model, transform, individual = growth.analyze(rows, spec, operation, module.DEFAULT_RUNTIME, work, frozen)
    warnings = record.pop("warnings", [])
    model_text = model_sha = None
    if operation == "train":
        frozen = module.freeze(method, spec, model, transform, rows, probe, admission=context)
        schema_validate(frozen, "frozen")
        model_text = json.dumps(frozen, ensure_ascii=False, allow_nan=False)
        path = work / "model.json"
        path.write_text(model_text, encoding="utf-8")
        model_sha = module.sha_file(path)
    (work / "individual-results.json").write_text(json.dumps(individual, allow_nan=False), encoding="utf-8")
    (work / "runtime-probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    return record, warnings, {"model_json": model_text, "model_sha256": model_sha, "individual_results": individual}


def analyze(request, context):
    response = {"api_version": "clinical-module-response@1.0", "ok": False, "reason_code": None,
                "diagnostics": {"stage": "validation", "details": {}}, "public_record": None, "private_record": None}
    stage = "validation"
    try:
        # The root owns source/use/export admission. This must precede schema,
        # model-file reads, probes, private directory creation and every fit.
        require = getattr(context, "require_request", None)
        need(callable(require), "ROOT_ADMISSION_CONTEXT_REQUIRED")
        try:
            require(request.get("method_id"), request.get("operation"), request.get("payload"))
        except Blocked:
            raise
        except Exception as error:
            code = getattr(error, "code", getattr(error, "reason_code", "ROOT_ADMISSION_REJECTED"))
            raise Blocked(code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code) else "ROOT_ADMISSION_REJECTED") from None
        metadata = validate_request(request, context)
        method, operation, payload = (request[name] for name in ["method_id", "operation", "payload"])
        model_source = model_reference_metadata(payload)
        stage = "analysis"
        if method in FORMAL:
            probe = formal_runtime.probe()
            need(all(probe["r_packages"].get(name) for name in formal_runtime.PACKAGES), "FORMAL_DEPENDENCY_UNAVAILABLE")
            analysis, warnings, private, details = formal_provider.analyze(method, operation, payload, probe, admission=context)
            if private["model_json"] is not None:
                schema_validate(strict_json(private["model_json"]), "frozen")
            provider_hash, runtime_hash = digest(formal_runtime.source_hashes()), digest(formal_runtime.binding(probe))
        else:
            probe = module.runtime_probe()
            analysis, warnings, private = legacy_compute(method, operation, payload, probe, context)
            details = analysis.pop("diagnostics", {})
            provider_hash, runtime_hash = digest(module.source_hashes()), digest(module.runtime_binding(probe, method))
        prefix = "formal" if method in FORMAL else "legacy"
        public = {"method_id": method, "operation": operation, **metadata, "model_source": model_source,
                  "admitted_request_sha256": digest(request), "request_bindings": copy.deepcopy(request["bindings"]),
                  "export_status": "local_only", "definition": copy.deepcopy(payload["spec"]),
                  "analysis": analysis, "warnings": warnings}
        diagnostics = {"stage": "complete", "provider_hash": provider_hash, "runtime_hash": runtime_hash, "details": details}
        schema_validate(public, prefix + ".public_record")
        schema_validate(private, prefix + ".private_record")
        schema_validate(diagnostics, prefix + ".diagnostics")
        response.update(ok=True, public_record=public, private_record=private, diagnostics=diagnostics)
        schema_validate(response, "response")
    except Blocked as error:
        response.update(ok=False, reason_code=error.code, diagnostics={"stage": stage, "details": {}}, public_record=None, private_record=None)
    except (AttributeError, KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
        response.update(ok=False, reason_code="ADMITTED_MODULE_EXECUTION_ERROR", diagnostics={"stage": "execution", "details": {}}, public_record=None, private_record=None)
    return response


def project(response, output_dir, context, request=None):
    """Render existing aggregate results in a fresh private directory; no fit."""
    request = request if request is not None else getattr(context, "bound_request", None)
    require = getattr(context, "require_request", None)
    need(callable(require) and isinstance(request, dict), "PROJECTION_BOUND_REQUEST_REQUIRED")
    try:
        require(request.get("method_id"), request.get("operation"), request.get("payload"))
    except Blocked:
        raise
    except Exception as error:
        code = getattr(error, "code", getattr(error, "reason_code", "ROOT_ADMISSION_REJECTED"))
        raise Blocked(code if isinstance(code, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,127}", code) else "ROOT_ADMISSION_REJECTED") from None
    schema_validate(request, "request")
    schema_validate(response, "response")
    need(response["ok"] is True, "CANNOT_PROJECT_BLOCKED_MODULE")
    metadata = context_metadata(context)
    public = response["public_record"]
    need(public["admitted_request_sha256"] == digest(request) and public["request_bindings"] == request["bindings"]
         and public["method_id"] == request["method_id"] and public["operation"] == request["operation"]
         and public["definition"] == request["payload"]["spec"], "PROJECTION_REQUEST_BINDING_MISMATCH")
    need(all(public[name] == value and (type(public[name]) is bool) == (type(value) is bool)
             for name, value in metadata.items()), "PROJECTION_CONTEXT_CLASSIFICATION_MISMATCH")
    need(request["payload"]["test_only"] is context.test_only, "PAYLOAD_CONTEXT_CLASSIFICATION_MISMATCH")
    project_root = Path(context.project_root).resolve()
    out = Path(output_dir).resolve()
    need(out != project_root and out.is_relative_to(project_root), "PROJECTION_DIRECTORY_OUTSIDE_PROJECT")
    need("private" in {part.lower() for part in out.relative_to(project_root).parts[:-1]}, "PROJECTION_PRIVATE_DIRECTORY_REQUIRED")
    need(not out.exists(), "OUTPUT_ALREADY_EXISTS")
    if public["method_id"] in FORMAL:
        from ..formal_artifacts import write_artifacts
        return write_artifacts(copy.deepcopy(public), out, admission=context)
    from ..artifacts import write_artifacts
    rendered = copy.deepcopy(public)
    rendered.update(status="complete", reason_code=None, tables=[], figures=[])
    out.mkdir(parents=True)
    return write_artifacts(out, rendered, admission=context)
