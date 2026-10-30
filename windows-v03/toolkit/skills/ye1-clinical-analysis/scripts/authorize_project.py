"""User-run local confirmation for one CSV and one declared study plan.

Wraps the unchanged project-choice, direct-evidence and captured-process APIs.
It supplies no global host isolation, user identity attestation or export grant.
Synthetic practice creates no real authorization and cannot admit real data.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,os,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_windows import ROOT,BACKEND,CORE,check,need,load,sha,save,env

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def review_text(plan):
    methods={"baseline.table1":"基线描述","association.logistic":"二分类Logistic关联","survival.kaplan_meier":"单事件右删失KM","survival.cox.association":"单事件右删失Cox关联"}
    lines=["本次本地分析待确认范围","","普通Codex可能具有其他文件/shell权限。本助手只捕获本次调用，不提供全局/网络隔离或身份认证。","本次B选择只支持指定文件和方案的本地计算，不新增任何外发授权。要求Agent技术上完全无法接触原件时请停止。","原始行、private和日志不贴聊天；成果先由你本地打开，软件结果仍需科学复核。","", "研究问题："+str(plan.get("estimand","待补")),"方法："+methods.get(plan.get("method"),"未支持/待补"),"输入文件："+str(plan.get("source","待补")),"输出新目录："+str(plan.get("output","待补")),"每人一行独立观察："+str(plan.get("independent_subjects","待补")),"","变量说明（请核对含义、单位和参考类别；不是数据行）："]
    for f in plan.get("fields",[]):
        kind={"id":"唯一标识（不展示实际值）","number":"数值","category":"分类"}.get(f.get("type"),"待核")
        lines.append("- "+str(f.get("name"))+"（源列 "+str(f.get("column",f.get("name")))+"）："+str(f.get("definition","按所给字典"))+"；单位 "+str(f.get("unit","1"))+"；类型 "+kind)
        if f.get("levels"):lines.append("  类别 "+", ".join(map(str,f["levels"]))+"；参考 "+str(f.get("reference",f["levels"][0])))
    if plan.get("baseline"):
        b=plan["baseline"];denominator={"nonmissing":"各变量非缺失人数","all":"全部所选记录"}.get(b.get("categorical_denominator"),"待核")
        lines.extend(["","描述分组："+str(b.get("group") or "总体"),"分类分母："+denominator,"描述变量/统计量："+"；".join(str(x.get("name"))+"="+{"mean_sd":"均值（标准差）","median_iqr":"中位数（四分位距）",None:"分类比例"}.get(x.get("summary"),"待核") for x in b.get("variables",[]))])
    if plan.get("logistic"):
        q=plan["logistic"];lines.extend(["","结局："+str(q.get("outcome"))+"；"+str(q.get("definition")),"事件/非事件："+str(q.get("event"))+" / "+str(q.get("non_event")),"主要暴露："+str(q.get("exposure")),"预定调整："+", ".join(map(str,q.get("covariates",[]))),"缺失处理：完整案例；固定model方差，不自动选变量或为显著性换模型。"])
    if plan.get("survival"):
        s=plan["survival"];lines.extend(["","时间零点："+str(s.get("time_zero_definition")),"随访列/单位："+str(s.get("time"))+" / "+str(s.get("time_unit")),"事件定义："+str(s.get("event_definition")),"删失定义："+str(s.get("censoring_definition")),"事件/删失码："+str(s.get("event_code"))+" / "+str(s.get("censor_code")),"观察终点："+str(s.get("observation_end")),"预定评价时点："+", ".join(map(str,s.get("evaluation_times",[]))),"预定协变量："+", ".join(map(str,s.get("covariates",[]))),"无竞争事件："+str(s.get("no_competing_events"))+"；协变量在零点已可用："+str(s.get("covariates_available_at_zero")),"缺失处理：完整案例。仅独立单事件右删失，不把重复/竞争事件硬套本方法。"])
    lines.extend(["","请先让Agent修正任何缺项或错误。完整结构化计划供复核，客户不用编辑JSON。","本次不自动外发图表或报告；上述范围正确后，才在终端手工确认。",""])
    return "\n".join(lines)

def run(plan_path,practice=False):
    check();path=Path(plan_path).resolve()
    import analyze
    plan=analyze.load(path);project=Path(plan["project"]).resolve();source=Path(plan["source"]).resolve()
    need(project.is_dir() and path.is_relative_to(project) and source.is_relative_to(project),"PLAN_AND_CSV_INSIDE_PROJECT_REQUIRED")
    need(not any(p.is_symlink() or (hasattr(p,"is_junction") and p.is_junction()) for p in [source,*source.parents]),"UNSAFE_SOURCE_PATH")
    stamp=datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    if practice:
        need(plan.get("data_origin")=="synthetic" and plan.get("task_purpose","engineering_test")=="engineering_test","PRACTICE_CANNOT_AUTHORIZE_REAL_DATA")
        record=project/"practice-confirmations"/(stamp+".json")
        save(record,{"schema_version":"ye1-practice-confirmation@1.0","source_kind":"simulated","data_origin":"synthetic","real_authorization":False,"plan_sha256":sha(path),"project_choice_created":False})
        return {"status":"PRACTICE_ONLY_NO_REAL_AUTHORIZATION","record":str(record)}
    need(plan.get("data_origin")=="real" and plan.get("task_purpose")=="research_analysis","REAL_RESEARCH_PLAN_REQUIRED")
    from local_console import interactive_input
    need(interactive_input(),"LOCAL_HUMAN_CONFIRMATION_REQUIRED")
    privacy=module("project_choice_api",BACKEND/"legacy/scripts/privacy_boundary.py")
    existing=None
    if (project/".ye1-privacy/choice.json").exists():
        existing,_=privacy.load(project);need(existing["mode"]=="B","EXISTING_STRICT_MODE_REQUIRES_REVIEW")
    review=project/"local-review"/("scope-"+stamp+".txt");review.parent.mkdir(exist_ok=True)
    text=review_text(plan)
    review.write_text(text,encoding="utf-8")
    print("请在本地打开并核对范围文件："+str(review))
    print("不要把该范围文件连同CSV原件上传到对话。若变量/方案不准确，先退出让Agent只修改方案。")
    attachment=input("该文件此前是否已上传？只填是否/平台，不填患者信息（未上传也需明确写）：").strip()
    need(0<len(attachment)<=500,"ATTACHMENT_HISTORY_STATEMENT_REQUIRED")
    phrase="确认本次指定文件和方案，仅本地分析，不自动外发"
    print("如已核对且同意，请手工输入完整句子；其他输入会停止："+phrase)
    answer=input().strip();need(answer==phrase,"USER_DID_NOT_CONFIRM")
    # Only after the local user accepts file access do we read its bytes for binding.
    need(source.is_file(),"CSV_FILE_NOT_FOUND");fingerprint=sha(source)
    choice=existing or {"schema":"ye1-data-choice/1","mode":"B","attachment_history":[{"user_statement":attachment}],"grants":[]}
    state=project/".ye1-privacy";state.mkdir(exist_ok=True)
    record=state/"evidence"/("terminal-"+stamp+".txt");record.parent.mkdir(exist_ok=True)
    record.write_text("本地终端确认记录；不是身份认证或宿主隔离证明。\n实际输入："+answer+"\n历史上传声明："+attachment+"\n范围文件SHA256："+sha(review)+"\nCSV SHA256："+fingerprint+"\n",encoding="utf-8")
    evidence={"kind":"direct_user","path":record.relative_to(project).as_posix(),"sha256":sha(record),"locator":"local terminal input "+stamp,"quote":answer,"scope_sha256":privacy.digest(privacy.encoded(choice))}
    if not existing:privacy.save_choice(project,choice,evidence,test_only=False)
    # Self-assess only the capability actually offered by the original capture adapter.
    done=subprocess.run([sys.executable,"-I","-c","import sys;print('capture-stdout');print('capture-stderr',file=sys.stderr)"],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=env(),timeout=15)
    need(done.returncode==0 and b"capture-stdout" in done.stdout and b"capture-stderr" in done.stdout,"LOCAL_CAPTURE_ASSESSMENT_FAILED")
    assessment=state/("capture-assessment-"+stamp+".json")
    save(assessment,{"scope":"this fixed captured invocation only","merged_stream_capture_checked":True,"global_host_isolation":False,"network_isolation":False,"identity_authentication":False,"assessed_adapter_sha256":sha(BACKEND/"integration/captured_study.py")})
    capture=module("local_captured_registration",BACKEND/"integration/captured_study.py")
    capture.register(project,CORE,str(assessment)+" sha256="+sha(assessment))
    plan.update(source_sha256=fingerprint,authorization={},authorization_ref=sha(record),plan_confirmation=answer)
    import analyze
    task=analyze.build(plan);contracts=analyze.api()
    study=module("local_study_plan_scope",CORE/"python/clinical_methods/study_input.py")
    plan["authorization"]={"choice_sha256":sha(state/"choice.json"),"plan_sha256":study.plan_scope_hash(task,contracts.canonical_hash),"scope_kind":"research_plan","confirmation":{"source_kind":"direct_user","source_path":str(record),"source_locator":"local terminal input "+stamp,"quote":answer}}
    authorized=path.with_name(path.stem+".authorized-"+stamp+".json");need(not authorized.exists(),"FRESH_AUTHORIZED_PLAN_REQUIRED");save(authorized,plan)
    return {"status":"LOCAL_PLAN_CONFIRMATION_RECORDED","authorized_plan":str(authorized),"data_sent":False,"export_grants_added":0,"identity_authenticated":False,"host_isolation":"not_established"}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--plan",required=True);p.add_argument("--practice",action="store_true");a=p.parse_args();print(json.dumps(run(a.plan,a.practice),ensure_ascii=False))
if __name__=="__main__":
    for stream in [sys.stdout,sys.stderr]:
        if hasattr(stream,"reconfigure"):stream.reconfigure(encoding="utf-8")
    try:
        selected=ROOT/".runtime/python/Scripts/python.exe"
        if selected.is_file() and Path(sys.executable).resolve()!=selected.resolve():
            raise SystemExit(subprocess.run([str(selected),"-I","-B","-X","utf8",str(Path(__file__).resolve()),*sys.argv[1:]],env=env()).returncode)
        main()
    except EOFError:
        print(json.dumps({"status":"NO_AUTHORIZATION_GRANTED","reason_code":"LOCAL_HUMAN_CONFIRMATION_REQUIRED","next":"The user must review and confirm in their own interactive local terminal."}));raise SystemExit(2)
    except KeyboardInterrupt:
        print(json.dumps({"status":"NO_AUTHORIZATION_GRANTED","reason_code":"USER_CANCELLED"}));raise SystemExit(2)
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired) as e:
        print(json.dumps({"status":"NO_AUTHORIZATION_GRANTED","reason_code":getattr(e,"code","LOCAL_CONFIRMATION_FAILED"),"next":"Review the local scope or missing prerequisite. Do not create host credentials or edit authorization records."}));raise SystemExit(2)
