# Reporting adapter only. survival.py is the sole numerical owner.
run_common_survival_provider <- function(task,data,output_dir) {
  script <- file.path(.clinical_common$root,"python/clinical_methods/survival_bridge.py")
  prepath <- file.path(output_dir,"private","provider-preflight.json")
  if(!common_python(script,c("--preflight",prepath),file.path(output_dir,"private","preflight.log"))||!file.exists(prepath)) return(list(ok=FALSE,reason_code="PROVIDER_PREFLIGHT_FAILED"))
  pre <- common_json_read(prepath)
  if(!isTRUE(pre$ok)) return(pre)
  for(p in names(.clinical_common$runtime$python_versions)) if(!identical(pre$runtime[[p]],.clinical_common$runtime$python_versions[[p]])) return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  if(!identical(pre$provider_version,.clinical_common$runtime$survival_provider_version)) return(list(ok=FALSE,reason_code="SURVIVAL_PROVIDER_VERSION_DRIFT"))
  request <- file.path(output_dir,"private","provider-request.json")
  response <- file.path(output_dir,"private","provider-response.json")
  private_request <- list(rows=.clinical_common$normalized$rows,spec=task$analysis$survival)
  if(study_is_task(task)) private_request$limits <- .clinical_common$normalized$resource_limits
  common_json_write(private_request,request)
  if(!common_python(script,c(request,response,if(study_is_task(task))as.character(.clinical_common$normalized$resource_limits$max_input_bytes) else character()),file.path(output_dir,"private","provider.log"))||!file.exists(response)) return(list(ok=FALSE,reason_code="PROVIDER_PROCESS_FAILED"))
  x <- common_json_read(response)
  if(!isTRUE(x$ok)) return(x)
  # request_sha256 is the Python canonical-JSON hash, not the R file-byte hash.
  # Both request/response files are separately bound by the private manifest.
  if(!identical(x$provider_version,pre$provider_version)) return(list(ok=FALSE,reason_code="SURVIVAL_PROVIDER_VERSION_DRIFT"))
  for(p in names(.clinical_common$runtime$python_versions)) if(!identical(x$runtime[[p]],.clinical_common$runtime$python_versions[[p]])) return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  x$provider <- list(id="clinical_methods.survival",version=x$provider_version,code_hash=x$provider_version,runtime=x$runtime)
  x
}

common_survival_result <- function(calculated,result,task,output_dir) {
  rec <- calculated$record; spec <- task$analysis$survival
  common_json_write(rec,file.path(output_dir,"private","backend.json"))
  result$counts$model_n <- rec$n_used %||% NULL
  result$counts$excluded_missing <- rec$n_excluded_missing %||% NULL
  result$counts$missing_by_field <- rec$missing_by_field %||% common_object()
  result$counts$events <- rec$target_events %||% NULL
  result$counts$censored <- rec$censored %||% NULL
  result$counts$predictor_parameters <- rec$cox$parameters %||% NULL
  result$diagnostics <- list(backend_status=rec$status,backend=list(original_status=rec$original_status,
    max_abs_score=rec$cox$max_abs_score %||% NULL,finite_mle_check=rec$cox$finite_mle_check %||% NULL,
    covariance=rec$cox$covariance %||% NULL,patient_rows_returned=FALSE))
  formal_ph_requested <- !is.null(spec$ph_test)
  ph_note <- if(formal_ph_requested) "Prespecified formal PH score test with explicit transform, term and global results. No test P value verifies the proportional hazards assumption." else rec$cox$ph_diagnostic_note %||% "Descriptive-only diagnostic; no formal PH test or PH assumption verification in this task."
  result$survival <- list(method=spec$method,time_unit=spec$time_unit,time_zero_definition=spec$time_zero_definition,
    event_definition=spec$event_definition,censoring_definition=spec$censoring_definition,
    event_code=spec$event_code,censor_code=spec$censor_code,missing_policy=spec$missing_policy,
    curve_method=rec$curve_method %||% "not computed",ties=rec$ties %||% "events before censoring at the same time",
    interval_boundary_note=rec$event_free_interval_note %||% "not computed",support=rec$support %||% NULL,
    curves=list(),model_status=rec$cox$status %||% "NOT_REQUESTED",model_reason=rec$cox$reason %||% NULL,
    cox_ties=if(spec$method=="cox_ph")spec$ties else NULL,
    ph_diagnostics=lapply(rec$cox$ph_trend_diagnostics %||% list(),function(p)list(term=p$term,
      rho=p$schoenfeld_log_time_spearman,diagnostic_kind="descriptive_only_schoenfeld_log_time_spearman",ph_assumption_verified=FALSE)),
    ph_assumption_verified=FALSE,ph_note=ph_note)
  result$limitations <- c(result$limitations,list(
    "Single-outcome right censoring with independent subjects; independent noninformative censoring remains a scientific assumption.",
    "Unadjusted KM on the method complete-case cohort (including Cox complete-case cohort when Cox is requested); not fitted Cox baseline or adjusted survival. Values at a prespecified grid, not a complete event-time staircase. No extrapolation beyond observed complete-case follow-up.",
    "Cox HR is conditional association, not individual absolute risk or a causal effect.",
    if(formal_ph_requested) "The formal PH score test is an asymptotic diagnostic, not proof that PH holds. Non-estimable tests carry null statistics and explicit reasons." else "This task requests descriptive PH diagnostics only; no formal PH P value or PH pass state is produced."))
  if(identical(rec$status,"BLOCKED_METHOD")) {
    result$reason_code <- rec$reason %||% "SURVIVAL_ESTIMATION_UNAVAILABLE"
    result$execution_status <- "blocked"; result$applicability_status <- "fail"
    return(result)
  }
  result$survival$curves <- lapply(seq_along(rec$curves),function(i) {
    p <- rec$curves[[i]]
    list(result_id=paste0(result$run_id,"-km-",i),time=p$time,n_at_risk=p$at_risk_before_time,
      estimate=p$event_free_probability,ci=list(lower=p$event_free_ci95[[1]],upper=p$event_free_ci95[[2]],level=0.95,method="Greenwood log-log pointwise; boundary point intervals descriptive"),
      denominator=rec$n_used,events=rec$target_events,censored=rec$censored,
      denominator_semantics="complete_case_cohort; risk count is time-specific t-minus")
  })
  result$estimates <- lapply(seq_along(rec$cox$terms %||% list()),function(i) {
    e <- rec$cox$terms[[i]]; name <- sub("\\[.*$","",e$term)
    variable <- Filter(function(v)identical(v$name,name),task$variables)
    list(result_id=paste0(result$run_id,"-cox-",i),term=e$term,estimate=e$hazard_ratio,
      log_hazard_ratio=e$log_hazard_ratio,standard_error=e$standard_error,
      ci=list(lower=e$hr_ci95[[1]],upper=e$hr_ci95[[2]],level=0.95,method="Wald normal on log hazard, exponentiated"),
      p=e$p,effect_scale="hazard_ratio",standard_error_scale="log_hazard",unit="dimensionless",
      predictor_unit=if(length(variable))variable[[1]]$unit else "declared contrast",exposure_unit="per declared predictor unit or category contrast",
      interpretation="Prespecified adjusted conditional hazard ratio; not risk ratio, absolute risk or causal effect.",
      reference=if(length(variable))variable[[1]]$reference %||% NULL else NULL,
      estimand=task$estimand,population=task$cohort$target_population,analysis_unit="subject",evaluation_set="complete_case_cohort",denominator=rec$n_used,
      events=rec$target_events)
  })
  result$execution_status <- if(identical(rec$status,"DESCRIPTIVE_ONLY_MODEL_NOT_ESTIMABLE"))"partial" else "complete"
  if(result$execution_status=="partial") result$reason_code <- rec$cox$reason %||% "COX_NOT_ESTIMABLE"
  result <- common_write_effects(result,output_dir)
  result <- common_attach_formal_ph(result,rec,output_dir)
  common_write_survival(result,output_dir)
}

common_write_survival <- function(result,output_dir) {
  s <- result$survival; points <- s$curves
  if(!length(points)) return(result)
  table <- do.call(rbind,lapply(points,function(p)data.frame(result_id=p$result_id,time=p$time,n_at_risk=p$n_at_risk,
    estimate=p$estimate,ci_lower=p$ci$lower,ci_upper=p$ci$upper,denominator=p$denominator,events=p$events,censored=p$censored,
    denominator_semantics=p$denominator_semantics,time_unit=s$time_unit,ci_method=p$ci$method)))
  ids <- lapply(points,`[[`,"result_id")
  path <- file.path(output_dir,"tables","survival_curve.csv");utils::write.csv(table,path,row.names=FALSE)
  result$tables <- c(result$tables,list(common_artifact("survival-curve-risk-table","table",path,result,ids,result$counts$model_n,s$time_unit,
    "Unadjusted KM on the method complete-case cohort, including Cox complete-case cohort. S(t) includes events through t; risk(t-) includes event and censored subjects at t. Prespecified grid only.",list(level=.95,method=points[[1]]$ci$method))))
  summary <- data.frame(n_total=result$counts$source_rows,n_used=result$counts$model_n,n_excluded_missing=result$counts$excluded_missing,
    events=result$counts$events,censored=result$counts$censored,time_unit=s$time_unit,time_zero_definition=s$time_zero_definition,
    event_definition=s$event_definition,censoring_definition=s$censoring_definition,event_code=s$event_code,censor_code=s$censor_code,
    missing_policy=s$missing_policy,model_status=s$model_status,model_reason=s$model_reason %||% "",cox_ties=s$cox_ties %||% "",
    ph_diagnostic_kind=if(is.null(s$ph_score_test))"descriptive_only" else "formal_score_and_descriptive",ph_assumption_verified=FALSE)
  path <- file.path(output_dir,"tables","survival_summary.csv");utils::write.csv(summary,path,row.names=FALSE)
  result$tables <- c(result$tables,list(common_artifact("survival-summary","table",path,result,ids,result$counts$model_n,"subjects",
    if(is.null(s$ph_score_test))"Sample flow and event/censoring definitions; no formal PH test requested." else "Sample flow and event/censoring definitions; formal PH results are separately linked in ph-score-tests.")))
  if(length(s$ph_diagnostics)) {
    ph <- do.call(rbind,lapply(s$ph_diagnostics,function(p)data.frame(term=p$term,rho=p$rho %||% NA_real_,diagnostic_kind=p$diagnostic_kind,ph_assumption_verified=FALSE)))
    path <- file.path(output_dir,"tables","ph_diagnostics.csv");utils::write.csv(ph,path,row.names=FALSE,na="")
    result$tables <- c(result$tables,list(common_artifact("ph-descriptive-diagnostics","table",path,result,lapply(result$estimates,`[[`,"result_id"),result$counts$model_n,"Spearman rho","Descriptive only; no formal PH test, P value or assumption verification.")))
  }
  figpath <- file.path(output_dir,"figures","survival.png")
  status <- tryCatch({
    grDevices::png(figpath,width=1200,height=850);on.exit(grDevices::dev.off(),add=TRUE)
    graphics::layout(matrix(c(1,2),2,1),heights=c(4,1));graphics::par(mar=c(3,5,4,2))
    graphics::plot(table$time,table$estimate,ylim=c(0,1),pch=19,xlab="",ylab="Event-free probability S(t)",main=paste0(common_result_label(result)," - KM at prespecified times"))
    graphics::segments(table$time,table$ci_lower,table$time,table$ci_upper,col="grey40")
    graphics::mtext("Pointwise 95% log-log CI; points do not imply a complete event-time curve",side=3,line=.3,cex=.8)
    graphics::par(mar=c(4,5,1,2));graphics::plot(table$time,rep(1,nrow(table)),type="n",ylim=c(.5,1.5),yaxt="n",xlab=paste("Follow-up",s$time_unit),ylab="Risk (t-)")
    graphics::text(table$time,rep(1,nrow(table)),labels=table$n_at_risk,cex=.8)
    grDevices::dev.off();on.exit(NULL,add=FALSE);TRUE
  },error=function(e)FALSE)
  if(status) result$figures <- c(result$figures,list(common_artifact("survival-curve","figure",figpath,result,ids,result$counts$model_n,s$time_unit,
    "Unadjusted KM on the method complete-case cohort, including Cox complete-case cohort. Prespecified grid with pointwise CI and risk table t-minus; no extrapolation or individual risk prediction.",list(level=.95,method=points[[1]]$ci$method)))) else {
    result$warnings <- c(result$warnings,list(list(code="FIGURE_FAILED",stage="figures")));result$execution_status <- "partial"
  }
  result
}

validate_common_survival_result <- function(x) {
  s <- x$survival
  if(!identical(s$ph_assumption_verified,FALSE)) stop("RESULT_PH_CLAIM_INVALID",call.=FALSE)
  if(!is.null(x$counts$model_n)&&!is.null(x$counts$events)&&!is.null(x$counts$censored)&&
     x$counts$events+x$counts$censored!=x$counts$model_n) stop("RESULT_SURVIVAL_COUNTS_INVALID",call.=FALSE)
  last <- Inf
  for(p in s$curves) {
    if(p$denominator!=x$counts$model_n||p$events!=x$counts$events||p$censored!=x$counts$censored||p$n_at_risk>p$denominator||p$estimate>last||
       p$ci$lower<0||p$ci$upper>1||p$ci$lower>p$estimate||p$estimate>p$ci$upper) stop("RESULT_SURVIVAL_CURVE_INVALID",call.=FALSE)
    last <- p$estimate
  }
  for(e in x$estimates) if(e$effect_scale!="hazard_ratio"||e$standard_error_scale!="log_hazard"||abs(log(e$estimate)-e$log_hazard_ratio)>1e-10) stop("RESULT_SURVIVAL_SCALE_INVALID",call.=FALSE)
  ph <- s$ph_score_test
  if(!is.null(ph)) {
    if(!identical(ph$ph_assumption_verified,FALSE)) stop("RESULT_PH_CLAIM_INVALID",call.=FALSE)
    terms <- vapply(ph$tests,`[[`,character(1),"term")
    if(anyDuplicated(terms)||sum(terms=="GLOBAL")!=1L) stop("RESULT_PH_TEST_LABELS_INVALID",call.=FALSE)
    dfs <- vapply(ph$tests,`[[`,numeric(1),"df")
    if(dfs[terms=="GLOBAL"]!=sum(dfs[terms!="GLOBAL"])||dfs[terms=="GLOBAL"]!=x$counts$predictor_parameters)
      stop("RESULT_PH_TEST_DF_INVALID",call.=FALSE)
    all_completed <- all(vapply(ph$tests,function(t)identical(t$status,"completed"),logical(1)))
    if(!identical(identical(ph$status,"completed"),all_completed)) stop("RESULT_PH_TEST_STATUS_INVALID",call.=FALSE)
    for(t in ph$tests) {
      if(t$denominator!=x$counts$model_n||t$events!=x$counts$events) stop("RESULT_PH_COUNTS_INVALID",call.=FALSE)
      if(identical(t$status,"completed")) {
        if(is.null(t$chisq)||t$chisq<0||is.null(t$p_value)||t$p_value<0||t$p_value>1||t$df<1) stop("RESULT_PH_TEST_INVALID",call.=FALSE)
      } else if(is.null(t$reason)||!nzchar(t$reason)||!is.null(t$chisq)||!is.null(t$p_value)) stop("RESULT_PH_TEST_REASON_REQUIRED",call.=FALSE)
    }
  }
  invisible(TRUE)
}
