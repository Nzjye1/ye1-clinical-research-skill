"""Freeze verified local evidence; never fit, relock, install or publish."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':Path(p).relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(ok,reason):
    if not ok:raise SystemExit(reason)
def bound_sources(value):
    for path,digest in value.get('source_sha256',{}).items():need(sha(ROOT/path)==digest,'EVIDENCE_SOURCE_DRIFT:'+path)
def latest(pattern,lockhash):
    matches=[(p,load(p)) for p in sorted((ROOT/'evidence').glob(pattern))]
    matches=[(p,v) for p,v in matches if v.get('runtime_lock_sha256')==lockhash]
    need(bool(matches),'MISSING_CURRENT_LOCK_EVIDENCE:'+pattern)
    return matches[-1]

def main():
    need(not (ROOT/'CANDIDATE-SHA256SUMS.txt').exists(),'CANDIDATE_ALREADY_FROZEN')
    lockpath=ROOT/'runtime-lock.json';lock=load(lockpath);lockhash=sha(lockpath)
    need(lock['core_version']=='0.8.0-candidate1','WRONG_CORE_VERSION')
    for path,digest in lock['code_hashes'].items():need(sha(ROOT/path)==digest,'PRODUCTION_DRIFT:'+path)
    for path,digest in lock['penalized_dependency_hashes'].items():need(sha(path)==digest,'PENALIZED_DEPENDENCY_DRIFT:'+path)
    need(len(lock['penalized_dependency_hashes'])==10,'DEPENDENCY_BINDING_INCOMPLETE')
    need(sha(lock['rscript_engine'])==lock['executable_hashes'][lock['rscript_engine']],'RSCRIPT_ENGINE_DRIFT')
    oldroot=ROOT.parent/'clinical-analysis-core-v0_7-dev-20261024';prior=load(oldroot/'runtime-lock.json')
    for key in ('prediction_provider_versions','association_plan_provider_version','survival_provider_version',
                'cox_prediction_provider_version','survival_evaluation_provider_version','psm_provider_version'):
        need(lock[key]==prior[key],'PREVIOUS_PROVIDER_CHANGED:'+key)
    preserved=['src/clinanalysis/R/table1.R','src/clinanalysis/R/clinical_prediction_common.R',
      'python/clinical_methods/association.py','python/clinical_methods/prediction.py',
      'python/clinical_methods/continuous_ridge/prediction_engine.py','python/clinical_methods/continuous_ridge/prediction_metrics.py',
      'python/clinical_methods/survival.py','python/clinical_methods/cox_prediction_bridge.py','python/clinical_methods/survival_v05_contracts.py',
      'python/clinical_methods/survival_evaluation.py','python/clinical_methods/survival_evaluation_bridge.py','python/clinical_methods/survival_v06_contracts.py',
      'src/clinanalysis/R/plugin_causal_comparison.R','src/clinanalysis/R/psm_v07.R','python/clinical_methods/psm_v07_contracts.py']
    for path in preserved:need(sha(ROOT/path)==sha(oldroot/path),'PREVIOUS_NUMERICAL_OWNER_CHANGED:'+path)
    settings=[('baseline_association','acceptance-*',41,'test_acceptance.py'),
      ('association_plan','association-plan-acceptance-*',53,'test_association_plan_acceptance.py'),
      ('prediction','prediction-acceptance-*',49,'test_prediction_acceptance.py'),
      ('survival_v04_regression','survival-acceptance-*',47,'test_survival_acceptance.py'),
      ('survival_v05_regression','survival-v05-acceptance-*',50,'test_survival_v05_acceptance.py'),
      ('survival_v06_evaluation','survival-v06-acceptance-*',59,'test_survival_v06_acceptance.py'),
      ('psm_v07','psm-v07-acceptance-*',48,'test_psm_v07_acceptance.py'),
      ('penalized_v08','penalized-v08-acceptance-*',95,'test_penalized_v08_acceptance.py')]
    suites={};history=[]
    for key,pattern,count,script in settings:
        path,receipt=latest(pattern+'/acceptance-receipt.json',lockhash)
        need(receipt['summary']['failed']==0 and receipt['summary']['passed']==count and
             all(x['status']=='PASS' for x in receipt['checks']),'FAILED_OR_INCOMPLETE_SUITE:'+key)
        if 'test_script_sha256' in receipt:need(receipt['test_script_sha256']==sha(ROOT/'tests'/script),'TEST_SOURCE_DRIFT:'+key)
        bound_sources(receipt);suites[key]=(path,receipt)
        for p in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            value=load(p);history.append({**ref(p),'suite':key,'summary':value['summary'],'runtime_lock_sha256':value['runtime_lock_sha256']})
    op,orr=latest('prediction-output-v03-*/receipt.json',lockhash)
    need(orr['summary']['passed']==10 and orr['summary']['failed']==0,'PREDICTION_OUTPUT_REGRESSION_FAILED')
    bound_sources(orr)
    noop=ROOT/'evidence/prediction-output-no-op-v08.json';no_op=load(noop)
    need(no_op['status']=='PASS','NO_OPERATING_POINT_FAILED')
    need(sha(ROOT/'tests/prediction_output_no_operating_point.R')==no_op['script_sha256'],'NO_OPERATING_POINT_SOURCE_DRIFT')
    for pathkey,hashkey in (('result_ref','result_sha256'),('log','log_sha256')):
        need(sha(ROOT/no_op[pathkey])==no_op[hashkey],'NO_OPERATING_POINT_EVIDENCE_DRIFT')
    runnerpath,runner=latest('regressions-v08-*/runner-receipt.json',lockhash)
    need(runner['status']=='PASS' and runner['production_unchanged'] and len(runner['runs'])==8,'REGRESSION_RUNNER_INCOMPLETE')
    need(sha(ROOT/'tools/run_regressions_v08.py')==runner['runner_script_sha256'],'REGRESSION_RUNNER_SOURCE_DRIFT')
    for row in runner['runs']:
        need(row['status']=='PASS' and row['returncode']==0,'RUNNER_SUITE_FAILED')
        need(sha(ROOT/row['script'])==row['script_sha256'] and sha(ROOT/row['log'])==row['log_sha256'],'RUNNER_LOG_OR_SOURCE_DRIFT')
        if 'reused_from_receipt' in row:need(sha(ROOT/row['reused_from_receipt'])==row['reused_from_receipt_sha256'],'REUSED_RECEIPT_DRIFT')
    unitpath,units=latest('units-v08-*/unit-receipt.json',lockhash)
    need(units['status']=='PASS' and units['returncode']==0 and units['production_and_tests_unchanged'],'FINAL_UNITS_FAILED')
    need(units['passed']>=603,'FINAL_UNITS_INCOMPLETE');bound_sources(units)
    need(sha(ROOT/'tools/run_units_v08.py')==units['runner_sha256'],'UNIT_RUNNER_SOURCE_DRIFT')
    unitlog=ROOT/units['log_ref'];need(sha(unitlog)==units['log_sha256'],'UNIT_LOG_DRIFT')
    changespath=ROOT/'evidence/test-expectation-update-v08.json';changes=load(changespath)
    need(changes['status']=='PASS' and changes['modified_test_files']==13 and len(changes['checks'])==35,'INHERITED_TEST_CHECK_INCOMPLETE')
    for item in changes['checks']:need(sha(ROOT/'tests'/item['test'])==item['current_sha256'],'INHERITED_TEST_DRIFT')
    guardpath=ROOT/'evidence/previous-candidates-preservation.json';guard=load(guardpath)
    need(guard['unchanged'] and len(guard['current_manifest_valid'])==7 and all(guard['current_manifest_valid'].values()),'OLD_CANDIDATE_CHANGED')
    origins=ROOT/'evidence/source-provenance.json'
    for item in load(origins)['source_tree_files']:need(sha(item['original'])==item['original_hash'],'ORIGINAL_SOURCE_CHANGED')
    fixturepath=ROOT/'fixtures/penalized-v08/fixture-manifest.json';fixture=load(fixturepath)
    for name,digest in fixture['source_sha256'].items():need(sha(fixturepath.parent/name)==digest,'FIXTURE_DRIFT:'+name)
    audits=[]
    programs={'association_plan':'audit_association_plan_exports.py','survival_v04_regression':'audit_survival_exports.py',
      'survival_v05_regression':'audit_survival_v05_exports.py','survival_v06_evaluation':'audit_survival_v06_exports.py',
      'psm_v07':'audit_psm_v07_exports.py','penalized_v08':'audit_penalized_v08_exports.py'}
    for key,program in programs.items():
        p=suites[key][0].parent/'export-audit.json';value=load(p)
        need(value['status']=='PASS' and value['runtime_lock_sha256']==lockhash,'EXPORT_AUDIT_FAILED:'+key)
        need(value['acceptance_receipt_sha256']==sha(suites[key][0]),'EXPORT_RECEIPT_DRIFT:'+key)
        need(value['audit_script_sha256']==sha(ROOT/'tools'/program),'EXPORT_AUDIT_SOURCE_DRIFT:'+key)
        audits.append(ref(p))
    visualpath=ROOT/'evidence/figure-visual-review-v08.json';visual=load(visualpath)
    need(visual['status']=='PASS' and len(visual['figures'])>=4 and visual['runtime_lock_sha256']==lockhash,'VISUAL_REVIEW_INCOMPLETE')
    for item in visual['figures']:need(sha(ROOT/item['local_ref'])==item['sha256'],'VISUAL_ARTIFACT_DRIFT')
    comparisonpath=suites['penalized_v08'][0].parent/'comparison-summary.json';comparison=load(comparisonpath)
    need(comparison['status']=='PASS' and comparison['runtime_lock_sha256']==lockhash and
         comparison['acceptance_receipt_sha256']==sha(suites['penalized_v08'][0]),'PENALIZED_REFERENCE_COMPARISON_INVALID')
    need(comparison['independent_optimizer_validation'] is False,'REFERENCE_SCOPE_OVERCLAIM')
    verificationpath=suites['penalized_v08'][0].parent/'verification-summary.json';verification=load(verificationpath)
    need(verification['status']=='PASS' and verification['runtime_lock_sha256']==lockhash and
         verification['production_and_owned_sources_unchanged'],'PENALIZED_VERIFICATION_INVALID')
    bound_sources(verification)
    for name,digest in verification['receipt_sha256'].items():need(sha(verificationpath.parent/name)==digest,'PENALIZED_VERIFICATION_RECEIPT_DRIFT')
    need(verification['run_counts']=={'unique_entry_outputs':73,'completed':32,'numerical_refusals':9,'contract_refusals':32},'PENALIZED_ENTRY_COVERAGE_INCOMPLETE')
    encodingreviewpath=ROOT/'evidence/encoding-reference-review-v08.json';encodingreview=load(encodingreviewpath)
    need(encodingreview['status']=='PASS' and encodingreview['runtime_lock_sha256']==lockhash and
         encodingreview['provider_sha256']==lock['penalized_provider_version'],'ENCODING_REFERENCE_REVIEW_INVALID')
    sidecars=['docs/METHOD-REVIEW-V06.md','evidence/dependency-probe-v06.json']
    deniedroot=ROOT.parent/'clinical-analysis-core-v0_6-dev-20261024'
    need(all(not (deniedroot/p).exists() and not (ROOT/p).exists() for p in sidecars),'DENIED_SIDECAR_UNEXPECTEDLY_EXISTS')
    execution={'current_runtime_lock_sha256':lockhash,'full_regression_runner':ref(runnerpath),'unit_receipt':ref(unitpath),
      'acceptance_history':history,'development_smoke_receipts':[ref(p) for p in sorted((ROOT/'evidence').glob('smoke-v08-*/receipt.json'))],
      'interrupted_attempts':[ref(p) for p in sorted((ROOT/'evidence').glob('*/interruption-receipt.json'))],
      'superseded_attempts':[ref(p) for p in sorted((ROOT/'evidence').glob('*/superseded-note.json'))],
      'harness_repairs':[ref(p) for p in sorted((ROOT/'evidence').glob('*/harness-repair-note.json'))],
      'development_refinements':[
        'Pinned complete glmnet controls, requested-versus-returned lambda values and positional coefficient extraction; numerical failure never switches optimizer.',
        'Kept full-double JSON transport for new method payloads only; bound exact package/runtime/dependency hashes in each frozen model. Old method JSON policy unchanged.',
        'Binary AUC ranks frozen logit to retain discrimination when probabilities saturate. External inference reports zero fits and no current-fit jerr.',
        'Read-only smoke review found declared codebook reference could be confused with learned reference. Added per-fold/final/frozen fitted levels/reference/encoding to public results and JSON-array CSV cells, with runtime/schema/unit/entry checks. No estimator or matrix changed.',
        'The first complete acceptance attempt was stopped for that output repair. Its patient-mode test fixture incorrectly retained an undeclared group column; fixed only fixture projection, preserved the failed/interrupted receipt and source snapshot, and reran full acceptance with original tolerances.',
        'The first export audit omitted generic metric result IDs from its expected writing-reference set. The actual references contained the complete generic and method-specific union. Preserved the failed audit and source snapshot, repaired the audit to check both layers, and reran the source-bound acceptance and audit without changing production or tolerances.',
        'Temporary executor loss was checked on the same Windows environment before continuation; no uncertain completion was counted.'],
      'previous_denied_v06_sidecars':{'status':'DENIED_NOT_EXECUTED_IN_PRIOR_BATCH','paths':[str(deniedroot/p) for p in sidecars],
        'current_action':'No retry, replacement, or delegated write; still absent and unnecessary for v0_8.'}}
    executionpath=ROOT/'evidence/execution-history-v08.json';dump(executionpath,execution)
    caps=load(ROOT/'method-capabilities.json');need(caps['core_version']==lock['core_version'] and len(caps['methods'])==16,'CAPABILITIES_VERSION_OR_COUNT')
    newmethods={'prediction.continuous.signed.lasso','prediction.continuous.signed.elasticnet','prediction.binary.lasso','prediction.binary.elasticnet'}
    for method in caps['methods']:
        mid=method['method_id'];key=('penalized_v08' if mid in newmethods else 'psm_v07' if mid=='causal.psm.att.continuous' else
          'survival_v06_evaluation' if mid=='evaluation.survival.cox.ipcw' else 'survival_v05_regression' if mid in ('prediction.survival.cox','survival.cox.association') else
          'survival_v04_regression' if mid.startswith('survival.') else 'prediction' if mid.startswith('prediction.') else 'association_plan' if mid.endswith('.plan') else 'baseline_association')
        method['integration_status']='synthetic_engineering_validated'
        method['validation_evidence']=[{**ref(suites[key][0]),'scope':'Small synthetic engineering acceptance only; clinical review pending'}]
    dump(ROOT/'method-capabilities.json',caps)
    gaps=['Clinical scientific acceptance, real patients/databases and independent external populations',
      'Independent optimizer validation; reference uses the same pinned glmnet engine plus independent preprocessing/CV/formulas',
      'Multi-alpha or temporal/nested CV, grouped category penalties, selection stability, valid postselection inference and uncertainty',
      'SHAP, Cox-LASSO, general signed Ridge, new penalized calibration/DCA and remaining broad method roadmap',
      'Inherited PSM/survival/causal/longitudinal/survey/trajectory gaps recorded in GAPS.md',
      'Complete clinical Skill integration, packaging, distribution/license choice and publication']
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE',
      'created_at':datetime.now(timezone.utc).isoformat(),'runtime_lock_sha256':lockhash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{**ref(unitlog),'receipt':ref(unitpath),'passed':units['passed'],'failed':0},
      'final_suites':{key:{**ref(p),**r['summary']} for key,(p,r) in suites.items()},
      'prediction_output_contract_regression':{**ref(op),**orr['summary'],'no_operating_point_helper':ref(noop)},
      'total_acceptance_checks_passed':sum(r['summary']['passed'] for p,r in suites.values())+orr['summary']['passed'],
      'total_acceptance_checks_failed':0,'export_audits':audits,'figure_visual_review':ref(visualpath),
      'previous_candidates_preservation':{**ref(guardpath),**guard},'source_provenance':ref(origins),
      'test_expectation_changes':ref(changespath),'inherited_test_files_checked':len(changes['checks']),
      'numerical_penalized_owner':'src/clinanalysis/R/penalized_v08.R','penalized_provider_version':lock['penalized_provider_version'],
      'penalized_engine':lock['penalized_runtime'],'prior_numerical_owners_and_providers_unchanged':True,
      'fixture_manifest':ref(fixturepath),'method_ids':[m['method_id'] for m in caps['methods']],
      'test_only':True,'scientific_review':'pending','export_status':'local_only','independent_personnel_review':'PENDING',
      'independent_R_reference':'INDEPENDENT_PREPROCESSING_CV_AND_FORMULAS_WITH_SAME_PINNED_GLMNET_NOT_INDEPENDENT_OPTIMIZER',
      'independent_reference_comparison':{**ref(comparisonpath),**comparison},
      'penalized_verification_summary':ref(verificationpath),'encoding_reference_review':ref(encodingreviewpath),
      'review_entry':'REVIEW-HANDOFF.md','not_tested_or_unimplemented':gaps,'remaining_execution_blockers':[],
      'prior_denied_writes_not_retried':execution['previous_denied_v06_sidecars'],'execution_history':ref(executionpath),
      'installation_or_download_performed':False,'system_changes_performed':False,'publication_or_push_performed':False,
      'license_release_decision':'NOT_MADE','checksum_scope':'Production, tools, tests, docs, synthetic fixtures, metadata and aggregate evidence; individual run data remain local/private and bound by run/result artifact hashes.'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    lines=['# v0_8 local candidate acceptance','',f'Frozen core {lock["core_version"]}. {units["passed"]} unit tests and {manifest["total_acceptance_checks_passed"]} acceptance checks passed; zero final failures. All final suites use one production lock.','']
    lines += [f'- {key}: {r["summary"]["passed"]} passed; [receipt]({p.relative_to(ROOT).as_posix()})' for key,(p,r) in suites.items()]
    lines += [f'- Prediction output correction: 10 passed; [receipt]({op.relative_to(ROOT).as_posix()})','',
      'Six public export audits and representative figure inspections passed. Prior numerical owners, seven frozen candidates and original sources were checked unchanged. Development failures and interrupted attempts remain in execution-history-v08.json and are not counted as passes.',
      '', 'The four new methods use glmnet 5.1 for signed continuous and binary outcomes. Independent preprocessing/CV/direct-engine reference and closed-form examples do not constitute independent-optimizer or clinical validation. Full Skill integration and remaining gaps are not complete.',
      '', '[Machine evidence](evidence/final-manifest.json) | [Independent review entry](REVIEW-HANDOFF.md) | [Gaps](GAPS.md)','']
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'DEVELOPMENT-STATUS.md').write_text('# v0_8 status\n\nFROZEN_LOCAL_CANDIDATE. See ACCEPTANCE.md and evidence/final-manifest.json. No further development edits in this directory; subsequent fixes use a new isolated copy. Not released; clinical scientific and personnel-independent review pending.\n',encoding='utf-8')
    files=set()
    for folder in ('src','python','schemas','tools','tests','docs','fixtures'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update(p for p,r in suites.values());files.update(ROOT/a['local_ref'] for a in audits);files.update((op,comparisonpath,unitpath,unitlog))
    for directory in (ROOT/'evidence').iterdir():
        if not directory.is_dir():continue
        files.update(p for p in directory.iterdir() if p.is_file() and (p.suffix=='.json' or p.name.endswith('.log')))
        snapshot=directory/'source-snapshot'
        if snapshot.is_dir():files.update(p for p in snapshot.rglob('*') if p.is_file())
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['freeze_status'],'checksum_files':len(files),'production_files':len(lock['code_hashes']),
      'unit_tests':units['passed'],'acceptance_passed':manifest['total_acceptance_checks_passed'],'acceptance_failed':0,'runtime_lock_sha256':lockhash}))
if __name__=='__main__':main()
