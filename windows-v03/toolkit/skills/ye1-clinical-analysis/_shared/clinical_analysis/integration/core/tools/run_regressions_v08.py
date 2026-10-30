"""At most two independent old regression suites on a fixed production lock."""
import argparse,hashlib,json,os,subprocess,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume-from',type=Path)
    parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=parser.parse_args()
    lock=load(ROOT/'runtime-lock.json');lockhash=sha(ROOT/'runtime-lock.json')
    directory=ROOT/'evidence'/('regressions-v08-'+time.strftime('%Y%m%d-%H%M%S'));directory.mkdir(exist_ok=False)
    scripts=['test_acceptance.py','test_association_plan_acceptance.py','test_prediction_acceptance.py',
      'test_survival_acceptance.py','test_survival_v05_acceptance.py','test_prediction_output_contract.py','test_survival_v06_acceptance.py','test_psm_v07_acceptance.py']
    results=[];reused={};previous=None
    if args.resume_from:
        path=args.resume_from.resolve()
        assert path.is_relative_to(ROOT/'evidence') and path.name in ('runner-receipt.json','progress-receipt.json')
        previous=load(path)
        assert previous['runtime_lock_sha256']==lockhash and previous['production_unchanged']
        observed={Path(x['script']).name for x in previous['runs']}
        assert len(observed)==len(previous['runs']) and observed<=set(scripts)
        if previous.get('status')=='PARTIAL_PROGRESS':
            assert set(previous['pending_scripts'])==set(scripts)-observed
        else:assert observed==set(scripts)
        for row in previous['runs']:
            assert sha(ROOT/row['script'])==row['script_sha256']
            assert sha(ROOT/row['log'])==row['log_sha256']
            if row['status']=='PASS' and row['returncode']==0:
                reused[Path(row['script']).name]={**row,'reused_from_receipt':path.relative_to(ROOT).as_posix(),
                  'reused_from_receipt_sha256':sha(path)}
        previous_ref={'local_ref':path.relative_to(ROOT).as_posix(),'sha256':sha(path)}
    def save_progress():
        observed={Path(row['script']).name for row in results}
        progress={'status':'PARTIAL_PROGRESS','runtime_lock_sha256':lockhash,'runs':results,
          'pending_scripts':[name for name in scripts if name not in observed],
          'no_operating_point':{'status':'NOT_RUN'},'runner_script_sha256':sha(Path(__file__)),
          'resumed_from':previous_ref if previous else None,
          'production_unchanged':sha(ROOT/'runtime-lock.json')==lockhash and all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())}
        target=directory/'progress-receipt.json';temporary=directory/'progress-receipt.pending'
        temporary.write_text(json.dumps(progress,indent=2)+'\n',encoding='utf-8')
        temporary.replace(target)
    def execute(name):
        assert sha(ROOT/'runtime-lock.json')==lockhash
        assert all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())
        started=datetime.now(timezone.utc).isoformat();sourcehash=sha(ROOT/'tests'/name)
        print('REGRESSION_STARTED',name,flush=True)
        command=[lock['python'],'-B',str(ROOT/'tests'/name)]
        if name in ('test_survival_v05_acceptance.py','test_survival_v06_acceptance.py','test_psm_v07_acceptance.py'):command+=['--frozen-lock-sha256',lockhash]
        proc=subprocess.run(command,cwd=ROOT,
          env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,timeout=900)
        text=(proc.stdout+b'\n'+proc.stderr).decode('utf-8',errors='replace')
        path=directory/(name+'.log');path.write_text(text,encoding='utf-8')
        assert sha(ROOT/'tests'/name)==sourcehash
        row={'script':'tests/'+name,'script_sha256':sourcehash,'started_at':started,
          'command':command,
          'returncode':proc.returncode,'status':'PASS' if proc.returncode==0 else 'FAIL',
          'log':path.relative_to(ROOT).as_posix(),'log_sha256':sha(path)}
        print(json.dumps(row),flush=True)
        return row
    # Each suite uses separate fixture namespaces and unique output directories;
    # numerical libraries and production sources remain read-only. Bound IO.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results.extend(reused.values())
        save_progress()
        pending=[pool.submit(execute,name) for name in scripts if name not in reused]
        for future in as_completed(pending):
            results.append(future.result());save_progress()
    results.sort(key=lambda row:scripts.index(Path(row['script']).name))
    if previous and previous['no_operating_point']['status']=='PASS':
        no_op=previous['no_operating_point']
        assert sha(ROOT/no_op['log'])==no_op['log_sha256']
    else:
        result_path=directory/'prediction-no-operating-point-result.json'
        proc=subprocess.run([lock['rscript'],'--vanilla',str(ROOT/'tests/prediction_output_no_operating_point.R'),str(ROOT),str(result_path)],cwd=ROOT,
          capture_output=True,timeout=90)
        path=directory/'prediction-no-operating-point.log';path.write_bytes(proc.stdout+b'\n'+proc.stderr)
        success=proc.returncode==0 and result_path.is_file() and load(result_path)['status']=='PASS'
        no_op={'status':'PASS' if success else 'FAIL','returncode':proc.returncode,
          'script_sha256':sha(ROOT/'tests/prediction_output_no_operating_point.R'),
          'result_ref':result_path.relative_to(ROOT).as_posix() if result_path.is_file() else None,
          'result_sha256':sha(result_path) if result_path.is_file() else None,
          'log':path.relative_to(ROOT).as_posix(),'log_sha256':sha(path)}
    (ROOT/'evidence/prediction-output-no-op-v08.json').write_text(json.dumps(no_op,indent=2)+'\n',encoding='utf-8')
    receipt={'runtime_lock_sha256':lockhash,'runs':results,'no_operating_point':no_op,
      'runner_script_sha256':sha(Path(__file__)),
      'resumed_from':previous_ref if previous else None,
      'production_unchanged':sha(ROOT/'runtime-lock.json')==lockhash and all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())}
    receipt['status']='PASS' if receipt['production_unchanged'] and all(x['status']=='PASS' for x in results) and no_op['status']=='PASS' else 'FAIL'
    path=directory/'runner-receipt.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'receipt':str(path),'status':receipt['status']}),flush=True)
    return int(receipt['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
