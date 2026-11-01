"""Compatibility plan entry: generated fixture, real routing, no stdin."""
from pathlib import Path
import argparse, csv, json, subprocess, sys
p=argparse.ArgumentParser();p.add_argument('--package',required=True);p.add_argument('--area',required=True);a=p.parse_args()
main=Path(a.package).resolve();project=Path(a.area).resolve();project.mkdir(parents=True,exist_ok=False);(project/'runs').mkdir()
source=project/'fixture.csv'
with source.open('x',encoding='utf-8',newline='') as f:
 w=csv.writer(f);w.writerow(['subject','age','exposure','arm','outcome','follow_days','event'])
 for i in range(40):w.writerow([f's{i}',30+i,1+i%8,'A' if i%2 else 'B',i%2,i+1,i%2])
plan={'schema_version':'ye1-analysis-plan@1.0','source':str(source),'project':str(project),'output':str(project/'runs/baseline'),'data_origin':'real','task_purpose':'research_analysis','study_id':'noninteractive_fixture','estimand':'Generated independent fixture subjects','independent_subjects':True,'method':'baseline.table1','fields':[{'name':'subject','type':'id','role':'id'},{'name':'age','type':'number','role':'descriptive_measure','unit':'year','dimension':'time'},{'name':'exposure','type':'number','role':'descriptive_measure'},{'name':'arm','type':'category','role':'stratification_label','levels':['A','B'],'reference':'A'}],'unselected_columns':['outcome','follow_days','event'],'baseline':{'group':'arm','categorical_denominator':'nonmissing','include_overall':True,'variables':[{'name':'age','type':'continuous','summary':'mean_sd','levels':[]},{'name':'exposure','type':'continuous','summary':'mean_sd','levels':[]},{'name':'arm','type':'categorical','summary':None,'levels':['A','B']}]}}
path=project/'plan.json';path.write_text(json.dumps(plan),encoding='utf-8');py=main/('.runtime/python/bin/python3' if sys.platform=='darwin' else '.runtime/python/Scripts/python.exe')
for name,args in [('compatibility',['authorize_project.py','--plan',str(path)]),('analysis',['analyze.py','run','--plan',str(path)])]:
 result=subprocess.run([str(py),'-I','-B','-X','utf8',str(main/'scripts'/args[0]),*args[1:]],stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf-8',timeout=500)
 (project/(name+'-call.json')).write_text(json.dumps({'exit':result.returncode,'stdout':result.stdout,'stderr':result.stderr},ensure_ascii=False,indent=2),encoding='utf-8')
 print(name,result.returncode,result.stdout,flush=True)
 if result.returncode:raise SystemExit(1)
assert (project/'runs/baseline/result.json').is_file()
assert not (project/'local-review').exists()
assert not list(project.rglob('terminal-*.txt'))
