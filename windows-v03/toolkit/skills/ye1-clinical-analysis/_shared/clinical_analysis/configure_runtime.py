"""Bind an explicitly selected local runtime without installing or fitting anything.

The checked-in requirements contain logical paths and previously fixed hashes.
Only ignored runtime outputs contain machine paths. Relative profile paths resolve
against the profile directory; relative command-line paths resolve against cwd.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REQUIREMENTS = ROOT / "runtime-requirements.json"
PROFILE_KEYS = {"python", "rscript", "r_libraries", "latent_r_library", "shap_library"}


class RuntimeBlocked(ValueError):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__(code + (": " + detail if detail else ""))


def need(condition, code, detail=""):
    if not condition:
        raise RuntimeBlocked(code, detail)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value, "CONFIG_DUPLICATE_JSON_KEY", key)
            value[key] = item
        return value
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs,
                          parse_constant=lambda value: (_ for _ in ()).throw(RuntimeBlocked("CONFIG_NONFINITE_JSON")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RuntimeBlocked("CONFIG_JSON_UNAVAILABLE_OR_INVALID", str(error)) from None


def bounded(root, relative):
    root = Path(root).resolve()
    value = Path(relative)
    need(not value.is_absolute() and ".." not in value.parts, "REQUIREMENT_PATH_INVALID", str(relative))
    path = (root / value).resolve()
    need(path.is_relative_to(root) and path.is_file(), "REQUIRED_FILE_UNAVAILABLE", str(relative))
    return path


def check_hash(path, expected, label):
    need(Path(path).is_file(), "RUNTIME_FILE_UNAVAILABLE", label)
    need(sha(path) == expected, "RUNTIME_BYTE_DRIFT", label)


def load_requirements(value=None):
    result = value if isinstance(value, dict) else read_json(value or REQUIREMENTS)
    need(result.get("schema_version") == "clinical-runtime-requirements@1.0", "REQUIREMENTS_VERSION_INVALID")
    return result


def _path(value, base, key, directory=False):
    need(isinstance(value, str) and bool(value.strip()) and not any(c in value for c in "\r\n\x00"),
         "CONFIG_PATH_REQUIRED", key)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = Path(base) / path
    path = path.resolve()
    need(path.is_dir() if directory else path.is_file(), "CONFIG_PATH_UNAVAILABLE", key)
    return path


def resolve_config(args):
    profile = {}
    profile_base = Path.cwd()
    if args.profile:
        profile_path = Path(args.profile).resolve()
        profile = read_json(profile_path)
        need(isinstance(profile, dict) and not set(profile) - PROFILE_KEYS, "CONFIG_PROFILE_FIELDS_INVALID")
        profile_base = profile_path.parent
    result = {}
    for key in ("python", "rscript", "latent_r_library", "shap_library"):
        supplied = getattr(args, key)
        value = supplied if supplied is not None else profile.get(key)
        base = Path.cwd() if supplied is not None else profile_base
        result[key] = _path(value, base, key, directory=key.endswith("library"))
    libraries = args.r_library if args.r_library is not None else profile.get("r_libraries")
    need(isinstance(libraries, list) and bool(libraries), "CONFIG_R_LIBRARIES_REQUIRED")
    base = Path.cwd() if args.r_library is not None else profile_base
    result["r_libraries"] = list(dict.fromkeys(_path(value, base, "r_libraries", directory=True) for value in libraries))
    return result


def _environment():
    env = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "R_LIBS", "R_LIBS_USER", "R_LIBS_SITE", "R_PROFILE", "R_PROFILE_USER",
                 "R_ENVIRON", "R_ENVIRON_USER", "LANG", "LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MONETARY", "LC_TIME"):
        env.pop(name, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run_json(command, *, input_text, env):
    try:
        result = subprocess.run(command, input=input_text, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60, env=env, cwd=ROOT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeBlocked("RUNTIME_PREFLIGHT_PROCESS_FAILED", type(error).__name__) from None
    need(result.returncode == 0, "RUNTIME_PREFLIGHT_PROCESS_FAILED", Path(command[0]).name)
    try:
        return json.loads(result.stdout.lstrip("\ufeff"))
    except json.JSONDecodeError:
        raise RuntimeBlocked("RUNTIME_PREFLIGHT_RESULT_INVALID", Path(command[0]).name) from None


PYTHON_PROBE = r'''
import hashlib, importlib, importlib.metadata as metadata, importlib.util, json, platform, sys
from pathlib import Path
request=json.load(sys.stdin)
result={'python':platform.python_version(),'platform':platform.system(),'executable':str(Path(sys.executable).resolve()),'packages':{},'files':{}}
for name,definition in request['packages'].items():
    imported=importlib.import_module(definition['import'])
    result['packages'][name]=metadata.version(definition['distribution'])
for name,module_name in request['files'].items():
    path=Path(importlib.util.find_spec(module_name).origin).resolve()
    result['files'][name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
result['shap_distributions']={d.metadata['Name'].lower():d.version for d in metadata.distributions(path=[request['shap_library']])}
print(json.dumps(result))
'''


R_PROBE = r'''
if(.Platform$OS.type=="windows")invisible(suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8")))
libraries<-strsplit(Sys.getenv("CLINICAL_RUNTIME_LIBRARIES"),"\n",fixed=TRUE)[[1L]]
.libPaths(c(libraries,.Library),include.site=FALSE)
if(!requireNamespace("jsonlite",quietly=TRUE))quit(status=3L)
packages<-strsplit(Sys.getenv("CLINICAL_RUNTIME_PACKAGES"),"\n",fixed=TRUE)[[1L]]
out<-list(R=as.character(getRversion()),r_home=normalizePath(R.home(),winslash="/",mustWork=TRUE),
 rscript_engine=normalizePath(file.path(R.home("bin"),"Rscript.exe"),winslash="/",mustWork=TRUE),
 libraries=as.list(.libPaths()),packages=list(),paths=list())
for(p in packages){
 ok<-suppressWarnings(requireNamespace(p,quietly=TRUE))
 if(!ok)quit(status=4L)
 out$packages[[p]]<-as.character(utils::packageVersion(p))
 out$paths[[p]]<-normalizePath(find.package(p),winslash="/",mustWork=TRUE)
}
cat(jsonlite::toJSON(out,auto_unbox=TRUE,null="null"))
'''


def python_preflight(config, requirements):
    request = {"packages": requirements["python_packages"],
               "files": {key: value["module"] for key, value in requirements["python_file_hashes"].items()},
               "shap_library": str(config["shap_library"])}
    result = run_json([str(config["python"]), "-I", "-B", "-c", PYTHON_PROBE],
                      input_text=json.dumps(request), env=_environment())
    need(result["python"] == requirements["lock_constants"]["python_versions"]["python"], "PYTHON_VERSION_DRIFT")
    need(result["platform"] == requirements["platform"], "PLATFORM_UNSUPPORTED")
    need(Path(result["executable"]).resolve() == config["python"], "PYTHON_EXECUTABLE_BINDING_MISMATCH")
    for name, definition in requirements["python_packages"].items():
        need(result["packages"].get(name) == definition["version"], "PYTHON_PACKAGE_VERSION_DRIFT", name)
    for name, definition in requirements["python_file_hashes"].items():
        need(result["files"][name]["sha256"] == definition["sha256"], "PYTHON_DEPENDENCY_BYTE_DRIFT", name)
    need(result["shap_distributions"] == requirements["shap"]["distributions"], "SHAP_DISTRIBUTION_DRIFT")
    return result


def r_preflight(config, requirements, *, latent=False):
    group = requirements["r_groups"]["latent" if latent else "core"]
    libraries = ([config["latent_r_library"]] if latent else []) + config["r_libraries"]
    env = _environment()
    env["CLINICAL_RUNTIME_LIBRARIES"] = "\n".join(str(p) for p in libraries)
    env["CLINICAL_RUNTIME_PACKAGES"] = "\n".join(group["versions"])
    result = run_json([str(config["rscript"]), "--vanilla", "-"], input_text=R_PROBE, env=env)
    need(result["R"] == requirements["lock_constants"]["versions"]["R"], "R_VERSION_DRIFT")
    allowed = {p.resolve() for p in libraries} | {(Path(result["r_home"]) / "library").resolve()}
    for name, version in group["versions"].items():
        need(result["packages"].get(name) == version, "R_PACKAGE_VERSION_DRIFT", name)
        package_path = Path(result["paths"][name]).resolve()
        need(package_path.parent in allowed, "R_PACKAGE_OUTSIDE_CONFIGURED_LIBRARIES", name)
    for name, hashes in group["files_sha256"].items():
        for relative, wanted in hashes.items():
            check_hash(bounded(result["paths"][name], relative), wanted, name + "/" + relative)
    engine = Path(result["rscript_engine"]).resolve()
    check_hash(engine, requirements["executables_sha256"]["rscript_engine"], "rscript_engine")
    for relative, wanted in requirements.get("r_engine_files_sha256", {}).items():
        check_hash(bounded(result["r_home"], relative), wanted, "R/" + relative)
    result["dependency_hashes"] = {str(bounded(result["paths"][name], relative)).replace("\\", "/"): wanted
                                   for name, hashes in group["files_sha256"].items() for relative, wanted in hashes.items()}
    return result


def verify_shap_inventory(root, requirements):
    root = Path(root).resolve()
    expected = requirements["shap"]["files_sha256"]
    actual = set()
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = [name for name in folders if name != "__pycache__"]
        for name in files:
            path = Path(directory) / name
            if path.suffix not in (".pyc", ".pyo"):
                actual.add(path.relative_to(root).as_posix())
    need(actual == set(expected), "SHAP_RUNTIME_INVENTORY_DRIFT")
    for relative, wanted in expected.items():
        check_hash(bounded(root, relative), wanted, "shap/" + relative)
    return dict(expected)


def code_bindings(core_root, requirements):
    core_root = Path(core_root).resolve()
    for relative, wanted in requirements["protected_source_hashes"].items():
        need(sha(bounded(core_root, relative)) == wanted, "PROTECTED_SOURCE_DRIFT", relative)
    files = set(requirements["code_files"])
    for directory in ("src/clinanalysis", "python/clinical_methods", "schemas"):
        for path in (core_root / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in (".pyc", ".pyo"):
                files.add(path.relative_to(core_root).as_posix())
    return {relative: sha(bounded(core_root, relative)) for relative in sorted(files)}


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix="." + path.name + ".", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(value)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def atomic_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def refresh_code_bindings(core_root=None, requirements=None, *, write=True):
    """Refresh code bytes only; fixed owner bytes and provider identities stay checked.

    Call after the integrator changes permitted transport/configuration sources.
    A deliberate fixed-owner change requires an explicit requirements review.
    """
    core_root = Path(core_root or ROOT / "integration/core").resolve()
    requirements = load_requirements(requirements)
    path = core_root / "runtime-lock.json"
    lock = read_json(path)
    for name, expected in requirements["lock_constants"].items():
        need(lock.get(name) == expected, "LOCK_FIXED_REQUIREMENT_DRIFT", name)
    previous = lock.get("code_hashes", {})
    lock["code_hashes"] = code_bindings(core_root, requirements)
    changed = sorted(name for name in set(previous) | set(lock["code_hashes"])
                     if previous.get(name) != lock["code_hashes"].get(name))
    if write:
        atomic_json(path, lock)
    return {"status": "CODE_BINDINGS_REFRESHED" if write else "CODE_BINDINGS_CHECKED",
            "code_files": len(lock["code_hashes"]), "changed_files": changed, "lock": lock}


def dependency_group(core_probe, requirements, name):
    return {str(bounded(core_probe["paths"][package], relative)).replace("\\", "/"): wanted
            for package, hashes in requirements["core_dependency_groups"][name].items()
            for relative, wanted in hashes.items()}


def configure(config, requirements=None, *, source_root=None, write=True):
    requirements = load_requirements(requirements)
    root = Path(source_root or ROOT).resolve()
    core = root / "integration/core"
    # Validate every configured executable and previously pinned vendor byte
    # before invoking native runtimes. No installations or package downloads.
    for name in ("python", "rscript"):
        check_hash(config[name], requirements["executables_sha256"][name], name)
    verify_shap_inventory(config["shap_library"], requirements)
    python = python_preflight(config, requirements)
    r = r_preflight(config, requirements)
    latent = r_preflight(config, requirements, latent=True)
    lock = copy.deepcopy(requirements["lock_constants"])
    lock.update(python=config["python"].as_posix(), rscript=config["rscript"].as_posix(),
                rscript_engine=Path(r["rscript_engine"]).as_posix(),
                r_libraries=[p.as_posix() for p in config["r_libraries"]],
                r_package_paths={name: r["paths"][name] for name in ("jsonlite", "digest")},
                code_hashes=code_bindings(core, requirements))
    lock["executable_hashes"] = {lock[name]: requirements["executables_sha256"][name]
                                 for name in ("python", "rscript", "rscript_engine")}
    for group, packages in (("penalized", ("glmnet", "Matrix")), ("cox_penalized", ("glmnet", "Matrix", "survival"))):
        lock[group + "_package_paths"] = {name: r["paths"][name] for name in packages}
        lock[group + "_dependency_hashes"] = dependency_group(r, requirements, group)
    module_runtime = {"schema_version": "clinical-module-runtime@1.0",
                      "latent_r_library": config["latent_r_library"].as_posix(),
                      "shap_library": config["shap_library"].as_posix(),
                      "rscript": lock["rscript"], "r_libraries": lock["r_libraries"],
                      "latent_r_package_paths": latent["paths"],
                      "latent_dependency_hashes": latent["dependency_hashes"],
                      "shap_files_sha256": requirements["shap"]["files_sha256"],
                      "python_package_versions": python["packages"],
                      "python_dependency_bindings": python["files"]}
    # This source package has the stable repository-relative _shared layout.
    repository = root.parents[1]
    agent = {"schema_version": "ye1-analysis-local-runtime@1.0",
             "integration_root": (root / "integration").as_posix(), "rscript": lock["rscript"]}
    if write:
        atomic_text(core / "runtime-libraries.txt", "\n".join(lock["r_libraries"]) + "\n")
        atomic_json(root / "integration/module-runtime.json", module_runtime)
        atomic_json(repository / ".clinical-local/agent-runtime.json", agent)
        # Write the effective core lock last; validation failures change none of
        # these outputs, and runs cannot consume an unvalidated new core lock.
        atomic_json(core / "runtime-lock.json", lock)
    return {"status": "RUNTIME_CONFIGURED" if write else "RUNTIME_PREFLIGHT_PASSED",
            "code_files": len(lock["code_hashes"]), "python_packages": len(python["packages"]),
            "core_r_packages": len(r["packages"]), "latent_r_packages": len(latent["packages"]),
            "shap_files": len(requirements["shap"]["files_sha256"]),
            "installation_performed": False, "numerical_execution_performed": False}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--profile", help="Local JSON profile; never commit machine paths.")
    result.add_argument("--python")
    result.add_argument("--rscript")
    result.add_argument("--r-library", action="append", help="Explicit R library, repeat in precedence order.")
    result.add_argument("--latent-r-library")
    result.add_argument("--shap-library")
    result.add_argument("--check-only", action="store_true", help="Run preflights without writing local bindings.")
    result.add_argument("--refresh-code-bindings", action="store_true", help="Refresh only the existing local lock code hashes.")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.refresh_code_bindings:
            need(not any(getattr(args, key) for key in ("profile", "python", "rscript", "r_library", "latent_r_library", "shap_library")),
                 "REFRESH_CANNOT_RECONFIGURE_RUNTIME")
            result = refresh_code_bindings(write=not args.check_only)
            result.pop("lock")
        else:
            result = configure(resolve_config(args), write=not args.check_only)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except RuntimeBlocked as error:
        print(json.dumps({"status": "blocked", "reason_code": error.code, "detail": error.detail}, ensure_ascii=True))
        return 2
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(json.dumps({"status": "blocked", "reason_code": "RUNTIME_CONFIGURATION_INVALID",
                          "detail": type(error).__name__}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
