"""Shared admitted origin/purpose context; no estimator or host-sandbox claim.

Only the bound module transport constructs this context after its full schema
and method registration checks. A Python object is not an OS security boundary.
Every numerical entry rechecks its request and the active captured invocation.
"""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


class OriginContextError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(ok, code):
    if not ok:
        raise OriginContextError(code)


def _contracts(core_root):
    path = Path(core_root) / "python/clinical_methods/contracts.py"
    spec = importlib.util.spec_from_file_location("module_admitted_common_contracts", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class AdmittedOriginContext:
    """One request's checked metadata; never a permission supplied by payload."""
    def __init__(self, task, core_root, *, allowed_methods, training_background_guard=None):
        self._task = copy.deepcopy(task)
        self._core = Path(core_root).resolve()
        self._allowed_methods = frozenset(allowed_methods)
        self._api = _contracts(self._core)
        self._background_guard = training_background_guard
        self._method = task["method_id"]
        self._operation = task["operation"]
        self._payload_sha256 = canonical(task["payload"])
        self.data_origin = task["data_origin"]
        self.task_purpose = task["task_purpose"]
        self.test_only = self.task_purpose == "engineering_test"
        self.scientific_review = "pending"
        self.project_root = Path(task["project_root"]).resolve()
        _need(self.data_origin in {"real", "synthetic"}, "MODULE_ORIGIN_INVALID")
        _need(self.task_purpose in {"engineering_test", "research_analysis"}, "MODULE_PURPOSE_INVALID")
        # This interface binds the exact normalized payload being analysed. It
        # does not assert that an upstream join, source identity or deidentifying
        # operation was independently reconstructed or authenticated.
        _need(len(task["sources"]) == 1 and
              task["sources"][0]["source_fingerprint"] == self._payload_sha256,
              "MODULE_NORMALIZED_SOURCE_BINDING_MISMATCH")
        self._admit()
        database = task["sources"][0]["database"].upper()
        _need(database not in {"FAERS", "JADER"}, "REPORT_DATA_NOT_CLINICAL_PATIENTS")
        _need(database not in {"NHANES", "CHARLS"}, "SURVEY_PROVIDER_INTEGRATION_PENDING")
        _need(database in {"MIMIC", "EICU", "SELF_FILE", "USER_CLINICAL", "VITALDB", "INSPIRE", "MOVER"},
              "ADAPTER_NOT_VALIDATED")

    def _admit(self):
        self._api._study_input.admit(self._task, self._core, vars(self._api),
                                    allowed_methods=self._allowed_methods)
        # Optional file-to-payload receipts are checked only after the original
        # admission. They bind local source bytes, not source identity or consent.
        path=Path(__file__).resolve().parents[3]/"scripts/ingestion.py"
        spec=importlib.util.spec_from_file_location("toolkit_local_ingestion_check",path)
        ingestion=importlib.util.module_from_spec(spec);spec.loader.exec_module(ingestion)
        ingestion.verify(self._task,required=self.data_origin=="real")

    def require_request(self, method_id, operation, payload):
        _need(method_id == self._method and operation == self._operation,
              "MODULE_ADMITTED_METHOD_OPERATION_MISMATCH")
        _need(canonical(payload) == self._payload_sha256, "MODULE_ADMITTED_PAYLOAD_CHANGED")
        self._admit()
        return self.public_metadata()

    def require_training_background(self, artifact):
        _need(callable(self._background_guard), "TRUSTED_TRAINING_BACKGROUND_CONTEXT_REQUIRED")
        return self._background_guard(artifact)

    def resource_limits(self):
        """Finite request-owned resource policy; never a payload authorization."""
        self._admit()
        return self._api._resource_budget.request_limits(self._task["execution"], self._method)

    def public_metadata(self):
        return {"data_origin": self.data_origin, "task_purpose": self.task_purpose,
                "test_only": self.test_only, "scientific_review": self.scientific_review,
                "source_verification": "normalized_payload_bytes_bound_source_identity_not_authenticated",
                "host_isolation": "not_established"}
