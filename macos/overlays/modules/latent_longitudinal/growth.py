"""Strict long-table validation and transport to the single R growth owner."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import numpy as np
if __package__:
    from .contracts import need, number
else:
    from contracts import need, number


def prepare(rows, spec, operation, model=None):
    keys, observed, subjects = set(), [], {}
    cols = [f["name"] for f in spec["covariates"]]
    time, outcome, subject = spec["time"]["name"], spec["outcome"]["name"], spec["subject_id"]
    missing_rows = 0
    for index, row in enumerate(rows):
        needed = {time, *cols} | ({outcome} if operation == "train" else set())
        need(needed <= set(row), "LONGITUDINAL_COLUMN_ABSENT")
        need(number(row[time]), "TIME_MUST_BE_FINITE_OBSERVED_NUMBER")
        key = (row[subject], row[time])
        need(key not in keys, "DUPLICATE_SUBJECT_TIME")
        keys.add(key)
        values = [row[c] for c in cols] + ([row[outcome]] if operation == "train" else [])
        need(all(v is None or number(v) for v in values), "LONGITUDINAL_NUMERIC_VALUES_REQUIRED")
        if any(v is None for v in values):
            need(operation == "train", "MISSING_EXTERNAL_COVARIATE")
            missing_rows += 1
            continue
        normalized = {"id": row[subject], "time": row[time], "row_index": index,
                      "yy": row[outcome] if operation == "train" else 0}
        normalized.update({"x"+str(j+1): row[c] for j, c in enumerate(cols)})
        observed.append(normalized)
        subjects.setdefault(row[subject], []).append(row[time])
    need(bool(observed), "NO_ANALYZABLE_ROWS")
    if operation == "train":
        need(len(subjects) >= 20 and len(subjects) <= 3000, "GROWTH_SUBJECT_COUNT_OUTSIDE_VALIDATED_LIMIT")
        min_times = 3 if spec["random"] == "intercept_slope" or spec["degree"] == 2 else 2
        need(all(len(set(t)) >= min_times for t in subjects.values()), "INSUFFICIENT_WITHIN_SUBJECT_TIMES")
        ys = np.array([r["yy"] for r in observed])
        need(np.std(ys) > 1e-10, "CONSTANT_GROWTH_OUTCOME")
    else:
        time_range = model["time_range"]
        need(all(time_range[0] <= r["time"] <= time_range[1] for r in observed),
             "EXTERNAL_TIME_EXTRAPOLATION_REJECTED")
    return observed, {"input_rows": len(rows), "analysis_rows": len(observed),
                      "input_subjects": len({r[subject] for r in rows}), "analysis_subjects": len(subjects),
                      "excluded_missing_rows": missing_rows}


def analyze(rows, spec, operation, runtime, workdir, frozen=None):
    model = frozen["model"] if frozen else None
    normalized, counts = prepare(rows, spec, operation, model)
    workdir = Path(workdir)
    request_path, response_path = workdir/"growth-engine-request.json", workdir/"growth-engine-response.json"
    runtime_path = workdir/"runtime.json"
    request_path.write_text(json.dumps({"operation": operation, "data": normalized, "spec": spec,
                                      "model": model}, allow_nan=False), encoding="utf-8")
    runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
    env = os.environ.copy()
    env["R_LIBS"] = os.pathsep.join(runtime["r_libraries"])
    # The parent shell can export C.UTF-8, which Windows R cannot set.
    for key in ["LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MONETARY", "LC_TIME", "LANG"]:
        env.pop(key, None)
    run = subprocess.run([runtime["rscript"], "--vanilla", str(Path(__file__).with_name("growth_engine.R")),
                          str(request_path), str(response_path), str(runtime_path)],
                         env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    (workdir/"growth-engine.log").write_text(run.stdout+run.stderr, encoding="utf-8")
    need(run.returncode == 0 and response_path.is_file(), "GROWTH_ENGINE_PROCESS_FAILED")
    out = json.loads(response_path.read_text(encoding="utf-8-sig"))
    need(out.get("ok") is True, out.get("reason_code", "GROWTH_ENGINE_RESULT_INVALID"))
    record = out["record"]
    record["counts"] = counts
    record["warnings"] = ["ORDINARY_MIXED_GROWTH_NOT_LATENT_TRAJECTORY",
                          "MISSING_AT_RANDOM_AND_MODEL_ASSUMPTIONS_UNVERIFIED",
                          "POINTWISE_MEAN_INTERVALS_NOT_INDIVIDUAL_PREDICTION_INTERVALS"]
    if operation == "predict":
        record["warnings"].append("FROZEN_POPULATION_MEAN_NO_EXTERNAL_PERFORMANCE_CLAIM")
    return record, out["model"], None, out.get("private", [])
