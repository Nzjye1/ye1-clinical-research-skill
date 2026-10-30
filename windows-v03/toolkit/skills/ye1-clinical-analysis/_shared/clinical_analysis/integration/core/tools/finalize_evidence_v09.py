"""Freeze only completed code-bound local evidence; no fitting or relocking."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'clinical-analysis-core-v0_8-dev-20261024'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':Path(p).relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(ok,reason):
    if not ok:raise SystemExit(reason)
def bound_sources(v):
    for p,h in v.get('source_sha256',{}).items():need(sha(ROOT/p)==h,'EVIDENCE_SOURCE_DRIFT:'+p)
def latest(pattern,lockhash):
    values=[(p,load(p)) for p in sorted((ROOT/'evidence').glob(pattern))]
    values=[(p,v) for p,v in values if v.get('runtime_lock_sha256')==lockhash]
    need(bool(values),'MISSING_CURRENT_LOCK_EVIDENCE:'+pattern)
    return values[-1]

def main():
    need(not (ROOT/'CANDIDATE-SHA256SUMS.txt').exists(),'CANDIDATE_ALREADY_FROZEN')
    lockpath=ROOT/'runtime-lock.json';lock=load(lockpath);lockhash=sha(lockpath)
    need(lock['core_version']=='0.9.0-candidate1','WRONG_CORE_VERSION')
    for p,h in lock['code_hashes'].items():need(sha(ROOT/p)==h,'PRODUCTION_DRIFT:'+p)
    prior=load(OLD/'runtime-lock.json')
    providers=['prediction_provider_versions','association_plan_provider_version','survival_provider_version',
      'cox_prediction_provider_version','survival_evaluation_provider_version','psm_provider_version','penalized_provider_version']
    for k in providers:need(lock[k]==prior[k],'OLD_PROVIDER_CHANGED:'+k)
    for p,h in lock['penalized_dependency_hashes'].items():need(sha(p)==h,'DEPENDENCY_DRIFT:'+p)
    need(lock['penalized_runtime']==prior['penalized_runtime'] and len(lock['penalized_dependency_hashes'])==10,'RUNTIME_CHANGED')
    preserved=['src/clinanalysis/R/table1.R','src/clinanalysis/R/clinical_prediction_common.R',
      'python/clinical_methods/association.py','python/clinical_methods/prediction.py',
      'python/clinical_methods/continuous_ridge/prediction_engine.py','python/clinical_methods/continuous_ridge/prediction_metrics.py',
      'python/clinical_methods/survival.py','python/clinical_methods/cox_prediction_bridge.py',
      'python/clinical_methods/survival_evaluation.py','python/clinical_methods/survival_evaluation_bridge.py',
      'src/clinanalysis/R/psm_v07.R','src/clinanalysis/R/penalized_v08.R']
    for p in preserved:need(sha(ROOT/p)==sha(OLD/p),'OLD_NUMERICAL_SOURCE_CHANGED:'+p)
    settings=[('baseline_association','acceptance-*',41,'test_acceptance.py'),
      ('association_plan','association-plan-acceptance-*',53,'test_association_plan_acceptance.py'),
      ('prediction','prediction-acceptance-*',49,'test_prediction_acceptance.py'),
      ('survival_v04','survival-acceptance-*',47,'test_survival_acceptance.py'),
      ('survival_v05','survival-v05-acceptance-*',50,'test_survival_v05_acceptance.py'),
      ('survival_v06','survival-v06-acceptance-*',59,'test_survival_v06_acceptance.py'),
      ('psm_v07','psm-v07-acceptance-*',48,'test_psm_v07_acceptance.py'),
      ('penalized_v08','penalized-v08-acceptance-*',95,'test_penalized_v08_acceptance.py'),
      ('interpretation_v09','interpretation-v09-acceptance-*',79,'test_interpretation_v09_acceptance.py')]
    suites={};history=[]
    for key,pattern,count,script in settings:
        p,v=latest(pattern+'/acceptance-receipt.json',lockhash)
        need(v['summary']['failed']==0 and all(x['status']=='PASS' for x in v['checks']),'FAILED_SUITE:'+key)
        need(v['summary']['passed']==len(v['checks']),'SUMMARY_COUNT_MISMATCH:'+key)
        if count is not None:need(v['summary']['passed']==count,'INCOMPLETE_SUITE:'+key)
        else:need(v['summary']['passed']>=50,'INTERPRETATION_COVERAGE_INCOMPLETE')
        if 'test_script_sha256' in v:need(sha(ROOT/'tests'/script)==v['test_script_sha256'],'TEST_SOURCE_DRIFT:'+key)
        bound_sources(v);suites[key]=(p,v)
        for hp in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            hv=load(hp);history.append({**ref(hp),'suite':key,'summary':hv['summary'],'runtime_lock_sha256':hv['runtime_lock_sha256']})
    op,ov=latest('prediction-output-v03-*/receipt.json',lockhash)
    need(ov['summary']['passed']==10 and ov['summary']['failed']==0 and len(ov['checks'])==10 and
         all(c['status']=='PASS' for c in ov['checks']),'PREDICTION_OUTPUT_REGRESSION_FAILED')
    need(ov['test_script_sha256']==sha(ROOT/'tests/test_prediction_output_contract.py'),'PREDICTION_OUTPUT_TEST_SOURCE_DRIFT')
    bound_sources(ov)
    rp,rv=latest('regressions-v09-*/runner-receipt.json',lockhash)
    need(rv['status']=='PASS' and rv['production_unchanged'] and len(rv['runs'])==9,'REGRESSION_RUNNER_INCOMPLETE')
    need(rv['runner_script_sha256']==sha(ROOT/'tools/run_regressions_v09.py'),'RUNNER_SOURCE_DRIFT')
    for r in rv['runs']:
        need(r['status']=='PASS' and r['returncode']==0,'RUNNER_SUITE_FAILURE')
        need(sha(ROOT/r['script'])==r['script_sha256'] and sha(ROOT/r['log'])==r['log_sha256'],'RUNNER_SOURCE_OR_LOG_DRIFT')
    fixture_repair=load(ROOT/'evidence/regression-fixture-repair-v09.json')
    need(fixture_repair['status']=='SUPPORTING_FIXTURE_RESTORED' and
         fixture_repair['production_or_test_source_changed'] is False,'INHERITED_FIXTURE_REPAIR_UNVERIFIED')
    need(sha(ROOT/fixture_repair['local_ref'])==fixture_repair['sha256']==sha(fixture_repair['original']),
         'INHERITED_FIXTURE_SOURCE_DRIFT')
    need(sha(ROOT/fixture_repair['failed_log'])==fixture_repair['failed_log_sha256'],'INHERITED_FIXTURE_FAILURE_LOG_DRIFT')
    noop=ROOT/'evidence/prediction-output-no-op-v09.json';nv=load(noop)
    need(nv['status']=='PASS' and nv['script_sha256']==sha(ROOT/'tests/prediction_output_no_operating_point.R'),'NO_OPERATING_POINT_FAILED')
    for pkey,hkey in [('result_ref','result_sha256'),('log','log_sha256')]:need(sha(ROOT/nv[pkey])==nv[hkey],'NO_OPERATING_POINT_DRIFT')
    up,uv=latest('units-v09-*/unit-receipt.json',lockhash)
    need(uv['status']=='PASS' and uv['returncode']==0 and uv['production_and_tests_unchanged'] and uv['passed']>603,'UNITS_INCOMPLETE')
    bound_sources(uv);need(uv['runner_sha256']==sha(ROOT/'tools/run_units_v09.py'),'UNIT_RUNNER_DRIFT')
    need(sha(ROOT/uv['log_ref'])==uv['log_sha256'],'UNIT_LOG_DRIFT')
    need(uv['r_provider']['failed']==0 and uv['r_provider']['returncode']==0 and
         sha(ROOT/uv['r_provider']['log_ref'])==uv['r_provider']['log_sha256'],'R_PROVIDER_UNIT_FAILED_OR_DRIFTED')
    ep=ROOT/'evidence/test-expectation-update-v09.json';ev=load(ep)
    need(ev['status']=='PASS' and len(ev['checks'])==43,'INHERITED_TEST_CHECK_INCOMPLETE')
    for r in ev['checks']:need(sha(ROOT/'tests'/r['test'])==r['current_sha256'],'INHERITED_TEST_DRIFT')
    gp=ROOT/'evidence/previous-candidates-preservation.json';gv=load(gp)
    need(gv['unchanged'] and len(gv['current_manifest_valid'])==8 and all(gv['current_manifest_valid'].values()),'OLD_CANDIDATE_CHANGED')
    origins=load(OLD/'evidence/source-provenance.json')['source_tree_files']
    for item in origins:need(sha(item['original'])==item['original_hash'],'ORIGINAL_SOURCE_CHANGED')
    audits=[]
    audit_programs={'association_plan':'audit_association_plan_exports.py','survival_v04':'audit_survival_exports.py',
      'survival_v05':'audit_survival_v05_exports.py','survival_v06':'audit_survival_v06_exports.py',
      'psm_v07':'audit_psm_v07_exports.py','penalized_v08':'audit_penalized_v08_exports.py',
      'interpretation_v09':'audit_interpretation_v09_exports.py'}
    for k,program in audit_programs.items():
        p=suites[k][0].parent/'export-audit.json';v=load(p)
        need(v['status']=='PASS' and v['runtime_lock_sha256']==lockhash,'EXPORT_AUDIT_FAILED:'+k)
        need(v['acceptance_receipt_sha256']==sha(suites[k][0]),'EXPORT_AUDIT_RECEIPT_DRIFT:'+k)
        need(v['audit_script_sha256']==sha(ROOT/'tools'/program),'EXPORT_AUDIT_SCRIPT_DRIFT:'+k);audits.append(ref(p))
    cp=suites['interpretation_v09'][0].parent/'comparison-summary.json';cv=load(cp)
    need(cv['status']=='PASS' and cv['runtime_lock_sha256']==lockhash,'INTERPRETATION_REFERENCE_FAILED')
    need(cv['acceptance_receipt_sha256']==sha(suites['interpretation_v09'][0]),'REFERENCE_RECEIPT_DRIFT')
    bound_sources(cv)
    avp=suites['interpretation_v09'][0].parent/'visual-review.json';av=load(avp)
    need(av['status']=='PASS' and av['runtime_lock_sha256']==lockhash and len(av['images'])==4,'FINAL_SUITE_VISUAL_REVIEW_INCOMPLETE')
    need(av['acceptance_receipt_sha256']==sha(suites['interpretation_v09'][0]),'FINAL_SUITE_VISUAL_RECEIPT_DRIFT')
    for r in av['images']:need(sha(avp.parent/r['path'])==r['sha256'],'FINAL_SUITE_VISUAL_ARTIFACT_DRIFT')
    vp=ROOT/'evidence/figure-visual-review-v09.json';vv=load(vp)
    need(vv['status']=='PASS' and vv['runtime_lock_sha256']==lockhash and len(vv['figures'])>=4,'VISUAL_REVIEW_INCOMPLETE')
    for r in vv['figures']:need(sha(ROOT/r['local_ref'])==r['sha256'],'VISUAL_ARTIFACT_DRIFT')
    pf=ROOT/'evidence/plot-label-fix-v09/verification-final.json';pv=load(pf)
    need(pv['status']=='PASS','PLOT_LABEL_FIX_UNVERIFIED')
    need(pv['numerical_outputs_unchanged'] and pv['repaired_image_visually_inspected'],'PLOT_FIX_CHECK_INCOMPLETE')
    # The later all-missing repair changes the numerical provider and runtime
    # lock. Preserve the plot-only verification against its archived lock; the
    # final visual review above verifies the current complete entry figures.
    archived_plot_lock=ROOT/'evidence/all-missing-fix-v09/source-snapshot/runtime-lock.json'
    need(sha(archived_plot_lock)==pv['runtime_lock_sha256'],'PLOT_FIX_ARCHIVED_LOCK_MISSING')
    for r in pv['bound_files']:
        target=archived_plot_lock if r['local_ref']=='runtime-lock.json' else (
            ROOT/'evidence/category-array-fix-v09/source-snapshot/clinical_interpretation_v09.R'
            if r['local_ref']=='src/clinanalysis/R/clinical_interpretation_v09.R' else ROOT/r['local_ref'])
        need(sha(target)==r['sha256'],'PLOT_FIX_EVIDENCE_DRIFT')
    missing_fix=load(ROOT/'evidence/all-missing-fix-v09/provider-unit-all-missing-run1.json')
    need(missing_fix['status']=='PASSED' and missing_fix['returncode']==0 and
         missing_fix['unit_results']['passed']==22 and missing_fix['unit_results']['failed']==0,'ALL_MISSING_FIX_UNVERIFIED')
    need(missing_fix['source_hashes_before']==missing_fix['source_hashes_after'],'ALL_MISSING_FIX_TEST_SOURCE_DRIFT')
    for p,h in missing_fix['source_hashes_after'].items():need(sha(ROOT/p)==h,'ALL_MISSING_FIX_CURRENT_SOURCE_DRIFT')
    need(sha(ROOT/missing_fix['log_path'])==missing_fix['log_sha256'],'ALL_MISSING_FIX_LOG_DRIFT')
    array_fix=load(ROOT/'evidence/category-array-fix-v09/serialization-probe-result.json')
    need(array_fix['status']=='PASS' and len(array_fix['cases'])==4 and all(r['passed'] for r in array_fix['cases']),
         'CATEGORY_ARRAY_FIX_UNVERIFIED')
    need(sha(ROOT/'src/clinanalysis/R/clinical_interpretation_v09.R')==array_fix['source_sha256'],'CATEGORY_ARRAY_FIX_SOURCE_DRIFT')
    crosspath=ROOT/'docs/CAPABILITY-CROSSWALK-V09.json';cross=load(crosspath)
    need(cross['row_count']==35 and len(cross['rows'])==35 and cross['preserves_original_order_and_duplicates'],'ORIGINAL_CROSSWALK_INCOMPLETE')
    crossmd=ROOT/'docs/CAPABILITY-CROSSWALK-V09.md';crossmdtext=crossmd.read_text(encoding='utf-8')
    pending_caption='第19、33、34行属于本批开发范围，验收前不算通过'
    need(crossmdtext.count(pending_caption)==1,'CROSSWALK_FREEZE_CAPTION_NOT_UNIQUE')
    deniedroot=ROOT.parent/'clinical-analysis-core-v0_6-dev-20261024'
    sidecars=['docs/METHOD-REVIEW-V06.md','evidence/dependency-probe-v06.json']
    need(all(not(deniedroot/p).exists() and not(ROOT/p).exists() for p in sidecars),'DENIED_SIDECAR_UNEXPECTEDLY_EXISTS')
    caps=load(ROOT/'method-capabilities.json');need(caps['core_version']==lock['core_version'] and len(caps['methods'])==17,'CAPABILITY_COUNT_OR_VERSION')
    pen={'prediction.continuous.signed.lasso','prediction.continuous.signed.elasticnet','prediction.binary.lasso','prediction.binary.elasticnet'}
    for m in caps['methods']:
        mid=m['method_id'];k=('interpretation_v09' if mid=='interpretation.linear.interventional' else 'penalized_v08' if mid in pen else
          'psm_v07' if mid=='causal.psm.att.continuous' else 'survival_v06' if mid=='evaluation.survival.cox.ipcw' else
          'survival_v05' if mid in ('prediction.survival.cox','survival.cox.association') else 'survival_v04' if mid.startswith('survival.') else
          'prediction' if mid.startswith('prediction.') else 'association_plan' if mid.endswith('.plan') else 'baseline_association')
        m['integration_status']='synthetic_engineering_validated';m['validation_evidence']=[{**ref(suites[k][0]),'scope':'Synthetic software acceptance only; scientific review pending'}]
    dump(ROOT/'method-capabilities.json',caps)
    for r in cross['rows']:
        r['implementation_state']='synthetic_engineering_validated_bounded_scope' if r['registered_methods'] else 'not_implemented_or_definition_pending'
    dump(crosspath,cross)
    crossmd.write_text(crossmdtext.replace(pending_caption,'第19、33、34行的本批限定范围已通过合成工程验收，仍不代表该原始项目的全部能力完成'),encoding='utf-8')
    historypath=ROOT/'evidence/execution-history-v09.json'
    dump(historypath,{'current_runtime_lock_sha256':lockhash,'acceptance_history':history,
      'development_receipts':[ref(p) for p in sorted((ROOT/'evidence').glob('smoke-v09-*/receipt.json'))],
      'interrupted_acceptance_receipts':[ref(p) for p in sorted((ROOT/'evidence').glob('interpretation-v09-acceptance-*/interruption-receipt.json'))],
      'interrupted_regression_receipts':[ref(p) for p in sorted((ROOT/'evidence').glob('regressions-v09-*/interruption-receipt.json'))],
      'regression_history':[{**ref(p),'status':load(p)['status']} for p in sorted((ROOT/'evidence').glob('regressions-v09-*/runner-receipt.json'))],
      'inherited_regression_fixture_repair':ref(ROOT/'evidence/regression-fixture-repair-v09.json'),
      'failed_run_diagnoses':[ref(p) for pattern in ('failure-classification.json','all-missing-category-diagnosis.json','harness-repair-note.json','csv-array-diagnosis.json','targeted-export-inspection.json')
        for p in sorted((ROOT/'evidence').glob('interpretation-v09-acceptance-*/'+pattern))],
      'targeted_repair_evidence':[ref(p) for folder in ('all-missing-fix-v09','category-array-fix-v09')
        for p in sorted((ROOT/'evidence'/folder).glob('*.json'))],
      'plot_label_correction':{'issue':ref(ROOT/'evidence/plot-label-fix-v09/issue.json'),'verification':ref(pf),
        'scope':'Plot headroom only; verification binds the archived pre-all-missing-fix lock. Final current-lock figures independently visually checked; all final validation rerun.'},
      'prior_denied_v06_sidecars':{'status':'DENIED_NOT_EXECUTED_IN_PRIOR_BATCH','paths':[str(deniedroot/p) for p in sidecars],'retried':False},
      'development_output_logs':[ref(p) for p in sorted((ROOT/'outputs').rglob('*.log'))],
      'development_projection_receipts':[ref(p) for p in sorted((ROOT/'outputs').rglob('*smoke*.json'))],
      'provider_development_report':{'source':'delegated provider tooling; final persistent code-bound R test log is in unit_receipt',
        'reported_fixes':['Missing category values represented as JSON null','Exact reload validation followed by native reconstructed R structures to normalize integer/double representation','Bounded byte hash reads in the test avoid an unreliable Windows R file-access precheck; no system ACL changes']},
      'rule':'Failed/superseded development attempts are retained and are not counted as final passes.'})
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE',
      'created_at':datetime.now(timezone.utc).isoformat(),'runtime_lock_sha256':lockhash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{'receipt':ref(up),'log':ref(ROOT/uv['log_ref']),'passed':uv['passed'],'failed':0,
        'python_passed':uv['python_passed'],'r_provider_passed':uv['r_provider']['passed'],'r_provider_log':ref(ROOT/uv['r_provider']['log_ref'])},
      'final_suites':{k:{**ref(p),**v['summary']} for k,(p,v) in suites.items()},
      'prediction_output_contract_regression':{**ref(op),**ov['summary'],'no_operating_point':ref(noop)},
      'total_acceptance_checks_passed':sum(v['summary']['passed'] for p,v in suites.values())+10,'total_acceptance_checks_failed':0,
      'full_regression_runner':ref(rp),'export_audits':audits,'figure_visual_review':ref(vp),
      'final_interpretation_suite_visual_review':ref(avp),
      'independent_formula_reference':ref(cp),'independent_official_SHAP_or_rms_runtime_validation':False,
      'previous_candidates_preservation':ref(gp),'prior_numerical_owners_and_providers_unchanged':True,
      'original_bound_source_files_checked':len(origins),'inherited_test_expectations':ref(ep),'original_35_row_crosswalk':ref(crosspath),
      'interpretation_owner':'src/clinanalysis/R/interpretation_v09.R','interpretation_provider_version':lock['interpretation_provider_version'],
      'model_scope':sorted(pen),'test_only':True,'scientific_review':'pending','export_status':'local_only','independent_personnel_review':'PENDING',
      'remaining_execution_blockers':[],'not_tested_or_unimplemented':['Cox/Ridge/association explanations and nomograms','Conditional, probability-scale or nonlinear SHAP',
        'Cox-LASSO; binary/survival matched inference; remaining original 35-row gaps','Real patient data, clinical validation and scientific approval','Complete clinical Skill packaging, license choice or release'],
      'execution_history':ref(historypath),'review_entry':'REVIEW-HANDOFF.md',
      'installation_performed':False,'system_changes_performed':False,'publication_or_push_performed':False,'license_release_decision':'NOT_MADE'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    lines=['# v0_9 local candidate acceptance','',f'Frozen core {lock["core_version"]}: {uv["passed"]} unit tests and {manifest["total_acceptance_checks_passed"]} acceptance checks passed, zero final failures. All final entry suites use the same production lock.','']
    lines += [f'- {k}: {v["summary"]["passed"]} passed; [receipt]({p.relative_to(ROOT).as_posix()})' for k,(p,v) in suites.items()]
    lines += ['- Prediction output correction: 10 passed; no-operating-point regression also passed.','',
      'Seven export audits and representative figure inspections passed. Eight previous frozen candidates and their existing numerical providers were preserved. Original source verification is limited to the explicit bound file list.',
      '', 'Development history retains the interrupted run and the 61-pass/18-fail run. The all-missing category type guard, category-array CSV projection and cropped plot label were repaired; two acceptance-fixture construction errors were corrected without weakening rejection expectations or numerical tolerances. Superseded runs are not counted as final passes.',
      '', 'New scope: raw-feature grouped interventional linear SHAP, global mean absolute grouped contribution and deterministic nomograms for four frozen penalized models. Gaussian scores use original outcome units; binomial scores use raw log odds. No probability-scale, conditional or generic nonlinear SHAP claim.',
      '', 'Independent coalition/formula references do not constitute official SHAP/rms package validation or clinical scientific approval. The original 35-row crosswalk preserves remaining gaps.',
      '', '[Machine evidence](evidence/final-manifest.json) | [Independent review](REVIEW-HANDOFF.md) | [Gaps](GAPS.md)']
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (ROOT/'DEVELOPMENT-STATUS.md').write_text('# v0_9 status\n\nFROZEN_LOCAL_CANDIDATE. Subsequent changes require a new isolated copy. Not released; scientific and independent personnel review pending. See ACCEPTANCE.md.\n',encoding='utf-8')
    files=set()
    for folder in ('src','python','schemas','tools','tests','docs','fixtures'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update(p for p in (ROOT/'outputs').rglob('*.log') if p.is_file())
    files.update(p for p in (ROOT/'outputs').rglob('*smoke*.json') if p.is_file())
    for directory in (ROOT/'evidence').iterdir():
        if directory.is_dir():
            files.update(p for p in directory.iterdir() if p.is_file() and
                (p.suffix in ('.json','.csv','.R','.py') or p.name.endswith('.log')))
            snapshot=directory/'source-snapshot'
            if snapshot.is_dir():files.update(p for p in snapshot.rglob('*') if p.is_file())
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['freeze_status'],'checksum_files':len(files),'production_files':len(lock['code_hashes']),
      'unit_tests':uv['passed'],'acceptance_passed':manifest['total_acceptance_checks_passed'],'runtime_lock_sha256':lockhash}))
if __name__=='__main__':main()
