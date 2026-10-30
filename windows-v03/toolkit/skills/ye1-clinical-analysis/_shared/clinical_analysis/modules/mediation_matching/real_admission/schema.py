"""Independent, closed admission fragments; no shared schema writes."""
from pathlib import Path
import copy
import json

HERE = Path(__file__).resolve().parent
MODULE = HERE.parent
METHODS = ("mediation.linear.binary_exposure", "causal.psm.att.binary", "causal.psm.matched.survival")


def obj(fields, required=None):
    return {"type": "object", "properties": fields, "required": list(fields) if required is None else required, "additionalProperties": False}


def nullable(value):
    return {"anyOf": [value, {"type": "null"}]}


def schemas():
    payload = json.loads((MODULE / "contracts/payload.schema.json").read_text(encoding="utf-8-sig"))
    payload = copy.deepcopy(payload)
    payload["properties"]["rows"].pop("maxItems", None)
    spec = payload["properties"]["spec"]
    spec["$id"] = "mediation-matching-admitted-spec@1.0"
    for branch in spec["anyOf"]:
        branch["properties"].pop("execution")
        branch["required"].remove("execution")
        branch["properties"]["schema_version"] = {"const": "mediation-matching-admitted-spec@1.0"}
    h = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    text = {"type": "string", "minLength": 1}
    bindings = obj({name: h for name in ("input_sha256", "plan_sha256", "code_sha256", "runtime_sha256")} |
                   {"model_sha256": {"type": "null"}})
    request = obj({"api_version": {"const": "clinical-module-request@1.0"}, "method_id": {"enum": list(METHODS)},
                   "operation": {"const": "analyze"}, "payload": payload, "bindings": bindings})
    public = json.loads((MODULE / "contracts/public_record.schema.json").read_text(encoding="utf-8-sig"))
    for branch in public["anyOf"]:
        for name in ("test_only", "scientific_review", "export_status"):
            branch["properties"].pop(name)
            branch["required"].remove(name)
    private = json.loads((MODULE / "contracts/private_record.schema.json").read_text(encoding="utf-8-sig"))
    provenance = obj({"data_origin": {"enum": ["real", "synthetic"]},
                      "task_purpose": {"enum": ["engineering_test", "research_analysis"]},
                      "scientific_review": {"const": "pending"}, "test_only": {"type": "boolean"}})
    diagnostics = obj({"module_id": {"const": "mediation_matching"}, "stage": {"enum": ["context", "request", "payload", "transport", "analysis"]},
                       "numerical_owner": {"const": "unchanged mediation_matching/R/provider.R"},
                       "causal_assumptions_verified": {"const": False}})
    response = obj({"api_version": {"const": "clinical-admitted-module-response@1.0"}, "ok": {"type": "boolean"},
                    "reason_code": nullable(text), "provenance": nullable(provenance), "diagnostics": diagnostics,
                    "public_record": nullable(public), "private_record": nullable(private)})
    return {"request.schema.json": request, "payload.schema.json": payload, "response.schema.json": response,
            "public_record.schema.json": response["properties"]["public_record"],
            "private_record.schema.json": response["properties"]["private_record"],
            "diagnostics.schema.json": diagnostics}


if __name__ == "__main__":
    destination = HERE / "contracts"
    destination.mkdir(exist_ok=True)
    for name, value in schemas().items():
        (destination / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
