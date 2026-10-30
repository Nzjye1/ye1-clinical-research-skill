temporal_fg_prepare <- function(data, analysis) {
  development <- data[data[[analysis$split]] == analysis$development_value, , drop = FALSE]
  validation <- data[data[[analysis$split]] == analysis$validation_value, , drop = FALSE]
  medians <- list()
  for (variable in unlist(analysis$median_impute_predictors %||% list(), use.names = FALSE)) {
    value <- stats::median(development[[variable]], na.rm = TRUE)
    if (!is.finite(value)) stop(sprintf("Development median is not estimable for %s", variable), call. = FALSE)
    medians[[variable]] <- value
    indicator <- analysis$missing_indicator_map[[variable]]
    development[[indicator]] <- as.integer(is.na(development[[variable]]))
    validation[[indicator]] <- as.integer(is.na(validation[[variable]]))
    development[[variable]][is.na(development[[variable]])] <- value
    validation[[variable]][is.na(validation[[variable]])] <- value
  }

  predictors <- unlist(analysis$baseline_predictors, use.names = FALSE)
  analysis_columns <- c(analysis$time, analysis$event, analysis$competing_event, predictors)
  development_complete <- stats::complete.cases(development[analysis_columns])
  validation_complete <- stats::complete.cases(validation[analysis_columns])
  development_observed <- development[[analysis$outcome_observed]] == 1
  validation_observed <- validation[[analysis$outcome_observed]] == 1

  list(
    development = development[development_complete & development_observed, , drop = FALSE],
    validation = validation[validation_complete & validation_observed, , drop = FALSE],
    medians = medians,
    excluded = list(
      development_outcome_unobserved = sum(!development_observed),
      validation_outcome_unobserved = sum(!validation_observed),
      development_predictor_missing = sum(development_observed & !development_complete),
      validation_predictor_missing = sum(validation_observed & !validation_complete)
    ),
    split_totals = list(development = nrow(development), validation = nrow(validation))
  )
}

temporal_fg_require_counts <- function(prepared, task, analysis) {
  observed <- c(
    total_n = nrow(prepared$development) + nrow(prepared$validation),
    total_events = sum(prepared$development[[analysis$event]] == 1) + sum(prepared$validation[[analysis$event]] == 1),
    validation_n = nrow(prepared$validation),
    validation_events = sum(prepared$validation[[analysis$event]] == 1)
  )
  required <- c(
    total_n = task$readiness$min_n %||% 1L,
    total_events = task$readiness$min_events %||% 1L,
    validation_n = task$readiness$min_validation_n %||% 1L,
    validation_events = task$readiness$min_validation_events %||% 1L
  )
  failed <- observed < required
  if (any(failed)) {
    stop(sprintf(
      "Outcome-observed analysis rows fail frozen sample gates: %s",
      paste(sprintf("%s=%d<%d", names(observed)[failed], observed[failed], required[failed]), collapse = "; ")
    ), call. = FALSE)
  }
  invisible(TRUE)
}

temporal_fg_fit <- function(data, analysis) {
  predictors <- unlist(analysis$baseline_predictors, use.names = FALSE)
  status <- factor(
    ifelse(data[[analysis$event]] == 1, "event", ifelse(data[[analysis$competing_event]] == 1, "competing", "censor")),
    levels = c("censor", "event", "competing")
  )
  fg_data <- data
  fg_data$.clin_time <- data[[analysis$time]]
  fg_data$.clin_status <- status
  formula <- stats::reformulate(predictors, response = "survival::Surv(.clin_time, .clin_status)")
  expanded <- survival::finegray(formula, data = fg_data, etype = "event")
  fit_formula <- stats::reformulate(predictors, response = "survival::Surv(fgstart, fgstop, fgstatus)")
  fit <- survival::coxph(
    fit_formula,
    data = expanded,
    weights = fgwt,
    ties = "breslow",
    x = TRUE,
    model = TRUE,
    control = survival::coxph.control(iter.max = 50L, eps = 1e-09)
  )
  coefficients <- stats::coef(fit)
  variance <- stats::vcov(fit)
  if (!length(coefficients) || any(!is.finite(coefficients)) || any(!is.finite(variance))) {
    stop("Fine-Gray model did not produce finite coefficients and variance.", call. = FALSE)
  }
  if (is.null(fit$iter) || any(fit$iter >= 50L)) stop("Fine-Gray model did not converge within the frozen iteration limit.", call. = FALSE)
  list(fit = fit, expanded_n = nrow(expanded), formula = formula)
}

temporal_fg_predict <- function(fitted, newdata, horizon) {
  baseline <- survival::basehaz(fitted$fit, centered = FALSE)
  eligible <- is.finite(baseline$time) & baseline$time <= horizon
  if (!any(eligible)) stop("Fine-Gray baseline hazard is unavailable at the frozen horizon.", call. = FALSE)
  h0 <- max(baseline$hazard[eligible])
  lp <- stats::predict(fitted$fit, newdata = newdata, type = "lp", reference = "zero")
  risk <- 1 - exp(-h0 * exp(lp))
  if (!is.finite(h0) || h0 < 0 || any(!is.finite(risk)) || any(risk < 0 | risk > 1)) {
    stop("Fine-Gray fixed-horizon absolute risks are not finite probabilities.", call. = FALSE)
  }
  list(risk = risk, baseline_subdistribution_hazard = h0)
}

temporal_fg_metrics <- function(event, risk) {
  metrics <- temporal_metrics(event, risk)
  if (any(!is.finite(metrics))) stop("Validation discrimination or calibration diagnostics are not all finite.", call. = FALSE)
  metrics
}

# Resolve the validated temporal Fine-Gray task to its registered route.
temporal_fine_gray_dispatch_kind <- function(task) {
  version <- task$schema_version %||% ""
  if (version %in% .formal_temporal_fg_task_versions) {
    validate_formal_temporal_fine_gray_task(task)
    return("FORMAL")
  }
  if (identical(version, .clinanalysis_schema_version)) {
    validate_analysis_task(task)
    if (!identical(task$analysis$method, "temporal_fine_gray_prediction") ||
        !isTRUE(task$analysis$pilot_only)) {
      stop(contract_error(
        "The legacy temporal Fine-Gray route requires a validated PILOT task"
      ))
    }
    return("PILOT")
  }
  stop(contract_error(sprintf(
    "Unsupported temporal Fine-Gray dispatch schema_version '%s'",
    version
  )))
}

#' Run a registered temporal Fine-Gray task
#'
#' FORMAL task versions use the observed FORMAL implementation. The legacy
#' technical-runnability task remains a one-model PILOT.
run_temporal_fine_gray_prediction <- function(
    task, data, output_dir, observer = NULL,
    formal_runner = run_formal_temporal_fine_gray_prediction,
    pilot_runner = run_temporal_fine_gray_pilot) {
  route <- temporal_fine_gray_dispatch_kind(task)
  if (identical(route, "FORMAL")) {
    return(formal_runner(
      task, data, output_dir, observer = observer
    ))
  }
  pilot_runner(task, data, output_dir)
}

run_temporal_fine_gray_pilot <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)

  analysis <- task$analysis
  prepared <- temporal_fg_prepare(data, analysis)
  temporal_fg_require_counts(prepared, task, analysis)
  fitted <- temporal_fg_fit(prepared$development, analysis)
  prediction <- temporal_fg_predict(fitted, prepared$validation, analysis$horizon)
  metrics <- temporal_fg_metrics(prepared$validation[[analysis$event]], prediction$risk)
  performance <- data.frame(
    model = "transparent_baseline",
    metric = names(metrics),
    estimate = unname(metrics),
    stringsAsFactors = FALSE
  )

  result$status <- "COMPLETE"
  result$counts <- list(
    input_n = nrow(data),
    development_n = prepared$split_totals$development,
    development_analysis_n = nrow(prepared$development),
    development_events = sum(prepared$development[[analysis$event]] == 1),
    development_competing_events = sum(prepared$development[[analysis$competing_event]] == 1),
    validation_n = prepared$split_totals$validation,
    validation_analysis_n = nrow(prepared$validation),
    validation_events = sum(prepared$validation[[analysis$event]] == 1),
    validation_competing_events = sum(prepared$validation[[analysis$competing_event]] == 1),
    outcome_observed_n = sum(data[[analysis$outcome_observed]] == 1),
    outcome_unobserved_n = sum(data[[analysis$outcome_observed]] == 0),
    excluded = prepared$excluded
  )
  result$estimates <- list(primary = as_result_rows(performance))
  result$sensitivities <- list(status = "NOT_REQUESTED", analyses = list())
  result$diagnostics$model <- list(
    execution_mode = "PILOT",
    model_count = 1L,
    adjusted_model_count = 0L,
    sensitivity_count = 0L,
    engine = "Fine-Gray subdistribution hazards",
    horizon_hours_after_landmark = analysis$horizon,
    predictors = as.list(unlist(analysis$baseline_predictors, use.names = FALSE)),
    formula = paste(deparse(fitted$formula), collapse = " "),
    expanded_development_n = fitted$expanded_n,
    iterations = as.integer(fitted$fit$iter),
    converged = TRUE,
    finite_coefficients = TRUE,
    finite_variance = TRUE,
    finite_absolute_risks = TRUE,
    absolute_risk_computable = TRUE,
    validation_risk_min = min(prediction$risk),
    validation_risk_max = max(prediction$risk),
    baseline_subdistribution_hazard = prediction$baseline_subdistribution_hazard,
    outcome_observation_handling = "Rows with outcome_observed=0 are excluded, never recoded as no event.",
    estimand_limit = "Technical complete-observation subset only; no formal target-population risk inference."
  )
  result$warnings[[length(result$warnings) + 1L]] <- list(
    code = "OUTCOME_OBSERVATION_LIMIT",
    severity = "WARNING",
    message = "Outcome-unobserved rows were excluded from fitting and validation; PILOT metrics do not establish formal target-population performance.",
    evidence = list(outcome_unobserved_n = result$counts$outcome_unobserved_n)
  )
  result$artifacts$tables$pilot_metrics <- write_csv_artifact(
    performance, output_dir, "pilot_metrics.csv",
    "single-model aggregate technical runnability metrics"
  )
  result
}

formal_temporal_fg_registered_dispatch_probe <- function(plugin, task) {
  formal_calls <- 0L
  pilot_calls <- 0L
  outcome <- tryCatch(
    plugin(
      task,
      data = data.frame(),
      output_dir = NULL,
      observer = NULL,
      formal_runner = function(...) {
        formal_calls <<- formal_calls + 1L
        "FORMAL_DISPATCH_SENTINEL"
      },
      pilot_runner = function(...) {
        pilot_calls <<- pilot_calls + 1L
        "PILOT_DISPATCH_SENTINEL"
      }
    ),
    error = function(e) NULL
  )
  identical(outcome, "FORMAL_DISPATCH_SENTINEL") &&
    identical(formal_calls, 1L) &&
    identical(pilot_calls, 0L)
}

materialize_model_runnability_receipt <- function(
  result,
  candidate_id,
  dataset_id,
  dataset_sha256,
  authorization_ref,
  output_path
) {
  if (!grepl("^[a-f0-9]{64}$", dataset_sha256)) stop("dataset_sha256 must be 64 lowercase hex characters.", call. = FALSE)
  metrics <- result$estimates$primary %||% list()
  metric_values <- stats::setNames(
    lapply(metrics, function(row) row$estimate),
    vapply(metrics, function(row) row$metric, character(1))
  )
  model <- result$diagnostics$model %||% list()
  pass <- identical(result$status, "COMPLETE") && isTRUE(model$converged) &&
    isTRUE(model$finite_coefficients) && isTRUE(model$finite_absolute_risks)
  receipt <- list(
    schema_version = "1.0.0",
    receipt_id = paste0("RECEIPT.", candidate_id, ".MODEL-TECHNICAL-RUNNABILITY.PILOT.V1"),
    candidate_id = candidate_id,
    check = "MODEL_TECHNICAL_RUNNABILITY",
    execution_mode = "PILOT",
    attempt_number = 1L,
    authorization_ref = authorization_ref,
    registered_dataset = list(dataset_id = dataset_id, sha256 = dataset_sha256),
    aggregate_only = TRUE,
    patient_level_payload = FALSE,
    formal_analysis_performed = FALSE,
    formal_outputs_generated = FALSE,
    result_driven_design_changes_made = FALSE,
    model_limits = list(primary_models_run = 1L, adjusted_models_run = 0L, sensitivity_analyses_run = 0L),
    status = if (pass) "COMPLETE" else "BLOCKED",
    technical_conclusion = if (pass) "PASS" else "BLOCKED",
    aggregate_diagnostics = list(
      counts = result$counts,
      model = list(
        engine = model$engine,
        horizon_hours_after_landmark = model$horizon_hours_after_landmark,
        predictors = model$predictors,
        converged = model$converged,
        finite_coefficients = model$finite_coefficients,
        finite_variance = model$finite_variance,
        absolute_risk_computable = model$absolute_risk_computable,
        finite_absolute_risks = model$finite_absolute_risks,
        validation_risk_min = model$validation_risk_min,
        validation_risk_max = model$validation_risk_max
      ),
      validation_metrics = metric_values
    ),
    limitations = list(
      model$estimand_limit %||% "No formal target-population inference.",
      "This receipt is a technical runnability result, not a candidate continuation or stop decision."
    ),
    candidate_lifecycle_decision = "NOT_MADE",
    next_responsibility = "research-topic-module consumes this aggregate receipt; the human gate decides the next controlled step"
  )
  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(receipt, output_path, auto_unbox = TRUE, pretty = TRUE, digits = NA, null = "null")
  invisible(receipt)
}
