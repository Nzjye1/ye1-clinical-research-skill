# Config-driven experimental analysis API. Its summary is unsuppressed and
# remains analysis-private with the fitted models and completed rows.
# It is not registered as a formal task plugin while method validation remains
# incomplete.
tvcr_analyze_experimental <- function(data, config) {
  required <- c("time", "status", "causes", "variables", "time_varying",
                "basis", "min_events", "support", "contrasts", "imputation")
  if (!is.list(config) || !setequal(names(config), required) ||
      !is.list(config$support) ||
      !setequal(names(config$support), c("event_quantiles", "min_at_risk")) ||
      length(config$support$event_quantiles) != 2L ||
      any(!is.finite(config$support$event_quantiles)) ||
      config$support$event_quantiles[[1L]] < 0 ||
      config$support$event_quantiles[[2L]] > 1 ||
      config$support$event_quantiles[[1L]] >=
        config$support$event_quantiles[[2L]] ||
      !is.numeric(config$support$min_at_risk) ||
      config$support$min_at_risk < 1 ||
      !length(config$contrasts))
    stop("Invalid competing-risk TVE analysis configuration.", call. = FALSE)
  if (!is.list(config$imputation) ||
      !setequal(names(config$imputation),
                c("missing_variables", "bounds", "m", "iterations", "seed")))
    stop("Invalid competing-risk TVE imputation configuration.", call. = FALSE)
  incomplete <- config$imputation$missing_variables
  if (length(incomplete)) {
    imputed <- tvcr_impute_continuous(
      data, config$time, config$status, config$causes, config$variables,
      config$time_varying, incomplete, config$basis,
      config$imputation$bounds, config$imputation$m,
      config$imputation$iterations, config$imputation$seed,
      min_events = config$min_events)
    datasets <- imputed$datasets
  } else {
    imputed <- NULL
    datasets <- list(data)
  }
  fitted <- lapply(datasets, function(d) tvcr_fit_causes(
    d, config$time, config$status, config$causes, config$variables,
    config$time_varying, config$basis, min_events = config$min_events))
  first_models <- fitted[[1L]]
  results <- lapply(config$contrasts, function(request) {
    single <- is.list(request) &&
      setequal(names(request), c("cause", "variable", "unit", "times"))
    multiple <- is.list(request) &&
      setequal(names(request), c("cause", "deltas", "times"))
    if ((!single && !multiple) ||
        length(request$cause) != 1L ||
        !as.character(request$cause) %in% names(first_models) ||
        (single && (length(request$variable) != 1L ||
                    !request$variable %in% config$variables)) ||
        (multiple && (!is.numeric(request$deltas) ||
                      is.null(names(request$deltas)) ||
                      !all(names(request$deltas) %in% config$variables))) ||
        !length(request$times) || any(!is.finite(request$times)) ||
        any(request$times < 0))
      stop("Invalid cause-specific contrast request.", call. = FALSE)
    cause <- as.character(request$cause)
    event_times <- first_models[[cause]]$event_times
    support <- stats::quantile(event_times,
                               config$support$event_quantiles, names = FALSE)
    estimates <- lapply(request$times, function(at) {
      at_risk <- sum(data[[config$time]] >= at)
      if (at < support[[1L]] || at > support[[2L]] ||
          at_risk < config$support$min_at_risk)
        return(list(time = at, at_risk = at_risk,
                    status = "OUTSIDE_SUPPORTED_TIME"))
      models <- lapply(fitted, `[[`, cause)
      contrasts <- if (single)
        lapply(models, tvcr_contrast, variable = request$variable,
               time = at, unit = request$unit) else
        lapply(models, tvcr_contrast_many, deltas = request$deltas,
               time = at)
      if (length(models) > 1L) {
        estimate <- tvcr_pool_contrast(models, contrasts)
      } else {
        contrast <- contrasts[[1L]]
        beta <- sum(models[[1L]]$beta[names(contrast)] * contrast)
        variance <- as.numeric(t(contrast) %*%
          models[[1L]]$variance[names(contrast), names(contrast), drop = FALSE] %*%
          contrast)
        if (!is.finite(variance) || variance <= 0)
          stop("Invalid single-model contrast variance.", call. = FALSE)
        estimate <- list(log_hr = beta, estimate = exp(beta),
          ci_low = exp(beta - stats::qnorm(.975) * sqrt(variance)),
          ci_high = exp(beta + stats::qnorm(.975) * sqrt(variance)),
          m = 1L, total_variance = variance)
      }
      estimate_status <- if (!is.null(imputed) &&
                             !isTRUE(imputed$chain_diagnostics$stable))
        "EXPERIMENTAL_CHAIN_UNSTABLE" else "EXPERIMENTAL_ESTIMATE"
      c(list(time = at, at_risk = at_risk, status = estimate_status),
        estimate)
    })
    list(cause = cause,
         contrast = if (single) list(variable = request$variable,
                                    unit = request$unit) else
                    list(deltas = request$deltas),
         support_event_times = unname(support), estimates = estimates)
  })
  list(status = "EXPERIMENTAL_METHOD_UNVALIDATED",
       disclosure_status = "PRIVATE_UNSUPPRESSED",
       internal_summary = list(counts = list(n = nrow(data),
         events = stats::setNames(lapply(config$causes, function(cause)
           sum(data[[config$status]] == cause)), as.character(config$causes))),
         contrasts = results,
         imputation = if (is.null(imputed))
           list(status = "NOT_NEEDED") else
           list(status = imputed$method,
                chains_stable = imputed$chain_diagnostics$stable,
                chains = imputed$chain_diagnostics$chains,
                iterations = imputed$chain_diagnostics$iterations)),
       private = list(imputation = imputed, fitted = fitted))
}
