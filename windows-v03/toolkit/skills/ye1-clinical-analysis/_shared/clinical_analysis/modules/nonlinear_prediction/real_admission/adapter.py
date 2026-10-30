"""Origin-aware transport over unchanged nonlinear and TreeSHAP numerical owners.

Only a root-created admitted context can enter this API. It reads no source
file, creates no permission, changes no estimator, and never relabels real rows
as synthetic. Old synthetic transports and frozen bundles remain unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
OWNER = ROOT.parent
MODEL_SCHEMA = "clinical-frozen-nonlinear-admitted@1.0"
PREDICTION_METHODS = {"prediction.binary.random_forest", "prediction.binary.hist_gradient_boosting"}
SHAP_METHODS = {"explanation.binary.random_forest.tree_shap": "prediction.binary.random_forest",
                "explanation.binary.hist_gradient_boosting.tree_shap": "prediction.binary.hist_gradient_boosting"}


class AdmissionBlocked(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise AdmissionBlocked(code)


def _authorize(request, context):
    # This must precede importing numerical owners or touching payload rows.
    callback = getattr(context, "require_request", None)
    need(callable(callback), "ADMITTED_ROOT_CONTEXT_REQUIRED")
    need(isinstance(request, dict), "MODULE_REQUEST_OBJECT_REQUIRED")
    callback(request.get("method_id"), request.get("operation"), request.get("payload"))
    origin = {k: getattr(context, k, None) for k in
              ("data_origin", "task_purpose", "scientific_review", "test_only")}
    need(origin["data_origin"] in {"real", "synthetic"}, "ADMITTED_DATA_ORIGIN_REQUIRED")
    need(origin["task_purpose"] in {"engineering_test", "research_analysis"}, "ADMITTED_TASK_PURPOSE_REQUIRED")
    need(origin["scientific_review"] == "pending" and type(origin["test_only"]) is bool,
         "ADMITTED_SCIENTIFIC_STATE_REQUIRED")
    need(origin["data_origin"] != "synthetic" or
         (origin["task_purpose"] == "engineering_test" and origin["test_only"] is True),
         "SYNTHETIC_ENGINEERING_SCOPE_REQUIRED")
    need(origin["task_purpose"] != "engineering_test" or origin["test_only"] is True,
         "ENGINEERING_TEST_CLASSIFICATION_REQUIRED")
    need(isinstance(getattr(context, "project_root", None), (str, Path)) and str(context.project_root),
         "ADMITTED_PROJECT_REQUIRED")
    return origin


def _owners():
    # Normal imports, with collision checks. No sys.modules aliasing, patched
    # functions, changed globals or temporary synthetic input labels are used.
    if str(OWNER) not in sys.path:
        sys.path.insert(0, str(OWNER))
    p = importlib.import_module("provider")
    bridge = importlib.import_module("adapter")
    facade = importlib.import_module("interface")
    for module, filename in ((p, "provider.py"), (bridge, "adapter.py"), (facade, "interface.py")):
        need(Path(module.__file__).resolve() == OWNER / filename, "NONLINEAR_OWNER_IMPORT_COLLISION")
    return p, bridge, facade


def transport_version():
    files = [ROOT / "adapter.py", ROOT / "frozen-model.schema.json", ROOT / "failure-diagnostics.schema.json"]
    return hashlib.sha256(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                                    sort_keys=True).encode()).hexdigest()


def _limitations(items, origin):
    # Numerical results stay untouched; remove only the old transport's static
    # synthetic classification sentence before adding the admitted classification.
    return [str(origin["data_origin"]).upper() + "; task_purpose=" + origin["task_purpose"] +
            "; scientific_review=pending; local_only."] + [
                v for v in items if not v.startswith("SYNTHETIC_TEST_ONLY;")]


def _validate(request, facade, shap=False):
    facade.validate_json(request, facade.CONTRACTS_ROOT / "module-request.schema.json")
    payload = request["payload"]
    schema = OWNER / ("tree_shap/schemas/payload.schema.json" if shap else "schemas/payload.schema.json")
    facade.validate_json(payload, schema)
    semantics = facade.semantics_and_guard(
        {**payload, "explain_with_outcomes": False} if shap else payload,
        "explain" if shap else request["operation"])
    return payload, semantics


def _build_bundle(model, method, spec, semantics, rows, fit_rows, holdout_rows, origin, p, bridge):
    grids = {}
    for feature in spec["features"]:
        name = feature["name"]
        if name not in spec["explanation"]["pdp_features"]:
            continue
        grids[name] = ([str(v) for v in feature["levels"]] if feature["type"] == "category" else
                       p.np.unique(p.np.quantile([r[name] for r in fit_rows if r[name] is not None],
                                              [.1, .3, .5, .7, .9])).tolist())
    group = spec["split"].get("group") if spec["split"]["method"] == "group" else None
    inner = bridge.seal({"schema_version": p.VERSION, "classification": "LOCAL_ONLY_MODEL_BUNDLE",
        "development_cohort_id": spec["cohort_id"], "definitions": bridge.definitions(spec),
        "development_id_digests": sorted(p.common._id_digest(r[spec["id"]]) for r in rows),
        "holdout_id_digests": sorted(p.common._id_digest(r[spec["id"]]) for r in holdout_rows),
        "group_guard": {"field": group, "development_group_digests": sorted({p.common._id_digest(r[group]) for r in rows})} if group else None,
        "model": model, "pdp_grids": grids,
        "fit_scope": "base-fit subset only; calibration disjoint; final holdout excluded from all learning"})
    return bridge.seal({"schema_version": MODEL_SCHEMA, "method_id": method,
        "provider_version": p.provider_version(), "runtime": p.runtime(), "target_policy": None,
        "canonical_semantics": copy.deepcopy(semantics), "origin_context": copy.deepcopy(origin),
        "transport_version": transport_version(), "test_only": origin["test_only"],
        "scientific_review": "pending", "export_status": "local_only", "bundle": inner})


def _check_bundle(bundle, method, spec, semantics, scope, origin, p, bridge, facade):
    facade.validate_json(bundle, ROOT / "frozen-model.schema.json")
    raw = copy.deepcopy(bundle); digest = raw.pop("sha256")
    need(digest == p.common._digest(raw), "MODEL_BUNDLE_HASH_MISMATCH")
    need(bundle["schema_version"] == MODEL_SCHEMA, "ADMITTED_FROZEN_MODEL_REQUIRED")
    need(bundle["method_id"] == method, "MODEL_METHOD_MISMATCH")
    need(bundle["provider_version"] == p.provider_version(), "MODEL_PROVIDER_VERSION_MISMATCH")
    need(bundle["transport_version"] == transport_version(), "MODEL_TRANSPORT_VERSION_MISMATCH")
    need(bundle["runtime"] == p.runtime(), "MODEL_RUNTIME_VERSION_MISMATCH")
    need(bundle["origin_context"] == origin and bundle["test_only"] == origin["test_only"], "FROZEN_ORIGIN_CONTEXT_MISMATCH")
    need(bundle["scientific_review"] == "pending" and bundle["export_status"] == "local_only",
         "MODEL_CLASSIFICATION_MISMATCH")
    need(bundle["canonical_semantics"] == semantics, "FROZEN_CANONICAL_SEMANTICS_MISMATCH")
    inner = copy.deepcopy(bundle["bundle"]); inner_hash = inner.pop("sha256", None)
    need(inner_hash == p.common._digest(inner) and inner.get("schema_version") == p.VERSION,
         "MODEL_INNER_BUNDLE_MISMATCH")
    need(set(inner) == {"schema_version", "classification", "development_cohort_id", "definitions",
         "development_id_digests", "holdout_id_digests", "group_guard", "model", "pdp_grids", "fit_scope"},
         "FROZEN_INNER_UNKNOWN_FIELD")
    need(bridge.definitions(spec) == inner["definitions"], "EXTERNAL_DEFINITIONS_DIFFER_FROM_FROZEN_MODEL")
    need((scope == "external" and spec["cohort_id"] != inner["development_cohort_id"]) or
         (scope == "development_holdout" and spec["cohort_id"] == inner["development_cohort_id"]),
         "FROZEN_APPLICATION_COHORT_MISMATCH")
    need(inner["model"]["kind"] == p.METHODS[method], "MODEL_ALGORITHM_MISMATCH")
    need(inner["model"]["calibration"]["method"] == spec["calibration"]["method"], "FROZEN_CALIBRATION_POLICY_MISMATCH")
    p.check_model(inner["model"])
    return bundle["bundle"]


def _eligible_rows(rows, spec, training, p, failure_state):
    """Reuse the common pure accounting owner after admission + payload guards.

    The only reconstruction is the exact all-missing special case used by the
    closed old interface P1 fix. Other invalid rows never produce invented counts.
    """
    failure_state["stage"] = "eligibility_or_compute"
    try:
        data, counts = p.common._rows(rows, spec, training=training)
    except p.Blocked as error:
        if str(error) == "NO_ANALYZABLE_OUTCOMES" and all(p.common._missing(r[spec["outcome"]]) for r in rows):
            n = len(rows)
            counts = {"total_n": n, "total_events": 0, "total_nonevents": 0, "missing_outcome_n": n,
                      "missing_feature_excluded_n": 0, "analyzable_n": 0, "analyzable_events": 0,
                      "analyzable_nonevents": 0, "source_rows": n, "prediction_n": None}
            if not training:
                counts.update(evaluation_n=0, evaluation_events=0, evaluation_nonevents=0)
            failure_state.update(counts=counts, counts_status="computed")
        raise
    counts.update(source_rows=len(rows), prediction_n=None)
    if not training:
        counts.update(evaluation_n=counts["analyzable_n"], evaluation_events=counts["analyzable_events"],
                      evaluation_nonevents=counts["analyzable_nonevents"])
    failure_state.update(counts=counts, counts_status="computed")
    return data, counts


def _inference(payload, method, op, bundle, semantics, origin, p, bridge, facade, failure_state=None):
    rows, spec, scope = payload["rows"], payload["spec"], payload["application_scope"]
    inner = _check_bundle(bundle, method, spec, semantics, scope, origin, p, bridge, facade)
    ids = {p.common._id_digest(r.get(spec["id"])) for r in rows}
    if scope == "development_holdout":
        need(ids <= set(inner["holdout_id_digests"]), "FROZEN_HOLDOUT_MEMBERSHIP_REQUIRED")
    else:
        need(not ids & set(inner["development_id_digests"]), "EXTERNAL_SUBJECT_OVERLAP")
    guard = inner["group_guard"]
    if guard and scope == "external":
        field = guard["field"]
        need(all(field in r and not p.common._missing(r[field]) for r in rows), "EXTERNAL_GROUP_COLUMN_REQUIRED")
        need(not {p.common._id_digest(r[field]) for r in rows} & set(guard["development_group_digests"]), "EXTERNAL_GROUP_OVERLAP")
    if op == "evaluate":
        data, counts = (_eligible_rows(rows, spec, False, p, failure_state) if failure_state is not None else
                        p.common._rows(rows, spec, training=False))
        lookup = {p.common._id_digest(r[spec["id"]]): i for i, r in enumerate(rows)}
        positions = [lookup[p.common._id_digest(r[spec["id"]])] for r in data]
    else:
        data, positions = p.common_bridge.binary_inference_rows(rows, spec)
        counts = {"total_n": len(rows), "analyzable_n": len(data), "missing_feature_excluded_n": len(rows)-len(data)}
    probabilities = p.predict(data, inner["model"])
    individual = p.common_bridge.private_predictions(positions, probabilities, op)
    record = {"status": "ESTIMATED" if op == "evaluate" else "INFERENCE_COMPLETE", "counts": counts,
        "validation": "frozen " + scope + " application", "metrics": p.common._metrics(data, probabilities, spec) if op == "evaluate" else None,
        "model_refitted": False, "preprocessing_refitted": False, "calibration_refitted": False,
        "internal_cv": None, "limitations": _limitations(p.LIMITATIONS, origin)}
    if failure_state is not None and record["metrics"] is not None:
        failure_state["metrics_status"] = "computed_not_accepted"
    return record, individual, data, positions


def _counts(record, individual, rows, op):
    counts = record["counts"]
    counts.update(source_rows=len(rows), prediction_n=len(individual))
    for key in ("training_n", "training_events", "training_nonevents", "holdout_n", "holdout_events", "holdout_nonevents",
                "model_fit_n", "calibration_n", "missing_outcome_n", "missing_feature_excluded_n"):
        counts.setdefault(key, None)
    measured = record.get("metrics") is not None
    counts["evaluation_n"] = (counts["holdout_n"] if op == "train" else counts["analyzable_n"]) if measured else None
    counts["evaluation_events"] = (counts.get("holdout_events") if op == "train" else counts.get("analyzable_events")) if measured else None
    counts["evaluation_nonevents"] = (counts.get("holdout_nonevents") if op == "train" else counts.get("analyzable_nonevents")) if measured else None


def _prediction(request, origin, p, bridge, facade, failure_state):
    payload, semantics = _validate(request, facade)
    op, method = request["operation"], request["method_id"]
    need(method in PREDICTION_METHODS and op in {"train", "evaluate", "infer", "explain"}, "MODULE_METHOD_OR_OPERATION_UNSUPPORTED")
    spec, rows = payload["spec"], payload["rows"]
    p.validate_spec(spec, method)
    bundle = bridge.strict_load(payload["frozen_model_json"].encode()) if payload["frozen_model_json"] is not None else None
    need(request["bindings"]["model_sha256"] == (bundle.get("sha256") if bundle else None), "MODULE_MODEL_BINDING_MISMATCH")
    need((op == "train" and bundle is None and payload["application_scope"] == "development") or
         (op != "train" and bundle is not None and payload["application_scope"] in {"external", "development_holdout"}),
         "MODULE_FROZEN_MODEL_OR_SCOPE_REQUIRED")
    need(op == "explain" or payload["explain_with_outcomes"] is False, "EXPLANATION_MUST_USE_EXPLAIN_OPERATION")
    individual = []
    if op == "train":
        data, counts = _eligible_rows(rows, spec, True, p, failure_state)
        record, model, partitions = p.train(data, counts, spec, method)
        if record["metrics"] is not None:
            failure_state["metrics_status"] = "computed_not_accepted"
        need(model is not None and record["status"] != "BLOCKED_ESTIMATION", record.get("reason_code", "ESTIMATION_BLOCKED"))
        fit_rows = [data[i] for i in partitions["model_fit"]]
        bundle = _build_bundle(model, method, spec, semantics, rows, fit_rows,
                               [data[i] for i in partitions["holdout"]], origin, p, bridge)
        lookup = {p.common._id_digest(r[spec["id"]]): i for i, r in enumerate(rows)}
        for partition, indices in partitions.items():
            selected = [data[i] for i in indices]
            if selected:
                positions = [lookup[p.common._id_digest(r[spec["id"]])] for r in selected]
                individual += p.common_bridge.private_predictions(positions, p.predict(selected, model), partition)
        record["limitations"] = _limitations(record["limitations"], origin)
    else:
        record, individual, data, positions = _inference(payload, method, "infer" if op == "explain" else op,
                                                        bundle, semantics, origin, p, bridge, facade, failure_state)
        if op == "explain":
            if payload["explain_with_outcomes"]:
                data, _ = _eligible_rows(rows, spec, False, p, failure_state)
            record["explanation"] = p.explain(data, bundle["bundle"]["model"], spec,
                label_available=payload["explain_with_outcomes"], grids=bundle["bundle"]["pdp_grids"])
            record["explanation"]["evaluation_set"] = "frozen_" + payload["application_scope"] + "_explanation"
            record["status"] = "EXPLAINED"
    _counts(record, individual, rows, op)
    if op == "explain" and payload["explain_with_outcomes"]:
        record["counts"].update(evaluation_n=len(data), evaluation_events=sum(r["_ye1_outcome"] for r in data),
                                 evaluation_nonevents=sum(1-r["_ye1_outcome"] for r in data))
    public = {k: record.get(k) for k in ("status", "counts", "validation", "metrics", "internal_cv", "explanation", "limitations")}
    diagnostics = {"stage": "complete", "provider_version": p.provider_version(), "runtime": p.runtime(), "counts": record["counts"],
        "fit_metadata": record.get("diagnostics"), "bindings_checked": "root_admitted_request; frozen_model_here",
        "model_refitted": op == "train", "preprocessing_refitted": op == "train",
        "calibration_refitted": op == "train" and spec["calibration"]["method"] == "sigmoid"}
    private = {"frozen_model_json": (json.dumps(bundle, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                                    if op == "train" else payload["frozen_model_json"]), "individual": individual}
    for key, name in ((diagnostics, "diagnostics"), (public, "public-record"), (private, "private-record")):
        facade.validate_json(key, OWNER / "schemas" / (name + ".schema.json"))
    return diagnostics, public, private


def _tree_shap(request, context, origin, p, bridge, facade):
    payload, semantics = _validate(request, facade, shap=True)
    need(request["operation"] == "explain", "MODULE_OPERATION_UNSUPPORTED")
    bundle = bridge.strict_load(payload["frozen_model_json"].encode())
    need(request["bindings"]["model_sha256"] == bundle.get("sha256"), "MODULE_MODEL_BINDING_MISMATCH")
    background = bridge.strict_load(payload["background_artifact_json"].encode())
    need(background.get("sha256") == payload["background_sha256"], "BACKGROUND_BINDING_MISMATCH")
    callback = getattr(context, "require_training_background", None)
    need(callable(callback), "TRUSTED_TRAINING_BACKGROUND_CONTEXT_REQUIRED")
    callback(background)
    method = SHAP_METHODS[request["method_id"]]
    p.validate_spec(payload["spec"], method)
    explanation_owner = importlib.import_module("tree_shap.explain")
    budget_callback = getattr(context, "resource_limits", None)
    limits = explanation_owner.resource_limits(budget_callback() if callable(budget_callback) else None,
                                              request["method_id"])
    explanation_owner.resource_guard(payload["rows"], bundle["bundle"]["model"], len(background["rows"]), limits)
    _, individual, data, positions = _inference(payload, method, "infer", bundle, semantics, origin, p, bridge, facade)
    background_owner = importlib.import_module("tree_shap.background")
    explanation_owner = importlib.import_module("tree_shap.explain")
    runtime_owner = importlib.import_module("tree_shap.runtime")
    matrix = background_owner.check_background(background, bundle, payload["spec"], resource_budget=limits)
    public, private, numerics = explanation_owner.explain(data, positions, bundle["bundle"]["model"], matrix, resource_budget=limits)
    need([r["row_index"] for r in private["individual"]] == [r["row_index"] for r in individual], "SHAP_INFERENCE_POSITION_MISMATCH")
    public["limitations"] = _limitations(public["limitations"], origin)
    private.update(model_sha256=bundle["sha256"], background_sha256=background["sha256"])
    diagnostics = {"stage": "complete", "prediction_provider_version": p.provider_version(),
        "explanation_provider_version": runtime_owner.version(), "runtime": runtime_owner.runtime(),
        "model_refitted": False, "preprocessing_refitted": False, "calibration_refitted": False,
        "counts": {"source_rows": len(payload["rows"]), "explained_n": len(data), "background_n": len(matrix)},
        "numerical_checks": numerics, "bindings_checked": "root_admitted_request_and_trusted_training_origin; frozen_model_background_integrity_here"}
    for value, name in ((diagnostics, "diagnostics"), (public, "public-record"), (private, "private-record")):
        runtime_owner.validate(value, name)
    return diagnostics, public, private


def analyze(request, context):
    """Receive the unchanged module-request@1.0 inside the root's V1.1 route."""
    p = None
    failure_state = {"stage": "admission_or_contract", "counts": None,
                     "counts_status": "not_evaluated", "metrics_status": "not_evaluated"}
    try:
        origin = _authorize(request, context)
        p, bridge, facade = _owners()
        locked = bridge.strict_load((p.CORE_ROOT / "runtime-lock.json").read_bytes())["prediction_python_versions"]
        need(p.runtime() == locked, "NONLINEAR_DEPENDENCY_VERSION_DRIFT")
        if request.get("method_id") in SHAP_METHODS:
            diagnostics, public, private = _tree_shap(request, context, origin, p, bridge, facade)
        else:
            diagnostics, public, private = _prediction(request, origin, p, bridge, facade, failure_state)
        response = {"api_version": "clinical-module-response@1.0", "ok": True, "reason_code": None,
                    "diagnostics": diagnostics, "public_record": public, "private_record": private}
        facade.validate_json(response, facade.CONTRACTS_ROOT / "module-response.schema.json")
        return response
    except Exception as error:
        code = getattr(error, "code", None)
        if code is None:
            code = (str(error) if isinstance(error, AdmissionBlocked) or
                    (p is not None and isinstance(error, p.Blocked)) else "NONLINEAR_ADMISSION_OR_INPUT_BLOCKED")
        code = str(code)
        if not code or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789" for c in code):
            code = "NONLINEAR_ADMISSION_OR_INPUT_BLOCKED"
        return {"api_version": "clinical-module-response@1.0", "ok": False, "reason_code": code,
                "diagnostics": failure_state, "public_record": None, "private_record": None}


def capture_training_background(training_request, training_response, context, *, trusted_run_hashes, size=100, seed=1729):
    """Trusted-root post-train hook; only deterministic partition replay/predict."""
    origin = _authorize(training_request, context)
    p, bridge, facade = _owners()
    q, response = training_request, training_response
    need(isinstance(trusted_run_hashes, dict) and set(trusted_run_hashes) == {"request_sha256", "response_sha256"},
         "TRUSTED_TRAINING_ARTIFACT_BINDINGS_REQUIRED")
    need(trusted_run_hashes["request_sha256"] == p.common._digest(q) and
         trusted_run_hashes["response_sha256"] == p.common._digest(response), "TRAINING_ARTIFACT_BINDING_MISMATCH")
    payload, semantics = _validate(q, facade)
    facade.validate_json(response, facade.CONTRACTS_ROOT / "module-response.schema.json")
    need(q["operation"] == "train" and response["ok"] and q["method_id"] in PREDICTION_METHODS,
         "SUCCESSFUL_TRAINING_ARTIFACTS_REQUIRED")
    need(payload["application_scope"] == "development" and payload["frozen_model_json"] is None and q["bindings"]["model_sha256"] is None,
         "ORIGINAL_TRAINING_REQUEST_REQUIRED")
    explanation_owner = importlib.import_module("tree_shap.explain")
    budget_callback = getattr(context, "resource_limits", None)
    limits = explanation_owner.resource_limits(budget_callback() if callable(budget_callback) else None,
        q["method_id"])
    need(type(size) is int and 10 <= size <= limits["max_background_rows"] and type(seed) is int and 0 <= seed < 2**32, "BACKGROUND_SAMPLING_INVALID")
    rows, spec = payload["rows"], payload["spec"]
    p.validate_spec(spec, q["method_id"])
    bundle = bridge.strict_load(response["private_record"]["frozen_model_json"].encode())
    inner = _check_bundle(bundle, q["method_id"], spec, semantics, "development_holdout", origin, p, bridge, facade)
    need(response["diagnostics"]["provider_version"] == p.provider_version() and response["diagnostics"]["runtime"] == p.runtime(),
         "TRAINING_RESPONSE_PROVIDER_MISMATCH")
    data, counts = p.common._rows(rows, spec, training=True)
    training_ix, holdout_ix = p.common._split(data, spec)
    training = [data[i] for i in training_ix]
    if spec["calibration"]["method"] == "sigmoid":
        cal_spec = copy.deepcopy(spec)
        cal_spec["split"]["test_fraction"] = spec["calibration"]["fraction"]
        cal_spec["split"]["seed"] = (spec["split"]["seed"] + 1871) % 2**32
        fit_ix, cal_ix = p.common._split(training, cal_spec)
    else:
        fit_ix, cal_ix = list(range(len(training))), []
    partition_ix = {"model_fit": [training_ix[i] for i in fit_ix], "calibration": [training_ix[i] for i in cal_ix], "holdout": holdout_ix}
    lookup = {p.common._id_digest(row[spec["id"]]): i for i, row in enumerate(rows)}
    expected = {lookup[p.common._id_digest(data[i][spec["id"]])]: role for role, indices in partition_ix.items() for i in indices}
    trace = response["private_record"]["individual"]
    need(len(trace) == len(expected) and len({v["row_index"] for v in trace}) == len(trace) and
         {v["row_index"]: v["partition"] for v in trace} == expected, "TRAINING_PARTITION_TRACE_MISMATCH")
    ordered = sorted(expected)
    predicted = p.predict([rows[i] for i in ordered], inner["model"])
    by_index = {v["row_index"]: v["prediction"] for v in trace}
    need(p.np.max(p.np.abs(predicted - [by_index[i] for i in ordered])) <= 1e-12, "TRAINING_TRACE_PREDICTION_MISMATCH")
    for role, indices in partition_ix.items():
        need(response["diagnostics"]["counts"][role + "_n"] == len(indices), "TRAINING_PARTITION_COUNTS_MISMATCH")
    positions = sorted(i for i, role in expected.items() if role == "model_fit")
    need(size <= len(positions), "BACKGROUND_SIZE_EXCEEDS_MODEL_FIT")
    chosen = sorted(p.np.random.default_rng(seed).choice(positions, size, replace=False).tolist())
    identity = spec["id"]; names = [v["name"] for v in spec["features"]]
    partitions = {role: sorted(p.common._id_digest(data[i][identity]) for i in indices) for role, indices in partition_ix.items()}
    artifact = bridge.seal({"schema_version": "clinical-tree-shap-background@1.0", "prediction_method_id": q["method_id"],
        "model_sha256": bundle["sha256"], "prediction_provider_version": bundle["provider_version"],
        "source": {"origin": "actual_successful_training_request_and_response", "cohort_id": spec["cohort_id"],
            "identity_namespace": semantics["identity_namespace"], "canonical_rows_sha256": p.common._digest(rows),
            "training_request_sha256": p.common._digest(q), "training_response_sha256": p.common._digest(response),
            "training_bindings": copy.deepcopy(q["bindings"]), "source_n": len(rows), "outcome_missing_n": counts["missing_outcome_n"]},
        "partition": {"role": "model_fit", "model_fit_id_digests": partitions["model_fit"], "calibration_id_digests": partitions["calibration"],
            "holdout_id_digests": partitions["holdout"], "excluded_outcome_id_digests": sorted(p.common._id_digest(rows[i][identity]) for i in range(len(rows)) if i not in expected)},
        "sampling": {"method": "uniform_without_replacement", "seed": seed, "n": size, "row_indices": chosen},
        "rows": [{identity: rows[i][identity], **{name: rows[i][name] for name in names}} for i in chosen],
        "classification": "LOCAL_PRIVATE_TRAINING_BACKGROUND",
        "authenticity": "hashes_and_partition_checks_are_integrity_only; common_owner_verifies_trusted_original_run"})
    importlib.import_module("tree_shap.background").check_background(artifact, bundle, spec, resource_budget=limits,
                                                                  budget_method=q["method_id"])
    return artifact
