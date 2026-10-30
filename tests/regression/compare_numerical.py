"""Independent oracles on the new forward-test CSVs; optimizer sharing disclosed."""
from pathlib import Path
import ast,argparse,copy,csv,hashlib,json,math,os,subprocess,sys
REPO=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--area',required=True);p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--core-area',default=str(REPO/'.pilot-local/v03/core-forward-4'));p.add_argument('--references',default=str(REPO/'tests/regression/reference-sources'));a=p.parse_args();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False);MAIN=Path(a.package).resolve();CORE=MAIN/'_shared/clinical_analysis/integration/core';ORIGINAL=Path(a.references).resolve();sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as runtime
CP=next(x.parent for x in Path(a.core_area).glob('*/runs'));profile=runtime.load(MAIN/'.runtime/toolkit-profile.json');RS=profile['rscript'];ENV=runtime.env();ENV['CLINICAL_TEST_R_LIBRARIES']=os.pathsep.join([str(MAIN/'.runtime/r-library'),str(Path(profile['R_home'])/'library')]);ENV['R_LIBS']=ENV['CLINICAL_TEST_R_LIBRARIES'];ENV['R_LIBS_USER']=ENV['R_LIBS'];ENV['R_LIBS_SITE']=''
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(command,label):
 x=subprocess.run(list(map(str,command)),capture_output=True,text=True,encoding='utf-8',env=ENV,timeout=240);save(AREA/(label+'-command.json'),{'command':list(map(str,command)),'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr});assert x.returncode==0,(label,x.stderr);return x
COMPARE=[];cells=0
def number(got,want,tol):
 global cells
 assert got is not None and want is not None;got=float(got);want=float(want);assert math.isfinite(got) and math.isfinite(want);delta=abs(got-want);assert delta<=tol+tol*abs(want),(delta,tol);cells+=1;return delta
basic=AREA/'basic-reference.json';run([RS,'--vanilla',REPO/'tests/regression/reference_basic.R',CP/'common.csv',basic,MAIN/'.runtime/r-library'],'basic-reference');b=load(basic)
for label,key in [('association-linear','linear'),('association-logistic','logistic'),('survival-cox-association','cox')]:
 result=load(CP/'runs'/label/'result.json');got=result['estimates'];want=b[key];assert len(got)==len(want);delta=0
 for x,y in zip(got,want):
  for field,left,right in [('estimate',x['estimate'],y['estimate']),('se',x['standard_error'],y['standard_error']),('lo',x['ci']['lower'],y['lower']),('hi',x['ci']['upper'],y['upper']),('p',x['p'],y['p'])]:delta=max(delta,number(left,right,1e-5))
 COMPARE.append({'method':label,'reference':'independent R lm/HC3, glm or survival::coxph','status':'PASS','max_abs_difference':delta,'absolute_and_relative_tolerance':1e-5})
km=load(CP/'runs/survival-kaplan_meier/result.json')['survival']['curves'];delta=0
for x,y in zip(km,b['km']):
 for left,right in [(x['time'],y['time']),(x['n_at_risk'],y['n_at_risk']),(x['estimate'],y['estimate']),(x['ci']['lower'],y['lower']),(x['ci']['upper'],y['upper'])]:delta=max(delta,number(left,right,1e-10))
COMPARE.append({'method':'survival.kaplan_meier','reference':'survival::survfit log-log, explicit t-minus risk counts','status':'PASS','max_abs_difference':delta,'absolute_and_relative_tolerance':1e-10})
def raw_rows(task):
 view=task['views'][0];variables={v['name']:v for v in task['variables']};rows=[]
 with Path(view['local_ref']).open(encoding='utf-8-sig',newline='') as h:
  for r in csv.DictReader(h):
   item={}
   for name,column in view['column_map'].items():
    var=variables[name];value=r[column];item[name]=None if value in var['missing_codes'] else float(value) if var['dtype']=='number' else value
   rows.append(item)
 return rows
def helpers(name,functions,namespace):
 source=(ORIGINAL/'tests'/name).read_text(encoding='utf-8');tree=ast.parse(source);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in functions];assert len(nodes)==len(functions);path=AREA/name;path.write_text(ast.unparse(ast.Module(body=nodes,type_ignores=[])),encoding='utf-8');exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace);return namespace
for group,methods,reference,test,functions in [
 ('penalized',['prediction.continuous.signed.lasso','prediction.continuous.signed.elasticnet','prediction.binary.lasso','prediction.binary.elasticnet'],'penalized_v08_reference.R','test_penalized_v08_acceptance.py',['close','subset','table','individual','loaded_model','model_path','predictions','compare_reference']),
 ('cox_penalized',['prediction.survival.cox.lasso','prediction.survival.cox.elasticnet'],'cox_penalized_v10_reference.R','test_cox_penalized_v10_acceptance.py',['close','subset','table','predictions','model_path','bundle','compare_reference'])]:
 source=ORIGINAL/'tests'/reference;target=AREA/reference;target.write_bytes(source.read_bytes());assert sha(source)==sha(target)
 helper=helpers(test,functions,{'Path':Path,'json':json,'csv':csv,'math':math,'sys':sys,'load':load})
 for method in methods:
  out=CP/'runs'/method.replace('.','-');task=load(out/'private/task-snapshot.json');key='penalized_prediction' if group=='penalized' else 'cox_penalized_prediction';request={'mode':'train','spec':task['analysis'][key]['spec'],'rows':raw_rows(task)};input=AREA/(method+'-input.json');answer=AREA/(method+'-reference.json');save(input,request);run([RS,'--vanilla',target,input,answer],method)
  evidence=helper['compare_reference']({'out':out,'result':load(out/'result.json'),'task':task},load(answer));COMPARE.append({'method':method,'status':'PASS','independent_reference_source_sha256':sha(target),'reference_scope':'Independent preprocessing/CV and direct glmnet; shared optimizer, not independent optimizer or clinical validation','comparison':evidence})
  save(AREA/'receipt.json',{'status':'IN_PROGRESS','basic_numeric_cells':cells,'comparisons':COMPARE})
save(AREA/'receipt.json',{'status':'PASS','basic_numeric_cells':cells,'comparisons':COMPARE,'candidate_numerical_provider_called_by_oracles':False,'shared_engine':'glmnet only; base regression uses independent stats/survival implementations','source_data':'fresh seed 2026103017 CSVs, no historical fixture rows or patient data'})
print(json.dumps({'status':'PASS','comparisons':len(COMPARE),'basic_numeric_cells':cells},ensure_ascii=False))
