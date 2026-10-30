"""Run all unit tests with source and production hashes fixed for the run."""
import hashlib,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    lockpath=ROOT/'runtime-lock.json';lock=json.loads(lockpath.read_text(encoding='utf-8'));lockhash=sha(lockpath)
    assert lock['core_version']=='0.8.0-candidate1'
    assert all(sha(ROOT/p)==h for p,h in lock['code_hashes'].items())
    sources={p.relative_to(ROOT).as_posix():sha(p) for p in sorted((ROOT/'tests').glob('*')) if p.is_file()}
    directory=ROOT/'evidence'/('units-v08-'+time.strftime('%Y%m%d-%H%M%S'));directory.mkdir(exist_ok=False)
    proc=subprocess.run([lock['python'],'-B','-m','unittest','discover','-s','tests','-p','test_*.py','-v'],cwd=ROOT,
      env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONIOENCODING':'utf-8'},capture_output=True,timeout=600)
    log=directory/'unit-tests.log';log.write_bytes(proc.stdout+b'\n'+proc.stderr)
    output=log.read_text(encoding='utf-8',errors='replace');found=re.search(r'Ran (\d+) tests',output)
    unchanged=sha(lockpath)==lockhash and all(sha(ROOT/p)==h for p,h in {**lock['code_hashes'],**sources}.items())
    ok=proc.returncode==0 and bool(found) and bool(re.search(r'\nOK\s*$',output)) and unchanged
    receipt={'status':'PASS' if ok else 'FAIL','returncode':proc.returncode,'runtime_lock_sha256':lockhash,
      'passed':int(found.group(1)) if ok else None,'tests_reported':int(found.group(1)) if found else None,
      'source_sha256':sources,'production_and_tests_unchanged':unchanged,
      'log_ref':log.relative_to(ROOT).as_posix(),'log_sha256':sha(log),'runner_sha256':sha(Path(__file__))}
    path=directory/'unit-receipt.json';path.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'passed':receipt['passed'],'receipt':str(path)}),flush=True)
    return int(not ok)
if __name__=='__main__':raise SystemExit(main())
