"""Write explicit v03 method metadata; validation promotion is a separate step.

This generator neither changes the production/runtime lock nor executes models.
It starts every method at integration_pending until final receipts are bound.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREDICTION_VERSIONS = {
    "prediction.binary.ridge": "9ab7b3fff4690d2d3c4125b647a6a797ba87aa66af1a154da108e83fcbe2abf1",
    "prediction.continuous.nonnegative.ridge": "8bfd5077c1a49c40f8b1c1f80d35658da2e74c9eba8cbfbdbd5beb075cec5def",
}
PLAN_OPTIONS = {
    "max_prespecified_models": 6,
    "roles": ["primary", "adjustment", "sensitivity"],
    "primary_model": "exactly_one_first",
    "model_selection": "none",
    "multiplicity": "unadjusted_prespecified",
    "ci_level": 0.95,
    "sample_strategies": ["per_model_complete_case", "common_complete_case"],
    "per_model_complete_case_order": ["prespecified_filter", "model_complete_cases"],
    "common_complete_case_order": ["union_model_fields_complete_cases", "prespecified_filter"],
    "common_union_fields": "all model outcomes, exposures, covariates and subgroup fields; filter-only fields excluded",
    "filter_missingness": "missing filter-only values excluded at filter step and counted separately",
    "same_sample_claim": "common eligibility does not imply equal samples after different sensitivity filters",
    "sensitivity": {
        "filters": ["eq", "ne", "lt", "le", "gt", "ge", "in"],
        "filter_roles": ["exposure", "covariate", "group"],
        "filters_only_in": "sensitivity models",
        "nested_legacy_sensitivity": "unsupported",
        "per_model_covariates": "explicit and prespecified",
        "flow": "source/common/filter/complete-case counts and exact blocked reasons",
    },
    "subgroup": {
        "moderator": "declared categorical levels and reference",
        "exposure": "numeric linear exposure only",
        "effect": "within-level exposure slope contrast from one pooled interaction model",
        "heterogeneity": "joint interaction Wald test, not comparison of within-level P values",
        "minimum_group_n": "explicit integer at least 5; engineering gate, not sufficient-sample guarantee",
        "no_events_or_nonevents": "exact model block with preserved group counts",
        "separate_subgroup_fits": False,
    },
    "rcs": {
        "basis": "existing restricted cubic spline with linear tails",
        "knots": "3 to 7 finite strictly increasing prespecified values",
        "grid": "3 to 101 finite strictly increasing prespecified values",
        "reference": "explicit; within declared increasing domain",
        "support": "knots and declared domain within actual model complete-case exposure support; grid inside domain",
        "contrast": "exposure value versus fixed reference; full model covariance",
        "tests": ["overall exposure joint Wald", "nonlinear terms joint Wald"],
        "confidence_intervals": "pointwise 95%; no simultaneous-band claim",
        "knot_or_reference_selection": "none; no outcome/significance-driven search",
        "extrapolation": "refused",
    },
    "causal_interpretation": False,
    "automatic_fallback": False,
}


def build_capabilities(lock):
    if lock.get("core_version") != "0.3.0-candidate1":
        raise ValueError("V03_RUNTIME_LOCK_REQUIRED")
    if lock.get("prediction_provider_versions") != PREDICTION_VERSIONS:
        raise ValueError("FROZEN_PREDICTION_PROVIDER_VERSION_DRIFT")
    if not isinstance(lock.get("association_plan_provider_version"), str) or len(lock["association_plan_provider_version"]) != 64:
        raise ValueError("ASSOCIATION_PLAN_PROVIDER_VERSION_REQUIRED")
    definitions = [
        ("baseline.table1", "clinanalysis.table1", "src/clinanalysis/R/table1.R",
         {"categorical_denominator": ["nonmissing", "all"], "summary": ["mean_sd", "median_iqr"]}),
        ("association.linear", "clinical_methods.association", "python/clinical_methods/association.py",
         {"model": "linear", "covariance": "HC3", "missing": "complete_case", "ci_level": 0.95}),
        ("association.logistic", "clinical_methods.association", "python/clinical_methods/association.py",
         {"model": "logistic", "covariance": "model", "missing": "complete_case", "ci_level": 0.95}),
        ("prediction.binary.ridge", "clinical_methods.prediction.binary", "python/clinical_methods/prediction.py",
         {"operations": ["train", "evaluate", "infer"], "split": ["random", "group", "temporal"],
          "preprocessing": "training_fold_only", "unknown_categories": "reject",
          "thresholds": "prespecified_and_frozen", "algorithm": "fixed_Ridge_Logistic"}),
        ("prediction.continuous.nonnegative.ridge", "clinical_methods.prediction.continuous",
         "python/clinical_methods/continuous_ridge/prediction_engine.py",
         {"operations": ["train", "evaluate", "infer"], "split": ["group"],
          "target_policy": {"domain": "nonnegative", "transform": "identity", "inverse_transform": "identity",
                            "output_policy": "clip_lower_zero", "lower_bound": 0},
          "preprocessing": "training_fold_only", "unknown_categories": "reject", "algorithm": "fixed_Ridge",
          "inner_CV_minimums": {"train_subjects": 100, "validation_subjects": 30}}),
    ]
    for family, variance in (("linear", "HC3"), ("logistic", "model")):
        options = copy.deepcopy(PLAN_OPTIONS)
        options.update(model=family, covariance=variance)
        options["rcs"]["effect_scale"] = "mean_difference" if family == "linear" else "odds_ratio"
        options["rcs"]["standard_error_scale"] = "outcome_units" if family == "linear" else "log_odds"
        options["rcs"]["interval_method"] = "Wald t using full HC3 covariance" if family == "linear" else "Wald normal on log odds contrast, exponentiated"
        definitions.append(("association."+family+".plan", "clinical_methods.association.plan",
                            "python/clinical_methods/association.py", options))
    methods = []
    for method, provider, file, options in definitions:
        prediction, plan = method.startswith("prediction."), method.endswith(".plan")
        version = (lock["prediction_provider_versions"][method] if prediction else
                   lock["association_plan_provider_version"] if plan else lock["code_hashes"][file])
        unsupported = ["real-data execution", "unreconciled repeated subjects", "joins without reconstructed evidence",
                       "unselected covariance or algorithm", "unknown categories", "undeclared units or future fields",
                       "unknown or non-none weights", "causal claims"]
        if plan:
            unsupported += ["RCS with subgroup interaction", "categorical-exposure subgroup contrasts",
                            "nested legacy sensitivity requests", "data-driven model/knots/reference selection",
                            "simultaneous RCS confidence bands", "absolute RCS outcome risk predictions"]
        methods.append({"method_id": method, "method_version": "1.0.0-candidate1", "provider_id": provider,
            "provider_version": version, "provider_code_path": file,
            "provider_version_scope": "composite_adapter_and_fixed_numerical_sources" if prediction else
                "composite_association_source_and_plan_bridge" if plan else "numerical_source_file",
            "input_schema": "clinical-study-input@"+("0.2.0-candidate1" if prediction else "0.3.0-candidate1" if plan else "0.1.0-candidate1"),
            "result_schema": "clinical-analysis-result@0.3.0-candidate1",
            "supported_view_kinds": ["subject_wide"] if prediction else ["subject_wide", "encounter_wide"],
            "supported_designs": ["iid"], "supported_weights": ["none"],
            "required_fields": ["explicit character subject/record keys", "declared units/coding/timing/missingness",
                                "bound source/plan/code", "explicit denominator and method scale"],
            "supported_options": options, "unsupported_conditions": unsupported,
            "runtime_requirements": {"core_R": lock["versions"],
                "python": lock["prediction_python_versions"] if prediction else
                          {"python": lock["python_versions"]["python"]} if method == "baseline.table1" else lock["python_versions"]},
            "private_outputs": "models, transforms, raw numerical records and any individual predictions remain local private artifacts",
            "validation_evidence": [], "integration_status": "integration_pending",
            "scope": "SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE", "test_only": True,
            "scientific_review": "pending", "export_status": "local_only"})
    return {"schema_version": "clinical-method-capabilities@0.3.0-candidate1", "core_version": lock["core_version"],
        "registration_owner": "clinanalysis::register_clinical_common", "single_task_entry": "clinanalysis::run_analysis_task",
        "methods": methods,
        "unregistered_capabilities": [{"method_group": name, "integration_status": "integration_pending"} for name in
            ["RCS_with_subgroup_interaction", "categorical_exposure_subgroup_contrasts", "signed_continuous_prediction",
             "LASSO/SHAP/Cox_prediction", "survival", "survey", "longitudinal", "causal", "trajectory/clustering",
             "postindex_outcome_descriptive_baseline_roles"]],
        "publication_status": "NOT_RELEASED", "real_database_adapters": "NOT_VALIDATED",
        "clinical_scientific_acceptance": "NOT_PERFORMED"}


def main():
    lock = json.loads((ROOT/"runtime-lock.json").read_text(encoding="utf-8"))
    value = build_capabilities(lock)
    (ROOT/"method-capabilities.json").write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    print("METHOD_CAPABILITIES_WRITTEN", len(value["methods"]))


if __name__ == "__main__":
    main()
