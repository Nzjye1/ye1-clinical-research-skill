# Thin compatibility projection. Common prediction code remains sole metric/plot owner.
# The local proxy chooses the existing binary branch only; output method identity stays true.
project_nonlinear_prediction <- function(calculated,task,output_dir,run_id="nonlinear-module",origin_context=NULL) {
  record <- calculated$record
  result <- common_empty_result(task,run_id)
  result$schema_version <- "nonlinear-module-preview/1.0.0"
  result$method_id <- task$analysis$method_id
  result$study_id <- "synthetic_nonlinear_module"
  origin_label <- NULL
  if(!is.null(origin_context)) {
    result$origin_context <- origin_context
    # The root helper validates origin/purpose/test_only/pending. The preview
    # schema is retained; it is never forged to select a source-aware label.
    origin_label <- common_result_label(result)
    if(!is.character(task$study_id)||length(task$study_id)!=1L||!nzchar(task$study_id)) stop("PROJECTION_STUDY_ID_REQUIRED",call.=FALSE)
    result$study_id <- task$study_id
    result$data_origin <- origin_context$data_origin
    result$task_purpose <- origin_context$task_purpose
    result$test_only <- origin_context$test_only
    result$scientific_review <- "pending"
  }
  result$applicability_status <- "limited"
  result$provider <- list(id="sklearn_nonlinear_binary",version=calculated$provider_version,
    code_hash=calculated$provider_version,runtime=calculated$runtime)
  result$binding$model_hash <- record$model_sha256
  proxy <- task
  proxy$analysis$method_id <- "prediction.binary.ridge"
  # No fit dispatch uses this proxy. It is only used by shared aggregate projection.
  result$counts <- record$counts
  evaluation <- common_prediction_evaluation_counts(record,proxy)
  for(n in names(evaluation)) result$counts[n] <- list(evaluation[[n]])
  result$diagnostics <- list(backend_status=record$status,backend=record$diagnostics,
    internal_cv=record$internal_cv,calibration=record$metrics$calibration)
  result$limitations <- c(result$limitations,record$limitations)
  if(!is.null(origin_context)) {
    result$limitations <- c(list(paste0(origin_label,"; local_only; clinical applicability is not established."),
      "Normalized payload origin/purpose are supplied by the admitted root context; this projection does not reconstruct original sources or joins."),
      Filter(function(x)!startsWith(x,"SYNTHETIC_TEST_ONLY;"),record$limitations))
  }
  result$provenance <- list(prediction_operation=task$analysis$prediction$operation,
    validation_scope="synthetic_technical_application_only",projection="shared_binary_projection_via_explicit_branch_proxy")
  if(!is.null(origin_context)) result$provenance <- c(result$provenance[setdiff(names(result$provenance),"validation_scope")],
    list(data_origin=origin_context$data_origin,task_purpose=origin_context$task_purpose,
      scientific_review="pending",validation_scope="frozen_model_projection_scientific_review_pending"))
  result$local_artifacts <- list(list(artifact_id="private-frozen-model",kind="local_only_model"),
    list(artifact_id="private-individual-predictions",kind="local_only_predictions"))
  if(!record$status%in%c("ESTIMATED","INFERENCE_COMPLETE","EXPLAINED")) {
    result$reason_code <- record$reason_code
    result$stage <- "compute"
    return(result)
  }
  result$execution_status <- "complete"
  result$metrics <- common_prediction_metrics(record,result,proxy)
  for(i in seq_along(result$metrics)) result$metrics[[i]]$model_role <- "frozen_nonlinear_model"
  if(!is.null(origin_context)) {
    operation <- task$analysis$prediction$operation
    application <- task$payload$application_scope %||% task$analysis$prediction$application_scope %||% "application"
    evaluation_set <- if(operation=="train")"internal_holdout" else if(operation=="evaluate")paste0("frozen_",application) else "new_data_inference"
    for(i in seq_along(result$metrics)) result$metrics[[i]]$evaluation_set <- evaluation_set
  }
  result <- common_prediction_table(result,output_dir)
  result <- common_prediction_figures(result,record,proxy,output_dir)
  if(!is.null(origin_context)) for(kind in c("tables","figures")) for(i in seq_along(result[[kind]])) {
    result[[kind]][[i]]$origin_context <- origin_context
    result[[kind]][[i]]$data_origin <- origin_context$data_origin
    result[[kind]][[i]]$task_purpose <- origin_context$task_purpose
    result[[kind]][[i]]$test_only <- origin_context$test_only
  }
  result$completed_parts <- list("frozen_model","prediction_contract","nonlinear_module_projection")
  # Extension is kept separate until the integration owner extends the shared schema.
  extension <- list(schema_version="nonlinear-module-result/1.0.0",test_only=TRUE,
    scientific_review="pending",export_status="local_only",method_id=result$method_id,
    tuning=record$internal_cv,explanation=record$explanation,diagnostics=record$diagnostics)
  if(!is.null(origin_context)) {
    extension$origin_context <- origin_context
    extension$data_origin <- origin_context$data_origin
    extension$task_purpose <- origin_context$task_purpose
    extension$test_only <- origin_context$test_only
  }
  extension$tables <- list(); extension$figures <- list()
  add_extension_artifact <- function(name,kind,caption) {
    suffix <- if(kind=="figure")".png" else ".csv"
    file <- file.path(output_dir,if(kind=="figure")"figures" else "tables",paste0(name,suffix))
    artifact <- common_artifact(name,kind,file,result,list(),record$counts$evaluation_n,"explicit",caption)
    if(!is.null(origin_context)) {
      artifact$origin_context <- origin_context
      artifact$data_origin <- origin_context$data_origin
      artifact$task_purpose <- origin_context$task_purpose
      artifact$test_only <- origin_context$test_only
    }
    field <- if(kind=="figure")"figures" else "tables"
    extension[[field]][[length(extension[[field]])+1L]] <<- artifact
  }
  exp <- record$explanation
  if(length(exp$permutation)) {
    tab <- do.call(rbind,lapply(exp$permutation,as.data.frame))
    utils::write.csv(tab,file.path(output_dir,"tables","permutation_importance.csv"),row.names=FALSE)
    grDevices::png(file.path(output_dir,"figures","nonlinear-permutation.png"),width=900,height=650)
    graphics::barplot(tab$increase_in_log_loss_mean,names.arg=tab$feature,ylab="Increase in log loss after permutation",
      main=if(is.null(origin_context))"SYNTHETIC TEST ONLY - permutation importance" else paste0("Permutation importance\n",origin_label),col="steelblue")
    graphics::abline(h=0,col="grey40")
    grDevices::dev.off()
    add_extension_artifact("permutation_importance","table","Frozen-model heldout permutation importance; repeat SD is not a confidence interval; not SHAP.")
    add_extension_artifact("nonlinear-permutation","figure",if(is.null(origin_context))"SYNTHETIC TEST ONLY. Marginal permutation loss increase; descriptive, not causal or SHAP." else
      paste0(origin_label,". Marginal permutation loss increase; descriptive, not causal or SHAP."))
  }
  if(length(exp$partial_dependence)) {
    tab <- do.call(rbind,lapply(exp$partial_dependence,as.data.frame))
    utils::write.csv(tab,file.path(output_dir,"tables","partial_dependence.csv"),row.names=FALSE)
    names <- unique(tab$feature)
    grDevices::png(file.path(output_dir,"figures","nonlinear-partial-dependence.png"),width=900,height=650)
    graphics::par(mfrow=c(1,length(names)))
    for(name in names) {
      part <- tab[tab$feature==name,]
      graphics::plot(seq_len(nrow(part)),part$mean_probability,type="b",xaxt="n",ylim=c(0,1),xlab=name,
        ylab="Mean frozen probability",main=if(is.null(origin_context))"SYNTHETIC - partial dependence" else
          paste(toupper(origin_context$data_origin),origin_context$task_purpose,"Partial dependence; review pending",sep="\n"))
      numeric_labels <- suppressWarnings(as.numeric(part$value))
      labels <- if(anyNA(numeric_labels))as.character(part$value) else signif(numeric_labels,3)
      graphics::axis(1,at=seq_len(nrow(part)),labels=labels)
    }
    grDevices::dev.off()
    add_extension_artifact("partial_dependence","table","Average frozen prediction under feature substitution; no causal or local attribution claim.")
    add_extension_artifact("nonlinear-partial-dependence","figure",if(is.null(origin_context))"SYNTHETIC TEST ONLY. Training-frozen grid, averaged over evaluation records; correlated features may form unsupported combinations." else
      paste0(origin_label,". Training-frozen grid, averaged over evaluation records; correlated features may form unsupported combinations."))
  }
  if(length(record$internal_cv$candidates)) {
    tuning <- do.call(rbind,lapply(record$internal_cv$candidates,function(x)data.frame(
      candidate_index=x$candidate_index,weighted_log_loss=x$weighted_log_loss,
      parameters=jsonlite::toJSON(x$parameters,auto_unbox=TRUE))))
    utils::write.csv(tuning,file.path(output_dir,"tables","tuning_candidates.csv"),row.names=FALSE)
    add_extension_artifact("tuning_candidates","table","Base-fitting-subset inner CV selection diagnostic; the winner score is not unbiased validation.")
  }
  jsonlite::write_json(extension,file.path(output_dir,"nonlinear-extension.json"),auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
  counts <- record$counts
  note <- c(if(is.null(origin_context))"# Synthetic nonlinear binary prediction" else paste0("# ",origin_label," - nonlinear binary prediction"), "",
    paste0("Method: ",result$method_id,". Operation: ",task$analysis$prediction$operation,"."),
    paste0("Source rows: ",counts$source_rows,"; analyzable records: ",counts$analyzable_n,"; evaluated outcome set: ",counts$evaluation_n %||% "none (inference)","."),
    if(task$analysis$prediction$operation=="train")paste0("Outer training: ",counts$training_n,"; base model fitting: ",counts$model_fit_n,
      "; disjoint calibration: ",counts$calibration_n,"; untouched holdout: ",counts$holdout_n,".") else
      "Frozen model, preprocessing, calibration, and thresholds were applied without refitting.",
    "",
    "All transformations and candidate selection occur inside the permitted fitting partitions. Inner CV is a selection diagnostic; it is not an unbiased final performance estimate.",
    "The sigmoid calibrator (when requested) uses a disjoint calibration subset. Base fitting never uses that subset or the final holdout.",
    "DCA thresholds and any clinical operating point were prespecified and frozen. DCA does not select a threshold or establish clinical utility.",
    "Metrics and ROC/calibration/DCA figures come from the existing common evaluation owner. ROC uses a fixed aggregate probability grid; exact AUC is computed separately.",
    "", "Aggregate evaluation:",
    vapply(result$metrics,function(m)paste0("- ",m$name,": ",if(is.null(m$value))"not estimable" else format(m$value,digits=6)),character(1)),
    "", "Permutation importance is marginal loss increase, not SHAP. Partial dependence averages frozen predictions under substitutions, not causal effects.",
    "No confidence interval is implied by a missing interval or by permutation repeat SD. Tree feature counts are not regression coefficient counts; EPV is not defined here.",
    "", if(is.null(origin_context))"SYNTHETIC_TEST_ONLY / scientific_review=pending / local_only. This preview is not the final integrated schema or clinical validation." else
      paste0(origin_label," / local_only. This projection is not clinical validation or a new source/join verification."))
  writeLines(note,file.path(output_dir,"METHODS-AND-RESULTS.md"),useBytes=TRUE)
  result
}

# Shared module response projection: consumes validated aggregate records only.
# The common caller persists private_record$frozen_model_json without reserializing it.
project_nonlinear_module <- function(response,task,output_dir,run_id="nonlinear-module",origin_context=NULL) {
  if(!isTRUE(response$ok)) stop(response$reason_code,call.=FALSE)
  record <- response$public_record
  record$diagnostics <- response$diagnostics$fit_metadata
  calculated <- list(record=record,provider_version=response$diagnostics$provider_version,
    runtime=response$diagnostics$runtime)
  project_nonlinear_prediction(calculated,task,output_dir,run_id,origin_context=origin_context)
}
