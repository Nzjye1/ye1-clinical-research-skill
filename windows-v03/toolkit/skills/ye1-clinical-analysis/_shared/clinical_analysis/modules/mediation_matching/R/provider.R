# Single numerical owner for the limited module. No I/O or provider fallback.
.mm_resource_sources <- Filter(Negate(is.null),lapply(sys.frames(),function(frame)frame$ofile))
if(!length(.mm_resource_sources))stop("MM_SOURCE_PATH_REQUIRED",call.=FALSE)
.mm_resource_source <- .mm_resource_sources[[length(.mm_resource_sources)]]
.mm_resource_core <- normalizePath(file.path(dirname(.mm_resource_source),"..","..","..","integration","core"),winslash="/",mustWork=TRUE)
source(file.path(.mm_resource_core,"src/clinanalysis/R/clinical_resource_budget.R"),local=TRUE,encoding="UTF-8")
mm_methods <- c("mediation.linear.binary_exposure", "causal.psm.att.binary", "causal.psm.matched.survival")
mm_psm_hash <- "ea001b38fae962be0ecc140d9c91acc1e01df9fee9c80ae99404404f144c2f17"
mm_need <- function(ok, code) if (!isTRUE(ok)) stop(structure(list(message=code, call=NULL),
  class=c("mm_blocked", "error", "condition")))
mm_keys <- function(x, keys) is.list(x) && !anyDuplicated(names(x)) && length(x)==length(keys) && setequal(names(x),keys)
mm_num <- function(x) is.numeric(x) && !is.complex(x) && length(x)==1L && !is.na(x) && is.finite(x)
mm_text <- function(x) is.character(x) && length(x)==1L && !is.na(x) && nzchar(trimws(x))
mm_vec <- function(x) unlist(x, use.names=FALSE)
mm_hash_file <- function(path) digest::digest(readBin(path,"raw",n=file.info(path)$size),algo="sha256",serialize=FALSE)
mm_utf8 <- function(x) vapply(enc2utf8(x),function(s)paste(sprintf("%02x",as.integer(charToRaw(s))),collapse=""),"")
mm_object <- function()structure(list(),names=character())
mm_finite <- function(x, missing=FALSE) is.numeric(x) && !is.complex(x) && !any(is.nan(x)) &&
  (missing || !anyNA(x)) && all(is.finite(x[!is.na(x)]))

mm_validate <- function(d,s,resource_budget=NULL) {
  mm_need(mm_keys(s,c("schema_version","method_id","fields","covariates","semantics","options","execution")),"MM_SPEC_KEYS_INVALID")
  mm_need(identical(s$schema_version,"mediation-matching-input@1.0.0") && s$method_id %in% mm_methods,"MM_METHOD_UNSUPPORTED")
  mm_need(mm_keys(s$execution,c("test_only","data_origin")) && identical(s$execution$test_only,TRUE) &&
    identical(s$execution$data_origin,"synthetic"),"MM_SYNTHETIC_ONLY")
  mm_need(mm_keys(s$fields,c("subject","exposure","outcome","mediator","time","event")),"MM_FIELD_KEYS_INVALID")
  mm_need(is.data.frame(d) && nrow(d)>0 && !anyDuplicated(names(d)),"MM_DATA_INVALID")
  clinical_resource_check_rows(nrow(d),clinical_resource_budget(resource_budget,s$method_id))
  cv <- mm_vec(s$covariates)
  mm_need((is.list(s$covariates)||is.character(s$covariates)) && length(cv)>=1 && length(cv)<=8 &&
    all(vapply(as.list(cv),mm_text,TRUE)) && !anyDuplicated(cv),"MM_COVARIATES_INVALID")
  fs <- s$fields; used <- mm_vec(Filter(Negate(is.null),fs))
  mm_need(all(vapply(Filter(Negate(is.null),fs),mm_text,TRUE)) && !anyDuplicated(c(used,cv)) &&
    all(c(used,cv) %in% names(d)) && !any(grepl("^mm_",c(used,cv))),"MM_FIELDS_INVALID")
  ids <- d[[fs$subject]]
  mm_need(is.character(ids) && !anyNA(ids) && all(nzchar(trimws(ids))) &&
    all(validUTF8(enc2utf8(ids))) && !anyDuplicated(ids),"MM_UNIQUE_SUBJECT_IDS_REQUIRED")
  a <- d[[fs$exposure]]
  mm_need(mm_finite(a) && all(a %in% c(0,1)),"MM_BINARY_EXPOSURE_REQUIRED")
  z <- s$semantics
  mm_need(mm_keys(z,c("population","exposure_definition","outcome_definition","outcome_unit","time_unit",
    "exposure_time","covariate_latest_time","mediator_time","outcome_time","design","weights",
    "causal_assumptions_verified","treatment_induced_confounder","censoring","delayed_entry",
    "competing_events","recurrent_events","time_varying","binary_horizon_complete")),"MM_SEMANTIC_KEYS_INVALID")
  mm_need(all(vapply(z[c("population","exposure_definition","outcome_definition","outcome_unit","time_unit")],mm_text,TRUE)),"MM_DEFINITIONS_REQUIRED")
  mm_need(z$time_unit %in% c("hour","day","year") && mm_num(z$exposure_time) && mm_num(z$covariate_latest_time) &&
    z$covariate_latest_time<=z$exposure_time,"MM_PRETREATMENT_COVARIATES_REQUIRED")
  mm_need(identical(z$design,"iid_subjects") && identical(z$weights,"none"),"MM_DESIGN_UNSUPPORTED")
  mm_need(identical(z$causal_assumptions_verified,FALSE),"MM_CAUSAL_VERIFICATION_NOT_SUPPORTED")
  mm_need(identical(z$treatment_induced_confounder,FALSE),"MM_TREATMENT_INDUCED_CONFOUNDING_UNSUPPORTED")
  mm_need(all(vapply(z[c("delayed_entry","competing_events","recurrent_events","time_varying")],identical,TRUE,FALSE)),"MM_SURVIVAL_STRUCTURE_UNSUPPORTED")
  o <- s$options
  if (s$method_id==mm_methods[1]) {
    mm_need(!is.null(fs$outcome) && !is.null(fs$mediator) && is.null(fs$time) && is.null(fs$event),"MM_MEDIATION_FIELDS_INVALID")
    mm_need(mm_keys(o,c("exposure_type","mediator_type","outcome_type","interaction","bootstrap_replicates","seed","ci_level","missingness","estimand")),"MM_MEDIATION_OPTIONS_INVALID")
    mm_need(identical(o$exposure_type,"binary") && identical(o$mediator_type,"continuous") && identical(o$outcome_type,"continuous"),"MM_MEDIATION_TYPES_UNSUPPORTED")
    mm_need(is.logical(o$interaction) && length(o$interaction)==1 && !is.na(o$interaction),"MM_INTERACTION_MUST_BE_PRESPECIFIED")
    mm_need(mm_num(o$bootstrap_replicates) && o$bootstrap_replicates==floor(o$bootstrap_replicates) &&
      o$bootstrap_replicates>=200 && o$bootstrap_replicates<=5000 && mm_num(o$seed) &&
      o$seed>=0 && o$seed<=2147483646 && o$seed==floor(o$seed),"MM_BOOTSTRAP_OPTIONS_INVALID")
    mm_need(identical(o$missingness,"complete_case_joint_models") && identical(o$estimand,"complete_case_empirical_natural_contrasts") &&
      mm_num(o$ci_level) && o$ci_level==.95,"MM_MEDIATION_ESTIMAND_UNSUPPORTED")
    mm_need(mm_num(z$mediator_time) && mm_num(z$outcome_time) && z$exposure_time<z$mediator_time &&
      z$mediator_time<z$outcome_time && identical(z$censoring,"none") && is.null(z$binary_horizon_complete),"MM_MEDIATION_TIME_INVALID")
    for(n in c(cv,fs$mediator,fs$outcome)) mm_need(mm_finite(d[[n]],TRUE),"MM_MEDIATION_NUMERIC_DATA_REQUIRED")
  } else {
    mm_need(mm_keys(o,c("outcome_type","caliper_width","categorical","ratio","replacement","estimand","inference","ci_level","missingness","risk_times")),"MM_MATCH_OPTIONS_INVALID")
    mm_need(is.null(fs$mediator) && is.null(z$mediator_time),"MM_MATCH_MEDIATOR_UNSUPPORTED")
    mm_need(mm_num(o$caliper_width) && o$caliper_width>=0 && o$caliper_width<=2 && mm_num(o$ratio) && o$ratio==1 &&
      identical(o$replacement,FALSE) && identical(o$missingness,"complete_case_covariates_endpoint_required") &&
      mm_num(o$ci_level) && o$ci_level==.95,"MM_MATCH_OPTIONS_UNSUPPORTED")
    mm_need(is.list(o$categorical) && !anyDuplicated(names(o$categorical)) && all(names(o$categorical)%in%cv),"MM_MATCH_CATEGORIES_INVALID")
    for(n in cv) if(!n %in% names(o$categorical)) mm_need(mm_finite(d[[n]],TRUE),"MM_MATCH_NUMERIC_COVARIATE_INVALID")
    if(s$method_id==mm_methods[2]) {
      mm_need(!is.null(fs$outcome) && is.null(fs$time) && is.null(fs$event) && identical(o$outcome_type,"binary") &&
        identical(o$inference,"paired_rd_exact_discordance") && identical(o$estimand,"ATT_retained_matched_treated_risk_difference"),"MM_BINARY_OPTIONS_UNSUPPORTED")
      mm_need(mm_finite(d[[fs$outcome]]) && all(d[[fs$outcome]]%in%c(0,1)),"MM_BINARY_ENDPOINT_REQUIRED")
      mm_need(mm_num(z$outcome_time) && z$outcome_time>z$exposure_time && identical(z$censoring,"none") &&
        identical(z$binary_horizon_complete,TRUE) && length(o$risk_times)==0,"MM_BINARY_HORIZON_INCOMPLETE")
    } else {
      mm_need(is.null(fs$outcome) && !is.null(fs$time) && !is.null(fs$event) && identical(o$outcome_type,"survival") &&
        identical(o$inference,"pooled_cox_pair_cluster_efron") && identical(o$estimand,"matched_population_working_marginal_hazard_ratio"),"MM_COX_OPTIONS_UNSUPPORTED")
      mm_need(mm_finite(d[[fs$time]]) && all(d[[fs$time]]>0) && mm_finite(d[[fs$event]]) && all(d[[fs$event]]%in%c(0,1)),"MM_SURVIVAL_ENDPOINT_INVALID")
      mm_need(identical(z$censoring,"right_independent_conditional_on_treatment") && is.null(z$outcome_time) &&
        is.null(z$binary_horizon_complete),"MM_CENSORING_UNSUPPORTED")
      rt <- mm_vec(o$risk_times)
      mm_need(is.numeric(rt) && length(rt)>=2 && length(rt)<=12 && all(is.finite(rt)) && rt[1]==0 &&
        all(diff(rt)>0),"MM_RISK_TIMES_INVALID")
    }
  }
  invisible(TRUE)
}

mm_empty <- function(s) list(schema_version="mediation-matching-result@1.0.0",
  method_id=if(mm_text(s$method_id)&&s$method_id%in%mm_methods)s$method_id else "unvalidated",status="unavailable",reason_code="NOT_RUN",test_only=TRUE,
  scientific_review="pending",export_status="local_only",causal_assumptions_verified=FALSE,
  semantics=NULL,options=NULL,counts=mm_object(),effects=list(),diagnostics=mm_object(),
  warnings=list(),limitations=list("SYNTHETIC_ENGINEERING_ONLY","IDENTIFICATION_ASSUMPTIONS_UNVERIFIED"))

mm_effect <- function(name,scale,estimate=NA_real_,reason="NOT_ESTIMATED",n=0L) list(
  effect_id=name,scale=scale,estimate=estimate,standard_error=NA_real_,ci_lower=NA_real_,ci_upper=NA_real_,
  standard_error_scale=switch(scale,hazard_ratio="log_hazard_ratio",odds_ratio="not_estimated_exact_interval",
    risk_difference="risk_difference",outcome_unit_mean_difference="outcome_units"),
  estimand=switch(name,paired_risk_difference="retained_matched_treated_risk_difference_under_unverified_assumptions",
    conditional_matched_odds_ratio="conditional_odds_ratio_given_discordant_formed_pair",
    matched_cox_hazard_ratio="matched_population_working_marginal_hazard_ratio",
    paste0("complete_case_empirical_",name,"_under_unverified_identification_assumptions")),
  definition=switch(name,ACME_0="Q(0,1)-Q(0,0)",ACME_1="Q(1,1)-Q(1,0)",ADE_0="Q(1,0)-Q(0,0)",
    ADE_1="Q(1,1)-Q(0,1)",TOTAL="Q(1,1)-Q(0,0)",paired_risk_difference="mean(Y_treated-Y_control) across formed pairs",
    conditional_matched_odds_ratio="b/c; b=treated_only_events and c=control_only_events in diagnostics",
    matched_cox_hazard_ratio="exp(treatment coefficient) in pooled matched Cox model; not a count risk ratio"),
  n_semantics=if(scale=="outcome_unit_mean_difference")"complete_case_subjects" else "formed_matched_pairs",
  ci_level=.95,ci_method=NULL,p_value=NA_real_,test_method=NULL,df=NA_real_,n=n,
  status="unavailable",reason_code=reason,lower_boundary=NULL,upper_boundary=NULL)

# Two fixed conditional mean models. No other optimization or effect provider.
mm_med_fit <- function(d,interaction) {
  ccols <- grep("^C[0-9]+$",names(d),value=TRUE)
  xm <- cbind(Intercept=1,A=d$A,as.matrix(d[ccols]))
  xy <- cbind(Intercept=1,A=d$A,M=d$M,as.matrix(d[ccols]))
  if(interaction) xy <- cbind(xy,AM=d$A*d$M)
  mm_need(length(unique(d$A))==2 && nrow(d)>ncol(xy)+2,"MM_MEDIATION_INSUFFICIENT_SUPPORT")
  fit <- function(x,y,label) {
    f <- stats::lm.fit(x,y,tol=1e-7)
    mm_need(f$rank==ncol(x),paste0("MM_",label,"_RANK_DEFICIENT"))
    mm_need(all(is.finite(f$coefficients)) && all(is.finite(f$residuals)),"MM_MEDIATION_NONFINITE_FIT")
    yss <- sum((y-mean(y))^2)
    mm_need(yss>0 && sum(f$residuals^2)>100*.Machine$double.eps*yss,paste0("MM_",label,"_RESIDUAL_VARIANCE_ZERO"))
    condition <- kappa(x,exact=TRUE)
    mm_need(is.finite(condition) && condition<1e12,"MM_MEDIATION_ILL_CONDITIONED")
    list(coef=f$coefficients,rank=f$rank,df=f$df.residual,rss=sum(f$residuals^2),condition=condition)
  }
  fm <- fit(xm,d$M,"MEDIATOR"); fy <- fit(xy,d$Y,"OUTCOME")
  m0 <- xm; m0[,"A"] <- 0
  m1 <- xm; m1[,"A"] <- 1
  mu <- list(drop(m0%*%fm$coef),drop(m1%*%fm$coef))
  q <- matrix(NA_real_,2,2)
  for(a in 0:1) for(b in 0:1) {
    nd <- xy; nd[,"A"] <- a; nd[,"M"] <- mu[[b+1L]]
    if(interaction) nd[,"AM"] <- a*mu[[b+1L]]
    q[a+1L,b+1L] <- mean(drop(nd%*%fy$coef))
  }
  effects <- c(ACME_0=q[1,2]-q[1,1],ACME_1=q[2,2]-q[2,1],
    ADE_0=q[2,1]-q[1,1],ADE_1=q[2,2]-q[1,2],TOTAL=q[2,2]-q[1,1])
  mm_need(all(is.finite(effects)),"MM_MEDIATION_NONFINITE_EFFECT")
  list(effects=effects,nested_means=q,models=list(mediator=fm,outcome=fy))
}

mm_med_analyze <- function(d,s,rec) {
  fs <- s$fields; cv <- mm_vec(s$covariates); required <- c(fs$exposure,fs$mediator,fs$outcome,cv)
  complete <- stats::complete.cases(d[required]); n <- sum(complete)
  rec$counts <- list(source_subjects=nrow(d),complete_case_subjects=n,excluded_missing=nrow(d)-n,
    source_treated=sum(d[[fs$exposure]]==1),source_control=sum(d[[fs$exposure]]==0),
    model_treated=sum(d[[fs$exposure]][complete]==1),model_control=sum(d[[fs$exposure]][complete]==0),
    missing_by_field=as.list(vapply(d[required],function(x)sum(is.na(x)),0L)))
  dd <- data.frame(A=d[[fs$exposure]][complete],M=d[[fs$mediator]][complete],Y=d[[fs$outcome]][complete])
  for(j in seq_along(cv)) dd[[paste0("C",j)]] <- d[[cv[j]]][complete]
  point <- tryCatch(mm_med_fit(dd,s$options$interaction),error=function(e)e)
  if(inherits(point,"error")) {
    rec$reason_code <- if(inherits(point,"mm_blocked"))conditionMessage(point) else "MM_MEDIATION_FIT_FAILED"
    return(list(record=rec,private=list()))
  }
  B <- as.integer(s$options$bootstrap_replicates)
  old_kind <- RNGkind(); had_seed <- exists(".Random.seed",.GlobalEnv,inherits=FALSE)
  if(had_seed) old_seed <- get(".Random.seed",.GlobalEnv,inherits=FALSE)
  on.exit({ do.call(RNGkind,as.list(old_kind)); if(had_seed) assign(".Random.seed",old_seed,.GlobalEnv)
    else if(exists(".Random.seed",.GlobalEnv,inherits=FALSE)) rm(".Random.seed",envir=.GlobalEnv) },add=TRUE)
  RNGkind("Mersenne-Twister","Inversion","Rejection"); set.seed(as.integer(s$options$seed))
  samples <- matrix(NA_real_,B,5,dimnames=list(NULL,names(point$effects)))
  indices <- matrix(0L,B,n); failures <- character()
  for(b in seq_len(B)) {
    ix <- sample.int(n,n,replace=TRUE); indices[b,] <- ix
    one <- tryCatch(mm_med_fit(dd[ix,,drop=FALSE],s$options$interaction),error=function(e)e)
    if(inherits(one,"error")) failures <- c(failures,if(inherits(one,"mm_blocked"))conditionMessage(one) else "MM_BOOTSTRAP_FIT_FAILED")
    else samples[b,] <- one$effects
  }
  success <- sum(stats::complete.cases(samples)); min_success <- max(200L,ceiling(.9*B))
  inference_ok <- success>=min_success
  rec$effects <- lapply(seq_along(point$effects),function(i) {
    e <- mm_effect(names(point$effects)[i],"outcome_unit_mean_difference",point$effects[i],n=n)
    e$ci_method <- "iid_subject_joint_model_percentile_bootstrap_type7"
    e$status <- "partial"; e$reason_code <- "MM_BOOTSTRAP_INSUFFICIENT_SUCCESS"
    if(inference_ok) {
      v <- samples[,i]; v <- v[is.finite(v)]
      ci <- stats::quantile(v,c(.025,.975),names=FALSE,type=7)
      e$standard_error <- stats::sd(v)
      if(e$standard_error>0 && all(is.finite(ci))) {
        e$ci_lower <- ci[1]; e$ci_upper <- ci[2]; e$status <- "completed"; e["reason_code"] <- list(NULL)
      } else e$reason_code <- "MM_BOOTSTRAP_DEGENERATE"
    }
    e
  })
  rec$diagnostics <- list(engine="stats::lm.fit",standardization="empirical_complete_case_covariates",
    bootstrap=list(requested=B,successful=success,failed=B-success,min_success_required=min_success,
      failures=if(length(failures))as.list(table(failures)) else mm_object(),seed=s$options$seed,rng="Mersenne-Twister/Inversion/Rejection",
      resampling_unit="iid_subject",both_models_same_resample=TRUE,refit_both_models=TRUE,
      target_covariates="resampled_empirical_distribution",confidence_method="percentile_type7"),
    models=lapply(point$models,function(m)m[c("rank","df","rss","condition")]),
    decomposition_error=max(abs(c(point$effects["TOTAL"]-point$effects["ADE_0"]-point$effects["ACME_1"],
      point$effects["TOTAL"]-point$effects["ADE_1"]-point$effects["ACME_0"]))),
    sensitivity_analysis="not_implemented",causal_identification="not_verified")
  rec$limitations <- c(rec$limitations,as.list(c("BINARY_A_CONTINUOUS_M_AND_Y_ONLY","COMPLETE_CASE_TARGET_NOT_FULL_POPULATION",
    "NO_UNMEASURED_EXPOSURE_MEDIATOR_EXPOSURE_OUTCOME_OR_MEDIATOR_OUTCOME_CONFOUNDING_ASSUMED",
    "NO_TREATMENT_INDUCED_MEDIATOR_OUTCOME_CONFOUNDER_ASSUMED","CONSISTENCY_NO_INTERFERENCE_POSITIVITY_ASSUMED",
    "CORRECT_LINEAR_CONDITIONAL_MEANS_AND_DECLARED_INTERACTION_ASSUMED","BOOTSTRAP_DOES_NOT_ADDRESS_CONFOUNDING",
    "SMALL_SAMPLE_PERCENTILE_COVERAGE_NOT_ESTABLISHED","NO_PROPORTION_MEDIATED_OR_CAUSAL_CERTIFICATION")))
  if(length(failures)) rec$warnings <- c(rec$warnings,list("MM_BOOTSTRAP_FAILED_REPLICATES"))
  if(any(vapply(point$models,function(m)m$condition>1e8,TRUE))) rec$warnings <- c(rec$warnings,list("MM_MEDIATION_LARGE_CONDITION_NUMBER"))
  good <- all(vapply(rec$effects,function(e)e$status=="completed",TRUE))
  rec$status <- if(good && !length(failures))"completed" else "partial"
  rec["reason_code"] <- list(if(!good)"MM_BOOTSTRAP_INFERENCE_UNAVAILABLE" else if(length(failures))"MM_BOOTSTRAP_FAILED_REPLICATES" else NULL)
  list(record=rec,private=list(models=point$models,complete_subject_ids=d[[fs$subject]][complete],
    bootstrap_indices=indices,bootstrap_effects=samples,canonical_complete_data=dd,nested_means=point$nested_means))
}

mm_binary_effects <- function(yt,yc) {
  mm_need(mm_finite(yt) && mm_finite(yc) && length(yt)==length(yc) && all(c(yt,yc)%in%c(0,1)),"MM_PAIRED_BINARY_INVALID")
  n <- length(yt); diff <- yt-yc; b <- sum(diff==1); c <- sum(diff== -1); nd <- b+c
  rd <- mm_effect("paired_risk_difference","risk_difference",if(n)mean(diff) else NA_real_,"NO_MATCHED_PAIRS",n)
  rd$ci_method <- "approximate_paired_t_unclipped"; rd$test_method <- "approximate_paired_t"
  if(n) { rd$status <- "partial"; rd$reason_code <- "INSUFFICIENT_MATCHED_PAIRS" }
  if(n>=2) {
    se <- sqrt(stats::var(diff)/n); rd$standard_error <- se; rd$df <- n-1
    rd$reason_code <- "ZERO_PAIRED_VARIANCE"
    if(is.finite(se)&&se>0) {
      rd$ci_lower <- rd$estimate-stats::qt(.975,n-1)*se; rd$ci_upper <- rd$estimate+stats::qt(.975,n-1)*se
      rd$p_value <- 2*stats::pt(-abs(rd$estimate/se),n-1); rd$status <- "completed"; rd["reason_code"] <- list(NULL)
    }
  }
  or <- mm_effect("conditional_matched_odds_ratio","odds_ratio",reason="NO_DISCORDANT_PAIRS",n=n)
  or$ci_method <- "exact_clopper_pearson_discordant_probability_transformed"
  or$test_method <- "exact_two_sided_mcnemar_binomial"
  if(nd>0) {
    test <- stats::binom.test(b,nd,p=.5,conf.level=.95)
    lo <- unname(test$conf.int[1]); hi <- unname(test$conf.int[2])
    or$estimate <- if(c>0)b/c else NA_real_
    or$ci_lower <- lo/(1-lo); or$ci_upper <- if(hi<1)hi/(1-hi) else NA_real_
    or$p_value <- test$p.value; or$status <- if(c>0)"completed" else "partial"
    or["reason_code"] <- list(if(c==0)"MATCHED_OR_UNBOUNDED" else NULL)
    or["lower_boundary"] <- list(if(lo==0)"zero" else NULL)
    or["upper_boundary"] <- list(if(hi==1)"positive_infinity" else NULL)
  }
  list(effects=list(rd,or),diagnostics=list(n_pairs=n,treated_events=sum(yt),control_events=sum(yc),
    both_events=sum(yt==1&yc==1),neither_events=sum(yt==0&yc==0),treated_only_events=b,
    control_only_events=c,discordant_pairs=nd,rd_variance=if(n>=2)stats::var(diff)/n else NA_real_,
    exact_test_null="equal_marginal_risks_equivalently_discordant_probability_half",
    conditional_or_not_marginal_or=TRUE))
}

mm_cox_effect <- function(d,risk_times) {
  n <- nrow(d); pairs <- length(unique(d$pair)); events <- sum(d$event)
  e <- mm_effect("matched_cox_hazard_ratio","hazard_ratio",reason="NO_MATCHED_PAIRS",n=pairs)
  e$ci_method <- "pair_cluster_sandwich_normal_log_hazard_ratio"; e$test_method <- "pair_cluster_robust_wald_z"
  diag <- list(engine="survival::coxph",ties="efron",timefix=FALSE,risk_set="pooled_matched_subjects_time_greater_or_equal_event_time",
    tie_order="events_before_censoring_at_same_time",stratified_by_pair=FALSE,cluster_unit="matched_pair",
    events=events,censored=n-events,n_pairs=pairs,n_subjects=n,log_hazard_ratio=NA_real_,
    robust_log_se=NA_real_,naive_log_se=NA_real_,ph_assumption="not_verified",
    risk_table=list(),event_counts_by_arm=list(treated=sum(d$event[d$A==1]),control=sum(d$event[d$A==0])))
  for(t in risk_times) for(a in 0:1) diag$risk_table[[length(diag$risk_table)+1L]] <- list(time=t,
    arm=if(a==1)"treated" else "control",at_risk=sum(d$A==a&d$time>=t),
    events_before=sum(d$A==a&d$event==1&d$time<t),censors_before=sum(d$A==a&d$event==0&d$time<t),
    denominator=sum(d$A==a),support_status=if(any(d$A==a&d$time>=t))"observed" else "no_followup_remaining")
  private <- list(); reason <- NULL
  if(pairs<2) reason <- "INSUFFICIENT_MATCHED_PAIRS" else if(events==0) reason <- "NO_MATCHED_EVENTS"
  else if(any(vapply(0:1,function(a)sum(d$event[d$A==a])==0,TRUE))) reason <- "MM_COX_EVENT_ARM_EMPTY"
  if(is.null(reason)) {
    warnings <- character()
    fit <- tryCatch(withCallingHandlers(survival::coxph(survival::Surv(time,event)~A,data=d,cluster=pair,
      robust=TRUE,ties="efron",x=TRUE,y=TRUE,model=TRUE,singular.ok=FALSE,
      control=survival::coxph.control(eps=1e-9,iter.max=50,timefix=FALSE)),warning=function(w) {
        warnings <<- c(warnings,conditionMessage(w)); invokeRestart("muffleWarning")
      }),error=function(x)NULL)
    if(is.null(fit)) reason <- "MM_COX_EXECUTION_FAILED"
    else if(length(warnings)) reason <- "MM_COX_PROVIDER_WARNING"
    else {
      beta <- unname(stats::coef(fit)[1]); se <- sqrt(unname(stats::vcov(fit)[1,1])); naive <- sqrt(fit$naive.var[1,1])
      vals <- c(beta,se,naive,exp(beta),exp(beta+c(-1,1)*stats::qnorm(.975)*se))
      if(any(!is.finite(vals)) || se<=0) reason <- "MM_COX_NONFINITE_OR_ZERO_VARIANCE"
      else {
        e$estimate <- exp(beta); e$standard_error <- se # explicitly log-HR, not HR scale
        e$ci_lower <- vals[5]; e$ci_upper <- vals[6]; e$p_value <- 2*stats::pnorm(-abs(beta/se))
        e$status <- "completed"; e["reason_code"] <- list(NULL)
        diag$log_hazard_ratio <- beta; diag$robust_log_se <- se; diag$naive_log_se <- naive
        diag$iterations <- fit$iter
      }
      private$fit <- fit
    }
    private$warning_messages <- warnings
  }
  if(!is.null(reason)) e$reason_code <- reason
  diag$standard_error_scale <- "log_hazard_ratio"
  list(effects=list(e),diagnostics=diag,private=private)
}

mm_match_analyze <- function(d,s,rec,baseline_root,resource_budget=NULL) {
  path <- file.path(baseline_root,"src/clinanalysis/R/psm_v07.R")
  mm_need(file.exists(path)&&identical(mm_hash_file(path),mm_psm_hash),"MM_FROZEN_PSM_HASH_MISMATCH")
  env <- new.env(parent=baseenv())
  source(file.path(baseline_root,"src/clinanalysis/R/clinical_resource_budget.R"),local=env,encoding="UTF-8")
  source(path,local=env,encoding="UTF-8")
  # Only the checked frozen owner receives these options; no numerical clone.
  opt <- list(treatment="mm_A",outcome="mm_design_outcome",covariates=s$covariates,categorical=s$options$categorical,
    propensity_model="logistic_mle",link="logit",estimand="ATT_retained_matched_treated",ratio=1,
    replacement=FALSE,distance="logit_ps",caliper=list(width=s$options$caliper_width,scale="sd_logit_ps",
      sd_scope="common_support_retained",ddof=1,boundary="inclusive"),
    common_support=list(strategy="minmax_both",boundary="inclusive",refit=FALSE),
    ordering=list(treated="descending_logit_ps_then_subject_id_utf8",control_tie="subject_id_utf8_ascending",row_order="subject_id_utf8_ascending"),
    inference=list(method="paired_t",ci_level=.95,variance="sample_variance_of_pair_differences",conditioning="formed_matched_pairs"),
    diagnostics=list(smd_denominator="pre_support_complete_case_treated_sample_sd",indicator_sd="bernoulli_p1mp",
      standardize_binary=TRUE,ps_overlap_edges=as.list((0:10)/10),balance_reference=.1),
    guards=list(min_arm_n=2,min_probability=1e-6,max_glm_iterations=100,glm_epsilon=1e-10,separation_detection="numerical_guards_only"),prespecified=TRUE)
  dd <- d[mm_vec(s$covariates)]; dd$mm_subject <- d[[s$fields$subject]]; dd$mm_A <- d[[s$fields$exposure]]; dd$mm_design_outcome <- 0
  sem <- list(subject_id="mm_subject",treatment_definition=s$semantics$exposure_definition,
    outcome_definition="Internal constant excluded from matching; continuous effect discarded",outcome_unit="1",
    index_time=s$semantics$exposure_time,time_unit=s$semantics$time_unit,target_population=s$semantics$population)
  matched <- env$psm_v07_analyze(dd,opt,sem,resource_budget); pairs <- matched$private$pairs
  if(!is.null(matched$record$reason_code)&&grepl("^RESOURCE_",matched$record$reason_code))mm_need(FALSE,matched$record$reason_code)
  rec$counts <- matched$record$flow
  rec$diagnostics <- list(propensity=matched$record$propensity,support=matched$record$support,
    balance=matched$record$balance,overlap=matched$record$overlap,matching_owner_sha256=mm_psm_hash,
    outcomes_used_in_design=FALSE,matching_inference_conditioning="formed_matched_pairs",
    ps_estimation_uncertainty_included=FALSE,match_selection_uncertainty_included=FALSE)
  priv <- list(pairs=pairs[,setdiff(names(pairs),c("treated_outcome","control_outcome","difference")),drop=FALSE],
    subjects=matched$private$subjects[,setdiff(names(matched$private$subjects),"outcome"),drop=FALSE],model=matched$private$model)
  rec$warnings <- matched$record$warnings
  rec$limitations <- c(rec$limitations,as.list(c("INFERENCE_CONDITIONAL_ON_FORMED_PAIRS",
    "PS_ESTIMATION_SUPPORT_RESTRICTION_MATCH_SELECTION_UNCERTAINTY_EXCLUDED","NO_UNMEASURED_CONFOUNDING_CONSISTENCY_POSITIVITY_ASSUMED",
    "INDEPENDENT_MATCHED_PAIRS_ASSUMED","TARGET_COMPLETE_COVARIATE_RETAINED_MATCHED_POPULATION",
    "BALANCE_DOES_NOT_ESTABLISH_EXCHANGEABILITY")))
  if(nrow(pairs)==0) {
    rec$reason_code <- matched$record$reason_code
    return(list(record=rec,private=priv))
  }
  ti <- match(pairs$treated_subject_id,d[[s$fields$subject]]); ci <- match(pairs$control_subject_id,d[[s$fields$subject]])
  mm_need(!anyNA(c(ti,ci)) && !anyDuplicated(c(ti,ci)),"MM_PAIR_JOIN_INVALID")
  if(nrow(pairs)<30) rec$warnings <- c(rec$warnings,list("MM_SMALL_NUMBER_OF_MATCHED_PAIRS"))
  if(s$method_id==mm_methods[2]) {
    one <- mm_binary_effects(d[[s$fields$outcome]][ti],d[[s$fields$outcome]][ci])
    priv$pairs$treated_outcome <- d[[s$fields$outcome]][ti]; priv$pairs$control_outcome <- d[[s$fields$outcome]][ci]
    rec$limitations <- c(rec$limitations,as.list(c("RISK_DIFFERENCE_T_INTERVAL_APPROXIMATE_AND_UNCLIPPED",
      "CONDITIONAL_MATCHED_OR_NOT_MARGINAL_OR_OR_ATT_RISK_RATIO","BINARY_HORIZON_MUST_BE_FULLY_OBSERVED")))
  } else {
    sx <- c(ti,ci)
    sd <- data.frame(A=d[[s$fields$exposure]][sx],time=d[[s$fields$time]][sx],event=d[[s$fields$event]][sx],pair=rep(pairs$pair_id,2))
    one <- mm_cox_effect(sd,mm_vec(s$options$risk_times)); priv$survival <- sd; priv$cox <- one$private
    rec$limitations <- c(rec$limitations,as.list(c("WORKING_MARGINAL_HR_NOT_ATT_RISK_OR_SURVIVAL_PROBABILITY",
      "HAZARD_RATIO_NONCOLLAPSIBLE","PROPORTIONAL_HAZARDS_NOT_VERIFIED",
      "INDEPENDENT_RIGHT_CENSORING_CONDITIONAL_ON_TREATMENT_ASSUMED","ASYMPTOTIC_CLUSTER_SANDWICH_MAY_BE_UNRELIABLE_WITH_FEW_PAIRS",
      "COX_MONOTONE_LIKELIHOOD_DETECTION_NUMERICAL_GUARDS_ONLY")))
  }
  rec$effects <- one$effects; rec$diagnostics$outcome <- one$diagnostics
  good <- all(vapply(rec$effects,function(e)e$status=="completed",TRUE))
  rec$status <- if(good)"completed" else "partial"
  rec["reason_code"] <- list(if(good)NULL else "MM_MATCHED_INFERENCE_PARTLY_UNAVAILABLE")
  list(record=rec,private=priv)
}

mm_analyze <- function(data,spec,baseline_root,resource_budget=NULL) {
  rec <- mm_empty(spec)
  tryCatch({
    mm_need(identical(as.character(getRversion()),"4.6.1") && identical(as.character(utils::packageVersion("stats")),"4.6.1"),"MM_R_RUNTIME_MISMATCH")
    mm_need(requireNamespace("digest",quietly=TRUE) && requireNamespace("jsonlite",quietly=TRUE),"MM_IO_DEPENDENCY_UNAVAILABLE")
    mm_need(identical(as.character(utils::packageVersion("digest")),"0.6.39") &&
      identical(as.character(utils::packageVersion("jsonlite")),"2.0.0"),"MM_IO_DEPENDENCY_VERSION_MISMATCH")
    if(identical(spec$method_id,mm_methods[3])) mm_need(requireNamespace("survival",quietly=TRUE) &&
      identical(as.character(utils::packageVersion("survival")),"3.8.6"),"MM_SURVIVAL_RUNTIME_MISMATCH")
    budget <- clinical_resource_budget(resource_budget,spec$method_id)
    mm_validate(data,spec,resource_budget)
    if(spec$method_id!=mm_methods[1])clinical_resource_check_pairs(sum(data[[spec$fields$exposure]]==1),sum(data[[spec$fields$exposure]]==0),budget)
    rec$semantics <- spec$semantics; rec$options <- spec$options
    data <- data[order(mm_utf8(data[[spec$fields$subject]]),method="radix"),,drop=FALSE]; rownames(data) <- NULL
    if(spec$method_id==mm_methods[1]) mm_med_analyze(data,spec,rec) else mm_match_analyze(data,spec,rec,baseline_root,resource_budget)
  },error=function(e) {
    rec$reason_code <- if(inherits(e,"mm_blocked")||inherits(e,"clinical_resource_blocked"))conditionMessage(e) else "MM_NUMERIC_EXECUTION_FAILED"
    list(record=rec,private=list())
  })
}
