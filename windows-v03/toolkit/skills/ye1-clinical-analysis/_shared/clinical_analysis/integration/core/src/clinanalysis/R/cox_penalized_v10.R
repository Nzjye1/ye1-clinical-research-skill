# Sole v0.10 Cox penalized numerical owner. Installed glmnet estimates slopes;
# survival supplies an offset-only Breslow baseline. No fallback or refitting.
# Reuse the unchanged v0.8 training preprocessing and local-control helpers.

cox_penalized_v10_need <- function(ok, code, ...) penalized_v08_need(ok, paste0("COX_PENALIZED_", code), ...)
cox_penalized_v10_method <- function(spec) paste0("prediction.survival.cox.",
  if (isTRUE(identical(as.numeric(spec$alpha), 1))) "lasso" else "elasticnet")
cox_penalized_v10_source <- function() list(coefficient_owner = "glmnet::glmnet",
  baseline_owner = "survival::coxph_offset_and_survfit", preprocessing_owner = "penalized_v08_prepare")
cox_penalized_v10_solver <- function() {
  s <- penalized_v08_solver()
  s[c("type_gaussian", "type_logistic")] <- NULL
  s$intercept <- "none"; s$family <- "cox"; s$cox_ties <- "breslow"
  s
}
cox_penalized_v10_runtime <- function() {
  r <- penalized_v08_runtime()
  cox_penalized_v10_need(requireNamespace("survival", quietly = TRUE), "ENGINE_UNAVAILABLE")
  r$survival <- as.character(utils::packageVersion("survival"))
  cox_penalized_v10_need(identical(r$survival, "3.8.6"), "ENGINE_VERSION_MISMATCH")
  r
}
cox_penalized_v10_empty_individual <- function() data.frame(subject_id = character(), group_id = character(),
  partition = character(), fold = integer(), duration = double(), event = double(), linear_predictor = double(),
  centered_linear_predictor = double(), horizon = double(), survival = double(), risk = double(), stringsAsFactors = FALSE)
cox_penalized_v10_empty_record <- function(options, semantics, n_input = 0L) {
  spec <- options$spec
  list(method_id = cox_penalized_v10_method(spec), operation = options$operation, status = "unavailable", reason_code = "NOT_RUN",
    family = "cox", penalty = if (isTRUE(spec$alpha == 1)) "lasso" else "elasticnet", alpha = spec$alpha,
    selected_lambda = NA_real_, selected_engine_lambda = NA_real_, selected_lambda_index = NA_integer_,
    coefficient_scale = "standardized_x_log_relative_hazard", prediction_scale = "cumulative_event_probability", semantics = semantics,
    flow = list(n_input = as.integer(n_input), n_training = NA_integer_, n_holdout = NA_integer_, n_predicted = 0L,
      n_cv_folds = 0L, n_features = length(spec$features), n_encoded_columns = NA_integer_, n_dropped_columns = NA_integer_,
      n_training_events = NA_integer_, n_training_censored = NA_integer_, n_holdout_events = NA_integer_, n_holdout_censored = NA_integer_,
      missing_duration_n = NA_integer_, missing_event_n = NA_integer_), preprocessing = list(),
    cv = list(status = "not_run", reason_code = "NOT_RUN", selection_rule = "min_deviance_per_event_largest_lambda_tie",
      loss_name = "heldout_only_breslow_partial_likelihood_deviance", weighting = "validation_event_count", scope = "training_only_tuning",
      rows = list(), folds = list(), fold_losses = list()), path = list(), coefficients = list(),
    baseline = list(method = "offset_only_breslow", reference_center = NA_real_, event_time_count = NA_integer_, last_event_time = NA_real_,
      max_followup = NA_real_, time_unit = spec$survival$time_unit, ties = "breslow", event_boundary = "event_at_t_included", coefficient_updates = 0L),
    horizons = list(), diagnostics = list(stage = "input", fold = NA_integer_, feature = NULL, code = "NOT_RUN", warning_count = 0L,
      jerr = NA_integer_, n_engine_fits = 0L, solver = cox_penalized_v10_solver()), limitations = as.list(c("SYNTHETIC_ENGINEERING_ONLY",
      "CV_IS_TUNING_NOT_EXTERNAL_PERFORMANCE", "HELDOUT_ONLY_EVENT_WEIGHTED_CV_NOT_GROUPED_CV", "ENGINEERING_SUPPORT_NOT_SAMPLE_SIZE_JUSTIFICATION",
      "NO_COEFFICIENT_OR_POSTSELECTION_INFERENCE", "NO_CAUSAL_CLAIM", "NO_CLINICAL_VALIDATION", "NO_FORMAL_PH_TEST_OR_IPCW_ADAPTER",
      "NO_V09_SHAP_OR_NOMOGRAM_ADAPTER", "PRESPECIFIED_SINGLE_ALPHA_AND_LAMBDA_GRID", "STRICT_OBSERVED_CATEGORY_SUPPORT",
      "NO_EXTRAPOLATION_BEYOND_TRAINING_FOLLOWUP")))
}
cox_penalized_v10_row_shapes <- function() {
  v <- penalized_v08_row_shapes()
  list(preprocessing = v$preprocessing,
    cv_row = list(lambda_index = 1L, lambda = 1, deviance_sum = 0, validation_events = 3L, deviance_per_event = 0, selected = TRUE),
    cv_fold = list(fold = 1L, n_training = 16L, n_validation = 6L, training_events = 8L, training_censored = 8L,
      validation_events = 3L, validation_censored = 3L, n_encoded_columns = 2L, n_dropped_columns = 0L,
      dropped_columns = list(), jerr = 0L, warning_count = 0L),
    cv_fold_loss = list(fold = 1L, lambda_index = 1L, lambda = 1, engine_lambda = 1, deviance_sum = 0, validation_events = 3L, deviance_per_event = 0),
    coefficient = list(term = "X0001", feature = "x", type = "number", level = NULL, coefficient = 0, nonzero = FALSE, source = "training"),
    path = list(lambda_index = 1L, lambda = 1, engine_lambda = 1, term = "X0001", feature = "x", type = "number", level = NULL,
      coefficient = 0, nonzero = FALSE),
    horizon = list(population = "holdout", horizon = 0, time_unit = "day", n_predicted = 1L, min_risk = 0, max_risk = 0, mean_risk = 0))
}

cox_penalized_v10_validate <- function(data, options, semantics, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, cox_penalized_v10_method(options$spec))
  need <- cox_penalized_v10_need; keys <- penalized_v08_keys; number <- penalized_v08_number; string <- penalized_v08_string
  need(keys(options, c("operation", "spec", "model_ref", "unknown_category_policy")), "OPTIONS_INVALID")
  need(is.character(options$operation) && length(options$operation) == 1L && options$operation %in% c("train", "infer") &&
    identical(options$unknown_category_policy, "reject"), "OPTIONS_INVALID")
  spec <- options$spec
  need(keys(spec, c("id", "duration", "event", "alpha", "lambda_grid", "features", "split", "selection_rule", "missing", "standardization",
    "cohort_id", "canonical_identity_namespace", "survival", "horizons")), "SPEC_INVALID")
  need(all(vapply(spec[c("id", "duration", "event", "cohort_id", "canonical_identity_namespace")], string, TRUE)) &&
    number(spec$alpha) && spec$alpha > 0 && spec$alpha <= 1, "SPEC_INVALID")
  need((is.list(spec$lambda_grid) || is.numeric(spec$lambda_grid)) && length(spec$lambda_grid) >= 2L && length(spec$lambda_grid) <= 30L &&
    all(vapply(as.list(spec$lambda_grid), number, TRUE)), "LAMBDA_GRID_INVALID")
  lambdas <- penalized_v08_vector(spec$lambda_grid)
  need(all(lambdas > 0) && all(diff(lambdas) < 0), "LAMBDA_GRID_INVALID")
  need(identical(spec$selection_rule, "min_deviance_per_event_largest_lambda_tie") && identical(spec$missing, "training_median_mode") &&
    identical(spec$standardization, "training_population_sd"), "SPEC_UNSUPPORTED")
  s <- spec$survival
  need(keys(s, c("outcome_type", "time_unit", "time_zero_definition", "event_definition", "censoring_definition", "event_code", "censor_code", "ties")) &&
    identical(s$outcome_type, "single_event_right_censored") && is.character(s$time_unit) && length(s$time_unit) == 1L && s$time_unit %in% c("day", "hour") &&
    all(vapply(s[c("time_zero_definition", "event_definition", "censoring_definition")], string, TRUE)) && number(s$event_code) && s$event_code == 1 &&
    number(s$censor_code) && s$censor_code == 0 && identical(s$ties, "breslow"), "SURVIVAL_SEMANTICS_UNSUPPORTED")
  need((is.list(spec$horizons) || is.numeric(spec$horizons)) && length(spec$horizons) >= 1L && length(spec$horizons) <= 8L &&
    all(vapply(as.list(spec$horizons), number, TRUE)), "HORIZONS_INVALID")
  horizons <- penalized_v08_vector(spec$horizons)
  need(all(horizons >= 0) && all(diff(horizons) > 0), "HORIZONS_INVALID")
  split <- spec$split
  need(keys(split, c("method", "partition_field", "fold_field", "group_field", "training_value", "holdout_value", "cv_folds")) &&
    is.character(split$method) && length(split$method) == 1L && split$method %in% c("prespecified_patient", "prespecified_group") &&
    string(split$partition_field) && string(split$fold_field) && identical(split$training_value, "train") && identical(split$holdout_value, "holdout") &&
    number(split$cv_folds) && split$cv_folds %in% 3:5, "SPLIT_INVALID")
  need(if (split$method == "prespecified_group") string(split$group_field) else is.null(split$group_field), "SPLIT_INVALID")
  need(is.list(spec$features) && length(spec$features) >= 1L && length(spec$features) <= 12L && all(vapply(spec$features, function(f)
    keys(f, c("name", "type")) && string(f$name) && is.character(f$type) && length(f$type) == 1L && f$type %in% c("number", "category"), TRUE)), "FEATURES_INVALID")
  features <- vapply(spec$features, `[[`, "", "name")
  protected <- c(spec$id, spec$duration, spec$event, split$partition_field, split$fold_field, split$group_field)
  need(!anyDuplicated(protected) && !anyDuplicated(features) && !any(features %in% protected), "FORBIDDEN_OR_DUPLICATE_FEATURE")
  need(keys(semantics, c("identity", "features", "duration", "event", "time", "survival")) &&
    identical(semantics$identity$subject_id, spec$id) && identical(semantics$identity$group_id, split$group_field) &&
    identical(semantics$identity$canonical_identity_namespace, spec$canonical_identity_namespace) &&
    length(semantics$features) == length(spec$features) && identical(vapply(semantics$features, `[[`, "", "name"), features) &&
    identical(semantics$duration$name, spec$duration) && identical(semantics$event$name, spec$event) &&
    penalized_v08_equal(semantics$survival, s), "SEMANTICS_INVALID")
  need(identical(semantics$duration$unit, s$time_unit) && identical(semantics$event$type, "time_to_event") &&
    identical(semantics$event$definition, s$event_definition) && number(semantics$event$event) && semantics$event$event == 1 &&
    number(semantics$event$non_event) && semantics$event$non_event == 0 && identical(semantics$time$delayed_entry, FALSE) &&
    number(semantics$time$index) && semantics$time$index == 0 && number(semantics$time$feature_cutoff) && semantics$time$feature_cutoff <= 0,
    "SURVIVAL_SEMANTICS_UNSUPPORTED")
  need(is.data.frame(data) && nrow(data) >= 1L && !anyDuplicated(names(data)), "DATA_INVALID")
  clinical_resource_check_rows(nrow(data), budget)
  declared_columns <- sum(vapply(semantics$features, function(f)
    if (identical(f$dtype, "number")) 1 else max(1, length(f$levels) - 1L), 0))
  clinical_resource_check_design(nrow(data), declared_columns, budget)
  required <- c(spec$id, features, split$partition_field, split$fold_field, split$group_field,
    if (options$operation == "train") c(spec$duration, spec$event) else character())
  need(all(required %in% names(data)), "REQUIRED_COLUMN_ABSENT")
  ids <- data[[spec$id]]
  need(is.character(ids) && !anyNA(ids) && all(nzchar(trimws(ids))) && all(validUTF8(enc2utf8(ids))) && !anyDuplicated(ids), "UNIQUE_STRING_IDS_REQUIRED")
  partitions <- data[[split$partition_field]]; folds <- data[[split$fold_field]]; train <- partitions == "train"
  need(is.character(partitions) && !anyNA(partitions) && all(partitions %in% c("train", "holdout")) &&
    is.numeric(folds) && !is.complex(folds) && !anyNA(folds) && all(is.finite(folds)) && all(folds == floor(folds)), "PARTITION_OR_FOLD_INVALID")
  if (options$operation == "train") need(is.null(options$model_ref) && any(train) && any(!train) &&
    all(folds[train] %in% seq_len(split$cv_folds)) && setequal(unique(folds[train]), seq_len(split$cv_folds)) && all(folds[!train] == 0), "PARTITION_OR_FOLD_INVALID")
  else need(keys(options$model_ref, c("local_ref", "content_hash")) && string(options$model_ref$local_ref) &&
    string(options$model_ref$content_hash) && grepl("^[a-f0-9]{64}$", options$model_ref$content_hash) && !any(train) && all(folds == 0), "EXTERNAL_PARTITION_REQUIRED")
  if (!is.null(split$group_field)) {
    groups <- data[[split$group_field]]
    need(is.character(groups) && !anyNA(groups) && all(nzchar(trimws(groups))) && all(validUTF8(enc2utf8(groups))), "GROUP_IDS_REQUIRED")
    for (g in unique(groups)) need(length(unique(partitions[groups == g])) == 1L && length(unique(folds[groups == g])) == 1L, "GROUP_PARTITION_OR_FOLD_LEAKAGE")
  }
  if (options$operation == "train") {
    duration <- data[[spec$duration]]; event <- data[[spec$event]]
    need(is.numeric(duration) && !is.complex(duration) && !anyNA(duration) && all(is.finite(duration)) && all(duration > 0), "POSITIVE_FINITE_DURATION_REQUIRED")
    need(is.numeric(event) && !is.complex(event) && !anyNA(event) && all(is.finite(event)) && all(event %in% c(0, 1)), "BINARY_EVENT_REQUIRED")
    need(all(horizons <= max(duration[train])), "HORIZON_OUTSIDE_TRAINING_SUPPORT")
  }
  for (i in seq_along(spec$features)) {
    f <- spec$features[[i]]; x <- data[[f$name]]
    if (f$type == "number") need(is.numeric(x) && !is.complex(x) && !any(is.nan(x)) && all(is.finite(x[!is.na(x)])), "NUMERIC_FEATURE_INVALID", feature = f$name)
    else {
      need(is.character(x) || is.factor(x), "CATEGORY_FEATURE_INVALID", feature = f$name)
      x <- as.character(x); present <- !is.na(x) & x != ""
      levels <- penalized_v08_vector(semantics$features[[i]]$levels)
      need(length(levels) >= 1L && all(x[present] %in% levels), "UNDECLARED_CATEGORY", feature = f$name)
    }
  }
  invisible(TRUE)
}

cox_penalized_v10_riskset_support <- function(x, duration, event, minimum) {
  cox_penalized_v10_need(sum(event) >= minimum, if (minimum == 8L) "FITTING_EVENTS_BELOW_EIGHT" else "VALIDATION_EVENTS_BELOW_THREE")
  informative <- any(vapply(sort(unique(duration[event == 1])), function(t) {
    risk <- x[duration >= t, , drop = FALSE]
    nrow(risk) >= 2L && any(vapply(seq_len(ncol(risk)), function(j) any(risk[, j] != risk[1L, j]), TRUE))
  }, TRUE))
  cox_penalized_v10_need(informative, "NO_INFORMATIVE_RISK_SET_CONTRAST")
  invisible(TRUE)
}
cox_penalized_v10_extract_path <- function(fit, lambdas, n_columns, warning_count = 0L) {
  need <- cox_penalized_v10_need
  need(warning_count == 0L, "GLMNET_WARNING", jerr = fit$jerr, warning_count = warning_count)
  need(is.numeric(fit$jerr) && length(fit$jerr) == 1L && is.finite(fit$jerr) && fit$jerr == 0, "GLMNET_JERR", jerr = fit$jerr)
  returned <- fit$lambda
  need(length(returned) == length(lambdas) && all(is.finite(returned)) && all(returned > 0) && all(diff(returned) < 0) &&
    all(abs(returned - lambdas) <= 32 * .Machine$double.eps * abs(lambdas)), "REQUESTED_LAMBDA_PATH_MISSING")
  coefficients <- as.matrix(fit$beta)
  need(identical(dim(coefficients), c(as.integer(n_columns), length(lambdas))) && all(is.finite(coefficients)) && is.null(fit$a0), "NONFINITE_COEFFICIENTS")
  list(coefficients = coefficients, engine_lambda = returned, jerr = 0L, warning_count = 0L)
}
cox_penalized_v10_fit <- function(x, duration, event, alpha, lambdas) {
  cox_penalized_v10_riskset_support(x, duration, event, 8L)
  warnings <- character(); control <- penalized_v08_control(ncol(x))
  fit <- tryCatch(withCallingHandlers(glmnet::glmnet(x = x, y = survival::Surv(duration, event), family = "cox", alpha = alpha,
    lambda = lambdas, standardize = FALSE, penalty.factor = rep(1, ncol(x)), relax = FALSE, cox.ties = "breslow", control = control),
    warning = function(w) { warnings <<- c(warnings, conditionMessage(w)); invokeRestart("muffleWarning") }),
    error = function(e) cox_penalized_v10_need(FALSE, "GLMNET_ERROR", warning_count = length(warnings)))
  c(cox_penalized_v10_extract_path(fit, lambdas, ncol(x), length(warnings)), list(control = control))
}
cox_penalized_v10_deviance <- function(x, coefficients, duration, event) {
  cox_penalized_v10_riskset_support(x, duration, event, 3L)
  eta <- x %*% coefficients
  cox_penalized_v10_need(all(is.finite(eta)), "NONFINITE_LINEAR_PREDICTOR")
  warnings <- character()
  loss <- tryCatch(withCallingHandlers(glmnet::coxnet.deviance(pred = eta, y = survival::Surv(duration, event),
    cox.ties = "breslow", std.weights = FALSE), warning = function(w) {warnings <<- c(warnings, conditionMessage(w)); invokeRestart("muffleWarning")}),
    error = function(e) cox_penalized_v10_need(FALSE, "DEVIANCE_ERROR", warning_count = length(warnings)))
  cox_penalized_v10_need(!length(warnings), "DEVIANCE_WARNING", warning_count = length(warnings))
  cox_penalized_v10_need(is.numeric(loss) && length(loss) == ncol(coefficients) && all(is.finite(loss)) && all(loss >= 0), "NONFINITE_OR_INVALID_DEVIANCE")
  as.numeric(loss)
}
cox_penalized_v10_baseline <- function(duration, event, eta) {
  need <- cox_penalized_v10_need
  need(all(is.finite(eta)), "NONFINITE_LINEAR_PREDICTOR")
  center <- mean(eta); q <- eta - center
  need(is.finite(center) && all(is.finite(q)) && all(is.finite(exp(q))) && all(exp(q) > 0), "BASELINE_RELATIVE_HAZARD_OUTSIDE_NUMERIC_SUPPORT")
  d <- data.frame(duration = duration, event = event, q = q)
  warnings <- character()
  result <- tryCatch(withCallingHandlers({
    fit <- survival::coxph(survival::Surv(duration, event) ~ offset(q), data = d, ties = "breslow", model = TRUE,
      control = survival::coxph.control(iter.max = 0L, timefix = FALSE))
    need(length(stats::coef(fit)) == 0L && (is.null(fit$iter) || all(fit$iter == 0)), "BASELINE_COEFFICIENT_REFIT_FORBIDDEN")
    survival::survfit(fit, newdata = data.frame(q = 0), stype = 2L, ctype = 1L, se.fit = FALSE, censor = FALSE)
  }, warning = function(w) { warnings <<- c(warnings, conditionMessage(w)); invokeRestart("muffleWarning") }),
    error = function(e) {if (inherits(e, "penalized_v08_blocked")) stop(e); need(FALSE, "BASELINE_ERROR", warning_count = length(warnings))})
  need(!length(warnings), "BASELINE_WARNING", warning_count = length(warnings))
  times <- as.numeric(result$time); hazard <- as.numeric(result$cumhaz)
  expected <- sort(unique(duration[event == 1]))
  need(length(times) == length(expected) && all(times == expected) && length(hazard) == length(times) && all(is.finite(hazard)) &&
    all(hazard > 0) && all(diff(hazard) > 0), "BASELINE_INVALID")
  list(method = "offset_only_breslow", center = center, event_times = as.list(times), cumulative_hazard = as.list(hazard),
    ties = "breslow", event_boundary = "event_at_t_included", coefficient_updates = 0L)
}
cox_penalized_v10_predict <- function(x, coefficients, baseline, horizons) {
  eta <- as.numeric(x %*% coefficients); q <- eta - baseline$center
  cox_penalized_v10_need(all(is.finite(eta)) && all(is.finite(q)), "NONFINITE_LINEAR_PREDICTOR")
  times <- penalized_v08_vector(baseline$event_times); hazards <- penalized_v08_vector(baseline$cumulative_hazard)
  # findInterval is right-continuous: an event exactly at a horizon is included.
  h <- c(0, hazards)[findInterval(horizons, times) + 1L]
  risk <- survival <- matrix(0, nrow(x), length(horizons))
  for (k in seq_along(horizons)) {
    if (h[[k]] == 0) {survival[, k] <- 1; next}
    log_hazard <- log(h[[k]]) + q
    cumulative <- exp(pmin(log_hazard, log(.Machine$double.xmax)))
    cumulative[log_hazard > log(.Machine$double.xmax)] <- Inf
    survival[, k] <- exp(-cumulative)
    risk[, k] <- -expm1(-cumulative)
  }
  cox_penalized_v10_need(all(is.finite(risk)) && all(is.finite(survival)) && all(risk >= 0 & risk <= 1) &&
    all(survival >= 0 & survival <= 1), "INVALID_RISK_PREDICTION")
  list(linear_predictor = eta, centered_linear_predictor = q, survival = survival, risk = risk)
}

cox_penalized_v10_validate_preprocessor <- function(pp, spec, semantics) {
  need <- function(x) cox_penalized_v10_need(x, "FROZEN_PREPROCESSOR_INVALID")
  keys <- penalized_v08_keys; number <- penalized_v08_number; string <- penalized_v08_string
  need(keys(pp, c("features", "columns", "dropped_columns")) && is.list(pp$features) && length(pp$features) == length(spec$features) &&
    is.list(pp$columns) && length(pp$columns) >= 2L && length(pp$columns) <= 60L && is.list(pp$dropped_columns))
  expected <- list()
  for (i in seq_along(spec$features)) {
    f <- pp$features[[i]]; declared <- spec$features[[i]]
    need(keys(f, c("name", "type", "impute", "levels", "reference")) && identical(f$name, declared$name) && identical(f$type, declared$type))
    if (f$type == "number") {
      need(number(f$impute) && is.list(f$levels) && !length(f$levels) && is.null(f$reference))
      expected[[length(expected) + 1L]] <- list(term = sprintf("X%04d", i), feature = f$name, type = f$type, level = NULL)
    } else {
      need(is.list(f$levels) && length(f$levels) >= 1L && all(vapply(f$levels, string, TRUE)))
      levels <- penalized_v08_vector(f$levels)
      need(!anyDuplicated(levels) && identical(levels, penalized_v08_sort(levels)) && identical(f$reference, levels[[1L]]) &&
        string(f$impute) && f$impute %in% levels && all(levels %in% penalized_v08_vector(semantics$features[[i]]$levels)))
      for (j in seq_along(levels[-1L])) expected[[length(expected) + 1L]] <- list(term = sprintf("X%04dL%04d", i, j + 1L),
        feature = f$name, type = f$type, level = levels[[j + 1L]])
    }
  }
  all_columns <- c(pp$columns, pp$dropped_columns)
  need(length(all_columns) == length(expected) && length(all_columns) <= 60L)
  expected_terms <- vapply(expected, `[[`, "", "term"); observed_terms <- vapply(all_columns, `[[`, "", "term")
  need(!anyDuplicated(observed_terms) && setequal(observed_terms, expected_terms))
  for (column in pp$columns) need(keys(column, c("term", "feature", "type", "level", "center", "scale")) &&
    number(column$center) && number(column$scale) && column$scale > 0 &&
    penalized_v08_equal(column[c("term", "feature", "type", "level")], expected[[match(column$term, expected_terms)]]))
  need(identical(vapply(pp$columns, `[[`, "", "term"), expected_terms[expected_terms %in% vapply(pp$columns, `[[`, "", "term")]))
  for (column in pp$dropped_columns) need(keys(column, c("term", "feature", "type", "level", "reason_code")) &&
    identical(column$reason_code, "ZERO_VARIANCE") && penalized_v08_equal(column[c("term", "feature", "type", "level")], expected[[match(column$term, expected_terms)]]))
  invisible(TRUE)
}
cox_penalized_v10_validate_cv <- function(cv, spec, support, selected) {
  need <- function(x) cox_penalized_v10_need(x, "FROZEN_CV_INVALID")
  keys <- penalized_v08_keys; number <- penalized_v08_number
  integer <- function(x, minimum = 0L) number(x) && x == floor(x) && x >= minimum
  template <- cox_penalized_v10_empty_record(list(operation = "train", spec = spec), list())$cv
  need(keys(cv, names(template)) && identical(cv$status, "completed") && is.null(cv$reason_code) &&
    penalized_v08_equal(cv[c("selection_rule", "loss_name", "weighting", "scope")], template[c("selection_rule", "loss_name", "weighting", "scope")]))
  lambdas <- penalized_v08_vector(spec$lambda_grid); folds <- spec$split$cv_folds; shapes <- cox_penalized_v10_row_shapes()
  need(is.list(cv$rows) && length(cv$rows) == length(lambdas) && is.list(cv$folds) && length(cv$folds) == folds &&
    is.list(cv$fold_losses) && length(cv$fold_losses) == folds * length(lambdas))
  totals <- numeric(length(lambdas)); total_events <- 0L; total_n <- 0L
  for (j in seq_len(folds)) {
    f <- cv$folds[[j]]
    need(keys(f, names(shapes$cv_fold)) && f$fold == j && integer(f$n_training, 8L) && integer(f$n_validation, 3L) &&
      integer(f$training_events, 8L) && integer(f$validation_events, 3L) && integer(f$training_censored) && integer(f$validation_censored) &&
      f$training_events + f$training_censored == f$n_training && f$validation_events + f$validation_censored == f$n_validation &&
      f$n_training + f$n_validation == support$n_training && f$training_events + f$validation_events == support$events &&
      integer(f$n_encoded_columns, 2L) && f$n_encoded_columns <= 60L && integer(f$n_dropped_columns) &&
      is.list(f$dropped_columns) && length(f$dropped_columns) == f$n_dropped_columns && f$jerr == 0 && f$warning_count == 0)
    for (drop in f$dropped_columns) need(keys(drop, c("term", "feature", "type", "level", "reason_code")) && identical(drop$reason_code, "ZERO_VARIANCE"))
    total_events <- total_events + f$validation_events; total_n <- total_n + f$n_validation
    for (k in seq_along(lambdas)) {
      l <- cv$fold_losses[[(j - 1L) * length(lambdas) + k]]
      need(keys(l, names(shapes$cv_fold_loss)) && l$fold == j && l$lambda_index == k && number(l$lambda) && l$lambda == lambdas[[k]] &&
        number(l$engine_lambda) && abs(l$engine_lambda - l$lambda) <= 32 * .Machine$double.eps * l$lambda &&
        number(l$deviance_sum) && l$deviance_sum >= 0 && integer(l$validation_events, 3L) && l$validation_events == f$validation_events &&
        number(l$deviance_per_event) && l$deviance_per_event == l$deviance_sum / l$validation_events)
      totals[[k]] <- totals[[k]] + l$deviance_sum
    }
  }
  need(total_events == support$events && total_n == support$n_training)
  for (k in seq_along(lambdas)) {
    r <- cv$rows[[k]]
    need(keys(r, names(shapes$cv_row)) && r$lambda_index == k && r$lambda == lambdas[[k]] && number(r$deviance_sum) && r$deviance_sum == totals[[k]] &&
      r$validation_events == total_events && number(r$deviance_per_event) && r$deviance_per_event == totals[[k]] / total_events &&
      identical(r$selected, k == selected))
  }
  need(selected == which.min(totals / total_events))
  invisible(TRUE)
}
cox_penalized_v10_validate_model <- function(model, spec, semantics, data, runtime, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, cox_penalized_v10_method(spec))
  need <- function(ok, code = "FROZEN_MODEL_INVALID") cox_penalized_v10_need(ok, code)
  keys <- penalized_v08_keys; number <- penalized_v08_number; string <- penalized_v08_string
  need(keys(model, c("schema_version", "method_id", "spec", "semantics", "engine", "source", "preprocessor", "cv", "selected_lambda",
    "selected_engine_lambda", "selected_lambda_index", "coefficients", "baseline", "training_support", "training_subject_ids", "training_group_ids")))
  need(identical(model$schema_version, "clinical-cox-penalized-model@0.10.0-candidate1") && identical(model$method_id, cox_penalized_v10_method(spec)))
  requested <- spec; trained <- model$spec; requested[c("cohort_id", "horizons")] <- NULL; trained[c("cohort_id", "horizons")] <- NULL
  need(penalized_v08_equal(requested, trained) && penalized_v08_equal(semantics, model$semantics), "FROZEN_SEMANTICS_OR_SPEC_MISMATCH")
  need(string(model$spec$cohort_id) && !identical(model$spec$cohort_id, spec$cohort_id), "DISTINCT_EXTERNAL_COHORT_REQUIRED")
  cox_penalized_v10_validate_preprocessor(model$preprocessor, spec, semantics)
  need(penalized_v08_equal(model$engine, c(runtime, list(solver = cox_penalized_v10_solver(), control = penalized_v08_control(length(model$preprocessor$columns))))), "FROZEN_ENGINE_MISMATCH")
  need(penalized_v08_equal(model$source, cox_penalized_v10_source()), "FROZEN_SOURCE_MISMATCH")
  need(is.list(model$coefficients) && length(model$coefficients) == length(model$preprocessor$columns) && all(vapply(model$coefficients, number, TRUE)))
  k <- model$selected_lambda_index; lambdas <- penalized_v08_vector(spec$lambda_grid)
  need(number(k) && k == floor(k) && k >= 1L && k <= length(lambdas) && number(model$selected_lambda) && model$selected_lambda == lambdas[[k]] &&
    number(model$selected_engine_lambda) && model$selected_engine_lambda > 0 &&
    abs(model$selected_engine_lambda - model$selected_lambda) <= 32 * .Machine$double.eps * abs(model$selected_lambda))
  s <- model$training_support
  need(keys(s, c("n_training", "events", "censored", "min_time", "max_followup", "last_event_time", "horizon_min", "horizon_max")) &&
    all(vapply(s, number, TRUE)) && s$n_training == floor(s$n_training) && s$n_training >= 9L &&
    s$events == floor(s$events) && s$events >= 9L && s$censored == floor(s$censored) && s$censored >= 0 && s$events + s$censored == s$n_training &&
    s$min_time > 0 && s$max_followup >= s$min_time && s$last_event_time >= s$min_time && s$last_event_time <= s$max_followup &&
    s$horizon_min == 0 && s$horizon_max == s$max_followup, "FROZEN_TRAINING_SUPPORT_INVALID")
  clinical_resource_check_rows(s$n_training, budget, "history")
  clinical_resource_check_design(nrow(data), length(model$preprocessor$columns), budget)
  horizons <- penalized_v08_vector(spec$horizons)
  need(all(horizons >= s$horizon_min & horizons <= s$horizon_max), "HORIZON_OUTSIDE_TRAINING_SUPPORT")
  original_horizons <- model$spec$horizons
  need((is.list(original_horizons) || is.numeric(original_horizons)) && length(original_horizons) >= 1L && length(original_horizons) <= 8L &&
    all(vapply(as.list(original_horizons), number, TRUE)), "FROZEN_TRAINING_SUPPORT_INVALID")
  original_horizons <- penalized_v08_vector(original_horizons)
  need(all(diff(original_horizons) > 0) && all(original_horizons >= 0 & original_horizons <= s$max_followup), "FROZEN_TRAINING_SUPPORT_INVALID")
  b <- model$baseline
  need(keys(b, c("method", "center", "event_times", "cumulative_hazard", "ties", "event_boundary", "coefficient_updates")) &&
    identical(b$method, "offset_only_breslow") && number(b$center) && identical(b$ties, "breslow") &&
    identical(b$event_boundary, "event_at_t_included") && number(b$coefficient_updates) && b$coefficient_updates == 0 &&
    is.list(b$event_times) && length(b$event_times) >= 1L && length(b$event_times) <= s$events &&
    all(vapply(b$event_times, number, TRUE)) && is.list(b$cumulative_hazard) && length(b$cumulative_hazard) == length(b$event_times) &&
    all(vapply(b$cumulative_hazard, number, TRUE)), "FROZEN_BASELINE_INVALID")
  times <- penalized_v08_vector(b$event_times); hazard <- penalized_v08_vector(b$cumulative_hazard)
  need(all(times >= s$min_time & times <= s$max_followup) && all(diff(times) > 0) && tail(times, 1) == s$last_event_time &&
    all(hazard > 0) && all(diff(hazard) > 0), "FROZEN_BASELINE_INVALID")
  cox_penalized_v10_validate_cv(model$cv, model$spec, s, k)
  need(is.list(model$training_subject_ids) && length(model$training_subject_ids) == s$n_training && all(vapply(model$training_subject_ids, string, TRUE)) &&
    is.list(model$training_group_ids) && all(vapply(model$training_group_ids, string, TRUE)))
  ids <- penalized_v08_vector(model$training_subject_ids); groups <- penalized_v08_vector(model$training_group_ids)
  need(!anyDuplicated(ids) && identical(ids, penalized_v08_sort(ids)) && !anyDuplicated(groups))
  need(!any(data[[spec$id]] %in% ids), "TRAINING_SUBJECT_OVERLAP")
  if (is.null(spec$split$group_field)) need(!length(groups)) else {
    need(length(groups) >= spec$split$cv_folds && length(groups) <= s$n_training && identical(groups, penalized_v08_sort(groups)))
    need(!any(data[[spec$split$group_field]] %in% groups), "TRAINING_GROUP_OVERLAP")
  }
  invisible(TRUE)
}
cox_penalized_v10_coefficient_rows <- function(columns, coefficients, source) lapply(seq_along(columns), function(i)
  c(columns[[i]][c("term", "feature", "type", "level")], list(coefficient = coefficients[[i]], nonzero = coefficients[[i]] != 0, source = source)))

cox_penalized_v10_analyze <- function(data, options, semantics, frozen_model = NULL, resource_budget = NULL) {
  record <- cox_penalized_v10_empty_record(options, semantics, if (is.data.frame(data)) nrow(data) else 0L)
  stage <- "input"; fold <- NA_integer_; model <- NULL
  tryCatch({
    # Count available labels before a training-input rejection, without ever
    # inspecting endpoint cells for inference.
    if (is.data.frame(data) && identical(options$operation, "train")) {
      spec <- options$spec; partition_field <- spec$split$partition_field
      if (penalized_v08_string(partition_field) && partition_field %in% names(data) && is.character(data[[partition_field]])) {
        partition <- data[[partition_field]]
        record$flow$n_training <- sum(partition == "train", na.rm = TRUE)
        record$flow$n_holdout <- sum(partition == "holdout", na.rm = TRUE)
        if (penalized_v08_string(spec$event) && spec$event %in% names(data) && is.numeric(data[[spec$event]])) {
          event <- data[[spec$event]]
          record$flow$n_training_events <- sum(event == 1 & partition == "train", na.rm = TRUE)
          record$flow$n_training_censored <- sum(event == 0 & partition == "train", na.rm = TRUE)
          record$flow$n_holdout_events <- sum(event == 1 & partition == "holdout", na.rm = TRUE)
          record$flow$n_holdout_censored <- sum(event == 0 & partition == "holdout", na.rm = TRUE)
        }
      }
      if (penalized_v08_string(spec$duration) && spec$duration %in% names(data)) record$flow$missing_duration_n <- sum(is.na(data[[spec$duration]]))
      if (penalized_v08_string(spec$event) && spec$event %in% names(data)) record$flow$missing_event_n <- sum(is.na(data[[spec$event]]))
    }
    budget <- clinical_resource_budget(resource_budget, cox_penalized_v10_method(options$spec))
    cox_penalized_v10_validate(data, options, semantics, budget)
    spec <- options$spec; split <- spec$split; operation <- options$operation; horizons <- penalized_v08_vector(spec$horizons)
    data <- data[order(penalized_v08_key(data[[spec$id]]), method = "radix"), , drop = FALSE]; rownames(data) <- NULL
    training <- data[[split$partition_field]] == "train"; holdout <- !training
    record$flow$n_training <- sum(training); record$flow$n_holdout <- if (operation == "train") sum(holdout) else 0L
    if (operation == "train") {
      event <- data[[spec$event]]
      record$flow$n_training_events <- sum(event[training]); record$flow$n_training_censored <- sum(1 - event[training])
      record$flow$n_holdout_events <- sum(event[holdout]); record$flow$n_holdout_censored <- sum(1 - event[holdout])
      record$flow$missing_duration_n <- 0L; record$flow$missing_event_n <- 0L
    }
    stage <- "runtime"; runtime <- cox_penalized_v10_runtime()
    add_counts <- function(counts, at, role, fold = NA_integer_) record$preprocessing <<- c(record$preprocessing,
      lapply(counts, function(x) c(list(stage = at, fold = as.integer(fold), role = role), x)))
    if (operation == "train") {
      cox_penalized_v10_need(is.null(frozen_model), "UNEXPECTED_FROZEN_MODEL")
      td <- data[training, , drop = FALSE]; duration <- td[[spec$duration]]; event <- td[[spec$event]]
      lambdas <- penalized_v08_vector(spec$lambda_grid); losses <- numeric(length(lambdas))
      record$flow$n_cv_folds <- as.integer(split$cv_folds)
      for (fold in seq_len(split$cv_folds)) {
        validation <- td[[split$fold_field]] == fold
        stage <- "cv_preprocessing"; prep <- penalized_v08_prepare(td[!validation, , drop = FALSE], spec$features, resource_budget = budget)
        add_counts(prep$counts, "cv", "fitting", fold)
        valid <- penalized_v08_prepare(td[validation, , drop = FALSE], spec$features, prep$model, resource_budget = budget)
        add_counts(valid$counts, "cv", "validation", fold)
        stage <- "cv_fit"; record$diagnostics$n_engine_fits <- record$diagnostics$n_engine_fits + 1L
        fit <- cox_penalized_v10_fit(prep$x, duration[!validation], event[!validation], spec$alpha, lambdas)
        record$cv$folds[[fold]] <- list(fold = as.integer(fold), n_training = sum(!validation), n_validation = sum(validation),
          training_events = sum(event[!validation]), training_censored = sum(1 - event[!validation]),
          validation_events = sum(event[validation]), validation_censored = sum(1 - event[validation]), n_encoded_columns = ncol(prep$x),
          n_dropped_columns = length(prep$model$dropped_columns), dropped_columns = prep$model$dropped_columns, jerr = fit$jerr, warning_count = fit$warning_count)
        stage <- "cv_validation"; fold_losses <- cox_penalized_v10_deviance(valid$x, fit$coefficients, duration[validation], event[validation])
        losses <- losses + fold_losses
        for (k in seq_along(lambdas)) record$cv$fold_losses[[length(record$cv$fold_losses) + 1L]] <- list(fold = as.integer(fold),
          lambda_index = as.integer(k), lambda = lambdas[[k]], engine_lambda = fit$engine_lambda[[k]], deviance_sum = fold_losses[[k]],
          validation_events = sum(event[validation]), deviance_per_event = fold_losses[[k]] / sum(event[validation]))
      }
      fold <- NA_integer_; total_events <- sum(event)
      cox_penalized_v10_need(all(is.finite(losses)), "NONFINITE_OR_INVALID_DEVIANCE")
      # Strictly decreasing requested grid: exact loss ties select its largest lambda.
      selected <- which.min(losses / total_events)
      record$cv$rows <- lapply(seq_along(lambdas), function(k) list(lambda_index = as.integer(k), lambda = lambdas[[k]],
        deviance_sum = losses[[k]], validation_events = total_events, deviance_per_event = losses[[k]] / total_events, selected = k == selected))
      record$cv$status <- "completed"; record$cv["reason_code"] <- list(NULL)
      stage <- "final_preprocessing"; prep <- penalized_v08_prepare(td, spec$features, resource_budget = budget); add_counts(prep$counts, "final", "fitting")
      stage <- "final_fit"; record$diagnostics$n_engine_fits <- record$diagnostics$n_engine_fits + 1L
      fit <- cox_penalized_v10_fit(prep$x, duration, event, spec$alpha, lambdas)
      beta <- as.numeric(fit$coefficients[, selected]); stage <- "training_baseline"
      baseline <- cox_penalized_v10_baseline(duration, event, as.numeric(prep$x %*% beta))
      support <- list(n_training = nrow(td), events = sum(event), censored = sum(1 - event), min_time = min(duration),
        max_followup = max(duration), last_event_time = max(duration[event == 1]), horizon_min = 0, horizon_max = max(duration))
      model <- list(schema_version = "clinical-cox-penalized-model@0.10.0-candidate1", method_id = cox_penalized_v10_method(spec),
        spec = spec, semantics = semantics, engine = c(runtime, list(solver = cox_penalized_v10_solver(), control = fit$control)),
        source = cox_penalized_v10_source(), preprocessor = prep$model, cv = record$cv, selected_lambda = lambdas[[selected]],
        selected_engine_lambda = fit$engine_lambda[[selected]], selected_lambda_index = as.integer(selected), coefficients = as.list(beta),
        baseline = baseline, training_support = support, training_subject_ids = as.list(td[[spec$id]]),
        training_group_ids = if (is.null(split$group_field)) list() else as.list(penalized_v08_sort(unique(td[[split$group_field]]))))
      for (k in seq_along(lambdas)) {
        rows <- cox_penalized_v10_coefficient_rows(prep$model$columns, fit$coefficients[, k], "training")
        record$path <- c(record$path, lapply(rows, function(x) c(list(lambda_index = as.integer(k), lambda = lambdas[[k]],
          engine_lambda = fit$engine_lambda[[k]]), x[setdiff(names(x), "source")])))
      }
      stage <- "holdout_prediction"; hp <- penalized_v08_prepare(data[holdout, , drop = FALSE], spec$features, prep$model, resource_budget = budget); add_counts(hp$counts, "final", "holdout")
      x <- matrix(NA_real_, nrow(data), ncol(prep$x)); x[training, ] <- prep$x; x[holdout, ] <- hp$x
      predicted <- cox_penalized_v10_predict(x, beta, baseline, horizons)
    } else {
      stage <- "external_validation"; cox_penalized_v10_validate_model(frozen_model, spec, semantics, data, runtime, budget); model <- frozen_model
      record$cv$reason_code <- "FROZEN_MODEL_NO_REFIT"
      stage <- "external_prediction"; prep <- penalized_v08_prepare(data, spec$features, model$preprocessor, resource_budget = budget); add_counts(prep$counts, "external", "external")
      predicted <- cox_penalized_v10_predict(prep$x, penalized_v08_vector(model$coefficients), model$baseline, horizons)
    }
    record$coefficients <- cox_penalized_v10_coefficient_rows(model$preprocessor$columns, penalized_v08_vector(model$coefficients),
      if (operation == "train") "training" else "frozen_training")
    record$selected_lambda <- model$selected_lambda; record$selected_engine_lambda <- model$selected_engine_lambda; record$selected_lambda_index <- as.integer(model$selected_lambda_index)
    record$flow$n_encoded_columns <- length(model$preprocessor$columns); record$flow$n_dropped_columns <- length(model$preprocessor$dropped_columns)
    record$flow$n_predicted <- nrow(data)
    record$baseline <- list(method = model$baseline$method, reference_center = model$baseline$center,
      event_time_count = length(model$baseline$event_times), last_event_time = model$training_support$last_event_time,
      max_followup = model$training_support$max_followup, time_unit = spec$survival$time_unit, ties = "breslow",
      event_boundary = "event_at_t_included", coefficient_updates = 0L)
    populations <- if (operation == "train") list(training = training, holdout = holdout) else list(external = rep(TRUE, nrow(data)))
    for (population in names(populations)) for (k in seq_along(horizons)) {
      risks <- predicted$risk[populations[[population]], k]
      record$horizons[[length(record$horizons) + 1L]] <- list(population = population, horizon = horizons[[k]], time_unit = spec$survival$time_unit,
        n_predicted = length(risks), min_risk = min(risks), max_risk = max(risks), mean_risk = mean(risks))
    }
    rows <- rep(seq_len(nrow(data)), each = length(horizons))
    individual <- data.frame(subject_id = data[[spec$id]][rows], group_id = if (is.null(split$group_field)) NA_character_ else data[[split$group_field]][rows],
      partition = data[[split$partition_field]][rows], fold = as.integer(data[[split$fold_field]][rows]),
      duration = if (operation == "infer") NA_real_ else data[[spec$duration]][rows], event = if (operation == "infer") NA_real_ else data[[spec$event]][rows],
      linear_predictor = predicted$linear_predictor[rows], centered_linear_predictor = predicted$centered_linear_predictor[rows],
      horizon = rep(horizons, times = nrow(data)), survival = as.numeric(t(predicted$survival)), risk = as.numeric(t(predicted$risk)), stringsAsFactors = FALSE)
    record$status <- "completed"; record["reason_code"] <- list(NULL); record$diagnostics$stage <- "complete"; record$diagnostics["code"] <- list(NULL)
    record$diagnostics$jerr <- if (operation == "train") 0L else NA_integer_
    list(ok = TRUE, reason_code = NULL, record = record, model = model, individual = individual)
  }, error = function(e) {
    code <- if ((inherits(e, "penalized_v08_blocked") || grepl("^RESOURCE_[A-Z_]+$", conditionMessage(e)))) conditionMessage(e) else "COX_PENALIZED_NUMERIC_EXECUTION_FAILED"
    if (startsWith(code, "PENALIZED_")) code <- paste0("COX_", code)
    record$status <- "unavailable"; record$reason_code <- code; record$horizons <- list()
    record$diagnostics$stage <- stage; record$diagnostics$fold <- as.integer(fold); record$diagnostics$code <- code
    record$diagnostics["feature"] <- list(if (inherits(e, "penalized_v08_blocked")) e$feature else NULL)
    if (inherits(e, "penalized_v08_blocked")) {record$diagnostics$jerr <- e$jerr; record$diagnostics$warning_count <- e$warning_count}
    if (startsWith(stage, "cv_")) {record$cv$status <- "unavailable"; record$cv$reason_code <- code}
    list(ok = FALSE, reason_code = code, record = record, model = NULL, individual = cox_penalized_v10_empty_individual())
  })
}
