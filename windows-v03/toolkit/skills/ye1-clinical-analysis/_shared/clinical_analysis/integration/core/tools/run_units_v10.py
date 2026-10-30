"""Run inherited and v10 units against one immutable production/test snapshot."""
import hashlib,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    lockpath=ROOT/'runtime-lock.json';lock=json.loads(lockpath.read_text(encoding='utf-8'));lockhash=sha(lockpath)
    assert lock['core_version']=='0.10.0-candidate1'
    assert all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'tests').glob('*')) if p.is_file()}
    directory=ROOT/'evidence'/('units-v10-'+time.strftime('%Y%m%d-%H%M%S'));directory.mkdir(exist_ok=False)
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'}
    proc=subprocess.run([lock['python'],'-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v'],cwd=ROOT,env=env,capture_output=True,timeout=900)
    log=directory/'unit-tests.log';log.write_bytes(proc.stdout+b'\n'+proc.stderr)
    output=log.read_text(encoding='utf-8',errors='replace');found=re.search(r'Ran (\d+) tests',output)
    rvalues=[]
    for script,prefix,minimum in [('test_interpretation_v09_provider.R','INTERPRETATION_PROVIDER_UNIT ',22),('cox_penalized_v10_provider_unit.R','COX_PENALIZED_PROVIDER_UNIT ',27),('cox_penalized_v10_projection_unit.R','COX_PENALIZED_PROJECTION_UNIT ',41)]:
        command=[lock['rscript'],'--vanilla',str(ROOT/'tests'/script)]
        if 'projection' in script:
            projection=directory/'projection';projection.mkdir();command.append(str(projection))
        rproc=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=240)
        rlog=directory/(script+'.log');rlog.write_bytes(rproc.stdout+b'\n'+rproc.stderr)
        rlines=[s.removeprefix(prefix) for s in rlog.read_text(encoding='utf-8',errors='replace').splitlines() if s.startswith(prefix)]
        value=json.loads(rlines[-1]) if rlines else {'passed':0,'failed':1,'checks':[]}
        value.update(script='tests/'+script,returncode=rproc.returncode,log_ref=rlog.relative_to(ROOT).as_posix(),log_sha256=sha(rlog),minimum_expected=minimum)
        rvalues.append(value)
    unchanged=sha(lockpath)==lockhash and all(sha(ROOT/p)==h for p,h in {**lock['code_hashes'],**sources}.items())
    ok=proc.returncode==0 and bool(found) and bool(re.search(r'\nOK\s*$',output)) and unchanged and all(x['returncode']==0 and x['failed']==0 and x['passed']>=x['minimum_expected'] for x in rvalues)
    receipt={'status':'PASS' if ok else 'FAIL','returncode':proc.returncode,'runtime_lock_sha256':lockhash,
      'passed':int(found.group(1))+sum(x['passed'] for x in rvalues) if ok else None,'tests_reported':int(found.group(1)) if found else None,
      'python_passed':int(found.group(1)) if proc.returncode==0 and found else None,'r_provider_runs':rvalues,
      'source_sha256':sources,'production_and_tests_unchanged':unchanged,
      'log_ref':log.relative_to(ROOT).as_posix(),'log_sha256':sha(log),'runner_sha256':sha(Path(__file__))}
    path=directory/'unit-receipt.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'passed':receipt['passed'],'receipt':str(path)}),flush=True)
    return int(not ok)
if __name__=='__main__':raise SystemExit(main())
