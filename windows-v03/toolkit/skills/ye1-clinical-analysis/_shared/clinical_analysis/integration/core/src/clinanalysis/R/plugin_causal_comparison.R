causal_design_matrix <- function(data, variables) {
  formula <- stats::reformulate(variables, intercept = FALSE)
  stats::model.matrix(formula, data = data)
}

weighted_mean_variance <- function(x, w) {
  keep <- is.finite(x) & is.finite(w) & w > 0
  x <- x[keep]; w <- w[keep]
  mean <- sum(w * x) / sum(w)
  variance <- sum(w * (x - mean)^2) / sum(w)
  c(mean = mean, variance = variance)
}

balance_table <- function(data, treatment, covariates, weights) {
  design <- causal_design_matrix(data, covariates)
  a <- data[[treatment]]
  rows <- lapply(seq_len(ncol(design)), function(j) {
    x <- design[, j]
    unweighted_1 <- weighted_mean_variance(x[a == 1], rep(1, sum(a == 1)))
    unweighted_0 <- weighted_mean_variance(x[a == 0], rep(1, sum(a == 0)))
    weighted_1 <- weighted_mean_variance(x[a == 1], weights[a == 1])
    weighted_0 <- weighted_mean_variance(x[a == 0], weights[a == 0])
    pooled_before <- sqrt((unweighted_1[["variance"]] + unweighted_0[["variance"]]) / 2)
    pooled_after <- sqrt((weighted_1[["variance"]] + weighted_0[["variance"]]) / 2)
    data.frame(
      covariate = colnames(design)[[j]],
      smd_before = if (pooled_before > 0) (unweighted_1[["mean"]] - unweighted_0[["mean"]]) / pooled_before else 0,
      smd_after = if (pooled_after > 0) (weighted_1[["mean"]] - weighted_0[["mean"]]) / pooled_after else 0,
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

causal_weights <- function(a, ps, estimand, stabilized) {
  prevalence <- mean(a)
  weights <- switch(
    estimand,
    ATE = if (isTRUE(stabilized)) ifelse(a == 1, prevalence / ps, (1 - prevalence) / (1 - ps)) else ifelse(a == 1, 1 / ps, 1 / (1 - ps)),
    ATT = ifelse(a == 1, 1, ps / (1 - ps)),
    ATO = ifelse(a == 1, 1 - ps, ps),
    stop("Unsupported causal estimand.", call. = FALSE)
  )
  weights
}

fit_propensity <- function(data, analysis) {
  formula <- stats::reformulate(unlist(analysis$propensity_covariates, use.names = FALSE), response = analysis$exposure)
  fit <- stats::glm(formula, data = data, family = stats::binomial())
  if (!isTRUE(fit$converged) || any(!is.finite(stats::coef(fit)))) stop("The prespecified propensity model failed to converge.", call. = FALSE)
  ps <- pmin(pmax(stats::fitted(fit), 1e-6), 1 - 1e-6)
  list(fit = fit, ps = ps, formula = formula)
}

truncate_weights <- function(weights, quantiles) {
  limits <- stats::quantile(weights, probs = quantiles, na.rm = TRUE, names = FALSE)
  list(weights = pmin(pmax(weights, limits[[1L]]), limits[[2L]]), limits = limits)
}

causal_point_estimate <- function(data, analysis) {
  propensity <- fit_propensity(data, analysis)
  a <- data[[analysis$exposure]]
  y <- data[[analysis$outcome]]
  raw_weights <- causal_weights(a, propensity$ps, analysis$estimand, analysis$stabilized_weights %||% TRUE)
  truncation <- truncate_weights(raw_weights, unlist(analysis$truncation_quantiles %||% list(0.01, 0.99), use.names = FALSE))
  weights <- truncation$weights
  estimator <- analysis$causal_estimator %||% "weighting"
  if (identical(estimator, "aipw")) {
    covariates <- unlist(analysis$outcome_covariates %||% analysis$propensity_covariates, use.names = FALSE)
    formula <- stats::reformulate(c(analysis$exposure, covariates), response = analysis$outcome)
    family <- if (identical(analysis$outcome_type, "binary")) stats::binomial() else stats::gaussian()
    outcome_fit <- stats::glm(formula, data = data, family = family)
    treated <- data; treated[[analysis$exposure]] <- 1
    control <- data; control[[analysis$exposure]] <- 0
    m1 <- stats::predict(outcome_fit, newdata = treated, type = "response")
    m0 <- stats::predict(outcome_fit, newdata = control, type = "response")
    influence_value <- m1 - m0 + a * (y - m1) / propensity$ps - (1 - a) * (y - m0) / (1 - propensity$ps)
    effect <- mean(influence_value)
  } else {
    treated_mean <- stats::weighted.mean(y[a == 1], weights[a == 1])
    control_mean <- stats::weighted.mean(y[a == 0], weights[a == 0])
    effect <- treated_mean - control_mean
  }
  treated_mean <- stats::weighted.mean(y[a == 1], weights[a == 1])
  control_mean <- stats::weighted.mean(y[a == 0], weights[a == 0])
  c(effect = effect, treated_mean = treated_mean, control_mean = control_mean, risk_ratio = if (control_mean > 0) treated_mean / control_mean else NA_real_)
}

plot_love <- function(balance) {
  plot_data <- rbind(
    data.frame(covariate = balance$covariate, sample = "Before weighting", smd = abs(balance$smd_before)),
    data.frame(covariate = balance$covariate, sample = "After weighting", smd = abs(balance$smd_after))
  )
  order <- balance$covariate[order(abs(balance$smd_before))]
  plot_data$covariate <- factor(plot_data$covariate, levels = order)
  ggplot2::ggplot(plot_data, ggplot2::aes(x = smd, y = covariate, color = sample, shape = sample)) +
    ggplot2::geom_vline(xintercept = 0.1, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_point(size = 2.2) +
    ggplot2::scale_color_manual(values = c("Before weighting" = publication_palette[[2L]], "After weighting" = publication_palette[[1L]])) +
    ggplot2::scale_shape_manual(values = c("Before weighting" = 17, "After weighting" = 16)) +
    publication_theme() +
    ggplot2::labs(x = "Absolute standardized mean difference", y = NULL, color = NULL, shape = NULL)
}

run_causal_comparison <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)
  analysis <- task$analysis
  required <- unique(c(analysis$outcome, analysis$exposure, unlist(analysis$propensity_covariates, use.names = FALSE), unlist(analysis$outcome_covariates %||% list(), use.names = FALSE)))
  model_data <- data[stats::complete.cases(data[required]), , drop = FALSE]
  a <- model_data[[analysis$exposure]]
  if (!all(a %in% c(0, 1))) {
    result$status <- "BLOCKED"
    result$warnings[[1L]] <- list(code = "NON_BINARY_TREATMENT", severity = "BLOCK", message = "Causal comparison requires treatment coded 0/1.")
    return(result)
  }
  propensity <- fit_propensity(model_data, analysis)
  raw_weights <- causal_weights(a, propensity$ps, analysis$estimand, analysis$stabilized_weights %||% TRUE)
  truncation <- truncate_weights(raw_weights, unlist(analysis$truncation_quantiles %||% list(0.01, 0.99), use.names = FALSE))
  weights <- truncation$weights
  balance <- balance_table(model_data, analysis$exposure, unlist(analysis$propensity_covariates, use.names = FALSE), weights)
  point <- causal_point_estimate(model_data, analysis)
  set.seed(task$seed %||% 20260718L)
  replicates <- as.integer(analysis$bootstrap_replicates %||% 400L)
  boot <- replicate(replicates, {
    sampled <- model_data[sample.int(nrow(model_data), replace = TRUE), , drop = FALSE]
    tryCatch(causal_point_estimate(sampled, analysis), error = function(e) rep(NA_real_, 4L))
  })
  confidence_level <- analysis$confidence_level %||% 0.95
  alpha <- (1 - confidence_level) / 2
  effect_boot <- boot["effect", ]
  ci <- stats::quantile(effect_boot, probs = c(alpha, 1 - alpha), na.rm = TRUE, names = FALSE)
  se <- stats::sd(effect_boot, na.rm = TRUE)
  primary <- data.frame(
    term = analysis$exposure, estimand = analysis$estimand,
    measure = if (identical(analysis$outcome_type, "binary")) "risk_difference" else "mean_difference",
    estimate = unname(point[["effect"]]), ci_low = ci[[1L]], ci_high = ci[[2L]], standard_error = se,
    p_value = 2 * stats::pnorm(-abs(point[["effect"]] / se)), confidence_level = confidence_level,
    estimator = analysis$causal_estimator %||% "weighting", stringsAsFactors = FALSE
  )
  max_smd <- max(abs(balance$smd_after), na.rm = TRUE)
  ess <- function(w) sum(w)^2 / sum(w^2)
  positivity_extreme <- mean(propensity$ps < 0.01 | propensity$ps > 0.99)

  result$status <- "COMPLETE"
  result$counts <- list(
    input_n = nrow(data), analysis_n = nrow(model_data), treated_n = sum(a == 1), control_n = sum(a == 0),
    excluded_missing_n = nrow(data) - nrow(model_data)
  )
  result$estimates <- list(primary = as_result_rows(primary), weighted_means = list(treated = point[["treated_mean"]], control = point[["control_mean"]], risk_ratio = point[["risk_ratio"]]))
  result$diagnostics$propensity <- list(
    formula = paste(deparse(propensity$formula), collapse = " "),
    min = min(propensity$ps), max = max(propensity$ps), extreme_fraction = positivity_extreme,
    weight_min = min(weights), weight_max = max(weights), truncation_limits = as.list(unname(truncation$limits)),
    effective_sample_size = list(overall = ess(weights), treated = ess(weights[a == 1]), control = ess(weights[a == 0])),
    max_absolute_smd_after = max_smd, bootstrap_replicates = replicates
  )
  result$artifacts$tables$balance <- write_csv_artifact(balance, output_dir, "balance_diagnostics.csv", "covariate balance before and after weighting")
  result$artifacts$tables$causal_effect <- write_csv_artifact(primary, output_dir, "causal_effect.csv", "prespecified causal effect estimate")
  figure <- plot_love(balance)
  artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "love_plot", task, 7, max(3.4, 0.35 * nrow(balance) + 1.5))
  artifact$source <- "propensity-score balance diagnostics"
  artifact$caption <- sprintf("Covariate balance before and after %s weighting for the %s estimand. Points show absolute standardized mean differences; the dashed line marks 0.10 (N = %d).", analysis$estimand, analysis$estimand, result$counts$analysis_n)
  result$artifacts$figures$love_plot <- artifact
  if (positivity_extreme > 0.01 || max_smd > 0.1) {
    result$warnings[[length(result$warnings) + 1L]] <- list(
      code = "CAUSAL_DIAGNOSTIC_WARNING", severity = "WARNING",
      message = "Inspect positivity and post-weighting balance before interpreting the causal estimate.",
      evidence = list(extreme_propensity_fraction = positivity_extreme, max_absolute_smd_after = max_smd)
    )
  }
  result
}
