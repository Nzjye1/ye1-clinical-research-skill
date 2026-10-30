formal_fg_apply_outcome_censoring <- function(data, analysis) {
  observed <- data[[analysis$outcome_observed]]
  state <- as.character(data[[analysis$observation_state]])
  allowed_states <- c("OBSERVED", "UTA_ONLY", "OTHER_UNOBSERVED")
  if (any(is.na(observed)) || !all(observed %in% c(0, 1))) stop("outcome_observed must be complete binary 0/1", call. = FALSE)
  if (any(is.na(state)) || !all(state %in% allowed_states)) stop("Unknown outcome-observation state", call. = FALSE)
  if (any((observed == 1) != (state == "OBSERVED"))) stop("Outcome-observation state does not reconcile with outcome_observed", call. = FALSE)
  if (any(data[[analysis$event]] == 1 & data[[analysis$competing_event]] == 1)) stop("Primary and competing events must be mutually exclusive", call. = FALSE)
  if (any(observed == 0 & (data[[analysis$event]] == 1 | data[[analysis$competing_event]] == 1))) {
    stop("Outcome-unobserved rows cannot carry an event", call. = FALSE)
  }
  last <- data[[analysis$last_observation_time]]
  if (!is.numeric(last) || any(!is.finite(last)) ||
      any(last[observed == 1] <= 0 | last[observed == 1] > analysis$horizon_hours) ||
      any(last[observed == 0] < 0 | last[observed == 0] > analysis$horizon_hours)) {
    stop(
      "observed outcome-observation time must be in (0, 84] and unobserved time in [0, 84]",
      call. = FALSE
    )
  }
  followup <- data[[analysis$time]]
  if (!is.numeric(followup) || any(!is.finite(followup) | followup <= 0 | followup > analysis$horizon_hours)) {
    stop("follow-up time must be in (0, 84]", call. = FALSE)
  }
  censored <- data
  unobserved <- observed == 0
  censored[[analysis$time]][unobserved] <- last[unobserved]
  censored[[analysis$event]][unobserved] <- 0L
  censored[[analysis$competing_event]][unobserved] <- 0L
  audit <- list(
    total_n = nrow(data), technically_observed_n = sum(state == "OBSERVED"),
    uta_only_n = sum(state == "UTA_ONLY"), other_unobserved_n = sum(state == "OTHER_UNOBSERVED"),
    outcome_unobserved_n = sum(unobserved), right_censored_at_last_known_n = sum(unobserved),
    outcome_unobserved_recoded_negative_n = 0L,
    reconciled = identical(sum(state == "UTA_ONLY") + sum(state == "OTHER_UNOBSERVED"), sum(unobserved))
  )
  if (!audit$reconciled) stop("Outcome-observation counts do not reconcile", call. = FALSE)
  list(data = censored, audit = audit)
}

formal_fg_initial_value <- function(x) {
  observed <- x[!is.na(x)]
  if (!length(observed)) stop("A model predictor is entirely missing in development", call. = FALSE)
  if (is.numeric(x)) stats::median(observed) else names(sort(table(observed), decreasing = TRUE))[[1L]]
}

formal_fg_numeric_code <- function(x) {
  if (is.numeric(x)) return(as.numeric(x))
  as.numeric(factor(x, levels = sort(unique(stats::na.omit(x)))))
}

formal_fg_zero_safe_followup_feature <- function(followup) {
  if (!is.numeric(followup) || any(!is.finite(followup)) ||
      any(followup < 0)) {
    formal_fg_stop(
      "IMPUTATION_FOLLOWUP_FEATURE_NONFINITE",
      "IMPUTATION"
    )
  }
  transformed <- log1p(followup)
  if (any(!is.finite(transformed))) {
    formal_fg_stop(
      "IMPUTATION_FOLLOWUP_FEATURE_NONFINITE",
      "IMPUTATION"
    )
  }
  transformed
}

formal_fg_imputation_model_step <- function(
    step,
    error_code = "IMPUTATION_MODEL_STEP_FAILED") {
  tryCatch(
    step(),
    formal_fg_safe_error = function(e) stop(e),
    error = function(e) {
      formal_fg_stop(error_code, "IMPUTATION")
    }
  )
}

formal_fg_development_target_state <- function(x, observed) {
  values <- unique(x[observed])
  values <- values[!is.na(values)]
  list(
    observed_n = sum(observed),
    distinct_n = length(values),
    constant = length(values) == 1L,
    constant_value = if (length(values) == 1L) values[[1L]] else NULL
  )
}

formal_fg_imputation_features <- function(dev, val, variables, analysis) {
  dev_matrix <- matrix(nrow = nrow(dev), ncol = 0L)
  val_matrix <- matrix(nrow = nrow(val), ncol = 0L)
  for (variable in variables) {
    if (is.numeric(dev[[variable]])) {
      dev_column <- as.numeric(dev[[variable]])
      val_column <- as.numeric(val[[variable]])
    } else {
      levels <- sort(unique(as.character(stats::na.omit(dev[[variable]]))))
      dev_column <- as.numeric(factor(dev[[variable]], levels = levels))
      val_column <- as.numeric(factor(val[[variable]], levels = levels))
      if (any(is.na(val_column))) {
        formal_fg_stop(
          "IMPUTATION_FEATURE_MATRIX_NONFINITE",
          "IMPUTATION"
        )
      }
    }
    dev_matrix <- cbind(dev_matrix, dev_column)
    val_matrix <- cbind(val_matrix, val_column)
    colnames(dev_matrix)[ncol(dev_matrix)] <- variable
    colnames(val_matrix)[ncol(val_matrix)] <- variable
  }
  dev_event <- as.numeric(dev[[analysis$event]])
  if (any(!is.finite(dev_event))) {
    formal_fg_stop("IMPUTATION_FEATURE_MATRIX_NONFINITE", "IMPUTATION")
  }
  dev_followup <- formal_fg_zero_safe_followup_feature(
    dev[[analysis$time]]
  )
  dev_matrix <- cbind(
    dev_matrix,
    development_event = dev_event,
    development_log1p_followup = dev_followup
  )
  val_matrix <- cbind(
    val_matrix,
    development_event = rep(mean(dev_event), nrow(val)),
    development_log1p_followup = rep(mean(dev_followup), nrow(val))
  )
  if (any(!is.finite(dev_matrix)) || any(!is.finite(val_matrix))) {
    formal_fg_stop("IMPUTATION_FEATURE_MATRIX_NONFINITE", "IMPUTATION")
  }
  center <- colMeans(dev_matrix)
  spread <- apply(dev_matrix, 2L, stats::sd)
  if (any(!is.finite(center)) || any(!is.finite(spread))) {
    formal_fg_stop("IMPUTATION_FEATURE_MATRIX_NONFINITE", "IMPUTATION")
  }
  informative <- spread > 0
  dev_matrix <- dev_matrix[, informative, drop = FALSE]
  val_matrix <- val_matrix[, informative, drop = FALSE]
  center <- center[informative]
  spread <- spread[informative]
  standardized <- list(
    development = sweep(
      sweep(dev_matrix, 2L, center, "-"),
      2L, spread, "/"
    ),
    validation = sweep(
      sweep(val_matrix, 2L, center, "-"),
      2L, spread, "/"
    )
  )
  if (any(!is.finite(standardized$development)) ||
      any(!is.finite(standardized$validation))) {
    formal_fg_stop("IMPUTATION_FEATURE_MATRIX_NONFINITE", "IMPUTATION")
  }
  standardized
}

formal_fg_impute_once <- function(development, validation, analysis, seed) {
  set.seed(seed)
  contract <- formal_temporal_fg_contract_for_analysis(analysis)
  predictors <- unlist(analysis$model_plan$primary_predictors, use.names = FALSE)
  dev <- development
  val <- validation
  original_missing_dev <- lapply(dev[predictors], is.na)
  original_missing_val <- lapply(val[predictors], is.na)
  initial <- lapply(dev[predictors], formal_fg_initial_value)
  for (variable in predictors) {
    dev[[variable]][is.na(dev[[variable]])] <- initial[[variable]]
    val[[variable]][is.na(val[[variable]])] <- initial[[variable]]
  }
  for (iteration in seq_len(analysis$imputation$iterations)) {
    for (variable in predictors) {
      missing_dev <- original_missing_dev[[variable]]
      missing_val <- original_missing_val[[variable]]
      if (!any(missing_dev) && !any(missing_val)) next
      observed_dev <- !missing_dev
      target_state <- formal_fg_development_target_state(
        development[[variable]],
        observed_dev
      )
      if (!target_state$observed_n) {
        formal_fg_stop(
          "IMPUTATION_TARGET_NO_OBSERVED_CASES",
          "IMPUTATION"
        )
      }
      if (target_state$constant) {
        dev[[variable]][missing_dev] <- target_state$constant_value
        val[[variable]][missing_val] <- target_state$constant_value
        next
      }
      others <- setdiff(predictors, variable)
      features <- formal_fg_imputation_features(dev, val, others, analysis)
      x_dev <- cbind(`(Intercept)` = 1, features$development)
      x_val <- cbind(`(Intercept)` = 1, features$validation)
      transformation <- contract$transformations[[variable]]
      binary <- identical(transformation, "BINARY_INDICATOR")
      categorical <- grepl("^TREATMENT_CODING_", transformation)
      if (categorical) {
        training <- data.frame(y = factor(development[[variable]][observed_dev]), features$development[observed_dev, , drop = FALSE], check.names = FALSE)
        fitted <- formal_fg_imputation_model_step(
          function() {
            nnet::multinom(
              y ~ ., data = training, trace = FALSE, maxit = 100L
            )
          },
          "IMPUTATION_CATEGORICAL_FIT_FAILED"
        )
        if (any(missing_dev)) {
          probabilities <- formal_fg_imputation_model_step(
            function() {
              stats::predict(
                fitted,
                newdata = data.frame(
                  features$development[missing_dev, , drop = FALSE]
                ),
                type = "probs"
              )
            },
            "IMPUTATION_CATEGORICAL_PREDICTION_FAILED"
          )
          if (is.null(dim(probabilities))) probabilities <- matrix(probabilities, nrow = 1L, dimnames = list(NULL, names(probabilities)))
          if (any(!is.finite(probabilities)) ||
              any(probabilities < 0) || any(probabilities > 1)) {
            formal_fg_stop(
              "IMPUTATION_CATEGORICAL_PREDICTION_FAILED",
              "IMPUTATION"
            )
          }
          categories <- colnames(probabilities)
          draw_category <- function(probability) sample(categories, 1L, prob = probability)
          dev[[variable]][missing_dev] <- apply(probabilities, 1L, draw_category)
        }
        if (any(missing_val)) {
          probabilities <- formal_fg_imputation_model_step(
            function() {
              stats::predict(
                fitted,
                newdata = data.frame(
                  features$validation[missing_val, , drop = FALSE]
                ),
                type = "probs"
              )
            },
            "IMPUTATION_CATEGORICAL_PREDICTION_FAILED"
          )
          if (is.null(dim(probabilities))) probabilities <- matrix(probabilities, nrow = 1L, dimnames = list(NULL, names(probabilities)))
          if (any(!is.finite(probabilities)) ||
              any(probabilities < 0) || any(probabilities > 1)) {
            formal_fg_stop(
              "IMPUTATION_CATEGORICAL_PREDICTION_FAILED",
              "IMPUTATION"
            )
          }
          categories <- colnames(probabilities)
          draw_category <- function(probability) sample(categories, 1L, prob = probability)
          val[[variable]][missing_val] <- apply(probabilities, 1L, draw_category)
        }
      } else if (binary) {
        fitted <- formal_fg_imputation_model_step(
          function() {
            suppressWarnings(stats::glm.fit(
              x_dev[observed_dev, , drop = FALSE],
              development[[variable]][observed_dev],
              family = stats::binomial()
            ))
          },
          "IMPUTATION_BINARY_FIT_FAILED"
        )
        beta <- fitted$coefficients
        if (any(!is.finite(beta))) {
          formal_fg_stop("IMPUTATION_BINARY_FIT_FAILED", "IMPUTATION")
        }
        if (any(missing_dev)) {
          probability <- formal_fg_imputation_model_step(
            function() {
              stats::plogis(drop(
                x_dev[missing_dev, , drop = FALSE] %*% beta
              ))
            },
            "IMPUTATION_BINARY_PREDICTION_FAILED"
          )
          if (any(!is.finite(probability))) {
            formal_fg_stop(
              "IMPUTATION_BINARY_PREDICTION_FAILED",
              "IMPUTATION"
            )
          }
          dev[[variable]][missing_dev] <- stats::rbinom(sum(missing_dev), 1L, probability)
        }
        if (any(missing_val)) {
          probability <- formal_fg_imputation_model_step(
            function() {
              stats::plogis(drop(
                x_val[missing_val, , drop = FALSE] %*% beta
              ))
            },
            "IMPUTATION_BINARY_PREDICTION_FAILED"
          )
          if (any(!is.finite(probability))) {
            formal_fg_stop(
              "IMPUTATION_BINARY_PREDICTION_FAILED",
              "IMPUTATION"
            )
          }
          val[[variable]][missing_val] <- stats::rbinom(sum(missing_val), 1L, probability)
        }
      } else {
        fitted <- formal_fg_imputation_model_step(
          function() {
            stats::lm.fit(
              x_dev[observed_dev, , drop = FALSE],
              development[[variable]][observed_dev]
            )
          },
          "IMPUTATION_CONTINUOUS_FIT_FAILED"
        )
        beta <- fitted$coefficients
        if (any(!is.finite(beta))) {
          formal_fg_stop("IMPUTATION_CONTINUOUS_FIT_FAILED", "IMPUTATION")
        }
        predictions <- formal_fg_imputation_model_step(
          function() {
            list(
              development = drop(x_dev %*% beta),
              validation = drop(x_val %*% beta)
            )
          },
          "IMPUTATION_CONTINUOUS_PREDICTION_FAILED"
        )
        predicted_dev <- predictions$development
        predicted_val <- predictions$validation
        if (any(!is.finite(predicted_dev)) ||
            any(!is.finite(predicted_val))) {
          formal_fg_stop(
            "IMPUTATION_CONTINUOUS_PREDICTION_FAILED",
            "IMPUTATION"
          )
        }
        donor_index <- which(observed_dev)
        draw_donor <- function(score) {
          distance <- abs(predicted_dev[donor_index] - score)
          nearest <- donor_index[order(distance, na.last = NA)[seq_len(min(5L, length(donor_index)))]]
          sample(nearest, 1L)
        }
        if (any(missing_dev)) {
          draws <- vapply(predicted_dev[missing_dev], draw_donor, integer(1))
          dev[[variable]][missing_dev] <- development[[variable]][draws]
        }
        if (any(missing_val)) {
          draws <- vapply(predicted_val[missing_val], draw_donor, integer(1))
          val[[variable]][missing_val] <- development[[variable]][draws]
        }
      }
    }
  }
  for (variable in predictors) {
    if (any(is.na(dev[[variable]])) || any(is.na(val[[variable]])) ||
        (is.numeric(dev[[variable]]) &&
          (any(!is.finite(dev[[variable]])) ||
            any(!is.finite(val[[variable]]))))) {
      formal_fg_stop("IMPUTATION_COMPLETION_INVALID", "IMPUTATION")
    }
  }
  list(development = dev, validation = val)
}

formal_fg_multiple_imputation <- function(development, validation, analysis) {
  m <- analysis$imputation$m
  completed <- lapply(seq_len(m), function(i) {
    formal_fg_impute_once(development, validation, analysis, analysis$imputation$seed + i - 1L)
  })
  list(
    completed = completed,
    diagnostics = list(
      engine = "DETERMINISTIC_DEVELOPMENT_DONOR_CHAINED_EQUATIONS",
      m = m, iterations = analysis$imputation$iterations, seed = analysis$imputation$seed,
      development_fit_only = TRUE, validation_outcomes_used = FALSE,
      validation_outcome_access_count = 0L,
      completed_datasets = length(completed), convergence_status = "COMPLETE",
      continuous_method = "PREDICTIVE_MEAN_MATCHING",
      binary_method = "LOGISTIC_REGRESSION",
      categorical_method = "MULTINOMIAL_LOGISTIC_REGRESSION"
    )
  )
}

formal_fg_rcs <- function(x, knots) {
  k1 <- knots[[1L]]; k2 <- knots[[2L]]; k3 <- knots[[3L]]
  plus3 <- function(z) pmax(z, 0)^3
  nonlinear <- plus3(x - k1) - plus3(x - k2) * (k3 - k1) / (k3 - k2) +
    plus3(x - k3) * (k2 - k1) / (k3 - k2)
  cbind(age_linear = x, age_rcs = nonlinear / (k3 - k1)^2)
}

formal_fg_design_matrix <- function(
  data,
  knots = NULL,
  predictors,
  parameter_df = NULL
) {
  if (is.null(knots)) knots <- unname(stats::quantile(data$age, c(0.1, 0.5, 0.9), names = FALSE, type = 7))
  if (length(unique(knots)) != 3L) stop("Development age spline knots are not distinct", call. = FALSE)
  age <- formal_fg_rcs(data$age, knots)
  matrix <- cbind(
    age,
    female = data$female,
    admission_context = data$admission_context,
    dementia_history = data$dementia_history,
    alcohol_use_history = data$alcohol_use_history,
    early_cardiac_arrest = data$early_cardiac_arrest,
    heart_rate_max_0_12h = data$heart_rate_max_0_12h / 10,
    systolic_bp_min_0_12h = data$systolic_bp_min_0_12h / 10,
    respiratory_rate_max_0_12h = data$respiratory_rate_max_0_12h / 5,
    temperature_max_0_12h = data$temperature_max_0_12h,
    spo2_min_0_12h = data$spo2_min_0_12h / 5,
    gcs_min_0_12h = data$gcs_min_0_12h,
    rass_min_0_12h = data$rass_min_0_12h,
    lactate_max_0_12h = log(data$lactate_max_0_12h),
    ph_min_0_12h = data$ph_min_0_12h / 0.1,
    glucose_max_0_12h = log(data$glucose_max_0_12h),
    sodium_latest_0_12h = data$sodium_latest_0_12h / 5,
    creatinine_max_0_12h = log(data$creatinine_max_0_12h),
    bun_max_0_12h = log(data$bun_max_0_12h),
    wbc_max_0_12h = log(data$wbc_max_0_12h),
    mechanical_ventilation_0_12h = data$mechanical_ventilation_0_12h,
    vasoactive_support_0_12h = data$vasoactive_support_0_12h,
    sedative_exposure_0_12h = data$sedative_exposure_0_12h,
    opioid_exposure_0_12h = data$opioid_exposure_0_12h
  )
  if ("ami_type" %in% predictors) {
    ami <- factor(data$ami_type, levels = c("NSTEMI", "STEMI", "OTHER_UNSPECIFIED"))
    if (any(is.na(ami))) stop("ami_type must use NSTEMI, STEMI, or OTHER_UNSPECIFIED", call. = FALSE)
    matrix <- cbind(
      matrix[, c("age_linear", "age_rcs", "female"), drop = FALSE],
      ami_type_STEMI = as.integer(ami == "STEMI"),
      ami_type_OTHER_UNSPECIFIED = as.integer(ami == "OTHER_UNSPECIFIED"),
      matrix[, setdiff(colnames(matrix), c("age_linear", "age_rcs", "female")), drop = FALSE]
    )
  }
  if (any(!is.finite(matrix))) stop("Frozen transformations produced a non-finite value", call. = FALSE)
  keep <- if (identical(predictors, c("age", "female"))) {
    c("age_linear", "age_rcs", "female")
  } else {
    expected <- unlist(lapply(predictors, function(variable) {
      if (identical(variable, "age")) return(c("age_linear", "age_rcs"))
      if (identical(variable, "ami_type")) {
        return(c("ami_type_STEMI", "ami_type_OTHER_UNSPECIFIED"))
      }
      variable
    }), use.names = FALSE)
    expected
  }
  if (length(setdiff(keep, colnames(matrix)))) {
    stop("Frozen predictor projection cannot be represented by the design matrix", call. = FALSE)
  }
  projected <- matrix[, keep, drop = FALSE]
  if (!is.null(parameter_df) && ncol(projected) != parameter_df) {
    stop(sprintf(
      "Frozen primary design matrix must contain exactly %d df",
      parameter_df
    ), call. = FALSE)
  }
  list(matrix = projected, knots = knots)
}

formal_fg_primary_model_step <- function(
    step,
    error_code,
    stage = "PRIMARY_FIT") {
  tryCatch(
    step(),
    formal_fg_safe_error = function(e) stop(e),
    error = function(e) formal_fg_stop(error_code, stage)
  )
}

formal_fg_fit_matrix <- function(
    data,
    matrix,
    analysis,
    case_weights = NULL,
    failure_stage = "PRIMARY_FIT") {
  if (!is.matrix(matrix) || !is.numeric(matrix) ||
      !nrow(matrix) || !ncol(matrix) ||
      is.null(colnames(matrix)) || any(!is.finite(matrix))) {
    formal_fg_stop("PRIMARY_FIT_DESIGN_INVALID", failure_stage)
  }
  structural_constant <- vapply(
    seq_len(ncol(matrix)),
    function(index) {
      column <- matrix[, index]
      all(column == column[[1L]])
    },
    logical(1)
  )
  names(structural_constant) <- colnames(matrix)
  status <- factor(
    ifelse(data[[analysis$event]] == 1, "event", ifelse(data[[analysis$competing_event]] == 1, "competing", "censor")),
    levels = c("censor", "event", "competing")
  )
  model_data <- data.frame(.time = data[[analysis$time]], .status = status, matrix, check.names = FALSE)
  formula <- stats::reformulate(colnames(matrix), response = "survival::Surv(.time, .status)")
  expanded <- formal_fg_primary_model_step(
    function() {
      survival::finegray(
        formula,
        data = model_data,
        etype = "event",
        weights = case_weights
      )
    },
    "PRIMARY_FIT_FINEGRAY_EXPANSION_FAILED",
    failure_stage
  )
  fit_formula <- stats::reformulate(colnames(matrix), response = "survival::Surv(fgstart, fgstop, fgstatus)")
  weights <- expanded$fgwt
  fit <- formal_fg_primary_model_step(
    function() {
      survival::coxph(
        fit_formula,
        data = expanded,
        weights = weights,
        ties = "breslow",
        x = TRUE,
        model = TRUE
      )
    },
    "PRIMARY_FIT_COXPH_FAILED",
    failure_stage
  )
  if (is.null(fit$converged) && !is.null(fit$iter)) fit$converged <- fit$iter < 20L
  coefficients <- stats::coef(fit)
  if (!length(coefficients) || is.null(names(coefficients))) {
    formal_fg_stop(
      "PRIMARY_FIT_NONSTRUCTURAL_SINGULARITY",
      failure_stage
    )
  }
  nonfinite_terms <- names(coefficients)[!is.finite(coefficients)]
  structural_terms <- names(structural_constant)[structural_constant]
  if (length(setdiff(nonfinite_terms, structural_terms))) {
    formal_fg_stop(
      "PRIMARY_FIT_NONSTRUCTURAL_SINGULARITY",
      failure_stage
    )
  }
  constrained_terms <- intersect(names(coefficients), structural_terms)
  if (!is.matrix(fit$var) ||
      !identical(dim(fit$var), c(length(coefficients), length(coefficients)))) {
    formal_fg_stop("PRIMARY_FIT_VARIANCE_NONFINITE", failure_stage)
  }
  if (length(constrained_terms)) {
    constrained_index <- match(constrained_terms, names(coefficients))
    fit$coefficients[constrained_index] <- 0
    fit$var[constrained_index, ] <- 0
    fit$var[, constrained_index] <- 0
  }
  if (any(!is.finite(stats::coef(fit)))) {
    formal_fg_stop(
      "PRIMARY_FIT_NONSTRUCTURAL_SINGULARITY",
      failure_stage
    )
  }
  if (any(!is.finite(stats::vcov(fit)))) {
    formal_fg_stop("PRIMARY_FIT_VARIANCE_NONFINITE", failure_stage)
  }
  list(
    fit = fit,
    expanded = expanded,
    weights = weights,
    formula = formula,
    structurally_constrained_terms = constrained_terms
  )
}

formal_fg_predict_fit <- function(
    fitted,
    matrix,
    horizon,
    shrinkage = 1,
    failure_stage = "PRIMARY_FIT") {
  formal_fg_primary_model_step(
    function() {
      beta <- stats::coef(fitted$fit) * shrinkage
      lp <- drop(matrix[, names(beta), drop = FALSE] %*% beta)
      expanded <- fitted$expanded
      x <- as.matrix(expanded[, names(beta), drop = FALSE])
      expanded_lp <- drop(x %*% beta)
      event_rows <- expanded$fgstatus == 1 & expanded$fgstop <= horizon
      event_times <- sort(unique(expanded$fgstop[event_rows]))
      cumulative <- 0
      for (event_time in event_times) {
        event_weight <- sum(
          fitted$weights[
            expanded$fgstatus == 1 &
              expanded$fgstop == event_time
          ]
        )
        risk <- expanded$fgstart < event_time &
          expanded$fgstop >= event_time
        denominator <- sum(
          fitted$weights[risk] * exp(expanded_lp[risk])
        )
        if (denominator > 0) {
          cumulative <- cumulative + event_weight / denominator
        }
      }
      prediction <- 1 - exp(-cumulative * exp(lp))
      if (!is.finite(cumulative) ||
          any(!is.finite(prediction) |
              prediction < 0 |
              prediction > 1)) {
        formal_fg_stop(
          "PRIMARY_FIT_PREDICTION_FAILED",
          failure_stage
        )
      }
      list(
        risk = prediction,
        baseline_subdistribution_hazard = cumulative,
        beta = beta
      )
    },
    "PRIMARY_FIT_PREDICTION_FAILED",
    failure_stage
  )
}

formal_fg_aj_risk <- function(time, event, competing, horizon) {
  status <- ifelse(event == 1, 1L, ifelse(competing == 1, 2L, 0L))
  times <- sort(unique(time[time <= horizon & status != 0]))
  survival <- 1; cif <- 0
  for (current in times) {
    at_risk <- sum(time >= current)
    if (!at_risk) next
    d1 <- sum(time == current & status == 1L)
    dall <- sum(time == current & status != 0L)
    cif <- cif + survival * d1 / at_risk
    survival <- survival * (1 - dall / at_risk)
  }
  cif
}

formal_fg_censor_survival <- function(time, event, competing, at) {
  censor <- event == 0 & competing == 0
  points <- sort(unique(time[censor & time <= at]))
  g <- 1
  for (current in points) {
    risk <- sum(time >= current)
    if (risk > 0) g <- g * (1 - sum(censor & time == current) / risk)
  }
  max(g, 1e-06)
}

formal_fg_ipcw_components <- function(time, event, competing, horizon) {
  before <- time <= horizon
  known <- before & (event == 1 | competing == 1) | time >= horizon
  target <- as.numeric(before & event == 1)
  weights <- numeric(length(time))
  for (i in which(known)) weights[[i]] <- 1 / formal_fg_censor_survival(time, event, competing, min(time[[i]], horizon))
  list(target = target, weights = weights, known = known)
}

formal_fg_metrics <- function(time, event, competing, risk, horizon = 84, calibration_grid = seq(0.01, 0.99, length.out = 50L)) {
  ipcw <- formal_fg_ipcw_components(time, event, competing, horizon)
  use <- ipcw$weights > 0
  y <- ipcw$target; w <- ipcw$weights
  brier <- sum(w[use] * (y[use] - risk[use])^2) / sum(w[use])
  null_risk <- formal_fg_aj_risk(time, event, competing, horizon)
  null_brier <- sum(w[use] * (y[use] - null_risk)^2) / sum(w[use])
  cases <- which(use & y == 1); controls <- which(use & y == 0)
  control_weights <- rowsum(w[controls], group = risk[controls], reorder = TRUE)
  control_risks <- as.numeric(rownames(control_weights))
  control_weights <- drop(control_weights)
  control_order <- order(control_risks)
  control_risks <- control_risks[control_order]
  control_weights <- control_weights[control_order]
  cumulative_control <- cumsum(control_weights)
  lower_weight <- c(0, utils::head(cumulative_control, -1L))
  case_scores <- vapply(risk[cases], function(case_risk) {
    exact <- match(case_risk, control_risks)
    if (!is.na(exact)) return(lower_weight[[exact]] + 0.5 * control_weights[[exact]])
    below <- findInterval(case_risk, control_risks)
    if (below == 0L) 0 else cumulative_control[[below]]
  }, numeric(1))
  auc_num <- sum(w[cases] * case_scores)
  auc_den <- sum(w[cases]) * sum(w[controls])
  auc <- if (auc_den > 0) auc_num / auc_den else NA_real_
  eps <- 1e-06
  cloglog_risk <- log(-log(pmax(1 - pmin(pmax(risk, eps), 1 - eps), eps)))
  calibration_data <- data.frame(y = y[use], lp = cloglog_risk[use], w = w[use])
  intercept_fit <- suppressWarnings(stats::glm(y ~ offset(lp), data = calibration_data, weights = w, family = stats::binomial(link = "cloglog")))
  slope_fit <- suppressWarnings(stats::glm(y ~ lp, data = calibration_data, weights = w, family = stats::binomial(link = "cloglog")))
  calibration_in_large <- unname(stats::coef(intercept_fit)[[1L]])
  slope <- unname(stats::coef(slope_fit)[[2L]])
  bins <- pmin(10L, floor((rank(risk[use], ties.method = "first") - 1L) * 10L / sum(use)) + 1L)
  decile <- do.call(rbind, lapply(split(seq_along(bins), bins), function(index) {
    data.frame(predicted = stats::weighted.mean(risk[use][index], w[use][index]), observed = stats::weighted.mean(y[use][index], w[use][index]))
  }))
  decile$absolute_error <- abs(decile$observed - decile$predicted)
  calibration_points <- stats::aggregate(observed ~ predicted, data = decile, FUN = mean)
  calibrated <- pmin(pmax(stats::approx(
    calibration_points$predicted, calibration_points$observed,
    xout = risk[use], rule = 2, ties = mean
  )$y, 0), 1)
  grid_calibrated <- pmin(pmax(stats::approx(
    calibration_points$predicted, calibration_points$observed,
    xout = calibration_grid, rule = 2, ties = mean
  )$y, 0), 1)
  ici <- sum(w[use] * abs(calibrated - risk[use])) / sum(w[use])
  list(
    metrics = c(
      TIME_DEPENDENT_AUC_AT_84H = auc, IPCW_BRIER_AT_84H = brier,
      SCALED_BRIER_VS_NULL = 1 - brier / null_brier,
      OE_RATIO_AT_84H = null_risk / mean(risk),
      CALIBRATION_IN_THE_LARGE_CLOGLOG = calibration_in_large,
      CALIBRATION_SLOPE = slope, ICI = ici,
      DECILE_ABSOLUTE_ERROR = max(decile$absolute_error)
    ),
    flexible_curve = data.frame(predicted = calibration_grid, calibrated = grid_calibrated),
    decile = decile, null_risk = null_risk
  )
}

formal_fg_evaluate_calibration_gate <- function(metrics, gate) {
  conditions <- c(
    oe_ratio = metrics[["OE_RATIO_AT_84H"]] >= gate$oe_ratio_range[[1L]] && metrics[["OE_RATIO_AT_84H"]] <= gate$oe_ratio_range[[2L]],
    calibration_slope = metrics[["CALIBRATION_SLOPE"]] >= gate$calibration_slope_range[[1L]] && metrics[["CALIBRATION_SLOPE"]] <= gate$calibration_slope_range[[2L]],
    ici = metrics[["ICI"]] <= gate$maximum_ici,
    decile_absolute_error = metrics[["DECILE_ABSOLUTE_ERROR"]] <= gate$maximum_decile_absolute_error
  )
  passed <- all(conditions)
  list(
    conditions = as.list(conditions), all_passed = passed,
    dca_status = if (passed) "GENERATED" else gate$failed_output,
    clinical_utility_claim_allowed = passed
  )
}

formal_fg_dca <- function(time, event, competing, risk, thresholds, horizon = 84) {
  ipcw <- formal_fg_ipcw_components(time, event, competing, horizon)
  use <- ipcw$weights > 0; y <- ipcw$target; w <- ipcw$weights
  do.call(rbind, lapply(thresholds, function(threshold) {
    treated <- risk >= threshold
    tp <- sum(w[use] * treated[use] * y[use]) / sum(w[use])
    fp <- sum(w[use] * treated[use] * (1 - y[use])) / sum(w[use])
    data.frame(threshold = threshold, net_benefit = tp - fp * threshold / (1 - threshold))
  }))
}

formal_fg_bootstrap_control <- function(
    attempt_binding_sha256,
    workers = NULL,
    chunk_size = 10L,
    max_chunks = Inf) {
  if (!formal_fg_sha256(attempt_binding_sha256)) {
    stop("Bootstrap execution requires a SHA-256 attempt binding", call. = FALSE)
  }
  if (is.null(workers)) {
    detected <- suppressWarnings(parallel::detectCores(logical = FALSE))
    if (is.na(detected) || detected < 1L) detected <- 1L
    workers <- min(2L, as.integer(detected))
  }
  workers <- as.integer(workers)
  chunk_size <- as.integer(chunk_size)
  if (length(workers) != 1L || is.na(workers) || workers < 1L || workers > 3L) {
    stop("Bootstrap workers must be an integer from 1 through 3", call. = FALSE)
  }
  if (length(chunk_size) != 1L || is.na(chunk_size) || chunk_size < 1L) {
    stop("Bootstrap chunk_size must be a positive integer", call. = FALSE)
  }
  if (length(max_chunks) != 1L || is.na(max_chunks) ||
      (!is.infinite(max_chunks) && (max_chunks < 1 || max_chunks != as.integer(max_chunks)))) {
    stop("Bootstrap max_chunks must be a positive integer or Inf", call. = FALSE)
  }
  list(
    schema_version = "formal-fg-bootstrap-control@1.0.0",
    attempt_binding_sha256 = attempt_binding_sha256,
    workers = workers,
    chunk_size = chunk_size,
    max_chunks = max_chunks
  )
}

formal_fg_bootstrap_seed_ledger <- function(seed, replicates) {
  if (length(seed) != 1L || is.na(seed) || seed != as.integer(seed)) {
    stop("Bootstrap seed must be one integer", call. = FALSE)
  }
  if (length(replicates) != 1L || is.na(replicates) ||
      replicates < 1L || replicates != as.integer(replicates)) {
    stop("Bootstrap replicates must be a positive integer", call. = FALSE)
  }
  old_kind <- RNGkind()
  had_seed <- exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  if (had_seed) old_seed <- get(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  on.exit({
    do.call(RNGkind, as.list(old_kind))
    if (had_seed) {
      assign(".Random.seed", old_seed, envir = .GlobalEnv)
    } else if (exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE)) {
      rm(".Random.seed", envir = .GlobalEnv)
    }
  }, add = TRUE)
  RNGkind("L'Ecuyer-CMRG")
  set.seed(as.integer(seed))
  current <- get(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  ledger <- vector("list", as.integer(replicates))
  for (i in seq_len(replicates)) {
    ledger[[i]] <- unname(as.integer(current))
    current <- parallel::nextRNGStream(current)
  }
  ledger
}

formal_fg_checkpoint_value_is_safe <- function(value, trail = "result") {
  if (is.null(value)) return(TRUE)
  if (is.environment(value) || is.function(value) || typeof(value) == "externalptr") return(FALSE)
  value_names <- names(value)
  if (!is.null(value_names) && any(grepl(
    "(^|_)(patient|record|row|path|file|directory|payload)(_|$)",
    value_names,
    ignore.case = TRUE
  ))) {
    return(FALSE)
  }
  if (is.data.frame(value)) value <- as.list(value)
  if (is.list(value)) {
    item_names <- names(value)
    if (!is.null(item_names)) {
      forbidden_name <- grepl(
        "(^|_)(patient|record|row|path|file|directory|payload)(_|$)",
        item_names,
        ignore.case = TRUE
      )
      if (any(forbidden_name)) return(FALSE)
    }
    return(all(vapply(
      seq_along(value),
      function(i) formal_fg_checkpoint_value_is_safe(
        value[[i]],
        paste0(trail, ".", if (is.null(item_names) || !nzchar(item_names[[i]])) i else item_names[[i]])
      ),
      logical(1)
    )))
  }
  if (!is.atomic(value)) return(FALSE)
  if (is.character(value)) {
    path_like <- grepl(
      "(/Users/|/private/|/home/|/tmp/|file://|[A-Za-z]:\\\\)",
      value,
      ignore.case = TRUE
    )
    row_like <- grepl("(record_id|patient_id|row[[:space:]_]*[0-9]+)", value, ignore.case = TRUE)
    if (any(path_like | row_like)) return(FALSE)
  }
  TRUE
}

formal_fg_bootstrap_checkpoint_hash <- function(checkpoint) {
  candidate <- checkpoint
  candidate$checkpoint_sha256 <- NULL
  digest::digest(
    jsonlite::toJSON(candidate, auto_unbox = TRUE, null = "null", digits = NA),
    algo = "sha256",
    serialize = FALSE
  )
}

formal_fg_validate_bootstrap_checkpoint <- function(
    checkpoint,
    replicates,
    seed,
    scope,
    execution,
    seed_ledger) {
  fields <- c(
    "schema_version", "status", "aggregate_only", "patient_level_payload",
    "physical_paths_present", "scope", "attempt_binding_sha256",
    "replicates_requested", "base_seed", "replicates_completed",
    "replicates_failed", "chunks_completed", "generation", "records",
    "checkpoint_sha256"
  )
  if (!is.list(checkpoint) || !identical(names(checkpoint), fields)) {
    stop("Bootstrap checkpoint fields are invalid", call. = FALSE)
  }
  if (!identical(checkpoint$schema_version, "formal-fg-bootstrap-checkpoint@1.0.0") ||
      !identical(checkpoint$status, "PARTIAL") ||
      !identical(checkpoint$aggregate_only, TRUE) ||
      !identical(checkpoint$patient_level_payload, FALSE) ||
      !identical(checkpoint$physical_paths_present, FALSE)) {
    stop("Only a privacy-safe PARTIAL bootstrap checkpoint can be resumed", call. = FALSE)
  }
  if (!identical(checkpoint$scope, scope %||% "DATA_SEMANTICS") ||
      !identical(checkpoint$attempt_binding_sha256, execution$attempt_binding_sha256) ||
      !identical(checkpoint$replicates_requested, as.integer(replicates)) ||
      !identical(checkpoint$base_seed, as.integer(seed))) {
    stop("Bootstrap checkpoint does not belong to this attempt and plan", call. = FALSE)
  }
  if (!identical(checkpoint$checkpoint_sha256, formal_fg_bootstrap_checkpoint_hash(checkpoint))) {
    stop("Bootstrap checkpoint checksum is invalid", call. = FALSE)
  }
  if (!is.list(checkpoint$records) ||
      !identical(checkpoint$replicates_completed, as.integer(length(checkpoint$records))) ||
      !identical(checkpoint$replicates_failed, 0L)) {
    stop("Bootstrap checkpoint counts are invalid", call. = FALSE)
  }
  replicate_ids <- vapply(checkpoint$records, `[[`, integer(1), "replicate_id")
  if (anyDuplicated(replicate_ids) ||
      !identical(replicate_ids, seq_len(checkpoint$replicates_completed))) {
    stop("Bootstrap checkpoint replicate identities are invalid or duplicated", call. = FALSE)
  }
  for (i in seq_along(checkpoint$records)) {
    record <- checkpoint$records[[i]]
    if (!identical(names(record), c("replicate_id", "seed", "status", "result")) ||
        !identical(record$status, "COMPLETE") ||
        !identical(unlist(record$seed, use.names = FALSE), seed_ledger[[record$replicate_id]]) ||
        !formal_fg_checkpoint_value_is_safe(record$result) ||
        as.numeric(utils::object.size(record$result)) > 1024^2) {
      stop("Bootstrap checkpoint replicate record is invalid", call. = FALSE)
    }
  }
  invisible(TRUE)
}

formal_fg_run_bootstrap_replicate <- function(replicate_id, seed_state, runner, stage) {
  on.exit(gc(verbose = FALSE), add = TRUE)
  assign(".Random.seed", seed_state, envir = .GlobalEnv)
  tryCatch(
    {
      value <- runner(replicate_id)
      if (is.null(value) || !formal_fg_checkpoint_value_is_safe(value) ||
          as.numeric(utils::object.size(value)) > 1024^2) {
        stop("Bootstrap runner returned a non-aggregate checkpoint value", call. = FALSE)
      }
      list(
        replicate_id = as.integer(replicate_id),
        seed = as.list(seed_state),
        status = "COMPLETE",
        result = value
      )
    },
    error = function(e) {
      list(
        replicate_id = as.integer(replicate_id),
        seed = as.list(seed_state),
        status = "FAILED",
        error_code = formal_fg_condition_code(e, stage)
      )
    }
  )
}

formal_fg_make_bootstrap_checkpoint <- function(
    status,
    scope,
    execution,
    replicates,
    seed,
    records,
    chunks_completed,
    generation) {
  checkpoint <- list(
    schema_version = "formal-fg-bootstrap-checkpoint@1.0.0",
    status = status,
    aggregate_only = TRUE,
    patient_level_payload = FALSE,
    physical_paths_present = FALSE,
    scope = scope %||% "DATA_SEMANTICS",
    attempt_binding_sha256 = execution$attempt_binding_sha256,
    replicates_requested = as.integer(replicates),
    base_seed = as.integer(seed),
    replicates_completed = as.integer(sum(vapply(records, `[[`, character(1), "status") == "COMPLETE")),
    replicates_failed = as.integer(sum(vapply(records, `[[`, character(1), "status") == "FAILED")),
    chunks_completed = as.integer(chunks_completed),
    generation = as.integer(generation),
    records = records,
    checkpoint_sha256 = NULL
  )
  checkpoint$checkpoint_sha256 <- formal_fg_bootstrap_checkpoint_hash(checkpoint)
  checkpoint
}

formal_fg_bootstrap_orchestrate_chunked <- function(
    replicates,
    seed,
    runner,
    observer,
    scope,
    execution,
    checkpoint,
    checkpoint_callback,
    resume_claim) {
  control_fields <- c(
    "schema_version", "attempt_binding_sha256", "workers", "chunk_size",
    "max_chunks"
  )
  if (!is.list(execution) || !identical(names(execution), control_fields) ||
      !identical(execution$schema_version, "formal-fg-bootstrap-control@1.0.0") ||
      !formal_fg_sha256(execution$attempt_binding_sha256) ||
      length(execution$workers) != 1L || is.na(execution$workers) ||
      execution$workers != as.integer(execution$workers) ||
      execution$workers < 1L || execution$workers > 3L ||
      length(execution$chunk_size) != 1L || is.na(execution$chunk_size) ||
      execution$chunk_size != as.integer(execution$chunk_size) ||
      execution$chunk_size < 1L ||
      length(execution$max_chunks) != 1L || is.na(execution$max_chunks) ||
      (!is.infinite(execution$max_chunks) &&
        (execution$max_chunks < 1L ||
          execution$max_chunks != as.integer(execution$max_chunks)))) {
    stop("Invalid deterministic bootstrap execution control", call. = FALSE)
  }
  if (!is.function(runner)) stop("Bootstrap runner must be a function", call. = FALSE)
  if (execution$workers > 1L && .Platform$OS.type == "windows") {
    stop("Bounded fork bootstrap workers are unavailable on Windows", call. = FALSE)
  }
  if (!is.null(checkpoint_callback) && !is.function(checkpoint_callback)) {
    stop("checkpoint_callback must be a function", call. = FALSE)
  }
  seed_ledger <- formal_fg_bootstrap_seed_ledger(seed, replicates)
  records <- list()
  chunks_completed <- 0L
  generation <- 0L
  if (!is.null(checkpoint)) {
    formal_fg_validate_bootstrap_checkpoint(
      checkpoint, replicates, seed, scope, execution, seed_ledger
    )
    if (!is.function(resume_claim) ||
        !isTRUE(resume_claim(checkpoint$checkpoint_sha256, checkpoint$generation))) {
      stop("Bootstrap resume token was not atomically claimed", call. = FALSE)
    }
    records <- checkpoint$records
    chunks_completed <- checkpoint$chunks_completed
    generation <- checkpoint$generation
  }
  completed_before <- length(records)
  pending <- if (completed_before < replicates) {
    seq.int(completed_before + 1L, replicates)
  } else {
    integer()
  }
  chunks <- split(pending, ceiling(seq_along(pending) / execution$chunk_size))
  if (length(chunks) > execution$max_chunks) {
    chunks <- chunks[seq_len(execution$max_chunks)]
  }
  stage <- scope %||% "DATA_SEMANTICS"
  if (is.environment(observer) && !is.null(scope)) {
    formal_fg_record_bootstrap(observer, scope, "RUNNING", completed_before, 0L)
  }
  chunks_this_run <- 0L
  for (chunk in chunks) {
    if (execution$workers == 1L) {
      chunk_records <- lapply(
        chunk,
        function(i) formal_fg_run_bootstrap_replicate(i, seed_ledger[[i]], runner, stage)
      )
    } else {
      chunk_records <- suppressWarnings(parallel::mclapply(
        chunk,
        function(i) formal_fg_run_bootstrap_replicate(i, seed_ledger[[i]], runner, stage),
        mc.cores = execution$workers,
        mc.preschedule = FALSE,
        mc.set.seed = FALSE,
        mc.silent = TRUE
      ))
      for (j in seq_along(chunk_records)) {
        if (inherits(chunk_records[[j]], "try-error") || is.null(chunk_records[[j]])) {
          chunk_records[[j]] <- list(
            replicate_id = as.integer(chunk[[j]]),
            seed = as.list(seed_ledger[[chunk[[j]]]]),
            status = "FAILED",
            error_code = formal_fg_condition_code(simpleError("worker terminated"), stage)
          )
        }
      }
    }
    chunk_records <- chunk_records[order(vapply(chunk_records, `[[`, integer(1), "replicate_id"))]
    records <- c(records, chunk_records)
    chunks_this_run <- chunks_this_run + 1L
    chunks_completed <- chunks_completed + 1L
    generation <- generation + 1L
    failed <- sum(vapply(records, `[[`, character(1), "status") == "FAILED")
    completed <- sum(vapply(records, `[[`, character(1), "status") == "COMPLETE")
    status <- if (failed) {
      "FAILED"
    } else if (completed == replicates) {
      "COMPLETE"
    } else {
      "PARTIAL"
    }
    current <- formal_fg_make_bootstrap_checkpoint(
      status, scope, execution, replicates, seed, records, chunks_completed, generation
    )
    if (is.environment(observer) && !is.null(scope)) {
      first_code <- if (failed) {
        Filter(function(x) identical(x$status, "FAILED"), records)[[1L]]$error_code
      } else {
        NULL
      }
      formal_fg_record_bootstrap(
        observer, scope, if (failed) "FAILED" else "RUNNING",
        completed, failed, first_code
      )
    }
    if (is.function(checkpoint_callback)) checkpoint_callback(current)
    if (failed) break
  }
  failed_records <- Filter(function(x) identical(x$status, "FAILED"), records)
  completed_records <- Filter(function(x) identical(x$status, "COMPLETE"), records)
  completed <- length(completed_records)
  failed <- length(failed_records)
  status <- if (failed) "FAILED" else if (completed == replicates) "COMPLETE" else "PARTIAL"
  final_checkpoint <- formal_fg_make_bootstrap_checkpoint(
    status, scope, execution, replicates, seed, records, chunks_completed, generation
  )
  if (is.environment(observer) && !is.null(scope)) {
    formal_fg_record_bootstrap(
      observer, scope,
      if (failed) "FAILED" else if (completed == replicates) "COMPLETE" else "RUNNING",
      completed, failed,
      if (failed) failed_records[[1L]]$error_code else NULL
    )
  }
  output <- vector("list", replicates)
  for (record in completed_records) output[[record$replicate_id]] <- record$result
  list(
    replicates_requested = as.integer(replicates),
    replicates_completed = as.integer(completed),
    failures = lapply(failed_records, `[[`, "error_code"),
    results = output,
    execution = list(
      status = status,
      workers = execution$workers,
      chunk_size = execution$chunk_size,
      chunks_completed_this_run = chunks_this_run,
      resumed = !is.null(checkpoint),
      rng = "L'Ecuyer-CMRG_REPLICATE_STREAMS"
    ),
    checkpoint = final_checkpoint
  )
}

formal_fg_bootstrap_orchestrate <- function(
    replicates,
    seed,
    runner,
    observer = NULL,
    scope = NULL,
    execution = NULL,
    checkpoint = NULL,
    checkpoint_callback = NULL,
    resume_claim = NULL) {
  if (!is.null(execution)) {
    return(formal_fg_bootstrap_orchestrate_chunked(
      replicates, seed, runner, observer, scope, execution, checkpoint,
      checkpoint_callback, resume_claim
    ))
  }
  if (!is.null(checkpoint) || !is.null(checkpoint_callback) || !is.null(resume_claim)) {
    stop("Bootstrap resume inputs require deterministic execution control", call. = FALSE)
  }
  set.seed(seed)
  output <- vector("list", replicates)
  failures <- character()
  if (is.environment(observer) && !is.null(scope)) {
    formal_fg_record_bootstrap(observer, scope, "RUNNING", 0L, 0L)
  }
  for (i in seq_len(replicates)) {
    output[[i]] <- tryCatch(runner(i), error = function(e) {
      stage <- scope %||% "DATA_SEMANTICS"
      failures <<- c(failures, formal_fg_condition_code(e, stage))
      NULL
    })
  }
  completed <- sum(!vapply(output, is.null, logical(1)))
  if (is.environment(observer) && !is.null(scope)) {
    formal_fg_record_bootstrap(
      observer, scope,
      if (length(failures)) "FAILED" else "COMPLETE",
      completed, length(failures), if (length(failures)) failures[[1L]] else NULL
    )
  }
  list(
    replicates_requested = replicates,
    replicates_completed = completed,
    failures = as.list(failures),
    results = output
  )
}

formal_fg_pool_models <- function(
    imputed,
    analysis,
    predictors,
    shrinkage = 1,
    failure_stage = "PRIMARY_FIT") {
  fits <- vector("list", length(imputed$completed))
  dev_risks <- vector("list", length(fits)); val_risks <- vector("list", length(fits))
  baseline_hazards <- numeric(length(fits))
  for (i in seq_along(fits)) {
    completed <- imputed$completed[[i]]
    expected_df <- if (identical(predictors, c("age", "female"))) {
      3L
    } else {
      analysis$model_plan$parameter_df
    }
    dev_design <- formal_fg_primary_model_step(
      function() {
        formal_fg_design_matrix(
          completed$development,
          predictors = predictors,
          parameter_df = expected_df
        )
      },
      "PRIMARY_FIT_DESIGN_INVALID",
      failure_stage
    )
    val_design <- formal_fg_primary_model_step(
      function() {
        formal_fg_design_matrix(
          completed$validation,
          knots = dev_design$knots,
          predictors = predictors,
          parameter_df = expected_df
        )
      },
      "PRIMARY_FIT_DESIGN_INVALID",
      failure_stage
    )
    fitted <- formal_fg_fit_matrix(
      completed$development,
      dev_design$matrix,
      analysis,
      failure_stage = failure_stage
    )
    fits[[i]] <- fitted
    development_prediction <- formal_fg_predict_fit(
      fitted,
      dev_design$matrix,
      analysis$horizon_hours,
      shrinkage,
      failure_stage = failure_stage
    )
    dev_risks[[i]] <- development_prediction$risk
    val_risks[[i]] <- formal_fg_predict_fit(
      fitted,
      val_design$matrix,
      analysis$horizon_hours,
      shrinkage,
      failure_stage = failure_stage
    )$risk
    baseline_hazards[[i]] <- development_prediction$baseline_subdistribution_hazard
  }
  coefficients <- lapply(fits, function(x) stats::coef(x$fit))
  common <- Reduce(intersect, lapply(coefficients, names))
  pooled_beta <- vapply(common, function(term) mean(vapply(coefficients, `[[`, numeric(1), term)), numeric(1)) * shrinkage
  within <- vapply(common, function(term) mean(vapply(fits, function(x) stats::vcov(x$fit)[term, term], numeric(1))), numeric(1))
  between <- vapply(common, function(term) stats::var(vapply(coefficients, `[[`, numeric(1), term)), numeric(1))
  total <- within + (1 + 1 / length(fits)) * between
  if (!length(common) || any(!is.finite(pooled_beta)) ||
      any(!is.finite(total)) || any(total < 0)) {
    formal_fg_stop("PRIMARY_FIT_VARIANCE_NONFINITE", failure_stage)
  }
  list(
    pooled_coefficients = data.frame(term = common, estimate = pooled_beta, standard_error = sqrt(total)),
    development_risk = Reduce(`+`, dev_risks) / length(dev_risks),
    validation_risk = Reduce(`+`, val_risks) / length(val_risks),
    baseline_subdistribution_hazards = as.list(baseline_hazards),
    pooled_baseline_subdistribution_hazard = mean(baseline_hazards),
    fits = fits
  )
}

formal_fg_run_sensitivities <- function(imputed, analysis, formula_checksum) {
  contract <- formal_temporal_fg_contract_for_analysis(analysis)
  predictors <- unlist(analysis$model_plan$primary_predictors, use.names = FALSE)
  observed_completed <- lapply(imputed$completed, function(x) list(
    development = x$development[x$development[[analysis$outcome_observed]] == 1, , drop = FALSE],
    validation = x$validation[x$validation[[analysis$outcome_observed]] == 1, , drop = FALSE]
  ))
  complete_pool <- formal_fg_pool_models(
    list(completed = observed_completed),
    analysis,
    predictors,
    failure_stage = "SENSITIVITY"
  )

  first <- imputed$completed[[1L]]
  dev_design <- formal_fg_design_matrix(
    first$development,
    predictors = predictors,
    parameter_df = analysis$model_plan$parameter_df
  )
  val_design <- formal_fg_design_matrix(
    first$validation,
    knots = dev_design$knots,
    predictors = predictors,
    parameter_df = analysis$model_plan$parameter_df
  )
  observation_fit <- suppressWarnings(stats::glm(
    first$development[[analysis$outcome_observed]] ~ dev_design$matrix,
    family = stats::binomial()
  ))
  dev_probability <- pmin(pmax(stats::fitted(observation_fit), 0.01), 0.99)
  coefficient <- stats::coef(observation_fit)
  val_probability <- pmin(pmax(stats::plogis(cbind(1, val_design$matrix) %*% coefficient), 0.01), 0.99)
  numerator <- mean(first$development[[analysis$outcome_observed]])
  raw_dev <- ifelse(first$development[[analysis$outcome_observed]] == 1, numerator / dev_probability, 0)
  raw_val <- ifelse(first$validation[[analysis$outcome_observed]] == 1, numerator / val_probability, 0)
  cutpoints <- unname(stats::quantile(raw_dev[raw_dev > 0], c(0.01, 0.99), names = FALSE))
  weight_dev <- ifelse(raw_dev > 0, pmin(pmax(raw_dev, cutpoints[[1L]]), cutpoints[[2L]]), 0)
  weight_val <- ifelse(raw_val > 0, pmin(pmax(raw_val, cutpoints[[1L]]), cutpoints[[2L]]), 0)
  weighted_dev <- first$development[weight_dev > 0, , drop = FALSE]
  weighted_val <- first$validation[weight_val > 0, , drop = FALSE]
  weighted_dev_design <- formal_fg_design_matrix(
    weighted_dev, knots = dev_design$knots, predictors = predictors,
    parameter_df = analysis$model_plan$parameter_df
  )
  weighted_val_design <- formal_fg_design_matrix(
    weighted_val, knots = dev_design$knots, predictors = predictors,
    parameter_df = analysis$model_plan$parameter_df
  )
  weighted_fit <- formal_fg_fit_matrix(
    weighted_dev,
    weighted_dev_design$matrix,
    analysis,
    case_weights = weight_dev[weight_dev > 0],
    failure_stage = "SENSITIVITY"
  )
  weighted_prediction <- formal_fg_predict_fit(
    weighted_fit,
    weighted_val_design$matrix,
    analysis$horizon_hours,
    failure_stage = "SENSITIVITY"
  )$risk
  weighted_metrics <- formal_fg_metrics(
    weighted_val[[analysis$time]], weighted_val[[analysis$event]],
    weighted_val[[analysis$competing_event]], weighted_prediction, analysis$horizon_hours
  )$metrics
  list(
    list(
      sensitivity_id = contract$sensitivity_ids[[1L]], status = "COMPLETE",
      label = "EXPLORATORY", formula_checksum = formula_checksum, may_replace_primary = FALSE,
      model_formula_unchanged = TRUE, imputations = length(observed_completed),
      pooled_coefficient_count = nrow(complete_pool$pooled_coefficients),
      outcome_unobserved_excluded_n = sum(first$development[[analysis$outcome_observed]] == 0) + sum(first$validation[[analysis$outcome_observed]] == 0),
      outcome_unobserved_recoded_negative_n = 0L
    ),
    list(
      sensitivity_id = contract$sensitivity_ids[[2L]], status = "COMPLETE",
      label = "EXPLORATORY", formula_checksum = formula_checksum, may_replace_primary = FALSE,
      model_formula_unchanged = TRUE,
      weighting = "DEVELOPMENT_FITTED_STABILIZED_ASSESSMENT_PROCESS_IPCW",
      truncation_quantiles = list(0.01, 0.99), truncation_cutpoints = as.list(cutpoints),
      development_weight_min = min(weight_dev[weight_dev > 0]), development_weight_max = max(weight_dev),
      validation_weight_min = min(weight_val[weight_val > 0]), validation_weight_max = max(weight_val),
      validation_outcomes_used_for_weight_learning = FALSE,
      validation_metrics = as.list(weighted_metrics)
    )
  )
}

formal_fg_synthetic_bootstrap_verification <- function(data, risk, analysis, plan, scope, observer = NULL) {
  n <- nrow(data)
  calibration_grid <- seq(0.01, 0.99, length.out = 50L)
  metric_names <- names(formal_fg_metrics(data[[analysis$time]], data[[analysis$event]], data[[analysis$competing_event]], risk, analysis$horizon_hours)$metrics)
  runner <- function(i) {
    index <- sample.int(n, n, replace = TRUE)
    evaluated <- formal_fg_metrics(
      data[[analysis$time]][index], data[[analysis$event]][index],
      data[[analysis$competing_event]][index], risk[index], analysis$horizon_hours,
      calibration_grid = calibration_grid
    )
    list(metrics = evaluated$metrics, calibration = evaluated$flexible_curve$calibrated)
  }
  observer_scope <- if (identical(scope, "DEVELOPMENT_FULL_PIPELINE")) "INTERNAL_BOOTSTRAP" else "VALIDATION_BOOTSTRAP"
  boot <- formal_fg_bootstrap_orchestrate(plan$replicates, plan$seed, runner, observer, observer_scope)
  if (boot$replicates_completed != plan$replicates) {
    code <- if (identical(observer_scope, "INTERNAL_BOOTSTRAP")) {
      "INTERNAL_BOOTSTRAP_REPLICATE_FAILED"
    } else {
      "VALIDATION_BOOTSTRAP_REPLICATE_FAILED"
    }
    formal_fg_stop(code, observer_scope)
  }
  completed <- boot$results[!vapply(boot$results, is.null, logical(1))]
  matrix <- do.call(rbind, lapply(completed, `[[`, "metrics"))
  calibration_matrix <- do.call(rbind, lapply(completed, `[[`, "calibration"))
  intervals <- data.frame(
    metric = metric_names,
    ci_low = apply(matrix, 2L, stats::quantile, probs = 0.025, na.rm = TRUE),
    ci_high = apply(matrix, 2L, stats::quantile, probs = 0.975, na.rm = TRUE)
  )
  list(
    scope = scope, replicates_requested = boot$replicates_requested,
    replicates_completed = boot$replicates_completed, failures = boot$failures,
    interval = "PERCENTILE_95_CI", intervals = as_result_rows(intervals),
    flexible_calibration_band = as_result_rows(data.frame(
      predicted = calibration_grid,
      ci_low = apply(calibration_matrix, 2L, stats::quantile, probs = 0.025, na.rm = TRUE),
      ci_high = apply(calibration_matrix, 2L, stats::quantile, probs = 0.975, na.rm = TRUE)
    )),
    verification_profile = if (scope == "DEVELOPMENT_FULL_PIPELINE")
      "SYNTHETIC_ORCHESTRATION_PLUS_SEPARATE_FULL_PIPELINE_SMOKE" else "FIXED_MODEL_NO_REFIT_NO_RECALIBRATION"
  )
}

formal_fg_full_pipeline_internal_bootstrap <- function(development, analysis, apparent_metrics, observer = NULL) {
  predictors <- unlist(analysis$model_plan$primary_predictors, use.names = FALSE)
  n <- nrow(development)
  runner <- function(i) {
    index <- sample.int(n, n, replace = TRUE)
    bootstrap_data <- development[index, , drop = FALSE]
    completed <- formal_fg_multiple_imputation(bootstrap_data, development, analysis)
    fitted <- formal_fg_pool_models(
      completed,
      analysis,
      predictors,
      failure_stage = "INTERNAL_BOOTSTRAP"
    )
    bootstrap_metrics <- formal_fg_metrics(
      bootstrap_data[[analysis$time]], bootstrap_data[[analysis$event]], bootstrap_data[[analysis$competing_event]],
      fitted$development_risk, analysis$horizon_hours
    )$metrics
    test_metrics <- formal_fg_metrics(
      development[[analysis$time]], development[[analysis$event]], development[[analysis$competing_event]],
      fitted$validation_risk, analysis$horizon_hours
    )$metrics
    bootstrap_metrics - test_metrics
  }
  boot <- formal_fg_bootstrap_orchestrate(
    analysis$internal_validation$replicates,
    analysis$internal_validation$seed,
    runner,
    observer,
    "INTERNAL_BOOTSTRAP"
  )
  if (boot$replicates_completed != analysis$internal_validation$replicates) {
    formal_fg_stop("INTERNAL_BOOTSTRAP_REPLICATE_FAILED", "INTERNAL_BOOTSTRAP")
  }
  optimism_matrix <- do.call(rbind, boot$results)
  optimism <- colMeans(optimism_matrix)
  corrected <- apparent_metrics[names(optimism)] - optimism
  list(
    scope = "DEVELOPMENT_FULL_PIPELINE", method = "PATIENT_LEVEL_BOOTSTRAP_FULL_PIPELINE",
    replicates_requested = boot$replicates_requested, replicates_completed = boot$replicates_completed,
    seed = analysis$internal_validation$seed, failures = boot$failures,
    optimism = as.list(optimism), bootstrap_corrected_metrics = as.list(corrected),
    uniform_shrinkage_factor = min(1, max(0, corrected[["CALIBRATION_SLOPE"]])),
    baseline_hazard_reestimated_from = "DEVELOPMENT_ONLY",
    verification_profile = "FULL_40_IMPUTATION_TRANSFORMATION_FIT_PIPELINE"
  )
}

run_formal_temporal_fine_gray_prediction <- function(task, data, output_dir, observer = NULL) {
  if (!is.environment(observer)) observer <- new_formal_fg_execution_observer()
  validate_formal_temporal_fine_gray_task(task)
  analysis <- task$analysis
  predictors <- unlist(analysis$model_plan$primary_predictors, use.names = FALSE)
  if (identical(analysis$execution_mode, "FORMAL") && identical(task$data$dataset_tag, "SYNTHETIC_TEST")) {
    stop("FORMAL execution cannot use a SYNTHETIC_TEST registration", call. = FALSE)
  }
  formal_fg_mark_stage(observer, "DATA_SEMANTICS")
  formal_fg_preflight_data(task, data)
  censoring <- formal_fg_apply_outcome_censoring(data, analysis)
  prepared <- censoring$data
  development <- prepared[prepared[[analysis$split]] == analysis$development_value, , drop = FALSE]
  validation <- prepared[prepared[[analysis$split]] == analysis$validation_value, , drop = FALSE]
  formal_fg_complete_stage(observer, "DATA_SEMANTICS")

  formal_fg_mark_stage(observer, "IMPUTATION")
  imputed <- formal_fg_multiple_imputation(development, validation, analysis)
  formal_fg_complete_stage(observer, "IMPUTATION")

  formal_fg_mark_stage(observer, "PRIMARY_FIT")
  primary <- formal_fg_pool_models(imputed, analysis, predictors)
  baseline <- formal_fg_pool_models(imputed, analysis, c("age", "female"))
  apparent_dev_metrics <- formal_fg_metrics(development[[analysis$time]], development[[analysis$event]], development[[analysis$competing_event]], primary$development_risk, analysis$horizon_hours)
  formal_fg_complete_stage(observer, "PRIMARY_FIT")

  formal_fg_mark_stage(observer, "INTERNAL_BOOTSTRAP")
  internal_bootstrap <- if (identical(analysis$execution_mode, "FORMAL")) {
    formal_fg_full_pipeline_internal_bootstrap(development, analysis, apparent_dev_metrics$metrics, observer)
  } else {
    verified <- formal_fg_synthetic_bootstrap_verification(
      development, primary$development_risk, analysis, analysis$internal_validation,
      "DEVELOPMENT_FULL_PIPELINE", observer
    )
    list(
      scope = "DEVELOPMENT_FULL_PIPELINE", method = "PATIENT_LEVEL_BOOTSTRAP_FULL_PIPELINE",
      replicates_requested = verified$replicates_requested,
      replicates_completed = verified$replicates_completed,
      seed = analysis$internal_validation$seed, failures = verified$failures,
      optimism = as.list(stats::setNames(rep(0, length(apparent_dev_metrics$metrics)), names(apparent_dev_metrics$metrics))),
      bootstrap_corrected_metrics = as.list(apparent_dev_metrics$metrics),
      uniform_shrinkage_factor = min(1, max(0, apparent_dev_metrics$metrics[["CALIBRATION_SLOPE"]])),
      baseline_hazard_reestimated_from = "DEVELOPMENT_ONLY",
      verification_profile = "SYNTHETIC_ORCHESTRATION_PLUS_SEPARATE_FULL_PIPELINE_SMOKE"
    )
  }
  formal_fg_complete_stage(observer, "INTERNAL_BOOTSTRAP")

  formal_fg_mark_stage(observer, "PRIMARY_FIT")
  shrinkage <- internal_bootstrap$uniform_shrinkage_factor
  primary <- formal_fg_pool_models(
    imputed, analysis, predictors, shrinkage = shrinkage
  )
  dev_metrics <- formal_fg_metrics(development[[analysis$time]], development[[analysis$event]], development[[analysis$competing_event]], primary$development_risk, analysis$horizon_hours)
  val_metrics <- formal_fg_metrics(validation[[analysis$time]], validation[[analysis$event]], validation[[analysis$competing_event]], primary$validation_risk, analysis$horizon_hours)
  formal_fg_complete_stage(observer, "PRIMARY_FIT")

  formal_fg_mark_stage(observer, "VALIDATION_BOOTSTRAP")
  validation_bootstrap <- formal_fg_synthetic_bootstrap_verification(
    validation, primary$validation_risk, analysis, analysis$temporal_validation,
    "VALIDATION_ONLY_FIXED_MODEL", observer
  )
  validation_bootstrap$method <- "VALIDATION_ONLY_FIXED_MODEL_PATIENT_BOOTSTRAP"
  validation_bootstrap$seed <- analysis$temporal_validation$seed
  validation_bootstrap$refit <- FALSE
  validation_bootstrap$recalibrate <- FALSE
  validation_bootstrap <- validation_bootstrap[c(
    "scope", "method", "replicates_requested", "replicates_completed", "seed", "failures",
    "interval", "intervals", "flexible_calibration_band", "refit", "recalibrate", "verification_profile"
  )]
  formal_fg_complete_stage(observer, "VALIDATION_BOOTSTRAP")
  gate <- formal_fg_evaluate_calibration_gate(val_metrics$metrics, analysis$calibration_gate)
  dca <- if (gate$all_passed) formal_fg_dca(
    validation[[analysis$time]], validation[[analysis$event]], validation[[analysis$competing_event]],
    primary$validation_risk, unlist(analysis$calibration_gate$thresholds), analysis$horizon_hours
  ) else NULL
  formula_checksum <- digest::digest(paste(primary$pooled_coefficients$term, collapse = "|"), algo = "sha256", serialize = FALSE)
  formal_fg_mark_stage(observer, "SENSITIVITY")
  sensitivities <- formal_fg_run_sensitivities(imputed, analysis, formula_checksum)
  formal_fg_complete_stage(observer, "SENSITIVITY")
  core <- list(
    schema_version = if (identical(task$schema_version, "2.0.0")) {
      "formal-temporal-fine-gray-result@2.0.0"
    } else {
      "formal-temporal-fine-gray-result@1.1.0"
    },
    analysis_id = task$analysis_id, candidate_id = analysis$candidate_id,
    execution_mode = analysis$execution_mode,
    status = if (identical(analysis$execution_mode, "SYNTHETIC_TEST")) "SYNTHETIC_CAPABILITY_VERIFIED" else "COMPLETE",
    aggregate_only = TRUE, patient_level_payload = FALSE, physical_paths_in_result = FALSE,
    checksum_scope = "CANONICAL_STRUCTURED_RESULT_EXCLUDING_STRUCTURED_RESULT_SHA256_FIELD",
    binding = list(
      sap_id = task$binding$sap_id, sap_sha256 = task$binding$sap_sha256,
      dataset_id = task$data$dataset_id, dataset_sha256 = task$data$sha256
    ),
    counts = list(
      input_n = nrow(prepared), development_n = nrow(development), validation_n = nrow(validation),
      development_events = sum(development[[analysis$event]]), validation_events = sum(validation[[analysis$event]]),
      development_competing_events = sum(development[[analysis$competing_event]]),
      validation_competing_events = sum(validation[[analysis$competing_event]]),
      observation = censoring$audit
    ),
    model = list(
      primary_model_id = analysis$model_plan$primary_model_id,
      baseline_model_id = analysis$model_plan$baseline_model_id,
      parameter_df = analysis$model_plan$parameter_df, transformation_map_sha256 = analysis$model_plan$transformation_map_sha256,
      pooled_coefficients = as_result_rows(primary$pooled_coefficients),
      baseline_pooled_coefficients = as_result_rows(baseline$pooled_coefficients),
      uniform_shrinkage_factor = shrinkage, uniform_shrinkage_capped_at_one = shrinkage <= 1,
      baseline_hazard_reestimated_from = "DEVELOPMENT_ONLY",
      pooled_development_baseline_subdistribution_hazard = primary$pooled_baseline_subdistribution_hazard,
      validation_refit = FALSE, validation_recalibration = FALSE, logistic_substitution = FALSE
    ),
    imputation = imputed$diagnostics,
    internal_validation = internal_bootstrap,
    temporal_validation = validation_bootstrap,
    performance = list(
      development = as.list(dev_metrics$metrics), validation = as.list(val_metrics$metrics),
      flexible_calibration_curve = as_result_rows(val_metrics$flexible_curve),
      flexible_calibration_band = validation_bootstrap$flexible_calibration_band,
      decile_calibration = as_result_rows(val_metrics$decile)
    ),
    calibration_gate = gate,
    decision_curve = if (gate$all_passed) list(status = "GENERATED", rows = as_result_rows(dca)) else list(status = "NOT_GENERATED_GATE_FAILED", rows = list()),
    clinical_utility_claim_allowed = gate$clinical_utility_claim_allowed,
    sensitivities = sensitivities,
    expected_output_ids = analysis$expected_output_ids,
    prohibited_actions_observed = list()
  )
  core$structured_result_sha256 <- digest::digest(
    jsonlite::toJSON(core, auto_unbox = TRUE, null = "null", digits = NA),
    algo = "sha256", serialize = FALSE
  )
  core
}

write_formal_temporal_fg_bundle <- function(result, output_dir) {
  # No output path is created until both registered runtime contracts pass.
  validate_registered_result_contract(result)
  metrics <- data.frame(
    partition = rep(c("development", "validation"), each = length(result$performance$development)),
    metric = rep(names(result$performance$development), 2L),
    estimate = c(unlist(result$performance$development), unlist(result$performance$validation))
  )
  tables <- list(
    "TABLE.CVCC-PRED-ISO-001.MAIN.1" = data.frame(section = names(result$counts), value = vapply(result$counts, function(x) if (length(x) == 1L) as.character(x) else "STRUCTURED_SUPPLEMENT", character(1))),
    "TABLE.CVCC-PRED-ISO-001.MAIN.2" = data.frame(item = c("imputations", "iterations", "validation_outcome_access_count"), value = c(result$imputation$m, result$imputation$iterations, result$imputation$validation_outcome_access_count)),
    "TABLE.CVCC-PRED-ISO-001.MAIN.3" = metrics
  )
  expected <- unlist(result$expected_output_ids, use.names = FALSE)
  artifact_by_id <- list()
  for (id in names(tables)) {
    filename <- paste0(gsub("[^A-Za-z0-9.-]", "_", id), ".csv")
    artifact_by_id[[id]] <- list(output_id = id, filename = filename, source_result_sha256 = result$structured_result_sha256, aggregate_only = TRUE)
  }
  supplements <- expected[grepl("^SUPPLEMENT", expected)]
  for (id in supplements) {
    filename <- paste0(gsub("[^A-Za-z0-9.-]", "_", id), ".json")
    artifact_by_id[[id]] <- list(output_id = id, filename = filename, source_result_sha256 = result$structured_result_sha256, aggregate_only = TRUE)
  }
  figure_ids <- expected[grepl("^FIGURE", expected)]
  for (id in figure_ids) {
    conditional_dca <- identical(id, "FIGURE.CVCC-PRED-ISO-001.MAIN.5")
    if (conditional_dca && !identical(result$decision_curve$status, "GENERATED")) {
      artifact_by_id[[id]] <- list(output_id = id, status = "NOT_GENERATED_GATE_FAILED", source_result_sha256 = result$structured_result_sha256, aggregate_only = TRUE)
      next
    }
    filename <- paste0(gsub("[^A-Za-z0-9.-]", "_", id), ".png")
    artifact_by_id[[id]] <- list(output_id = id, filename = filename, source_result_sha256 = result$structured_result_sha256, aggregate_only = TRUE)
  }
  artifact_by_id[["RESULT.CVCC-PRED-ISO-001.STRUCTURED.V1"]] <- list(
    output_id = "RESULT.CVCC-PRED-ISO-001.STRUCTURED.V1", filename = "structured_result.json",
    source_result_sha256 = result$structured_result_sha256, aggregate_only = TRUE
  )
  manifest <- list(
    schema_version = .formal_temporal_fg_manifest_version,
    source_result_sha256 = result$structured_result_sha256,
    artifacts = unname(artifact_by_id[expected])
  )
  validate_registered_result_contract(manifest)
  validate_formal_temporal_fine_gray_output_manifest(manifest, result)

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(result, file.path(output_dir, "structured_result.json"), auto_unbox = TRUE, pretty = TRUE, null = "null", digits = NA)
  for (id in names(tables)) {
    utils::write.csv(tables[[id]], file.path(output_dir, artifact_by_id[[id]]$filename), row.names = FALSE)
  }
  for (id in supplements) {
    jsonlite::write_json(
      list(output_id = id, source_result_sha256 = result$structured_result_sha256, aggregate_only = TRUE),
      file.path(output_dir, artifact_by_id[[id]]$filename), auto_unbox = TRUE, pretty = TRUE
    )
  }
  for (id in figure_ids) {
    if (identical(id, "FIGURE.CVCC-PRED-ISO-001.MAIN.5") && !identical(result$decision_curve$status, "GENERATED")) next
    filename <- artifact_by_id[[id]]$filename
    grDevices::png(file.path(output_dir, filename), width = 1800, height = 1200, res = 200)
    if (identical(id, "FIGURE.CVCC-PRED-ISO-001.MAIN.1")) {
      values <- unlist(result$counts[c("development_n", "validation_n")])
      graphics::barplot(values, names.arg = c("Development", "Validation"), ylab = "Patients", main = "Patient-isolated anchor-era cohorts", col = c("#2C6EAA", "#E07A5F"))
    } else if (identical(id, "FIGURE.CVCC-PRED-ISO-001.MAIN.2")) {
      values <- unlist(result$performance$validation[c("TIME_DEPENDENT_AUC_AT_84H", "IPCW_BRIER_AT_84H", "SCALED_BRIER_VS_NULL")])
      graphics::barplot(values, names.arg = c("AUC", "Brier", "Scaled Brier"), ylim = range(c(0, values), finite = TRUE), main = "Held-out 84-hour performance", col = "#2C6EAA")
    } else if (identical(id, "FIGURE.CVCC-PRED-ISO-001.MAIN.3")) {
      curve <- do.call(rbind, lapply(result$performance$flexible_calibration_curve, as.data.frame))
      graphics::plot(curve$predicted, curve$calibrated, xlim = c(0, 1), ylim = c(0, 1), xlab = "Predicted risk", ylab = "Flexible calibrated risk", main = "Held-out calibration", col = "#2C6EAA")
      graphics::abline(0, 1, lty = 2, col = "gray40")
    } else if (identical(id, "FIGURE.CVCC-PRED-ISO-001.MAIN.4")) {
      coefficients <- do.call(rbind, lapply(result$model$pooled_coefficients, as.data.frame))
      graphics::dotchart(
        coefficients$estimate, labels = coefficients$term,
        xlab = "Uniformly shrunken coefficient",
        main = sprintf("Frozen %d-df Fine-Gray model", result$model$parameter_df)
      )
      graphics::abline(v = 0, lty = 2, col = "gray40")
    } else {
      dca <- do.call(rbind, lapply(result$decision_curve$rows, as.data.frame))
      graphics::plot(dca$threshold, dca$net_benefit, type = "b", xlab = "Threshold", ylab = "Net benefit", main = "Calibration-gated competing-risk DCA", col = "#2C6EAA")
      graphics::abline(h = 0, lty = 2, col = "gray40")
    }
    grDevices::dev.off()
  }
  jsonlite::write_json(
    manifest,
    file.path(output_dir, "output_manifest.json"), auto_unbox = TRUE, pretty = TRUE, null = "null"
  )
  invisible(result)
}
