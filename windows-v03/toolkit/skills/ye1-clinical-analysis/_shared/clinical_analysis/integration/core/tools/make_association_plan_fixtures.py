"""Paired 200-row synthetic association-plan fixtures; no source database I/O."""
from __future__ import annotations
import copy,csv,hashlib,importlib.util,json,math,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'fixtures'
FIELDS=['id','x','z','group','y','binary']
MAP={'id':'stay_code','x':'exposure_pct','z':'covariate_scaled','group':'group_code','y':'outcome_lab','binary':'event_code'}
def dump(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def write_csv(p,rows):
    with Path(p).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def build_rows():
    rng=random.Random(2026102403);rows=[]
    for i in range(200):
        x=rng.uniform(-2.5,2.5);z=rng.gauss(0,1);group='A' if i%2==0 else 'B'
        y=2+.6*x+.22*x*x-.4*z+.3*x*(group=='B')+rng.gauss(0,.9)
        eta=.1+.25*x+.14*x*x-.22*z+.2*x*(group=='B')
        binary=str(int(rng.random()<1/(1+math.exp(-eta))))
        rows.append(dict(id=f'SYNTHETIC-V03-{i+1:06d}',x=x,z=z,group=group,y=y,binary=binary))
    for field,indices in [('x',[1,20,39]),('z',[2,22,42,62,82]),('group',[4,44]),('y',[3,30]),('binary',[5,31])]:
        for i in indices:rows[i][field]=''
    return rows
def mapped(rows):
    return [{MAP['id']:r['id'],MAP['x']:100*r['x'] if r['x']!='' else '-999',
       MAP['z']:r['z'] if r['z']!='' else '-999',MAP['group']:{'A':'F','B':'M','':'UNK'}[r['group']],
       MAP['y']:r['y'] if r['y']!='' else '-999',MAP['binary']:{'0':'no','1':'yes','':'UNK'}[r['binary']]} for r in rows]
def module():
    loader=importlib.util.spec_from_file_location('association_fixture_contracts',ROOT/'python/clinical_methods/contracts.py')
    value=importlib.util.module_from_spec(loader);sys.modules[loader.name]=value;loader.loader.exec_module(value);return value
def model_spec(kind,covariates):
    return {'model':kind,'outcome':'binary' if kind=='logistic' else 'y','exposure':'x','covariates':covariates,
      'missing':'complete_case','covariance':'model' if kind=='logistic' else 'HC3','categorical':{},
      'row_unit':'subject','independent':True,'key':['id'],'subject_id':'id','sensitivity':[],
      **({'event':'1','non_event':'0'} if kind=='logistic' else {})}
def model_entry(kind,model_id,role,covariates,where=None):
    return {'model_id':model_id,'label':model_id,'rationale':'Prespecified synthetic acceptance model; no data-driven selection',
      'role':role,'where':where or [],'spec':model_spec(kind,covariates),'curve':None,'subgroup_min_n':None}
def make_plan(kind,scenario='sequence',strategy='per_model_complete_case'):
    if scenario=='sequence':
        models=[model_entry(kind,'primary','primary',[]),model_entry(kind,'adjusted','adjustment',['z']),
          model_entry(kind,'restricted','sensitivity',['z'],[{'field':'group','op':'eq','value':'A'}])]
    elif scenario=='rcs':
        models=[model_entry(kind,'linear','primary',['z']),model_entry(kind,'spline','adjustment',['z'])]
        models[1]['spec']['nonlinear']={'method':'restricted_cubic','knots':[-2.,0.,2.]}
        models[1]['curve']={'reference':0.,'grid':[-2.,-1.,0.,1.,2.],'domain':[-2.,2.]}
    elif scenario=='subgroup':
        models=[model_entry(kind,'interaction','primary',['z'])]
        models[0]['spec']['subgroup']={'field':'group','levels':['A','B'],'reference':'A'}
        models[0]['subgroup_min_n']=30
    else:raise ValueError('unknown synthetic scenario')
    return {'sample_strategy':strategy,'multiplicity':'unadjusted_prespecified','models':models}
def prepare_task(c,csv_path,out,kind='linear',scenario='sequence',db='mimic',strategy='per_model_complete_case'):
    task=c.make_association_plan_task(str(csv_path),str(out),str(ROOT),method_id='association.'+kind+'.plan',database='eICU' if db=='eicu' else 'MIMIC')
    task['study_id']='synthetic-association-plan-200';task['analysis']['association']=make_plan(kind,scenario,strategy)
    if db=='eicu':
        task['views'][0]['column_map']=MAP.copy()
        for v in task['variables']:
            if v['name']=='x':v.update(source_unit='percent',unit='1',conversion={'scale':.01,'offset':0},missing_codes=['-999'])
            elif v['name']=='z':v['missing_codes']=['-999']
            elif v['name']=='y':v['missing_codes']=['-999']
            elif v['name']=='group':v.update(codes={'F':'A','M':'B'},missing_codes=['UNK'])
            elif v['name']=='binary':v.update(codes={'no':'0','yes':'1'},missing_codes=['UNK'])
    c.seal_task(task,str(ROOT));return task
def main():
    FIX.mkdir(exist_ok=True);rows=build_rows()
    write_csv(FIX/'association-plan-canonical.csv',rows);write_csv(FIX/'association-plan-mimic.csv',rows)
    write_csv(FIX/'association-plan-eicu.csv',mapped(rows));c=module()
    for db in ['mimic','eicu']:
        for kind in ['linear','logistic']:
            for scenario in ['sequence','rcs','subgroup']:
                label=f'{db}-{kind}-{scenario}'
                task=prepare_task(c,FIX/f'association-plan-{db}.csv',ROOT/'outputs'/('association-plan-example-'+label),kind,scenario,db)
                dump(FIX/('association-plan-'+label+'.json'),task)
    dump(FIX/'association-plan-fixture-manifest.json',{'purpose':'SYNTHETIC_TEST_ONLY','seed':2026102403,'n_rows':200,
      'source_fingerprints':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in FIX.glob('association-plan-*.csv')},
      'mapping':'same synthetic records; renamed columns, percent->1, F/M->A/B and no/yes->0/1; explicit -999/UNK missing',
      'scope':'No real source database or clinical-validity claim'})
    print('SYNTHETIC_ASSOCIATION_PLAN_FIXTURES_READY')
if __name__=='__main__':main()
