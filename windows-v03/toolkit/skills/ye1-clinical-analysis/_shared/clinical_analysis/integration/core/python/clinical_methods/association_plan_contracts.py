"""Strict semantic contract for prespecified association model plans.

This module performs no filtering, sample selection, estimation or model choice.
The sole numerical owner association.py receives the fully declared plan.
"""
from __future__ import annotations
import copy

INPUT_VERSION = "clinical-study-input@0.3.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-association-v03-20261024"
METHODS = {"association.linear.plan", "association.logistic.plan"}
S = {"type": "string", "minLength": 1}
NAME = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
N = {"type": "number"}


def obj(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required,
            "additionalProperties": False}


def arr(schema, minimum=0, maximum=None):
    result = {"type": "array", "items": schema, "minItems": minimum}
    if maximum is not None:
        result["maxItems"] = maximum
    return result


FILTER = obj({"field": NAME, "op": {"enum": ["eq", "ne", "lt", "le", "gt", "ge", "in"]},
              "value": {"anyOf": [N, S, arr({"type": ["string", "number"]}, 1, 50)]}})
CURVE = obj({"reference": N, "grid": arr(N, 3, 101),
             "domain": arr(N, 2, 2)})


def make_schema(legacy_schema, legacy_spec):
    schema = copy.deepcopy(legacy_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    spec = copy.deepcopy(legacy_spec)
    spec["properties"]["sensitivity"] = arr({}, 0, 0)
    spec["properties"]["nonlinear"]["anyOf"][0]["properties"]["knots"]["maxItems"] = 7
    model = obj({"model_id": NAME, "label": S, "rationale": S,
                 "role": {"enum": ["primary", "adjustment", "sensitivity"]},
                 "where": arr(FILTER, 0, 10), "spec": spec,
                 "curve": {"anyOf": [CURVE, {"type": "null"}]},
                 "subgroup_min_n": {"type": ["integer", "null"], "minimum": 5}})
    plan = obj({"sample_strategy": {"enum": ["per_model_complete_case", "common_complete_case"]},
                "multiplicity": {"const": "unadjusted_prespecified"}, "models": arr(model, 1, 6)})
    analysis = schema["properties"]["analysis"]
    analysis["properties"].update(method_id={"enum": sorted(METHODS)}, spec={"type": "null"},
                                  baseline={"type": "null"}, association=plan)
    analysis["required"].append("association")
    return schema


def code_requirements(legacy):
    return set(legacy) | {"python/clinical_methods/association_plan_contracts.py",
        "python/clinical_methods/association_plan_bridge.py", "src/clinanalysis/R/clinical_association_plan.R"}


def token(value):
    return format(float(value), ".15g") if type(value) in (int, float) else str(value)


def validate_options(task, rows, variables, root, helpers, *, timing_guard=None):
    need = helpers["need"]
    stage = "method_applicability"
    analysis, identity, timing = task["analysis"], task["identity"], task["time"]
    method = analysis["method_id"]
    need(method in METHODS, "METHOD_NOT_INTEGRATED", stage)
    logistic = method == "association.logistic.plan"
    model_kind, variance = ("logistic", "model") if logistic else ("linear", "HC3")
    need(analysis["ci_level"] == .95, "CI_LEVEL_UNSUPPORTED", stage)
    need(analysis["variance"] == variance, "VARIANCE_CONTRACT_MISMATCH", stage)
    need(analysis["effect_scale"] == ("odds_ratio" if logistic else "outcome units"), "EFFECT_SCALE_MISMATCH", stage)
    need(task["missingness"] == {"strategy": "complete_case", "fit_scope": "not_applicable", "exclusion_denominator": "selected_view"},
         "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    need(task["derivation"] == {"strategy": "declared_unit_conversion_only", "version": "1"}, "DERIVATION_NOT_ENABLED", stage)
    plan = analysis["association"]
    models = plan["models"]
    need(len({m["model_id"] for m in models}) == len(models), "MODEL_ID_DUPLICATE", stage)
    need(models[0]["role"] == "primary" and all(m["role"] != "primary" for m in models[1:]), "PRIMARY_MODEL_ORDER_INVALID", stage)
    first = models[0]["spec"]
    for model in models:
        need(bool(model["label"].strip()) and bool(model["rationale"].strip()), "MODEL_PROVENANCE_REQUIRED", stage)
        spec = model["spec"]
        need(spec["model"] == model_kind, "METHOD_MODEL_MISMATCH", stage)
        need(spec["outcome"] == first["outcome"] and spec["exposure"] == first["exposure"], "MODEL_SEQUENCE_TARGET_MISMATCH", stage)
        need(spec["covariance"] == variance, "VARIANCE_OPTION_INTEGRATION_PENDING", stage)
        need(spec["key"] == identity["record_keys"] and spec["subject_id"] == identity["subject_key"]
             and spec["row_unit"] == identity["analysis_unit"] and spec["independent"] is True,
             "METHOD_IDENTITY_MISMATCH", stage)
        outcome, exposure = spec["outcome"], spec["exposure"]
        predictors = [exposure] + spec["covariates"]
        subgroup = spec.get("subgroup")
        if subgroup:
            predictors.append(subgroup["field"])
        need(all(name in variables for name in [outcome] + predictors), "MODEL_FIELD_MISSING", stage)
        need(not any(variables[name]["dtype"] == "id" for name in predictors), "ID_MODEL_FIELD_FORBIDDEN", stage)
        need(len([exposure]+spec["covariates"]) == len(set([exposure]+spec["covariates"]))
             and outcome not in predictors, "DUPLICATE_OR_OUTCOME_PREDICTOR", stage)
        need(outcome == task["outcome"]["field"], "OUTCOME_CONTRACT_MISMATCH", stage)
        need(variables[outcome]["role"] == "outcome", "OUTCOME_ROLE_INVALID", stage)
        if timing_guard is not None:
            timing_guard("outcome", task, variables[outcome], need, stage)
        else:
            need(variables[outcome]["available_at"] <= timing["analysis_as_of"]
                 and timing["outcome_window"][0] <= variables[outcome]["occurred_at"] <= timing["outcome_window"][1],
                 "OUTCOME_LABEL_NOT_MATURE", stage)
        need(variables[exposure]["role"] == "exposure", "EXPOSURE_ROLE_INVALID", stage)
        need(all(variables[name]["role"] in {"covariate", "group"} for name in spec["covariates"]), "COVARIATE_ROLE_INVALID", stage)
        for name in predictors:
            need(variables[name]["dtype"] in {"number", "category"}, "MODEL_FIELD_TYPE_UNSUPPORTED", stage)
            if timing_guard is not None:
                timing_guard("predictor", task, variables[name], need, stage)
            else:
                need(variables[name]["occurred_at"] <= variables[name]["available_at"] <= timing["feature_cutoff"], "FUTURE_INFORMATION", stage)
        # The provider adds the subgroup dummy automatically; a duplicate
        # declaration in categorical is legal only if it agrees exactly.
        categories = {name for name in [exposure]+spec["covariates"] if variables[name]["dtype"] == "category"}
        allowed_categories = categories | ({subgroup["field"]} if subgroup else set())
        need(categories <= set(spec["categorical"]) <= allowed_categories, "CATEGORY_SPEC_MISMATCH", stage)
        for name, contract in spec["categorical"].items():
            need(contract == {"levels": variables[name]["levels"], "reference": variables[name]["reference"]}, "CATEGORY_SPEC_MISMATCH", stage)
        if logistic:
            need(task["outcome"]["type"] == "binary" and variables[outcome]["dtype"] == "category"
                 and "event" in spec and "non_event" in spec, "BINARY_CODING_MISMATCH", stage)
            need(token(task["outcome"]["event"]) == token(spec["event"])
                 and token(task["outcome"]["non_event"]) == token(spec["non_event"])
                 and token(spec["event"]) != token(spec["non_event"])
                 and {token(spec["event"]), token(spec["non_event"])} == set(variables[outcome]["levels"]),
                 "BINARY_CODING_MISMATCH", stage)
        else:
            need(task["outcome"]["type"] == "continuous" and variables[outcome]["dtype"] == "number", "CONTINUOUS_OUTCOME_REQUIRED", stage)
            need("event" not in spec and "non_event" not in spec, "CONTINUOUS_EVENT_CODING_NOT_ALLOWED", stage)
        nonlinear, curve = spec.get("nonlinear"), model["curve"]
        need(not (nonlinear and subgroup), "RCS_SUBGROUP_COMBINATION_NOT_SUPPORTED_V03", stage)
        if nonlinear:
            need(variables[exposure]["dtype"] == "number", "SPLINE_REQUIRES_NUMERIC_EXPOSURE", stage)
            knots = nonlinear["knots"]
            need(all(a < b for a, b in zip(knots, knots[1:])), "SPLINE_KNOTS_ORDER", stage)
            need(curve is not None, "RCS_CURVE_SPEC_REQUIRED", stage)
        else:
            need(curve is None, "CURVE_REQUIRES_RCS", stage)
        if curve:
            low, high = curve["domain"]
            need(low < high, "CURVE_DOMAIN_INVALID", stage)
            need(low <= curve["reference"] <= high, "CURVE_REFERENCE_OUTSIDE_DOMAIN", stage)
            need(all(low <= x <= high for x in curve["grid"]) and all(a < b for a,b in zip(curve["grid"],curve["grid"][1:])),
                 "CURVE_GRID_INVALID", stage)
        if subgroup:
            name = subgroup["field"]
            need(name not in {outcome,exposure} and variables[name]["dtype"] == "category"
                 and variables[name]["role"] in {"covariate", "group"}, "SUBGROUP_CONTRACT_MISMATCH", stage)
            need({"levels":subgroup["levels"],"reference":subgroup["reference"]} ==
                 {"levels":variables[name]["levels"],"reference":variables[name]["reference"]}, "SUBGROUP_CONTRACT_MISMATCH", stage)
            need(variables[exposure]["dtype"] == "number", "SUBGROUP_NUMERIC_EXPOSURE_REQUIRED", stage)
            need(model["subgroup_min_n"] is not None, "SUBGROUP_MINIMUM_REQUIRED", stage)
        else:
            need(model["subgroup_min_n"] is None, "SUBGROUP_MINIMUM_WITHOUT_SUBGROUP", stage)
        need(model["role"] == "sensitivity" or not model["where"], "FILTER_ONLY_FOR_SENSITIVITY", stage)
        for condition in model["where"]:
            name, op, value = condition["field"], condition["op"], condition["value"]
            need(name in variables, "SENSITIVITY_FIELD_MISSING", stage)
            var = variables[name]
            need(var["dtype"] != "id" and var["role"] in {"exposure", "covariate", "group"}, "SENSITIVITY_FIELD_ROLE_INVALID", stage)
            if timing_guard is not None:
                timing_guard("filter", task, var, need, stage)
            else:
                need(var["occurred_at"] <= var["available_at"] <= timing["feature_cutoff"], "FUTURE_INFORMATION", stage)
            values = value if op == "in" else [value]
            need((isinstance(value,list) and bool(value)) if op == "in" else not isinstance(value,list), "SENSITIVITY_FILTER_VALUE_INVALID", stage)
            if var["dtype"] == "number":
                need(all(type(x) in (int,float) for x in values), "SENSITIVITY_FILTER_VALUE_INVALID", stage)
            else:
                need(op in {"eq", "ne", "in"}, "CATEGORY_FILTER_OPERATOR_INVALID", stage)
                need(all(type(x) is str and x in var["levels"] for x in values), "SENSITIVITY_FILTER_CATEGORY_INVALID", stage)
    return {"sample_strategy":plan["sample_strategy"], "model_ids":[m["model_id"] for m in models],
            "fit_scope":"not_applicable", "numeric_support_checks":"per_model_complete_cases_in_provider"}
