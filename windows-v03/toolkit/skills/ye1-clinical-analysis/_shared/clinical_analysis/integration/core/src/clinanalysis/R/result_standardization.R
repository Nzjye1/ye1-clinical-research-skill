collect_effect_estimates <- function(result) {
  if (identical(result$method, "modified_poisson")) {
    estimate <- result$estimates[["primary", exact = TRUE]]
    if (is.null(estimate)) return(data.frame())
    return(data.frame(
      outcome = estimate$term, estimand = estimate$contrast,
      measure = estimate$estimate_type, estimate = estimate$estimate,
      ci_low = estimate$ci_low, ci_high = estimate$ci_high,
      p_value = estimate$p_value, confidence_level = estimate$confidence_level,
      stringsAsFactors = FALSE
    ))
  }
  if (identical(result$method, "cause_specific_cox")) {
    rows <- lapply(c("primary_event", "competing_event"), function(key) {
      estimate <- result$estimates[[key]]
      if (is.null(estimate)) return(NULL)
      data.frame(
        outcome = estimate$label %||% key, estimand = "Exposure group contrast",
        measure = estimate$estimate_type, estimate = estimate$estimate,
        ci_low = estimate$ci_low, ci_high = estimate$ci_high,
        p_value = estimate$p_value, confidence_level = estimate$confidence_level,
        stringsAsFactors = FALSE
      )
    })
    rows <- Filter(Negate(is.null), rows)
    if (!length(rows)) return(data.frame())
    return(do.call(rbind, rows))
  }
  if (result$method %in% c("generic_regression", "survival_analysis", "longitudinal_model", "causal_comparison", "prediction_validation", "temporal_logistic_prediction")) {
    rows <- result$estimates[["primary", exact = TRUE]] %||% list()
    if (!length(rows)) return(data.frame())
    keys <- unique(unlist(lapply(rows, names), use.names = FALSE))
    normalized <- lapply(rows, function(row) {
      missing <- setdiff(keys, names(row))
      row[missing] <- NA
      as.data.frame(row[keys], stringsAsFactors = FALSE)
    })
    x <- do.call(rbind, normalized)
    value <- function(primary, fallback = NA) {
      if (primary %in% names(x)) return(x[[primary]])
      if (length(fallback) == nrow(x)) fallback else rep(fallback, nrow(x))
    }
    return(data.frame(
      outcome = as.character(value("term", value("metric", result$method))),
      estimand = as.character(value("estimand", value("term", result$method))),
      measure = as.character(value("measure", value("metric", "estimate"))),
      estimate = as.numeric(value("estimate")),
      ci_low = as.numeric(value("ci_low")), ci_high = as.numeric(value("ci_high")),
      p_value = as.numeric(value("p_value")),
      confidence_level = as.numeric(value("confidence_level")),
      stringsAsFactors = FALSE
    ))
  }
  data.frame()
}

diagnostic_item <- function(code, status, message, source) {
  list(code = code, status = status, message = message, source = source)
}

build_diagnostic_index <- function(result) {
  index <- list()
  readiness <- result$diagnostics$readiness %||% list(status = "UNKNOWN")
  index[[length(index) + 1L]] <- diagnostic_item(
    "ANALYSIS_READINESS", readiness$status %||% "UNKNOWN",
    "Deterministic analysis-readiness gate.", "diagnostics.readiness"
  )
  if (identical(result$method, "modified_poisson") && !is.null(result$diagnostics$model)) {
    model <- result$diagnostics$model
    index[[length(index) + 1L]] <- diagnostic_item(
      "MODEL_CONVERGENCE", if (isTRUE(model$converged)) "PASS" else "BLOCK",
      "Modified Poisson model convergence.", "diagnostics.model.converged"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "FITTED_RISK_RANGE", if ((model$fitted_probability_above_one_n %||% 0) > 0) "WARNING" else "PASS",
      "Check whether any fitted risks exceed one.", "diagnostics.model.fitted_probability_above_one_n"
    )
  }
  if (identical(result$method, "cause_specific_cox") && length(result$estimates)) {
    for (key in c("primary_event", "competing_event")) {
      estimate <- result$estimates[[key]]
      if (is.null(estimate)) next
      min_p <- estimate$ph_rank_test$min %||% NA_real_
      status <- if (is.na(min_p)) "UNKNOWN" else if (min_p < 0.05) "WARNING" else "PASS"
      index[[length(index) + 1L]] <- diagnostic_item(
        paste0(toupper(key), "_PH_ASSUMPTION"), status,
        "Rank-transformed Schoenfeld residual test across fitted models.",
        paste0("estimates.", key, ".ph_rank_test")
      )
    }
    multistate <- result$diagnostics$multistate %||% list(status = "UNKNOWN")
    index[[length(index) + 1L]] <- diagnostic_item(
      "MULTISTATE_APPLICABILITY", multistate$status %||% "UNKNOWN",
      multistate$reason %||% "Prespecified common-baseline-state gate.", "diagnostics.multistate"
    )
  }
  if (result$method %in% c("generic_regression", "survival_analysis", "longitudinal_model")) {
    model <- result$diagnostics$model %||% list()
    index[[length(index) + 1L]] <- diagnostic_item(
      "MODEL_FIT", if (identical(result$status, "COMPLETE") && !isTRUE(model$singular)) "PASS" else if (isTRUE(model$singular)) "WARNING" else "BLOCK",
      "Prespecified model fit and convergence status.", "diagnostics.model"
    )
    if (!is.null(result$diagnostics$proportional_hazards)) {
      index[[length(index) + 1L]] <- diagnostic_item(
        "PROPORTIONAL_HAZARDS", "REVIEW", "Schoenfeld residual tests require statistical review.",
        "diagnostics.proportional_hazards"
      )
    }
  }
  if (identical(result$method, "causal_comparison")) {
    propensity <- result$diagnostics$propensity %||% list()
    max_smd <- propensity$max_absolute_smd_after %||% Inf
    extreme <- propensity$extreme_fraction %||% 1
    index[[length(index) + 1L]] <- diagnostic_item(
      "COVARIATE_BALANCE", if (is.finite(max_smd) && max_smd <= 0.1) "PASS" else "WARNING",
      "Maximum absolute standardized mean difference after weighting.", "diagnostics.propensity.max_absolute_smd_after"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "POSITIVITY", if (is.finite(extreme) && extreme <= 0.01) "PASS" else "WARNING",
      "Fraction of propensity scores outside 0.01 to 0.99.", "diagnostics.propensity.extreme_fraction"
    )
  }
  if (identical(result$method, "prediction_validation")) {
    index[[length(index) + 1L]] <- diagnostic_item(
      "CALIBRATION_REQUIRED", if (length(result$artifacts$figures$calibration %||% list())) "PASS" else "BLOCK",
      "Prediction validation includes calibration rather than discrimination alone.", "artifacts.figures.calibration"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "DATASET_FLOW", "REVIEW",
      "Confirm that the manuscript reports development and validation cohort flow with counts.",
      "diagnostics.model.prediction_origin"
    )
  }
  if (identical(result$method, "temporal_logistic_prediction")) {
    model <- result$diagnostics$model %||% list()
    index[[length(index) + 1L]] <- diagnostic_item(
      "MODEL_CONVERGENCE", if (isTRUE(model$baseline_converged) && isTRUE(model$minimal_converged)) "PASS" else "BLOCK",
      "Both prespecified logistic models converged with finite coefficients.", "diagnostics.model"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "VALIDATION_ONLY_BOOTSTRAP", if (identical(model$bootstrap_scope, "validation_only_fixed_model")) "PASS" else "BLOCK",
      "Uncertainty resamples the validation set without refitting or recalibration.", "diagnostics.model.bootstrap_scope"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "INFLUENCE_DIAGNOSTICS", if (!is.null(result$diagnostics$influence)) "PASS" else "BLOCK",
      "Cook distance and leverage summaries are available for review.", "diagnostics.influence"
    )
  }
  if (identical(result$method, "temporal_fine_gray_prediction")) {
    model <- result$diagnostics$model %||% list()
    index[[length(index) + 1L]] <- diagnostic_item(
      "MODEL_CONVERGENCE", if (isTRUE(model$converged) && isTRUE(model$finite_coefficients) && isTRUE(model$finite_variance)) "PASS" else "BLOCK",
      "The single prespecified Fine-Gray PILOT model converged with finite estimates.", "diagnostics.model"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "ABSOLUTE_RISK_COMPUTABILITY", if (isTRUE(model$absolute_risk_computable) && isTRUE(model$finite_absolute_risks)) "PASS" else "BLOCK",
      "Fixed-horizon Fine-Gray absolute risks are finite and computable.", "diagnostics.model.absolute_risk_computable"
    )
    index[[length(index) + 1L]] <- diagnostic_item(
      "OUTCOME_OBSERVATION_BOUNDARY", "WARNING",
      "Outcome-unobserved rows are excluded rather than treated as negative; formal target-population inference remains out of scope.", "diagnostics.model.outcome_observation_handling"
    )
  }
  index
}

normalize_result_for_review <- function(result) {
  result$warnings <- lapply(result$warnings %||% list(), function(warning) list(
    code = warning$code %||% "UNSPECIFIED_WARNING",
    severity = warning$severity %||% "WARNING",
    message = warning$message %||% "",
    evidence = warning$evidence %||% list()
  ))
  result$diagnostic_index <- build_diagnostic_index(result)
  if (!length(result$sensitivities)) {
    result$sensitivities <- list(status = "NOT_REQUESTED", analyses = list())
  }
  result
}
