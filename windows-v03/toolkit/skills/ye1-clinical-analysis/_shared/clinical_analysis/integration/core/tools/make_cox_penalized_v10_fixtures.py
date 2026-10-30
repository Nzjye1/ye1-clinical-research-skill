"""Bounded, prespecified synthetic Cox fixtures. Never a real-data recipe."""
from __future__ import annotations
import argparse,copy,csv,hashlib,importlib.util,json,math,random,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
GRID=[1,.5,.2,.1,.05,.02]
HORIZONS=[0,5,10,20,40,50]
METHODS={'lasso':'prediction.survival.cox.lasso','elasticnet':'prediction.survival.cox.elasticnet'}
MAP={'patient_id':'stay_code','group_id':'center_code','partition':'split_code','fold':'cv_number','age':'age_months','severity':'severity_percent','sex':'category_code','constant':'constant_raw','duration':'followup_hours','event':'terminal_code'}

def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(path,name):
    sys.path.insert(0,str(ROOT/'python'));spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
def write_csv(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def build_rows(external=False):
    rng=random.Random(2026102410+int(external));rows=[];n=48 if external else 144
    for i in range(n):
        group=i//4;age=round(rng.uniform(22,82),2);severity=round(rng.gauss(0,.9),6);sex='F' if i%4<2 else 'M'
        eta=.023*(age-50)+.9*severity+.25*(sex=='M')
        event_time=max(1,min(30,round(14*math.exp(-eta)*rng.expovariate(1))))
        censor_time=8+(i*7)%33;event=int(event_time<=censor_time);duration=event_time if event else censor_time
        training=not external and group<27;fold=(1 if group<6 else 2 if group<15 else 3) if training else 0
        prefix='EXTERNAL' if external else 'DEVELOPMENT'
        rows.append({'patient_id':f'SYNTHETIC-V10-{prefix}-{i+1:06d}','group_id':f'SYNTHETIC-V10-{prefix}-GROUP-{group+1:04d}',
          'partition':'train' if training else 'holdout','fold':fold,'age':age,'severity':severity,'sex':sex,'constant':3,'duration':duration,'event':event})
    # Exact event/censor ties are deliberate; no epsilon perturbation is used.
    for i in (0,24,60):
        if i+1<len(rows):rows[i].update(duration=5,event=1);rows[i+1].update(duration=5,event=0)
    rows[47 if external else 107].update(duration=50,event=0)
    for i,key in [(3,'age'),(8,'severity'),(20,'sex'),(23,'sex'),(42,'age'),(53,'severity'),(60,'sex'),(63,'sex'),(87,'age'),(91,'severity'),(100,'sex'),(103,'sex'),(116,'age'),(129,'severity'),(137,'sex')]:
        if i<len(rows):rows[i][key]=''
    return rows

def options(penalty='lasso',split='group',operation='train',model_ref=None,cohort_id=None):
    return {'operation':operation,'spec':{'id':'patient_id','duration':'duration','event':'event','alpha':1 if penalty=='lasso' else .5,
      'lambda_grid':GRID.copy(),'features':[{'name':name,'type':kind} for name,kind in [('age','number'),('severity','number'),('sex','category'),('constant','number')]],
      'split':{'method':'prespecified_group' if split=='group' else 'prespecified_patient','partition_field':'partition','fold_field':'fold','group_field':'group_id' if split=='group' else None,'training_value':'train','holdout_value':'holdout','cv_folds':3},
      'selection_rule':'min_deviance_per_event_largest_lambda_tie','missing':'training_median_mode','standardization':'training_population_sd',
      'cohort_id':cohort_id or ('synthetic-v10-development' if operation=='train' else 'synthetic-v10-external'),'canonical_identity_namespace':'synthetic_cox_penalized_v10',
      'survival':{'outcome_type':'single_event_right_censored','time_unit':'day','time_zero_definition':'Synthetic baseline at index time zero','event_definition':'Synthetic terminal event','censoring_definition':'Synthetic right censoring at last follow-up','event_code':1,'censor_code':0,'ties':'breslow'},'horizons':HORIZONS.copy()},
      'model_ref':model_ref,'unknown_category_policy':'reject'}

def single_signal_rows():
    rows=build_rows()
    for i,row in enumerate(rows):
        signal=(-1,-1,1,1)[i%4];noise=(-1,1,-1,1)[i%4]
        row.update(age=50+signal,severity=noise,sex='F',duration=5 if signal==1 else 20,event=1)
    rows[107].update(duration=50,event=0)
    return rows

def mapped(rows):
    result=[]
    for row in rows:
        item={}
        for name,value in row.items():
            if name=='partition':value={'train':'TRAIN','holdout':'TEST'}[value]
            elif name=='sex':value={'F':'female','M':'male','Z':'unseen','':'UNK',None:'UNK'}.get(value,value)
            elif name in ('age','severity','duration'):value='-999' if value in ('',None) else value*{'age':12,'severity':100,'duration':24}[name]
            elif name=='event':value='-999' if value in ('',None) else value
            item[MAP[name]]=value
        result.append(item)
    return result

def prepare_task(c,path,out,penalty='lasso',db='mimic',opts=None,root=None):
    root=Path(root or ROOT)
    task=c.make_cox_penalized_task(str(path),str(out),str(root),database='eICU' if db=='eicu' else 'MIMIC',method_id=METHODS[penalty],cox_penalized_options=copy.deepcopy(options(penalty) if opts is None else opts))
    task['study_id']='synthetic-cox-penalized-v10'
    for var in task['variables']:
        if var['name']=='sex':var.update(levels=['M','F','Z'],reference='M',codes={x:x for x in ['M','F','Z']},concept='Synthetic prespecified category')
    if db=='eicu':
        task['views'][0]['column_map']={key:MAP[key] for key in task['views'][0]['column_map']}
        for var in task['variables']:
            name=var['name']
            if name=='partition':var.update(codes={'TRAIN':'train','TEST':'holdout'})
            elif name=='sex':var.update(codes={'female':'F','male':'M','unseen':'Z'},missing_codes=['UNK'])
            elif name=='age':var.update(source_unit='month',conversion={'scale':1/12,'offset':0},missing_codes=['-999'])
            elif name=='severity':var.update(source_unit='percent',conversion={'scale':.01,'offset':0},missing_codes=['-999'])
            elif name=='duration':var.update(source_unit='hour',conversion={'scale':1/24,'offset':0},missing_codes=['-999'])
            elif name=='event':var.update(missing_codes=['-999'])
    return c.seal_task(task,str(root))

def reference_input(rows=None,penalty='lasso',opts=None):return {'mode':'train','rows':copy.deepcopy(build_rows() if rows is None else rows),'spec':copy.deepcopy((options(penalty) if opts is None else opts)['spec'])}

def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--data-only',action='store_true');parser.add_argument('--out',type=Path,default=ROOT/'fixtures/cox-penalized-v10');args=parser.parse_args(argv)
    args.out.mkdir(parents=True,exist_ok=True)
    for external in (False,True):
        rows=build_rows(external);name='external' if external else 'development'
        for db in ('mimic','eicu'):write_csv(args.out/f'{name}-{db}.csv',mapped(rows) if db=='eicu' else rows)
    for penalty in METHODS:
        dump(args.out/f'reference-{penalty}.json',reference_input(penalty=penalty))
        if not args.data_only:
            c=module(ROOT/'python/clinical_methods/contracts.py','cox_fixture_contracts')
            for db in ('mimic','eicu'):dump(args.out/f'train-{penalty}-{db}.json',prepare_task(c,args.out/f'development-{db}.csv',ROOT/'outputs'/f'cox-penalized-v10-{penalty}-{db}',penalty,db))
    training=[r for r in build_rows() if r['partition']=='train']
    folds=[{'fold':k,'n_validation':sum(r['fold']==k for r in training),'validation_events':sum(r['event'] for r in training if r['fold']==k),'fitting_events':sum(r['event'] for r in training if r['fold']!=k)} for k in (1,2,3)]
    assert all(r['validation_events']>=3 and r['fitting_events']>=8 for r in folds)
    dump(args.out/'fixture-manifest.json',{'purpose':'SYNTHETIC_TEST_ONLY','development_n':144,'training_n':108,'holdout_n':36,'external_n':48,'group_size':4,'folds':folds,'lambda_grid':GRID,'horizons':HORIZONS,'methods':list(METHODS.values()),'source_sha256':{p.name:sha(p) for p in sorted(args.out.glob('*.csv'))},'scope':'Independent preprocessing/CV and formulas with shared installed engines; no independent optimizer or clinical validation'})
    print(json.dumps({'status':'COX_PENALIZED_V10_SYNTHETIC_FIXTURES_READY','development':144,'training':108,'holdout':36,'external':48,'folds':folds}))
if __name__=='__main__':main()
