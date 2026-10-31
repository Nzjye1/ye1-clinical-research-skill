"""One stable local facade over the registered clinical analysis owners."""
from pathlib import Path
import argparse,copy,datetime,importlib.util,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];BACKEND=ROOT/"_shared/clinical_analysis";INTEGRATION=BACKEND/"integration"
sys.path.insert(0,str(ROOT/"scripts"))

class Blocked(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
def need(ok,code):
    if not ok:raise Blocked(code)
def load(p):
    p=Path(p);need(p.stat().st_size<=2*1024*1024,"METADATA_BYTE_LIMIT")
    def pairs(items):
        result={}
        for k,v in items:need(k not in result,"DUPLICATE_JSON_KEY");result[k]=v
        return result
    return json.loads(p.read_text(encoding="utf-8-sig"),object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(Blocked("NONFINITE_JSON")))
def catalog():
    value=load(BACKEND/"agent/catalog.json")
    from legacy_analysis import definitions
    value["methods"]+=definitions();return value
def definition(method):
    matches=[x for x in catalog()["methods"] if x["method_id"]==method];need(len(matches)==1,"METHOD_NOT_SUPPORTED");return matches[0]
def kind(d):
    if d["task_family"] in {"compat_test","compat_planning"}:return d["task_family"]
    if d["task_family"]=="result_view":return "existing_result_view"
    if d["task_family"]=="real_engineering":return "legacy_restricted"
    return "alias" if d["method_id"]!=d["backend_method_id"] else "backend"
def schema(d):
    if d["task_family"] in {"compat_test","compat_planning"}:
        from legacy_analysis import schema as legacy_schema
        return legacy_schema(d["method_id"])
    need(kind(d)!="legacy_restricted","LEGACY_ENGINEERING_ENTRY_NOT_A_GENERAL_CUSTOMER_METHOD")
    version="ye1-result-view-request@1.1" if d["task_family"]=="result_view" else "clinical-module-task@1.1" if d["task_family"]=="module" else "clinical-study-input@1.0"
    if d["task_family"]=="core":
        # Export the very factories used by validate_task, rather than the old
        # frozen legacy-version union. This changes no execution contract.
        sys.path.insert(0,str(INTEGRATION/"core/python"))
        from clinical_methods import contracts as c
        method=d["backend_method_id"]
        if method in c._association_plan_admission.METHODS:
            document=c._association_plan_admission.make_schema(c.STUDY_SCHEMA,c.ASSOCIATION_PLAN_SCHEMA)
        elif method==c._psm_v07_admission.METHOD:
            document=c._psm_v07_admission.make_schema(c.STUDY_SCHEMA,c.PSM_V07_SCHEMA)
        else:
            document=c._real_family_admission.schema_for_task({"analysis":{"method_id":method}},c.STUDY_SCHEMA,vars(c))
        document=copy.deepcopy(document);document["properties"]["analysis"]["properties"]["method_id"]={"const":method}
        if method=="survival.cox.association":
            ph=c._real_family_admission.schema_for_task({"analysis":{"method_id":method,"survival":{"ph_test":{}}}},c.STUDY_SCHEMA,vars(c))
            ph["properties"]["analysis"]["properties"]["method_id"]={"const":method}
            document={"anyOf":[document,ph]}
        return {"method_id":d["method_id"],"backend_method_id":method,"input_version":version,"task_envelope":document,"parameters":document,"schema_source":"original validate_task schema factories","schema_only_no_dependency_or_execution_claim":True}
    if d["task_family"]=="module":
        legacy=load(INTEGRATION/"module-lock.json");selected=load(INTEGRATION/"admitted-module-lock.json")
        owner=next(x for x in legacy["modules"] if d["backend_method_id"] in x["methods"])
        key=owner.get("registration_id",owner["directory"]);descriptor=selected["modules"][key]
        payload=descriptor["methods"][d["backend_method_id"]]["schemas"].get("payload")
        task=load(INTEGRATION/"contracts/module-task-origin.schema.json")
        task["properties"]["method_id"]={"const":d["backend_method_id"]}
        task["properties"]["operation"]={"enum":descriptor["methods"][d["backend_method_id"]]["operations"]}
        task["properties"]["payload"]=load(BACKEND/"modules"/owner["directory"]/payload) if payload else load(INTEGRATION/d["schema_resource"])
        return {"method_id":d["method_id"],"backend_method_id":d["backend_method_id"],"input_version":version,"task_envelope":task,"schema_only_no_dependency_or_execution_claim":True}
    path=BACKEND/"agent/analysis_call.py";spec=importlib.util.spec_from_file_location("native_schema_only",path);native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    selection=copy.deepcopy(d);selection["input_schema_version"]=version
    return {**native.schema(INTEGRATION,selection),"input_version":version,"schema_only_no_dependency_or_execution_claim":True}
def doctor(method):
    profile=ROOT/".runtime/toolkit-profile.json";need(profile.is_file(),"TOOLKIT_INSTALLATION_REQUIRED")
    from runtime_windows import check
    return check(method=method)
def execute(method,task_path,validate_only=False):
    d=definition(method);need(kind(d)!="legacy_restricted","LEGACY_ENGINEERING_ENTRY_NOT_A_GENERAL_CUSTOMER_METHOD")
    doctor(method);task_path=Path(task_path).resolve();task=load(task_path)
    need(task.get("schema_version") in {"clinical-study-input@1.0","clinical-module-task@1.1","ye1-result-view-request@1.1","ye1-compat-study@1.0"},"CURRENT_ORIGIN_AWARE_TASK_REQUIRED")
    need(task.get("data_origin") in {"real","synthetic"},"DATA_ORIGIN_REQUIRED")
    if task["data_origin"]=="real" and d["task_family"]!="result_view":
        need(any(ref.startswith("ye1-ingestion-v1:") for source in task.get("sources",[]) for ref in source.get("evidence_refs",[])),"LOCAL_PREPARATION_RECEIPT_REQUIRED")
    project=Path(task["project_root"]).resolve();out=Path(task["output_dir"] if d["task_family"]=="result_view" else task["execution"]["output_dir"]).resolve()
    need(project.is_dir() and task_path.is_relative_to(project) and out.is_relative_to(project) and out!=project,"TASK_AND_OUTPUT_INSIDE_PROJECT_REQUIRED")
    if not validate_only:
        reason="OUTPUT_ALREADY_EXISTS" if out.exists() else None
        if reason is None and d["task_family"] in {"core","module"}:
            attempt=out.parent/"private"
            if any((attempt/(out.name+suffix)).exists() for suffix in [".task.json",".agent-call.json",".console.log"]):reason="OUTPUT_SNAPSHOT_ALREADY_EXISTS"
        if reason:
            return {"status":"blocked","reason_code":reason,"method_id":method,"output":str(out),
                    "analysis_executed":False,"existing_output_and_attempt_evidence_preserved":True,
                    "action":"This invocation did not execute analysis. Choose a new output name; retain the existing output and prior attempt files."},2
    private=project/"private/entry-logs";private.mkdir(parents=True,exist_ok=True);log=private/(datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")+".log")
    from runtime_windows import env
    command=[sys.executable,"-B","-X","utf8",str(BACKEND/"agent/analysis_call.py"),"--catalog",str(BACKEND/"agent/catalog.json"),"--runtime",str(ROOT/".clinical-local/agent-runtime.json"),"validate" if validate_only else "run",method,"--task",str(task_path)]
    if d["task_family"]=="compat_test":command=[sys.executable,"-I","-B","-X","utf8",str(ROOT/"scripts/legacy_analysis.py"),"validate" if validate_only else "run","--method",method,"--task",str(task_path)]
    with log.open("xb") as stream:done=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,env=env(),cwd=ROOT,timeout=1800)
    response={"status":"CONTRACT_VALIDATED_NOT_EXECUTED" if validate_only else "ANALYSIS_COMPLETED","method_id":method,"output":str(out),"scientific_review":"pending","support_log":str(log)}
    if done.returncode:
        response["status"]="blocked";response["reason_code"]="NATIVE_ANALYSIS_NOT_COMPLETE"
        last={}
        try:
            last=json.loads(log.read_text(encoding="utf-8").strip().splitlines()[-1]);code=last.get("reason_code")
            if isinstance(code,str) and re.fullmatch(r"[A-Z][A-Z0-9_]+",code):response["reason_code"]=code
        except (ValueError,OSError,IndexError):pass
        # An existing result alone cannot prove this invocation computed it.
        # Only the native execution summary for this selected method/output
        # can classify a newly computed partial/presentation failure.
        current=(not validate_only and last.get("executed_task_count")==1 and last.get("selected_method_id")==method and
                 isinstance(last.get("result"),str) and Path(last["result"]).resolve()==out/"result.json")
        if current and (out/"result.json").is_file():
            result=load(out/"result.json")
            if result.get("execution_status") in {"complete","partial"}:
                response.update(status="ANALYSIS_COMPUTED_ARTIFACT_REVIEW_REQUIRED",reason_code="LOCAL_PRESENTATION_OR_PARTIAL_RESULT")
    return response,0 if done.returncode==0 else 2
def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest="action",required=True)
    fixture=sub.add_parser("public-fixture",help="Offline, fixed-hash public acceptance fixture only")
    for name in ("fixture","source","output","rscript"):fixture.add_argument("--"+name,required=True)
    sub.add_parser("list")
    for action in ["describe","schema","doctor"]:sub.add_parser(action).add_argument("--method",required=action!="doctor",default="baseline.table1")
    for action in ["run","validate"]:
        parser=sub.add_parser(action);parser.add_argument("--method",required=True);parser.add_argument("--task",required=True)
    planning=sub.add_parser("plan");planning.add_argument("--method",required=True);planning.add_argument("--assumptions",required=True);planning.add_argument("--output",required=True)
    args=p.parse_args()
    if args.action=="public-fixture":
        from public_fixture import run
        value=run(args.fixture,args.source,args.output,args.rscript)
    elif args.action=="list":
        entries=[{"method_id":d["method_id"],"backend_method_id":d["backend_method_id"],"chinese_name":d["title"],"kind":kind(d),"operations":d["operations"]} for d in catalog()["methods"]]
        value={"entries":entries,"counts":{k:sum(x["kind"]==k for x in entries) for k in ["backend","alias","existing_result_view","legacy_restricted","compat_test","compat_planning"]},"runtime_required_for_discovery":False,"implementation_count_is_not_scientific_acceptance":True}
    elif args.action=="describe":
        d=copy.deepcopy(definition(args.method));historical=d.pop("runtime_requirements",None)
        import method_groups
        value={**d,"kind":kind(d),"product_validation":"local_synthetic_paths_see_references_CAPABILITIES_no_clinical_validation_claim","runtime_requirements":{"python":"3.14.5","R":"4.6.1","dependency_groups":method_groups.for_method(args.method)},"upstream_historical_runtime_metadata":historical}
    elif args.action=="schema":value=schema(definition(args.method))
    elif args.action=="doctor":value=doctor(args.method)
    elif args.action=="plan":
        from legacy_analysis import planning
        value=planning(args.method,args.assumptions,args.output)
    else:
        value,code=execute(args.method,args.task,args.action=="validate");print(json.dumps(value,ensure_ascii=False));return code
    print(json.dumps(value,ensure_ascii=False));return 0
if __name__=="__main__":
    for stream in [sys.stdout,sys.stderr]:
        if hasattr(stream,"reconfigure"):stream.reconfigure(encoding="utf-8")
    try:
        from runtime_platform import runtime_python
        selected=runtime_python(ROOT)
        if selected.is_file() and Path(sys.executable).resolve()!=selected.resolve() and any(x in sys.argv for x in ["run","validate","doctor","plan","public-fixture"]):
            from runtime_windows import env
            raise SystemExit(subprocess.run([str(selected),"-I","-B","-X","utf8",str(Path(__file__).resolve()),*sys.argv[1:]],env=env()).returncode)
        raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,ImportError,StopIteration,subprocess.TimeoutExpired) as error:
        print(json.dumps({"status":"blocked","reason_code":getattr(error,"code","LOCAL_INPUT_OR_RUNTIME_NOT_READY"),"missing_groups":getattr(error,"groups",[]),"support_log":getattr(error,"support_log",None),"action":"Keep local evidence; review the method contract or install its required group. Do not change algorithms, locks, data origin or user authorization to force success."}));raise SystemExit(2)
