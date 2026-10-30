# v06 transport, aggregate projection, validation and plotting only.
# IPCW numerical owner: survival_evaluation.py. Frozen Cox inference owner unchanged.
run_common_survival_evaluation_provider <- function(task,data,output_dir) {
  script <- file.path(.clinical_common$root,"python/clinical_methods/survival_evaluation_bridge.py")
  private <- file.path(output_dir,"private")
  prepath <- file.path(private,"provider-preflight.json")
  if(!common_python(script,c("--preflight",prepath),file.path(private,"preflight.log"))||!file.exists(prepath))
    return(list(ok=FALSE,reason_code="SURVIVAL_EVALUATION_PREFLIGHT_FAILED"))
  pre <- common_json_read(prepath)
  if(!isTRUE(pre$ok)) return(pre)
  expected <- .clinical_common$runtime$python_versions
  for(p in names(expected)) if(!identical(pre$runtime[[p]],expected[[p]]))
    return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  if(!identical(pre$provider_version,.clinical_common$runtime$survival_evaluation_provider_version))
    return(list(ok=FALSE,reason_code="SURVIVAL_EVALUATION_PROVIDER_VERSION_DRIFT"))
  if(!identical(pre$frozen_model_provider_version,.clinical_common$runtime$cox_prediction_provider_version))
    return(list(ok=FALSE,reason_code="COX_PREDICTION_PROVIDER_VERSION_DRIFT"))
  prediction <- task$analysis$cox_prediction
  prediction$model_ref <- NULL;prediction$model_sha256 <- NULL
  request <- list(operation="evaluate",rows=.clinical_common$normalized$rows,
    spec=task$analysis$survival,prediction=prediction,
    feature_semantics=.clinical_common$normalized$cox_feature_semantics,
    model_json=.clinical_common$normalized$model_json,evaluation=task$analysis$survival_evaluation)
  if(study_is_task(task)) request$study_context <- list(
    provenance_version="clinical-frozen-provenance@1.0",data_origin=task$data_origin,
    task_purpose=task$task_purpose,test_only=identical(task$task_purpose,"engineering_test"),
    scientific_review="pending",export_status="local_only")
  reqpath <- file.path(private,"provider-request.json");resppath <- file.path(private,"provider-response.json")
  limits <- common_resource_limits(task)
  if(!is.null(limits)) request$limits <- limits
  common_json_write(request,reqpath)
  if(!common_python(script,c(reqpath,resppath,if(!is.null(limits))as.character(limits$max_input_bytes) else character()),file.path(private,"provider.log"))||!file.exists(resppath))
    return(list(ok=FALSE,reason_code="SURVIVAL_EVALUATION_PROCESS_FAILED"))
  calculated <- common_json_read(resppath)
  if(!isTRUE(calculated$ok)) return(calculated)
  if(!identical(calculated$provider_version,pre$provider_version)||
     !identical(calculated$frozen_model_provider_version,pre$frozen_model_provider_version))
    return(list(ok=FALSE,reason_code="SURVIVAL_EVALUATION_PROVIDER_VERSION_DRIFT"))
  for(p in names(expected)) if(!identical(calculated$runtime[[p]],expected[[p]]))
    return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  calculated$provider <- list(id="clinical_methods.survival.evaluation",version=calculated$provider_version,
    code_hash=calculated$provider_version,runtime=calculated$runtime)
  calculated
}

common_survival_evaluation_ids <- function(result) {
  ids <- character()
  for(h in result$survival_evaluation$horizon_results %||% list()) {
    ids <- c(ids,h$result_id)
    for(section in c("metrics","roc","calibration","dca"))
      ids <- c(ids,vapply(h[[section]],`[[`,character(1),"result_id"))
  }
  ids
}

common_survival_evaluation_result <- function(calculated,result,task,output_dir) {
  rec <- calculated$record;pop <- rec$population;model <- calculated$model_bundle
  spec <- task$analysis$survival;private <- file.path(output_dir,"private")
  common_json_write(rec,file.path(private,"backend.json"))
  for(name in c("frozen_cox_model.json","individual_predictions.csv","censoring_grid.json","individual_ipcw.json"))
    if(!file.exists(file.path(private,name))) stop("SURVIVAL_EVALUATION_PRIVATE_ARTIFACT_MISSING",call.=FALSE)
  if(!identical(model$model_sha256,rec$model_sha256)||
     !identical(common_sha(file.path(private,"frozen_cox_model.json")),task$analysis$cox_prediction$model_sha256))
    stop("SURVIVAL_EVALUATION_MODEL_BINDING_INVALID",call.=FALSE)
  result$binding$model_hash <- rec$model_sha256
  result$counts$model_n <- model$training_summary$n_complete
  result$counts$training_n <- model$training_summary$n_complete
  result$counts$training_events <- model$training_summary$n_events
  result$counts$training_censored <- model$training_summary$n_censored
  result$counts$evaluation_n <- pop$n_evaluable
  result$counts$events <- pop$n_events;result$counts$censored <- pop$n_censored
  result$counts$excluded_missing <- pop$n_dropped_missing
  result$counts$eligible <- pop$n_evaluable
  result$counts$missing_by_field <- common_object()
  rec$semantics <- list(time_unit=spec$time_unit,time_zero_definition=spec$time_zero_definition,
    event_definition=spec$event_definition,censoring_definition=spec$censoring_definition,
    event_code=spec$event_code,censor_code=spec$censor_code)
  rec$horizon_results <- lapply(seq_along(rec$horizon_results),function(i) {
    h <- rec$horizon_results[[i]];h$result_id <- paste0(result$run_id,"-ipcw-h",i)
    for(section in c("metrics","roc","calibration","dca")) {
      h[[section]] <- lapply(seq_along(h[[section]]),function(j) {
        row <- h[[section]][[j]];row$result_id <- paste0(h$result_id,"-",section,"-",j);row
      })
    }
    h
  })
  result$survival_evaluation <- rec
  result$execution_status <- if(identical(rec$status,"completed"))"complete" else "partial"
  result$reason_code <- if(identical(rec$status,"completed"))NULL else
    if(identical(rec$status,"unavailable"))"SURVIVAL_EVALUATION_UNAVAILABLE" else "SURVIVAL_EVALUATION_PARTIAL"
  result$diagnostics <- list(backend_status="FROZEN_RISK_IPCW_EVALUATION",backend=list(
    risk_model_refitted=FALSE,censoring_distribution_estimated=TRUE,censoring_assumption_verified=FALSE,
    uncertainty="not_implemented",specialist_metric_package_validation=FALSE))
  result$provenance$prediction_operation <- "evaluate"
  result$provenance$fit_scope <- "frozen_risk_model_with_evaluation_censoring_nuisance"
  result$provenance$validation_scope <- if(study_is_task(task))task$validation$kind else "synthetic_technical_application_only"
  if(study_is_task(task)) {
    result$provenance$frozen_model_origin <- if(is.null(model$provenance_version)) {
      list(data_origin="unrecorded_legacy",task_purpose="unrecorded_legacy",scientific_review="pending")
    } else {
      model[c("provenance_version","data_origin","task_purpose","test_only","scientific_review","export_status")]
    }
  }
  result$local_artifacts <- list(list(artifact_id="private-frozen-cox-model",kind="local_only_model"),
    list(artifact_id="private-individual-cox-predictions",kind="local_only_predictions"),
    list(artifact_id="private-censoring-grid",kind="private_metadata"),
    list(artifact_id="private-individual-ipcw",kind="private_metadata"))
  result$limitations <- c(result$limitations,list(
    "Prespecified cumulative/dynamic AUC, Brier and net benefit use marginal inverse-censoring weights estimated in this evaluation cohort. The risk model, transformations, coefficients and training baseline remain frozen.",
    "The declared assumption is independent censoring of event time and model features; it is not verified. Conditional or informative censoring is unsupported.",
    "Cases have an event at or before t; controls remain observed strictly after t. Censoring at or before t contributes zero weight and remains in the population denominator, never a negative label.",
    "Exact event/censor ties use original events before original censors; cases use G(U-), controls use G(t). Weight guards G>=0.05 and weight<=20 are fixed engineering bounds, not evidence of scientific adequacy.",
    "ROC curves display only prespecified thresholds plus the all-negative boundary. AUC uses exact weighted case-control ranks with half credit for equal scores, not the plotted grid integral.",
    "Calibration is a descriptive fixed-bin Hajek weighted observed proportion and ordinary mean predicted risk, with distinct denominators. Sparse bins are not merged; no slope, intercept, test or uncertainty interval is provided.",
    "DCA is IPCW substitution into population net-benefit moments with prespecified thresholds and treat-all/none. It is not the finite-sample positive-group-KM estimator in dcurves.",
    "Effective sample size describes weight concentration and is not a count of independently observed subjects or pairs. Early-censoring, event and control counts remain explicit at each horizon.",
    "Reference evidence uses R survival censoring estimates and independently written source-formula metrics; specialist survival metric packages were unavailable. Clinical external validity, transportability and clinical utility are not established."))
  result <- common_write_survival_evaluation(result,output_dir)
  result$completed_parts <- c(result$completed_parts,list("unchanged_frozen_cox_inference","evaluation_censoring_nuisance",
    "prespecified_ipcw_metrics_with_estimability_reasons"))
  result
}

# Only flatten declared aggregate scalar fields. No model, identity, individual
# prediction or full censoring time grid is accepted by this projection helper.
common_survival_evaluation_row <- function(values) {
  as.data.frame(lapply(values,function(v) if(is.null(v))NA else v),
    stringsAsFactors=FALSE,check.names=FALSE)
}

common_write_survival_evaluation <- function(result,output_dir) {
  rec <- result$survival_evaluation
  groups <- list(sample_flow=list(),metrics=list(),roc=list(),calibration=list(),dca=list())
  source_ids <- list(sample_flow=list(),metrics=list(),roc=list(),calibration=list(),dca=list())
  for(h in rec$horizon_results) {
    base <- list(horizon=h$horizon,horizon_status=h$status,evaluation_n=h$counts$n,
      time_unit=rec$semantics$time_unit,model_sha256=rec$model_sha256,
      method_id=rec$method_id,method_version=result$method_version,core_version=result$core_version,
      provider_version=result$provider$version,frozen_model_provider_version=rec$frozen_model_provider_version,
      source_ids=paste(vapply(result$source_refs,`[[`,character(1),"source_id"),collapse=";"),
      estimator=rec$options$estimator,censoring_source=rec$options$censoring_source,
      censoring_assumption=rec$options$censoring_assumption,tie_order=rec$options$tie_order,
      uncertainty=rec$options$uncertainty)
    groups$sample_flow <- c(groups$sample_flow,list(common_survival_evaluation_row(c(
      list(result_id=h$result_id),base,h$counts,h$weights,h$diagnostics,
      list(reason_codes=paste(unlist(h$reason_codes),collapse=";"),
        full_followup_events=rec$population$n_events,full_followup_censored=rec$population$n_censored,
        training_n=result$counts$training_n,training_events=result$counts$training_events,
        training_censored=result$counts$training_censored,excluded_missing=rec$population$n_dropped_missing,
        event_definition=rec$semantics$event_definition,censoring_definition=rec$semantics$censoring_definition,
        time_zero_definition=rec$semantics$time_zero_definition,event_code=rec$semantics$event_code,
        censor_code=rec$semantics$censor_code)))))
    source_ids$sample_flow <- c(source_ids$sample_flow,list(h$result_id))
    for(section in c("metrics","roc","calibration","dca")) {
      for(row in h[[section]]) {
        rowbase <- base[setdiff(names(base),names(row))]
        extra <- if(section=="metrics")list(scale=if(row$metric=="auc")"weighted_pair_concordance_probability" else "squared_probability_error") else
          if(section=="roc")list(case_weight_denominator=h$weights$sum_case_weights,
          control_weight_denominator=h$weights$sum_control_weights,
          sensitivity_denominator="sum_case_weights",fpr_denominator="sum_control_weights",scale="weighted_probability") else
          if(section=="calibration")list(predicted_denominator="bin_subject_count",
            observed_denominator="bin_sum_case_plus_control_weights",method="ipcw_hajek_fixed_bins",scale="absolute_event_probability") else list(scale="net_benefit_per_evaluation_subject")
        groups[[section]] <- c(groups[[section]],list(common_survival_evaluation_row(c(row,rowbase,
          list(parent_result_id=h$result_id,n_horizon_cases=h$counts$n_cases,n_horizon_controls=h$counts$n_controls,
            n_horizon_censored=h$counts$n_censored_by_horizon),extra))))
        source_ids[[section]] <- c(source_ids[[section]],list(row$result_id))
      }
    }
  }
  captions <- list(
    sample_flow="Horizon-specific cases (event U<=t), controls (U>t), and censored-by-t partition evaluation n. At-risk-before-t uses U>=t. Full-followup event/censor counts, training counts, G, raw weight sums and ESS have distinct meanings; no weight clipping.",
    metrics="Exact cumulative/dynamic IPCW AUC uses weighted case-control pairs; IPCW Brier divides by all evaluation subjects, including early censoring. Numerator and denominator definitions are explicit per row. Null estimates retain reasons; no intervals.",
    roc="Prespecified fixed probability thresholds only, plus above-all negative boundary. Sensitivity divides by case-weight sum; FPR/specificity by control-weight sum. This grid is for display and is not integrated to estimate AUC.",
    calibration="Descriptive fixed-bin Hajek calibration. Mean predicted risk divides by bin subject n; observed risk divides by bin case-plus-control weight sum. Small/empty/zero-weight bins are unavailable with reasons, without merging or intervals.",
    dca="IPCW net benefit: (weighted TP - threshold odds * weighted FP)/all evaluation subjects. Treat-all and treat-none are explicit. Prespecified thresholds; not a positive-group-KM estimator and no clinical utility claim.")
  for(section in names(groups)) {
    path <- file.path(output_dir,"tables",paste0("survival_evaluation_",section,".csv"))
    utils::write.csv(do.call(rbind,groups[[section]]),path,row.names=FALSE,na="")
    result$tables <- c(result$tables,list(common_artifact(paste0("survival-evaluation-",section),"table",path,result,
      source_ids[[section]],NULL,"explicit per row: subjects, weights, probability or net benefit",captions[[section]])))
  }
  for(i in seq_along(rec$horizon_results)) {
    h <- rec$horizon_results[[i]]
    path <- file.path(output_dir,"figures",paste0("survival_evaluation_h",i,".png"))
    ok <- tryCatch({
      grDevices::png(path,width=1500,height=750,pointsize=16)
      tryCatch({
        graphics::par(mfrow=c(1,3),cex=1,mar=c(5,5,4,2),oma=c(4,0,4,0))
        graphics::plot(c(0,1),c(0,1),type="n",xlab="IPCW false positive rate",ylab="IPCW sensitivity",main="Cumulative / dynamic ROC")
        graphics::abline(0,1,lty=2,col="grey65")
        r <- Filter(function(r)identical(r$status,"completed"),h$roc)
        if(length(r)) graphics::lines(vapply(r,`[[`,numeric(1),"false_positive_rate"),vapply(r,`[[`,numeric(1),"sensitivity"),type="b",pch=19,col="#1D5F91") else
          graphics::text(.5,.45,"Unavailable; see reason table",cex=.85)
        auc <- h$metrics[[1L]]$value;brier <- h$metrics[[2L]]$value
        graphics::mtext(paste("Exact AUC =",if(is.null(auc))"NA" else format(auc,digits=4)),side=3,line=.3,cex=.85)
        graphics::plot(c(0,1),c(0,1),type="n",xlab="Mean predicted risk (all bin subjects)",
          ylab="Observed risk (IPCW Hajek ratio)",main="Fixed-bin descriptive calibration")
        graphics::abline(0,1,lty=2,col="grey65")
        ca <- Filter(function(r)identical(r$status,"completed"),h$calibration)
        if(length(ca)) {
          xx <- vapply(ca,`[[`,numeric(1),"mean_predicted_risk");yy <- vapply(ca,`[[`,numeric(1),"observed_risk")
          graphics::points(xx,yy,pch=19,col="#1D5F91",cex=1.2)
          graphics::text(xx,yy,labels=paste0("n=",vapply(ca,`[[`,numeric(1),"n")),pos=ifelse(yy>.85,1,3),cex=.7)
        } else graphics::text(.5,.45,"No estimable bins",cex=.85)
        graphics::mtext(paste("Brier =",if(is.null(brier))"NA" else format(brier,digits=4),"; no intervals"),side=3,line=.3,cex=.85)
        dc <- Filter(function(r)identical(r$status,"completed"),h$dca)
        if(length(dc)) {
          xx <- vapply(dc,`[[`,numeric(1),"threshold");ym <- vapply(dc,`[[`,numeric(1),"net_benefit_model")
          ya <- vapply(dc,`[[`,numeric(1),"net_benefit_all")
          yr <- range(c(ym,ya,0));if(diff(yr)==0) yr<-yr+c(-.05,.05)
          xr<-range(xx);if(diff(xr)==0)xr<-pmax(0,pmin(1,xr+c(-.05,.05)))
          graphics::plot(xx,ym,type="b",pch=19,xlim=xr,ylim=yr,xlab="Prespecified risk threshold",ylab="IPCW net benefit per subject",main="Decision curve",col="#1D5F91")
          graphics::lines(xx,ya,type="b",pch=17,col="#B25735");graphics::abline(h=0,lty=2,col="grey45")
          graphics::legend("bottomleft",legend=c("Frozen model","Treat all","Treat none"),lty=c(1,1,2),pch=c(19,17,NA),col=c("#1D5F91","#B25735","grey45"),bty="n",cex=.8)
        } else {
          graphics::plot(c(0,1),c(0,1),type="n",xlab="Risk threshold",ylab="IPCW net benefit",main="Decision curve")
          graphics::text(.5,.45,"Unavailable; see reason table",cex=.85)
        }
        graphics::mtext(paste(common_result_label(result),"| t =",h$horizon,rec$semantics$time_unit,"| evaluation n =",h$counts$n,"|",h$status),outer=TRUE,side=3,line=1.5,font=2,cex=1.1)
        graphics::mtext(paste("Cases",h$counts$n_cases,"; controls",h$counts$n_controls,"; censored by t",h$counts$n_censored_by_horizon,
          "| Marginal censoring assumption unverified; uncertainty not implemented."),outer=TRUE,side=1,line=1,cex=.8)
        graphics::mtext("Frozen risk model; evaluation-cohort censoring weights. Fixed grids and bins; no clinical validation claim.",outer=TRUE,side=1,line=2.3,cex=.8)
      },finally=grDevices::dev.off())
      TRUE
    },error=function(e)FALSE)
    if(ok) {
      ids <- c(list(h$result_id),unlist(lapply(c("metrics","roc","calibration","dca"),function(s)lapply(h[[s]],`[[`,"result_id")),recursive=FALSE))
      result$figures <- c(result$figures,list(common_artifact(paste0("survival-evaluation-h",i),"figure",path,result,ids,
        h$counts$n,"explicit panel scales: weighted rates, probability, net benefit",paste(captions$roc,captions$calibration,captions$dca))))
    } else {
      result$execution_status <- "partial"
      result$warnings <- c(result$warnings,list(list(code="SURVIVAL_EVALUATION_FIGURE_FAILED",stage="figures")))
    }
  }
  result
}

validate_common_survival_evaluation_result <- function(x) {
  rec <- x$survival_evaluation;p <- rec$population
  near <- function(a,b) !is.null(a)&&!is.null(b)&&abs(a-b)<=1e-10*(1+abs(b))
  require <- function(ok,code) if(!isTRUE(ok))stop(code,call.=FALSE)
  require(identical(x$method_id,"evaluation.survival.cox.ipcw")&&length(x$metrics)==0&&
    length(x$estimates)==0&&is.null(x$survival)&&is.null(x$cox_prediction),"RESULT_IPCW_ROLE_INVALID")
  require(identical(rec$model_sha256,x$binding$model_hash),"RESULT_IPCW_MODEL_BINDING_INVALID")
  require(p$n_input==p$n_evaluable&&p$n_dropped_missing==0&&p$n_events+p$n_censored==p$n_evaluable,
    "RESULT_IPCW_POPULATION_INVALID")
  require(x$counts$evaluation_n==p$n_evaluable&&x$counts$events==p$n_events&&x$counts$censored==p$n_censored&&
    x$counts$training_n==x$counts$training_events+x$counts$training_censored,"RESULT_IPCW_COUNT_PROJECTION_INVALID")
  require(identical(rec$censoring_metadata$assumption_verified,FALSE)&&
    identical(rec$censoring_metadata$weight_clipping,FALSE)&&rec$options$uncertainty=="not_implemented",
    "RESULT_IPCW_UNSUPPORTED_CLAIM")
  require(length(rec$horizon_results)==p$n_horizons,"RESULT_IPCW_HORIZON_COUNT_INVALID")
  last <- -Inf
  for(h in rec$horizon_results) {
    co<-h$counts;w<-h$weights
    require(h$horizon>last&&h$horizon>=0,"RESULT_IPCW_HORIZON_ORDER_INVALID");last<-h$horizon
    require(co$n==p$n_evaluable&&co$n_cases+co$n_controls+co$n_censored_by_horizon==co$n&&
      co$n_at_risk_before_horizon==co$n_controls+co$n_events_at_horizon+co$n_censored_at_horizon,
      "RESULT_IPCW_HORIZON_COUNTS_INVALID")
    if(h$status!="unavailable") {
      require(near(w$sum_case_weights+w$sum_control_weights,co$n)&&near(w$sum_weights,co$n)&&
        isTRUE(h$diagnostics$weight_mass_identity_ok)&&isTRUE(h$diagnostics$km_identity_ok)&&
        w$g_at_horizon>=.05&&w$max_weight<=20,"RESULT_IPCW_WEIGHT_INVALID")
    }
    require(identical(vapply(h$metrics,`[[`,character(1),"metric"),c("auc","brier")),"RESULT_IPCW_METRIC_SET_INVALID")
    for(m in h$metrics) {
      if(m$status=="completed") require(near(m$value,m$numerator/m$denominator)&&m$value>=0&&m$value<=1&&is.null(m$reason),"RESULT_IPCW_METRIC_INVALID") else
        require(is.null(m$value)&&!is.null(m$reason),"RESULT_IPCW_METRIC_REASON_REQUIRED")
      if(m$metric=="brier")require(near(m$denominator,co$n),"RESULT_IPCW_BRIER_DENOMINATOR_INVALID")
      if(m$metric=="auc"&&!is.null(m$denominator)&&!is.null(w$sum_case_weights)&&!is.null(w$sum_control_weights))
        require(near(m$denominator,w$sum_case_weights*w$sum_control_weights),"RESULT_IPCW_AUC_DENOMINATOR_INVALID")
    }
    require(length(h$roc)==length(rec$options$roc_thresholds)+1&&
      h$roc[[1L]]$boundary=="above_all"&&is.null(h$roc[[1L]]$threshold)&&
      isTRUE(all.equal(unname(vapply(h$roc[-1],`[[`,numeric(1),"threshold")),rev(unlist(rec$options$roc_thresholds,use.names=FALSE)))),
      "RESULT_IPCW_ROC_GRID_INVALID")
    for(r in h$roc) if(r$status=="completed")require(near(r$sensitivity,r$tp_weight/w$sum_case_weights)&&
      near(r$false_positive_rate,r$fp_weight/w$sum_control_weights)&&near(r$specificity,1-r$false_positive_rate),"RESULT_IPCW_ROC_DENOMINATOR_INVALID") else
        require(is.null(r$sensitivity)&&is.null(r$false_positive_rate)&&!is.null(r$reason),"RESULT_IPCW_ROC_REASON_REQUIRED")
    require(sum(vapply(h$calibration,`[[`,numeric(1),"n"))==co$n&&
      length(h$calibration)==length(rec$options$calibration$probability_edges)-1,"RESULT_IPCW_CALIBRATION_PARTITION_INVALID")
    for(b in h$calibration) {
      require(b$n_cases+b$n_controls+b$n_censored_by_horizon==b$n,"RESULT_IPCW_BIN_COUNTS_INVALID")
      if(b$n>0)require(near(b$mean_predicted_risk,b$predicted_risk_sum/b$n),"RESULT_IPCW_PREDICTED_BIN_DENOMINATOR_INVALID")
      if(b$status=="completed")require(b$n>=rec$options$calibration$min_bin_n&&
        near(b$observed_risk,b$sum_case_weights/b$sum_weights),"RESULT_IPCW_OBSERVED_BIN_DENOMINATOR_INVALID") else
        require(is.null(b$observed_risk)&&!is.null(b$reason),"RESULT_IPCW_CALIBRATION_REASON_REQUIRED")
    }
    require(isTRUE(all.equal(unname(vapply(h$dca,`[[`,numeric(1),"threshold")),unlist(rec$options$dca_thresholds,use.names=FALSE))),"RESULT_IPCW_DCA_GRID_INVALID")
    for(d in h$dca) {
      require(d$n_treated_cases+d$n_treated_controls+d$n_treated_censored_by_horizon==d$n_treated&&
        d$population_denominator==co$n,"RESULT_IPCW_DCA_COUNTS_INVALID")
      if(d$status=="completed")require(near(d$net_benefit_model,d$numerator_model/co$n)&&
        near(d$net_benefit_all,d$numerator_all/co$n)&&d$net_benefit_none==0&&
        near(d$numerator_model,d$tp_weight-d$threshold_odds*d$fp_weight)&&
        near(d$numerator_all,w$sum_case_weights-d$threshold_odds*w$sum_control_weights),"RESULT_IPCW_DCA_DENOMINATOR_INVALID") else
        require(is.null(d$net_benefit_model)&&is.null(d$net_benefit_all)&&!is.null(d$reason),"RESULT_IPCW_DCA_REASON_REQUIRED")
    }
  }
  invisible(TRUE)
}
