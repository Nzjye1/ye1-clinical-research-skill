"""New-seed public draft -> preparation -> native owner -> table/plot/report tests."""
from pathlib import Path
import argparse,copy,csv,json,math,random,subprocess,sys,concurrent.futures
REPO=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--area',required=True);p.add_argument('--methods',nargs='*');args=p.parse_args();MAIN=Path(args.package).resolve();AREA=Path(args.area).resolve();AREA.mkdir(parents=True,exist_ok=False);PROJECT=AREA/'中文 客户合成研究';PROJECT.mkdir();CORE=MAIN/'_shared/clinical_analysis/integration/core'
sys.path.insert(0,str(CORE/'python'));from clinical_methods import contracts as c
sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as runtime
PY=MAIN/'.runtime/python/Scripts/python.exe';rng=random.Random(2026103017);N=480
HEADER=['id','x','z','group','y','binary','category','site','time','label_ready','patient_id','partition','fold','age','severity','sex','outcome','duration','event','status']
records=[]
for n in range(N):
 x=rng.gauss(0,1);z=rng.gauss(0,1);category=n%2;group='A' if n%2==0 else 'B';age=55+10*z;severity=rng.gauss(0,1);sex='F' if n%2==0 else 'M'
 prob=1/(1+math.exp(-(.25+.35*x-.2*z+.2*category)));binary=int(rng.random()<prob);score=1+.5*x-.25*z+.3*category+rng.gauss(0,1)
 failure=rng.expovariate(.05*math.exp(.2*x-.15*z+.15*category));censor=rng.uniform(12,30);duration=min(failure,censor,30);event=int(failure<=min(censor,30))
 records.append(dict(zip(HEADER,[f'fresh{n:04}',x,z,group,score,binary,category,'S1' if n%3 else 'S2',duration,30,f'fresh{n:04}','train' if n<360 else 'holdout',n%3+1 if n<360 else 0,age,severity,sex,score,duration,event,str(event)])))
def save(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
sources={}
for label in ['common','binomial','nonnegative','prediction']:
 path=PROJECT/(label+'.csv')
 with path.open('x',encoding='utf-8-sig',newline='') as stream:
  writer=csv.DictWriter(stream,fieldnames=HEADER);writer.writeheader()
  for source in records:
   row=copy.deepcopy(source)
   if label=='binomial':row['outcome']=row['binary']
   if label=='nonnegative':row.update(y=math.exp(.1*row['y']),time=0,label_ready=24)
   if label=='prediction':row.update(time=0,label_ready=24)
   writer.writerow(row)
 sources[label]=path

def initial(method):
 out=PROJECT/'runs'/method.replace('.','-');source=sources['common']
 if method in {'association.linear','association.logistic','baseline.table1'}:
  task=c.make_example_task(source,out,CORE,database='SELF_FILE')
  if method=='association.logistic':
   task['analysis']['spec'].update(model='logistic',outcome='binary',covariance='model',event='1',non_event='0');task['analysis'].update(effect_scale='odds_ratio',variance='model');task['outcome'].update(field='binary',type='binary',event='1',non_event='0',definition='New synthetic Bernoulli endpoint')
  elif method=='baseline.table1':task.update(purpose='descriptive',outcome=None);task['analysis'].update(spec=None,effect_scale='descriptive',variance='not_applicable')
  task['analysis']['method_id']=method
 elif method.endswith('.plan'):task=c.make_association_plan_task(source,out,CORE,method_id=method,database='SELF_FILE')
 elif method in {'survival.kaplan_meier','survival.cox.association'}:
  task=c.make_formal_ph_task(source,out,CORE,database='SELF_FILE') if method=='survival.cox.association' else c.make_survival_task(source,out,CORE,method_id=method,database='SELF_FILE')
 elif method=='prediction.survival.cox':task=c.make_cox_prediction_task(source,out,CORE,database='SELF_FILE',training_subjects=[r['id'] for r in records[:360]],holdout_subjects=[r['id'] for r in records[360:]],horizons=[0,5,10,20],canonical_identity_namespace='fresh-2026103017')
 elif method.startswith('prediction.survival.cox.'):
  task=c.make_cox_penalized_task(source,out,CORE,database='SELF_FILE',method_id=method)
 elif method.startswith(('prediction.continuous.signed.','prediction.binary.lasso','prediction.binary.elasticnet')):
  if method.startswith('prediction.binary.'):source=sources['binomial']
  task=c.make_penalized_task(source,out,CORE,database='SELF_FILE',method_id=method)
 elif method in {'prediction.binary.ridge','prediction.continuous.nonnegative.ridge'}:
  source=sources['prediction'] if method=='prediction.binary.ridge' else sources['nonnegative'];task=c.make_prediction_task(source,out,CORE,database='SELF_FILE',method_id=method)
  if method=='prediction.continuous.nonnegative.ridge':
   # Explicit feature clocks are zero; the source's time column is not selected
   # as a predictor. The old predictor contract still requires its declared
   # scheduling metadata to be compatible.
   pass
 elif method=='causal.psm.att.continuous':
  task=c.make_psm_task(source,out,CORE,database='SELF_FILE')
  # PSM declares binary treatment separately from the endpoint.
  task['variables'][1]['name']='binary';task['views'][0]['column_map'].pop('treatment');task['views'][0]['column_map']['binary']='binary';task['analysis']['psm']['treatment']='binary'
 else:raise ValueError(method)
 task.update(schema_version='clinical-study-input@1.0',data_origin='synthetic',task_purpose='engineering_test',project_root=str(PROJECT),authorization=None)
 task['purpose']='descriptive' if method=='baseline.table1' else 'survival' if method.startswith(('survival.','prediction.survival.')) else 'prediction' if method.startswith('prediction.') else 'association'
 task['study_id']='new_'+method.replace('.','_');task['execution'].update(mode='local',authorization_ref=None,max_rows=1000,max_bytes=2_000_000,max_decoded_bytes=4_000_000)
 task['time']['policy']='ordered_observation'
 for s in task['sources']:s.update(database='SELF_FILE',verification_status='local_bytes_bound',source_kind='synthetic_fixture',snapshot='fresh-2026103017',evidence_refs=['new synthetic fixture seed 2026103017']);s['source_fingerprint']={'$file_sha256':str(source)}
 for view in task['views']:
  view.update(local_ref=str(source),format='csv',unselected_columns=[h for h in HEADER if h not in view['column_map']],location_policy='project_local');view['content_hash']={'$file_sha256':str(source)}
 return task

methods=args.methods or ['baseline.table1','association.linear','association.logistic','association.linear.plan','association.logistic.plan','prediction.continuous.nonnegative.ridge','prediction.binary.ridge','prediction.continuous.signed.lasso','prediction.continuous.signed.elasticnet','prediction.binary.lasso','prediction.binary.elasticnet','survival.kaplan_meier','survival.cox.association','prediction.survival.cox','prediction.survival.cox.lasso','prediction.survival.cox.elasticnet','causal.psm.att.continuous']
def execute(method):
 try:
  task=initial(method);draft={'schema_version':'ye1-toolkit-draft@1.0','method_id':method,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(PROJECT),'local_tables':{},'task':task};path=PROJECT/(method+'-draft.json');save(path,draft)
  commands=[]
  for action in ['prepare','run']:
   cmd=[str(PY),'-I','-B','-X','utf8',str(MAIN/'scripts/prepare_task.py'),'--draft',str(path)] if action=='prepare' else [str(PY),'-I','-B','-X','utf8',str(MAIN/'scripts/toolkit.py'),'run','--method',method,'--task',prepared]
   x=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',env=runtime.env(),timeout=500);commands.append({'command':cmd,'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr})
   save(AREA/(method+'-calls.json'),commands)
   if x.returncode:return {'method':method,'status':'FAIL','stage':action,'response':x.stdout}
   if action=='prepare':prepared=json.loads(x.stdout)['task']
  out=Path(task['execution']['output_dir']);result=json.loads((out/'result.json').read_text(encoding='utf-8'));assert result['execution_status']=='complete';assert list((out/'tables').glob('*.csv'));assert list((out/'figures').glob('*.png'));assert (out/'报告.md').is_file();assert (out/'presentation-manifest.json').is_file()
  return {'method':method,'status':'PASS','task':prepared,'output':str(out),'result_status':result['execution_status'],'tables':len(list((out/'tables').glob('*.csv'))),'figures':len(list((out/'figures').glob('*.png')))}
 except Exception as error:return {'method':method,'status':'FAIL','stage':'driver_assertion','error':str(error)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=[]
 for result in pool.map(execute,methods):results.append(result);save(AREA/'receipt.json',{'seed':2026103017,'new_synthetic_rows':N,'results':results});print(json.dumps(result,ensure_ascii=False),flush=True)
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
