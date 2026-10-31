"""Method-scoped installation evidence and stable native-runtime declarations."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,platform,subprocess,sys,tarfile,zipfile
import method_groups
from runtime_platform import runtime_python
ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"_shared/clinical_analysis";INTEGRATION=BACKEND/"integration";CORE=INTEGRATION/"core"
class RuntimeBlocked(ValueError):
    def __init__(self,code,groups=None):self.code=code;self.groups=groups or [];super().__init__(code)
def need(ok,code,groups=None):
    if not ok:raise RuntimeBlocked(code,groups)
def load(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+".tmp");temp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+"\n",encoding="utf-8");temp.replace(p)
def env():
    result=os.environ.copy()
    for key in ["PYTHONPATH","PYTHONHOME","R_LIBS","R_LIBS_USER","R_LIBS_SITE","R_PROFILE","R_PROFILE_USER","R_ENVIRON","R_ENVIRON_USER","LANG","LC_ALL","LC_COLLATE","LC_CTYPE","LC_MONETARY","LC_TIME"]:result.pop(key,None)
    result.update(PYTHONDONTWRITEBYTECODE="1",PYTHONIOENCODING="utf-8",MPLBACKEND="Agg",MPLCONFIGDIR=str(ROOT/".runtime/cache/matplotlib"),OMP_NUM_THREADS="1",OPENBLAS_NUM_THREADS="1",MKL_NUM_THREADS="1")
    if platform.system()=="Darwin":result.update(LANG="en_US.UTF-8",LC_CTYPE="en_US.UTF-8")
    return result
PY_FILES=r'''
from pathlib import Path
import hashlib,importlib.metadata as m,json,platform,sys
request=json.load(sys.stdin);prefix=Path(sys.prefix).resolve();directory=request.get('directory')
if directory:directory=Path(directory).resolve()
files={};versions={}
for name in request['packages']:
 d=next((x for x in m.distributions(path=[str(directory)]) if x.metadata['Name'].lower()==name.lower()),None) if directory else m.distribution(name)
 if d is None:raise ValueError('distribution missing')
 versions[name]=d.version
 for rel in d.files or []:
  p=Path(d.locate_file(rel)).resolve()
  if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
   if not p.is_relative_to(directory or prefix):raise ValueError('dependency outside product prefix')
   files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps({'python':platform.python_version(),'prefix':str(prefix),'base_prefix':sys.base_prefix,'base_executable':str(Path(sys._base_executable).resolve()),'packages':versions,'files':files}))
'''
R_META=r'''
if(.Platform$OS.type=='windows')invisible(suppressWarnings(Sys.setlocale('LC_CTYPE','.UTF-8')))
a<-commandArgs(trailingOnly=TRUE);Encoding(a)<-'UTF-8';.libPaths(c(a[[1]],.Library),include.site=FALSE)
names<-strsplit(a[[2]],',',fixed=TRUE)[[1]]
out<-list(R=as.character(getRversion()),r_arch=R.version$arch,r_home=normalizePath(R.home(),winslash='/',mustWork=TRUE),versions=list(),paths=list())
for(p in names){found<-find.package(p,quiet=TRUE);if(length(found)){out$versions[[p]]<-as.character(utils::packageVersion(p));out$paths[[p]]<-normalizePath(found,winslash='/',mustWork=TRUE)}}
cat(jsonlite::toJSON(out,auto_unbox=TRUE))
'''
def run_json(command,stdin=None):
    done=subprocess.run(list(map(str,command)),input=stdin,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=120,env=env(),cwd=ROOT)
    if done.returncode:
        path=ROOT/".runtime/diagnostics"/(datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+"-probe.json")
        save(path,{"scope":"fixed dependency probe; contains no analysis input","command":list(map(str,command)),"exit":done.returncode,"stdout":done.stdout,"stderr":done.stderr})
        error=RuntimeBlocked("RUNTIME_PROBE_FAILED");error.support_log=str(path);raise error
    try:return json.loads(done.stdout.lstrip("\ufeff"))
    except ValueError:raise RuntimeBlocked("RUNTIME_PROBE_RESULT_INVALID") from None
def py_probe(names,directory=None):
    value={"packages":names}
    if directory:value["directory"]=str(directory)
    return run_json([runtime_python(ROOT),"-I","-B","-c",PY_FILES],json.dumps(value))
def package_files(path):
    return {str(p.resolve()):sha(p) for p in Path(path).rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix not in {".pyc",".pyo"}}
def planned_R_file(spec,name,relative,rhome):
    if platform.system()=="Darwin" and relative.startswith("libs/x64/") and relative.endswith(".dll"):
        relative="libs/"+relative[len("libs/x64/"):-len(".dll")]+".so"
    package=next((x for x in spec["r_packages"] if x["name"]==name),None)
    if package:
        archive=ROOT/"third-party/r"/package["binary"]["filename"]
        if platform.system()=="Darwin":
            with tarfile.open(archive,"r:gz") as z:
                member=z.getmember(name+"/"+relative)
                need(member.isfile(),"R_BINARY_MEMBER_INVALID")
                raw=z.extractfile(member).read()
        else:
            with zipfile.ZipFile(archive) as z:
                raw=z.read(name+"/"+relative)
        return str((ROOT/".runtime/r-library"/name/relative).resolve()),hashlib.sha256(raw).hexdigest()
    path=Path(rhome)/"library"/name/relative
    if path.is_file():return str(path.resolve()),sha(path)
    if platform.system()=="Darwin":raise RuntimeBlocked("FOUNDATION_R_DECLARATION_UNAVAILABLE")
    requirements=load(BACKEND/"runtime-requirements.json")
    for group in requirements["core_dependency_groups"].values():
        if name in group and relative in group[name]:return str(path.resolve()),group[name][relative]
    raise RuntimeBlocked("FOUNDATION_R_DECLARATION_UNAVAILABLE")
def registry_config(vendor):
    original=load(INTEGRATION/"module-lock.json");admitted=load(INTEGRATION/"admitted-module-lock.json")
    if vendor.is_dir():
        entry=next(x for x in original["modules"] if x.get("registration_id")=="tree_shap")
        fixed={k:v for k,v in entry["supplementary_files_sha256"].items() if not k.startswith("tree_shap/_vendor/")}
        fixed.update({"tree_shap/_vendor/"+Path(k).relative_to(vendor).as_posix():v for k,v in package_files(vendor).items()})
        entry["supplementary_files_sha256"]=fixed
        admitted["modules"]["tree_shap"]["legacy_registration_sha256"]=canonical(entry)
    result={}
    for name,value in [("module-lock.json",original),("admitted-module-lock.json",admitted)]:
        path=ROOT/".runtime/registry"/name;save(path,value)
        result[name]={"path":str(path),"sha256":sha(path),"template_sha256":sha(INTEGRATION/name)}
    return result
def configure(installed,rscript):
    spec=load(ROOT/"runtime-spec.json");installed=method_groups.closure(installed);runtime=ROOT/".runtime";python=runtime_python(ROOT);rlib=runtime/"r-library"
    all_python={x["name"]:x for x in spec["python_packages"]};all_R={x["name"]:x for x in spec["r_packages"]}
    wanted_R=set(all_R)|{name for group in spec["groups"].values() for name in group["foundation_R"]}
    r=run_json([rscript,"--vanilla","-",rlib,",".join(sorted(wanted_R))],R_META)
    need(r["R"]==spec["R"],"R_VERSION_UNSUPPORTED")
    if platform.system()=="Darwin":need(r.get("r_arch") in {"arm64","aarch64"},"R_ARM64_REQUIRED")
    rhome=Path(r["r_home"]);groups={}
    base=None
    for name in installed:
        definition=spec["groups"][name];py=py_probe(definition["python"]);base=base or py
        need(py["python"]==spec["python"] and Path(py["prefix"]).resolve()==(runtime/"python").resolve(),"ISOLATED_PYTHON_REQUIRED")
        need(py["packages"]=={p:all_python[p]["version"] for p in definition["python"]},"PYTHON_PACKAGE_VERSION_DRIFT")
        files=dict(py["files"])
        for package in definition["R"]:
            need(r["versions"].get(package)==all_R[package]["version"],"R_DEPENDENCY_VERSION_DRIFT",[name])
            need(Path(r["paths"][package]).resolve()==(rlib/package).resolve(),"R_LIBRARY_NOT_ISOLATED",[name]);files.update(package_files(r["paths"][package]))
        for package,version in definition["foundation_R"].items():
            need(r["versions"].get(package)==version,"FOUNDATION_R_COMPONENT_VERSION_REQUIRED",[name])
            need(Path(r["paths"][package]).resolve()==(rhome/"library"/package).resolve(),"FOUNDATION_R_COMPONENT_PATH_REQUIRED",[name]);files.update(package_files(r["paths"][package]))
        if definition.get("vendor_python"):
            vendor=py_probe(definition["vendor_python"],runtime/"shap")
            need(vendor["packages"]=={p:all_python[p]["version"] for p in definition["vendor_python"]},"TREE_SHAP_DEPENDENCY_VERSION_DRIFT")
            files.update(package_files(runtime/"shap"))
        groups[name]={"python_packages":py["packages"],"R_packages":{p:r["versions"][p] for p in definition["R"]},"files":files}
    cfg=(runtime/"python/pyvenv.cfg").read_text(encoding="utf-8").lower();need("include-system-site-packages = false" in cfg,"SYSTEM_SITE_PACKAGES_MUST_BE_DISABLED")
    foundation={}
    for path in [Path(base["base_executable"]),Path(base["base_prefix"])/"python314.dll",Path(base["base_prefix"])/"python3.dll",python,runtime/"python/pyvenv.cfg",Path(rscript),rhome/"bin/x64/Rscript.exe"]:
        if path.is_file():foundation[str(path.resolve())]=sha(path)
    requirements=load(BACKEND/"runtime-requirements.json")
    engine_files=("bin/exec/R","lib/libR.dylib") if platform.system()=="Darwin" else requirements["r_engine_files_sha256"]
    for relative in engine_files:
        path=rhome/relative;need(path.is_file(),"R_ENGINE_COMPONENT_MISSING");foundation[str(path.resolve())]=sha(path)
    loader=importlib.util.spec_from_file_location("original_transport_code_bindings",BACKEND/"configure_runtime.py");module=importlib.util.module_from_spec(loader);loader.loader.exec_module(module)
    lock=copy.deepcopy(requirements["lock_constants"])
    for key in ["python_versions","prediction_python_versions"]:lock[key]["python"]=spec["python"]
    engine=rhome/"bin/x64/Rscript.exe";engine=engine if engine.is_file() else Path(rscript)
    lock.update(python=python.as_posix(),rscript=Path(rscript).resolve().as_posix(),rscript_engine=engine.as_posix(),r_libraries=[rlib.as_posix(),(rhome/"library").as_posix()],r_package_paths={p:(rlib/p).as_posix() for p in ["jsonlite","digest"]},code_hashes=module.code_bindings(CORE,requirements),installation_performed=True)
    # Historical developer constants predate the V1 admission adapter. Use the
    # same exact per-method composite definition as prediction_bridge, computed
    # from already-verified immutable source bytes; no optional imports needed.
    provider_files=["prediction.py","prediction_bridge.py","real_family_admission.py","continuous_ridge/__init__.py","continuous_ridge/core.py","continuous_ridge/prediction_engine.py","continuous_ridge/prediction_metrics.py"]
    provider_hashes={name:lock["code_hashes"]["python/clinical_methods/"+name] for name in provider_files}
    lock["prediction_provider_versions"]={"prediction.binary.ridge":canonical({name:provider_hashes[name] for name in provider_files[:3]}),"prediction.continuous.nonnegative.ridge":canonical(provider_hashes)}
    lock["executable_hashes"]={lock[k]:sha(lock[k]) for k in ["python","rscript","rscript_engine"]}
    # Declare optional requirements now; availability is checked per group.
    # Adding a group therefore does not invalidate prior result runtime hashes.
    for group,names in [("penalized",["glmnet","Matrix"]),("cox_penalized",["glmnet","Matrix","survival"])]:
        lock[group+"_package_paths"]={p:((rlib/p) if p in all_R else rhome/"library"/p).as_posix() for p in names}
        lock[group+"_dependency_hashes"]={}
        for package,files in requirements["core_dependency_groups"][group].items():
            for rel in files:
                path,digest=planned_R_file(spec,package,rel,rhome);lock[group+"_dependency_hashes"][path]=digest
    corepath=CORE/"runtime-lock.json"
    if corepath.exists():need(load(corepath)==lock,"CORE_RUNTIME_DECLARATION_CHANGED_REINSTALL_REQUIRED")
    else:save(corepath,lock)
    (CORE/"runtime-libraries.txt").write_text("\n".join(lock["r_libraries"])+"\n",encoding="utf-8")
    agent=ROOT/".clinical-local/agent-runtime.json";save(agent,{"schema_version":"ye1-analysis-local-runtime@1.0","integration_root":str(INTEGRATION),"rscript":lock["rscript"]})
    vendor=runtime/"shap";registry=registry_config(vendor)
    module_runtime=INTEGRATION/"module-runtime.json"
    save(module_runtime,{"schema_version":"clinical-toolkit-module-runtime@3.0","latent_r_library":str(rlib),"shap_library":str(vendor),"rscript":lock["rscript"],"r_libraries":lock["r_libraries"],"registry":registry,"requirements_are_not_installation_evidence":True})
    configs={str(p):sha(p) for p in [corepath,CORE/"runtime-libraries.txt",agent,module_runtime,*[Path(x["path"]) for x in registry.values()]]}
    profile={"schema_version":"ye1-toolkit-installed@3.0","product_root":str(ROOT),"spec_sha256":sha(ROOT/"runtime-spec.json"),"python":str(python),"base_python":base["base_prefix"],"rscript":str(Path(rscript).resolve()),"R_home":str(rhome),"installed_groups":installed,"groups":groups,"foundation_files":foundation,"config_files":configs,"core_runtime_sha256":sha(corepath),"code_hashes":lock["code_hashes"],"no_global_host_isolation_claim":True}
    save(runtime/"toolkit-profile.json",profile);return profile
def check(method="baseline.table1"):
    path=ROOT/".runtime/toolkit-profile.json";need(path.is_file(),"TOOLKIT_INSTALLATION_REQUIRED");profile=load(path);spec=load(ROOT/"runtime-spec.json")
    need(profile.get("schema_version")=="ye1-toolkit-installed@3.0","TOOLKIT_PROFILE_INVALID");need(Path(profile["product_root"]).resolve()==ROOT,"REINSTALL_AFTER_MOVE")
    need(sha(ROOT/"runtime-spec.json")==profile["spec_sha256"],"RUNTIME_SPEC_CHANGED_REINSTALL_REQUIRED")
    required=method_groups.for_method(method);missing=[x for x in required if x not in profile["installed_groups"]]
    need(not missing,"DEPENDENCY_GROUP_NOT_INSTALLED",missing)
    files={**profile["foundation_files"],**profile["config_files"]}
    for group in required:files.update(profile["groups"][group]["files"])
    for name,digest in files.items():need(Path(name).is_file() and sha(name)==digest,"DEPENDENCY_OR_CONFIGURATION_BYTE_DRIFT")
    for relative,digest in profile["code_hashes"].items():need((CORE/relative).is_file() and sha(CORE/relative)==digest,"BACKEND_SOURCE_DRIFT")
    current=run_json([profile["python"],"-I","-B","-c","import json,platform,sys;print(json.dumps({'python':platform.python_version(),'prefix':sys.prefix}))"])
    need(current["python"]==spec["python"] and Path(current["prefix"]).resolve()==ROOT/".runtime/python","PYTHON_RUNTIME_VERSION_OR_PREFIX_CHANGED")
    modules=["numpy","scipy","statsmodels","pandas","patsy"]
    if "ml" in required:modules.append("sklearn")
    if "plot" in required:modules.extend(["matplotlib","matplotlib.font_manager","PIL.Image","PIL.ImageDraw","PIL.ImageFont","PIL.PngImagePlugin"])
    imports="import importlib,json,sys;[importlib.import_module(x) for x in "+repr(modules)+"];"
    if "shap" in required:imports+="sys.path.insert(0,"+repr(str(ROOT/".runtime/shap"))+");import shap;"
    run_json([profile["python"],"-I","-B","-c",imports+"print(json.dumps({'imports':'ready'}))"])
    r_names=sorted({p for g in required for p in spec["groups"][g]["R"]}|{p for g in required for p in spec["groups"][g]["foundation_R"]})
    probe=R_META.replace("cat(jsonlite::toJSON(out,auto_unbox=TRUE))","for(p in names)stopifnot(suppressPackageStartupMessages(requireNamespace(p,quietly=TRUE)));cat(jsonlite::toJSON(out,auto_unbox=TRUE))")
    run_json([profile["rscript"],"--vanilla","-",ROOT/".runtime/r-library",",".join(r_names)],probe)
    status="MACOS_ARM64_TOOLKIT_RUNTIME_READY" if platform.system()=="Darwin" else "WINDOWS_TOOLKIT_RUNTIME_READY"
    return {"status":status,"method_id":method,"python":spec["python"],"R":spec["R"],"required_groups":required,"installed_groups":profile["installed_groups"],"network_isolation":"not_provided"}
