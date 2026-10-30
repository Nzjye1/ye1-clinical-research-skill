# Thin prediction adapter for the existing clinanalysis run/registry branch.
# All fitting, preprocessing, CV and numerical metrics belong to locked Python.
run_common_prediction_provider <- function(task,data,output_dir) {
  root <- .clinical_common$root
  bridge <- file.path(root,"python/clinical_methods/prediction_bridge.py")
  prefile <- file.path(output_dir,"private","prediction-preflight.json")
  preflight_ok <- common_python(bridge,c("--preflight",prefile),file.path(output_dir,"private","prediction-preflight.log"))
  if(!file.exists(prefile)) return(list(ok=FALSE,reason_code="PREDICTION_PREFLIGHT_FAILED"))
  pre <- common_json_read(prefile)
  if(!isTRUE(pre$ok)) return(pre)
  expected <- .clinical_common$runtime$prediction_python_versions
  for(p in names(expected)) if(!identical(pre$runtime[[p]],expected[[p]])) return(list(ok=FALSE,reason_code="PREDICTION_DEPENDENCY_VERSION_DRIFT"))
  options <- task$analysis$prediction
  request <- list(operation=options$operation,method_id=task$analysis$method_id,
    rows=.clinical_common$normalized$rows,spec=options$spec,model_bundle=NULL,model_ref=options$model_ref %||% NULL,
    canonical_semantics=.clinical_common$normalized$canonical_semantics %||% NULL)
  if(study_is_task(task)) request$study_context <- list(
    provenance_version="clinical-frozen-provenance@1.0",data_origin=task$data_origin,
    task_purpose=task$task_purpose,test_only=identical(task$task_purpose,"engineering_test"),
    scientific_review="pending",export_status="local_only")
  reqfile <- file.path(output_dir,"private","prediction-request.json")
  respfile <- file.path(output_dir,"private","prediction-response.json")
  common_json_write(request,reqfile)
  provider_ok <- common_python(bridge,c(reqfile,respfile),file.path(output_dir,"private","prediction-provider.log"))
  if(!file.exists(respfile)) return(list(ok=FALSE,reason_code="PREDICTION_PROVIDER_PROCESS_FAILED"))
  calculated <- common_json_read(respfile)
  if(!isTRUE(calculated$ok)) return(calculated)
  for(p in names(expected)) if(!identical(calculated$runtime[[p]],expected[[p]])) return(list(ok=FALSE,reason_code="PREDICTION_DEPENDENCY_VERSION_DRIFT"))
  pre_version <- pre$provider_versions[[task$analysis$method_id]] %||% pre$provider_version
  if(!identical(calculated$provider_version,pre_version)) return(list(ok=FALSE,reason_code="PREDICTION_PROVIDER_VERSION_DRIFT"))
  calculated$provider <- list(id=if(identical(task$analysis$method_id,"prediction.binary.ridge"))"clinical_methods.prediction.binary" else "clinical_methods.prediction.continuous",
    version=calculated$provider_version,code_hash=calculated$provider_version,runtime=calculated$runtime)
  calculated
}

common_prediction_evaluation_counts <- function(record,task) {
  operation <- task$analysis$prediction$operation
  rc <- record$counts %||% common_object()
  n <- if(operation=="infer")NULL else rc$evaluation_n %||% NULL
  binary <- identical(task$analysis$method_id,"prediction.binary.ridge")
  events <- nonevents <- NULL
  if(binary&&!is.null(n)) {
    events <- if(operation=="train")rc$holdout_events %||% NULL else rc$analyzable_events %||% NULL
    nonevents <- if(operation=="train")rc$holdout_nonevents %||% NULL else rc$analyzable_nonevents %||% NULL
  }
  list(evaluation_n=n,evaluation_events=events,evaluation_nonevents=nonevents)
}

common_prediction_metrics <- function(record,result,task) {
  operation <- task$analysis$prediction$operation
  evaluation_set <- if(study_is_task(task))task$validation$kind else if(operation=="train")"internal_holdout" else if(operation=="evaluate")"synthetic_frozen_application" else "new_data_inference"
  evaluation <- common_prediction_evaluation_counts(record,task)
  n <- evaluation$evaluation_n
  outcome <- Filter(function(v)identical(v$name,task$outcome$field),task$variables)
  outcome_unit <- if(length(outcome))outcome[[1L]]$unit else "unspecified"
  result_metrics <- list()
  add <- function(name,value,unit,scale,baseline=FALSE,uncertainty=NULL,numerator=NULL,denominator=NULL,denominator_semantics="not_a_count_ratio") {
    result_metrics[[length(result_metrics)+1L]] <<- list(result_id=paste0(result$run_id,"-metric-",length(result_metrics)+1L),
      name=name,value=value,unit=unit,scale=scale,evaluation_set=evaluation_set,
      evaluation_n=n,evaluation_events=evaluation$evaluation_events,evaluation_nonevents=evaluation$evaluation_nonevents,
      numerator=numerator,denominator=denominator,denominator_semantics=denominator_semantics,
      uncertainty=uncertainty,reason_code=if(is.null(value)) {if(!is.null(denominator)&&denominator==0)"ZERO_RATIO_DENOMINATOR" else "METRIC_NOT_ESTIMABLE"} else NULL,
      model_role=if(baseline)"training_constant_comparator" else "frozen_ridge_model")
  }
  metrics <- record$metrics %||% common_object()
  binary <- identical(task$analysis$method_id,"prediction.binary.ridge")
  if(binary) {
    for(name in c("auc","average_precision","brier","log_loss","observed_prevalence","mean_prediction")) {
      if(name%in%names(metrics)) {
        interval <- metrics$bootstrap$intervals95[[name]] %||% NULL
        ci <- if(!is.null(interval))list(lower=interval[[1L]],upper=interval[[2L]],level=.95,method=metrics$bootstrap$method) else NULL
        if(name=="observed_prevalence") add(name,metrics[[name]],"1","proportion",uncertainty=ci,
          numerator=evaluation$evaluation_events,denominator=n,denominator_semantics="evaluated_labels")
        else add(name,metrics[[name]],"1",if(name=="brier")"squared_probability_error" else "dimensionless",uncertainty=ci)
      }
    }
    for(name in c("intercept","slope","intercept_in_large","intercept_offset","joint_intercept")) if(name%in%names(metrics$calibration))
      add(paste0("calibration_",name),metrics$calibration[[name]],"1","diagnostic_logit_scale")
    operating <- metrics$clinical_operating_point
    if(!is.null(operating)) {
      tp<-operating$true_positive;fn<-operating$false_negative;tn<-operating$true_negative;fp<-operating$false_positive
      ratios<-list(sensitivity=list(tp,tp+fn,"events"),specificity=list(tn,tn+fp,"nonevents"),
        positive_predictive_value=list(tp,tp+fp,"predicted_positive"),negative_predictive_value=list(tn,tn+fn,"predicted_negative"),
        accuracy=list(tp+tn,operating$n,"evaluated_labels"))
      for(name in names(ratios)) if(name%in%names(operating)) {
        ratio<-ratios[[name]]
        add(paste0("operating_point_",name),operating[[name]],"1","proportion",numerator=ratio[[1L]],denominator=ratio[[2L]],denominator_semantics=ratio[[3L]])
      }
    }
  } else {
    for(name in c("MAE","RMSE","R_squared","median_absolute_error","mean_error_observed_minus_predicted","calibration_slope","calibration_intercept")) if(name%in%names(metrics)) {
      uncertainty <- record$evaluation$bootstrap95[[name]] %||% NULL
      ci <- if(!is.null(uncertainty$lower95))list(lower=uncertainty$lower95,upper=uncertainty$upper95,level=.95,method="patient percentile bootstrap") else NULL
      add(name,metrics[[name]],if(name%in%c("R_squared","calibration_slope"))"1" else outcome_unit,
        if(name%in%c("R_squared","calibration_slope"))"dimensionless" else "original_outcome_scale",uncertainty=ci)
    }
    baseline <- record$baseline_metrics %||% record$evaluation$baseline_metrics %||% common_object()
    for(name in c("MAE","RMSE","R_squared","median_absolute_error","mean_error_observed_minus_predicted")) if(name%in%names(baseline))
      add(paste0("constant_",name),baseline[[name]],if(name=="R_squared")"1" else outcome_unit,if(name=="R_squared")"dimensionless" else "original_outcome_scale",baseline=TRUE)
  }
  result_metrics
}

common_prediction_table <- function(result,output_dir) {
  if(!length(result$metrics))return(result)
  rows <- lapply(result$metrics,function(m)data.frame(result_id=m$result_id,name=m$name,value=m$value %||% NA_real_,unit=m$unit,
    scale=m$scale,evaluation_set=m$evaluation_set,evaluation_n=m$evaluation_n %||% NA_real_,
    evaluation_events=m$evaluation_events %||% NA_real_,evaluation_nonevents=m$evaluation_nonevents %||% NA_real_,
    numerator=m$numerator %||% NA_real_,denominator=m$denominator %||% NA_real_,denominator_semantics=m$denominator_semantics,model_role=m$model_role,
    reason_code=m$reason_code %||% "",stringsAsFactors=FALSE))
  file <- file.path(output_dir,"tables","prediction_metrics.csv")
  utils::write.csv(do.call(rbind,rows),file,row.names=FALSE,na="")
  result$tables <- list(common_artifact("prediction-metrics","table",file,result,lapply(result$metrics,`[[`,"result_id"),NULL,
    "explicit per metric",paste0(common_result_label(result),". evaluation_n is the labelled evaluation cohort; evaluation_events/nonevents apply to binary outcomes. Count ratios carry arithmetic numerator/denominator and their semantics; other metrics leave those fields empty. Scales are explicit; missing uncertainty is not an interval.")))
  result
}

common_prediction_figures <- function(result,record,task,output_dir) {
  metrics <- record$metrics %||% common_object()
  ids <- lapply(result$metrics,`[[`,"result_id")
  add_figure <- function(name,caption,draw,source_ids=ids) {
    file <- file.path(output_dir,"figures",paste0(name,".png"))
    success <- tryCatch({
      grDevices::png(file,width=900,height=650)
      tryCatch(draw(),finally=grDevices::dev.off())
      TRUE
    },error=function(e)FALSE)
    if(success) result$figures[[length(result$figures)+1L]] <<- common_artifact(name,"figure",file,result,source_ids,NULL,
      "explicit per metric",caption)
    else {
      result$warnings[[length(result$warnings)+1L]] <<- list(code="PREDICTION_FIGURE_FAILED",stage="figures")
      result$execution_status <<- "partial"
    }
  }
  if(identical(task$analysis$method_id,"prediction.binary.ridge")) {
    roc <- metrics$aggregate_roc_pr %||% list()
    if(length(roc)) add_figure("binary-roc-grid",paste0(common_result_label(result),". Prespecified probability threshold grid, not a complete event-step ROC; AUC is separately computed by the fixed provider; no curve CI."),function(){
      x<-vapply(roc,`[[`,numeric(1),"fpr");y<-vapply(roc,`[[`,numeric(1),"tpr")
      graphics::plot(x,y,type="l",xlim=c(0,1),ylim=c(0,1),xlab="False positive rate",ylab="True positive rate",main=paste0(common_result_label(result)," - ROC threshold grid"))
      graphics::abline(0,1,lty=2,col="grey50")
    })
    bins <- metrics$calibration_bins %||% list()
    if(length(bins)) add_figure("binary-calibration",paste0(common_result_label(result),". Aggregate diagnostic calibration bins, no recalibration of the frozen model and no bin CI."),function(){
      x<-vapply(bins,`[[`,numeric(1),"predicted_mean");y<-vapply(bins,`[[`,numeric(1),"observed_fraction")
      graphics::plot(x,y,pch=19,xlim=c(0,1),ylim=c(0,1),xlab="Mean predicted probability",ylab="Observed fraction",main=paste0(common_result_label(result)," - calibration diagnostics"))
      graphics::abline(0,1,lty=2,col="grey50")
    })
    curve <- metrics$decision_curve %||% list()
    if(length(curve)) add_figure("binary-dca",paste0(common_result_label(result),". Exploratory net benefit at frozen prespecified thresholds; no clinical utility approval and no confidence interval."),function(){
      x<-vapply(curve,`[[`,numeric(1),"threshold");y<-vapply(curve,`[[`,numeric(1),"net_benefit");all<-vapply(curve,`[[`,numeric(1),"treat_all")
      graphics::plot(x,y,type="b",ylim=range(c(y,all,0)),xlab="Prespecified threshold",ylab="Net benefit",main=paste0(common_result_label(result)," - decision curve"))
      graphics::lines(x,all,lty=2);graphics::abline(h=0,lty=3)
      graphics::legend("bottomleft",c("Frozen model","Treat all","Treat none"),lty=1:3,bty="n")
    })
  } else {
    baseline<-record$baseline_metrics %||% record$evaluation$baseline_metrics
    if(all(c("MAE","RMSE")%in%names(metrics))&&all(c("MAE","RMSE")%in%names(baseline))) add_figure("continuous-error-comparator",
      paste0(common_result_label(result),". Original-scale MAE/RMSE of the frozen nonnegative Ridge model versus a training-median constant; no error-bar CI."),function(){
      values<-rbind(c(metrics$MAE,metrics$RMSE),c(baseline$MAE,baseline$RMSE))
      graphics::barplot(values,beside=TRUE,names.arg=c("MAE","RMSE"),col=c("steelblue","grey70"),ylab="Original outcome units",main=paste0(common_result_label(result)," - continuous errors"))
      graphics::legend("topright",c("Frozen Ridge","Training median"),fill=c("steelblue","grey70"),bty="n")
    })
  }
  result
}

common_prediction_result <- function(calculated,result,task,output_dir) {
  record <- calculated$record
  common_json_write(record,file.path(output_dir,"private","backend.json"))
  bundle <- calculated$model_bundle %||% .clinical_common$normalized$model_bundle
  if(!is.null(bundle)) {
    # Python owns the byte/type-preserving frozen JSON; R must not turn 1.0 into
    # 1 inside a canonical-hashed model or its transformation chain.
    if(!file.exists(file.path(output_dir,"private","model-bundle.json"))) stop("PREDICTION_MODEL_ARTIFACT_MISSING",call.=FALSE)
    result$binding["model_hash"] <- list(bundle$sha256 %||% NULL)
  }
  if(!is.null(calculated$individual)&&!file.exists(file.path(output_dir,"private","individual-predictions.json"))) stop("PREDICTION_TRACE_ARTIFACT_MISSING",call.=FALSE)
  rc <- record$counts %||% common_object()
  result$counts$source_rows <- rc$source_rows %||% rc$n_total %||% result$counts$source_rows
  result$counts$eligible <- rc$analyzable_n %||% result$counts$eligible
  result$counts["model_n"] <- list(if(task$analysis$prediction$operation=="train")rc$training_n %||% NULL else NULL)
  result$counts["excluded_missing"] <- list(rc$missing_outcome_n %||% 0L)
  for(name in c("training_n","training_events","training_nonevents","holdout_n","holdout_events","holdout_nonevents","evaluation_n","missing_outcome_n","missing_feature_excluded_n","prediction_n","prediction_clipped_n"))
    result$counts[name] <- list(rc[[name]] %||% NULL)
  evaluation <- common_prediction_evaluation_counts(record,task)
  for(name in names(evaluation)) result$counts[name] <- list(evaluation[[name]])
  result$diagnostics <- list(backend_status=record$status,backend=record$diagnostics %||% common_object(),
    internal_cv=record$internal_cv %||% common_object(),calibration=record$metrics$calibration %||% common_object())
  result$limitations <- c(result$limitations,record$limitations %||% list(),list(
    if(study_is_task(task))"Project-bound identity checks do not establish clinical transportability or source independence."
    else "Frozen synthetic application is not evidence of real source independence or clinical transportability."))
  result$provenance$prediction_operation <- task$analysis$prediction$operation
  result$provenance$fit_scope <- if(task$analysis$prediction$operation=="train")"training_partition_and_inner_training_folds_only" else "frozen_no_refit"
  result$provenance$validation_scope <- if(study_is_task(task))task$validation$kind else "synthetic_technical_application_only"
  if(study_is_task(task)&&!is.null(bundle)) {
    result$provenance$frozen_model_origin <- if(is.null(bundle$provenance_version)) {
      list(data_origin="unrecorded_legacy",task_purpose="unrecorded_legacy",scientific_review="pending")
    } else {
      bundle[c("provenance_version","data_origin","task_purpose","test_only","scientific_review","export_status")]
    }
  }
  result$provenance$target_policy <- bundle$target_policy %||% bundle$bundle$target_policy %||% NULL
  result$local_artifacts <- list()
  if(file.exists(file.path(output_dir,"private","model-bundle.json"))) result$local_artifacts <- c(result$local_artifacts,list(list(artifact_id="private-frozen-model",kind="local_only_model")))
  if(file.exists(file.path(output_dir,"private","individual-predictions.json"))) result$local_artifacts <- c(result$local_artifacts,list(list(artifact_id="private-individual-predictions",kind="local_only_predictions")))
  if(!(record$status%in%c("ESTIMATED","INFERENCE_COMPLETE","PREDICTED"))) {
    result$execution_status <- "blocked"
    result$applicability_status <- "limited"
    result$reason_code <- record$reason %||% "PREDICTION_ESTIMATION_UNAVAILABLE"
    result$stage <- "compute"
    return(result)
  }
  result$metrics <- common_prediction_metrics(record,result,task)
  result$execution_status <- "complete"
  cv <- record$internal_cv
  if(!is.null(cv$status)&&!(cv$status%in%c("ESTIMATED","NOT_REQUESTED"))) {
    result$execution_status <- "partial"
    result$warnings <- list(list(code="PREDICTION_CV_INCOMPLETE",stage="internal_validation"))
  }
  result <- common_prediction_table(result,output_dir)
  result <- common_prediction_figures(result,record,task,output_dir)
  result$completed_parts <- c(result$completed_parts,list("frozen_model","prediction_contract"))
  result
}
