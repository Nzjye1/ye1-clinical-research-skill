"""Replay retained v0.9 frozen models through the locked v0.10 public entry.

No training, source-data edits, lock refresh, installation, or old-output writes.
Run only after the parent has bound the final source hashes in runtime-lock.json.
Patient-level inputs and outputs remain in local private subdirectories.
"""
from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode = True
from clinical_test_paths import configure_process, configured_reference, runtime_path
ROOT = Path(__file__).resolve().parents[1]
OLD = configured_reference("CLINICAL_TEST_V09_REVIEW")
OLD_CORE = OLD / "临床 SHAP 列线图 独立副本"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def without_result_ids(value):
    if isinstance(value, dict):
        return {key: without_result_ids(item) for key, item in value.items() if key != "result_id"}
    if isinstance(value, list):
        return [without_result_ids(item) for item in value]
    return value


def table_without_run_metadata(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        assert reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "CSV_COLUMNS_INVALID"
        return [{key: item for key, item in row.items() if key not in {"result_id", "run_id", "core_version"}} for row in reader]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=["apply_g_lasso", "apply_b_enet", "apply_constant_g_lasso"])
    args = parser.parse_args()
    cases = args.case or ["apply_g_lasso", "apply_b_enet"]
    assert len(cases) == len(set(cases)), "DUPLICATE_CASE"
    lock_path = ROOT / "runtime-lock.json"
    lock = load(lock_path)
    source_before = {name: sha(ROOT / name) for name in lock["code_hashes"]}
    assert source_before == lock["code_hashes"], "FINAL_SOURCE_LOCK_REQUIRED"
    lock_before = sha(lock_path)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    evidence = ROOT / "evidence" / f"nomogram-label-p1-v10-public-{stamp}-{uuid.uuid4().hex[:6]}"
    evidence.mkdir(exist_ok=False)
    private_inputs = evidence / "private-inputs"
    private_inputs.mkdir()
    sys.path.insert(0, str(ROOT / "python"))
    spec = importlib.util.spec_from_file_location("nomogram_p1_v10_contracts", ROOT / "python/clinical_methods/contracts.py")
    contracts = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = contracts
    spec.loader.exec_module(contracts)
    review_path = OLD / "INDEPENDENT-V09-INTERPRETATION-REVIEW.txt"
    failure_path = OLD_CORE / "outputs/apply_g_lasso/figures/nomogram.png"
    old_hashes = {str(path): sha(path) for path in [review_path, failure_path]}
    receipt = {
        "status": "RUNNING",
        "scope": "ACTUAL_LOCKED_V10_PUBLIC_ENTRY_FROZEN_REPLAY_NO_TRAINING",
        "runtime_lock_sha256": lock_before,
        "plot_source_sha256": sha(ROOT / "src/clinanalysis/R/clinical_interpretation_v09.R"),
        "numerical_owner_sha256": sha(ROOT / "src/clinanalysis/R/interpretation_v09.R"),
        "cases": [],
        "visual_review": "pending_actual_png_inspection",
    }
    try:
        for case in cases:
            old_task_path = OLD_CORE / "inputs" / f"{case}.json"
            old_output = OLD_CORE / "outputs" / case
            task = copy.deepcopy(load(old_task_path))
            old_hashes[str(old_task_path)] = sha(old_task_path)
            options = task["analysis"]["interpretation"]
            target = private_inputs / case
            target.mkdir()
            for name in ["model_ref", "explainer_ref"]:
                reference = options[name]
                source = Path(reference["local_ref"])
                assert source.resolve().is_relative_to(OLD_CORE.resolve()), "OLD_REFERENCE_SCOPE_INVALID"
                assert sha(source) == reference["content_hash"], "OLD_FROZEN_REFERENCE_HASH_MISMATCH"
                old_hashes[str(source)] = sha(source)
                copied = target / source.name
                shutil.copyfile(source, copied)
                assert sha(copied) == reference["content_hash"], "FROZEN_COPY_CHANGED"
                reference["local_ref"] = str(copied)
            for index, view in enumerate(task["views"]):
                source = Path(view["local_ref"])
                assert source.resolve().is_relative_to(OLD_CORE.resolve()), "OLD_VIEW_SCOPE_INVALID"
                assert sha(source) == view["content_hash"], "OLD_VIEW_HASH_MISMATCH"
                old_hashes[str(source)] = sha(source)
                copied = target / f"application-{index}.csv"
                shutil.copyfile(source, copied)
                view["local_ref"] = str(copied)
            output = evidence / f"run-{case}"
            task["execution"]["output_dir"] = str(output)
            contracts.seal_task(task, ROOT)
            task_path = target / "task.json"
            dump(task_path, task)
            process = subprocess.run(
                [lock["rscript"], "--vanilla", str(ROOT / "tools/run_core.R"), str(task_path), str(output)],
                cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"},
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
            )
            (evidence / f"{case}.stdout.log").write_text(process.stdout, encoding="utf-8")
            (evidence / f"{case}.stderr.log").write_text(process.stderr, encoding="utf-8")
            assert process.returncode == 0, f"PUBLIC_ENTRY_PROCESS_FAILED:{case}"
            result = load(output / "result.json")
            assert result["execution_status"] == "complete", f"PUBLIC_ENTRY_INCOMPLETE:{case}:{result['reason_code']}"
            assert load(output / "private/result-validation.json")["ok"] is True, f"PUBLIC_RESULT_SCHEMA_FAILED:{case}"
            original = load(old_output / "result.json")
            assert without_result_ids(result["interpretation"]) == without_result_ids(original["interpretation"]), f"INTERPRETATION_NUMERIC_DRIFT:{case}"
            assert len(result["tables"]) == 6 and len(result["figures"]) == 2, f"ARTIFACT_COUNT:{case}"
            tables = []
            for artifact in result["tables"]:
                name = artifact["artifact_id"] + ".csv"
                old_table, new_table = old_output / "tables" / name, output / "tables" / name
                assert table_without_run_metadata(old_table) == table_without_run_metadata(new_table), f"TABLE_CONTENT_DRIFT:{case}:{name}"
                old_hashes[str(old_table)] = sha(old_table)
                tables.append({"name": name, "semantic_and_numeric_cells_exact": True, "old_sha256": sha(old_table), "new_sha256": sha(new_table)})
            private_equal = []
            for name in ["interpretation-encoded-contributions.csv", "interpretation-individual-contributions.csv", "interpretation-individual-points.csv"]:
                old_file, new_file = old_output / "private" / name, output / "private" / name
                assert sha(old_file) == sha(new_file), f"PRIVATE_NUMERIC_CSV_DRIFT:{case}:{name}"
                old_hashes[str(old_file)] = sha(old_file)
                private_equal.append({"name": name, "byte_identical": True, "sha256": sha(new_file)})
            receipt["cases"].append({"case": case, "output": str(output), "public_entry_complete": True,
                "schema_passed": True, "interpretation_record_exact_except_result_ids": True,
                "tables": tables, "private_csv_checks": private_equal,
                "frozen_model_sha256": options["model_ref"]["content_hash"],
                "frozen_explainer_sha256": options["explainer_ref"]["content_hash"],
                "figure": str(output / "figures/nomogram.png"), "figure_sha256": sha(output / "figures/nomogram.png")})
        assert old_hashes == {name: sha(name) for name in old_hashes}, "ORIGINAL_EVIDENCE_CHANGED"
        assert source_before == {name: sha(ROOT / name) for name in source_before}, "PRODUCTION_SOURCE_CHANGED_DURING_REPLAY"
        assert lock_before == sha(lock_path), "RUNTIME_LOCK_CHANGED_DURING_REPLAY"
        receipt.update(status="PASS_PENDING_VISUAL_REVIEW", old_sources_unchanged=True,
                       frozen_models_copied_byte_exact=True, production_source_unchanged=True,
                       original_evidence_hashes=old_hashes)
    except Exception as exc:
        receipt.update(status="FAIL", reason=str(exc), original_evidence_hashes=old_hashes)
        dump(evidence / "public-replay-receipt.json", receipt)
        raise
    dump(evidence / "public-replay-receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "evidence": str(evidence), "cases": len(receipt["cases"])}, ensure_ascii=True))


if __name__ == "__main__":
    main()
