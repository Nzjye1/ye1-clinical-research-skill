.formal_temporal_fg_result_version <- "formal-temporal-fine-gray-result@1.1.0"
.formal_temporal_fg_result_v4_version <- "formal-temporal-fine-gray-result@2.0.0"
.formal_temporal_fg_manifest_version <- "formal-temporal-fine-gray-output-manifest@1.1.0"

formal_fg_result_metric_ids <- function(contract = formal_temporal_fg_contract()) {
  setdiff(contract$metric_ids, "FLEXIBLE_CALIBRATION_CURVE")
}

formal_fg_primary_term_ids <- function(contract = formal_temporal_fg_contract()) {
  legacy <- c(
    "age_linear", "age_rcs", "female", "ami_type_STEMI",
    "ami_type_OTHER_UNSPECIFIED", "admission_context", "dementia_history",
    "alcohol_use_history", "early_cardiac_arrest", "heart_rate_max_0_12h",
    "systolic_bp_min_0_12h", "respiratory_rate_max_0_12h",
    "temperature_max_0_12h", "spo2_min_0_12h", "gcs_min_0_12h",
    "rass_min_0_12h", "lactate_max_0_12h", "ph_min_0_12h",
    "glucose_max_0_12h", "sodium_latest_0_12h", "creatinine_max_0_12h",
    "bun_max_0_12h", "wbc_max_0_12h", "mechanical_ventilation_0_12h",
    "vasoactive_support_0_12h", "sedative_exposure_0_12h",
    "opioid_exposure_0_12h"
  )
  if (identical(contract$parameter_df, 25L)) {
    return(setdiff(
      legacy,
      c("ami_type_STEMI", "ami_type_OTHER_UNSPECIFIED")
    ))
  }
  legacy
}

formal_fg_result_numeric <- function(x, lower = -Inf, upper = Inf) {
  is.numeric(x) && length(x) == 1L && is.finite(x) && x >= lower && x <= upper
}

formal_fg_result_integer <- function(x, lower = 0) {
  formal_fg_result_numeric(x, lower = lower) && x == floor(x)
}

formal_fg_result_string <- function(x) {
  is.character(x) && length(x) == 1L && nzchar(x)
}

formal_fg_result_exact_object <- function(x, fields, label) {
  if (!is.list(x) || is.null(names(x))) return(sprintf("%s must be an object", label))
  c(
    sprintf("%s missing field: %s", label, setdiff(fields, names(x))),
    sprintf("%s unknown field: %s", label, setdiff(names(x), fields))
  )
}

formal_fg_result_forbidden_payload <- function(x, trail = "result") {
  problems <- character()
  if (is.character(x)) {
    bad <- grepl("[/\\\\]", x) |
      grepl("analysis[-_]?ready\\.csv|mimic", x, ignore.case = TRUE)
    if (any(bad)) problems <- c(problems, sprintf("Physical path or real-data reference is forbidden at %s", trail))
    return(problems)
  }
  if (!is.list(x)) return(problems)
  forbidden <- c(
    "path", "file", "directory", "payload", "patient_payload", "patient_rows",
    "row_level_data", "records", "patient_id", "record_id", "subject_id",
    "stay_id", "hadm_id", "timestamps", "timestamp_list"
  )
  bad <- intersect(names(x), forbidden)
  if (length(bad)) problems <- c(problems, sprintf("Forbidden result field at %s: %s", trail, bad))
  for (name in names(x)) {
    problems <- c(problems, formal_fg_result_forbidden_payload(x[[name]], paste0(trail, ".", name)))
  }
  problems
}

formal_fg_result_check_rows <- function(rows, n, fields, label) {
  problems <- character()
  if (!is.list(rows) || length(rows) != n) {
    return(sprintf("%s must contain exactly %d aggregate rows", label, n))
  }
  for (i in seq_along(rows)) {
    problems <- c(problems, formal_fg_result_exact_object(rows[[i]], fields, sprintf("%s[%d]", label, i)))
  }
  problems
}

formal_fg_result_check_metrics <- function(
  x,
  label,
  contract = formal_temporal_fg_contract()
) {
  ids <- formal_fg_result_metric_ids(contract)
  problems <- formal_fg_result_exact_object(x, ids, label)
  if (is.list(x)) {
    for (id in intersect(ids, names(x))) {
      if (!formal_fg_result_numeric(x[[id]])) problems <- c(problems, sprintf("%s.%s must be finite", label, id))
    }
  }
  problems
}

formal_fg_result_checksum <- function(result) {
  core <- result
  core$structured_result_sha256 <- NULL
  digest::digest(
    jsonlite::toJSON(core, auto_unbox = TRUE, null = "null", digits = NA),
    algo = "sha256", serialize = FALSE
  )
}

#' Validate the strict aggregate FORMAL temporal Fine-Gray result contract
#'
#' This validator is registered at package load and is mandatory before any
#' structured result or bundle is written.
#'
#' @param result Aggregate structured result.
#' @return Invisibly returns TRUE or raises a contract error.
#' @export
validate_formal_temporal_fine_gray_result <- function(result) {
  contract <- if (identical(
    result$schema_version,
    .formal_temporal_fg_result_v4_version
  )) {
    formal_temporal_fg_contract_v4()
  } else {
    formal_temporal_fg_contract()
  }
  top <- c(
    "schema_version", "analysis_id", "candidate_id", "execution_mode", "status",
    "aggregate_only", "patient_level_payload", "physical_paths_in_result",
    "checksum_scope", "binding", "counts", "model", "imputation",
    "internal_validation", "temporal_validation", "performance",
    "calibration_gate", "decision_curve", "clinical_utility_claim_allowed",
    "sensitivities", "expected_output_ids", "prohibited_actions_observed",
    "structured_result_sha256"
  )
  problems <- formal_fg_result_exact_object(result, top, "result")
  if (!is.list(result)) stop(contract_error(problems))
  problems <- c(problems, formal_fg_result_forbidden_payload(result))
  if (!(result$schema_version %in% c(
    .formal_temporal_fg_result_version,
    .formal_temporal_fg_result_v4_version
  ))) problems <- c(problems, "Unsupported FORMAL temporal Fine-Gray result schema_version")
  if (!formal_fg_result_string(result$analysis_id)) problems <- c(problems, "analysis_id must be one non-empty string")
  if (!identical(result$candidate_id, contract$candidate_id)) problems <- c(problems, "candidate_id mismatch")
  if (!identical(result$execution_mode, "FORMAL") && !identical(result$execution_mode, "SYNTHETIC_TEST")) problems <- c(problems, "execution_mode must be FORMAL or SYNTHETIC_TEST")
  expected_status <- if (identical(result$execution_mode, "FORMAL")) "COMPLETE" else "SYNTHETIC_CAPABILITY_VERIFIED"
  if (!identical(result$status, expected_status)) problems <- c(problems, "status is inconsistent with execution_mode")
  if (!identical(result$aggregate_only, TRUE) || !identical(result$patient_level_payload, FALSE) || !identical(result$physical_paths_in_result, FALSE)) problems <- c(problems, "result must be aggregate-only, patient-payload-free, and path-free")
  if (!identical(result$checksum_scope, "CANONICAL_STRUCTURED_RESULT_EXCLUDING_STRUCTURED_RESULT_SHA256_FIELD")) problems <- c(problems, "checksum_scope drift")

  binding_fields <- c("sap_id", "sap_sha256", "dataset_id", "dataset_sha256")
  problems <- c(problems, formal_fg_result_exact_object(result$binding, binding_fields, "result.binding"))
  if (is.list(result$binding)) {
    if (!formal_fg_result_string(result$binding$sap_id) || !formal_fg_result_string(result$binding$dataset_id)) problems <- c(problems, "binding IDs must be non-empty strings")
    if (!formal_fg_sha256(result$binding$sap_sha256) || !formal_fg_sha256(result$binding$dataset_sha256)) problems <- c(problems, "binding checksums must be lowercase SHA-256")
    if (identical(
      result$schema_version,
      .formal_temporal_fg_result_v4_version
    ) && (
      !identical(result$binding$sap_id, contract$sap_id) ||
      !identical(result$binding$sap_sha256, contract$sap_sha256) ||
      !identical(result$binding$dataset_id, contract$dataset_id) ||
      !identical(result$binding$dataset_sha256, contract$dataset_sha256)
    )) problems <- c(
      problems,
      "V4 result requires exact frozen SAP V3 and immutable dataset V2 bindings"
    )
  }

  count_fields <- c("input_n", "development_n", "validation_n", "development_events", "validation_events", "development_competing_events", "validation_competing_events", "observation")
  problems <- c(problems, formal_fg_result_exact_object(result$counts, count_fields, "result.counts"))
  observation_fields <- c("total_n", "technically_observed_n", "uta_only_n", "other_unobserved_n", "outcome_unobserved_n", "right_censored_at_last_known_n", "outcome_unobserved_recoded_negative_n", "reconciled")
  if (is.list(result$counts)) {
    for (field in setdiff(count_fields, "observation")) if (!formal_fg_result_integer(result$counts[[field]])) problems <- c(problems, sprintf("result.counts.%s must be a nonnegative integer", field))
    problems <- c(problems, formal_fg_result_exact_object(result$counts$observation, observation_fields, "result.counts.observation"))
    if (formal_fg_result_integer(result$counts$development_n) && formal_fg_result_integer(result$counts$validation_n) && formal_fg_result_integer(result$counts$input_n) && result$counts$development_n + result$counts$validation_n != result$counts$input_n) problems <- c(problems, "partition counts do not reconcile")
  }
  observation <- if (is.list(result$counts)) result$counts$observation else NULL
  if (is.list(observation)) {
    for (field in setdiff(observation_fields, "reconciled")) if (!formal_fg_result_integer(observation[[field]])) problems <- c(problems, sprintf("result.counts.observation.%s must be a nonnegative integer", field))
    if (!identical(observation$reconciled, TRUE) || !identical(observation$outcome_unobserved_recoded_negative_n, 0L)) problems <- c(problems, "outcome-unobserved censoring reconciliation failed")
    if (formal_fg_result_integer(observation$uta_only_n) && formal_fg_result_integer(observation$other_unobserved_n) && formal_fg_result_integer(observation$outcome_unobserved_n) && observation$uta_only_n + observation$other_unobserved_n != observation$outcome_unobserved_n) problems <- c(problems, "UTA and other-unobserved counts do not reconcile")
    if (formal_fg_result_integer(observation$outcome_unobserved_n) && !identical(observation$outcome_unobserved_n, observation$right_censored_at_last_known_n)) problems <- c(problems, "unobserved outcomes must all be right censored at last known observation")
  }

  model_fields <- c("primary_model_id", "baseline_model_id", "parameter_df", "transformation_map_sha256", "pooled_coefficients", "baseline_pooled_coefficients", "uniform_shrinkage_factor", "uniform_shrinkage_capped_at_one", "baseline_hazard_reestimated_from", "pooled_development_baseline_subdistribution_hazard", "validation_refit", "validation_recalibration", "logistic_substitution")
  problems <- c(problems, formal_fg_result_exact_object(result$model, model_fields, "result.model"))
  if (is.list(result$model)) {
    if (!identical(result$model$primary_model_id, contract$primary_model_id) || !identical(result$model$baseline_model_id, contract$baseline_model_id)) problems <- c(problems, "frozen model IDs drifted")
    if (!identical(result$model$parameter_df, contract$parameter_df) || !identical(result$model$transformation_map_sha256, contract$transformation_map_sha256)) problems <- c(problems, "frozen model df or transformation checksum drifted")
    problems <- c(problems, formal_fg_result_check_rows(result$model$pooled_coefficients, contract$parameter_df, c("term", "estimate", "standard_error"), "result.model.pooled_coefficients"))
    problems <- c(problems, formal_fg_result_check_rows(result$model$baseline_pooled_coefficients, 3L, c("term", "estimate", "standard_error"), "result.model.baseline_pooled_coefficients"))
    if (is.list(result$model$pooled_coefficients) && length(result$model$pooled_coefficients) == contract$parameter_df) {
      terms <- vapply(result$model$pooled_coefficients, function(row) if (is.list(row) && formal_fg_result_string(row$term)) row$term else NA_character_, character(1))
      if (!identical(terms, formal_fg_primary_term_ids(contract))) problems <- c(problems, "primary coefficient terms do not match the frozen model")
    }
    if (is.list(result$model$baseline_pooled_coefficients) && length(result$model$baseline_pooled_coefficients) == 3L) {
      terms <- vapply(result$model$baseline_pooled_coefficients, function(row) if (is.list(row) && formal_fg_result_string(row$term)) row$term else NA_character_, character(1))
      if (!identical(terms, c("age_linear", "age_rcs", "female"))) problems <- c(problems, "baseline coefficient terms must be age_linear, age_rcs, female")
    }
    for (rows in list(result$model$pooled_coefficients, result$model$baseline_pooled_coefficients)) if (is.list(rows)) for (row in rows) if (is.list(row) && (!formal_fg_result_numeric(row$estimate) || !formal_fg_result_numeric(row$standard_error, 0))) problems <- c(problems, "coefficient estimates and standard errors must be finite")
    if (!formal_fg_result_numeric(result$model$uniform_shrinkage_factor, 0, 1) || !identical(result$model$uniform_shrinkage_capped_at_one, TRUE)) problems <- c(problems, "uniform shrinkage must be finite and capped at one")
    if (!identical(result$model$baseline_hazard_reestimated_from, "DEVELOPMENT_ONLY") || !formal_fg_result_numeric(result$model$pooled_development_baseline_subdistribution_hazard, 0)) problems <- c(problems, "baseline hazard must be finite and reestimated from development only")
    if (!identical(result$model$validation_refit, FALSE) || !identical(result$model$validation_recalibration, FALSE) || !identical(result$model$logistic_substitution, FALSE)) problems <- c(problems, "validation refit/recalibration and logistic substitution are forbidden")
  }

  imputation_fields <- c("engine", "m", "iterations", "seed", "development_fit_only", "validation_outcomes_used", "validation_outcome_access_count", "completed_datasets", "convergence_status", "continuous_method", "binary_method", "categorical_method")
  problems <- c(problems, formal_fg_result_exact_object(result$imputation, imputation_fields, "result.imputation"))
  if (is.list(result$imputation)) {
    expected <- list(engine = "DETERMINISTIC_DEVELOPMENT_DONOR_CHAINED_EQUATIONS", m = 40L, iterations = 20L, seed = 20260722L, development_fit_only = TRUE, validation_outcomes_used = FALSE, validation_outcome_access_count = 0L, completed_datasets = 40L, convergence_status = "COMPLETE", continuous_method = "PREDICTIVE_MEAN_MATCHING", binary_method = "LOGISTIC_REGRESSION", categorical_method = "MULTINOMIAL_LOGISTIC_REGRESSION")
    if (!identical(result$imputation, expected)) problems <- c(problems, "imputation result must remain m=40, development-learned, outcome-blind in validation, and converged")
  }

  internal_fields <- c("scope", "method", "replicates_requested", "replicates_completed", "seed", "failures", "optimism", "bootstrap_corrected_metrics", "uniform_shrinkage_factor", "baseline_hazard_reestimated_from", "verification_profile")
  problems <- c(problems, formal_fg_result_exact_object(result$internal_validation, internal_fields, "result.internal_validation"))
  if (is.list(result$internal_validation)) {
    if (!identical(result$internal_validation$scope, "DEVELOPMENT_FULL_PIPELINE") || !identical(result$internal_validation$method, "PATIENT_LEVEL_BOOTSTRAP_FULL_PIPELINE") || !identical(result$internal_validation$replicates_requested, 1000L) || !identical(result$internal_validation$replicates_completed, 1000L) || !identical(result$internal_validation$seed, 20260722L) || length(result$internal_validation$failures) != 0L || !identical(result$internal_validation$baseline_hazard_reestimated_from, "DEVELOPMENT_ONLY")) problems <- c(problems, "development full-pipeline bootstrap contract drifted")
    problems <- c(problems, formal_fg_result_check_metrics(result$internal_validation$optimism, "result.internal_validation.optimism", contract), formal_fg_result_check_metrics(result$internal_validation$bootstrap_corrected_metrics, "result.internal_validation.bootstrap_corrected_metrics", contract))
    expected_profile <- if (identical(result$execution_mode, "FORMAL")) "FULL_40_IMPUTATION_TRANSFORMATION_FIT_PIPELINE" else "SYNTHETIC_ORCHESTRATION_PLUS_SEPARATE_FULL_PIPELINE_SMOKE"
    if (!formal_fg_result_numeric(result$internal_validation$uniform_shrinkage_factor, 0, 1) || !identical(result$internal_validation$verification_profile, expected_profile)) problems <- c(problems, "invalid internal-validation shrinkage or verification profile")
  }

  temporal_fields <- c("scope", "method", "replicates_requested", "replicates_completed", "seed", "failures", "interval", "intervals", "flexible_calibration_band", "refit", "recalibrate", "verification_profile")
  problems <- c(problems, formal_fg_result_exact_object(result$temporal_validation, temporal_fields, "result.temporal_validation"))
  if (is.list(result$temporal_validation)) {
    if (!identical(result$temporal_validation$scope, "VALIDATION_ONLY_FIXED_MODEL") || !identical(result$temporal_validation$method, "VALIDATION_ONLY_FIXED_MODEL_PATIENT_BOOTSTRAP") || !identical(result$temporal_validation$replicates_requested, 2000L) || !identical(result$temporal_validation$replicates_completed, 2000L) || !identical(result$temporal_validation$seed, 20260723L) || length(result$temporal_validation$failures) != 0L || !identical(result$temporal_validation$interval, "PERCENTILE_95_CI") || !identical(result$temporal_validation$refit, FALSE) || !identical(result$temporal_validation$recalibrate, FALSE)) problems <- c(problems, "held-out fixed-model validation bootstrap contract drifted")
    problems <- c(problems, formal_fg_result_check_rows(result$temporal_validation$intervals, 8L, c("metric", "ci_low", "ci_high"), "result.temporal_validation.intervals"), formal_fg_result_check_rows(result$temporal_validation$flexible_calibration_band, 50L, c("predicted", "ci_low", "ci_high"), "result.temporal_validation.flexible_calibration_band"))
    if (is.list(result$temporal_validation$intervals) && length(result$temporal_validation$intervals) == 8L) {
      ids <- vapply(result$temporal_validation$intervals, function(row) if (is.list(row) && formal_fg_result_string(row$metric)) row$metric else NA_character_, character(1))
      if (!identical(ids, formal_fg_result_metric_ids(contract))) problems <- c(problems, "validation interval metric IDs drifted")
    }
    if (!identical(result$temporal_validation$verification_profile, "FIXED_MODEL_NO_REFIT_NO_RECALIBRATION")) problems <- c(problems, "temporal validation verification_profile drifted")
  }

  performance_fields <- c("development", "validation", "flexible_calibration_curve", "flexible_calibration_band", "decile_calibration")
  problems <- c(problems, formal_fg_result_exact_object(result$performance, performance_fields, "result.performance"))
  if (is.list(result$performance)) {
    problems <- c(problems, formal_fg_result_check_metrics(result$performance$development, "result.performance.development"), formal_fg_result_check_metrics(result$performance$validation, "result.performance.validation"), formal_fg_result_check_rows(result$performance$flexible_calibration_curve, 50L, c("predicted", "calibrated"), "result.performance.flexible_calibration_curve"), formal_fg_result_check_rows(result$performance$flexible_calibration_band, 50L, c("predicted", "ci_low", "ci_high"), "result.performance.flexible_calibration_band"), formal_fg_result_check_rows(result$performance$decile_calibration, 10L, c("predicted", "observed", "absolute_error"), "result.performance.decile_calibration"))
  }

  gate_fields <- c("conditions", "all_passed", "dca_status", "clinical_utility_claim_allowed")
  condition_fields <- c("oe_ratio", "calibration_slope", "ici", "decile_absolute_error")
  problems <- c(problems, formal_fg_result_exact_object(result$calibration_gate, gate_fields, "result.calibration_gate"))
  gate <- result$calibration_gate
  if (is.list(gate)) {
    problems <- c(problems, formal_fg_result_exact_object(gate$conditions, condition_fields, "result.calibration_gate.conditions"))
    if (is.list(gate$conditions) && (!all(vapply(gate$conditions, is.logical, logical(1))) || !all(lengths(gate$conditions) == 1L))) problems <- c(problems, "calibration gate conditions must be scalar booleans")
    calculated_pass <- is.list(gate$conditions) && length(gate$conditions) == 4L && all(unlist(gate$conditions, use.names = FALSE))
    if (!identical(gate$all_passed, calculated_pass)) problems <- c(problems, "calibration gate all_passed is inconsistent with its four conditions")
    expected_dca <- if (calculated_pass) "GENERATED" else "NOT_GENERATED_GATE_FAILED"
    if (!identical(gate$dca_status, expected_dca) || !identical(gate$clinical_utility_claim_allowed, calculated_pass) || !identical(result$clinical_utility_claim_allowed, calculated_pass)) problems <- c(problems, "calibration gate, DCA, and clinical-utility status are inconsistent")
  }
  problems <- c(problems, formal_fg_result_exact_object(result$decision_curve, c("status", "rows"), "result.decision_curve"))
  if (is.list(result$decision_curve) && is.list(gate)) {
    expected_dca <- if (isTRUE(gate$all_passed)) "GENERATED" else "NOT_GENERATED_GATE_FAILED"
    if (!identical(result$decision_curve$status, expected_dca)) problems <- c(problems, "decision_curve status is inconsistent with the calibration gate")
    expected_rows <- if (isTRUE(gate$all_passed)) 5L else 0L
    problems <- c(problems, formal_fg_result_check_rows(result$decision_curve$rows, expected_rows, c("threshold", "net_benefit"), "result.decision_curve.rows"))
    if (expected_rows == 5L && is.list(result$decision_curve$rows) && length(result$decision_curve$rows) == 5L) {
      thresholds <- vapply(result$decision_curve$rows, function(row) if (is.list(row) && formal_fg_result_numeric(row$threshold)) row$threshold else NA_real_, numeric(1))
      if (!isTRUE(all.equal(thresholds, c(.05, .1, .15, .2, .25)))) problems <- c(problems, "DCA thresholds drifted")
    }
  }

  if (!is.list(result$sensitivities) || length(result$sensitivities) != 2L) {
    problems <- c(problems, "Exactly two frozen sensitivity results are required")
  } else {
    complete_fields <- c("sensitivity_id", "status", "label", "formula_checksum", "may_replace_primary", "model_formula_unchanged", "imputations", "pooled_coefficient_count", "outcome_unobserved_excluded_n", "outcome_unobserved_recoded_negative_n")
    ipcw_fields <- c("sensitivity_id", "status", "label", "formula_checksum", "may_replace_primary", "model_formula_unchanged", "weighting", "truncation_quantiles", "truncation_cutpoints", "development_weight_min", "development_weight_max", "validation_weight_min", "validation_weight_max", "validation_outcomes_used_for_weight_learning", "validation_metrics")
    problems <- c(problems, formal_fg_result_exact_object(result$sensitivities[[1L]], complete_fields, "result.sensitivities[1]"), formal_fg_result_exact_object(result$sensitivities[[2L]], ipcw_fields, "result.sensitivities[2]"))
    ids <- vapply(result$sensitivities, function(x) if (is.list(x) && formal_fg_result_string(x$sensitivity_id)) x$sensitivity_id else "", character(1))
    if (!identical(ids, contract$sensitivity_ids)) problems <- c(problems, "Sensitivity IDs or order drifted")
    for (item in result$sensitivities) if (is.list(item) && (!identical(item$status, "COMPLETE") || !identical(item$label, "EXPLORATORY") || !formal_fg_sha256(item$formula_checksum) || !identical(item$may_replace_primary, FALSE) || !identical(item$model_formula_unchanged, TRUE))) problems <- c(problems, "Sensitivities must remain complete exploratory non-replacement analyses with the frozen formula")
    first <- result$sensitivities[[1L]]
    if (is.list(first) && (!identical(first$imputations, 40L) || !identical(first$pooled_coefficient_count, contract$parameter_df) || !formal_fg_result_integer(first$outcome_unobserved_excluded_n) || !identical(first$outcome_unobserved_recoded_negative_n, 0L))) problems <- c(problems, "complete-observation sensitivity contract drifted")
    second <- result$sensitivities[[2L]]
    if (is.list(second)) {
      if (!identical(second$weighting, "DEVELOPMENT_FITTED_STABILIZED_ASSESSMENT_PROCESS_IPCW") || !identical(second$truncation_quantiles, list(0.01, 0.99)) || !is.list(second$truncation_cutpoints) || length(second$truncation_cutpoints) != 2L || !identical(second$validation_outcomes_used_for_weight_learning, FALSE)) problems <- c(problems, "assessment-process IPCW must use development-fitted stabilized weights and frozen 1/99 truncation")
      for (field in c("development_weight_min", "development_weight_max", "validation_weight_min", "validation_weight_max")) if (!formal_fg_result_numeric(second[[field]], 0)) problems <- c(problems, sprintf("%s must be finite and nonnegative", field))
      problems <- c(problems, formal_fg_result_check_metrics(second$validation_metrics, "result.sensitivities[2].validation_metrics", contract))
    }
  }

  if (!identical(unlist(result$expected_output_ids, use.names = FALSE), contract$expected_output_ids)) problems <- c(problems, "Expected output IDs or order drifted")
  if (!is.list(result$prohibited_actions_observed) || length(result$prohibited_actions_observed)) problems <- c(problems, "prohibited_actions_observed must be an empty array")
  if (!formal_fg_sha256(result$structured_result_sha256)) {
    problems <- c(problems, "structured_result_sha256 must be present and lowercase SHA-256")
  } else if (!identical(result$structured_result_sha256, formal_fg_result_checksum(result))) {
    problems <- c(problems, "structured_result_sha256 does not match the canonical structured result")
  }
  problems <- unique(problems[nzchar(problems)])
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

#' Validate the strict FORMAL temporal Fine-Gray output manifest
#'
#' @param manifest Aggregate output manifest.
#' @param result Optional already-validated structured result for cross-binding.
#' @return Invisibly returns TRUE or raises a contract error.
validate_formal_temporal_fine_gray_output_manifest <- function(manifest, result = NULL) {
  problems <- formal_fg_result_exact_object(manifest, c("schema_version", "source_result_sha256", "artifacts"), "manifest")
  if (!is.list(manifest)) stop(contract_error(problems))
  if (!identical(manifest$schema_version, .formal_temporal_fg_manifest_version)) problems <- c(problems, "Unsupported FORMAL output manifest schema_version")
  if (!formal_fg_sha256(manifest$source_result_sha256)) problems <- c(problems, "manifest source_result_sha256 must be lowercase SHA-256")
  expected <- formal_temporal_fg_contract()$expected_output_ids
  if (!is.list(manifest$artifacts) || length(manifest$artifacts) != length(expected)) {
    problems <- c(problems, "Output manifest must contain exactly the 18 allowlisted artifacts")
  } else {
    ids <- vapply(manifest$artifacts, function(x) if (is.list(x) && formal_fg_result_string(x$output_id)) x$output_id else "", character(1))
    if (!identical(ids, expected)) problems <- c(problems, "Output manifest IDs or order drifted")
    for (i in seq_along(manifest$artifacts)) {
      artifact <- manifest$artifacts[[i]]
      dca_failed <- identical(expected[[i]], "FIGURE.CVCC-PRED-ISO-001.MAIN.5") && is.list(artifact) && identical(artifact$status, "NOT_GENERATED_GATE_FAILED")
      fields <- if (dca_failed) c("output_id", "status", "source_result_sha256", "aggregate_only") else c("output_id", "filename", "source_result_sha256", "aggregate_only")
      problems <- c(problems, formal_fg_result_exact_object(artifact, fields, sprintf("manifest.artifacts[%d]", i)))
      if (is.list(artifact)) {
        if (!identical(artifact$output_id, expected[[i]]) || !identical(artifact$source_result_sha256, manifest$source_result_sha256) || !identical(artifact$aggregate_only, TRUE)) problems <- c(problems, sprintf("manifest.artifacts[%d] is not checksum-bound and aggregate-only", i))
        if (dca_failed) {
          if (!identical(artifact$status, "NOT_GENERATED_GATE_FAILED")) problems <- c(problems, "DCA failure status drifted")
        } else if (!formal_fg_result_string(artifact$filename) || grepl("[/\\\\]", artifact$filename) || grepl("^\\.|\\.\\.", artifact$filename) || !grepl("^[A-Za-z0-9_.-]+$", artifact$filename)) {
          problems <- c(problems, sprintf("manifest.artifacts[%d].filename must be a safe basename", i))
        }
      }
    }
  }
  if (!is.null(result)) {
    validate_formal_temporal_fine_gray_result(result)
    if (!identical(manifest$source_result_sha256, result$structured_result_sha256)) problems <- c(problems, "Manifest checksum is not bound to the structured result")
    dca <- if (is.list(manifest$artifacts) && length(manifest$artifacts) >= 8L) manifest$artifacts[[8L]] else NULL
    if (identical(result$decision_curve$status, "GENERATED") && (!is.list(dca) || is.null(dca$filename) || !is.null(dca$status))) problems <- c(problems, "Generated DCA result requires a generated DCA artifact")
    if (identical(result$decision_curve$status, "NOT_GENERATED_GATE_FAILED") && (!is.list(dca) || !identical(dca$status, "NOT_GENERATED_GATE_FAILED") || !is.null(dca$filename))) problems <- c(problems, "Failed calibration gate requires exact NOT_GENERATED_GATE_FAILED manifest status")
  }
  problems <- unique(problems[nzchar(problems)])
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}
