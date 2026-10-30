longitudinal_fixed_formula <- function(analysis) {
  terms <- c(
    analysis$exposure, analysis$repeated_time,
    paste(analysis$exposure, analysis$repeated_time, sep = ":"),
    unlist(analysis$covariates %||% list(), use.names = FALSE)
  )
  stats::reformulate(unique(terms), response = analysis$outcome)
}

fit_longitudinal_once <- function(data, analysis) {
  fixed <- longitudinal_fixed_formula(analysis)
  engine <- analysis$longitudinal_engine
  if (identical(engine, "gee")) {
    family <- switch(
      analysis$outcome_type,
      continuous = stats::gaussian(), binary = stats::binomial(), count = stats::poisson(),
      stop("GEE supports continuous, binary, or count outcomes.", call. = FALSE)
    )
    corstr <- switch(analysis$correlation %||% "exchangeable", independence = "independence", exchangeable = "exchangeable", ar1 = "ar1")
    ordered_data <- data[order(data[[analysis$subject_id]], data[[analysis$repeated_time]]), , drop = FALSE]
    ordered_data$.clin_id <- match(ordered_data[[analysis$subject_id]], unique(ordered_data[[analysis$subject_id]]))
    fit <- geepack::geeglm(
      fixed, id = .clin_id, data = ordered_data,
      family = family, corstr = corstr, std.err = "san.se"
    )
    beta <- stats::coef(fit)
    variance <- fit$geese$vbeta
    dimnames(variance) <- list(names(beta), names(beta))
    return(list(fit = fit, beta = beta, vcov = variance, data = ordered_data, fixed = fixed, family = family$family, variance_method = "GEE sandwich"))
  }
  random <- if (isTRUE(analysis$random_slope)) {
    sprintf("(1 + %s | %s)", analysis$repeated_time, analysis$subject_id)
  } else {
    sprintf("(1 | %s)", analysis$subject_id)
  }
  formula <- stats::as.formula(sprintf("%s + %s", paste(deparse(fixed), collapse = " "), random))
  if (identical(engine, "lmm")) {
    fit <- lme4::lmer(formula, data = data, REML = FALSE)
    return(list(fit = fit, beta = lme4::fixef(fit), vcov = as.matrix(stats::vcov(fit)), data = data, fixed = fixed, family = "gaussian", variance_method = "model-based"))
  }
  family <- switch(
    analysis$outcome_type,
    binary = stats::binomial(), count = stats::poisson(),
    stop("GLMM supports binary or count outcomes.", call. = FALSE)
  )
  fit <- lme4::glmer(formula, data = data, family = family)
  list(fit = fit, beta = lme4::fixef(fit), vcov = as.matrix(stats::vcov(fit)), data = data, fixed = fixed, family = family$family, variance_method = "model-based")
}

typical_value <- function(x) {
  if (is.numeric(x)) return(stats::median(x, na.rm = TRUE))
  if (is.factor(x)) return(factor(levels(x)[[1L]], levels = levels(x)))
  sort(unique(stats::na.omit(x)))[[1L]]
}

longitudinal_prediction_grid <- function(fitted, analysis, confidence_level) {
  data <- fitted$data
  time_values <- seq(min(data[[analysis$repeated_time]], na.rm = TRUE), max(data[[analysis$repeated_time]], na.rm = TRUE), length.out = 60L)
  groups <- sort(unique(data[[analysis$exposure]]))
  grid <- expand.grid(.clin_time = time_values, .clin_group = groups, KEEP.OUT.ATTRS = FALSE, stringsAsFactors = FALSE)
  names(grid)[names(grid) == ".clin_time"] <- analysis$repeated_time
  names(grid)[names(grid) == ".clin_group"] <- analysis$exposure
  for (variable in unlist(analysis$covariates %||% list(), use.names = FALSE)) grid[[variable]] <- typical_value(data[[variable]])
  if (is.factor(data[[analysis$exposure]])) grid[[analysis$exposure]] <- factor(grid[[analysis$exposure]], levels = levels(data[[analysis$exposure]]))
  design <- stats::model.matrix(stats::delete.response(stats::terms(fitted$fixed)), grid)
  design <- design[, names(fitted$beta), drop = FALSE]
  eta <- as.vector(design %*% fitted$beta)
  se <- sqrt(rowSums((design %*% fitted$vcov) * design))
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  transform <- if (identical(fitted$family, "gaussian")) identity else if (identical(fitted$family, "binomial")) stats::plogis else exp
  grid$estimate <- transform(eta)
  grid$ci_low <- transform(eta - z * se)
  grid$ci_high <- transform(eta + z * se)
  grid$plot_time <- grid[[analysis$repeated_time]]
  grid$group <- survival_group_labels(grid[[analysis$exposure]], analysis)
  grid
}

plot_longitudinal_trajectory <- function(grid, analysis) {
  ggplot2::ggplot(grid, ggplot2::aes(x = plot_time, y = estimate, color = group, linetype = group, fill = group)) +
    ggplot2::geom_ribbon(ggplot2::aes(ymin = ci_low, ymax = ci_high), alpha = 0.12, color = NA) +
    ggplot2::geom_line(linewidth = 0.9) +
    ggplot2::scale_color_manual(values = publication_palette) +
    ggplot2::scale_fill_manual(values = publication_palette) +
    ggplot2::scale_linetype_manual(values = c("solid", "22", "42", "13")) +
    publication_theme() +
    ggplot2::labs(
      x = analysis$time_label %||% analysis$repeated_time,
      y = analysis$outcome_label %||% paste("Model-estimated", analysis$outcome),
      color = NULL, fill = NULL, linetype = NULL
    )
}

run_longitudinal_model <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)
  analysis <- task$analysis
  required <- unique(c(analysis$outcome, analysis$exposure, analysis$subject_id, analysis$repeated_time, unlist(analysis$covariates %||% list(), use.names = FALSE)))
  model_data <- data[stats::complete.cases(data[required]), , drop = FALSE]
  fitted <- fit_longitudinal_once(model_data, analysis)
  confidence_level <- analysis$confidence_level %||% 0.95
  exponentiate <- analysis$outcome_type %in% c("binary", "count")
  measure <- switch(analysis$outcome_type, continuous = "mean_difference", binary = "odds_ratio", count = "rate_ratio")
  rows <- coefficient_rows(fitted$beta, fitted$vcov, confidence_level, exponentiate, measure, analysis$multiplicity %||% "none")
  interaction_term <- paste(analysis$exposure, analysis$repeated_time, sep = ":")
  reverse_interaction <- paste(analysis$repeated_time, analysis$exposure, sep = ":")
  primary <- rows[rows$term %in% c(interaction_term, reverse_interaction) | startsWith(rows$term, interaction_term) | startsWith(rows$term, reverse_interaction), , drop = FALSE]
  grid <- longitudinal_prediction_grid(fitted, analysis, confidence_level)

  result$status <- "COMPLETE"
  result$counts <- list(
    input_rows = nrow(data), analysis_rows = nrow(model_data), subjects = length(unique(model_data[[analysis$subject_id]])),
    excluded_missing_rows = nrow(data) - nrow(model_data), model_parameters = length(fitted$beta)
  )
  result$estimates <- list(primary = as_result_rows(primary), coefficients = as_result_rows(rows), trajectories = as_result_rows(grid))
  result$diagnostics$model <- list(
    engine = analysis$longitudinal_engine, family = fitted$family,
    formula = paste(deparse(stats::formula(fitted$fit)), collapse = " "),
    variance_method = fitted$variance_method,
    singular = if (inherits(fitted$fit, "merMod")) lme4::isSingular(fitted$fit, tol = 1e-4) else NULL
  )
  if (isTRUE(result$diagnostics$model$singular)) {
    result$warnings[[1L]] <- list(code = "SINGULAR_RANDOM_EFFECTS", severity = "WARNING", message = "The prespecified mixed model has a singular random-effects fit; no simpler model was substituted.")
  }
  result$artifacts$tables$model_coefficients <- write_csv_artifact(rows, output_dir, "model_coefficients.csv", "longitudinal model coefficients")
  result$artifacts$tables$trajectory_estimates <- write_csv_artifact(grid, output_dir, "trajectory_estimates.csv", "model-estimated longitudinal trajectories")
  figure <- plot_longitudinal_trajectory(grid, analysis)
  artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "longitudinal_trajectory", task, 7, 4.6)
  artifact$source <- "prespecified longitudinal model marginal predictions"
  artifact$caption <- sprintf(
    "Model-estimated longitudinal outcome trajectories by exposure group. Lines show marginal predictions and shaded bands show %.0f%% confidence intervals from the prespecified %s model (N = %d subjects).",
    100 * confidence_level, toupper(analysis$longitudinal_engine), result$counts$subjects
  )
  result$artifacts$figures$longitudinal_trajectory <- artifact
  result
}
