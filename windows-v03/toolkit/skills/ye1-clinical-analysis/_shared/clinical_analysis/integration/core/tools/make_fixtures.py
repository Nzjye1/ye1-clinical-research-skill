"""Small synthetic-only paired adapter fixtures; never reads source databases."""
from __future__ import annotations
import copy
import csv
import importlib.util
import json
import math
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

def build_rows():
    rng = random.Random(20261023)
    rows=[]
    for i in range(120):
        x=rng.gauss(0,1); z=rng.gauss(0,1); g="A" if i%2==0 else "B"
        y=3+1.2*x-.7*z+.4*(g=="B")+rng.gauss(0,.8)
        eta=.1+.4*x-.25*z+.3*(g=="B")
        b=int(rng.random()<1/(1+math.exp(-eta)))
        rows.append({"id":f"{i+1:06d}","x":x,"z":z,"group":g,"y":y,"binary":str(b)})
    for i in [1,20,39,58,77]: rows[i]["x"]=""
    for i in [2,22,42,62]: rows[i]["z"]=""
    for i in [3,30,80]: rows[i]["y"]=""
    for i in [4,40]: rows[i]["binary"]=""
    return rows

def write_csv(path,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    FIX.mkdir(exist_ok=True)
    rows=build_rows()
    write_csv(FIX/"canonical.csv",rows)
    write_csv(FIX/"mimic.csv",rows)
    eicu=[]
    for r in rows:
        eicu.append({"patientunitstayid":r["id"],"exposure_pct":r["x"]*100 if r["x"]!="" else "-999",
          "adjustment":r["z"] if r["z"]!="" else "-999", "sex_code":"F" if r["group"]=="A" else "M",
          "lab_result":r["y"] if r["y"]!="" else "-999", "status":{"0":"no","1":"yes","":"UNK"}[r["binary"]]})
    write_csv(FIX/"eicu.csv",eicu)
    # Deliberately use the production contract builder rather than a second schema implementation.
    spec=importlib.util.spec_from_file_location("core_contracts",ROOT/"python/clinical_methods/contracts.py")
    contracts=importlib.util.module_from_spec(spec);sys.modules[spec.name]=contracts;spec.loader.exec_module(contracts)
    for db in ["MIMIC","eICU"]:
        csv_path=FIX/("mimic.csv" if db=="MIMIC" else "eicu.csv")
        task=contracts.make_example_task(str(csv_path),str(ROOT/"outputs"/f"example_{db}"),str(ROOT),database=db)
        if db=="eICU":
            task["views"][0]["column_map"]={"id":"patientunitstayid","x":"exposure_pct","z":"adjustment",
              "group":"sex_code","y":"lab_result","binary":"status"}
            for v in task["variables"]:
                if v["name"]=="x":v.update(source_unit="percent",unit="1",conversion={"scale":.01,"offset":0},missing_codes=["-999"])
                elif v["name"] in ["z","y"]:v["missing_codes"]=["-999"]
                elif v["name"]=="group":v["codes"]={"F":"A","M":"B"}
                elif v["name"]=="binary":v.update(codes={"no":"0","yes":"1"},missing_codes=["UNK"])
        for method in ["baseline.table1","association.linear","association.logistic"]:
            case=copy.deepcopy(task)
            case["study_id"]="synthetic-paired-adapter-120"
            case["analysis"]["method_id"]=method
            model="logistic" if method.endswith("logistic") else "linear"
            a=case["analysis"]["spec"]
            a.update(model=model,outcome="binary" if model=="logistic" else "y",exposure="x",covariates=["z","group"],
                     categorical={"group":{"levels":["A","B"],"reference":"A"}},
                     covariance="model" if model=="logistic" else "HC3")
            if model=="logistic":a.update(event="1",non_event="0")
            else:a.pop("event",None);a.pop("non_event",None)
            case["analysis"]["variance"]=a["covariance"]
            case["analysis"]["effect_scale"]="odds_ratio" if model=="logistic" else "outcome units"
            case["outcome"].update(field=a["outcome"],type="binary" if model=="logistic" else "continuous",
                                   event="1" if model=="logistic" else None,non_event="0" if model=="logistic" else None)
            case["analysis"]["baseline"]["variables"]=[{"name":v,"type":"continuous","summary":"median_iqr","levels":[]} for v in ["x","z"]]+[
                {"name":"group","type":"categorical","summary":None,"levels":["A","B"]}]
            if method=="baseline.table1":case["analysis"].update(spec=None,effect_scale="descriptive")
            contracts.seal_task(case,str(ROOT))
            dump(FIX/f"{db.lower()}_{method.split('.')[-1]}.json",case)
    dump(FIX/"fixture-manifest.json",{"purpose":"SYNTHETIC_TEST_ONLY","n_rows":120,"seed":20261023,
      "canonical_columns":["id","x","z","group","y","binary"],
      "mapping":"MIMIC identity; eICU renamed fields, exposure percent->1, F/M->A/B, no/yes->0/1, -999/UNK missing",
      "disclaimer":"Synthetic adapter semantics only; no real database connection or clinical validation."})
    print("SYNTHETIC_FIXTURES_COMPLETE")
if __name__=="__main__":main()
