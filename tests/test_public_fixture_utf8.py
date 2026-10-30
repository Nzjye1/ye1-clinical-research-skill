"""Public PBC generator regression: inherited locale plus Unicode absolute path.

This only regenerates the allowlisted two-column public fixture. It does not
authorize ordinary real research or claim a PBC baseline/GUI test.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workdir',required=True);p.add_argument('--rscript',required=True);p.add_argument('--r-library',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];main=root/'windows-v03/toolkit/skills/ye1-clinical-analysis'
    area=Path(a.workdir).resolve();area.mkdir(parents=True,exist_ok=False);folder=area/'中文 路径';folder.mkdir();output=folder/'固定 公开投影.csv'
    assert (main/'examples/make_public_pbc.R').read_bytes()==(main/'tests/public_fixture/make_pbc_fixture.R').read_bytes()
    command=[str(Path(a.rscript).resolve()),'--vanilla',str(main/'examples/make_public_pbc.R'),str(output),str(Path(a.r_library).resolve())]
    env=os.environ.copy();env.update(LANG='C.UTF-8',LC_ALL='C.UTF-8')
    x=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,env=env)
    (area/'stdout.log').write_bytes(x.stdout);(area/'stderr.log').write_bytes(x.stderr)
    record={'command':command,'returncode':x.returncode,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'locale':'inherited LANG=LC_ALL=C.UTF-8','scope':'fixed public fixture only','ordinary_PBC_baseline':'NOT_TESTED','GUI_discovery':'NOT_TESTED','global_locale_changed':False}
    (area/'command.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    assert x.returncode==0
    digest=hashlib.sha256(output.read_bytes()).hexdigest();assert digest=='92cc9dc9f6e8b95e2bedc9f7bab201755e761795374765bdd3c466b2d516d151'
    record.update(status='PASS',sha256=digest,bytes=output.stat().st_size)
    (area/'result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(record))

if __name__=='__main__':main()
