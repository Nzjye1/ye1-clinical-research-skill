readiness_finding <- function(code, severity, message, evidence = list()) {
  list(code = code, severity = severity, message = message, evidence = evidence)
}

analysis_required_columns <- function(analysis) {
  common_covariates <- unlist(analysis$covariates %||% list(), use.names = FALSE)
  required <- switch(
    analysis$method,
    modified_poisson = c(analysis$outcome, analysis$exposure, analysis$cluster_id, common_covariates),
    cause_specific_cox = c(
      analysis$time, analysis$event, analysis$competing_event, analysis$exposure,
      analysis$cluster_id, common_covariates,
      unlist(analysis$missing_data$auxiliary_variables %||% list(), use.names = FALSE),
      analysis$multistate_gate$baseline_state_indicator
    ),
    generic_regression = c(
      analysis$outcome, analysis$exposure, analysis$cluster_id, common_covariates,
      unlist(analysis$effect_modifiers %||% list(), use.names = FALSE),
      unlist(analysis$missing_data$auxiliary_variables %||% list(), use.names = FALSE)
    ),
    survival_analysis = c(
      analysis$time, analysis$event, analysis$competing_event, analysis$exposure,
      analysis$cluster_id, common_covariates, unlist(analysis$cox_strata %||% list(), use.names = FALSE)
    ),
    longitudinal_model = c(
      analysis$outcome, analysis$exposure, analysis$subject_id,
      analysis$repeated_time, common_covariates
    ),
    causal_comparison = c(
      analysis$outcome, analysis$exposure,
      unlist(analysis$propensity_covariates %||% list(), use.names = FALSE),
      unlist(analysis$outcome_covariates %||% list(), use.names = FALSE)
    ),
    prediction_validation = c(
      analysis$outcome, analysis$prediction, analysis$time, analysis$event,
      unlist(analysis$subgroup_variables %||% list(), use.names = FALSE)
    ),
    temporal_logistic_prediction = {
      imputed <- unlist(analysis$median_impute_predictors %||% list(), use.names = FALSE)
      generated <- unlist(analysis$missing_indicator_map %||% list(), use.names = FALSE)
      sensitivities <- analysis$prediction_sensitivities %||% list()
      sensitivity_columns <- unlist(lapply(sensitivities, function(x) c(x$outcome, x$eligibility)), use.names = FALSE)
      timing <- analysis$timing_analysis %||% list()
      qc <- analysis$qc_variables %||% list()
      c(analysis$outcome, analysis$split,
        setdiff(c(unlist(analysis$baseline_predictors %||% list(), use.names = FALSE), common_covariates), generated),
        imputed, sensitivity_columns, timing$time, timing$component, unlist(qc, use.names = FALSE))
    },
    temporal_fine_gray_prediction = {
      imputed <- unlist(analysis$median_impute_predictors %||% list(), use.names = FALSE)
      generated <- unlist(analysis$missing_indicator_map %||% list(), use.names = FALSE)
      qc <- analysis$qc_variables %||% list()
      c(
        analysis$time, analysis$event, analysis$competing_event, analysis$split,
        analysis$outcome_observed,
        setdiff(unlist(analysis$baseline_predictors %||% list(), use.names = FALSE), generated),
        imputed, unlist(qc, use.names = FALSE)
      )
    },
    character()
  )
  unique(required[!is.na(required) & nzchar(required)])
}

append_finding <- function(findings, code, severity, message, evidence = list()) {
  findings[[length(findings) + 1L]] <- readiness_finding(code, severity, message, evidence)
  findings
}

#' Check whether standardized data are ready for a specified analysis
#'
#' @param task Validated task.
#' @param data Analysis-ready data frame.
#' @return Structured readiness report.
#' @export
check_analysis_readiness <- function(task, data) {
  findings <- list()
  analysis <- task$analysis
  required <- analysis_required_columns(analysis)
  missing_columns <- setdiff(required, names(data))
  if (length(missing_columns)) {
    findings <- append_finding(findings, "MISSING_COLUMNS", "BLOCK", "Required analysis columns are missing.", list(columns = missing_columns))
  }

  if (!length(missing_columns)) {
    n <- nrow(data)
    min_n <- task$readiness$min_n %||% 30L
    if (n < min_n) {
      findings <- append_finding(findings, "INSUFFICIENT_N", "BLOCK", sprintf("Sample size %d is below the required minimum %d.", n, min_n), list(n = n, minimum = min_n))
    }

    binary_outcome <- analysis$method %in% c("modified_poisson", "cause_specific_cox", "survival_analysis", "temporal_logistic_prediction", "temporal_fine_gray_prediction") ||
      identical(analysis$outcome_type, "binary") ||
      isTRUE((analysis$validation_type %||% "") %in% c("binary", "survival"))
    outcome_name <- if (analysis$method %in% c("cause_specific_cox", "survival_analysis", "temporal_fine_gray_prediction") || identical(analysis$validation_type, "survival")) analysis$event else analysis$outcome
    if (!is.null(outcome_name) && nzchar(outcome_name)) {
      outcome <- data[[outcome_name]]
      observed <- stats::na.omit(unique(outcome))
      if (binary_outcome && !all(observed %in% c(0, 1))) {
        findings <- append_finding(findings, "NON_BINARY_OUTCOME", "BLOCK", "The specified event/outcome must use binary 0/1 coding.", list(observed_values = utils::head(observed, 20L)))
      }
      if (identical(analysis$outcome_type, "continuous") && !is.numeric(outcome)) {
        findings <- append_finding(findings, "NON_NUMERIC_OUTCOME", "BLOCK", "A continuous outcome must be numeric.")
      }
      if (identical(analysis$outcome_type, "count") && (!is.numeric(outcome) || any(outcome < 0 | outcome != floor(outcome), na.rm = TRUE))) {
        findings <- append_finding(findings, "INVALID_COUNT_OUTCOME", "BLOCK", "A count outcome must contain non-negative integers.")
      }
      if (identical(analysis$outcome_type, "ordinal")) {
        allowed <- unlist(analysis$outcome_order %||% list(), use.names = FALSE)
        if (!length(allowed) || !all(observed %in% allowed)) findings <- append_finding(findings, "INVALID_ORDINAL_OUTCOME", "BLOCK", "Observed ordinal values must match outcome_order.")
      }
      if (binary_outcome && all(observed %in% c(0, 1))) {
        events <- sum(outcome == 1, na.rm = TRUE)
        min_events <- task$readiness$min_events %||% 10L
        if (events < min_events) findings <- append_finding(findings, "INSUFFICIENT_EVENTS", "BLOCK", sprintf("Only %d events are available; minimum is %d.", events, min_events), list(events = events, minimum = min_events))
      }
    }

    if (analysis$method %in% c("cause_specific_cox", "survival_analysis", "temporal_fine_gray_prediction") || identical(analysis$validation_type, "survival")) {
      followup <- data[[analysis$time]]
      if (!is.numeric(followup) || any(followup <= 0, na.rm = TRUE)) findings <- append_finding(findings, "INVALID_FOLLOWUP_TIME", "BLOCK", "Survival follow-up time must be numeric and strictly positive.")
    }
    if (analysis$method %in% c("cause_specific_cox", "survival_analysis", "temporal_fine_gray_prediction") && !is.null(analysis$competing_event)) {
      event <- data[[analysis$event]]; competing <- data[[analysis$competing_event]]
      valid_competing <- stats::na.omit(unique(competing))
      if (!all(valid_competing %in% c(0, 1))) findings <- append_finding(findings, "NON_BINARY_COMPETING_EVENT", "BLOCK", "The competing event must use binary 0/1 coding.")
      if (any(event == 1 & competing == 1, na.rm = TRUE)) findings <- append_finding(findings, "NON_EXCLUSIVE_EVENTS", "BLOCK", "Primary and competing events overlap on one or more rows.")
    }

    if (!is.null(analysis$exposure) && nzchar(analysis$exposure)) {
      exposure <- data[[analysis$exposure]]
      if (length(unique(stats::na.omit(exposure))) < 2L) findings <- append_finding(findings, "CONSTANT_EXPOSURE", "BLOCK", "Exposure has fewer than two distinct observed values.")
      if (analysis$method %in% c("modified_poisson", "causal_comparison") && !is.numeric(exposure)) findings <- append_finding(findings, "NON_NUMERIC_EXPOSURE", "BLOCK", "This method requires a numeric exposure.")
      if (identical(analysis$method, "causal_comparison") && !all(stats::na.omit(unique(exposure)) %in% c(0, 1))) findings <- append_finding(findings, "NON_BINARY_TREATMENT", "BLOCK", "Causal comparison requires treatment coded 0/1.")
      if (identical(analysis$exposure_transform %||% "identity", "log2") && (!is.numeric(exposure) || any(exposure <= 0, na.rm = TRUE))) findings <- append_finding(findings, "NON_POSITIVE_LOG2_EXPOSURE", "BLOCK", "log2 exposure transformation requires a positive numeric exposure.")
    }

    if (identical(analysis$method, "prediction_validation")) {
      prediction <- data[[analysis$prediction]]
      if (!is.numeric(prediction) || any(!is.finite(prediction), na.rm = TRUE)) findings <- append_finding(findings, "INVALID_PREDICTION", "BLOCK", "Prediction values must be finite numeric values.")
      if (length(unique(stats::na.omit(prediction))) < 2L) findings <- append_finding(findings, "CONSTANT_PREDICTION", "BLOCK", "Prediction values have no variation.")
      if (identical(analysis$prediction_scale %||% "risk", "risk") && any(prediction < 0 | prediction > 1, na.rm = TRUE)) findings <- append_finding(findings, "INVALID_PREDICTED_RISK", "BLOCK", "Predicted risks must be between 0 and 1.")
    }

    if (identical(analysis$method, "temporal_logistic_prediction")) {
      split <- data[[analysis$split]]
      development <- split == analysis$development_value
      validation <- split == analysis$validation_value
      allowed_split <- !is.na(split) & split %in% c(analysis$development_value, analysis$validation_value)
      if (any(!allowed_split)) findings <- append_finding(findings, "INVALID_TEMPORAL_SPLIT", "BLOCK", "Every row must have exactly the prespecified development or validation split value.", list(invalid_n = sum(!allowed_split)))
      if (!any(development, na.rm = TRUE) || !any(validation, na.rm = TRUE)) findings <- append_finding(findings, "MISSING_TEMPORAL_SPLIT", "BLOCK", "Both development and validation split values must be present.")
      if (any(development, na.rm = TRUE) && length(unique(stats::na.omit(data[[analysis$outcome]][development]))) < 2L) findings <- append_finding(findings, "DEVELOPMENT_SINGLE_CLASS", "BLOCK", "Development outcome must contain events and non-events.")
      if (any(validation, na.rm = TRUE) && length(unique(stats::na.omit(data[[analysis$outcome]][validation]))) < 2L) findings <- append_finding(findings, "VALIDATION_SINGLE_CLASS", "BLOCK", "Validation outcome must contain events and non-events.")
      validation_n <- sum(validation, na.rm = TRUE)
      validation_events <- sum(data[[analysis$outcome]][validation] == 1, na.rm = TRUE)
      min_validation_n <- task$readiness$min_validation_n %||% 1L
      min_validation_events <- task$readiness$min_validation_events %||% 1L
      if (validation_n < min_validation_n) findings <- append_finding(findings, "INSUFFICIENT_VALIDATION_N", "BLOCK", sprintf("Validation sample size %d is below the required minimum %d.", validation_n, min_validation_n), list(n = validation_n, minimum = min_validation_n))
      if (validation_events < min_validation_events) findings <- append_finding(findings, "INSUFFICIENT_VALIDATION_EVENTS", "BLOCK", sprintf("Validation events %d are below the required minimum %d.", validation_events, min_validation_events), list(events = validation_events, minimum = min_validation_events))
      if (any(is.na(data[[analysis$outcome]]))) findings <- append_finding(findings, "MISSING_PRIMARY_OUTCOME", "BLOCK", "The primary outcome must be observed for every analysis row.", list(missing_n = sum(is.na(data[[analysis$outcome]]))))
      for (sensitivity in analysis$prediction_sensitivities %||% list()) {
        values <- stats::na.omit(unique(data[[sensitivity$outcome]]))
        if (!all(values %in% c(0, 1))) findings <- append_finding(findings, "NON_BINARY_SENSITIVITY_OUTCOME", "BLOCK", sprintf("Sensitivity outcome %s must use 0/1 coding.", sensitivity$outcome))
        if (is.null(sensitivity$eligibility)) {
          if (any(is.na(data[[sensitivity$outcome]]))) findings <- append_finding(findings, "MISSING_SENSITIVITY_OUTCOME", "BLOCK", sprintf("Sensitivity outcome %s must be complete.", sensitivity$outcome), list(missing_n = sum(is.na(data[[sensitivity$outcome]]))))
        } else {
          eligibility <- data[[sensitivity$eligibility]]
          if (any(is.na(eligibility)) || !all(stats::na.omit(unique(eligibility)) %in% c(0, 1))) findings <- append_finding(findings, "INVALID_SENSITIVITY_ELIGIBILITY", "BLOCK", sprintf("Sensitivity eligibility %s must be complete binary 0/1.", sensitivity$eligibility))
          eligible <- !is.na(eligibility) & eligibility == 1
          missing_eligible_outcome <- eligible & is.na(data[[sensitivity$outcome]])
          if (any(missing_eligible_outcome)) findings <- append_finding(findings, "MISSING_ELIGIBLE_SENSITIVITY_OUTCOME", "BLOCK", sprintf("Sensitivity outcome %s must be observed for every eligible row.", sensitivity$outcome), list(missing_n = sum(missing_eligible_outcome)))
        }
      }
      qc <- analysis$qc_variables %||% list()
      if (!is.null(qc$record_id)) {
        record_id <- data[[qc$record_id]]
        invalid_id <- is.na(record_id) | !nzchar(trimws(as.character(record_id)))
        if (any(invalid_id)) findings <- append_finding(findings, "MISSING_RECORD_ID", "BLOCK", "Every analysis row requires a non-empty restricted record ID.", list(invalid_n = sum(invalid_id)))
        duplicate_n <- sum(duplicated(record_id[!invalid_id]))
        if (duplicate_n > 0L) findings <- append_finding(findings, "DUPLICATE_RECORD_ID", "BLOCK", "The analysis dataset must contain exactly one row per patient.", list(duplicate_n = duplicate_n))
      }
      semantic_flags <- c(
        FUTURE_PREDICTOR = qc$future_predictor_violation,
        OUTCOME_AT_OR_BEFORE_LANDMARK = qc$outcome_at_or_before_landmark,
        DRUG_FREE_RULE = qc$drug_free_rule_violation
      )
      for (code in names(semantic_flags)) {
        variable <- semantic_flags[[code]]
        if (is.null(variable) || !nzchar(variable)) next
        values <- data[[variable]]
        if (any(is.na(values)) || !all(stats::na.omit(unique(values)) %in% c(0, 1))) findings <- append_finding(findings, paste0("INVALID_", code, "_FLAG"), "BLOCK", sprintf("%s must be a complete binary audit flag.", variable))
        violation_n <- sum(values == 1, na.rm = TRUE)
        if (violation_n > 0L) findings <- append_finding(findings, paste0(code, "_VIOLATION"), "BLOCK", sprintf("%s contains one or more frozen semantic violations.", variable), list(violation_n = violation_n))
      }
      if (!is.null(qc$invalid_interval_count)) {
        invalid_intervals <- data[[qc$invalid_interval_count]]
        if (!is.numeric(invalid_intervals) || any(is.na(invalid_intervals) | invalid_intervals < 0 | invalid_intervals != floor(invalid_intervals))) findings <- append_finding(findings, "INVALID_INTERVAL_COUNT_FIELD", "BLOCK", "invalid_interval_count must contain complete non-negative integers.")
      }
      timing <- analysis$timing_analysis %||% NULL
      if (!is.null(timing)) {
        event <- data[[analysis$outcome]] == 1
        event_time <- data[[timing$time]]
        event_component <- data[[timing$component]]
        horizon <- max(unlist(timing$breaks, use.names = FALSE))
        if (!is.numeric(event_time)) {
          findings <- append_finding(findings, "NON_NUMERIC_FIRST_EVENT_TIME", "BLOCK", "First-event time must be numeric hours from the landmark.")
          invalid_event_time <- event
        } else {
          invalid_event_time <- event & (is.na(event_time) | !is.finite(event_time) | event_time <= 0 | event_time >= horizon)
        }
        if (any(invalid_event_time, na.rm = TRUE)) findings <- append_finding(findings, "INVALID_FIRST_EVENT_TIME", "BLOCK", "Every primary event requires a finite first-event time strictly after the landmark and before the horizon.", list(invalid_n = sum(invalid_event_time, na.rm = TRUE), horizon = horizon))
        component_present <- !is.na(event_component) & nzchar(trimws(as.character(event_component)))
        missing_component <- event & !component_present
        if (any(missing_component, na.rm = TRUE)) findings <- append_finding(findings, "MISSING_FIRST_EVENT_COMPONENT", "BLOCK", "Every primary event requires a first-event component.", list(invalid_n = sum(missing_component, na.rm = TRUE)))
        inconsistent_non_event <- !event & (!is.na(event_time) | component_present)
        if (any(inconsistent_non_event, na.rm = TRUE)) findings <- append_finding(findings, "NON_EVENT_WITH_EVENT_DETAIL", "BLOCK", "Non-event rows must not carry first-event timing or component values.", list(invalid_n = sum(inconsistent_non_event, na.rm = TRUE)))
      }
    }

    if (identical(analysis$method, "temporal_fine_gray_prediction")) {
      split <- data[[analysis$split]]
      development <- !is.na(split) & split == analysis$development_value
      validation <- !is.na(split) & split == analysis$validation_value
      allowed_split <- !is.na(split) & split %in% c(analysis$development_value, analysis$validation_value)
      if (any(!allowed_split)) findings <- append_finding(findings, "INVALID_TEMPORAL_SPLIT", "BLOCK", "Every row must have exactly the prespecified development or validation split value.", list(invalid_n = sum(!allowed_split)))
      if (!any(development) || !any(validation)) findings <- append_finding(findings, "MISSING_TEMPORAL_SPLIT", "BLOCK", "Both development and validation split values must be present.")

      observed_status <- data[[analysis$outcome_observed]]
      if (any(is.na(observed_status)) || !all(stats::na.omit(unique(observed_status)) %in% c(0, 1))) {
        findings <- append_finding(findings, "INVALID_OUTCOME_OBSERVED", "BLOCK", "outcome_observed must be complete binary 0/1.")
      } else {
        event <- data[[analysis$event]]
        competing <- data[[analysis$competing_event]]
        inconsistent <- observed_status == 0 & (event == 1 | competing == 1)
        if (any(inconsistent)) findings <- append_finding(findings, "UNOBSERVED_ROW_WITH_EVENT", "BLOCK", "Outcome-unobserved rows cannot carry primary or competing events.", list(invalid_n = sum(inconsistent)))
        development_observed <- development & observed_status == 1
        validation_observed <- validation & observed_status == 1
        if (length(unique(event[development_observed])) < 2L) findings <- append_finding(findings, "DEVELOPMENT_SINGLE_CLASS", "BLOCK", "Outcome-observed development rows must contain events and non-events.")
        if (length(unique(event[validation_observed])) < 2L) findings <- append_finding(findings, "VALIDATION_SINGLE_CLASS", "BLOCK", "Outcome-observed validation rows must contain events and non-events.")
        validation_n <- sum(validation_observed)
        validation_events <- sum(event[validation_observed] == 1)
        min_validation_n <- task$readiness$min_validation_n %||% 1L
        min_validation_events <- task$readiness$min_validation_events %||% 1L
        if (validation_n < min_validation_n) findings <- append_finding(findings, "INSUFFICIENT_VALIDATION_N", "BLOCK", sprintf("Outcome-observed validation sample size %d is below the required minimum %d.", validation_n, min_validation_n), list(n = validation_n, minimum = min_validation_n))
        if (validation_events < min_validation_events) findings <- append_finding(findings, "INSUFFICIENT_VALIDATION_EVENTS", "BLOCK", sprintf("Outcome-observed validation events %d are below the required minimum %d.", validation_events, min_validation_events), list(events = validation_events, minimum = min_validation_events))
      }

      followup <- data[[analysis$time]]
      invalid_followup <- !is.numeric(followup) || any(!is.finite(followup) | followup <= 0 | followup > analysis$horizon)
      if (invalid_followup) findings <- append_finding(findings, "FOLLOWUP_OUTSIDE_FROZEN_HORIZON", "BLOCK", "Follow-up must be finite, positive, and no greater than the frozen horizon.")

      qc <- analysis$qc_variables %||% list()
      if (!is.null(qc$record_id)) {
        record_id <- data[[qc$record_id]]
        invalid_id <- is.na(record_id) | !nzchar(trimws(as.character(record_id)))
        if (any(invalid_id)) findings <- append_finding(findings, "MISSING_RECORD_ID", "BLOCK", "Every analysis row requires a non-empty restricted record ID.", list(invalid_n = sum(invalid_id)))
        duplicate_n <- sum(duplicated(record_id[!invalid_id]))
        if (duplicate_n > 0L) findings <- append_finding(findings, "DUPLICATE_RECORD_ID", "BLOCK", "The PILOT dataset must contain exactly one row per restricted record ID.", list(duplicate_n = duplicate_n))
      }
      semantic_flags <- c(
        FUTURE_PREDICTOR = qc$future_predictor_violation,
        OUTCOME_AT_OR_BEFORE_LANDMARK = qc$outcome_at_or_before_landmark
      )
      for (code in names(semantic_flags)) {
        variable <- semantic_flags[[code]]
        if (is.null(variable) || !nzchar(variable)) next
        values <- data[[variable]]
        if (any(is.na(values)) || !all(stats::na.omit(unique(values)) %in% c(0, 1))) findings <- append_finding(findings, paste0("INVALID_", code, "_FLAG"), "BLOCK", sprintf("%s must be a complete binary audit flag.", variable))
        violation_n <- sum(values == 1, na.rm = TRUE)
        if (violation_n > 0L) findings <- append_finding(findings, paste0(code, "_VIOLATION"), "BLOCK", sprintf("%s contains one or more frozen semantic violations.", variable), list(violation_n = violation_n))
      }
      if (!is.null(qc$invalid_interval_count)) {
        invalid_intervals <- data[[qc$invalid_interval_count]]
        if (!is.numeric(invalid_intervals) || any(is.na(invalid_intervals) | invalid_intervals < 0 | invalid_intervals != floor(invalid_intervals))) findings <- append_finding(findings, "INVALID_INTERVAL_COUNT_FIELD", "BLOCK", "invalid_interval_count must contain complete non-negative integers.")
      }
    }

    if (identical(analysis$method, "longitudinal_model")) {
      repeated_time <- data[[analysis$repeated_time]]
      if (!is.numeric(repeated_time)) findings <- append_finding(findings, "NON_NUMERIC_REPEATED_TIME", "BLOCK", "Longitudinal repeated_time must be numeric for trajectory estimation.")
      observations <- table(data[[analysis$subject_id]])
      if (sum(observations >= 2L) < 2L) findings <- append_finding(findings, "INSUFFICIENT_REPEATED_SUBJECTS", "BLOCK", "At least two subjects must have repeated observations.")
    }

    missing_fraction <- vapply(data[required], function(x) mean(is.na(x)), numeric(1))
    max_missing <- task$readiness$max_missing_fraction %||% 0.5
    exempt_missing <- character()
    if (identical(analysis$method, "temporal_logistic_prediction")) {
      timing <- analysis$timing_analysis %||% list()
      sensitivities <- analysis$prediction_sensitivities %||% list()
      conditional_sensitivity_outcomes <- unlist(lapply(sensitivities, function(x) if (!is.null(x$eligibility)) x$outcome else NULL), use.names = FALSE)
      qc <- analysis$qc_variables %||% list()
      exempt_missing <- c(
        unlist(analysis$median_impute_predictors %||% list(), use.names = FALSE),
        timing$time, timing$component, conditional_sensitivity_outcomes,
        qc$restart_delay_minutes, qc$restart_same_drug
      )
    }
    if (identical(analysis$method, "temporal_fine_gray_prediction")) {
      exempt_missing <- unlist(analysis$median_impute_predictors %||% list(), use.names = FALSE)
    }
    excessive <- setdiff(names(missing_fraction)[missing_fraction > max_missing], exempt_missing)
    if (length(excessive)) findings <- append_finding(findings, "EXCESSIVE_MISSINGNESS", "BLOCK", "One or more required variables exceed the missingness threshold.", list(fractions = as.list(missing_fraction[excessive]), maximum = max_missing))
    nonzero <- names(missing_fraction)[missing_fraction > 0 & missing_fraction <= max_missing]
    if (analysis$method %in% c("temporal_logistic_prediction", "temporal_fine_gray_prediction")) nonzero <- setdiff(nonzero, exempt_missing)
    if (length(nonzero)) {
      missing_method <- analysis$missing_data$method %||% "complete_case"
      findings <- append_finding(
        findings,
        if (identical(missing_method, "multiple_imputation")) "MULTIPLE_IMPUTATION_REQUIRED" else "COMPLETE_CASE_REDUCTION",
        "WARNING",
        if (identical(missing_method, "multiple_imputation")) "Missing model variables will be handled by the prespecified multiple-imputation procedure." else "Rows with missing model variables will be excluded by this task.",
        list(fractions = as.list(missing_fraction[nonzero]))
      )
    }
  }

  severities <- vapply(findings, `[[`, character(1), "severity")
  status <- if ("BLOCK" %in% severities) "BLOCK" else if ("WARNING" %in% severities) "WARNING" else "PASS"
  list(status = status, findings = findings)
}
