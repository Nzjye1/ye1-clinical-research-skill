"""Two actual public-entry calls before broad acceptance; does not freeze delivery."""
import importlib.util,json,os,subprocess,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    lock=load(ROOT/'runtime-lock.json');lockhash=sha(ROOT/'runtime-lock.json')
    directory=ROOT/'evidence'/('smoke-v10-'+time.strftime('%Y%m%d-%H%M%S'));directory.mkdir()
    f=module('fixture_v10',ROOT/'tools/make_cox_penalized_v10_fixtures.py');c=module('contract_v10',ROOT/'python/clinical_methods/contracts.py')
    rows=f.build_rows();source=directory/'development.csv';f.write_csv(source,rows)
    runs=[]
    for operation in ('train','infer'):
        out=directory/operation
        if operation=='train':opts=f.options()
        else:
            source=directory/'external.csv';f.write_csv(source,f.build_rows(True));model=directory/'train/private/cox-penalized-model.json'
            if not model.exists():break
            opts=f.options(operation='infer',model_ref={'local_ref':str(model),'content_hash':sha(model)})
        task=f.prepare_task(c,source,out,opts=opts);taskpath=directory/(operation+'.json');f.dump(taskpath,task)
        proc=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tools/run_core.R'),str(taskpath),str(out)],cwd=ROOT,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'},capture_output=True,timeout=90)
        log=directory/(operation+'.log');log.write_bytes(proc.stdout+b'\n'+proc.stderr)
        result=load(out/'result.json') if (out/'result.json').exists() else {}
        schema_ok=False;schema_error=None
        try:c.validate_schema(result,load(ROOT/'schemas/result.schema.json'));schema_ok=True
        except Exception as exc:schema_error=str(exc)
        runs.append({'operation':operation,'returncode':proc.returncode,'execution_status':result.get('execution_status'),'reason':result.get('reason_code'),
          'schema_ok':schema_ok,'schema_error':schema_error,'result_ref':str(out/'result.json'),'log_ref':str(log),'log_sha256':sha(log)})
    unchanged=sha(ROOT/'runtime-lock.json')==lockhash and all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())
    ok=len(runs)==2 and unchanged and all(x['returncode']==0 and x['execution_status']=='complete' and x['schema_ok'] for x in runs)
    receipt={'status':'PASS' if ok else 'FAIL','scope':'Two-entry smoke only, not final acceptance','runtime_lock_sha256':lockhash,'production_unchanged':unchanged,'runs':runs}
    f.dump(directory/'receipt.json',receipt);print(json.dumps({'receipt':str(directory/'receipt.json'),**receipt}),flush=True)
    return int(not ok)
if __name__=='__main__':raise SystemExit(main())
