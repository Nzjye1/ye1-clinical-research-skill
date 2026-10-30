"""Module-only schema fragments. Shared contract/schema registration is untouched."""
from __future__ import annotations
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parents[1] / "integration" / "core"
S = {"type": "string", "minLength": 1}
N = {"type": "number"}
I = {"type": "integer", "minimum": 0}
B = {"type": "boolean"}
NULL = {"type": "null"}
HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
METHODS = ["mediation.linear.binary_exposure", "causal.psm.att.binary", "causal.psm.matched.survival"]


def obj(props):
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(item, minimum=0, maximum=None):
    out = {"type": "array", "items": item, "minItems": minimum}
    if maximum is not None:
        out["maxItems"] = maximum
    return out


def nullable(item):
    return {"anyOf": [item, NULL]}


def choice(*values):
    return {"enum": list(values)}


def constant(value):
    return {"const": value}


def spec_branch(method):
    med, surv = method == METHODS[0], method == METHODS[2]
    fields = obj({"subject": S, "exposure": S, "outcome": NULL if surv else S,
                  "mediator": S if med else NULL, "time": S if surv else NULL, "event": S if surv else NULL})
    sem = obj({"population": S, "exposure_definition": S, "outcome_definition": S, "outcome_unit": S,
               "time_unit": choice("hour", "day", "year"), "exposure_time": N, "covariate_latest_time": N,
               "mediator_time": N if med else NULL, "outcome_time": NULL if surv else N,
               "design": constant("iid_subjects"), "weights": constant("none"), "causal_assumptions_verified": constant(False),
               "treatment_induced_confounder": constant(False),
               "censoring": constant("right_independent_conditional_on_treatment" if surv else "none"),
               "delayed_entry": constant(False), "competing_events": constant(False), "recurrent_events": constant(False),
               "time_varying": constant(False), "binary_horizon_complete": constant(True) if method == METHODS[1] else NULL})
    if med:
        options = obj({"exposure_type": constant("binary"), "mediator_type": constant("continuous"), "outcome_type": constant("continuous"),
                       "interaction": B, "bootstrap_replicates": {"type": "integer", "minimum": 200, "maximum": 5000},
                       "seed": {"type": "integer", "minimum": 0, "maximum": 2147483646}, "ci_level": constant(.95),
                       "missingness": constant("complete_case_joint_models"), "estimand": constant("complete_case_empirical_natural_contrasts")})
    else:
        options = obj({"outcome_type": constant("survival" if surv else "binary"),
                       "caliper_width": {"type": "number", "minimum": 0, "maximum": 2},
                       "categorical": {"type": "object", "additionalProperties": obj({"levels": arr(S, 2), "reference": S})},
                       "ratio": constant(1), "replacement": constant(False),
                       "estimand": constant("matched_population_working_marginal_hazard_ratio" if surv else "ATT_retained_matched_treated_risk_difference"),
                       "inference": constant("pooled_cox_pair_cluster_efron" if surv else "paired_rd_exact_discordance"),
                       "ci_level": constant(.95), "missingness": constant("complete_case_covariates_endpoint_required"),
                       "risk_times": arr({"type": "number", "minimum": 0}, 2, 12) if surv else arr(N, 0, 0)})
    return obj({"schema_version": constant("mediation-matching-input@1.0.0"), "method_id": constant(method), "fields": fields,
                "covariates": arr(S, 1, 8), "semantics": sem, "options": options,
                "execution": obj({"test_only": constant(True), "data_origin": constant("synthetic")})})


def input_schema():
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "mediation-matching-input@1.0.0",
            "description": "Module spec only; row-level, chronology, rank and causal assumption checks remain mandatory.",
            "anyOf": [spec_branch(m) for m in METHODS]}


def result_schema():
    legacy = json.loads((BASE / "schemas/result.schema.json").read_text(encoding="utf-8-sig"))
    psm = copy.deepcopy(legacy["anyOf"][0]["properties"]["psm"]["anyOf"][0]["properties"])
    # The inherited PSM result fragment historically encoded the 200-row fixture
    # guard in its counters. Keep method/shape/probability constraints intact and
    # align only those named counters with the finite matching profile ceiling.
    matching_ceiling = json.loads((BASE / "config/resource-budget-profiles.json").read_text(encoding="utf-8"))["profiles"]["pair_matching"]["ceiling_rows"]
    row_counts = {
        "n_input", "n_input_treated", "n_input_control", "n_excluded_missing_covariates",
        "n_excluded_missing_treated", "n_excluded_missing_control", "n_complete_case",
        "n_complete_case_treated", "n_complete_case_control", "n_support_retained",
        "n_support_treated", "n_support_control", "n_discarded_support_treated",
        "n_discarded_support_control", "n_unmatched_support_treated", "n_unmatched_support_control",
        "n_matched_subjects", "n_missing", "n_missing_treated", "n_missing_control",
        "n_retained_treated", "n_retained_control", "n_before_treated", "n_before_control",
        "n_after_treated", "n_after_control", "n", "denominator",
    }

    def update_count_bounds(value):
        if isinstance(value, dict):
            for name, definition in value.get("properties", {}).items():
                dtype = definition.get("type")
                integer = dtype == "integer" or isinstance(dtype, list) and "integer" in dtype
                # Small conditional bounds encode support states, not capacity.
                if integer and definition.get("maximum", 0) > 2:
                    if name in row_counts:
                        definition["maximum"] = matching_ceiling
                    elif name == "n_matched_pairs":
                        definition["maximum"] = matching_ceiling // 2
            for item in value.values():
                update_count_bounds(item)
        elif isinstance(value, list):
            for item in value:
                update_count_bounds(item)

    for section in ("flow", "support", "balance", "overlap"):
        update_count_bounds(psm[section])
    for name in ("balance", "overlap"):
        item = psm[name]["items"]
        item["properties"].pop("result_id", None)
        item["required"] = [k for k in item["required"] if k != "result_id"]
    ef = obj({"effect_id": S, "scale": choice("outcome_unit_mean_difference", "risk_difference", "odds_ratio", "hazard_ratio"),
              "standard_error_scale": choice("log_hazard_ratio", "not_estimated_exact_interval", "risk_difference", "outcome_units"),
              "estimand": S, "definition": S, "n_semantics": choice("complete_case_subjects", "formed_matched_pairs"),
              "estimate": nullable(N), "standard_error": nullable(N), "ci_lower": nullable(N), "ci_upper": nullable(N),
              "ci_level": constant(.95), "ci_method": nullable(S), "p_value": nullable({"type": "number", "minimum": 0, "maximum": 1}),
              "test_method": nullable(S), "df": nullable(I), "n": I, "status": choice("completed", "partial", "unavailable"),
              "reason_code": nullable(S), "lower_boundary": nullable(choice("zero")), "upper_boundary": nullable(choice("positive_infinity")),
              "result_id": S})
    artifact = obj({"artifact_id": S, "kind": choice("table", "figure"), "source_result_ids": arr(S, 1), "sha256": HASH,
                    "relative_path": S, "caption": S, "test_only": constant(True), "scientific_review": constant("pending"),
                    "export_status": constant("local_only")})
    models = obj({"rank": I, "df": I, "rss": N, "condition": N})
    med_diag = obj({"engine": constant("stats::lm.fit"), "standardization": constant("empirical_complete_case_covariates"),
                    "bootstrap": obj({"requested": I, "successful": I, "failed": I, "min_success_required": I,
                                      "failures": {"type": "object", "additionalProperties": I}, "seed": I, "rng": S,
                                      "resampling_unit": constant("iid_subject"), "both_models_same_resample": constant(True),
                                      "refit_both_models": constant(True), "target_covariates": constant("resampled_empirical_distribution"),
                                      "confidence_method": constant("percentile_type7")}),
                    "models": obj({"mediator": models, "outcome": models}), "decomposition_error": N,
                    "sensitivity_analysis": constant("not_implemented"), "causal_identification": constant("not_verified")})
    binary_diag = obj({**{n: I for n in ("n_pairs", "treated_events", "control_events", "both_events", "neither_events", "treated_only_events", "control_only_events", "discordant_pairs")},
                       "rd_variance": nullable(N), "exact_test_null": S, "conditional_or_not_marginal_or": constant(True)})
    risk = obj({"time": N, "arm": choice("treated", "control"), "at_risk": I, "events_before": I, "censors_before": I,
                "denominator": I, "support_status": choice("observed", "no_followup_remaining")})
    cox_diag = obj({"engine": constant("survival::coxph"), "ties": constant("efron"), "timefix": constant(False), "risk_set": S,
                   "tie_order": S, "stratified_by_pair": constant(False), "cluster_unit": constant("matched_pair"),
                   **{n: I for n in ("events", "censored", "n_pairs", "n_subjects")},
                   **{n: nullable(N) for n in ("log_hazard_ratio", "robust_log_se", "naive_log_se")},
                   "ph_assumption": constant("not_verified"), "risk_table": arr(risk), "event_counts_by_arm": obj({"treated": I, "control": I}),
                   "standard_error_scale": constant("log_hazard_ratio"), "iterations": I})
    cox_diag["required"].remove("iterations")
    branches = []
    for method in METHODS:
        sp = spec_branch(method)["properties"]
        if method == METHODS[0]:
            counts = obj({**{n: I for n in ("source_subjects", "complete_case_subjects", "excluded_missing", "source_treated", "source_control", "model_treated", "model_control")},
                          "missing_by_field": {"type": "object", "additionalProperties": I}})
            diag = med_diag
        else:
            counts = psm["flow"]
            diag = obj({"propensity": psm["propensity"], "support": psm["support"], "balance": psm["balance"], "overlap": psm["overlap"],
                        "matching_owner_sha256": HASH, "outcomes_used_in_design": constant(False), "matching_inference_conditioning": constant("formed_matched_pairs"),
                        "ps_estimation_uncertainty_included": constant(False), "match_selection_uncertainty_included": constant(False),
                        "outcome": binary_diag if method == METHODS[1] else cox_diag})
            diag["required"].remove("outcome")
        branches.append(obj({"schema_version": constant("mediation-matching-result@1.0.0"), "method_id": constant(method),
                             "status": choice("completed", "partial", "unavailable"), "reason_code": nullable(S), "test_only": constant(True),
                             "scientific_review": constant("pending"), "export_status": constant("local_only"), "causal_assumptions_verified": constant(False),
                             "semantics": nullable(sp["semantics"]), "options": nullable(sp["options"]),
                             "counts": {"anyOf": [obj({}), counts]}, "diagnostics": {"anyOf": [obj({}), diag]},
                             "effects": arr(ef), "warnings": arr(S), "limitations": arr(S), "result_id": S,
                             "binding": obj({"source_id": S, "source_sha256": HASH, "adapter_manifest_sha256": HASH, "python_adapter_sha256": HASH,
                                             "input_sha256": HASH, "spec_sha256": HASH, "provider_sha256": HASH, "adapter_sha256": HASH,
                                             "R": S, "stats": S, "survival": nullable(S)}), "artifacts": arr(artifact)}))
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "mediation-matching-result@1.0.0", "anyOf": branches}


def module_schemas():
    nullable_num = nullable(N)
    row = obj({"subject_id": S, "exposure": N, "mediator": nullable_num, "outcome": nullable_num,
               "time": nullable_num, "event": nullable_num,
               "covariates": arr({"anyOf": [N, S, NULL]}, 1, 8)})
    structure = obj({"grain": constant("subject_wide"), "subject_key": S, "record_keys": arr(S, 1, 1),
                     "cluster_key": NULL, "weights": constant("none"),
                     "missingness": choice("complete_case_joint_models", "complete_case_covariates_endpoint_required"),
                     "time_origin": N, "time_unit": choice("day", "hour", "year"), "analysis_as_of": N})
    variable = obj({"name": S, "dtype": choice("id", "number", "category"),
                    "role": choice("subject", "exposure", "mediator", "outcome", "time", "event", "covariate"),
                    "unit": S, "time_role": choice("identifier", "baseline", "exposure", "mediator", "outcome", "followup_duration", "event_at_followup"),
                    "measured_at": nullable_num, "available_at": nullable_num})
    # Broad transport ceiling; the method profile and explicit budget are checked
    # before normalization/dispatch, including pair-comparison work for matching.
    payload = obj({"spec": input_schema(), "structure": structure, "variables": arr(variable, 4, 14), "rows": arr(row, 1, 100000)})
    diag = obj({"module_id": constant("mediation_matching"), "stage": choice("request_contract", "payload_contract", "analysis"),
                "numerical_owner": constant("R/provider.R"), "status": choice("completed", "partial", "unavailable"),
                "causal_assumptions_verified": constant(False)})
    public = copy.deepcopy(result_schema())
    public.pop("$id", None)
    for branch in public["anyOf"]:
        for key in ("schema_version", "binding", "result_id", "artifacts"):
            del branch["properties"][key]
            branch["required"].remove(key)
        ef = branch["properties"]["effects"]["items"]
        ef["properties"].pop("result_id", None)
        ef["required"] = [k for k in ef["required"] if k != "result_id"]
    private = obj({"format": constant("R_serialize_v3_base64"), "media_type": constant("application/x-r-serialized"), "blob": S})
    return {"payload.schema.json": payload, "diagnostics.schema.json": diag,
            "public_record.schema.json": public, "private_record.schema.json": private}


if __name__ == "__main__":
    destination = ROOT / "contracts"
    destination.mkdir(exist_ok=True)
    values = {"input.fragment.schema.json": input_schema(), "result.fragment.schema.json": result_schema(), **module_schemas()}
    for name, value in values.items():
        (destination / name).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    print("MODULE_SCHEMA_FRAGMENTS_WRITTEN")
