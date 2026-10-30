"""Read-only v06 public/private/source audit; emits a new local receipt only."""
from __future__ import annotations
import csv, hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ATOL=RTOL=1e-10
SECTIONS=("metrics","roc","calibration","dca")

def load(path):return json.loads(Path(path).read_text(encoding="utf-8-sig"))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def table(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as handle:return list(csv.DictReader(handle))
def close(actual,expected):
    assert actual is not None and expected is not None,"null scalar"
    assert math.isfinite(float(actual)) and math.isfinite(float(expected)),"nonfinite export"
    assert abs(float(actual)-float(expected))<=ATOL+RTOL*abs(float(expected)),"scalar differs beyond fixed atol+rtol 1e-10"
def equal(actual,expected):
    if expected is None:assert actual in ("","NA",None),"null/reason projection lost"
    elif isinstance(expected,bool):assert str(actual).lower()==str(expected).lower(),"boolean differs"
    elif type(expected) in (int,float):close(actual,expected)
    else:assert actual==expected,"text semantics differ"
def subset(actual,expected):
    if isinstance(expected,dict):
        assert isinstance(actual,dict)
        for key,value in expected.items():assert key in actual;subset(actual[key],value)
    elif isinstance(expected,list):
        assert isinstance(actual,list) and len(actual)==len(expected)
        for a,b in zip(actual,expected):subset(a,b)
    else:equal(actual,expected)
def ess(values):
    total=math.fsum(values);return total**2/math.fsum(x*x for x in values) if total else None
def source_rows(task):
    view=task["views"][0];path=Path(view["local_ref"]).resolve();assert path.is_relative_to(ROOT)
    rows=[]
    for source in table(path):
        row={}
        for variable in task["variables"]:
            name=variable["name"];value=source[view["column_map"][name]]
            if value in variable["missing_codes"]:row[name]=None
            elif variable["dtype"]=="number":row[name]=float(value)*variable["conversion"]["scale"]+variable["conversion"]["offset"]
            elif variable["dtype"]=="category":row[name]=variable["codes"][value]
            else:row[name]=value
        rows.append(row)
    return rows
def privacy(out,result,counts):
    for path in out.rglob("*"):
        if not path.is_file() or "private" in path.relative_to(out).parts or path.suffix.lower() not in (".json",".csv",".html",".md",".txt"):continue
        text=path.read_text(encoding="utf-8-sig",errors="replace")
        assert all(marker not in text for marker in ("SYNTHETIC-V06-EXT-","SYNTHETIC-V06-HAND-","SYNTHETIC-V05-DEV-")),"private identity escaped"
        assert all('"'+key+'"' not in text for key in ("subject_id","training_subjects","model_json","individual_predictions","individual_ipcw","censoring_grid","coefficients")),"private record fields escaped"
        counts["public_files_scanned"]+=1
    assert result["test_only"] is True and result["export_status"]=="local_only" and result["scientific_review"]=="pending"
    assert not result["metrics"] and not result["estimates"] and result["survival"] is None and result["cox_prediction"] is None

def audit_record(out,result,task,counts):
    public=result["survival_evaluation"];response=load(out/"private/provider-response.json");raw=response["record"]
    subset(public,raw);subset(load(out/"private/backend.json"),raw)
    spec=task["analysis"]["survival"];options=task["analysis"]["survival_evaluation"]
    for key in ("time_unit","time_zero_definition","event_definition","censoring_definition","event_code","censor_code"):equal(public["semantics"][key],spec[key])
    assert public["options"]==options
    assert public["censoring_metadata"]["assumption_verified"] is False and public["censoring_metadata"]["weight_clipping"] is False
    assert public["censoring_metadata"]["source"]=="evaluation_cohort" and public["censoring_metadata"]["full_grid_location"]=="private"
    assert result["diagnostics"]["backend"]["risk_model_refitted"] is False
    assert result["diagnostics"]["backend"]["specialist_metric_package_validation"] is False
    source=Path(task["analysis"]["cox_prediction"]["model_ref"]);model_path=out/"private/frozen_cox_model.json";model=load(model_path)
    assert model_path.read_bytes()==source.read_bytes() and sha(model_path)==task["analysis"]["cox_prediction"]["model_sha256"]
    assert public["model_sha256"]==model["model_sha256"]==result["binding"]["model_hash"]
    payload={key:value for key,value in model.items() if key!="model_sha256"}
    assert hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()).hexdigest()==model["model_sha256"]
    request=load(out/"private/provider-request.json")
    assert request["operation"]=="evaluate" and request["prediction"]["operation"]=="infer"
    assert request["model_json"]==source.read_bytes().decode("utf-8") and "model" not in request
    assert public["frozen_model_provider_version"]==response["frozen_model_provider_version"]==model["provider_version"]
    rows=source_rows(task);n=len(rows);ids=[row[spec["subject_id"]] for row in rows]
    assert len(set(ids))==n and not set(ids).intersection(model["identity"]["training_subjects"])
    assert all(row[spec["time"]] is not None and row[spec["status"]] is not None for row in rows)
    pop=public["population"];assert pop["n_input"]==pop["n_evaluable"]==n and pop["n_dropped_missing"]==0
    assert pop["n_events"]==sum(row[spec["status"]]==spec["event_code"] for row in rows)
    assert pop["n_censored"]==n-pop["n_events"]
    assert result["counts"]["events"]==pop["n_events"] and result["counts"]["censored"]==pop["n_censored"]
    assert result["counts"]["training_n"]==model["training_summary"]["n_complete"]
    individual=table(out/"private/individual_predictions.csv")
    risks={(r["subject_id"],float(r["horizon"])):float(r["event_risk"]) for r in individual}
    assert len(risks)==len(individual)==n*len(public["horizon_results"])
    contributions=load(out/"private/individual_ipcw.json");lookup={(r["subject_id"],r["horizon"]):r for r in contributions}
    assert len(lookup)==len(contributions)==len(individual)
    subset(response["private_evaluation"]["individual_ipcw"],contributions)
    grid=load(out/"private/censoring_grid.json");subset(response["private_evaluation"]["censoring_grid"],grid)
    times=sorted({row[spec["time"]] for row in rows});assert [row["time"] for row in grid]==times
    for point in grid:
        u=point["time"];assert point["n_risk"]==sum(row[spec["time"]]>=u for row in rows)
        assert point["n_events"]==sum(row[spec["time"]]==u and row[spec["status"]]==spec["event_code"] for row in rows)
        assert point["n_censored"]==sum(row[spec["time"]]==u and row[spec["status"]]==spec["censor_code"] for row in rows)
        assert point["censor_risk"]==point["n_risk"]-point["n_events"]
    groups={name:[] for name in ("sample_flow",)+SECTIONS};result_ids=set()
    for h in public["horizon_results"]:
        t=h["horizon"];co=h["counts"];w=h["weights"];items=[lookup[subject,t] for subject in ids];p=[risks[subject,t] for subject in ids]
        assert all(h["diagnostics"][key] is None or 0<=h["diagnostics"][key]<=1 for key in ("km_event_probability","weighted_case_probability"))
        expected_classes=["case" if row[spec["status"]]==spec["event_code"] and row[spec["time"]]<=t else "control" if row[spec["time"]]>t else "censored_by_horizon" for row in rows]
        assert co["n"]==n and co["n_cases"]==expected_classes.count("case") and co["n_controls"]==expected_classes.count("control")
        assert co["n_censored_by_horizon"]==expected_classes.count("censored_by_horizon")
        assert co["n_cases"]+co["n_controls"]+co["n_censored_by_horizon"]==n
        assert co["n_at_risk_before_horizon"]==sum(row[spec["time"]]>=t for row in rows)
        assert co["n_events_at_horizon"]==sum(row[spec["time"]]==t and row[spec["status"]]==spec["event_code"] for row in rows)
        assert co["n_censored_at_horizon"]==sum(row[spec["time"]]==t and row[spec["status"]]==spec["censor_code"] for row in rows)
        for entry,row,classification,risk in zip(items,rows,expected_classes,p):
            assert entry["classification"]==classification and entry["horizon_status"]==h["status"]
            equal(entry["observed_time"],row[spec["time"]]);equal(entry["event_risk"],risk)
            assert entry["event"]==int(row[spec["status"]]==spec["event_code"])
            if classification=="censored_by_horizon":assert entry["g_denominator"] is None
        finite=all(item["weight"] is not None for item in items)
        if finite:
            a=[item["case_weight"] for item in items];b=[item["control_weight"] for item in items];weights=[item["weight"] for item in items]
            for ww,aa,bb in zip(weights,a,b):close(ww,aa+bb)
            for key,expected in (("sum_case_weights",math.fsum(a)),("sum_control_weights",math.fsum(b)),("sum_weights",math.fsum(weights)),("max_weight",max(weights)),("ess",ess(weights)),("case_ess",ess(a)),("control_ess",ess(b))):
                equal(w[key],expected)
            if h["status"]!="unavailable":
                close(math.fsum(weights),n);assert h["diagnostics"]["weight_mass_identity_ok"] is True and h["diagnostics"]["km_identity_ok"] is True
                close(h["diagnostics"]["weighted_case_probability"],h["diagnostics"]["km_event_probability"])
        result_ids.add(h["result_id"]);groups["sample_flow"].append((h,h))
        assert [r["threshold"] for r in h["roc"]]==[None]+list(reversed(options["roc_thresholds"]))
        assert h["roc"][0]["boundary"]=="above_all"
        assert [r["threshold"] for r in h["dca"]]==options["dca_thresholds"]
        for section in SECTIONS:
            for point in h[section]:result_ids.add(point["result_id"]);groups[section].append((point,h))
        for m in h["metrics"]:
            if m["metric"]=="brier":close(m["denominator"],n);assert m["denominator_definition"]=="all_evaluation_subjects_including_early_censoring"
            elif finite:close(m["denominator"],math.fsum(a)*math.fsum(b))
            if m["status"]=="completed":assert 0<=m["value"]<=1;close(m["value"],m["numerator"]/m["denominator"])
            else:assert m["value"] is None and m["reason"]
        if finite:
            for point in h["roc"]:
                selected=[i for i,x in enumerate(p) if point["threshold"] is not None and x>=point["threshold"]]
                assert point["n_treated"]==len(selected);close(point["tp_weight"],math.fsum(a[i] for i in selected));close(point["fp_weight"],math.fsum(b[i] for i in selected))
            for point in h["calibration"]:
                selected=[i for i,x in enumerate(p) if x>=point["lower"] and (x<=point["upper"] if point["right_inclusive"] else x<point["upper"])]
                assert point["n"]==len(selected);close(point["predicted_risk_sum"],math.fsum(p[i] for i in selected))
                if selected:close(point["mean_predicted_risk"],math.fsum(p[i] for i in selected)/len(selected))
                aa=math.fsum(a[i] for i in selected);bb=math.fsum(b[i] for i in selected)
                close(point["sum_case_weights"],aa);close(point["sum_control_weights"],bb);equal(point["ess"],ess([weights[i] for i in selected]))
                if point["status"]=="completed":close(point["observed_risk"],aa/(aa+bb))
                else:assert point["observed_risk"] is None and point["reason"]
            for point in h["dca"]:
                selected=[i for i,x in enumerate(p) if x>=point["threshold"]];assert point["n_treated"]==len(selected)
                assert point["n_treated_cases"]==sum(expected_classes[i]=="case" for i in selected)
                assert point["n_treated_controls"]==sum(expected_classes[i]=="control" for i in selected)
                assert point["n_treated_censored_by_horizon"]==sum(expected_classes[i]=="censored_by_horizon" for i in selected)
                equal(point["treated_ess"],ess([weights[i] for i in selected]));close(point["population_denominator"],n)
                if point["status"]=="completed":
                    close(point["net_benefit_model"],(point["tp_weight"]-point["threshold_odds"]*point["fp_weight"])/n)
                    close(point["net_benefit_all"],(w["sum_case_weights"]-point["threshold_odds"]*w["sum_control_weights"])/n)
                else:assert point["net_benefit_model"] is None and point["net_benefit_all"] is None and point["reason"]
        counts["horizon_source_reconstructions"]+=1
    for section,expected_rows in groups.items():
        exported=table(out/"tables"/f"survival_evaluation_{section}.csv");assert len(exported)==len(expected_rows)
        by_id={point["result_id"]:(point,h) for point,h in expected_rows};assert {row["result_id"] for row in exported}==set(by_id)
        for row in exported:
            point,h=by_id[row["result_id"]]
            for key,value in {"horizon":h["horizon"],"evaluation_n":n,"horizon_status":h["status"],"model_sha256":public["model_sha256"],"time_unit":spec["time_unit"],"uncertainty":"not_implemented","tie_order":"events_before_censoring"}.items():equal(row[key],value)
            if section=="sample_flow":
                for field in ("counts","weights","diagnostics"):
                    for key,value in h[field].items():equal(row[key],value)
                equal(row["full_followup_events"],pop["n_events"]);equal(row["full_followup_censored"],pop["n_censored"])
                equal(row["reason_codes"],";".join(h["reason_codes"]))
                for key,value in public["semantics"].items():equal(row[key],value)
            else:
                for key,value in point.items():equal(row[key],value)
                equal(row["parent_result_id"],h["result_id"])
                if section=="roc":
                    equal(row["case_weight_denominator"],h["weights"]["sum_case_weights"]);equal(row["control_weight_denominator"],h["weights"]["sum_control_weights"])
                if section=="calibration":assert row["predicted_denominator"]=="bin_subject_count" and row["observed_denominator"]=="bin_sum_case_plus_control_weights"
            counts[section+"_csv_rows"]+=1
    expected_artifacts={"survival-evaluation-"+s:(out/"tables"/f"survival_evaluation_{s}.csv",{point["result_id"] for point,h in groups[s]}) for s in groups}
    for i,h in enumerate(public["horizon_results"],1):
        expected_artifacts["survival-evaluation-h"+str(i)]=(out/"figures"/f"survival_evaluation_h{i}.png",{h["result_id"]}|{r["result_id"] for s in SECTIONS for r in h[s]})
    assert {a["artifact_id"] for a in result["tables"]+result["figures"]}==set(expected_artifacts)
    for artifact in result["tables"]+result["figures"]:
        path,ids=expected_artifacts[artifact["artifact_id"]];assert path.is_file() and sha(path)==artifact["data_hash"]
        assert set(artifact["source_result_ids"])==ids and ids<=result_ids and artifact["caption"]
        counts["artifact_hashes"]+=1
    counts["evaluation_runs"]+=1;counts["individual_prediction_rows_audited_locally"]+=len(individual)
    counts["individual_ipcw_rows_audited_locally"]+=len(contributions);counts["private_censoring_grid_rows"]+=len(grid)
    counts["source_cohort_reconstructions"]+=1
    return result_ids

def audit(suite):
    receipt=load(suite/"acceptance-receipt.json");assert receipt["summary"]["failed"]==0,"acceptance contains failures"
    assert receipt["runtime_lock_sha256"]==sha(ROOT/"runtime-lock.json")
    assert all(sha(ROOT/path)==value for path,value in receipt["source_sha256"].items()),"acceptance source binding changed"
    counts={key:0 for key in ("runs","evaluation_runs","public_files_scanned","individual_prediction_rows_audited_locally","individual_ipcw_rows_audited_locally",
      "private_censoring_grid_rows","source_cohort_reconstructions","horizon_source_reconstructions","artifact_hashes","writing_reference_checks")+(tuple(s+"_csv_rows" for s in ("sample_flow",)+SECTIONS))}
    for item in receipt["runs"]:
        out=Path(item["output_dir"]).resolve();assert out.is_relative_to(suite)
        result=load(out/"result.json");task=load(item["task_path"]);assert result["binding"]["input_hash"]==sha(item["task_path"])
        privacy(out,result,counts);ids=set()
        if result.get("survival_evaluation") is not None:ids=audit_record(out,result,task,counts)
        else:assert result["execution_status"]=="blocked" and not result["tables"] and not result["figures"]
        writing=load(out/"writing-references.json");assert set(writing["result_ids"])==ids
        counts["writing_reference_checks"]+=1;counts["runs"]+=1
    assert counts["evaluation_runs"]>=12 and counts["horizon_source_reconstructions"]>=30,"required coverage absent"
    return {"status":"PASS",**counts,"tolerance":{"absolute":ATOL,"relative":RTOL},"runtime_lock_sha256":receipt["runtime_lock_sha256"],
      "acceptance_receipt_sha256":sha(suite/"acceptance-receipt.json"),"scope":"Local source/private/public projections, all subject and weight denominators, ESS, immutable model bytes, exact artifact/result references and privacy boundary; not clinical or specialist-package validation"}
def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT);target=suite/"export-audit.json";assert not target.exists(),"audit receipt exists"
    try:result=audit(suite)
    except Exception as exc:result={"status":"FAIL","reason":type(exc).__name__+": "+str(exc)}
    result["audit_script_sha256"]=sha(__file__);target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result));return int(result["status"]!="PASS")
if __name__=="__main__":raise SystemExit(main())
