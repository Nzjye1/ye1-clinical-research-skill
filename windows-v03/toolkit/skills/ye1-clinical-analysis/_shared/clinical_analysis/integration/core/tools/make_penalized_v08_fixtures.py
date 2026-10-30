"""Prespecified small synthetic v08 cohorts, splits and adapter mappings."""
from __future__ import annotations
import copy,csv,hashlib,importlib.util,json,random,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/penalized-v08'
METHODS={('gaussian','lasso'):'prediction.continuous.signed.lasso',('gaussian','elasticnet'):'prediction.continuous.signed.elasticnet',('binomial','lasso'):'prediction.binary.lasso',('binomial','elasticnet'):'prediction.binary.elasticnet'}
GRID=[1,.5,.2,.1,.05,.02]
MAP={'patient_id':'stay_code','group_id':'center_code','partition':'split_code','fold':'cv_number','age':'age_months','severity':'severity_percent','sex':'category_code','constant':'constant_raw','outcome':'endpoint_percent'}
def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(path,name):
    sys.path.insert(0,str(ROOT/'python'));s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def write_csv(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as h:w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def build_rows(family='gaussian',external=False):
    rng=random.Random(2026102408+(1 if external else 0));n=48 if external else 144;rows=[]
    for i in range(n):
        g=i//4;binary=i%2;age=round(rng.uniform(22,82),2);severity=round(.8*(2*binary-1)+rng.gauss(0,.9),6);sex='F' if i%4<2 else 'M'
        signed=round(-4+.07*(age-50)+1.1*severity+.7*(sex=='M')+rng.gauss(0,.6),6)
        train=not external and g<27;fold=(1 if g<6 else 2 if g<15 else 3) if train else 0;prefix='EXTERNAL' if external else 'DEVELOPMENT'
        rows.append({'patient_id':f'SYNTHETIC-V08-{prefix}-{i+1:06d}','group_id':f'SYNTHETIC-V08-{prefix}-GROUP-{g+1:04d}',
          'partition':'train' if train else 'holdout','fold':fold,'age':age,'severity':severity,'sex':sex,'constant':3,'outcome':signed if family=='gaussian' else binary})
    missing=[(3,'age'),(8,'severity'),(20,'sex'),(23,'sex'),(42,'age'),(53,'severity'),(60,'sex'),(63,'sex'),(87,'age'),(91,'severity'),(100,'sex'),(103,'sex'),(116,'age'),(129,'severity'),(137,'sex')]
    for i,key in missing:
        if i<len(rows):rows[i][key]=''
    return rows
def options(family='gaussian',penalty='lasso',split='group',operation='train',model_ref=None,cohort_id=None):
    return {'operation':operation,'spec':{'id':'patient_id','outcome':'outcome','family':family,'alpha':1 if penalty=='lasso' else .5,
      'lambda_grid':GRID.copy(),'features':[{'name':name,'type':kind} for name,kind in [('age','number'),('severity','number'),('sex','category'),('constant','number')]],
      'split':{'method':'prespecified_group' if split=='group' else 'prespecified_patient','partition_field':'partition','fold_field':'fold','group_field':'group_id' if split=='group' else None,'training_value':'train','holdout_value':'holdout','cv_folds':3},
      'selection_rule':'min_mean_loss_largest_lambda_tie','missing':'training_median_mode','standardization':'training_population_sd','response_transform':'training_center_scale' if family=='gaussian' else 'identity',
      'clinical_threshold':.5 if family=='binomial' else None,'cohort_id':cohort_id or ('synthetic-v08-development' if operation=='train' else 'synthetic-v08-external'),'canonical_identity_namespace':'synthetic_penalized_v08'},
      'model_ref':model_ref,'unknown_category_policy':'reject'}
def analytic_rows(family='gaussian'):
    rows=build_rows(family)
    for i,row in enumerate(rows):
        if family=='gaussian':x1=(-1,-1,1,1)[i%4];x2=(-1,1,-1,1)[i%4]
        else:x1=(-1,1)[(i%4)//2];x2=x1 if (i//4)%2==0 else -x1
        row.update(age=50+x1,severity=x2,sex='F',constant=3,outcome=.6*x1-.8*x2 if family=='gaussian' else i%2)
    return rows
def mapped(rows,family='gaussian'):
    out=[]
    for row in rows:
        item={}
        for key,value in row.items():
            if key=='partition':value={'train':'TRAIN','holdout':'TEST'}[value]
            elif key=='sex':value={'F':'female','M':'male','Z':'unseen','':'UNK',None:'UNK'}.get(value,value)
            elif key in ('age','severity','outcome'):value='-999' if value in ('',None) else value*(12 if key=='age' else 1 if key=='outcome' and family=='binomial' else 100)
            item[MAP[key]]=value
        out.append(item)
    return out
def prepare_task(c,path,out,family='gaussian',penalty='lasso',db='mimic',opts=None):
    task=c.make_penalized_task(str(path),str(out),str(ROOT),database='eICU' if db=='eicu' else 'MIMIC',method_id=METHODS[family,penalty],penalized_options=copy.deepcopy(options(family,penalty) if opts is None else opts))
    task['study_id']='synthetic-penalized-v08'
    for v in task['variables']:
        if v['name']=='sex':v.update(levels=['M','F','Z'],reference='M',codes={x:x for x in ['M','F','Z']},concept='Synthetic prespecified category')
    if db=='eicu':
        task['views'][0]['column_map']={k:MAP[k] for k in task['views'][0]['column_map']}
        for v in task['variables']:
            name=v['name']
            if name=='partition':v.update(codes={'TRAIN':'train','TEST':'holdout'})
            elif name=='sex':v.update(codes={'female':'F','male':'M','unseen':'Z'},missing_codes=['UNK'])
            elif name=='age':v.update(source_unit='month',conversion={'scale':1/12,'offset':0},missing_codes=['-999'])
            elif name=='severity' or name=='outcome' and family=='gaussian':v.update(source_unit='percent',conversion={'scale':.01,'offset':0},missing_codes=['-999'])
            elif name=='outcome':v.update(missing_codes=['-999'])
    c.seal_task(task,str(ROOT));return task
def reference_input(rows=None,family='gaussian',penalty='lasso',opts=None):
    return {'mode':'train','rows':copy.deepcopy(build_rows(family) if rows is None else rows),'spec':copy.deepcopy((options(family,penalty) if opts is None else opts)['spec'])}
def main():
    FIX.mkdir(parents=True,exist_ok=True)
    for family in ('gaussian','binomial'):
        for external in (False,True):
            rows=build_rows(family,external);cohort='external' if external else 'development'
            for db in ('mimic','eicu'):write_csv(FIX/f'{cohort}-{family}-{db}.csv',mapped(rows,family) if db=='eicu' else rows)
        for penalty in ('lasso','elasticnet'):
            dump(FIX/f'reference-{family}-{penalty}.json',reference_input(family=family,penalty=penalty))
            if '--data-only' not in sys.argv:
                c=module(ROOT/'python/clinical_methods/contracts.py','penalized_fixture_contracts')
                for db in ('mimic','eicu'):dump(FIX/f'train-{family}-{penalty}-{db}.json',prepare_task(c,FIX/f'development-{family}-{db}.csv',ROOT/'outputs'/f'penalized-v08-{family}-{penalty}-{db}',family,penalty,db))
    manifest={'purpose':'SYNTHETIC_TEST_ONLY','development_n':144,'training_n':108,'holdout_n':36,'external_n':48,'group_size':4,'training_groups':27,'holdout_groups':9,'external_groups':12,'cv_validation_subjects':[24,36,48],'cv_fitting_binomial_class_counts':[42,36,30],'lambda_grid':GRID,'methods':list(METHODS.values()),'source_sha256':{p.name:sha(p) for p in sorted(FIX.glob('*.csv'))},'scope':'Fixed synthetic cohorts only; independent preprocessing/CV with direct installed glmnet calls, not independent-optimizer or clinical validation'}
    dump(FIX/'fixture-manifest.json',manifest);print(json.dumps({'status':'PENALIZED_V08_SYNTHETIC_FIXTURES_READY','n':144,'training':108,'holdout':36,'external':48,'fold_n':[24,36,48]}))
if __name__=='__main__':main()
