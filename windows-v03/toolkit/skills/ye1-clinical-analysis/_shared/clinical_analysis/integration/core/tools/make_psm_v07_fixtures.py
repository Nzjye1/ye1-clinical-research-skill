"""Prespecified v07 synthetic PSM fixtures; all prior candidates stay read-only."""
from __future__ import annotations
import copy, csv, hashlib, importlib.util, json, math, random, sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/"fixtures/psm-v07"
MAP={"patient_id":"stay_code","treatment":"therapy_code","age":"age_months","severity":"severity_percent","sex":"sex_code","outcome":"signed_measurement"}
OPTIONS={"treatment":"treatment","outcome":"outcome","covariates":["age","severity","sex"],
 "categorical":{"sex":{"levels":["F","M"],"reference":"F"}},"propensity_model":"logistic_mle","link":"logit",
 "estimand":"ATT_retained_matched_treated","ratio":1,"replacement":False,"distance":"logit_ps",
 "caliper":{"width":.2,"scale":"sd_logit_ps","sd_scope":"common_support_retained","ddof":1,"boundary":"inclusive"},
 "common_support":{"strategy":"minmax_both","boundary":"inclusive","refit":False},
 "ordering":{"treated":"descending_logit_ps_then_subject_id_utf8","control_tie":"subject_id_utf8_ascending","row_order":"subject_id_utf8_ascending"},
 "inference":{"method":"paired_t","ci_level":.95,"variance":"sample_variance_of_pair_differences","conditioning":"formed_matched_pairs"},
 "diagnostics":{"smd_denominator":"pre_support_complete_case_treated_sample_sd","standardize_binary":True,
  "ps_overlap_edges":[0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1],"balance_reference":.1,"indicator_sd":"bernoulli_p1mp"},
 "guards":{"min_arm_n":2,"min_probability":1e-6,"max_glm_iterations":100,"glm_epsilon":1e-10,"separation_detection":"numerical_guards_only"},"prespecified":True}
SEMANTICS={"subject_id":"patient_id","treatment_definition":"Synthetic baseline treatment assignment",
 "outcome_definition":"Synthetic signed post-index continuous measurement","outcome_unit":"1","index_time":0,
 "time_unit":"hour","target_population":"Synthetic support-retained matched treated subjects"}

def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);sys.modules[name]=obj;spec.loader.exec_module(obj);return obj
def write_csv(path,rows):
    with Path(path).open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def build_rows(missing=True):
    rng=random.Random(2026102407);rows=[]
    for i in range(120):
        age=round(rng.uniform(22,82),1);severity=round(rng.uniform(0,4),3);sex="F" if rng.random()<.55 else "M"
        score=-.15+.018*(age-50)+.65*(severity-2)+.35*(sex=="M")
        treatment=int(rng.random()<1/(1+math.exp(-score)))
        outcome=round(-8+.07*(age-50)+1.6*(severity-2)+1.8*treatment+rng.gauss(0,2),6)
        rows.append({"patient_id":f"SYNTHETIC-V07-{i+1:06d}","treatment":treatment,"age":age,"severity":severity,"sex":sex,"outcome":outcome})
    if missing:
        for i,fields in ((3,["age"]),(22,["severity"]),(57,["sex"]),(88,["age","severity"]),(113,["sex"])):
            for field in fields:rows[i][field]=""
    return rows
def mapped(rows):
    output=[]
    for row in rows:
        output.append({MAP["patient_id"]:row["patient_id"],
          MAP["treatment"]:row["treatment"]+1 if row["treatment"] not in ("",None) else "-999",
          MAP["age"]:12*row["age"] if row["age"] not in ("",None) else "-999",
          MAP["severity"]:100*row["severity"] if row["severity"] not in ("",None) else "-999",
          MAP["sex"]:{"F":"female","M":"male","":"UNK",None:"UNK"}.get(row["sex"],row["sex"]),
          MAP["outcome"]:row["outcome"] if row["outcome"] not in ("",None) else "-999"})
    return output
def prepare_task(c,path,out,db="mimic",options=None):
    task=c.make_psm_task(str(path),str(out),str(ROOT),database="eICU" if db=="eicu" else "MIMIC",psm_options=copy.deepcopy(OPTIONS if options is None else options))
    task["study_id"]="synthetic-psm-v07"
    if db=="eicu":
        task["views"][0]["column_map"]=MAP.copy()
        for variable in task["variables"]:
            name=variable["name"]
            if name=="age":variable.update(source_unit="month",conversion={"scale":1/12,"offset":0},missing_codes=["-999"])
            elif name=="severity":variable.update(source_unit="percent",conversion={"scale":.01,"offset":0},missing_codes=["-999"])
            elif name=="treatment":variable.update(conversion={"scale":1,"offset":-1},missing_codes=["-999"])
            elif name=="outcome":variable["missing_codes"]=["-999"]
            elif name=="sex":variable.update(codes={"female":"F","male":"M"},missing_codes=["UNK"])
    c.seal_task(task,str(ROOT));return task
def reference_input(rows=None,options=None):
    return {"mode":"analyze","rows":copy.deepcopy(build_rows() if rows is None else rows),"options":copy.deepcopy(OPTIONS if options is None else options),"semantics":copy.deepcopy(SEMANTICS)}
def hand_inputs():
    return {"mode":"hands","matching":[
      {"name":"treated_priority","ids":["T-low","T-high","C-near","C-far"],"treatment":[1,1,0,0],"logit":[0,1,.5,-.5],"eligible":[True]*4,"absolute_caliper":1,"expected_pairs":[["T-high","C-near"],["T-low","C-far"]]},
      {"name":"control_distance_tie","ids":["T","C-Z","C-A"],"treatment":[1,0,0],"logit":[0,-1,1],"eligible":[True]*3,"absolute_caliper":1,"expected_pairs":[["T","C-A"]]},
      {"name":"inclusive_boundary","ids":["T","C"],"treatment":[1,0],"logit":[1,0],"eligible":[True]*2,"absolute_caliper":1,"expected_pairs":[["T","C"]]},
      {"name":"next_float_outside_boundary","ids":["T","C"],"treatment":[1,0],"logit":[math.nextafter(1,math.inf),0],"eligible":[True]*2,"absolute_caliper":1,"expected_pairs":[]},
      {"name":"near_distance_not_tie","ids":["T","C-Z","C-A"],"treatment":[1,0,0],"logit":[0,1,math.nextafter(1,math.inf)],"eligible":[True]*3,"absolute_caliper":2,"expected_pairs":[["T","C-Z"]]},
      {"name":"utf8_and_full_string_ids","ids":["10","001","é","Z","9007199254740993","9007199254740992"],"treatment":[1,1,1,0,0,0],"logit":[0]*6,"caliper_multiplier":.2,"expected_pairs":[["001","9007199254740992"],["10","9007199254740993"],["é","Z"]]},
      {"name":"inclusive_support_and_scale","ids":["T0","T1","T2","C0","C1","C2"],"treatment":[1,1,1,0,0,0],"logit":[-2,0,2,-1,1,3],"caliper_multiplier":1,"expected_pairs":[["T2","C1"],["T1","C0"]]},
      {"name":"nonoverlapping_support","ids":["T0","T1","C0","C1"],"treatment":[1,1,0,0],"logit":[1,2,-2,-1],"caliper_multiplier":.2,"expected_pairs":[]},
      {"name":"overlap_range_but_empty_arm","ids":["T0","T1","C0","C1"],"treatment":[1,1,0,0],"logit":[-2,2,-1,1],"caliper_multiplier":.2,"expected_pairs":[]},
      {"name":"zero_caliper_no_exact_pair","ids":["T0","T1","T2","C0","C1","C2"],"treatment":[1,1,1,0,0,0],"logit":[-2,0,2,-1,1,3],"caliper_multiplier":0,"expected_pairs":[]},
      {"name":"one_pair_support","ids":["T0","T1","C0","C1"],"treatment":[1,1,0,0],"logit":[0,1,.5,1.5],"caliper_multiplier":2,"expected_pairs":[["T1","C0"]]}
    ],"effects":[
      {"name":"covariance_counterexample","treated":[10,20,30,40],"control":[8,19,27,38]},
      {"name":"signed_outcomes","treated":[-5,-3,2,0],"control":[-8,-2,-1,-2]},
      {"name":"one_pair","treated":[-1],"control":[-3]},
      {"name":"zero_pairs","treated":[],"control":[]},
      {"name":"constant_difference","treated":[3,5,9],"control":[1,3,7]},
      {"name":"zero_difference","treated":[3,5,9],"control":[3,5,9]}
    ],"balance":{"treated_numeric":[0,2,4,6],"control_numeric":[0,0,2,2],"matched_treated":[2,4],"matched_control":[0,2],
      "treated_binary_numeric":[0,0,1,1],"control_binary_numeric":[0,0,0,1],"treated_indicator":[0,0,1,1],"control_indicator":[0,0,0,1],
      "zero_variance_treated":[1,1,1,1],"zero_variance_control":[0,1,0,1]}}
def main():
    FIX.mkdir(parents=True,exist_ok=True);rows=build_rows()
    write_csv(FIX/"psm-canonical.csv",rows);write_csv(FIX/"psm-mimic.csv",rows);write_csv(FIX/"psm-eicu.csv",mapped(rows))
    dump(FIX/"reference-input.json",reference_input(rows));dump(FIX/"hand-inputs.json",hand_inputs())
    if "--data-only" not in sys.argv:
        c=module(ROOT/"python/clinical_methods/contracts.py","psm_v07_fixture_contracts")
        for db in ("mimic","eicu"):dump(FIX/(db+"-psm.json"),prepare_task(c,FIX/("psm-"+db+".csv"),ROOT/"outputs"/("psm-v07-"+db),db))
    complete=[row for row in rows if all(row[v]!="" for v in OPTIONS["covariates"])]
    manifest={"purpose":"SYNTHETIC_TEST_ONLY","n_input":len(rows),"n_complete_case":len(complete),"n_excluded_missing_covariates":len(rows)-len(complete),
      "n_input_treated":sum(row["treatment"] for row in rows),"n_complete_case_treated":sum(row["treatment"] for row in complete),
      "source_sha256":{p.name:sha(p) for p in sorted(FIX.glob("*.csv"))},"options":OPTIONS,
      "reference_scope":"Independent R/source-formula implementation; no MatchIt or clinical validation"}
    dump(FIX/"fixture-manifest.json",manifest);print(json.dumps({"status":"PSM_V07_SYNTHETIC_FIXTURES_READY","n":len(rows),"complete":len(complete),"treated":manifest["n_input_treated"],"hand_matching_cases":len(hand_inputs()["matching"])}))
if __name__=="__main__":main()
