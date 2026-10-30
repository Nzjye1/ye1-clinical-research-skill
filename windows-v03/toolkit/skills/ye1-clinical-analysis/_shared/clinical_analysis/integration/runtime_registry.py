"""Select a byte-bound installation registry, preserving the immutable template.

Only package/runtime bindings differ by install prefix. Estimator source and
manifest checks remain owned by module_task and admitted_modules.
"""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parent

class RegistryError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)

def bound_path(name):
    if name not in {"module-lock.json","admitted-module-lock.json"}:raise RegistryError("RUNTIME_REGISTRY_NAME_INVALID")
    original=ROOT/name;config=ROOT/"module-runtime.json"
    if not config.is_file():return original
    if config.stat().st_size>8*1024*1024:raise RegistryError("RUNTIME_REGISTRY_CONFIG_SIZE_INVALID")
    value=json.loads(config.read_text(encoding="utf-8-sig"))
    if value.get("schema_version")!="clinical-toolkit-module-runtime@3.0":return original
    entry=value.get("registry",{}).get(name)
    if not isinstance(entry,dict) or set(entry)!={"path","sha256","template_sha256"}:raise RegistryError("RUNTIME_REGISTRY_BINDING_INVALID")
    path=Path(entry["path"]).resolve();allowed=(ROOT.parents[2]/".runtime/registry").resolve()
    if not path.is_relative_to(allowed) or path.name!=name or path.is_symlink() or not path.is_file():raise RegistryError("RUNTIME_REGISTRY_PATH_INVALID")
    if path.stat().st_size>8*1024*1024:raise RegistryError("RUNTIME_REGISTRY_FILE_SIZE_INVALID")
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if not all(isinstance(entry[k],str) and re.fullmatch("[0-9a-f]{64}",entry[k]) for k in ["sha256","template_sha256"]):raise RegistryError("RUNTIME_REGISTRY_BINDING_INVALID")
    if digest(path)!=entry["sha256"] or digest(original)!=entry["template_sha256"]:raise RegistryError("RUNTIME_REGISTRY_DRIFT")
    return path

def read_lock(name):return json.loads(bound_path(name).read_text(encoding="utf-8-sig"))
def lock_digest(name):return hashlib.sha256(bound_path(name).read_bytes()).hexdigest()
