"""Closed contracts for external interpretation of frozen v0.8 models.

The original v0.9 task is bound by the shared validator. An internal method-only
view reuses v0.8 inference checks without sealing or replacing the bound task.
No transform, background statistic or attribution is fitted here.
"""
from __future__ import annotations

import copy
import hashlib
import json


INPUT_VERSION = "clinical-study-input@0.9.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-linear-interpretation-v09-20261024"
METHOD = "interpretation.linear.interventional"
EXPLAINER_VERSION = "clinical-frozen-interpretation@0.9.0-candidate1"
MAX_ROWS = 200
PROVIDER_SOURCE = "src/clinanalysis/R/interpretation_v09.R"


def code_requirements(base):
    return set(base) | {"python/clinical_methods/interpretation_v09_contracts.py", PROVIDER_SOURCE,
        "src/clinanalysis/R/clinical_interpretation_v09.R"}


def obj(properties):
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def options_schema(penalized):
    reference = obj({"local_ref": {"type": "string", "minLength": 1},
        "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}})
    return obj({"model_method_id": {"enum": sorted(penalized.METHODS)},
        "spec": copy.deepcopy(penalized.options_schema()["properties"]["spec"]),
        "model_ref": copy.deepcopy(reference), "explainer_ref": copy.deepcopy(reference)})


def make_schema(base, penalized):
    schema = copy.deepcopy(base)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    schema["properties"]["execution"]["properties"]["authorization_ref"] = {"const": AUTHORIZATION_REF}
    analysis = schema["properties"]["analysis"]
    analysis["properties"].update(method_id={"const": METHOD}, spec={"type": "null"},
        baseline={"type": "null"}, interpretation=options_schema(penalized),
        effect_scale={"enum": ["outcome units", "log_odds"]},
        variance={"const": "not_applicable"}, ci_level={"type": "null"})
    analysis["required"].append("interpretation")
    return schema


def inference_options(options):
    return {"operation": "infer", "spec": copy.deepcopy(options["spec"]),
        "model_ref": copy.deepcopy(options["model_ref"]), "unknown_category_policy": "reject"}


def inference_view(task):
    """Return only an internal validation view, never a replacement receipt."""
    value = copy.deepcopy(task)
    options = value["analysis"].pop("interpretation")
    value["analysis"].update(method_id=options["model_method_id"],
        penalized_prediction=inference_options(options), ci_level=.95,
        effect_scale="probability" if options["model_method_id"].startswith("prediction.binary.") else "outcome units")
    return value


def validate_time(task, need, stage, penalized):
    penalized.validate_time(inference_view(task), need, stage)


def explainer_schema(spec, variables, *, max_background_rows=MAX_ROWS):
    string = {"type": "string", "minLength": 1}
    name = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
    number = {"type": "number"}
    nullable_number = {"type": ["number", "null"]}
    nullable_string = {"type": ["string", "null"]}
    scalar = {"type": ["number", "string", "null"]}
    hash_schema = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    def array(item, minimum=0, maximum=2400):
        return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}
    row = {spec["id"]: string}
    for feature in spec["features"]:
        row[feature["name"]] = ({"type": ["number", "null"]} if feature["type"] == "number"
            else {"enum": copy.deepcopy(variables[feature["name"]]["levels"]) + [None]})
    definition = obj({"method": {"const": "exact_affine_grouped_interventional_shap"},
        "background": {"const": "full_frozen_training_empirical"}, "coalition_unit": {"const": "raw_feature"},
        "missing_policy": {"const": "frozen_training_median_mode"},
        "score_scale": {"const": "signed_original_outcome" if spec["family"] == "gaussian" else "logit"},
        "score_unit": {"const": variables[spec["outcome"]]["unit"] if spec["family"] == "gaussian" else "1"},
        "conditional": {"const": False}, "probability_scale": {"const": False}, "causal": {"const": False}})
    domain = obj({"feature": name, "type": {"enum": ["number", "category"]}, "unit": string,
        "observed_min": nullable_number, "observed_max": nullable_number, "fitted_levels": array(string),
        "fitted_reference": nullable_string, "impute_value": {"type": ["number", "string"]},
        "missing_policy": {"const": "frozen_training_median_mode"}, "encoding_rule": string,
        "n_encoded_columns": {"type": "integer", "minimum": 0, "maximum": 60},
        "score_min": number, "score_max": number, "score_range": {"type": "number", "minimum": 0}})
    axis = obj({"feature": name, "type": {"enum": ["number", "category"]}, "unit": string,
        "input_kind": string, "value": scalar, "resolved_value": scalar,
        "score_contribution": number, "points": number})
    return obj({"schema_version": {"const": EXPLAINER_VERSION}, "method_id": {"const": METHOD},
        "model_method_id": string, "model_sha256": hash_schema, "model_content_sha256": hash_schema,
        "provider_version": hash_schema, "transform_sha256": hash_schema, "definition": definition,
        "background": obj({"scope": {"const": "full_training"},
            "n": {"type": "integer", "minimum": 1, "maximum": max_background_rows},
            "subject_ids_sha256": hash_schema, "training_groups_sha256": hash_schema, "rows_sha256": hash_schema,
            "rows": array(obj(row), 1, max_background_rows),
            "encoded_means": array(obj({"term": string, "mean": number}), 1, 60)}),
        "score": obj({"intercept": number,
            "coefficients": array(obj({"term": string, "feature": name, "coefficient": number}), 1, 60),
            "base_value": number}),
        "nomogram": obj({"domain_policy": {"const": "frozen_training_observed"},
            "constant_model": {"type": "boolean"}, "score_at_zero": number, "score_per_point": nullable_number,
            "points_denominator": {"type": "number", "minimum": 0}, "max_total_points": {"type": "number", "minimum": 0},
            "domains": array(domain, 1, 12), "axes": array(axis, 1),
            "total_axis": array(obj({"total_points": number, "score": number, "prediction": number}), 1)})})


def _bound_explainer(task, variables, model_wrapper, root, helpers):
    need = helpers["need"]
    stage = "binding"
    options = task["analysis"]["interpretation"]
    reference, spec = options["explainer_ref"], options["spec"]
    limits = (helpers["_resource_budget"].resolve(task["execution"], task["analysis"]["method_id"])
              if task.get("schema_version") == "clinical-study-input@1.0" else None)
    artifact_max_bytes = limits["max_input_bytes"] if limits else helpers["MAX_BYTES"]
    path = helpers["confined"](reference["local_ref"], root, "EXPLAINER_OUTSIDE_ISOLATED_ROOT")
    need(path.is_file() and path.suffix.lower() == ".json" and path.stat().st_size <= artifact_max_bytes,
         "FROZEN_EXPLAINER_FILE_REQUIRED", stage)
    raw = path.read_bytes()
    need(len(raw) <= artifact_max_bytes, "FROZEN_EXPLAINER_FILE_REQUIRED", stage)
    need(hashlib.sha256(raw).hexdigest() == reference["content_hash"], "EXPLAINER_CONTENT_HASH_MISMATCH", stage)
    try:
        bundle = helpers["read_json_bytes"](raw)
    except (UnicodeError, json.JSONDecodeError):
        raise helpers["ContractBlocked"]("FROZEN_EXPLAINER_JSON_INVALID", stage) from None
    legacy_schema = explainer_schema(spec, variables, max_background_rows=(
        limits["max_background_rows"] if limits else MAX_ROWS))
    if task.get("schema_version") == "clinical-study-input@1.0":
        upgraded = copy.deepcopy(legacy_schema)
        upgraded["properties"].update({
            "provenance_version": {"const": "clinical-frozen-provenance@1.0"},
            "data_origin": {"enum": ["real", "synthetic"]},
            "task_purpose": {"enum": ["engineering_test", "research_analysis"]},
            "test_only": {"type": "boolean"},
            "scientific_review": {"const": "pending"}, "export_status": {"const": "local_only"}})
        upgraded["required"] += ["provenance_version", "data_origin", "task_purpose", "test_only", "scientific_review", "export_status"]
        origin_schema = upgraded if task["data_origin"] == "real" else {"anyOf": [legacy_schema, upgraded]}
        helpers["validate_schema"](bundle, origin_schema, "explainer")
        if task["data_origin"] == "real" or "provenance_version" in bundle:
            family = helpers["_real_family_admission"]
            actual = family.frozen_context(task, bundle, need, stage)
            expected_origin = family.frozen_context(task, model_wrapper, need, stage)
            need(actual == expected_origin, "EXPLAINER_MODEL_ORIGIN_MISMATCH", stage)
    else:
        helpers["validate_schema"](bundle, legacy_schema, "explainer")
    need(bundle["model_method_id"] == options["model_method_id"], "EXPLAINER_MODEL_METHOD_MISMATCH", stage)
    need(bundle["model_sha256"] == options["model_ref"]["content_hash"], "EXPLAINER_MODEL_HASH_MISMATCH", stage)
    lock_path = root / "runtime-lock.json"
    need(lock_path.is_file(), "INTERPRETATION_PROVIDER_BINDING_REQUIRED", stage)
    expected = helpers["read_json"](lock_path).get("interpretation_provider_version")
    need(isinstance(expected, str) and len(expected) == 64, "INTERPRETATION_PROVIDER_BINDING_REQUIRED", stage)
    need(bundle["provider_version"] == expected == helpers["file_hash"](root / PROVIDER_SOURCE),
         "INTERPRETATION_PROVIDER_VERSION_MISMATCH", stage)
    background = bundle["background"]
    ids = [row[spec["id"]] for row in background["rows"]]
    training_ids = model_wrapper["model"]["training_subject_ids"]
    need(background["n"] == len(ids) == len(training_ids), "EXPLAINER_BACKGROUND_COUNT_MISMATCH", stage)
    need(ids == training_ids, "EXPLAINER_BACKGROUND_IDENTITY_MISMATCH", stage)
    terms = [row["term"] for row in background["encoded_means"]]
    coefficients = bundle["score"]["coefficients"]
    names = [feature["name"] for feature in spec["features"]]
    need(len(terms) == len(set(terms)) and terms == [row["term"] for row in coefficients]
         and all(row["feature"] in names for row in coefficients), "EXPLAINER_ENCODED_FIELDS_MISMATCH", stage)
    domains = bundle["nomogram"]["domains"]
    need([row["feature"] for row in domains] == names
         and all(row["type"] == variables[row["feature"]]["dtype"]
                 and row["unit"] == variables[row["feature"]]["unit"] for row in domains),
         "EXPLAINER_DOMAIN_FIELDS_MISMATCH", stage)
    need(all(row["feature"] in names and row["type"] == variables[row["feature"]]["dtype"]
             and row["unit"] == variables[row["feature"]]["unit"] for row in bundle["nomogram"]["axes"]),
         "EXPLAINER_DOMAIN_FIELDS_MISMATCH", stage)
    # R recomputes the model/transform/background content hashes and validates
    # every learned quantity. Python does not duplicate R's JSON numeric encoding
    # or fit/recompute any background statistic, contribution or nomogram axis.
    return bundle


def validate_options(task, rows, variables, root, helpers, penalized):
    options = task["analysis"]["interpretation"]
    binary = options["model_method_id"].startswith("prediction.binary.")
    helpers["need"](task["analysis"]["effect_scale"] == ("log_odds" if binary else "outcome units"),
                    "INTERPRETATION_SCALE_MISMATCH", "method_applicability")
    _, _, model_wrapper = penalized.validate_options(inference_view(task), rows, variables, root, helpers)
    bundle = _bound_explainer(task, variables, model_wrapper, root, helpers)
    flow = {"scope": (helpers["_real_family_admission"].interpretation_scope(task)
                       if task.get("schema_version") == "clinical-study-input@1.0" else "external_synthetic_disjoint"), "n_application": len(rows),
        "n_background": bundle["background"]["n"], "outcomes_used": False, "background_refitted": False}
    # Reuse the frozen wrapper's field ordering after the v0.8 comparison has
    # established exact semantic values against the task's canonical metadata.
    return flow, copy.deepcopy(model_wrapper["canonical_semantics"]), model_wrapper, bundle
