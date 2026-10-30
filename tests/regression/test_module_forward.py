"""New CSVs through public preparation and all independent module owners."""
from pathlib import Path
import argparse,ast,copy,csv,hashlib,json,math,random,subprocess,sys,concurrent.futures
import numpy as np
REPO=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--area',required=True);p.add_argument('--methods',nargs='*');a=p.parse_args();MAIN=Path(a.package).resolve();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False);PROJECT=AREA/'中文 模块研究';PROJECT.mkdir();OWNER=MAIN/'_shared/clinical_analysis/modules';ORIGINAL=REPO/'tests/regression/fixture-sources'
sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as runtime
PY=MAIN/'.runtime/python/Scripts/python.exe'
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def metadata_functions(relative,names,namespace):
 source=(ORIGINAL/relative).read_text(encoding='utf-8');tree=ast.parse(source);selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert len(selected)==len(names)
 snapshot=AREA/'generator-sources'/relative;snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_text(ast.unparse(ast.Module(body=selected,type_ignores=[])),encoding='utf-8')
 exec(compile(ast.Module(body=selected,type_ignores=[]),str(snapshot),'exec'),namespace);return namespace
latent=metadata_functions('latent_longitudinal/tests/fixtures.py',['cluster_request','growth_request'],{'np':np,'VERSION':'latent-longitudinal-input@1.0'})
formal=metadata_functions('latent_longitudinal/tests/formal_fixtures.py',['request','envelope'],{'np':np,'copy':copy,'digest':digest})
latent_envelope=metadata_functions('latent_longitudinal/tests/test_api.py',['make_request'],{'copy':copy,'digest':digest,'module':type('FixtureMetadataOnly',(),{'source_hashes':staticmethod(lambda:{})})()})
tree=metadata_functions('nonlinear_prediction/tests/support.py',['specification'],{'RF':'prediction.binary.random_forest','HGB':'prediction.binary.hist_gradient_boosting'})
mm=metadata_functions('mediation_matching/tests/make_fixtures.py',['spec'],{})

def csv_table(method,rows,record=None,types=None):
 names=list(rows[0]);labels={n:'源列_'+n for n in names};file=PROJECT/(method+'.csv')
 with file.open('x',encoding='utf-8-sig',newline='') as h:
  w=csv.writer(h);w.writerow([labels[n] for n in names]);w.writerows([[r[n] if r[n] is not None else '' for n in names] for r in rows])
 fields=[{'name':n,'column':labels[n],'type':(types or {}).get(n,'number' if isinstance(next((r[n] for r in rows if r[n] is not None),''),(int,float)) else 'string'),'missing_codes':['']} for n in names]
 table={'path':str(file),'fields':fields,'format':'csv','unselected_columns':[]}
 if record is not None:table['record']=record
 return table

def payload(method,out):
 if method.startswith(('exploration.','latent.','longitudinal.')):
  if method=='latent.profile.gaussian':q=formal['envelope'](formal['request']('profile',seed=2026103031),out/'private/work')
  elif method=='latent.trajectory.gaussian':q=formal['envelope'](formal['request']('trajectory',seed=2026103032),out/'private/work')
  else:
   local=latent['growth_request'](seed=2026103033) if method=='longitudinal.growth.gaussian' else latent['cluster_request'](method,seed=2026103034)
   q=latent_envelope['make_request'](local,out/'private/work')
  rows=q['payload']['data'];q['payload']['data']={'$csv_rows':'input'};return q['payload'],csv_table(method,rows)
 if method.startswith('prediction.binary.'):
  rng=np.random.default_rng(2026103035);n=520;x=rng.normal(size=n);z=rng.normal(50,10,n);g=rng.integers(0,2,n);eta=-.3+.35*x+.35*x*(z-50)/10+.3*g;y=rng.binomial(1,1/(1+np.exp(-eta)))
  rows=[{'id':'fresh-module-'+str(i),'x':float(x[i]),'z':float(z[i]),'category':str(g[i]),'binary':str(y[i]),'site':'site'+str(i%20),'time':0.,'label_ready':24.} for i in range(n)]
  spec=tree['specification'](method,split='group',calibration='none');spec['tuning']['candidates']=spec['tuning']['candidates'][:1];spec['explanation']={'permutation_repeats':2,'pdp_features':['x']}
  kinds={'id':('id','id','1'),'x':('number','feature','1'),'z':('number','feature','year'),'category':('category','feature','1'),'binary':('category','outcome','1'),'site':('category','split','1'),'time':('number','time','hour'),'label_ready':('number','label_time','hour')}
  dc={'grain':'subject','subject_key':'id','record_keys':['id'],'group_key':'site','identity_namespace':'fresh-module-2026103035','fields':[{'name':name,'dtype':kind,'role':role,'unit':unit,'occurred_at':24 if role=='outcome' else 0,'available_at':24 if role=='outcome' else 0} for name,(kind,role,unit) in kinds.items()],'independent_subjects':True,'time':{'unit':'hour','origin':'synthetic baseline','prediction_at':0,'outcome_start':0,'outcome_end':24,'analysis_as_of':24},'missing':{'strategy':'train_median_mode','fit_scope':'training_only'},'weights':{'kind':'none','field':None}}
  return {'rows':{'$csv_rows':'input'},'spec':spec,'data_contract':dc,'frozen_model_json':None,'explain_with_outcomes':False,'application_scope':'development'},csv_table(method,rows,types={'binary':'category','category':'category'})
 kind='mediation' if method.startswith('mediation.') else 'binary' if method.endswith('.binary') else 'survival';s=mm['spec'](kind);s.pop('execution');s['schema_version']='mediation-matching-admitted-spec@1.0';s['semantics']['population']='New synthetic independent subjects seed 2026103036'
 rng=random.Random(2026103036);rows=[]
 for j in range(180):
  x=rng.gauss(0,1);z=rng.gauss(0,1)
  for exposure in (0,1):
   mediator=.6+.8*exposure+.2*x+rng.gauss(0,.7);outcome=.5+.4*exposure+.7*mediator+.2*exposure*mediator+.2*x+rng.gauss(0,.8);event=rng.expovariate(.1*math.exp(.3*exposure));censor=rng.uniform(4,25)
   row={'id':f'fresh-mm-{j}-{exposure}','A':exposure,'x':x,'z':z}
   if kind=='mediation':row.update(M=mediator,Y=outcome)
   elif kind=='binary':row['Y']=int(rng.random()<1/(1+math.exp(-(-.3+.3*exposure+.2*x))))
   else:row.update(T=min(event,censor),E=int(event<=censor))
   rows.append(row)
 fs=s['fields'];sem=s['semantics'];roles={name:role for role,name in fs.items() if name is not None}|{'x':'covariate','z':'covariate'};variables=[]
 for name,role in roles.items():
  clock={'covariate':-1,'exposure':0,'mediator':1,'outcome':30}.get(role);unit='day' if role=='time' else sem['outcome_unit'] if role=='outcome' else '1'
  variables.append({'name':name,'role':role,'dtype':'id' if role=='subject' else 'number','unit':unit,'time_role':{'subject':'identifier','exposure':'exposure','covariate':'baseline','mediator':'mediator','outcome':'outcome','time':'followup_duration','event':'event_at_followup'}[role],'measured_at':clock,'available_at':clock})
 st={'grain':'subject_wide','subject_key':'id','record_keys':['id'],'cluster_key':None,'weights':'none','missingness':s['options']['missingness'],'time_origin':0,'time_unit':'day','analysis_as_of':30}
 record={'subject_id':{'$field':'id'},'exposure':{'$field':'A'},'covariates':[{'$field':'x'},{'$field':'z'}]}
 for role in ('mediator','outcome','time','event'):record[role]={'$field':fs[role]} if fs[role] else None
 return {'spec':s,'structure':st,'variables':variables,'rows':{'$csv_rows':'input'}},csv_table(method,rows,record)

methods=a.methods or ['prediction.binary.random_forest','prediction.binary.hist_gradient_boosting','exploration.cluster.kmeans','exploration.cluster.gmm','longitudinal.growth.gaussian','latent.profile.gaussian','latent.trajectory.gaussian','mediation.linear.binary_exposure','causal.psm.att.binary','causal.psm.matched.survival']
def execute(method):
 try:
  out=PROJECT/'runs'/method.replace('.','-');data,table=payload(method,out)
  task={'schema_version':'clinical-module-task@1.1','study_id':'new_'+method.replace('.','_'),'method_id':method,'operation':'train' if method.startswith(('prediction.','exploration.','latent.','longitudinal.')) else 'analyze','payload':data,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(PROJECT),'authorization':None,'plan_sha256':'0'*64,'execution':{'output_dir':str(out),'mode':'local','privacy_profile':'captured_local_process','authorization_ref':None,'export_policy':'local_only','max_rows':1000,'max_bytes':2_000_000,'max_decoded_bytes':4_000_000},'sources':[{'source_id':'new_csv','database':'SELF_FILE','snapshot':'fresh-2026103030','period':'synthetic only','recipe_version':'explicit-mapping-1','recipe_hash':digest(table),'source_fingerprint':'0'*64,'evidence_refs':['new synthetic CSV generation; no patient records'],'verification_status':'local_bytes_bound','source_kind':'synthetic_fixture'}]}
  draft={'schema_version':'ye1-toolkit-draft@1.0','method_id':method,'data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(PROJECT),'local_tables':{'input':table},'task':task};path=PROJECT/(method+'-draft.json');save(path,draft);calls=[]
  for action in ['prepare','run']:
   cmd=[str(PY),'-I','-B','-X','utf8',str(MAIN/'scripts/prepare_task.py'),'--draft',str(path)] if action=='prepare' else [str(PY),'-I','-B','-X','utf8',str(MAIN/'scripts/toolkit.py'),'run','--method',method,'--task',prepared]
   x=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',env=runtime.env(),timeout=1200);calls.append({'command':cmd,'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr});save(AREA/(method+'-calls.json'),calls)
   if x.returncode:return {'method':method,'status':'FAIL','stage':action,'response':x.stdout}
   if action=='prepare':prepared=json.loads(x.stdout)['task']
  result=json.loads((out/'result.json').read_text(encoding='utf-8'));assert result['execution_status']=='complete';assert list((out/'tables').glob('*.csv'));assert list((out/'figures').glob('*.png'));assert (out/'报告.md').is_file();assert (out/'presentation-manifest.json').is_file()
  return {'method':method,'status':'PASS','task':prepared,'output':str(out),'tables':len(list((out/'tables').glob('*.csv'))),'figures':len(list((out/'figures').glob('*.png')))}
 except Exception as error:return {'method':method,'status':'FAIL','stage':'driver_assertion','error':str(error)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=[]
 for result in pool.map(execute,methods):results.append(result);save(AREA/'receipt.json',{'fresh_seeds':[2026103031,2026103032,2026103033,2026103034,2026103035,2026103036],'results':results});print(json.dumps(result,ensure_ascii=False),flush=True)
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
