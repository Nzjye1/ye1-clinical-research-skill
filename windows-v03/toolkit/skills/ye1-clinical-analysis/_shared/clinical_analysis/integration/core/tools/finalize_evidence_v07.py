"""Freeze verified local evidence only; never fit, relock, install or publish."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def ref(p):return {'local_ref':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
def need(ok,reason):
    if not ok:raise SystemExit(reason)
def main():
    need(not (ROOT/'CANDIDATE-SHA256SUMS.txt').exists(),'CANDIDATE_ALREADY_FROZEN')
    lockpath=ROOT/'runtime-lock.json';lock=load(lockpath);lockhash=sha(lockpath)
    need(lock['core_version']=='0.7.0-candidate1','WRONG_CORE_VERSION')
    for path,digest in lock['code_hashes'].items():need(sha(ROOT/path)==digest,'PRODUCTION_DRIFT:'+path)
    oldroot=ROOT.parent/'clinical-analysis-core-v0_6-dev-20261024';prior=load(oldroot/'runtime-lock.json')
    for key in ('prediction_provider_versions','association_plan_provider_version','survival_provider_version','cox_prediction_provider_version','survival_evaluation_provider_version'):
        need(lock[key]==prior[key],'PREVIOUS_PROVIDER_CHANGED:'+key)
    preserved=['src/clinanalysis/R/table1.R','src/clinanalysis/R/clinical_prediction_common.R',
      'python/clinical_methods/association.py','python/clinical_methods/prediction.py',
      'python/clinical_methods/continuous_ridge/prediction_engine.py','python/clinical_methods/continuous_ridge/prediction_metrics.py',
      'python/clinical_methods/survival.py','python/clinical_methods/cox_prediction_bridge.py','python/clinical_methods/survival_v05_contracts.py','python/clinical_methods/survival_evaluation.py','python/clinical_methods/survival_evaluation_bridge.py','python/clinical_methods/survival_v06_contracts.py','src/clinanalysis/R/plugin_causal_comparison.R']
    for path in preserved:need(sha(ROOT/path)==sha(oldroot/path),'FROZEN_OWNER_CHANGED:'+path)
    settings=[('baseline_association','acceptance-*',41,'test_acceptance.py'),
      ('association_plan','association-plan-acceptance-*',53,'test_association_plan_acceptance.py'),
      ('prediction','prediction-acceptance-*',49,'test_prediction_acceptance.py'),
      ('survival_v04_regression','survival-acceptance-*',47,'test_survival_acceptance.py'),
      ('survival_v05_regression','survival-v05-acceptance-*',50,'test_survival_v05_acceptance.py'),
      ('survival_v06_evaluation','survival-v06-acceptance-*',59,'test_survival_v06_acceptance.py'),
      ('psm_v07','psm-v07-acceptance-*',48,'test_psm_v07_acceptance.py')]
    suites={};history=[]
    for key,pattern,count,script in settings:
        candidates=[]
        for path in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            receipt=load(path);history.append({**ref(path),'suite':key,'summary':receipt['summary'],'runtime_lock_sha256':receipt['runtime_lock_sha256']})
            if receipt['runtime_lock_sha256']==lockhash:candidates.append((path,receipt))
        need(bool(candidates),'MISSING_SUITE:'+key);path,receipt=candidates[-1]
        need(receipt['summary']['failed']==0 and all(x['status']=='PASS' for x in receipt['checks']),'FAILED_SUITE:'+key)
        if count is not None:need(receipt['summary']['passed']==count,'INCOMPLETE_SUITE:'+key)
        else:need(receipt['summary']['passed']>=40,'INCOMPLETE_V07_SUITE')
        if 'test_script_sha256' in receipt:need(receipt['test_script_sha256']==sha(ROOT/'tests'/script),'TEST_SOURCE_DRIFT:'+key)
        for rel,digest in receipt.get('source_sha256',{}).items():need(sha(ROOT/rel)==digest,'ACCEPTANCE_SOURCE_DRIFT:'+rel)
        suites[key]=(path,receipt)
    output=[]
    for path in sorted((ROOT/'evidence').glob('prediction-output-v03-*/receipt.json')):
        receipt=load(path)
        if receipt['runtime_lock_sha256']==lockhash:output.append((path,receipt))
    need(bool(output),'MISSING_PREDICTION_OUTPUT_REGRESSION');op,orr=output[-1]
    need(orr['summary']['passed']==10 and orr['summary']['failed']==0,'FAILED_PREDICTION_OUTPUT_REGRESSION')
    noop=ROOT/'evidence/prediction-output-no-op-v07.json';no_op=load(noop)
    need(no_op['status']=='PASS','FAILED_NO_OPERATING_POINT')
    need(sha(ROOT/'tests/prediction_output_no_operating_point.R')==no_op['script_sha256'],'NO_OPERATING_POINT_SOURCE_DRIFT')
    need(sha(ROOT/no_op['result_ref'])==no_op['result_sha256'],'NO_OPERATING_POINT_RESULT_DRIFT')
    need(sha(ROOT/no_op['log'])==no_op['log_sha256'],'NO_OPERATING_POINT_LOG_DRIFT')
    runners=[]
    for path in sorted((ROOT/'evidence').glob('regressions-v07-*/runner-receipt.json')):
        value=load(path)
        if value['runtime_lock_sha256']==lockhash:runners.append((path,value))
    need(bool(runners) and runners[-1][1]['status']=='PASS','REGRESSION_RUNNER_INCOMPLETE')
    for run in runners[-1][1]['runs']:
        need(sha(ROOT/run['script'])==run['script_sha256'],'RUNNER_SOURCE_DRIFT')
        need(sha(ROOT/run['log'])==run['log_sha256'],'RUNNER_LOG_DRIFT')
        if 'reused_from_receipt' in run:
            need(sha(ROOT/run['reused_from_receipt'])==run['reused_from_receipt_sha256'],'REUSED_RUNNER_RECEIPT_DRIFT')
    if 'runner_script_sha256' in runners[-1][1]:
        need(sha(ROOT/'tools/run_regressions_v07.py')==runners[-1][1]['runner_script_sha256'],'RUNNER_PROGRAM_DRIFT')
    units=[]
    for path in sorted((ROOT/'evidence').glob('units-v07-*/unit-receipt.json')):
        value=load(path)
        if value['runtime_lock_sha256']==lockhash:units.append((path,value))
    need(bool(units),'MISSING_FINAL_UNITS');unitpath,unitreceipt=units[-1]
    need(unitreceipt['status']=='PASS' and unitreceipt['returncode']==0 and unitreceipt['production_and_tests_unchanged'],'FINAL_UNIT_TESTS_FAILED')
    need(sha(ROOT/'tools/run_units_v07.py')==unitreceipt['runner_sha256'],'UNIT_RUNNER_DRIFT')
    for path,digest in unitreceipt['source_sha256'].items():need(sha(ROOT/path)==digest,'UNIT_SOURCE_DRIFT:'+path)
    unit=ROOT/unitreceipt['log_ref'];need(sha(unit)==unitreceipt['log_sha256'],'UNIT_LOG_DRIFT')
    unitn=unitreceipt['passed'];need(unitn>=500,'INCOMPLETE_FINAL_UNITS')
    changespath=ROOT/'evidence/test-expectation-update-v07.json';changes=load(changespath)
    need(changes['status']=='PASS' and changes['modified_test_files']==10,'TEST_EXPECTATIONS_NOT_VERIFIED')
    for item in changes['checks']:need(sha(ROOT/'tests'/item['test'])==item['current_sha256'],'INHERITED_TEST_DRIFT')
    guardpath=ROOT/'evidence/previous-candidates-preservation.json';guard=load(guardpath)
    need(guard['unchanged'] and all(guard['current_manifest_valid'].values()),'PREVIOUS_CANDIDATE_CHANGED')
    origins=ROOT/'evidence/source-provenance.json'
    for item in load(origins)['source_tree_files']:need(sha(Path(item['original']))==item['original_hash'],'ORIGINAL_SOURCE_CHANGED')
    fixture=load(ROOT/'fixtures/psm-v07/fixture-manifest.json')
    for name,digest in fixture['source_sha256'].items():need(sha(ROOT/'fixtures/psm-v07'/name)==digest,'PSM_FIXTURE_DRIFT:'+name)
    audits=[]
    audit_programs={'association_plan':'audit_association_plan_exports.py','survival_v04_regression':'audit_survival_exports.py',
      'survival_v05_regression':'audit_survival_v05_exports.py','survival_v06_evaluation':'audit_survival_v06_exports.py','psm_v07':'audit_psm_v07_exports.py'}
    for key in ('association_plan','survival_v04_regression','survival_v05_regression','survival_v06_evaluation','psm_v07'):
        path=suites[key][0].parent/'export-audit.json';value=load(path)
        need(value['status']=='PASS','EXPORT_AUDIT_FAILED:'+key)
        need(value['runtime_lock_sha256']==lockhash,'EXPORT_AUDIT_LOCK_DRIFT:'+key)
        need(value['acceptance_receipt_sha256']==sha(suites[key][0]),'EXPORT_AUDIT_RECEIPT_DRIFT:'+key)
        need(value['audit_script_sha256']==sha(ROOT/'tools'/audit_programs[key]),'EXPORT_AUDIT_SOURCE_DRIFT:'+key)
        audits.append(ref(path))
    visualpath=ROOT/'evidence/figure-visual-review-v07.json';visual=load(visualpath)
    need(visual['status']=='PASS' and len(visual['figures'])>=2,'VISUAL_REVIEW_REQUIRED')
    need(visual['runtime_lock_sha256']==lockhash,'VISUAL_REVIEW_LOCK_DRIFT')
    for item in visual['figures']:need(sha(ROOT/item['local_ref'])==item['sha256'],'VISUAL_ARTIFACT_DRIFT')
    comparisonpath=suites['psm_v07'][0].parent/'comparison-summary.json'
    comparison=load(comparisonpath)
    need(comparison['status']=='PASS' and comparison['runtime_lock_sha256']==lockhash,'COMPARISON_SUMMARY_INVALID')
    need(comparison['acceptance_receipt_sha256']==sha(suites['psm_v07'][0]),'COMPARISON_RECEIPT_DRIFT')
    scale_detail=suites['psm_v07'][0].parent/'numeric-scale-detail.json'
    need(scale_detail.is_file(),'MISSING_NUMERIC_SCALE_DETAIL')
    scale=load(scale_detail)
    need(scale['status']=='PASS' and scale['runtime_lock_sha256']==lockhash,'NUMERIC_SCALE_DETAIL_INVALID')
    need(scale['acceptance_receipt_sha256']==sha(suites['psm_v07'][0]),'NUMERIC_SCALE_RECEIPT_DRIFT')
    sidecars=['docs/METHOD-REVIEW-V06.md','evidence/dependency-probe-v06.json']
    need(all(not (oldroot/p).exists() and not (ROOT/p).exists() for p in sidecars),'DENIED_SIDECAR_UNEXPECTEDLY_EXISTS')
    execution={'current_runtime_lock_sha256':lockhash,'full_regression_runner':ref(runners[-1][0]),
      'regression_runner_history':[ref(p) for p in sorted((ROOT/'evidence').glob('regressions-v07-*/runner-receipt.json'))],
      'development_smoke_receipts':[ref(p) for p in sorted((ROOT/'evidence').glob('smoke-v07-*/receipt.json'))],
      'acceptance_history':history,
      'development_refinements':[
        'Read-only review found unstable aggregate algebraic checks for large correlated outcomes. Direct pair-difference estimation was correct; the projection no longer rejects it by subtracting marginal means/variances. Hand and real-entry high-baseline regressions were added without relaxing numerical tolerances.',
        'Before first locked integration, schema closure was aligned for empty complete-case arms, nonfinite paired moments/inference and SMD numeric range. True matched pair counts and precise null reasons were retained; old schema branches remained unchanged.',
        'A bounded in-memory R check confirmed default CSV formatting lost small differences on 1e12 baselines. PSM public/private numeric CSV serialization now uses 17 significant digits; no estimator or input values were rounded. Uncomputed overlap figure denominators display unavailable rather than zero.',
        'First smoke passed structural/schema execution but export auditing found metadata.population shadowed overlap.population. Renamed metadata to target_population_scope and added explicit duplicate-field rejection. That guard then exposed the shared effect.estimand; it is now explicitly checked for agreement and emitted once. Superseded locks/source/receipts were preserved, unfinished regression/unit processes stopped, and all final acceptance rerun under the corrected lock. A temporary executor disconnection did not count as completed work.',
        'The first complete PSM suite returned 47 PASS/1 FAIL: the independent oracle put NO_MATCHED_PAIRS into support.reason_code even though common support was successfully computed. Corrected that stage projection and added explicit top/effect refusal assertions, preserving the original receipt and five-file source snapshot. Numerical code, tolerances and coverage remained fixed; all 48 checks and the source-bound unit suite were rerun.'],
      'executor_recovery':'A later transport disconnection interrupted the old-regression runner. After the original Windows executor returned, no Python/Rscript processes remained. Reused only the two completed baseline/association suites after checking exact recorded exit-zero log hashes, final-lock PASS receipts and source hashes. Missing suites were resumed; a per-suite progress receipt now preserves confirmed completions across disconnects.',
      'previous_denied_v06_sidecars':{'status':'DENIED_NOT_EXECUTED_IN_PRIOR_BATCH','paths':[str(oldroot/p) for p in sidecars],
        'current_action':'No retry, replacement, or delegated write; files remain absent and unnecessary for this batch.'}}
    executionpath=ROOT/'evidence/execution-history-v07.json';dump(executionpath,execution)
    caps=load(ROOT/'method-capabilities.json')
    need(caps['core_version']==lock['core_version'],'CAPABILITIES_VERSION_MISMATCH')
    for method in caps['methods']:
        mid=method['method_id'];key=('psm_v07' if mid=='causal.psm.att.continuous' else 'survival_v06_evaluation' if mid=='evaluation.survival.cox.ipcw' else
          'survival_v05_regression' if mid in ('prediction.survival.cox','survival.cox.association') else
          'survival_v04_regression' if mid.startswith('survival.') else 'prediction' if mid.startswith('prediction.') else
          'association_plan' if mid.endswith('.plan') else 'baseline_association')
        method['integration_status']='synthetic_engineering_validated'
        method['validation_evidence']=[{**ref(suites[key][0]),'scope':'Small synthetic engineering acceptance only; clinical review pending'}]
    dump(ROOT/'method-capabilities.json',caps)
    gaps=['Clinical scientific/causal acceptance and real patient/database validation',
      'Formal complete/quasi-separation diagnosis and unavailable MatchIt package validation',
      'Binary/survival matched outcomes, other matching designs and PS/matching-selection uncertainty',
      'Remaining survival evaluation uncertainty, conditional censoring and complex event semantics',
      'Other causal/longitudinal/survey/trajectory methods, complete Skill and distribution/publication']
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE',
      'created_at':datetime.now(timezone.utc).isoformat(),'runtime_lock_sha256':lockhash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{**ref(unit),'receipt':ref(unitpath),'passed':unitn,'failed':0},
      'final_suites':{key:{**ref(path),**receipt['summary']} for key,(path,receipt) in suites.items()},
      'prediction_output_contract_regression':{**ref(op),**orr['summary'],'no_operating_point_helper':ref(noop)},
      'total_acceptance_checks_passed':sum(r['summary']['passed'] for p,r in suites.values())+orr['summary']['passed'],
      'total_acceptance_checks_failed':0,'export_audits':audits,'figure_visual_review':ref(visualpath),
      'previous_candidates_preservation':{**ref(guardpath),**guard},'source_provenance':ref(origins),
      'test_expectation_changes':ref(changespath),'inherited_test_files_checked':len(changes['checks']),
      'numerical_PSM_owner':'src/clinanalysis/R/psm_v07.R',
      'PSM_provider_version':lock['psm_provider_version'],'prior_numerical_owners_and_providers_unchanged':True,
      'survival_evaluation_provider_version':lock['survival_evaluation_provider_version'],
      'frozen_cox_provider_version':lock['cox_prediction_provider_version'],
      'fixture_manifest':ref(ROOT/'fixtures/psm-v07/fixture-manifest.json'),'method_ids':[m['method_id'] for m in caps['methods']],
      'test_only':True,'scientific_review':'pending','export_status':'local_only','independent_personnel_review':'PENDING',
      'independent_R_reference':'INDEPENDENT_R_GLM_SOURCE_FORMULA_MATCHING_AND_PAIRED_T_TEST_NOT_MATCHIT_VALIDATION',
      'independent_formula_comparison':{**ref(comparisonpath),**comparison},
      'numeric_comparison_by_scale':ref(scale_detail),
      'review_entry':'REVIEW-HANDOFF.md','not_tested_or_unimplemented':gaps,'remaining_execution_blockers':[],
      'prior_denied_writes_not_retried':execution['previous_denied_v06_sidecars'],'execution_history':ref(executionpath),
      'installation_or_download_performed':False,'system_changes_performed':False,'publication_or_push_performed':False,
      'license_release_decision':'NOT_MADE','checksum_scope':'Production, tools, tests, docs, synthetic fixtures, metadata and aggregate evidence. Individual run files remain local/private and are bound by run manifests/public artifact hashes.'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    lines=['# v0_7 local candidate acceptance','',f'Frozen core {lock["core_version"]}. {unitn} unit tests passed; {manifest["total_acceptance_checks_passed"]} acceptance checks passed; 0 failed. All final suites use the same production lock.','']
    lines += [f'- {key}: {r["summary"]["passed"]} passed — [receipt]({p.relative_to(ROOT).as_posix()})' for key,(p,r) in suites.items()]
    lines += [f'- Prediction output correction regression: 10 passed — [receipt]({op.relative_to(ROOT).as_posix()})','',
      'Five public export audits and representative visual inspections are recorded. Old numerical owners and v0_1 through v0_6 remain unchanged. Matching pairs and individual PS/outcomes remain local/private.',
      '', 'The new method supports signed continuous outcomes only. Numerical propensity guards are not formal separation diagnosis. Independent R/formula/paired-t reference evidence is not MatchIt package validation. Personnel-independent and clinical scientific review remain pending.',
      '', '[Machine evidence](evidence/final-manifest.json) · [Independent review](REVIEW-HANDOFF.md) · [Gaps](GAPS.md)','']
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'DEVELOPMENT-STATUS.md').write_text('# v0_7 status\n\nFROZEN_LOCAL_CANDIDATE. See ACCEPTANCE.md and evidence/final-manifest.json. No further development edits in this directory; subsequent work uses a new isolated copy. Not released; scientific review pending.\n',encoding='utf-8')
    files=set()
    for folder in ('src','python','schemas','tools','tests','docs','fixtures'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update(path for path,receipt in suites.values());files.update(ROOT/item['local_ref'] for item in audits);files.add(op);files.add(scale_detail)
    files.update(path for path in runners[-1][0].parent.iterdir() if path.is_file())
    files.update(ROOT/item['local_ref'] for item in history)
    files.update(ROOT/item['local_ref'] for item in execution['development_smoke_receipts'])
    for directory in (ROOT/'evidence').iterdir():
        if not directory.is_dir():continue
        files.update(p for p in directory.iterdir() if p.is_file() and p.name in ('harness-repair-note.json','interruption-note.json','superseded-note.json','superseded-receipt.json','receipt.json','comparison-summary.json','preflight-receipt.json','superseded-by-endpoint-defect.json','visual-review-acceptance.json'))
        if directory.name.startswith(('regressions-v07-','units-v07-','recovery-v07-')):
            files.update(p for p in directory.iterdir() if p.is_file())
        snapshot=directory/'source-snapshot'
        if snapshot.is_dir():files.update(p for p in snapshot.rglob('*') if p.is_file())
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['freeze_status'],'checksum_files':len(files),'production_files':len(lock['code_hashes']),
      'unit_tests':unitn,'acceptance_passed':manifest['total_acceptance_checks_passed'],'acceptance_failed':0,'runtime_lock_sha256':lockhash}))
if __name__=='__main__':main()
