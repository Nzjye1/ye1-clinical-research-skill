"""Four actual entry operations on a fixed lock, using synthetic rows only."""
import hashlib,importlib.util,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from clinical_methods import contracts as c
s=importlib.util.spec_from_file_location('v09_smoke_fixture',ROOT/'tools/make_interpretation_v09_fixtures.py')
f=importlib.util.module_from_spec(s);s.loader.exec_module(f)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def main():
    lock=load(ROOT/'runtime-lock.json');lockhash=sha(ROOT/'runtime-lock.json')
    assert lock['core_version']=='0.9.0-candidate1'
    assert all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())
    suite=ROOT/'evidence'/('smoke-v09-'+time.strftime('%Y%m%d-%H%M%S'));suite.mkdir(exist_ok=False)
    rows=[]
    for family,penalty,db in [('gaussian','lasso','mimic'),('binomial','elasticnet','eicu')]:
        trainout=suite/(family+'-train');modelpath=trainout/'private/penalized-model.json';explainpath=trainout/'private/linear-explainer.json'
        for operation in ('train','interpret'):
            out=trainout if operation=='train' else suite/(family+'-interpret')
            if operation=='train':
                path=ROOT/'fixtures/interpretation-v09'/f'development-{family}-{db}.csv'
                task=f.training_task(c,path,out,family,penalty,db)
            else:
                if not modelpath.exists() or not explainpath.exists():continue
                path=ROOT/'fixtures/interpretation-v09'/f'external-{family}-{db}.csv'
                model=load(modelpath)
                opts=f.interpretation_options(modelpath,explainpath,model['model']['spec'],model['method_id'])
                task=f.interpretation_task(c,path,out,opts,db)
            tp=suite/(out.name+'.json');dump(tp,task)
            proc=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tools/run_core.R'),str(tp),str(out)],cwd=ROOT,
              env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'},capture_output=True,timeout=180)
            log=suite/(out.name+'.log');log.write_bytes(proc.stdout+b'\n'+proc.stderr)
            result=load(out/'result.json') if (out/'result.json').exists() else {}
            row={'case':out.name,'returncode':proc.returncode,'execution_status':result.get('execution_status'),
              'reason_code':result.get('reason_code'),'tables':len(result.get('tables',[])),'figures':len(result.get('figures',[])),
              'result_ref':(out/'result.json').relative_to(ROOT).as_posix(),'log_ref':log.relative_to(ROOT).as_posix()}
            row['status']='PASS' if proc.returncode==0 and result.get('execution_status')=='complete' and (result.get('interpretation') if operation=='interpret' else explainpath.exists()) else 'FAIL'
            rows.append(row);print(json.dumps(row),flush=True)
    unchanged=sha(ROOT/'runtime-lock.json')==lockhash and all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())
    value={'scope':'Four-operation development smoke, not full acceptance','runtime_lock_sha256':lockhash,'source_sha256':{'tools/smoke_v09.py':sha(Path(__file__))},
      'production_unchanged':unchanged,'checks':rows,'summary':{'passed':sum(x['status']=='PASS' for x in rows),'failed':sum(x['status']!='PASS' for x in rows)}}
    dump(suite/'receipt.json',value);print(json.dumps({'receipt':str(suite/'receipt.json'),'summary':value['summary']}),flush=True)
    return int(not unchanged or len(rows)!=4 or value['summary']['failed']>0)
if __name__=='__main__':raise SystemExit(main())
