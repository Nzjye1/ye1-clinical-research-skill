"""Existing R comparison/planning assets, with explicit standalone contracts."""
from pathlib import Path
import argparse,copy,csv,hashlib,json,math,os,re,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_toolkit import ROOT,CORE,BACKEND,load,save,sha,canonical,check,env
import ingestion as i
VERSION="ye1-compat-study@1.0"
TESTS={"compat.test.welch_t":("独立两组 Welch t 检验","welch_t"),"compat.test.paired_t":("配对 t 检验（每对一行）","paired_t"),"compat.test.wilcoxon_rank_sum":("两独立组 Wilcoxon 秩和检验","wilcoxon"),"compat.test.fisher_2x2":("2×2 Fisher 精确检验","fisher"),"compat.test.chi_square":("两组列联表 Pearson 卡方检验","chi_square")}
PLANNING={"compat.sample_size.mean_precision":("均值估计精度样本量","mean_precision"),"compat.sample_size.proportion_precision":("比例估计精度样本量","proportion_precision"),"compat.sample_size.two_mean":("独立两组均值差样本量","two_mean"),"compat.sample_size.two_proportion":("独立两组比例差样本量","two_proportion")}
def definitions():
    return [{"method_id":method,"backend_method_id":method,"title":title,"group":"legacy_comparison" if method in TESTS else "legacy_planning","task_family":"compat_test" if method in TESTS else "compat_planning","operations":["compare"] if method in TESTS else ["plan"],"numerical_owner":"unchanged legacy stats_worker.R","validation_owner":"explicit standalone contract + original R guards","limitations":["Existing restricted worker operation, not an additional general toolkit or cold-client validation claim"]} for method,(title,_) in {**TESTS,**PLANNING}.items()]
def plan_hash(task):
    value=copy.deepcopy(task);value.pop("plan_sha256",None);value["execution"].pop("output_dir",None);return canonical(value)
def _api():
    sys.path.insert(0,str(CORE/"python"));from clinical_methods import contracts as c
    return c
def schema(method):
    c=_api();obj=c.object_schema;text={"type":"string","minLength":1};nullable={"type":["string","null"]}
    if method in PLANNING:
        fields={"mean_precision":["sd","half_width","confidence"],"proportion_precision":["proportion","half_width","confidence"],"two_mean":["sd","difference","alpha","power"],"two_proportion":["p1","p2","alpha","power"]}[PLANNING[method][1]]
        return {"method_id":method,"parameters":obj({**{k:{"type":"number"} for k in fields},"design":{"const":"independent_simple_random"},"assumption_source":text,"loss_fraction":{"type":"number","minimum":0,"maximum":.999999}}),"operation":"plan","input":"Planning assumptions only; no patient rows, no post hoc observed power"}
    field=obj({"name":{"type":"string","pattern":"^[A-Za-z][A-Za-z0-9_]*$"},"type":{"enum":["number","integer","category","binary","string"]},"levels":{"type":"array","items":{"type":"string"}},"reference":nullable,"unit":text})
    design=obj({"row_unit":{"enum":["subject","independent_pair"]},"independent_units":{"const":True},"independence_basis":text,"research_question":text,"population":text,"estimand":text,"assumptions_review":text,"pairing_definition":nullable})
    comparison=obj({"outcome":text,"group":nullable,"paired_with":nullable,"group_order":{"type":"array","items":{"type":"string"}},"method":{"const":TESTS[method][1]},"missing":{"const":"complete_case"}})
    common=c.STUDY_SCHEMA["properties"]
    task=obj({"schema_version":{"const":VERSION},"study_id":{"type":"string","pattern":"^[A-Za-z][A-Za-z0-9_.-]{0,119}$"},"method_id":{"const":method},"operation":{"const":"compare"},"payload":obj({"dictionary":obj({"key":text,"fields":{"type":"array","items":field,"minItems":2}}),"design":design,"comparison":comparison,"rows":{"type":"array","items":{"type":"object"},"minItems":1}}),"data_origin":{"enum":["real","synthetic"]},"task_purpose":{"enum":["engineering_test","research_analysis"]},"project_root":text,"authorization":copy.deepcopy(common["authorization"]),"sources":copy.deepcopy(common["sources"]),"plan_sha256":{"type":"string","pattern":"^[a-f0-9]{64}$"},"execution":obj({"output_dir":text,"mode":{"const":"local"},"privacy_profile":{"const":"captured_local_process"},"authorization_ref":{"type":["string","null"]},"export_policy":{"const":"local_only"},"max_rows":{"type":"integer","minimum":1},"max_bytes":{"type":"integer","minimum":1},"max_decoded_bytes":{"type":"integer","minimum":1}})})
    return {"method_id":method,"input_version":VERSION,"task_envelope":task,"schema_only_no_execution_claim":True}
def _worker(payload,out):
    spec=load(ROOT/"runtime-spec.json");worker=ROOT/"_shared/compat/stats_worker.R";i.need(sha(worker)==spec["compat_worker_sha256"],"COMPAT_NUMERICAL_SOURCE_DRIFT");profile=load(ROOT/".runtime/toolkit-profile.json")
    private=out/"private";private.mkdir(parents=True,exist_ok=False);source=private/"worker-input.json";answer=private/"worker-output.json";save(source,payload)
    process_env=env();process_env.update(R_LIBS=os.pathsep.join([str(ROOT/".runtime/r-library"),str(Path(profile["R_home"])/"library")]),R_LIBS_USER=str(ROOT/".runtime/r-library"),R_LIBS_SITE="")
    with (private/"worker.log").open('xb') as stream:x=subprocess.run([profile["rscript"],"--vanilla",str(worker),str(source),str(answer)],env=process_env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
    i.need(x.returncode==0 and answer.is_file(),"COMPAT_R_WORKER_FAILED");return load(answer)
def _display(method,result,out,values):
    tables=out/"tables";figures=out/"figures";tables.mkdir();figures.mkdir();title=({**TESTS,**PLANNING})[method][0]
    with (tables/"summary.csv").open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['item','value']);writer.writerows(values)
    # Only display an effect/CI actually supplied by the original test. Rank
    # and chi-square tests receive no invented location effect or interval.
    summary=dict(values);effect=summary.get('estimate');interval=summary.get('ci95');finite=lambda x:type(x) in {int,float} and math.isfinite(x)
    contrast=method in {'compat.test.welch_t','compat.test.paired_t','compat.test.fisher_2x2'} and finite(effect) and isinstance(interval,list) and len(interval)==2 and all(finite(x) for x in interval)
    profile=load(ROOT/".runtime/toolkit-profile.json");payload=out/"private/display.json";save(payload,{"title":method,"unit":str(summary.get('unit','analysis_records')),"labels":[str(k) for k,v in values if isinstance(v,(int,float)) and k in {'n_used','analyzable_n','recruit_n'}],"values":[v for k,v in values if isinstance(v,(int,float)) and k in {'n_used','analyzable_n','recruit_n'}],"contrast":{'estimate':effect,'lower':interval[0],'upper':interval[1],'null':1 if method.endswith('fisher_2x2') else 0,'scale':'Conditional odds ratio' if method.endswith('fisher_2x2') else 'Mean difference (original outcome units)'} if contrast else None})
    process_env=env();process_env['R_LIBS_USER']=str(ROOT/'.runtime/r-library')
    with (out/"private/display.log").open('xb') as stream:x=subprocess.run([profile['rscript'],'--vanilla',str(ROOT/'scripts/plot_compat.R'),str(ROOT/'.runtime/r-library'),str(payload),str(figures/'denominator.png')],stdout=stream,stderr=subprocess.STDOUT,env=process_env,timeout=45)
    i.need(x.returncode==0 and (figures/'denominator.png').is_file(),"COMPAT_DISPLAY_INCOMPLETE")
    lines=['# '+title,'','计算与解释待科学复核；原始行和日志留本地。','',*[f'- {k}：{v}' for k,v in values],'','[完整摘要表](tables/summary.csv)','','![已有对比估计及区间（如原检验提供）与实际分母；或计划样本量](figures/denominator.png)','','图仅展示原数值输出。Wilcoxon/卡方或无有限区间时只展示实际分母，不虚构效应或置信区间。','检验不自动证明因果或临床意义；不为显著性更换方法。配对、独立性、分组顺序和缺失规则由本次计划明确声明。Wilcoxon 不自动等于中位数检验。卡方期望频数不足时拒绝，不自动改 Fisher。','' if method in TESTS else '样本量仅适用于声明的独立简单随机、等比例两组（如适用）及指定近似；两均值为共同SD的双侧t规划，不是Welch规划；不是聚类、生存、非劣效或模型开发样本量。',str(result.get('limitations','')),'','未经另行明确授权，不向对话或外部发送图表/报告。']
    (out/"报告.md").write_text('\n'.join(lines)+'\n',encoding='utf-8');save(out/'presentation-manifest.json',{'schema_version':'ye1-legacy-presentation@1.0','method_id':method,'result_sha256':sha(out/'result.json'),'scientific_review':'pending','automatic_export':False})
def planning(method,assumptions,out):
    i.need(method in PLANNING,"PLANNING_METHOD_REQUIRED");check(method);c=_api();i.need(Path(assumptions).stat().st_size<=65536,"PLANNING_ASSUMPTIONS_BYTE_LIMIT");value=load(assumptions);c.validate_schema(value,schema(method)['parameters']);out=Path(out).resolve();i.need(not out.exists() and out.parent.is_dir(),"FRESH_OUTPUT_DIRECTORY_REQUIRED")
    answer=_worker({'sample_size':{**value,'method':PLANNING[method][1]}},out);i.need(answer.get('status')=='COMPUTED_REVIEW_PENDING',"PLANNING_ASSUMPTIONS_REJECTED")
    result={'schema_version':'ye1-existing-planning-result@1.0','method_id':method,'execution_status':'complete','input_assumptions_sha256':sha(assumptions),'scientific_review':'pending','patient_records_processed':False,'numerical_owner':'unchanged legacy stats_worker.R',**answer};save(out/'result.json',result);_display(method,result,out,[(k,result[k]) for k in ['analyzable_n','recruit_n','unit','limitations']]);return {'status':'ANALYSIS_COMPLETED','method_id':method,'output':str(out),'scientific_review':'pending'}
def compare(method,path,validate_only=False):
    i.need(method in TESTS,"COMPARISON_METHOD_REQUIRED");check(method);i.need(Path(path).stat().st_size<=2_000_000,"NORMALIZED_TASK_BYTE_BUDGET_EXCEEDED");task=load(path);c=_api();c.validate_schema(task,schema(method)['task_envelope']);i.need(task['plan_sha256']==plan_hash(task),"COMPAT_PLAN_BINDING_MISMATCH")
    project=Path(task['project_root']).resolve();out=i.confined(task['execution']['output_dir'],project);i.need(not out.exists() and out!=project and out.parent.is_dir(),"FRESH_OUTPUT_DIRECTORY_REQUIRED")
    if task['data_origin']=='real' and not os.environ.get('YE1_STUDY_CAPTURED_RECEIPT'):
        sys.path.insert(0,str(BACKEND/'integration'));import captured_study
        value=captured_study.run(project,path,CORE,ROOT/'.clinical-local/agent-runtime.json',action='validate' if validate_only else 'run');i.need(value['returncode']==0,"CAPTURED_COMPAT_INVOCATION_FAILED");return value
    c._study_input.admit(task,CORE,vars(c),allowed_methods=frozenset(TESTS));i.verify(task,required=task['data_origin']=='real')
    i.need(len(task['sources'])==1 and task['sources'][0]['source_fingerprint']==canonical(task['payload']),"COMPAT_NORMALIZED_SOURCE_BINDING_MISMATCH")
    database=task['sources'][0]['database'].upper();i.need(database not in {'FAERS','JADER'},"REPORT_DATA_NOT_CLINICAL_PATIENTS");i.need(database not in {'NHANES','CHARLS'},"SURVEY_PROVIDER_INTEGRATION_PENDING");i.need(database in {'SELF_FILE','USER_CLINICAL','MIMIC','EICU','VITALDB','INSPIRE','MOVER'},"ADAPTER_NOT_VALIDATED")
    from clinical_methods import resource_budget
    limits=resource_budget.resolve(task['execution'],method);payload=task['payload'];rows=payload['rows'];i.need(len(rows)<=limits['max_rows'],"RESOURCE_ROW_BUDGET_EXCEEDED");dictionary=payload['dictionary'];fields=dictionary['fields'];names=[x['name'] for x in fields];i.need(len(names)==len(set(names)) and dictionary['key'] in names,"COMPAT_DICTIONARY_INVALID")
    types={x['name']:x for x in fields};ids=[r.get(dictionary['key']) for r in rows];i.need(all(isinstance(x,str) and x.strip() for x in ids) and len(set(ids))==len(ids),"COMPAT_UNIQUE_INDEPENDENT_UNITS_REQUIRED")
    for row in rows:
        i.need(set(row)==set(names),"COMPAT_ROW_FIELDS_MISMATCH")
        for name,value in row.items():
            field=types[name]
            if value is None:continue
            i.need(isinstance(value,(int,float)) and not isinstance(value,bool) if field['type'] in {'number','integer'} else isinstance(value,str),"COMPAT_FIELD_TYPE_INVALID")
            if field['type']=='integer':i.need(float(value).is_integer(),"INTEGER_VALUE_REQUIRED")
            if field['type'] in {'category','binary'}:i.need(value in field['levels'],"COMPAT_UNDECLARED_LEVEL")
    design=payload['design'];spec=payload['comparison'];used=[spec[x] for x in ['outcome','group','paired_with'] if spec[x] is not None];i.need(set(used)<=set(names),"COMPAT_SELECTED_FIELD_MISSING")
    if TESTS[method][1]=='paired_t':i.need(design['row_unit']=='independent_pair' and bool(design['pairing_definition']) and spec['paired_with'] is not None and spec['group'] is None and spec['group_order']==[],"EXPLICIT_WIDE_PAIR_DESIGN_REQUIRED")
    else:i.need(design['row_unit']=='subject' and spec['paired_with'] is None and spec['group'] is not None and len(spec['group_order'])==2 and len(set(spec['group_order']))==2,"EXPLICIT_TWO_INDEPENDENT_GROUPS_REQUIRED")
    if validate_only:return {'status':'CONTRACT_VALIDATED_NOT_EXECUTED','method_id':method}
    answer=_worker({'rows':rows,'dictionary':{'fields':fields},'tasks':[{'id':'comparison','kind':'compare',**spec}]},out);raw=answer['results'][0];i.need(raw['status']=='OK',"EXISTING_COMPARISON_GUARD_REJECTED")
    public={k:v for k,v in raw.items() if k not in {'source_rows'}};result={'schema_version':'ye1-existing-comparison-result@1.0','method_id':method,'execution_status':'complete','data_origin':task['data_origin'],'task_purpose':task['task_purpose'],'scientific_review':'pending','export_status':'local_only','test_only':task['task_purpose']=='engineering_test','plan_sha256':task['plan_sha256'],'numerical_owner':'unchanged legacy stats_worker.R','comparison':public};save(out/'result.json',result)
    values=[(k,v) for k,v in public.items() if k not in {'counts'}];_display(method,result,out,values);return {'status':'ANALYSIS_COMPLETED','method_id':method,'output':str(out),'scientific_review':'pending'}
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    for action in ['run','validate']:
        q=sub.add_parser(action);q.add_argument('--method',required=True);q.add_argument('--task',required=True)
    q=sub.add_parser('plan');q.add_argument('--method',required=True);q.add_argument('--assumptions',required=True);q.add_argument('--output',required=True);a=p.parse_args()
    value=planning(a.method,a.assumptions,a.output) if a.action=='plan' else compare(a.method,a.task,a.action=='validate');print(json.dumps(value,ensure_ascii=False))
if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    try:main()
    except (OSError,ValueError,KeyError,TypeError,ImportError,subprocess.TimeoutExpired) as error:
        print(json.dumps({'status':'blocked','reason_code':getattr(error,'code','COMPAT_INPUT_OR_RUNTIME_INVALID'),'action':'Keep private worker logs; clarify design/assumptions. No method substitution or automatic export occurred.'}));raise SystemExit(2)
