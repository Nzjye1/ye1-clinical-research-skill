# Transport, contract projection and aggregate artifacts only.
# All fitting/preprocessing/prediction/statistics belong to penalized_v08.R.
.penalized_v08_methods <- c("prediction.continuous.signed.lasso","prediction.continuous.signed.elasticnet",
  "prediction.binary.lasso","prediction.binary.elasticnet")

# Provenance belongs to the task/wrapper, not the numerical payload.
common_penalized_wrap_origin <- function(value,task) {
  if(!identical(task$schema_version,"clinical-study-input@1.0")) return(value)
  metadata <- list(provenance_version="clinical-frozen-provenance@1.0",data_origin=task$data_origin,
    task_purpose=task$task_purpose,test_only=identical(task$task_purpose,"engineering_test"),
    scientific_review="pending",export_status="local_only")
  for(name in names(metadata)) value[[name]] <- metadata[[name]]
  value
}

common_penalized_strip_explainer_origin <- function(value) {
  value[setdiff(names(value),c("provenance_version","data_origin","task_purpose","test_only","scientific_review","export_status"))]
}

common_penalized_origin_record <- function(record,task) {
  if(!identical(task$schema_version,"clinical-study-input@1.0")) return(record)
  record$limitations <- Filter(function(value)!identical(value,"SYNTHETIC_ENGINEERING_ONLY"),record$limitations)
  record$limitations <- c(record$limitations,list(paste0("DECLARED_SOURCE_",toupper(task$data_origin),
    "; TASK_PURPOSE_",toupper(task$task_purpose),"; SCIENTIFIC_REVIEW_PENDING")))
  record
}

common_penalized_source_label <- function(result) {
  if(identical(result$data_origin,"real")) "REAL DATA; scientific review pending" else "SYNTHETIC TEST ONLY"
}

run_common_penalized_provider <- function(task,data,output_dir) {
  root <- .clinical_common$root;lock <- .clinical_common$runtime
  source <- file.path(root,"src/clinanalysis/R/penalized_v08.R");version <- common_sha(source)
  if(!identical(version,lock$penalized_provider_version)) return(list(ok=FALSE,reason_code="PENALIZED_PROVIDER_VERSION_DRIFT"))
  for(p in c("glmnet","Matrix")) {
    if(!requireNamespace(p,quietly=TRUE)) return(list(ok=FALSE,reason_code="PENALIZED_ENGINE_UNAVAILABLE"))
    if(!identical(as.character(utils::packageVersion(p)),lock$penalized_runtime[[p]]))
      return(list(ok=FALSE,reason_code="PENALIZED_ENGINE_VERSION_MISMATCH"))
    if(!identical(common_path(find.package(p)),common_path(lock$penalized_package_paths[[p]])))
      return(list(ok=FALSE,reason_code="PENALIZED_LIBRARY_BINDING_MISMATCH"))
  }
  if(!identical(as.character(getRversion()),lock$penalized_runtime$R)) return(list(ok=FALSE,reason_code="PENALIZED_ENGINE_VERSION_MISMATCH"))
  if(length(lock$penalized_dependency_hashes)!=10L) return(list(ok=FALSE,reason_code="PENALIZED_DEPENDENCY_BINDING_REQUIRED"))
  for(p in names(lock$penalized_dependency_hashes))
    if(!file.exists(p)||!identical(common_sha(p),lock$penalized_dependency_hashes[[p]]))
      return(list(ok=FALSE,reason_code="PENALIZED_DEPENDENCY_DRIFT"))
  normalized <- .clinical_common$normalized;options <- normalized$penalized_options
  bundle <- normalized$frozen_penalized_model
  value <- penalized_v08_analyze(data,options,normalized$penalized_semantics,
    frozen_model=if(is.null(bundle))NULL else bundle$model,resource_budget=normalized$resource_limits)
  if(!is.list(value$record)) return(list(ok=FALSE,reason_code=value$reason_code %||% "PENALIZED_PROVIDER_FAILED"))
  value$record <- common_penalized_origin_record(value$record,task)
  private <- file.path(output_dir,"private")
  backend <- file.path(private,"backend.json");common_json_write(value$record,backend)
  record <- common_json_read(backend)
  if(!is.null(value$individual)) common_psm_write_frame(value$individual,file.path(private,"penalized-individual-predictions.csv"))
  model_hash <- NULL;explainer_hash <- NULL
  if(isTRUE(value$ok)) {
    if(identical(options$operation,"train")) {
      if(!is.list(value$model)) return(list(ok=FALSE,reason_code="PENALIZED_FROZEN_MODEL_MISSING"))
      frozen <- list(schema_version="clinical-frozen-penalized@0.8.0-candidate1",method_id=task$analysis$method_id,
        provider_version=version,canonical_semantics=normalized$penalized_semantics,model=value$model,
        runtime_binding=list(versions=lock$penalized_runtime,package_paths=lock$penalized_package_paths,
          dependency_hashes=lock$penalized_dependency_hashes,rscript_engine=lock$rscript_engine,
          rscript_sha256=lock$executable_hashes[[lock$rscript_engine]]),
        test_only=TRUE,scientific_review="pending",export_status="local_only")
      frozen <- common_penalized_wrap_origin(frozen,task)
      modelpath <- file.path(private,"penalized-model.json");common_json_write(frozen,modelpath);model_hash <- common_sha(modelpath)
      # The frozen v0.8 model and numerical record above are unchanged. This
      # v0.9 private sidecar learns no new transform and reads training features
      # only; its separate source owner verifies the exact training identity set.
      explainer_version <- common_interpretation_provider_version()
      explainer <- interpretation_v09_freeze(data,value$model,model_hash,explainer_version,resource_budget=normalized$resource_limits)
      explainer <- common_penalized_wrap_origin(explainer,task)
      explainer_path <- file.path(private,"linear-explainer.json")
      common_json_write(explainer,explainer_path);explainer_hash <- common_sha(explainer_path)
    } else model_hash <- options$model_ref$content_hash
  }
  list(ok=TRUE,record=record,model_hash=model_hash,explainer_hash=explainer_hash,provider=list(id="clinanalysis.penalized_v08",
    version=version,code_hash=version,runtime=lock$penalized_runtime))
}

common_penalized_ids <- function(result) {
  record <- result$penalized_prediction
  if(is.null(record)) return(character())
  rows <- c(record$preprocessing,record$cv$rows,record$cv$folds,record$cv$fold_losses,
    record$path,record$coefficients,record$metrics)
  c(record$result_id,vapply(rows,`[[`,character(1),"result_id"))
}

common_penalized_metrics <- function(record,result,task) {
  lapply(seq_along(record$metrics),function(i) {
    m <- record$metrics[[i]];binary <- identical(record$family,"binomial")
    ratios <- c(sensitivity="events",specificity="nonevents",ppv="predicted_positive",npv="predicted_negative",accuracy="evaluated_labels")
    ratio <- m$metric%in%names(ratios)
    list(result_id=paste0(result$run_id,"-metric-",i),name=m$metric,value=m$value,
      unit=if(binary)"1" else record$semantics$outcome$unit,
      scale=if(!binary)"signed_original_outcome_units" else if(m$metric=="brier")"squared_probability_error" else if(m$metric=="log_loss")"mean_negative_natural_log_likelihood" else "dimensionless",
      evaluation_set=if(record$operation=="train")"internal_holdout" else if(identical(result$data_origin,"real"))"frozen_application" else "synthetic_frozen_application",
      evaluation_n=m$n,evaluation_events=m$events,evaluation_nonevents=m$non_events,
      numerator=if(ratio)m$numerator else NULL,denominator=if(ratio)m$denominator else NULL,
      denominator_semantics=if(ratio)unname(ratios[[m$metric]]) else "not_a_count_ratio",uncertainty=NULL,
      reason_code=if(ratio&&!is.null(m$denominator)&&m$denominator==0)"ZERO_RATIO_DENOMINATOR" else m$reason_code,
      model_role=if(startsWith(m$metric,"training_mean_"))"training_constant_comparator" else "frozen_penalized_model")
  })
}

common_penalized_result <- function(calculated,result,task,output_dir) {
  rec <- calculated$record;rec$result_id <- paste0(result$run_id,"-penalized")
  with_ids <- function(rows,label) lapply(seq_along(rows),function(i){row<-rows[[i]];row$result_id<-paste0(rec$result_id,"-",label,"-",i);row})
  for(name in c("preprocessing","path","coefficients","metrics")) rec[[name]] <- with_ids(rec[[name]],name)
  for(name in c("rows","folds","fold_losses")) rec$cv[[name]] <- with_ids(rec$cv[[name]],paste0("cv-",name))
  result$penalized_prediction <- rec;flow <- rec$flow;train <- identical(rec$operation,"train");infer <- identical(rec$operation,"infer")
  complete <- identical(rec$status,"completed")
  result$counts <- list(source_rows=flow$n_input,subjects=flow$n_input,eligible=flow$n_input,
    model_n=if(train&&complete)flow$n_training else NULL,excluded_missing=0L,
    training_n=if(train)flow$n_training else NULL,training_events=if(train)flow$n_training_events else NULL,
    training_nonevents=if(train)flow$n_training_non_events else NULL,holdout_n=if(train)flow$n_holdout else NULL,
    holdout_events=if(train)flow$n_holdout_events else NULL,holdout_nonevents=if(train)flow$n_holdout_non_events else NULL,
    evaluation_n=if(infer||!complete)NULL else flow$n_evaluated,
    evaluation_events=if(infer||!complete)NULL else flow$n_evaluation_events,
    evaluation_nonevents=if(infer||!complete)NULL else flow$n_evaluation_non_events,
    missing_outcome_n=flow$missing_outcome_n,missing_feature_excluded_n=0L,
    prediction_n=flow$n_predicted,prediction_clipped_n=0L)
  result$binding["model_hash"] <- list(calculated$model_hash)
  result$diagnostics <- list(backend_status=rec$status,backend=list(penalized=rec$diagnostics))
  result$provenance$prediction_operation <- rec$operation
  result$provenance$fit_scope <- if(train)"training_partition_and_inner_training_folds_only" else "frozen_no_refit"
  result$provenance$validation_scope <- if(train)"internal_holdout" else if(infer)"new_data_inference" else if(identical(result$data_origin,"real"))"frozen_application" else "synthetic_frozen_application"
  result$provenance$target_policy <- if(rec$family=="gaussian")list(domain="signed_real",transform="training_center_scale",
    inverse_transform="frozen_response_mean_plus_scale_times_linear_score",output_policy="identity_no_clipping") else
    list(domain="binary_0_1",event=1,transform="identity",inverse_transform="logistic_of_frozen_linear_score",output_policy="probability")
  result$limitations <- unique(c(result$limitations,rec$limitations,as.list(c(
    "The selected nonzero list refers to encoded columns; a categorical predictor is not selected as a penalized group.",
    "semantics.features.reference is the declared codebook reference only. Interpret model coefficients using preprocessing.fitted_reference and fitted_levels from the corresponding final/frozen training model; each CV fold learns its own encoding.",
    "Training CV selects lambda; it is not a nested-CV estimate of generalization performance.",
    "Coefficient paths and selected coefficients have no postselection p-values or confidence intervals.",
    "Gaussian predictions use a frozen training response inverse transform with no clipping; existing nonnegative Ridge retains its separate policy.",
    "Identity overlap is checked within the declared canonical namespace; this does not prove real external cohort independence."))))
  result$metrics <- common_penalized_metrics(rec,result,task)
  result$execution_status <- if(complete)"complete" else "blocked"
  result$applicability_status <- if(complete)"pass" else "limited"
  result["reason_code"] <- list(rec$reason_code);result$stage <- "compute"
  if(complete) result$completed_parts <- c(result$completed_parts,list("frozen_penalized_pipeline","penalized_prediction_contract"),
    if(train)list("fold_local_preprocessing_and_prespecified_lambda_cv") else list("frozen_no_refit_application"))
  result$local_artifacts <- c(result$local_artifacts,list(list(artifact_id="penalized-individual-predictions",kind="private_predictions")))
  if(train&&complete) result$local_artifacts <- c(result$local_artifacts,list(list(artifact_id="penalized-model",kind="private_frozen_pipeline")))
  if(train&&complete&&!is.null(calculated$explainer_hash)) result$local_artifacts <- c(result$local_artifacts,
    list(list(artifact_id="linear-explainer",kind="private_frozen_training_background")))
  validate_common_penalized_result(result)
  common_write_penalized_outputs(result,output_dir)
}

validate_common_penalized_result <- function(result) {
  rec <- result$penalized_prediction
  if(is.null(rec)) return(invisible(TRUE))
  need <- function(ok,code) if(!isTRUE(ok)) stop(code,call.=FALSE)
  same <- function(a,b) isTRUE(all.equal(a,b,tolerance=1e-12,check.attributes=FALSE))
  need(result$method_id%in%.penalized_v08_methods&&identical(result$method_id,rec$method_id),"RESULT_PENALIZED_METHOD_MISMATCH")
  need(same(result$counts$source_rows,rec$flow$n_input)&&same(result$counts$prediction_n,rec$flow$n_predicted),"RESULT_PENALIZED_COUNT_MISMATCH")
  need(identical(result$counts$prediction_clipped_n,0L)||same(result$counts$prediction_clipped_n,0),"RESULT_PENALIZED_CLIPPING_INVALID")
  need(!length(result$estimates)&&!length(result$tests),"RESULT_PENALIZED_POSTSELECTION_INFERENCE_FORBIDDEN")
  for(row in rec$preprocessing) {
    levels <- row$fitted_levels
    need(is.list(levels),"RESULT_PENALIZED_FITTED_LEVELS_INVALID")
    if(row$type=="number") {
      need(!length(levels)&&is.null(row$fitted_reference)&&identical(row$encoding_rule,"identity_numeric"),
        "RESULT_PENALIZED_NUMERIC_ENCODING_INVALID")
    } else {
      need(length(levels)>0L&&all(vapply(levels,function(x)is.character(x)&&length(x)==1L&&!is.na(x)&&nzchar(x),logical(1))),
        "RESULT_PENALIZED_FITTED_LEVELS_INVALID")
      values <- unlist(levels,use.names=FALSE)
      need(!anyDuplicated(values)&&identical(values,penalized_v08_sort(values))&&
        identical(row$fitted_reference,values[[1L]])&&
        identical(row$encoding_rule,"treatment_utf8_observed_reference_first"),"RESULT_PENALIZED_CATEGORY_ENCODING_INVALID")
    }
  }
  if(rec$status=="completed") {
    need(is.null(rec$reason_code)&&!is.null(result$binding$model_hash),"RESULT_PENALIZED_COMPLETION_INVALID")
    need(same(rec$flow$n_predicted,rec$flow$n_input),"RESULT_PENALIZED_PREDICTION_COUNT_INVALID")
    need(rec$diagnostics$warning_count==0&&if(rec$operation=="train")rec$diagnostics$jerr==0 else is.null(rec$diagnostics$jerr),"RESULT_PENALIZED_ENGINE_DIAGNOSTIC_INVALID")
    need(is.finite(rec$selected_lambda)&&rec$selected_lambda>0&&is.finite(rec$selected_engine_lambda)&&rec$selected_engine_lambda>0&&
      abs(rec$selected_lambda-rec$selected_engine_lambda)<=32*.Machine$double.eps*abs(rec$selected_lambda),"RESULT_PENALIZED_LAMBDA_INVALID")
    need(length(rec$coefficients)==rec$flow$n_encoded_columns+1L,"RESULT_PENALIZED_COEFFICIENT_COUNT_INVALID")
    if(rec$operation=="train") {
      need(rec$cv$status=="completed"&&length(rec$cv$rows)>=2L&&length(rec$cv$folds)==rec$flow$n_cv_folds,"RESULT_PENALIZED_CV_INCOMPLETE")
      need(same(rec$flow$n_training+rec$flow$n_holdout,rec$flow$n_input)&&same(rec$flow$n_evaluated,rec$flow$n_holdout),"RESULT_PENALIZED_TRAINING_FLOW_INVALID")
      need(same(sum(vapply(rec$cv$folds,`[[`,numeric(1),"n_validation")),rec$flow$n_training),"RESULT_PENALIZED_CV_DENOMINATOR_INVALID")
      selected <- which(vapply(rec$cv$rows,`[[`,logical(1),"selected"))
      need(length(selected)==1L&&selected==rec$selected_lambda_index,"RESULT_PENALIZED_CV_SELECTION_INVALID")
      losses <- vapply(rec$cv$rows,`[[`,numeric(1),"mean_loss")
      need(selected==which.min(losses),"RESULT_PENALIZED_CV_SELECTION_INVALID")
      for(row in rec$cv$rows) need(same(row$n_validation,rec$flow$n_training)&&same(row$mean_loss,row$loss_sum/row$n_validation),"RESULT_PENALIZED_CV_LOSS_INVALID")
      need(length(rec$path)==length(rec$cv$rows)*length(rec$coefficients),"RESULT_PENALIZED_PATH_INCOMPLETE")
    } else need(rec$diagnostics$n_engine_fits==0&&rec$cv$status=="not_run"&&!length(rec$path),"RESULT_PENALIZED_EXTERNAL_REFIT_FORBIDDEN")
  } else need(!is.null(rec$reason_code)&&result$execution_status=="blocked"&&is.null(result$binding$model_hash),"RESULT_PENALIZED_REFUSAL_INVALID")
  if(rec$operation=="infer") need(!length(rec$metrics)&&rec$flow$n_evaluated==0&&is.null(result$counts$evaluation_n),"RESULT_PENALIZED_INFER_EVALUATION_FORBIDDEN")
  for(i in seq_along(rec$metrics)) {
    m <- rec$metrics[[i]];mirror <- result$metrics[[i]]
    need(same(m$value,mirror$value)&&same(m$n,rec$flow$n_evaluated)&&same(m$events,rec$flow$n_evaluation_events)&&same(m$non_events,rec$flow$n_evaluation_non_events),"RESULT_PENALIZED_METRIC_COUNTS_INVALID")
    need((!is.null(m$value)&&is.null(m$reason_code))||(is.null(m$value)&&!is.null(m$reason_code)),"RESULT_PENALIZED_METRIC_REASON_INVALID")
  }
  invisible(TRUE)
}

common_penalized_frame <- function(rows) {
  if(!length(rows)) return(data.frame())
  fields <- names(rows[[1L]])
  if(anyDuplicated(fields)||any(vapply(rows,function(x)!setequal(names(x),fields)||anyDuplicated(names(x))>0L,logical(1))))
    stop("PENALIZED_EXPORT_COLUMNS_INVALID",call.=FALSE)
  as.data.frame(setNames(lapply(fields,function(f) {
    values <- lapply(rows,function(row)row[[f]])
    if(f=="fitted_levels") {
      if(!all(vapply(values,is.list,logical(1)))) stop("PENALIZED_EXPORT_FITTED_LEVELS_INVALID",call.=FALSE)
      vapply(values,function(v)as.character(jsonlite::toJSON(as.character(unlist(v,use.names=FALSE)),auto_unbox=FALSE,null="null",digits=17)),character(1))
    }
    else if(any(vapply(values,is.character,logical(1)))) vapply(values,function(v)if(is.null(v))NA_character_ else as.character(v),character(1))
    else if(any(vapply(values,is.logical,logical(1)))) vapply(values,function(v)if(is.null(v))NA else as.logical(v),logical(1))
    else vapply(values,function(v)if(is.null(v))NA_real_ else as.numeric(v),numeric(1))
  }),fields),stringsAsFactors=FALSE,check.names=FALSE)
}

common_write_penalized_outputs <- function(result,output_dir) {
  rec <- result$penalized_prediction
  metadata <- list(method_id=result$method_id,method_version=result$method_version,provider_version=result$provider$version,
    core_version=result$core_version,run_id=result$run_id,operation=rec$operation,family=rec$family,penalty=rec$penalty,
    alpha=rec$alpha,coefficient_scale=rec$coefficient_scale,prediction_scale=rec$prediction_scale,
    outcome_unit=rec$semantics$outcome$unit,scientific_review="pending",export_status="local_only",test_only=result$test_only)
  if(!is.null(result$data_origin)) metadata <- c(metadata,list(data_origin=result$data_origin,task_purpose=result$task_purpose))
  table <- function(name,rows,caption,denominator=NULL,units="explicit per field") {
    if(!length(rows)) return(invisible(NULL))
    if(any(names(metadata)%in%names(rows[[1L]]))) stop("PENALIZED_EXPORT_METADATA_COLLISION",call.=FALSE)
    data <- common_penalized_frame(lapply(rows,function(row)c(metadata,row)))
    file <- file.path(output_dir,"tables",paste0(name,".csv"));common_psm_write_frame(data,file)
    ids <- lapply(rows,function(row)row$result_id %||% rec$result_id)
    result$tables[[length(result$tables)+1L]] <<- common_artifact(name,"table",file,result,ids,denominator,units,caption)
  }
  flowrows <- lapply(names(rec$flow),function(name)list(result_id=rec$result_id,count_name=name,value=rec$flow[[name]],
    count_semantics=if(grepl("events",name)&&rec$family=="gaussian")"not_applicable_continuous_outcome" else if(name=="missing_outcome_n"&&rec$operation=="infer")"not_read_in_infer" else "explicit_subject_or_design_count"))
  table("penalized_flow",flowrows,paste0(common_penalized_source_label(result),". Subject flow and design counts. Missing training/evaluation labels are refused; features are imputed within fit scope. Null means not applicable or not evaluated, never zero."))
  table("penalized_imputation",rec$preprocessing,paste0(common_penalized_source_label(result),". Missingness and fitted encoding by fold/role. fitted_levels is a JSON array of observed training levels in UTF8 order; fitted_reference is its first level. Application rows reuse the corresponding frozen training encoding. semantics.features.reference is only the declared codebook reference."))
  table("penalized_cv",rec$cv$rows,paste0(common_penalized_source_label(result),". Training-only tuning curve: total OOF loss divided by total validation subjects, exact ties choose largest prespecified lambda. No CI or external performance claim."),rec$flow$n_training)
  table("penalized_cv_folds",rec$cv$folds,paste0(common_penalized_source_label(result),". Prespecified patient/group folds. Training event counts refer to each fold's fitting subset."))
  table("penalized_cv_fold_losses",rec$cv$fold_losses,paste0(common_penalized_source_label(result),". Each candidate includes every validation subject. Requested and engine-returned lambda recorded separately; no path interpolation."))
  table("penalized_coefficient_path",rec$path,paste0(common_penalized_source_label(result),". Full outer-training coefficient path on standardized encoded design/declared response scale. Includes intercept; no inferential p-value or CI."),if(rec$operation=="train")rec$flow$n_training else NULL)
  table("penalized_coefficients",rec$coefficients,paste0(common_penalized_source_label(result),". Frozen selected coefficients on the declared standardized scale; encoded-column selection is not a causal or grouped-variable conclusion."))
  selected <- Filter(function(row)isTRUE(row$nonzero)&&row$type!="intercept",rec$coefficients)
  # Header-only output is intentional evidence for an all-zero selected model.
  if(length(selected)) table("penalized_nonzero",selected,paste0(common_penalized_source_label(result),". Nonzero encoded columns excluding intercept; no postselection inference."))
  else if(length(rec$coefficients)) {
    rows <- common_penalized_frame(lapply(rec$coefficients,function(row)c(metadata,row)))[FALSE,,drop=FALSE]
    file <- file.path(output_dir,"tables","penalized_nonzero.csv");common_psm_write_frame(rows,file)
    result$tables[[length(result$tables)+1L]] <- common_artifact("penalized_nonzero","table",file,result,list(rec$result_id),0L,
      "encoded columns",paste0(common_penalized_source_label(result),". No nonzero slope columns at the selected lambda; an intercept-only fitted model is valid."))
  }
  table("penalized_metrics",rec$metrics,paste0(common_penalized_source_label(result),". Frozen-model evaluation; each row states its actual numerator/denominator and n/events/non-events. RMSE is the square root of its sum-of-squares ratio; AUC ranks the frozen linear score over event-control pairs, avoiding probability-saturation ties. No uncertainty interval."),rec$flow$n_evaluated)
  figure <- function(name,ids,caption,draw,denominator=NULL,units="explicit axes") {
    file <- file.path(output_dir,"figures",paste0(name,".png"))
    grDevices::png(file,width=1400,height=850,res=150)
    completed <- FALSE
    tryCatch({draw();completed<-TRUE},finally=grDevices::dev.off())
    if(!completed) stop("PENALIZED_FIGURE_FAILED",call.=FALSE)
    result$figures[[length(result$figures)+1L]] <<- common_artifact(name,"figure",file,result,ids,denominator,units,caption)
  }
  if(rec$status=="completed"&&rec$operation=="train") {
    figure("penalized_cv",lapply(rec$cv$rows,`[[`,"result_id"),
      paste0(common_penalized_source_label(result),". Prespecified lambda CV curve; fold-local transformations, subject-count weighting. Vertical line is selected lambda. Training tuning only, no confidence band."),function(){
        grid <- vapply(rec$cv$rows,`[[`,numeric(1),"lambda");loss <- vapply(rec$cv$rows,`[[`,numeric(1),"mean_loss")
        graphics::par(mar=c(5,5,4,2));graphics::plot(log(grid),loss,type="b",pch=19,col="#176B6B",lwd=2,
          xlab="log(requested lambda)",ylab=if(rec$family=="gaussian")paste0("OOF mean squared error (",rec$semantics$outcome$unit," squared)") else "OOF mean log loss",
          main=paste0("Training CV: ",rec$penalty," (alpha = ",rec$alpha,")"))
        graphics::abline(v=log(rec$selected_lambda),lty=2,col="#A84432")
        graphics::mtext(paste0("Training n = ",rec$flow$n_training,"; folds = ",rec$flow$n_cv_folds,paste0("; ",common_penalized_source_label(result))),side=3,line=.3,cex=.8)
      },rec$flow$n_training)
    figure("penalized_coefficient_path",lapply(rec$path,`[[`,"result_id"),
      paste0(common_penalized_source_label(result),". Full outer-training path excluding intercept; standardized encoded coefficients. Selection applies to encoded columns and carries no postselection CI or p-value."),function(){
        rows <- Filter(function(row)row$type!="intercept",rec$path);terms <- unique(vapply(rows,`[[`,character(1),"term"))
        grid <- vapply(rec$cv$rows,`[[`,numeric(1),"lambda")
        y <- vapply(terms,function(term)vapply(Filter(function(row)row$term==term,rows),`[[`,numeric(1),"coefficient"),numeric(length(grid)))
        graphics::par(mar=c(5,5,4,2));graphics::matplot(log(grid),y,type="l",lty=1,lwd=2,col=grDevices::hcl.colors(length(terms),"Dark 3"),
          xlab="log(requested lambda)",ylab=rec$coefficient_scale,main=paste0("Outer-training coefficient path: ",rec$penalty))
        graphics::abline(v=log(rec$selected_lambda),lty=2,col="#A84432");graphics::abline(h=0,col="#BBBBBB")
        if(length(terms)<=12) graphics::legend("topright",legend=terms,col=grDevices::hcl.colors(length(terms),"Dark 3"),lty=1,cex=.65,bty="n")
        graphics::mtext(paste0("Term-to-feature mapping is retained in the coefficient table; ",common_penalized_source_label(result)),side=3,line=.3,cex=.75)
      },rec$flow$n_training)
  }
  result
}
