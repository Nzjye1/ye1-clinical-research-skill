"""Minimal four-method Windows runtime; no installer or global discovery here."""
from pathlib import Path
import copy,hashlib,importlib.metadata,importlib.util,json,os,platform,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"_shared/clinical_analysis";CORE=BACKEND/"integration/core"

class RuntimeErrorCode(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
def need(x,code):
    if not x:raise RuntimeErrorCode(code)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def save(p,value):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix(p.suffix+".tmp");temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8");temp.replace(p)
def env():
    if load(ROOT/"runtime-spec.json").get("schema_version")=="ye1-toolkit-runtime-spec@3.0":
        from runtime_toolkit import env as toolkit_env
        return toolkit_env()
    value=os.environ.copy()
    for key in ["PYTHONPATH","PYTHONHOME","R_LIBS","R_LIBS_USER","R_LIBS_SITE","R_PROFILE","R_PROFILE_USER","R_ENVIRON","R_ENVIRON_USER","LANG","LC_ALL","LC_COLLATE","LC_CTYPE","LC_MONETARY","LC_TIME"]:value.pop(key,None)
    value["PYTHONDONTWRITEBYTECODE"]="1";value["PYTHONIOENCODING"]="utf-8";return value

PY_PROBE=r'''
import hashlib,importlib,importlib.metadata as m,json,platform,sys
from pathlib import Path
spec=json.load(sys.stdin);files={};versions={}
for package in spec['python_packages']:
 d=m.distribution(package['name']);versions[package['name']]=d.version
 for relative in d.files or []:
  p=Path(d.locate_file(relative)).resolve()
  if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
   if not p.is_relative_to(Path(sys.prefix).resolve()):raise ValueError('dependency escaped venv')
   files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
import numpy,scipy,statsmodels,pandas,patsy
from statsmodels.duration.hazard_regression import PHReg
cfg=(Path(sys.prefix)/'pyvenv.cfg').read_text(encoding='utf-8').lower()
if 'include-system-site-packages = false' not in cfg:raise ValueError('system site packages enabled')
print(json.dumps({'python':platform.python_version(),'prefix':str(Path(sys.prefix).resolve()),'base_prefix':sys.base_prefix,'base_executable':str(Path(sys._base_executable).resolve()),'system_site_packages':False,'packages':versions,'files':files}))
'''
R_PROBE=r'''
if(.Platform$OS.type=='windows')invisible(suppressWarnings(Sys.setlocale('LC_CTYPE','.UTF-8')))
args<-commandArgs(trailingOnly=TRUE)
Encoding(args)<-'UTF-8'
.libPaths(c(args[[1L]],.Library),include.site=FALSE)
stopifnot(requireNamespace('jsonlite',quietly=TRUE),requireNamespace('digest',quietly=TRUE))
pkgs<-c('jsonlite','digest')
out<-list(R=as.character(getRversion()),r_home=normalizePath(R.home(),winslash='/',mustWork=TRUE),engine=normalizePath(file.path(R.home('bin'),'Rscript.exe'),winslash='/',mustWork=TRUE),versions=list(),paths=list())
for(p in pkgs){out$versions[[p]]<-as.character(utils::packageVersion(p));out$paths[[p]]<-normalizePath(find.package(p),winslash='/',mustWork=TRUE)}
cat(jsonlite::toJSON(out,auto_unbox=TRUE))
'''
def run_json(command,*,stdin=None):
    done=subprocess.run(list(map(str,command)),input=stdin,capture_output=True,text=True,encoding="utf-8",errors="replace",env=env(),timeout=90,cwd=ROOT)
    need(done.returncode==0,"RUNTIME_PROBE_FAILED")
    try:return json.loads(done.stdout.lstrip("\ufeff"))
    except ValueError:raise RuntimeErrorCode("RUNTIME_PROBE_RESULT_INVALID") from None

def create_bindings(rscript):
    spec=load(ROOT/"runtime-spec.json");runtime=ROOT/".runtime";py=runtime/"python/Scripts/python.exe";rlib=runtime/"r-library"
    need(platform.system()=="Windows" and platform.machine().upper() in {"AMD64","X86_64"},"WINDOWS_X64_REQUIRED")
    pyresult=run_json([py,"-I","-B","-c",PY_PROBE],stdin=json.dumps(spec))
    need(pyresult["python"]==spec["python"],"PYTHON_VERSION_UNSUPPORTED")
    need(Path(pyresult["prefix"]).resolve()==(runtime/"python").resolve(),"ISOLATED_VENV_REQUIRED")
    need(pyresult["system_site_packages"] is False,"ISOLATED_VENV_REQUIRED")
    need(pyresult["packages"]=={x["name"]:x["version"] for x in spec["python_packages"]},"PYTHON_DEPENDENCY_VERSION_DRIFT")
    r=run_json([rscript,"--vanilla","-",rlib],stdin=R_PROBE)
    need(r["R"]==spec["R"],"R_VERSION_UNSUPPORTED")
    need(r["versions"]=={x["name"]:x["version"] for x in spec["r_packages"]},"R_DEPENDENCY_VERSION_DRIFT")
    need(all(Path(x).resolve().parent==rlib.resolve() for x in r["paths"].values()),"R_LIBRARY_NOT_ISOLATED")
    dependency_files=dict(pyresult["files"])
    for p in [Path(pyresult["base_executable"]),Path(pyresult["base_prefix"])/"python314.dll",Path(pyresult["base_prefix"])/"python3.dll",runtime/"python/pyvenv.cfg"]:
        need(p.is_file(),"BASE_PYTHON_BINDING_UNAVAILABLE");dependency_files[str(p.resolve())]=sha(p)
    for path in r["paths"].values():
        for p in Path(path).rglob("*"):
            if p.is_file():dependency_files[str(p.resolve())]=sha(p)
    module_spec=importlib.util.spec_from_file_location("original_code_binding_checks",BACKEND/"configure_runtime.py")
    original=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(original)
    requirements=load(BACKEND/"runtime-requirements.json");lock=copy.deepcopy(requirements["lock_constants"])
    lock["python_versions"]={"python":spec["python"],"numpy":"2.5.4","scipy":"1.18.1","statsmodels":"0.14.6"}
    lock.update(python=py.as_posix(),rscript=Path(rscript).resolve().as_posix(),rscript_engine=Path(r["engine"]).as_posix(),r_libraries=[rlib.as_posix(),str(Path(r["r_home"])/"library").replace("\\","/")],r_package_paths=r["paths"],code_hashes=original.code_bindings(CORE,requirements),installation_performed=True)
    lock["executable_hashes"]={lock[k]:sha(lock[k]) for k in ["python","rscript","rscript_engine"]}
    for rel in requirements.get("r_engine_files_sha256",{}):
        p=Path(r["r_home"])/rel;dependency_files[str(p.resolve())]=sha(p)
    (CORE/"evidence").mkdir(exist_ok=True)
    save(CORE/"runtime-lock.json",lock);(CORE/"runtime-libraries.txt").write_text("\n".join(lock["r_libraries"])+"\n",encoding="utf-8")
    save(ROOT/".clinical-local/agent-runtime.json",{"schema_version":"ye1-analysis-local-runtime@1.0","integration_root":(BACKEND/"integration").as_posix(),"rscript":lock["rscript"]})
    profile={"schema_version":"ye1-installed-windows@2.0","product_root":str(ROOT),"spec_sha256":sha(ROOT/"runtime-spec.json"),"python":str(py),"rscript":str(Path(rscript).resolve()),"python_version":pyresult["python"],"R_version":r["R"],"python_packages":pyresult["packages"],"r_packages":r["versions"],"dependency_files":dependency_files,"executables":lock["executable_hashes"],"runtime_lock_sha256":sha(CORE/"runtime-lock.json"),"base_python":pyresult["base_prefix"],"full_os_or_network_isolation":False}
    save(runtime/"profile.json",profile)
    return check()

def check(method="baseline.table1"):
    if load(ROOT/"runtime-spec.json").get("schema_version")=="ye1-toolkit-runtime-spec@3.0":
        from runtime_toolkit import check as toolkit_check
        return toolkit_check(method)
    profile_path=ROOT/".runtime/profile.json";need(profile_path.is_file(),"INSTALLATION_REQUIRED")
    p=load(profile_path);need(p.get("schema_version")=="ye1-installed-windows@2.0","INSTALLATION_PROFILE_INVALID")
    need(Path(p["product_root"]).resolve()==ROOT,"REINSTALL_AFTER_MOVE")
    need(sha(ROOT/"runtime-spec.json")==p["spec_sha256"],"RUNTIME_SPEC_CHANGED_REINSTALL_REQUIRED")
    live=run_json([p["python"],"-I","-B","-c","import json,platform,sys;print(json.dumps({'python':platform.python_version(),'prefix':sys.prefix}))"])
    need(live["python"]==load(ROOT/"runtime-spec.json")["python"] and Path(live["prefix"]).resolve()==(ROOT/".runtime/python").resolve(),"PYTHON_RUNTIME_VERSION_OR_PREFIX_CHANGED")
    need((CORE/"runtime-lock.json").is_file() and sha(CORE/"runtime-lock.json")==p["runtime_lock_sha256"],"RUNTIME_LOCK_DRIFT")
    for path,expected in {**p["dependency_files"],**p["executables"]}.items():
        need(Path(path).is_file() and sha(path)==expected,"DEPENDENCY_BYTE_DRIFT")
    lock=load(CORE/"runtime-lock.json")
    for rel,expected in lock["code_hashes"].items():need((CORE/rel).is_file() and sha(CORE/rel)==expected,"BACKEND_SOURCE_DRIFT")
    need(Path(load(ROOT/".clinical-local/agent-runtime.json")["integration_root"]).resolve()==BACKEND/"integration","RUNTIME_ROOT_DRIFT")
    return {"status":"WINDOWS_RUNTIME_READY","python":p["python_version"],"R":p["R_version"],"python_distributions":len(p["python_packages"]),"r_packages":len(p["r_packages"]),"methods":load(ROOT/"runtime-spec.json")["methods"],"network_isolation":"not_provided"}
