temporal_prepare_split <- function(data, analysis, outcome) {
  split <- data[[analysis$split]]
  development <- data[!is.na(split) & split == analysis$development_value, , drop = FALSE]
  validation <- data[!is.na(split) & split == analysis$validation_value, , drop = FALSE]
  imputed <- unlist(analysis$median_impute_predictors %||% list(), use.names = FALSE)
  medians <- list()
  for (variable in imputed) {
    values <- development[[variable]]
    median_value <- stats::median(values, na.rm = TRUE)
    if (!is.finite(median_value)) stop(sprintf("Development median is not estimable for %s", variable), call. = FALSE)
    medians[[variable]] <- median_value
    indicator <- analysis$missing_indicator_map[[variable]]
    development[[indicator]] <- as.integer(is.na(development[[variable]]))
    validation[[indicator]] <- as.integer(is.na(validation[[variable]]))
    development[[variable]][is.na(development[[variable]])] <- median_value
    validation[[variable]][is.na(validation[[variable]])] <- median_value
  }
  predictors <- unique(c(unlist(analysis$baseline_predictors, use.names = FALSE), unlist(analysis$covariates, use.names = FALSE)))
  complete_development <- stats::complete.cases(development[c(outcome, predictors)])
  complete_validation <- stats::complete.cases(validation[c(outcome, predictors)])
  list(
    development = development[complete_development, , drop = FALSE],
    validation = validation[complete_validation, , drop = FALSE],
    medians = medians,
    excluded = list(development = sum(!complete_development), validation = sum(!complete_validation))
  )
}

temporal_fit_model <- function(data, outcome, predictors) {
  formula <- stats::reformulate(predictors, response = outcome)
  fit <- stats::glm(formula, data = data, family = stats::binomial(), control = stats::glm.control(maxit = 100))
  coefficients <- stats::coef(fit)
  if (!isTRUE(fit$converged) || any(!is.finite(coefficients))) stop("Prespecified logistic model did not converge to finite coefficients.", call. = FALSE)
  list(fit = fit, formula = formula)
}

temporal_require_finite <- function(data, columns, label) {
  if (!nrow(data)) stop(sprintf("%s is empty.", label), call. = FALSE)
  missing <- setdiff(columns, names(data))
  if (length(missing)) stop(sprintf("%s is missing required fields: %s", label, paste(missing, collapse = ", ")), call. = FALSE)
  invalid <- vapply(data[columns], function(x) !is.numeric(x) || any(!is.finite(x)), logical(1))
  if (any(invalid)) stop(sprintf("%s contains non-finite required results: %s", label, paste(names(invalid)[invalid], collapse = ", ")), call. = FALSE)
  invisible(TRUE)
}

temporal_require_primary_counts <- function(prepared, task, outcome) {
  total_n <- nrow(prepared$development) + nrow(prepared$validation)
  total_events <- sum(prepared$development[[outcome]] == 1) + sum(prepared$validation[[outcome]] == 1)
  validation_n <- nrow(prepared$validation)
  validation_events <- sum(prepared$validation[[outcome]] == 1)
  requirements <- c(
    total_n = task$readiness$min_n %||% 1L,
    total_events = task$readiness$min_events %||% 1L,
    validation_n = task$readiness$min_validation_n %||% 1L,
    validation_events = task$readiness$min_validation_events %||% 1L
  )
  observed <- c(total_n = total_n, total_events = total_events, validation_n = validation_n, validation_events = validation_events)
  failed <- observed < requirements
  if (any(failed)) stop(sprintf("Complete analysis rows fail frozen sample gates: %s", paste(sprintf("%s=%d<%d", names(observed)[failed], observed[failed], requirements[failed]), collapse = "; ")), call. = FALSE)
  invisible(TRUE)
}

temporal_auc <- function(outcome, risk) {
  if (length(unique(outcome)) < 2L) return(NA_real_)
  binary_auc(outcome, risk)
}

temporal_metrics <- function(outcome, risk) {
  risk <- pmin(pmax(risk, 1e-8), 1 - 1e-8)
  calibration <- tryCatch(stats::glm(outcome ~ stats::qlogis(risk), family = stats::binomial()), error = function(e) NULL)
  coefficients <- if (is.null(calibration) || !isTRUE(calibration$converged)) c(NA_real_, NA_real_) else stats::coef(calibration)
  observed <- mean(outcome)
  predicted <- mean(risk)
  c(
    auc = temporal_auc(outcome, risk),
    brier = mean((outcome - risk)^2),
    calibration_intercept = unname(coefficients[[1L]]),
    calibration_slope = unname(coefficients[[2L]]),
    observed_risk = observed,
    mean_predicted_risk = predicted,
    oe_ratio = if (predicted > 0) observed / predicted else NA_real_
  )
}

temporal_bootstrap_metrics <- function(outcome, risk, replicates, confidence_level, seed) {
  set.seed(seed)
  point <- temporal_metrics(outcome, risk)
  sampled <- replicate(replicates, {
    index <- sample.int(length(outcome), replace = TRUE)
    temporal_metrics(outcome[index], risk[index])
  })
  alpha <- (1 - confidence_level) / 2
  intervals <- t(apply(sampled, 1L, stats::quantile, probs = c(alpha, 1 - alpha), na.rm = TRUE, names = FALSE))
  labels <- c(
    auc = "AUC", brier = "Brier score", calibration_intercept = "Calibration intercept",
    calibration_slope = "Calibration slope", observed_risk = "Observed risk",
    mean_predicted_risk = "Mean predicted risk", oe_ratio = "Observed/expected ratio"
  )
  data.frame(
    metric = unname(labels[names(point)]), estimate = unname(point),
    ci_low = intervals[, 1L], ci_high = intervals[, 2L],
    confidence_level = confidence_level, stringsAsFactors = FALSE
  )
}

temporal_calibration_bins <- function(outcome, risk, bins, model_role) {
  breaks <- unique(stats::quantile(risk, probs = seq(0, 1, length.out = bins + 1L), na.rm = TRUE, names = FALSE))
  if (length(breaks) < 3L) return(data.frame())
  group <- cut(risk, breaks = breaks, include.lowest = TRUE, labels = FALSE)
  rows <- lapply(sort(unique(group)), function(value) {
    index <- group == value
    n <- sum(index); observed <- mean(outcome[index]); se <- sqrt(observed * (1 - observed) / n)
    data.frame(model = model_role, bin = value, n = n, events = sum(outcome[index]), predicted = mean(risk[index]), observed = observed,
      ci_low = max(0, observed - 1.96 * se), ci_high = min(1, observed + 1.96 * se), stringsAsFactors = FALSE)
  })
  do.call(rbind, rows)
}

temporal_coefficient_table <- function(fitted, role, confidence_level) {
  beta <- stats::coef(fitted$fit)
  rows <- coefficient_rows(beta, stats::vcov(fitted$fit), confidence_level, exponentiate = TRUE, measure = "odds ratio", multiplicity = "none")
  rows$model <- role
  rows$coefficient <- unname(beta[rows$term])
  rows[, c("model", "term", "coefficient", "standard_error", "estimate", "ci_low", "ci_high", "p_value", "confidence_level")]
}

temporal_influence <- function(fit) {
  cook <- stats::cooks.distance(fit)
  leverage <- stats::hatvalues(fit)
  list(
    n = length(cook), max_cooks_distance = max(cook, na.rm = TRUE),
    p99_cooks_distance = unname(stats::quantile(cook, 0.99, na.rm = TRUE)),
    cooks_distance_gt_1_n = sum(cook > 1, na.rm = TRUE),
    cooks_distance_gt_4_over_n_n = sum(cook > 4 / length(cook), na.rm = TRUE),
    max_leverage = max(leverage, na.rm = TRUE),
    leverage_gt_2p_over_n_n = sum(leverage > 2 * length(stats::coef(fit)) / length(leverage), na.rm = TRUE)
  )
}

temporal_run_sensitivity <- function(data, analysis, sensitivity, confidence_level, replicates, seed) {
  selected <- data
  if (!is.null(sensitivity$eligibility)) selected <- selected[!is.na(selected[[sensitivity$eligibility]]) & selected[[sensitivity$eligibility]] == 1, , drop = FALSE]
  prepared <- temporal_prepare_split(selected, analysis, sensitivity$outcome)
  predictors <- unlist(analysis$covariates, use.names = FALSE)
  fitted <- temporal_fit_model(prepared$development, sensitivity$outcome, predictors)
  risk <- stats::predict(fitted$fit, newdata = prepared$validation, type = "response")
  metrics <- temporal_bootstrap_metrics(prepared$validation[[sensitivity$outcome]], risk, replicates, confidence_level, seed)
  metrics$sensitivity_id <- sensitivity$id
  metrics$refit <- TRUE
  list(metrics = metrics, development_n = nrow(prepared$development), validation_n = nrow(prepared$validation), validation_events = sum(prepared$validation[[sensitivity$outcome]] == 1), formula = paste(deparse(fitted$formula), collapse = " "))
}

temporal_wilson <- function(events, n, confidence_level) {
  if (!n) return(c(NA_real_, NA_real_))
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  p <- events / n
  center <- (p + z^2 / (2 * n)) / (1 + z^2 / n)
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / (1 + z^2 / n)
  c(max(0, center - half), min(1, center + half))
}

temporal_timing_table <- function(data, analysis, confidence_level) {
  spec <- analysis$timing_analysis %||% NULL
  if (is.null(spec)) return(data.frame())
  events <- data[data[[analysis$outcome]] == 1 & !is.na(data[[spec$time]]), , drop = FALSE]
  interval <- cut(events[[spec$time]], breaks = unlist(spec$breaks, use.names = FALSE), labels = unlist(spec$labels, use.names = FALSE), right = FALSE, include.lowest = TRUE)
  rows <- lapply(levels(interval), function(label) {
    n <- sum(interval == label, na.rm = TRUE); ci <- temporal_wilson(n, nrow(events), confidence_level)
    data.frame(dimension = "time_interval", level = label, n = n, denominator = nrow(events), proportion = n / nrow(events), ci_low = ci[1L], ci_high = ci[2L], stringsAsFactors = FALSE)
  })
  components <- sort(unique(stats::na.omit(as.character(events[[spec$component]]))))
  rows <- c(rows, lapply(components, function(label) {
    n <- sum(as.character(events[[spec$component]]) == label, na.rm = TRUE); ci <- temporal_wilson(n, nrow(events), confidence_level)
    data.frame(dimension = "event_component", level = label, n = n, denominator = nrow(events), proportion = n / nrow(events), ci_low = ci[1L], ci_high = ci[2L], stringsAsFactors = FALSE)
  }))
  do.call(rbind, rows)
}

temporal_qc_table <- function(data, analysis) {
  qc <- analysis$qc_variables %||% list()
  rows <- list()
  add <- function(metric, value, denominator = nrow(data)) data.frame(metric = metric, value = value, denominator = denominator, stringsAsFactors = FALSE)
  if (!is.null(qc$record_id)) rows[[length(rows) + 1L]] <- add("duplicate_record_id_n", sum(duplicated(data[[qc$record_id]])))
  if (!is.null(qc$future_predictor_violation)) rows[[length(rows) + 1L]] <- add("future_predictor_violation_n", sum(data[[qc$future_predictor_violation]] == 1, na.rm = TRUE))
  if (!is.null(qc$outcome_at_or_before_landmark)) rows[[length(rows) + 1L]] <- add("outcome_at_or_before_landmark_n", sum(data[[qc$outcome_at_or_before_landmark]] == 1, na.rm = TRUE))
  if (!is.null(qc$drug_free_rule_violation)) rows[[length(rows) + 1L]] <- add("drug_free_rule_violation_n", sum(data[[qc$drug_free_rule_violation]] == 1, na.rm = TRUE))
  if (!is.null(qc$invalid_interval_count)) rows[[length(rows) + 1L]] <- add("invalid_interval_count", sum(data[[qc$invalid_interval_count]], na.rm = TRUE))
  if (!is.null(qc$restart_delay_minutes)) for (threshold in c(15, 30, 60)) rows[[length(rows) + 1L]] <- add(paste0("restart_within_", threshold, "_minutes_n"), sum(data[[qc$restart_delay_minutes]] < threshold, na.rm = TRUE))
  if (!is.null(qc$restart_same_drug)) rows[[length(rows) + 1L]] <- add("restart_same_drug_n", sum(data[[qc$restart_same_drug]] == 1, na.rm = TRUE), sum(!is.na(data[[qc$restart_same_drug]])))
  if (!is.null(qc$episode_duration_hours)) {
    duration <- data[[qc$episode_duration_hours]]
    for (probability in c(0.5, 0.95, 0.99)) rows[[length(rows) + 1L]] <- add(paste0("episode_duration_q", probability * 100, "_hours"), unname(stats::quantile(duration, probability, na.rm = TRUE)))
    rows[[length(rows) + 1L]] <- add("episode_duration_max_hours", max(duration, na.rm = TRUE))
    rows[[length(rows) + 1L]] <- add("episode_duration_gt_168h_n", sum(duration > 168, na.rm = TRUE))
    rows[[length(rows) + 1L]] <- add("episode_duration_gt_336h_n", sum(duration > 336, na.rm = TRUE))
  }
  if (!is.null(qc$episode_record_count)) rows[[length(rows) + 1L]] <- add("episode_record_count_max", max(data[[qc$episode_record_count]], na.rm = TRUE))
  event_free <- data[[analysis$outcome]] == 0
  if (!is.null(qc$icu_exit_before_horizon)) {
    rows[[length(rows) + 1L]] <- add("icu_exit_before_horizon_n", sum(data[[qc$icu_exit_before_horizon]] == 1, na.rm = TRUE))
    rows[[length(rows) + 1L]] <- add("icu_exit_before_horizon_event_free_n", sum(data[[qc$icu_exit_before_horizon]] == 1 & event_free, na.rm = TRUE), sum(event_free, na.rm = TRUE))
  }
  if (!is.null(qc$hospital_discharge_before_horizon)) {
    rows[[length(rows) + 1L]] <- add("hospital_discharge_before_horizon_n", sum(data[[qc$hospital_discharge_before_horizon]] == 1, na.rm = TRUE))
    rows[[length(rows) + 1L]] <- add("hospital_discharge_before_horizon_event_free_n", sum(data[[qc$hospital_discharge_before_horizon]] == 1 & event_free, na.rm = TRUE), sum(event_free, na.rm = TRUE))
  }
  if (!length(rows)) return(data.frame())
  do.call(rbind, rows)
}

temporal_calibration_axis_upper <- function(calibration) {
  maximum <- max(c(calibration$predicted, calibration$observed, calibration$ci_high), na.rm = TRUE)
  if (!is.finite(maximum)) return(1)
  min(1, max(0.1, ceiling(maximum * 20) / 20))
}

build_temporal_calibration_figure <- function(calibration) {
  labels <- c(baseline = "Baseline model", minimal_adjusted = "Minimal model")
  calibration$model_display <- factor(
    unname(labels[as.character(calibration$model)]),
    levels = unname(labels)
  )
  upper <- temporal_calibration_axis_upper(calibration)
  breaks <- pretty(c(0, upper), n = 5)
  breaks <- breaks[breaks >= 0 & breaks <= upper]
  ggplot2::ggplot(calibration, ggplot2::aes(x = predicted, y = observed, color = model_display)) +
    ggplot2::geom_abline(intercept = 0, slope = 1, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = ci_low, ymax = ci_high), width = upper / 80) +
    ggplot2::geom_point(size = 2) +
    ggplot2::scale_color_manual(values = c("Baseline model" = "#E76F6A", "Minimal model" = "#00A9B7"), drop = FALSE) +
    ggplot2::scale_x_continuous(limits = c(0, upper), breaks = breaks, expand = ggplot2::expansion(mult = c(0, 0.02))) +
    ggplot2::scale_y_continuous(limits = c(0, upper), breaks = breaks, expand = ggplot2::expansion(mult = c(0, 0.02))) +
    ggplot2::coord_equal() + publication_theme() +
    ggplot2::theme(legend.position = "none") +
    ggplot2::labs(x = "Predicted risk", y = "Observed outcome proportion", color = "Model")
}

build_temporal_roc_figure <- function(roc, performance) {
  labels <- c(baseline = "Baseline model", minimal_adjusted = "Minimal model")
  auc <- performance[performance$metric == "AUC", c("model", "estimate", "ci_low", "ci_high"), drop = FALSE]
  auc$label <- sprintf("%s %.3f (%.3f-%.3f)", labels[as.character(auc$model)], auc$estimate, auc$ci_low, auc$ci_high)
  roc$model_display <- factor(unname(labels[as.character(roc$model)]), levels = unname(labels))
  subtitle <- paste("AUC (95% CI):", paste(auc$label, collapse = "; "))
  ggplot2::ggplot(roc, ggplot2::aes(x = one_minus_specificity, y = sensitivity, color = model_display)) +
    ggplot2::geom_abline(intercept = 0, slope = 1, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_line(linewidth = 0.9) + ggplot2::coord_equal() +
    ggplot2::scale_color_manual(values = c("#E76F6A", "#00A9B7"), drop = FALSE) +
    ggplot2::scale_x_continuous(limits = c(0, 1)) + ggplot2::scale_y_continuous(limits = c(0, 1)) +
    publication_theme() + ggplot2::labs(x = "1 - Specificity", y = "Sensitivity", color = NULL, subtitle = subtitle) +
    ggplot2::theme(plot.subtitle = ggplot2::element_text(size = 7.5))
}

build_temporal_performance_figure <- function(roc, calibration, performance) {
  build_temporal_roc_figure(roc, performance) + build_temporal_calibration_figure(calibration) +
    patchwork::plot_annotation(tag_levels = "A") + patchwork::plot_layout(ncol = 2, widths = c(1, 1))
}

build_temporal_event_timing_figure <- function(timing) {
  intervals <- timing[timing$dimension == "time_interval", , drop = FALSE]
  components <- timing[timing$dimension == "event_component", , drop = FALSE]
  intervals$level <- factor(intervals$level, levels = intervals$level)
  component_labels <- c(death = "In-hospital death", vasopressor_restart = "Recorded vasopressor\nrestart")
  components$level_display <- unname(component_labels[components$level])
  components$level_display[is.na(components$level_display)] <- components$level[is.na(components$level_display)]
  components$level_display <- factor(components$level_display, levels = components$level_display)
  interval_plot <- ggplot2::ggplot(intervals, ggplot2::aes(x = level, y = proportion)) +
    ggplot2::geom_col(fill = "#00A9B7", width = 0.66) +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = ci_low, ymax = ci_high), width = 0.18) +
    ggplot2::geom_text(ggplot2::aes(label = paste0("n=", n)), vjust = -0.6, size = 3.3) +
    ggplot2::scale_y_continuous(labels = scales::percent_format(accuracy = 1), expand = ggplot2::expansion(mult = c(0, 0.12))) +
    publication_theme() + ggplot2::labs(x = "Time after landmark", y = "Share of first events")
  component_plot <- ggplot2::ggplot(components, ggplot2::aes(x = level_display, y = proportion)) +
    ggplot2::geom_col(fill = "#E76F6A", width = 0.66) +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = ci_low, ymax = ci_high), width = 0.18) +
    ggplot2::geom_text(ggplot2::aes(label = paste0("n=", n)), vjust = -0.6, size = 3.3) +
    ggplot2::scale_y_continuous(labels = scales::percent_format(accuracy = 1), expand = ggplot2::expansion(mult = c(0, 0.12))) +
    publication_theme() + ggplot2::labs(x = "First-event component", y = "Share of first events")
  interval_plot + component_plot + patchwork::plot_annotation(tag_levels = "A")
}

build_temporal_robustness_figure <- function(performance, sensitivity_table) {
  primary <- performance[performance$model == "minimal_adjusted", , drop = FALSE]
  primary$analysis <- "Primary 6-hour landmark"
  sensitivity_table$analysis <- unname(c(
    eight_hour_landmark = "8-hour landmark",
    restart_only = "Restart-only outcome"
  )[sensitivity_table$sensitivity_id])
  rows <- rbind(
    primary[, c("metric", "estimate", "ci_low", "ci_high", "confidence_level", "analysis")],
    sensitivity_table[, c("metric", "estimate", "ci_low", "ci_high", "confidence_level", "analysis")]
  )
  rows <- rows[rows$metric %in% c("AUC", "Brier score", "Observed/expected ratio"), , drop = FALSE]
  rows$analysis <- factor(rows$analysis, levels = rev(c("Primary 6-hour landmark", "8-hour landmark", "Restart-only outcome")))
  ggplot2::ggplot(rows, ggplot2::aes(x = estimate, y = analysis)) +
    ggplot2::geom_vline(data = data.frame(metric = "Observed/expected ratio", reference = 1), ggplot2::aes(xintercept = reference), color = "#5B6570", linetype = "22") +
    ggplot2::geom_errorbar(ggplot2::aes(xmin = ci_low, xmax = ci_high), orientation = "y", width = 0.18, color = "#00A9B7") +
    ggplot2::geom_point(size = 2.2, color = "#00A9B7") +
    ggplot2::facet_wrap(~metric, scales = "free_x", ncol = 3) + publication_theme() +
    ggplot2::labs(x = "Estimate (95% CI)", y = NULL)
}

build_temporal_cohort_flow_figure <- function(flow) {
  required <- c("step_order", "step_label", "n")
  missing <- setdiff(required, names(flow))
  if (length(missing)) stop(sprintf("Cohort-flow table is missing: %s", paste(missing, collapse = ", ")), call. = FALSE)
  flow <- flow[order(flow$step_order), , drop = FALSE]
  flow$x <- 0.5
  flow$y <- rev(seq_len(nrow(flow)))
  wrap <- function(value) paste(strwrap(value, width = 52), collapse = "\n")
  flow$box_label <- sprintf("%s\nn = %s", vapply(flow$step_label, wrap, character(1)), scales::comma(flow$n))
  arrows <- if (nrow(flow) > 1L) data.frame(
    x = 0.5, xend = 0.5,
    y = flow$y[-nrow(flow)] - 0.28,
    yend = flow$y[-1L] + 0.28,
    excluded = flow$excluded_from_previous[-1L]
  ) else data.frame()
  plot <- ggplot2::ggplot(flow, ggplot2::aes(x = x, y = y)) +
    ggplot2::geom_label(ggplot2::aes(label = box_label), fill = "#EAF7F8", color = "#143642", label.size = 0.45, size = 3.3, lineheight = 1.05) +
    ggplot2::coord_cartesian(xlim = c(0.1, 0.9), ylim = c(0.6, nrow(flow) + 0.4), clip = "off") +
    ggplot2::theme_void() + ggplot2::theme(plot.margin = ggplot2::margin(12, 18, 12, 18))
  if (nrow(arrows)) {
    plot <- plot +
      ggplot2::geom_segment(data = arrows, ggplot2::aes(x = x, xend = xend, y = y, yend = yend), inherit.aes = FALSE, arrow = grid::arrow(length = grid::unit(0.12, "inches")), linewidth = 0.5, color = "#5B6570") +
      ggplot2::geom_text(data = arrows, ggplot2::aes(x = 0.67, y = (y + yend) / 2, label = paste0("Excluded: ", scales::comma(excluded))), inherit.aes = FALSE, hjust = 0, size = 3, color = "#5B6570")
  }
  plot
}

run_temporal_logistic_prediction <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)
  analysis <- task$analysis
  confidence_level <- analysis$confidence_level %||% 0.95
  replicates <- as.integer(analysis$bootstrap_replicates %||% 2000L)
  prepared <- temporal_prepare_split(data, analysis, analysis$outcome)
  temporal_require_primary_counts(prepared, task, analysis$outcome)
  baseline <- temporal_fit_model(prepared$development, analysis$outcome, unlist(analysis$baseline_predictors, use.names = FALSE))
  minimal <- temporal_fit_model(prepared$development, analysis$outcome, unlist(analysis$covariates, use.names = FALSE))
  baseline_risk <- stats::predict(baseline$fit, newdata = prepared$validation, type = "response")
  minimal_risk <- stats::predict(minimal$fit, newdata = prepared$validation, type = "response")
  if (any(!is.finite(baseline_risk)) || any(!is.finite(minimal_risk))) stop("Primary validation predictions must all be finite.", call. = FALSE)
  outcome <- prepared$validation[[analysis$outcome]]
  baseline_metrics <- temporal_bootstrap_metrics(outcome, baseline_risk, replicates, confidence_level, task$seed %||% 20260718L)
  minimal_metrics <- temporal_bootstrap_metrics(outcome, minimal_risk, replicates, confidence_level, (task$seed %||% 20260718L) + 1L)
  baseline_metrics$model <- "baseline"; minimal_metrics$model <- "minimal_adjusted"
  performance <- rbind(baseline_metrics, minimal_metrics)
  coefficients <- rbind(temporal_coefficient_table(baseline, "baseline", confidence_level), temporal_coefficient_table(minimal, "minimal_adjusted", confidence_level))
  calibration <- rbind(temporal_calibration_bins(outcome, baseline_risk, analysis$calibration_bins %||% 10L, "baseline"), temporal_calibration_bins(outcome, minimal_risk, analysis$calibration_bins %||% 10L, "minimal_adjusted"))
  sensitivities <- lapply(seq_along(analysis$prediction_sensitivities %||% list()), function(i) temporal_run_sensitivity(data, analysis, analysis$prediction_sensitivities[[i]], confidence_level, replicates, (task$seed %||% 20260718L) + 10L + i))
  sensitivity_table <- if (length(sensitivities)) do.call(rbind, lapply(sensitivities, `[[`, "metrics")) else data.frame()
  timing <- temporal_timing_table(data, analysis, confidence_level)
  qc <- temporal_qc_table(data, analysis)
  temporal_require_finite(performance, c("estimate", "ci_low", "ci_high", "confidence_level"), "Primary performance metrics")
  temporal_require_finite(coefficients, c("coefficient", "standard_error", "estimate", "ci_low", "ci_high", "p_value", "confidence_level"), "Primary model coefficients")
  temporal_require_finite(calibration, c("n", "events", "predicted", "observed", "ci_low", "ci_high"), "Calibration table")
  if (nrow(sensitivity_table)) temporal_require_finite(sensitivity_table, c("estimate", "ci_low", "ci_high", "confidence_level"), "Sensitivity performance metrics")
  result$status <- "COMPLETE"
  result$counts <- list(input_n = nrow(data), development_n = nrow(prepared$development), validation_n = nrow(prepared$validation), development_events = sum(prepared$development[[analysis$outcome]] == 1), validation_events = sum(outcome == 1), excluded_missing = prepared$excluded)
  result$estimates <- list(primary = as_result_rows(minimal_metrics), performance_metrics = as_result_rows(performance), coefficients = as_result_rows(coefficients), timing = if (nrow(timing)) as_result_rows(timing) else list())
  result$sensitivities <- list(status = if (length(sensitivities)) "COMPLETE" else "NOT_REQUESTED", analyses = lapply(sensitivities, function(x) x[setdiff(names(x), "metrics")]), estimates = if (nrow(sensitivity_table)) as_result_rows(sensitivity_table) else list())
  result$diagnostics$model <- list(baseline_converged = baseline$fit$converged, minimal_converged = minimal$fit$converged, variance_estimator = "model_based", bootstrap_scope = "validation_only_fixed_model", bootstrap_interval = "percentile", bootstrap_replicates = replicates, calibration_intercept_method = "joint_with_slope", sensitivity_refit = TRUE, decision_curve_enabled = FALSE, imputation_medians_learned_in_development = prepared$medians, baseline_formula = paste(deparse(baseline$formula), collapse = " "), minimal_formula = paste(deparse(minimal$formula), collapse = " "))
  result$diagnostics$influence <- list(baseline = temporal_influence(baseline$fit), minimal_adjusted = temporal_influence(minimal$fit))
  result$diagnostics$qc <- if (nrow(qc)) as_result_rows(qc) else list()
  result$artifacts$tables$performance_metrics <- write_csv_artifact(performance, output_dir, "performance_metrics.csv", "fixed temporal validation performance with percentile bootstrap intervals")
  result$artifacts$tables$model_coefficients <- write_csv_artifact(coefficients, output_dir, "model_coefficients.csv", "model-based Wald coefficient estimates")
  result$artifacts$tables$calibration <- write_csv_artifact(calibration, output_dir, "calibration.csv", "validation calibration by predicted-risk groups")
  influence <- do.call(rbind, lapply(names(result$diagnostics$influence), function(role) data.frame(model = role, as.data.frame(result$diagnostics$influence[[role]], stringsAsFactors = FALSE), check.names = FALSE)))
  result$artifacts$tables$influence_summary <- write_csv_artifact(influence, output_dir, "influence_summary.csv", "aggregate Cook distance and leverage diagnostics")
  roc <- rbind(transform(roc_coordinates(outcome, baseline_risk), model = "baseline"), transform(roc_coordinates(outcome, minimal_risk), model = "minimal_adjusted"))
  result$artifacts$tables$roc <- write_csv_artifact(roc, output_dir, "roc_coordinates.csv", "validation ROC coordinates for both frozen models")
  if (nrow(sensitivity_table)) result$artifacts$tables$sensitivity_performance <- write_csv_artifact(sensitivity_table, output_dir, "sensitivity_performance.csv", "prespecified refitted sensitivity models")
  if (nrow(timing)) result$artifacts$tables$event_timing <- write_csv_artifact(timing, output_dir, "event_timing.csv", "aggregate event timing and component distribution")
  if (nrow(qc)) result$artifacts$tables$qc_summary <- write_csv_artifact(qc, output_dir, "qc_summary.csv", "aggregate episode and outcome-definition quality checks")
  performance_figure <- build_temporal_performance_figure(roc, calibration, performance)
  performance_artifact <- save_publication_figure(performance_figure, file.path(output_dir, "figures"), "temporal_performance", task, 7, 4.8)
  performance_artifact$source <- "fixed temporal validation predictions"
  performance_artifact$caption <- "Discrimination and calibration of the frozen baseline and minimally adjusted models in the temporal validation set."
  result$artifacts$figures$temporal_performance <- performance_artifact
  if (nrow(timing)) {
    timing_artifact <- save_publication_figure(build_temporal_event_timing_figure(timing), file.path(output_dir, "figures"), "temporal_event_timing", task, 10, 4.8)
    timing_artifact$source <- "aggregate first-event timing table"
    timing_artifact$caption <- "Timing and component distribution of the first recorded event after the landmark."
    result$artifacts$figures$event_timing <- timing_artifact
  }
  if (nrow(sensitivity_table)) {
    robustness_artifact <- save_publication_figure(build_temporal_robustness_figure(performance, sensitivity_table), file.path(output_dir, "figures"), "temporal_robustness", task, 11, 4.6)
    robustness_artifact$source <- "primary and prespecified sensitivity performance tables"
    robustness_artifact$caption <- "Primary and prespecified sensitivity performance with percentile bootstrap confidence intervals."
    result$artifacts$figures$robustness <- robustness_artifact
  }
  result
}
