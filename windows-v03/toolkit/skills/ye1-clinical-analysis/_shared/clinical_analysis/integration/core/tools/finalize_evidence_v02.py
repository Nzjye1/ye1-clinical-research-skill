"""Verify existing final receipts and describe the local candidate; no fitting."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/'evidence/acceptance-20261024-001816/acceptance-receipt.json'
PRED=ROOT/'evidence/prediction-acceptance-20261024-001956/acceptance-receipt.json'
P1=ROOT/'outputs/p1-retest-20261024T002021-135892/receipt.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
def require(ok,message):
    if not ok:raise SystemExit(message)
def main():
    lock=load(ROOT/'runtime-lock.json');lock_hash=sha(ROOT/'runtime-lock.json')
    for relative,expected in lock['code_hashes'].items():
        require(sha(ROOT/relative)==expected,'CODE_DRIFT:'+relative)
    for path,expected in lock['executable_hashes'].items():require(sha(Path(path))==expected,'EXECUTABLE_DRIFT')
    reg,pred,p1=map(load,(REG,PRED,P1))
    for receipt in (reg,pred,p1):require(receipt['runtime_lock_sha256']==lock_hash,'RECEIPT_LOCK_MISMATCH')
    require(reg['summary']['passed']==41 and reg['summary']['failed']==0,'REGRESSION_INCOMPLETE')
    require(pred['summary']['passed']==47 and pred['summary']['failed']==0,'PREDICTION_INCOMPLETE')
    require(p1['status']=='PASS' and len(p1['cases'])==7 and all(c['passed'] for c in p1['cases']),'P1_INCOMPLETE')
    for receipt in (reg,pred):require(all(x['status']=='PASS' for x in receipt['checks']),'CHECK_FAILURE')
    unit=ROOT/'evidence/unit-tests-v02-final.log';unittext=unit.read_text(encoding='utf-8-sig',errors='replace')
    match=re.search(r'Ran (\d+) tests',unittext)
    require(match and int(match.group(1))==106 and re.search(r'\nOK\s*$',unittext),'UNIT_INCOMPLETE')
    audit_path=PRED.parent/'export-audit.json';audit=load(audit_path)
    require(audit['status']=='PASS' and audit['metric_scalars_and_csv_rows']==137 and audit['max_export_difference']==0,'EXPORT_AUDIT_INCOMPLETE')
    require(audit['test_script_sha256']==sha(ROOT/'tests/test_prediction_acceptance.py')==pred['test_script_sha256'],'TEST_SOURCE_DRIFT')
    preservation=load(ROOT/'evidence/v0_1-preservation-check.json')
    require(preservation['previous_candidate_unchanged'] and preservation['previous_lock_valid_now'],'V01_CHANGED')
    origins=load(ROOT/'evidence/source-provenance.json')
    for source in origins['source_tree_files']:
        require(sha(Path(source['original']))==source['original_hash'],'ORIGINAL_SOURCE_DRIFT')
    numeric=[s for s in origins['source_tree_files'] if s['relative'].endswith(('table1.R','association.py','prediction.py','prediction_engine.py','prediction_metrics.py'))]
    require(len(numeric)==5 and all(s['byte_preserved'] and sha(ROOT/s['relative'])==s['original_hash'] for s in numeric),'NUMERICAL_SOURCE_DRIFT')
    snapshot=load(ROOT/'evidence/p1-snapshot-final.json')
    require(snapshot['status']=='PASS','P1_SNAPSHOT_INCOMPLETE')
    independent_root=ROOT.parent/'clinical-analysis-core-v0_1-independent-acceptance-20261023/p1-fixes-retest-20261024'
    independent_report=independent_root/'TARGETED-P1-RECHECK.txt'
    independent_receipt=independent_root/'run-20261023T162445041875Z/receipt.json'
    require(sha(independent_report)=='36fd8cb6dbdff0f7bcb0d4ee2621cb40670fe8356ce7f54ec0d6f954e0a600c1','INDEPENDENT_REPORT_DRIFT')
    require(sha(independent_receipt)=='0b6c52c86460f8e58fb2529737f3a94e121af6411c1aa449e7e1048e8b3b2775','INDEPENDENT_RECEIPT_DRIFT')
    independent=load(independent_receipt)
    require(independent['status']=='PASS_THREE_P1_TARGETED_RECHECK_ONLY' and independent['summary']['checks_failed']==0,'INDEPENDENT_P1_NOT_PASSED')
    fix_signatures={}
    for label,base in [('final_prediction_candidate',ROOT),('sealed_P1_snapshot',Path(snapshot['snapshot']))]:
        contract=(base/'python/clinical_methods/contracts.py').read_text(encoding='utf-8')
        common=(base/'src/clinanalysis/R/clinical_common.R').read_text(encoding='utf-8')
        checks={'strict_csv': 'strict=True' in contract and 'CSV_ENCODING_OR_FORMAT_INVALID' in contract,
          'ID_model_guard':'ID_MODEL_FIELD_FORBIDDEN' in contract,
          'dynamic_categorical_denominator':'denominator_policy <- tb$categorical_denominator' in common and 'categorical_denominator=denominator_policy' in common and 'group_missing_policy="exclude"' in common}
        require(all(checks.values()),'P1_FIX_SIGNATURE_MISSING')
        fix_signatures[label]={'signatures':checks,'contract_sha256':sha(base/'python/clinical_methods/contracts.py'),'R_adapter_sha256':sha(base/'src/clinanalysis/R/clinical_common.R')}
    inclusion={'status':'PASS','independent_scope':'sealed P1 snapshot only; not prediction independent acceptance',
       'independent_report':{'local_ref':independent_report.as_posix(),'sha256':sha(independent_report)},
       'independent_receipt':{'local_ref':independent_receipt.as_posix(),'sha256':sha(independent_receipt),'summary':independent['summary']},
       'fix_source_signatures':fix_signatures,'final_candidate_actual_R_cases':{**ref(P1),'passed':7,'failed':0},
       'equivalence_claim':'same three protections verified by source signatures and final-candidate runtime cases, not byte identity of whole adapters'}
    write(ROOT/'evidence/p1-fix-inclusion.json',inclusion)
    methods=load(ROOT/'method-capabilities.json')
    for method in methods['methods']:
        prediction=method['method_id'].startswith('prediction.')
        checks=[c for c in (pred if prediction else reg)['checks'] if c.get('method')==method['method_id'] and c['name'].startswith('valid_') and (not prediction or c['name'].endswith('_train'))]
        require(len(checks)==2,'METHOD_TWO_ADAPTER_EVIDENCE_INCOMPLETE')
        require(all(c['provider']['id']==method['provider_id'] and c['provider']['version']==method['provider_version'] for c in checks),'METHOD_PROVIDER_MISMATCH')
        method['integration_status']='synthetic_engineering_validated'
        method['validation_evidence']=[{**ref(PRED if prediction else REG),'test_scope':'SYNTHETIC_ONLY_NOT_CLINICAL_SCIENTIFIC_ACCEPTANCE'}]
    write(ROOT/'method-capabilities.json',methods)
    figures=[]
    for sub,file in [('mimic-binary-train','binary-calibration.png'),('mimic-binary-train','binary-dca.png'),('mimic-binary-train','binary-roc-grid.png'),('mimic-continuous-train','continuous-error-comparator.png')]:
        p=PRED.parent/('中文 路径 '+sub)/'figures'/file
        require(p.is_file(),'FIGURE_MISSING')
        figures.append({**ref(p),'visual_review':'PASS','scope':'human-readable axes/title/legend; synthetic only; numerical series covered separately'})
    write(ROOT/'evidence/figure-visual-review.json',{'status':'PASS','figures':figures,'test_only':True})
    not_tested=[
      'Real database extraction, real patient data, actual cross-source patient independence or transportability',
      'Clinical scientific validity, clinical utility and publication readiness',
      'Mac, R package installation, R CMD check, migration or release packaging',
      'Signed continuous outcomes, LASSO, SHAP, Cox prediction and other unregistered methods',
      'Legal joins with reconstructed source evidence and postindex outcome descriptive-baseline roles remain integration_pending']
    final={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','created_at':datetime.now(timezone.utc).isoformat(),
      'runtime_lock_sha256':lock_hash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{**ref(unit),'passed':106,'failed':0},
      'baseline_association_regression':{**ref(REG),**reg['summary'],'scope_note':'This inherited suite tests baseline/association only; prediction is covered by the separate final suite.'},
      'prediction_acceptance':{**ref(PRED),**pred['summary']},'p1_fix_regression':{**ref(P1),'passed':7,'failed':0},
      'prediction_export_audit':{**ref(audit_path),**audit},'p1_stable_snapshot':snapshot,
      'independent_p1_evidence_and_final_fix_inclusion':ref(ROOT/'evidence/p1-fix-inclusion.json'),
      'independent_prediction_status':'NOT_YET_INDEPENDENTLY_REVIEWED','independent_prediction_entry':'docs/PREDICTION-REVIEW-HANDOFF.md',
      'previous_candidate_preservation':{**ref(ROOT/'evidence/v0_1-preservation-check.json'),**preservation},
      'source_originals_rechecked_unchanged':True,'numerical_sources_byte_preserved':True,
      'numerical_source_provenance':ref(ROOT/'evidence/source-provenance.json'),
      'figure_visual_review':ref(ROOT/'evidence/figure-visual-review.json'),
      'method_ids':[m['method_id'] for m in methods['methods']],
      'test_only':True,'scientific_review':'pending','export_status':'local_only',
      'publication_or_push_performed':False,'installation_or_download_performed':False,'license_release_decision':'NOT_MADE',
      'not_tested':not_tested,'remaining_execution_blockers':[],
      'history_policy':'Earlier smoke/diagnostic receipts retained; only explicitly referenced final receipts establish this freeze.',
      'checksum_scope':'Production, tools, tests, docs, fixtures, top-level metadata and explicitly referenced final receipts; run output trees and independent P1 snapshot have their own manifests.'}
    write(ROOT/'evidence/final-manifest.json',final)
    lines=['# v0_2 本地候选验收','',
      '最终冻结：`0.2.0-candidate1`。106 项单测、41 项旧基线/关联回归、47 项预测验收、7 个 P1 定向案例全部通过，最终选定回执中失败为 0。各套件有重叠，不相加冒充独立测试数。早期诊断/失败记录原样保留。','',
      '这是小合成数据的工程通过；临床科学评审 pending，TEST_ONLY、local_only，未发布。','',
      '- [最终机器回执](evidence/final-manifest.json)','- [预测 47 项回执]('+PRED.relative_to(ROOT).as_posix()+')',
      '- [旧回归 41 项回执]('+REG.relative_to(ROOT).as_posix()+')','- [当前代码 P1 7 案例]('+P1.relative_to(ROOT).as_posix()+')',
      '- [P1 稳定独审快照](review-snapshots/p1-fixes-20261023/REVIEW-HANDOFF.md)','- [预测指标/CSV 导出审计]('+audit_path.relative_to(ROOT).as_posix()+')','',
      '## 已完成的闭环','',
      '沿用 clinanalysis 单任务入口、registry 和固定数值源码。两 adapter 的开发队列各 200 行，结局缺失 2 行，随机或连续患者组拆分的主案例为训练 158、留出 40。外部合成视图 80 行，其中 79 行有结局；无结局推理 80 行。两 adapter 预测差及保存重载预测差均为 0。','',
      '训练插补、缩放、类别与内部 CV 仅使用训练范围。仅改变留出特征分布，冻结模型、转换和内部 CV 不变。二分类实际验过 random/group/temporal；连续只注册 group，保留原 CV 每折训练至少 100、验证至少 30 的门槛。未知类别、患者跨折/开发组重叠、未来特征、未成熟标签和语义/版本漂移均定位拒绝。','',
      '非负连续方法明确名为 prediction.continuous.nonnegative.ridge，冻结 domain=nonnegative、identity 变换/逆变换及 clip_lower_zero。负结局拒绝；私有轨迹保留原始线性值、逆变换值、最终输出，边界 -1/0/1 输出 0/0/1 已验证。没有删除旧截断，也没有声称支持有符号连续结局。','',
      '独立 base R 对照：连续 Ridge 系数最大差 5.9952e-15，二分类 Ridge Logistic 最大差 1.36091e-7；预设 atol/rtol 为 1e-5。确定性映射/计数/手算指标容差 1e-8。连续原尺度误差和训练中位数常数对照、二分类 AUC/AP/Brier、校准/DCA 均复核。12 个有标签运行的 137 个最终指标/CSV 数值与数值端最大差 0。','',
      '三项 P1 已修实现并回归：baseline=null 时 ID 型暴露仍拒绝；引号格式错误的 CSV 身份列严格拒绝；all/nonmissing 分类分母与表注一致。稳定 P1 快照另外通过原 57 单测和 7 个 R 案例。随后独立复核通过9个R案例、12检查和57单测，363文件哈希不变；[独立报告](../clinical-analysis-core-v0_1-independent-acceptance-20261023/p1-fixes-retest-20261024/TARGETED-P1-RECHECK.txt)。当前版本包含相同三项保护的[源码签名与实际运行核对](evidence/p1-fix-inclusion.json)。独审范围只覆盖P1快照，预测尚待独审，[复验入口](docs/PREDICTION-REVIEW-HANDOFF.md)。按结局描述分组并非统计禁止；相应角色本候选尚未接入。','',
      '统一结果保留版本、provider、尺度、分母、缺失、拒绝原因和图表引用。冻结模型与逐行合成推理仅在本地 private/；推理不伪造评估指标。ROC 图明确为固定阈值网格，校准只作诊断；DCA 不表示临床批准。四张代表图已目视检查标题、坐标和图例。','',
      '## 冻结与未测','',f'生产文件 {len(lock["code_hashes"])} 个绑定于 runtime-lock.json；原数值文件逐字节保留；原源码只读复核无变。v0_1 冻结代码及所列元数据 hash 与开始时一致。checksum 文件的覆盖范围见 final-manifest.json；不把后来独审新增输出误称为本次冻结内容。','']
    lines.extend('- '+x for x in not_tested)
    lines.extend(['','没有安装、下载、改系统设置、修改旧 Skill/数据库/研究/围术期包，没有 push/tag 或发布。无剩余执行阻塞；真实临床科学验证与未注册能力仍待后续。'])
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    selected=set()
    for folder in ('src','python','schemas','tools','tests','docs','fixtures'):
        selected.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    selected.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    selected.update([REG,PRED,P1,audit_path,unit,ROOT/'evidence/final-manifest.json',ROOT/'evidence/source-provenance.json',ROOT/'evidence/v0_1-start-hashes.json',ROOT/'evidence/v0_1-preservation-check.json',ROOT/'evidence/p1-snapshot-final.json',ROOT/'evidence/p1-fix-inclusion.json',ROOT/'evidence/figure-visual-review.json'])
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(selected))+'\n',encoding='utf-8')
    print(json.dumps({'status':final['status'],'units':106,'old_regression':41,'prediction':47,'P1':7,'export_values':137,'production_files':len(lock['code_hashes']),'checksum_files':len(selected),'remaining_blockers':[]}))
if __name__=='__main__':main()
