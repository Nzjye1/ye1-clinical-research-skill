"""Literal local CSV adapter and R transport, never an estimator.

Development outputs are confined to this module. Patients/IDs are never printed.
The integrated caller must preserve its stronger existing governance checks.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

MODULE = Path(__file__).resolve().parents[1]
BASELINE = MODULE.parents[1] / "integration" / "core"
RSCRIPT = Path(json.loads((BASELINE / "runtime-lock.json").read_text(encoding="utf-8-sig"))["rscript"])
sys.path.insert(0, str(BASELINE / "python"))
from clinical_methods import resource_budget as budgets


class ContractError(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise ContractError(code)


def keys(value, expected):
    return isinstance(value, dict) and set(value) == set(expected)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "MM_DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(ContractError("MM_NONFINITE_JSON")))


def dump(value, path):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _resource_limits(method, resource_budget):
    try:
        return budgets.request_limits({}, method) if resource_budget is None else budgets.validate_limits(resource_budget, method)
    except budgets.BudgetError as error:
        raise ContractError(error.code) from None


def normalize(manifest_path, *, resource_budget=None):
    manifest_path = Path(manifest_path).resolve()
    m = load(manifest_path)
    need(keys(m, {"spec", "source"}), "MM_MANIFEST_KEYS_INVALID")
    s, src = m["spec"], m["source"]
    need(keys(s, {"schema_version", "method_id", "fields", "covariates", "semantics", "options", "execution"}), "MM_SPEC_KEYS_INVALID")
    need(s["execution"] == {"test_only": True, "data_origin": "synthetic"}, "MM_SYNTHETIC_ONLY")
    limits = _resource_limits(s["method_id"], resource_budget)
    need(keys(src, {"source_id", "file", "sha256", "column_map", "units"}), "MM_SOURCE_KEYS_INVALID")
    need(isinstance(src["source_id"], str) and bool(src["source_id"].strip()), "MM_SOURCE_ID_REQUIRED")
    path = (manifest_path.parent / src["file"]).resolve()
    need(path.is_file() and path.stat().st_size <= 2_000_000, "MM_SOURCE_FILE_INVALID")
    need(sha(path) == src["sha256"], "MM_SOURCE_HASH_MISMATCH")
    fields = s["fields"]
    need(keys(fields, {"subject", "exposure", "outcome", "mediator", "time", "event"}), "MM_FIELD_KEYS_INVALID")
    needed = [v for v in fields.values() if v is not None] + s["covariates"]
    need(all(isinstance(v, str) and v for v in needed) and len(needed) == len(set(needed)), "MM_FIELDS_INVALID")
    mapping = src["column_map"]
    need(keys(mapping, needed) and len(set(mapping.values())) == len(mapping), "MM_COLUMN_MAP_INVALID")
    categories = {} if s["method_id"] == "mediation.linear.binary_exposure" else s["options"].get("categorical", {})
    numeric = set(needed) - {fields["subject"]} - set(categories)
    need(keys(src["units"], numeric), "MM_UNITS_REQUIRED")
    for name, unit in src["units"].items():
        need(keys(unit, {"source_unit", "target_unit", "multiplier", "offset"}), "MM_UNIT_SPEC_INVALID")
        need(all(isinstance(unit[k], str) and unit[k] for k in ("source_unit", "target_unit")), "MM_UNIT_SPEC_INVALID")
        need(all(type(unit[k]) in (int, float) and math.isfinite(unit[k]) for k in ("multiplier", "offset"))
             and unit["multiplier"] > 0, "MM_UNIT_CONVERSION_INVALID")
        if name in (fields["exposure"], fields["event"]) or (s["options"].get("outcome_type") == "binary" and name == fields["outcome"]):
            need(unit == {"source_unit": "1", "target_unit": "1", "multiplier": 1, "offset": 0}, "MM_BINARY_CODE_CONVERSION_FORBIDDEN")
        if name == fields["time"]:
            need(unit["target_unit"] == s["semantics"]["time_unit"] and unit["offset"] == 0, "MM_TIME_UNIT_MISMATCH")
        if name == fields["outcome"]:
            need(unit["target_unit"] == s["semantics"]["outcome_unit"], "MM_OUTCOME_UNIT_MISMATCH")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        need(reader.fieldnames is not None and len(set(reader.fieldnames)) == len(reader.fieldnames), "MM_CSV_HEADER_INVALID")
        need(set(mapping.values()).issubset(reader.fieldnames), "MM_CSV_COLUMN_MISSING")
        rows = []
        for row in reader:
            need(None not in row and all(v is not None for v in row.values()), "MM_CSV_ROW_WIDTH_INVALID")
            out = {}
            for name in needed:
                raw = row[mapping[name]]
                if name not in numeric:
                    out[name] = raw
                elif raw == "":
                    out[name] = None
                else:
                    try:
                        value = float(raw)
                    except ValueError:
                        raise ContractError("MM_NONNUMERIC_CELL") from None
                    need(math.isfinite(value), "MM_NONFINITE_CELL")
                    unit = src["units"][name]
                    value = value * unit["multiplier"] + unit["offset"]
                    need(math.isfinite(value), "MM_NONFINITE_UNIT_CONVERSION")
                    out[name] = value
            rows.append(out)
        try:
            budgets.check_rows(len(rows), limits)
        except budgets.BudgetError as error:
            raise ContractError(error.code) from None
    if s["method_id"] != "mediation.linear.binary_exposure":
        exposure = s["fields"]["exposure"]
        need(sum(row[exposure] == 1 for row in rows) * sum(row[exposure] == 0 for row in rows)
             <= limits["max_candidate_pairs"], "RESOURCE_CANDIDATE_PAIR_BUDGET_EXCEEDED")
    return s, rows, {"source_id": src["source_id"], "source_sha256": src["sha256"],
                     "adapter_manifest_sha256": sha(manifest_path), "python_adapter_sha256": sha(__file__)}


def run(manifest_path, output_dir, *, resource_budget=None):
    output_dir = Path(output_dir).resolve()
    need(output_dir.is_relative_to(MODULE) and output_dir != MODULE, "MM_DEV_OUTPUT_OUTSIDE_MODULE")
    need(not output_dir.exists(), "MM_OUTPUT_ALREADY_EXISTS")
    spec, rows, provenance = normalize(manifest_path, resource_budget=resource_budget)
    private = output_dir / "private"
    private.mkdir(parents=True)
    dump(spec, private / "spec.json")
    dump(provenance, private / "source-binding.json")
    dump(_resource_limits(spec["method_id"], resource_budget), private / "resource-budget.json")
    with (private / "canonical.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    result = subprocess.run([str(RSCRIPT), "--vanilla", str(MODULE / "R/run.R"), str(MODULE),
                             str(private / "spec.json"), str(output_dir), str(BASELINE), str(private / "resource-budget.json")], cwd=MODULE,
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    # Local engine log may include diagnostic metadata, never print raw data/errors.
    (private / "engine.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    need(result.returncode == 0 and (output_dir / "result.json").is_file(), "MM_R_TRANSPORT_FAILED")
    public = load(output_dir / "result.json")
    return {"status": public["status"], "reason_code": public["reason_code"], "method_id": public["method_id"]}


if __name__ == "__main__":
    try:
        need(len(sys.argv) == 3, "MM_CLI_ARGUMENTS_INVALID")
        print(json.dumps(run(sys.argv[1], sys.argv[2]), ensure_ascii=False))
    except ContractError as error:
        print(json.dumps({"status": "blocked", "reason_code": str(error)}))
        sys.exit(2)
    except Exception:
        print(json.dumps({"status": "failed", "reason_code": "MM_ADAPTER_EXECUTION_FAILED"}))
        sys.exit(3)
