"""Finalize observed evidence only; no fits, lock changes, install or publication."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(v,msg):
    if not v:raise SystemExit(msg)
def main():
    lock=load(ROOT/'runtime-lock.json');lh=sha(ROOT/'runtime-lock.json')
    need(lock['core_version']=='0.4.0-candidate1','WRONG_VERSION')
    for p,h in lock['code_hashes'].items():need(sha(ROOT/p)==h,'CODE_DRIFT:'+p)
    prior=load(ROOT.parent/'clinical-analysis-core-v0_3-dev-20261024/runtime-lock.json')
    for k in ['prediction_provider_versions','association_plan_provider_version']:need(lock[k]==prior[k],'PRIOR_PROVIDER_DRIFT:'+k)
    for p in ['src/clinanalysis/R/table1.R','python/clinical_methods/association.py','python/clinical_methods/prediction.py','python/clinical_methods/continuous_ridge/prediction_engine.py','python/clinical_methods/continuous_ridge/prediction_metrics.py']:
        need(lock['code_hashes'][p]==prior['code_hashes'][p],'PRIOR_NUMERICAL_SOURCE_DRIFT:'+p)
    suites={};history=[]
    for key,pattern,n in [('baseline_association','acceptance-*',41),('association_plan','association-plan-acceptance-*',53),('prediction','prediction-acceptance-*',49),('survival','survival-acceptance-*',None)]:
        candidates=[]
        for p in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            r=load(p);history.append({**ref(p),'summary':r['summary'],'runtime_lock_sha256':r['runtime_lock_sha256']})
            if r['runtime_lock_sha256']==lh:candidates.append((p,r))
        need(bool(candidates),'MISSING_SUITE:'+key)
        p,r=candidates[-1];need(r['summary']['failed']==0 and all(c['status']=='PASS' for c in r['checks']),'FAILED_SUITE:'+key)
        need(n is None or r['summary']['passed']==n,'INCOMPLETE_SUITE:'+key)
        suites[key]=(p,r)
    for key,script in [('prediction','test_prediction_acceptance.py'),('association_plan','test_association_plan_acceptance.py'),('survival','test_survival_acceptance.py')]:
        need(suites[key][1]['test_script_sha256']==sha(ROOT/'tests'/script),'TEST_DRIFT:'+key)
    for key,script in [('association_plan','association_plan_reference.R'),('survival','survival_reference.R')]:need(suites[key][1]['R_reference_sha256']==sha(ROOT/'tests'/script),'REFERENCE_DRIFT:'+key)
    repair_candidates=[]
    for p in sorted((ROOT/'evidence').glob('prediction-output-v03-*/receipt.json')):
        r=load(p)
        if r['runtime_lock_sha256']==lh:repair_candidates.append((p,r))
    need(bool(repair_candidates),'PREDICTION_OUTPUT_REGRESSION_REQUIRED')
    repairpath,repair=repair_candidates[-1]
    need(repair['summary']['passed']==10 and repair['summary']['failed']==0,'PREDICTION_OUTPUT_REGRESSION_FAILED')
    noop=ROOT/'evidence/prediction-output-no-op-v04.json';need(load(noop)['status']=='PASS','NO_OPERATING_POINT_REGRESSION_FAILED')
    unit=ROOT/'evidence/unit-tests-v04-final.log';text=unit.read_text(encoding='utf-8-sig')
    need(re.search(r'Ran 247 tests',text) and re.search(r'\nOK\s*$',text),'UNIT_TESTS_NOT_PASS')
    corrections=ROOT/'evidence/test-expectation-update-v04.json';fixes=load(corrections)
    need(fixes['status']=='PASS' and len(fixes['checks'])==2,'TEST_CORRECTIONS_UNVERIFIED')
    for change in fixes['checks']:need(sha(ROOT/'tests'/change['test'])==change['current_sha256'],'CORRECTED_TEST_DRIFT')
    guard=ROOT/'evidence/previous-candidates-preservation.json';g=load(guard)
    need(g['unchanged'] and all(g['current_manifest_valid'].values()),'OLD_CANDIDATE_DRIFT')
    provenance=ROOT/'evidence/source-provenance.json';origins=load(provenance)
    for item in origins['source_tree_files']:need(sha(Path(item['original']))==item['original_hash'],'ORIGINAL_DRIFT')
    survival=[x for x in origins['source_tree_files'] if x['relative']=='python/clinical_methods/survival.py'][0]
    need(survival['byte_preserved'] and sha(ROOT/survival['relative'])==survival['original_hash'],'SURVIVAL_NUMERICAL_SOURCE_DRIFT')
    auditrefs=[]
    for key in ['association_plan','survival']:
        p=suites[key][0].parent/'export-audit.json';a=load(p);need(a['status']=='PASS','AUDIT_FAILED:'+key);auditrefs.append(ref(p))
    visual=ROOT/'evidence/figure-visual-review-v04.json';v=load(visual);need(v['status']=='PASS' and len(v['figures'])>=2,'VISUAL_REVIEW_REQUIRED')
    for item in v['figures']:need(sha(ROOT/item['local_ref'])==item['sha256'],'FIGURE_DRIFT')
    caps=load(ROOT/'method-capabilities.json')
    for method in caps['methods']:
        mid=method['method_id'];key='survival' if mid.startswith('survival.') else 'prediction' if mid.startswith('prediction.') else 'association_plan' if mid.endswith('.plan') else 'baseline_association'
        method['integration_status']='synthetic_engineering_validated';method['validation_evidence']=[{**ref(suites[key][0]),'scope':'small synthetic engineering acceptance only'}]
    dump(ROOT/'method-capabilities.json',caps)
    not_tested=['Clinical scientific validity, real patient/source databases and causal claims','Formal PH test: unfinished capability requiring a later batch; descriptive correlations do not replace it','Absolute risk prediction, frozen survival prediction external validation, time-dependent ROC/calibration/DCA','Competing risks, delayed entry, recurrent events, interval censoring, time-varying covariates, survey/clustered/stratified survival inference','Grouped KM/log-rank; complete event-time staircase output','Mac, package installation, formal release packaging, full clinical Skill and licensing decisions']
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE','created_at':datetime.now(timezone.utc).isoformat(),
      'runtime_lock_sha256':lh,'production_files_bound':len(lock['code_hashes']),'unit_tests':{**ref(unit),'passed':247,'failed':0},
      'final_suites':{k:{**ref(p),**r['summary']} for k,(p,r) in suites.items()},'export_audits':auditrefs,'figure_visual_review':ref(visual),
      'prediction_output_contract_regression':{**ref(repairpath),**repair['summary'],'no_operating_point_helper':ref(noop)},
      'test_expectation_corrections':ref(corrections),
      'survival_numerical_owner':'python/clinical_methods/survival.py','survival_source_byte_preserved':True,'survival_provider_version':lock['survival_provider_version'],
      'survival_R_reference_checks':[c for c in suites['survival'][1]['checks'] if c['name'].startswith('independent_R')],
      'prior_numerical_sources_and_providers_unchanged':True,'previous_candidates_preservation':{**ref(guard),**g},'source_provenance':ref(provenance),
      'method_ids':[m['method_id'] for m in caps['methods']],'test_only':True,'scientific_review':'pending','export_status':'local_only',
      'independent_personnel_review':'PENDING','independent_R_numeric_reference':'DEVELOPMENT_ACCEPTANCE_ONLY','review_entry':'REVIEW-HANDOFF.md',
      'prior_independent_repairs_evidence':[
        {'local_ref':'historical-reference:clinical-analysis-core-v0_1-independent-acceptance-20261023/p1-fixes-retest-20261024/TARGETED-P1-RECHECK.txt','scope':'Historical three P1 fixes closed on their frozen snapshot; not independent v04 acceptance.'},
        {'local_ref':'historical-reference:clinical-analysis-core-v0_3-independent-acceptance-20261024/INDEPENDENT-V03-REVIEW.txt','scope':'Historical prediction denominator/event-count P1 closure and bounded association review; v04 has its own full development regressions.'}],
      'publication_or_push_performed':False,'installation_or_download_performed':False,'license_release_decision':'NOT_MADE',
      'not_tested':not_tested,'remaining_execution_blockers':[],'history':history,
      'history_note':'An initial smoke used missing CLI output argument and was refused before a run; corrected smoke passed under an interim lock. First survival suite: 46 PASS/1 FAIL because repeated patients correctly triggered the earlier REPEATED_SUBJECT_REQUIRES_OTHER_METHOD gate while the test expected a later duplicate-key code. First association-plan suite: 1 PASS/44 FAIL (45 checks reached) because its common assertion still required core/result version 0.3, causing dependent checks to fail despite correctly emitted v0.4 results. Both original tests and failure diagnoses retained; exactly one assertion line in each test was corrected and both complete suites rerun without production/fixture/tolerance changes. Only selected final suites matching the current lock count as acceptance.',
      'checksum_scope':'Production/tools/tests/docs/fixtures/top-level metadata and aggregate evidence; individual run files are bound by their private manifests and artifact hashes.'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    lines=['# v0_4 冻结验收回执','','已冻结为本地候选 `0.4.0-candidate1`。247 项单测通过；以下完整入口套件均绑定同一最终生产锁，失败数为 0。','']
    for k,(p,r) in suites.items():lines.append(f'- {k}: {r["summary"]["passed"]} 通过；[回执]({p.relative_to(ROOT).as_posix()})')
    lines+=['','KM/Cox 使用唯一原版 survival.py，逐字节保持；旧基线、关联和预测数值来源及 provider 版本未变。风险表、事件/删失和缺失分母、HR/SE 尺度、图表引用及拒绝原因经过公共结果检查。','','独立 R survival 对照是开发验收的一部分，人员独审尚未进行；临床科学审查仍 pending。正式 PH 检验明确未完成，当前仅描述性相关，无 PH 通过状态或正式 PH P 值。','','[总回执](evidence/final-manifest.json) · [独审入口](REVIEW-HANDOFF.md) · [差距清单](GAPS.md)','','未测/未实现：','']
    lines+=['- '+x for x in not_tested]
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    files=set()
    for folder in ['src','python','schemas','tools','tests','docs','fixtures']:
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update(p for p,r in suites.values());files.update(ROOT/x['local_ref'] for x in auditrefs);files.add(repairpath)
    for item in history:
        directory=(ROOT/item['local_ref']).parent
        files.update(p for p in directory.iterdir() if p.is_file() and p.name in ['acceptance-receipt.json','failure-diagnosis.json','original-test-source.py'])
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['freeze_status'],'checksum_files':len(files),'production_files':len(lock['code_hashes']),'suites':{k:r['summary'] for k,(p,r) in suites.items()}}))
if __name__=='__main__':main()
