html_escape <- function(x) {
  x <- gsub("&", "&amp;", as.character(x), fixed = TRUE)
  x <- gsub("<", "&lt;", x, fixed = TRUE)
  x <- gsub(">", "&gt;", x, fixed = TRUE)
  x <- gsub('"', "&quot;", x, fixed = TRUE)
  x
}

html_table <- function(data) {
  if (is.null(data) || !nrow(data)) return("<p class=\"muted\">None.</p>")
  headings <- paste0("<th>", html_escape(names(data)), "</th>", collapse = "")
  rows <- apply(data, 1L, function(row) {
    paste0("<tr>", paste0("<td>", html_escape(row), "</td>", collapse = ""), "</tr>")
  })
  paste0("<table><thead><tr>", headings, "</tr></thead><tbody>", paste(rows, collapse = ""), "</tbody></table>")
}

format_report_number <- function(x) {
  if (!is.numeric(x)) return(as.character(x))
  vapply(x, function(value) {
    if (is.na(value)) return("NA")
    if (abs(value - round(value)) < sqrt(.Machine$double.eps) && abs(value) >= 1) {
      return(formatC(value, digits = 0, format = "f", big.mark = ","))
    }
    formatC(value, digits = 4, format = "fg")
  }, character(1))
}

report_count_table <- function(result) {
  if (!length(result$counts)) return(data.frame())
  data.frame(
    measure = names(result$counts),
    value = vapply(result$counts, function(x) paste(format_report_number(x), collapse = ", "), character(1)),
    stringsAsFactors = FALSE
  )
}

report_estimate_table <- function(result) {
  if (identical(result$method, "modified_poisson")) {
    x <- result$estimates$primary
    if (is.null(x)) return(data.frame())
    return(data.frame(
      estimand = x$contrast,
      measure = "Risk ratio",
      estimate = format_report_number(x$estimate),
      confidence_interval = sprintf("%s to %s", format_report_number(x$ci_low), format_report_number(x$ci_high)),
      p_value = format_report_number(x$p_value),
      stringsAsFactors = FALSE
    ))
  }
  if (identical(result$method, "cause_specific_cox")) {
    keys <- c("primary_event", "competing_event")
    available <- keys[vapply(keys, function(key) !is.null(result$estimates[[key]]), logical(1))]
    if (!length(available)) return(data.frame())
    return(do.call(rbind, lapply(available, function(key) {
      x <- result$estimates[[key]]
      data.frame(
        estimand = x$label %||% gsub("_", " ", key),
        measure = "Cause-specific hazard ratio",
        estimate = format_report_number(x$estimate),
        confidence_interval = sprintf("%s to %s", format_report_number(x$ci_low), format_report_number(x$ci_high)),
        p_value = format_report_number(x$p_value),
        stringsAsFactors = FALSE
      )
    })))
  }
  rows <- collect_effect_estimates(result)
  if (nrow(rows)) {
    return(data.frame(
      estimand = rows$estimand,
      measure = gsub("_", " ", rows$measure),
      estimate = format_report_number(rows$estimate),
      confidence_interval = ifelse(
        is.na(rows$ci_low) | is.na(rows$ci_high), "Not reported",
        sprintf("%s to %s", format_report_number(rows$ci_low), format_report_number(rows$ci_high))
      ),
      p_value = format_report_number(rows$p_value), stringsAsFactors = FALSE
    ))
  }
  data.frame()
}

report_readiness_table <- function(result) {
  findings <- result$diagnostics$readiness$findings %||% list()
  if (!length(findings)) return(data.frame())
  do.call(rbind, lapply(findings, function(x) data.frame(
    severity = x$severity %||% "",
    code = x$code %||% "",
    message = x$message %||% "",
    stringsAsFactors = FALSE
  )))
}

report_table1 <- function(result) {
  rows <- result$tables$table1$rows %||% list()
  if (!length(rows)) return(data.frame())
  do.call(rbind, lapply(rows, function(row) as.data.frame(row, stringsAsFactors = FALSE, check.names = FALSE)))
}

report_diagnostic_table <- function(result) {
  items <- result$diagnostic_index %||% list()
  if (!length(items)) return(data.frame())
  do.call(rbind, lapply(items, function(x) data.frame(
    status = x$status %||% "", code = x$code %||% "",
    message = x$message %||% "", source = x$source %||% "",
    stringsAsFactors = FALSE
  )))
}

report_warning_table <- function(result) {
  warnings <- result$warnings %||% list()
  if (!length(warnings)) return(data.frame())
  do.call(rbind, lapply(warnings, function(x) data.frame(
    severity = x$severity %||% "", code = x$code %||% "",
    message = x$message %||% "", stringsAsFactors = FALSE
  )))
}

report_rows_table <- function(rows) {
  if (is.null(rows) || !length(rows)) return(data.frame())
  do.call(rbind, lapply(rows, function(row) as.data.frame(row, stringsAsFactors = FALSE, check.names = FALSE)))
}

report_temporal_performance_table <- function(result) {
  data <- report_rows_table(result$estimates$performance_metrics %||% list())
  if (!nrow(data)) return(data.frame())
  labels <- c(baseline = "Baseline model", minimal_adjusted = "Minimal model")
  data$model <- unname(labels[as.character(data$model)] %||% as.character(data$model))
  data.frame(
    model = data$model,
    metric = data$metric,
    estimate = format_report_number(data$estimate),
    confidence_interval = sprintf("%s to %s", format_report_number(data$ci_low), format_report_number(data$ci_high)),
    stringsAsFactors = FALSE
  )
}

report_temporal_sensitivity_table <- function(result) {
  data <- report_rows_table(result$sensitivities$estimates %||% list())
  if (!nrow(data)) return(data.frame())
  labels <- c(eight_hour_landmark = "Eight-hour landmark", restart_only = "Recorded restart only")
  data$sensitivity <- unname(labels[as.character(data$sensitivity_id)])
  data$sensitivity[is.na(data$sensitivity)] <- as.character(data$sensitivity_id[is.na(data$sensitivity)])
  data.frame(
    sensitivity = data$sensitivity,
    metric = data$metric,
    estimate = format_report_number(data$estimate),
    confidence_interval = sprintf("%s to %s", format_report_number(data$ci_low), format_report_number(data$ci_high)),
    refit = ifelse(as.logical(data$refit), "Yes, prespecified", "No"),
    stringsAsFactors = FALSE
  )
}

report_temporal_timing_table <- function(result) {
  data <- report_rows_table(result$estimates$timing %||% list())
  if (!nrow(data)) return(data.frame())
  data.frame(
    dimension = gsub("_", " ", data$dimension),
    level = data$level,
    n = format_report_number(data$n),
    denominator = format_report_number(data$denominator),
    proportion = format_report_number(data$proportion),
    confidence_interval = sprintf("%s to %s", format_report_number(data$ci_low), format_report_number(data$ci_high)),
    stringsAsFactors = FALSE
  )
}

report_temporal_qc_table <- function(result) {
  data <- report_rows_table(result$diagnostics$qc %||% list())
  if (!nrow(data)) return(data.frame())
  keep <- c(
    "future_predictor_violation_n", "outcome_at_or_before_landmark_n", "drug_free_rule_violation_n",
    "invalid_interval_count", "restart_within_15_minutes_n", "restart_within_30_minutes_n",
    "restart_within_60_minutes_n", "restart_same_drug_n", "episode_duration_max_hours",
    "episode_duration_gt_168h_n", "episode_duration_gt_336h_n", "episode_record_count_max",
    "icu_exit_before_horizon_event_free_n", "hospital_discharge_before_horizon_event_free_n"
  )
  labels <- c(
    future_predictor_violation_n = "Predictor future-information violations",
    outcome_at_or_before_landmark_n = "Outcomes at or before landmark",
    drug_free_rule_violation_n = "Six-hour drug-free-rule violations",
    invalid_interval_count = "Invalid source intervals reported",
    restart_within_15_minutes_n = "Recorded restarts within 15 minutes after landmark",
    restart_within_30_minutes_n = "Recorded restarts within 30 minutes after landmark",
    restart_within_60_minutes_n = "Recorded restarts within 60 minutes after landmark",
    restart_same_drug_n = "Recorded restarts using a prior-episode drug",
    episode_duration_max_hours = "Maximum episode duration, hours",
    episode_duration_gt_168h_n = "Episodes longer than 7 days",
    episode_duration_gt_336h_n = "Episodes longer than 14 days",
    episode_record_count_max = "Maximum source records in one episode",
    icu_exit_before_horizon_event_free_n = "Event-free patients leaving the index ICU before 24 hours",
    hospital_discharge_before_horizon_event_free_n = "Event-free patients discharged before 24 hours"
  )
  data <- data[data$metric %in% keep, , drop = FALSE]
  data$metric <- factor(data$metric, levels = keep)
  data <- data[order(data$metric), , drop = FALSE]
  data.frame(
    check = unname(labels[as.character(data$metric)]),
    value = format_report_number(data$value),
    denominator = format_report_number(data$denominator),
    stringsAsFactors = FALSE
  )
}

report_temporal_calibration_note <- function(result) {
  data <- report_rows_table(result$estimates$performance_metrics %||% list())
  data <- data[data$model == "minimal_adjusted", , drop = FALSE]
  if (!nrow(data)) return("Calibration summary unavailable.")
  metric <- stats::setNames(data$estimate, data$metric)
  observed <- unname(metric[["Observed risk"]]); predicted <- unname(metric[["Mean predicted risk"]])
  intercept <- unname(metric[["Calibration intercept"]]); slope <- unname(metric[["Calibration slope"]])
  oe <- unname(metric[["Observed/expected ratio"]])
  if (any(!is.finite(c(observed, predicted, intercept, slope, oe)))) return("Calibration summary unavailable.")
  sprintf(
    paste0(
      "In temporal validation, observed risk was %s and mean predicted risk was %s ",
      "(absolute underprediction %s). The calibration intercept was %s, slope %s, and observed/expected ratio %s. ",
      "These values must be reported as temporal calibration limitations; no recalibration was performed."
    ),
    format_report_number(observed), format_report_number(predicted), format_report_number(observed - predicted),
    format_report_number(intercept), format_report_number(slope), format_report_number(oe)
  )
}

report_temporal_semantic_audit <- function(output_dir) {
  path <- file.path(output_dir, "review", "evidence", "restart_boundary_semantic_audit.json")
  if (!file.exists(path)) return(list(table = data.frame(), note = "No post-analysis restart-boundary receipt is attached."))
  audit <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE), error = function(e) NULL)
  if (is.null(audit)) return(list(table = data.frame(), note = "The attached restart-boundary receipt is not valid JSON."))
  boundary <- audit$boundary_source_reconciliation %||% list()
  table <- data.frame(
    check = c(
      "Receipt status", "Recorded restart events", "Missing prior boundary sources",
      "Missing restart boundary sources", "Valid records overlapping the six-hour window",
      "Same orderid", "Same linkorderid", "Cross-stay boundary pairs",
      "Prior continueinnextdept", "Restart continueinnextdept", "Outcome-label changes required"
    ),
    value = c(
      audit$status %||% "", audit$restart_events %||% NA,
      boundary$missing_prior_boundary_source %||% NA, boundary$missing_restart_boundary_source %||% NA,
      boundary$valid_record_overlaps_six_hour_window %||% NA, boundary$same_orderid %||% NA,
      boundary$same_linkorderid %||% NA, boundary$cross_stay_only %||% NA,
      boundary$prior_continueinnextdept %||% NA, boundary$restart_continueinnextdept %||% NA,
      audit$label_changes_required %||% NA
    ),
    stringsAsFactors = FALSE
  )
  list(
    table = table,
    note = paste0(
      "This receipt supports only the frozen recorded endpoint. Use the wording 'new recorded vasopressor episode after the six-hour vasopressor-free landmark'; ",
      "do not infer clinician-assessed readiness, uninterrupted unrecorded infusion, treatment effect, or unqualified clinical failure."
    )
  )
}

report_review_gate <- function(output_dir) {
  path <- file.path(output_dir, "review", "review_gate.json")
  if (!file.exists(path)) return("PENDING")
  gate <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE), error = function(e) NULL)
  gate$status %||% "PENDING"
}

report_figure_cards <- function(result, output_dir) {
  figures <- result$artifacts$figures %||% list()
  if (!length(figures)) return("<p class=\"muted\">No figure was produced.</p>")
  paste(vapply(names(figures), function(name) {
    figure <- figures[[name]]
    png <- figure$formats$png %||% figure$path
    relative <- file.path("figures", basename(png))
    paste0(
      "<figure><img src=\"", html_escape(relative), "\" alt=\"", html_escape(name), "\">",
      "<figcaption><strong>", html_escape(gsub("_", " ", name)), ".</strong> ",
      html_escape(figure$caption %||% figure$source %||% ""), "</figcaption></figure>"
    )
  }, character(1)), collapse = "")
}

write_technical_report <- function(result, output_dir) {
  status_class <- if (identical(result$status, "COMPLETE")) "ok" else "alert"
  multistate <- result$diagnostics$multistate %||% list(status = "Not applicable")
  temporal_sections <- ""
  if (identical(result$method, "temporal_logistic_prediction")) {
    semantic <- report_temporal_semantic_audit(output_dir)
    temporal_sections <- paste0(
      "<section class=\"card\"><h2>Temporal validation performance</h2>", html_table(report_temporal_performance_table(result)),
      "<p class=\"callout\">", html_escape(report_temporal_calibration_note(result)), "</p></section>",
      "<section class=\"card\"><h2>Prespecified sensitivity analyses</h2>", html_table(report_temporal_sensitivity_table(result)),
      "<p class=\"muted\">Both checks retain the frozen predictor specification; no result-driven model, threshold, subgroup, or additional sensitivity was added.</p></section>",
      "<section class=\"card\"><h2>When the first recorded event occurred</h2>", html_table(report_temporal_timing_table(result)), "</section>",
      "<section class=\"card\"><h2>Episode, timeline, and observation-boundary QC</h2>", html_table(report_temporal_qc_table(result)),
      "<p class=\"muted\">Index-ICU exit does not end hospitalization-level inputevents surveillance. Hospital discharge ends observable in-hospital follow-up; post-discharge events are outside the estimand. Extreme episode chains are retained as prespecified source-record limitations.</p></section>",
      "<section class=\"card\"><h2>Post-analysis restart-boundary receipt</h2>", html_table(semantic$table),
      "<p class=\"callout\">", html_escape(semantic$note), "</p><p><a href=\"review/evidence/restart_boundary_semantic_audit.json\">Machine-readable semantic audit receipt</a></p></section>"
    )
  }
  current_gate <- report_review_gate(output_dir)
  body <- paste0(
    "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">",
    "<title>", html_escape(result$analysis_id), " - technical report</title>",
    "<style>",
    "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;color:#17212b;background:#f4f6f8;margin:0;line-height:1.5}",
    ".page{max-width:1040px;margin:32px auto;padding:0 24px}.hero,.card{background:white;border:1px solid #dfe5ea;border-radius:10px;padding:24px;margin-bottom:18px}",
    "h1{font-size:27px;margin:4px 0 6px}h2{font-size:18px;margin:0 0 14px}.eyebrow{color:#52606d;font-size:13px;text-transform:uppercase;letter-spacing:.06em}",
    ".status{display:inline-block;border-radius:999px;padding:4px 10px;font-size:12px;font-weight:700}.ok{background:#dff5e8;color:#146c43}.alert{background:#fee5e5;color:#9f2525}",
    ".meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-top:18px}.meta div{background:#f7f9fa;padding:10px 12px;border-radius:6px}",
    "table{border-collapse:collapse;width:100%;font-size:14px}th{text-align:left;background:#edf2f5}th,td{border-bottom:1px solid #dfe5ea;padding:9px 10px;vertical-align:top}",
    "figure{margin:12px 0 24px}img{display:block;max-width:100%;height:auto;margin:auto}figcaption{color:#52606d;font-size:13px;margin-top:8px}",
    ".muted{color:#687785}.callout{background:#eef5f8;border-left:4px solid #3b718a;padding:12px 14px}.checklist li{margin:7px 0}@media print{body{background:white}.page{margin:0;max-width:none}.hero,.card{break-inside:avoid;border-color:#bbb}}",
    "</style></head><body><main class=\"page\">",
    "<section class=\"hero\"><div class=\"eyebrow\">Clinical analysis technical report</div>",
    "<h1>", html_escape(result$analysis_id), "</h1><span class=\"status ", status_class, "\">", html_escape(result$status), "</span>",
    "<div class=\"meta\"><div><strong>Method</strong><br>", html_escape(result$method), "</div>",
    "<div><strong>Schema</strong><br>", html_escape(result$schema_version), "</div>",
    "<div><strong>Generated (UTC)</strong><br>", html_escape(result$provenance$generated_at_utc), "</div>",
    "<div><strong>R</strong><br>", html_escape(result$provenance$r_version), "</div></div></section>",
    "<section class=\"card\"><h2>Analysis population</h2>", html_table(report_count_table(result)), "</section>",
    "<section class=\"card\"><h2>Table 1. Baseline characteristics</h2>", html_table(report_table1(result)),
    "<p class=\"muted\">Values are mean (SD), median [Q1, Q3], or n (%), as prespecified. SMD is the absolute standardized mean difference.</p></section>",
    "<section class=\"card\"><h2>Primary estimates</h2>", html_table(report_estimate_table(result)), "</section>",
    temporal_sections,
    "<section class=\"card\"><h2>Readiness findings</h2>", html_table(report_readiness_table(result)), "</section>",
    "<section class=\"card\"><h2>Diagnostic index</h2>", html_table(report_diagnostic_table(result)), "</section>",
    "<section class=\"card\"><h2>Warnings</h2>", html_table(report_warning_table(result)), "</section>",
    "<section class=\"card\"><h2>Figures</h2>", report_figure_cards(result, output_dir), "</section>",
    "<section class=\"card\"><h2>Review notes</h2><p><strong>Multistate gate:</strong> ", html_escape(multistate$status), "</p>",
    "<p><strong>Writing gate:</strong> ", html_escape(current_gate), ". Writing remains disallowed until checksum-bound human and independent-agent approvals are recorded.</p>",
    "<p><a href=\"review/reviewer_input.json\">Reviewer input</a> | <a href=\"review/decision.template.json\">Decision template</a> | <a href=\"review/review_gate.json\">Current gate</a></p>",
    "<ul class=\"checklist\"><li>Confirm cohort, exposure, outcome, time zero, and censoring definitions against the approved SAP.</li>",
    "<li>Review model diagnostics, missing-data assumptions, and every warning in result.json.</li>",
    "<li>Confirm that figure labels and numerical precision match the target journal.</li>",
    "<li>Human statistical approval is required before manuscript writing.</li></ul></section>",
    "</main></body></html>"
  )
  path <- file.path(output_dir, "technical_report.html")
  writeLines(body, path, useBytes = TRUE)
  normalizePath(path, mustWork = TRUE)
}
