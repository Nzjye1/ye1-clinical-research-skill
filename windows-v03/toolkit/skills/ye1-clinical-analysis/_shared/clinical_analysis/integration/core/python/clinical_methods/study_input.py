"""Origin-aware admission for the existing clinical task validator.

No estimation, defaults for clinical hypotheses, or permission creation occurs
here. Real data uses the same project choice and quotable evidence as legacy.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import os

INPUT_VERSION = "clinical-study-input@1.0"
RESULT_VERSION = "clinical-analysis-result@1.0"
METHODS = {"baseline.table1", "association.linear", "association.logistic",
           "association.linear.plan", "association.logistic.plan",
           "prediction.continuous.signed.lasso", "prediction.continuous.signed.elasticnet",
           "prediction.binary.lasso", "prediction.binary.elasticnet", "interpretation.linear.interventional",
           "prediction.survival.cox.lasso", "prediction.survival.cox.elasticnet",
           "causal.psm.att.continuous",
           "prediction.continuous.nonnegative.ridge", "prediction.binary.ridge",
           "survival.kaplan_meier", "survival.cox.association",
           "prediction.survival.cox", "evaluation.survival.cox.ipcw"}


def make_schema(base):
    s = copy.deepcopy(base)
    s["$id"] = INPUT_VERSION
    p = s["properties"]
    p["schema_version"] = {"const": INPUT_VERSION}
    p["data_origin"] = {"enum": ["real", "synthetic"]}
    p["task_purpose"] = {"enum": ["engineering_test", "research_analysis"]}
    p["project_root"] = {"type": "string", "minLength": 1}
    confirmation = {"type": "object", "additionalProperties": False,
        "required": ["source_kind", "source_path", "source_locator", "quote"], "properties": {
            "source_kind": {"enum": ["direct_user", "delegated_user_instruction"]},
            **{k: {"type": "string", "minLength": 1} for k in ("source_path", "source_locator", "quote")}}}
    p["authorization"] = {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": False,
        "required": ["choice_sha256", "plan_sha256", "confirmation"], "properties": {
            "choice_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "external_files": {"type":"array","items":{"type":"object","additionalProperties":False,"required":["path","sha256"],"properties":{"path":{"type":"string","minLength":1},"sha256":{"type":"string","pattern":"^[0-9a-f]{64}$"}}}},
            "plan_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}, "scope_kind": {"enum": ["engineering_instruction", "research_plan"]}, "confirmation": confirmation}}]}
    s["required"] += ["data_origin", "task_purpose", "project_root", "authorization"]
    source = p["sources"]["items"]
    source["properties"]["verification_status"] = {"const": "local_bytes_bound"}
    source["properties"]["source_kind"] = {"enum": ["user_clinical_file", "public_clinical_extract", "synthetic_fixture"]}
    source["required"].append("source_kind")
    var = p["variables"]["items"]["properties"]
    var["role"]["enum"] += ["descriptive_measure", "stratification_label", "outcome_summary"]
    var["occurred_at"] = var["available_at"] = {"type": ["number", "null"]}
    timing = p["time"]["properties"]
    timing["policy"] = {"enum": ["descriptive_snapshot", "cross_sectional_association", "ordered_observation"]}
    p["time"]["required"].append("policy")
    for k in ("index", "feature_cutoff", "label_mature_at", "analysis_as_of"):
        timing[k] = {"type": ["number", "null"]}
    timing["outcome_window"] = {"anyOf": [{"type": "null"}, timing["outcome_window"]]}
    p["outcome"] = {"anyOf": [{"type": "null"}, p["outcome"]]}
    view = p["views"]["items"]
    # Source labels are literal CSV metadata, never formula/model identifiers.
    # Keep canonical variable names ASCII; do not normalize or rename raw CSV.
    view["properties"]["column_map"]["additionalProperties"] = {
        "type": "string", "minLength": 1, "maxLength": 256,
        "pattern": "^[^\\x00-\\x1f\\x7f-\\x9f]+$"}
    view["properties"].update(location_policy={"enum":["project_local","explicit_bound_external"]},format={"enum": ["csv", "csv_gzip"]},
                              unselected_columns={"type": "array", "items": {"type": "string"}})
    view["properties"]["selection"] = {"type":"object","additionalProperties":False,"required":["kind","order_by"],"properties":{"kind":{"const":"engineering_one_record_per_subject"},"order_by":{"type":"array","minItems":1,"items":{"type":"string"}}}}
    view["required"] += ["format", "unselected_columns"]
    baseline = p["analysis"]["properties"]["baseline"]["anyOf"][0]
    baseline["properties"]["group"] = {"type": ["string", "null"]}
    execution = p["execution"]["properties"]
    execution["mode"] = {"const": "local"}
    execution["privacy_profile"] = {"enum": ["legacy_exclusive_gateway", "captured_local_process"]}
    execution["authorization_ref"] = {"type": ["string", "null"]}
    for k in ("max_rows", "max_bytes"):
        execution[k] = {"type": "integer", "minimum": 1}
    execution["max_decoded_bytes"] = {"type": "integer", "minimum": 1}
    execution["resource_budget"] = {"type":"object", "additionalProperties":False, "properties": {
        "max_design_columns":{"type":"integer","minimum":1,"maximum":1024},
        "max_work_units":{"type":"integer","minimum":1,"maximum":10000000000},
        "max_candidate_pairs":{"type":"integer","minimum":1,"maximum":100000000},
        "max_background_rows":{"type":"integer","minimum":1,"maximum":100000}}}
    p["execution"]["required"].append("max_decoded_bytes")
    return s


def plan_scope_hash(task, canonical):
    value = copy.deepcopy(task)
    value.pop("authorization", None)
    value.pop("plan_hash", None)
    value.pop("plan_sha256", None)
    value.pop("execution", None)
    return canonical(value)


def _module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def admit(task, core_root, g, *, allowed_methods=None):
    need = g["need"]
    project = Path(task["project_root"]).resolve()
    need(project.is_dir(), "PROJECT_DIRECTORY_REQUIRED", "admission")
    method = task.get("analysis", {}).get("method_id", task.get("method_id"))
    need(method in (METHODS if allowed_methods is None else allowed_methods), "REAL_METHOD_ADMISSION_NOT_IMPLEMENTED", "admission")
    origin = task["data_origin"]
    kinds = {s["source_kind"] for s in task["sources"]}
    need(kinds <= ({"synthetic_fixture"} if origin == "synthetic" else
                   {"user_clinical_file", "public_clinical_extract"}), "SOURCE_ORIGIN_CONFLICT", "admission")
    if origin == "synthetic":
        need(task["task_purpose"] == "engineering_test" and task["authorization"] is None and task["execution"]["authorization_ref"] is None,
             "SYNTHETIC_ENGINEERING_SCOPE_REQUIRED", "admission")
        return {"project": project, "authorization_ref": None,
                "source_verification": "local_bytes_bound_not_source_identity_authenticated"}
    legacy = Path(core_root).resolve().parents[1] / "legacy/scripts"
    privacy = _module(legacy / "privacy_boundary.py", "clinical_study_project_privacy")
    evidence = _module(legacy / "confirmation_evidence.py", "clinical_study_confirmation")
    need(os.environ.get("YE1_PRIVACY_CONTROLLED_RUN") == "1", "CONTROLLED_ADAPTER_REQUIRED", "admission")
    need(bool(os.environ.get("YE1_PRIVACY_PROJECT")) and Path(os.environ["YE1_PRIVACY_PROJECT"]).resolve() == project,
         "PROJECT_CHOICE_CONTEXT_MISMATCH", "admission")
    # Test fixtures must never authorize real input through a test host/choice.
    need(os.environ.get("YE1_PRIVACY_SYNTHETIC_TEST") != "1", "TEST_CONTEXT_CANNOT_AUTHORIZE_REAL_DATA", "admission")
    try:
        choice, history = privacy.load(project)
        if task["execution"].get("privacy_profile", "legacy_exclusive_gateway") == "captured_local_process":
            capture = _module(Path(core_root).resolve().parent / "captured_study.py", "clinical_study_captured_adapter")
            capture.verify_context(project, task, core_root)
        else:
            privacy.host_check(project, choice["mode"], test_only=False)
    except (OSError, ValueError, KeyError, TypeError) as e:
        code = str(e) if str(e).isupper() and " " not in str(e) else "PROJECT_PRIVACY_CONTEXT_REQUIRED"
        need(False, code, "admission", ["existing project choice and assessed controlled adapter"])
    auth = task["authorization"]
    need(isinstance(auth, dict), "PROJECT_PLAN_CONFIRMATION_REQUIRED", "admission")
    choice_hash = hashlib.sha256((project / ".ye1-privacy/choice.json").read_bytes()).hexdigest()
    need(auth["choice_sha256"] == choice_hash, "PROJECT_CHOICE_CHANGED", "admission")
    need(auth["plan_sha256"] == plan_scope_hash(task, g["canonical_hash"]), "CONFIRMED_PLAN_CHANGED", "admission")
    scope_kind = auth.get("scope_kind", "research_plan")
    need(scope_kind == "research_plan" or task["task_purpose"] == "engineering_test",
         "ENGINEERING_PERMISSION_CANNOT_APPROVE_RESEARCH", "admission")
    try:
        record = auth["confirmation"]
        if isinstance(record, dict) and record.get("source_kind") == "delegated_user_instruction":
            need(scope_kind == "engineering_instruction" and task["task_purpose"] == "engineering_test",
                 "DELEGATED_INSTRUCTION_CANNOT_APPROVE_RESEARCH", "admission")
            path = Path(record["source_path"]).resolve()
            need(path.is_relative_to(project) and path.is_file() and not path.is_symlink(),
                 "INSTRUCTION_RECORD_REQUIRED", "admission")
            raw = path.read_bytes()
            need(len(raw) <= 524288 and bool(record["source_locator"]) and bool(record["quote"])
                 and record["quote"] in raw.decode("utf-8-sig"), "INSTRUCTION_RECORD_CHANGED", "admission")
            confirmed = {"source_sha256": hashlib.sha256(raw).hexdigest(), "kind": "delegated_user_instruction"}
        else:
            confirmed = evidence.validate(record, simulated=False)
    except (OSError, ValueError, KeyError, TypeError):
        need(False, "ACTUAL_USER_CONFIRMATION_REQUIRED", "admission")
    need(task["execution"]["authorization_ref"] == confirmed["source_sha256"],
         "AUTHORIZATION_SOURCE_CHANGED", "admission")
    return {"project": project, "authorization_ref": confirmed["source_sha256"],
            "choice_revision": len(history), "choice_sha256": choice_hash,
            "host_isolation": "descriptor_is_not_isolation_proof",
            "source_verification": "local_bytes_bound_not_source_identity_authenticated"}


def validate_time(task, need):
    tm = task["time"]
    method = task["analysis"]["method_id"]
    need(not tm["delayed_entry"], "DELAYED_ENTRY_UNSUPPORTED", "view_semantics")
    if tm["policy"] == "descriptive_snapshot":
        need(method == "baseline.table1", "DESCRIPTIVE_TIME_CANNOT_SUPPORT_MODEL", "view_semantics")
    elif tm["policy"] == "cross_sectional_association":
        need(method in {"association.linear", "association.logistic"}, "TIME_POLICY_METHOD_MISMATCH", "view_semantics")
    else:
        vals = [tm[k] for k in ("index", "feature_cutoff", "label_mature_at", "analysis_as_of")]
        need(all(v is not None for v in vals) and tm["outcome_window"] is not None,
             "ORDERED_TIME_VALUES_REQUIRED", "view_semantics")
        need(tm["index"] <= tm["feature_cutoff"] <= tm["outcome_window"][0] < tm["outcome_window"][1]
             <= tm["label_mature_at"] <= tm["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", "view_semantics")
    need(tm["timezone"] in {"relative", "not_applicable"}, "TIMEZONE_UNSUPPORTED", "view_semantics")


def validate_variable_time(task, variable, need):
    a, b = variable["occurred_at"], variable["available_at"]
    need((a is None) == (b is None), "PARTIAL_VARIABLE_TIMING", "view_semantics")
    if a is not None:
        need(a <= b, "AVAILABILITY_BEFORE_MEASUREMENT", "view_semantics")
    if task["time"]["policy"] == "ordered_observation" and variable["role"] in {"exposure", "covariate"}:
        need(a is not None and b <= task["time"]["feature_cutoff"], "FUTURE_INFORMATION", "view_semantics")
    if task["time"]["policy"] == "cross_sectional_association" and variable["role"] in {"exposure", "covariate"}:
        cutoff = task["time"]["feature_cutoff"]
        if b is not None and cutoff is not None:
            need(b <= cutoff, "FUTURE_INFORMATION", "view_semantics")


def seal(task, core_root, g):
    for view in task["views"]:
        path = Path(view["local_ref"])
        if task["data_origin"] == "synthetic" and path.is_file():
            view["content_hash"] = g["file_hash"](path)
            for source in task["sources"]:
                if source["source_id"] in view["source_ids"]:
                    source["source_fingerprint"] = view["content_hash"]
        view["transformation_hash"] = g["transformation_hash"](task, view)
    task["execution"]["expected_source_hashes"] = {s["source_id"]: s["source_fingerprint"] for s in task["sources"]}
    task["execution"]["expected_code_hashes"] = {p: g["file_hash"](Path(core_root)/p) for p in g["required_code_for_task"](task)}
    task["plan_hash"] = g["plan_hash"](task)
    return task


def resolve_view(task, view, admission, g):
    if view.get("location_policy", "project_local") == "project_local":
        return g["confined"](view["local_ref"], admission["project"], "VIEW_OUTSIDE_ISOLATED_ROOT")
    g["need"](task["data_origin"] == "real", "EXTERNAL_VIEW_REQUIRES_REAL_ADMISSION", "binding")
    path = Path(view["local_ref"]).resolve()
    refs = task["authorization"].get("external_files", [])
    matches = [ref for ref in refs if Path(ref["path"]).resolve() == path and ref["sha256"] == view["content_hash"]]
    g["need"](len(matches) == 1, "EXTERNAL_SOURCE_BINDING_REQUIRED", "binding")
    # Read permission still comes from the selected execution environment. This
    # exact file binding is not a filesystem permission or a directory grant.
    return path


def select_engineering_records(task, view, rows, g):
    selection = view.get("selection")
    if selection is None:
        return rows
    need = g["need"]
    need(task["task_purpose"] == "engineering_test", "ENGINEERING_SELECTION_CANNOT_DEFINE_RESEARCH_COHORT", "view_semantics")
    identity = task["identity"]
    need(identity["analysis_unit"] == "subject" and selection["order_by"] == identity["record_keys"],
         "ENGINEERING_SELECTION_KEYS_INVALID", "view_semantics")
    subject = identity["subject_key"]
    need(all(row[subject] is not None and all(isinstance(row[k],str) for k in identity["record_keys"]) for row in rows),
         "ENGINEERING_SELECTION_ID_REQUIRED", "view_semantics")
    ordered = sorted(rows, key=lambda row: tuple(row[k].encode("utf-8") for k in selection["order_by"]))
    selected = {}
    for row in ordered:
        selected.setdefault(row[subject],row)
    return list(selected.values())
