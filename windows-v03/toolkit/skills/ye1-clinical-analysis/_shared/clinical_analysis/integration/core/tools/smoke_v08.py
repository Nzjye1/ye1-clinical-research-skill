"""Six source-bound real-entry development smoke operations, no overwrites."""
import copy,hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from clinical_methods import contracts as c
spec=importlib.util.spec_from_file_location('v08_smoke_fixture',ROOT/'tools/make_penalized_v08_fixtures.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def dump(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    lock=load(ROOT/'runtime-lock.json');lockhash=sha(ROOT/'runtime-lock.json')
    assert lock['core_version']=='0.8.0-candidate1'
    assert all(sha(ROOT/path)==digest for path,digest in lock['code_hashes'].items())
    suite=ROOT/'evidence'/('smoke-v08-'+time.strftime('%Y%m%d-%H%M%S'));suite.mkdir(exist_ok=False)
    checks=[]
    for family,penalty,db in [('gaussian','lasso','mimic'),('binomial','elasticnet','eicu')]:
        model=None
        for operation in ('train','evaluate','infer'):
            if operation!='train' and model is None:continue
            label=f'{family}-{operation}';rows=f.build_rows(family,operation!='train')
            if operation=='infer':
                for row in rows:row['outcome']=''
            path=suite/f'{label}.csv';f.write_csv(path,f.mapped(rows,family) if db=='eicu' else rows)
            options=f.options(family,penalty,operation=operation,model_ref=model)
            out=suite/label;task=f.prepare_task(c,path,out,family,penalty,db,options)
            taskpath=suite/f'{label}.json';dump(taskpath,task)
            proc=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tools/run_core.R'),str(taskpath),str(out)],cwd=ROOT,
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'},capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
            (suite/f'{label}.log').write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
            result=load(out/'result.json') if (out/'result.json').is_file() else {}
            row={'case':label,'returncode':proc.returncode,'execution_status':result.get('execution_status'),
                'reason_code':result.get('reason_code'),'tables':len(result.get('tables',[])),'figures':len(result.get('figures',[])),
                'result_ref':str((out/'result.json').relative_to(ROOT))}
            row['status']='PASS' if proc.returncode==0 and result.get('penalized_prediction') and result['execution_status']=='complete' else 'FAIL'
            if operation=='train' and row['status']=='PASS':
                modelpath=out/'private/penalized-model.json';model={'local_ref':str(modelpath),'content_hash':sha(modelpath)}
            checks.append(row);print(json.dumps(row),flush=True)
    unchanged=sha(ROOT/'runtime-lock.json')==lockhash and all(sha(ROOT/path)==digest for path,digest in lock['code_hashes'].items())
    value={'scope':'Small development smoke only, not full acceptance','runtime_lock_sha256':lockhash,
        'production_unchanged':unchanged,'checks':checks,'summary':{'passed':sum(x['status']=='PASS' for x in checks),'failed':sum(x['status']!='PASS' for x in checks)}}
    dump(suite/'receipt.json',value);print(json.dumps({'receipt':str(suite/'receipt.json'),'summary':value['summary']}))
    return int(not unchanged or len(checks)!=6 or value['summary']['failed']>0)
if __name__=='__main__':raise SystemExit(main())
