# Experimental substantive-model-compatible FCS for continuous baseline
# covariates. Inputs must already be on their declared analysis scales. This
# method cannot be used for formal results until synthetic calibration passes.
tvcr_draw_conditional_normal <- function(data, variable, observed, predictors) {
  design <- cbind(1, as.matrix(data[predictors]))
  storage.mode(design) <- "double"
  response <- data[[variable]]
  fit <- stats::lm.fit(design[observed, , drop = FALSE], response[observed])
  residual_df <- sum(observed) - ncol(design)
  if (fit$rank != ncol(design) || residual_df < 3L ||
      !is.finite(sum(fit$residuals^2)) || sum(fit$residuals^2) <= 0)
    stop("Conditional covariate model lacks full-rank residual support.",
         call. = FALSE)
  residual_variance <- sum(fit$residuals^2) / stats::rchisq(1L, residual_df)
  covariance <- residual_variance *
    solve(crossprod(design[observed, , drop = FALSE]))
  beta <- as.numeric(fit$coefficients +
    t(chol(covariance)) %*% stats::rnorm(ncol(design)))
  list(mean = as.numeric(design %*% beta), sd = sqrt(residual_variance))
}

tvcr_draw_bounded_normal <- function(mean, sd, bounds, limit = 1000L) {
  if (length(bounds) != 2L || bounds[1L] >= bounds[2L] ||
      !is.finite(mean) || !is.finite(sd) || sd <= 0)
    stop("Invalid bounded-normal proposal parameters.", call. = FALSE)
  for (attempt in seq_len(limit)) {
    value <- stats::rnorm(1L, mean, sd)
    if (is.finite(value) && value >= bounds[1L] && value <= bounds[2L])
      return(value)
  }
  stop("Bounded-normal proposal limit exceeded.", call. = FALSE)
}

tvcr_chain_diagnostics <- function(diagnostics, variables, threshold = 1.1,
                                   min_acceptance = 0.05,
                                   sd_not_applicable = character()) {
  if (!is.numeric(threshold) || length(threshold) != 1L ||
      !is.finite(threshold) || threshold <= 1 ||
      !is.numeric(min_acceptance) || length(min_acceptance) != 1L ||
      !is.finite(min_acceptance) || min_acceptance < 0 ||
      min_acceptance > 1 ||
      !all(sd_not_applicable %in% variables))
    stop("Invalid chain diagnostic thresholds.", call. = FALSE)
  m <- length(diagnostics)
  iterations <- nrow(diagnostics[[1L]][[variables[[1L]]]])
  result <- list()
  for (variable in variables) {
    means <- sds <- acceptance <- matrix(NA_real_, iterations, m)
    for (chain in seq_len(m)) {
      record <- diagnostics[[chain]][[variable]]
      means[, chain] <- record[, "mean"]
      sds[, chain] <- record[, "sd"]
      acceptance[, chain] <- record[, "acceptance"]
    }
    rhat_mean <- rhat_sd <- rep(NA_real_, iterations)
    if (iterations >= 4L) {
      for (i in 4:iterations) {
        rhat_mean[[i]] <- continuous_split_rhat(means[seq_len(i), , drop = FALSE])
        if (all(is.finite(sds[seq_len(i), , drop = FALSE])))
          rhat_sd[[i]] <- continuous_split_rhat(sds[seq_len(i), , drop = FALSE])
      }
    }
    tail_mean <- utils::tail(rhat_mean, 5L)
    tail_sd <- utils::tail(rhat_sd, 5L)
    sd_applicable <- !variable %in% sd_not_applicable
    sd_ok <- !sd_applicable ||
      all(is.finite(tail_sd) & tail_sd <= threshold)
    minimum_acceptance <- min(colMeans(acceptance))
    acceptance_ok <- is.finite(minimum_acceptance) &&
      minimum_acceptance >= min_acceptance
    stable <- iterations >= 8L && acceptance_ok &&
      all(is.finite(tail_mean) & tail_mean <= threshold) &&
      sd_ok
    result[[variable]] <- list(
      mean_rhat = utils::tail(rhat_mean, 1L),
      sd_rhat = if (sd_applicable) utils::tail(rhat_sd, 1L) else NA_real_,
      sd_status = if (sd_applicable) "ASSESSED" else "STRUCTURALLY_UNDEFINED_N1",
      mean_acceptance = mean(acceptance),
      min_chain_acceptance = minimum_acceptance,
      acceptance_ok = acceptance_ok,
      stable = stable,
      failure_reasons = c(if (iterations < 8L) "INSUFFICIENT_ITERATIONS",
                          if (!acceptance_ok) "LOW_ACCEPTANCE",
                          if (!all(is.finite(tail_mean) & tail_mean <= threshold))
                            "MEAN_RHAT_FAILED",
                          if (!sd_ok)
                            "SD_RHAT_FAILED"))
  }
  list(variables = result,
       stable = all(vapply(result, `[[`, logical(1), "stable")),
       iterations = iterations, chains = m, threshold = threshold,
       min_acceptance = min_acceptance)
}

tvcr_impute_continuous <- function(data, time, status, causes, variables,
                                   time_varying, missing_variables, basis,
                                   bounds, m, iterations, seed,
                                   min_events = 11L) {
  if (!is.data.frame(data) || !length(missing_variables) ||
      anyDuplicated(missing_variables) ||
      !all(missing_variables %in% variables) ||
      !all(variables %in% names(data)) ||
      !all(c(time, status) %in% names(data)) ||
      anyNA(data[, c(time, status, setdiff(variables, missing_variables)),
                  drop = FALSE]) ||
      !all(vapply(data[variables], is.numeric, logical(1))) ||
      !identical(sort(names(bounds)), sort(missing_variables)) ||
      length(m) != 1L || !is.numeric(m) || !is.finite(m) ||
      m < 2 || m != as.integer(m) ||
      length(iterations) != 1L || !is.numeric(iterations) ||
      !is.finite(iterations) || iterations < 2 ||
      iterations != as.integer(iterations) ||
      length(seed) != 1L || !is.numeric(seed) || !is.finite(seed))
    stop("Invalid continuous imputation configuration.", call. = FALSE)
  tvcr_basis(0, basis)
  missing <- lapply(data[missing_variables], is.na)
  for (variable in missing_variables) {
    if (!any(missing[[variable]]))
      stop("Declared incomplete covariate has no missing values.", call. = FALSE)
    observed <- data[[variable]][!missing[[variable]]]
    limits <- bounds[[variable]]
    if (length(limits) != 2L || limits[1L] >= limits[2L] ||
        any(!is.finite(observed)) ||
        any(observed < limits[1L] | observed > limits[2L]) ||
        length(observed) < length(variables) + 4L)
      stop("Observed covariate values lack bounded support.", call. = FALSE)
  }
  set.seed(as.integer(seed))
  completed <- vector("list", as.integer(m))
  diagnostics <- list()
  for (imputation in seq_len(m)) {
    current <- data
    for (variable in missing_variables) {
      indices <- which(missing[[variable]])
      if (length(indices))
        current[[variable]][indices] <- sample(data[[variable]][!missing[[variable]]],
                                               length(indices), replace = TRUE)
    }
    per_variable <- lapply(missing_variables, function(x) {
      matrix(NA_real_, nrow = iterations, ncol = 3L,
             dimnames = list(NULL, c("mean", "sd", "acceptance")))
    })
    names(per_variable) <- missing_variables
    for (iteration in seq_len(iterations)) {
      fitted <- tryCatch(
        tvcr_fit_causes(current, time, status, causes, variables,
                        time_varying, basis, min_events = min_events),
        error = function(e) stop(sprintf(
          "Imputation %d sweep %d: %s", imputation, iteration,
          conditionMessage(e)), call. = FALSE))
      for (cause in names(fitted)) {
        drawn <- MASS::mvrnorm(1L, mu = fitted[[cause]]$beta,
                              Sigma = fitted[[cause]]$variance)
        names(drawn) <- names(fitted[[cause]]$beta)
        fitted[[cause]]$beta <- drawn
      }
      baselines <- lapply(names(fitted), function(cause) {
        event_data <- current
        event_data$.tvcr_event <- as.integer(current[[status]] ==
          causes[[match(cause, as.character(causes))]])
        tvcr_baseline_increments(fitted[[cause]], event_data,
                                 time, ".tvcr_event")
      })
      names(baselines) <- names(fitted)
      for (variable in missing_variables) {
        indices <- which(missing[[variable]])
        if (!length(indices)) next
        conditional <- tvcr_draw_conditional_normal(
          current, variable, !missing[[variable]],
          setdiff(variables, variable))
        accepted <- 0L
        for (i in indices) {
          proposal <- tvcr_draw_bounded_normal(
            conditional$mean[[i]], conditional$sd, bounds[[variable]])
          log_ratio <- tvcr_log_outcome_ratio(
            fitted, baselines, current[i, , drop = FALSE], time,
            status, variable, proposal)
          if (log(stats::runif(1L)) < log_ratio) {
            current[[variable]][[i]] <- proposal
            accepted <- accepted + 1L
          }
        }
        values <- current[[variable]][indices]
        per_variable[[variable]][iteration, ] <- c(
          mean(values), if (length(values) > 1L) stats::sd(values) else NA_real_,
          accepted / length(indices))
      }
    }
    for (variable in missing_variables) {
      if (any(current[[variable]][!missing[[variable]]] !=
              data[[variable]][!missing[[variable]]]))
        stop("Observed covariate value changed during imputation.", call. = FALSE)
    }
    completed[[imputation]] <- current
    diagnostics[[paste0("imputation_", imputation)]] <- per_variable
  }
  list(datasets = completed, diagnostics = diagnostics,
       chain_diagnostics = tvcr_chain_diagnostics(
         diagnostics, missing_variables,
         sd_not_applicable = missing_variables[vapply(missing,
           function(x) sum(x) == 1L, logical(1))]),
       method = "EXPERIMENTAL_SMC_FCS_COMPETING_TVE_NORMAL",
       parameters = list(m = as.integer(m), iterations = as.integer(iterations),
                         seed = as.integer(seed), basis = basis,
                         missing_variables = missing_variables,
                         bounds = bounds))
}
