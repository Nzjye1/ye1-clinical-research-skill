.onLoad <- function(libname, pkgname) {
  register_analysis_plugin("modified_poisson", run_modified_poisson)
  register_analysis_plugin("cause_specific_cox", run_cause_specific_cox)
  register_analysis_plugin("generic_regression", run_generic_regression)
  register_analysis_plugin("survival_analysis", run_survival_analysis)
  register_analysis_plugin("longitudinal_model", run_longitudinal_model)
  register_analysis_plugin("causal_comparison", run_causal_comparison)
  register_analysis_plugin("prediction_validation", run_prediction_validation)
  register_analysis_plugin("temporal_logistic_prediction", run_temporal_logistic_prediction)
  register_analysis_plugin("temporal_fine_gray_prediction", run_temporal_fine_gray_prediction)
  register_analysis_plugin("categorical_logistic_g_computation", run_categorical_logistic_g_computation)
  register_task_contract(
    "categorical-transfer-gcomp-task@1.0.0",
    validate_categorical_gcomp_task
  )
  register_task_contract(
    "categorical-transfer-gcomp-task@1.1.0",
    validate_categorical_gcomp_task
  )
  register_task_contract(
    "categorical-transfer-gcomp-task@1.2.0",
    validate_categorical_gcomp_task
  )
  register_result_contract(
    "categorical-gcomp-cohort-flow@1.0.0",
    validate_categorical_gcomp_cohort
  )
  register_result_contract(
    "categorical-gcomp-unadjusted-source-risks@1.0.0",
    validate_categorical_gcomp_unadjusted
  )
  register_result_contract(
    "categorical-gcomp-adjusted-risks@1.0.0",
    validate_categorical_gcomp_adjusted
  )
  register_result_contract(
    "categorical-gcomp-first-event-composition@1.0.0",
    validate_categorical_gcomp_first_event
  )
  register_result_contract(
    "categorical-gcomp-credibility-results@1.0.0",
    validate_categorical_gcomp_credibility
  )
  register_result_contract(
    "categorical-gcomp-diagnostics@1.0.0",
    validate_categorical_gcomp_diagnostics
  )
  register_result_contract(
    "categorical-gcomp-result-bundle@1.0.0",
    validate_categorical_gcomp_bundle
  )
  register_result_contract(
    "categorical-gcomp-result-bundle@1.1.0",
    validate_categorical_gcomp_bundle
  )
  register_result_contract(
    "categorical-gcomp-formal-execution-binding@1.0.0",
    validate_categorical_gcomp_formal_execution_binding
  )
  register_result_contract(
    "categorical-gcomp-failure-diagnostic@1.0.0",
    validate_categorical_gcomp_failure
  )
  register_result_contract(
    "full-article-tfl-bundle@1.0.0",
    validate_categorical_gcomp_full_output_manifest
  )
  register_result_contract(
    "formal-temporal-fine-gray-result@1.1.0",
    validate_formal_temporal_fine_gray_result
  )
  register_result_contract(
    "formal-temporal-fine-gray-result@2.0.0",
    validate_formal_temporal_fine_gray_result
  )
  register_result_contract(
    "formal-temporal-fine-gray-output-manifest@1.1.0",
    validate_formal_temporal_fine_gray_output_manifest
  )
  register_result_contract(
    "formal-temporal-fine-gray-failure-diagnostic@1.0.0",
    validate_formal_temporal_fine_gray_failure_diagnostic
  )
  register_result_contract(
    "formal-temporal-fine-gray-failure-diagnostic@1.1.0",
    validate_formal_temporal_fine_gray_failure_diagnostic
  )
  register_result_contract(
    "formal-temporal-fine-gray-failure-diagnostic@1.2.0",
    validate_formal_temporal_fine_gray_failure_diagnostic
  )
  register_result_contract(
    "formal-temporal-fine-gray-failure-diagnostic@1.3.0",
    validate_formal_temporal_fine_gray_failure_diagnostic
  )
  register_result_contract(
    "formal-runner-startup-diagnostic@1.0.0",
    validate_formal_runner_startup_diagnostic
  )
}

utils::globalVariables(c(
  "exposure_value", "risk", "ci_low", "ci_high", "time", "incidence", "group", "event",
  "term", "estimate", "n_censor", "n_risk", "survival", "sensitivity", "one_minus_specificity",
  "predicted", "observed", "threshold", "net_benefit", "strategy", "sample", "smd", "covariate",
  ".clin_id", "fgwt", "plot_time", "auc", "label", "model", "x", "y", "box_label",
  "xend", "yend", "excluded", "level", "proportion", "n", "level_display", "analysis",
  "reference", "analysis_id", "absolute_change", "threshold_assessment", "low", "high",
  "step_id", "n_entered", "n_excluded", "n_remaining", "exclusion_reason", "step_order"
))
