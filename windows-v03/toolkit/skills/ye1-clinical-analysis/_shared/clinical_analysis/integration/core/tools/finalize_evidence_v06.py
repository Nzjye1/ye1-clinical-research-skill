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
    need(lock['core_version']=='0.6.0-candidate1','WRONG_CORE_VERSION')
    for path,digest in lock['code_hashes'].items():need(sha(ROOT/path)==digest,'PRODUCTION_DRIFT:'+path)
    oldroot=ROOT.parent/'clinical-analysis-core-v0_5-dev-20261024';prior=load(oldroot/'runtime-lock.json')
    for key in ('prediction_provider_versions','association_plan_provider_version','survival_provider_version','cox_prediction_provider_version'):
        need(lock[key]==prior[key],'PREVIOUS_PROVIDER_CHANGED:'+key)
    preserved=['src/clinanalysis/R/table1.R','src/clinanalysis/R/clinical_prediction_common.R',
      'python/clinical_methods/association.py','python/clinical_methods/prediction.py',
      'python/clinical_methods/continuous_ridge/prediction_engine.py','python/clinical_methods/continuous_ridge/prediction_metrics.py',
      'python/clinical_methods/survival.py','python/clinical_methods/cox_prediction_bridge.py','python/clinical_methods/survival_v05_contracts.py']
    for path in preserved:need(sha(ROOT/path)==sha(oldroot/path),'FROZEN_OWNER_CHANGED:'+path)
    settings=[('baseline_association','acceptance-*',41,'test_acceptance.py'),
      ('association_plan','association-plan-acceptance-*',53,'test_association_plan_acceptance.py'),
      ('prediction','prediction-acceptance-*',49,'test_prediction_acceptance.py'),
      ('survival_v04_regression','survival-acceptance-*',47,'test_survival_acceptance.py'),
      ('survival_v05_regression','survival-v05-acceptance-*',50,'test_survival_v05_acceptance.py'),
      ('survival_v06_evaluation','survival-v06-acceptance-*',None,'test_survival_v06_acceptance.py')]
    suites={};history=[]
    for key,pattern,count,script in settings:
        candidates=[]
        for path in sorted((ROOT/'evidence').glob(pattern+'/acceptance-receipt.json')):
            receipt=load(path);history.append({**ref(path),'suite':key,'summary':receipt['summary'],'runtime_lock_sha256':receipt['runtime_lock_sha256']})
            if receipt['runtime_lock_sha256']==lockhash:candidates.append((path,receipt))
        need(bool(candidates),'MISSING_SUITE:'+key);path,receipt=candidates[-1]
        need(receipt['summary']['failed']==0 and all(x['status']=='PASS' for x in receipt['checks']),'FAILED_SUITE:'+key)
        if count is not None:need(receipt['summary']['passed']==count,'INCOMPLETE_SUITE:'+key)
        else:need(receipt['summary']['passed']>=40,'INCOMPLETE_V06_SUITE')
        if 'test_script_sha256' in receipt:need(receipt['test_script_sha256']==sha(ROOT/'tests'/script),'TEST_SOURCE_DRIFT:'+key)
        for rel,digest in receipt.get('source_sha256',{}).items():need(sha(ROOT/rel)==digest,'ACCEPTANCE_SOURCE_DRIFT:'+rel)
        suites[key]=(path,receipt)
    output=[]
    for path in sorted((ROOT/'evidence').glob('prediction-output-v03-*/receipt.json')):
        receipt=load(path)
        if receipt['runtime_lock_sha256']==lockhash:output.append((path,receipt))
    need(bool(output),'MISSING_PREDICTION_OUTPUT_REGRESSION');op,orr=output[-1]
    need(orr['summary']['passed']==10 and orr['summary']['failed']==0,'FAILED_PREDICTION_OUTPUT_REGRESSION')
    noop=ROOT/'evidence/prediction-output-no-op-v06.json';no_op=load(noop)
    need(no_op['status']=='PASS','FAILED_NO_OPERATING_POINT')
    need(sha(ROOT/'tests/prediction_output_no_operating_point.R')==no_op['script_sha256'],'NO_OPERATING_POINT_SOURCE_DRIFT')
    need(sha(ROOT/no_op['result_ref'])==no_op['result_sha256'],'NO_OPERATING_POINT_RESULT_DRIFT')
    need(sha(ROOT/no_op['log'])==no_op['log_sha256'],'NO_OPERATING_POINT_LOG_DRIFT')
    runners=[]
    for path in sorted((ROOT/'evidence').glob('regressions-v06-*/runner-receipt.json')):
        value=load(path)
        if value['runtime_lock_sha256']==lockhash:runners.append((path,value))
    need(bool(runners) and runners[-1][1]['status']=='PASS','REGRESSION_RUNNER_INCOMPLETE')
    for run in runners[-1][1]['runs']:
        need(sha(ROOT/run['script'])==run['script_sha256'],'RUNNER_SOURCE_DRIFT')
        need(sha(ROOT/run['log'])==run['log_sha256'],'RUNNER_LOG_DRIFT')
        if 'reused_from_receipt' in run:
            need(sha(ROOT/run['reused_from_receipt'])==run['reused_from_receipt_sha256'],'REUSED_RUNNER_RECEIPT_DRIFT')
    if 'runner_script_sha256' in runners[-1][1]:
        need(sha(ROOT/'tools/run_regressions_v06.py')==runners[-1][1]['runner_script_sha256'],'RUNNER_PROGRAM_DRIFT')
    unit=ROOT/'evidence/unit-tests-v06-final.log';text=unit.read_text(encoding='utf-8-sig');match=re.search(r'Ran (\d+) tests',text)
    need(match and int(match.group(1))>=430 and re.search(r'\nOK\s*$',text),'FINAL_UNIT_TESTS_FAILED')
    unitn=int(match.group(1))
    changespath=ROOT/'evidence/test-expectation-update-v06.json';changes=load(changespath)
    need(changes['status']=='PASS' and changes['modified_test_files']==7,'TEST_EXPECTATIONS_NOT_VERIFIED')
    for item in changes['checks']:need(sha(ROOT/'tests'/item['test'])==item['current_sha256'],'INHERITED_TEST_DRIFT')
    guardpath=ROOT/'evidence/previous-candidates-preservation.json';guard=load(guardpath)
    need(guard['unchanged'] and all(guard['current_manifest_valid'].values()),'PREVIOUS_CANDIDATE_CHANGED')
    origins=ROOT/'evidence/source-provenance.json'
    for item in load(origins)['source_tree_files']:need(sha(Path(item['original']))==item['original_hash'],'ORIGINAL_SOURCE_CHANGED')
    fixture=load(ROOT/'fixtures/survival-v06/fixture-manifest.json')
    need(sha(Path(fixture['frozen_source']))==fixture['frozen_model_file_sha256'],'FROZEN_MODEL_SOURCE_CHANGED')
    audits=[]
    for key in ('association_plan','survival_v04_regression','survival_v05_regression','survival_v06_evaluation'):
        path=suites[key][0].parent/'export-audit.json';value=load(path)
        need(value['status']=='PASS','EXPORT_AUDIT_FAILED:'+key);audits.append(ref(path))
    visualpath=ROOT/'evidence/figure-visual-review-v06.json';visual=load(visualpath)
    need(visual['status']=='PASS' and len(visual['figures'])>=3,'VISUAL_REVIEW_REQUIRED')
    for item in visual['figures']:need(sha(ROOT/item['local_ref'])==item['sha256'],'VISUAL_ARTIFACT_DRIFT')
    comparisonpath=suites['survival_v06_evaluation'][0].parent/'comparison-summary.json'
    comparison=load(comparisonpath)
    need(comparison['status']=='PASS' and comparison['runtime_lock_sha256']==lockhash,'COMPARISON_SUMMARY_INVALID')
    need(comparison['acceptance_receipt_sha256']==sha(suites['survival_v06_evaluation'][0]),'COMPARISON_RECEIPT_DRIFT')
    sidecars=['docs/METHOD-REVIEW-V06.md','evidence/dependency-probe-v06.json']
    need(all(not (ROOT/p).exists() for p in sidecars),'DENIED_SIDECAR_UNEXPECTEDLY_EXISTS')
    execution={'current_runtime_lock_sha256':lockhash,'full_regression_runner':ref(runners[-1][0]),
      'regression_runner_history':[ref(p) for p in sorted((ROOT/'evidence').glob('regressions-v06-*/runner-receipt.json'))],
      'development_smoke_receipts':[ref(p) for p in sorted((ROOT/'evidence').glob('smoke-v06-*/receipt.json'))],
      'acceptance_history':history,
      'auxiliary_documentation_write':{'status':'DENIED_NOT_EXECUTED','targets':[str(ROOT/p) for p in sidecars],
        'reason_reported_by_research_agent':'The research subtask was initially scoped read-only.',
        'raw_approval_rejection_text_available':False,'retried':False,'both_paths_confirmed_absent':True,
        'effect':'Nonessential sidecars absent. Authorized implementation, formula review and acceptance continued.'},
      'temporary_executor_disconnect':{'operation':'read-only sidecar existence check','status':'NOT_EXECUTED',
        'error':'exec_command failed: CreateProcess { message: "Rejected(\\"Failed to create unified exec process: exec-server transport disconnected\\")" }',
        'recovery':'Original Windows executor restored; later read-only checks succeeded; no machine switch.'},
      'development_refinements':['Added explicit UTF-8 BOM model refusal; CRLF/native text byte preservation retained.',
        'Improved graph type size and added explicit CSV scales before final production lock.',
        'First 430-test run had three errors in one inherited generic result fixture for v06: required nullable survival_evaluation was absent. Added that null field for v06 only; original positive/unknown-field assertions retained. Original source and failed log preserved.',
        'First v06 acceptance had three negative-fixture failures: unpaired survival/outcome semantics reached an earlier guard and two model fixtures were overwritten by same-named task fixtures. Fixture construction was corrected without changing production or tolerances; original receipt/source snapshot retained.',
        'Read-only review found two exact probability endpoint counterexamples: separately rounded IPCW AUC masses and Brier/weighted-case masses could produce 1.0000000000000002 and reject valid data. The unique evaluator retained exact rational weights through moment ratios before final float conversion; no clipping, tolerance relaxation or alternative estimator. Counterexamples were added to reference/entry coverage. Earlier lock results remain superseded historical evidence.',
        'The final old-regression runner initially omitted the required --frozen-lock-sha256 argument for the v05 suite. Its startup guard refused before any case execution. Corrected runner invocation and reran that suite; preserved original failure receipt/logs and reused other passed suites only after verifying identical lock, test source and log hashes. No test assertion or production change.',
        'The standalone R no-operating-point output helper also lacked its required second output-path argument in the initial runner and first resumption. Assertions executed but writing its result failed with args[[2]] out of bounds. Corrected only the runner call and reran the helper, requiring both exit zero and hash-bound PASS JSON; preserved both unsuccessful receipts/logs.']}
    executionpath=ROOT/'evidence/execution-history-v06.json';dump(executionpath,execution)
    caps=load(ROOT/'method-capabilities.json')
    need(caps['core_version']==lock['core_version'],'CAPABILITIES_VERSION_MISMATCH')
    for method in caps['methods']:
        mid=method['method_id'];key=('survival_v06_evaluation' if mid=='evaluation.survival.cox.ipcw' else
          'survival_v05_regression' if mid in ('prediction.survival.cox','survival.cox.association') else
          'survival_v04_regression' if mid.startswith('survival.') else 'prediction' if mid.startswith('prediction.') else
          'association_plan' if mid.endswith('.plan') else 'baseline_association')
        method['integration_status']='synthetic_engineering_validated'
        method['validation_evidence']=[{**ref(suites[key][0]),'scope':'Small synthetic engineering acceptance only; clinical review pending'}]
    dump(ROOT/'method-capabilities.json',caps)
    gaps=['Clinical scientific acceptance, real patient/database validation, source independence, transportability and clinical utility',
      'Conditional/informative censoring, survey/clustered evaluation and other censoring estimators',
      'Metric intervals, calibration slope/intercept/tests/smoothing, within-bin KM and integrated survival scores',
      'Competing risks, delayed entry, recurrent events and time-varying covariates',
      'Complete clinical Skill, real database adapters, Mac deployment, license/publication decisions']
    manifest={'core_version':lock['core_version'],'status':'LOCAL_CANDIDATE_NOT_RELEASED','freeze_status':'FROZEN_LOCAL_CANDIDATE',
      'created_at':datetime.now(timezone.utc).isoformat(),'runtime_lock_sha256':lockhash,'production_files_bound':len(lock['code_hashes']),
      'unit_tests':{**ref(unit),'passed':unitn,'failed':0},
      'final_suites':{key:{**ref(path),**receipt['summary']} for key,(path,receipt) in suites.items()},
      'prediction_output_contract_regression':{**ref(op),**orr['summary'],'no_operating_point_helper':ref(noop)},
      'total_acceptance_checks_passed':sum(r['summary']['passed'] for p,r in suites.values())+orr['summary']['passed'],
      'total_acceptance_checks_failed':0,'export_audits':audits,'figure_visual_review':ref(visualpath),
      'previous_candidates_preservation':{**ref(guardpath),**guard},'source_provenance':ref(origins),
      'test_expectation_changes':ref(changespath),'inherited_test_files_checked':len(changes['checks']),
      'numerical_evaluation_owner':'python/clinical_methods/survival_evaluation.py',
      'frozen_risk_model_owner':'python/clinical_methods/survival.py','prior_numerical_owners_and_providers_unchanged':True,
      'survival_evaluation_provider_version':lock['survival_evaluation_provider_version'],
      'frozen_cox_provider_version':lock['cox_prediction_provider_version'],
      'frozen_model_file_sha256':fixture['frozen_model_file_sha256'],'method_ids':[m['method_id'] for m in caps['methods']],
      'test_only':True,'scientific_review':'pending','export_status':'local_only','independent_personnel_review':'PENDING',
      'independent_R_reference':'SURVIVAL_CENSORING_PLUS_SOURCE_FORMULA_METRICS_NOT_SPECIALIST_PACKAGE_VALIDATION',
      'independent_formula_comparison':{**ref(comparisonpath),**comparison},
      'review_entry':'REVIEW-HANDOFF.md','not_tested_or_unimplemented':gaps,'remaining_execution_blockers':[],
      'auxiliary_documentation_writes':execution['auxiliary_documentation_write'],'execution_history':ref(executionpath),
      'installation_or_download_performed':False,'system_changes_performed':False,'publication_or_push_performed':False,
      'license_release_decision':'NOT_MADE','checksum_scope':'Production, tools, tests, docs, synthetic fixtures, metadata and aggregate evidence. Individual run files remain local/private and are bound by run manifests/public artifact hashes.'}
    dump(ROOT/'evidence/final-manifest.json',manifest)
    lines=['# v0_6 local candidate acceptance','',f'Frozen core {lock["core_version"]}. {unitn} unit tests passed; {manifest["total_acceptance_checks_passed"]} acceptance checks passed; 0 failed. All final suites use the same production lock.','']
    lines += [f'- {key}: {r["summary"]["passed"]} passed — [receipt]({p.relative_to(ROOT).as_posix()})' for key,(p,r) in suites.items()]
    lines += [f'- Prediction output correction regression: 10 passed — [receipt]({op.relative_to(ROOT).as_posix()})','',
      'Four export audits and representative visual inspections are recorded. Old numerical owners and v0_1–v0_5 candidate manifests remain unchanged. Formal PH/Cox prediction and older baseline/association/Ridge coverage are retained.',
      '', 'Reference evidence is R survival censoring construction plus independent source-formula metrics. Unavailable specialist metric packages were not installed or claimed as validation. Personnel-independent review and all clinical scientific review remain pending.',
      '', '[Machine evidence](evidence/final-manifest.json) · [Independent review](REVIEW-HANDOFF.md) · [Gaps](GAPS.md)',
      '', 'The read-only method-research subtask was denied two auxiliary sidecar targets; neither file was created or retried. Main implementation and required acceptance are complete; exact targets and reported reason are in execution-history-v06.json.','']
    (ROOT/'ACCEPTANCE.md').write_text('\n'.join(lines),encoding='utf-8')
    (ROOT/'DEVELOPMENT-STATUS.md').write_text('# v0_6 status\n\nFROZEN_LOCAL_CANDIDATE. See ACCEPTANCE.md and evidence/final-manifest.json. No further edits in this directory; use a new isolated development copy for subsequent work. Not released; clinical review pending.\n',encoding='utf-8')
    files=set()
    for folder in ('src','python','schemas','tools','tests','docs','fixtures'):
        files.update(p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files.update(p for p in ROOT.iterdir() if p.is_file() and p.name!='CANDIDATE-SHA256SUMS.txt')
    files.update(p for p in (ROOT/'evidence').iterdir() if p.is_file())
    files.update(path for path,receipt in suites.values());files.update(ROOT/item['local_ref'] for item in audits);files.add(op)
    files.update(path for path in runners[-1][0].parent.iterdir() if path.is_file())
    files.update(ROOT/item['local_ref'] for item in history)
    files.update(ROOT/item['local_ref'] for item in execution['development_smoke_receipts'])
    for directory in (ROOT/'evidence').iterdir():
        if not directory.is_dir():continue
        files.update(p for p in directory.iterdir() if p.is_file() and p.name in ('harness-repair-note.json','interruption-note.json','superseded-note.json','superseded-receipt.json','receipt.json','comparison-summary.json','preflight-receipt.json','superseded-by-endpoint-defect.json','visual-review-acceptance.json'))
        if directory.name.startswith('regressions-v06-'):
            files.update(p for p in directory.iterdir() if p.is_file())
        snapshot=directory/'source-snapshot'
        if snapshot.is_dir():files.update(p for p in snapshot.rglob('*') if p.is_file())
    (ROOT/'CANDIDATE-SHA256SUMS.txt').write_text('\n'.join(sha(p)+'  '+p.relative_to(ROOT).as_posix() for p in sorted(files))+'\n',encoding='utf-8')
    print(json.dumps({'status':manifest['freeze_status'],'checksum_files':len(files),'production_files':len(lock['code_hashes']),
      'unit_tests':unitn,'acceptance_passed':manifest['total_acceptance_checks_passed'],'acceptance_failed':0,'runtime_lock_sha256':lockhash}))
if __name__=='__main__':main()
