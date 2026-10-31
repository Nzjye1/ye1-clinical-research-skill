"""Compile an Agent-authored local draft; customers review a local scope file."""
from pathlib import Path
import argparse,copy,datetime,importlib.util,json,os,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_toolkit import ROOT,BACKEND,CORE,env,check,save,sha
from runtime_platform import runtime_python
import ingestion as i
import toolkit

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
def review(draft,method):
    return "\n".join(["本次本地分析范围（不含数据行）", "", "普通 Codex 具有文件和命令权限。本工具只捕获本次调用，不保证全局主机或网络隔离。", "B 选项仅允许本次指定文件与计划的本地计算；不增加任何对话回传或外发授权。需要严格隔离时请停止。", "", "方法："+method["title"]+" / "+draft["method_id"],"",json.dumps(draft,ensure_ascii=False,indent=2),"", "请核对字段、单位、结局、时间、分组、缺失规则、模型参数、样本划分及冻结模型来源。缺失项由 Agent 澄清和修改，不让客户修代码。", "原始行、private 和日志留本地，统计结果仍需科学复核。"])

def confirm(draft,project,stamp,method):
    from local_console import interactive_input
    i.need(interactive_input(),"LOCAL_HUMAN_CONFIRMATION_REQUIRED")
    privacy=module("toolkit_original_choice",BACKEND/"legacy/scripts/privacy_boundary.py");existing=None
    if (project/".ye1-privacy/choice.json").exists():
        existing,_=privacy.load(project);i.need(existing["mode"]=="B","EXISTING_STRICT_MODE_REQUIRES_REVIEW")
    scope=project/"local-review"/("scope-"+stamp+".txt");scope.parent.mkdir(exist_ok=True);scope.write_text(review(draft,method),encoding="utf-8")
    print("请在本地打开并核对："+str(scope));print("不要上传 CSV 原始行。范围不正确时取消，由 Agent 修改计划。")
    history=input("请如实说明此前是否上传过该文件、上传到何处；不要输入患者信息：").strip();i.need(0<len(history)<=500,"ATTACHMENT_HISTORY_STATEMENT_REQUIRED")
    phrase="确认本次指定文件和分析计划的本地分析，不自动外发";print("同意上述范围时手动输入："+phrase)
    answer=input().strip();i.need(answer==phrase,"USER_DID_NOT_CONFIRM")
    state=project/".ye1-privacy";record=state/"evidence"/("terminal-"+stamp+".txt");record.parent.mkdir(parents=True,exist_ok=True)
    record.write_text("本地终端确认；不是身份认证或主机隔离证明。\n实际输入："+answer+"\n历史上传声明："+history+"\n范围 SHA256："+sha(scope)+"\n",encoding="utf-8")
    choice=existing or {"schema":"ye1-data-choice/1","mode":"B","attachment_history":[{"user_statement":history}],"grants":[]}
    evidence={"kind":"direct_user","path":record.relative_to(project).as_posix(),"sha256":sha(record),"locator":"local terminal input "+stamp,"quote":answer,"scope_sha256":privacy.digest(privacy.encoded(choice))}
    if not existing:privacy.save_choice(project,choice,evidence,test_only=False)
    probe=subprocess.run([sys.executable,"-I","-c","import sys;print('capture-stdout');print('capture-stderr',file=sys.stderr)"],capture_output=True,env=env(),timeout=15)
    i.need(probe.returncode==0 and b"capture-stdout" in probe.stdout and b"capture-stderr" in probe.stderr,"LOCAL_CAPTURE_ASSESSMENT_FAILED")
    assessment=state/("capture-assessment-"+stamp+".json");save(assessment,{"scope":"this fixed captured invocation only","stdout_stderr_capture_checked":True,"global_host_isolation":False,"network_isolation":False,"identity_authentication":False,"adapter_sha256":sha(BACKEND/"integration/captured_study.py")})
    capture=module("toolkit_capture_registration",BACKEND/"integration/captured_study.py");capture.register(project,CORE,str(assessment)+" sha256="+sha(assessment))
    return {"choice_sha256":sha(state/"choice.json"),"plan_sha256":"0"*64,"scope_kind":"research_plan","confirmation":{"source_kind":"direct_user","source_path":str(record),"source_locator":"local terminal input "+stamp,"quote":answer}},sha(record)

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
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if practice:
        i.need(origin=="synthetic","PRACTICE_CANNOT_AUTHORIZE_REAL_DATA");record=project/"practice-confirmations"/(stamp+".json");save(record,{"status":"PRACTICE_ONLY_NO_REAL_AUTHORIZATION","draft_sha256":sha(path),"source_files_read":False,"project_choice_created":False});return {"status":"PRACTICE_ONLY_NO_REAL_AUTHORIZATION","record":str(record)}
    sys.path.insert(0,str(CORE/"python"));from clinical_methods import resource_budget
    resolved=resource_budget.resolve(task["execution"],method["backend_method_id"])
    limits={k:resolved[k] for k in ("max_rows","max_bytes","max_decoded_bytes")}
    check(draft["method_id"]);authorization,reference=confirm(draft,project,stamp,method) if origin=="real" else (None,None)
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
        fallback="LOCAL_HUMAN_CONFIRMATION_REQUIRED" if isinstance(error,EOFError) else "USER_CANCELLED" if isinstance(error,KeyboardInterrupt) else "LOCAL_DRAFT_OR_CONFIRMATION_INVALID"
        value={"status":"LOCAL_TASK_NOT_PREPARED","reason_code":getattr(error,"code",fallback),"action":"Keep local evidence; the Agent should clarify or repair the draft. Do not edit raw data, scientific contracts or authorization records to force success."}
        try:
            index=sys.argv.index("--draft");folder=Path(sys.argv[index+1]).resolve().parent/"support-logs";folder.mkdir(exist_ok=True)
            diagnostic=folder/(datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+"-preparation.json");save(diagnostic,value);value["support_log"]=str(diagnostic)
        except (OSError,ValueError,IndexError):pass
        print(json.dumps(value));raise SystemExit(2)
