format_number_for_formula <- function(x) {
  paste(format(x, digits = 17, scientific = FALSE, trim = TRUE), collapse = ",")
}

survival_spline_specs <- function(data, variables, df) {
  specs <- list()
  for (variable in variables) {
    observed <- data[[variable]]
    reference <- observed
    reference[is.na(reference)] <- stats::median(reference, na.rm = TRUE)
    basis <- splines::ns(reference, df = df)
    specs[[variable]] <- list(
      knots = as.numeric(attr(basis, "knots")),
      boundary_knots = as.numeric(attr(basis, "Boundary.knots"))
    )
  }
  specs
}

survival_model_formula <- function(analysis, event, spline_specs) {
  covariates <- unlist(analysis$covariates %||% list(), use.names = FALSE)
  spline_variables <- unlist(analysis$spline_covariates %||% list(), use.names = FALSE)
  terms <- c(analysis$exposure)
  for (variable in covariates) {
    if (variable %in% spline_variables) {
      spec <- spline_specs[[variable]]
      terms <- c(terms, sprintf(
        "splines::ns(%s, knots=c(%s), Boundary.knots=c(%s))",
        variable,
        format_number_for_formula(spec$knots),
        format_number_for_formula(spec$boundary_knots)
      ))
    } else {
      terms <- c(terms, variable)
    }
  }
  stats::as.formula(sprintf(
    "survival::Surv(%s, %s) ~ %s",
    analysis$time, event, paste(terms, collapse = " + ")
  ))
}

fit_cause_specific_cox_once <- function(data, analysis, event, spline_specs) {
  formula <- survival_model_formula(analysis, event, spline_specs)
  fit <- survival::coxph(
    formula,
    data = data,
    ties = "efron",
    robust = TRUE,
    x = TRUE,
    y = TRUE,
    model = TRUE
  )
  exposure <- analysis$exposure
  beta <- unname(stats::coef(fit)[[exposure]])
  variance <- unname(stats::vcov(fit)[exposure, exposure])
  ph <- tryCatch(survival::cox.zph(fit, transform = "rank"), error = function(e) NULL)
  ph_p <- if (is.null(ph)) NA_real_ else unname(ph$table[exposure, "p"])
  list(beta = beta, variance = variance, fit = fit, ph_p = ph_p, formula = paste(deparse(formula), collapse = " "))
}

pool_cause_specific_models <- function(fits, confidence_level = 0.95) {
  betas <- vapply(fits, `[[`, numeric(1), "beta")
  variances <- vapply(fits, `[[`, numeric(1), "variance")
  m <- length(fits)
  pooled <- mean(betas)
  within <- mean(variances)
  between <- if (m > 1L) stats::var(betas) else 0
  total <- within + (1 + 1 / m) * between
  se <- sqrt(total)
  degrees_freedom <- if (m > 1L && is.finite(between) && between > 0) {
    (m - 1) * (1 + within / ((1 + 1 / m) * between))^2
  } else {
    Inf
  }
  critical <- if (is.finite(degrees_freedom)) {
    stats::qt(1 - (1 - confidence_level) / 2, df = degrees_freedom)
  } else {
    stats::qnorm(1 - (1 - confidence_level) / 2)
  }
  test_statistic <- pooled / se
  p_value <- if (is.finite(degrees_freedom)) {
    2 * stats::pt(-abs(test_statistic), df = degrees_freedom)
  } else {
    2 * stats::pnorm(-abs(test_statistic))
  }
  ph_values <- vapply(fits, `[[`, numeric(1), "ph_p")
  list(
    m = m,
    log_hr = pooled,
    estimate_type = "cause_specific_hazard_ratio",
    estimate = exp(pooled),
    ci_low = exp(pooled - critical * se),
    ci_high = exp(pooled + critical * se),
    p_value = p_value,
    degrees_freedom = if (is.finite(degrees_freedom)) degrees_freedom else NA_real_,
    within_variance = within,
    between_variance = between,
    total_variance = total,
    confidence_level = confidence_level,
    ph_rank_test = list(
      p_values = as.list(ph_values),
      min = min(ph_values, na.rm = TRUE),
      median = stats::median(ph_values, na.rm = TRUE),
      max = max(ph_values, na.rm = TRUE),
      n_below_0_05 = sum(ph_values < 0.05, na.rm = TRUE),
      n_models = length(ph_values)
    )
  )
}

prepare_survival_imputations <- function(data, analysis, event_for_imputation) {
  method <- analysis$missing_data$method %||% "complete_case"
  model_variables <- unique(c(
    analysis$time, event_for_imputation, analysis$exposure,
    unlist(analysis$covariates %||% list(), use.names = FALSE),
    unlist(analysis$missing_data$auxiliary_variables %||% list(), use.names = FALSE)
  ))
  input <- data[model_variables]
  log_variables <- unlist(analysis$missing_data$log_transform %||% list(), use.names = FALSE)
  for (variable in log_variables) input[[variable]] <- log(input[[variable]])

  if (identical(method, "complete_case")) {
    complete <- input[stats::complete.cases(input), , drop = FALSE]
    for (variable in log_variables) complete[[variable]] <- exp(complete[[variable]])
    return(list(
      datasets = list(complete),
      diagnostics = list(event = event_for_imputation, method = method, m = 1L, input_n = nrow(data), complete_n = nrow(complete))
    ))
  }

  m <- as.integer(analysis$missing_data$m %||% 20L)
  maxit <- as.integer(analysis$missing_data$maxit %||% 15L)
  initial <- mice::mice(input, m = 1L, maxit = 0L, printFlag = FALSE)
  methods <- initial$method
  methods[colSums(is.na(input)) == 0] <- ""
  continuous_missing <- names(methods)[methods != ""]
  methods[continuous_missing] <- analysis$missing_data$continuous_method %||% "pmm"
  predictor_matrix <- initial$predictorMatrix
  diag(predictor_matrix) <- 0
  imputed <- mice::mice(
    input,
    m = m,
    maxit = maxit,
    method = methods,
    predictorMatrix = predictor_matrix,
    seed = as.integer(analysis$missing_data$seed %||% 20260717L),
    printFlag = FALSE
  )
  datasets <- lapply(seq_len(m), function(i) {
    completed <- mice::complete(imputed, action = i)
    for (variable in log_variables) completed[[variable]] <- exp(completed[[variable]])
    completed
  })
  list(
    datasets = datasets,
    diagnostics = list(
      event = event_for_imputation,
      method = method,
      engine = "mice",
      continuous_method = analysis$missing_data$continuous_method %||% "pmm",
      m = m,
      maxit = maxit,
      seed = as.integer(analysis$missing_data$seed %||% 20260717L),
      imputed_variables = as.list(continuous_missing),
      log_transformed_variables = as.list(log_variables),
      excluded_post_index_variables = analysis$missing_data$excluded_variables %||% list(),
      logged_events = as.list(imputed$loggedEvents %||% data.frame())
    )
  )
}

aalen_johansen_summary <- function(data, analysis, time_point = 3) {
  status <- ifelse(data[[analysis$event]] == 1, 1L, ifelse(data[[analysis$competing_event]] == 1, 2L, 0L))
  aj_data <- data.frame(
    time = data[[analysis$time]],
    status = factor(status, levels = c(0L, 1L, 2L), labels = c("censor", "death", "live_discharge")),
    exposure = data[[analysis$exposure]]
  )
  fit <- survival::survfit(survival::Surv(time, status) ~ exposure, data = aj_data)
  summary_at <- summary(fit, times = time_point, extend = TRUE)
  pstate <- summary_at$pstate
  strata <- as.character(summary_at$strata)
  rows <- lapply(seq_len(nrow(pstate)), function(i) {
    group_value <- sub("^[^=]+=", "", strata[[i]])
    list(
      group = label_exposure_groups(strata[[i]], analysis$exposure_group_labels %||% NULL),
      group_value = group_value,
      time = time_point,
      death_cumulative_incidence = unname(pstate[i, 2L]),
      live_discharge_cumulative_incidence = unname(pstate[i, 3L])
    )
  })

  curve_summary <- summary(fit)
  curve <- data.frame(
    time = curve_summary$time,
    group = as.character(curve_summary$strata),
    death = curve_summary$pstate[, 2L],
    live_discharge = curve_summary$pstate[, 3L]
  )
  list(fit = fit, time_point = rows, curve = curve)
}

plot_competing_risk_curves <- function(curve, analysis) {
  long <- rbind(
    data.frame(time = curve$time, group = curve$group, event = "Hospital death", incidence = curve$death),
    data.frame(time = curve$time, group = curve$group, event = "Live discharge", incidence = curve$live_discharge)
  )
  max_time <- analysis$plot_max_time %||% max(long$time, na.rm = TRUE)
  long <- long[long$time <= max_time, , drop = FALSE]
  long$group <- label_exposure_groups(long$group, analysis$exposure_group_labels %||% NULL)
  p <- ggplot2::ggplot(long, ggplot2::aes(x = time, y = incidence, color = group, linetype = group)) +
    ggplot2::geom_step(linewidth = 0.85) +
    ggplot2::facet_wrap(~event, scales = "free_y") +
    ggplot2::scale_color_manual(values = publication_palette) +
    ggplot2::scale_linetype_manual(values = c("solid", "22", "42", "13")) +
    ggplot2::scale_x_continuous(
      limits = c(0, max_time),
      breaks = scales::breaks_pretty(n = 6),
      expand = ggplot2::expansion(mult = c(0, 0.015))
    ) +
    ggplot2::scale_y_continuous(labels = scales::label_percent(accuracy = 1), expand = ggplot2::expansion(mult = c(0, 0.04))) +
    ggplot2::labs(
      x = analysis$time_label %||% "Days from landmark",
      y = "Cumulative incidence",
      color = NULL,
      linetype = NULL
    ) +
    publication_theme()
  p
}

plot_cause_specific_estimates <- function(primary, competing, analysis) {
  plot_data <- data.frame(
    event = c(
      analysis$primary_event_label %||% "Primary event",
      analysis$competing_event_label %||% "Competing event"
    ),
    estimate = c(primary$estimate, competing$estimate),
    ci_low = c(primary$ci_low, competing$ci_low),
    ci_high = c(primary$ci_high, competing$ci_high),
    stringsAsFactors = FALSE
  )
  plot_data$event <- factor(plot_data$event, levels = rev(plot_data$event))
  plot_data$numeric_label <- sprintf("%.2f (%.2f-%.2f)", plot_data$estimate, plot_data$ci_low, plot_data$ci_high)
  plot_data$text_x <- max(plot_data$ci_high) * 1.08
  ggplot2::ggplot(plot_data, ggplot2::aes(y = event, x = estimate)) +
    ggplot2::geom_vline(xintercept = 1, linewidth = 0.45, color = "#5B6570", linetype = "22") +
    ggplot2::geom_segment(
      ggplot2::aes(x = ci_low, xend = ci_high, y = event, yend = event),
      linewidth = 0.8,
      color = publication_palette[[1L]]
    ) +
    ggplot2::geom_point(size = 2.4, color = publication_palette[[1L]]) +
    ggplot2::geom_text(
      ggplot2::aes(x = text_x, label = numeric_label), hjust = 0,
      size = 3, color = "black"
    ) +
    ggplot2::scale_x_log10(
      breaks = c(0.5, 0.6, 0.7, 0.8, 0.9, 1, 1.2, 1.4),
      labels = scales::label_number(accuracy = 0.01)
    ) +
    ggplot2::coord_cartesian(xlim = c(min(plot_data$ci_low) * 0.95, max(plot_data$text_x) * 1.25), clip = "off") +
    ggplot2::labs(x = "Cause-specific hazard ratio (95% CI)", y = NULL) +
    publication_theme() +
    ggplot2::theme(legend.position = "none")
}

run_cause_specific_cox <- function(task, data, output_dir) {
  if (!is.null(task$analysis$continuous_v4))
    return(run_continuous_cause_specific_cox(task, data, output_dir))
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)

  analysis <- task$analysis
  confidence_level <- analysis$confidence_level %||% 0.95
  spline_specs <- survival_spline_specs(
    data,
    unlist(analysis$spline_covariates %||% list(), use.names = FALSE),
    as.integer(analysis$spline_df %||% 3L)
  )
  death_imputed <- prepare_survival_imputations(data, analysis, analysis$event)
  competing_imputed <- prepare_survival_imputations(data, analysis, analysis$competing_event)
  death_fits <- lapply(death_imputed$datasets, fit_cause_specific_cox_once, analysis = analysis, event = analysis$event, spline_specs = spline_specs)
  competing_fits <- lapply(competing_imputed$datasets, fit_cause_specific_cox_once, analysis = analysis, event = analysis$competing_event, spline_specs = spline_specs)
  death <- pool_cause_specific_models(death_fits, confidence_level)
  competing <- pool_cause_specific_models(competing_fits, confidence_level)
  death$label <- analysis$primary_event_label %||% analysis$event
  competing$label <- analysis$competing_event_label %||% analysis$competing_event

  aj <- aalen_johansen_summary(data, analysis, time_point = analysis$cumulative_incidence_time %||% 3)
  gate_field <- analysis$multistate_gate$baseline_state_indicator %||% NULL
  baseline_nonzero <- if (is.null(gate_field)) 0L else sum(data[[gate_field]] != 0, na.rm = TRUE)
  multistate <- if (baseline_nonzero > 0L) {
    list(
      status = "MULTISTATE_DOWNGRADED",
      baseline_state_violation_n = baseline_nonzero,
      reason = "Not all patients share the prespecified common baseline state at the landmark."
    )
  } else {
    list(status = "MULTISTATE_ELIGIBLE", baseline_state_violation_n = 0L)
  }

  result$status <- "COMPLETE"
  result$counts <- list(
    analysis_n = nrow(data),
    exposure_0_n = sum(data[[analysis$exposure]] == 0, na.rm = TRUE),
    exposure_1_n = sum(data[[analysis$exposure]] == 1, na.rm = TRUE),
    primary_events = sum(data[[analysis$event]] == 1, na.rm = TRUE),
    competing_events = sum(data[[analysis$competing_event]] == 1, na.rm = TRUE)
  )
  result$estimates <- list(
    primary_event = death,
    competing_event = competing,
    cumulative_incidence = aj$time_point
  )
  result$diagnostics$multiple_imputation <- list(
    primary_event = death_imputed$diagnostics,
    competing_event = competing_imputed$diagnostics
  )
  result$diagnostics$spline_specs <- spline_specs
  result$diagnostics$multistate <- multistate

  dir.create(file.path(output_dir, "figures"), recursive = TRUE, showWarnings = FALSE)
  figure <- plot_competing_risk_curves(aj$curve, analysis)
  artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "cumulative_incidence", task, 7.2, 3.9)
  artifact$source <- "unadjusted Aalen-Johansen estimates"
  artifact$display_time_max <- analysis$plot_max_time %||% max(aj$curve$time, na.rm = TRUE)
  artifact$caption <- sprintf(
    "Cumulative incidence of hospital death and live discharge through %.0f days by exposure strategy. Curves are unadjusted Aalen-Johansen estimates; color and line type identify groups (N = %d).",
    artifact$display_time_max, result$counts$analysis_n
  )
  result$artifacts$figures$cumulative_incidence <- artifact
  effect_figure <- plot_cause_specific_estimates(death, competing, analysis)
  effect_artifact <- save_publication_figure(effect_figure, file.path(output_dir, "figures"), "cause_specific_estimates", task, 6.4, 3.2)
  effect_artifact$source <- "pooled adjusted cause-specific Cox models"
  effect_artifact$caption <- sprintf(
    "Adjusted cause-specific hazard ratios for hospital death and live discharge. Points show pooled estimates and horizontal lines show %.0f%% confidence intervals from the prespecified Cox models (N = %d).",
    100 * confidence_level, result$counts$analysis_n
  )
  result$artifacts$figures$cause_specific_estimates <- effect_artifact
  result
}
