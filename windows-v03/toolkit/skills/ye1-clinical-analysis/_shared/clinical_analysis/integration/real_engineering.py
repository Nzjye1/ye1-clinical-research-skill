"""Explicit local engineering permission and descriptive source adapter; no estimators."""
from pathlib import Path
import csv,gzip,hashlib,io,json,math,re,sys
ROOT=Path(__file__).resolve().parent;CORE=ROOT/"core";REPO=ROOT.parents[2]
sys.path.insert(0,str(CORE/"python"))
from clinical_methods.contracts import validate_schema
from module_contract import ContractError,read_json
HASH={"type":"string","pattern":"^[0-9a-f]{64}$"}
def obj(fields):return {"type":"object","additionalProperties":False,"required":list(fields),"properties":fields}
TEXT={"type":"string","minLength":1}
SCHEMA=obj({"schema_version":{"const":"clinical-real-engineering-task@1.0"},"study_id":TEXT,
 "method_id":{"const":"baseline.summary"},"operation":{"const":"describe"},"data_origin":{"const":"real_local_normalized"},
 "purpose":{"const":"local_engineering_e2e"},"authorization_ref":HASH,"source":obj({"path":TEXT,"sha256":HASH,"format":{"const":"csv_gzip"},"patient_key":TEXT,"record_key":TEXT}),
 "adapter":{"enum":["direct","named_alias"]},"selection":obj({"max_patients":{"type":"integer","minimum":1,"maximum":200},"seed":{"type":"integer"},"encounter":{"const":"utf8_min_record_key_not_first_operation"}}),
 "structure":obj({"source_grain":{"const":"encounter_wide"},"analysis_grain":{"const":"one_selected_encounter_per_patient"},"joins":{"const":"none"},"weights":{"const":"none"},"missingness":{"const":"observed_per_variable_no_imputation"},"time_policy":{"const":"recorded_snapshot_no_prediction_claim"}}),
 "variables":{"type":"array","minItems":3,"maxItems":3,"items":obj({"name":{"enum":["age","bmi","preop_cr"]},"source_field":TEXT,"unit":{"enum":["year","kg/m^2","mg/dL"]},"role":{"const":"descriptive_measure"},"timing":{"const":"recorded_snapshot_clock_unverified"},"summary":{"const":"median_iqr"}})},
 "execution":obj({"mode":{"const":"real_engineering"},"output_dir":TEXT,"export_policy":{"const":"local_only"}}),"plan_sha256":HASH})
UNITS={"age":"year","bmi":"kg/m^2","preop_cr":"mg/dL"}
COUNTS=obj({k:{"type":"integer","minimum":0} for k in ["source_records","source_patients","patients_with_multiple_records","extra_records_not_represented","selected_patients","selected_records","unselected_patients"]}|{k:obj({name:{"type":"integer","minimum":0} for name in UNITS}) for k in ["missing_by_variable","literal_zero_by_variable"]})
RESULT_SCHEMA=obj({"schema_version":{"const":"clinical-real-engineering-result@1.0"},"run_id":TEXT,"study_id":TEXT,"method_id":{"const":"baseline.summary"},"method_version":{"const":"1.0.0-descriptive-owner"},
 "execution_status":{"const":"complete"},"purpose":{"const":"local_engineering_e2e"},"data_origin":{"const":"real_local_normalized"},"test_only":{"const":True},"scientific_review":{"const":"pending"},"export_status":{"const":"local_only"},"structure":SCHEMA["properties"]["structure"],
 "provider":obj({"id":{"const":"clinanalysis.table1::table1_group_summary"},"code_sha256":HASH,"numerical_fits":{"const":0}}),"bindings":obj({"input_sha256":HASH,"plan_sha256":HASH}),"counts":COUNTS,
 "source_binding":obj({"source_sha256":HASH,"authorization_sha256":HASH,"canonical_selected_sha256":HASH,"host_isolation":{"const":"not_established"},"selection_claim":{"const":"deterministic engineering sample; not first surgery or a formal clinical cohort"}}),
 "artifacts":{"type":"array","items":obj({"relative_path":TEXT,"kind":{"enum":["table","figure","report"]},"sha256":HASH,"bytes":{"type":"integer","minimum":0},"source_result_id":TEXT,"input_sha256":HASH,"method_id":{"const":"baseline.summary"},"method_version":{"const":"1.0.0-descriptive-owner"},"semantics_source":TEXT})},"limitations":{"type":"array","items":TEXT}})
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def plan_hash(task):
 value=json.loads(json.dumps(task));value.pop("plan_sha256",None);value["execution"].pop("output_dir",None);return canonical(value)
def need(value,code):
 if not value:raise ContractError(code)
def dump(path,value):
 with Path(path).open("x",encoding="utf-8") as h:json.dump(value,h,ensure_ascii=False,indent=2,allow_nan=False);h.write("\n")
def inspect(task):
 validate_schema(task,SCHEMA);need(task["plan_sha256"]==plan_hash(task),"REAL_PLAN_BINDING_MISMATCH")
 from module_task import load_registry
 load_registry(task["method_id"])
 policy=read_json(REPO/".clinical-local/source-authorizations.json")
 matches=[p for p in policy["receipts"] if p["sha256"]==task["authorization_ref"]]
 need(len(matches)==1,"REAL_SOURCE_PERMISSION_REQUIRED")
 receipt_path=Path(matches[0]["path"]).resolve();need(sha(receipt_path)==task["authorization_ref"],"REAL_PERMISSION_BYTES_CHANGED")
 receipt=read_json(receipt_path)
 need(receipt["schema_version"]=="clinical-local-source-authorization@1.0" and receipt["authority"]["kind"]=="explicit_user_local_engineering_scope" and bool(receipt["authority"]["reference"]),"REAL_PERMISSION_SCOPE_INVALID")
 need(task["study_id"]==receipt["study_id"],"REAL_STUDY_SCOPE_MISMATCH")
 need(receipt["allowed_method"]==task["method_id"] and receipt["purpose"]==task["purpose"] and receipt["selection"]==task["selection"],"REAL_PERMISSION_SCOPE_MISMATCH")
 source=Path(task["source"]["path"]).resolve()
 need(source==Path(receipt["source"]["path"]).resolve() and task["source"]==receipt["source"],"REAL_SOURCE_SCOPE_MISMATCH")
 need(task["variables"]==receipt["variables"] and [v["name"] for v in task["variables"]]==list(UNITS),"REAL_VARIABLE_SCOPE_MISMATCH")
 need(task["structure"]==receipt["structure"],"REAL_GRAIN_SCOPE_MISMATCH")
 need(all(v["unit"]==UNITS[v["name"]] for v in task["variables"]),"REAL_UNIT_UNCONFIRMED")
 need(source.is_file() and source.stat().st_size<=262144,"REAL_SOURCE_BYTE_LIMIT")
 raw=source.read_bytes();need(hashlib.sha256(raw).hexdigest()==task["source"]["sha256"],"REAL_SOURCE_CHANGED")
 with gzip.GzipFile(fileobj=io.BytesIO(raw)) as h:decoded=h.read(8*1024*1024+1)
 need(len(decoded)<=8*1024*1024,"REAL_DECOMPRESSED_BYTE_LIMIT")
 reader=csv.DictReader(io.StringIO(decoded.decode("utf-8-sig"),newline=""),strict=True);columns=reader.fieldnames
 need(columns and len(columns)==len(set(columns)),"REAL_SOURCE_HEADER_INVALID")
 identifiers={"name","patient_name","姓名","身份证","phone","telephone","email","address","dob","birth_date"}
 need(not (set(x.lower() for x in columns)&identifiers),"DIRECT_IDENTIFIER_HEADER_REVIEW_REQUIRED")
 required=[task["source"]["patient_key"],task["source"]["record_key"]]+[v["source_field"] for v in task["variables"]]
 need(len(required)==len(set(required)) and set(required)<=set(columns),"REAL_FIELDS_OR_ID_ROLE_INVALID")
 rows=list(reader);need(0<len(rows)<=10000,"REAL_ROW_LIMIT")
 need(all(None not in row and all(v is not None for v in row.values()) for row in rows),"REAL_ROW_WIDTH_INVALID")
 grouped={};records=set()
 for row in rows:
  subject,record=(row[task["source"][k]] for k in ("patient_key","record_key"))
  for field,value in (("source.patient_key",subject),("source.record_key",record)):
   pseudonym=bool(re.fullmatch(r"\d{1,9}|[0-9a-fA-F-]{24,64}|(?i:vitaldb[:._-])?(?i:case|subject|patient)?[:._-]?\d{1,9}",value))
   if not pseudonym:raise ContractError("IDENTITY_VALUE_REVIEW_REQUIRED",field)
  need(record not in records,"REAL_RECORD_KEY_DUPLICATE");records.add(record);grouped.setdefault(subject,[]).append(row)
 chosen=sorted(grouped,key=lambda s:hashlib.sha256((str(task["selection"]["seed"])+":"+s).encode()).digest())[:task["selection"]["max_patients"]]
 selected=[min(grouped[s],key=lambda r:r[task["source"]["record_key"]].encode("utf-8")) for s in chosen]
 result=[];missing={v["name"]:0 for v in task["variables"]};zero={v["name"]:0 for v in task["variables"]}
 for row in selected:
  item={"subject_id":row[task["source"]["patient_key"]],"record_id":row[task["source"]["record_key"]]}
  for v in task["variables"]:
   raw_value=row[v["source_field"]]
   if raw_value=="":item[v["name"]]=None;missing[v["name"]]+=1
   else:
    try:value=float(raw_value)
    except (ValueError,OverflowError):raise ContractError("REAL_NUMERIC_VALUE_REVIEW_REQUIRED")
    need(math.isfinite(value),"REAL_NUMERIC_VALUE_REVIEW_REQUIRED");need(value>=0,"REAL_NEGATIVE_MEASUREMENT_REVIEW_REQUIRED")
    zero[v["name"]]+=int(value==0);item[v["name"]]=value
  result.append(item)
 flow={"source_records":len(rows),"source_patients":len(grouped),"patients_with_multiple_records":sum(len(v)>1 for v in grouped.values()),"extra_records_not_represented":len(rows)-len(grouped),
       "selected_patients":len(result),"selected_records":len(result),"unselected_patients":len(grouped)-len(result),"missing_by_variable":missing,"literal_zero_by_variable":zero}
 return result,flow,{"source_sha256":task["source"]["sha256"],"authorization_sha256":task["authorization_ref"],"canonical_selected_sha256":canonical(result),"host_isolation":"not_established","selection_claim":"deterministic engineering sample; not first surgery or a formal clinical cohort"}
def prepare(task_path,output):
 task=read_json(task_path);rows,flow,binding=inspect(task);output=Path(output).resolve()
 need(output.is_relative_to(CORE) and output==Path(task["execution"]["output_dir"]).resolve(),"REAL_OUTPUT_BINDING_INVALID")
 private=output/"private";need(private.is_dir(),"REAL_PRIVATE_DIRECTORY_REQUIRED")
 fields={v["name"]:v["name"] if task["adapter"]=="direct" else "mapped_"+v["name"] for v in task["variables"]}
 path=private/"selected.csv"
 with path.open("x",encoding="utf-8",newline="") as h:
  writer=csv.DictWriter(h,["subject_id","record_id"]+list(fields.values()));writer.writeheader()
  for r in rows:writer.writerow({**{k:r[k] for k in ("subject_id","record_id")},**{column:r[name] for name,column in fields.items()}})
 dump(private/"real-prepared.json",{"variables":[{**v,"column":fields[v["name"]]} for v in task["variables"]],"flow":flow,"binding":binding,"selected_csv_sha256":sha(path)})
def finish(task_path,output):
 from module_worker import artifacts
 task=read_json(task_path);output=Path(output).resolve();prepared=read_json(output/"private/real-prepared.json")
 need(sha(output/"private/selected.csv")==prepared["selected_csv_sha256"],"REAL_SELECTED_BYTES_CHANGED")
 run_id="real-engineering-"+hashlib.sha256(Path(task_path).read_bytes()).hexdigest()[:16]
 request={"method_id":task["method_id"],"bindings":{"input_sha256":sha(task_path),"plan_sha256":task["plan_sha256"]}}
 files=artifacts(output,request,run_id,{"method_version":"1.0.0-descriptive-owner"},"real_local_normalized")
 result={"schema_version":"clinical-real-engineering-result@1.0","run_id":run_id,"study_id":task["study_id"],"method_id":task["method_id"],"method_version":"1.0.0-descriptive-owner",
   "execution_status":"complete","purpose":"local_engineering_e2e","data_origin":"real_local_normalized","test_only":True,"scientific_review":"pending","export_status":"local_only",
   "structure":task["structure"],
   "provider":{"id":"clinanalysis.table1::table1_group_summary","code_sha256":sha(CORE/"src/clinanalysis/R/table1.R"),"numerical_fits":0},"bindings":request["bindings"],"counts":prepared["flow"],"source_binding":prepared["binding"],"artifacts":files,
   "limitations":["Real recorded snapshot with unverified measurement clock; descriptive engineering E2E only.","No model, group hypothesis test, causal estimate, prospective validation or clinical conclusion.","Selected encounter is determined by source key bytes; not the patient's first surgery.","Pseudonymous identifiers remain private; no complete anonymity or host isolation claim."]}
 validate_schema(result,RESULT_SCHEMA);dump(output/"result.json",result)
def main():
 mode,task_path,output=sys.argv[1:4]
 if mode=="prepare":prepare(task_path,output)
 elif mode=="finish":finish(task_path,output)
 else:raise ContractError("REAL_WORKER_MODE_INVALID")
if __name__=="__main__":
 try:main()
 except (ContractError,ValueError,OSError) as error:
  code=getattr(error,"code","REAL_ENGINEERING_REJECTED")
  print(json.dumps({"status":"blocked","reason_code":code}));raise SystemExit(2)
