#' Run a validated analysis task
#'
#' @param task Task list or path to JSON/YAML task.
#' @param data Optional data frame. When omitted, data are loaded from the task.
#' @param output_dir Output directory.
#' @param execution_binding Optional checksum-bound execution authorization
#'   binding required by the full-article v1.2 task path.
#' @param planned_display_contract Optional prospective aggregate-only display
#'   contract required by the full-article v1.2 task path.
#' @param planned_display_contract Optional planned full-article display contract.
#' @return Structured result invisibly.
#' @export
run_analysis_task <- function(task, data = NULL, output_dir = NULL, execution_binding = NULL, planned_display_contract = NULL) {
  original_task_path <- if (is.character(task) && length(task) == 1L) task else NULL
  if (is.character(task) && length(task) == 1L) {
    if (file.info(task)$size > 2097152) stop("TASK_BYTE_LIMIT",call.=FALSE)
    task_bytes <- if (tolower(tools::file_ext(task)) == "json") readBin(task,"raw",n=2097153) else NULL
    task_text <- if (!is.null(task_bytes)) rawToChar(task_bytes) else NULL
    if(!is.null(task_text)) Encoding(task_text) <- "UTF-8"
    common_candidate <- if (!is.null(task_text)) jsonlite::fromJSON(task_text,simplifyVector=FALSE) else NULL
    is_module <- isTRUE(common_candidate$schema_version%in%c("clinical-module-task@1.0","clinical-module-task@1.1"))
    is_real <- identical(common_candidate$schema_version,"clinical-real-engineering-task@1.0")
    if(isTRUE(getOption("clinanalysis.common_cli_only",FALSE)) && !is_module && !is_real && !startsWith(common_candidate$schema_version %||% "","clinical-study-input@")) stop("SCHEMA_VERSION_UNSUPPORTED",call.=FALSE)
    if (is_module || is_real || startsWith(common_candidate$schema_version %||% "", "clinical-study-input@")) {
      task <- common_candidate
      attr(task,"common_task_bytes") <- task_bytes
    } else task <- read_analysis_task(task)
  }
  if(identical(task$schema_version,"clinical-real-engineering-task@1.0")) {
    if(!is.null(data)) stop("INLINE_DATA_NOT_SUPPORTED",call.=FALSE)
    return(invisible(run_real_engineering_task(task,output_dir %||% task$execution$output_dir,original_task_path)))
  }
  if(isTRUE(task$schema_version%in%c("clinical-module-task@1.0","clinical-module-task@1.1"))) {
    return(invisible(run_clinical_module(task,data,output_dir,original_task_path)))
  }
  if (startsWith(task$schema_version %||% "", "clinical-study-input@")) {
    return(invisible(run_clinical_common(task, data, output_dir, original_task_path)))
  }
  if ((task$schema_version %||% "") %in% .categorical_gcomp_task_versions) {
    return(invisible(run_categorical_logistic_g_computation(
      task, data, output_dir, execution_binding, planned_display_contract
    )))
  }
  if ((task$schema_version %||% "") %in% .formal_temporal_fg_task_versions) {
    output_dir <- output_dir %||% file.path("outputs", task$analysis_id %||% "formal-failed")
    return(invisible(formal_fg_run_observed(task, data, output_dir)))
  }
  validate_analysis_task(task)
  continuous_binding <- NULL
  if (!is.null(task$analysis$continuous_v4) && is.null(data)) {
    if (is.null(task$analysis$continuous_v4$fixed_knots))
      stop("Bound continuous Cox task requires fixed main-cohort knots.", call. = FALSE)
    row_path <- normalizePath(task$data$path, mustWork = TRUE)
    work_root <- normalizePath(file.path(getwd(), "work"), mustWork = FALSE)
    if (!startsWith(row_path, paste0(work_root, "/")))
      stop("Continuous Cox row input must be inside this analysis module's work.", call. = FALSE)
    manifest_path <- file.path(dirname(row_path), "manifest.json")
    if (!file.exists(manifest_path)) stop("Bound private-cohort manifest is missing.", call. = FALSE)
    manifest <- jsonlite::fromJSON(manifest_path, simplifyVector = FALSE)
    hash <- function(path) digest::digest(file = path, algo = "sha256")
    task_file <- file.path(dirname(row_path), paste0(tools::file_path_sans_ext(basename(row_path)), "-task.json"))
    if (is.null(original_task_path) ||
        !identical(normalizePath(original_task_path, mustWork = TRUE),
                   normalizePath(task_file, mustWork = TRUE)))
      stop("Continuous Cox task must use its bound private-cohort task file.", call. = FALSE)
    if (!identical(manifest$outputs_sha256[[basename(row_path)]], hash(row_path)) ||
        !identical(manifest$outputs_sha256[[basename(task_file)]], hash(task_file)))
      stop("Private-cohort row or task hash drift.", call. = FALSE)
    code_files <- c(r_continuous = "plugin_cause_specific_cox_continuous.R",
                    r_diagnostics = "continuous_mi_diagnostics.R",
                    r_dispatch = "plugin_cause_specific_cox.R", r_run = "run.R")
    for (key in names(code_files))
      if (!identical(manifest$code_sha256[[key]], hash(file.path(getwd(), "R", code_files[[key]]))))
        stop("Continuous Cox code hash drift.", call. = FALSE)
    continuous_binding <- list(manifest_sha256 = hash(manifest_path),
      source_request_sha256 = manifest$source_request_sha256,
      config_sha256 = manifest$config_sha256)
  }
  if (is.null(data)) data <- load_analysis_data(task$data)
  output_dir <- output_dir %||% file.path("outputs", task$analysis_id)
  if (!is.null(task$analysis$continuous_v4) && file.exists(output_dir))
    stop("Continuous Cox output directory must be new; no overwrite.", call. = FALSE)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  plugin <- get_analysis_plugin(task$analysis$method)
  result <- tryCatch(
    plugin(task, data, output_dir),
    error = function(e) {
      failed <- new_analysis_result(task, status = "FAILED")
      failed$warnings[[1L]] <- list(
        code = "ANALYSIS_ERROR", severity = "BLOCK", message = conditionMessage(e)
      )
      failed
    }
  )
  if (!is.null(continuous_binding)) result$provenance$cohort_binding <- continuous_binding
  table1 <- build_table1(task, data)
  if (!is.null(table1)) {
    if (identical(table1$status, "COMPLETE")) {
      result$tables$table1 <- table1[setdiff(names(table1), c("formatted", "statistics"))]
      result$tables$table1$rows <- lapply(seq_len(nrow(table1$formatted)), function(i) as.list(table1$formatted[i, , drop = FALSE]))
      result$artifacts$tables$table1 <- write_table1_artifacts(table1, output_dir)
      if (table1$group_missing_n > 0L) {
        result$warnings[[length(result$warnings) + 1L]] <- list(
          code = "TABLE1_GROUP_MISSING", severity = "WARNING",
          message = sprintf("Table 1 excluded %d rows with missing group assignment.", table1$group_missing_n)
        )
      }
    } else {
      result$warnings[[length(result$warnings) + 1L]] <- list(
        code = table1$code, severity = "BLOCK",
        message = "Table 1 could not be generated; the primary analysis result remains unchanged."
      )
      result$tables$table1 <- table1
    }
  }
  result <- normalize_result_for_review(result)
  effects <- collect_effect_estimates(result)
  if (nrow(effects)) {
    result$artifacts$tables$effect_estimates <- list(
      path = normalizePath(file.path(output_dir, "effect_estimates.csv"), mustWork = FALSE),
      source = "estimates"
    )
  }
  if (isTRUE(task$outputs$html_report %||% TRUE)) {
    report_path <- write_technical_report(result, output_dir)
    result$artifacts$report <- list(path = report_path, format = "html")
  }
  figure_manifest_path <- write_figure_manifest(result, output_dir)
  if (!is.null(figure_manifest_path)) result$artifacts$figure_manifest <- list(path = figure_manifest_path, format = "markdown")
  result$artifacts$audit_manifest <- list(path = normalizePath(file.path(output_dir, "audit_manifest.json"), mustWork = FALSE), format = "json")
  result$artifacts$review <- list(directory = normalizePath(file.path(output_dir, "review"), mustWork = FALSE), mode = "READ_ONLY_INPUT")
  write_result_bundle(result, output_dir)
  review_bundle <- write_review_bundle(result, task, output_dir)
  write_audit_manifest(result, task, output_dir, review_bundle)
  invisible(result)
}
