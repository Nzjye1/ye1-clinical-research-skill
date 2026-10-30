"""Generate the one-off review-only P1 snapshot from frozen v0.1; never overwrite."""
from pathlib import Path
import difflib, hashlib, importlib.util, json, os, shutil, subprocess, sys

from clinical_test_paths import configure_process, configured_reference, runtime_path
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'clinical-analysis-core-v0_1-dev-20261023'
REVIEW = ROOT.parent / 'clinical-analysis-core-v0_1-independent-acceptance-20261023'
DEST = ROOT / 'review-snapshots/p1-fixes-20261023'
PY = str(runtime_path("python"))

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def inventory(root): return {p.relative_to(root).as_posix():sha(p) for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}

RUNNER = r'''"""Repeat the P1 checks into a NEW output directory inside this snapshot."""
from pathlib import Path
import copy,csv,hashlib,importlib.util,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    lock=read(ROOT/'runtime-lock.json')
    for rel,want in lock['code_hashes'].items(): assert sha(ROOT/rel)==want,rel
    spec=importlib.util.spec_from_file_location('snapshot_contracts',ROOT/'python/clinical_methods/contracts.py')
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    output=ROOT/'outputs'/('p1-retest-'+time.strftime('%Y%m%dT%H%M%S')+'-'+str(os.getpid()))
    output.mkdir(parents=True,exist_ok=False)
    records=[]
    for case in ['id_typed_exposure_no_baseline','malformed_id_quoted_csv','baseline_all_denominator','baseline_nonmissing_denominator','mimic_linear','mimic_logistic','mimic_table1']:
        task=read(ROOT/'fixtures/p1'/f'{case}.json')
        out=output/case;task['execution']['output_dir']=str(out)
        c.seal_task(task,ROOT)
        path=output/(case+'.json');write(path,task)
        run=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tools/run_core.R'),str(path),str(out)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        (output/(case+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
        result=read(out/'result.json') if (out/'result.json').exists() else {}
        validation=read(out/'private/result-validation.json') if (out/'private/result-validation.json').exists() else {}
        checks={'entry_returncode_zero':run.returncode==0,'result_validation_ok':validation.get('ok') is True}
        code={'id_typed_exposure_no_baseline':'ID_MODEL_FIELD_FORBIDDEN','malformed_id_quoted_csv':'CSV_ENCODING_OR_FORMAT_INVALID'}.get(case)
        raw=Path(task['views'][0]['local_ref'])
        checks['original_raw_hash_bound']=sha(raw)==task['views'][0]['content_hash']==task['sources'][0]['source_fingerprint']
        if code:
            checks.update(exact_blocked=result.get('execution_status')=='blocked',exact_reason=result.get('reason_code')==code,no_estimates=result.get('estimates')==[],no_provider_request=not (out/'private/provider-request.json').exists())
        else:
            checks.update(complete=result.get('execution_status')=='complete',no_reason=result.get('reason_code') is None)
            if case=='mimic_linear': checks['model_n_108']=result.get('counts',{}).get('model_n')==108
            if case=='mimic_logistic': checks['model_n_109']=result.get('counts',{}).get('model_n')==109
        denominator_evidence=[]
        if case.startswith('baseline_'):
            policy=task['analysis']['baseline']['categorical_denominator']
            checks['both_table_captions_options']=len(result.get('tables',[]))==2 and all('categorical denominator policy='+policy+';' in a['caption'] and a['options']=={'categorical_denominator':policy,'group_missing_policy':'exclude'} for a in result.get('tables',[]))
            with (out/'tables/table1_statistics.csv').open(encoding='utf-8-sig',newline='') as f: stats=list(csv.DictReader(f))
            # The inherited independent-review fixture has two missing binary values.
            denominator_evidence=[r for r in stats if r.get('variable')=='binary' and r.get('group')=='overall' and r.get('level') in ['0','1']]
            expected=120 if policy=='all' else 118
            checks['numeric_denominator_expected']=len(denominator_evidence)==2 and all(float(r['denominator'])==expected for r in denominator_evidence)
            checks['category_counts_56_62']=sorted(float(r['n']) for r in denominator_evidence)==[56,62]
            checks['category_proportions_correct']=len(denominator_evidence)==2 and all(abs(float(r['proportion'])-float(r['n'])/expected)<=1e-8 for r in denominator_evidence)
        records.append({'case':case,'passed':all(checks.values()),'checks':checks,'execution_status':result.get('execution_status'),'reason_code':result.get('reason_code'),'result':str(out/'result.json'),'raw_sha256':sha(raw),'categorical_denominator_evidence':denominator_evidence})
    units=[]
    for name in ['test_contracts.py','test_provider.py']:
        p=subprocess.run([lock['python'],'-B',str(ROOT/'tests'/name)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        log=output/(name+'.log');log.write_text(p.stdout+p.stderr,encoding='utf-8')
        units.append({'suite':name,'passed':p.returncode==0,'log':str(log)})
    receipt={'status':'PASS' if all(r['passed'] for r in records) and all(u['passed'] for u in units) else 'FAIL','test_only':True,'scientific_review':'pending','export_status':'local_only','runtime_lock_sha256':sha(ROOT/'runtime-lock.json'),'cases':records,'unit_suites':units,'not_tested':['prediction final freeze','real databases','clinical validity','Mac','full independent R numerical reference rerun']}
    write(output/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'receipt':str(output/'receipt.json')},ensure_ascii=False))
    return 0 if receipt['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
'''

def main():
    before=inventory(SOURCE)
    oldlock=read(SOURCE/'runtime-lock.json')
    assert all(sha(SOURCE/k)==v for k,v in oldlock['code_hashes'].items())
    mirror=next(p for p in REVIEW.iterdir() if p.is_dir() and (p/'outputs/id_typed_exposure_no_baseline.json').exists())
    DEST.mkdir(parents=True,exist_ok=False)
    for folder in ('src','python','schemas','tools','tests'):
        shutil.copytree(SOURCE/folder,DEST/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (DEST/'evidence').mkdir();(DEST/'fixtures/p1').mkdir(parents=True)
    shutil.copyfile(SOURCE/'evidence/runtime-probe.json',DEST/'evidence/runtime-probe.json')
    contracts=DEST/'python/clinical_methods/contracts.py'
    data=contracts.read_bytes()
    old=b'csv.DictReader(io.StringIO(text, newline=""))'
    assert data.count(old)==1
    data=data.replace(old,b'csv.DictReader(io.StringIO(text, newline=""), strict=True)')
    old=b'        need(all(x in variables for x in used), "MODEL_FIELD_MISSING", stage)'
    assert data.count(old)==1
    nl=b'\r\n' if b'\r\n' in data else b'\n'
    data=data.replace(old,old+nl+b'        need(all(variables[x]["dtype"] != "id" for x in used[1:]), "ID_MODEL_FIELD_FORBIDDEN", stage)')
    contracts.write_bytes(data)
    r=DEST/'src/clinanalysis/R/clinical_common.R';data=r.read_bytes()
    old=b'        result$tables <- list(common_artifact("table1-formatted","table",p1,result,list(),result$counts$model_n,"per variable","SYNTHETIC TEST ONLY: baseline; nonmissing categorical denominators."),'
    old2=b'          common_artifact("table1-statistics","table",p2,result,list(),result$counts$model_n,"per variable","Full-precision baseline statistics; variable missingness and denominators retained."))'
    nl=b'\r\n' if b'\r\n' in data else b'\n'
    old=old+nl+old2
    assert data.count(old)==1
    new='''        denominator_policy <- tb$categorical_denominator
        result$tables <- list(common_artifact("table1-formatted","table",p1,result,list(),result$counts$model_n,"per variable",paste0("SYNTHETIC TEST ONLY: baseline; categorical denominator policy=",denominator_policy,"; rows missing the group are excluded.")),
          common_artifact("table1-statistics","table",p2,result,list(),result$counts$model_n,"per variable",paste0("Full-precision baseline statistics; categorical denominator policy=",denominator_policy,"; variable missingness and denominators retained.")))
        for(i in seq_along(result$tables)) result$tables[[i]]$options <- list(categorical_denominator=denominator_policy,group_missing_policy="exclude")'''.encode().replace(b'\n',nl)
    r.write_bytes(data.replace(old,new))
    (DEST/'tools/retest_p1.py').write_text(RUNNER,encoding='utf-8')
    spec=importlib.util.spec_from_file_location('snapshot_contracts',contracts)
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    tasks={name:read(mirror/'outputs'/f'{name}.json') for name in ['id_typed_exposure_no_baseline','malformed_id_quoted_csv','baseline_all_denominator']}
    tasks['baseline_nonmissing_denominator']=json.loads(json.dumps(tasks['baseline_all_denominator']))
    tasks['baseline_nonmissing_denominator']['analysis']['baseline']['categorical_denominator']='nonmissing'
    for name in ['mimic_linear','mimic_logistic','mimic_table1']: tasks[name]=read(SOURCE/'fixtures'/f'{name}.json')
    copied=[]
    for name,task in tasks.items():
        for view in task['views']:
            raw=Path(view['local_ref'])
            assert raw.is_relative_to(SOURCE) or raw.is_relative_to(mirror)
            newraw=DEST/'fixtures/p1'/raw.name
            if newraw.exists(): assert sha(newraw)==sha(raw)
            else: shutil.copyfile(raw,newraw)
            copied.append({'source':str(raw),'snapshot':newraw.relative_to(DEST).as_posix(),'sha256':sha(raw)})
            view['local_ref']=str(newraw)
        task['execution']['output_dir']=str(DEST/'outputs'/name)
        c.seal_task(task,DEST);write(DEST/'fixtures/p1'/f'{name}.json',task)
    freeze=subprocess.run([PY,'-B',str(DEST/'tools/freeze_core.py')],cwd=DEST,capture_output=True,text=True,timeout=60,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    (DEST/'evidence/freeze.log').write_text(freeze.stdout+freeze.stderr,encoding='utf-8');assert freeze.returncode==0
    lock=read(DEST/'runtime-lock.json')
    lock['status']='GENERATED_REVIEW_ONLY_P1_SNAPSHOT_NOT_RELEASED'
    lock['code_hashes']={p.relative_to(DEST).as_posix():sha(p) for folder in ('src','python','schemas','tools','tests') for p in sorted((DEST/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    write(DEST/'runtime-lock.json',lock)
    changed=[];diff=[]
    for rel in lock['code_hashes']:
        if (SOURCE/rel).exists() and sha(SOURCE/rel)!=sha(DEST/rel):
            changed.append(rel)
            diff.extend(difflib.unified_diff((SOURCE/rel).read_text(encoding='utf-8-sig').splitlines(True),(DEST/rel).read_text(encoding='utf-8-sig').splitlines(True),fromfile='frozen-v01/'+rel,tofile='p1-snapshot/'+rel))
    assert set(changed)=={'python/clinical_methods/contracts.py','src/clinanalysis/R/clinical_common.R'}
    (DEST/'evidence/three-fixes.patch').write_text(''.join(diff),encoding='utf-8')
    write(DEST/'evidence/source-integrity.json',{'source':str(SOURCE),'before':before,'all_source_files_unchanged':before==inventory(SOURCE),'numerical_sources_byte_identical':all(sha(SOURCE/rel)==sha(DEST/rel) for rel in ['python/clinical_methods/association.py','src/clinanalysis/R/table1.R']),'changed_source_files':changed,'fixture_sources':copied})
    print(str(DEST),flush=True)

if __name__=='__main__':main()
