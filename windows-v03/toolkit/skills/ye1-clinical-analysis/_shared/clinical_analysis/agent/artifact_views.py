"""Publish source-bound aggregate artifacts and select existing components; no estimators."""
from pathlib import Path
import hashlib
import json
import sys

VIEW_SPECS = {
 "result.baseline.table": ("已有总体或分组基线表", ["table1-formatted","table1-statistics","baseline-display"], ["baseline.table1"], []),
 "result.association.effects": ("已有OLS或Logistic效应表图", ["effect-estimates","association-forest"], ["association.linear","association.logistic"], []),
 "result.binary.roc": ("二分类已有 ROC/AUC", ["binary-roc-grid"], ["prediction.binary.ridge","prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"], ["auc"]),
 "result.binary.calibration": ("二分类已有校准", ["binary-calibration"], ["prediction.binary.ridge","prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"], ["calibration_","observed_prevalence","mean_prediction"]),
 "result.binary.dca": ("二分类已有 DCA", ["binary-dca"], ["prediction.binary.ridge","prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"], []),
 "result.survival.roc": ("普通 Cox 已有 IPCW ROC", ["survival-evaluation-roc"], ["evaluation.survival.cox.ipcw"], []),
 "result.survival.calibration": ("普通 Cox 已有 IPCW 校准", ["survival-evaluation-calibration"], ["evaluation.survival.cox.ipcw"], []),
 "result.survival.dca": ("普通 Cox 已有 IPCW DCA", ["survival-evaluation-dca"], ["evaluation.survival.cox.ipcw"], []),
 "result.survival.ph": ("已有正式 PH 检验", ["ph-score-tests"], ["survival.cox.association"], []),
 "result.nomogram": ("已有冻结惩罚模型列线图", ["nomogram","nomogram_domains","nomogram_axes","nomogram_mapping"], ["interpretation.linear.interventional"], []),
 "result.importance": ("已有全局加性贡献重要性", ["interpretation_global_importance"], ["interpretation.linear.interventional"], []),
}


class ViewError(ValueError):
 def __init__(self,code):super().__init__(code);self.code=code
def need(ok,code):
 if not ok:raise ViewError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path,byte_limit=2*1024*1024,expected_sha256=None):
 path=Path(path);need(path.is_file() and path.stat().st_size<=byte_limit,"RESULT_BYTES_INVALID")
 raw=path.read_bytes();need(len(raw)<=byte_limit,"RESULT_BYTES_INVALID")
 if expected_sha256 is not None:need(hashlib.sha256(raw).hexdigest()==expected_sha256,"SOURCE_RESULT_BINDING_MISMATCH")
 def pairs(items):
  value={}
  for key,item in items:need(key not in value,"RESULT_DUPLICATE_KEY");value[key]=item
  return value
 return json.loads(raw.decode("utf-8-sig"),object_pairs_hook=pairs,parse_constant=lambda _:need(False,"RESULT_NONFINITE_JSON"))
def safe(base,relative):
 need(isinstance(relative,str),"ARTIFACT_PATH_INVALID")
 path=(base/relative).resolve();need(path.is_relative_to(base.resolve()) and "private" not in {p.casefold() for p in path.relative_to(base.resolve()).parts},"ARTIFACT_PATH_INVALID")
 return path
def save(path,value):
 with Path(path).open("x",encoding="utf-8") as handle:json.dump(value,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write("\n")
def disclosure_api(root):
 sys.path.insert(0,str(root))
 import data_disclosure
 return data_disclosure


def publish(root,result,task,output):
 """Add a separate Agent artifact manifest; preserve the numerical result/CSV bytes."""
 api=disclosure_api(root);output=Path(output).resolve();source=output/"result.json"
 study=task.get("schema_version")=="clinical-study-input@1.0"
 admitted_module=task.get("schema_version")=="clinical-module-task@1.1"
 real=task.get("schema_version")=="clinical-real-engineering-task@1.0"
 module=task.get("schema_version") in {"clinical-module-task@1.0","clinical-module-task@1.1"} or real
 origin=task["data_origin"] if module or study else "synthetic_inline_normalized"
 need(study or module or task.get("purpose")=="SYNTHETIC_TEST_ONLY","RESULT_ORIGIN_UNSUPPORTED")
 need(((study or admitted_module) and origin in {"real","synthetic"} and result.get("data_origin")==origin and result.get("task_purpose")==task["task_purpose"] and result.get("test_only")== (task["task_purpose"]=="engineering_test")) or origin=="synthetic_inline_normalized" or (real and origin=="real_local_normalized" and task["purpose"]=="local_engineering_e2e"),"REAL_RESULT_CONTRACT_NOT_ENABLED")
 method=task["method_id"] if module else task["analysis"]["method_id"]
 need(result["method_id"]==method,"RESULT_METHOD_MISMATCH")
 run_id=result["run_id"];version=result["method_version"]
 bindings=result.get("bindings",result.get("binding",{}))
 provenance={"result_id":run_id,"method_id":method,"method_version":version,
             "input_sha256":bindings.get("input_sha256",bindings.get("input_hash")),
             "plan_sha256":bindings.get("plan_sha256",bindings.get("plan_hash"))}
 files=[]
 if module:
  artifacts=result["artifacts"]
  for item in artifacts:
   if item["kind"] not in ("table","figure"):continue
   path=safe(output,item["relative_path"]);need(path.is_file() and sha(path)==item["sha256"],"SOURCE_ARTIFACT_HASH_MISMATCH")
   stem=path.stem
   if stem.startswith(("figures__","tables__")):stem=stem.split("__",1)[1]
   files.append({"relative_path":item["relative_path"],"kind":item["kind"],"sha256":item["sha256"],"artifact_ids":[stem],"source_contract":item})
 else:
  for kind,section,folder,suffix in (("table","tables","tables",".csv"),("figure","figures","figures",".png")):
   declared=result.get(section,[])
   found=set()
   for path in sorted((output/folder).glob("*")):
    if not path.is_file() or path.suffix.lower()!=suffix:continue
    digest=sha(path);matches=[a for a in declared if a["data_hash"]==digest]
    if not matches:continue
    found.update(a["artifact_id"] for a in matches)
    files.append({"relative_path":path.relative_to(output).as_posix(),"kind":kind,"sha256":digest,
                  "artifact_ids":[a["artifact_id"] for a in matches],"source_contract":matches})
   need(found=={a["artifact_id"] for a in declared},"DECLARED_ARTIFACT_MISSING")
 for item in files:
  if item["kind"]!="table":continue
  path=safe(output,item["relative_path"]);metadata=path.with_name(path.name+".metadata.json")
  if metadata.exists():
   matches=[a for a in result.get("artifacts",[]) if a["relative_path"]==metadata.relative_to(output).as_posix()]
   need(len(matches)==1,"UNBOUND_TABLE_METADATA")
   envelope,_=api.read_table_envelope(metadata,matches[0]["sha256"])
   need(envelope["data_origin"]==origin and envelope["provenance"]==provenance,"TABLE_PROVENANCE_MISMATCH")
  else:api.table_envelope(path,origin,provenance,context={"task_purpose":task["task_purpose"],"test_only":result["test_only"]} if study or admitted_module else None)
  envelope,_=api.read_table_envelope(metadata)
  item["metadata"]={"relative_path":metadata.relative_to(output).as_posix(),"sha256":sha(metadata),"row_count":envelope["row_count"],"format":envelope["schema_version"]}
 manifest={"schema_version":"clinical-agent-artifacts@1.0","source_result_sha256":sha(source),"method_id":method,"method_version":version,
           "data_origin":origin,"share_contract":"Every table is CSV plus its hash-bound metadata; a bare zero-row CSV is not a provenance-complete export.","files":files}
 if study or admitted_module:manifest.update(task_purpose=task["task_purpose"],test_only=result["test_only"],scientific_review="pending")
 save(output/"agent-artifacts.json",manifest)
 return output/"agent-artifacts.json"


def request_schema(method,input_version="ye1-result-view-request@1.0"):
 ref={"type":"object","additionalProperties":False,"required":["path","sha256"],"properties":{"path":{"type":"string"},"sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}}}
 value={"type":"object","additionalProperties":False,"required":["schema_version","method_id","operation","source_result","source_manifest","output_dir","export_policy"],
         "properties":{"schema_version":{"const":"ye1-result-view-request@1.0"},"method_id":{"const":method},"operation":{"enum":["export_existing"]},"source_result":ref,"source_manifest":ref,
                       "output_dir":{"type":"string"},"export_policy":{"const":"local_only"}}}
 if input_version=="ye1-result-view-request@1.1":
  value["properties"].update(schema_version={"const":input_version},project_root={"type":"string","minLength":1},
    data_origin={"enum":["real","synthetic"]},task_purpose={"enum":["engineering_test","research_analysis"]},
    execution={"type":"object","additionalProperties":False,"required":["mode","privacy_profile"],
      "properties":{"mode":{"const":"local"},"privacy_profile":{"const":"captured_local_process"}}})
  value["required"] += ["project_root","data_origin","task_purpose","execution"]
 else:need(input_version=="ye1-result-view-request@1.0","RESULT_VIEW_SCHEMA_VERSION_UNSUPPORTED")
 return value


def validate_admitted_source(result):
 """Recover the registered closed record schema; no rows or model are loaded."""
 from module_task import load_registry,canonical
 from module_worker import admitted_result_schema
 from module_contract import _check,_validator
 from admitted_modules import load_selection,_apply_schemas
 context=result.get("origin_context")
 keys={"data_origin","task_purpose","test_only","scientific_review","source_verification","host_isolation"}
 need(isinstance(context,dict) and set(context)==keys,"SOURCE_ORIGIN_CONTEXT_INVALID")
 need(context["data_origin"] in {"real","synthetic"} and context["task_purpose"] in {"engineering_test","research_analysis"}
      and type(context["test_only"]) is bool and context["test_only"]==(context["task_purpose"]=="engineering_test")
      and (context["data_origin"]!="synthetic" or context["task_purpose"]=="engineering_test")
      and context["scientific_review"]=="pending"
      and context["source_verification"]=="normalized_payload_bytes_bound_source_identity_not_authenticated"
      and context["host_isolation"]=="not_established","SOURCE_ORIGIN_CONTEXT_INVALID")
 need(all(result.get(k)==context[k] for k in ("data_origin","task_purpose","test_only","scientific_review")),"SOURCE_ORIGIN_CONTEXT_MISMATCH")
 registry,meta,_=load_registry(result["method_id"]);info=meta[result["method_id"]]
 selection,_=load_selection(info,result["method_id"]);definition=registry.methods[result["method_id"]]
 _apply_schemas(registry,definition,info,selection,result["method_id"])
 packet={"registry":registry,"definition":definition,"origin_context":context,"response":{"ok":result.get("module_record") is not None},"info":info}
 _check(_validator(admitted_result_schema(packet)),result,"SOURCE_RESULT_SCHEMA_INVALID")
 need(result["module_id"]==definition["module_id"] and result["method_version"]==definition["method_version"]
      and result["provider"]["module_manifest_sha256"]==selection["manifest_sha256"]
      and result["provider"]["registered_code_sha256"]==canonical(selection),"SOURCE_MODULE_REGISTRATION_MISMATCH")
 for record in (result.get("module_record"),result.get("diagnostics")):
  if isinstance(record,dict):
   need(all(k not in record or record[k]==context[k] for k in ("data_origin","task_purpose","test_only","scientific_review")),"SOURCE_RECORD_ORIGIN_MISMATCH")


def project(root,request,definition,validate_only=False):
 root=Path(root).resolve();core=root/"core";api=disclosure_api(root)
 sys.path.insert(0,str(core/"python"));from clinical_methods.contracts import validate_schema
 mid=definition["method_id"];v1=request.get("schema_version")=="ye1-result-view-request@1.1"
 validate_schema(request,request_schema(mid,request.get("schema_version")))
 project_root=Path(request["project_root"]).resolve() if v1 else core
 need(project_root.is_dir(),"PROJECT_DIRECTORY_REQUIRED")
 if v1 and request["data_origin"]=="real":
  import captured_study
  captured_study.verify_context(project_root,request,core)
 source=Path(request["source_result"]["path"]).resolve();manifest_path=Path(request["source_manifest"]["path"]).resolve()
 need(source.is_relative_to(project_root) and source.name=="result.json" and "private" not in {p.casefold() for p in source.relative_to(project_root).parts},"RESULT_SOURCE_OUTSIDE_PUBLIC_ROOT")
 need(manifest_path==source.parent/"agent-artifacts.json","RESULT_MANIFEST_REQUIRED")
 need(source.is_file() and manifest_path.is_file(),"SOURCE_RESULT_OR_MANIFEST_MISSING")
 result=load(source,expected_sha256=request["source_result"]["sha256"]);manifest=load(manifest_path,expected_sha256=request["source_manifest"]["sha256"])
 admitted_module=result.get("schema_version")=="clinical-modular-result@1.1"
 if admitted_module:
  validate_admitted_source(result)
 elif result.get("schema_version")=="clinical-modular-result@1.0":
  from module_task import load_registry
  from module_worker import result_schema
  from module_contract import _check,_validator
  registry,_,_=load_registry(result["method_id"])
  _check(_validator(result_schema(registry,registry.methods[result["method_id"]])),result,"SOURCE_RESULT_SCHEMA_INVALID")
 else:validate_schema(result,load(core/"schemas/result.schema.json",byte_limit=4*1024*1024))
 need(manifest["schema_version"]=="clinical-agent-artifacts@1.0" and manifest["source_result_sha256"]==request["source_result"]["sha256"],"SOURCE_RESULT_BINDING_MISMATCH")
 title,ids,allowed,metric_names=VIEW_SPECS[mid]
 need(result["method_id"] in allowed and manifest["method_id"]==result["method_id"],"RESULT_VIEW_MODEL_NOT_SUPPORTED")
 need(result["execution_status"] in ("complete","partial"),"SOURCE_RESULT_NOT_COMPUTED")
 if v1:
  need(result.get("schema_version") in {"clinical-analysis-result@1.0","clinical-modular-result@1.1"},"RESULT_ORIGIN_CONTEXT_VERSION_UNSUPPORTED")
  expected={"data_origin":request["data_origin"],"task_purpose":request["task_purpose"],
            "test_only":request["task_purpose"]=="engineering_test","scientific_review":"pending"}
  need(all(result.get(k)==v and manifest.get(k)==v for k,v in expected.items()),"RESULT_ORIGIN_PURPOSE_MISMATCH")
 else:need(manifest["data_origin"]=="synthetic_inline_normalized" and result.get("test_only") is True,"REAL_RESULT_CONTRACT_NOT_ENABLED")
 selected=[f for f in manifest["files"] if set(f["artifact_ids"])&set(ids)]
 need(bool(selected),"RESULT_COMPONENT_NOT_AVAILABLE")
 checked=[]
 declared={}
 if v1:
  if admitted_module:
   for artifact in result["artifacts"]:
    if artifact["kind"] not in {"table","figure"}:continue
    stem=Path(artifact["relative_path"]).stem
    if stem.startswith(("figures__","tables__")):stem=stem.split("__",1)[1]
    key=(artifact["kind"],stem)
    need(key not in declared,"SOURCE_ARTIFACT_ID_DUPLICATE")
    declared[key]=artifact["sha256"]
  else:
   for kind,section in (("table","tables"),("figure","figures")):
    for artifact in result.get(section,[]):
     key=(kind,artifact["artifact_id"])
     need(key not in declared,"SOURCE_ARTIFACT_ID_DUPLICATE")
     declared[key]=artifact["data_hash"]
 for item in selected:
  if v1:
   need(bool(item["artifact_ids"]) and len(set(item["artifact_ids"]))==len(item["artifact_ids"]),"SOURCE_ARTIFACT_DECLARATION_MISMATCH")
   need(all(declared.get((item["kind"],aid))==item["sha256"] for aid in item["artifact_ids"]),"SOURCE_ARTIFACT_DECLARATION_MISMATCH")
  path=safe(source.parent,item["relative_path"]);need(path.is_file() and sha(path)==item["sha256"],"SOURCE_ARTIFACT_HASH_MISMATCH")
  checked.append((path,item["relative_path"],item["sha256"]))
  if item["kind"]=="table":
   meta=item["metadata"];metadata=safe(source.parent,meta["relative_path"]);envelope,_=api.read_table_envelope(metadata,meta["sha256"])
   need(envelope["data_origin"]==manifest["data_origin"],"TABLE_ORIGIN_MISMATCH")
   if v1:need(all(envelope.get(k)==v for k,v in expected.items()),"TABLE_ORIGIN_PURPOSE_MISMATCH")
   if v1:
    binding=result["bindings"] if admitted_module else result["binding"]
    need(envelope["provenance"]=={"result_id":result["run_id"],"method_id":result["method_id"],"method_version":result["method_version"],
      "input_sha256":binding["input_sha256" if admitted_module else "input_hash"],"plan_sha256":binding["plan_sha256" if admitted_module else "plan_hash"]},"TABLE_PROVENANCE_MISMATCH")
   checked.append((metadata,meta["relative_path"],meta["sha256"]))
 output=Path(request["output_dir"]).resolve()
 need(output!=project_root and output.is_relative_to(project_root) and not output.exists() and output.parent.is_dir(),"FRESH_OUTPUT_INSIDE_BACKEND_CORE_REQUIRED")
 summary={"selected_method_id":mid,"source_method_id":result["method_id"],"operation":"export_existing","numerical_execution_count":0,
          "scientific_review":"pending","source_execution_status":result["execution_status"],"data_origin":manifest["data_origin"],
          "selected_artifact_count":len(selected),"component":title}
 if v1:summary.update(task_purpose=request["task_purpose"],test_only=expected["test_only"])
 if validate_only:return {**summary,"status":"CONTRACT_VALIDATED_NOT_EXECUTED"}
 output.mkdir();copied=[]
 for path,relative,expected_hash in checked:
  target=safe(output,relative);target.parent.mkdir(parents=True,exist_ok=True)
  raw=path.read_bytes();need(len(raw)<=8*1024*1024 and hashlib.sha256(raw).hexdigest()==expected_hash,"SOURCE_ARTIFACT_CHANGED")
  with target.open("xb") as handle:handle.write(raw)
  copied.append({"relative_path":relative,"sha256":sha(target)})
 metrics=[m for m in result.get("metrics",[]) if any(m["name"]==name or name.endswith("_") and m["name"].startswith(name) for name in metric_names)]
 report={"schema_version":"clinical-result-view@1.1" if v1 else "clinical-result-view@1.0",**summary,"source_result":request["source_result"],"source_manifest":request["source_manifest"],"provider":result.get("provider"),
         "counts":result.get("counts",result.get("module_record",{}).get("counts",{})),"metrics":metrics,"files":copied,
         "limitations":["Only already-computed public artifacts were selected; no new evaluation, fitting, tuning, calibration or uncertainty calculation.","Combined survival figure panels are not exported for a single component; individual tables remain usable."]}
 save(output/"result-view.json",report)
 return {**summary,"status":"EXPORTED_EXISTING_RESULT","result":str(output/"result-view.json")}
