file_md5 <- function(path) {
  unname(tools::md5sum(path))
}

relative_output_path <- function(path, output_dir) {
  normalized <- normalizePath(path, mustWork = FALSE)
  root <- paste0(normalizePath(output_dir, mustWork = TRUE), .Platform$file.sep)
  if (startsWith(normalized, root)) substring(normalized, nchar(root) + 1L) else normalized
}

figure_type_from_name <- function(name) {
  switch(
    name,
    cause_specific_estimates = "forest-plot",
    cumulative_incidence = "other",
    standardized_risk = "other",
    regression_effects = "forest-plot",
    standardized_predictions = "other",
    kaplan_meier = "km",
    cox_effects = "forest-plot",
    fine_gray_effects = "forest-plot",
    longitudinal_trajectory = "other",
    love_plot = "other",
    roc = "roc",
    calibration = "calibration",
    decision_curve = "other",
    subgroup_performance = "forest-plot",
    temporal_performance = "performance",
    event_timing = "clinical-timing",
    robustness = "robustness",
    "other"
  )
}

write_figure_manifest <- function(result, output_dir) {
  figures <- result$artifacts$figures %||% list()
  if (!length(figures)) return(NULL)
  path <- file.path(output_dir, "figures", "_figure_manifest.md")
  rows <- vapply(seq_along(figures), function(i) {
    name <- names(figures)[[i]]
    figure <- figures[[name]]
    primary <- figure$formats$pdf %||% figure$path
    sprintf(
      "| Figure %d | %s | %s | R/ggplot2 | no | 0 | %s |",
      i,
      relative_output_path(primary, output_dir),
      figure_type_from_name(name),
      gsub("\\|", "\\\\|", figure$caption %||% figure$source %||% name)
    )
  }, character(1))
  contents <- c(
    "# Figure Manifest", "",
    sprintf("Generated: %s", format(Sys.Date(), "%Y-%m-%d")),
    "Study type: custom clinical analysis", "",
    "| Figure | Path | Type | Tool | Critic | Rounds | Description |",
    "|---|---|---|---|---|---|---|",
    rows, "", "## Critic notes", "",
    "- Automated format and provenance checks are complete. Independent qualitative figure review is still required before submission."
  )
  writeLines(contents, path, useBytes = TRUE)
  normalizePath(path, mustWork = TRUE)
}

review_gate_status <- function(decision_path, result_checksum, required_roles, analysis_id = NULL) {
  if (!file.exists(decision_path)) {
    return(list(status = "PENDING", reason = "No signed review decision exists."))
  }
  decision <- tryCatch(jsonlite::fromJSON(decision_path, simplifyVector = FALSE), error = function(e) NULL)
  if (is.null(decision)) return(list(status = "INVALID", reason = "Review decision is not valid JSON."))
  if (!identical(decision$result_checksum_md5 %||% "", result_checksum)) {
    return(list(status = "STALE", reason = "Review decision does not match the current result checksum."))
  }
  if (!is.null(analysis_id) && !identical(decision$analysis_id %||% "", analysis_id)) {
    return(list(status = "INVALID", reason = "Review decision analysis_id does not match the current analysis."))
  }
  approvals <- decision$approvals %||% list()
  approval_statuses <- vapply(approvals, function(x) x$status %||% "PENDING", character(1))
  if ("REJECTED" %in% approval_statuses || identical(decision$overall_conclusion %||% "", "REJECTED")) {
    return(list(status = "REJECTED", reason = "At least one reviewer rejected the result."))
  }
  if ("CHANGES_REQUIRED" %in% approval_statuses || identical(decision$overall_conclusion %||% "", "CHANGES_REQUIRED")) {
    return(list(status = "CHANGES_REQUIRED", reason = "At least one reviewer requires changes."))
  }
  approved_roles <- vapply(approvals, function(x) {
    if (identical(x$status %||% "", "APPROVED")) x$role %||% "" else ""
  }, character(1))
  missing_roles <- setdiff(required_roles, approved_roles)
  if (length(missing_roles)) {
    return(list(status = "PENDING", reason = "One or more required approvals are missing.", missing_roles = as.list(missing_roles)))
  }
  if (!identical(decision$overall_conclusion %||% "", "APPROVED")) {
    return(list(status = "PENDING", reason = "Role approvals are present but overall_conclusion is not APPROVED."))
  }
  list(status = "APPROVED", reason = "All required roles approved the current result checksum.")
}

write_review_bundle <- function(result, task, output_dir) {
  review_dir <- file.path(output_dir, "review")
  dir.create(review_dir, recursive = TRUE, showWarnings = FALSE)
  task_path <- file.path(review_dir, "analysis_task.json")
  jsonlite::write_json(task, task_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  result_path <- file.path(output_dir, "result.json")
  result_checksum <- file_md5(result_path)
  required_roles <- unlist(
    task$review$required_roles %||% list("human_statistician", "independent_review_agent"),
    use.names = FALSE
  )
  decision_path <- file.path(review_dir, "decision.json")
  gate <- review_gate_status(decision_path, result_checksum, required_roles, result$analysis_id)

  template <- list(
    schema_version = "0.1.0",
    analysis_id = result$analysis_id,
    result_checksum_md5 = result_checksum,
    overall_conclusion = "PENDING",
    approvals = lapply(required_roles, function(role) list(
      role = role, status = "PENDING", reviewer = NULL,
      reviewed_at_utc = NULL, conclusion = NULL, required_actions = list()
    ))
  )
  template_path <- file.path(review_dir, "decision.template.json")
  jsonlite::write_json(template, template_path, auto_unbox = TRUE, pretty = TRUE, null = "null")

  safe_files <- list.files(output_dir, recursive = TRUE, full.names = TRUE)
  safe_files <- safe_files[file.info(safe_files)$isdir %in% FALSE]
  safe_files <- safe_files[!grepl("(^|/)review/decision\\.json$", safe_files)]
  reviewer_input <- list(
    schema_version = "0.1.0",
    analysis_id = result$analysis_id,
    mode = "READ_ONLY",
    patient_level_data_included = FALSE,
    result_checksum_md5 = result_checksum,
    allowed_files = as.list(sort(unique(c(
      vapply(safe_files, relative_output_path, character(1), output_dir = output_dir),
      "audit_manifest.json"
    )))),
    required_checks = list(
      "estimand_and_SAP_alignment", "analysis_population", "missing_data",
      "model_diagnostics", "effect_estimates", "table_figure_consistency",
      "warnings_and_sensitivities", "publication_readiness"
    ),
    forbidden_actions = list("modify_result", "access_patient_level_data", "approve_without_checksum_match")
  )
  reviewer_path <- file.path(review_dir, "reviewer_input.json")
  jsonlite::write_json(reviewer_input, reviewer_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  gate_path <- file.path(review_dir, "review_gate.json")
  jsonlite::write_json(gate, gate_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  list(
    task_path = normalizePath(task_path, mustWork = TRUE),
    reviewer_input_path = normalizePath(reviewer_path, mustWork = TRUE),
    decision_template_path = normalizePath(template_path, mustWork = TRUE),
    decision_path = normalizePath(decision_path, mustWork = FALSE),
    gate_path = normalizePath(gate_path, mustWork = TRUE),
    gate = gate,
    result_checksum_md5 = result_checksum
  )
}

write_audit_manifest <- function(result, task, output_dir, review_bundle) {
  manifest_path <- file.path(output_dir, "audit_manifest.json")
  files <- list.files(output_dir, recursive = TRUE, full.names = TRUE)
  files <- files[file.info(files)$isdir %in% FALSE]
  files <- setdiff(files, manifest_path)
  artifacts <- lapply(sort(files), function(path) list(
    path = relative_output_path(path, output_dir),
    size_bytes = unname(file.info(path)$size),
    checksum_md5 = file_md5(path),
    classification = "aggregate_or_configuration"
  ))
  data_path <- task$data$path
  input_provenance <- list(
    file_name = basename(data_path),
    size_bytes = if (file.exists(data_path)) unname(file.info(data_path)$size) else NULL,
    checksum_md5 = if (file.exists(data_path)) file_md5(data_path) else NULL,
    patient_level_data_embedded_in_bundle = FALSE
  )
  manifest <- list(
    schema_version = "0.1.0",
    analysis_id = result$analysis_id,
    generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
    task_checksum_md5 = file_md5(review_bundle$task_path),
    result_checksum_md5 = review_bundle$result_checksum_md5,
    input_provenance = input_provenance,
    artifacts = artifacts,
    review_gate = review_bundle$gate,
    writing_allowed = identical(review_bundle$gate$status, "APPROVED") || !isTRUE(task$review$writing_requires_approval %||% TRUE)
  )
  jsonlite::write_json(manifest, manifest_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  normalizePath(manifest_path, mustWork = TRUE)
}

#' Refresh the checksum-bound review gate without rerunning an analysis
#'
#' @param output_dir Existing analysis output directory.
#' @return Structured review-gate status invisibly.
#' @export
refresh_review_gate <- function(output_dir) {
  result_path <- file.path(output_dir, "result.json")
  task_path <- file.path(output_dir, "review", "analysis_task.json")
  decision_path <- file.path(output_dir, "review", "decision.json")
  if (!file.exists(result_path) || !file.exists(task_path)) {
    stop("Output directory does not contain result.json and review/analysis_task.json.", call. = FALSE)
  }
  result <- jsonlite::fromJSON(result_path, simplifyVector = FALSE)
  task <- jsonlite::fromJSON(task_path, simplifyVector = FALSE)
  checksum <- file_md5(result_path)
  required_roles <- unlist(
    task$review$required_roles %||% list("human_statistician", "independent_review_agent"),
    use.names = FALSE
  )
  gate <- review_gate_status(decision_path, checksum, required_roles, result$analysis_id)
  gate_path <- file.path(output_dir, "review", "review_gate.json")
  jsonlite::write_json(gate, gate_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  manifest_path <- file.path(output_dir, "audit_manifest.json")
  if (file.exists(manifest_path)) {
    manifest <- jsonlite::fromJSON(manifest_path, simplifyVector = FALSE)
    manifest$review_gate <- gate
    manifest$writing_allowed <- identical(gate$status, "APPROVED") || !isTRUE(task$review$writing_requires_approval %||% TRUE)
    manifest$review_gate_refreshed_at_utc <- format(Sys.time(), tz = "UTC", usetz = TRUE)
    jsonlite::write_json(manifest, manifest_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  }
  invisible(gate)
}
