"""Integrator-only development lock refresh; never a release or acceptance claim."""
from pathlib import Path
import hashlib,json,sys
from module_contract import ModuleRegistry
ROOT=Path(__file__).resolve().parent
SOURCES={
    "mediation_matching":("mediation_matching","integration-request.json"),
    "nonlinear_prediction":("nonlinear_prediction","integration-request.json"),
    "latent_longitudinal":("latent_longitudinal","integration-request.json"),
    "cox_evaluation_explanation":("cox-evaluation-explanation","integration-request.json"),
    "tree_shap":("nonlinear_prediction","integration-request-tree-shap.json"),
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def main():
    core=ROOT/"core";registry=ModuleRegistry();entries=[]
    old=json.loads((ROOT/"module-lock.json").read_text(encoding="utf-8")) if (ROOT/"module-lock.json").exists() else None
    selected=set(sys.argv[1:])
    if selected-set(SOURCES):raise SystemExit("Unknown module acknowledgement")
    for key,(name,manifest_path) in SOURCES.items():
        previous=next((entry for entry in (old or {}).get("modules",[]) if entry["directory"]==name and entry.get("manifest_path","integration-request.json")==manifest_path),None)
        if old is not None and key not in selected:
            if previous is not None:entries.append(previous)
            continue
        module=ROOT.parent/"modules"/name
        receipt=registry.register_manifest(module,manifest_path)
        receipt["registration_id"]=key
        receipt["directory"]=name
        receipt["manifest_path"]=manifest_path
        receipt["manifest_sha256"]=sha(module/manifest_path)
        if key=="tree_shap":
            extra=[module/"tree_shap/schemas/background.schema.json",module/"tree_shap/requirements.txt"]
            runtime_config=json.loads((ROOT/"module-runtime.json").read_text(encoding="utf-8"))
            vendor=Path(runtime_config["shap_library"]).resolve()
            expected=runtime_config["shap_files_sha256"]
            actual={p.relative_to(vendor).as_posix() for p in vendor.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc",".pyo")}
            if actual!=set(expected) or any(sha(vendor/rel)!=digest for rel,digest in expected.items()):
                raise SystemExit("Configured SHAP runtime inventory drift; no replacement or installation performed")
            receipt["supplementary_files_sha256"]={p.relative_to(module).as_posix():sha(p) for p in sorted(extra)}
            receipt["supplementary_files_sha256"].update({"tree_shap/_vendor/"+rel:digest for rel,digest in expected.items()})
            receipt["runtime_tree"]="tree_shap/_vendor"
            base=next(e for e in entries if e["directory"]=="nonlinear_prediction" and e.get("manifest_path","integration-request.json")=="integration-request.json")
            receipt["dependencies_sha256"]={"nonlinear_prediction":canonical(base)}
        entries.append(receipt)
    files=[p for p in ROOT.glob("*.py") if p.name!="update_development_lock.py"]+list((ROOT/"contracts").glob("*.json"))+list(ROOT.glob("*.R"))
    manifest={"schema_version":"clinical-module-lock@1.0","status":"ACTIVE_DEVELOPMENT_NOT_ACCEPTANCE", "modules":entries,
              "integration_files_sha256":{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}}
    dump(ROOT/"module-lock.json",manifest)
    lock=json.loads((core/"runtime-lock.json").read_text(encoding="utf-8"))
    names=set(lock["code_hashes"])
    names.update(p.relative_to(core).as_posix() for p in (core/"src/clinanalysis/R").glob("clinical_modular*.R"))
    lock["code_hashes"]={name:sha(core/name) for name in sorted(names)}
    lock["status"]="ACTIVE_MODULAR_DEVELOPMENT"
    dump(core/"runtime-lock.json",lock)
    print(json.dumps({"status":"DEVELOPMENT_LOCK_UPDATED","modules":[e["module_id"] for e in entries],"acceptance_claimed":False}))
if __name__=="__main__":main()
