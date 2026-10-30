"""Freeze only verified local v05 evidence; never fit, install, publish or relock."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(value,code):
    if not value:raise SystemExit(code)

def main():
    lockpath=ROOT/'runtime-lock.json';lock=load(lockpath);lockhash=sha(lockpath)
    need(lock['core_version']=='0.5.0-candidate1','WRONG_CORE_VERSION')
    for p,h in lock['code_hashes'].items():need(sha(ROOT/p)==h,'PRODUCTION_DRIFT:'+p)
    prior=load(ROOT.parent/'clinical-analysis-core-v0_4-dev-20261024/runtime-lock.json')
    for key in ('prediction_provider_versions','association_plan_provider_version'):
        need(lock[key]==prior[key],'PREVIOUS_NUMERICAL_PROVIDER_DRIFT:'+key)
    preserved=['src/clinanalysis/R/table1.R','src/clinanalysis/R/clinical_prediction_common.R',
      'python/clinical_methods/association.py','python/clinical_methods/prediction.py',
      'python/clinical_methods/continuous_ridge/prediction_engine.py','python/clinical_methods/continuous_ridge/prediction_metrics.py']
    for p in preserved:need(lock['code_hashes'][p]==prior['code_hashes'][p],'PREVIOUS_SOURCE_DRIFT:'+p)
    suites={};history=[]
    settings=[('baseline_association','acceptance-*',41,'test_acceptance.py'),
      ('association_plan','association-plan-acceptance-*',53,'test_association_plan_acceptance.py'),
      ('prediction','prediction-acceptance-*',49,'test_prediction_acceptance.py'),
      ('survival_v04_regression','survival-acceptance-*',47,'test_survival_acceptance.py'),
      ('survival_v05','survival-v05-acceptance-*',None,'test_survival_v05_acceptance.py')]
    for key,pattern,count,script in settings:
        candidates=[]
        for p in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            r=load(p);history.append({**ref(p),'suite':key,'summary':r['summary'],'runtime_lock_sha256':r['runtime_lock_sha256']})
            if r['runtime_lock_sha256']==lockhash:candidates.append((p,r))
        need(bool(candidates),'MISSING_SUITE:'+key)
        p,r=candidates[-1]
        need(r['summary']['failed']==0 and all(c['status']=='PASS' for c in r['checks']),'FAILED_SUITE:'+key)
        if count is not None:need(r['summary']['passed']==count,'INCOMPLETE_SUITE:'+key)
        if 'test_script_sha256' in r:need(r['test_script_sha256']==sha(ROOT/'tests'/script),'TEST_SOURCE_DRIFT:'+key)
        if 'source_sha256' in r:
            for path,digest in r['source_sha256'].items():need(sha(ROOT/path)==digest,'ACCEPTANCE_SOURCE_DRIFT:'+path)
        suites[key]=(p,r)
    for key,name in [('association_plan','association_plan_reference.R'),('survival_v04_regression','survival_reference.R'),('survival_v05','survival_v05_reference.R')]:
        r=suites[key][1]
        if 'R_reference_sha256' in r:need(r['R_reference_sha256']==sha(ROOT/'tests'/name),'REFERENCE_DRIFT:'+key)
    repair=[]
    for p in sorted((ROOT/'evidence').glob('prediction-output-v03-*/receipt.json')):
        r=load(p)
        if r['runtime_lock_sha256']==lockhash:repair.append((p,r))
    need(bool(repair),'MISSING_PREDICTION_OUTPUT_REGRESSION');rp,rr=repair[-1]
    need(rr['summary']['passed']==10 and rr['summary']['failed']==0,'PREDICTION_OUTPUT_REGRESSION_FAILED')
    noop=ROOT/'evidence/prediction-output-no-op-v05.json';need(load(noop)['status']=='PASS','PREDICTION_NO_OPERATING_POINT_FAILED')
    unit=ROOT/'evidence/unit-tests-v05-final.log';unittext=unit.read_text(encoding='utf-8-sig')
    match=re.search(r'Ran (\d+) tests',unittext)
    need(match and int(match.group(1))>=336 and re.search(r'\nOK\s*$',unittext),'FINAL_UNIT_TESTS_FAILED')
    unitn=int(match.group(1))
    execution_history=ROOT/'evidence/execution-history-v05.json';execution=load(execution_history)
    need(execution['current_runtime_lock_sha256']==lockhash,'EXECUTION_HISTORY_LOCK_MISMATCH')
    corrections=ROOT/'evidence/test-expectation-update-v05.json';changes=load(corrections)
    need(changes['status']=='PASS' and len(changes['checks'])==5,'TEST_EXPECTATIONS_NOT_VERIFIED')
    for x in changes['checks']:need(sha(ROOT/'tests'/x['test'])==x['current_sha256'],'INHERITED_TEST_DRIFT')
    guard=ROOT/'evidence/previous-candidates-preservation.json';g=load(guard)
    need(g['unchanged'] and all(g['current_manifest_valid'].values()),'FROZEN_PRIOR_CANDIDATE_CHANGED')
    provenance=ROOT/'evidence/source-provenance.json';origins=load(provenance)
    for item in origins['source_tree_files']:need(sha(Path(item['original']))==item['original_hash'],'ORIGINAL_SOURCE_CHANGED')
    audits=[]
    for key in ('association_plan','survival_v04_regression','survival_v05'):
        p=suites[key][0].parent/'export-audit.json';a=load(p)
        need(a['status']=='PASS','EXPORT_AUDIT_FAILED:'+key);audits.append(ref(p))
    visual=ROOT/'evidence/figure-visual-review-v05.json';v=load(visual)
    need(v['status']=='PASS' and len(v['figures'])>=3,'VISUAL_REVIEW_REQUIRED')
    for item in v['figures']:need(sha(ROOT/item['local_ref'])==item['sha256'],'FIGURE_DRIFT')
    caps=load(ROOT/'method-capabilities.json')
    for m in caps['methods']:
        mid=m['method_id'];key=('survival_v05' if mid=='prediction.survival.cox' or mid=='survival.cox.association' else
          'survival_v04_regression' if mid.startswith('survival.') else 'prediction' if mid.startswith('prediction.') else
          'association_plan' if mid.endswith('.plan') else 'baseline_association')
        m['integration_status']='synthetic_engineering_validated'
        m['validation_evidence']=[{**ref(suites[key][0]),'scope':'Small synthetic development acceptance only; clinical review pending'}]
    dump(ROOT/'method-capabilities.json',caps)
    gaps=['Clinical scientific validity, causal interpretation, real patients/databases and transportability',
      'Survival time-dependent ROC/AUC, IPCW Brier, calibration, DCA and prediction confidence intervals',
      'Competing risks, delayed entry, recurrent events, interval censoring, time-varying covariates, survey/clustered/stratified survival inference',
      'Grouped KM/log-rank and full event-time staircase output',
      'Mac deployment, installers, full clinical Skill Release and license/publication decisions']
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE',
      'created_at':datetime.now(timezone.utc).isoformat(),'runtime_lock_sha256':lockhash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{**ref(unit),'passed':unitn,'failed':0},'final_suites':{k:{**ref(p),**r['summary']} for k,(p,r) in suites.items()},
      'export_audits':audits,'figure_visual_review':ref(visual),
      'prediction_output_contract_regression':{**ref(rp),**rr['summary'],'no_operating_point_helper':ref(noop)},
      'test_expectation_changes':ref(corrections),'previous_candidates_preservation':{**ref(guard),**g},'source_provenance':ref(provenance),
      'survival_numerical_owner':'python/clinical_methods/survival.py','survival_source_byte_preserved':False,
      'survival_owner_change':'Versioned formal PH and frozen Breslow prediction extension using the same guarded Cox fit; exact legacy numerical regression retained',
      'survival_provider_version':lock['survival_provider_version'],'cox_prediction_provider_version':lock['cox_prediction_provider_version'],
      'prior_non_survival_numerical_sources_and_providers_unchanged':True,
      'method_ids':[m['method_id'] for m in caps['methods']],
      'test_only':True,'scientific_review':'pending','export_status':'local_only','independent_personnel_review':'PENDING',
      'independent_R_numeric_reference':'DEVELOPMENT_ACCEPTANCE_ONLY','review_entry':'REVIEW-HANDOFF.md',
      'prior_independent_repairs_evidence':[
        {'local_ref':'historical-reference:clinical-analysis-core-v0_1-independent-acceptance-20261023/p1-fixes-retest-20261024/TARGETED-P1-RECHECK.txt','scope':'Historical three P1 closures, not v05 independent acceptance'},
        {'local_ref':'historical-reference:clinical-analysis-core-v0_3-independent-acceptance-20261024/INDEPENDENT-V03-REVIEW.txt','scope':'Historical prediction denominator/event P1 closure, not v05 independent acceptance'}],
      'publication_or_push_performed':False,'installation_or_download_performed':False,'license_release_decision':'NOT_MADE',
      'not_tested':gaps,'remaining_execution_blockers':[],'history':history,'execution_history':ref(execution_history),
      'checksum_scope':'Production, tools, tests, docs, fixtures, metadata and aggregate evidence. Individual local run files are bound by their private manifests and public artifact hashes.'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    lines=['# v0_5 本地候选冻结回执','',f'已冻结为 0.5.0-candidate1。{unitn} 项单测通过；以下完整验收均绑定同一生产锁，失败数为 0。','']
    lines += [f'- {k}: {r["summary"]["passed"]} 通过；[回执]({p.relative_to(ROOT).as_posix()})' for k,(p,r) in suites.items()]
    lines += ['','正式 PH 与 Cox 风险预测使用同一生存 owner；旧 KM/Cox 数值精确回归保留。固定 Ridge、关联、基线及旧冻结版本保护检查通过。',
      '','独立 R 数值对照是开发验收的一部分，尚未完成人员独立复核；临床科学复核仍为 pending。',
      '','[总回执](evidence/final-manifest.json) · [独审入口](REVIEW-HANDOFF.md) · [边界与缺口](GAPS.md)','']
    lines += ['- '+x for x in gaps]
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    files=set()
    for folder in ['src','python','schemas','tools','tests','docs','fixtures']:
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update(p for p,r in suites.values());files.update(ROOT/x['local_ref'] for x in audits);files.add(rp)
    for item in history:
        d=(ROOT/item['local_ref']).parent
        files.update(p for p in d.iterdir() if p.is_file() and p.name in ['acceptance-receipt.json','failure-diagnosis.json','original-test-source.py'])
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['freeze_status'],'checksum_files':len(files),'production_files':len(lock['code_hashes']),'unit_tests':unitn,'suites':{k:r['summary'] for k,(p,r) in suites.items()}}))
if __name__=='__main__':main()
