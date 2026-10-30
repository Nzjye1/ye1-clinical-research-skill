.formal_temporal_fg_failure_diagnostic_version <-
  "formal-temporal-fine-gray-failure-diagnostic@1.3.0"
.formal_temporal_fg_failure_diagnostic_versions <- c(
  "formal-temporal-fine-gray-failure-diagnostic@1.0.0",
  "formal-temporal-fine-gray-failure-diagnostic@1.1.0",
  "formal-temporal-fine-gray-failure-diagnostic@1.2.0",
  .formal_temporal_fg_failure_diagnostic_version
)

.formal_fg_failure_stages <- c(
  "TASK_VALIDATION", "PLUGIN_LOOKUP", "DATA_SEMANTICS", "IMPUTATION",
  "PRIMARY_FIT", "INTERNAL_BOOTSTRAP", "VALIDATION_BOOTSTRAP",
  "SENSITIVITY", "RESULT_VALIDATION", "BUNDLE_WRITE"
)

.formal_fg_failure_catalog <- list(
  TASK_CONTRACT_INVALID = c("FORMAL_TASK_CONTRACT_ERROR", "The FORMAL task contract is invalid."),
  PLUGIN_LOOKUP_FAILED = c("FORMAL_PLUGIN_REGISTRATION_ERROR", "The registered FORMAL plugin is unavailable."),
  FORMAL_DATA_NOT_SUPPLIED = c("FORMAL_DATA_CONTRACT_ERROR", "Standardized analysis data were not supplied to the FORMAL runner."),
  REQUIRED_COLUMN_MISSING = c("FORMAL_DATA_CONTRACT_ERROR", "Required analysis columns are missing."),
  COLUMN_TYPE_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "One or more analysis columns have an invalid type."),
  BINARY_VALUE_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "A frozen binary field contains an invalid or missing value."),
  CATEGORY_VALUE_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "A frozen categorical field contains an invalid value."),
  VALIDATION_CATEGORY_NOT_TRANSPORTABLE = c("FORMAL_DATA_CONTRACT_ERROR", "A validation category was not observed in development."),
  TIME_WINDOW_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "A frozen follow-up or observation time is outside the allowed window."),
  OUTCOME_SEMANTICS_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "Competing-event or outcome-observation semantics are invalid."),
  PATIENT_ISOLATION_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "Patient-isolated one-record input semantics are invalid."),
  PARTITION_INVALID = c("FORMAL_DATA_CONTRACT_ERROR", "The frozen development and validation partitions are invalid."),
  EVENT_GATE_FAILED = c("FORMAL_DATA_CONTRACT_ERROR", "A frozen event-count readiness gate failed."),
  DEVELOPMENT_PREDICTOR_ALL_MISSING = c("FORMAL_DATA_CONTRACT_ERROR", "A frozen predictor is entirely missing in development."),
  FROZEN_TRANSFORMATION_NONFINITE = c("FORMAL_DATA_CONTRACT_ERROR", "A frozen predictor transformation would be non-finite or unidentified."),
  IMPUTATION_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The frozen multiple-imputation stage failed."),
  IMPUTATION_FOLLOWUP_FEATURE_NONFINITE = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The zero-safe follow-up feature for chained-equation imputation is non-finite."),
  IMPUTATION_FEATURE_MATRIX_NONFINITE = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The chained-equation imputation feature matrix is non-finite."),
  IMPUTATION_MODEL_STEP_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A chained-equation imputation model step failed."),
  IMPUTATION_TARGET_NO_OBSERVED_CASES = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "An imputation target has no observed development cases."),
  IMPUTATION_BINARY_FIT_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A binary chained-equation imputation fit failed."),
  IMPUTATION_BINARY_PREDICTION_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A binary chained-equation imputation prediction failed."),
  IMPUTATION_CATEGORICAL_FIT_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A categorical chained-equation imputation fit failed."),
  IMPUTATION_CATEGORICAL_PREDICTION_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A categorical chained-equation imputation prediction failed."),
  IMPUTATION_CONTINUOUS_FIT_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A continuous chained-equation imputation fit failed."),
  IMPUTATION_CONTINUOUS_PREDICTION_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A continuous chained-equation imputation prediction failed."),
  IMPUTATION_COMPLETION_INVALID = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The completed chained-equation imputation contains an invalid residual value."),
  PRIMARY_FIT_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The frozen primary or baseline Fine-Gray fit failed."),
  PRIMARY_FIT_DESIGN_INVALID = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The frozen Fine-Gray design matrix is non-finite or malformed."),
  PRIMARY_FIT_FINEGRAY_EXPANSION_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The Fine-Gray risk-set expansion failed."),
  PRIMARY_FIT_COXPH_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The Fine-Gray weighted Cox fit operation failed."),
  PRIMARY_FIT_NONSTRUCTURAL_SINGULARITY = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The Fine-Gray fit has a non-structural unidentified coefficient."),
  PRIMARY_FIT_VARIANCE_NONFINITE = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The Fine-Gray coefficient variance is non-finite."),
  PRIMARY_FIT_PREDICTION_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The frozen Fine-Gray fixed-horizon prediction failed."),
  INTERNAL_BOOTSTRAP_REPLICATE_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The frozen development bootstrap did not complete all requested replicates."),
  VALIDATION_BOOTSTRAP_REPLICATE_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "The frozen validation bootstrap did not complete all requested replicates."),
  SENSITIVITY_FAILED = c("FORMAL_STATISTICAL_PIPELINE_ERROR", "A frozen exploratory sensitivity analysis failed."),
  RESULT_CONTRACT_INVALID = c("FORMAL_RESULT_CONTRACT_ERROR", "The aggregate result failed its registered runtime contract."),
  BUNDLE_WRITE_FAILED = c("FORMAL_BUNDLE_WRITE_ERROR", "The validated aggregate bundle could not be written completely."),
  DATA_SEMANTICS_FAILED = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The data-semantics stage failed without an allowlisted detail code."),
  UNEXPECTED_IMPUTATION_FAILURE = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The imputation stage failed without an allowlisted detail code."),
  UNEXPECTED_PRIMARY_FIT_FAILURE = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The primary-fit stage failed without an allowlisted detail code."),
  UNEXPECTED_INTERNAL_BOOTSTRAP_FAILURE = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The development-bootstrap stage failed without an allowlisted detail code."),
  UNEXPECTED_VALIDATION_BOOTSTRAP_FAILURE = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The validation-bootstrap stage failed without an allowlisted detail code."),
  UNEXPECTED_SENSITIVITY_FAILURE = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The sensitivity stage failed without an allowlisted detail code."),
  PLUGIN_FAILED_WITHOUT_DIAGNOSTIC = c("FORMAL_UNEXPECTED_STAGE_ERROR", "The FORMAL plugin returned failure without a registered safe diagnostic.")
)

.formal_fg_failure_diagnostic_v1_1_codes <- c(
  "IMPUTATION_FOLLOWUP_FEATURE_NONFINITE",
  "IMPUTATION_FEATURE_MATRIX_NONFINITE",
  "IMPUTATION_MODEL_STEP_FAILED"
)

.formal_fg_failure_diagnostic_v1_2_codes <- c(
  "IMPUTATION_TARGET_NO_OBSERVED_CASES",
  "IMPUTATION_BINARY_FIT_FAILED",
  "IMPUTATION_BINARY_PREDICTION_FAILED",
  "IMPUTATION_CATEGORICAL_FIT_FAILED",
  "IMPUTATION_CATEGORICAL_PREDICTION_FAILED",
  "IMPUTATION_CONTINUOUS_FIT_FAILED",
  "IMPUTATION_CONTINUOUS_PREDICTION_FAILED",
  "IMPUTATION_COMPLETION_INVALID"
)

.formal_fg_failure_diagnostic_v1_3_codes <- c(
  "PRIMARY_FIT_DESIGN_INVALID",
  "PRIMARY_FIT_FINEGRAY_EXPANSION_FAILED",
  "PRIMARY_FIT_COXPH_FAILED",
  "PRIMARY_FIT_NONSTRUCTURAL_SINGULARITY",
  "PRIMARY_FIT_VARIANCE_NONFINITE",
  "PRIMARY_FIT_PREDICTION_FAILED"
)

.formal_fg_default_error_by_stage <- c(
  TASK_VALIDATION = "TASK_CONTRACT_INVALID",
  PLUGIN_LOOKUP = "PLUGIN_LOOKUP_FAILED",
  DATA_SEMANTICS = "DATA_SEMANTICS_FAILED",
  IMPUTATION = "UNEXPECTED_IMPUTATION_FAILURE",
  PRIMARY_FIT = "UNEXPECTED_PRIMARY_FIT_FAILURE",
  INTERNAL_BOOTSTRAP = "UNEXPECTED_INTERNAL_BOOTSTRAP_FAILURE",
  VALIDATION_BOOTSTRAP = "UNEXPECTED_VALIDATION_BOOTSTRAP_FAILURE",
  SENSITIVITY = "UNEXPECTED_SENSITIVITY_FAILURE",
  RESULT_VALIDATION = "RESULT_CONTRACT_INVALID",
  BUNDLE_WRITE = "BUNDLE_WRITE_FAILED"
)

formal_fg_safe_condition <- function(code, stage) {
  if (!code %in% names(.formal_fg_failure_catalog)) stop("Unknown safe FORMAL error code", call. = FALSE)
  if (!stage %in% .formal_fg_failure_stages) stop("Unknown FORMAL failure stage", call. = FALSE)
  structure(
    list(message = unname(.formal_fg_failure_catalog[[code]][[2L]]), code = code, stage = stage),
    class = c("formal_fg_safe_error", "error", "condition")
  )
}

formal_fg_stop <- function(code, stage) stop(formal_fg_safe_condition(code, stage))

new_formal_fg_execution_observer <- function() {
  observer <- new.env(parent = emptyenv())
  observer$current_stage <- "TASK_VALIDATION"
  observer$last_completed_stage <- "NONE"
  observer$bootstrap <- list(
    internal = list(status = "NOT_STARTED", requested = 1000L, completed = 0L, failed = 0L, first_error_code = NULL),
    validation = list(status = "NOT_STARTED", requested = 2000L, completed = 0L, failed = 0L, first_error_code = NULL)
  )
  observer
}

formal_fg_mark_stage <- function(observer, stage) {
  if (!is.environment(observer) || !stage %in% .formal_fg_failure_stages) {
    stop("Invalid FORMAL execution observer stage", call. = FALSE)
  }
  observer$current_stage <- stage
  invisible(observer)
}

formal_fg_complete_stage <- function(observer, stage) {
  formal_fg_mark_stage(observer, stage)
  observer$last_completed_stage <- stage
  invisible(observer)
}

formal_fg_condition_code <- function(condition, stage) {
  if (inherits(condition, "formal_fg_safe_error") &&
      is.character(condition$code) && length(condition$code) == 1L &&
      condition$code %in% names(.formal_fg_failure_catalog)) {
    return(condition$code)
  }
  unname(.formal_fg_default_error_by_stage[[stage]] %||% "DATA_SEMANTICS_FAILED")
}

formal_fg_record_bootstrap <- function(observer, scope, status, completed, failed, first_error_code = NULL) {
  key <- switch(scope, INTERNAL_BOOTSTRAP = "internal", VALIDATION_BOOTSTRAP = "validation", NULL)
  if (is.null(key) || !status %in% c("NOT_STARTED", "RUNNING", "COMPLETE", "FAILED")) {
    stop("Invalid FORMAL bootstrap progress update", call. = FALSE)
  }
  expected <- if (identical(key, "internal")) 1000L else 2000L
  observer$bootstrap[[key]] <- list(
    status = status,
    requested = expected,
    completed = as.integer(completed),
    failed = as.integer(failed),
    first_error_code = first_error_code
  )
  invisible(observer)
}

formal_fg_failure_diagnostic <- function(condition, observer) {
  stage <- if (inherits(condition, "formal_fg_safe_error") &&
               is.character(condition$stage) && length(condition$stage) == 1L) {
    condition$stage
  } else if (is.environment(observer)) {
    observer$current_stage
  } else {
    "DATA_SEMANTICS"
  }
  if (!stage %in% .formal_fg_failure_stages) stage <- "DATA_SEMANTICS"
  code <- formal_fg_condition_code(condition, stage)
  catalog <- .formal_fg_failure_catalog[[code]]
  diagnostic_version <- if (
    code %in% .formal_fg_failure_diagnostic_v1_3_codes
  ) {
    "formal-temporal-fine-gray-failure-diagnostic@1.3.0"
  } else {
    "formal-temporal-fine-gray-failure-diagnostic@1.2.0"
  }
  diagnostic <- list(
    schema_version = diagnostic_version,
    status = "FAILED",
    aggregate_only = TRUE,
    patient_level_payload = FALSE,
    physical_paths_in_diagnostic = FALSE,
    failure_stage = stage,
    last_completed_stage = if (is.environment(observer)) observer$last_completed_stage else "NONE",
    error_code = code,
    exception_class = unname(catalog[[1L]]),
    safe_message = unname(catalog[[2L]]),
    bootstrap = if (is.environment(observer)) observer$bootstrap else new_formal_fg_execution_observer()$bootstrap,
    acceptable_result_generated = FALSE,
    output_manifest_generated = FALSE,
    acceptable_bundle_generated = FALSE
  )
  validate_formal_temporal_fine_gray_failure_diagnostic(diagnostic)
  diagnostic
}

validate_formal_temporal_fine_gray_failure_diagnostic <- function(diagnostic) {
  top_fields <- c(
    "schema_version", "status", "aggregate_only", "patient_level_payload",
    "physical_paths_in_diagnostic", "failure_stage", "last_completed_stage",
    "error_code", "exception_class", "safe_message", "bootstrap",
    "acceptable_result_generated", "output_manifest_generated", "acceptable_bundle_generated"
  )
  problems <- formal_fg_result_exact_object(diagnostic, top_fields, "failure_diagnostic")
  if (!is.list(diagnostic)) stop(contract_error(problems))
  if (!diagnostic$schema_version %in%
      .formal_temporal_fg_failure_diagnostic_versions) {
    problems <- c(
      problems,
      "Unsupported FORMAL failure diagnostic schema_version"
    )
  }
  if (!identical(diagnostic$status, "FAILED") || !identical(diagnostic$aggregate_only, TRUE) ||
      !identical(diagnostic$patient_level_payload, FALSE) || !identical(diagnostic$physical_paths_in_diagnostic, FALSE)) {
    problems <- c(problems, "FORMAL failure diagnostics must be failed, aggregate-only, patient-free, and path-free")
  }
  if (!diagnostic$failure_stage %in% .formal_fg_failure_stages) problems <- c(problems, "Unknown FORMAL failure stage")
  if (!diagnostic$last_completed_stage %in% c("NONE", .formal_fg_failure_stages)) problems <- c(problems, "Unknown last completed FORMAL stage")
  if (!diagnostic$error_code %in% names(.formal_fg_failure_catalog)) {
    problems <- c(problems, "Unknown FORMAL safe error code")
  } else {
    version_1_0 <- identical(
      diagnostic$schema_version,
      "formal-temporal-fine-gray-failure-diagnostic@1.0.0"
    )
    version_1_1 <- identical(
      diagnostic$schema_version,
      "formal-temporal-fine-gray-failure-diagnostic@1.1.0"
    )
    version_1_2 <- identical(
      diagnostic$schema_version,
      "formal-temporal-fine-gray-failure-diagnostic@1.2.0"
    )
    if (version_1_0 && diagnostic$error_code %in%
        c(
          .formal_fg_failure_diagnostic_v1_1_codes,
          .formal_fg_failure_diagnostic_v1_2_codes,
          .formal_fg_failure_diagnostic_v1_3_codes
        )) {
      problems <- c(
        problems,
        "Failure diagnostic 1.0.0 cannot use later imputation substage codes"
      )
    }
    if (version_1_1 && diagnostic$error_code %in%
        c(
          .formal_fg_failure_diagnostic_v1_2_codes,
          .formal_fg_failure_diagnostic_v1_3_codes
        )) {
      problems <- c(
        problems,
        "Failure diagnostic 1.1.0 cannot use later operation codes"
      )
    }
    if (version_1_2 && diagnostic$error_code %in%
        .formal_fg_failure_diagnostic_v1_3_codes) {
      problems <- c(
        problems,
        "Failure diagnostic 1.2.0 cannot use 1.3.0 primary-fit operation codes"
      )
    }
    expected <- .formal_fg_failure_catalog[[diagnostic$error_code]]
    if (!identical(diagnostic$exception_class, unname(expected[[1L]])) ||
        !identical(diagnostic$safe_message, unname(expected[[2L]]))) {
      problems <- c(problems, "FORMAL exception class and safe message must match the allowlisted error code")
    }
  }
  problems <- c(problems, formal_fg_result_exact_object(diagnostic$bootstrap, c("internal", "validation"), "failure_diagnostic.bootstrap"))
  if (is.list(diagnostic$bootstrap)) {
    for (key in c("internal", "validation")) {
      item <- diagnostic$bootstrap[[key]]
      label <- paste0("failure_diagnostic.bootstrap.", key)
      problems <- c(problems, formal_fg_result_exact_object(item, c("status", "requested", "completed", "failed", "first_error_code"), label))
      expected_requested <- if (identical(key, "internal")) 1000L else 2000L
      if (is.list(item)) {
        if (!item$status %in% c("NOT_STARTED", "RUNNING", "COMPLETE", "FAILED") ||
            !identical(item$requested, expected_requested) ||
            !formal_fg_result_integer(item$completed) || !formal_fg_result_integer(item$failed) ||
            item$completed + item$failed > item$requested) {
          problems <- c(problems, paste(label, "contains invalid aggregate bootstrap counts"))
        }
        if (!is.null(item$first_error_code) &&
            (!is.character(item$first_error_code) || length(item$first_error_code) != 1L ||
             !item$first_error_code %in% names(.formal_fg_failure_catalog))) {
          problems <- c(problems, paste(label, "contains a non-allowlisted first error code"))
        }
      }
    }
  }
  if (!identical(diagnostic$acceptable_result_generated, FALSE) ||
      !identical(diagnostic$output_manifest_generated, FALSE) ||
      !identical(diagnostic$acceptable_bundle_generated, FALSE)) {
    problems <- c(problems, "A failure diagnostic cannot claim an acceptable result, manifest, or bundle")
  }
  rendered <- jsonlite::toJSON(diagnostic, auto_unbox = TRUE, null = "null")
  forbidden <- c(
    "(^|[^A-Za-z])[A-Za-z]:[/\\\\]", "(/Users/|/private/|/tmp/|~/)",
    "patient[_ -]?id", "subject[_ -]?id", "record[_ -]?id", "row[_ -]?[0-9]", "call stack", "traceback"
  )
  if (any(vapply(forbidden, grepl, logical(1), x = rendered, ignore.case = TRUE, perl = TRUE))) {
    problems <- c(problems, "FORMAL failure diagnostic contains forbidden path, identifier, row, or call-stack material")
  }
  problems <- unique(problems[nzchar(problems)])
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

formal_fg_failure_result <- function(task, diagnostic) {
  validate_formal_temporal_fine_gray_failure_diagnostic(diagnostic)
  failed <- new_analysis_result(task, status = "FAILED")
  failed$diagnostics$formal_failure <- diagnostic
  failed$warnings[[1L]] <- list(
    code = diagnostic$error_code,
    severity = "BLOCK",
    message = diagnostic$safe_message
  )
  failed
}

extract_formal_failure_diagnostic <- function(result) {
  diagnostic <- if (is.list(result) && identical(result$status %||% NULL, "FAILED")) {
    result$diagnostics$formal_failure %||% NULL
  } else NULL
  if (is.null(diagnostic)) stop(contract_error("A FAILED FORMAL result requires a registered safe diagnostic"))
  validate_registered_result_contract(diagnostic)
  diagnostic
}

formal_fg_run_observed <- function(
    task, data, output_dir,
    plugin_lookup = get_analysis_plugin,
    result_validator = validate_registered_result_contract,
    bundle_writer = write_formal_temporal_fg_bundle) {
  observer <- new_formal_fg_execution_observer()
  tryCatch({
    formal_fg_mark_stage(observer, "TASK_VALIDATION")
    validate_analysis_task(task)
    formal_fg_complete_stage(observer, "TASK_VALIDATION")

    if (is.null(data)) formal_fg_stop("FORMAL_DATA_NOT_SUPPLIED", "DATA_SEMANTICS")

    formal_fg_mark_stage(observer, "PLUGIN_LOOKUP")
    plugin <- plugin_lookup(task$analysis$method)
    formal_fg_complete_stage(observer, "PLUGIN_LOOKUP")

    result <- plugin(task, data, output_dir, observer = observer)
    if (identical(result$status %||% NULL, "FAILED")) {
      existing <- result$diagnostics$formal_failure %||% NULL
      if (is.null(existing)) {
        condition <- formal_fg_safe_condition("PLUGIN_FAILED_WITHOUT_DIAGNOSTIC", observer$current_stage)
        return(formal_fg_failure_result(task, formal_fg_failure_diagnostic(condition, observer)))
      }
      validate_registered_result_contract(existing)
      return(result)
    }

    formal_fg_mark_stage(observer, "RESULT_VALIDATION")
    result_validator(result)
    formal_fg_complete_stage(observer, "RESULT_VALIDATION")

    formal_fg_mark_stage(observer, "BUNDLE_WRITE")
    bundle_writer(result, output_dir)
    formal_fg_complete_stage(observer, "BUNDLE_WRITE")
    result
  }, error = function(e) {
    formal_fg_failure_result(task, formal_fg_failure_diagnostic(e, observer))
  })
}

formal_fg_preflight_data <- function(task, data) {
  analysis <- task$analysis
  contract <- formal_temporal_fg_contract_for_task(task)
  if (!is.data.frame(data)) formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")

  required <- unique(c(
    analysis$patient_id, analysis$time, analysis$event, analysis$competing_event,
    analysis$outcome_observed, analysis$last_observation_time,
    analysis$observation_state, analysis$split,
    analysis$qc_variables$future_predictor_violation,
    contract$primary_predictors
  ))
  if (length(setdiff(required, names(data)))) {
    formal_fg_stop("REQUIRED_COLUMN_MISSING", "DATA_SEMANTICS")
  }
  if (!nrow(data)) formal_fg_stop("PARTITION_INVALID", "DATA_SEMANTICS")

  id <- data[[analysis$patient_id]]
  if (!(is.character(id) || is.numeric(id) || is.integer(id)) ||
      length(id) != nrow(data) || any(is.na(id)) ||
      (is.character(id) && any(!nzchar(id))) ||
      (is.numeric(id) && any(!is.finite(id)))) {
    formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
  }
  if (anyDuplicated(id)) formal_fg_stop("PATIENT_ISOLATION_INVALID", "DATA_SEMANTICS")

  complete_binary <- c(
    analysis$event, analysis$competing_event, analysis$outcome_observed,
    analysis$qc_variables$future_predictor_violation
  )
  for (field in complete_binary) {
    value <- data[[field]]
    if (!(is.numeric(value) || is.integer(value) || is.logical(value))) {
      formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
    }
    if (any(is.na(value)) || !all(value %in% c(0, 1))) {
      formal_fg_stop("BINARY_VALUE_INVALID", "DATA_SEMANTICS")
    }
  }
  if (any(data[[analysis$qc_variables$future_predictor_violation]] != 0)) {
    formal_fg_stop("OUTCOME_SEMANTICS_INVALID", "DATA_SEMANTICS")
  }

  state <- data[[analysis$observation_state]]
  if (!(is.character(state) || is.factor(state))) formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
  state <- as.character(state)
  allowed_states <- c("OBSERVED", "UTA_ONLY", "OTHER_UNOBSERVED")
  if (any(is.na(state)) || !all(state %in% allowed_states)) {
    formal_fg_stop("CATEGORY_VALUE_INVALID", "DATA_SEMANTICS")
  }
  observed <- data[[analysis$outcome_observed]]
  event <- data[[analysis$event]]
  competing <- data[[analysis$competing_event]]
  if (any((observed == 1) != (state == "OBSERVED")) ||
      any(event == 1 & competing == 1) ||
      any(observed == 0 & (event == 1 | competing == 1))) {
    formal_fg_stop("OUTCOME_SEMANTICS_INVALID", "DATA_SEMANTICS")
  }

  followup <- data[[analysis$time]]
  if (!is.numeric(followup)) formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
  if (any(!is.finite(followup)) || any(followup <= 0 | followup > analysis$horizon_hours)) {
    formal_fg_stop("TIME_WINDOW_INVALID", "DATA_SEMANTICS")
  }
  last_observation <- data[[analysis$last_observation_time]]
  if (!is.numeric(last_observation)) formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
  if (any(!is.finite(last_observation))) formal_fg_stop("TIME_WINDOW_INVALID", "DATA_SEMANTICS")
  if (task$binding$sap_id %in% c(
    "SAP.CVCC-PRED-ISO-001.FROZEN.V2",
    "SAP.CVCC-PRED-ISO-001.FROZEN.V3"
  )) {
    if (any(last_observation[observed == 1] <= 0 | last_observation[observed == 1] > analysis$horizon_hours) ||
        any(last_observation[observed == 0] != 0)) {
      formal_fg_stop("TIME_WINDOW_INVALID", "DATA_SEMANTICS")
    }
  } else if (any(last_observation <= 0 | last_observation > analysis$horizon_hours)) {
    formal_fg_stop("TIME_WINDOW_INVALID", "DATA_SEMANTICS")
  }

  split <- data[[analysis$split]]
  if (!(is.character(split) || is.factor(split))) formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
  split <- as.character(split)
  allowed_split <- c(analysis$development_value, analysis$validation_value)
  if (any(is.na(split)) || !all(split %in% allowed_split) || !all(allowed_split %in% split)) {
    formal_fg_stop("PARTITION_INVALID", "DATA_SEMANTICS")
  }
  development_index <- split == analysis$development_value
  validation_index <- split == analysis$validation_value
  if (length(intersect(id[development_index], id[validation_index]))) {
    formal_fg_stop("PATIENT_ISOLATION_INVALID", "DATA_SEMANTICS")
  }

  binary_predictors <- names(contract$transformations)[
    unlist(contract$transformations, use.names = FALSE) == "BINARY_INDICATOR"
  ]
  categorical_predictors <- names(contract$transformations)[
    grepl("^TREATMENT_CODING_", unlist(contract$transformations, use.names = FALSE))
  ]
  numeric_predictors <- setdiff(contract$primary_predictors, categorical_predictors)
  for (field in numeric_predictors) {
    value <- data[[field]]
    if (!is.numeric(value)) formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
    observed_value <- value[!is.na(value)]
    if (any(!is.finite(observed_value))) formal_fg_stop("FROZEN_TRANSFORMATION_NONFINITE", "DATA_SEMANTICS")
    if (field %in% binary_predictors && !all(observed_value %in% c(0, 1))) {
      formal_fg_stop("BINARY_VALUE_INVALID", "DATA_SEMANTICS")
    }
  }

  for (field in contract$primary_predictors) {
    if (all(is.na(data[[field]][development_index]))) {
      formal_fg_stop("DEVELOPMENT_PREDICTOR_ALL_MISSING", "DATA_SEMANTICS")
    }
  }
  for (field in categorical_predictors) {
    value <- data[[field]]
    if (!(is.character(value) || is.factor(value))) {
      formal_fg_stop("COLUMN_TYPE_INVALID", "DATA_SEMANTICS")
    }
    value <- as.character(value)
    if (identical(field, "ami_type") &&
        !all(stats::na.omit(value) %in% c("NSTEMI", "STEMI", "OTHER_UNSPECIFIED"))) {
      formal_fg_stop("CATEGORY_VALUE_INVALID", "DATA_SEMANTICS")
    }
    development_levels <- unique(stats::na.omit(value[development_index]))
    validation_levels <- unique(stats::na.omit(value[validation_index]))
    if (length(setdiff(validation_levels, development_levels))) {
      formal_fg_stop("VALIDATION_CATEGORY_NOT_TRANSPORTABLE", "DATA_SEMANTICS")
    }
  }

  positive_transform <- names(contract$transformations)[
    unlist(contract$transformations, use.names = FALSE) == "NATURAL_LOG_AFTER_UNIT_HARMONIZATION"
  ]
  for (field in positive_transform) {
    observed_value <- data[[field]][!is.na(data[[field]])]
    if (any(observed_value <= 0)) {
      formal_fg_stop("FROZEN_TRANSFORMATION_NONFINITE", "DATA_SEMANTICS")
    }
  }
  development_age <- data$age[development_index & !is.na(data$age)]
  if (length(unique(development_age)) < 3L ||
      length(unique(stats::quantile(development_age, c(.1, .5, .9), names = FALSE, type = 7))) != 3L) {
    formal_fg_stop("FROZEN_TRANSFORMATION_NONFINITE", "DATA_SEMANTICS")
  }

  development_events <- sum(event[development_index])
  validation_events <- sum(event[validation_index])
  if (development_events < task$readiness$min_development_events ||
      validation_events < task$readiness$min_validation_events) {
    formal_fg_stop("EVENT_GATE_FAILED", "DATA_SEMANTICS")
  }

  list(
    input_n = nrow(data),
    development_n = sum(development_index),
    validation_n = sum(validation_index),
    development_events = development_events,
    validation_events = validation_events,
    frozen_semantics_validated = TRUE,
    patient_isolation_validated = TRUE,
    transformation_domain_validated = TRUE
  )
}
