"""Deterministic synthetic v05 cohorts. Writes only the new survival-v05 folder."""
from __future__ import annotations
import copy, csv, hashlib, importlib.util, json, math, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "survival-v05"
SEED = 2026102405
TRAIN_N = 260
HORIZONS = [0, .5, 1, 5, 10, 20]
NAMESPACE = "synthetic_survival_v05_shared_identity"
MAP = {"id":"stay_code", "time":"followup_hours", "status":"event_code",
       "x":"baseline_x", "z":"baseline_z", "group":"group_code"}
COVARIATES = [{"name":n,"type":"numeric","available_at_time_zero":True} for n in ("x","z")] + [
    {"name":"group","type":"category","levels":["A","B","C"],"reference":"A","available_at_time_zero":True}]

def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")

def write_csv(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer=csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)

def build_rows(external=False, missing=True):
    rng=random.Random(SEED+(1 if external else 0)); rows=[]
    for i in range(100 if external else 360):
        x=rng.gauss(.3 if external else 0,1); z=rng.uniform(-1.4,1.4)
        group="ABC"[i%3]
        rate=.055*math.exp(.30*x-.22*z+(.20 if group=="B" else -.10 if group=="C" else 0))
        event=-math.log(max(rng.random(),1e-14))/rate; censor=rng.uniform(20,30)
        rows.append(dict(id=f"SYNTHETIC-V05-{'EXT' if external else 'DEV'}-{i+1:06d}",
                         time=min(30,max(.5,math.ceil(min(event,censor)*2)/2)),
                         status=str(int(event<=censor)),x=x,z=z,group=group))
    # Prespecified exact-event and simultaneous-censor cases; horizons above do
    # not use fitted outcomes or observed event-time selection.
    rows[0].update(time=.5,status="1"); rows[6].update(time=.5,status="0")
    rows[9].update(time=1,status="1"); rows[12].update(time=1,status="0")
    if missing and not external:
        # Valid application cohorts have observed features. Training complete
        # cases are fitted locally; missing holdout/inference features get their
        # own explicit rejection tests rather than silently dropping people.
        fields={"x":[3,23,103],"z":[4,24,104],"group":[5,25,105],
                "time":[1,21,101],"status":[2,22,102]}
        for field,indices in fields.items():
            for i in indices:
                if i<len(rows): rows[i][field]=""
    return rows

def mapped(rows):
    return [{MAP["id"]:r["id"],MAP["time"]:24*r["time"] if r["time"]!="" else "-999",
             MAP["status"]:{"0":"no","1":"yes","":"UNK"}[r["status"]],
             MAP["x"]:r["x"] if r["x"]!="" else "-999",MAP["z"]:r["z"] if r["z"]!="" else "-999",
             MAP["group"]:{"A":"alpha","B":"beta","C":"gamma","":"UNK"}[r["group"]]} for r in rows]

def module():
    spec=importlib.util.spec_from_file_location("survival_v05_fixture_contracts",ROOT/"python/clinical_methods/contracts.py")
    result=importlib.util.module_from_spec(spec);sys.modules[spec.name]=result;spec.loader.exec_module(result);return result

def prepare_task(c, path, out, kind="train", db="mimic", rows=None, transform="km", model_ref=None, model_sha256=None, horizons=None):
    rows=build_rows() if rows is None else rows
    if kind=="ph":
        task=c.make_formal_ph_task(str(path),str(out),str(ROOT),database="eICU" if db=="eicu" else "MIMIC",transform=transform)
    else:
        task=c.make_cox_prediction_task(str(path),str(out),str(ROOT),database="eICU" if db=="eicu" else "MIMIC",
            operation=kind,training_subjects=[r["id"] for r in rows[:TRAIN_N]] if kind=="train" else [],
            holdout_subjects=[r["id"] for r in rows[TRAIN_N:]] if kind=="train" else [],
            horizons=list(HORIZONS if horizons is None else horizons),canonical_identity_namespace=NAMESPACE,
            model_ref=str(model_ref) if model_ref is not None else None,model_sha256=model_sha256)
    task["study_id"]="synthetic-survival-v05-360"
    task["analysis"]["survival"]["covariates"]=copy.deepcopy(COVARIATES)
    task["analysis"]["survival"]["evaluation_times"]=list(HORIZONS if kind=="ph" or horizons is None else horizons)
    for variable in task["variables"]:
        if variable["name"]=="group": variable.update(levels=["A","B","C"],reference="A",codes={k:k for k in "ABC"})
    if db=="eicu":
        task["views"][0]["column_map"]=MAP.copy()
        for variable in task["variables"]:
            name=variable["name"]
            if name=="time": variable.update(source_unit="hour",unit="day",conversion={"scale":1/24,"offset":0},missing_codes=["-999"])
            elif name in ("x","z"): variable["missing_codes"]=["-999"]
            elif name=="status": variable.update(codes={"yes":"1","no":"0"},missing_codes=["UNK"])
            elif name=="group": variable.update(codes={"alpha":"A","beta":"B","gamma":"C"},missing_codes=["UNK"])
    c.seal_task(task,str(ROOT));return task

def main():
    FIX.mkdir(exist_ok=True);dev=build_rows();external=build_rows(external=True)
    for label,rows in [("development",dev),("external",external)]:
        write_csv(FIX/f"{label}-canonical.csv",rows)
        write_csv(FIX/f"{label}-mimic.csv",rows)
        write_csv(FIX/f"{label}-eicu.csv",mapped(rows))
    if "--data-only" not in sys.argv:
        c=module()
        for db in ("mimic","eicu"):
            for kind in ("train","ph"):
                label=f"{db}-{kind}"
                dump(FIX/f"{label}.json",prepare_task(c,FIX/f"development-{db}.csv",ROOT/"outputs"/f"v05-example-{label}",kind,db,dev))
        dump(FIX/"mimic-ph-identity.json",prepare_task(c,FIX/"development-mimic.csv",ROOT/"outputs/v05-example-ph-identity","ph",rows=dev,transform="identity"))
    manifest={"purpose":"SYNTHETIC_TEST_ONLY","seed":SEED,"development_rows":len(dev),"training_partition":TRAIN_N,
        "holdout_partition":len(dev)-TRAIN_N,"external_rows":len(external),"horizons":HORIZONS,
        "categorical_term_degrees_of_freedom":2,"mapping":"hours/24 to days; renamed columns; explicit event and category codes; missing sentinels",
        "source_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(FIX.glob("*.csv"))},
        "scope":"Synthetic adapter and numerical acceptance only; no real database, clinical validity, external validation or scientific acceptance claim"}
    dump(FIX/"fixture-manifest.json",manifest);print(json.dumps({"status":"SYNTHETIC_V05_FIXTURES_READY","development_rows":len(dev),"external_rows":len(external)}))

if __name__=="__main__":main()
