# Origin/purpose transport only. Estimation remains in table1.R / association.py.
study_is_task <- function(task) identical(task$schema_version,"clinical-study-input@1.0")
study_label <- function(task) {
  if(!study_is_task(task)) return("SYNTHETIC TEST ONLY")
  paste(if(identical(task$data_origin,"real"))"REAL DATA" else "SYNTHETIC DATA",
        task$task_purpose,"scientific review pending",sep=" | ")
}
study_result_context <- function(result, task) {
  if(!study_is_task(task)) return(result)
  result$schema_version <- "clinical-analysis-result@1.0"
  result$data_origin <- task$data_origin
  result$task_purpose <- task$task_purpose
  result$test_only <- identical(task$task_purpose,"engineering_test")
  result$limitations <- list("Execution and method eligibility do not establish clinical scientific validity.",
    "Local source bytes are bound; source identity, clinical definitions and host isolation are not authenticated by a hash.")
  if(identical(task$time$policy,"cross_sectional_association"))
    result$limitations <- c(result$limitations,list("Cross-sectional conditional association; no temporal prediction or causal claim."))
  result
}
study_artifact_context <- function(artifact,result) {
  if(!identical(result$schema_version,"clinical-analysis-result@1.0")) return(artifact)
  artifact$data_origin <- result$data_origin
  artifact$task_purpose <- result$task_purpose
  artifact$test_only <- result$test_only
  artifact
}

study_stamp_png <- function(path,result) {
  if(!identical(result$schema_version,"clinical-analysis-result@1.0")) return(invisible(TRUE))
  script <- file.path(.clinical_common$root,"python/clinical_methods/study_artifacts.py")
  log <- file.path(dirname(dirname(path)),"private",paste0(basename(path),"-metadata.log"))
  if(!common_python(script,c(path,result$data_origin,result$task_purpose),log)) stop("PNG_CONTEXT_STAMP_FAILED",call.=FALSE)
  invisible(TRUE)
}
