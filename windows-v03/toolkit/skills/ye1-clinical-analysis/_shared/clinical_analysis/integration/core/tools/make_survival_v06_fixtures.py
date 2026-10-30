"""New v06 synthetic fixtures and byte-preserved frozen v05 model only."""
from __future__ import annotations
import copy, csv, hashlib, importlib.util, json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REFERENCE_ROOT=ROOT.parent/"tests/reference-baselines"
FIX=ROOT/"fixtures/survival-v06"
FROZEN_SOURCE=REFERENCE_ROOT/"clinical-analysis-core-v0_5-dev-20261024/evidence/survival-v05-acceptance-20261024-031849-fce9e7/run-train-mimic/private/frozen_cox_model.json"
HORIZONS=[0,1,5,10,20]
NAMESPACE="synthetic_survival_v05_shared_identity"
MAP={"id":"stay_code","time":"followup_hours","status":"event_code","x":"baseline_x","z":"baseline_z","group":"group_code"}
COVARIATES=[{"name":name,"type":"numeric","available_at_time_zero":True} for name in ("x","z")]+[
 {"name":"group","type":"category","levels":["A","B","C"],"reference":"A","available_at_time_zero":True}]
OPTIONS={"estimator":"marginal_reverse_km_ipcw","censoring_source":"evaluation_cohort",
 "censoring_assumption":"independent_of_event_time_and_model_features","tie_order":"events_before_censoring",
 "min_censoring_survival":.05,"max_ipcw_weight":20,"positivity_policy":"reject_no_clipping",
 "roc_thresholds":[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1],
 "calibration":{"method":"ipcw_hajek_fixed_bins","probability_edges":[0,.2,.4,.6,.8,1],"min_bin_n":5},
 "dca_thresholds":[.05,.1,.2,.3,.5],"uncertainty":"not_implemented","prespecified":True}
HAND_OPTIONS={**OPTIONS,"roc_thresholds":[0,.5,1],
 "calibration":{"method":"ipcw_hajek_fixed_bins","probability_edges":[0,.5,1],"min_bin_n":2},"dca_thresholds":[.25,.5,.75]}

def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write_csv(path,rows):
    with Path(path).open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);sys.modules[name]=value;spec.loader.exec_module(value);return value
def build_rows():
    old=module(ROOT/"tools/make_survival_v05_fixtures.py","v06_readonly_v05_fixture_helpers")
    rows=old.build_rows(external=True)
    for i,row in enumerate(rows):row["id"]=f"SYNTHETIC-V06-EXT-{i+1:06d}"
    return rows
def mapped(rows):
    return [{MAP["id"]:r["id"],MAP["time"]:24*r["time"] if r["time"]!="" else "-999",
      MAP["status"]:{"0":"no","1":"yes","":"UNK"}.get(r["status"],r["status"]),
      MAP["x"]:r["x"] if r["x"]!="" else "-999",MAP["z"]:r["z"] if r["z"]!="" else "-999",
      MAP["group"]:{"A":"alpha","B":"beta","C":"gamma","":"UNK"}.get(r["group"],r["group"])} for r in rows]
def frozen_model():
    FIX.mkdir(parents=True,exist_ok=True);target=FIX/"frozen_cox_model.json"
    assert FROZEN_SOURCE.is_file(),"original frozen v05 acceptance model is required"
    if target.exists():assert target.read_bytes()==FROZEN_SOURCE.read_bytes(),"existing v06 fixture model differs; never overwrite"
    else:shutil.copyfile(FROZEN_SOURCE,target)
    assert sha(target)==sha(FROZEN_SOURCE);return target
def prepare_task(c,path,out,db="mimic",horizons=None,options=None,model_ref=None,model_sha256=None):
    model_ref=frozen_model() if model_ref is None else Path(model_ref)
    task=c.make_survival_evaluation_task(str(path),str(out),str(ROOT),database="eICU" if db=="eicu" else "MIMIC",
      model_ref=str(model_ref),model_sha256=sha(model_ref) if model_sha256 is None else model_sha256,
      horizons=list(HORIZONS if horizons is None else horizons),canonical_identity_namespace=NAMESPACE,
      evaluation_options=copy.deepcopy(OPTIONS if options is None else options))
    task["study_id"]="synthetic-survival-v06-evaluation"
    task["analysis"]["survival"]["covariates"]=copy.deepcopy(COVARIATES)
    for variable in task["variables"]:
        if variable["name"]=="group":variable.update(levels=["A","B","C"],reference="A",codes={k:k for k in "ABC"})
    if db=="eicu":
        task["views"][0]["column_map"]=MAP.copy()
        for variable in task["variables"]:
            name=variable["name"]
            if name=="time":variable.update(source_unit="hour",unit="day",conversion={"scale":1/24,"offset":0},missing_codes=["-999"])
            elif name in ("x","z"):variable["missing_codes"]=["-999"]
            elif name=="status":variable.update(codes={"yes":"1","no":"0"},missing_codes=["UNK"])
            elif name=="group":variable.update(codes={"alpha":"A","beta":"B","gamma":"C"},missing_codes=["UNK"])
    c.seal_task(task,str(ROOT));return task
def direct_spec():
    return {"method":"cox_ph","subject_id":"id","time":"time","status":"status","time_unit":"day",
      "time_zero_definition":"synthetic origin","event_definition":"synthetic event","censoring_definition":"synthetic right censoring",
      "event_code":"1","censor_code":"0","independent_subjects":True,"missing_policy":"complete_case",
      "evaluation_times":[0,1,2,3,6],"covariates":[{"name":"x","type":"numeric","available_at_time_zero":True}],
      "competing_codes":[],"competing_event_definitions":[],"left_truncation":False,"time_varying_covariates":False,
      "recurrent_events":False,"interval_censoring":False,"weights":False,"strata":False,"cluster":False,"ties":"breslow","min_events_per_parameter":10}
def hand_case(label,times,status,risks,horizons):
    rows=[{"id":f"SYNTHETIC-V06-HAND-{label}-{i+1}","time":t,"status":str(s),"x":0} for i,(t,s) in enumerate(zip(times,status))]
    predictions=[{"subject_id":row["id"],"horizon":h,"survival_probability":1-float(risks[i]),"event_risk":float(risks[i])} for h in horizons for i,row in enumerate(rows)]
    spec=direct_spec();spec["evaluation_times"]=list(horizons)
    return {"rows":rows,"spec":spec,"horizons":horizons,"individual_predictions":predictions,"evaluation":copy.deepcopy(HAND_OPTIONS)}
def hand_cases():
    cases={
      "uncensored":hand_case("uncensored",[1,2,4,5],[1]*4,[.9,.8,.2,.1],[0,3,6]),
      "event-censor-tie":hand_case("tie",[1,1,2,3],[1,0,1,0],[.8,.9,.6,.2],[1,2,3]),
      "score-ties":hand_case("score",[1,2,4,5],[1]*4,[.5]*4,[3]),
      "fractional-perfect-auc":hand_case("fractional",[1,2,3,4,5,6],[0,1,1,0,0,0],[.5,.8,.8,.2,.2,.2],[3]),
      "fractional-brier-endpoint":hand_case("brierend",list(range(1,14)),[0,0,1,0,1,0,0,0,1,1,1,1,1],[0]*13,[13]),
      "hajek-not-bin-km":hand_case("hajek",[1,1,2,3],[1,0,1,0],[.8,.2,.1,.7],[2]),
      "zero-G":hand_case("zero",[1,2],[1,0],[.8,.2],[1,3]),
      "guard-equality":hand_case("eq",[1]*20+[2],[1]+[0]*19+[1],[.8]+[.5]*19+[.2],[1]),
      "guard-violation":hand_case("gt",[1]*21+[2],[1]+[0]*20+[1],[.8]+[.5]*20+[.2],[1]),
      "near-ties":hand_case("near",[1,1+1e-12,2,3],[1,0,1,0],[.8,.9,.6,.2],[1,1+1e-12,2]),
      "calibration-boundaries":hand_case("edges",[1,2,4,5],[1]*4,[0,.5,.5,1],[3]),
      "zero-weight-bin":hand_case("zerobin",[1,1,2,3,4,5],[0,0,1,1,1,1],[.1,.2,.7,.8,.9,.95],[2])}
    return cases
def main():
    FIX.mkdir(parents=True,exist_ok=True);model=frozen_model();rows=build_rows()
    write_csv(FIX/"evaluation-canonical.csv",rows);write_csv(FIX/"evaluation-mimic.csv",rows);write_csv(FIX/"evaluation-eicu.csv",mapped(rows))
    for name,value in hand_cases().items():dump(FIX/("hand-"+name+".json"),value)
    if "--data-only" not in sys.argv:
        c=module(ROOT/"python/clinical_methods/contracts.py","v06_fixture_contracts")
        for db in ("mimic","eicu"):dump(FIX/(db+"-evaluation.json"),prepare_task(c,FIX/f"evaluation-{db}.csv",ROOT/"outputs"/("v06-example-"+db),db))
    manifest={"purpose":"SYNTHETIC_TEST_ONLY","evaluation_rows":len(rows),"horizons":HORIZONS,
      "frozen_source":str(FROZEN_SOURCE),"frozen_model_file_sha256":sha(model),"frozen_model_internal_sha256":json.loads(model.read_text(encoding="utf-8"))["model_sha256"],
      "source_sha256":{path.name:sha(path) for path in sorted(FIX.glob("*.csv"))},"hand_cases":list(hand_cases()),
      "scope":"Formula-reference engineering acceptance only; no specialist-package, clinical or real external validation"}
    dump(FIX/"fixture-manifest.json",manifest);print(json.dumps({"status":"SYNTHETIC_V06_FIXTURES_READY","evaluation_rows":len(rows),"hand_cases":len(hand_cases()),"frozen_model_file_sha256":sha(model)}))
if __name__=="__main__":main()
