fit_generic_regression_once <- function(data, analysis) {
  formula <- model_formula(analysis)
  family <- analysis$model_family
  if (identical(family, "ordinal")) {
    data[[analysis$outcome]] <- ordered(data[[analysis$outcome]], levels = unlist(analysis$outcome_order, use.names = FALSE))
    fit <- MASS::polr(formula, data = data, Hess = TRUE, method = "logistic", control = list(reltol = 1e-12, maxit = 1000L))
    return(list(fit = fit, vcov = stats::vcov(fit), variance_method = "model-based", converged = isTRUE(fit$convergence == 0L)))
  }
  if (identical(family, "negative_binomial")) {
    fit <- MASS::glm.nb(formula, data = data, control = stats::glm.control(maxit = 100))
  } else {
    glm_family <- switch(
      family,
      gaussian = stats::gaussian(link = "identity"),
      binomial = stats::binomial(link = "logit"),
      poisson = stats::poisson(link = "log"),
      stop(sprintf("Unsupported model_family: %s", family), call. = FALSE)
    )
    method <- if (identical(analysis$estimator %||% "maximum_likelihood", "bias_reduced")) brglm2::brglmFit else "glm.fit"
    fit <- stats::glm(formula, data = data, family = glm_family, method = method, control = stats::glm.control(maxit = 100))
  }
  vcov <- robust_model_vcov(fit, data, analysis$cluster_id %||% NULL)
  variance_method <- if (!is.null(analysis$cluster_id) && nzchar(analysis$cluster_id)) {
    paste("cluster-robust HC1 by", analysis$cluster_id)
  } else {
    "heteroskedasticity-robust HC0"
  }
  list(fit = fit, vcov = vcov, variance_method = variance_method, converged = isTRUE(fit$converged))
}

generic_measure <- function(family) {
  switch(
    family,
    gaussian = "mean_difference",
    binomial = "odds_ratio",
    poisson = "rate_ratio",
    negative_binomial = "rate_ratio",
    ordinal = "proportional_odds_ratio"
  )
}

standardized_prediction_once <- function(fit, variance, data, analysis, value) {
  newdata <- data
  newdata[[analysis$exposure]] <- value
  design <- stats::model.matrix(stats::delete.response(stats::terms(fit)), newdata)
  beta <- stats::coef(fit)
  beta <- beta[is.finite(beta)]
  design <- design[, names(beta), drop = FALSE]
  variance <- variance[names(beta), names(beta), drop = FALSE]
  eta <- as.vector(design %*% beta)
  family <- analysis$model_family
  inverse <- switch(family, gaussian = identity, binomial = stats::plogis, poisson = exp, negative_binomial = exp)
  derivative <- switch(family, gaussian = rep(1, length(eta)), binomial = stats::plogis(eta) * (1 - stats::plogis(eta)), poisson = exp(eta), negative_binomial = exp(eta))
  prediction <- inverse(eta)
  gradient <- colMeans(design * derivative)
  list(
    estimate = mean(prediction),
    variance = drop(t(gradient) %*% variance %*% gradient),
    gradient = gradient
  )
}

pool_standardized_contrasts <- function(fits, vcovs, datasets, analysis, values, confidence_level) {
  if (!identical(analysis$model_family, "binomial") || length(values) != 2L) {
    return(data.frame())
  }
  low_value <- values[[1L]]
  high_value <- values[[2L]]
  per_fit <- lapply(seq_along(fits), function(i) {
    low <- standardized_prediction_once(fits[[i]], vcovs[[i]], datasets[[i]], analysis, low_value)
    high <- standardized_prediction_once(fits[[i]], vcovs[[i]], datasets[[i]], analysis, high_value)
    risk_difference_gradient <- high$gradient - low$gradient
    log_risk_ratio_gradient <- high$gradient / high$estimate - low$gradient / low$estimate
    list(
      risk_difference = high$estimate - low$estimate,
      risk_difference_variance = drop(
        t(risk_difference_gradient) %*% vcovs[[i]] %*% risk_difference_gradient
      ),
      log_risk_ratio = log(high$estimate / low$estimate),
      log_risk_ratio_variance = drop(
        t(log_risk_ratio_gradient) %*% vcovs[[i]] %*% log_risk_ratio_gradient
      )
    )
  })
  pool_one <- function(estimate_name, variance_name) {
    q <- vapply(per_fit, `[[`, numeric(1), estimate_name)
    u <- vapply(per_fit, `[[`, numeric(1), variance_name)
    m <- length(q)
    qbar <- mean(q)
    within <- mean(u)
    between <- if (m > 1L) stats::var(q) else 0
    list(estimate = qbar, standard_error = sqrt(within + (1 + 1 / m) * between))
  }
  risk_difference <- pool_one("risk_difference", "risk_difference_variance")
  log_risk_ratio <- pool_one("log_risk_ratio", "log_risk_ratio_variance")
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  data.frame(
    contrast = rep(sprintf("%s vs %s", high_value, low_value), 2L),
    estimate_type = c("risk_difference", "risk_ratio"),
    estimate = c(risk_difference$estimate, exp(log_risk_ratio$estimate)),
    ci_low = c(
      risk_difference$estimate - z * risk_difference$standard_error,
      exp(log_risk_ratio$estimate - z * log_risk_ratio$standard_error)
    ),
    ci_high = c(
      risk_difference$estimate + z * risk_difference$standard_error,
      exp(log_risk_ratio$estimate + z * log_risk_ratio$standard_error)
    ),
    standard_error = c(risk_difference$standard_error, log_risk_ratio$standard_error),
    confidence_level = rep(confidence_level, 2L),
    imputations = rep(length(fits), 2L),
    stringsAsFactors = FALSE
  )
}

pool_standardized_predictions <- function(fits, vcovs, datasets, analysis, values, confidence_level) {
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  do.call(rbind, lapply(values, function(value) {
    estimates <- lapply(seq_along(fits), function(i) standardized_prediction_once(fits[[i]], vcovs[[i]], datasets[[i]], analysis, value))
    q <- vapply(estimates, `[[`, numeric(1), "estimate")
    u <- vapply(estimates, `[[`, numeric(1), "variance")
    m <- length(q); qbar <- mean(q); within <- mean(u); between <- if (m > 1L) stats::var(q) else 0
    se <- sqrt(within + (1 + 1 / m) * between)
    bounds <- if (identical(analysis$model_family, "binomial")) c(0, 1) else c(-Inf, Inf)
    data.frame(
      exposure_value = value, estimate = qbar,
      ci_low = max(bounds[[1L]], qbar - z * se), ci_high = min(bounds[[2L]], qbar + z * se),
      standard_error = se, confidence_level = confidence_level, stringsAsFactors = FALSE
    )
  }))
}

plot_standardized_predictions <- function(rows, analysis) {
  ggplot2::ggplot(rows, ggplot2::aes(x = exposure_value, y = estimate)) +
    ggplot2::geom_ribbon(ggplot2::aes(ymin = ci_low, ymax = ci_high), fill = publication_palette[[1L]], alpha = 0.14) +
    ggplot2::geom_line(color = publication_palette[[1L]], linewidth = 0.9) +
    ggplot2::geom_point(shape = 21, fill = publication_palette[[1L]], color = "black", size = 2) +
    publication_theme() + ggplot2::labs(
      x = analysis$exposure_label %||% analysis$exposure,
      y = switch(analysis$model_family, gaussian = "Model-standardized mean", binomial = "Model-standardized risk", poisson = "Model-standardized rate", negative_binomial = "Model-standardized rate")
    )
}

run_generic_regression <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)

  analysis <- task$analysis
  required <- unique(c(analysis$outcome, model_terms(analysis), analysis$cluster_id))
  required <- required[!is.na(required) & nzchar(required)]
  prepared <- prepare_regression_datasets(data, analysis, required)
  fits <- lapply(prepared$datasets, fit_generic_regression_once, analysis = analysis)
  if (!all(vapply(fits, `[[`, logical(1), "converged"))) {
    result$status <- "BLOCKED"
    result$warnings[[1L]] <- list(
      code = "MODEL_NONCONVERGENCE", severity = "BLOCK",
      message = "At least one prespecified regression model did not converge; no alternative model was selected."
    )
    return(result)
  }
  beta_fits <- lapply(fits, `[[`, "fit")
  vcovs <- lapply(fits, `[[`, "vcov")
  family <- analysis$model_family
  exponentiate <- family %in% c("binomial", "poisson", "negative_binomial", "ordinal")
  measure <- generic_measure(family)
  coefficients <- if (length(beta_fits) == 1L) {
    coefficient_rows(
      stats::coef(beta_fits[[1L]]), vcovs[[1L]], analysis$confidence_level %||% 0.95,
      exponentiate, measure, analysis$multiplicity %||% "none"
    )
  } else {
    pool_model_coefficients(
      beta_fits, vcovs, analysis$confidence_level %||% 0.95,
      exponentiate, measure, analysis$multiplicity %||% "none"
    )
  }
  crude_analysis <- analysis
  crude_analysis$covariates <- list()
  crude_analysis$effect_modifiers <- list()
  crude_fits <- lapply(prepared$datasets, fit_generic_regression_once, analysis = crude_analysis)
  crude_models <- lapply(crude_fits, `[[`, "fit")
  crude_vcovs <- lapply(crude_fits, `[[`, "vcov")
  unadjusted <- if (length(crude_models) == 1L) {
    coefficient_rows(stats::coef(crude_models[[1L]]), crude_vcovs[[1L]], analysis$confidence_level %||% 0.95, exponentiate, measure, "none")
  } else {
    pool_model_coefficients(crude_models, crude_vcovs, analysis$confidence_level %||% 0.95, exponentiate, measure, "none")
  }
  unadjusted <- unadjusted[startsWith(unadjusted$term, analysis$exposure), , drop = FALSE]
  primary <- coefficients[coefficients$term == analysis$exposure | startsWith(coefficients$term, paste0(analysis$exposure, ":")), , drop = FALSE]
  if (!nrow(primary)) primary <- coefficients[startsWith(coefficients$term, analysis$exposure), , drop = FALSE]

  result$status <- "COMPLETE"
  result$counts <- list(
    input_n = nrow(data), analysis_n = nrow(prepared$datasets[[1L]]),
    excluded_missing_n = nrow(data) - nrow(prepared$datasets[[1L]]),
    model_parameters = sum(is.finite(stats::coef(beta_fits[[1L]]))),
    aliased_parameters = sum(!is.finite(stats::coef(beta_fits[[1L]]))),
    imputations = length(beta_fits)
  )
  standardized_values <- unlist(analysis$standardized_values %||% list(), use.names = FALSE)
  standardized <- if (length(standardized_values) && !identical(family, "ordinal")) {
    pool_standardized_predictions(beta_fits, vcovs, prepared$datasets, analysis, standardized_values, analysis$confidence_level %||% 0.95)
  } else data.frame()
  standardized_contrasts <- pool_standardized_contrasts(
    beta_fits, vcovs, prepared$datasets, analysis, standardized_values,
    analysis$confidence_level %||% 0.95
  )
  result$estimates <- list(
    primary = as_result_rows(primary), coefficients = as_result_rows(coefficients),
    unadjusted = as_result_rows(unadjusted),
    standardized_predictions = if (nrow(standardized)) as_result_rows(standardized) else list(),
    standardized_contrasts = if (nrow(standardized_contrasts)) as_result_rows(standardized_contrasts) else list()
  )
  result$diagnostics$model <- list(
    family = family, estimator = analysis$estimator %||% "maximum_likelihood",
    converged = TRUE, formula = paste(deparse(stats::formula(beta_fits[[1L]])), collapse = " "),
    variance_method = fits[[1L]]$variance_method,
    aliased_terms = as.list(names(stats::coef(beta_fits[[1L]]))[!is.finite(stats::coef(beta_fits[[1L]]))]),
    multiplicity = analysis$multiplicity %||% "none"
  )
  result$diagnostics$missing_data <- prepared$diagnostics
  result$artifacts$tables$model_coefficients <- write_csv_artifact(
    coefficients, output_dir, "model_coefficients.csv", "prespecified regression coefficient table"
  )
  result$artifacts$tables$unadjusted_coefficients <- write_csv_artifact(
    unadjusted, output_dir, "unadjusted_coefficients.csv", "unadjusted exposure association"
  )
  if (nrow(primary)) {
    figure_rows <- coefficients[coefficients$term != "(Intercept)", , drop = FALSE]
    figure <- effect_forest_plot(
      figure_rows,
      switch(family, gaussian = "Adjusted coefficient (95% CI)", binomial = "Adjusted odds ratio (95% CI)",
             poisson = "Adjusted rate ratio (95% CI)", negative_binomial = "Adjusted rate ratio (95% CI)",
             ordinal = "Adjusted proportional odds ratio (95% CI)"),
      if (exponentiate) 1 else 0
    )
    artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "regression_effects", task, 7, max(3.2, 0.42 * nrow(figure_rows) + 1.4))
    artifact$source <- "prespecified adjusted regression model"
    artifact$caption <- sprintf(
      "Adjusted effects from the prespecified %s regression model. Points show estimates and horizontal lines show %.0f%% confidence intervals (N = %d); multiplicity adjustment: %s.",
      gsub("_", " ", family), 100 * (analysis$confidence_level %||% 0.95), result$counts$analysis_n,
      analysis$multiplicity %||% "none"
    )
    result$artifacts$figures$regression_effects <- artifact
  }
  if (nrow(standardized)) {
    result$artifacts$tables$standardized_predictions <- write_csv_artifact(
      standardized, output_dir, "standardized_predictions.csv", "model-standardized marginal predictions"
    )
    figure <- plot_standardized_predictions(standardized, analysis)
    artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "standardized_predictions", task, 7, 4.5)
    artifact$source <- "model-standardized marginal predictions"
    artifact$caption <- sprintf("Model-standardized outcome estimates across prespecified exposure values. Points show marginal estimates and the shaded band shows %.0f%% confidence intervals (N = %d).", 100 * (analysis$confidence_level %||% 0.95), result$counts$analysis_n)
    result$artifacts$figures$standardized_predictions <- artifact
  }
  if (nrow(standardized_contrasts)) {
    result$artifacts$tables$standardized_contrasts <- write_csv_artifact(
      standardized_contrasts, output_dir, "standardized_contrasts.csv",
      "pooled marginal risk difference and risk ratio"
    )
  }
  result
}
