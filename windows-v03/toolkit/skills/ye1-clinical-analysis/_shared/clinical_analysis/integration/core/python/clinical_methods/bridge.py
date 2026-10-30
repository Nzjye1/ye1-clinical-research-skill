"""Private file bridge to the byte-preserved association provider.

This is a numerical adapter, not a task executor or an authorization boundary.
The R run_analysis_task common-contract branch owns validation and execution.
Only fixed status codes are written to stdout. Inputs and responses stay local.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys

sys.dont_write_bytecode = True

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_ROWS = 200

if __package__:
    from . import resource_budget
else:
    import resource_budget


def cli_byte_limit(args):
    """Bound the file read before decoding JSON; a CLI cap cannot lift ceilings."""
    if len(args) not in (2, 3) or (len(args) == 3 and args[0] == "--preflight"):
        raise ValueError("invalid arguments")
    value = int(args[2]) if len(args) == 3 else MAX_INPUT_BYTES
    if not 1 <= value <= resource_budget.ABSOLUTE_MAX_INPUT_BYTES:
        raise ValueError("invalid budget")
    return value


def _association_columns(spec):
    categories = spec.get("categorical", {})
    categories = categories if isinstance(categories, dict) else {}

    def width(field):
        config = categories.get(field)
        if isinstance(config, dict) and isinstance(config.get("levels"), list):
            return max(1, len(config["levels"]) - 1)
        nonlinear = spec.get("nonlinear")
        if field == spec.get("exposure") and isinstance(nonlinear, dict) and isinstance(nonlinear.get("knots"), list):
            return max(1, len(nonlinear["knots"]) - 1)
        return 1

    predictors = [spec.get("exposure")] + list(spec.get("covariates", []))
    subgroup = spec.get("subgroup")
    group_width = 0
    if isinstance(subgroup, dict):
        group_width = max(1, len(subgroup.get("levels", [])) - 1)
        if subgroup.get("field") in predictors:
            predictors.remove(subgroup["field"])
    return 1 + sum(width(field) for field in predictors) + group_width + width(spec.get("exposure")) * group_width


def resource_check(request, method_id, legacy_rows=MAX_ROWS, kind="association"):
    """Conservative declared allocation checks, before importing numerical owners.

    Work counts are deterministic admission estimates, not runtime guarantees.
    No complete-case filtering or numerical/statistical validation happens here.
    """
    try:
        supplied = request.get("limits")
        if "limits" not in request:
            limits = {"max_rows": legacy_rows, "max_input_bytes": MAX_INPUT_BYTES,
                      "max_design_columns": 128, "max_work_units": 250_000_000}
        else:
            if (method_id.startswith("association.") and request.get("schema_version") == "clinical-association-request@1.0"
                    and isinstance(supplied, dict) and set(supplied) == {"max_rows", "max_input_bytes"}):
                supplied = {**supplied, "max_design_columns": 128, "max_work_units": 250_000_000}
            limits = resource_budget.validate_limits(supplied, method_id)
        resource_budget.check_rows(len(request["rows"]), limits)
        if len(canonical_bytes(request)) > limits["max_input_bytes"]:
            return "PROVIDER_INPUT_LIMIT"
        specs = []
        if kind == "association_plan":
            specs = [item["spec"] for item in request["plan"].get("models", [])]
        elif kind == "association":
            spec = request["spec"]
            specs = [spec] + [{**spec, **{k: item[k] for k in ("covariates", "nonlinear", "covariance") if k in item}}
                             for item in spec.get("sensitivity", [])]
        n = len(request["rows"])
        if specs:
            widths = [_association_columns(spec) for spec in specs]
            columns, work = max(widths), sum(n * p * p for p in widths)
        elif kind in {"survival", "cox_prediction", "survival_evaluation"}:
            spec = request["spec"]
            columns = max(1, sum(max(1, len(cov.get("levels", [])) - 1) if cov.get("type") == "category" else 1
                                 for cov in spec.get("covariates", [])))
            grid = len(request.get("prediction", {}).get("horizons", spec.get("evaluation_times", [])))
            if kind == "cox_prediction" and request.get("operation") == "infer":
                work = n * columns + n * max(1, grid)
            elif kind == "survival_evaluation":
                work = n * n * max(1, grid) + n * columns
            else:
                # Cox's exact risk-set contrast LP materializes up to n^2*p
                # entries; KM's event scans also require a quadratic bound.
                work = n * n * columns + n * columns * columns + n * max(1, grid)
                if "ph_test" in spec:
                    work += n * n * columns * columns
        else:
            columns, work = 1, n
        if columns > limits["max_design_columns"]:
            return "RESOURCE_DESIGN_BUDGET_EXCEEDED"
        if work > limits["max_work_units"]:
            return "RESOURCE_WORK_BUDGET_EXCEEDED"
        return None
    except resource_budget.BudgetError as exc:
        return exc.code
    except (KeyError, TypeError, ValueError, OverflowError):
        return "PROVIDER_REQUEST_INVALID"


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def request_hash(request: dict) -> str:
    return hashlib.sha256(canonical_bytes(request)).hexdigest()


def _request_valid(request: object) -> bool:
    if not isinstance(request, dict):
        return False
    if set(request) not in ({"rows", "spec"}, {"rows", "spec", "limits"}, {"rows", "spec", "schema_version", "limits"}):
        return False
    if "schema_version" in request and request["schema_version"] != "clinical-association-request@1.0":
        return False
    return (isinstance(request["rows"], list) and 0 < len(request["rows"])
            and all(isinstance(row, dict) for row in request["rows"])
            and isinstance(request["spec"], dict))


def _finite_tree(value: object) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and _finite_tree(v) for k, v in value.items())
    if isinstance(value, (tuple, list)):
        return all(_finite_tree(v) for v in value)
    return value is None or isinstance(value, (str, int, bool))


def preflight() -> dict:
    """Read fixed dependency versions without input rows or numerical analysis."""
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import numpy
            import scipy
            import statsmodels
            if __package__:
                from . import association
            else:
                import association
        return {
            "ok": True,
            "runtime": {"python": platform.python_version(), "numpy": numpy.__version__,
                        "scipy": scipy.__version__, "statsmodels": statsmodels.__version__},
            "provider_version": hashlib.sha256(Path(association.__file__).read_bytes()).hexdigest(),
        }
    except ImportError:
        return {"ok": False, "reason_code": "PROVIDER_DEPENDENCY_UNAVAILABLE"}
    except Exception:
        return {"ok": False, "reason_code": "PROVIDER_EXECUTION_FAILED"}


def invoke(request: object) -> dict:
    """Call exactly one fixed provider; never retry or substitute estimators."""
    if not _request_valid(request) or not _finite_tree(request):
        return {"ok": False, "reason_code": "PROVIDER_REQUEST_INVALID"}
    reason = resource_check(request, "association." + str(request["spec"].get("model", "linear")))
    if reason:
        return {"ok": False, "reason_code": reason}
    try:
        # Suppress incidental dependency output; never forward row-bearing errors.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import numpy
            import scipy
            import statsmodels
            if __package__:
                from . import association
            else:
                import association
            record = association.analyze(request["rows"], request["spec"])
        if not _finite_tree(record):
            return {"ok": False, "reason_code": "PROVIDER_NONFINITE_RESULT"}
        return {
            "ok": True,
            "record": record,
            "runtime": {
                "python": platform.python_version(),
                "numpy": numpy.__version__,
                "scipy": scipy.__version__,
                "statsmodels": statsmodels.__version__,
            },
            "provider_version": hashlib.sha256(Path(association.__file__).read_bytes()).hexdigest(),
            "request_sha256": request_hash(request),
        }
    except ImportError:
        return {"ok": False, "reason_code": "PROVIDER_DEPENDENCY_UNAVAILABLE"}
    except Exception:
        return {"ok": False, "reason_code": "PROVIDER_EXECUTION_FAILED"}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        byte_limit = cli_byte_limit(args)
    except (ValueError, TypeError, OverflowError):
        print("PROVIDER_ARGUMENTS_INVALID")
        return 2
    response_path = Path(args[1])
    if args[0] == "--preflight":
        response = preflight()
    else:
        request_path = Path(args[0])
        try:
            if request_path.stat().st_size > byte_limit:
                response = {"ok": False, "reason_code": "PROVIDER_INPUT_LIMIT"}
            else:
                def reject_constant(_: str) -> None:
                    raise ValueError("invalid numeric literal")
                request = json.loads(request_path.read_text(encoding="utf-8-sig"),
                                     parse_constant=reject_constant)
                response = invoke(request)
        except Exception:
            response = {"ok": False, "reason_code": "PROVIDER_INPUT_UNREADABLE"}
    try:
        # Exclusive creation: a bridge rerun can never overwrite prior evidence.
        with response_path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(response, handle, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))
            handle.write("\n")
    except Exception:
        print("PROVIDER_OUTPUT_UNAVAILABLE")
        return 3
    print("PROVIDER_RESPONSE_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
