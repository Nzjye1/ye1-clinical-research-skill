"""Read-only audit of completed v05 runs; writes one new local audit receipt."""
from __future__ import annotations
import csv, hashlib, json, math, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ATOL=1e-8
ARTIFACT_FILES={"ph-score-tests":"tables/ph_score_tests.csv",
 "cox-prediction-summary":"tables/cox_prediction_summary.csv","cox-prediction-sample-flow":"tables/cox_prediction_sample_flow.csv",
 "cox-predicted-risk":"figures/cox_predicted_risk.png","survival-curve-risk-table":"tables/survival_curve.csv",
 "survival-summary":"tables/survival_summary.csv","ph-descriptive-diagnostics":"tables/ph_diagnostics.csv",
 "effect-estimates":"tables/effect_estimates.csv","survival-curve":"figures/survival.png","association-forest":"figures/effects.png"}

def load(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def table(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as handle:return list(csv.DictReader(handle))
def close(a,b):
    assert math.isfinite(float(a)) and math.isfinite(float(b)),"nonfinite export"
    assert abs(float(a)-float(b))<=ATOL,"CSV/private/public scalar mismatch"
def equal(a,b):
    if b is None:assert a in ("","NA",None),"null must remain explicit"
    elif isinstance(b,bool):assert str(a).lower()==str(b).lower()
    elif isinstance(b,(int,float)):close(a,b)
    else:assert a==b,"text semantics mismatch"

def source_rows(task):
    view=task["views"][0];source=Path(view["local_ref"]).resolve();assert source.is_relative_to(ROOT)
    source_data=table(source);variables=task["variables"];result=[]
    for row in source_data:
        target={}
        for variable in variables:
            name=variable["name"];value=row[view["column_map"][name]]
            if value in variable["missing_codes"]:target[name]=None
            elif variable["dtype"]=="number":target[name]=float(value)*variable["conversion"]["scale"]+variable["conversion"]["offset"]
            elif variable["dtype"]=="category":target[name]=variable["codes"][value]
            else:target[name]=value
        result.append(target)
    return result

def audit_ph(out,result,raw,counts):
    public=result["survival"].get("ph_score_test")
    if public is None:return set()
    original=raw["ph_test"]
    assert public["method"]==original["method"]=="cox_score" and public["ph_assumption_verified"] is False
    assert public["status"]==original["status"]
    for key in ("transform","terms","singledf","global"):assert public[key]==original[key]
    assert public["ties"]=="breslow"
    assert public["terms"] is True and public["singledf"] is False and public["global"] is True
    original_rows=original.get("table",original.get("tests",[]));expected={row["term"]:row for row in original_rows}
    assert len(public["tests"])==len(expected)
    ids=set()
    for row in public["tests"]:
        target=expected[row["term"]];ids.add(row["result_id"])
        for field in ("chisq","df","p_value"):equal(row[field],target[field])
        assert row["status"]==target["status"]
        assert row["denominator"]==raw["n_used"] and row["events"]==raw["target_events"]
        if target.get("p_value") is None:
            assert row["chisq"] is None and row.get("reason"),"unavailable PH row lost null/reason"
        else:assert 0<=row["p_value"]<=1 and row["chisq"]>=0
    if ids:
        exported=table(out/"tables/ph_score_tests.csv");assert len(exported)==len(ids)
        points={row["result_id"]:row for row in public["tests"]}
        for row in exported:
            point=points[row["result_id"]]
            for key in ("term","chisq","df","p_value","status","denominator","events"):equal(row[key],point[key])
            for key in ("method","transform","ties"):equal(row[key],public[key])
            equal(row["reason"],point.get("reason"));equal(row["ph_assumption_verified"],False)
            counts["formal_ph_csv_rows"]+=1
    return ids

def audit_prediction(out,result,raw,task,counts):
    public=result.get("cox_prediction")
    if public is None:return set()
    assert not result["estimates"] and not result["metrics"] and result["survival"] is None
    assert public["uncertainty"]=="not_implemented" and public["summary_estimand"]=="mean_frozen_predicted_absolute_event_risk"
    spec=task["analysis"]["survival"];options=task["analysis"]["cox_prediction"]
    for key in ("time_unit","time_zero_definition","event_definition","censoring_definition","event_code","censor_code"):
        assert public["semantics"][key]==spec[key]
    for key,value in raw.items():
        if key!="prediction_summary":assert public[key]==value,"public prediction metadata differs from raw"
    model_path=out/"private/frozen_cox_model.json";model=load(model_path)
    assert public["model_sha256"]==model["model_sha256"]==result["binding"]["model_hash"]
    payload={key:value for key,value in model.items() if key!="model_sha256"}
    assert hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")).hexdigest()==model["model_sha256"]
    assert public["baseline_convention"]==model["baseline"]["convention"]=="right_continuous_breslow"
    assert model["feature_semantics"],"canonical feature semantics absent from frozen model"
    variables={variable["name"]:variable for variable in task["variables"]}
    assert [feature["name"] for feature in model["feature_semantics"]]==[covariate["name"] for covariate in spec["covariates"]]
    for feature in model["feature_semantics"]:
        declared=variables[feature["name"]]
        for key in ("name","dtype","role","unit","dimension","concept","levels","reference"):assert feature[key]==declared[key]
        for key in ("occurred_at","available_at"):close(feature[key],declared[key])
    if options["operation"]=="infer":
        source=Path(options["model_ref"]);assert sha(source)==options["model_sha256"]
        assert model_path.read_bytes()==source.read_bytes(),"inference must retain exact immutable model serialization"
        request=load(out/"private/provider-request.json")
        assert request["model_json"]==source.read_text(encoding="utf-8-sig"),"native model JSON text changed across R transport"
        assert "model" not in request,"parsed model object should not cross R serialization"
    individual=table(out/"private/individual_predictions.csv");assert individual
    fields={"subject_id","horizon","survival_probability","event_risk"};assert set(individual[0])==fields
    source=source_rows(task);pop=public["analysis_population"]
    ids=[row[spec["subject_id"]] for row in source]
    apply_ids=set(options["holdout_subjects"]) if options["operation"]=="train" else set(ids)
    assert {row["subject_id"] for row in individual}==apply_ids
    assert len(individual)==len(apply_ids)*len(options["horizons"])
    assert len(set((row["subject_id"],float(row["horizon"])) for row in individual))==len(individual)
    assert not apply_ids.intersection(model["identity"]["training_subjects"])
    assert pop["n_input"]==len(source) and pop["n_predicted"]==len(apply_ids)
    application=[row for row in source if row[spec["subject_id"]] in apply_ids]
    assert pop["n_predicted_events"]==sum(row[spec["status"]]==spec["event_code"] for row in application)
    assert pop["n_predicted_censored"]==sum(row[spec["status"]]==spec["censor_code"] for row in application)
    assert pop["n_predicted_missing_status"]==sum(row[spec["status"]] is None for row in application)
    assert pop["n_predicted_missing_time"]==sum(row[spec["time"]] is None for row in application)
    assert pop["n_predicted_events"]+pop["n_predicted_censored"]+pop["n_predicted_missing_status"]==pop["n_predicted"]
    assert pop["n_training_events"]+pop["n_training_censored"]==pop["n_training_complete"]
    if options["operation"]=="train":
        selected=[row for row in source if row[spec["subject_id"]] in set(options["training_subjects"])]
        required=[spec["time"],spec["status"]]+[v["name"] for v in spec["covariates"]]
        complete=[row for row in selected if all(row[name] is not None for name in required)]
        assert pop["n_training_declared"]==len(selected) and pop["n_training_complete"]==len(complete)
        assert pop["n_dropped_training_missing"]==len(selected)-len(complete)
        assert pop["n_training_events"]==sum(row[spec["status"]]==spec["event_code"] for row in complete)
        assert pop["n_holdout"]==len(apply_ids)
        missing={name:sum(row[name] is None for row in selected) for name in required};missing={name:n for name,n in missing.items() if n}
        assert pop["training_missing_by_field"]==missing
        assert public["support"]["last_event_time"]==max(row[spec["time"]] for row in complete if row[spec["status"]]==spec["event_code"])
        assert public["support"]["max_observed_time"]==max(row[spec["time"]] for row in complete)
    summary={row["horizon"]:row for row in public["prediction_summary"]};raw_summary={row["horizon"]:row for row in raw["prediction_summary"]}
    assert set(summary)==set(options["horizons"])
    result_ids=set()
    for horizon,row in summary.items():
        result_ids.add(row["result_id"])
        for key,value in raw_summary[horizon].items():equal(row[key],value)
        values=[entry for entry in individual if float(entry["horizon"])==horizon]
        assert row["n"]==len(values)==len(apply_ids)
        for field in ("survival_probability","event_risk"):
            numbers=[float(entry[field]) for entry in values];assert all(0<=number<=1 for number in numbers)
            for suffix,value in (("min",min(numbers)),("mean",math.fsum(numbers)/len(numbers)),("max",max(numbers))):close(row[field+"_"+suffix],value)
        close(row["survival_probability_mean"]+row["event_risk_mean"],1)
        if horizon==0:assert row["event_risk_max"]==0
    exported=table(out/"tables/cox_prediction_summary.csv");assert len(exported)==len(summary)
    for row in exported:
        point=summary[float(row["horizon"])];assert row["result_id"]==point["result_id"]
        equal(row["denominator"],point["n"])
        for field in ("survival_probability","event_risk"):
            for suffix in ("min","mean","max"):equal(row[field+"_"+suffix],point[field+"_"+suffix])
        assert row["scale"]=="absolute_event_risk" and row["uncertainty"]=="not_implemented"
        assert row["time_unit"]==spec["time_unit"] and row["model_sha256"]==model["model_sha256"]
        equal(row["prediction_events"],pop["n_predicted_events"]);equal(row["prediction_censored"],pop["n_predicted_censored"])
        counts["prediction_summary_csv_rows"]+=1
    flow=table(out/"tables/cox_prediction_sample_flow.csv");assert len(flow)==1;row=flow[0]
    for key,value in pop.items():
        if key in row:equal(row[key],value)
    for key,value in public["semantics"].items():equal(row[key],value)
    equal(row["last_training_event"],public["support"]["last_event_time"])
    equal(row["max_training_observed_time"],public["support"]["max_observed_time"])
    equal(row["baseline_convention"],public["baseline_convention"])
    counts["prediction_runs"]+=1;counts["individual_rows_audited_locally"]+=len(individual)
    counts["source_denominator_reconstructions"]+=1
    return result_ids

def audit(suite):
    receipt=load(suite/"acceptance-receipt.json")
    assert receipt["runtime_lock_sha256"]==sha(ROOT/"runtime-lock.json"),"production lock differs from acceptance"
    counts={"runs":0,"public_files_scanned":0,"formal_ph_csv_rows":0,"prediction_summary_csv_rows":0,"prediction_runs":0,
            "individual_rows_audited_locally":0,"source_denominator_reconstructions":0,"artifact_hashes":0,"writing_reference_checks":0}
    for run in receipt["runs"]:
        out=Path(run["output_dir"]).resolve();assert out.is_relative_to(suite)
        result=load(out/"result.json");task=load(run["task_path"]);counts["runs"]+=1
        assert result["binding"]["input_hash"]==sha(run["task_path"])
        assert result["test_only"] is True and result["scientific_review"]=="pending" and result["export_status"]=="local_only"
        for path in out.rglob("*"):
            if not path.is_file() or "private" in path.relative_to(out).parts or path.suffix.lower() not in (".json",".csv",".html",".md",".txt"):continue
            text=path.read_text(encoding="utf-8-sig",errors="replace")
            assert "SYNTHETIC-V05-DEV-" not in text and "SYNTHETIC-V05-EXT-" not in text,"individual identity exposed in public artifact"
            counts["public_files_scanned"]+=1
        raw=load(out/"private/backend.json") if (out/"private/backend.json").exists() else None
        ids={entry["result_id"] for entry in result["estimates"]}
        if result.get("survival") is not None:
            ids.update(row["result_id"] for row in result["survival"]["curves"])
            if raw is not None:ids.update(audit_ph(out,result,raw,counts))
        if result.get("cox_prediction") is not None:ids.update(audit_prediction(out,result,raw,task,counts))
        for artifact in result["tables"]+result["figures"]:
            path=out/ARTIFACT_FILES[artifact["artifact_id"]];assert path.is_file() and sha(path)==artifact["data_hash"]
            assert set(artifact["source_result_ids"])<=ids
            if artifact["artifact_id"].startswith("cox-prediction") or artifact["artifact_id"]=="cox-predicted-risk":
                expected={row["result_id"] for row in result["cox_prediction"]["prediction_summary"]}
                assert set(artifact["source_result_ids"])==expected
                assert "predict" in artifact["caption"].lower() or "training" in artifact["caption"].lower()
            if artifact["artifact_id"]=="ph-score-tests":assert set(artifact["source_result_ids"])=={row["result_id"] for row in result["survival"]["ph_score_test"]["tests"]}
            counts["artifact_hashes"]+=1
        writing=load(out/"writing-references.json");assert set(writing["result_ids"])==ids
        counts["writing_reference_checks"]+=1
    assert counts["prediction_runs"]>=7 and counts["formal_ph_csv_rows"]>=12,"required completed prediction/PH coverage absent"
    return {"status":"PASS",**counts,"scalar_absolute_tolerance":ATOL,"runtime_lock_sha256":receipt["runtime_lock_sha256"],
            "acceptance_receipt_sha256":sha(suite/"acceptance-receipt.json"),"scope":"Public/raw/private scalar projection, independent source counts, immutable model bytes, local-only individual data, result provenance and artifact hashes; no refitting or clinical acceptance"}

def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT)
    target=suite/"export-audit.json";assert not target.exists(),"audit receipt already exists"
    try:value=audit(suite)
    except Exception as exc:value={"status":"FAIL","reason":type(exc).__name__+": "+str(exc)}
    value["audit_script_sha256"]=sha(Path(__file__));target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(value));return int(value["status"]!="PASS")

if __name__=="__main__":raise SystemExit(main())
