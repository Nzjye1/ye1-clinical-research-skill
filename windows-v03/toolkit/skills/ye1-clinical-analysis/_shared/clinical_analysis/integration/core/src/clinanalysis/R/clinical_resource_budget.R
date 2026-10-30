# Resource admission only. No estimator, model selection or sampling here.
.clinical_resource_cache <- new.env(parent=emptyenv())
clinical_resource_block <- function(code,detail=list()) {
  stop(structure(list(message=code,call=NULL,detail=detail),class=c("clinical_resource_blocked","error","condition")))
}
clinical_resource_profiles <- function() {
  path <- getOption("clinanalysis.resource_profile_file",NULL)
  if(exists(".clinical_common",inherits=TRUE) && !is.null(.clinical_common$root)) path <- file.path(.clinical_common$root,"config","resource-budget-profiles.json")
  if(is.null(path)||!file.exists(path)) clinical_resource_block("RESOURCE_PROFILE_REQUIRED")
  key <- normalizePath(path,winslash="/",mustWork=TRUE)
  if(!exists(key,envir=.clinical_resource_cache,inherits=FALSE)) assign(key,jsonlite::fromJSON(key,simplifyVector=FALSE),envir=.clinical_resource_cache)
  get(key,envir=.clinical_resource_cache,inherits=FALSE)
}
clinical_resource_budget <- function(resource_budget=NULL,method_id="baseline.table1") {
  cfg <- clinical_resource_profiles();name <- "tabular"
  if(grepl("psm|matching",method_id)) name <- "pair_matching"
  else if(grepl("formal_ph",method_id)) name <- "formal_ph"
  else if(grepl("tree_shap",method_id)) name <- "tree_explanation"
  else if(method_id %in% c("prediction.binary.random_forest","prediction.binary.hist_gradient_boosting")) name <- "tree_training"
  else if(grepl("ipcw",method_id)) name <- "survival_evaluation"
  else if(grepl("interpretation",method_id)) name <- "linear_explanation"
  else if(grepl("prediction.survival.cox",method_id,fixed=TRUE)) name <- "survival_prediction"
  else if(grepl("trajectory|growth|profile",method_id)) name <- "latent_longitudinal"
  p <- cfg$profiles[[name]];d <- cfg$defaults
  out <- list(max_rows=p$default_rows,max_input_bytes=min(cfg$absolute$max_input_bytes,4*d$max_decoded_bytes+1048576),
    max_design_columns=d$max_design_columns,max_work_units=d$max_work_units,max_candidate_pairs=d$max_candidate_pairs,
    max_background_rows=if(is.null(p$default_background_rows))d$max_background_rows else p$default_background_rows,
    max_history_rows=cfg$absolute$max_history_rows)
  if(!is.null(resource_budget)) {
    if(!is.list(resource_budget)||is.null(names(resource_budget))||anyDuplicated(names(resource_budget))||length(setdiff(names(resource_budget),names(out)))) clinical_resource_block("RESOURCE_BUDGET_INVALID")
    for(k in names(resource_budget)) out[[k]] <- resource_budget[[k]]
  }
  ceiling <- cfg$absolute;ceiling$max_rows <- p$ceiling_rows
  if(!is.null(p$ceiling_background_rows)) ceiling$max_background_rows <- p$ceiling_background_rows
  for(k in names(out)) {
    v <- out[[k]]
    if(is.logical(v)||!is.numeric(v)||length(v)!=1L||!is.finite(v)||v!=floor(v)||v<1||v>ceiling[[k]]) clinical_resource_block("RESOURCE_BUDGET_INVALID",list(field=k,maximum=ceiling[[k]]))
  }
  if(out$max_history_rows!=cfg$absolute$max_history_rows) clinical_resource_block("RESOURCE_BUDGET_INVALID",list(field="max_history_rows"))
  out
}
clinical_resource_check_rows <- function(count,budget,kind="input") {
  key <- switch(kind,input="max_rows",background="max_background_rows",history="max_history_rows",clinical_resource_block("RESOURCE_BUDGET_INVALID"))
  code <- switch(kind,input="RESOURCE_ROW_BUDGET_EXCEEDED",background="RESOURCE_BACKGROUND_BUDGET_EXCEEDED",history="RESOURCE_HISTORY_BUDGET_EXCEEDED")
  if(!is.numeric(count)||length(count)!=1L||!is.finite(count)||count<0||count!=floor(count)||count>budget[[key]]) clinical_resource_block(code,list(actual=count,maximum=budget[[key]]))
  invisible(TRUE)
}
clinical_resource_check_design <- function(rows,columns,budget) {
  if(!is.numeric(rows)||!is.numeric(columns)||length(rows)!=1L||length(columns)!=1L||!is.finite(rows)||!is.finite(columns)||rows<0||columns<0) clinical_resource_block("RESOURCE_BUDGET_INVALID")
  if(columns>budget$max_design_columns) clinical_resource_block("RESOURCE_DESIGN_BUDGET_EXCEEDED",list(actual=columns,maximum=budget$max_design_columns))
  work <- as.double(rows)*as.double(columns)*as.double(columns)
  if(!is.finite(work)||work>budget$max_work_units) clinical_resource_block("RESOURCE_WORK_BUDGET_EXCEEDED",list(estimated=work,maximum=budget$max_work_units))
  invisible(TRUE)
}
clinical_resource_check_pairs <- function(treated,controls,budget) {
  pairs <- as.double(treated)*as.double(controls)
  if(!is.finite(pairs)||pairs<0||pairs>budget$max_candidate_pairs) clinical_resource_block("RESOURCE_CANDIDATE_PAIR_BUDGET_EXCEEDED",list(estimated_pairs=pairs,maximum=budget$max_candidate_pairs))
  invisible(TRUE)
}
common_resource_limits <- function(task) {
  if(!study_is_task(task)) return(NULL)
  .clinical_common$normalized$resource_limits
}
