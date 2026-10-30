survival_complete_data <- function(data, analysis) {
  required <- unique(c(
    analysis$time, analysis$event, analysis$competing_event, analysis$exposure,
    unlist(analysis$covariates %||% list(), use.names = FALSE), analysis$cluster_id
  ))
  required <- required[!is.na(required) & nzchar(required)]
  data[stats::complete.cases(data[required]), , drop = FALSE]
}

survival_group_labels <- function(x, analysis) {
  values <- as.character(x)
  labels <- analysis$exposure_group_labels %||% list()
  factor(vapply(values, function(value) as.character(labels[[value]] %||% value), character(1)))
}

fit_kaplan_meier <- function(data, analysis) {
  data$.clin_group <- survival_group_labels(data[[analysis$exposure]], analysis)
  formula <- stats::as.formula(sprintf("survival::Surv(%s, %s) ~ .clin_group", analysis$time, analysis$event))
  fit <- survival::survfit(formula, data = data, conf.type = "log-log")
  curve_summary <- summary(fit)
  curve <- data.frame(
    time = curve_summary$time, survival = curve_summary$surv,
    ci_low = curve_summary$lower, ci_high = curve_summary$upper,
    n_risk = curve_summary$n.risk, n_event = curve_summary$n.event,
    n_censor = curve_summary$n.censor, group = sub("^.clin_group=", "", curve_summary$strata),
    stringsAsFactors = FALSE
  )
  logrank <- survival::survdiff(formula, data = data)
  p_value <- stats::pchisq(logrank$chisq, df = length(logrank$n) - 1L, lower.tail = FALSE)
  table <- summary(fit)$table
  if (is.null(dim(table))) table <- matrix(table, nrow = 1L, dimnames = list(names(fit$strata) %||% "Overall", names(table)))
  median_rows <- data.frame(
    group = sub("^.clin_group=", "", rownames(table)), n = unname(table[, "records"]),
    events = unname(table[, "events"]), median = unname(table[, "median"]),
    ci_low = unname(table[, "0.95LCL"]), ci_high = unname(table[, "0.95UCL"]), stringsAsFactors = FALSE
  )
  max_time <- analysis$plot_max_time %||% max(data[[analysis$time]], na.rm = TRUE)
  risk_times <- pretty(c(0, max_time), n = 6)
  risk_times <- risk_times[risk_times >= 0 & risk_times <= max_time]
  risk_summary <- summary(fit, times = risk_times, extend = TRUE)
  risk <- data.frame(
    time = risk_summary$time, n_risk = risk_summary$n.risk,
    group = sub("^.clin_group=", "", risk_summary$strata), stringsAsFactors = FALSE
  )
  list(fit = fit, curve = curve, risk = risk, medians = median_rows, logrank_p = p_value, max_time = max_time)
}

plot_kaplan_meier <- function(km, analysis) {
  curve <- km$curve[km$curve$time <= km$max_time, , drop = FALSE]
  groups <- levels(factor(curve$group))
  line_types <- rep(c("solid", "22", "42", "13"), length.out = length(groups))
  names(line_types) <- groups
  colors <- rep(publication_palette, length.out = length(groups)); names(colors) <- groups
  main <- ggplot2::ggplot(curve, ggplot2::aes(x = time, y = survival, color = group, linetype = group)) +
    ggplot2::geom_step(linewidth = 0.85) +
    ggplot2::geom_point(
      data = curve[curve$n_censor > 0, , drop = FALSE], shape = 3, size = 1.4, stroke = 0.45
    ) +
    ggplot2::scale_color_manual(values = colors) + ggplot2::scale_linetype_manual(values = line_types) +
    ggplot2::scale_x_continuous(limits = c(0, km$max_time), breaks = sort(unique(km$risk$time)), expand = ggplot2::expansion(mult = c(0, 0.01))) +
    ggplot2::scale_y_continuous(limits = c(0, 1), labels = scales::label_percent(accuracy = 1), expand = ggplot2::expansion(mult = c(0, 0.02))) +
    publication_theme() +
    ggplot2::labs(x = NULL, y = "Survival probability", color = NULL, linetype = NULL) +
    ggplot2::annotate("text", x = km$max_time * 0.98, y = 0.04, hjust = 1, size = 2.7,
                      label = sprintf("Log-rank p = %s", format.pval(km$logrank_p, digits = 3, eps = 0.001)))
  risk <- ggplot2::ggplot(km$risk, ggplot2::aes(x = time, y = group, label = n_risk, color = group)) +
    ggplot2::geom_text(size = 2.8, show.legend = FALSE) +
    ggplot2::scale_color_manual(values = colors) +
    ggplot2::scale_x_continuous(limits = c(0, km$max_time), breaks = sort(unique(km$risk$time)), expand = ggplot2::expansion(mult = c(0, 0.01))) +
    ggplot2::labs(x = analysis$time_label %||% "Follow-up time", y = "Number at risk") +
    publication_theme(base_size = 9) +
    ggplot2::theme(axis.line.y = ggplot2::element_blank(), axis.ticks.y = ggplot2::element_blank(), legend.position = "none")
  patchwork::wrap_plots(main, risk, ncol = 1, heights = c(3.4, 1.15))
}

fit_standard_cox <- function(data, analysis) {
  rhs <- c(model_terms(analysis), sprintf("survival::strata(%s)", unlist(analysis$cox_strata %||% list(), use.names = FALSE)))
  formula <- stats::as.formula(sprintf(
    "survival::Surv(%s, %s) ~ %s", analysis$time, analysis$event,
    paste(rhs, collapse = " + ")
  ))
  cluster <- analysis$cluster_id %||% NULL
  fit <- survival::coxph(
    formula, data = data, ties = "efron", x = TRUE, y = TRUE, model = TRUE,
    robust = !is.null(cluster), cluster = if (is.null(cluster)) NULL else data[[cluster]]
  )
  ph <- survival::cox.zph(fit, transform = "rank")
  list(fit = fit, vcov = stats::vcov(fit), ph = ph, formula = formula)
}

fit_fine_gray <- function(data, analysis) {
  data$.clin_time <- data[[analysis$time]]
  data$.clin_status <- factor(
    ifelse(data[[analysis$event]] == 1, "event", ifelse(data[[analysis$competing_event]] == 1, "competing", "censor")),
    levels = c("censor", "event", "competing")
  )
  rhs <- paste(model_terms(analysis), collapse = " + ")
  formula <- stats::as.formula(sprintf("survival::Surv(.clin_time, .clin_status) ~ %s", rhs))
  expanded <- survival::finegray(formula, data = data, etype = "event")
  fit_formula <- stats::as.formula(sprintf("survival::Surv(fgstart, fgstop, fgstatus) ~ %s", rhs))
  fit <- survival::coxph(fit_formula, data = expanded, weights = fgwt, ties = "breslow", x = TRUE)
  list(fit = fit, vcov = stats::vcov(fit), expanded_n = nrow(expanded), formula = fit_formula)
}

restricted_mean_survival <- function(time, event, tau) {
  fit <- survival::survfit(survival::Surv(time, event) ~ 1)
  indices <- which(fit$time < tau)
  change_times <- fit$time[indices]
  interval_ends <- c(change_times, tau)
  interval_starts <- c(0, change_times)
  survival_at_start <- c(1, fit$surv[indices])
  sum((interval_ends - interval_starts) * survival_at_start)
}

fit_rmst <- function(data, analysis, seed) {
  groups <- sort(unique(data[[analysis$exposure]]))
  if (length(groups) != 2L) stop("RMST currently requires exactly two exposure groups.", call. = FALSE)
  tau <- analysis$tau
  estimate_once <- function(d) {
    values <- vapply(groups, function(g) {
      subset <- d[d[[analysis$exposure]] == g, , drop = FALSE]
      restricted_mean_survival(subset[[analysis$time]], subset[[analysis$event]], tau)
    }, numeric(1))
    c(group_0 = values[[1L]], group_1 = values[[2L]], difference = values[[2L]] - values[[1L]])
  }
  point <- estimate_once(data)
  set.seed(seed)
  replicates <- as.integer(analysis$bootstrap_replicates %||% 400L)
  boot <- replicate(replicates, estimate_once(data[sample.int(nrow(data), replace = TRUE), , drop = FALSE]))
  confidence_level <- analysis$confidence_level %||% 0.95
  alpha <- (1 - confidence_level) / 2
  ci <- apply(boot, 1L, stats::quantile, probs = c(alpha, 1 - alpha), na.rm = TRUE, names = FALSE)
  rows <- data.frame(
    term = c(paste0(analysis$exposure, "=", groups[[1L]]), paste0(analysis$exposure, "=", groups[[2L]]), "difference"),
    measure = c("restricted_mean_survival_time", "restricted_mean_survival_time", "rmst_difference"),
    estimate = unname(point), ci_low = ci[1L, ], ci_high = ci[2L, ],
    confidence_level = confidence_level, stringsAsFactors = FALSE
  )
  list(rows = rows, bootstrap_replicates = replicates, tau = tau, groups = groups)
}

run_survival_analysis <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)
  analysis <- task$analysis
  model_data <- survival_complete_data(data, analysis)
  engine <- analysis$survival_engine
  confidence_level <- analysis$confidence_level %||% 0.95

  result$counts <- list(
    input_n = nrow(data), analysis_n = nrow(model_data),
    excluded_missing_n = nrow(data) - nrow(model_data), events = sum(model_data[[analysis$event]] == 1)
  )
  if (identical(engine, "kaplan_meier")) {
    km <- fit_kaplan_meier(model_data, analysis)
    result$estimates <- list(primary = as_result_rows(km$medians), survival_medians = as_result_rows(km$medians))
    result$diagnostics$model <- list(engine = engine, logrank_p_value = km$logrank_p)
    result$artifacts$tables$survival_medians <- write_csv_artifact(km$medians, output_dir, "survival_medians.csv", "Kaplan-Meier medians")
    result$artifacts$tables$number_at_risk <- write_csv_artifact(km$risk, output_dir, "number_at_risk.csv", "Kaplan-Meier number at risk")
    figure <- plot_kaplan_meier(km, analysis)
    artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "kaplan_meier", task, 7, 5.5)
    artifact$source <- "unadjusted Kaplan-Meier estimator"
    artifact$caption <- sprintf(
      "Kaplan-Meier survival estimates by exposure group. Censoring is shown by crosses, the lower panel gives numbers at risk, and the prespecified log-rank p value is %s (N = %d).",
      format.pval(km$logrank_p, digits = 3, eps = 0.001), result$counts$analysis_n
    )
    result$artifacts$figures$kaplan_meier <- artifact
  } else if (identical(engine, "cox")) {
    fitted <- fit_standard_cox(model_data, analysis)
    rows <- coefficient_rows(stats::coef(fitted$fit), fitted$vcov, confidence_level, TRUE, "hazard_ratio", analysis$multiplicity %||% "none")
    primary <- rows[startsWith(rows$term, analysis$exposure), , drop = FALSE]
    result$estimates <- list(primary = as_result_rows(primary), coefficients = as_result_rows(rows))
    result$diagnostics$model <- list(engine = engine, formula = paste(deparse(fitted$formula), collapse = " "), converged = TRUE)
    result$diagnostics$proportional_hazards <- list(table = as_result_rows(as.data.frame(fitted$ph$table)))
    result$artifacts$tables$model_coefficients <- write_csv_artifact(rows, output_dir, "model_coefficients.csv", "adjusted Cox model")
    figure <- effect_forest_plot(rows, "Adjusted hazard ratio (95% CI)", 1)
    artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "cox_effects", task, 7, max(3.2, 0.42 * (nrow(rows) - 1) + 1.4))
    artifact$source <- "prespecified adjusted Cox model"
    artifact$caption <- sprintf("Adjusted hazard ratios from the prespecified Cox model. Points show estimates and horizontal lines show %.0f%% confidence intervals (N = %d).", 100 * confidence_level, result$counts$analysis_n)
    result$artifacts$figures$cox_effects <- artifact
  } else if (identical(engine, "fine_gray")) {
    fitted <- fit_fine_gray(model_data, analysis)
    rows <- coefficient_rows(stats::coef(fitted$fit), fitted$vcov, confidence_level, TRUE, "subdistribution_hazard_ratio", analysis$multiplicity %||% "none")
    primary <- rows[startsWith(rows$term, analysis$exposure), , drop = FALSE]
    result$estimates <- list(primary = as_result_rows(primary), coefficients = as_result_rows(rows))
    result$diagnostics$model <- list(engine = engine, expanded_n = fitted$expanded_n, formula = paste(deparse(fitted$formula), collapse = " "), variance_method = "weighted model-based")
    result$artifacts$tables$model_coefficients <- write_csv_artifact(rows, output_dir, "model_coefficients.csv", "Fine-Gray subdistribution hazards model")
    figure <- effect_forest_plot(rows, "Subdistribution hazard ratio (95% CI)", 1)
    artifact <- save_publication_figure(figure, file.path(output_dir, "figures"), "fine_gray_effects", task, 7, max(3.2, 0.42 * (nrow(rows) - 1) + 1.4))
    artifact$source <- "prespecified Fine-Gray model"
    artifact$caption <- sprintf("Subdistribution hazard ratios from the prespecified Fine-Gray competing-risk model. Points show estimates and horizontal lines show %.0f%% confidence intervals (N = %d).", 100 * confidence_level, result$counts$analysis_n)
    result$artifacts$figures$fine_gray_effects <- artifact
  } else if (identical(engine, "rmst")) {
    fitted <- fit_rmst(model_data, analysis, task$seed %||% 20260718L)
    result$estimates <- list(primary = as_result_rows(fitted$rows[fitted$rows$term == "difference", , drop = FALSE]), rmst = as_result_rows(fitted$rows))
    result$diagnostics$model <- list(engine = engine, tau = fitted$tau, bootstrap_replicates = fitted$bootstrap_replicates)
    result$artifacts$tables$rmst <- write_csv_artifact(fitted$rows, output_dir, "rmst_estimates.csv", "restricted mean survival time")
  }
  result$status <- "COMPLETE"
  result
}
