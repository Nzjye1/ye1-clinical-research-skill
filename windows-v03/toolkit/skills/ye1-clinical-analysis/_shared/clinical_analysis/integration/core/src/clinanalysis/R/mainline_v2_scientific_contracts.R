validate_mainline_v2_cohort_derivation <- function(flow, primary_analysis_n) {
  required <- c(
    "step_order", "step_id", "n_entered", "n_excluded", "n_remaining",
    "exclusion_reason"
  )
  if (!is.data.frame(flow) || nrow(flow) < 3L || !all(required %in% names(flow))) {
    stop("V2 cohort derivation is incomplete", call. = FALSE)
  }
  if (!identical(as.integer(flow$step_order), seq_len(nrow(flow)))) {
    stop("V2 cohort steps are not contiguous", call. = FALSE)
  }
  if (any(flow$n_entered < 0 | flow$n_excluded < 0 | flow$n_remaining < 0)) {
    stop("V2 cohort counts cannot be negative", call. = FALSE)
  }
  if (any(flow$n_entered != flow$n_excluded + flow$n_remaining)) {
    stop("V2 cohort arithmetic does not reconcile", call. = FALSE)
  }
  if (nrow(flow) > 1L &&
      any(flow$n_entered[-1L] != flow$n_remaining[-nrow(flow)])) {
    stop("V2 cohort derivation steps do not chain", call. = FALSE)
  }
  if (any(!nzchar(trimws(flow$exclusion_reason)))) {
    stop("V2 cohort exclusion reason is empty", call. = FALSE)
  }
  if (flow$n_remaining[[nrow(flow)]] != primary_analysis_n) {
    stop("V2 terminal cohort count differs from primary analysis n", call. = FALSE)
  }
  invisible(TRUE)
}

validate_mainline_v2_display_semantics <- function(display, source) {
  if (!identical(display$semantic_status, "PASS")) {
    stop("V2 display semantic review did not PASS", call. = FALSE)
  }
  if (identical(display$role, "COHORT_FLOW")) {
    required <- c("n_entered", "n_excluded", "n_remaining", "exclusion_reason")
    if (!identical(display$display_type, "FLOW_DIAGRAM") ||
        !identical(display$source_object, "cohort_derivation") ||
        !all(required %in% display$source_fields) ||
        identical(display$substitution_type, "SOURCE_DISTRIBUTION_BAR_CHART")) {
      stop("source distribution cannot satisfy V2 cohort flow semantics", call. = FALSE)
    }
    validate_mainline_v2_cohort_derivation(source, display$primary_analysis_n)
  }
  invisible(TRUE)
}

validate_mainline_v2_sensitivity_information <- function(sensitivities) {
  if (!is.data.frame(sensitivities) ||
      !all(c("information_status", "supports_robustness") %in% names(sensitivities))) {
    stop("V2 sensitivity information is incomplete", call. = FALSE)
  }
  if (!any(sensitivities$information_status == "INFORMATIVE")) {
    stop("no informative V2 sensitivity analysis", call. = FALSE)
  }
  invalid <- sensitivities$information_status == "NON_INFORMATIVE" &
    sensitivities$supports_robustness
  if (any(invalid)) {
    stop("non-informative sensitivity cannot support robustness", call. = FALSE)
  }
  invisible(TRUE)
}

build_mainline_v2_cohort_flow_figure <- function(flow, primary_analysis_n) {
  validate_mainline_v2_cohort_derivation(flow, primary_analysis_n)
  plot_data <- transform(
    flow,
    label = paste0(
      step_id, "\nEntered: ", n_entered, "; Excluded: ", n_excluded,
      "\nRemaining: ", n_remaining, "\n", exclusion_reason
    )
  )
  ggplot2::ggplot(plot_data, ggplot2::aes(x = 1, y = -step_order, label = label)) +
    ggplot2::geom_label(size = 3.2, label.size = 0.25) +
    ggplot2::geom_segment(
      data = plot_data[-nrow(plot_data), , drop = FALSE],
      ggplot2::aes(x = 1, xend = 1, y = -step_order - 0.25, yend = -step_order - 0.75),
      inherit.aes = FALSE,
      arrow = grid::arrow(length = grid::unit(0.12, "inches"))
    ) +
    ggplot2::scale_x_continuous(limits = c(0.7, 1.3)) +
    ggplot2::theme_void() +
    ggplot2::labs(title = "Cohort derivation")
}
