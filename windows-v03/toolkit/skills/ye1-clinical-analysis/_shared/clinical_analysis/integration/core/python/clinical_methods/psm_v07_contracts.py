"""Closed synthetic input contracts for the prespecified v0.7 PSM design.

The sole R numerical owner fits propensity scores, forms matched pairs and
performs paired inference. This module maps meanings and records missingness;
it never drops rows, estimates a propensity score or selects a match.
"""
from __future__ import annotations

import copy

INPUT_VERSION = "clinical-study-input@0.7.0-candidate1"
AUTHORIZATION_REF = "codex_delegation:clinical-core-psm-v07-20261024"
METHOD = "causal.psm.att.continuous"
METHODS = {METHOD}
MAX_ROWS = 200  # Frozen legacy synthetic envelope; V1 admission resolves request budgets.
MAX_COVARIATES = 8
S = {"type": "string", "minLength": 1}
NAME = {"type": "string", "pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
MISSINGNESS = {"strategy": "complete_case_covariates_outcome_required",
               "fit_scope": "propensity_covariates_only", "exclusion_denominator": "source_subjects"}
OVERLAP_EDGES = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1]


def obj(properties):
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


def arr(schema, minimum, maximum=None):
    value = {"type": "array", "items": schema, "minItems": minimum}
    if maximum is not None:
        value["maxItems"] = maximum
    return value


CATEGORY = obj({"levels": arr(S, 2), "reference": S})
OPTIONS = obj({
    "treatment": NAME, "outcome": NAME, "covariates": arr(NAME, 1, MAX_COVARIATES),
    "categorical": {"type": "object", "additionalProperties": CATEGORY},
    "propensity_model": {"const": "logistic_mle"}, "link": {"const": "logit"},
    "estimand": {"const": "ATT_retained_matched_treated"}, "ratio": {"const": 1},
    "replacement": {"const": False}, "distance": {"const": "logit_ps"},
    "caliper": obj({"width": {"type": "number", "minimum": 0, "maximum": 2},
                    "scale": {"const": "sd_logit_ps"},
                    "sd_scope": {"const": "common_support_retained"},
                    "ddof": {"const": 1}, "boundary": {"const": "inclusive"}}),
    "common_support": obj({"strategy": {"const": "minmax_both"},
                           "boundary": {"const": "inclusive"}, "refit": {"const": False}}),
    "ordering": obj({"treated": {"const": "descending_logit_ps_then_subject_id_utf8"},
                     "control_tie": {"const": "subject_id_utf8_ascending"},
                     "row_order": {"const": "subject_id_utf8_ascending"}}),
    "inference": obj({"method": {"const": "paired_t"}, "ci_level": {"const": .95},
                      "variance": {"const": "sample_variance_of_pair_differences"},
                      "conditioning": {"const": "formed_matched_pairs"}}),
    "diagnostics": obj({
        "smd_denominator": {"const": "pre_support_complete_case_treated_sample_sd"},
        "indicator_sd": {"const": "bernoulli_p1mp"}, "standardize_binary": {"const": True},
        "ps_overlap_edges": {**arr({"type": "number", "minimum": 0, "maximum": 1}, 11, 11),
                             "const": OVERLAP_EDGES},
        "balance_reference": {"const": .1}}),
    "guards": obj({"min_arm_n": {"const": 2}, "min_probability": {"const": .000001},
                   "max_glm_iterations": {"const": 100}, "glm_epsilon": {"const": .0000000001},
                   "separation_detection": {"const": "numerical_guards_only"}}),
    "prespecified": {"const": True}})

DEFAULT_OPTIONS = {
    "treatment": "treatment", "outcome": "outcome", "covariates": ["age", "severity", "sex"],
    "categorical": {"sex": {"levels": ["F", "M"], "reference": "F"}},
    "propensity_model": "logistic_mle", "link": "logit", "estimand": "ATT_retained_matched_treated",
    "ratio": 1, "replacement": False, "distance": "logit_ps",
    "caliper": {"width": .2, "scale": "sd_logit_ps", "sd_scope": "common_support_retained",
                "ddof": 1, "boundary": "inclusive"},
    "common_support": {"strategy": "minmax_both", "boundary": "inclusive", "refit": False},
    "ordering": {"treated": "descending_logit_ps_then_subject_id_utf8",
                 "control_tie": "subject_id_utf8_ascending", "row_order": "subject_id_utf8_ascending"},
    "inference": {"method": "paired_t", "ci_level": .95,
                  "variance": "sample_variance_of_pair_differences", "conditioning": "formed_matched_pairs"},
    "diagnostics": {"smd_denominator": "pre_support_complete_case_treated_sample_sd",
                    "indicator_sd": "bernoulli_p1mp", "standardize_binary": True,
                    "ps_overlap_edges": OVERLAP_EDGES, "balance_reference": .1},
    "guards": {"min_arm_n": 2, "min_probability": .000001, "max_glm_iterations": 100,
               "glm_epsilon": .0000000001, "separation_detection": "numerical_guards_only"},
    "prespecified": True}


def make_schema(base_schema):
    schema = copy.deepcopy(base_schema)
    schema["$id"] = INPUT_VERSION
    schema["properties"]["schema_version"] = {"const": INPUT_VERSION}
    analysis = schema["properties"]["analysis"]
    analysis["properties"].update(method_id={"const": METHOD}, spec={"type": "null"},
                                  baseline={"type": "null"}, psm=copy.deepcopy(OPTIONS))
    analysis["required"].append("psm")
    schema["properties"]["execution"]["properties"]["max_rows"]["maximum"] = MAX_ROWS
    return schema


def code_requirements(base_code):
    return set(base_code) | {"python/clinical_methods/psm_v07_contracts.py",
        "src/clinanalysis/R/psm_v07.R", "src/clinanalysis/R/clinical_psm_v07.R"}


def canonical_semantics(task):
    variables = {variable["name"]: variable for variable in task["variables"]}
    options = task["analysis"]["psm"]
    return {"subject_id": task["identity"]["subject_key"],
            "treatment_definition": variables[options["treatment"]]["concept"],
            "outcome_definition": task["outcome"]["definition"],
            "outcome_unit": variables[options["outcome"]]["unit"],
            "index_time": task["time"]["index"], "time_unit": task["time"]["unit"],
            "target_population": task["cohort"]["target_population"]}


def validate_time(task, need, stage="view_semantics"):
    timing = task["time"]
    need(timing["unit"] == "hour" and timing["timezone"] == "relative"
         and timing["boundary"] == "[start,end]" and not timing["delayed_entry"],
         "TIME_SEMANTICS_UNSUPPORTED", stage)
    need(timing["feature_cutoff"] <= timing["index"], "PSM_FEATURE_CUTOFF_AFTER_INDEX", stage)
    need(timing["outcome_window"][0] > timing["index"], "PSM_OUTCOME_WINDOW_NOT_POST_TREATMENT", stage)
    need(timing["outcome_window"][0] < timing["outcome_window"][1]
         <= timing["label_mature_at"] <= timing["analysis_as_of"], "OUTCOME_LABEL_NOT_MATURE", stage)


def validate_options(task, rows, variables, root, helpers):
    need = helpers["need"]
    stage = "method_applicability"
    analysis, identity, timing = task["analysis"], task["identity"], task["time"]
    options = analysis["psm"]
    need(analysis["method_id"] == METHOD, "METHOD_NOT_INTEGRATED", stage)
    helpers["validate_schema"](options, OPTIONS, "analysis.psm")
    need(analysis["effect_scale"] == "matched_mean_difference", "EFFECT_SCALE_MISMATCH", stage)
    need(analysis["variance"] == "paired_t" and analysis["ci_level"] == .95,
         "PSM_INFERENCE_OPTIONS_UNSUPPORTED", stage)
    need(task["missingness"] == MISSINGNESS, "MISSINGNESS_POLICY_UNSUPPORTED", stage)
    need(task["derivation"] == {"strategy": "declared_unit_conversion_only", "version": "1"},
         "DERIVATION_NOT_ENABLED", stage)
    need(task["validation"] == {"kind": "none", "overlap_status": "not_applicable",
                                "transportability": "not_evaluated"}, "PSM_VALIDATION_SCOPE_INVALID", stage)
    subject = identity["subject_key"]
    view = next(view for view in task["views"] if view["view_id"] == analysis["required_view_ids"][0])
    need(view["kind"] == "subject_wide" and identity["analysis_unit"] == "subject"
         and identity["encounter_key"] is None and identity["record_keys"] == [subject]
         and task["split"]["group_key"] == subject, "PSM_SUBJECT_VIEW_REQUIRED", stage)
    treatment, outcome, covariates = options["treatment"], options["outcome"], options["covariates"]
    need(len({subject, treatment, outcome}) == 3, "PSM_ID_TREATMENT_OUTCOME_MUST_DIFFER", stage)
    need(all(name in variables for name in [treatment, outcome] + covariates), "MODEL_FIELD_MISSING", stage)
    need(len(covariates) == len(set(covariates)), "DUPLICATE_COVARIATE", stage)
    need(not any(variables[name]["dtype"] == "id" for name in covariates), "ID_MODEL_FIELD_FORBIDDEN", stage)
    need(not set(covariates).intersection({subject, treatment, outcome}), "PSM_RESERVED_COVARIATE", stage)
    tvar, ovar = variables[treatment], variables[outcome]
    need(tvar["dtype"] == "number" and tvar["role"] == "exposure"
         and tvar["source_unit"] == tvar["unit"] == "1", "PSM_TREATMENT_FIELD_INVALID", stage)
    need(tvar["occurred_at"] == tvar["available_at"] == timing["index"],
         "PSM_TREATMENT_TIMING_INVALID", stage)
    need(task["outcome"]["type"] == "continuous" and ovar["dtype"] == "number",
         "PSM_OUTCOME_TYPE_UNSUPPORTED", stage)
    need(task["outcome"]["field"] == outcome and ovar["role"] == "outcome"
         and task["outcome"]["event"] is None and task["outcome"]["non_event"] is None
         and task["outcome"]["censoring"] == "none", "PSM_OUTCOME_CONTRACT_MISMATCH", stage)
    need(timing["index"] < ovar["occurred_at"] and ovar["available_at"] <= timing["analysis_as_of"]
         and timing["outcome_window"][0] <= ovar["occurred_at"] <= timing["outcome_window"][1],
         "OUTCOME_LABEL_NOT_MATURE", stage)
    need(all(row[treatment] is not None for row in rows), "PSM_TREATMENT_MISSING", stage)
    need(all(row[treatment] in (0, 1) for row in rows), "PSM_TREATMENT_NOT_BINARY", stage)
    need(all(row[outcome] is not None for row in rows), "PSM_OUTCOME_MISSING", stage)
    for name in covariates:
        variable = variables[name]
        need(variable["dtype"] in {"number", "category"} and variable["role"] in {"covariate", "group"},
             "PSM_COVARIATE_FIELD_INVALID", stage)
        need(variable["occurred_at"] <= variable["available_at"] <= timing["index"],
             "PSM_POST_TREATMENT_COVARIATE", stage)
    category_names = {name for name in covariates if variables[name]["dtype"] == "category"}
    need(set(options["categorical"]) == category_names, "CATEGORY_SPEC_MISMATCH", stage)
    for name, declaration in options["categorical"].items():
        need(declaration == {"levels": variables[name]["levels"], "reference": variables[name]["reference"]},
             "CATEGORY_SPEC_MISMATCH", stage)
    semantics = canonical_semantics(task)
    need(all(isinstance(semantics[key], str) and semantics[key].strip() for key in
             ("treatment_definition", "outcome_definition", "outcome_unit", "target_population")),
         "PSM_SEMANTIC_DEFINITION_REQUIRED", stage)
    complete = [row for row in rows if all(row[name] is not None for name in covariates)]
    excluded = [row for row in rows if any(row[name] is None for name in covariates)]
    flow = {"n_source_subjects": len(rows), "n_treated": sum(row[treatment] == 1 for row in rows),
            "n_control": sum(row[treatment] == 0 for row in rows),
            "n_covariate_complete": len(complete),
            "n_complete_treated": sum(row[treatment] == 1 for row in complete),
            "n_complete_control": sum(row[treatment] == 0 for row in complete),
            "n_excluded_missing_covariates": len(excluded),
            "n_excluded_missing_treated": sum(row[treatment] == 1 for row in excluded),
            "n_excluded_missing_control": sum(row[treatment] == 0 for row in excluded),
            "missing_by_covariate": {name: sum(row[name] is None for row in rows) for name in covariates},
            "missing_covariates_by_arm": {
                label: {name: sum(row[name] is None for row in rows if row[treatment] == code)
                        for name in covariates} for label, code in (("treated", 1), ("control", 0))},
            "exclusion_basis": "propensity_covariates_only", "outcome_used_for_propensity_or_matching": False,
            "input_inference_unit": "subject", "variance_unit": "matched_pair"}
    return flow, semantics
