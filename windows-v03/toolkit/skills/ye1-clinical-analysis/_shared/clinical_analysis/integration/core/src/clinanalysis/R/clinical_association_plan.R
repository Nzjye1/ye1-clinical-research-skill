# Thin reporting adapter for the single association.py numerical owner.
# No fitting, knot selection, contrast arithmetic or inferential computation here.
run_common_association_plan_provider <- function(task,data,output_dir) {
  script <- file.path(.clinical_common$root,"python/clinical_methods/association_plan_bridge.py")
  prepath <- file.path(output_dir,"private","provider-preflight.json")
  common_python(script,c("--preflight",prepath),file.path(output_dir,"private","preflight.log"))
  if(!file.exists(prepath)) return(list(ok=FALSE,reason_code="PROVIDER_PREFLIGHT_FAILED"))
  pre <- common_json_read(prepath)
  if(!isTRUE(pre$ok)) return(pre)
  for(p in names(.clinical_common$runtime$python_versions)) if(!identical(pre$runtime[[p]],.clinical_common$runtime$python_versions[[p]])) return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  if(!identical(pre$provider_version,.clinical_common$runtime$association_plan_provider_version)) return(list(ok=FALSE,reason_code="ASSOCIATION_PLAN_PROVIDER_VERSION_DRIFT"))
  request <- file.path(output_dir,"private","provider-request.json")
  response <- file.path(output_dir,"private","provider-response.json")
  limits <- common_resource_limits(task)
  payload <- list(rows=.clinical_common$normalized$rows,plan=task$analysis$association)
  if(!is.null(limits)) payload$limits <- limits
  common_json_write(payload,request)
  common_python(script,c(request,response,if(!is.null(limits))as.character(limits$max_input_bytes) else character()),file.path(output_dir,"private","provider.log"))
  if(!file.exists(response)) return(list(ok=FALSE,reason_code="PROVIDER_PROCESS_FAILED"))
  x <- common_json_read(response)
  if(!isTRUE(x$ok)) return(x)
  for(p in names(.clinical_common$runtime$python_versions)) if(!identical(x$runtime[[p]],.clinical_common$runtime$python_versions[[p]])) return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  if(!identical(x$provider_version,pre$provider_version)) return(list(ok=FALSE,reason_code="ASSOCIATION_PLAN_PROVIDER_VERSION_DRIFT"))
  x$provider <- list(id="clinical_methods.association.plan",version=x$provider_version,code_hash=x$provider_version,runtime=x$runtime)
  x
}

common_plan_estimate <- function(result,task,model,term,estimate,se,ci,p,component,
                                 contrast=NULL,exposure_value=NULL,reference=NULL,scale=NULL,se_scale=NULL) {
  spec <- model$spec
  logistic <- identical(spec$model,"logistic")
  y <- Filter(function(v)identical(v$name,spec$outcome),task$variables)[[1L]]
  x <- Filter(function(v)identical(v$name,spec$exposure),task$variables)[[1L]]
  list(result_id=paste0(result$run_id,"-",model$model_id,"-",component,"-",length(result$estimates)+1L),
    term=term,estimate=estimate,standard_error=se,ci=list(lower=ci[[1L]],upper=ci[[2L]],level=0.95,
      method=if(logistic)"Wald normal on log odds contrast, exponentiated" else "Wald t using full HC3 covariance"),
    p=p,effect_scale=scale %||% if(logistic)"odds_ratio" else "mean_difference",
    standard_error_scale=se_scale %||% if(logistic)"log_odds" else "outcome_units",
    unit=if(logistic)"dimensionless" else y$unit,predictor_unit=x$unit,exposure_unit=x$unit,
    interpretation=if(component=="rcs_curve")"Conditional exposure contrast versus the prespecified reference; not absolute outcome risk or causal effect." else if(component=="subgroup_effect")"Within-level exposure slope from the pooled interaction model; heterogeneity is assessed by the joint interaction test." else "Prespecified conditional exposure association; no causal interpretation.",
    reference=if(is.null(reference))NULL else as.character(reference),estimand=task$estimand,population=task$cohort$target_population,
    analysis_unit=task$identity$analysis_unit,evaluation_set=model$model_id,denominator=model$n_used,
    model_id=model$model_id,component=component,contrast=contrast,exposure_value=exposure_value)
}

common_plan_test <- function(result,id,name,test,n,failed_reason=NULL) {
  computed <- !is.null(test$p) && is.null(failed_reason)
  list(result_id=paste0(result$run_id,"-",id,"-test-",name),model_id=id,name=name,
    status=if(computed)"COMPUTED" else if(!is.null(failed_reason))"NOT_ESTIMABLE" else "NOT_REQUESTED",
    reason_code=if(computed)NULL else failed_reason %||% "NOT_REQUESTED",
    method=test$method %||% "not estimated",statistic=test$statistic %||% NULL,
    df_num=test$df_num %||% test$df %||% NULL,df_denom=test$df_denom %||% NULL,p=test$p %||% NULL,
    denominator=n,scope=test$scope %||% if(name=="interaction")"Joint exposure-by-subgroup terms; not comparison of within-group P values" else if(name=="nonlinearity")"Joint nonlinear exposure terms" else "All exposure terms",
    multiplicity="unadjusted_prespecified")
}

common_association_plan_result <- function(calculated,result,task,output_dir) {
  rec <- calculated$record
  common_json_write(rec,file.path(output_dir,"private","backend.json"))
  result$diagnostics <- list(backend_status=rec$status,backend=list(sample_strategy=rec$sample_strategy,multiplicity=rec$multiplicity,
    common_complete_n=rec$common_complete_n,patient_rows_returned=FALSE))
  result$counts <- list(source_rows=rec$source_rows %||% result$counts$source_rows,subjects=result$counts$subjects,
    eligible=rec$common_complete_n %||% result$counts$eligible,model_n=NULL,excluded_missing=NULL)
  result$provenance$association_sample_strategy <- task$analysis$association$sample_strategy
  result$limitations <- c(result$limitations,rec$limitations %||% list(),list(
    "Prespecified model sequence and sensitivity subsets; per-model flows are not a single common denominator.",
    "Unadjusted multiple tests and pointwise confidence intervals; no simultaneous-band or causal claim."))
  for(i in seq_along(rec$models)) {
    item <- rec$models[[i]]; r <- item$record; specitem <- task$analysis$association$models[[i]]
    flow <- setNames(lapply(c("source_rows","common_complete_n","excluded_common_missing","n_before_filter","n_after_filter","excluded_filter","filter_missing_excluded","n_used","n_excluded_missing"),function(k)item$flow[[k]] %||% NULL),
      c("source_rows","common_complete_n","excluded_common_missing","n_before_filter","n_after_filter","excluded_filter","filter_missing_excluded","n_used","n_excluded_missing"))
    flow$sample_strategy <- item$flow$sample_strategy %||% rec$sample_strategy
    flow$filter_missing_semantics <- "Missing filter values fail the prespecified condition and count within excluded_filter."
    result$model_results <- c(result$model_results,list(list(model_id=item$model_id,label=item$label,rationale=item$rationale,role=item$role,
      status=r$status,reason_code=r$reason %||% NULL,covariates=specitem$spec$covariates,flow=flow,
      nonlinear=specitem$spec$nonlinear %||% NULL,subgroup=specitem$spec$subgroup %||% NULL,
      subgroup_counts=r$subgroup_counts %||% list(),missing_by_field=r$missing_by_field %||% common_object(),
      events=r$events %||% NULL,non_events=r$non_events %||% NULL,predictor_parameters=r$predictor_parameters %||% NULL)))
    success <- identical(r$status,"COMPUTED_REVIEW_PENDING")
    for(pair in list(c("overall_exposure","exposure_test"),c("nonlinearity","nonlinearity_test"),c("interaction","interaction_test")))
      result$tests <- c(result$tests,list(common_plan_test(result,item$model_id,pair[[1L]],r[[pair[[2L]]]] %||% list(),r$n_used %||% NULL,if(success)NULL else r$reason %||% "ESTIMATION_UNAVAILABLE")))
    if(!success) {
      result$warnings <- c(result$warnings,list(list(code=r$reason %||% "ESTIMATION_UNAVAILABLE",stage=paste0("model:",item$model_id))))
      next
    }
    model <- c(specitem,list(n_used=r$n_used))
    reporting <- r$reporting %||% list()
    if(!is.null(reporting$curve)) {
      curve <- reporting$curve
      for(point in curve$points) result$estimates <- c(result$estimates,list(common_plan_estimate(result,task,model,
        paste0(specitem$spec$exposure," vs reference"),point$estimate,point$standard_error,point$ci95,NULL,"rcs_curve",
        contrast=paste0("exposure versus ",curve$reference),exposure_value=point$x,reference=curve$reference)))
    } else if(length(reporting$subgroup_effects)) {
      for(effect in reporting$subgroup_effects) {
        e <- common_plan_estimate(result,task,model,paste0(specitem$spec$exposure," within ",effect$level),effect$estimate,
          effect$standard_error,effect$ci95,effect$p,"subgroup_effect",contrast=paste0(specitem$spec$subgroup$field,"=",effect$level),reference=NULL)
        e$denominator <- effect$n_used
        e$fit_denominator <- r$n_used
        e$subgroup_level <- effect$level
        e$subgroup_reference <- specitem$spec$subgroup$reference
        e$events <- effect$events %||% NULL;e$non_events <- effect$non_events %||% NULL
        result$estimates <- c(result$estimates,list(e))
      }
    } else {
      for(coef in r$coefficients) if(identical(coef$term,specitem$spec$exposure)||startsWith(coef$term,paste0(specitem$spec$exposure,"["))) {
        logistic <- identical(r$model,"logistic")
        result$estimates <- c(result$estimates,list(common_plan_estimate(result,task,model,coef$term,
          if(logistic)coef$odds_ratio else coef$estimate,coef$standard_error,if(logistic)coef$or_ci95 else coef$ci95,coef$p,
          "exposure_effect",contrast=coef$term,reference=specitem$spec$categorical[[specitem$spec$exposure]]$reference %||% NULL)))
      }
    }
  }
  successes <- sum(vapply(result$model_results,function(m)identical(m$status,"COMPUTED_REVIEW_PENDING"),logical(1)))
  result$execution_status <- if(successes==length(result$model_results)&&successes>0)"complete" else if(successes>0)"partial" else "blocked"
  result$applicability_status <- if(result$execution_status=="complete")"pass" else if(successes>0)"limited" else "fail"
  result["reason_code"] <- list(if(result$execution_status=="complete")NULL else rec$reason %||% "ASSOCIATION_PLAN_ESTIMATION_UNAVAILABLE")
  result$local_artifacts <- c(result$local_artifacts,list(list(artifact_id="association-plan-backend",kind="private_numerical_result")))
  common_write_association_plan(result,task,rec,output_dir)
}

common_write_association_plan <- function(result,task,rec,output_dir) {
  row <- function(x) as.data.frame(lapply(x,function(v)if(is.null(v))NA else v),stringsAsFactors=FALSE,check.names=FALSE)
  if(length(result$model_results)) {
    flow_rows <- lapply(result$model_results,function(m)row(c(list(model_id=m$model_id,label=m$label,role=m$role,status=m$status,
      reason_code=m$reason_code,covariates=paste(unlist(m$covariates),collapse=";"),events=m$events,non_events=m$non_events),m$flow)))
    p <- file.path(output_dir,"tables","model_flow.csv");utils::write.csv(do.call(rbind,flow_rows),p,row.names=FALSE,na="")
    result$tables <- c(result$tables,list(common_artifact("model-flow","table",p,result,list(),NULL,"rows and independent subjects",
      paste0(study_label(task),". Prespecified model-specific filtering and complete-case flow; missing filter values are excluded."))))
    result$tables[[length(result$tables)]]$options <- list(sample_strategy=task$analysis$association$sample_strategy)
  }
  if(length(result$tests)) {
    p <- file.path(output_dir,"tables","model_tests.csv");utils::write.csv(do.call(rbind,lapply(result$tests,row)),p,row.names=FALSE,na="")
    result$tables <- c(result$tables,list(common_artifact("model-tests","table",p,result,lapply(result$tests,`[[`,"result_id"),NULL,"Wald F or chi-square; explicit df",
      "Prespecified overall, nonlinear and interaction joint Wald tests. Unadjusted multiplicity; different within-group P values do not test interaction.")))
  }
  subgroup_rows <- list()
  for(m in result$model_results) for(g in m$subgroup_counts) subgroup_rows <- c(subgroup_rows,list(row(list(
    model_id=m$model_id,status=m$status,reason_code=m$reason_code,level=g$level,n_used=g$n_used,events=g$events,non_events=g$non_events))))
  if(length(subgroup_rows)) {
    p <- file.path(output_dir,"tables","subgroup_counts.csv");utils::write.csv(do.call(rbind,subgroup_rows),p,row.names=FALSE,na="")
    result$tables <- c(result$tables,list(common_artifact("subgroup-counts","table",p,result,list(),NULL,"independent subjects/events/non-events",
      "Actual model complete-case subgroup counts, including blocked small or zero-event groups. No estimates are imputed for blocked groups.")))
  }
  if(!length(result$estimates)) return(result)
  tab <- do.call(rbind,lapply(result$estimates,function(e)row(list(result_id=e$result_id,model_id=e$model_id,component=e$component,term=e$term,
    contrast=e$contrast,exposure_value=e$exposure_value,reference=e$reference,estimate=e$estimate,standard_error=e$standard_error,
    ci_lower=e$ci$lower,ci_upper=e$ci$upper,p=e$p,effect_scale=e$effect_scale,standard_error_scale=e$standard_error_scale,
    denominator=e$denominator,fit_denominator=e$fit_denominator %||% e$denominator,events=e$events %||% NULL,non_events=e$non_events %||% NULL,
    subgroup_level=e$subgroup_level %||% NULL,subgroup_reference=e$subgroup_reference %||% NULL))))
  p <- file.path(output_dir,"tables","association_effects.csv");utils::write.csv(tab,p,row.names=FALSE,na="")
  result$tables <- c(result$tables,list(common_artifact("association-plan-effects","table",p,result,lapply(result$estimates,`[[`,"result_id"),NULL,"explicit effect scale and denominator per row",
    "Conditional exposure, pooled within-group slopes or prespecified-reference RCS contrasts; full covariance pointwise 95% intervals; no causal claim.",list(level=0.95,method="Wald full covariance contrast"))))
  for(i in seq_along(rec$models)) {
    item <- rec$models[[i]];specitem <- task$analysis$association$models[[i]]
    selected <- tab[tab$model_id==item$model_id,,drop=FALSE]
    if(!nrow(selected)) next
    curve <- item$record$reporting$curve %||% NULL
    fig <- file.path(output_dir,"figures",paste0(item$model_id,if(is.null(curve))"-effects.png" else "-rcs.png"))
    ok <- tryCatch({
      grDevices::png(fig,width=1000,height=650)
      tryCatch({
        graphics::par(mar=c(5,if(is.null(curve))12 else 5,4,2))
        if(!is.null(curve)) {
          graphics::plot(selected$exposure_value,selected$estimate,type="n",xlim=unlist(curve$domain),ylim=range(c(selected$ci_lower,selected$ci_upper)),
            xlab=paste0(specitem$spec$exposure," (",Filter(function(v)identical(v$name,specitem$spec$exposure),task$variables)[[1L]]$unit,")"),ylab=selected$effect_scale[[1L]],
            main=paste0(study_label(task)," - ",item$model_id," RCS"))
          graphics::polygon(c(selected$exposure_value,rev(selected$exposure_value)),c(selected$ci_lower,rev(selected$ci_upper)),col=grDevices::adjustcolor("steelblue",alpha.f=.2),border=NA)
          graphics::lines(selected$exposure_value,selected$estimate,col="steelblue4",lwd=2)
          graphics::abline(v=curve$reference,lty=3,col="grey40")
          graphics::legend("topleft",legend=c("Reference contrast","Pointwise 95% CI"),lty=c(1,NA),pch=c(NA,15),col=c("steelblue4","lightsteelblue"),bty="n")
        } else {
          yy <- seq_len(nrow(selected));graphics::plot(selected$estimate,yy,xlim=range(c(selected$ci_lower,selected$ci_upper)),yaxt="n",ylab="",xlab=selected$effect_scale[[1L]],pch=19,
            main=paste0(study_label(task)," - ",item$model_id))
          graphics::axis(2,at=yy,labels=selected$term,las=1);graphics::segments(selected$ci_lower,yy,selected$ci_upper,yy)
        }
        null_value <- if(selected$effect_scale[[1L]]=="odds_ratio")1 else 0
        if(!is.null(curve)) graphics::abline(h=null_value,lty=2,col="grey50") else graphics::abline(v=null_value,lty=2,col="grey50")
      },finally=grDevices::dev.off())
      TRUE
    },error=function(e)FALSE)
    if(ok) {
      art <- common_artifact(paste0(item$model_id,if(is.null(curve))"-effects" else "-rcs"),"figure",fig,result,as.list(selected$result_id),NULL,selected$effect_scale[[1L]],
        if(is.null(curve))"Conditional exposure effects. Subgroup contrasts use the pooled interaction fit; see separate joint test." else "Prespecified knots, reference and supported domain; relative RCS contrast with pointwise full-covariance 95% interval. No knot search.",list(level=0.95,method="Wald full covariance contrast"))
      art$options <- if(is.null(curve))list(model_id=item$model_id) else list(model_id=item$model_id,knots=curve$knots,reference=curve$reference,domain=curve$domain,observed_domain=curve$observed_domain,grid=curve$grid)
      result$figures <- c(result$figures,list(art))
    } else {
      result$execution_status <- "partial";result$warnings <- c(result$warnings,list(list(code="FIGURE_FAILED",stage=paste0("figure:",item$model_id))))
    }
  }
  result
}
