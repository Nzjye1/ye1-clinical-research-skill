"""Exact headers, bounded local mapping, refusal and recovery, synthetic only."""
from pathlib import Path
import argparse,copy,csv,gzip,hashlib,io,json,subprocess,sys,concurrent.futures
REPO=Path(__file__).resolve().parents[2];p=argparse.ArgumentParser();p.add_argument('--package',default=str(REPO/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--area',required=True);p.add_argument('--core-area',default=str(REPO/'.pilot-local/v03/core-forward-4'));p.add_argument('--rf-area',default=str(REPO/'.pilot-local/v03/module-forward-1'));p.add_argument('--hgb-area',default=str(REPO/'.pilot-local/v03/module-forward-2'));a=p.parse_args();MAIN=Path(a.package).resolve();AREA=Path(a.area).resolve();AREA.mkdir(parents=True,exist_ok=False);sys.path.insert(0,str(MAIN/'scripts'));import runtime_toolkit as rt
CP=next(x.parent for x in Path(a.core_area).glob('*/runs'));MP=next(x.parent for x in Path(a.rf_area).glob('*/runs'));PY=MAIN/('.runtime/python/bin/python3' if sys.platform=='darwin' else '.runtime/python/Scripts/python.exe')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def write_csv(p,header,rows):
 with p.open('x',encoding='utf-8-sig',newline='') as h:w=csv.writer(h);w.writerow(header);w.writerows(rows)
original_files={str(p):sha(p) for project in [CP,MP] for p in project.glob('*.csv')};results=[]
def call(label,command):
 x=subprocess.run(list(map(str,command)),stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',env=rt.env(),timeout=300);save(AREA/(label+'-command.json'),{'command':list(map(str,command)),'exit':x.returncode,'stdout':x.stdout,'stderr':x.stderr});assert 'DO_NOT_ECHO_PRIVATE_VALUE' not in x.stdout;return x
def replace(value,old,new):
 if isinstance(value,dict):return {k:replace(v,old,new) for k,v in value.items()}
 if isinstance(value,list):return [replace(v,old,new) for v in value]
 return new if value==old else value
def prepare(label,draft,expect=None,practice=False):
 project=Path(draft['project_root']);file=project/(AREA.name+'-'+label+'-draft.json');save(file,draft);cmd=[PY,'-I','-B',MAIN/'scripts/prepare_task.py','--draft',file]+(['--practice'] if practice else []);x=call(label+'-prepare',cmd)
 if expect:
  assert x.returncode==2,(label,x.stdout);value=load_json(x.stdout);assert value['reason_code']==expect,(label,value);assert not Path(draft['task']['execution']['output_dir']).exists();return {'case':label,'status':'PASS','refused':expect}
 assert x.returncode==0,(label,x.stdout);return load_json(x.stdout)['task']
def load_json(s):return json.loads(s)
def execute(label,draft,expected_code=None):
 task=prepare(label,draft);x=call(label+'-run',[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',draft['method_id'],'--task',task]);out=Path(draft['task']['execution']['output_dir'])
 if expected_code:
  assert x.returncode==2 and load_json(x.stdout)['reason_code']==expected_code and not out.exists(),(label,x.stdout);return {'case':label,'status':'PASS','refused':expected_code}
 assert x.returncode==0 and (out/'result.json').is_file() and list((out/'figures').glob('*.png')) and (out/'报告.md').is_file(),(label,x.stdout);return {'case':label,'status':'PASS','output':str(out),'task':task}
def core_positive(method):
 label='chinese-'+method.replace('.','-');draft=load(CP/(method+'-draft.json'));old=Path(draft['task']['views'][0]['local_ref']);file=CP/(AREA.name+'-'+label+'.csv')
 with old.open(encoding='utf-8-sig',newline='') as h:raw=list(csv.reader(h))
 names={name:'中文 列_'+name for name in raw[0]};write_csv(file,[names[x] for x in raw[0]],raw[1:]);draft=replace(draft,str(old),str(file));draft['task']['execution']['output_dir']=str(CP/'runs'/(AREA.name+'-'+label))
 for view in draft['task']['views']:view['column_map']={k:names[v] for k,v in view['column_map'].items()};view['unselected_columns']=[names[v] for v in view['unselected_columns']]
 value=execute(label,draft);got=load(Path(value['output'])/'result.json');want=load(CP/'runs'/method.replace('.','-')/'result.json')
 def clean(v):
  if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k not in {'result_id','source_result_ids'}}
  if isinstance(v,list):return [clean(x) for x in v]
  return v
 assert clean({k:got[k] for k in ['counts','estimates','survival']})==clean({k:want[k] for k in ['counts','estimates','survival']});value['same_numeric_and_semantic_results_as_ascii']=True;return value
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for value in pool.map(core_positive,['baseline.table1','association.logistic','survival.kaplan_meier','survival.cox.association']):results.append(value);save(AREA/'receipt.json',{'results':results})
base=load(MP/'exploration.cluster.kmeans-draft.json');table=base['local_tables']['input'];old=Path(table['path'])
with old.open(encoding='utf-8-sig',newline='') as h:raw=list(csv.reader(h))
def case(label):
 d=copy.deepcopy(base);out=MP/'runs'/(AREA.name+'-'+label);d['task']['execution']['output_dir']=str(out);d['task']['payload']['work_dir']=str(out/'private/work');return d
mixed=case('mixed-header');file=MP/(AREA.name+'-mixed.csv');header=raw[0][:];header[0]='sid';write_csv(file,header,raw[1:]);mixed['local_tables']['input']['path']=str(file);mixed['local_tables']['input']['fields'][0]['column']='sid';results.append(execute('mixed-header',mixed))
negative=[]
d=case('duplicate-source');file=MP/(AREA.name+'-duplicate.csv');header=raw[0][:];header[1]=header[0];write_csv(file,header,raw[1:]);d['local_tables']['input']['path']=str(file);negative.append(('duplicate-source',d,'CSV_HEADER_INVALID'))
d=case('mapping-collision');d['local_tables']['input']['fields'][1]['column']=d['local_tables']['input']['fields'][0]['column'];negative.append(('mapping-collision',d,'COLUMN_MAP_NOT_ONE_TO_ONE'))
d=case('missing-column');d['local_tables']['input']['fields'][1]['column']='不存在的列';negative.append(('missing-column',d,'CSV_UNDECLARED_OR_MISSING_COLUMN'))
d=case('duplicate-canonical');d['local_tables']['input']['fields'][1]['name']=d['local_tables']['input']['fields'][0]['name'];negative.append(('duplicate-canonical',d,'FIELD_NAMES_INVALID'))
d=case('exclusion-overlap');d['local_tables']['input']['unselected_columns']=[d['local_tables']['input']['fields'][1]['column']];negative.append(('exclusion-overlap',d,'COLUMN_PROJECTION_CONFLICT'))
d=case('nonfinite');file=MP/(AREA.name+'-nonfinite.csv');bad=copy.deepcopy(raw);bad[1][2]='NaN';write_csv(file,bad[0],bad[1:]);d['local_tables']['input']['path']=str(file);negative.append(('nonfinite',d,'NONFINITE_INPUT_VALUE'))
d=case('private-invalid-value');file=MP/(AREA.name+'-invalid-number.csv');bad=copy.deepcopy(raw);bad[1][2]='DO_NOT_ECHO_PRIVATE_VALUE';write_csv(file,bad[0],bad[1:]);d['local_tables']['input']['path']=str(file);negative.append(('private-invalid-value',d,'NUMERIC_VALUE_INVALID'))
d=case('row-budget');d['task']['execution']['max_rows']=20;negative.append(('row-budget',d,'ROW_BUDGET_EXCEEDED_NO_SAMPLING'))
d=case('zero-budget');d['task']['execution']['max_rows']=0;negative.append(('zero-budget',d,'RESOURCE_BUDGET_INVALID'))
d=case('decoded-budget');d['task']['execution']['max_decoded_bytes']=50;negative.append(('decoded-budget',d,'DECODED_BYTE_BUDGET_EXCEEDED'))
d=case('not-utf8');file=MP/(AREA.name+'-not-utf8.csv');file.write_bytes(b'\xff\xfe\x81\x82\x83');d['local_tables']['input']['path']=str(file);negative.append(('not-utf8',d,'UTF8_CSV_REQUIRED'))
d=case('method-mismatch');d['task']['method_id']='exploration.cluster.gmm';negative.append(('method-mismatch',d,'DRAFT_METHOD_MISMATCH'))
d=case('synthetic-research');d['task_purpose']=d['task']['task_purpose']='research_analysis';negative.append(('synthetic-research',d,'ORIGIN_PURPOSE_CONFLICT'))
d=case('real-missing-file');d['data_origin']=d['task']['data_origin']='real';d['task_purpose']=d['task']['task_purpose']='research_analysis';d['task']['sources'][0]['source_kind']='user_clinical_file';d['local_tables']['input']['path']=str(MP/'missing-file.csv');negative.append(('real-missing-file',d,'INPUT_FILE_MISSING_OR_BYTE_BUDGET'))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for value in pool.map(lambda x:prepare(x[0],x[1],x[2]),negative):results.append(value);save(AREA/'receipt.json',{'results':results})
d=case('real-practice');d['data_origin']=d['task']['data_origin']='real';d['task_purpose']=d['task']['task_purpose']='research_analysis';results.append(prepare('real-practice',d,'PRACTICE_CANNOT_AUTHORIZE_REAL_DATA',practice=True))
d=case('changed-source');file=MP/(AREA.name+'-changed.csv');file.write_bytes(old.read_bytes());d['local_tables']['input']['path']=str(file);task=prepare('changed-source',d);rawbytes=file.read_bytes();position=rawbytes.index(b'0');file.write_bytes(rawbytes[:position]+b'1'+rawbytes[position+1:]);x=call('changed-source-run',[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',d['method_id'],'--task',task]);assert x.returncode==2 and load_json(x.stdout)['reason_code']=='SOURCE_CHANGED_AFTER_PREPARATION' and not Path(d['task']['execution']['output_dir']).exists();results.append({'case':'changed-source-after-preparation','status':'PASS','refused':'SOURCE_CHANGED_AFTER_PREPARATION'})
for label,method,mutate in [('future-feature','association.logistic',lambda t:t['variables'][1].update(available_at=100)),('missing-outcome','association.logistic',lambda t:t['analysis']['spec'].update(outcome='missing_outcome')),('missing-survival-time','survival.kaplan_meier',lambda t:t['analysis']['survival'].update(time='missing_time'))]:
 d=load(CP/(method+'-draft.json'));d['task']['execution']['output_dir']=str(CP/'runs'/(AREA.name+'-'+label));mutate(d['task']);task=prepare(label,d);x=call(label+'-run',[PY,'-I','-B',MAIN/'scripts/toolkit.py','run','--method',method,'--task',task]);assert x.returncode==2 and not Path(d['task']['execution']['output_dir']).exists();results.append({'case':label,'status':'PASS','refused':load_json(x.stdout)['reason_code']})
assert all(sha(path)==digest for path,digest in original_files.items());assert not (MP/'.ye1-privacy/choice.json').exists()
save(AREA/'receipt.json',{'status':'PASS','cases':len(results),'results':results,'all_original_source_CSVs_unchanged':True,'actual_real_data_or_user_authorization_tested':False,'no_real_choice_created':True,'no_private_sentinel_in_stdout':True});print(json.dumps({'status':'PASS','cases':len(results)}))
