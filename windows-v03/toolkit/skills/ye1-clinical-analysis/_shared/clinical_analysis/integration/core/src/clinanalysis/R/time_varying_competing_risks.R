# Generic cause-specific Cox models with one declared time basis. The substantive
# model is independent of cohort, exposure, event names, and display time points.
tvcr_basis <- function(time, specification) {
  if (!is.list(specification) ||
      !identical(sort(names(specification)), c("scale", "type")) ||
      length(specification$scale) != 1L ||
      !is.numeric(specification$scale) ||
      !is.finite(specification$scale) || specification$scale <= 0 ||
      length(specification$type) != 1L ||
      !specification$type %in% c("log1p", "linear"))
    stop("Invalid time-basis specification.", call. = FALSE)
  if (any(!is.finite(time)) || any(time < 0))
    stop("Time basis requires finite nonnegative time.", call. = FALSE)
  scaled <- time / specification$scale
  if (identical(specification$type, "log1p")) log1p(scaled) else scaled
}

tvcr_fit_one <- function(data, time, event, variables, time_varying,
                         basis, ties = "efron", min_events = 11L) {
  required <- c(time, event, variables)
  if (!is.data.frame(data) || !length(variables) ||
      anyDuplicated(required) || any(!required %in% names(data)) ||
      any(make.names(required) != required) ||
      any(!time_varying %in% variables) || anyDuplicated(time_varying) ||
      !length(time_varying) ||
      anyNA(data[, required, drop = FALSE]) ||
      !all(vapply(data[variables], is.numeric, logical(1))) ||
      any(!is.finite(as.matrix(data[variables]))) ||
      !is.numeric(data[[time]]) ||
      any(!is.finite(data[[time]]) | data[[time]] <= 0) ||
      !all(data[[event]] %in% 0:1) ||
      length(min_events) != 1L || !is.numeric(min_events) ||
      !is.finite(min_events) || min_events < 1 ||
      sum(data[[event]]) < min_events ||
      !identical(ties, "efron"))
    stop("Invalid time-varying cause-specific Cox input.", call. = FALSE)
  tvcr_basis(0, basis)
  terms <- c(variables, paste0("tt(", time_varying, ")"))
  formula <- stats::reformulate(terms,
    response = sprintf("survival::Surv(%s,%s)", time, event))
  warned <- FALSE
  fit <- withCallingHandlers(
    survival::coxph(formula, data = data, ties = ties,
      tt = function(x, t, ...) x * tvcr_basis(t, basis), x = TRUE, y = TRUE),
    warning = function(w) { warned <<- TRUE; invokeRestart("muffleWarning") })
  beta <- stats::coef(fit)
  variance <- stats::vcov(fit)
  if (warned || !identical(names(beta), terms) ||
      any(!is.finite(beta)) || any(!is.finite(variance)) ||
      qr(fit$x)$rank != length(terms))
    stop("Time-varying cause-specific Cox fit lacks finite full-rank estimates.",
         call. = FALSE)
  list(beta = beta, variance = variance, fit = fit,
       event_times = sort(data[[time]][data[[event]] == 1L]),
       basis = basis, variables = variables, time_varying = time_varying,
       ties = ties)
}

tvcr_fit_causes <- function(data, time, status, causes, variables,
                            time_varying, basis, min_events = 11L) {
  if (!status %in% names(data) || anyNA(data[[status]]) ||
      length(causes) < 2L || anyDuplicated(causes) ||
      anyNA(causes) || any(causes == 0) ||
      !all(data[[status]] %in% c(0, causes)))
    stop("Invalid competing-event status or cause set.", call. = FALSE)
  event_name <- ".tvcr_event"
  if (event_name %in% names(data))
    stop("Reserved competing-event column already exists.", call. = FALSE)
  output <- vector("list", length(causes))
  names(output) <- as.character(causes)
  for (i in seq_along(causes)) {
    d <- data
    d[[event_name]] <- as.integer(d[[status]] == causes[[i]])
    output[[i]] <- tvcr_fit_one(d, time, event_name, variables,
                               time_varying, basis, min_events = min_events)
  }
  output
}

tvcr_contrast <- function(model, variable, time, unit = 1) {
  if (length(time) != 1L || !is.numeric(time) ||
      !is.finite(time) || time < 0 ||
      length(unit) != 1L || !is.numeric(unit) ||
      !is.finite(unit) || unit <= 0 ||
      !variable %in% model$variables)
    stop("Invalid time-varying model contrast.", call. = FALSE)
  terms <- variable
  values <- unit
  if (variable %in% model$time_varying) {
    terms <- c(terms, paste0("tt(", variable, ")"))
    values <- c(values, unit * tvcr_basis(time, model$basis))
  }
  if (!all(terms %in% names(model$beta)))
    stop("Contrast terms absent from model.", call. = FALSE)
  stats::setNames(values, terms)
}

tvcr_contrast_many <- function(model, deltas, time) {
  if (!is.numeric(deltas) || !length(deltas) ||
      is.null(names(deltas)) || anyDuplicated(names(deltas)) ||
      any(!is.finite(deltas)) ||
      !all(names(deltas) %in% model$variables))
    stop("Invalid multivariable time contrast.", call. = FALSE)
  pieces <- lapply(names(deltas), function(variable) {
    tvcr_contrast(model, variable, time, unit = 1) * deltas[[variable]]
  })
  unlist(pieces, use.names = TRUE)
}

tvcr_pool_contrast <- function(models, contrasts, confidence_level = .95) {
  m <- length(models)
  if (m < 2L || length(contrasts) != m ||
      !is.numeric(confidence_level) || length(confidence_level) != 1L ||
      !is.finite(confidence_level) || confidence_level <= 0 ||
      confidence_level >= 1)
    stop("Invalid multiple-imputation contrast inputs.", call. = FALSE)
  estimates <- variances <- numeric(m)
  for (i in seq_len(m)) {
    contrast <- contrasts[[i]]
    if (!length(contrast) || !all(names(contrast) %in% names(models[[i]]$beta)) ||
        any(!is.finite(contrast)))
      stop("Contrast does not match fitted model.", call. = FALSE)
    estimates[i] <- sum(models[[i]]$beta[names(contrast)] * contrast)
    variances[i] <- as.numeric(t(contrast) %*%
      models[[i]]$variance[names(contrast), names(contrast), drop = FALSE] %*%
      contrast)
  }
  within <- mean(variances)
  between <- stats::var(estimates)
  total <- within + (1 + 1 / m) * between
  if (!is.finite(total) || total <= 0 || !is.finite(within) || within <= 0)
    stop("Invalid pooled variance.", call. = FALSE)
  relative <- (1 + 1 / m) * between / within
  degrees_freedom <- if (relative > 0)
    (m - 1) * (1 + 1 / relative)^2 else Inf
  critical <- if (is.finite(degrees_freedom))
    stats::qt((1 + confidence_level) / 2, degrees_freedom) else
    stats::qnorm((1 + confidence_level) / 2)
  log_hr <- mean(estimates)
  se <- sqrt(total)
  list(log_hr = log_hr, estimate = exp(log_hr),
       ci_low = exp(log_hr - critical * se),
       ci_high = exp(log_hr + critical * se),
       p_value = if (is.finite(degrees_freedom))
         2 * stats::pt(-abs(log_hr / se), degrees_freedom) else
         2 * stats::pnorm(-abs(log_hr / se)),
       within_variance = within, between_variance = between,
       total_variance = total, degrees_freedom = degrees_freedom,
       confidence_level = confidence_level, m = m)
}

# Efron baseline increments are reconstructed because survival::basehaz does
# not support coxph fits with tt() terms. Each risk score uses the event time,
# not the subject's own follow-up time.
tvcr_baseline_increments <- function(model, data, time, event) {
  observed_times <- sort(unique(data[[time]][data[[event]] == 1L]))
  if (!length(observed_times))
    stop("Cause has no event times.", call. = FALSE)
  beta <- model$beta
  ordinary <- model$variables
  changing <- model$time_varying
  fixed_score <- as.numeric(as.matrix(data[ordinary]) %*% beta[ordinary])
  changing_score <- as.numeric(as.matrix(data[changing]) %*%
                                 beta[paste0("tt(", changing, ")")])
  increments <- numeric(length(observed_times))
  for (i in seq_along(observed_times)) {
    at <- observed_times[[i]]
    risk <- data[[time]] >= at
    events <- data[[event]] == 1L & data[[time]] == at
    count <- sum(events)
    eta <- fixed_score[risk] +
      tvcr_basis(at, model$basis) * changing_score[risk]
    offset <- max(eta)
    scores <- exp(eta - offset)
    event_scores <- scores[events[risk]]
    risk_sum <- sum(scores)
    event_sum <- sum(event_scores)
    denominators <- risk_sum - (seq_len(count) - 1) * event_sum / count
    if (any(!is.finite(denominators) | denominators <= 0))
      stop("Invalid Efron risk-set denominator.", call. = FALSE)
    increments[i] <- exp(-offset) * sum(1 / denominators)
  }
  if (any(!is.finite(increments) | increments <= 0))
    stop("Invalid cause-specific baseline increments.", call. = FALSE)
  data.frame(time = observed_times, increment = increments)
}

# Log substantive-likelihood ratio for changing one baseline covariate of one
# person, conditional on fitted cause-specific coefficients and baseline hazards.
# The event-specific baseline factor cancels from this ratio.
tvcr_log_outcome_ratio <- function(models, baselines, row, time, status,
                                   variable, proposed) {
  if (!is.data.frame(row) || nrow(row) != 1L ||
      !variable %in% names(row) ||
      !is.finite(row[[variable]]) ||
      !is.numeric(proposed) || length(proposed) != 1L ||
      !is.finite(proposed) ||
      !is.finite(row[[time]]) || row[[time]] <= 0 ||
      !identical(sort(names(models)), sort(names(baselines))) ||
      is.na(row[[status]]) ||
      !as.character(row[[status]]) %in% c("0", names(models)))
    stop("Invalid substantive-likelihood input.", call. = FALSE)
  change <- proposed - row[[variable]]
  if (change == 0) return(0)
  ratio <- 0
  for (cause in names(models)) {
    model <- models[[cause]]
    base <- baselines[[cause]]
    if (!variable %in% model$variables ||
        any(!c("time", "increment") %in% names(base)) ||
        any(!is.finite(base$time) | !is.finite(base$increment)) ||
        any(base$increment <= 0))
      stop("Model and baseline hazard mismatch.", call. = FALSE)
    t <- base$time[base$time <= row[[time]]]
    dh <- base$increment[base$time <= row[[time]]]
    coefficient <- rep(unname(model$beta[[variable]]), length(t))
    event_coefficient <- unname(model$beta[[variable]])
    if (variable %in% model$time_varying) {
      tv_beta <- unname(model$beta[[paste0("tt(", variable, ")")]])
      coefficient <- coefficient + tv_beta * tvcr_basis(t, model$basis)
      event_coefficient <- event_coefficient +
        tv_beta * tvcr_basis(row[[time]], model$basis)
    }
    if (as.character(row[[status]]) == cause)
      ratio <- ratio + change * event_coefficient
    if (length(t)) {
      fixed <- sum(as.numeric(unlist(row[model$variables], use.names = FALSE)) *
                   model$beta[model$variables])
      changing <- sum(as.numeric(unlist(row[model$time_varying], use.names = FALSE)) *
                      model$beta[paste0("tt(", model$time_varying, ")")])
      current_eta <- fixed + changing * tvcr_basis(t, model$basis)
      ratio <- ratio - sum(dh * exp(current_eta) *
                             expm1(change * coefficient))
    }
  }
  if (!is.finite(ratio))
    stop("Non-finite substantive-likelihood ratio.", call. = FALSE)
  ratio
}
