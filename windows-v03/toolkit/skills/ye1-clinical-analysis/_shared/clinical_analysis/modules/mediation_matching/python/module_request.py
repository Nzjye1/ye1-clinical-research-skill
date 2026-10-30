"""Build the integrator's private request from either tested literal CSV adapter."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from adapter import normalize, dump, MODULE


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build(manifest_path):
    s, rows, provenance = normalize(manifest_path)
    fs, z, cv = s["fields"], s["semantics"], s["covariates"]
    categories = s["options"].get("categorical", {})
    variables = []
    for role, name in list(fs.items()) + [("covariate", n) for n in cv]:
        if name is None:
            continue
        time_role = {"subject": "identifier", "exposure": "exposure", "covariate": "baseline", "mediator": "mediator",
                     "outcome": "outcome", "time": "followup_duration", "event": "event_at_followup"}[role]
        tm = {"subject": None, "exposure": z["exposure_time"], "covariate": z["covariate_latest_time"],
              "mediator": z["mediator_time"], "outcome": z["outcome_time"], "time": None, "event": None}[role]
        unit = z["time_unit"] if role == "time" else (z["outcome_unit"] if role == "outcome" else ("not_applicable" if role == "subject" else "1"))
        variables.append({"name": name, "dtype": "id" if role == "subject" else ("category" if name in categories else "number"),
                          "role": role, "unit": unit, "time_role": time_role, "measured_at": tm, "available_at": tm})
    encoded = []
    for row in rows:
        record = {"subject_id": row[fs["subject"]], "exposure": row[fs["exposure"]],
                  **{k: row[fs[k]] if fs[k] is not None else None for k in ("mediator", "outcome", "time", "event")},
                  "covariates": [row[k] for k in cv]}
        encoded.append(record)
    structure = {"grain": "subject_wide", "subject_key": fs["subject"], "record_keys": [fs["subject"]], "cluster_key": None,
                 "weights": "none", "missingness": s["options"]["missingness"], "time_origin": z["exposure_time"],
                 "time_unit": z["time_unit"], "analysis_as_of": 100}
    # Development fixture bindings are real hashes. The shared entrypoint must
    # supply/verify its own canonical input/plan/code/runtime binding policy.
    code = {n: hashlib.sha256((MODULE / n).read_bytes()).hexdigest() for n in ("R/provider.R", "R/module_api.R", "R/adapter.R")}
    return {"api_version": "clinical-module-request@1.0", "method_id": s["method_id"], "operation": "analyze",
            "payload": {"spec": s, "structure": structure, "variables": variables, "rows": encoded},
            "bindings": {"input_sha256": canonical_hash(encoded), "plan_sha256": canonical_hash(s), "code_sha256": canonical_hash(code),
                         "runtime_sha256": canonical_hash({"R": "4.6.1", "stats": "4.6.1", "survival": "3.8.6", "jsonlite": "2.0.0", "digest": "0.6.39"}),
                         "model_sha256": None}}


if __name__ == "__main__":
    dump(build(sys.argv[1]), sys.argv[2])
    print("PRIVATE_SYNTHETIC_MODULE_REQUEST_WRITTEN")
