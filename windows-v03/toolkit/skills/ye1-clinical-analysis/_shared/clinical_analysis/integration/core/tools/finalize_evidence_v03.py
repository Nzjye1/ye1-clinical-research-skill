"""Bind final observed v03 evidence; never fit, install, refreeze or publish."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(ok,reason):
    if not ok:raise SystemExit(reason)
def main():
    lock=load(ROOT/'runtime-lock.json');lock_hash=sha(ROOT/'runtime-lock.json')
    for p,h in lock['code_hashes'].items():need(sha(ROOT/p)==h,'PRODUCTION_CODE_DRIFT:'+p)
    previous=load(ROOT.parent/'clinical-analysis-core-v0_2-dev-20261023/runtime-lock.json')
    need(lock['prediction_provider_versions']==previous['prediction_provider_versions'],'PREDICTION_PROVIDER_CHANGED')
    receipts={};history=[]
    for key,pattern,count in [('baseline_association','acceptance-*',41),('prediction','prediction-acceptance-*',49),('association_plan','association-plan-acceptance-*',53)]:
        candidates=[]
        for p in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            r=load(p);history.append({**ref(p),'summary':r['summary'],'runtime_lock_sha256':r['runtime_lock_sha256']})
            if r['runtime_lock_sha256']==lock_hash:candidates.append((p,r))
        need(bool(candidates),'FINAL_RECEIPT_MISSING:'+key)
        path,r=candidates[-1]
        need(r['summary']['passed']==count and r['summary']['failed']==0 and all(c['status']=='PASS' for c in r['checks']),'FINAL_RECEIPT_FAILURE:'+key)
        receipts[key]=(path,r)
    planpath,plan=receipts['association_plan'];predpath,pred=receipts['prediction'];regpath,reg=receipts['baseline_association']
    need(plan['test_script_sha256']==sha(ROOT/'tests/test_association_plan_acceptance.py'),'PLAN_TEST_SOURCE_DRIFT')
    need(plan['R_reference_sha256']==sha(ROOT/'tests/association_plan_reference.R'),'R_REFERENCE_DRIFT')
    need(pred['test_script_sha256']==sha(ROOT/'tests/test_prediction_acceptance.py'),'PREDICTION_TEST_SOURCE_DRIFT')
    repair_candidates=[]
    for p in sorted((ROOT/'evidence').glob('prediction-output-v03-*/receipt.json')):
        candidate=load(p)
        if candidate['runtime_lock_sha256']==lock_hash:repair_candidates.append((p,candidate))
    need(bool(repair_candidates),'PREDICTION_OUTPUT_REPAIR_RECEIPT_MISSING')
    repairpath,repair=repair_candidates[-1]
    need(repair['summary']['passed']==10 and repair['summary']['failed']==0,'PREDICTION_OUTPUT_REPAIR_FAILURE')
    need(repair['test_script_sha256']==sha(ROOT/'tests/test_prediction_output_contract.py'),'PREDICTION_OUTPUT_TEST_SOURCE_DRIFT')
    noop_path=ROOT/'evidence/prediction-output-no-op-v03.json'
    need(load(noop_path)['status']=='PASS','NO_OPERATING_POINT_OUTPUT_CHECK_REQUIRED')
    auditpath=planpath.parent/'export-audit.json';audit=load(auditpath)
    need(audit['status']=='PASS' and audit['audit_script_sha256']==sha(ROOT/'tools/audit_association_plan_exports.py'),'EXPORT_AUDIT_FAILED_OR_DRIFT')
    unitpath=ROOT/'evidence/unit-tests-v03-authorized-final.log';text=unitpath.read_text(encoding='utf-8-sig',errors='replace')
    need(re.search(r'Ran 171 tests',text) and re.search(r'\nOK\s*$',text),'FINAL_UNIT_TESTS_REQUIRED')
    authorization_path=ROOT/'evidence/prediction-test-update-authorized.json';authorization=load(authorization_path)
    need(authorization['updated_sha256']==sha(ROOT/'tests/test_prediction_acceptance.py') and authorization['production_lock_sha256']==lock_hash,'AUTHORIZED_TEST_UPDATE_BINDING_MISMATCH')
    patch_scope_path=ROOT/'evidence/prediction-test-patch-scope.json';patch_scope=load(patch_scope_path)
    need(patch_scope['status']=='PASS' and patch_scope['updated_sha256']==authorization['updated_sha256'] and patch_scope['original_reconstructed_sha256']==authorization['previous_sha256'],'AUTHORIZED_PATCH_SCOPE_MISMATCH')
    independent_root=ROOT.parent/'clinical-analysis-core-v0_3-independent-acceptance-20261024'
    independent=load(independent_root/'final-review.json')
    need(independent['runtime_lock_sha256']==lock_hash,'INDEPENDENT_REVIEW_PRODUCTION_DRIFT')
    need(independent['new_P0_observed']==0 and independent['new_P1_observed']==0 and all(v=='CLOSED_FOR_THIS_CHECKPOINT' for v in independent['prior_prediction_P1'].values()),'INDEPENDENT_REVIEW_FINDINGS_UNRESOLVED')
    independent_evidence={'scope':'Bounded independent review of the unchanged production checkpoint; its historical pending full-regression note is resolved only by the separate final development regression receipt.',
      'reported_status_at_review':independent['status'],'prior_prediction_P1':independent['prior_prediction_P1'],
      'association_scope':independent['association_scope'],
      'sources':[{'local_ref':p.as_posix(),'sha256':sha(p)} for p in [independent_root/'INDEPENDENT-V03-REVIEW.txt',independent_root/'final-review.json',independent_root/'EVIDENCE-SHA256SUMS.txt']]}
    guardpath=ROOT/'evidence/previous-candidates-preservation.json';guard=load(guardpath)
    need(guard['unchanged'] and all(guard['current_manifest_valid'].values()),'PREVIOUS_CANDIDATES_CHANGED')
    origins=load(ROOT/'evidence/source-provenance.json')
    for item in origins['source_tree_files']:need(sha(Path(item['original']))==item['original_hash'],'ORIGINAL_SOURCE_CHANGED')
    preserved=[x for x in origins['source_tree_files'] if x['relative'].endswith(('table1.R','prediction.py','prediction_engine.py','prediction_metrics.py'))]
    need(len(preserved)==4 and all(x['byte_preserved'] and sha(ROOT/x['relative'])==x['original_hash'] for x in preserved),'FIXED_NUMERICAL_SOURCE_CHANGED')
    providerpath=ROOT/'evidence/provider-v03-final.json';provider=load(providerpath)
    need(provider['status']=='PASS' and provider['legacy_output_equivalence_cases']==8,'LEGACY_ASSOCIATION_EQUIVALENCE_MISSING')
    for p,h in provider['source_hashes'].items():need(sha(ROOT/p)==h,'PROVIDER_EVIDENCE_DRIFT')
    need(provider['preflight']['provider_version']==lock['association_plan_provider_version'],'PROVIDER_VERSION_MISMATCH')
    caps=load(ROOT/'method-capabilities.json')
    caps.pop('candidate_finalization_status',None)
    for method in caps['methods']:
        key='association_plan' if method['method_id'].endswith('.plan') else 'prediction' if method['method_id'].startswith('prediction.') else 'baseline_association'
        path,receipt=receipts[key]
        valid=[c for c in receipt['checks'] if c['name'].startswith('valid_') and c.get('method')==method['method_id']]
        need(len(valid)>=2,'TWO_ADAPTER_METHOD_EVIDENCE_REQUIRED')
        need(all(c['provider']['id']==method['provider_id'] and c['provider']['version']==method['provider_version'] for c in valid),'METHOD_PROVIDER_MISMATCH')
        method['integration_status']='synthetic_engineering_validated'
        method['validation_evidence']=[{**ref(path),'scope':'synthetic technical acceptance only'}]
    write(ROOT/'method-capabilities.json',caps)
    visualpath=ROOT/'evidence/figure-visual-review-v03.json';visual=load(visualpath)
    need(visual['status']=='PASS' and len(visual['figures'])==4,'VISUAL_REVIEW_REQUIRED')
    for item in visual['figures']:need(sha(ROOT/item['local_ref'])==item['sha256'],'VISUAL_ARTIFACT_DRIFT')
    not_tested=['Real database extraction, real patient data and cross-source identity independence',
      'Clinical scientific validity, causal effects or publication readiness','Mac, package installation, R CMD check, migration or release packaging',
      'RCS-by-subgroup combinations, categorical-exposure subgroup effects, simultaneous confidence bands or multiplicity-adjusted inference',
      'Multiple imputation, automatic model/variable/knot selection, complex designs or unregistered analyses',
      'Full clinical Skill and all shared-core capabilities remain incomplete; independent review is bounded to its explicitly documented synthetic scope']
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE','created_at':datetime.now(timezone.utc).isoformat(),
      'runtime_lock_sha256':lock_hash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{**ref(unitpath),'passed':171,'failed':0},
      'final_suites':{k:{**ref(p),**r['summary']} for k,(p,r) in receipts.items()},
      'prediction_output_P1_repairs':{**ref(repairpath),**repair['summary'],'no_operating_point_helper':ref(noop_path),
        'scope':'Two v02 independent-review output defects repaired in v03 only and closed by bounded independent recheck; six main-chain model bytes/backend/predictions/provider unchanged, two zero-ratio-denominator boundaries checked.'},
      'export_audit':{**ref(auditpath),**audit},'figure_visual_review':ref(visualpath),
      'numerical_owner':'python/clinical_methods/association.py; existing fitter/basis/joint Wald reused, explicit versioned extension',
      'association_source_byte_preserved':False,'legacy_association_exact_output_cases':8,'legacy_equivalence_evidence':ref(providerpath),
      'baseline_and_prediction_numerical_sources_byte_preserved':True,'prediction_provider_versions_unchanged':True,
      'original_reused_sources_read_only_hash_check':True,'source_provenance':ref(ROOT/'evidence/source-provenance.json'),
      'previous_candidates_preservation':{**ref(guardpath),**guard},
      'method_ids':[m['method_id'] for m in caps['methods']],
      'test_only':True,'scientific_review':'pending','export_status':'local_only','independent_v03_review':'BOUNDED_SCOPE_PASSED',
      'independent_review_evidence':independent_evidence,'authorized_test_update':ref(authorization_path),
      'authorized_patch_scope_verification':ref(patch_scope_path),
      'former_test_update_blocker':'Resolved by explicit user authorization on 2026-10-23 17:39:14 UTC; one subsequent patch attempt applied and final prediction suite completed. Earlier denied attempts and checkpoint retained as history.',
      'independent_review_entry':'REVIEW-HANDOFF.md','publication_or_push_performed':False,'installation_or_download_performed':False,
      'license_release_decision':'NOT_MADE','not_tested':not_tested,'remaining_execution_blockers':[],
      'history':history,'history_note':'First plan suite 38 pass/15 fail retained: fourteen missing raw-input bindings fixed in production; numeric 0 vs 0.0 audit assertion repaired without changing tolerance. Initial smoke code-drift refusal retained. Transport interruption ended prediction-acceptance-20261024-005333 and association-plan-acceptance-20261024-005338 before receipts; partial outputs retained and not counted as passes. Final receipts above match current lock.',
      'prior_independent_P1_review':{'local_ref':'historical-reference:clinical-analysis-core-v0_1-independent-acceptance-20261023/p1-fixes-retest-20261024/TARGETED-P1-RECHECK.txt','scope':'Previously frozen three-fix snapshot only: 9 R cases, 12 checks and 57 units passed. Does not independently validate this candidate or prediction.'},
      'checksum_scope':'Source/tools/tests/docs/fixtures/top-level metadata and explicit final receipts; prior run output trees remain retained, individual output artifact hashes are recorded in their run manifests.'}
    write(ROOT/'evidence/final-manifest.json',manifest)
    comparisons=[c for c in plan['checks'] if c['name'].startswith(('independent_R','mapped_','two_adapter','common_'))]
    lines=['# v0_3 本地候选验收','',
      '最终冻结版本 `0.3.0-candidate1`：171 项单测、53 项本批关联计划验收、41 项旧基线/关联回归、49 项预测回归全部通过，最终选定回执失败为 0。套件有重叠，不将数量相加充作互不重复检查。','',
      '仅完成这批小合成数据工程验收及有界独立复验。状态仍为 TEST_ONLY / scientific_review=pending / local_only，未发布，整套底座及完整临床 Skill 未完成。','',
      '- [机器总回执](evidence/final-manifest.json)','- [本批53项回执]('+planpath.relative_to(ROOT).as_posix()+')',
      '- [基线/关联回归]('+regpath.relative_to(ROOT).as_posix()+')','- [预测回归]('+predpath.relative_to(ROOT).as_posix()+')',
      '- [导出复核]('+auditpath.relative_to(ROOT).as_posix()+')','- [独审入口](REVIEW-HANDOFF.md)','',
      '## 本批实现','',
      '连续结局 OLS/HC3 和二分类普通 Logistic MLE 的预设模型序列、逐模型或共同完整案例策略、预设敏感性子集、合并交互模型的组内斜率与单独联合交互检验、固定结点/参考/有效域的 RCS 相对效应曲线。整体暴露和非线性联合检验、完整协方差逐点95%区间、尺度/模型分母/缺失/筛选流与不可估计原因均进入统一结果和表图。','',
      '共同完整案例按全部建模字段并集先取资格集，再应用各模型筛选；仅作筛选的字段缺失单独计数。敏感性子集因此仍可能有不同最终分母。亚组效应来自合并交互拟合，不是组间效应，也不通过比较组内P值判断交互。通用效应reference为空，亚组参考水平另列subgroup_reference。失败小组/零事件组的计数仍保留。','',
      '两种200行合成adapter使用不同字段、单位和分类编码；同一科学计划的效应、曲线与分母一致。独立R用lm/glm、sandwich HC3和独立重建RCS设计/对比矩阵，对照效应、完整协方差区间及联合Wald检验；推断固定atol/rtol=1e-5，计数/确定性映射/导出固定1e-8，未放宽容差。','',
      'association.py为唯一数值owner，新增显式版本扩展；没有另造拟合器或失败替代路径。原8种关联场景输出与冻结v0_2逐值一致，基线和预测数值文件保持原字节，两预测provider版本不变。clinanalysis仍是唯一任务执行入口。','',
      '## 失败记录与修复','',
      '首轮关联38通过/15失败原样保留。14个非法输入虽正确拒绝，但统一结果未保留原始提交哈希，已修实现：在语义验证前保存原始input_hash，无效plan_hash等仍为空。另一项是验收把数值0与0.0当字符串比较，改用原1e-8数值容差；未修改算法或放宽标准。初始冒烟中一次正在编辑触发CORE_CODE_DRIFT也保留。最终完整套件均按修复后的同一代码锁重跑。','',
      '## 冻结与边界','',f'生产代码锁绑定 {len(lock["code_hashes"])} 个文件，旧v0_1/v0_2按开始时明确清单复核无变。没有安装、下载、修改系统设置、扫描原始数据库、上传、push/tag或发布。图表只连接预设网格点，区间为逐点区间，不是同时置信带。','']
    lines += ['', '## 预测输出 P1 修复', '',
      '另外针对 v0_2 独审两项输出 P1，新增 10 项针对性检查全部通过，另有关闭 operating point 的输出辅助测试通过。79 人外部评价现公开 42 事件/37 非事件；敏感度 32/42、特异度 16/37、PPV 32/53、NPV 16/26、准确率 48/79。CSV同步真实分子/分母、评价人数、事件数及尺度；非计数比例指标的算术分子/分母为空。内部留出、无标签推理和零比例分母均明确区分。六条主链的模型完整字节、后端数值、预测和 provider 与旧独审结果相同，数值实现未改。', '',
      '- [预测输出修复回执]('+repairpath.relative_to(ROOT).as_posix()+')',
      '- [原预测独审报告](../clinical-analysis-core-v0_2-independent-prediction-20261024/INDEPENDENT-PREDICTION-REVIEW.txt)', '',
      '另行独立复验已关闭这两项预测 P1，并完成三水平亚组、预设模型/敏感性、RCS 和失败边界的有界检查。其 899 次数值比较最大绝对差为 3.749889287973929e-11。独审报告当时注明完整预测回归待验；本次授权更新断言后已完整运行49项并通过，未用独审或修复前48项结果代替。', '',
      '- [独立复验报告](../clinical-analysis-core-v0_3-independent-acceptance-20261024/INDEPENDENT-V03-REVIEW.txt)',
      '- [授权及测试变更绑定](evidence/prediction-test-update-authorized.json)', '',
      '先前两次自动审批拒绝记录和待验检查点保留。用户于2026-10-23 17:39:14 UTC明确允许测试修改，此后一次重试成功，原覆盖保留并新增真实分母语义检查。生产代码锁未变，最终交付清单已重新生成。', '']
    lines += ['- '+s for s in not_tested]
    lines += ['', '执行环境断连中止了 prediction-acceptance-20261024-005333 和 association-plan-acceptance-20261024-005338；未生成完整回执的部分输出保留，不计作通过。连接恢复后以相同生产锁完整重跑，最终回执见上。', '', '既有三项 P1 修复的独立关闭证据：[TARGETED-P1-RECHECK.txt](../clinical-analysis-core-v0_1-independent-acceptance-20261023/p1-fixes-retest-20261024/TARGETED-P1-RECHECK.txt)。该早期证据只适用于当时封存修复快照；本批另外保留相关回归和上述v0_3有界独审。']
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    files=set()
    for folder in ('src','python','schemas','tools','tests','docs','fixtures'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update([p for p,r in receipts.values()]+[auditpath,repairpath,noop_path])
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['status'],'units':171,'association_plan':53,'baseline_association':41,'prediction':49,'checksum_files':len(files),'production_files':len(lock['code_hashes']),'remaining_blockers':[]}))
if __name__=='__main__':main()
