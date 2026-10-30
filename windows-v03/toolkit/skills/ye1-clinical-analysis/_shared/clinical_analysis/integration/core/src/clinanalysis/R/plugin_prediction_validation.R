binary_auc <- function(y, score) {
  positives <- score[y == 1]
  negatives <- score[y == 0]
  if (!length(positives) || !length(negatives)) return(NA_real_)
  ranks <- rank(c(positives, negatives), ties.method = "average")
  (sum(ranks[seq_along(positives)]) - length(positives) * (length(positives) + 1) / 2) /
    (length(positives) * length(negatives))
}

roc_coordinates <- function(y, score) {
  order <- order(score, decreasing = TRUE)
  y <- y[order]; score <- score[order]
  distinct <- c(TRUE, diff(score) != 0)
  tp <- cumsum(y == 1)[distinct]
  fp <- cumsum(y == 0)[distinct]
  data.frame(
    threshold = score[distinct], sensitivity = tp / sum(y == 1),
    one_minus_specificity = fp / sum(y == 0), stringsAsFactors = FALSE
  )
}

calibration_bins <- function(y, risk, bins) {
  breaks <- unique(stats::quantile(risk, probs = seq(0, 1, length.out = bins + 1L), na.rm = TRUE))
  if (length(breaks) < 3L) breaks <- seq(0, 1, length.out = bins + 1L)
  group <- cut(risk, breaks = breaks, include.lowest = TRUE, labels = FALSE)
  rows <- lapply(sort(unique(group)), function(g) {
    keep <- group == g
    observed <- mean(y[keep]); n <- sum(keep)
    se <- sqrt(observed * (1 - observed) / n)
    data.frame(bin = g, n = n, predicted = mean(risk[keep]), observed = observed,
               ci_low = max(0, observed - 1.96 * se), ci_high = min(1, observed + 1.96 * se))
  })
  do.call(rbind, rows)
}

binary_validation <- function(data, analysis, seed) {
  y <- data[[analysis$outcome]]
  risk <- data[[analysis$prediction]]
  if (!all(y %in% c(0, 1))) stop("Binary validation outcome must use 0/1 coding.", call. = FALSE)
  if (any(risk < 0 | risk > 1)) stop("Predicted risks must be between 0 and 1.", call. = FALSE)
  auc <- binary_auc(y, risk)
  set.seed(seed)
  replicates <- as.integer(analysis$bootstrap_replicates %||% 400L)
  boot_auc <- replicate(replicates, {
    index <- sample.int(length(y), replace = TRUE)
    binary_auc(y[index], risk[index])
  })
  confidence_level <- analysis$confidence_level %||% 0.95
  alpha <- (1 - confidence_level) / 2
  auc_ci <- stats::quantile(boot_auc, c(alpha, 1 - alpha), na.rm = TRUE, names = FALSE)
  clipped <- pmin(pmax(risk, 1e-6), 1 - 1e-6)
  calibration <- stats::glm(y ~ stats::qlogis(clipped), family = stats::binomial())
  thresholds <- unlist(analysis$decision_thresholds %||% list(), use.names = FALSE)
  if (!length(thresholds)) thresholds <- seq(0.01, 0.80, by = 0.01)
  prevalence <- mean(y)
  dca <- do.call(rbind, lapply(thresholds, function(threshold) {
    positive <- risk >= threshold
    odds <- threshold / (1 - threshold)
    data.frame(
      threshold = threshold,
      model = sum(positive & y == 1) / length(y) - sum(positive & y == 0) / length(y) * odds,
      treat_all = prevalence - (1 - prevalence) * odds,
      treat_none = 0
    )
  }))
  metrics <- data.frame(
    metric = c("AUC", "Brier score", "Calibration intercept", "Calibration slope"),
    estimate = c(auc, mean((risk - y)^2), stats::coef(calibration)[[1L]], stats::coef(calibration)[[2L]]),
    ci_low = c(auc_ci[[1L]], NA, NA, NA), ci_high = c(auc_ci[[2L]], NA, NA, NA), stringsAsFactors = FALSE
  )
  list(
    metrics = metrics, roc = roc_coordinates(y, risk), calibration = calibration_bins(y, risk, analysis$calibration_bins %||% 10L),
    dca = dca, bootstrap_replicates = replicates
  )
}

censor_survival_at <- function(time, event, query) {
  fit <- survival::survfit(survival::Surv(time, 1 - event) ~ 1)
  values <- summary(fit, times = query, extend = TRUE)$surv
  pmax(values, 1e-6)
}

survival_validation <- function(data, analysis) {
  time <- data[[analysis$time]]; event <- data[[analysis$event]]; risk <- data[[analysis$prediction]]
  horizon <- analysis$horizon
  concordance <- survival::concordance(survival::Surv(time, event) ~ risk, reverse = TRUE)
  event_by_horizon <- as.integer(time <= horizon & event == 1)
  weights <- numeric(length(time))
  early_event <- time <= horizon & event == 1
  beyond <- time > horizon
  if (any(early_event)) weights[early_event] <- 1 / censor_survival_at(time, event, pmax(time[early_event] - 1e-8, 0))
  if (any(beyond)) weights[beyond] <- 1 / censor_survival_at(time, event, rep(horizon, sum(beyond)))
  brier <- mean(weights * (event_by_horizon - risk)^2)
  breaks <- unique(stats::quantile(risk, probs = seq(0, 1, length.out = (analysis$calibration_bins %||% 10L) + 1L), na.rm = TRUE))
  group <- cut(risk, breaks = breaks, include.lowest = TRUE, labels = FALSE)
  bins <- do.call(rbind, lapply(sort(unique(group)), function(g) {
    keep <- group == g
    fit <- survival::survfit(survival::Surv(time[keep], event[keep]) ~ 1, conf.type = "log-log")
    at_horizon <- summary(fit, times = horizon, extend = TRUE)
    data.frame(
      bin = g, n = sum(keep), predicted = mean(risk[keep]),
      observed = 1 - at_horizon$surv,
      ci_low = max(0, 1 - at_horizon$upper), ci_high = min(1, 1 - at_horizon$lower)
    )
  }))
  c_se <- sqrt(unname(concordance$var))
  metrics <- data.frame(
    metric = c("Harrell C-index", paste0("IPCW Brier score at ", horizon)),
    estimate = c(unname(concordance$concordance), brier),
    ci_low = c(max(0, unname(concordance$concordance) - 1.96 * c_se), NA_real_),
    ci_high = c(min(1, unname(concordance$concordance) + 1.96 * c_se), NA_real_), stringsAsFactors = FALSE
  )
  list(metrics = metrics, calibration = bins, concordance_variance = unname(concordance$var), horizon = horizon)
}

plot_roc_validation <- function(roc, auc_row) {
  ggplot2::ggplot(roc, ggplot2::aes(x = one_minus_specificity, y = sensitivity)) +
    ggplot2::geom_abline(intercept = 0, slope = 1, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_line(color = publication_palette[[1L]], linetype = "solid", linewidth = 0.9) +
    ggplot2::coord_equal() +
    ggplot2::scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
    ggplot2::scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
    ggplot2::annotate("text", x = 0.98, y = 0.05, hjust = 1, size = 2.8,
                      label = sprintf("AUC %.3f (95%% CI %.3f-%.3f)", auc_row$estimate, auc_row$ci_low, auc_row$ci_high)) +
    publication_theme() + ggplot2::labs(x = "1 - Specificity", y = "Sensitivity")
}

plot_calibration_validation <- function(calibration, risk) {
  main <- ggplot2::ggplot(calibration, ggplot2::aes(x = predicted, y = observed)) +
    ggplot2::geom_abline(intercept = 0, slope = 1, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_errorbar(ggplot2::aes(ymin = ci_low, ymax = ci_high), width = 0.015, color = publication_palette[[1L]]) +
    ggplot2::geom_line(color = publication_palette[[1L]], linewidth = 0.75) +
    ggplot2::geom_point(shape = 21, fill = publication_palette[[1L]], color = "black", size = 2) +
    ggplot2::scale_x_continuous(limits = c(0, 1), expand = c(0, 0)) +
    ggplot2::scale_y_continuous(limits = c(0, 1), expand = c(0, 0)) +
    publication_theme() + ggplot2::labs(x = NULL, y = "Observed outcome proportion")
  histogram <- ggplot2::ggplot(data.frame(risk = risk), ggplot2::aes(x = risk)) +
    ggplot2::geom_histogram(bins = 30, fill = publication_palette[[1L]], color = "white", linewidth = 0.2) +
    ggplot2::scale_x_continuous(expand = c(0, 0)) + ggplot2::coord_cartesian(xlim = c(0, 1)) + publication_theme(base_size = 9) +
    ggplot2::labs(x = "Predicted risk", y = "Count")
  patchwork::wrap_plots(main, histogram, ncol = 1, heights = c(3, 1.15))
}

plot_decision_curve <- function(dca) {
  long <- rbind(
    data.frame(threshold = dca$threshold, strategy = "Model", net_benefit = dca$model),
    data.frame(threshold = dca$threshold, strategy = "Treat all", net_benefit = dca$treat_all),
    data.frame(threshold = dca$threshold, strategy = "Treat none", net_benefit = dca$treat_none)
  )
  upper <- max(c(dca$model, dca$treat_all, 0), na.rm = TRUE) * 1.05
  lower <- min(-0.05, min(dca$model, na.rm = TRUE) - 0.02)
  ggplot2::ggplot(long, ggplot2::aes(x = threshold, y = net_benefit, color = strategy, linetype = strategy)) +
    ggplot2::geom_line(linewidth = 0.85) +
    ggplot2::scale_color_manual(values = c("Model" = publication_palette[[1L]], "Treat all" = publication_palette[[2L]], "Treat none" = "#000000")) +
    ggplot2::scale_linetype_manual(values = c("Model" = "solid", "Treat all" = "22", "Treat none" = "42")) +
    ggplot2::coord_cartesian(ylim = c(lower, upper)) +
    publication_theme() + ggplot2::labs(x = "Threshold probability", y = "Net benefit", color = NULL, linetype = NULL)
}

prediction_subgroups <- function(data, analysis, seed) {
  if (!identical(analysis$validation_type, "binary")) return(data.frame())
  variables <- unlist(analysis$subgroup_variables %||% list(), use.names = FALSE)
  rows <- list()
  set.seed(seed)
  replicates <- as.integer(analysis$bootstrap_replicates %||% 400L)
  alpha <- (1 - (analysis$confidence_level %||% 0.95)) / 2
  for (variable in variables) {
    for (level in unique(data[[variable]])) {
      subset <- data[!is.na(data[[variable]]) & data[[variable]] == level, , drop = FALSE]
      if (nrow(subset) < 30L || length(unique(subset[[analysis$outcome]])) < 2L) next
      boot <- replicate(replicates, {
        index <- sample.int(nrow(subset), replace = TRUE)
        binary_auc(subset[[analysis$outcome]][index], subset[[analysis$prediction]][index])
      })
      ci <- stats::quantile(boot, c(alpha, 1 - alpha), na.rm = TRUE, names = FALSE)
      rows[[length(rows) + 1L]] <- data.frame(
        variable = variable, level = as.character(level), n = nrow(subset),
        auc = binary_auc(subset[[analysis$outcome]], subset[[analysis$prediction]]),
        ci_low = ci[[1L]], ci_high = ci[[2L]], stringsAsFactors = FALSE
      )
    }
  }
  if (length(rows)) do.call(rbind, rows) else data.frame()
}

plot_subgroup_performance <- function(subgroups, overall_auc) {
  subgroups$label <- paste0(subgroups$variable, ": ", subgroups$level, " (N = ", subgroups$n, ")")
  subgroups$label <- factor(subgroups$label, levels = rev(subgroups$label))
  lower <- max(0, min(0.5, min(subgroups$ci_low, na.rm = TRUE) - 0.02))
  ggplot2::ggplot(subgroups, ggplot2::aes(x = auc, y = label)) +
    ggplot2::geom_vline(xintercept = overall_auc, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_segment(ggplot2::aes(x = ci_low, xend = ci_high, y = label, yend = label), color = publication_palette[[1L]], linewidth = 0.7) +
    ggplot2::geom_point(shape = 21, fill = publication_palette[[1L]], color = "black", size = 2.2) +
    ggplot2::scale_x_continuous(limits = c(lower, 1), breaks = scales::breaks_pretty(n = 6)) +
    publication_theme() + ggplot2::theme(legend.position = "none") +
    ggplot2::labs(x = "Area under the curve (95% CI)", y = NULL)
}

run_prediction_validation <- function(task, data, output_dir) {
  readiness <- check_analysis_readiness(task, data)
  result <- new_analysis_result(task, status = if (readiness$status == "BLOCK") "BLOCKED" else "RUNNING")
  result$diagnostics$readiness <- readiness
  if (readiness$status == "BLOCK") return(result)
  analysis <- task$analysis
  required <- unique(c(analysis$outcome, analysis$prediction, analysis$time, analysis$event, unlist(analysis$subgroup_variables %||% list(), use.names = FALSE)))
  required <- required[!is.na(required) & nzchar(required)]
  model_data <- data[stats::complete.cases(data[required]), , drop = FALSE]
  if (identical(analysis$prediction_scale %||% "risk", "linear_predictor")) model_data[[analysis$prediction]] <- stats::plogis(model_data[[analysis$prediction]])
  validation <- if (identical(analysis$validation_type, "binary")) {
    binary_validation(model_data, analysis, task$seed %||% 20260718L)
  } else {
    survival_validation(model_data, analysis)
  }
  subgroups <- prediction_subgroups(model_data, analysis, task$seed %||% 20260718L)
  result$status <- "COMPLETE"
  result$counts <- list(input_n = nrow(data), analysis_n = nrow(model_data), excluded_missing_n = nrow(data) - nrow(model_data), events = sum(model_data[[analysis$outcome]] == 1))
  result$estimates <- list(primary = as_result_rows(validation$metrics), performance_metrics = as_result_rows(validation$metrics), subgroup_performance = if (nrow(subgroups)) as_result_rows(subgroups) else list())
  result$diagnostics$model <- list(
    validation_type = analysis$validation_type,
    prediction_origin = analysis$prediction_origin,
    bootstrap_replicates = validation$bootstrap_replicates %||% NULL,
    horizon = validation$horizon %||% NULL,
    no_model_refitting = TRUE
  )
  result$artifacts$tables$performance_metrics <- write_csv_artifact(validation$metrics, output_dir, "performance_metrics.csv", "prespecified prediction validation metrics")
  result$artifacts$tables$calibration <- write_csv_artifact(validation$calibration, output_dir, "calibration.csv", "calibration by predicted-risk groups")
  if (nrow(subgroups)) result$artifacts$tables$subgroup_performance <- write_csv_artifact(subgroups, output_dir, "subgroup_performance.csv", "prespecified subgroup performance")
  calibration_figure <- plot_calibration_validation(validation$calibration, model_data[[analysis$prediction]])
  artifact <- save_publication_figure(calibration_figure, file.path(output_dir, "figures"), "calibration", task, 5, 5.4)
  artifact$source <- "observed versus predicted outcome risk"
  brier_value <- validation$metrics$estimate[grepl("Brier", validation$metrics$metric)][[1L]]
  artifact$caption <- sprintf("Calibration of predicted risk in the validation data. Points show observed outcome proportions within prespecified risk groups, vertical lines show 95%% confidence intervals, and the lower panel shows the prediction distribution (N = %d; Brier score = %.3f).", result$counts$analysis_n, brier_value)
  result$artifacts$figures$calibration <- artifact
  if (identical(analysis$validation_type, "binary")) {
    result$artifacts$tables$roc <- write_csv_artifact(validation$roc, output_dir, "roc_coordinates.csv", "receiver operating characteristic coordinates")
    result$artifacts$tables$decision_curve <- write_csv_artifact(validation$dca, output_dir, "decision_curve.csv", "decision-curve net benefit")
    roc_figure <- plot_roc_validation(validation$roc, validation$metrics[validation$metrics$metric == "AUC", , drop = FALSE])
    roc_artifact <- save_publication_figure(roc_figure, file.path(output_dir, "figures"), "roc", task, 4.5, 4.5)
    roc_artifact$source <- "external or held-out validation predictions"
    auc_row <- validation$metrics[validation$metrics$metric == "AUC", , drop = FALSE]
    roc_artifact$caption <- sprintf("Receiver operating characteristic curve in the validation data. The solid blue line shows discrimination and the dashed diagonal shows chance performance (N = %d; AUC = %.3f, 95%% CI %.3f-%.3f).", result$counts$analysis_n, auc_row$estimate, auc_row$ci_low, auc_row$ci_high)
    result$artifacts$figures$roc <- roc_artifact
    dca_figure <- plot_decision_curve(validation$dca)
    dca_artifact <- save_publication_figure(dca_figure, file.path(output_dir, "figures"), "decision_curve", task, 7, 4.3)
    dca_artifact$source <- "decision-curve analysis"
    dca_artifact$caption <- sprintf("Decision-curve analysis across prespecified threshold probabilities. Net benefit for the model is compared with treat-all and treat-none strategies (N = %d).", result$counts$analysis_n)
    result$artifacts$figures$decision_curve <- dca_artifact
    if (nrow(subgroups)) {
      subgroup_figure <- plot_subgroup_performance(subgroups, auc_row$estimate)
      subgroup_artifact <- save_publication_figure(subgroup_figure, file.path(output_dir, "figures"), "subgroup_performance", task, 7, max(3.3, 0.42 * nrow(subgroups) + 1.5))
      subgroup_artifact$source <- "prespecified subgroup discrimination"
      subgroup_artifact$caption <- sprintf("Discrimination across prespecified validation subgroups. Points show subgroup AUC estimates, horizontal lines show %.0f%% bootstrap confidence intervals, and the dashed line marks overall AUC %.3f.", 100 * (analysis$confidence_level %||% 0.95), auc_row$estimate)
      result$artifacts$figures$subgroup_performance <- subgroup_artifact
    }
  }
  result
}
