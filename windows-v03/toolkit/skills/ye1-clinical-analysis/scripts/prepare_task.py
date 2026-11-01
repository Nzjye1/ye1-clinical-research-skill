"""Compile an explicit local draft without interactive prompts."""
from pathlib import Path
import argparse,copy,datetime,importlib.util,json,os,secrets,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_toolkit import ROOT,BACKEND,CORE,env,check,save,sha
from runtime_platform import runtime_python
import ingestion as i
import toolkit

def prepare(path,practice=False):
    path=Path(path).resolve();draft=toolkit.load(path)
    i.need(set(draft)=={"schema_version","method_id","data_origin","task_purpose","project_root","local_tables","task"} and draft["schema_version"]=="ye1-toolkit-draft@1.0","LOCAL_DRAFT_SCHEMA_INVALID")
    project=Path(draft["project_root"]).resolve();i.need(project.is_dir() and path.is_relative_to(project),"DRAFT_INSIDE_PROJECT_REQUIRED")
    i.confined(path,project);method=toolkit.definition(draft["method_id"]);i.need(toolkit.kind(method)!="legacy_restricted" and method["task_family"] not in {"result_view","compat_planning"},"ANALYSIS_DRAFT_METHOD_REQUIRED")
    task=draft["task"];origin=draft["data_origin"];purpose=draft["task_purpose"]
    i.need(origin in {"real","synthetic"} and (purpose=="engineering_test" if origin=="synthetic" else purpose=="research_analysis"),"ORIGIN_PURPOSE_CONFLICT")
    i.need(task.get("data_origin")==origin and task.get("task_purpose")==purpose and Path(task["project_root"]).resolve()==project,"DRAFT_TASK_ORIGIN_OR_PROJECT_MISMATCH")
    i.need(task.get("analysis",{}).get("method_id",task.get("method_id"))==method["backend_method_id"],"DRAFT_METHOD_MISMATCH")
    out=i.confined(task["execution"]["output_dir"],project);i.need(out!=project and not out.exists(),"FRESH_ANALYSIS_OUTPUT_REQUIRED")
    task["project_root"]=str(project);task["execution"]["output_dir"]=str(out)
    for view in task.get("views",[]):
        if isinstance(view.get("local_ref"),str):view["local_ref"]=str(i.confined(view["local_ref"],project))
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+"-"+secrets.token_hex(8)
    if practice:
        i.need(origin=="synthetic","PRACTICE_CANNOT_AUTHORIZE_REAL_DATA");record=project/"practice-confirmations"/(stamp+".json");save(record,{"status":"PRACTICE_ONLY_NO_REAL_AUTHORIZATION","draft_sha256":sha(path),"source_files_read":False,"project_choice_created":False});return {"status":"PRACTICE_ONLY_NO_REAL_AUTHORIZATION","record":str(record)}
    sys.path.insert(0,str(CORE/"python"));from clinical_methods import resource_budget
    resolved=resource_budget.resolve(task["execution"],method["backend_method_id"])
    limits={k:resolved[k] for k in ("max_rows","max_bytes","max_decoded_bytes")}
    check(draft["method_id"]);authorization,reference=None,None
    if origin == "real" and (project/".ye1-privacy/choice.json").exists():
        sys.path.insert(0,str(BACKEND/"integration"));import captured_study
        captured_study._choice(project,captured_study._layout(CORE))
    files=[];task=i.materialize(copy.deepcopy(task),draft["local_tables"],project,limits,files);i.need(files,"LOCAL_BOUND_SOURCE_REQUIRED")
    receipt=project/"private/prepared"/(stamp+"-ingestion.json");save(receipt,{"schema_version":"ye1-local-ingestion@1.0","draft_sha256":sha(path),"data_origin":origin,"files":files,"normalization":"explicit mapping/types/missing codes; no sampling, renaming, model or design inference","source_identity_authenticated":False})
    task["sources"][0]["evidence_refs"].append(i.PREFIX+sha(receipt)+":"+receipt.relative_to(project).as_posix())
    task["authorization"]=authorization;task["execution"]["authorization_ref"]=reference
    sys.path.insert(0,str(CORE/"python"));from clinical_methods import contracts as c
    if task.get("schema_version")=="clinical-study-input@1.0":
        task=c.seal_task(task,CORE)
        if authorization:
            task["authorization"]["plan_sha256"]=c._study_input.plan_scope_hash(task,c.canonical_hash)
            task=c.seal_task(task,CORE)
    else:
        i.need(task.get("schema_version") in {"clinical-module-task@1.1","ye1-compat-study@1.0"},"CURRENT_ORIGIN_AWARE_TASK_REQUIRED")
        sys.path.insert(0,str(BACKEND/"integration"));import module_task
        task["sources"][0]["source_fingerprint"]=module_task.canonical(task["payload"])
        if authorization:authorization["plan_sha256"]=c._study_input.plan_scope_hash(task,c.canonical_hash)
        if task["schema_version"]=="ye1-compat-study@1.0":
            from legacy_analysis import plan_hash
            task["plan_sha256"]=plan_hash(task)
        else:task["plan_sha256"]=module_task.plan_hash(task)
    out.parent.mkdir(parents=True,exist_ok=True)
    target=project/"private/prepared"/(stamp+"-task.json");save(target,task)
    i.need(target.stat().st_size<=2_000_000,"NORMALIZED_TASK_BYTE_BUDGET_EXCEEDED")
    return {"status":"LOCAL_TASK_PREPARED_NOT_ANALYSED","task":str(target),"receipt":str(receipt),"method_id":draft["method_id"],"export_grants_added":0,"data_sent":False,"scientific_review":"pending"}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--draft",required=True);p.add_argument("--practice",action="store_true");a=p.parse_args();print(json.dumps(prepare(a.draft,a.practice),ensure_ascii=False))
if __name__=="__main__":
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,"reconfigure"):stream.reconfigure(encoding="utf-8")
    try:
        selected=runtime_python(ROOT)
        if selected.is_file() and Path(sys.executable).resolve()!=selected.resolve():raise SystemExit(subprocess.run([str(selected),"-I","-B","-X","utf8",str(Path(__file__).resolve()),*sys.argv[1:]],env=env()).returncode)
        main()
    except (OSError,ValueError,KeyError,TypeError,ImportError,EOFError,KeyboardInterrupt,subprocess.TimeoutExpired) as error:
        fallback="USER_CANCELLED" if isinstance(error,KeyboardInterrupt) else "LOCAL_DRAFT_INVALID"
        value={"status":"LOCAL_TASK_NOT_PREPARED","reason_code":getattr(error,"code",fallback),"action":"Keep local evidence; the Agent should clarify or repair the draft. Do not edit raw data, scientific contracts or authorization records to force success."}
        try:
            index=sys.argv.index("--draft");folder=Path(sys.argv[index+1]).resolve().parent/"support-logs";folder.mkdir(exist_ok=True)
            diagnostic=folder/(datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+"-preparation.json");save(diagnostic,value);value["support_log"]=str(diagnostic)
        except (OSError,ValueError,IndexError):pass
        print(json.dumps(value));raise SystemExit(2)
