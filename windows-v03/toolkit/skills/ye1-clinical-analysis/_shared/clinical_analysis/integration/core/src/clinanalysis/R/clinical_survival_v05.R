# v05 reporting and frozen-model transport only. Numerical owner: survival.py.
run_common_cox_prediction_provider <- function(task,data,output_dir) {
  script <- file.path(.clinical_common$root,"python/clinical_methods/cox_prediction_bridge.py")
  private <- file.path(output_dir,"private")
  prepath <- file.path(private,"provider-preflight.json")
  if(!common_python(script,c("--preflight",prepath),file.path(private,"preflight.log"))||!file.exists(prepath))
    return(list(ok=FALSE,reason_code="COX_PREDICTION_PREFLIGHT_FAILED"))
  pre <- common_json_read(prepath)
  if(!isTRUE(pre$ok)) return(pre)
  expected <- .clinical_common$runtime$python_versions
  for(p in names(expected)) if(!identical(pre$runtime[[p]],expected[[p]]))
    return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  if(!identical(pre$provider_version,.clinical_common$runtime$cox_prediction_provider_version))
    return(list(ok=FALSE,reason_code="COX_PREDICTION_PROVIDER_VERSION_DRIFT"))
  options <- task$analysis$cox_prediction
  # The contract has already read and bound the model once. Forward that exact
  # text: serializing the parsed object here would change 1.0 into 1 and its hash.
  options$model_ref <- NULL; options$model_sha256 <- NULL
  request <- list(operation=options$operation,rows=.clinical_common$normalized$rows,
    spec=task$analysis$survival,prediction=options,
    feature_semantics=.clinical_common$normalized$cox_feature_semantics)
  if(identical(options$operation,"infer")) request$model_json <- .clinical_common$normalized$model_json
  if(study_is_task(task)) request$study_context <- list(
    provenance_version="clinical-frozen-provenance@1.0",data_origin=task$data_origin,
    task_purpose=task$task_purpose,test_only=identical(task$task_purpose,"engineering_test"),
    scientific_review="pending",export_status="local_only")
  reqpath <- file.path(private,"provider-request.json");resppath <- file.path(private,"provider-response.json")
  limits <- common_resource_limits(task)
  if(!is.null(limits)) request$limits <- limits
  common_json_write(request,reqpath)
  if(!common_python(script,c(reqpath,resppath,if(!is.null(limits))as.character(limits$max_input_bytes) else character()),file.path(private,"provider.log"))||!file.exists(resppath))
    return(list(ok=FALSE,reason_code="COX_PREDICTION_PROCESS_FAILED"))
  calculated <- common_json_read(resppath)
  if(!isTRUE(calculated$ok)) return(calculated)
  if(!identical(calculated$provider_version,pre$provider_version))
    return(list(ok=FALSE,reason_code="COX_PREDICTION_PROVIDER_VERSION_DRIFT"))
  for(p in names(expected)) if(!identical(calculated$runtime[[p]],expected[[p]]))
    return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  calculated$provider <- list(id="clinical_methods.survival.cox_prediction",version=calculated$provider_version,
    code_hash=calculated$provider_version,runtime=calculated$runtime)
  calculated
}

common_attach_formal_ph <- function(result,record,output_dir) {
  ph <- record$ph_test
  if(is.null(ph)) return(result)
  raw_tests <- ph$table
  ph$table <- NULL
  ph$ties <- "breslow"
  ph$ph_assumption_verified <- FALSE
  ph$tests <- lapply(seq_along(raw_tests),function(i) {
    p <- raw_tests[[i]]
    p$result_id <- paste0(result$run_id,"-ph-",i)
    p$denominator <- record$n_used
    p$events <- record$target_events
    p
  })
  result$survival$ph_score_test <- ph
  if(!identical(ph$status,"completed")) {
    result$execution_status <- "partial"
    result$reason_code <- "FORMAL_PH_TEST_UNAVAILABLE"
  }
  if(!length(ph$tests)) return(result)
  rows <- lapply(ph$tests,function(p)data.frame(result_id=p$result_id,term=p$term,
    chisq=p$chisq %||% NA_real_,df=p$df,p_value=p$p_value %||% NA_real_,status=p$status,
    reason=p$reason %||% "",denominator=p$denominator,events=p$events,method=ph$method,
    transform=ph$transform,ties=ph$ties,ph_assumption_verified=FALSE,stringsAsFactors=FALSE))
  path <- file.path(output_dir,"tables","ph_score_tests.csv")
  utils::write.csv(do.call(rbind,rows),path,row.names=FALSE,na="")
  result$tables <- c(result$tables,list(common_artifact("ph-score-tests","table",path,result,
    lapply(ph$tests,`[[`,"result_id"),record$n_used,"chi-square statistic and asymptotic P value",
    "Nuisance-adjusted Cox PH score test. Prespecified transform and whole-term/global tests; null values carry non-estimability reasons. A non-significant test does not verify PH assumptions.")))
  result
}

common_cox_prediction_result <- function(calculated,result,task,output_dir) {
  record <- calculated$record; pop <- record$analysis_population
  options <- task$analysis$cox_prediction; spec <- task$analysis$survival
  private <- file.path(output_dir,"private")
  common_json_write(record,file.path(private,"backend.json"))
  bundle <- calculated$model_bundle
  if(!file.exists(file.path(private,"frozen_cox_model.json"))||is.null(bundle$model_sha256))
    stop("COX_MODEL_ARTIFACT_MISSING",call.=FALSE)
  if(!file.exists(file.path(private,"individual_predictions.csv")))
    stop("COX_PREDICTION_ARTIFACT_MISSING",call.=FALSE)
  if(!identical(bundle$model_sha256,record$model_sha256)) stop("COX_MODEL_RESULT_BINDING_INVALID",call.=FALSE)
  if(study_is_task(task)&&identical(options$operation,"infer")&&
      !identical(common_sha(file.path(private,"frozen_cox_model.json")),task$analysis$cox_prediction$model_sha256))
    stop("COX_MODEL_ARTIFACT_BYTES_CHANGED",call.=FALSE)
  result$binding$model_hash <- bundle$model_sha256
  result$counts$model_n <- pop$n_training_complete
  result$counts$training_n <- pop$n_training_complete
  result$counts$training_events <- pop$n_training_events
  result$counts$training_censored <- pop$n_training_censored
  result$counts$holdout_n <- pop$n_holdout
  result$counts$prediction_n <- pop$n_predicted
  result$counts$prediction_events <- pop$n_predicted_events
  result$counts$prediction_censored <- pop$n_predicted_censored
  result$counts$prediction_missing_status <- pop$n_predicted_missing_status
  result$counts$prediction_missing_time <- pop$n_predicted_missing_time
  result$counts$excluded_missing <- if(options$operation=="train")pop$n_dropped_training_missing else 0L
  result$counts$eligible <- pop$n_input-result$counts$excluded_missing
  result$counts$missing_by_field <- if(options$operation=="train")pop$training_missing_by_field %||% common_object() else common_object()
  record$prediction_summary <- lapply(seq_along(record$prediction_summary),function(i) {
    p <- record$prediction_summary[[i]]
    p$result_id <- paste0(result$run_id,"-cox-risk-",i)
    p
  })
  record$semantics <- list(time_unit=spec$time_unit,time_zero_definition=spec$time_zero_definition,
    event_definition=spec$event_definition,censoring_definition=spec$censoring_definition,
    event_code=spec$event_code,censor_code=spec$censor_code)
  record$uncertainty <- "not_implemented"
  record$summary_estimand <- "mean_frozen_predicted_absolute_event_risk"
  result$cox_prediction <- record
  result$execution_status <- "complete"
  result$diagnostics <- list(backend_status="FROZEN_RISK_PREDICTIONS_COMPUTED",backend=list(patient_rows_returned=FALSE,
    performance_evaluation="not_implemented",ph_assumption_verified=FALSE))
  result$provenance$prediction_operation <- options$operation
  result$provenance$fit_scope <- if(options$operation=="train")"training_complete_cases_only" else "frozen_no_refit"
  result$provenance$validation_scope <- if(study_is_task(task))task$validation$kind else "synthetic_technical_application_only"
  if(study_is_task(task)) {
    result$provenance$frozen_model_origin <- if(is.null(bundle$provenance_version)) {
      list(data_origin="unrecorded_legacy",task_purpose="unrecorded_legacy",scientific_review="pending")
    } else {
      bundle[c("provenance_version","data_origin","task_purpose","test_only","scientific_review","export_status")]
    }
  }
  result$local_artifacts <- list(list(artifact_id="private-frozen-cox-model",kind="local_only_model"),
    list(artifact_id="private-individual-cox-predictions",kind="local_only_predictions"))
  result$limitations <- c(result$limitations,list(
    "Frozen Cox absolute event risk at prespecified horizons, using the training-centered right-continuous Breslow baseline. This is a prediction, not a causal effect.",
    "Mean predicted risks are descriptive summaries of model predictions, not observed risks, calibration, discrimination or clinical performance evidence.",
    "Training and application event/censor counts describe their complete follow-up labels, not horizon-specific outcomes or prediction denominators.",
    "Application uses frozen transformations, coefficients and baseline without refitting. Only known identities in the same declared namespace can be checked for training overlap; real source independence and transportability remain unverified.",
    "Time support ends at the last training event; no extrapolation. Prediction uncertainty, time-dependent ROC/IPCW Brier, calibration and DCA are not implemented."))
  result <- common_write_cox_prediction(result,output_dir)
  result$completed_parts <- c(result$completed_parts,list("frozen_cox_model","frozen_absolute_risk_inference"))
  result
}

common_write_cox_prediction <- function(result,output_dir) {
  rec <- result$cox_prediction; pop <- rec$analysis_population
  rows <- lapply(rec$prediction_summary,function(p)data.frame(result_id=p$result_id,horizon=p$horizon,
    denominator=p$n,survival_probability_min=p$survival_probability_min,
    survival_probability_mean=p$survival_probability_mean,survival_probability_max=p$survival_probability_max,
    event_risk_min=p$event_risk_min,event_risk_mean=p$event_risk_mean,event_risk_max=p$event_risk_max,
    time_unit=rec$semantics$time_unit,scale="absolute_event_risk",evaluation_set=if(rec$operation=="train")"prespecified_holdout" else if(identical(result$schema_version,"clinical-analysis-result@1.0"))result$provenance$validation_scope else "synthetic_frozen_application",
    prediction_events=pop$n_predicted_events,prediction_censored=pop$n_predicted_censored,
    prediction_missing_status=pop$n_predicted_missing_status,prediction_missing_time=pop$n_predicted_missing_time,
    model_sha256=rec$model_sha256,uncertainty=rec$uncertainty,stringsAsFactors=FALSE))
  table <- do.call(rbind,rows);ids <- lapply(rec$prediction_summary,`[[`,"result_id")
  path <- file.path(output_dir,"tables","cox_prediction_summary.csv")
  utils::write.csv(table,path,row.names=FALSE,na="")
  caption <- "Frozen model predictions at prespecified horizons; denominator is the application cohort. Mean/min/max are predicted probabilities, not observed event risk or performance. Event/censor counts describe complete follow-up, not horizon-specific outcomes; no prediction confidence intervals."
  result$tables <- c(result$tables,list(common_artifact("cox-prediction-summary","table",path,result,ids,
    pop$n_predicted,"absolute probability [0,1]",caption)))
  summary <- data.frame(operation=rec$operation,n_input=pop$n_input,n_training_declared=pop$n_training_declared,
    n_training_complete=pop$n_training_complete,n_training_events=pop$n_training_events,n_training_censored=pop$n_training_censored,
    n_dropped_training_missing=pop$n_dropped_training_missing,n_holdout=pop$n_holdout,n_predicted=pop$n_predicted,
    n_predicted_events=pop$n_predicted_events,n_predicted_censored=pop$n_predicted_censored,
    n_predicted_missing_status=pop$n_predicted_missing_status,n_predicted_missing_time=pop$n_predicted_missing_time,
    time_unit=rec$semantics$time_unit,time_zero_definition=rec$semantics$time_zero_definition,
    event_definition=rec$semantics$event_definition,censoring_definition=rec$semantics$censoring_definition,
    event_code=rec$semantics$event_code,censor_code=rec$semantics$censor_code,
    baseline_convention=rec$baseline_convention,last_training_event=rec$support$last_event_time,
    max_training_observed_time=rec$support$max_observed_time,model_sha256=rec$model_sha256,stringsAsFactors=FALSE)
  path <- file.path(output_dir,"tables","cox_prediction_sample_flow.csv")
  utils::write.csv(summary,path,row.names=FALSE,na="")
  result$tables <- c(result$tables,list(common_artifact("cox-prediction-sample-flow","table",path,result,ids,NULL,
    "explicit training and application subject counts","Training counts are from the frozen model; application counts are from the current mapped cohort. Distinct cohort denominators and event/censor definitions are explicit.")))
  path <- file.path(output_dir,"figures","cox_predicted_risk.png")
  ok <- tryCatch({
    grDevices::png(path,width=1100,height=720)
    tryCatch({
      graphics::par(mar=c(5,5,5,2))
      graphics::plot(table$horizon,table$event_risk_mean,type="b",pch=19,ylim=c(0,1),
        xlab=paste("Prespecified horizon",rec$semantics$time_unit),ylab="Mean predicted absolute event risk",
        main=paste(common_result_label(result),"- frozen Cox predictions"))
      graphics::mtext(paste("Application n =",pop$n_predicted,"; model predictions, no performance estimate or CI"),side=3,line=.5,cex=.85)
    },finally=grDevices::dev.off())
    TRUE
  },error=function(e)FALSE)
  if(ok) result$figures <- c(result$figures,list(common_artifact("cox-predicted-risk","figure",path,result,ids,
    pop$n_predicted,"absolute probability [0,1]",caption))) else {
    result$execution_status <- "partial"
    result$warnings <- c(result$warnings,list(list(code="COX_PREDICTION_FIGURE_FAILED",stage="figures")))
  }
  result
}

validate_common_cox_prediction_result <- function(x) {
  rec <- x$cox_prediction;p <- rec$analysis_population
  if(!identical(x$binding$model_hash,rec$model_sha256)) stop("RESULT_COX_MODEL_BINDING_INVALID",call.=FALSE)
  if(p$n_training_events+p$n_training_censored!=p$n_training_complete||
     p$n_predicted_events+p$n_predicted_censored+p$n_predicted_missing_status!=p$n_predicted) stop("RESULT_COX_PREDICTION_COUNTS_INVALID",call.=FALSE)
  if(p$n_predicted_missing_time>p$n_predicted||p$n_predicted_missing_status>p$n_predicted) stop("RESULT_COX_PREDICTION_MISSING_COUNTS_INVALID",call.=FALSE)
  if(p$n_training_declared-p$n_dropped_training_missing!=p$n_training_complete) stop("RESULT_COX_TRAINING_FLOW_INVALID",call.=FALSE)
  if(length(x$metrics)||length(x$estimates)||!is.null(x$survival)) stop("RESULT_COX_PREDICTION_ROLE_INVALID",call.=FALSE)
  if(!identical(rec$uncertainty,"not_implemented")) stop("RESULT_COX_UNCERTAINTY_CLAIM_INVALID",call.=FALSE)
  if(length(rec$prediction_summary)!=length(rec$horizons)||
     !isTRUE(all.equal(vapply(rec$prediction_summary,`[[`,numeric(1),"horizon"),unlist(rec$horizons,use.names=FALSE))))
    stop("RESULT_COX_PREDICTION_HORIZON_MISMATCH",call.=FALSE)
  for(pair in list(c("prediction_n","n_predicted"),c("training_n","n_training_complete"),
                  c("training_events","n_training_events"),c("training_censored","n_training_censored"),
                  c("prediction_events","n_predicted_events"),c("prediction_censored","n_predicted_censored"),
                  c("prediction_missing_status","n_predicted_missing_status"),c("prediction_missing_time","n_predicted_missing_time")))
    if(x$counts[[pair[[1L]]]]!=p[[pair[[2L]]]]) stop("RESULT_COX_COUNT_PROJECTION_INVALID",call.=FALSE)
  last_time <- -Inf;last_risk <- -Inf
  for(q in rec$prediction_summary) {
    if(q$n!=p$n_predicted||q$horizon<=last_time||q$horizon<0||q$horizon>rec$support$last_event_time||
       q$event_risk_mean<last_risk-1e-12) stop("RESULT_COX_PREDICTION_GRID_INVALID",call.=FALSE)
    if(q$event_risk_min<0||q$event_risk_max>1||q$event_risk_min>q$event_risk_mean||q$event_risk_mean>q$event_risk_max||
       q$survival_probability_min<0||q$survival_probability_max>1||
       abs(q$event_risk_mean+q$survival_probability_mean-1)>1e-12||
       abs(q$event_risk_min+q$survival_probability_max-1)>1e-12||
       abs(q$event_risk_max+q$survival_probability_min-1)>1e-12) stop("RESULT_COX_PROBABILITY_INVALID",call.=FALSE)
    if(q$horizon==0&&q$event_risk_max!=0) stop("RESULT_COX_TIME_ZERO_INVALID",call.=FALSE)
    last_time<-q$horizon;last_risk<-q$event_risk_mean
  }
  invisible(TRUE)
}
