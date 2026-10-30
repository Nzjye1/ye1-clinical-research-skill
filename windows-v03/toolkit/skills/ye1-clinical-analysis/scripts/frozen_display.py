"""Local restricted graphics from already-computed frozen predictions only."""
from pathlib import Path
import csv,json,subprocess
from runtime_toolkit import ROOT,load,save,sha,env,need

def create(task,result,out,core):
    out=Path(out)
    if list((out/"figures").glob("*.png")):return None
    candidates=[out/"private/penalized-individual-predictions.csv",out/"private/cox-penalized-individual-predictions.csv"]
    if result["method_id"] in {"prediction.binary.ridge","prediction.continuous.nonnegative.ridge"}:candidates.append(out/"private/individual-predictions.json")
    if result["method_id"] in {"prediction.binary.random_forest","prediction.binary.hist_gradient_boosting"}:candidates.append(out/"private/module-response.json")
    source=next((p for p in candidates if p.is_file()),None)
    if source is None:return None
    if task["data_origin"]=="real":
        import sys
        sys.path.insert(0,str(core.parent));import captured_study
        captured_study.verify_context(Path(task["project_root"]),task,core)
    if source.suffix==".json":columns=["prediction"]
    else:
        with source.open(encoding="utf-8-sig",newline="") as stream:columns=next(csv.reader(stream))
    prediction="prediction" if "prediction" in columns else "risk" if "risk" in columns else None
    need(prediction is not None,"FROZEN_DISPLAY_PREDICTION_COLUMN_REQUIRED")
    method=result["method_id"];analysis=task.get("analysis",{});options=next((analysis[k] for k in ("penalized_prediction","cox_penalized_prediction","prediction","cox_prediction") if isinstance(analysis.get(k),dict)),{});operation=task.get("operation",options.get("operation"))
    kind="binary" if method.startswith("prediction.binary.") else "risk" if method.startswith("prediction.survival.") else "continuous"
    # No rows pass through the Agent/Python response. The local R plotter reads
    # the existing private artifact inside this already-admitted invocation.
    folder=out/"private/frozen-display";folder.mkdir(exist_ok=False);request=folder/"display-request.json";image=folder/"frozen-predictions.png";countfile=folder/"counts.json"
    source_hash=sha(source)
    module_json=source.name=="module-response.json"
    normalized=out/"private/task-snapshot.json" if module_json else out/"private/normalized.json";normalized_hash=sha(normalized) if source.suffix==".json" else None
    save(request,{"source":str(source),"format":"module_json" if module_json else "json" if source.suffix==".json" else "csv","source_sha256":source_hash,"normalized":str(normalized) if normalized_hash else None,"subject_key":task.get("payload",{}).get("spec",{}).get("id") if module_json else task.get("identity",{}).get("subject_key"),"prediction":prediction,"observed":"observed" if operation=="evaluate" and "observed" in columns else None,"kind":kind,"operation":operation,"method_id":method,"time_unit":task.get("time",{}).get("unit"),"image":str(image),"counts":str(countfile),"prediction_table":str(folder/"predictions.csv")})
    profile=load(ROOT/".runtime/toolkit-profile.json")
    with (folder/"display.log").open("xb") as stream:
        done=subprocess.run([profile["rscript"],"--vanilla",str(ROOT/"scripts/plot_frozen.R"),str(ROOT/".runtime/r-library"),str(request)],env=env(),stdout=stream,stderr=subprocess.STDOUT,timeout=60)
    need(done.returncode==0 and image.is_file() and countfile.is_file(),"FROZEN_LOCAL_DISPLAY_INCOMPLETE")
    need(sha(source)==source_hash,"FROZEN_DISPLAY_SOURCE_CHANGED")
    if normalized_hash:need(sha(normalized)==normalized_hash,"FROZEN_DISPLAY_IDENTITY_SOURCE_CHANGED")
    counts=load(countfile)
    with (folder/"summary.csv").open("x",encoding="utf-8-sig",newline="") as stream:
        writer=csv.writer(stream);writer.writerow(["item","value"]);writer.writerows((k,v) for k,v in counts.items() if isinstance(v,(int,float,str,bool)))
    manifest={"schema_version":"ye1-frozen-local-display@1.0","classification":"local_private","data_origin":task["data_origin"],"method_id":method,"operation":operation,"source_result_sha256":sha(out/"result.json"),"source_predictions":{"path":source.relative_to(out).as_posix(),"sha256":sha(source)},"normalized_identity_source_sha256":normalized_hash,"image":{"path":image.relative_to(out).as_posix(),"sha256":sha(image)},"prediction_table":{"path":"private/frozen-display/predictions.csv","sha256":sha(folder/"predictions.csv")},"counts":counts,"model_refitted":False,"clinical_metric_computed":False,"patient_identifiers_plotted":False,"automatic_export":False,"scientific_review":"pending"}
    save(folder/"manifest.json",manifest);return folder/"manifest.json"
