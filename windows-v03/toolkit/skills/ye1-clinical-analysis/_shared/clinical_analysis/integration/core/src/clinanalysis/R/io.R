#' Load a standardized analysis data set
#'
#' @param data_spec Task `data` section.
#' @return A data frame.
#' @export
load_analysis_data <- function(data_spec) {
  path <- normalizePath(data_spec$path, mustWork = FALSE)
  if (!file.exists(path)) stop(sprintf("Analysis data do not exist: %s", path), call. = FALSE)
  format <- tolower(data_spec$format)
  data <- switch(
    format,
    csv = utils::read.csv(path, check.names = FALSE),
    rds = readRDS(path),
    parquet = {
      if (!requireNamespace("arrow", quietly = TRUE)) {
        stop("Package 'arrow' is required to read Parquet data.", call. = FALSE)
      }
      as.data.frame(arrow::read_parquet(path))
    },
    stop(sprintf("Unsupported data format: %s", format), call. = FALSE)
  )
  if (!is.data.frame(data)) stop("Loaded analysis data must be a data frame.", call. = FALSE)
  data
}

#' Write a machine-readable result bundle
#'
#' @param result Structured analysis result.
#' @param output_dir Destination directory.
#' @return Output directory invisibly.
#' @export
write_result_bundle <- function(result, output_dir) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  known_tables <- c(
    "primary_estimate.csv", "standardized_risks.csv", "effect_estimates.csv",
    "cause_specific_estimates.csv", "cumulative_incidence.csv",
    "readiness_findings.csv"
  )
  stale_tables <- file.path(output_dir, known_tables)
  unlink(stale_tables[file.exists(stale_tables)])
  jsonlite::write_json(
    result,
    file.path(output_dir, "result.json"),
    auto_unbox = TRUE,
    pretty = TRUE,
    digits = NA,
    null = "null"
  )

  if (length(result$estimates)) {
    effects <- collect_effect_estimates(result)
    if (nrow(effects)) {
      utils::write.csv(effects, file.path(output_dir, "effect_estimates.csv"), row.names = FALSE)
    }
    primary <- result$estimates[["primary", exact = TRUE]]
    if (!is.null(primary) && identical(result$method, "modified_poisson")) {
      utils::write.csv(as.data.frame(primary, stringsAsFactors = FALSE), file.path(output_dir, "primary_estimate.csv"), row.names = FALSE)
    }
    standardized <- result$estimates$standardized_risks
    if (length(standardized)) {
      utils::write.csv(do.call(rbind, lapply(standardized, as.data.frame)), file.path(output_dir, "standardized_risks.csv"), row.names = FALSE)
    }
    if (!is.null(result$estimates$primary_event)) {
      event_rows <- lapply(c("primary_event", "competing_event"), function(event_name) {
        estimate <- result$estimates[[event_name]]
        data.frame(
          event = event_name,
          label = estimate$label %||% event_name,
          estimate_type = estimate$estimate_type,
          estimate = estimate$estimate,
          ci_low = estimate$ci_low,
          ci_high = estimate$ci_high,
          p_value = estimate$p_value,
          confidence_level = estimate$confidence_level,
          degrees_freedom = estimate$degrees_freedom,
          imputations = estimate$m,
          stringsAsFactors = FALSE
        )
      })
      utils::write.csv(do.call(rbind, event_rows), file.path(output_dir, "cause_specific_estimates.csv"), row.names = FALSE)
    }
    if (length(result$estimates$cumulative_incidence)) {
      incidence <- do.call(rbind, lapply(result$estimates$cumulative_incidence, as.data.frame, stringsAsFactors = FALSE))
      utils::write.csv(incidence, file.path(output_dir, "cumulative_incidence.csv"), row.names = FALSE)
    }
  }
  findings <- result$diagnostics$readiness$findings %||% list()
  if (length(findings)) {
    readiness <- do.call(rbind, lapply(findings, function(x) {
      data.frame(
        code = x$code %||% "",
        severity = x$severity %||% "",
        message = x$message %||% "",
        stringsAsFactors = FALSE
      )
    }))
    utils::write.csv(readiness, file.path(output_dir, "readiness_findings.csv"), row.names = FALSE)
  }
  invisible(output_dir)
}
