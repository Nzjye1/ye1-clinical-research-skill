"""Run inherited synthetic engineering regressions against an installed Skill.

Requires all documented dependency groups. Every output goes to a new area;
commands and stdout/stderr survive first failure. No archive/cold-PC claim.
"""
from pathlib import Path
import argparse,concurrent.futures,datetime,json,os,subprocess,sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--package',required=True)
    p.add_argument('--area',required=True)
    a=p.parse_args()
    package=Path(a.package).resolve();area=Path(a.area).resolve()
    area.mkdir(parents=True,exist_ok=False)
    python=package/('.runtime/python/bin/python3' if sys.platform=='darwin' else '.runtime/python/Scripts/python.exe')
    scripts=Path(__file__).resolve().parent/'regression'
    results=[]
    env=os.environ.copy()
    for key in list(env):
        if key=='LANG' or key.startswith('LC_'):env.pop(key)
    if sys.platform=='darwin':env.update(LANG='en_US.UTF-8',LC_CTYPE='en_US.UTF-8')
    env['PYTHONDONTWRITEBYTECODE']='1'
    def save():
        (area/'receipt.json').write_text(json.dumps({'results':results,'source_data':'synthetic engineering fixtures only',
            'physical_cold_pc':False,'scientific_review':'pending'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def run(case):
        label,script,extra=case
        command=[str(python),'-I','-B','-X','utf8',str(scripts/script),'--package',str(package),'--area',str(area/label),*map(str,extra)]
        record={'suite':label,'command':command,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        with (area/(label+'.stdout.log')).open('xb') as out,(area/(label+'.stderr.log')).open('xb') as err:
            done=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env)
        record.update(returncode=done.returncode,status='PASS' if done.returncode==0 else 'FAIL',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        (area/(label+'-command.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        return record
    def batch(cases):
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            for record in pool.map(run,cases):
                results.append(record);save();print(json.dumps({'suite':record['suite'],'status':record['status']}),flush=True)
        return all(x['status']=='PASS' for x in results)
    if not batch([('core','test_core_forward.py',[]),('module','test_module_forward.py',[]),('legacy','test_legacy_forward.py',[])]):return 1
    common=['--core-area',area/'core','--rf-area',area/'module','--hgb-area',area/'module']
    if not batch([('frozen','test_frozen_forward.py',common),('input-guards','test_input_guards.py',common),('numerical','compare_numerical.py',['--core-area',area/'core'])]):return 1
    if not batch([('aliases-views','test_alias_views.py',['--core-area',area/'core']),('reload','test_reload_operations.py',common),('numerical-additional','compare_additional.py',['--core-area',area/'core','--legacy-area',area/'legacy','--numerical-area',area/'numerical'])]):return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
