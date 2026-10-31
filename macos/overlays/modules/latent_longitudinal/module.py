"""Local module API/CLI. Not a second shared clinical task dispatcher."""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
if __package__:
    from .contracts import (VERSION, CLUSTER, GROWTH, FORMAL, Blocked, need, digest,
                            validate_request, frozen_definition, strict_json)
else:
    from contracts import (VERSION, CLUSTER, GROWTH, FORMAL, Blocked, need, digest,
                           validate_request, frozen_definition, strict_json)

ROOT = Path(__file__).resolve().parent
RESULT_VERSION = "latent-longitudinal-result/1"
MODEL_VERSION = "latent-longitudinal-frozen/1"
_LOCAL_RUNTIME = json.loads((ROOT.parents[1]/"integration/core/runtime-lock.json").read_text(encoding="utf-8-sig"))
DEFAULT_RUNTIME = {"rscript":_LOCAL_RUNTIME["rscript"],"r_libraries":_LOCAL_RUNTIME["r_libraries"]}
SOURCE_FILES = ["__init__.py", "module.py", "contracts.py", "clustering.py", "growth.py", "growth_engine.R",
                "artifacts.py", "latent_longitudinal_adapter.R", "api.py", "schema_tools.py"]


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    files = SOURCE_FILES + sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/"schemas").glob("*.schema.json"))
    return {p: sha_file(ROOT/p) for p in files}


def runtime_probe(runtime=None):
    runtime = runtime or DEFAULT_RUNTIME
    result = {"python": platform.python_version(), "platform": platform.system(),
              "executable": str(Path(sys.executable)), "packages": {}, "R": None, "r_packages": {},
              "rscript": runtime["rscript"], "r_libraries": runtime["r_libraries"]}
    for name in ["numpy", "scipy", "pandas", "scikit-learn", "matplotlib", "threadpoolctl", "statsmodels", "pytest"]:
        try:
            result["packages"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][name] = None
    libs = json.dumps(runtime["r_libraries"])
    # Paths are JSON strings, parsed as JSON, never concatenated into shell code.
    r_script = ".libPaths(c(" + ",".join(json.dumps(x) for x in runtime["r_libraries"]) + ",.libPaths()))\n"
    r_script += """
pkgs <- c('jsonlite','digest','nlme','lme4','mclust','lcmm','tidyLPA','flexmix','marqLevAlg',
          'mvtnorm','spacefillr','doParallel','foreach','iterators','numDeriv','Rcpp','survival','parallel','codetools')
out <- list(R=as.character(getRversion()), packages=list(), paths=list())
for(p in pkgs) { ok <- requireNamespace(p,quietly=TRUE); out$packages[p] <- list(if(ok)as.character(packageVersion(p))else NULL)
  out$paths[p] <- list(if(ok)find.package(p)else NULL) }
if(requireNamespace('jsonlite',quietly=TRUE)) cat(jsonlite::toJSON(out,auto_unbox=TRUE,null='null'))
"""
    env = os.environ.copy()
    for key in ["LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MONETARY", "LC_TIME", "LANG"]:
        env.pop(key, None)
    try:
        proc = subprocess.run([runtime["rscript"], "--vanilla", "-"], input=r_script, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
        if proc.returncode == 0:
            parsed = json.loads(proc.stdout)
            result["R"] = parsed["R"]
            result["r_packages"] = parsed["packages"]
            result["r_package_paths"] = parsed["paths"]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        pass
    bound_files = {"python_executable": sha_file(sys.executable)}
    if Path(runtime["rscript"]).is_file():
        bound_files["rscript_executable"] = sha_file(runtime["rscript"])
    for package in ["nlme", "jsonlite"]:
        path = result.get("r_package_paths", {}).get(package)
        if path:
            native = "libs/"+package+".so" if platform.system()=="Darwin" else "libs/x64/"+package+".dll"
            for suffix in ["DESCRIPTION", "R/"+package+".rdb", "R/"+package+".rdx", native]:
                p = Path(path)/suffix
                if p.is_file():
                    bound_files["R/"+package+"/"+suffix] = sha_file(p)
    import sklearn.cluster._kmeans as km
    import sklearn.mixture._gaussian_mixture as gm
    bound_files["sklearn/_kmeans.py"] = sha_file(km.__file__)
    bound_files["sklearn/_gaussian_mixture.py"] = sha_file(gm.__file__)
    result["files_sha256"] = bound_files
    return result


def runtime_binding(probe, method):
    # Test-only/reference packages and library locations are not numerical inputs.
    relevant = ["numpy", "scipy", "scikit-learn", "threadpoolctl"] if method in CLUSTER else []
    r_relevant = ["nlme", "jsonlite"] if method in GROWTH else []
    hashes = {k: v for k, v in probe["files_sha256"].items()
              if (method in CLUSTER and (k.startswith("sklearn/") or k == "python_executable"))
              or (method in GROWTH and (k.startswith("R/") or k == "rscript_executable"))}
    return {"python": probe["python"], "platform": probe["platform"],
            "packages": {k: probe["packages"].get(k) for k in relevant},
            "R": probe["R"] if method in GROWTH else None,
            "r_packages": {k: probe["r_packages"].get(k) for k in r_relevant}, "files_sha256": hashes}


def freeze(method, spec, model, transform, rows, probe, admission=None):
    salt = secrets.token_hex(16)
    result = {"schema_version": MODEL_VERSION if admission is None else "latent-longitudinal-admitted-frozen/1", "method_id": method,
              "definition": frozen_definition(spec), "cohort_id": spec["cohort_id"],
              "provider_hash": digest(source_hashes()), "runtime": runtime_binding(probe, method),
              "test_only": True if admission is None else admission.test_only, "scientific_review": "pending", "export_status": "local_only",
              "model": model, "transform": transform, "subject_hash_salt": salt,
              "development_id_digests": sorted({digest([salt, r[spec["subject_id"]]]) for r in rows})}
    if admission is not None:
        need(admission.scientific_review == "pending", "ADMISSION_REVIEW_MUST_REMAIN_PENDING")
        result.update(data_origin=admission.data_origin, task_purpose=admission.task_purpose)
    result["sha256"] = digest(result)
    return result


def load_frozen(reference, method, spec, rows, probe, admission=None):
    path = Path(reference["path"])
    need(path.is_file() and path.stat().st_size <= 8*1024*1024, "MODEL_FILE_UNAVAILABLE_OR_OVERSIZED")
    need(sha_file(path) == reference["sha256"], "MODEL_FILE_SHA256_MISMATCH")
    frozen = strict_json(path.read_text(encoding="utf-8"))
    checksum = frozen.pop("sha256", None)
    need(checksum == digest(frozen), "MODEL_CONTENT_SHA256_MISMATCH")
    frozen["sha256"] = checksum
    version = MODEL_VERSION if admission is None else "latent-longitudinal-admitted-frozen/1"
    need(frozen["schema_version"] == version and frozen["method_id"] == method, "FROZEN_METHOD_MISMATCH")
    need(frozen["provider_hash"] == digest(source_hashes()), "FROZEN_SOURCE_DRIFT")
    need(frozen["runtime"] == runtime_binding(probe, method), "FROZEN_RUNTIME_DRIFT")
    if admission is None:
        need(frozen["test_only"] is True and frozen["scientific_review"] == "pending"
             and frozen["export_status"] == "local_only", "FROZEN_CLASSIFICATION_MISMATCH")
    else:
        need(admission.scientific_review == "pending" and frozen["test_only"] is admission.test_only
             and frozen.get("data_origin") == admission.data_origin and frozen.get("task_purpose") == admission.task_purpose
             and frozen["scientific_review"] == "pending" and frozen["export_status"] == "local_only", "FROZEN_CLASSIFICATION_MISMATCH")
    need(frozen["definition"] == frozen_definition(spec), "FROZEN_DEFINITION_MISMATCH")
    need(frozen["cohort_id"] != spec["cohort_id"], "EXTERNAL_COHORT_MUST_DIFFER")
    external = {digest([frozen["subject_hash_salt"], r[spec["subject_id"]]]) for r in rows}
    need(not external & set(frozen["development_id_digests"]), "EXTERNAL_SUBJECT_OVERLAP")
    return frozen


def compute_local(request, private, runtime=None, probe=None):
    """Single numerical orchestration, with private file transport for R only."""
    private = Path(private)
    need(not private.exists(), "OUTPUT_ALREADY_EXISTS")
    private.mkdir(parents=True)
    runtime = runtime or DEFAULT_RUNTIME
    probe = probe or runtime_probe(runtime)
    public = {"schema_version": RESULT_VERSION, "method_id": request.get("method_id"),
              "operation": request.get("operation"), "status": "blocked", "reason_code": None,
              "test_only": True, "scientific_review": "pending", "export_status": "local_only",
              "provider": {"id": "latent_longitudinal", "code_hash": digest(source_hashes())},
              "binding": {"runtime_hash": digest(probe)}, "definition": {},
              "analysis": {}, "warnings": [], "tables": [], "figures": [], "private_artifacts": []}
    try:
        validate_request(request)
        public["definition"] = copy.deepcopy(request["spec"])
        public["binding"]["request_hash"] = digest(request)
        (private/"request.json").write_text(json.dumps(request, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        method, spec, op, rows = (request[k] for k in ["method_id", "spec", "operation", "rows"])
        if method in FORMAL:
            package = "mclust" if method == "latent.profile.gaussian" else "lcmm"
            available = probe["r_packages"].get(package) is not None
            need(False, "FORMAL_PROVIDER_NOT_IMPLEMENTED" if available else "FORMAL_DEPENDENCY_UNAVAILABLE",
                 {"availability": [{"method_id": method, "required_provider": package,
                                    "installed_version": probe["r_packages"].get(package),
                                    "implementation": "not_implemented", "fitted": False}],
                  "no_fallback": True, "minimum_primary_package": package})
        frozen = load_frozen(request["model_ref"], method, spec, rows, probe) if op != "train" else None
        if method in CLUSTER:
            if __package__:
                from .clustering import analyze
            else:
                from clustering import analyze
            record, model, transform, individual = analyze(rows, spec, method, frozen)
            record["preprocessing"] = [{"feature": f["name"], "unit": f["unit"], "median": transform["median"][i],
                                        "mean": transform["mean"][i], "scale": transform["scale"][i],
                                        "fit_scope": "training_only"} for i, f in enumerate(spec["features"])]
        else:
            need(probe["r_packages"].get("nlme") is not None and probe["r_packages"].get("jsonlite") is not None,
                 "GROWTH_DEPENDENCY_UNAVAILABLE")
            if __package__:
                from .growth import analyze
            else:
                from growth import analyze
            record, model, transform, individual = analyze(rows, spec, op, runtime, private, frozen)
        public["analysis"] = record
        public["warnings"] = record.pop("warnings", [])
        if op == "train":
            frozen = freeze(method, spec, model, transform, rows, probe)
            model_path = private/"model.json"
            model_path.write_text(json.dumps(frozen, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            public["private_artifacts"].append({"kind": "frozen_model", "path": "private/model.json",
                                                "sha256": sha_file(model_path), "contains_local_identifiers": "hashed"})
        elif frozen is not None:
            public["binding"]["frozen_model_sha256"] = request["model_ref"]["sha256"]
        if individual:
            path = private/"individual-results.json"
            path.write_text(json.dumps(individual, allow_nan=False), encoding="utf-8")
            public["private_artifacts"].append({"kind": "individual_results", "path": "private/individual-results.json",
                                                "sha256": sha_file(path), "contains_local_identifiers": "row_positions"})
        public["status"] = "complete"
    except Blocked as error:
        public["reason_code"] = error.code
        public["analysis"] = error.diagnostics
    except (ValueError, KeyError, TypeError, OSError, subprocess.TimeoutExpired) as error:
        public["status"] = "failed"
        public["reason_code"] = "MODULE_EXECUTION_ERROR"
        public["analysis"] = {"error_type": type(error).__name__}
    (private/"runtime-probe.json").write_text(json.dumps(probe, indent=2), encoding="utf-8")
    return public


def run(request, output_dir, runtime=None, probe=None):
    """Standalone development harness; shared integration uses api.analyze/project."""
    output = Path(output_dir)
    need(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    public = compute_local(request, output/"private", runtime, probe)
    if __package__:
        from .artifacts import write_artifacts
    else:
        from artifacts import write_artifacts
    try:
        public = write_artifacts(output, public)
    except (OSError, ValueError, RuntimeError) as error:
        if public["status"] == "complete":
            public["status"] = "partial"
            public["reason_code"] = "ARTIFACT_GENERATION_FAILED"
        public["warnings"].append("ARTIFACT_GENERATION_FAILED")
        public["artifact_error_type"] = type(error).__name__
    (output/"result.json").write_text(json.dumps(public, indent=2, allow_nan=False, ensure_ascii=False), encoding="utf-8")
    return public


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--probe":
        Path(sys.argv[2]).write_text(json.dumps(runtime_probe(), indent=2), encoding="utf-8")
        return 0
    if len(sys.argv) not in {3, 4}:
        print("Usage: module.py REQUEST.json NEW_OUTPUT_DIRECTORY [RUNTIME.json]")
        return 2
    request = strict_json(Path(sys.argv[1]).read_text(encoding="utf-8-sig"))
    runtime = strict_json(Path(sys.argv[3]).read_text(encoding="utf-8-sig")) if len(sys.argv) == 4 else None
    result = run(request, sys.argv[2], runtime)
    # Only aggregate status is printed, including for failures.
    print(json.dumps({"status": result["status"], "reason_code": result["reason_code"], "method_id": result["method_id"]}))
    return 0 if result["status"] == "complete" else 3


if __name__ == "__main__":
    sys.exit(main())
