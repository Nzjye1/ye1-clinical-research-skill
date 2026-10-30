"""Registered frozen operations on new external subjects, source models unchanged."""
from pathlib import Path
import argparse,copy,csv,hashlib,json,math,random,subprocess,sys
import numpy as np
REPO=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--area',required=True);p.add_argument('--core-area',default=str(REPO/'.pilot-local/v03/core-forward-4'));p.add_argument('--rf-area',default=str(REPO/'.pilot-local/v03/module-forward-1'));p.add_argument('--hgb-area',default=str(REPO/'.pilot-local/v03/module-forward-2'));p.add_argument('--only',nargs='*');a=p.parse_args();MAIN=Path(a.package).resolve();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False);sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as rt
PY=MAIN/'.runtime/python/Scripts/python.exe';CP=next(x.parent for x in Path(a.core_area).glob('*/runs'));RP=next(x.parent for x in Path(a.rf_area).glob('*/runs'));HP=next(x.parent for x in Path(a.hgb_area).glob('*/runs'));RESULTS=[];MODELS={}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def track(p):MODELS[str(p)]=sha(p);return p
def replace(v,old,new):
 if isinstance(v,dict):return {k:replace(x,old,new) for k,x in v.items()}
 if isinstance(v,list):return [replace(x,old,new) for x in v]
 return new if v==old else v
def call(label,cmd):
 x=subprocess.run(list(map(str,cmd)),stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',env=rt.env(),timeout=900);save(AREA/(label+'-command.json'),{'command':list(map(str,cmd)),'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr});return x
def run(method,operation,project,draft):
 label=AREA.name+'-'+method.replace('.','-')+'-'+operation;out=project/'runs'/label;draft['task']['execution']['output_dir']=str(out)
 for key in ('work_dir','workdir'):
  if key in draft['task'].get('payload',{}):draft['task']['payload'][key]=str(out/'private/work')
 file=project/(label+'-draft.json');save(file,draft);x=call(label+'-prepare',[PY,'-I','-B',MAIN/'scripts/prepare_task.py','--draft',file]);stage='prepare'
 if x.returncode==0:private=json.loads(x.stdout)['task'];x=call(label+'-run',[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',method,'--task',private]);stage='run'
 item={'method':method,'operation':operation,'status':'PASS' if x.returncode==0 else 'FAIL','stage':stage,'response':x.stdout}
 if x.returncode==0:
  r=load(out/'result.json');assert r['execution_status']=='complete' and (out/'报告.md').is_file() and (list((out/'tables').glob('*.csv')) or (out/'private/frozen-display/predictions.csv').is_file()) and (list((out/'figures').glob('*.png')) or (out/'private/frozen-display/frozen-predictions.png').is_file());item.update(output=str(out),task=private)
 RESULTS.append(item);save(AREA/'receipt.json',{'results':RESULTS,'purpose':'New external synthetic subjects; no real data or user authorization simulation'});print(json.dumps(item,ensure_ascii=False),flush=True)
rng=random.Random(2026103101)
with (CP/'common.csv').open(encoding='utf-8-sig',newline='') as h:header=next(csv.reader(h))
rows=[]
for n in range(160):
 x=rng.gauss(0,1);z=rng.gauss(0,1);binary=int(rng.random()<1/(1+math.exp(-(.2+.3*x-.2*z))));y=.5+.5*x-.2*z+rng.gauss(0,1);failure=rng.expovariate(.05*math.exp(.2*x));censor=rng.uniform(12,30);duration=min(failure,censor,30);event=int(failure<=min(censor,30))
 rows.append(dict(zip(header,[f'reload03-{n}',x,z,'A' if n%2==0 else 'B',y,binary,str(n%2),'S1' if n%3 else 'S2',0,24,f'reload03-{n}','holdout',0,55+10*z,rng.gauss(0,1),'F' if n%2==0 else 'M',y,duration,event,str(event)])))
methods=['prediction.binary.ridge','prediction.continuous.nonnegative.ridge','prediction.continuous.signed.lasso','prediction.continuous.signed.elasticnet','prediction.binary.lasso','prediction.binary.elasticnet','prediction.survival.cox','prediction.survival.cox.lasso','prediction.survival.cox.elasticnet']
for method in methods:
 if a.only and method not in a.only:continue
 train=CP/'runs'/method.replace('.','-');original=load(train/'private/task-snapshot.json');draft=load(CP/(method+'-draft.json'));source=CP/(AREA.name+'-'+method+'.csv');data=copy.deepcopy(rows)
 for row in data:
  if method.startswith('prediction.binary.'):row['outcome']=row['binary']
  if method=='prediction.continuous.nonnegative.ridge':row['y']=math.exp(.1*row['y'])
  if method=='prediction.survival.cox':row['time']=row['duration'];row['label_ready']=30
 with source.open('x',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=header);w.writeheader();w.writerows(data)
 for operation in ['infer'] if method.startswith('prediction.survival.') else ['evaluate','infer']:
  task=copy.deepcopy(original);task['study_id']='reload_'+operation+'_'+method.replace('.','_');task['execution']['output_dir']='unused';task['authorization']=None;task['execution']['authorization_ref']=None;task['plan_hash']='0'*64;task['validation'].update(kind='new_data_inference' if operation=='infer' else 'synthetic_frozen_application',overlap_status='verified_synthetic_disjoint');task['split'].update(strategy='none',fit_scope='frozen_only');task['missingness']['fit_scope']='frozen_only'
  if 'prediction' in task['analysis']:
   options=task['analysis']['prediction'];model=track(train/'private/model-bundle.json');options.update(operation=operation,model_ref={'local_ref':str(model),'content_hash':sha(model)});options['spec']['cohort_id']='reload-external-3101'
  elif 'penalized_prediction' in task['analysis']:
   options=task['analysis']['penalized_prediction'];model=track(train/'private/penalized-model.json');options.update(operation=operation,model_ref={'local_ref':str(model),'content_hash':sha(model)});options['spec']['cohort_id']='reload-external-3101'
  elif 'cox_penalized_prediction' in task['analysis']:
   options=task['analysis']['cox_penalized_prediction'];model=track(train/'private/cox-penalized-model.json');options.update(operation=operation,model_ref={'local_ref':str(model),'content_hash':sha(model)});options['spec']['cohort_id']='reload-external-3101'
  else:
   options=task['analysis']['cox_prediction'];model=track(train/'private/frozen_cox_model.json');options.update(operation='infer',training_subjects=[],holdout_subjects=[],model_ref=str(model),model_sha256=sha(model));task['validation']['kind']='new_data_inference'
  for view in task['views']:view.update(local_ref=str(source),content_hash={'$file_sha256':str(source)},unselected_columns=[name for name in header if name not in view['column_map']])
  for s in task['sources']:s.update(source_fingerprint={'$file_sha256':str(source)},snapshot='new-reload-3101',evidence_refs=['new external synthetic seed 2026103101'])
  run(method,operation,CP,{'schema_version':'ye1-toolkit-draft@1.0','method_id':method,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(CP),'local_tables':{},'task':task})

for suffix,project,area in [('random_forest',RP,'module-forward-1'),('hist_gradient_boosting',HP,'module-forward-2')]:
 method='prediction.binary.'+suffix
 if a.only and method not in a.only:continue
 original=load(project/'runs'/('prediction-binary-'+suffix)/'private/task-snapshot.json');model=project/(AREA.name+'-'+suffix+'-model.json');model.write_text(load(project/'runs'/('prediction-binary-'+suffix)/'private/module-response.json')['private_record']['frozen_model_json'],encoding='utf-8');track(model)
 for operation in ['evaluate','infer','explain']:
  task=copy.deepcopy(original);task['operation']=operation;payload=task['payload'];payload['spec']['cohort_id']='reload-external-3101';payload['data_contract']['missing']['fit_scope']='frozen_only';payload['frozen_model_json']={'$file_text':str(model)};payload['application_scope']='external';payload['explain_with_outcomes']=False;names=['id','x','z','category','site','time','label_ready']+(['binary'] if operation=='evaluate' else []);file=project/(AREA.name+'-'+suffix+'-'+operation+'.csv')
  with file.open('x',encoding='utf-8-sig',newline='') as h:
   w=csv.writer(h);w.writerow(names);w.writerows([[str(row['binary']) if name=='binary' else 55+10*row['z'] if name=='z' else 'external_site'+str(n%16) if name=='site' else row[name] for name in names] for n,row in enumerate(rows)])
  table={'path':str(file),'format':'csv','unselected_columns':[],'fields':[{'name':name,'column':name,'type':'string' if name in {'id','category','site','binary'} else 'number','missing_codes':['']} for name in names]};payload['rows']={'$csv_rows':'input'}
  run(method,operation,project,{'schema_version':'ye1-toolkit-draft@1.0','method_id':method,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(project),'local_tables':{'input':table},'task':task})

def functions(file,namespace):exec(compile(file.read_text(encoding='utf-8'),str(file),'exec'),namespace);return namespace
metadata=REPO/'tests/regression/fixture-sources/latent_longitudinal/tests';latent=functions(metadata/'fixtures.py',{'np':np,'VERSION':'latent-longitudinal-input@1.0'});formal=functions(metadata/'formal_fixtures.py',{'np':np,'copy':copy,'digest':rt.canonical});envelope=functions(metadata/'test_api.py',{'copy':copy,'digest':rt.canonical,'module':type('MetadataOnly',(),{'source_hashes':staticmethod(lambda:{})})()})
for method,project in [('exploration.cluster.kmeans',RP),('exploration.cluster.gmm',HP),('longitudinal.growth.gaussian',HP),('latent.profile.gaussian',RP),('latent.trajectory.gaussian',HP)]:
 if a.only and method not in a.only:continue
 train=project/'runs'/method.replace('.','-');model=track(train/'private/work/model.json');operation='assign' if method in {'exploration.cluster.kmeans','exploration.cluster.gmm','latent.profile.gaussian'} else 'predict'
 local=formal['request']('profile' if method=='latent.profile.gaussian' else 'trajectory',seed=2026103102) if method.startswith('latent.') else latent['growth_request'](seed=2026103103) if method=='longitudinal.growth.gaussian' else latent['cluster_request'](method,seed=2026103104)
 local['operation']=operation;local['spec']['cohort_id']='reload-external-3102';local['model_ref']={'path':str(model),'sha256':sha(model)}
 for row in local['rows']:row['sid']='reload-'+row['sid'];row.pop('split',None);row.pop('partition',None)
 q=formal['envelope'](local,project/'unused') if method.startswith('latent.') else envelope['make_request'](local,project/'unused');payload=q['payload'];data=payload['data'];names=list(data[0]);file=project/(AREA.name+'-'+method+'.csv')
 with file.open('x',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=names);w.writeheader();w.writerows(data)
 table={'path':str(file),'format':'csv','unselected_columns':[],'fields':[{'name':name,'column':name,'type':'string' if name=='sid' else 'number','missing_codes':['']} for name in names]};payload['data']={'$csv_rows':'input'};original=load(train/'private/task-snapshot.json');original.update(operation=operation,payload=payload);run(method,operation,project,{'schema_version':'ye1-toolkit-draft@1.0','method_id':method,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(project),'local_tables':{'input':table},'task':original})
assert all(sha(path)==expected for path,expected in MODELS.items());save(AREA/'model-integrity.json',{'all_original_models_unchanged':True,'files':MODELS});save(AREA/'receipt.json',{'status':'PASS' if all(x['status']=='PASS' for x in RESULTS) else 'FAIL','new_seeds':[2026103101,2026103102,2026103103,2026103104],'all_original_models_unchanged':True,'results':RESULTS});raise SystemExit(0 if all(x['status']=='PASS' for x in RESULTS) else 1)
