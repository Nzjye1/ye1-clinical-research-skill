"""Two bounded real-entry smoke runs before full acceptance; no overwrites."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from clinical_methods import contracts as c
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
    suite=ROOT/'evidence'/('smoke-v06-'+time.strftime('%Y%m%d-%H%M%S'));suite.mkdir(exist_ok=False)
    lock=load(ROOT/'runtime-lock.json');checks=[]
    for db in ('mimic','eicu'):
        task=load(ROOT/'fixtures/survival-v06'/f'{db}-evaluation.json');out=suite/db
        task['execution']['output_dir']=str(out);c.seal_task(task,str(ROOT));path=suite/f'{db}.json';dump(path,task)
        proc=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tools/run_core.R'),str(path),str(out)],cwd=ROOT,
          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        (suite/f'{db}.log').write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
        r=load(out/'result.json') if (out/'result.json').exists() else {}
        row={'adapter':db,'returncode':proc.returncode,'execution_status':r.get('execution_status'),'reason_code':r.get('reason_code')}
        row['status']='PASS' if proc.returncode==0 and r.get('survival_evaluation') and r['execution_status'] in ('complete','partial') and len(r['figures'])==5 else 'FAIL'
        checks.append(row)
    receipt={'scope':'Small real-entry smoke only','runtime_lock_sha256':hashlib.sha256((ROOT/'runtime-lock.json').read_bytes()).hexdigest(),'checks':checks}
    dump(suite/'receipt.json',receipt);print(json.dumps({'receipt':str(suite/'receipt.json'),'checks':checks}))
    return int(any(x['status']!='PASS' for x in checks))
if __name__=='__main__':raise SystemExit(main())
