"""Local clinical extension. Agent manages plans and paths; patient data and models stay local.

Exact --help and selfcheck do not read research files. Real analysis uses the existing
controlled privacy adapter and version-bound actual user plan evidence. Engineering
synthetic-demo builds its own fixture and cannot accept an arbitrary data file.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import importlib
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import sys

MODULES = ("association", "prediction", "trajectory", "clustering", "survival")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def selfcheck():
    """Import checks only. No project selection or research inputs are accessed."""
    packages = {"numpy": "numpy", "scipy": "scipy", "pandas": "pandas",
                "statsmodels": "statsmodels", "scikit-learn": "sklearn",
                "python-docx": "docx", "Pillow": "PIL", "openpyxl": "openpyxl",
                "matplotlib": "matplotlib"}
    checks = {}
    for name, module in packages.items():
        try:
            # find_spec does not build Matplotlib's cache or open patient files.
            found = importlib.util.find_spec(module) is not None
            checks[name] = {"available": found,
                            "version": importlib.metadata.version(name) if found else None}
        except (ImportError, ValueError, importlib.metadata.PackageNotFoundError):
            checks[name] = {"available": False, "version": None}
    return {"status": "READY" if sys.version_info >= (3, 11) and all(
        v["available"] for v in checks.values()) else "PARTIAL_READY",
        "python": ".".join(map(str, sys.version_info[:3])), "dependencies": checks,
        "text_available": True, "research_data_read": False,
        "scope": "Package presence/version; method, font and visual checks are separate"}


def load_table(path, sheet=None, *, payload=None):
    p = Path(path)
    payload = p.read_bytes() if payload is None else payload
    if p.suffix.lower() == ".csv":
        with io.StringIO(payload.decode('utf-8-sig'), newline='') as stream:
            records = list(csv.reader(stream))
    elif p.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(payload), read_only=True, data_only=False)
        try:
            if sheet is None and len(book.sheetnames) != 1:
                raise ValueError("EXACT_SHEET_REQUIRED")
            if sheet is not None and sheet not in book.sheetnames:
                raise ValueError("EXACT_SHEET_REQUIRED")
            records = list(book[sheet or book.sheetnames[0]].values)
        finally:
            book.close()
    else:
        raise ValueError("CSV_OR_XLSX_REQUIRED")
    if len(records) < 2:
        raise ValueError("EMPTY_DATA")
    header = records[0]
    if (not all(isinstance(v, str) and v.strip() for v in header)
            or len(header) != len(set(header))):
        raise ValueError("UNIQUE_NONEMPTY_HEADER_REQUIRED")
    if any(len(r) != len(header) for r in records[1:]):
        raise ValueError("RAGGED_ROWS")
    if any(isinstance(v, str) and v.startswith("=") for r in records[1:] for v in r):
        raise ValueError("FORMULA_VALUES_REQUIRE_VERIFICATION")
    return [dict(zip(header, r)) for r in records[1:]]


def analyze_rows(module, rows, spec, model=None):
    if module not in MODULES:
        raise ValueError("UNSUPPORTED_MODULE")
    engine = importlib.import_module("clinical." + module)
    return (engine.validate_external(rows, model, spec) if model is not None
            else engine.analyze(rows, spec))


def new_output(path):
    target = Path(path)
    if target.exists() or target.is_symlink():
        raise ValueError("PRESERVE_PRIOR_OUTPUT")
    target.mkdir(parents=True)
    return target


def execute(module, rows, spec, target, *, test_only=False, source_hash=None,
            model=None, figures=False):
    """Local API for controlled adapters and engineering tests; no external dispatch."""
    target = Path(target)
    if not target.is_dir() or target.is_symlink() or any(target.iterdir()):
        raise ValueError('NEW_EMPTY_OUTPUT_REQUIRED')
    # Exclusive claim prevents two cooperative adapters sharing an empty target.
    with (target/'.clinical-owner').open('x', encoding='utf-8') as stream:
        stream.write('Local clinical output; preserve this version.\n')
    result = analyze_rows(module, rows, spec, model)
    if not isinstance(result, dict):
        raise ValueError("RESULT_OBJECT_REQUIRED")
    result = dict(result)
    # Fitted transforms/coefs and development-ID digests are local model material.
    bundle = result.pop("model_bundle", None)
    if bundle is not None:
        write_json(target / "model-local-only.json", bundle)
    record = {"schema": "ye1-clinical-result/1", "version": "0.5.0-rc1",
              "module": module, "test_only": test_only,
              "use": "SYNTHETIC_TEST_ONLY" if test_only else "SCIENTIFIC_REVIEW_PENDING",
              "result": result}
    write_json(target / "analysis.json", record)
    write_json(target / "spec.json", spec)
    if figures:
        try:
            from clinical.plots import render
            figure_result = render(record, target / "figures", spec.get('language','zh'))
        except (ImportError, OSError, RuntimeError, ValueError):
            figure_result = {"status":"BLOCKED_ENVIRONMENT", "files":[],
                             "next":"Retain computed tables; resume plotting in an available project environment"}
        write_json(target / "figures.json", figure_result)
    write_json(target / "manifest.json", {
        "schema": "ye1-clinical-manifest/1", "module": module,
        "source_sha256": source_hash, "spec_sha256": digest(spec),
        "test_only": test_only, "sent": False,
        "files": {p.relative_to(target).as_posix(): file_hash(p) for p in target.rglob('*')
                  if p.is_file() and '.plot-cache' not in p.parts},
        "review": "Methods, small cells, privacy, figures and scientific claims remain to review"})
    return record


def check_confirmation(job, data_path, model_path=None, *, source_bytes=None, model_bytes=None, sheet=None):
    from confirmation_evidence import validate
    if job.get("schema") != "ye1-clinical-job/1" or job.get("module") not in MODULES:
        raise ValueError("JOB_SCHEMA")
    data_hash = hashlib.sha256(source_bytes).hexdigest() if source_bytes is not None else file_hash(data_path)
    if job.get("source_sha256") != data_hash:
        raise ValueError("DATA_VERSION_CHANGED")
    if 'sheet' not in job or job['sheet'] != sheet:
        raise ValueError('EXACT_TABLE_SELECTION_REQUIRED')
    if Path(data_path).suffix.lower() == '.xlsx' and not isinstance(sheet,str):
        raise ValueError('EXACT_SHEET_REQUIRED')
    binding = {k: job[k] for k in ("module", "analysis", "source_sha256", "sheet")}
    if model_path is not None:
        model_hash = hashlib.sha256(model_bytes).hexdigest() if model_bytes is not None else file_hash(model_path)
        if job.get("model_sha256") != model_hash:
            raise ValueError("MODEL_VERSION_CHANGED")
        binding["model_sha256"] = job["model_sha256"]
    confirmation = job.get("confirmation", {})
    if confirmation.get('source_kind') != 'direct_user' or validate(confirmation)['kind'] != 'direct_user':
        raise ValueError('ACTUAL_USER_PLAN_CONFIRMATION_REQUIRED')
    if confirmation.get("plan_sha256") != digest(binding):
        raise ValueError("EXACT_PLAN_CONFIRMATION_REQUIRED")
    return data_hash


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("selfcheck", help="Independent presence/version check; no data access")
    demo = sub.add_parser("synthetic-demo", help="Built-in synthetic fixtures only; no customer data")
    demo.add_argument("module", choices=MODULES)
    demo.add_argument("--out", required=True)
    demo.add_argument("--figures", action="store_true")
    run = sub.add_parser("analyze", help="Controlled local adapter only; no data printed")
    run.add_argument("--data", required=True)
    run.add_argument("--job", required=True)
    run.add_argument("--out", required=True)
    run.add_argument("--sheet")
    run.add_argument("--model", help="Frozen local prediction model for external validation")
    run.add_argument("--figures", action="store_true")
    # Only exact help is exempt: mixed help/data arguments cannot enter processing.
    if args in (["--help"], ["-h"]):
        parser.print_help()
        return 0
    if args and args[0] == "analyze":
        from privacy_boundary import cli_local_entry
        cli_local_entry()
    options = parser.parse_args(args)
    target = None
    try:
        if options.command == "selfcheck":
            result = selfcheck()
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "READY" else 3
        if options.command == "synthetic-demo":
            from clinical.synthetic import fixture
            rows, spec = fixture(options.module)
            target = new_output(options.out)
            result = execute(options.module, rows, spec, target, test_only=True, figures=options.figures)
        else:
            job = json.loads(Path(options.job).read_text(encoding="utf-8"))
            # Bind and consume the same captured bytes; concurrent source replacement
            # cannot silently change the analyzed data or frozen external model.
            data_payload = Path(options.data).read_bytes()
            model_payload = Path(options.model).read_bytes() if options.model else None
            selected_sheet = options.sheet if options.sheet is not None else job.get('sheet')
            h = check_confirmation(job, options.data, options.model,
                                   source_bytes=data_payload, model_bytes=model_payload,
                                   sheet=selected_sheet)
            if options.model is not None and job["module"] != "prediction":
                raise ValueError("EXTERNAL_VALIDATION_REQUIRES_PREDICTION")
            model = json.loads(model_payload.decode('utf-8')) if model_payload is not None else None
            rows = load_table(options.data, selected_sheet, payload=data_payload)
            target = new_output(options.out)
            result = execute(job["module"], rows, job["analysis"], target,
                             source_hash=h, model=model, figures=options.figures)
        status = result["result"].get("status", "COMPUTED_REVIEW_PENDING")
        print(json.dumps({"status": status, "test_only": result["test_only"],
                          "output_retained_locally": True, "sent": False}))
        return 2 if "BLOCKED" in status or "UNSUPPORTED" in status else 0
    except (ImportError, OSError) as exc:
        status, code, exit_code = "BLOCKED_ENVIRONMENT", "DEPENDENCY_OR_LOCAL_IO_UNAVAILABLE", 3
    except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
        status, code, exit_code = "BLOCKED_VALIDATION", "INPUT_OR_METHOD_PRECONDITION_FAILED", 2
    if target is not None:
        write_json(target / "failure.json", {"status": status, "code": code,
                   "test_only": options.command == "synthetic-demo", "sent": False})
    print(json.dumps({"status": status, "code": code, "sent": False}))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
