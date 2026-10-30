"""Small paired synthetic survival cohorts; no real database access."""
from __future__ import annotations
import csv,hashlib,importlib.util,json,math,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures'
MAP={'id':'stay_code','time':'followup_hours','status':'event_code','x':'baseline_x','z':'baseline_z','group':'group_code'}
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def write_csv(p,rows):
    with Path(p).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def build_rows():
    rng=random.Random(2026102404);rows=[]
    for i in range(200):
        x=rng.gauss(0,1);z=rng.uniform(-1,1);group='A' if i%2==0 else 'B'
        event=-math.log(max(rng.random(),1e-12))/(.065*math.exp(.25*x-.18*z+.15*(group=='B')))
        censor=rng.uniform(16,30);followup=min(event,censor)
        rows.append(dict(id=f'SYNTHETIC-V04-{i+1:06d}',time=min(30,max(.5,math.ceil(followup*2)/2)),status=str(int(event<=censor)),x=x,z=z,group=group))
    for field,indices in [('time',[1,21,41,61]),('status',[2,22,42]),('x',[3,23,43]),('z',[4,24,44,64,84]),('group',[5,25])]:
        for i in indices:rows[i][field]=''
    return rows
def hand_rows():
    return [dict(id=f'SYNTHETIC-HAND-{i+1}',time=t,status=s,x=i/6,z=(i%3)/3,group='A' if i%2==0 else 'B') for i,(t,s) in enumerate(zip([1,1,2,2,3,4],['1','0','1','0','1','0']))]
def mapped(rows):
    return [{MAP['id']:r['id'],MAP['time']:24*r['time'] if r['time']!='' else '-999',MAP['status']:{'0':'no','1':'yes','':'UNK'}[r['status']],
      MAP['x']:r['x'] if r['x']!='' else '-999',MAP['z']:r['z'] if r['z']!='' else '-999',MAP['group']:{'A':'F','B':'M','':'UNK'}[r['group']]} for r in rows]
def module():
    loader=importlib.util.spec_from_file_location('survival_fixture_contracts',ROOT/'python/clinical_methods/contracts.py')
    c=importlib.util.module_from_spec(loader);sys.modules[loader.name]=c;loader.loader.exec_module(c);return c
def prepare_task(c,path,out,kind='km',db='mimic',grid=None):
    method='survival.kaplan_meier' if kind=='km' else 'survival.cox.association'
    task=c.make_survival_task(str(path),str(out),str(ROOT),method_id=method,database='eICU' if db=='eicu' else 'MIMIC')
    task['study_id']='synthetic-survival-200';s=task['analysis']['survival']
    s['evaluation_times']=grid if grid is not None else [0,1,5,10,15,20]
    s['covariates']=[] if kind=='km' else [{'name':n,'type':'numeric','available_at_time_zero':True} for n in ['x','z']]+[{'name':'group','type':'category','levels':['A','B'],'reference':'A','available_at_time_zero':True}]
    for v in task['variables']:
        if v['name']=='group':v.update(levels=['A','B'],reference='A',codes={'A':'A','B':'B'})
    if db=='eicu':
        task['views'][0]['column_map']=MAP.copy()
        for v in task['variables']:
            if v['name']=='time':v.update(source_unit='hour',unit='day',conversion={'scale':1/24,'offset':0},missing_codes=['-999'])
            elif v['name'] in ['x','z']:v['missing_codes']=['-999']
            elif v['name']=='status':v.update(codes={'yes':'1','no':'0'},missing_codes=['UNK'])
            elif v['name']=='group':v.update(codes={'F':'A','M':'B'},missing_codes=['UNK'])
    c.seal_task(task,str(ROOT));return task
def main():
    FIX.mkdir(exist_ok=True);rows=build_rows();c=module()
    write_csv(FIX/'survival-canonical.csv',rows);write_csv(FIX/'survival-mimic.csv',rows);write_csv(FIX/'survival-eicu.csv',mapped(rows));write_csv(FIX/'survival-hand.csv',hand_rows())
    for db in ['mimic','eicu']:
        for kind in ['km','cox']:
            label=f'{db}-{kind}';dump(FIX/f'survival-{label}.json',prepare_task(c,FIX/f'survival-{db}.csv',ROOT/'outputs'/f'survival-example-{label}',kind,db))
    dump(FIX/'survival-hand.json',prepare_task(c,FIX/'survival-hand.csv',ROOT/'outputs/survival-example-hand','km',grid=[0,1,1.5,2,2.5,3,4]))
    dump(FIX/'survival-fixture-manifest.json',{'purpose':'SYNTHETIC_TEST_ONLY','seed':2026102404,'n_rows':200,'source_fingerprints':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FIX.glob('survival-*.csv')},'mapping':'Same synthetic records; renamed columns, hours/24 -> days, yes/no -> 1/0, F/M -> A/B; -999/UNK missing','scope':'No real source database or clinical-validity claim'})
    print('SYNTHETIC_SURVIVAL_FIXTURES_READY')
if __name__=='__main__':main()
