"""Local result presentation inside the same already-admitted invocation.

No grants, consent, study plan or numerical algorithm are created here.
Real tasks must still have the original active captured-process receipt.
"""
from pathlib import Path
import csv,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def general_report(task,result,output):
    method=result["method_id"];origin=task["data_origin"]
    catalog=json.loads((ROOT/"_shared/clinical_analysis/agent/catalog.json").read_text(encoding="utf-8"))
    definition=next(x for x in catalog["methods"] if x["method_id"]==method)
    description=("合成软件验收数据；不得作为临床研究结论。" if origin=="synthetic" else "用户指定资料的本地计算结果；未科学复核，不自动回传或外发。")
    lines=["# "+definition["title"],"",description,"",f"方法：`{method}`；原owner版本：`{result['method_version']}`；执行状态：`{result['execution_status']}`。",""]
    if result.get("reason_code"):lines.extend(["尚需处理的原因：`"+str(result["reason_code"])+"`。",""])
    counts=result.get("counts")
    if isinstance(counts,dict):
        selected=[(k,v) for k,v in counts.items() if isinstance(v,(int,float,str)) and "sha" not in k and k not in {"subject_id","patient_id","record_id"}]
        if selected:lines.extend(["## 样本流","","|后端字段|实际值|","|---|---:|",*["|"+str(k)+"|"+str(v)+"|" for k,v in selected],""])
    lines.extend(["## 实际表图","","完整精度、样本/缺失分母、评价集和尺度以原表及绑定元数据为准。下方仅预览原聚合表，不重新计算或改选模型。",""])
    for table in sorted((output/"tables").glob("*.csv")):
        lines.extend(["### "+table.stem,"",f"[完整CSV与同名metadata]({table.relative_to(output).as_posix()})",""])
        with table.open(encoding="utf-8-sig",newline="") as f:reader=csv.DictReader(f);rows=list(reader);columns=reader.fieldnames or []
        # A local report can link every aggregate table, but does not copy a
        # subject-level table or provenance/identifier columns into a preview.
        if any(x.lower() in {"subject_id","patient_id","id","record_id"} for x in columns):
            lines.extend(["此表含个体标识列，仅保留本地文件链接，不在预览复制。",""]);continue
        columns=[x for x in columns if not x.startswith("core_") and x not in {"result_id","run_id","study_id"} and not x.endswith("sha256")][:8]
        if columns:
            cell=lambda x:str(x).replace("|","\\|").replace("\r"," ").replace("\n"," ")
            lines.extend(["|"+"|".join(columns)+"|","|"+"|".join("---" for _ in columns)+"|"])
            for row in rows[:12]:lines.append("|"+"|".join(cell(row.get(k,"")) for k in columns)+"|")
            if len(rows)>12:lines.append(f"预览12行；完整表保留{len(rows)}行。")
            lines.append("")
    for figure in sorted((output/"figures").glob("*.png")):lines.extend([f"![{figure.stem}]({figure.relative_to(output).as_posix()})",""])
    if (output/"private/frozen-display/manifest.json").is_file():
        lines.extend(["### 冻结应用的本地受限展示","","[本地打开预测图](private/frozen-display/frozen-predictions.png)","","[逐对象预测 CSV（私有，可能包含标识）](private/frozen-display/predictions.csv) · [实际计数表](private/frozen-display/summary.csv)","","这张图仅展示原方法已经计算的私有预测值：连续评估为观测值与预测值散点和恒等线；其他情况为预测分布。未拟合新曲线，未新增临床评价指标。它保存在 private，不属于自动获准外发的公开图；图上不绘制患者标识。","","[来源、实际分母与文件哈希](private/frozen-display/manifest.json)",""])
    if method.startswith("association."):
        explanation="OLS系数按原结局单位解释；Logistic报告OR而非风险比。调整、敏感性、亚组和固定结点RCS均沿用预定模型；核每模型分母，交互检验不能用组内P值大小替代。多次预设检验不自动获得多重性校正或因果解释。"
    elif method.startswith("prediction.") or method.startswith("evaluation."):
        explanation="训练内调参或CV不是独立外部临床验证。核训练/留出/外部评价的实际分母、事件编码和时间可知性；冻结推理/评价不重新拟合模型。生存IPCW还依赖可识别时点、删失假设和positivity；描述校准图不等于校准斜率或正式检验。"
    elif method.startswith("causal.psm."):
        explanation="匹配后效应属于实际保留的配对人群。核匹配丢失、平衡、分母及配对/聚类方差；该实现不包含PS估计/匹配选择的全部不确定性，也不由软件证明无混杂或总体因果ATT。"
    elif method.startswith("mediation."):
        explanation="本方法限定二元基线暴露、连续中介/结局及已指定线性模型/交互和联合bootstrap。间接/直接效应的因果含义依赖识别假设，不自动扩展到其他中介模型族。"
    elif method.startswith(("exploration.","latent.","longitudinal.")):
        explanation="核候选类数/模型、收敛、实际样本与稳定性结果。探索分群不是疾病亚型证明，正式LPA/LCGA不等于所有潜类推断。冻结赋类或已观测纵向序列后验结果不冒充前瞻临床预测；失败或不稳定部分须保留。"
    else:
        explanation="模型贡献/列线图须核链接尺度、参考背景及目标队列。链接尺度的加性贡献不自动是逐项概率贡献，汇总重要性不构成因果重要性；仅使用对应owner支持的冻结模型和操作。"
    lines.extend(["## 解释与限制","",explanation,"","科学复核pending。软件执行成功不等于方法适用于真实研究、可发表或临床有效。更细的方法诊断/限制保留在原result.json和本地报告中。","","原件、private、模型及日志均留本地。任何对话回传/外发须另经原审阅和授权，本次执行不自动授予。",""])
    with (output/"报告.md").open("x",encoding="utf-8") as f:f.write("\n".join(lines))
def render(task,output,core):
    output=Path(output);result=json.loads((output/"result.json").read_text(encoding="utf-8"))
    plan_hash=task.get("plan_hash",task.get("plan_sha256"))
    result_hash=result.get("binding",{}).get("plan_hash",result.get("bindings",{}).get("plan_sha256"))
    if result["data_origin"]!=task["data_origin"] or result_hash!=plan_hash:raise ValueError("PRESENTATION_SOURCE_MISMATCH")
    if task["data_origin"]=="real":
        sys.path.insert(0,str(core.parent));import captured_study
        captured_study.verify_context(Path(task["project_root"]),task,core)
    import analyze
    method=result["method_id"]
    from frozen_display import create as create_frozen_display
    frozen_manifest=create_frozen_display(task,result,output,core)
    if method=="survival.kaplan_meier":
        validated=analyze.api().validate_task(task,core)
        from km_display import create
        create(task,validated["rows"],output,core)
    if method in {"baseline.table1","association.logistic","survival.kaplan_meier","survival.cox.association"}:analyze.report(output,task)
    else:general_report(task,result,output)
    files=[output/"报告.md"]
    if frozen_manifest is not None:files.append(frozen_manifest)
    if (output/"display/manifest.json").is_file():files.append(output/"display/manifest.json")
    manifest={"schema_version":"ye1-local-presentation@3.0","data_origin":task["data_origin"],"task_purpose":task["task_purpose"],"source_result_sha256":sha(output/"result.json"),"task_plan_hash":plan_hash,"files":[{"path":p.relative_to(output).as_posix(),"sha256":sha(p)} for p in files],"automatic_export":False,"scientific_review":"pending"}
    with (output/"presentation-manifest.json").open("x",encoding="utf-8") as f:json.dump(manifest,f,indent=2,ensure_ascii=False)
