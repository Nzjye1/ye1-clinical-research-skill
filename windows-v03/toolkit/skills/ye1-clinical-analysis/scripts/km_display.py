"""Full synthetic KM display using the unchanged original numerical owner.

The prespecified analysis grid and original result stay unchanged. This optional
display expands only the curve rendering grid to all observed times. It creates
no model, chooses no inferential horizon and never handles real-origin input.
"""
from pathlib import Path
import csv,hashlib,json,sys,subprocess

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def create(task, rows, output, core):
    if task["analysis"]["method_id"]!="survival.kaplan_meier":raise ValueError("KM_DISPLAY_ONLY")
    origin=task.get("data_origin")
    if origin=="real":
        sys.path.insert(0,str(core.parent));import captured_study
        captured_study.verify_context(Path(task["project_root"]),task,core)
    elif origin!="synthetic":raise ValueError("DISPLAY_ORIGIN_UNSUPPORTED")
    import numpy as np
    sys.path.insert(0,str(core/"python"))
    from clinical_methods import survival
    spec=task["analysis"]["survival"]
    _,kept,time,status,_,_,_=survival._validate(rows,spec)
    grid=sorted(set([0.0,*map(float,time)]))
    points=survival._curve(time,status,grid,1)
    display=Path(output)/"display";display.mkdir(exist_ok=False)
    table=display/"km-step.csv"
    with table.open("x",encoding="utf-8",newline="") as f:
        writer=csv.writer(f);writer.writerow(["time","n_at_risk","survival","ci_lower","ci_upper"])
        for point in points:writer.writerow([point["time"],point["at_risk_before_time"],point["event_free_probability"],*point["event_free_ci95"]])
    censored=set(float(t) for t,s in zip(time,status) if s==0)
    marks=display/"censor-marks.csv"
    with marks.open("x",encoding="utf-8",newline="") as f:
        writer=csv.writer(f);writer.writerow(["time","survival"])
        for point in points:
            if point["time"] in censored:writer.writerow([point["time"],point["event_free_probability"]])
    script=Path(__file__).with_name("plot_km.R");runtime=json.loads((core/"runtime-lock.json").read_text(encoding="utf-8"));figure=display/"km-step.png"
    with (display/"plot.log").open("xb") as log:
        done=subprocess.run([runtime["rscript"],"--vanilla",str(script),str(table),str(marks),str(figure),spec["time_unit"],origin],stdout=log,stderr=subprocess.STDOUT,timeout=60)
    if done.returncode!=0 or not figure.is_file():raise ValueError("KM_PLOT_FAILED")
    result=Path(output)/"result.json"
    manifest={"schema_version":"ye1-km-display@2.0","data_origin":origin,"task_purpose":task["task_purpose"],"scientific_review":"pending",
        "source_result_sha256":sha(result),"numerical_owner_sha256":sha(core/"python/clinical_methods/survival.py"),
        "owner_calls":["survival._validate","survival._curve"],"source_rows":len(rows),"n_used":len(kept),"grid":"all observed times for display only; prespecified result grid unchanged",
        "files":[{"path":p.name,"sha256":sha(p)} for p in [table,marks,figure]],"plot_script_sha256":sha(script),"real_patient_validation":False}
    (display/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
