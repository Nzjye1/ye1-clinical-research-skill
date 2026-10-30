.clinanalysis_schema_version <- "0.1.0"

`%||%` <- function(x, y) {
  if (is.null(x)) y else x
}

contract_error <- function(messages) {
  structure(
    list(message = paste(messages, collapse = "\n"), problems = messages),
    class = c("clinanalysis_contract_error", "error", "condition")
  )
}

#' Read an internal analysis task
#'
#' @param path JSON or YAML task file.
#' @return A validated task list.
#' @export
read_analysis_task <- function(path) {
  if (!file.exists(path)) {
    stop(contract_error(sprintf("Task file does not exist: %s", path)))
  }
  ext <- tolower(tools::file_ext(path))
  task <- switch(
    ext,
    json = jsonlite::fromJSON(path, simplifyVector = FALSE),
    yaml = yaml::read_yaml(path),
    yml = yaml::read_yaml(path),
    stop(contract_error("Task file must use .json, .yaml, or .yml"))
  )
  validate_analysis_task(task)
  task
}

#' Validate an internal analysis task
#'
#' This is deterministic validation. It does not ask a language model to infer
#' missing statistical fields.
#'
#' @param task Task list.
#' @return Invisibly returns `TRUE` or raises a contract error.
#' @export
validate_analysis_task <- function(task) {
  if (startsWith(task$schema_version %||% "", "clinical-study-input@")) {
    return(validate_registered_task_contract(task))
  }
  if (exists(".categorical_gcomp_task_versions", inherits = TRUE) &&
    (task$schema_version %||% "") %in% .categorical_gcomp_task_versions) {
    return(validate_registered_task_contract(task))
  }
  if ((task$schema_version %||% "") %in% .formal_temporal_fg_task_versions) {
    return(validate_formal_temporal_fine_gray_task(task))
  }
  problems <- character()
  required_top <- c("schema_version", "analysis_id", "data", "analysis")
  missing_top <- setdiff(required_top, names(task))
  if (length(missing_top)) {
    problems <- c(problems, sprintf("Missing top-level field: %s", missing_top))
  }

  if (!is.null(task$schema_version) && !identical(task$schema_version, .clinanalysis_schema_version)) {
    problems <- c(problems, sprintf(
      "Unsupported schema_version '%s'; expected '%s'",
      task$schema_version, .clinanalysis_schema_version
    ))
  }
  if (!is.null(task$analysis_id) && (!is.character(task$analysis_id) || length(task$analysis_id) != 1L || !nzchar(task$analysis_id))) {
    problems <- c(problems, "analysis_id must be one non-empty string")
  }

  if (!is.null(task$data)) {
    for (field in c("path", "format")) {
      if (is.null(task$data[[field]])) problems <- c(problems, sprintf("Missing data.%s", field))
    }
    supported_formats <- c("csv", "parquet", "rds")
    if (!is.null(task$data$format) && !(tolower(task$data$format) %in% supported_formats)) {
      problems <- c(problems, sprintf("Unsupported data.format '%s'", task$data$format))
    }
  }

  if (!is.null(task$analysis)) {
    for (field in c("method")) {
      if (is.null(task$analysis[[field]])) problems <- c(problems, sprintf("Missing analysis.%s", field))
    }
    method <- task$analysis$method %||% ""
    method_fields <- switch(
      method,
      modified_poisson = c("outcome"),
      cause_specific_cox = c("time", "event", "competing_event"),
      generic_regression = c("outcome", "outcome_type", "model_family"),
      survival_analysis = c("time", "event", "survival_engine"),
      longitudinal_model = c("outcome", "outcome_type", "subject_id", "repeated_time", "longitudinal_engine"),
      causal_comparison = c("outcome", "outcome_type", "estimand"),
      prediction_validation = c("outcome", "prediction", "validation_type", "prediction_origin"),
      temporal_logistic_prediction = c("outcome", "split", "development_value", "validation_value", "baseline_predictors", "covariates"),
      temporal_fine_gray_prediction = c("time", "event", "competing_event", "split", "development_value", "validation_value", "outcome_observed", "baseline_predictors", "horizon", "pilot_only"),
      character()
    )
    for (field in method_fields) {
      if (is.null(task$analysis[[field]])) problems <- c(problems, sprintf("Missing analysis.%s", field))
    }
    if (!is.null(task$analysis$method) && !(task$analysis$method %in% names(analysis_plugin_registry()))) {
      problems <- c(problems, sprintf("Unregistered analysis method '%s'", task$analysis$method))
    }
    exposure_methods <- c(
      "modified_poisson", "cause_specific_cox", "generic_regression",
      "survival_analysis", "longitudinal_model", "causal_comparison"
    )
    if (method %in% exposure_methods && (is.null(task$analysis$exposure) || !nzchar(task$analysis$exposure))) {
      problems <- c(problems, sprintf("%s requires analysis.exposure", method))
    }
    transform <- task$analysis$exposure_transform %||% "identity"
    if (!(transform %in% c("identity", "log2"))) {
      problems <- c(problems, sprintf("Unsupported exposure_transform '%s'", transform))
    }
    if (method %in% c("cause_specific_cox", "generic_regression")) {
      missing_method <- task$analysis$missing_data$method %||% "complete_case"
      if (!(missing_method %in% c("complete_case", "multiple_imputation"))) {
        problems <- c(problems, sprintf("Unsupported missing_data.method '%s'", missing_method))
      }
      m <- task$analysis$missing_data$m %||% 20L
      if (identical(missing_method, "multiple_imputation") && (!is.numeric(m) || length(m) != 1L || m < 2L)) {
        problems <- c(problems, "multiple_imputation requires missing_data.m >= 2")
      }
    }
    if (method %in% c("cause_specific_cox", "survival_analysis")) {
      plot_max_time <- task$analysis$plot_max_time %||% NULL
      if (!is.null(plot_max_time) && (!is.numeric(plot_max_time) || length(plot_max_time) != 1L || plot_max_time <= 0)) problems <- c(problems, "analysis.plot_max_time must be one positive number")
    }
    allowed_outcome_types <- c("continuous", "binary", "count", "ordinal")
    if (!is.null(task$analysis$outcome_type) && !(task$analysis$outcome_type %in% allowed_outcome_types)) {
      problems <- c(problems, sprintf("Unsupported outcome_type '%s'", task$analysis$outcome_type))
    }
    if (identical(method, "generic_regression")) {
      allowed_families <- c("gaussian", "binomial", "poisson", "negative_binomial", "ordinal")
      if (!((task$analysis$model_family %||% "") %in% allowed_families)) problems <- c(problems, "Unsupported generic regression model_family")
      compatible <- list(continuous = "gaussian", binary = "binomial", count = c("poisson", "negative_binomial"), ordinal = "ordinal")
      expected <- compatible[[task$analysis$outcome_type %||% ""]] %||% character()
      if (length(expected) && !((task$analysis$model_family %||% "") %in% expected)) problems <- c(problems, "outcome_type and model_family are incompatible")
      if (identical(task$analysis$model_family, "ordinal") && !length(task$analysis$outcome_order %||% list())) {
        problems <- c(problems, "Ordinal regression requires analysis.outcome_order")
      }
      estimator <- task$analysis$estimator %||% "maximum_likelihood"
      if (!(estimator %in% c("maximum_likelihood", "bias_reduced"))) problems <- c(problems, "Unsupported analysis.estimator")
      if (identical(estimator, "bias_reduced") && !identical(task$analysis$model_family, "binomial")) {
        problems <- c(problems, "bias_reduced estimator is only supported for binomial regression")
      }
    }
    if (identical(method, "survival_analysis")) {
      engine <- task$analysis$survival_engine %||% ""
      if (!(engine %in% c("kaplan_meier", "cox", "fine_gray", "rmst"))) problems <- c(problems, "Unsupported survival_engine")
      if (identical(engine, "fine_gray") && is.null(task$analysis$competing_event)) problems <- c(problems, "fine_gray requires competing_event")
      if (identical(engine, "rmst") && (is.null(task$analysis$tau) || task$analysis$tau <= 0)) problems <- c(problems, "rmst requires a positive tau")
    }
    if (identical(method, "longitudinal_model")) {
      engine <- task$analysis$longitudinal_engine %||% ""
      if (!(engine %in% c("gee", "lmm", "glmm"))) problems <- c(problems, "Unsupported longitudinal_engine")
      if (identical(engine, "lmm") && !identical(task$analysis$outcome_type, "continuous")) problems <- c(problems, "lmm requires a continuous outcome")
      if (identical(engine, "glmm") && !(task$analysis$outcome_type %in% c("binary", "count"))) problems <- c(problems, "glmm requires a binary or count outcome")
    }
    if (identical(method, "causal_comparison")) {
      if (!length(task$analysis$propensity_covariates %||% list())) problems <- c(problems, "causal_comparison requires propensity_covariates")
      if (!((task$analysis$estimand %||% "") %in% c("ATE", "ATT", "ATO"))) problems <- c(problems, "Unsupported causal estimand")
      if (identical(task$analysis$causal_estimator %||% "weighting", "aipw") && !identical(task$analysis$estimand, "ATE")) {
        problems <- c(problems, "aipw currently requires estimand=ATE")
      }
      if (!((task$analysis$outcome_type %||% "") %in% c("continuous", "binary"))) problems <- c(problems, "causal_comparison supports continuous or binary outcomes")
      truncation <- unlist(task$analysis$truncation_quantiles %||% list(0.01, 0.99), use.names = FALSE)
      if (length(truncation) != 2L || any(!is.finite(truncation)) || truncation[1L] < 0 || truncation[2L] > 1 || truncation[1L] >= truncation[2L]) {
        problems <- c(problems, "truncation_quantiles must be two increasing probabilities in [0,1]")
      }
    }
    if (identical(method, "prediction_validation")) {
      validation_type <- task$analysis$validation_type %||% ""
      if (!(validation_type %in% c("binary", "survival"))) problems <- c(problems, "Unsupported validation_type")
      if (!((task$analysis$prediction_origin %||% "") %in% c("external", "internal_holdout", "out_of_fold"))) problems <- c(problems, "prediction_origin must identify external, internal_holdout, or out_of_fold predictions")
      if (identical(validation_type, "survival") && (is.null(task$analysis$time) || is.null(task$analysis$event) || is.null(task$analysis$horizon))) {
        problems <- c(problems, "Survival prediction validation requires time, event, and horizon")
      }
    }
    if (identical(method, "temporal_logistic_prediction")) {
      if (!identical(task$analysis$variance_estimator %||% "model_based", "model_based")) problems <- c(problems, "temporal_logistic_prediction requires model_based variance")
      if (!identical(task$analysis$bootstrap_scope %||% "validation_only_fixed_model", "validation_only_fixed_model")) problems <- c(problems, "temporal_logistic_prediction requires validation-only fixed-model bootstrap")
      if (!identical(task$analysis$bootstrap_interval %||% "percentile", "percentile")) problems <- c(problems, "temporal_logistic_prediction requires percentile bootstrap intervals")
      if (!identical(task$analysis$calibration_intercept_method %||% "joint_with_slope", "joint_with_slope")) problems <- c(problems, "temporal_logistic_prediction requires jointly estimated calibration intercept and slope")
      if (isTRUE(task$analysis$decision_curve_enabled %||% FALSE)) problems <- c(problems, "Decision-curve analysis is not prespecified for temporal_logistic_prediction")
      imputed <- unlist(task$analysis$median_impute_predictors %||% list(), use.names = FALSE)
      indicator_map <- task$analysis$missing_indicator_map %||% list()
      if (!setequal(names(indicator_map), imputed)) problems <- c(problems, "missing_indicator_map must define every median-imputed predictor exactly once")
      sensitivities <- task$analysis$prediction_sensitivities %||% list()
      if (length(sensitivities) > 2L) problems <- c(problems, "At most two prediction sensitivities are allowed")
      if (length(sensitivities) && any(!vapply(sensitivities, function(x) isTRUE(x$refit), logical(1)))) problems <- c(problems, "Every temporal prediction sensitivity must refit the unchanged model")
      timing <- task$analysis$timing_analysis %||% NULL
      if (!is.null(timing)) {
        breaks <- unlist(timing$breaks %||% list(), use.names = FALSE)
        labels <- unlist(timing$labels %||% list(), use.names = FALSE)
        if (length(breaks) < 2L || any(diff(breaks) <= 0) || length(labels) != length(breaks) - 1L) problems <- c(problems, "timing_analysis requires increasing breaks and one label per interval")
      }
    }
    if (identical(method, "temporal_fine_gray_prediction")) {
      if (!isTRUE(task$analysis$pilot_only %||% FALSE)) problems <- c(problems, "temporal_fine_gray_prediction is PILOT-only and requires pilot_only=true")
      if (identical(task$analysis$development_value, task$analysis$validation_value)) problems <- c(problems, "development and validation values must differ")
      predictors <- unlist(task$analysis$baseline_predictors %||% list(), use.names = FALSE)
      if (!length(predictors) || any(!nzchar(predictors)) || anyDuplicated(predictors)) problems <- c(problems, "temporal_fine_gray_prediction requires unique non-empty baseline_predictors")
      if (length(task$analysis$covariates %||% list())) problems <- c(problems, "temporal_fine_gray_prediction permits one baseline model and no adjusted model")
      imputed <- unlist(task$analysis$median_impute_predictors %||% list(), use.names = FALSE)
      indicator_map <- task$analysis$missing_indicator_map %||% list()
      if (!setequal(names(indicator_map), imputed)) problems <- c(problems, "missing_indicator_map must define every median-imputed predictor exactly once")
      if (length(task$analysis$prediction_sensitivities %||% list())) problems <- c(problems, "temporal_fine_gray_prediction permits zero sensitivity analyses")
      if (isTRUE(task$analysis$decision_curve_enabled %||% FALSE)) problems <- c(problems, "Decision-curve analysis is not permitted for the technical runnability PILOT")
      horizon <- task$analysis$horizon %||% NA_real_
      if (!is.numeric(horizon) || length(horizon) != 1L || !is.finite(horizon) || horizon <= 0) problems <- c(problems, "temporal_fine_gray_prediction requires one positive finite horizon")
    }
    multiplicity <- task$analysis$multiplicity %||% "none"
    if (!(multiplicity %in% c("none", "holm", "BH"))) problems <- c(problems, "Unsupported multiplicity method")
    bootstrap_replicates <- task$analysis$bootstrap_replicates %||% 400L
    if (!is.numeric(bootstrap_replicates) || length(bootstrap_replicates) != 1L || bootstrap_replicates < 50L || bootstrap_replicates > 5000L) problems <- c(problems, "bootstrap_replicates must be between 50 and 5000")
    calibration_bins <- task$analysis$calibration_bins %||% 10L
    if (!is.numeric(calibration_bins) || length(calibration_bins) != 1L || calibration_bins < 4L || calibration_bins > 20L) problems <- c(problems, "calibration_bins must be between 4 and 20")
    thresholds <- unlist(task$analysis$decision_thresholds %||% list(), use.names = FALSE)
    if (length(thresholds) && any(!is.finite(thresholds) | thresholds <= 0 | thresholds >= 1)) problems <- c(problems, "decision_thresholds must be between 0 and 1")
  }

  if (!is.null(task$outputs)) {
    formats <- unlist(task$outputs$figure_formats %||% list("png", "pdf", "svg", "tiff"), use.names = FALSE)
    unsupported <- setdiff(formats, c("png", "pdf", "svg", "tiff"))
    if (!length(formats)) problems <- c(problems, "outputs.figure_formats must not be empty")
    if (length(unsupported)) problems <- c(problems, sprintf("Unsupported outputs.figure_formats: %s", paste(unsupported, collapse = ", ")))
    dpi <- task$outputs$figure_dpi %||% 600L
    if (!is.numeric(dpi) || length(dpi) != 1L || dpi < 72 || dpi > 1200) {
      problems <- c(problems, "outputs.figure_dpi must be between 72 and 1200")
    }
    width <- task$outputs$figure_width_in %||% NULL
    target_journal <- task$outputs$target_journal %||% "generic"
    if (!is.null(width) && (!is.numeric(width) || length(width) != 1L || width <= 0 || width > journal_max_width(target_journal))) {
      problems <- c(problems, sprintf("outputs.figure_width_in exceeds the allowed width for %s", target_journal))
    }
  }

  if (!is.null(task$readiness)) {
    for (field in c("min_n", "min_events", "min_validation_n", "min_validation_events")) {
      value <- task$readiness[[field]]
      if (!is.null(value) && (!is.numeric(value) || length(value) != 1L || value < 1)) problems <- c(problems, sprintf("readiness.%s must be one positive number", field))
    }
  }

  table1 <- task$tfl$table1 %||% list(enabled = FALSE)
  if (isTRUE(table1$enabled)) {
    if (is.null(table1$group) || !nzchar(table1$group)) problems <- c(problems, "Enabled tfl.table1 requires a group")
    variables <- table1$variables %||% list()
    if (!length(variables)) problems <- c(problems, "Enabled tfl.table1 requires variables")
    variable_names <- vapply(variables, function(x) x$name %||% "", character(1))
    if (any(!nzchar(variable_names))) problems <- c(problems, "Every Table 1 variable requires a name")
    if (anyDuplicated(variable_names)) problems <- c(problems, "Table 1 variable names must be unique")
    allowed_types <- c("continuous", "categorical", "binary")
    invalid_types <- vapply(variables, function(x) !(x$type %||% "") %in% allowed_types, logical(1))
    if (any(invalid_types)) problems <- c(problems, "Unsupported Table 1 variable type")
    invalid_summary <- vapply(variables, function(x) {
      summary <- x$summary %||% if (identical(x$type, "continuous")) "mean_sd" else NULL
      !is.null(summary) && (!identical(x$type, "continuous") || !(summary %in% c("mean_sd", "median_iqr")))
    }, logical(1))
    if (any(invalid_summary)) problems <- c(problems, "Table 1 summary must be mean_sd or median_iqr and only applies to continuous variables")
  }

  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

new_analysis_result <- function(task, status = "COMPLETE") {
  list(
    schema_version = .clinanalysis_schema_version,
    analysis_id = task$analysis_id,
    method = task$analysis$method,
    status = status,
    counts = list(),
    tables = list(),
    estimates = list(),
    diagnostics = list(),
    diagnostic_index = list(),
    sensitivities = list(),
    warnings = list(),
    artifacts = list(tables = list(), figures = list()),
    provenance = list(
      generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
      r_version = R.version.string,
      platform = R.version$platform,
      package_version = as.character(utils::packageVersion("clinanalysis")),
      seed = task$seed %||% 20260718L
    )
  )
}
