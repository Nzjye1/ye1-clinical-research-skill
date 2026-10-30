"""Strict private transport: unchanged frozen Cox inference, then sole IPCW owner."""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
if __package__:
    from . import cox_prediction_bridge as frozen_bridge
    from . import survival_evaluation
else:
    import cox_prediction_bridge as frozen_bridge
    import survival_evaluation

MAX_INPUT_BYTES = 2 * 1024 * 1024
REQUEST_FIELDS = {"operation", "rows", "spec", "prediction", "feature_semantics", "model_json", "evaluation"}
canonical_bytes = frozen_bridge.canonical_bytes
_strict_json = frozen_bridge._strict_json


def provider_version():
    root = Path(__file__).parent
    files = ("survival_evaluation.py", "survival_evaluation_bridge.py", "survival.py", "cox_prediction_bridge.py", "real_family_admission.py")
    return hashlib.sha256(canonical_bytes({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                           for name in files})).hexdigest()


def preflight():
    result = frozen_bridge.preflight()
    if not result.get("ok"):
        return result
    return {"ok": True, "runtime": result["runtime"], "provider_version": provider_version(),
            "frozen_model_provider_version": result["provider_version"]}


def invoke(request):
    expected = REQUEST_FIELDS | ({"study_context"} if isinstance(request, dict) and "study_context" in request else set())
    if isinstance(request, dict) and "limits" in request:
        expected.add("limits")
    if not (isinstance(request, dict) and set(request) == expected
            and request.get("operation") == "evaluate" and frozen_bridge._finite_tree(request)
            and isinstance(request.get("rows"), list) and 0 < len(request["rows"])
            and all(isinstance(row, dict) for row in request["rows"])
            and isinstance(request.get("spec"), dict) and set(request["spec"]) <= frozen_bridge.SPEC_FIELDS
            and isinstance(request.get("prediction"), dict) and request["prediction"].get("operation") == "infer"):
        return {"ok": False, "reason_code": "PROVIDER_REQUEST_INVALID"}
    default_rows = frozen_bridge.transport.resource_budget.profile("evaluation.survival.cox.ipcw")["default_rows"]
    reason = frozen_bridge.transport.resource_check(request, "evaluation.survival.cox.ipcw", default_rows, "survival_evaluation")
    if reason:
        return {"ok": False, "reason_code": reason}
    try:
        survival_evaluation.validate_evaluation(request["evaluation"], request.get("limits"))
        survival_evaluation.validate_labels(request["rows"], request["spec"], request.get("limits"))
        survival_evaluation.validate_horizons(request["prediction"].get("horizons"), request["spec"])
        inference_request = {key: request[key] for key in ("rows", "spec", "prediction", "feature_semantics", "model_json")}
        inference_request["operation"] = "infer"
        if "study_context" in request:
            inference_request["study_context"] = request["study_context"]
        if "limits" in request:
            inference_request["limits"] = request["limits"]
        # The only production source of risks. Never invoke a fitter, rebuild
        # a baseline, or change the frozen provider's version for v0.6.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            inferred = frozen_bridge.invoke(inference_request)
        if not inferred.get("ok"):
            return inferred
        result = survival_evaluation.evaluate(
            request["rows"], request["spec"], request["prediction"]["horizons"],
            inferred["individual_predictions"], request["evaluation"],
            inferred["model_bundle"]["model_sha256"], inferred["provider_version"], resource_budget=request.get("limits"))
        if not result.get("ok"):
            return result
        result.update(model_bundle=inferred["model_bundle"], individual_predictions=inferred["individual_predictions"],
                      runtime=inferred["runtime"], provider_version=provider_version(),
                      request_sha256=hashlib.sha256(canonical_bytes(request)).hexdigest(),
                      frozen_model_provider_version=inferred["provider_version"])
        if not frozen_bridge._finite_tree(result):
            return {"ok": False, "reason_code": "PROVIDER_NONFINITE_RESULT"}
        return result
    except (survival_evaluation.EvaluationBlocked, survival_evaluation.survival.SurvivalBlocked) as exc:
        return {"ok": False, "reason_code": str(exc)}
    except ImportError:
        return {"ok": False, "reason_code": "PROVIDER_DEPENDENCY_UNAVAILABLE"}
    except Exception:
        return {"ok": False, "reason_code": "PROVIDER_EXECUTION_FAILED"}


def _write_response(response, destination, artifacts, model_json=None):
    """Exclusive outputs; roll back only files opened exclusively by this call.

    An available original model JSON string is copied verbatim after strict
    validation, avoiding a host round trip or a change to frozen model bytes.
    Native canonical JSON is used when this helper receives no original text.
    """
    target = Path(destination)
    paths = [target]
    if artifacts and response.get("ok"):
        paths.extend(target.parent / name for name in (
            "frozen_cox_model.json", "individual_predictions.csv", "censoring_grid.json", "individual_ipcw.json"))
    if len(set(paths)) != len(paths) or any(path.exists() or path.is_symlink() for path in paths):
        raise FileExistsError("private output already exists")
    if len(paths) > 1 and model_json is not None:
        if not isinstance(model_json, str) or canonical_bytes(_strict_json(model_json)) != canonical_bytes(response["model_bundle"]):
            raise ValueError("original model does not match validated bundle")
    created = []

    def write_text(path, value):
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            created.append(path)
            stream.write(value)

    try:
        if len(paths) > 1:
            model_text = model_json if model_json is not None else canonical_bytes(response["model_bundle"]).decode("utf-8") + "\n"
            write_text(paths[1], model_text)
            with paths[2].open("x", encoding="utf-8", newline="") as stream:
                created.append(paths[2])
                writer = csv.DictWriter(stream, fieldnames=["subject_id", "horizon", "survival_probability", "event_risk"], lineterminator="\n")
                writer.writeheader()
                writer.writerows(response["individual_predictions"])
            write_text(paths[3], canonical_bytes(response["private_evaluation"]["censoring_grid"]).decode("utf-8") + "\n")
            write_text(paths[4], canonical_bytes(response["private_evaluation"]["individual_ipcw"]).decode("utf-8") + "\n")
        write_text(target, canonical_bytes(response).decode("utf-8") + "\n")
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        byte_limit = frozen_bridge.transport.cli_byte_limit(args)
    except (ValueError, TypeError, OverflowError):
        print("PROVIDER_ARGUMENTS_INVALID")
        return 2
    artifacts = args[0] != "--preflight"
    model_json = None
    if not artifacts:
        response = preflight()
    else:
        try:
            path = Path(args[0])
            if path.stat().st_size > byte_limit:
                response = {"ok": False, "reason_code": "PROVIDER_INPUT_LIMIT"}
            else:
                request = _strict_json(path.read_text(encoding="utf-8-sig"))
                response = invoke(request)
                if response.get("ok"):
                    model_json = request["model_json"]
        except Exception:
            response = {"ok": False, "reason_code": "PROVIDER_INPUT_UNREADABLE"}
    try:
        _write_response(response, args[1], artifacts, model_json=model_json)
    except Exception:
        print("PROVIDER_OUTPUT_UNAVAILABLE")
        return 3
    print("PROVIDER_RESPONSE_READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
