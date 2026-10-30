"""Two small real-entry checks before complete acceptance; never overwrite runs."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from clinical_methods import contracts as c
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def dump(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def main():
    suite=ROOT/'evidence'/('smoke-v05-'+time.strftime('%Y%m%d-%H%M%S'));suite.mkdir(exist_ok=False)
    lock=load(ROOT/'runtime-lock.json');checks=[]
    for name in ['mimic-train','mimic-ph']:
        task=load(ROOT/'fixtures/survival-v05'/f'{name}.json');out=suite/name
        task['execution']['output_dir']=str(out);c.seal_task(task,str(ROOT));path=suite/f'{name}.json';dump(path,task)
        proc=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tools/run_core.R'),str(path),str(out)],cwd=ROOT,
          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
        (suite/f'{name}.log').write_text(proc.stdout+'\n'+proc.stderr,encoding='utf-8')
        result=load(out/'result.json') if (out/'result.json').exists() else {}
        row={'name':name,'returncode':proc.returncode,'execution_status':result.get('execution_status'),'reason_code':result.get('reason_code')}
        row['status']='PASS' if proc.returncode==0 and row['execution_status']=='complete' else 'FAIL';checks.append(row)
    receipt={'scope':'Small entry smoke, not full acceptance','runtime_lock_sha256':hashlib.sha256((ROOT/'runtime-lock.json').read_bytes()).hexdigest(),'checks':checks}
    dump(suite/'receipt.json',receipt);print(json.dumps({'receipt':str(suite/'receipt.json'),'checks':checks}))
    return int(any(x['status']!='PASS' for x in checks))
if __name__=='__main__':raise SystemExit(main())
