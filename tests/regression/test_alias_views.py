"""Alias plan guards and byte-identical existing-result views; no new view fit."""
from pathlib import Path
import argparse,copy,hashlib,json,subprocess,sys
REPO=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--core-area',default=str(REPO/'.pilot-local/v03/core-forward-4'));p.add_argument('--area',required=True);a=p.parse_args();MAIN=Path(a.package).resolve();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False);CP=next(x.parent for x in Path(a.core_area).glob('*/runs'));CORE=MAIN/'_shared/clinical_analysis/integration/core';sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as rt
PY=MAIN/('.runtime/python/bin/python3' if sys.platform=='darwin' else '.runtime/python/Scripts/python.exe');ns={'copy':copy};source=REPO/'tests/regression/fixture-sources/core/association_plan.py';exec(compile(source.read_text(encoding='utf-8'),str(source),'exec'),ns)
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
results=[]
def call(label,command):
 x=subprocess.run(list(map(str,command)),stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',env=rt.env(),timeout=300);save(AREA/(label+'-call.json'),{'command':list(map(str,command)),'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr});return x
def record(value):results.append(value);save(AREA/'receipt.json',{'results':results});print(json.dumps(value,ensure_ascii=False),flush=True)
for leaf in ['adjusted','sensitivity','subgroup','rcs']:
 for kind in ['linear','logistic']:
  method='association.'+leaf+'.'+kind;label=AREA.name+'-'+method.replace('.','-');draft=load(CP/('association.'+kind+'.plan-draft.json'));draft['method_id']=method;task=draft['task'];task['execution']['output_dir']=str(CP/'runs'/label);plan=ns['make_plan'](kind,'rcs' if leaf=='rcs' else 'subgroup' if leaf=='subgroup' else 'sequence')
  if leaf=='adjusted':plan['models']=plan['models'][:2]
  task['analysis']['association']=plan;file=CP/(label+'-draft.json');save(file,draft);x=call(label+'-prepare',[PY,'-I','-B',MAIN/'scripts/prepare_task.py','--draft',file]);phase='prepare'
  if x.returncode==0:prepared=json.loads(x.stdout)['task'];x=call(label+'-run',[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',method,'--task',prepared]);phase='run'
  value={'method':method,'status':'PASS' if x.returncode==0 else 'FAIL','stage':phase,'response':x.stdout}
  if x.returncode==0:
   out=Path(task['execution']['output_dir']);r=load(out/'result.json');assert r['method_id']=='association.'+kind+'.plan';assert list((out/'tables').glob('*.csv')) and list((out/'figures').glob('*.png')) and (out/'报告.md').is_file();value.update(output=str(out),task=prepared,shared_backend=r['method_id'])
  record(value)
  # Wrong leaf plan must fail before any numerical result is created.
  if leaf in {'rcs','subgroup','sensitivity'}:
   base=load(CP/('association.'+kind+'.plan-draft.json'));base['method_id']=method;base['task']['execution']['output_dir']=str(CP/'runs'/(label+'-wrong-leaf'));wrong=CP/(label+'-wrong-draft.json');save(wrong,base);x=call(label+'-wrong-prepare',[PY,'-I','-B',MAIN/'scripts/prepare_task.py','--draft',wrong]);assert x.returncode==0;private=json.loads(x.stdout)['task'];x=call(label+'-wrong-run',[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',method,'--task',private]);assert x.returncode==2 and json.loads(x.stdout)['reason_code']=='LEAF_SCOPE_MISMATCH' and not Path(base['task']['execution']['output_dir']).exists();record({'method':method,'negative':'wrong leaf refused before fit','status':'PASS'})
mapping={'result.baseline.table':'baseline-table1','result.association.effects':'association-logistic','result.binary.roc':'prediction-binary-ridge','result.binary.calibration':'prediction-binary-ridge','result.binary.dca':'prediction-binary-ridge','result.importance':'frozen-linear-interpretation','result.nomogram':'frozen-linear-interpretation','result.survival.roc':'frozen-cox-evaluation','result.survival.calibration':'frozen-cox-evaluation','result.survival.dca':'frozen-cox-evaluation','result.survival.ph':'survival-cox-association'}
for method,folder in mapping.items():
 label=AREA.name+'-'+method.replace('.','-');source=CP/'runs'/folder;out=CP/'runs'/label;task={'schema_version':'ye1-result-view-request@1.1','method_id':method,'operation':'export_existing','source_result':{'path':str(source/'result.json'),'sha256':sha(source/'result.json')},'source_manifest':{'path':str(source/'agent-artifacts.json'),'sha256':sha(source/'agent-artifacts.json')},'output_dir':str(out),'export_policy':'local_only','project_root':str(CP),'data_origin':'synthetic','task_purpose':'engineering_test','execution':{'mode':'local','privacy_profile':'captured_local_process'}};file=CP/(label+'-view.json');save(file,task);before={str(x):sha(x) for x in source.rglob('*') if x.is_file()};x=call(label,[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',method,'--task',file]);value={'method':method,'status':'PASS' if x.returncode==0 else 'FAIL','response':x.stdout}
 if x.returncode==0:
  view=load(out/'result-view.json');assert view['numerical_execution_count']==0 and view['files'];assert all(sha(out/f['relative_path'])==f['sha256']==sha(source/f['relative_path']) for f in view['files']);assert all(sha(path)==digest for path,digest in before.items());value.update(output=str(out),copied_files=len(view['files']),new_fits=0,all_copied_bytes_equal=True)
 record(value)
raise SystemExit(0 if all(x['status']=='PASS' for x in results) else 1)
