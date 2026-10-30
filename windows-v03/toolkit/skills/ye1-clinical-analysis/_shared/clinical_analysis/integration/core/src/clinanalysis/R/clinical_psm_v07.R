# PSM transport, aggregate result projection and artifacts only.
# All propensity fitting, matching and paired estimation live in psm_v07.R.
common_psm_write_frame <- function(data,path) {
  # write.csv's default numeric formatting can discard small differences on
  # large outcome baselines. Seventeen significant digits preserve doubles
  # for local audit/reload; identity strings and null values stay unchanged.
  data[] <- lapply(data,function(column) {
    if(!is.numeric(column)) return(column)
    text <- formatC(column,format="g",digits=17)
    text[is.na(column)] <- NA_character_
    text
  })
  utils::write.csv(data,path,row.names=FALSE,na="")
}

run_common_psm_provider <- function(task,data,output_dir) {
  source <- file.path(.clinical_common$root,"src/clinanalysis/R/psm_v07.R")
  version <- common_sha(source)
  if(!identical(version,.clinical_common$runtime$psm_provider_version))
    return(list(ok=FALSE,reason_code="PSM_PROVIDER_VERSION_DRIFT"))
  runtime <- list(R=as.character(getRversion()),stats=as.character(utils::packageVersion("stats")))
  if(!identical(runtime,.clinical_common$runtime$psm_runtime))
    return(list(ok=FALSE,reason_code="PSM_RUNTIME_VERSION_DRIFT"))
  normalized <- .clinical_common$normalized
  value <- psm_v07_analyze(data,normalized$psm_options,normalized$psm_semantics,normalized$resource_limits)
  private <- file.path(output_dir,"private")
  # R NA is transport absence, never a public NaN or silently fabricated zero.
  path <- file.path(private,"backend.json")
  common_json_write(value$record,path)
  record <- common_json_read(path)
  common_psm_write_frame(value$private$pairs,file.path(private,"psm_pairs.csv"))
  common_psm_write_frame(value$private$subjects,file.path(private,"psm_subjects.csv"))
  common_json_write(value$private$model,file.path(private,"psm_model.json"))
  list(ok=TRUE,record=record,provider=list(id="clinanalysis.psm_v07",version=version,
    code_hash=version,runtime=runtime))
}

common_psm_ids <- function(result) {
  record <- result$psm
  if(is.null(record)) return(character())
  c(record$result_id,record$effect$result_id,
    vapply(record$balance,`[[`,character(1),"result_id"),
    vapply(record$overlap,`[[`,character(1),"result_id"))
}

common_psm_result <- function(calculated,result,task,output_dir) {
  rec <- calculated$record
  rec$result_id <- paste0(result$run_id,"-psm")
  rec$effect$result_id <- paste0(rec$result_id,"-effect")
  for(section in c("balance","overlap")) rec[[section]] <- lapply(seq_along(rec[[section]]),function(i) {
    row <- rec[[section]][[i]];row$result_id <- paste0(rec$result_id,"-",section,"-",i);row
  })
  rec$semantics$outcome_type <- "continuous"
  rec$semantics$event_count_semantics <- "not_applicable_continuous_outcome"
  rec$semantics$causal_assumptions_verified <- FALSE
  flow <- rec$flow
  result$psm <- rec
  result$counts <- list(source_rows=flow$n_input,subjects=flow$n_input,eligible=flow$n_complete_case,
    model_n=flow$n_matched_subjects,excluded_missing=flow$n_excluded_missing_covariates,
    missing_by_field=if(length(flow$missing_by_field)) lapply(flow$missing_by_field,`[[`,"n_missing") else common_object(),
    events=NULL,non_events=NULL)
  result$diagnostics <- list(backend_status=rec$status)
  result$warnings <- lapply(rec$warnings,function(w) list(code=if(is.character(w))w else w$code,stage="psm_diagnostics"))
  result$limitations <- unique(c(result$limitations,rec$limitations,as.list(c(
    "Continuous matched-pair contrast only; no event count applies.",
    "ATT interpretation requires unverified study assumptions and is limited to complete-covariate retained matched treated subjects.",
    "Paired t inference conditions on formed pairs; independent/iid and difference-distribution assumptions remain unverified.",
    "PS estimation, matching selection and unmeasured confounding uncertainty are not included.",
    "SMD and overlap diagnostics do not establish causal validity; small aggregate cells require review."))))
  result$execution_status <- switch(rec$status,completed="complete",partial="partial",unavailable="blocked","blocked")
  result["reason_code"] <- list(rec$reason_code)
  result$applicability_status <- if(identical(rec$status,"completed"))"pass" else "limited"
  result$stage <- "compute"
  result$completed_parts <- c(result$completed_parts,list("psm_diagnostic_flow"))
  if(identical(rec$propensity$status,"completed")) result$completed_parts <- c(result$completed_parts,list("fixed_propensity_fit"))
  if(identical(rec$effect$status,"completed")) result$completed_parts <- c(result$completed_parts,list("conditional_matched_pair_inference"))
  result$local_artifacts <- c(result$local_artifacts,list(
    list(artifact_id="psm-pairs",kind="private_matched_pairs"),
    list(artifact_id="psm-subjects",kind="private_propensity_and_matching_status"),
    list(artifact_id="psm-model",kind="private_fitted_propensity_model")))
  validate_common_psm_result(result)
  common_write_psm_outputs(result,output_dir,task)
}

validate_common_psm_result <- function(result) {
  rec <- result$psm
  if(is.null(rec)) return(invisible(TRUE))
  require <- function(ok,code) if(!isTRUE(ok)) stop(code,call.=FALSE)
  equal <- function(a,b) !is.null(a)&&!is.null(b)&&isTRUE(all.equal(a,b,tolerance=1e-10,check.attributes=FALSE))
  f <- rec$flow;e <- rec$effect
  require(identical(result$method_id,"causal.psm.att.continuous")&&identical(rec$method_id,result$method_id),"RESULT_PSM_METHOD_INVALID")
  require(is.null(result$counts$events)&&is.null(result$counts$non_events)&&
    identical(rec$semantics$event_count_semantics,"not_applicable_continuous_outcome")&&
    identical(rec$semantics$causal_assumptions_verified,FALSE),"RESULT_PSM_SEMANTICS_INVALID")
  require(equal(f$n_input,result$counts$source_rows)&&equal(f$n_input,result$counts$subjects),"RESULT_PSM_SOURCE_COUNT_MISMATCH")
  for(name in setdiff(names(f),"missing_by_field")) {
    value <- f[[name]]
    require(is.null(value)||(length(value)==1L&&is.numeric(value)&&is.finite(value)&&value>=0&&value==floor(value)),"RESULT_PSM_COUNT_INVALID")
  }
  if(!is.null(f$n_input_treated)&&!is.null(f$n_input_control))
    require(equal(f$n_input_treated+f$n_input_control,f$n_input),"RESULT_PSM_ARM_COUNT_MISMATCH")
  if(!is.null(f$n_complete_case)) {
    require(equal(f$n_complete_case+f$n_excluded_missing_covariates,f$n_input)&&
      equal(f$n_complete_case_treated+f$n_complete_case_control,f$n_complete_case)&&
      equal(f$n_excluded_missing_treated+f$n_excluded_missing_control,f$n_excluded_missing_covariates)&&
      equal(f$n_complete_case_treated+f$n_excluded_missing_treated,f$n_input_treated)&&
      equal(f$n_complete_case_control+f$n_excluded_missing_control,f$n_input_control),"RESULT_PSM_MISSING_FLOW_MISMATCH")
    require(equal(result$counts$eligible,f$n_complete_case)&&equal(result$counts$excluded_missing,f$n_excluded_missing_covariates),"RESULT_PSM_PUBLIC_FLOW_MISMATCH")
    for(name in names(f$missing_by_field)) {
      row <- f$missing_by_field[[name]]
      require(equal(row$n_missing,row$n_missing_treated+row$n_missing_control)&&
        row$n_missing<=f$n_excluded_missing_covariates&&equal(row$n_missing,result$counts$missing_by_field[[name]]),"RESULT_PSM_MISSING_FIELD_MISMATCH")
    }
  }
  require(equal(f$n_matched_subjects,2*f$n_matched_pairs)&&equal(e$n_pairs,f$n_matched_pairs)&&
    equal(result$counts$model_n,f$n_matched_subjects),"RESULT_PSM_PAIR_DENOMINATOR_MISMATCH")
  if(!is.null(f$n_support_retained)) {
    require(equal(f$n_support_treated+f$n_support_control,f$n_support_retained)&&
      equal(f$n_support_treated+f$n_discarded_support_treated,f$n_complete_case_treated)&&
      equal(f$n_support_control+f$n_discarded_support_control,f$n_complete_case_control)&&
      equal(f$n_unmatched_support_treated+f$n_matched_pairs,f$n_support_treated)&&
      equal(f$n_unmatched_support_control+f$n_matched_pairs,f$n_support_control),"RESULT_PSM_SUPPORT_FLOW_MISMATCH")
  }
  if(!is.null(rec$support$caliper_width))
    require(equal(rec$support$caliper_width,rec$options$caliper$width*rec$support$logit_sd),"RESULT_PSM_CALIPER_SCALE_MISMATCH")
  require(identical(e$conditioning,"formed_matched_pairs")&&identical(e$ps_estimation_uncertainty_included,FALSE),"RESULT_PSM_INFERENCE_SCOPE_INVALID")
  if(identical(e$inference_status,"completed")) {
    # Direct pair differences are authoritative. Algebraically equivalent
    # marginal-mean and covariance decompositions suffer catastrophic
    # cancellation for large, highly correlated outcomes. Keep the recorded
    # decomposition residual as a diagnostic, never as a rejection gate.
    require(e$n_pairs>=2&&equal(e$df,e$n_pairs-1)&&e$standard_error>0&&
      equal(e$standard_error^2,e$paired_difference_variance/e$n_pairs)&&
      equal(e$t_statistic,e$estimate/e$standard_error)&&
      !is.null(e$p_value)&&e$p_value>=0&&e$p_value<=1&&e$ci_lower<=e$estimate&&e$ci_upper>=e$estimate,
      "RESULT_PSM_PAIRED_INFERENCE_INVALID")
  } else require(!is.null(e$inference_reason_code)&&is.null(e$ci_lower)&&is.null(e$ci_upper)&&
      is.null(e$p_value)&&is.null(e$t_statistic),"RESULT_PSM_UNAVAILABLE_INFERENCE_INVALID")
  for(row in rec$balance) {
    require(identical(row$denominator_scope,"pre_support_complete_case_treated")&&
      equal(row$n_before_treated,f$n_complete_case_treated)&&equal(row$n_before_control,f$n_complete_case_control)&&
      equal(row$n_after_treated,f$n_matched_pairs)&&equal(row$n_after_control,f$n_matched_pairs),"RESULT_PSM_BALANCE_DENOMINATOR_INVALID")
    for(when in c("before","after")) {
      value <- row[[paste0("smd_",when)]];reason <- row[[paste0("smd_",when,"_reason")]]
      if(is.null(value)) require(!is.null(reason),"RESULT_PSM_BALANCE_REASON_REQUIRED")
      else require(row$reference_sd>0&&is.null(reason)&&equal(value,
        (row[[paste0("mean_",when,"_treated")]]-row[[paste0("mean_",when,"_control")]])/row$reference_sd),"RESULT_PSM_SMD_SCALE_INVALID")
    }
  }
  for(population in c("ps_fit","support_retained","matched")) for(arm in c("treated","control")) {
    rows <- Filter(function(row)identical(row$population,population)&&identical(row$arm,arm),rec$overlap)
    if(!length(rows)) next
    target <- switch(population,ps_fit=f[[paste0("n_complete_case_",arm)]],
      support_retained=f[[paste0("n_support_",arm)]],matched=f$n_matched_pairs)
    require(length(rows)==10L&&equal(sum(vapply(rows,`[[`,numeric(1),"n")),target),"RESULT_PSM_OVERLAP_COUNT_MISMATCH")
    for(row in rows) {
      require(equal(row$denominator,target)&&row$n<=target,"RESULT_PSM_OVERLAP_DENOMINATOR_INVALID")
      require(if(target>0)equal(row$proportion,row$n/target) else is.null(row$proportion),"RESULT_PSM_OVERLAP_PROPORTION_INVALID")
    }
  }
  invisible(TRUE)
}

common_psm_csv <- function(rows,path,columns) {
  if(any(vapply(rows,function(row)anyDuplicated(names(row))>0L,logical(1))))
    stop("PSM_CSV_DUPLICATE_FIELD",call.=FALSE)
  allnames <- unique(c(columns,unlist(lapply(rows,names),use.names=FALSE)))
  if(!length(rows)) data <- as.data.frame(setNames(lapply(allnames,function(n)character()),allnames),stringsAsFactors=FALSE)
  else {
    items <- lapply(rows,function(row) as.data.frame(setNames(lapply(allnames,function(n) {
      x <- row[[n]]
      if(is.null(x))NA else if(is.list(x))as.character(jsonlite::toJSON(x,auto_unbox=TRUE,null="null",digits=NA)) else x
    }),allnames),stringsAsFactors=FALSE,check.names=FALSE))
    data <- do.call(rbind,items)
  }
  common_psm_write_frame(data,path)
}

common_write_psm_outputs <- function(result,output_dir,task=NULL) {
  rec <- result$psm;f <- rec$flow
  label <- if(is.null(task)) "SYNTHETIC TEST ONLY" else study_label(task)
  metadata <- list(run_id=result$run_id,method_id=result$method_id,provider_version=result$provider$version,
    core_version=result$core_version,input_hash=result$binding$input_hash,view_hash=result$provenance$view_hash,
    source_fingerprint=paste(vapply(result$source_refs,`[[`,character(1),"source_fingerprint"),collapse="|"),
    estimand=rec$options$estimand,target_population_scope="complete_covariate_retained_matched_treated",
    outcome_unit=rec$semantics$outcome_unit,event_count_semantics="not_applicable_continuous_outcome",
    scientific_review="pending",export_status="local_only",test_only=result$test_only)
  if(!is.null(task)&&study_is_task(task)) metadata <- c(metadata,list(data_origin=result$data_origin,task_purpose=result$task_purpose))
  flow <- c(list(result_id=rec$result_id,status=rec$status,reason_code=rec$reason_code,
    denominator=f$n_input,denominator_semantics="source_subjects"),f)
  effect <- c(rec$effect,list(denominator=rec$effect$n_pairs,denominator_semantics="matched_pairs",
    standard_error_scale="outcome_units",effect_scale="treated_minus_control_outcome_units"))
  datasets <- list(flow=list(flow),balance=rec$balance,overlap=rec$overlap,effect=list(effect))
  captions <- list(
    flow=paste0(label,". Source, missing covariates, common support and unmatched flow; event counts do not apply to continuous outcomes."),
    balance="Signed SMD with fixed pre-support treated reference SD: numeric sample SD, categorical indicator Bernoulli SD; nulls retain reasons. A 0.1 reference does not establish validity.",
    overlap="Prespecified propensity probability bins by stage and treatment arm; each row retains its actual population/arm denominator. Zero-arm proportions are unavailable.",
    effect="Matched treated-minus-control mean difference. Conditional paired t inference when estimable; df is pairs minus one. Unverified causal/t-distribution assumptions; PS fitting and matching-selection uncertainty excluded.")
  for(section in names(datasets)) {
    rows <- lapply(datasets[[section]],function(row) {
      meta <- metadata
      # The effect record owns its estimand. Check this one documented shared
      # semantic before emitting it once; every other duplicate remains an error.
      if("estimand" %in% names(row)) {
        if(!identical(row$estimand,meta$estimand))stop("PSM_CSV_ESTIMAND_MISMATCH",call.=FALSE)
        meta$estimand <- NULL
      }
      c(meta,row)
    })
    path <- file.path(output_dir,"tables",paste0("psm_",section,".csv"))
    empty_columns <- if(section=="overlap")c("population","arm","bin_index","lower","upper","right_inclusive","n","denominator","proportion") else character()
    common_psm_csv(rows,path,c(names(metadata),"result_id",empty_columns))
    ids <- if(section=="flow")list(rec$result_id) else if(section=="effect")list(rec$effect$result_id) else lapply(rec[[section]],`[[`,"result_id")
    denominator <- switch(section,flow=f$n_input,effect=rec$effect$n_pairs,NULL)
    ci <- if(section=="effect"&&identical(rec$effect$inference_status,"completed"))list(level=0.95,method="conditional_paired_t") else NULL
    artifact <- common_artifact(paste0("psm-",section),"table",path,result,ids,denominator,
      if(section=="effect")rec$semantics$outcome_unit else if(section=="balance")"standard_deviations" else "subjects_and_proportions",captions[[section]],ci)
    artifact$options <- list(psm=rec$options,assumptions_verified=FALSE)
    result$tables <- c(result$tables,list(artifact))
  }
  numeric_value <- function(x) if(is.null(x))NA_real_ else as.numeric(x)
  plots <- list(
    balance=function() {
      rows <- rec$balance
      if(!length(rows)) {graphics::plot.new();graphics::text(.5,.6,"No balance estimates available");graphics::text(.5,.4,rec$reason_code %||% "PS fit unavailable");return(invisible(NULL))}
      before <- vapply(rows,function(x)abs(numeric_value(x$smd_before)),numeric(1))
      after <- vapply(rows,function(x)abs(numeric_value(x$smd_after)),numeric(1))
      labels <- vapply(rows,function(x)if(is.null(x$level))x$covariate else paste0(x$covariate," [",x$level,"]"),character(1))
      graphics::par(mar=c(5,13,4,2),oma=c(3,0,0,0))
      limit <- max(c(before,after,.15),na.rm=TRUE)*1.15
      yy <- seq_along(rows)
      graphics::plot(before,yy,xlim=c(0,limit),ylim=c(.5,length(rows)+.5),yaxt="n",ylab="",xlab="Absolute SMD (fixed pre-match treated denominator)",pch=17,col="#606B83",main=paste0(label," - matched balance"))
      graphics::points(after,yy,pch=19,col="#087F8C");graphics::abline(v=.1,lty=2,col="#B2473E")
      graphics::axis(2,at=yy,labels=labels,las=1)
      graphics::legend("topright",legend=c("Before support / matching","After matching"),pch=c(17,19),col=c("#606B83","#087F8C"),bty="n")
      graphics::mtext(paste0("Undefined SMDs: before ",sum(is.na(before)),", after ",sum(is.na(after)),". See table reasons. Causal assumptions unverified."),side=1,outer=TRUE,line=1)
    },
    overlap=function() {
      graphics::par(mfrow=c(1,3),mar=c(5,4,4,1),oma=c(3,0,1,0))
      for(pop in c("ps_fit","support_retained","matched")) {
        rows <- Filter(function(x)identical(x$population,pop),rec$overlap)
        graphics::plot(NA,xlim=c(0,1),ylim=c(0,1),xlab="Propensity score (fixed bins)",ylab="Within-arm proportion",main=gsub("_"," ",pop))
        denominators <- rep(NA_integer_,2)
        for(i in 1:2) {
          arm <- c("treated","control")[[i]];group <- Filter(function(x)identical(x$arm,arm),rows)
          if(length(group)) {
            denominators[[i]] <- group[[1]]$denominator
            x <- vapply(group,function(z)(z$lower+z$upper)/2,numeric(1))
            y <- vapply(group,function(z)numeric_value(z$proportion),numeric(1))
            if(denominators[[i]]>0)graphics::lines(x,y,type="b",pch=c(19,17)[[i]],lwd=2,col=c("#087F8C","#B2473E")[[i]])
          }
        }
        graphics::legend("topright",legend=paste0(c("Treated n=","Control n="),ifelse(is.na(denominators),"unavailable",denominators)),pch=c(19,17),col=c("#087F8C","#B2473E"),bty="n")
        if(!length(rows))graphics::text(.5,.4,"PS fit unavailable")
      }
      graphics::mtext(paste0(label,". Bin shares, not density estimates. Zero-arm proportions unavailable; overlap does not verify positivity."),side=1,outer=TRUE,line=1)
    })
  for(section in names(plots)) {
    path <- file.path(output_dir,"figures",paste0("psm_",section,".png"))
    ok <- tryCatch({
      grDevices::png(path,width=if(section=="overlap")1500 else 1200,height=700,pointsize=16)
      tryCatch(plots[[section]](),finally=grDevices::dev.off());TRUE
    },error=function(e)FALSE)
    if(ok) {
      if(!is.null(task)&&study_is_task(task)) study_stamp_png(path,result)
      ids <- lapply(rec[[section]],`[[`,"result_id")
      if(!length(ids))ids <- list(rec$result_id)
      artifact <- common_artifact(paste0("psm-",section,"-figure"),"figure",path,result,ids,NULL,
        if(section=="balance")"absolute_standardized_mean_difference" else "propensity_probability_and_bin_proportion",captions[[section]])
      artifact$options <- list(psm=rec$options,assumptions_verified=FALSE)
      result$figures <- c(result$figures,list(artifact))
    } else {
      result$warnings <- c(result$warnings,list(list(code="PSM_FIGURE_FAILED",stage="figures")))
      if(identical(result$execution_status,"complete")) {result$execution_status <- "partial";result$reason_code <- "PSM_FIGURE_FAILED"}
    }
  }
  result
}
