"""Repeat the P1 checks into a NEW output directory inside this snapshot."""
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
    unitlog=ROOT/'evidence/unit-tests-v02-final.log'
    units=[{'suite':'separate complete v02 unit suite', 'passed':'\nOK' in unitlog.read_text(encoding='utf-8-sig'), 'log':str(unitlog)}]
    receipt={'status':'PASS' if all(r['passed'] for r in records) and all(u['passed'] for u in units) else 'FAIL','test_only':True,'scientific_review':'pending','export_status':'local_only','runtime_lock_sha256':sha(ROOT/'runtime-lock.json'),'cases':records,'unit_suites':units,'not_tested':['prediction final freeze','real databases','clinical validity','Mac','full independent R numerical reference rerun']}
    write(output/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'receipt':str(output/'receipt.json')},ensure_ascii=False))
    return 0 if receipt['status']=='PASS' else 1
if __name__=='__main__':sys.exit(main())
