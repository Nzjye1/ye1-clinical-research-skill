# Single ordinary-growth numerical owner. nlme::lme is the only optimizer.
# No latent classes, random-effect clustering, adaptive model fallback, or refit
# on external data. This file is invoked by the module-local Python transport.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=3L) stop("EXPECTED_REQUEST_RESPONSE_RUNTIME")
runtime <- jsonlite::fromJSON(args[[3]], simplifyVector=FALSE)
.libPaths(c(unlist(runtime$r_libraries, use.names=FALSE), .libPaths()))
request <- jsonlite::fromJSON(args[[1]], simplifyVector=FALSE)
write_result <- function(value) jsonlite::write_json(value, args[[2]], auto_unbox=TRUE,
    pretty=TRUE, digits=17L, null="null", na="null", dataframe="rows")
block <- function(code) stop(structure(list(message=code, call=NULL),class=c("ll_blocked","error","condition")))
assert <- function(value, code) if(!isTRUE(value)) block(code)
rows <- function(x) lapply(seq_len(nrow(x)),function(i)as.list(x[i,,drop=FALSE]))
as_matrix <- function(x) do.call(rbind,lapply(x,function(z)as.numeric(unlist(z,use.names=FALSE))))

design <- function(data, spec) {
  fixed <- c("tt", if(spec$degree==2L)"tt2", paste0("x",seq_along(spec$covariates)))
  if(!length(spec$covariates)) fixed <- fixed[!grepl("^x",fixed)]
  stats::reformulate(fixed, response="yy")
}

grid_predictions <- function(beta, variance, df, spec, time_range, reference) {
  times <- seq(time_range[[1]],time_range[[2]],length.out=61L)
  grid <- data.frame(tt=(times-spec$time$origin)/spec$time$scale)
  if(spec$degree==2L) grid$tt2 <- grid$tt^2
  for(i in seq_along(reference)) grid[[paste0("x",i)]] <- reference[[i]]
  X <- stats::model.matrix(stats::delete.response(stats::terms(design(grid,spec))),grid)
  X <- X[,names(beta),drop=FALSE]
  fit <- as.vector(X %*% beta)
  se <- sqrt(rowSums((X %*% variance)*X))
  crit <- stats::qt(.975,df=min(df))
  rows(data.frame(time=times, estimate=fit, se=se, lower=fit-crit*se, upper=fit+crit*se,
                  ci_method="pointwise_t_min_fixed_term_df", scope="population_mean_at_training_covariate_means"))
}

calculate <- function() {
  spec <- request$spec
  # fromJSON(simplifyVector=FALSE) gives row records, handled explicitly.
  data <- do.call(rbind,lapply(request$data,as.data.frame,stringsAsFactors=FALSE))
  assert(nrow(data)>0,"NO_ANALYZABLE_ROWS")
  data$tt <- (data$time-spec$time$origin)/spec$time$scale
  if(spec$degree==2L) data$tt2 <- data$tt^2
  if(identical(request$operation,"predict")) {
    model <- request$model
    beta <- unlist(model$beta)
    variance <- as_matrix(model$fixed_covariance)
    dimnames(variance) <- list(names(beta),names(beta))
    df <- unlist(model$df)
    X <- stats::model.matrix(stats::delete.response(stats::terms(design(data,spec))),data)
    X <- X[,names(beta),drop=FALSE]
    prediction <- as.vector(X %*% beta)
    se <- sqrt(rowSums((X %*% variance)*X))
    crit <- stats::qt(.975,df=min(df))
    assert(all(is.finite(c(prediction,se))),"NONFINITE_FROZEN_PREDICTION")
    return(list(ok=TRUE, record=list(coefficients=model$coefficients,
      trajectories=grid_predictions(beta,variance,df,spec,model$time_range,model$reference),
      diagnostics=list(n_engine_fits=0L,model_refitted=FALSE,transform_refitted=FALSE,
        prediction_kind="population_fixed_mean_not_subject_forecast")),
      model=model, private=rows(data.frame(row_index=data$row_index,prediction=prediction,
        lower=prediction-crit*se,upper=prediction+crit*se))))
  }
  data$id <- factor(data$id)
  fixed <- design(data,spec)
  X <- stats::model.matrix(fixed,data)
  assert(qr(X)$rank==ncol(X),"FIXED_DESIGN_RANK_DEFICIENT")
  random <- if(identical(spec$random,"intercept_slope")) ~1+tt|id else ~1|id
  set.seed(spec$seed)
  warnings_seen <- character()
  fit <- withCallingHandlers(nlme::lme(fixed,random=random,data=data,method="ML",na.action=na.fail,
     control=nlme::lmeControl(maxIter=spec$max_iter,msMaxIter=spec$max_iter,
       msMaxEval=spec$max_iter*2L,niterEM=0L,returnObject=FALSE,opt="nlminb")),
     warning=function(w) {warnings_seen <<- c(warnings_seen,conditionMessage(w));invokeRestart("muffleWarning")})
  assert(!length(warnings_seen),"GROWTH_ENGINE_WARNING")
  assert(is.matrix(fit$apVar) && all(is.finite(fit$apVar)) &&
         min(eigen(fit$apVar,symmetric=TRUE,only.values=TRUE)$values)>0,"VARIANCE_HESSIAN_INVALID")
  beta <- nlme::fixef(fit)
  variance <- as.matrix(stats::vcov(fit))
  random_cov <- as.matrix(nlme::getVarCov(fit,type="random.effects"))
  eig <- eigen(random_cov,symmetric=TRUE,only.values=TRUE)$values
  assert(all(is.finite(c(beta,variance,random_cov,fit$sigma))) && fit$sigma^2>1e-10,
         "NONFINITE_OR_ZERO_VARIANCE")
  assert(min(eig)>1e-6*max(c(eig,fit$sigma^2)),"SINGULAR_RANDOM_EFFECTS_REJECTED")
  tab <- summary(fit)$tTable
  df <- as.numeric(tab[,"DF"])
  assert(all(df>0),"FIXED_DF_INVALID")
  coeff <- data.frame(term=names(beta),estimate=as.numeric(beta),se=sqrt(diag(variance)),df=df)
  crit <- stats::qt(.975,df)
  coeff$lower <- coeff$estimate-crit*coeff$se
  coeff$upper <- coeff$estimate+crit*coeff$se
  coeff$p_value <- 2*stats::pt(abs(coeff$estimate/coeff$se),df,lower.tail=FALSE)
  coeff$ci_method <- "nlme_fixed_t"
  coeff$scope <- "prespecified_population_growth_ML"
  reference <- lapply(seq_along(spec$covariates),function(i)mean(data[[paste0("x",i)]]))
  time_range <- as.list(range(data$time))
  model <- list(beta=as.list(beta),fixed_covariance=lapply(seq_len(nrow(variance)),function(i)as.list(unname(variance[i,]))),
    df=as.list(df),random_covariance=lapply(seq_len(nrow(random_cov)),function(i)as.list(unname(random_cov[i,]))),
    residual_variance=fit$sigma^2,coefficients=rows(coeff),reference=reference,time_range=time_range)
  residual <- stats::residuals(fit,type="normalized")
  residual_summary <- list(mean=mean(residual),sd=stats::sd(residual),max_abs=max(abs(residual)),
    assumption_verified=FALSE,scope="descriptive_normalized_conditional_residuals")
  list(ok=TRUE,record=list(coefficients=rows(coeff),
    trajectories=grid_predictions(beta,variance,df,spec,time_range,reference),
    fit_statistics=list(log_likelihood=as.numeric(stats::logLik(fit)),AIC=stats::AIC(fit),
      BIC=stats::BIC(fit),estimation="ML",residual_variance=fit$sigma^2),
    diagnostics=list(n_engine_fits=1L,model_refitted=TRUE,transform_refitted=FALSE,
      singular=FALSE,variance_hessian_positive_definite=TRUE,residuals=residual_summary,
      prediction_kind="population_fixed_mean_not_subject_forecast")),model=model,private=list())
}

out <- tryCatch(calculate(),ll_blocked=function(e)list(ok=FALSE,reason_code=conditionMessage(e)),
  error=function(e)list(ok=FALSE,reason_code=if(grepl("convergence|iteration limit|evaluation limit",conditionMessage(e),ignore.case=TRUE))
    "GROWTH_NOT_CONVERGED" else "GROWTH_ENGINE_FAILURE"))
write_result(out)
