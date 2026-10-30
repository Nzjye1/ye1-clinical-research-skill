transform_exposure <- function(x, transform) {
  switch(transform, identity = x, log2 = log2(x), stop(sprintf("Unsupported transform: %s", transform)))
}

modified_poisson_standardized_risk <- function(fit, vcov, model_data, exposure_name, transform, value, confidence_level) {
  newdata <- model_data
  newdata[[exposure_name]] <- value
  newdata$.clin_exposure <- transform_exposure(newdata[[exposure_name]], transform)
  design <- stats::model.matrix(stats::delete.response(stats::terms(fit)), newdata)
  beta <- stats::coef(fit)
  design <- design[, names(beta), drop = FALSE]
  predicted <- as.vector(exp(design %*% beta))
  gradient <- colMeans(design * predicted)
  se <- sqrt(drop(t(gradient) %*% vcov %*% gradient))
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  risk <- mean(predicted)
  list(
    exposure_value = as.numeric(value),
    risk = risk,
    ci_low = max(0, risk - z * se),
    ci_high = min(1, risk + z * se),
    standard_error = se
  )
}

plot_standardized_risks <- function(risks, exposure_label) {
  plot_data <- do.call(rbind, lapply(risks, as.data.frame))
  p <- ggplot2::ggplot(plot_data, ggplot2::aes(x = exposure_value, y = risk)) +
    ggplot2::geom_ribbon(ggplot2::aes(ymin = ci_low, ymax = ci_high), fill = publication_palette[[1L]], alpha = 0.16) +
    ggplot2::geom_line(color = publication_palette[[1L]], linewidth = 0.9) +
    ggplot2::geom_point(color = publication_palette[[1L]], size = 1.8) +
    ggplot2::scale_y_continuous(labels = scales::label_percent(accuracy = 1), expand = ggplot2::expansion(mult = c(0, 0.05))) +
    publication_theme() +
    ggplot2::theme(legend.position = "none") +
    ggplot2::labs(x = exposure_label, y = "Model-standardized risk", title = NULL)
  p
}

run_modified_poisson <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)

  set.seed(task$seed %||% 20260718L)
  analysis <- task$analysis
  covariates <- unlist(analysis$covariates %||% list(), use.names = FALSE)
  required <- unique(c(analysis$outcome, analysis$exposure, analysis$cluster_id, covariates))
  required <- required[!is.na(required) & nzchar(required)]
  model_data <- data[stats::complete.cases(data[required]), , drop = FALSE]
  transform <- analysis$exposure_transform %||% "identity"
  model_data$.clin_exposure <- transform_exposure(model_data[[analysis$exposure]], transform)
  formula <- stats::reformulate(c(".clin_exposure", covariates), response = analysis$outcome)
  fit <- stats::glm(formula, data = model_data, family = stats::poisson(link = "log"))

  if (!is.null(analysis$cluster_id) && nzchar(analysis$cluster_id)) {
    # HC1 plus cluster-count adjustment reproduces the finite-sample
    # correction used by the frozen statsmodels reference implementation.
    robust_vcov <- sandwich::vcovCL(
      fit,
      cluster = model_data[[analysis$cluster_id]],
      type = "HC1",
      cadjust = TRUE
    )
    variance_method <- sprintf("cluster-robust HC1 with cluster adjustment by %s", analysis$cluster_id)
  } else {
    robust_vcov <- sandwich::vcovHC(fit, type = "HC0")
    variance_method <- "heteroskedasticity-robust HC0"
  }

  beta <- stats::coef(fit)[[".clin_exposure"]]
  se <- sqrt(robust_vcov[".clin_exposure", ".clin_exposure"])
  confidence_level <- analysis$confidence_level %||% 0.95
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  rr <- exp(beta)
  primary <- list(
    term = analysis$exposure,
    contrast = if (identical(transform, "log2")) "per doubling" else "per one-unit increase",
    estimate_type = "risk_ratio",
    estimate = rr,
    ci_low = exp(beta - z * se),
    ci_high = exp(beta + z * se),
    standard_error_log = se,
    p_value = 2 * stats::pnorm(-abs(beta / se)),
    confidence_level = confidence_level,
    variance_method = variance_method
  )

  standardized_values <- unlist(analysis$standardized_values %||% list(), use.names = FALSE)
  standardized_risks <- lapply(
    standardized_values,
    function(value) modified_poisson_standardized_risk(
      fit, robust_vcov, model_data, analysis$exposure, transform, value, confidence_level
    )
  )

  fitted <- stats::fitted(fit)
  result$status <- "COMPLETE"
  result$counts <- list(
    input_n = nrow(data),
    analysis_n = nrow(model_data),
    excluded_missing_n = nrow(data) - nrow(model_data),
    events = sum(model_data[[analysis$outcome]] == 1),
    clusters = if (!is.null(analysis$cluster_id)) length(unique(model_data[[analysis$cluster_id]])) else NULL,
    model_parameters = length(stats::coef(fit))
  )
  result$estimates <- list(primary = primary, standardized_risks = standardized_risks)
  result$diagnostics$model <- list(
    converged = isTRUE(fit$converged),
    fitted_probability_max = max(fitted),
    fitted_probability_above_one_n = sum(fitted > 1),
    events_per_parameter = result$counts$events / result$counts$model_parameters,
    formula = paste(deparse(formula), collapse = " ")
  )
  if (any(fitted > 1)) {
    result$warnings[[length(result$warnings) + 1L]] <- list(
      code = "FITTED_RISK_ABOVE_ONE",
      severity = "WARNING",
      message = "Modified Poisson produced fitted risks above 1; inspect model specification and standardized risks."
    )
  }

  if (length(standardized_risks)) {
    dir.create(file.path(output_dir, "figures"), recursive = TRUE, showWarnings = FALSE)
    figure <- plot_standardized_risks(
      standardized_risks,
      analysis$exposure_label %||% analysis$exposure
    )
    artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "standardized_risk", task, 7, 4.5)
    artifact$source <- "model-standardized marginal risks with delta-method confidence intervals"
    artifact$caption <- sprintf(
      "Model-standardized outcome risk across prespecified exposure values. Points show marginal risks and the shaded band shows %.0f%% delta-method confidence intervals (N = %d).",
      100 * confidence_level, result$counts$analysis_n
    )
    result$artifacts$figures$standardized_risk <- artifact
  }
  result
}
