"""Install only explicitly selected method groups in this product's runtime."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,platform,subprocess,sys,venv
# Python isolated mode intentionally excludes the script directory. Bootstrap
# only this installed helper directory, never cwd or a developer checkout.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_toolkit import ROOT,load,save,need,sha,env,configure,check,RuntimeBlocked as RuntimeErrorCode
import method_groups

def logged_python(command,log,code,timeout=120):
    # Stream output to disk so failed and timed-out bootstrap attempts remain
    # diagnosable, including a partial venv created before pip is available.
    with log.open("xb") as out:
        try:
            return subprocess.run(command,env=env(),stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
        except (OSError,subprocess.TimeoutExpired) as error:
            out.write(("\n"+str(error)+"\n").encode("utf-8",errors="replace"))
            raise RuntimeErrorCode(code) from None


def ensure_python(runtime,logdir,version):
    directory=runtime/"python";python=directory/"Scripts/python.exe"
    need(not any(p.is_symlink() or (hasattr(p,"is_junction") and p.is_junction()) for p in [directory,python.parent,python]),"UNSAFE_INSTALL_PATH")
    if not python.is_file():
        done=logged_python([sys.executable,"-I","-B","-m","venv",str(directory)],logdir/"python-venv-create.log","LOCAL_VENV_CREATION_FAILED")
        need(done.returncode==0,"LOCAL_VENV_CREATION_FAILED")
    # Ownership of .runtime is checked by the caller. Verify the executable's
    # actual prefix before allowing ensurepip to write into an existing venv.
    probe="from pathlib import Path; import platform,sys; p=Path(sys.prefix); ok=p.resolve()==Path(sys.argv[1]).resolve() and sys.prefix!=sys.base_prefix and platform.python_version()==sys.argv[2] and 'include-system-site-packages = false' in (p/'pyvenv.cfg').read_text(encoding='utf-8').lower(); print('isolated_venv_valid='+str(ok)); sys.exit(0 if ok else 1)"
    done=logged_python([str(python),"-I","-B","-c",probe,str(directory),version],logdir/"python-venv-check.log","LOCAL_VENV_INVALID")
    need(done.returncode==0,"LOCAL_VENV_INVALID")
    pip=[str(python),"-I","-B","-X","utf8","-m","pip","--isolated","--version"]
    done=logged_python(pip,logdir/"python-pip-check.log","LOCAL_PIP_CHECK_FAILED")
    if done.returncode:
        done=logged_python([str(python),"-I","-B","-X","utf8","-m","ensurepip","--upgrade","--default-pip"],logdir/"python-ensurepip.log","LOCAL_PIP_BOOTSTRAP_FAILED")
        need(done.returncode==0,"LOCAL_PIP_BOOTSTRAP_FAILED")
        done=logged_python(pip,logdir/"python-pip-recheck.log","LOCAL_PIP_BOOTSTRAP_FAILED")
        need(done.returncode==0,"LOCAL_PIP_BOOTSTRAP_FAILED")
    return python


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--rscript",required=True);parser.add_argument("--install",action="store_true");parser.add_argument("--wheelhouse",help="Optional offline official-wheel directory; hashes remain enforced");parser.add_argument("--groups",nargs="+",default=["base"]);parser.add_argument("--method");parser.add_argument("--all",action="store_true")
    args=parser.parse_args();full_spec=load(ROOT/"runtime-spec.json");runtime=ROOT/".runtime";rscript=Path(args.rscript).resolve();previous=[]
    if (runtime/"toolkit-profile.json").is_file():
        profile=load(runtime/"toolkit-profile.json");need(profile["product_root"]==str(ROOT),"REINSTALL_AFTER_MOVE");need(profile["spec_sha256"]==sha(ROOT/"runtime-spec.json"),"RUNTIME_SPEC_CHANGED_REINSTALL_REQUIRED");previous=profile["installed_groups"]
    try:selected=method_groups.closure(previous+(list(full_spec["groups"]) if args.all else args.groups)+(method_groups.for_method(args.method) if args.method else []))
    except ValueError:raise RuntimeErrorCode("DEPENDENCY_GROUP_INVALID") from None
    py_names={p for group in selected for p in full_spec["groups"][group]["python"]};vendor_names={p for group in selected for p in full_spec["groups"][group].get("vendor_python",[])};r_names={p for group in selected for p in full_spec["groups"][group]["R"]}
    spec={**full_spec,"python_packages":[p for p in full_spec["python_packages"] if p["name"] in py_names|vendor_names],"r_packages":[p for p in full_spec["r_packages"] if p["name"] in r_names]}
    need(platform.system()=="Windows" and platform.machine().upper() in {"AMD64","X86_64"},"WINDOWS_X64_REQUIRED")
    need(platform.python_version()==spec["python"] and sys.maxsize>2**32,"PYTHON_3_14_5_X64_REQUIRED")
    need(rscript.is_file(),"RSCRIPT_NOT_FOUND")
    done=subprocess.run([str(rscript),"--vanilla","-e","cat(as.character(getRversion()))"],capture_output=True,text=True,encoding="utf-8",env=env(),timeout=30)
    need(done.returncode==0 and done.stdout.strip()==spec["R"],"R_4_6_1_X64_REQUIRED")
    for pkg in spec["r_packages"]:
        for kind in ["binary","source"]:need(sha(ROOT/"third-party/r"/pkg[kind]["filename"])==pkg[kind]["sha256"],"BUNDLED_R_PACKAGE_HASH_MISMATCH")
    if not args.install:
        print(json.dumps({"status":"READY_TO_INSTALL","target":str(runtime),"groups":selected,"python_distributions":len(py_names),"isolated_shap_distributions":len(vendor_names),"r_packages":len(spec["r_packages"]),"download_hosts":["files.pythonhosted.org"] if not args.wheelhouse else [],"system_changes":False,"next":"Repeat with --install after approving these local changes."}));return 0
    if previous:
        # Adding a group must not silently accept drift in an existing group.
        bound={**profile["foundation_files"],**profile["config_files"]}
        for group in previous:bound.update(profile["groups"][group]["files"])
        need(all(Path(p).is_file() and sha(p)==expected for p,expected in bound.items()),"EXISTING_DEPENDENCY_DRIFT_REVIEW_REQUIRED")
    need(not ROOT.is_symlink() and not runtime.is_symlink(),"UNSAFE_INSTALL_PATH")
    state=runtime/"install-state.json"
    if runtime.exists():
        need(state.is_file() and load(state).get("product_root")==str(ROOT) and load(state).get("schema_version")=="ye1-toolkit-install-state@3.0","EXISTING_RUNTIME_NOT_OWNED_BY_INSTALLER")
    else:runtime.mkdir()
    save(state,{"schema_version":"ye1-toolkit-install-state@3.0","product_root":str(ROOT),"version":spec["product_version"],"status":"installing","groups":selected})
    logdir=ROOT/"install-logs"/datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f");logdir.mkdir(parents=True)
    python=ensure_python(runtime,logdir,spec["python"])
    print(json.dumps({"stage":"preparing_python_dependencies","logs":str(logdir),"target":str(runtime),"global_environment_modified":False}),flush=True)
    if args.wheelhouse:
        wheels=Path(args.wheelhouse).resolve();need(wheels.is_dir(),"OFFLINE_WHEEL_DIRECTORY_REQUIRED")
    else:
        from download_wheels import acquire
        wheels=acquire(spec,runtime/"wheels",logdir/"wheel-downloads.json")
    requirements=logdir/"selected-main.lock";requirements.write_text("--only-binary=:all:\n"+"\n".join(p["name"]+"=="+p["version"]+" --hash=sha256:"+p["sha256"] for p in spec["python_packages"] if p["name"] in py_names)+"\n",encoding="utf-8")
    command=[str(python),"-I","-X","utf8","-m","pip","--isolated","install","--disable-pip-version-check","--no-input","--no-cache-dir","--no-compile","--no-deps","--only-binary=:all:","--require-hashes","-r",str(requirements),"--no-index","--find-links",str(wheels)]
    print(json.dumps({"stage":"installing_verified_local_wheels","logs":str(logdir)}),flush=True)
    with (logdir/"python-install.log").open("xb") as out:
        done=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,env=env(),timeout=300,cwd=ROOT)
    need(done.returncode==0,"PYTHON_PACKAGES_INSTALL_FAILED")
    if vendor_names and "shap" not in previous:
        vendor=runtime/"shap"
        if vendor.exists():
            # An interrupted, installer-owned attempt is preserved, not erased.
            need(not vendor.is_symlink() and not (hasattr(vendor,"is_junction") and vendor.is_junction()),"UNSAFE_VENDOR_PATH")
            archive=runtime/"failed-installs"/("shap-"+datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            need(vendor.resolve().is_relative_to(runtime.resolve()) and archive.resolve().is_relative_to(runtime.resolve()),"UNSAFE_VENDOR_RECOVERY_PATH")
            archive.parent.mkdir(exist_ok=True);vendor.rename(archive)
        requirements=logdir/"shap-vendor.lock";requirements.write_text("--only-binary=:all:\n"+"\n".join(p["name"]+"=="+p["version"]+" --hash=sha256:"+p["sha256"] for p in spec["python_packages"] if p["name"] in vendor_names)+"\n",encoding="utf-8")
        command=[str(python),"-I","-X","utf8","-m","pip","--isolated","install","--disable-pip-version-check","--no-input","--no-cache-dir","--no-compile","--no-deps","--only-binary=:all:","--require-hashes","--no-index","--find-links",str(wheels),"--target",str(vendor),"-r",str(requirements)]
        with (logdir/"shap-vendor-install.log").open("xb") as out:done=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,env=env(),timeout=300,cwd=ROOT)
        need(done.returncode==0,"TREE_SHAP_PACKAGES_INSTALL_FAILED")
    rlib=runtime/"r-library";rlib.mkdir(exist_ok=True)
    print(json.dumps({"stage":"installing_local_R_packages","logs":str(logdir)}),flush=True)
    command=[str(rscript),"--vanilla",str(ROOT/"scripts/install_r.R"),str(rlib),*[str(ROOT/"third-party/r"/p["binary"]["filename"]) for p in spec["r_packages"]]]
    with (logdir/"r-install.log").open("xb") as out:done=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT,env=env(),timeout=120,cwd=ROOT)
    need(done.returncode==0,"R_PACKAGES_INSTALL_FAILED")
    configure(selected,rscript)
    # Verify every selected group, rather than mistaking a successful base
    # check for successful optional dependency installation.
    checked=set()
    for method in full_spec["method_groups"]:
        required=method_groups.for_method(method)
        if set(required)<=set(selected) and not set(required)<=checked:
            check(method);checked.update(required)
    result=check(args.method or "baseline.table1");save(state,{"schema_version":"ye1-toolkit-install-state@3.0","product_root":str(ROOT),"version":spec["product_version"],"status":"complete","installed_groups":selected,"logs":str(logdir)})
    print(json.dumps({**result,"status":"INSTALLED_AND_VERIFIED","target":str(runtime),"logs":str(logdir),"global_environment_modified":False}));return 0

if __name__=="__main__":
    for stream in [sys.stdout,sys.stderr]:
        if hasattr(stream,"reconfigure"):stream.reconfigure(encoding="utf-8")
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as error:
        print(json.dumps({"status":"INSTALLATION_NOT_COMPLETE","reason_code":getattr(error,"code","INSTALLER_FAILED"),"next":"Keep install-logs; correct the prerequisite or network problem and rerun the same installer. Do not edit code or locks."}));raise SystemExit(2)
