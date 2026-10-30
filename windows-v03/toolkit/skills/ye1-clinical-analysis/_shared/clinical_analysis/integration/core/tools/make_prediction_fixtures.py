"""Small paired synthetic adapters for the v0.2 prediction acceptance.

No database, patient identifiers, external I/O or package installation.
"""
from __future__ import annotations
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"
FIELDS = ["id", "x", "z", "category", "y", "binary", "site", "time", "label_ready"]
MAP = {"id": "patientunitstayid", "x": "feature_percent", "z": "age_months",
       "category": "category_code", "y": "continuous_endpoint", "binary": "endpoint_status",
       "site": "hospital_code", "time": "prediction_hour", "label_ready": "label_ready_hour"}


def load_contracts():
    sys.path.insert(0, str(ROOT / "python" / "clinical_methods"))
    spec = importlib.util.spec_from_file_location("prediction_fixture_contracts", ROOT / "python/clinical_methods/contracts.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def synthetic(n, seed, prefix):
    rng = np.random.default_rng(seed)
    x = rng.integers(-8, 9, n) / 4.0
    age = rng.integers(25, 76, n)
    category = rng.integers(0, 2, n)
    eta = -.15 + .55 * x + .018 * (age - 50) + .25 * category
    probability = 1 / (1 + np.exp(-eta))
    binary = rng.binomial(1, probability)
    y = 70 + 8 * x + .25 * (age - 50) + 4 * category + rng.integers(-9, 10, n)
    rows = []
    for i in range(n):
        rows.append({"id": prefix + f"{i:08d}", "x": "" if i % 19 == 0 else float(x[i]),
                     "z": "" if i % 23 == 0 else int(age[i]),
                     "category": "" if i % 29 == 0 else str(category[i]),
                     "y": "" if i in {17, 93} else float(y[i]),
                     "binary": "" if i in {27, 117} else str(binary[i]),
                     "site": "S" + str(i % 20).zfill(2), "time": i * 100,
                     "label_ready": i * 100 + 24})
    return rows


def write_csv(path, rows, fields=FIELDS):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def mapped(rows):
    values = []
    for row in rows:
        out = {MAP[k]: v for k, v in row.items()}
        out[MAP["x"]] = "-999" if row["x"] == "" else float(row["x"]) * 100
        out[MAP["z"]] = "-999" if row["z"] == "" else int(row["z"]) * 12
        out[MAP["category"]] = "UNK" if row["category"] == "" else {"0": "A", "1": "B"}[row["category"]]
        out[MAP["y"]] = "-999" if row["y"] == "" else row["y"]
        out[MAP["binary"]] = "UNK" if row["binary"] == "" else {"0": "no", "1": "yes"}[row["binary"]]
        values.append(out)
    return values


def prepare_task(contracts, path, out, method, database="MIMIC", operation="train", model_ref=None):
    builder_path = Path(str(path).replace("prediction-eicu-", "prediction-canonical-")) if database.lower()=="eicu" else path
    task = contracts.make_prediction_task(str(builder_path), str(out), str(ROOT), method,
                                         operation=operation, model_ref=model_ref)
    task["views"][0]["local_ref"] = str(Path(path).resolve())
    task["study_id"] = "synthetic-prediction-paired-adapter"
    task["sources"][0]["database"] = database
    for var in task["variables"]:
        if var["name"] == "z":
            var.update(source_unit="year",unit="year",dimension="time",conversion={"scale":1,"offset":0})
    if database.lower() == "eicu":
        task["views"][0]["column_map"] = dict(MAP)
        for var in task["variables"]:
            name = var["name"]
            if name == "x":
                var.update(source_unit="percent", unit="1", dimension="dimensionless",
                           conversion={"scale": .01, "offset": 0}, missing_codes=["-999"])
            elif name == "z":
                var.update(source_unit="month", unit="year", dimension="time",
                           conversion={"scale": 1 / 12, "offset": 0}, missing_codes=["-999"])
            elif name == "category":
                var.update(codes={"A": "0", "B": "1"}, missing_codes=["UNK"])
            elif name == "y":
                var["missing_codes"] = ["-999"]
            elif name == "binary":
                var.update(codes={"no": "0", "yes": "1"}, missing_codes=["UNK"])
    contracts.seal_task(task, str(ROOT))
    return task


def main():
    FIX.mkdir(exist_ok=True)
    dev = synthetic(200, 20261024, "SYNTHETIC-DEV-")
    external = synthetic(80, 20261025, "SYNTHETIC-EXT-")
    inference = copy.deepcopy(external)
    for row in inference:
        row["y"] = row["binary"] = ""
    for cohort, rows in [("development", dev), ("external", external), ("inference", inference)]:
        write_csv(FIX / f"prediction-canonical-{cohort}.csv", rows)
        write_csv(FIX / f"prediction-mimic-{cohort}.csv", rows)
        write_csv(FIX / f"prediction-eicu-{cohort}.csv", mapped(rows), list(MAP.values()))
    contracts = load_contracts()
    if hasattr(contracts, "make_prediction_task"):
        for db in ["mimic", "eicu"]:
            for kind in ["continuous", "binary"]:
                method = "prediction.continuous.nonnegative.ridge" if kind=="continuous" else "prediction.binary.ridge"
                csv_path = FIX / f"prediction-{db}-development.csv"
                task = prepare_task(contracts, csv_path, ROOT / "outputs" / f"prediction-example-{db}-{kind}", method,
                                    "MIMIC" if db == "mimic" else "eICU")
                dump(FIX / f"prediction-{db}-{kind}-train.json", task)
    paths = sorted(FIX.glob("prediction-*.csv"))
    dump(FIX / "prediction-fixture-manifest.json", {
        "purpose": "SYNTHETIC_TEST_ONLY", "development_n": 200, "external_n": 80,
        "development_seed": 20261024, "external_seed": 20261025,
        "fields": FIELDS, "source_fingerprints": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "mapping": "MIMIC identity; eICU renamed fields, percent->1, month->year, A/B->0/1, no/yes->0/1, explicit missing codes",
        "scope": "Two synthetic mappings of the same records. No actual database connection, independence or clinical scientific validity claim."})
    print("SYNTHETIC_PREDICTION_FIXTURES_READY")


if __name__ == "__main__":
    main()
