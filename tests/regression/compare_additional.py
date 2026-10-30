"""Baseline, PH, PSM and legacy primitives supplement the first ten oracles."""
from pathlib import Path
import argparse,ast,copy,csv,hashlib,json,math,os,subprocess,sys
REPO=Path(__file__).resolve().parents[2];parser=argparse.ArgumentParser();parser.add_argument('--area',required=True);parser.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));parser.add_argument('--core-area',default=str(REPO/'.pilot-local/v03/core-forward-4'));parser.add_argument('--references',default=str(REPO/'tests/regression/reference-sources'));parser.add_argument('--legacy-area',default=str(REPO/'.pilot-local/v03/legacy-forward-2'));parser.add_argument('--numerical-area',default=str(REPO/'.pilot-local/v03/numerical-1'));a=parser.parse_args();MAIN=Path(a.package).resolve();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False);ORIGINAL=Path(a.references).resolve();sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as rt
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
CP=next(x.parent for x in Path(a.core_area).glob('*/runs'));LP=next(x.parent for x in Path(a.legacy_area).glob('*/runs'));b=load(Path(a.numerical_area)/'basic-reference.json');cells=0
def number(x,y,tol=1e-8):
 global cells
 assert x is not None and y is not None;x=float(x);y=float(y);assert math.isfinite(x) and math.isfinite(y);d=abs(x-y);assert d<=tol+tol*abs(y),(d,tol);cells+=1;return d
results=[];stats=load(CP/'runs/baseline-table1/private/backend.json')['statistics'];overall=next(x for x in stats if x['variable']=='x' and x['group']=='overall');ref=b['baseline'];d=0
for x,y in [(overall['mean'],ref['x_mean']),(overall['sd'],ref['x_sd']),(overall['median'],ref['x_quantiles']['50%']),(overall['q1'],ref['x_quantiles']['25%']),(overall['q3'],ref['x_quantiles']['75%']),(overall['n'],ref['n'])]:d=max(d,number(x,y,1e-10))
for level in ['A','B']:
 row=next(x for x in stats if x['variable']=='group' and x['level']==level and x['group']=='overall');d=max(d,number(row['n'],ref['group_counts'][level]),number(row['proportion'],ref['group_counts'][level]/ref['n']))
results.append({'method':'baseline.table1','status':'PASS','reference':'base R full-precision mean/SD/type7 quantiles and category counts','max_abs_difference':d})
ph=load(CP/'runs/survival-cox-association/private/backend.json')['ph_test']['table'];d=0
for got,want in zip(ph,b['ph']):
 assert got['term']==want['_row']
 for x,y in [(got['chisq'],want['chisq']),(got['df'],want['df']),(got['p_value'],want['p'])]:d=max(d,number(x,y))
results.append({'method':'survival.cox.association/formal_ph','status':'PASS','reference':'survival::cox.zph transform km terms/global','max_abs_difference':d})
profile=rt.load(MAIN/'.runtime/toolkit-profile.json');ENV=rt.env();ENV['CLINICAL_TEST_R_LIBRARIES']=os.pathsep.join([str(MAIN/'.runtime/r-library'),str(Path(profile['R_home'])/'library')]);ENV['R_LIBS']=ENV['CLINICAL_TEST_R_LIBRARIES'];ENV['R_LIBS_USER']=ENV['R_LIBS'];ENV['R_LIBS_SITE']=''
def run(code,input,output,label,extra=None):
 command=[profile['rscript'],'--vanilla',str(code),str(input),str(output),*(extra or [])];x=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env=ENV,timeout=180);save(AREA/(label+'-command.json'),{'command':command,'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr,'reference_sha256':sha(code)});assert x.returncode==0,x.stderr;return load(output)
psm=CP/'runs/causal-psm-att-continuous';task=load(psm/'private/task-snapshot.json');view=task['views'][0];variables={v['name']:v for v in task['variables']};rows=[]
with Path(view['local_ref']).open(encoding='utf-8-sig',newline='') as h:
 for source in csv.DictReader(h):rows.append({name:None if source[column] in variables[name]['missing_codes'] else float(source[column]) if variables[name]['dtype']=='number' else source[column] for name,column in view['column_map'].items()})
raw=load(psm/'private/backend.json');input=AREA/'psm-input.json';save(input,{'mode':'analyze','rows':rows,'options':raw['options'],'semantics':raw['semantics']});source=ORIGINAL/'tests/psm_v07_reference.R';code=AREA/source.name;code.write_bytes(source.read_bytes());answer=run(code,input,AREA/'psm-reference.json','psm')
helper=ORIGINAL/'tests/test_psm_v07_acceptance.py';text=helper.read_text(encoding='utf-8');tree=ast.parse(text);names={'close','subset','table','private_table','effect_compare','compare_reference'};nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]+[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='EFFECT_NUMERIC' for k in n.targets)];script=AREA/'psm-comparison-functions.py';script.write_text(ast.unparse(ast.Module(body=nodes,type_ignores=[])),encoding='utf-8');namespace={'Path':Path,'math':math,'copy':copy,'csv':csv,'load':load};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(script),'exec'),namespace);evidence=namespace['compare_reference']({'out':psm,'result':load(psm/'result.json')},answer);results.append({'method':'causal.psm.att.continuous','status':'PASS','reference':'Independent glm + distance-table matching + paired t and balance equations; shared base stats, not MatchIt validation','comparison':evidence})
source=REPO/'tests/regression/reference_legacy.R';code=AREA/source.name;code.write_bytes(source.read_bytes());answer=run(code,LP/'中文 原表.csv',AREA/'legacy-reference.json','legacy',[str(MAIN/'.runtime/r-library')])
for method,item in answer['tests'].items():
 got=load(LP/'runs'/('compat-test-'+method)/'result.json')['comparison'];d=number(got['p'],item['p'])
 for key in ['estimate','ci95']:
  if item[key] is None:assert got.get(key) is None
  elif isinstance(item[key],list):
   for x,y in zip(got[key],item[key]):d=max(d,number(x,y))
  else:d=max(d,number(got[key],item[key]))
 results.append({'method':'compat.test.'+method,'status':'PASS','reference':'direct stats primitive, production worker not sourced','max_abs_difference':d})
for method,want in answer['planning'].items():
 got=load(LP/'runs'/('compat-sample_size-'+method)/'result.json');d=max(number(got['analyzable_n'],want['analyzable_n']),number(got['recruit_n'],want['recruit_n']));results.append({'method':'compat.sample_size.'+method,'status':'PASS','reference':'direct qnorm/power.t.test/power.prop.test, fixed assumptions','max_abs_difference':d})
save(AREA/'receipt.json',{'status':'PASS','scalar_numeric_cells_excluding_detailed_psm':cells,'comparisons':results,'patient_data_used':False,'references_call_candidate_numerical_provider':False});print(json.dumps({'status':'PASS','comparisons':len(results),'scalar_cells_excluding_detailed_psm':cells}))
