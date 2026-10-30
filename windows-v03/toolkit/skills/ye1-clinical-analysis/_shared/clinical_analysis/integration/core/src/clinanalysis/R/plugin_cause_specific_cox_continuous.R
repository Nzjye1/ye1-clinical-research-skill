# Opt-in continuous-exposure route. It does not alter the legacy binary plugin.
continuous_block <- function(code, detail) {
  stop(structure(list(message = detail, code = code),
                 class = c("continuous_cox_block", "error", "condition")))
}

continuous_columns <- function(a, s) {
  c(a$exposure, a$time, a$event, a$competing_event, s$age, s$sex,
    s$ami, s$ckd, s$other_shock, unlist(s$physiology, use.names = FALSE),
    unlist(s$treatments, use.names = FALSE))
}

continuous_check <- function(task, data) {
  a <- task$analysis; s <- a$continuous_v4; md <- a$missing_data
  if (!identical(a$method, "cause_specific_cox") ||
      !identical(md$method, "multiple_imputation"))
    continuous_block("METHOD", "Continuous route requires cause_specific_cox and multiple_imputation.")
  if (!identical(sort(names(s$physiology)), c("creatinine", "lactate", "map")) ||
      !identical(sort(names(s$treatments)), c("circulatory", "magnesium", "rrt")))
    continuous_block("MAPPING", "Required physiology/treatment mappings are incomplete.")
  columns <- continuous_columns(a, s)
  if (anyNA(columns) || any(!nzchar(columns)) || anyDuplicated(columns) ||
      length(setdiff(columns, names(data))) || any(make.names(columns) != columns))
    continuous_block("COLUMNS", "Mapped columns must exist, be unique and use R-safe names.")
  expected_covs <- c(s$age, s$sex, s$ami, s$ckd,
                     s$physiology$creatinine, s$physiology$lactate, s$physiology$map)
  if (!identical(unname(unlist(a$covariates, use.names = FALSE)), unname(expected_covs)))
    continuous_block("COVARIATES", "The seven frozen adjustment terms must be present in order.")
  if (!identical(as.integer(md$m), 50L) || !identical(as.integer(md$maxit), 30L) ||
      !identical(as.integer(md$seed), 20260922L) || !identical(as.integer(s$donors), 5L) ||
      !identical(as.numeric(s$exposure_unit), 0.5) ||
      !identical(as.numeric(s$reference), 2.0))
    continuous_block("FROZEN_PARAMETERS", "Frozen m/maxit/seed/donors/exposure scale/reference mismatch.")
  if (!identical(sort(names(s$bounds)), c("creatinine", "lactate", "map")) ||
      !isTRUE(all.equal(unlist(s$bounds$creatinine), c(.2,20))) ||
      !isTRUE(all.equal(unlist(s$bounds$lactate), c(.2,30))) ||
      !isTRUE(all.equal(unlist(s$bounds$map), c(20,200))))
    continuous_block("BOUNDS", "Physiology bounds must match the frozen source cleaning ranges.")
  if (!identical(as.character(utils::packageVersion("mice")), "3.19.0") ||
      !identical(as.character(utils::packageVersion("survival")), "3.8.6"))
    continuous_block("RUNTIME", "mice/survival versions do not match renv.lock.")
  if (any(!is.finite(data[[a$time]]) | data[[a$time]] <= 0) ||
      !is.numeric(data[[a$exposure]]) || any(!is.finite(data[[a$exposure]])) ||
      anyNA(data[, setdiff(columns, unlist(s$physiology)), drop = FALSE]))
    continuous_block("FIXED_FIELDS", "Exposure, follow-up, event and fixed predictors must be complete and valid.")
  if (!all(data[[a$event]] %in% 0:1) || !all(data[[a$competing_event]] %in% 0:1) ||
      any(data[[a$event]] + data[[a$competing_event]] != 1L))
    continuous_block("EVENT", "Death and live discharge must form one complete event type.")
  if (sum(data[[a$event]] == 1L) < 11L || sum(data[[a$competing_event]] == 1L) < 11L)
    continuous_block("SMALL_EVENT_CELL", "Event and discharge counts require at least 11 rows for a public result.")
  for (col in c(s$sex, s$ami, s$ckd, s$other_shock, unlist(s$treatments))) {
    if (!all(data[[col]] %in% 0:1)) continuous_block("FLAG", "All case/treatment flags must be complete 0/1.")
  }
  for (key in names(s$physiology)) {
    x <- data[[s$physiology[[key]]]]; bounds <- unlist(s$bounds[[key]])
    if (!is.numeric(x) || any(!is.finite(x[!is.na(x)])) ||
        any(x < bounds[1L] | x > bounds[2L], na.rm = TRUE))
      continuous_block("PHYSIOLOGY", paste("Invalid observed", key, "value."))
    if (sum(!is.na(x)) < 5L || length(unique(stats::na.omit(x))) < 2L)
      continuous_block("DONORS", paste("Insufficient PMM observed-value support for", key))
  }
  for (col in c(a$exposure, expected_covs))
    if (length(unique(stats::na.omit(data[[col]]))) < 2L)
      continuous_block("CONSTANT_MODEL_TERM", paste("Constant model term", col))
  private <- normalizePath(s$private_dir %||% "", mustWork = FALSE)
  work <- normalizePath(file.path(getwd(), "work"), mustWork = FALSE)
  if (!nzchar(s$private_dir %||% "") || !startsWith(private, paste0(work, "/")))
    continuous_block("PRIVATE_DIR", "Private output must be within this analysis module's work directory.")
  if (dir.exists(private) && length(list.files(private, all.files = TRUE, no.. = TRUE)))
    continuous_block("PRIVATE_DIR_EXISTS", "A private run directory must be new and empty.")
  invisible(TRUE)
}

continuous_rcs <- function(x, k) {
  if (length(k) != 3L || any(diff(k) <= 0)) continuous_block("KNOTS", "Exposure knots collide.")
  tp <- function(v, z) pmax(v-z, 0)^3
  (tp(x,k[1L]) - (k[3L]-k[1L])/(k[3L]-k[2L])*tp(x,k[2L]) +
     (k[2L]-k[1L])/(k[3L]-k[2L])*tp(x,k[3L]))/(k[3L]-k[1L])^2
}

continuous_nelson_aalen <- function(time, event) {
  at <- sort(unique(time[event == 1L]))
  if (!length(at)) continuous_block("EVENT_SUPPORT", "No observed cause-specific events.")
  step <- vapply(at, function(t) sum(event == 1L & time == t)/sum(time >= t), numeric(1))
  c(0, cumsum(step))[findInterval(time, at)+1L]
}

continuous_mice_input <- function(data, a, s, knots) {
  p <- s$physiology
  input <- data[c(a$exposure, a$time, a$event, s$age, s$sex, s$ami,
                  s$ckd, s$other_shock, unlist(s$treatments))]
  input[[p$creatinine]] <- log(data[[p$creatinine]])
  input[[p$lactate]] <- log(data[[p$lactate]])
  input[[p$map]] <- data[[p$map]]
  input$exposure_rcs_fixed <- continuous_rcs(data[[a$exposure]], knots)
  input$death_na_fixed <- continuous_nelson_aalen(data[[a$time]], data[[a$event]])
  input$discharge_na_fixed <- continuous_nelson_aalen(data[[a$time]], data[[a$competing_event]])
  input
}

continuous_impute <- function(data, a, s, knots, private, label) {
  p <- s$physiology; targets <- unlist(p, use.names = FALSE)
  x <- continuous_mice_input(data, a, s, knots)
  methods <- stats::setNames(rep("", ncol(x)), names(x))
  methods[targets[colSums(is.na(x[targets])) > 0L]] <- "pmm"
  predictors <- matrix(0L, ncol(x), ncol(x), dimnames = list(names(x), names(x)))
  auxiliary <- setdiff(names(x), c(targets, a$exposure, a$time, a$event,
                                   s$age, s$sex, s$ami, s$ckd))
  constant <- auxiliary[vapply(x[auxiliary], function(z) length(unique(stats::na.omit(z))) < 2L, logical(1))]
  for (target in targets) predictors[target, setdiff(names(x), c(target, constant))] <- 1L
  active <- names(methods)[methods != ""]
  n_missing <- colSums(is.na(x[targets]))
  sd_not_applicable <- names(n_missing)[n_missing == 1L]
  dir.create(private, recursive = TRUE, showWarnings = FALSE)
  if (!length(active)) {
    x[[p$creatinine]] <- exp(x[[p$creatinine]])
    x[[p$lactate]] <- exp(x[[p$lactate]])
    x[[a$competing_event]] <- 1L - x[[a$event]]
    return(list(datasets = rep(list(x), 50L),
    missing = lapply(p, function(col) is.na(data[[col]])),
    diagnostic = list(status = "NO_IMPUTATION_NEEDED", imputed_variables = list(),
                      constant_auxiliary_excluded = as.list(constant))))
  }
  run <- function(iter) mice::mice(x, m = 50L, maxit = iter, method = methods,
    predictorMatrix = predictors, donors = 5L, seed = 20260922L,
    remove.collinear = FALSE, remove.constant = FALSE, printFlag = FALSE)
  mids <- run(30L)
  diag30 <- continuous_chain_diagnostics(mids, active, sd_not_applicable)
  saveRDS(list(mids=mids, predictor_matrix=predictors, config=s, knots=knots),
          file.path(private, paste0(label, "-mids-30.rds")))
  diag80 <- NULL
  if (!diag30$stable) {
    mids <- run(80L)
    diag80 <- continuous_chain_diagnostics(mids, active, sd_not_applicable)
    saveRDS(list(mids=mids, predictor_matrix=predictors, config=s, knots=knots),
            file.path(private, paste0(label, "-mids-80.rds")))
    if (!diag80$stable) continuous_block("CHAIN_DRIFT", "MICE chains fail the frozen 80-iteration Rhat guard.")
  }
  if (!is.null(mids$loggedEvents) && nrow(mids$loggedEvents))
    continuous_block("MICE_LOGGED_EVENTS", "MICE flagged a predictor; inspect private diagnostics.")
  completed <- lapply(seq_len(50L), function(i) {
    d <- mice::complete(mids, i)
    d[[p$creatinine]] <- exp(d[[p$creatinine]])
    d[[p$lactate]] <- exp(d[[p$lactate]])
    d[[a$competing_event]] <- 1L - d[[a$event]]
    for (key in names(p)) {
      col <- p[[key]]; observed <- data[[col]]; z <- d[[col]]; bounds <- unlist(s$bounds[[key]])
      if (any(!is.finite(z)) || any(z < bounds[1L] | z > bounds[2L]) ||
          !isTRUE(all.equal(z[!is.na(observed)], observed[!is.na(observed)], tolerance=1e-10)))
        continuous_block("INVALID_IMPUTATION", paste("Imputed", key, "outside bounds or observed values altered."))
    }
    d
  })
  distributions <- lapply(names(p), function(key) {
    col <- p[[key]]; observed <- data[[col]]
    imputed <- unlist(lapply(completed, function(d) d[[col]][is.na(observed)]), use.names=FALSE)
    list(observed_range=range(observed,na.rm=TRUE),
         imputed_range=if (length(imputed)) range(imputed) else NULL,
         observed_quartiles=as.list(stats::quantile(observed,c(.25,.5,.75),na.rm=TRUE)),
         imputed_quartiles=if (length(imputed)) as.list(stats::quantile(imputed,c(.25,.5,.75))) else NULL,
         observed_distinct_values=length(unique(stats::na.omit(observed))),
         imputed_on_observed_value_support=if (length(imputed)) {
           donors <- observed[!is.na(observed)]
           all(vapply(imputed,function(value)
             any(abs(donors-value) <= 1e-10*pmax(1,abs(value))),logical(1)))
         } else NA)
  })
  names(distributions) <- names(p)
  diagnostic <- list(status="COMPLETE", m=50L, seed=20260922L, donors=5L,
      matchtype=1L, ridge=1e-5, maxit=if (is.null(diag80)) 30L else 80L,
      imputed_variables=as.list(active),
      missing_counts=as.list(n_missing),
      predictor_matrix=lapply(active,function(target) as.list(names(which(predictors[target,]==1L)))),
      constant_auxiliary_excluded=as.list(constant), chain_30=diag30,
      chain_80=diag80, distributions=distributions,
      logged_events=if (is.null(mids$loggedEvents)) list() else
        split(mids$loggedEvents,seq_len(nrow(mids$loggedEvents))))
  saveRDS(diagnostic,file.path(private,paste0(label,"-diagnostics-private.rds")))
  for (pass in c("chain_30","chain_80")) if (!is.null(diagnostic[[pass]])) {
    for (target in active) {
      diagnostic[[pass]]$mean[[target]]$chain_values <- NULL
      diagnostic[[pass]]$sd[[target]]$chain_values <- NULL
    }
  }
  for (target in active) if (n_missing[[target]] <= 10L) {
    for (pass in c("chain_30","chain_80")) if (!is.null(diagnostic[[pass]])) {
      diagnostic[[pass]]$mean[[target]] <- list(status="WITHHELD_SMALL_MISSING_CELL",
                                                 stable=diagnostic[[pass]]$mean[[target]]$stable)
      diagnostic[[pass]]$sd[[target]] <- list(status=if (n_missing[[target]]==1L)
        "STRUCTURALLY_UNDEFINED_N1" else "WITHHELD_SMALL_MISSING_CELL",
        stable=diagnostic[[pass]]$sd[[target]]$stable)
    }
    key <- names(p)[match(target,unlist(p,use.names=FALSE))]
    diagnostic$distributions[[key]]$imputed_range <- NULL
    diagnostic$distributions[[key]]$imputed_quartiles <- NULL
    diagnostic$distributions[[key]]$imputed_on_observed_value_support <- NULL
    diagnostic$missing_counts[[target]] <- "WITHHELD_1_TO_10"
  }
  list(datasets=completed, missing=lapply(p,function(col) is.na(data[[col]])),
       diagnostic=diagnostic)
}

continuous_cox_fit <- function(d, a, s, event, nonlinear=FALSE) {
  terms <- c(a$exposure, if (nonlinear) "exposure_rcs_fixed", unlist(a$covariates))
  form <- stats::reformulate(terms, response=sprintf("survival::Surv(%s,%s)",a$time,event))
  warned <- FALSE
  fit <- withCallingHandlers(survival::coxph(form,data=d,ties="efron",x=TRUE,y=TRUE,model=TRUE),
    warning=function(w) {warned <<- TRUE; invokeRestart("muffleWarning")})
  beta <- stats::coef(fit); v <- stats::vcov(fit)
  if (warned || !identical(names(beta),terms) || any(!is.finite(beta)) ||
      any(!is.finite(v)) || qr(fit$x)$rank != length(terms))
    continuous_block("COX_FIT", "A required Cox model did not converge at full rank.")
  ph <- survival::cox.zph(fit,transform="rank")
  slopes <- vapply(seq_along(terms),function(j) {
    z <- ph$y[,j]; ok <- is.finite(z) & is.finite(ph$x)
    if (sum(ok)<3L) return(NA_real_)
    unname(stats::coef(stats::lm(z[ok]~ph$x[ok]))[2L])
  },numeric(1))
  names(slopes) <- terms
  list(beta=beta,variance=v,ph=ph$table,ph_trend=slopes,
       private_fit=fit,private_ph=ph)
}

continuous_pool <- function(fits, contrast) {
  if (all(contrast == 0)) return(list(log_hr=0,estimate=1,ci_low=1,ci_high=1,
    p_value=NA_real_,estimate_type="cause_specific_hazard_ratio",
    confidence_level=.95,m=length(fits),degrees_freedom=NA_real_,
    within_variance=0,between_variance=0,total_variance=0,
    missing_information_fraction=NA_real_,ph_rank_test=list(min=NA_real_)))
  b <- vapply(fits,function(f) sum(f$beta[names(contrast)]*contrast),numeric(1))
  u <- vapply(fits,function(f) unname(t(contrast)%*%f$variance[names(contrast),names(contrast),drop=FALSE]%*%contrast),numeric(1))
  m <- length(fits); q <- mean(b); within <- mean(u); between <- stats::var(b)
  total <- within+(1+1/m)*between
  if (!is.finite(total) || total <= 0) continuous_block("POOL", "Rubin variance is invalid.")
  ratio <- (1+1/m)*between/within
  df <- if (is.finite(ratio) && ratio>0) (m-1)*(1+1/ratio)^2 else Inf
  critical <- if (is.finite(df)) stats::qt(.975,df) else stats::qnorm(.975)
  list(log_hr=q,estimate=exp(q),ci_low=exp(q-critical*sqrt(total)),
       ci_high=exp(q+critical*sqrt(total)),p_value=if (is.finite(df))
         2*stats::pt(-abs(q/sqrt(total)),df) else 2*stats::pnorm(-abs(q/sqrt(total))),
       estimate_type="cause_specific_hazard_ratio",confidence_level=.95,m=m,
       degrees_freedom=if (is.finite(df)) df else NA_real_,
       within_variance=within,between_variance=between,total_variance=total,
       missing_information_fraction=(ratio+2/(df+3))/(ratio+1),
       ph_rank_test=list(min=NA_real_))
}

continuous_run_set <- function(data,a,s,knots,private,label) {
  imputed <- continuous_impute(data,a,s,knots,private,label)
  fitmany <- function(event,nonlinear=FALSE) lapply(imputed$datasets,continuous_cox_fit,
    a=a,s=s,event=event,nonlinear=nonlinear)
  death <- fitmany(a$event); discharge <- fitmany(a$competing_event)
  nonlinear <- fitmany(a$event,TRUE)
  contrast <- stats::setNames(s$exposure_unit,a$exposure)
  grid <- seq(unname(stats::quantile(data[[a$exposure]],.01)),
              unname(stats::quantile(data[[a$exposure]],.99)),length.out=50L)
  if (s$reference < min(grid) || s$reference > max(grid))
    continuous_block("RCS_REFERENCE", "Reference lacks central exposure support.")
  rcs <- lapply(grid,function(x) {
    delta <- c(x-s$reference,continuous_rcs(x,knots)-continuous_rcs(s$reference,knots))
    names(delta) <- c(a$exposure,"exposure_rcs_fixed")
    c(list(exposure=x),continuous_pool(nonlinear,delta))
  })
  cc <- data[stats::complete.cases(data[,unlist(s$physiology),drop=FALSE]),,drop=FALSE]
  ccfit <- continuous_cox_fit(cc,a,s,a$event)
  saveRDS(list(death=death,discharge=discharge,nonlinear=nonlinear,
               complete_case=ccfit),file.path(private,paste0(label,"-model-private.rds")))
  # A single complete-case fit uses its direct covariance, not fictitious MI.
  cc_beta <- sum(ccfit$beta[names(contrast)]*contrast)
  cc_var <- unname(t(contrast)%*%ccfit$variance[names(contrast),names(contrast),drop=FALSE]%*%contrast)
  cc_summary <- list(estimate=exp(cc_beta),ci_low=exp(cc_beta-1.96*sqrt(cc_var)),
                     ci_high=exp(cc_beta+1.96*sqrt(cc_var)),n=nrow(cc))
  diagnostic <- imputed$diagnostic
  diagnostic$model <- list(death_fitted=length(death),discharge_fitted=length(discharge),
    nonlinear_fitted=length(nonlinear),
    death_ph=lapply(death,`[[`,"ph"),discharge_ph=lapply(discharge,`[[`,"ph"),
    nonlinear_ph=lapply(nonlinear,`[[`,"ph"),
    death_ph_trend=lapply(death,`[[`,"ph_trend"),
    complete_case_ph=ccfit$ph,complete_case_ph_trend=ccfit$ph_trend)
  list(primary=continuous_pool(death,contrast),competing=continuous_pool(discharge,contrast),
       rcs=rcs,cc=cc_summary,imputed=imputed,diagnostic=diagnostic)
}

continuous_mnar <- function(core,a,s) {
  scenarios <- list(creatinine_up=c("creatinine",1.25),creatinine_down=c("creatinine",.8),
    lactate_up=c("lactate",1.25),lactate_down=c("lactate",.8),
    map_up=c("map",10),map_down=c("map",-10))
  lapply(names(scenarios),function(id) {
    key <- scenarios[[id]][1L]; shift <- as.numeric(scenarios[[id]][2L]); col <- s$physiology[[key]]
    missing <- core$imputed$missing[[key]]; bounds <- unlist(s$bounds[[key]])
    if (!any(missing)) return(list(id=id,status="NOT_APPLICABLE_NO_MISSING"))
    shifted <- lapply(core$imputed$datasets,function(d) {
      d[[col]][missing] <- if (key=="map") d[[col]][missing]+shift else d[[col]][missing]*shift
      d
    })
    if (any(vapply(shifted,function(d) any(d[[col]]<bounds[1L]|d[[col]]>bounds[2L]),logical(1))))
      return(list(id=id,status="UNSUPPORTED_RANGE"))
    fits <- lapply(shifted,continuous_cox_fit,a=a,s=s,event=a$event)
    list(id=id,status="COMPLETE",estimate=continuous_pool(fits,stats::setNames(s$exposure_unit,a$exposure)))
  })
}

continuous_single_level <- function(data,a,s,covariates) {
  level <- a
  level$covariates <- as.list(covariates)
  fit <- continuous_cox_fit(data,level,s,a$event)
  beta <- unname(fit$beta[[a$exposure]])*s$exposure_unit
  variance <- unname(fit$variance[a$exposure,a$exposure])*s$exposure_unit^2
  list(estimate=exp(beta),ci_low=exp(beta-1.96*sqrt(variance)),
       ci_high=exp(beta+1.96*sqrt(variance)),n=nrow(data),
       exposure_unit=s$exposure_unit)
}

continuous_overall_aj <- function(data,a,time_point) {
  status <- factor(ifelse(data[[a$event]]==1L,1L,2L),levels=0:2,
                   labels=c("censor","death","live_discharge"))
  fit <- survival::survfit(survival::Surv(data[[a$time]],status)~1)
  at <- summary(fit,times=time_point,extend=TRUE)
  list(list(group="overall",time=time_point,
            death_cumulative_incidence=unname(at$pstate[1L,2L]),
            live_discharge_cumulative_incidence=unname(at$pstate[1L,3L])))
}

run_continuous_cause_specific_cox <- function(task,data,output_dir) {
  result <- new_analysis_result(task,status="RUNNING")
  tryCatch({
    a <- task$analysis; s <- a$continuous_v4
    continuous_check(task,data)
    result$diagnostics$readiness <- check_analysis_readiness(task,data)
    if (identical(result$diagnostics$readiness$status,"BLOCK"))
      continuous_block("READINESS","Shared readiness checks failed.")
    knots <- if (is.null(s$fixed_knots))
      unname(stats::quantile(data[[a$exposure]],c(.1,.5,.9))) else
      as.numeric(unlist(s$fixed_knots,use.names=FALSE))
    if (length(knots)!=3L || any(!is.finite(knots)))
      continuous_block("KNOTS","Three finite fixed main-cohort exposure knots are required.")
    if (any(diff(knots)<=0)) continuous_block("KNOTS","Exposure quantile knots collide.")
    private <- normalizePath(s$private_dir,mustWork=FALSE)
    main <- continuous_run_set(data,a,s,knots,private,"main")
    mnar <- continuous_mnar(main,a,s)
    unadjusted <- continuous_single_level(data,a,s,character())
    case_mix <- continuous_single_level(data,a,s,unlist(a$covariates)[1:4])
    aj <- continuous_overall_aj(data,a,a$cumulative_incidence_time %||% 72)
    groups <- list()
    for (group in s$subgroups %||% list()) {
      if (is.null(group$id) || is.null(group$column) ||
          !group$column %in% names(data) || !all(data[[group$column]] %in% 0:1))
        continuous_block("SUBGROUP","Subgroup requires id and complete binary selection column.")
      selected <- data[data[[group$column]]==1L,,drop=FALSE]
      deaths <- sum(selected[[a$event]]==1L); live <- sum(selected[[a$competing_event]]==1L)
      if (deaths<120L || live<30L) {
        groups[[group$id]] <- list(status="DESCRIPTIVE_ONLY",support="BELOW_120_DEATH_OR_30_DISCHARGE")
      } else {
        sub <- continuous_run_set(selected,a,s,knots,private,paste0("group-",group$id))
        groups[[group$id]] <- list(status="COMPLETE",primary=sub$primary,
                                   diagnostics_status=sub$diagnostic$status)
      }
    }
    result$status <- "COMPLETE"
    result$counts <- list(analysis_n=nrow(data),primary_events=sum(data[[a$event]]==1L),
                          competing_events=sum(data[[a$competing_event]]==1L))
    result$estimates <- list(primary_event=main$primary,competing_event=main$competing,
      rcs=main$rcs,complete_case=main$cc,mnar=mnar,subgroups=groups,
      unadjusted=unadjusted,case_mix=case_mix,cumulative_incidence=aj)
    result$estimates$primary_event$label <- "Death per 0.5 exposure unit"
    result$estimates$competing_event$label <- "Live discharge per 0.5 exposure unit"
    result$diagnostics$multiple_imputation <- main$diagnostic
    result$diagnostics$knots <- as.list(knots)
    result$diagnostics$runtime <- list(R=as.character(getRversion()),
      mice=as.character(utils::packageVersion("mice")),
      survival=as.character(utils::packageVersion("survival")))
    result
  },continuous_cox_block=function(e) {
    result$status <- "BLOCKED"
    result$warnings[[1L]] <- list(code=e$code,severity="BLOCK",message=e$message)
    result
  },error=function(e) {
    result$status <- "BLOCKED"
    result$warnings[[1L]] <- list(code="CONTINUOUS_COX_RUNTIME",severity="BLOCK",
      message="Continuous Cox execution failed; inspect analysis-private diagnostics.")
    result
  })
}
