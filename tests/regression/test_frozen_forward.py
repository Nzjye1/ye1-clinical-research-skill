"""Frozen native models: independent new subjects, no retraining or origin change."""
from pathlib import Path
import argparse,copy,csv,hashlib,json,math,random,subprocess,sys
REPO=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--area',required=True);p.add_argument('--core-area',default=str(REPO/'.pilot-local/v03/core-forward-4'));p.add_argument('--rf-area',default=str(REPO/'.pilot-local/v03/module-forward-1'));p.add_argument('--hgb-area',default=str(REPO/'.pilot-local/v03/module-forward-2'));a=p.parse_args();MAIN=Path(a.package).resolve();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as runtime
CORE=MAIN/'_shared/clinical_analysis/integration/core';sys.path.insert(0,str(CORE/'python'));from clinical_methods import contracts as c
PY=MAIN/'.runtime/python/Scripts/python.exe'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def project(area):return next(x for x in (REPO/'.pilot-local/v03'/area).iterdir() if x.is_dir() and (x/'runs').is_dir())
CP=next(x.parent for x in Path(a.core_area).glob('*/runs'));RP=next(x.parent for x in Path(a.rf_area).glob('*/runs'));HP=next(x.parent for x in Path(a.hgb_area).glob('*/runs'))
SEED=2026103050;rng=random.Random(SEED);header=['id','x','z','group','y','binary','category','site','time','label_ready','patient_id','partition','fold','age','severity','sex','outcome','duration','event','status'];rows=[]
for n in range(160):
 x=rng.gauss(0,1);z=rng.gauss(0,1);sex='F' if n%2==0 else 'M';eventtime=rng.expovariate(.05*math.exp(.2*x-.15*z));censor=rng.uniform(12,30);duration=min(eventtime,censor,30);event=int(eventtime<=min(censor,30));outcome=.5+.4*x+rng.gauss(0,1);binary=int(rng.random()<1/(1+math.exp(-(.25+.35*x-.2*z))))
 rows.append(dict(zip(header,[f'external03-{n}',x,z,'A' if n%2==0 else 'B',outcome,binary,str(n%2),'external_site'+str(n%16),duration,30,f'external03-{n}','holdout',0,55+10*z,rng.gauss(0,1),sex,outcome,duration,event,str(event)])))
source=CP/'fresh-external-3050.csv'
with source.open('x',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=header);w.writeheader();w.writerows(rows)
RESULTS=[];FILES={}
def run(label,method,project,task,tables=None):
 draft={'schema_version':'ye1-toolkit-draft@1.0','method_id':method,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(project),'local_tables':tables or {},'task':task};path=project/(label+'-draft.json');save(path,draft);calls=[]
 for action in ['prepare','run']:
  cmd=[str(PY),'-I','-B','-X','utf8',str(MAIN/'scripts/prepare_task.py'),'--draft',str(path)] if action=='prepare' else [str(PY),'-I','-B','-X','utf8',str(MAIN/'scripts/toolkit.py'),'run','--method',method,'--task',prepared]
  x=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',env=runtime.env(),timeout=900);calls.append({'command':cmd,'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr});save(AREA/(label+'-calls.json'),calls)
  if x.returncode:
   result={'label':label,'method':method,'status':'FAIL','stage':action,'response':x.stdout};RESULTS.append(result);save(AREA/'receipt.json',{'new_seed':SEED,'results':RESULTS});print(json.dumps(result,ensure_ascii=False),flush=True);return None
  if action=='prepare':prepared=json.loads(x.stdout)['task']
 out=Path(task['execution']['output_dir']);result=load(out/'result.json');assert result['execution_status']=='complete';assert list((out/'tables').glob('*.csv'));assert list((out/'figures').glob('*.png'));assert (out/'报告.md').is_file()
 item={'label':label,'method':method,'status':'PASS','output':str(out),'task':prepared,'tables':len(list((out/'tables').glob('*.csv'))),'figures':len(list((out/'figures').glob('*.png')))};RESULTS.append(item);save(AREA/'receipt.json',{'new_seed':SEED,'results':RESULTS});print(json.dumps(item,ensure_ascii=False),flush=True);return out
def track(path):FILES[str(path)]=sha(path);return path
def promote(task,method):
 task.update(schema_version='clinical-study-input@1.0',data_origin='synthetic',task_purpose='engineering_test',project_root=str(CP),authorization=None,purpose='interpretation' if method.startswith('interpretation.') else 'survival')
 task['execution'].update(mode='local',authorization_ref=None,max_rows=1000,max_bytes=2_000_000,max_decoded_bytes=4_000_000);task['time'].update(policy='ordered_observation',analysis_as_of=task['time']['label_mature_at'])
 for s in task['sources']:s.update(database='SELF_FILE',verification_status='local_bytes_bound',source_kind='synthetic_fixture',snapshot='new-external-3050',evidence_refs=['fresh external synthetic seed 2026103050'],source_fingerprint={'$file_sha256':str(source)})
 for v in task['views']:v.update(local_ref=str(source),content_hash={'$file_sha256':str(source)},format='csv',location_policy='project_local',unselected_columns=[h for h in header if h not in v['column_map']])
 return task
def evaluation_options():return {'estimator':'marginal_reverse_km_ipcw','censoring_source':'evaluation_cohort','censoring_assumption':'independent_of_event_time_and_model_features','tie_order':'events_before_censoring','min_censoring_survival':.05,'max_ipcw_weight':20,'positivity_policy':'reject_no_clipping','roc_thresholds':[0,.2,.5,.8,1],'calibration':{'method':'ipcw_hajek_fixed_bins','probability_edges':[0,1],'min_bin_n':2},'dca_thresholds':[.1,.3,.5],'uncertainty':'not_implemented','prespecified':True}
model=track(CP/'runs/prediction-survival-cox/private/frozen_cox_model.json');method='evaluation.survival.cox.ipcw';task=c.make_survival_evaluation_task(source,CP/'runs/frozen-cox-evaluation',CORE,database='SELF_FILE',model_ref=model,model_sha256=sha(model),horizons=[5,10,20],canonical_identity_namespace='fresh-2026103017',evaluation_options=evaluation_options());run('frozen-cox-evaluation',method,CP,promote(task,method))
model=track(CP/'runs/prediction-continuous-signed-lasso/private/penalized-model.json');explainer=track(model.with_name('linear-explainer.json'));spec=copy.deepcopy(load(model)['model']['spec']);spec['cohort_id']='new-external-3050'
opts={'model_method_id':'prediction.continuous.signed.lasso','spec':spec,'model_ref':{'local_ref':str(model),'content_hash':sha(model)},'explainer_ref':{'local_ref':str(explainer),'content_hash':sha(explainer)}};method='interpretation.linear.interventional';bounded=CP/'fresh-bounded-external-3051.csv';bounded_rows=copy.deepcopy(rows);bounded_rng=random.Random(2026103051)
for n,row in enumerate(bounded_rows):row.update(id='bounded-new-'+str(n),patient_id='bounded-new-'+str(n),age=bounded_rng.uniform(50,60),severity=bounded_rng.uniform(-.25,.25))
with bounded.open('x',encoding='utf-8-sig',newline='') as h:w=csv.DictWriter(h,fieldnames=header);w.writeheader();w.writerows(bounded_rows)
oldsource=source;source=bounded
task=c.make_interpretation_task(source,CP/'runs/frozen-linear-interpretation',CORE,database='SELF_FILE',interpretation_options=opts);run('frozen-linear-interpretation',method,CP,promote(task,method));source=oldsource

def module_task(method,operation,payload,project,out):
 return {'schema_version':'clinical-module-task@1.1','study_id':'frozen_'+operation+'_'+method.replace('.','_'),'method_id':method,'operation':operation,'payload':payload,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(project),'authorization':None,'plan_sha256':'0'*64,'execution':{'output_dir':str(out),'mode':'local','privacy_profile':'captured_local_process','authorization_ref':None,'export_policy':'local_only','max_rows':1000,'max_bytes':2_000_000,'max_decoded_bytes':4_000_000},'sources':[{'source_id':'new_external','database':'SELF_FILE','snapshot':'fresh-3050','period':'synthetic only','recipe_version':'explicit-mapping-1','recipe_hash':digest({'method':method,'operation':operation}),'source_fingerprint':'0'*64,'evidence_refs':['new synthetic external CSV; original frozen model files'],'verification_status':'local_bytes_bound','source_kind':'synthetic_fixture'}]}
for prediction,project in [('random_forest',RP),('hist_gradient_boosting',HP)]:
 method='explanation.binary.'+prediction+'.tree_shap';training=project/'runs'/('prediction-binary-'+prediction);response=load(training/'private/module-response.json');frozen=track(training/'private/frozen-model.json') if (training/'private/frozen-model.json').exists() else training/'private/frozen-shap-model.json'
 # The integration saves the actual model text inside the private response.
 frozen=project/(prediction+'-frozen-3050.json');frozen.write_text(response['private_record']['frozen_model_json'],encoding='utf-8');track(frozen);background=track(training/'private/training-background.json')
 taskpath=load(Path(a.rf_area if prediction=='random_forest' else a.hgb_area)/'receipt.json')['results'];trainingtask=load(next(x['task'] for x in taskpath if x['method']=='prediction.binary.'+prediction));payload=copy.deepcopy(trainingtask['payload']);payload['spec']['cohort_id']='new-external-3050';payload['data_contract']['missing']['fit_scope']='frozen_only';payload.pop('explain_with_outcomes')
 payload.update(rows={'$csv_rows':'input'},frozen_model_json={'$file_text':str(frozen)},application_scope='external',background_artifact_json={'$file_text':str(background)},background_sha256={'$json_value':{'path':str(background),'keys':['sha256']}},feature_perturbation='interventional')
 file=project/(prediction+'-new-external-3050.csv');names=['id','x','z','category','site','time','label_ready']
 with file.open('x',encoding='utf-8-sig',newline='') as h:
  w=csv.writer(h);w.writerow(['中文_'+x for x in names]);w.writerows([[('explain-external-'+str(n) if k=='id' else 55+10*rows[n]['z'] if k=='z' else 0 if k=='time' else 24 if k=='label_ready' else rows[n][k]) for k in names] for n in range(4)])
 table={'path':str(file),'format':'csv','unselected_columns':[],'fields':[{'name':x,'column':'中文_'+x,'type':'string' if x in {'id','category','site'} else 'number','missing_codes':['']} for x in names]}
 out=project/'runs'/('frozen-'+prediction+'-shap');run('frozen-'+prediction+'-shap',method,project,module_task(method,'explain',payload,project,out),{'input':table})

model=track(CP/'runs/prediction-survival-cox-lasso/private/cox-penalized-model.json');wrapper=load(model);m=wrapper['model'];s=m['spec'];sem=m['semantics'];variables=[{'name':s['id'],'dtype':'id','role':'subject','unit':'1','measured_at':None,'available_at':None}]+[{'name':f['name'],'dtype':f['type'],'role':'feature','unit':sem['features'][n]['unit'],'measured_at':-2,'available_at':-1} for n,f in enumerate(s['features'])]+[{'name':s['duration'],'dtype':'number','role':'duration','unit':'day','measured_at':None,'available_at':None},{'name':s['event'],'dtype':'number','role':'event','unit':'1','measured_at':None,'available_at':None}]
structure={'grain':'subject_wide','subject_key':s['id'],'group_key':None,'time_origin':0,'time_unit':'day','independent_subjects':True,'weights':'none','delayed_entry':False,'recurrent_events':False,'canonical_identity_namespace':s['canonical_identity_namespace'],'feature_cutoff':0,'analysis_as_of':30,'label_mature_at':30}
record={'subject_id':{'$field':'patient_id'},'group_id':None,'values':[{'$field':f['name']} for f in s['features']],'duration':{'$field':'duration'},'event':{'$field':'event'}}
table={'path':str(source),'format':'csv','unselected_columns':[h for h in header if h not in {'patient_id','age','severity','sex','duration','event'}],'fields':[{'name':x,'column':x,'type':'string' if x in {'patient_id','sex'} else 'number','missing_codes':['']} for x in ['patient_id','age','severity','sex','duration','event']],'record':record}
base={'model_json':{'$file_text':str(model)},'explainer_json':None,'model_method_id':m['method_id'],'cohort_id':'new-ce-external-3050','horizons':[7,14],'structure':structure,'variables':variables,'rows':{'$csv_rows':'input'},'evaluation':evaluation_options(),'display_domains':[]}
method='evaluation.survival.cox.penalized.ipcw';run('frozen-penalized-cox-evaluation',method,CP,module_task(method,'evaluate',base,CP,CP/'runs/frozen-penalized-cox-evaluation'),{'input':table})
method='interpretation.survival.cox.penalized.interventional';freeze=copy.deepcopy(base);freeze.update(rows=[],evaluation=None);freeze['structure']['label_mature_at']=None
freeze['display_domains']=[{'feature':f['name'],'type':f['type'],'unit':sem['features'][n]['unit'],'minimum':20 if f['name']=='age' else -6 if f['type']=='number' else None,'maximum':100 if f['name']=='age' else 6 if f['type']=='number' else None,'levels':m['preprocessor']['features'][n]['levels'] if f['type']=='category' else [],'prespecified':True,'source_note':'Fixed synthetic display bounds before application, not selected from fitted effects.'} for n,f in enumerate(s['features'])]
out=run('frozen-penalized-cox-explainer',method,CP,module_task(method,'fit_explainer',freeze,CP,CP/'runs/frozen-penalized-cox-explainer'))
if out:
 response=load(out/'private/module-response.json');file=CP/'frozen-cox-explainer-3050.json';file.write_text(response['private_record']['explainer_json'],encoding='utf-8');track(file);payload=copy.deepcopy(base);payload.update(explainer_json={'$file_text':str(file)},evaluation=None);payload['structure']['label_mature_at']=None;et=copy.deepcopy(table);et['record']['duration']=None;et['record']['event']=None;run('frozen-penalized-cox-explain',method,CP,module_task(method,'explain',payload,CP,CP/'runs/frozen-penalized-cox-explain'),{'input':et})
assert all(sha(path)==expected for path,expected in FILES.items()),'Original frozen artifact changed'
save(AREA/'model-integrity.json',{'all_original_frozen_files_unchanged':True,'files':FILES})
raise SystemExit(0 if all(x['status']=='PASS' for x in RESULTS) else 1)
