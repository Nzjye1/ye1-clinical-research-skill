"""Freeze only completed current-lock evidence; no fitting, relocking or release."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':Path(p).relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(ok,why):
    if not ok:raise SystemExit(why)
def sources(v):
    for p,h in v.get('source_sha256',{}).items():need(sha(ROOT/p)==h,'EVIDENCE_SOURCE_DRIFT:'+p)
def latest(pattern,lockhash):
    values=[(p,load(p)) for p in sorted((ROOT/'evidence').glob(pattern))]
    values=[(p,v) for p,v in values if v.get('runtime_lock_sha256')==lockhash]
    need(bool(values),'MISSING_CURRENT_EVIDENCE:'+pattern)
    return values[-1]
SETTINGS=[('baseline_association','acceptance-*',41,'test_acceptance.py',None),
 ('association_plan','association-plan-acceptance-*',53,'test_association_plan_acceptance.py','audit_association_plan_exports.py'),
 ('prediction','prediction-acceptance-*',49,'test_prediction_acceptance.py',None),
 ('survival_v04','survival-acceptance-*',47,'test_survival_acceptance.py','audit_survival_exports.py'),
 ('survival_v05','survival-v05-acceptance-*',50,'test_survival_v05_acceptance.py','audit_survival_v05_exports.py'),
 ('survival_v06','survival-v06-acceptance-*',59,'test_survival_v06_acceptance.py','audit_survival_v06_exports.py'),
 ('psm_v07','psm-v07-acceptance-*',48,'test_psm_v07_acceptance.py','audit_psm_v07_exports.py'),
 ('penalized_v08','penalized-v08-acceptance-*',95,'test_penalized_v08_acceptance.py','audit_penalized_v08_exports.py'),
 ('interpretation_v09','interpretation-v09-acceptance-*',79,'test_interpretation_v09_acceptance.py','audit_interpretation_v09_exports.py'),
 ('cox_penalized_v10','cox-penalized-v10-acceptance-*',111,'test_cox_penalized_v10_acceptance.py','audit_cox_penalized_v10_exports.py')]
def main():
    need(not(ROOT/'CANDIDATE-SHA256SUMS.txt').exists(),'ALREADY_FROZEN')
    lock=load(ROOT/'runtime-lock.json');lh=sha(ROOT/'runtime-lock.json')
    need(lock['core_version']=='0.10.0-candidate1','VERSION_MISMATCH')
    for p,h in lock['code_hashes'].items():need(sha(ROOT/p)==h,'PRODUCTION_DRIFT:'+p)
    suites={};audits=[];history=[]
    for name,pattern,count,script,auditor in SETTINGS:
        p,v=latest(pattern+'/acceptance-receipt.json',lh)
        need(v['summary']['passed']==count and v['summary']['failed']==0 and len(v['checks'])==count and all(x['status']=='PASS' for x in v['checks']),'SUITE_INCOMPLETE:'+name)
        if 'test_script_sha256' in v:need(v['test_script_sha256']==sha(ROOT/'tests'/script),'TEST_DRIFT:'+name)
        sources(v);suites[name]=(p,v)
        if auditor:
            ap=p.parent/'export-audit.json';av=load(ap)
            need(av['status']=='PASS' and av['runtime_lock_sha256']==lh,'EXPORT_AUDIT_FAILED:'+name)
            need(av['acceptance_receipt_sha256']==sha(p) and av['audit_script_sha256']==sha(ROOT/'tools'/auditor),'AUDIT_BINDING_MISMATCH:'+name)
            audits.append(ref(ap))
        for hp in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            hv=load(hp);history.append({**ref(hp),'suite':name,'summary':hv['summary'],'runtime_lock_sha256':hv['runtime_lock_sha256']})
    op,ov=latest('prediction-output-v03-*/receipt.json',lh)
    need(ov['summary']['passed']==10 and ov['summary']['failed']==0 and len(ov['checks'])==10 and all(x['status']=='PASS' for x in ov['checks']),'PREDICTION_OUTPUT_FAILED')
    need(ov['test_script_sha256']==sha(ROOT/'tests/test_prediction_output_contract.py'),'PREDICTION_OUTPUT_TEST_DRIFT');sources(ov)
    rp,rv=latest('regressions-v10-*/runner-receipt.json',lh)
    need(rv['status']=='PASS' and rv['production_unchanged'] and len(rv['runs'])==10,'OLD_REGRESSIONS_INCOMPLETE')
    need(rv['runner_script_sha256']==sha(ROOT/'tools/run_regressions_v10.py'),'REGRESSION_RUNNER_DRIFT')
    for row in rv['runs']:
        need(row['returncode']==0 and row['status']=='PASS' and sha(ROOT/row['script'])==row['script_sha256'] and sha(ROOT/row['log'])==row['log_sha256'],'REGRESSION_BINDING_DRIFT')
    no=ROOT/'evidence/prediction-output-no-op-v10.json';nv=load(no)
    need(nv['status']=='PASS' and sha(ROOT/'tests/prediction_output_no_operating_point.R')==nv['script_sha256'],'NO_OPERATING_POINT_FAILED')
    for pkey,hkey in [('result_ref','result_sha256'),('log','log_sha256')]:need(sha(ROOT/nv[pkey])==nv[hkey],'NO_OP_BINDING_DRIFT')
    up,uv=latest('units-v10-*/unit-receipt.json',lh)
    need(uv['status']=='PASS' and uv['returncode']==0 and uv['production_and_tests_unchanged'] and uv['passed']>=805,'UNITS_INCOMPLETE')
    need(uv['runner_sha256']==sha(ROOT/'tools/run_units_v10.py') and sha(ROOT/uv['log_ref'])==uv['log_sha256'],'UNIT_BINDING_DRIFT');sources(uv)
    for row in uv['r_provider_runs']:need(row['returncode']==0 and row['failed']==0 and sha(ROOT/row['log_ref'])==row['log_sha256'],'R_UNITS_FAILED')
    gp=ROOT/'evidence/previous-candidates-preservation.json';gv=load(gp)
    need(gv['unchanged'] and len(gv['current_manifest_valid'])==9 and all(gv['current_manifest_valid'].values()),'OLD_CANDIDATE_CHANGED')
    ip=ROOT/'evidence/inheritance-v10.json';iv=load(ip);need(iv['status']=='PASS' and iv['runtime_lock_sha256']==lh and iv['all_old_numerical_provider_versions_unchanged'],'INHERITANCE_FAILED')
    ep=ROOT/'evidence/test-expectation-update-v10.json';ev=load(ep);need(ev['status']=='PASS' and len(ev['checks'])==48,'INHERITED_TESTS_INCOMPLETE')
    for row in ev['checks']:need(sha(ROOT/'tests'/row['test'])==row['current_sha256'],'INHERITED_TEST_DRIFT')
    vp=ROOT/'evidence/figure-visual-review-v10.json';vv=load(vp)
    need(vv['status']=='PASS' and vv['runtime_lock_sha256']==lh and len(vv['images'])>=3,'FINAL_FIGURE_REVIEW_INCOMPLETE')
    for row in vv['images']:need(sha(ROOT/row['local_ref'])==row['sha256'],'FIGURE_DRIFT')
    pp=ROOT/'evidence/nomogram-p1-verification-v10.json';pv=load(pp)
    need(pv['status']=='PASS' and pv['runtime_lock_sha256']==lh and pv['old_v09_unchanged'] and pv['numerical_artifacts_unchanged'] and pv['actual_pngs_inspected'],'P1_REPAIR_INCOMPLETE')
    for row in pv['bound_files']:need(sha(ROOT/row['local_ref'])==row['sha256'],'P1_EVIDENCE_DRIFT')
    deny=ROOT.parent/'clinical-analysis-core-v0_6-dev-20261024'
    need(all(not(deny/p).exists() and not(ROOT/p).exists() for p in ['docs/METHOD-REVIEW-V06.md','evidence/dependency-probe-v06.json']),'PRIOR_DENIED_FILES_UNEXPECTEDLY_PRESENT')
    cp=ROOT/'docs/CAPABILITY-CROSSWALK-V10.json';cv=load(cp)
    need(cv['row_count']==35 and len(cv['rows'])==35 and cv['preserves_original_order_and_duplicates'],'CROSSWALK_INCOMPLETE')
    caps=load(ROOT/'method-capabilities.json');need(caps['core_version']==lock['core_version'] and len(caps['methods'])==19,'METHOD_REGISTRY_INCOMPLETE')
    preliminary=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='CANDIDATE-SHA256SUMS.txt']
    need(sum(p.stat().st_size for p in preliminary)<500000000,'DELIVERY_SIZE_REVIEW_REQUIRED')
    for method in caps['methods']:
        mid=method['method_id'];key=('cox_penalized_v10' if mid.startswith('prediction.survival.cox.') else 'interpretation_v09' if mid=='interpretation.linear.interventional' else 'penalized_v08' if mid.endswith(('.lasso','.elasticnet')) else 'psm_v07' if mid=='causal.psm.att.continuous' else 'survival_v06' if mid=='evaluation.survival.cox.ipcw' else 'survival_v05' if mid in ('prediction.survival.cox','survival.cox.association') else 'survival_v04' if mid.startswith('survival.') else 'prediction' if mid.startswith('prediction.') else 'association_plan' if mid.endswith('.plan') else 'baseline_association')
        method['integration_status']='synthetic_engineering_validated';method['validation_evidence']=[{**ref(suites[key][0]),'scope':'Bounded synthetic software checks only; scientific review pending'}]
    dump(ROOT/'method-capabilities.json',caps)
    for row in cv['rows']:row['implementation_state']='synthetic_engineering_validated_bounded_scope' if row['registered_methods'] else 'not_implemented_or_definition_pending'
    dump(cp,cv)
    hp=ROOT/'evidence/execution-history-v10.json'
    dump(hp,{'current_runtime_lock_sha256':lh,'acceptance_history':history,
        'unit_history':[{**ref(p),'status':load(p)['status']} for p in sorted((ROOT/'evidence').glob('units-v10-*/unit-receipt.json'))],
        'regression_history':[{**ref(p),'status':load(p)['status']} for p in sorted((ROOT/'evidence').glob('regressions-v10-*/runner-receipt.json'))],
        'smoke_history':[ref(p) for p in sorted((ROOT/'evidence').glob('smoke-v10-*/receipt.json'))],
        'rule':'All failed/superseded attempts and repairs retained locally and in final checksum manifest; none counted as final passes.',
        'supplemental_development_evidence':[ref(ROOT/q) for q in ['evidence/inheritance-check-initial-attempt-v10.json','evidence/verify_v10_inheritance.initial.py.txt','evidence/nomogram-label-p1-v10-20261024-004710-f6bc03/nomogram-p1-targeted-receipt.json','evidence/nomogram-label-p1-v10-20261024-004710-f6bc03/visual-review-supplement.json','evidence/nomogram-label-p1-v10-20261024-005045-c0a8c5/nomogram-p1-targeted-receipt.json','evidence/cox-v10-provider-20261024/provider-summary.json'] if (ROOT/q).exists()],
        'prior_denied_v06_sidecars':'Remain absent; no retry or alternative reproduction of those files.',
        'independent_v09_p1':'Received during v10 development; repair is in this isolated copy only and separately evidenced.'})
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE',
        'created_at':datetime.now(timezone.utc).isoformat(),'runtime_lock_sha256':lh,'production_files_bound':len(lock['code_hashes']),
        'unit_tests':{'receipt':ref(up),'passed':uv['passed'],'failed':0,'python_passed':uv['python_passed'],'r_provider_passed':sum(r['passed'] for r in uv['r_provider_runs'])},
        'final_suites':{key:{**ref(p),**v['summary']} for key,(p,v) in suites.items()},
        'prediction_output_contract_regression':{**ref(op),**ov['summary'],'no_operating_point':ref(no)},
        'total_acceptance_checks_passed':sum(v['summary']['passed'] for p,v in suites.values())+10,'total_acceptance_checks_failed':0,
        'full_regression_runner':ref(rp),'export_audits':audits,'figure_visual_review':ref(vp),'v09_p1_repair':ref(pp),
        'previous_candidates_preservation':ref(gp),'inheritance':ref(ip),'inherited_test_expectations':ref(ep),'original_35_row_crosswalk':ref(cp),
        'bound_original_source_files_checked':iv['bound_original_source_files_checked'],
        'new_cox_verification_summary':ref(ROOT/'evidence/cox-penalized-v10-acceptance-20261024-final-01/verification-summary.json'),
        'numerical_owner':'src/clinanalysis/R/cox_penalized_v10.R','numerical_provider_version':lock['cox_penalized_provider_version'],
        'independent_reference_limit':'Independent transforms/direct calls share glmnet optimizer; manual riskset/Breslow and fixed-coefficient survival check baseline/risk. Not independent optimizer or clinical validation.',
        'test_only':True,'scientific_review':'pending','independent_personnel_review':'PENDING','export_status':'local_only','remaining_execution_blockers':[],
        'not_tested_or_unimplemented':['Cox penalized IPCW/PH/postselection inference/SHAP/nomogram bridges','Binary and survival matched-outcome inference; other original35 gaps','Real patients/database adapters and clinical external validation','Full clinical Skill packaging, license decision, Mac validation and public release'],
        'timing_and_repairs':ref(ROOT/'evidence/timing-and-repairs-v10.json'),'next_parallel_work_split':ref(ROOT/'docs/NEXT-PARALLEL-BATCH.md'),'parallel_dependency_probe':ref(ROOT/'evidence/parallel-dependency-probe-v10/receipt.json'),
        'execution_history':ref(hp),'review_entry':'REVIEW-HANDOFF.md','installation_performed':False,'system_changes_performed':False,'publication_or_push_performed':False,'license_release_decision':'NOT_MADE'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    text=['# v0.10 local candidate acceptance','',f'Frozen {lock["core_version"]}: {uv["passed"]} units and {manifest["total_acceptance_checks_passed"]} acceptance checks passed, zero final failures. All final entry suites bind the same production lock.','']
    text += [f'- {key}: {v["summary"]["passed"]} passed; [receipt]({p.relative_to(ROOT).as_posix()})' for key,(p,v) in suites.items()]
    text += ['- Prediction output denominator regression:10 passed; no-operating-point regression passed.','',
      'Eight public export audits and representative PNG inspection passed. Nine previous candidates and all inherited numerical owners remain unchanged. The original35 mapping has bounded updates, not a claim of complete capability.',
      '', 'The v09 long-category nomogram label P1 is repaired only in this v10 copy; the original clipping evidence and failed/superseded development attempts are retained. See its separate code-bound receipt for lossless labels, real PNG checks and unchanged numerical artifacts. Formal independent targeted recheck remains separate.',
      '', 'New Cox LASSO/Elastic Net train/infer methods freeze preprocessing, selection, centered linear scores and training Breslow baseline. Existing ordinary-Cox IPCW/PH and v09 explanation/nomogram interfaces explicitly do not accept the new model. No coefficients-only claim of full survival prediction and no clinical scientific approval.',
      '', '[Machine evidence](evidence/final-manifest.json) | [Review entry](REVIEW-HANDOFF.md) | [Remaining gaps](GAPS.md)']
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    (ROOT/'DEVELOPMENT-STATUS.md').write_text('# v0.10 status\n\nFROZEN_LOCAL_CANDIDATE. Subsequent development requires a new isolated copy. Not released; independent personnel and clinical scientific reviews remain pending. See ACCEPTANCE.md.\n',encoding='utf-8')
    (ROOT/'README.md').write_text('# Shared clinical analysis core v0.10 local candidate\n\nFROZEN_LOCAL_CANDIDATE, not a release or complete clinical Skill.\n\nThis isolated candidate adds explicitly bounded Cox LASSO/Elastic Net train/infer using the existing clinanalysis task entry, pinned glmnet coefficient fitting, training-only fixed-offset Breslow baseline and unchanged v0.8 preprocessing owner. Full transforms, coefficients, selection, centering, baseline steps and support are frozen for external application. Existing ordinary-Cox IPCW/PH and v09 explanation interfaces do not automatically accept these new models.\n\nIt also repairs the v09 independent-review P1 long-category nomogram label clipping in this copy only, retaining numeric tables and frozen models. The v09 original remains unchanged.\n\nSee [acceptance](ACCEPTANCE.md), [machine receipt](evidence/final-manifest.json), [independent review entry](REVIEW-HANDOFF.md), [implementation boundary](docs/IMPLEMENTATION-V10.md), [original35 mapping](docs/CAPABILITY-CROSSWALK-V10.md) and [gaps](GAPS.md). Tests use only small synthetic data. Engineering passes do not establish clinical scientific validity. No install, raw database scan, upload, GitHub push/tag, license decision or publication was performed.\n\nRun tools/verify_candidate.py for read-only integrity. Rerun experiments only in a fresh isolated review/development copy with explicit rebinding; never overwrite this frozen candidate.\n',encoding='utf-8')
    handoff=ROOT/'REVIEW-HANDOFF.md';handoff.write_text(handoff.read_text(encoding='utf-8').replace('this handoff is prepared before final acceptance','the final code-bound checks are complete and independent personnel review remains pending'),encoding='utf-8')
    files=[p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='CANDIDATE-SHA256SUMS.txt']
    total=sum(p.stat().st_size for p in files);need(total<=536870912,'DELIVERY_SIZE_REVIEW_REQUIRED')
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':'FROZEN_LOCAL_CANDIDATE','checksum_files':len(files),'checksum_bytes':total,'production_files':len(lock['code_hashes']),'unit_passed':uv['passed'],'acceptance_passed':manifest['total_acceptance_checks_passed'],'runtime_lock_sha256':lh}),flush=True)
if __name__=='__main__':main()
