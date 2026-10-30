"""Prespecified local synthetic v09 cohorts; no patient/source database access."""
from __future__ import annotations
import copy,csv,hashlib,importlib.util,json,math,random,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'fixtures/interpretation-v09'
METHODS={('gaussian','lasso'):'prediction.continuous.signed.lasso',('gaussian','elasticnet'):'prediction.continuous.signed.elasticnet',('binomial','lasso'):'prediction.binary.lasso',('binomial','elasticnet'):'prediction.binary.elasticnet'}
GRID=[1,.5,.2,.1,.05,.02]
MAP={'patient_id':'stay_code','group_id':'center_code','partition':'split_code','fold':'cv_number','age':'age_months','severity':'severity_percent','sex':'category_code','constant':'constant_raw','outcome':'endpoint_percent'}
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(p,name):
    sys.path.insert(0,str(ROOT/'python'));s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def write_csv(p,rows):
    with Path(p).open('w',encoding='utf-8',newline='') as h:w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def build_rows(family='gaussian',external=False):
    rng=random.Random(2026102409+int(external));n=48 if external else 144;rows=[]
    for i in range(n):
        group=i//4;sex=('F','M','Z')[i%3];age=rng.randint(120,280)/4;severity=rng.randint(-8,8)/4
        signed=round(16*(-8+.04*(age-50)+.8*severity+{'F':0,'M':2,'Z':4}[sex]+rng.uniform(-.2,.2)))/16
        probability=1/(1+math.exp(-(.04*(age-50)+.9*severity+{'F':-.5,'M':.8,'Z':-.3}[sex])))
        binary=int(rng.random()<probability);training=not external and group<27;fold=(1 if group<6 else 2 if group<15 else 3) if training else 0
        prefix='EXTERNAL' if external else 'DEVELOPMENT'
        rows.append({'patient_id':f'SYNTHETIC-V09-{prefix}-{i+1:06d}','group_id':f'SYNTHETIC-V09-{prefix}-GROUP-{group+1:04d}',
          'partition':'train' if training else 'holdout','fold':fold,'age':age,'severity':severity,'sex':sex,'constant':3,'outcome':signed if family=='gaussian' else binary})
    if not external:
        rows[0].update(age=20,severity=-3);rows[1].update(age=80,severity=3)
    for i,key in [(3,'age'),(8,'severity'),(19,'sex'),(20,'sex'),(21,'sex'),(42,'age'),(53,'severity'),(60,'sex'),(61,'sex'),(62,'sex'),(87,'age'),(91,'severity'),(99,'sex'),(100,'sex'),(101,'sex'),(116,'age'),(129,'severity'),(137,'sex')]:
        if i<n:rows[i][key]=''
    if not external and family=='binomial':
        for fold in (1,2,3):
            y=[r['outcome'] for r in rows if r['partition']=='train' and r['fold']!=fold];assert min(y.count(0),y.count(1))>=8
    return rows
def options(family='gaussian',penalty='lasso',operation='train',model_ref=None):
    return {'operation':operation,'spec':{'id':'patient_id','outcome':'outcome','family':family,'alpha':1 if penalty=='lasso' else .5,'lambda_grid':GRID.copy(),
      'features':[{'name':n,'type':t} for n,t in [('age','number'),('severity','number'),('sex','category'),('constant','number')]],
      'split':{'method':'prespecified_group','partition_field':'partition','fold_field':'fold','group_field':'group_id','training_value':'train','holdout_value':'holdout','cv_folds':3},
      'selection_rule':'min_mean_loss_largest_lambda_tie','missing':'training_median_mode','standardization':'training_population_sd','response_transform':'training_center_scale' if family=='gaussian' else 'identity',
      'clinical_threshold':.5 if family=='binomial' else None,'cohort_id':'synthetic-v09-development' if operation=='train' else 'synthetic-v09-external','canonical_identity_namespace':'synthetic_interpretation_v09'},'model_ref':model_ref,'unknown_category_policy':'reject'}
def mapped(rows,family='gaussian'):
    out=[]
    for row in rows:
        item={}
        for k,v in row.items():
            if k=='partition':v={'train':'TRAIN','holdout':'TEST'}[v]
            elif k=='sex':v={'F':'female','M':'male','Z':'third','':'UNK',None:'UNK'}.get(v,v)
            elif k in ('age','severity','outcome'):
                scale=12 if k=='age' else 1 if k=='outcome' and family=='binomial' else 100
                if v in ('',None):v='-999'
                else:
                    original=v;v*=scale;assert v*(1/12 if scale==12 else .01 if scale==100 else 1)==original,'adapter conversion must be exactly reversible'
            item[MAP[k]]=v
        out.append(item)
    return out
def adapt_task(c,task,db):
    task['study_id']='synthetic-interpretation-v09'
    for v in task['variables']:
        if v['name']=='sex':v.update(levels=['Z','M','F'],reference='Z',codes={x:x for x in ('Z','M','F')},concept='Synthetic three-level baseline category')
    if db=='eicu':
        task['views'][0]['column_map']={k:MAP[k] for k in task['views'][0]['column_map']}
        binary=task['outcome']['type']=='binary'
        for v in task['variables']:
            n=v['name']
            if n=='partition':v.update(codes={'TRAIN':'train','TEST':'holdout'})
            elif n=='sex':v.update(codes={'female':'F','male':'M','third':'Z'},missing_codes=['UNK'])
            elif n=='age':v.update(source_unit='month',conversion={'scale':1/12,'offset':0},missing_codes=['-999'])
            elif n=='severity' or n=='outcome' and not binary:v.update(source_unit='percent',conversion={'scale':.01,'offset':0},missing_codes=['-999'])
            elif n=='outcome':v.update(missing_codes=['-999'])
    c.seal_task(task,str(ROOT));return task
def training_task(c,path,out,family='gaussian',penalty='lasso',db='mimic',opts=None):
    task=c.make_penalized_task(str(path),str(out),str(ROOT),database='eICU' if db=='eicu' else 'MIMIC',method_id=METHODS[family,penalty],penalized_options=copy.deepcopy(opts or options(family,penalty)))
    return adapt_task(c,task,db)
def interpretation_options(model_path,explainer_path,spec,method):
    spec=copy.deepcopy(spec);spec['cohort_id']='synthetic-v09-external'
    return {'model_method_id':method,'spec':spec,'model_ref':{'local_ref':str(model_path),'content_hash':sha(model_path)},'explainer_ref':{'local_ref':str(explainer_path),'content_hash':sha(explainer_path)}}
def interpretation_task(c,path,out,explain_options,db='mimic'):
    task=c.make_interpretation_task(str(path),str(out),str(ROOT),database='eICU' if db=='eicu' else 'MIMIC',interpretation_options=copy.deepcopy(explain_options));return adapt_task(c,task,db)
def main():
    FIX.mkdir(parents=True,exist_ok=True)
    for family in ('gaussian','binomial'):
        for external in (False,True):
            rows=build_rows(family,external)
            if external:
                for row in rows:row['outcome']=''
            for db in ('mimic','eicu'):write_csv(FIX/f'{"external" if external else "development"}-{family}-{db}.csv',mapped(rows,family) if db=='eicu' else rows)
    manifest={'purpose':'SYNTHETIC_TEST_ONLY','development_n':144,'training_n':108,'holdout_n':36,'external_n':48,'background':'all 108 final training subjects; never default 100-row sampling','fold_validation_n':[24,36,48],'raw_features':4,'observed_category_levels':['F','M','Z'],'declared_reference':'Z','expected_fitted_reference':'F','adapter_conversion':'exact canonical floating values; model and explainer hash equivalence required','source_sha256':{p.name:sha(p) for p in sorted(FIX.glob('*.csv'))}}
    dump(FIX/'fixture-manifest.json',manifest);print(json.dumps({'status':'INTERPRETATION_V09_SYNTHETIC_FIXTURES_READY','n':144,'training':108,'external':48}))
if __name__=='__main__':main()
