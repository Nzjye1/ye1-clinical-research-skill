"""Portable analysis adapter. Estimation and strict validation remain upstream."""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, math, os, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "_shared/clinical_analysis"
CORE = BACKEND / "integration/core"
METHODS = {"baseline.table1", "association.logistic", "survival.kaplan_meier", "survival.cox.association"}
VERSION = "0.2.0-windows-candidate1"
sys.path.insert(0,str(ROOT/"scripts"))
from runtime_platform import runtime_python

class Blocked(ValueError):
    def __init__(self, code): self.code = code; super().__init__(code)

def need(value, code):
    if not value: raise Blocked(code)

def input_action(code):
    return {
        "FIELD_NAMES_INVALID":"fields.name须为ASCII字母开头的唯一规范名（仅字母、数字、下划线）；中文原表头放column，不改原CSV。",
        "SOURCE_COLUMN_LABEL_INVALID":"column及unselected_columns须为1至256字符的非空实际表头，不含控制字符；按原样匹配，不自动去空格、转大小写或重命名。",
        "COLUMN_MAP_NOT_ONE_TO_ONE":"每个规范字段必须映射不同的实际源列；不能让两个字段使用同一列。请核对字典，保留原CSV。",
        "COLUMN_PROJECTION_CONFLICT":"unselected_columns不可重复，也不能含已映射的源列。请明确每列用途，不静默删列。",
        "CSV_HEADER_INVALID":"CSV表头缺失或含重复列名。保留原件，先澄清每列含义；如另存修订副本须记录对照，不能自动选择第一列。",
        "CSV_UNDECLARED_OR_MISSING_COLUMN":"实际CSV表头与column和unselected_columns不一致：可能缺少指定列，或有未声明列。核对精确拼写、大小写和空格；不自动删列或编造字段。",
    }.get(code,"Ask the Agent to review the declared fields/design or installation status; do not edit source data, analysis code or locks to force success.")

def source_columns(fields,unselected):
    labels=[f.get("column",f["name"]) for f in fields]
    need(isinstance(unselected,list),"SOURCE_COLUMN_LABEL_INVALID")
    need(all(isinstance(x,str) and bool(x.strip()) and re.fullmatch(r"[^\x00-\x1f\x7f-\x9f]{1,256}",x) for x in labels+unselected),"SOURCE_COLUMN_LABEL_INVALID")
    need(len(set(labels))==len(labels),"COLUMN_MAP_NOT_ONE_TO_ONE")
    need(len(set(unselected))==len(unselected) and not set(labels).intersection(unselected),"COLUMN_PROJECTION_CONFLICT")
    return dict(zip([f["name"] for f in fields],labels))

def load(path):
    need(Path(path).stat().st_size <= 2*1024*1024, "PLAN_BYTE_LIMIT")
    def pairs(items):
        d = {}
        for k, v in items:
            need(k not in d, "DUPLICATE_JSON_KEY"); d[k] = v
        return d
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(Blocked("NONFINITE_JSON")))

def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False); f.write("\n")

def api():
    sys.path.insert(0, str(CORE / "python"))
    from clinical_methods import contracts
    return contracts

def runtime():
    from runtime_windows import check
    check()
    path = ROOT / ".clinical-local/agent-runtime.json"
    need(path.is_file() and (CORE / "runtime-lock.json").is_file(), "RUNTIME_CONFIGURATION_REQUIRED")
    config = load(path)
    need(Path(config["integration_root"]).resolve() == (BACKEND / "integration").resolve(), "RUNTIME_RECONFIGURE_AFTER_MOVE")
    return path

def build(plan):
    allowed = {"schema_version", "method", "source", "source_sha256", "project", "output", "data_origin", "task_purpose",
        "study_id", "estimand", "independent_subjects", "fields", "unselected_columns", "baseline", "logistic", "survival",
        "authorization", "authorization_ref", "max_rows", "max_bytes", "max_decoded_bytes", "plan_confirmation"}
    need(isinstance(plan, dict) and not set(plan)-allowed, "PLAN_FIELDS_INVALID")
    need(plan.get("schema_version") == "ye1-analysis-plan@1.0", "PLAN_VERSION_INVALID")
    method = plan.get("method"); need(method in METHODS, "METHOD_NOT_SUPPORTED")
    need(plan.get("independent_subjects") is True, "INDEPENDENT_SUBJECTS_REQUIRED")
    origin = plan.get("data_origin"); need(origin in {"synthetic", "real"}, "DATA_ORIGIN_REQUIRED")
    project = Path(plan["project"]).resolve(); source = Path(plan["source"]).resolve(); out = Path(plan["output"]).resolve()
    need(project.is_dir() and source.is_relative_to(project), "SOURCE_INSIDE_PROJECT_REQUIRED")
    need(out.is_relative_to(project) and out != project and not out.exists() and out.parent.is_dir(), "FRESH_OUTPUT_REQUIRED")
    import ingestion
    ingestion.confined(plan["source"], project)
    need(source.is_file(), "SOURCE_FILE_REQUIRED")
    need(plan.get("task_purpose", "engineering_test") == ("research_analysis" if origin == "real" else "engineering_test"), "ORIGIN_PURPOSE_CONFLICT")
    need(source.stat().st_size <= plan.get("max_bytes", 2_000_000), "INPUT_BYTE_BUDGET_EXCEEDED")
    actual_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    need(not plan.get("source_sha256") or plan["source_sha256"] == actual_sha256, "SOURCE_CHANGED")
    fields = plan.get("fields"); need(isinstance(fields, list) and fields, "FIELDS_REQUIRED")
    names = [f.get("name") for f in fields]
    need(all(isinstance(n, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", n) for n in names) and len(set(names))==len(names), "FIELD_NAMES_INVALID")
    column_map=source_columns(fields,plan.get("unselected_columns",[]))
    ids = [f["name"] for f in fields if f.get("role")=="id"]
    need(len(ids)==1, "ONE_SUBJECT_KEY_REQUIRED")
    c = api()
    # Build only metadata against a nonexistent path; never read a real source in the synthetic helper.
    dummy = project / (".metadata-only-" + hashlib.sha256(str(source).encode()).hexdigest() + ".absent")
    need(not dummy.exists(), "METADATA_TEMPLATE_PATH_OCCUPIED")
    task = c.make_survival_task(dummy, out, CORE, method, "SELF_FILE") if method.startswith("survival.") else c.make_example_task(dummy, out, CORE, "SELF_FILE")
    task.update(schema_version="clinical-study-input@1.0", data_origin=origin,
        task_purpose=plan.get("task_purpose", "engineering_test"), project_root=str(project),
        authorization=None, study_id=plan["study_id"], estimand=plan["estimand"])
    task["sources"][0].update(source_kind="synthetic_fixture" if origin=="synthetic" else "user_clinical_file",
        snapshot=plan["study_id"], period="user_declared", verification_status="local_bytes_bound",
        source_fingerprint=actual_sha256, evidence_refs=["local_plan_and_source_bytes"])
    task["identity"].update(subject_key=ids[0], record_keys=[ids[0]])
    task["split"]["group_key"] = ids[0]
    task["variables"] = []
    survival = method.startswith("survival.")
    for f in fields:
        need(not set(f)-{"name","column","type","role","unit","dimension","levels","reference","definition"}, "FIELD_OPTIONS_UNSUPPORTED")
        need(f.get("type") in {"id", "number", "category"} and f.get("role") in {"id", "exposure", "covariate", "group", "descriptive_measure", "stratification_label", "outcome_summary", "outcome", "survival_time", "survival_status"}, "FIELD_DEFINITION_INVALID")
        levels = f.get("levels", [])
        endpoint = f["role"] in {"survival_time", "survival_status"}
        unit=f.get("unit","1")
        dimension=f.get("dimension",c.UNIT_DIMENSIONS.get(unit))
        need(isinstance(dimension,str) and bool(dimension.strip()),"UNIT_DIMENSION_DEFINITION_REQUIRED")
        task["variables"].append({"name":f["name"], "dtype":f["type"], "role":f["role"],
            "unit":unit, "source_unit":unit, "dimension":dimension,
            "conversion":{"scale":1, "offset":0}, "levels":levels, "reference":f.get("reference", levels[0] if levels else None),
            "codes":{v:v for v in levels}, "missing_codes":["", "NA"], "occurred_at":plan.get("survival", {}).get("observation_end") if endpoint else 0 if survival else None,
            "available_at":plan.get("survival", {}).get("observation_end") if endpoint else 0 if survival else None,
            "concept":f.get("definition", f["name"]), "codebook_version":"user-plan-v1", "aggregation":"already_one_value_per_row"})
    task["views"][0].update(local_ref=str(source), content_hash=actual_sha256,
        column_map=column_map, keys=ids,
        format="csv_gzip" if source.name.endswith(".gz") else "csv", unselected_columns=plan.get("unselected_columns", []))
    task["execution"].update(mode="local", authorization_ref=None,
        max_rows=plan.get("max_rows",1000), max_bytes=plan.get("max_bytes",2_000_000), max_decoded_bytes=plan.get("max_decoded_bytes",4_000_000))
    if origin=="real": task["execution"]["privacy_profile"]="captured_local_process"
    task["analysis"].update(method_id=method, baseline=None, spec=None)
    if method=="baseline.table1":
        need(isinstance(plan.get("baseline"),dict), "BASELINE_VARIABLES_REQUIRED")
        task.update(purpose="descriptive", outcome=None)
        task["analysis"].update(baseline=plan["baseline"], effect_scale="descriptive", variance="not_applicable")
    elif method=="association.logistic":
        opts = plan.get("logistic", {})
        need(not set(opts)-{"outcome","exposure","covariates","event","non_event","definition"}, "LOGISTIC_OPTIONS_UNSUPPORTED")
        need(all(opts.get(k) for k in ["outcome", "exposure", "event", "non_event", "definition"]), "OUTCOME_EXPOSURE_AND_EVENT_DEFINITION_REQUIRED")
        need(opts["event"] != opts["non_event"], "EVENT_CODES_MUST_DIFFER")
        task["purpose"]="association"
        task["outcome"].update(field=opts["outcome"], type="binary", event=opts["event"], non_event=opts["non_event"], definition=opts["definition"])
        used = [opts["exposure"], *opts.get("covariates", [])]
        task["analysis"].update(effect_scale="odds_ratio", variance="model", spec={"model":"logistic", "outcome":opts["outcome"],
            "exposure":opts["exposure"], "covariates":opts.get("covariates",[]), "missing":"complete_case", "covariance":"model",
            "categorical":{f["name"]:{"levels":f["levels"], "reference":f.get("reference", f["levels"][0])} for f in fields if f["type"]=="category" and f["name"] in used},
            "row_unit":"subject", "independent":True, "key":ids, "subject_id":ids[0], "sensitivity":[], "event":opts["event"], "non_event":opts["non_event"]})
    else:
        opts=plan.get("survival", {})
        need(not set(opts)-{"time","status","time_unit","time_zero_definition","event_definition","censoring_definition","event_code","censor_code","observation_end","evaluation_times","no_competing_events","covariates_available_at_zero","covariates"}, "SURVIVAL_OPTIONS_UNSUPPORTED")
        need(all(opts.get(k) for k in ["time", "status", "time_unit", "time_zero_definition", "event_definition", "censoring_definition", "event_code", "censor_code", "observation_end", "evaluation_times"]), "SURVIVAL_DEFINITIONS_REQUIRED")
        need(opts.get("no_competing_events") is True and opts.get("covariates_available_at_zero") is True, "SURVIVAL_DESIGN_CONFIRMATION_REQUIRED")
        end=opts["observation_end"]; task["purpose"]="survival"
        task["cohort"]["index_event"]=opts["time_zero_definition"]
        task["time"].update(unit=opts["time_unit"], policy="ordered_observation", index=0,feature_cutoff=0,eligibility_window=[-1,0], observation_end=end,outcome_window=[0,end],label_mature_at=end,analysis_as_of=end,boundary="(0,end]")
        task["outcome"].update(field=opts["status"],type="time_to_event",event=opts["event_code"],non_event=opts["censor_code"],definition=opts["event_definition"],censoring="right")
        spec=task["analysis"]["survival"]
        for k in ["time", "status", "time_unit", "time_zero_definition", "event_definition", "censoring_definition", "event_code", "censor_code", "evaluation_times"]: spec[k]=opts[k]
        spec.update(subject_id=ids[0],covariates=[])
        for name in opts.get("covariates", []):
            f=next((x for x in fields if x["name"]==name), None); need(f is not None,"COVARIATE_FIELD_REQUIRED")
            item={"name":name,"type":"numeric" if f["type"]=="number" else "category","available_at_time_zero":True}
            if f["type"]=="category":item.update(levels=f["levels"],reference=f.get("reference",f["levels"][0]))
            spec["covariates"].append(item)
    if not survival:
        task["time"].update(policy="descriptive_snapshot" if method=="baseline.table1" else "cross_sectional_association", timezone="not_applicable",index=None,feature_cutoff=None,outcome_window=None,label_mature_at=None,analysis_as_of=None)
    task["cohort"].update(target_population=plan["estimand"],inclusion=["all rows in the declared source; no implicit sampling"],exclusion=[],selection_order=["declared input", "method-specific complete cases"])
    return c.seal_task(task, CORE)

def execute(plan_path, validate_only=False):
    config = runtime(); plan=load(plan_path); task=build(plan)
    prepared = api().validate_task(task, CORE) if plan["data_origin"]=="synthetic" else None
    out=Path(task["execution"]["output_dir"]); taskfile=out.parent / "private" / (out.name+".prepared-task.json")
    save(taskfile, task)
    command=[sys.executable,"-B","-X","utf8",str(BACKEND/"agent/analysis_call.py"),"--catalog",str(BACKEND/"agent/catalog.json"),"--runtime",str(config),"validate" if validate_only else "run",plan["method"],"--task",str(taskfile)]
    # Raw runner streams always stay local. This adapter emits fixed status only.
    log=taskfile.with_suffix(".adapter.log")
    with log.open("xb") as stream:
        from runtime_windows import env
        done=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=180,cwd=ROOT,env=env())
    if done.returncode:
        if (out/"result.json").is_file() and load(out/"result.json").get("execution_status") in {"complete","partial"}:
            return {"status":"ANALYSIS_COMPUTED_ARTIFACT_REVIEW_REQUIRED","reason_code":"LOCAL_PRESENTATION_OR_PARTIAL_RESULT","output":str(out),"support_log":str(log),"scientific_review":"pending"},1
        status={"status":"blocked","reason_code":"BACKEND_REJECTED","support_log":str(log)}
        try:
            detail=json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1]); status["reason_code"]=detail.get("reason_code") or status["reason_code"]
        except (ValueError,OSError): pass
        status["action"]=input_action(status["reason_code"])
        return status,2
    if validate_only: return {"status":"CONTRACT_VALIDATED_NOT_EXECUTED","method":plan["method"]},0
    if not (out/"presentation-manifest.json").is_file():
        return {"status":"ANALYSIS_COMPUTED_ARTIFACT_REVIEW_REQUIRED", "reason_code":"LOCAL_PRESENTATION_NOT_COMPLETE", "output":str(out), "scientific_review":"pending"},1
    return {"status":"ANALYSIS_COMPLETED", "method":plan["method"],"output":str(out),"scientific_review":"pending"},0

def report(output, task=None):
    output=Path(output).resolve(); result=load(output/"result.json")
    real=result.get("data_origin")=="real"
    if real:
        need(task is not None and task.get("data_origin")=="real", "REAL_REPORT_REQUIRES_CAPTURED_TASK")
        sys.path.insert(0,str(BACKEND/"integration"));import captured_study
        captured_study.verify_context(Path(task["project_root"]),task,CORE)
        need(result.get("binding",{}).get("plan_hash")==task["plan_hash"],"REPORT_PLAN_BINDING_MISMATCH")
    else:need(result.get("data_origin")=="synthetic","REPORT_ORIGIN_UNSUPPORTED")
    need(result.get("execution_status") in {"complete","partial"}, "COMPUTED_RESULT_REQUIRED")
    lines=["# 临床统计分析结果", "", "用户指定CSV的本地计算结果；尚未科学复核，不自动外发。" if real else "合成软件验收数据；不得作为临床研究结论。", "",f"方法：`{result['method_id']}`；版本：`{result['method_version']}`。", "", "本次只运行选定分析；完整案例及各变量缺失分母以随附表和样本流为准。", ""]
    counts=result.get("counts",{})
    flow=(f"输入记录 {counts.get('source_rows','未提供')}；描述统计的有效人数和缺失按各变量分别计数，见表中的分母。" if result["method_id"]=="baseline.table1" else f"输入记录 {counts.get('source_rows','未提供')}；用于本次方法 {counts.get('model_n') or '见表'}；因所需字段缺失排除 {counts.get('excluded_missing') if counts.get('excluded_missing') is not None else '见表'}。")
    lines.extend(["## 本次数值概览","",flow+"这是本次软件样本流，不自动等于正式研究样本。",""])
    if result["method_id"] in {"association.logistic","survival.cox.association"}:
        scale="OR" if result["method_id"]=="association.logistic" else "HR"
        for item in result.get("estimates",[]):
            if item.get("term")=="intercept":continue
            ci=item["ci"];compat="区间包含1，数据仍与无关联值相容" if ci["lower"]<=1<=ci["upper"] else "该区间未跨1；解释仍受设计和模型假设限制"
            lines.append(f"- {item['term']}：{scale} {item['estimate']:.4g}，95% CI {ci['lower']:.4g}–{ci['upper']:.4g}；{compat}。")
        lines.append("")
    for table in sorted((output/"tables").glob("*.csv")):
        # Retain every full aggregate CSV, but keep the customer preview legible.
        with table.open(encoding="utf-8-sig",newline="") as f: rows=list(csv.reader(f))
        titles={"table1":"基线描述表","table1_statistics":"基线完整统计量","effect_estimates":"效应估计","survival_curve":"预定时点与风险集","survival_summary":"生存样本流与定义","ph_diagnostics":"描述性PH诊断","ph_score_tests":"正式PH score检验"}
        lines.extend([f"## {titles.get(table.stem,table.stem)}", "",f"[完整精度 CSV]({table.relative_to(output).as_posix()})", ""])
        preview={"effect_estimates":["term","estimate","ci_lower","ci_upper","p","denominator"],"survival_curve":["time","n_at_risk","estimate","ci_lower","ci_upper"],"survival_summary":["n_total","n_used","n_excluded_missing","events","censored"],"ph_diagnostics":["term","rho","ph_assumption_verified"]}
        labels={"term":"变量/对比","estimate":"估计值","ci_lower":"95%CI下界","ci_upper":"95%CI上界","p":"P值","denominator":"分析人数","time":"时间","n_at_risk":"风险集人数","n_total":"输入记录","n_used":"使用记录","n_excluded_missing":"缺失排除","events":"事件","censored":"删失","rho":"描述性相关","ph_assumption_verified":"PH假设已证明"}
        if table.stem=="table1_statistics":
            lines.extend(["完整底数用于复核；主要描述见基线描述表。",""]);continue
        if rows and table.stem in preview:
            header=rows[0];selected=[x for x in preview[table.stem] if x in header];indices=[header.index(x) for x in selected]
            selected_rows=[]
            for row in rows[1:]:
                if table.stem=="effect_estimates" and row[header.index("term")]=="intercept":continue
                values=[]
                for i in indices:
                    value=row[i]
                    try:value=format(float(value),".5g") if value else value
                    except ValueError:pass
                    values.append(value)
                selected_rows.append(values)
            rows=[[labels.get(x,x) for x in selected],*selected_rows]
        if rows:
            esc=lambda x:x.replace("|","\\|").replace("\n"," ")
            lines.extend(["|"+"|".join(map(esc,rows[0]))+"|","|"+"|".join("---" for _ in rows[0])+"|"])
            lines.extend("|"+"|".join(map(esc,row))+"|" for row in rows[1:13])
            if len(rows)>13: lines.append("仅预览前12行；完整精度及全部结果见CSV，计算未截断。")
            lines.append("")
    for figure in sorted((output/"figures").glob("*.png")):
        lines.extend([f"![{figure.stem}]({figure.relative_to(output).as_posix()})",""])
    if (output/"display/km-step.png").is_file():
        lines.extend(["## 完整 KM 阶梯展示", "", "预定时点推断表保持原样；此图用相同数值 owner 在全部观察时点展示阶梯，未另选假设或模型。", "", "![完整 KM 阶梯图](display/km-step.png)", "", "[阶梯底数与来源绑定](display/manifest.json)", ""])
    mid=result["method_id"]
    interpretation = "连续变量统计量与分类比例描述当前样本的分布，比例需连同相应非缺失分母阅读；组间表不自动证明组间差异。" if mid=="baseline.table1" else "OR 是给定所列协变量后的优势比，不等于风险比或因果效应；95% CI 跨 1 表示数据未排除无关联，不能为显著性改模型。" if mid=="association.logistic" else "KM 描述在独立右删失假设下的事件未发生概率，须核对风险集与删失；不能把竞争事件直接删失后解释成目标事件绝对风险。" if mid=="survival.kaplan_meier" else "HR 为所列协变量条件下的相对瞬时风险，属于模型条件下的关联估计，不自动证明因果。"
    if mid=="survival.cox.association":
        ph=result.get("survival",{}).get("ph_score_test")
        if isinstance(ph,dict) and ph.get("status")=="completed":
            interpretation+=(f" 本次已完成预设的正式 PH score 检验（方法 {ph.get('method')}；时间变换 {ph.get('transform')}；"
                             f"ties={ph.get('ties')}；terms={ph.get('terms')}；global={ph.get('global')}；singledf={ph.get('singledf')}）。"
                             " 逐项和/或GLOBAL结果按本次设置见[正式PH检验表](tables/ph_score_tests.csv)，各项完成状态以表中status为准。"
                             " 正式检验评估所选时间变换下与PH不相容的证据；单项与整体检验不能相互替代，P值未达阈值也不证明PH假设成立。")
        elif isinstance(ph,dict) and ph.get("status") not in {None,"not_requested"}:
            interpretation+=(f" 本次正式 PH score 检验尚未全部完成（status={ph.get('status')}）；"
                             "请按正式PH检验表及result.json中的逐项状态和原因解释，不能宣称全部正式检验已完成。")
        else:
            interpretation+=" 本次仅提供描述性Schoenfeld残差与对数时间的秩相关诊断，未执行正式 PH score 检验；描述性相关及其图形不能验证PH假设成立。"
        interpretation+=" PH假设仍需结合描述性诊断、研究设计和科学复核判断。随附生存概率表/图是完整案例队列的KM描述，不是调整后的Cox生存预测。"
    lines.extend(["## 解释与边界","",interpretation,"","科学复核状态 pending。本报告不提供临床建议或可发表结论。方法诊断、剔除与失败原因保存在 result.json 及日志中。","","本报告、图表、原件、private与日志均先留本地。任何对话回传或外发须另有明确审阅与授权，本次确认未自动授予。",""])
    target=output/"报告.md"
    with target.open("x",encoding="utf-8") as f:f.write("\n".join(lines))

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest="action",required=True)
    doctor=sub.add_parser("doctor")
    sub.add_parser("capabilities")
    for name in ["validate", "run"]: sub.add_parser(name).add_argument("--plan",required=True)
    sub.add_parser("report-synthetic").add_argument("--output",required=True)
    args=p.parse_args()
    if args.action=="doctor":
        from runtime_windows import check
        value=check();value["version"]=VERSION
        print(json.dumps(value));return 0
    if args.action=="capabilities":print(json.dumps({"version":VERSION,"methods":sorted(METHODS),"runtime_bundled":False,"cold_install_tested":False,"workbuddy_tested":False}));return 0
    if args.action=="report-synthetic":report(args.output);print(json.dumps({"status":"SYNTHETIC_REPORT_WRITTEN"}));return 0
    value,code=execute(args.plan,args.action=="validate"); print(json.dumps(value,ensure_ascii=False));return code

if __name__=="__main__":
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,"reconfigure"):stream.reconfigure(encoding="utf-8")
    try:
        selected=runtime_python(ROOT)
        if selected.is_file() and Path(sys.executable).resolve()!=selected.resolve():
            from runtime_windows import env
            raise SystemExit(subprocess.run([str(selected),"-I","-B","-X","utf8",str(Path(__file__).resolve()),*sys.argv[1:]],env=env()).returncode)
        raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,StopIteration,subprocess.TimeoutExpired) as e:
        code=getattr(e,"code","INVALID_INPUT_OR_LOCAL_PREREQUISITE")
        value={"status":"blocked", "reason_code":code,"action":input_action(code)}
        try:
            import datetime
            index=sys.argv.index("--plan")
            plan_path=Path(sys.argv[index+1]).resolve()
            if not plan_path.is_file():raise OSError("no plan context")
            folder=plan_path.parent/"support-logs";folder.mkdir(exist_ok=True)
            diagnostic=folder/(datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".json")
            with diagnostic.open("x",encoding="utf-8") as f:json.dump(value,f,indent=2)
            value["support_log"]=str(diagnostic)
        except (OSError,ValueError,IndexError):pass
        print(json.dumps(value));raise SystemExit(2)
