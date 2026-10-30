# Sole v0.8 penalized prediction numerical owner: installed glmnet only.
# Observations, identities, learned preprocessing and frozen model are private.

penalized_v08_empty_individual <- function() {
  data.frame(subject_id = character(), group_id = character(), partition = character(), fold = integer(),
    observed = double(), prediction = double(), linear_predictor = double(), stringsAsFactors = FALSE)
}

penalized_v08_solver <- function() {
  list(thresh = 1e-10, maxit = 100000L, standardize = FALSE, intercept = TRUE,
    penalty_factor = "equal_one", relax = FALSE, type_gaussian = "covariance", type_logistic = "Newton",
    fdev = 0, devmax = 1, eps = 1e-6, big = 9.9e35, mnlam = 5L, pmin = 1e-9,
    exmx = 250, itrace = 0L, prec = 1e-10, mxit = 100L, epsnr = 1e-6, mxitnr = 25L,
    trace_it = 0L, dfmax = "n_encoded_plus_one", pmax = "n_encoded",
    lambda_epsilon_multiplier = 32L)
}

penalized_v08_method <- function(spec) {
  paste0(if (identical(spec$family, "gaussian")) "prediction.continuous.signed." else "prediction.binary.",
    if (identical(as.numeric(spec$alpha), 1)) "lasso" else "elasticnet")
}

penalized_v08_empty_record <- function(options, semantics, n_input = 0L) {
  spec <- options$spec
  list(method_id = penalized_v08_method(spec), operation = options$operation,
    status = "unavailable", reason_code = "NOT_RUN", family = spec$family,
    penalty = if (identical(as.numeric(spec$alpha), 1)) "lasso" else "elasticnet", alpha = spec$alpha,
    selected_lambda = NA_real_, selected_engine_lambda = NA_real_, selected_lambda_index = NA_integer_,
    coefficient_scale = if (identical(spec$family, "gaussian")) "standardized_x_standardized_y" else "standardized_x_log_odds",
    prediction_scale = if (identical(spec$family, "gaussian")) "signed_original_outcome" else "event_probability",
    semantics = semantics,
    flow = list(n_input = as.integer(n_input), n_training = NA_integer_, n_holdout = NA_integer_,
      n_evaluated = 0L, n_predicted = 0L, n_cv_folds = 0L, n_features = length(spec$features),
      n_encoded_columns = NA_integer_, n_dropped_columns = NA_integer_, n_training_events = NA_integer_,
      n_training_non_events = NA_integer_, n_holdout_events = NA_integer_, n_holdout_non_events = NA_integer_,
      n_evaluation_events = NA_integer_, n_evaluation_non_events = NA_integer_, missing_outcome_n = NA_integer_),
    preprocessing = list(),
    cv = list(status = "not_run", reason_code = "NOT_RUN", selection_rule = "min_mean_loss_largest_lambda_tie",
      loss_name = if (identical(spec$family, "gaussian")) "mean_squared_error_original_outcome" else "binomial_log_loss",
      weighting = "validation_subject_count", scope = "training_only_tuning", rows = list(), folds = list(), fold_losses = list()),
    path = list(), coefficients = list(), metrics = list(),
    diagnostics = list(stage = "input", fold = NA_integer_, feature = NULL, code = "NOT_RUN",
      warning_count = 0L, jerr = NA_integer_, n_engine_fits = 0L, solver = penalized_v08_solver()),
    limitations = as.list(c("SYNTHETIC_ENGINEERING_ONLY", "CV_IS_TUNING_NOT_EXTERNAL_PERFORMANCE",
      "NO_COEFFICIENT_OR_POSTSELECTION_INFERENCE", "NO_CAUSAL_CLAIM", "NO_CLINICAL_VALIDATION",
      "PRESPECIFIED_SINGLE_ALPHA_AND_LAMBDA_GRID", "STRICT_OBSERVED_CATEGORY_SUPPORT")))
}

# Stable aggregate row fields are defined here for the result schema owner.
penalized_v08_row_shapes <- function() {
  list(
    preprocessing = list(stage = "cv", fold = 1L, role = "fitting", feature = "x", type = "number",
      n_rows = 1L, n_missing = 0L, n_imputed = 0L, fitted_levels = list(), fitted_reference = NULL,
      encoding_rule = "identity_numeric"),
    cv_row = list(lambda_index = 1L, lambda = 1, loss_sum = 0, n_validation = 1L, mean_loss = 0, selected = TRUE),
    cv_fold = list(fold = 1L, n_training = 1L, n_validation = 1L, training_events = NA_integer_,
      training_non_events = NA_integer_, n_encoded_columns = 2L, n_dropped_columns = 0L),
    cv_fold_loss = list(fold = 1L, lambda_index = 1L, lambda = 1, engine_lambda = 1, loss_sum = 0, n_validation = 1L, mean_loss = 0),
    coefficient = list(term = "(Intercept)", feature = NULL, type = "intercept", level = NULL,
      coefficient = 0, nonzero = FALSE, source = "training"),
    path = list(lambda_index = 1L, lambda = 1, engine_lambda = 1, term = "(Intercept)", feature = NULL, type = "intercept", level = NULL,
      coefficient = 0, nonzero = FALSE),
    metric = list(population = "holdout", metric = "mae", value = 0, numerator = 0, denominator = 1L,
      numerator_semantics = "sum_absolute_error", denominator_semantics = "evaluated_subjects", reason_code = NULL,
      threshold = NA_real_, ranking_score = NULL, n = 1L, events = NA_integer_, non_events = NA_integer_))
}

penalized_v08_need <- function(condition, code, feature = NULL, jerr = NA_integer_, warning_count = 0L) {
  if (!isTRUE(condition)) stop(structure(list(message = code, call = NULL, feature = feature,
    jerr = if (is.numeric(jerr) && length(jerr) == 1L && is.finite(jerr)) as.integer(jerr) else NA_integer_,
    warning_count = as.integer(warning_count)), class = c("penalized_v08_blocked", "error", "condition")))
}

penalized_v08_number <- function(x) is.numeric(x) && !is.complex(x) && length(x) == 1L && !is.na(x) && is.finite(x)
penalized_v08_string <- function(x) is.character(x) && length(x) == 1L && !is.na(x) && nzchar(trimws(x))
penalized_v08_keys <- function(x, keys) is.list(x) && length(x) == length(keys) &&
  !anyDuplicated(names(x)) && setequal(names(x), keys)
penalized_v08_vector <- function(x) unlist(x, use.names = FALSE)
penalized_v08_key <- function(x) vapply(enc2utf8(x), function(s) paste(sprintf("%02x", as.integer(charToRaw(s))), collapse = ""), "")
penalized_v08_sort <- function(x) x[order(penalized_v08_key(x), method = "radix")]
penalized_v08_object <- function() structure(list(), names = character())

penalized_v08_runtime <- function() {
  penalized_v08_need(requireNamespace("glmnet", quietly = TRUE) && requireNamespace("Matrix", quietly = TRUE), "PENALIZED_ENGINE_UNAVAILABLE")
  versions <- list(R = as.character(getRversion()), glmnet = as.character(utils::packageVersion("glmnet")),
    Matrix = as.character(utils::packageVersion("Matrix")))
  penalized_v08_need(identical(versions, list(R = "4.6.1", glmnet = "5.1", Matrix = "1.7.5")), "PENALIZED_ENGINE_VERSION_MISMATCH")
  versions
}

penalized_v08_control <- function(p) {
  list(fdev = 0, eps = 1e-6, big = 9.9e35, mnlam = 5L, devmax = 1,
    pmin = 1e-9, exmx = 250, itrace = 0L, prec = 1e-10, mxit = 100L,
    epsnr = 1e-6, mxitnr = 25L, thresh = 1e-10, maxit = 100000L,
    dfmax = as.integer(p + 1L), pmax = as.integer(p), trace.it = 0L)
}

penalized_v08_validate <- function(data, options, semantics, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, penalized_v08_method(options$spec))
  need <- penalized_v08_need
  need(penalized_v08_keys(options, c("operation", "spec", "model_ref", "unknown_category_policy")), "PENALIZED_OPTIONS_INVALID")
  need(options$operation %in% c("train", "evaluate", "infer") && length(options$operation) == 1L &&
    identical(options$unknown_category_policy, "reject"), "PENALIZED_OPTIONS_INVALID")
  spec <- options$spec
  need(penalized_v08_keys(spec, c("id", "outcome", "family", "alpha", "lambda_grid", "features", "split", "selection_rule", "missing",
    "standardization", "response_transform", "clinical_threshold", "cohort_id", "canonical_identity_namespace")), "PENALIZED_SPEC_INVALID")
  need(all(vapply(spec[c("id", "outcome", "cohort_id", "canonical_identity_namespace")], penalized_v08_string, TRUE)) &&
    spec$family %in% c("gaussian", "binomial") && length(spec$family) == 1L &&
    penalized_v08_number(spec$alpha) && spec$alpha > 0 && spec$alpha <= 1, "PENALIZED_SPEC_INVALID")
  lambdas <- spec$lambda_grid
  need((is.numeric(lambdas) || is.list(lambdas)) && length(lambdas) >= 2L && length(lambdas) <= 30L &&
    all(vapply(as.list(lambdas), penalized_v08_number, TRUE)), "PENALIZED_LAMBDA_GRID_INVALID")
  lambdas <- penalized_v08_vector(lambdas)
  need(all(lambdas > 0) && all(diff(lambdas) < 0), "PENALIZED_LAMBDA_GRID_INVALID")
  need(identical(spec$selection_rule, "min_mean_loss_largest_lambda_tie") && identical(spec$missing, "training_median_mode") &&
    identical(spec$standardization, "training_population_sd") && identical(spec$response_transform,
      if (spec$family == "gaussian") "training_center_scale" else "identity"), "PENALIZED_SPEC_UNSUPPORTED")
  need(if (spec$family == "gaussian") is.null(spec$clinical_threshold) else is.null(spec$clinical_threshold) ||
    (penalized_v08_number(spec$clinical_threshold) && spec$clinical_threshold > 0 && spec$clinical_threshold < 1), "PENALIZED_THRESHOLD_INVALID")
  split <- spec$split
  need(penalized_v08_keys(split, c("method", "partition_field", "fold_field", "group_field", "training_value", "holdout_value", "cv_folds")) &&
    split$method %in% c("prespecified_patient", "prespecified_group") && length(split$method) == 1L &&
    penalized_v08_string(split$partition_field) && penalized_v08_string(split$fold_field) &&
    identical(split$training_value, "train") && identical(split$holdout_value, "holdout") &&
    penalized_v08_number(split$cv_folds) && split$cv_folds %in% 3:5, "PENALIZED_SPLIT_INVALID")
  need(if (split$method == "prespecified_group") penalized_v08_string(split$group_field) else is.null(split$group_field), "PENALIZED_SPLIT_INVALID")
  need(is.list(spec$features) && length(spec$features) >= 1L && all(vapply(spec$features, function(f)
    penalized_v08_keys(f, c("name", "type")) && penalized_v08_string(f$name) && is.character(f$type) && length(f$type) == 1L &&
      f$type %in% c("number", "category"), TRUE)), "PENALIZED_FEATURES_INVALID")
  need(length(spec$features) <= 12L, "PENALIZED_FEATURE_LIMIT")
  features <- vapply(spec$features, `[[`, "", "name")
  protected <- c(spec$id, spec$outcome, split$partition_field, split$fold_field, split$group_field)
  need(!anyDuplicated(protected) && !anyDuplicated(features) && !any(features %in% protected), "PENALIZED_FORBIDDEN_OR_DUPLICATE_FEATURE")
  need(is.list(semantics) && penalized_v08_keys(semantics, c("identity", "features", "outcome", "time")) &&
    identical(semantics$identity$subject_id, spec$id) && identical(semantics$identity$group_id, split$group_field) &&
    identical(semantics$identity$canonical_identity_namespace, spec$canonical_identity_namespace) &&
    length(semantics$features) == length(spec$features), "PENALIZED_SEMANTICS_INVALID")
  need(identical(vapply(semantics$features, `[[`, "", "name"), features) && identical(semantics$outcome$name, spec$outcome), "PENALIZED_SEMANTICS_INVALID")
  need(is.data.frame(data) && nrow(data) >= 1L && !anyDuplicated(names(data)), "PENALIZED_DATA_INVALID")
  clinical_resource_check_rows(nrow(data), budget)
  declared_columns <- sum(vapply(semantics$features, function(f)
    if (identical(f$dtype, "number")) 1 else max(1, length(f$levels) - 1L), 0))
  clinical_resource_check_design(nrow(data), declared_columns, budget)
  required <- c(spec$id, features, split$partition_field, split$fold_field, split$group_field,
    if (options$operation != "infer") spec$outcome else character())
  need(all(required %in% names(data)), "PENALIZED_REQUIRED_COLUMN_ABSENT")
  ids <- data[[spec$id]]
  need(is.character(ids) && !anyNA(ids) && all(nzchar(trimws(ids))) && all(validUTF8(enc2utf8(ids))) && !anyDuplicated(ids), "PENALIZED_UNIQUE_STRING_IDS_REQUIRED")
  partitions <- data[[split$partition_field]]; folds <- data[[split$fold_field]]
  need(is.character(partitions) && !anyNA(partitions) && all(partitions %in% c("train", "holdout")) &&
    is.numeric(folds) && !is.complex(folds) && !anyNA(folds) && all(is.finite(folds)) && all(folds == floor(folds)), "PENALIZED_PARTITION_OR_FOLD_INVALID")
  train <- partitions == "train"
  if (options$operation == "train") {
    need(is.null(options$model_ref) && any(train) && any(!train) && all(folds[train] %in% seq_len(split$cv_folds)) &&
      setequal(unique(folds[train]), seq_len(split$cv_folds)) && all(folds[!train] == 0), "PENALIZED_PARTITION_OR_FOLD_INVALID")
  } else need(!any(train) && all(folds == 0), "PENALIZED_EXTERNAL_PARTITION_REQUIRED")
  if (!is.null(split$group_field)) {
    groups <- data[[split$group_field]]
    need(is.character(groups) && !anyNA(groups) && all(nzchar(trimws(groups))) && all(validUTF8(enc2utf8(groups))), "PENALIZED_GROUP_IDS_REQUIRED")
    for (g in unique(groups)) need(length(unique(partitions[groups == g])) == 1L && length(unique(folds[groups == g])) == 1L,
      "PENALIZED_GROUP_PARTITION_OR_FOLD_LEAKAGE")
  }
  if (options$operation != "infer") {
    y <- data[[spec$outcome]]
    need(is.numeric(y) && !is.complex(y) && !anyNA(y) && all(is.finite(y)), "PENALIZED_OBSERVED_OUTCOME_REQUIRED")
    if (spec$family == "binomial") need(all(y %in% c(0, 1)), "PENALIZED_BINARY_OUTCOME_REQUIRED")
  }
  for (i in seq_along(spec$features)) {
    f <- spec$features[[i]]; x <- data[[f$name]]
    if (f$type == "number") need(is.numeric(x) && !is.complex(x) && !any(is.nan(x)) && all(is.finite(x[!is.na(x)])), "PENALIZED_NUMERIC_FEATURE_INVALID", f$name)
    else {
      need(is.character(x) || is.factor(x), "PENALIZED_CATEGORY_FEATURE_INVALID", f$name)
      x <- as.character(x); present <- !is.na(x) & x != ""
      declared <- penalized_v08_vector(semantics$features[[i]]$levels)
      need(length(declared) >= 1L && all(x[present] %in% declared), "PENALIZED_UNDECLARED_CATEGORY", f$name)
    }
  }
  invisible(TRUE)
}

penalized_v08_prepare <- function(data, features, fitted = NULL, resource_budget = NULL, row_kind = "input") {
  budget <- clinical_resource_budget(resource_budget, "prediction.continuous.signed.lasso")
  clinical_resource_check_rows(nrow(data), budget, row_kind)
  declared_columns <- if (!is.null(fitted)) length(fitted$columns) else sum(vapply(features, function(f) {
    x <- data[[f$name]]
    if (identical(f$type, "number")) 1 else max(1, length(unique(x[!is.na(x) & x != ""])) - 1L)
  }, 0))
  clinical_resource_check_design(nrow(data), declared_columns, budget)
  learning <- is.null(fitted)
  feature_models <- if (learning) list() else fitted$features
  raw_columns <- list(); column_metadata <- list(); missing_counts <- list()
  for (i in seq_along(features)) {
    f <- features[[i]]; x <- data[[f$name]]
    if (f$type == "category") x <- as.character(x)
    missing <- is.na(x) | if (f$type == "category") x == "" else FALSE
    if (learning) {
      penalized_v08_need(any(!missing), "PENALIZED_ALL_MISSING_FITTING_FEATURE", f$name)
      if (f$type == "number") fm <- list(name = f$name, type = f$type, impute = stats::median(x[!missing]), levels = list(), reference = NULL)
      else {
        levels <- penalized_v08_sort(unique(x[!missing]))
        counts <- vapply(levels, function(level) sum(x[!missing] == level), 0L)
        fm <- list(name = f$name, type = f$type, impute = levels[[which.max(counts)]], levels = as.list(levels), reference = levels[[1L]])
      }
      feature_models[[i]] <- fm
    } else fm <- feature_models[[i]]
    if (f$type == "category") penalized_v08_need(all(x[!missing] %in% penalized_v08_vector(fm$levels)), "PENALIZED_UNKNOWN_OBSERVED_CATEGORY", f$name)
    x[missing] <- fm$impute
    missing_counts[[i]] <- list(feature = f$name, type = f$type, n_rows = nrow(data), n_missing = sum(missing), n_imputed = sum(missing),
      fitted_levels = fm$levels, fitted_reference = fm$reference,
      encoding_rule = if (f$type == "number") "identity_numeric" else "treatment_utf8_observed_reference_first")
    levels <- if (f$type == "number") list(NULL) else as.list(penalized_v08_vector(fm$levels)[-1L])
    penalized_v08_need(length(raw_columns) + length(levels) <= 60L, "PENALIZED_ENCODED_LIMIT", f$name)
    for (j in seq_along(levels)) {
      level <- levels[[j]]
      term <- if (f$type == "number") sprintf("X%04d", i) else sprintf("X%04dL%04d", i, j + 1L)
      raw_columns[[term]] <- if (f$type == "number") x else as.numeric(x == level)
      column_metadata[[term]] <- list(term = term, feature = f$name, type = f$type, level = level)
    }
  }
  raw <- if (length(raw_columns)) do.call(cbind, raw_columns) else matrix(numeric(), nrow(data), 0L)
  if (learning) {
    columns <- dropped <- list()
    for (term in colnames(raw)) {
      center <- mean(raw[, term]); scale <- sqrt(mean((raw[, term] - center)^2))
      penalized_v08_need(is.finite(center) && is.finite(scale), "PENALIZED_NONFINITE_FEATURE_SCALE", column_metadata[[term]]$feature)
      if (scale == 0) dropped[[length(dropped) + 1L]] <- c(column_metadata[[term]], list(reason_code = "ZERO_VARIANCE"))
      else columns[[length(columns) + 1L]] <- c(column_metadata[[term]], list(center = center, scale = scale))
    }
    penalized_v08_need(length(columns) >= 2L, "PENALIZED_INSUFFICIENT_NONCONSTANT_COLUMNS")
    fitted <- list(features = feature_models, columns = columns, dropped_columns = dropped)
  }
  matrix <- do.call(cbind, lapply(fitted$columns, function(column) (raw[, column$term] - column$center) / column$scale))
  colnames(matrix) <- vapply(fitted$columns, `[[`, "", "term")
  penalized_v08_need(nrow(matrix) == nrow(data) && ncol(matrix) >= 2L && all(is.finite(matrix)), "PENALIZED_NONFINITE_DESIGN")
  list(x = matrix, model = fitted, counts = missing_counts)
}

penalized_v08_response <- function(y, family) {
  if (family == "binomial") {
    penalized_v08_need(sum(y == 0) >= 8L && sum(y == 1) >= 8L, "PENALIZED_FITTING_CLASS_COUNT_BELOW_EIGHT")
    return(list(values = y, transform = list(method = "identity", center = 0, scale = 1)))
  }
  center <- mean(y); scale <- sqrt(mean((y - center)^2))
  penalized_v08_need(is.finite(center) && is.finite(scale), "PENALIZED_NONFINITE_RESPONSE_SCALE")
  penalized_v08_need(scale > 0, "PENALIZED_CONSTANT_FITTING_RESPONSE")
  list(values = (y - center) / scale, transform = list(method = "training_center_scale", center = center, scale = scale))
}

penalized_v08_fit <- function(x, y, family, alpha, lambdas) {
  response <- penalized_v08_response(y, family)
  warnings <- character(); control <- penalized_v08_control(ncol(x))
  fit <- tryCatch(withCallingHandlers(glmnet::glmnet(x = x, y = response$values, family = family, alpha = alpha,
    lambda = lambdas, standardize = FALSE, intercept = TRUE, penalty.factor = rep(1, ncol(x)),
    relax = FALSE, type.gaussian = "covariance", type.logistic = "Newton", control = control),
    warning = function(w) { warnings <<- c(warnings, conditionMessage(w)); invokeRestart("muffleWarning") }),
    error = function(e) penalized_v08_need(FALSE, "PENALIZED_GLMNET_ERROR", warning_count = length(warnings)))
  path <- penalized_v08_extract_path(fit, lambdas, ncol(x), length(warnings))
  c(path, list(response_transform = response$transform, control = control, jerr = 0L))
}

# Validate exact engine outputs before selecting a requested path column.
penalized_v08_extract_path <- function(fit, lambdas, n_columns, warning_count = 0L) {
  penalized_v08_need(warning_count == 0L, "PENALIZED_GLMNET_WARNING", jerr = fit$jerr, warning_count = warning_count)
  penalized_v08_need(length(fit$jerr) == 1L && is.finite(fit$jerr) && fit$jerr == 0, "PENALIZED_GLMNET_JERR", jerr = fit$jerr)
  returned <- fit$lambda
  penalized_v08_need(length(returned) == length(lambdas) && all(is.finite(returned)) && all(returned > 0) &&
    all(diff(returned) < 0) && all(abs(returned - lambdas) <= 32 * .Machine$double.eps * abs(lambdas)), "PENALIZED_REQUESTED_LAMBDA_PATH_MISSING")
  coefficients <- as.matrix(fit$beta); intercept <- as.numeric(fit$a0)
  penalized_v08_need(identical(dim(coefficients), c(as.integer(n_columns), length(lambdas))) && length(intercept) == length(lambdas) &&
    all(is.finite(coefficients)) && all(is.finite(intercept)), "PENALIZED_NONFINITE_COEFFICIENTS")
  list(coefficients = coefficients, intercept = intercept, engine_lambda = returned)
}

penalized_v08_predict <- function(x, coefficients, intercept, response_transform, family) {
  eta <- sweep(x %*% coefficients, 2L, intercept, `+`)
  penalized_v08_need(all(is.finite(eta)), "PENALIZED_NONFINITE_LINEAR_PREDICTOR")
  prediction <- if (family == "gaussian") response_transform$center + response_transform$scale * eta else stats::plogis(eta)
  penalized_v08_need(all(is.finite(prediction)), "PENALIZED_NONFINITE_PREDICTION")
  list(prediction = prediction, linear_predictor = eta)
}

penalized_v08_loss <- function(y, prediction, eta, family) {
  losses <- if (family == "gaussian") (prediction - y)^2 else pmax(eta, 0) - y * eta + log1p(exp(-abs(eta)))
  sums <- colSums(losses)
  penalized_v08_need(all(is.finite(losses)) && all(losses >= 0) && all(is.finite(sums)), "PENALIZED_NONFINITE_LOSS")
  sums
}

penalized_v08_metrics <- function(y, prediction, eta, family, training_mean, threshold, population) {
  n <- length(y); events <- if (family == "binomial") sum(y == 1) else NA_integer_
  non_events <- if (family == "binomial") sum(y == 0) else NA_integer_
  rows <- list()
  add <- function(metric, numerator, denominator, numerator_semantics, denominator_semantics,
                  value = if (denominator > 0) numerator / denominator else NA_real_, reason = NULL, at = NA_real_) {
    penalized_v08_need(is.finite(numerator) && numerator >= 0 && is.finite(denominator) && denominator >= 0 &&
      (is.na(value) || is.finite(value)), "PENALIZED_NONFINITE_METRIC")
    rows[[length(rows) + 1L]] <<- list(population = population, metric = metric, value = value,
      numerator = numerator, denominator = as.integer(denominator), numerator_semantics = numerator_semantics,
      denominator_semantics = denominator_semantics, reason_code = reason, threshold = at,
      ranking_score = if (metric == "auc") "logit" else NULL,
      n = as.integer(n), events = as.integer(events), non_events = as.integer(non_events))
  }
  if (family == "gaussian") {
    absolute <- sum(abs(prediction - y)); squared <- sum((prediction - y)^2)
    baseline_absolute <- sum(abs(training_mean - y)); baseline_squared <- sum((training_mean - y)^2)
    add("mae", absolute, n, "sum_absolute_error", "evaluated_subjects")
    add("rmse", squared, n, "sum_squared_error", "evaluated_subjects", sqrt(squared / n))
    add("training_mean_mae", baseline_absolute, n, "sum_absolute_error", "evaluated_subjects")
    add("training_mean_rmse", baseline_squared, n, "sum_squared_error", "evaluated_subjects", sqrt(baseline_squared / n))
  } else {
    auc_denominator <- events * non_events
    concordance <- if (auc_denominator) {
      # Rank the unsaturated monotone-link score; plogis rounding must not create ties.
      differences <- outer(eta[y == 1], eta[y == 0], `-`)
      sum(differences > 0) + 0.5 * sum(differences == 0)
    } else 0
    add("auc", concordance, auc_denominator, "concordant_event_nonevent_pairs_plus_half_ties", "event_nonevent_pairs",
      reason = if (!events) "NO_EVENTS" else if (!non_events) "NO_NON_EVENTS" else NULL)
    add("brier", sum((prediction - y)^2), n, "sum_squared_probability_error", "evaluated_subjects")
    add("log_loss", sum(pmax(eta, 0) - y * eta + log1p(exp(-abs(eta)))), n, "sum_binomial_log_loss", "evaluated_subjects")
    if (!is.null(threshold)) {
      positive <- prediction >= threshold; tp <- sum(positive & y == 1); tn <- sum(!positive & y == 0)
      add("sensitivity", tp, events, "true_positives", "actual_events", reason = if (!events) "NO_EVENTS" else NULL, at = threshold)
      add("specificity", tn, non_events, "true_negatives", "actual_non_events", reason = if (!non_events) "NO_NON_EVENTS" else NULL, at = threshold)
      add("ppv", tp, sum(positive), "true_positives", "predicted_events", reason = if (!any(positive)) "NO_PREDICTED_EVENTS" else NULL, at = threshold)
      add("npv", tn, sum(!positive), "true_negatives", "predicted_non_events", reason = if (all(positive)) "NO_PREDICTED_NON_EVENTS" else NULL, at = threshold)
      add("accuracy", tp + tn, n, "correct_classifications", "evaluated_subjects", at = threshold)
    }
  }
  rows
}

penalized_v08_equal <- function(a, b) {
  if (is.null(a) || is.null(b)) return(is.null(a) && is.null(b))
  if (is.numeric(a) && is.numeric(b)) return(length(a) == length(b) && all(is.finite(a)) && all(is.finite(b)) && all(a == b))
  if (is.list(a) && is.list(b)) {
    if (length(a) != length(b)) return(FALSE)
    if (is.null(names(a)) && is.null(names(b))) return(all(vapply(seq_along(a), function(i) penalized_v08_equal(a[[i]], b[[i]]), TRUE)))
    if (is.null(names(a)) || is.null(names(b)) || anyDuplicated(names(a)) || anyDuplicated(names(b)) || !setequal(names(a), names(b))) return(FALSE)
    return(all(vapply(names(a), function(k) penalized_v08_equal(a[[k]], b[[k]]), TRUE)))
  }
  identical(a, b)
}

penalized_v08_validate_model <- function(model, spec, semantics, data, runtime, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, penalized_v08_method(spec))
  need <- function(ok, code = "PENALIZED_FROZEN_MODEL_INVALID") penalized_v08_need(ok, code)
  need(penalized_v08_keys(model, c("schema_version", "method_id", "spec", "semantics", "engine", "preprocessor", "response_transform",
    "selected_lambda", "selected_engine_lambda", "selected_lambda_index", "intercept", "coefficients", "training_outcome_mean",
    "training_subject_ids", "training_group_ids")))
  need(identical(model$schema_version, "clinical-penalized-model@0.8.0-candidate1") && identical(model$method_id, penalized_v08_method(spec)))
  requested <- spec; trained <- model$spec; requested$cohort_id <- NULL; trained$cohort_id <- NULL
  need(penalized_v08_equal(requested, trained) && penalized_v08_equal(semantics, model$semantics), "PENALIZED_FROZEN_SEMANTICS_OR_SPEC_MISMATCH")
  need(penalized_v08_string(model$spec$cohort_id) && !identical(model$spec$cohort_id, spec$cohort_id), "PENALIZED_DISTINCT_EXTERNAL_COHORT_REQUIRED")
  pp <- model$preprocessor
  need(penalized_v08_keys(pp, c("features", "columns", "dropped_columns")) && is.list(pp$features) &&
    length(pp$features) == length(spec$features) && is.list(pp$columns) && length(pp$columns) >= 2L && is.list(pp$dropped_columns))
  expected <- list()
  for (i in seq_along(spec$features)) {
    feature <- spec$features[[i]]; f <- pp$features[[i]]
    need(penalized_v08_keys(f, c("name", "type", "impute", "levels", "reference")) && identical(f$name, feature$name) && identical(f$type, feature$type))
    if (f$type == "number") {
      need(penalized_v08_number(f$impute) && is.list(f$levels) && !length(f$levels) && is.null(f$reference))
      expected[[length(expected) + 1L]] <- list(term = sprintf("X%04d", i), feature = f$name, type = f$type, level = NULL)
    } else {
      need(is.list(f$levels) && length(f$levels) >= 1L && all(vapply(f$levels, penalized_v08_string, TRUE)))
      levels <- penalized_v08_vector(f$levels)
      need(!anyDuplicated(levels) && identical(levels, penalized_v08_sort(levels)) &&
        identical(f$reference, levels[[1L]]) && f$impute %in% levels && length(f$impute) == 1L &&
        all(levels %in% penalized_v08_vector(semantics$features[[i]]$levels)))
      for (j in seq_along(levels[-1L])) expected[[length(expected) + 1L]] <- list(term = sprintf("X%04dL%04d", i, j + 1L),
        feature = f$name, type = f$type, level = levels[[j + 1L]])
    }
  }
  all_columns <- c(pp$columns, pp$dropped_columns)
  need(length(all_columns) == length(expected))
  expected_terms <- vapply(expected, `[[`, "", "term")
  observed_terms <- vapply(all_columns, `[[`, "", "term")
  need(!anyDuplicated(observed_terms) && setequal(observed_terms, expected_terms))
  for (column in pp$columns) {
    need(penalized_v08_keys(column, c("term", "feature", "type", "level", "center", "scale")) &&
      penalized_v08_number(column$center) && penalized_v08_number(column$scale) && column$scale > 0)
    need(penalized_v08_equal(column[c("term", "feature", "type", "level")], expected[[match(column$term, expected_terms)]]))
  }
  need(identical(vapply(pp$columns, `[[`, "", "term"), expected_terms[expected_terms %in% vapply(pp$columns, `[[`, "", "term")]))
  for (column in pp$dropped_columns) need(penalized_v08_keys(column, c("term", "feature", "type", "level", "reason_code")) &&
    identical(column$reason_code, "ZERO_VARIANCE") &&
    penalized_v08_equal(column[c("term", "feature", "type", "level")], expected[[match(column$term, expected_terms)]]))
  engine <- c(runtime, list(solver = penalized_v08_solver(), control = penalized_v08_control(length(pp$columns))))
  need(penalized_v08_equal(model$engine, engine), "PENALIZED_FROZEN_ENGINE_MISMATCH")
  transform <- model$response_transform
  need(penalized_v08_keys(transform, c("method", "center", "scale")) && identical(transform$method, spec$response_transform) &&
    penalized_v08_number(transform$center) && penalized_v08_number(transform$scale) && transform$scale > 0)
  if (spec$family == "binomial") need(transform$center == 0 && transform$scale == 1)
  need(penalized_v08_number(model$intercept) && is.list(model$coefficients) && length(model$coefficients) == length(pp$columns) &&
    all(vapply(model$coefficients, penalized_v08_number, TRUE)) && penalized_v08_number(model$training_outcome_mean))
  k <- model$selected_lambda_index; lambdas <- penalized_v08_vector(spec$lambda_grid)
  need(penalized_v08_number(k) && k == floor(k) && k >= 1L && k <= length(lambdas) &&
    penalized_v08_number(model$selected_lambda) && model$selected_lambda == lambdas[[k]] &&
    penalized_v08_number(model$selected_engine_lambda) && model$selected_engine_lambda > 0 &&
    abs(model$selected_engine_lambda - model$selected_lambda) <= 32 * .Machine$double.eps * abs(model$selected_lambda))
  need(is.list(model$training_subject_ids) && length(model$training_subject_ids) >= 1L &&
    all(vapply(model$training_subject_ids, penalized_v08_string, TRUE)) && is.list(model$training_group_ids) &&
    all(vapply(model$training_group_ids, penalized_v08_string, TRUE)))
  clinical_resource_check_rows(length(model$training_subject_ids), budget, "history")
  if (length(model$training_group_ids)) clinical_resource_check_rows(length(model$training_group_ids), budget, "history")
  clinical_resource_check_design(nrow(data), length(pp$columns), budget)
  ids <- penalized_v08_vector(model$training_subject_ids); groups <- penalized_v08_vector(model$training_group_ids)
  need(!anyDuplicated(ids) && identical(ids, penalized_v08_sort(ids)) && !anyDuplicated(groups))
  need(!any(data[[spec$id]] %in% ids), "PENALIZED_TRAINING_SUBJECT_OVERLAP")
  if (is.null(spec$split$group_field)) need(!length(groups)) else {
    need(length(groups) >= 1L && identical(groups, penalized_v08_sort(groups)))
    need(!any(data[[spec$split$group_field]] %in% groups), "PENALIZED_TRAINING_GROUP_OVERLAP")
  }
  invisible(TRUE)
}

penalized_v08_coefficient_rows <- function(columns, coefficients, intercept, source) {
  metadata <- c(list(list(term = "(Intercept)", feature = NULL, type = "intercept", level = NULL)),
    lapply(columns, function(x) x[c("term", "feature", "type", "level")]))
  values <- c(intercept, coefficients)
  lapply(seq_along(values), function(i) c(metadata[[i]], list(coefficient = values[[i]], nonzero = values[[i]] != 0, source = source)))
}

penalized_v08_analyze <- function(data, options, semantics, frozen_model = NULL, resource_budget = NULL) {
  record <- penalized_v08_empty_record(options, semantics, if (is.data.frame(data)) nrow(data) else 0L)
  stage <- "input"; fold <- NA_integer_; model <- NULL
  tryCatch({
    budget <- clinical_resource_budget(resource_budget, penalized_v08_method(options$spec))
    penalized_v08_validate(data, options, semantics, budget)
    spec <- options$spec; split <- spec$split; operation <- options$operation
    data <- data[order(penalized_v08_key(data[[spec$id]]), method = "radix"), , drop = FALSE]; rownames(data) <- NULL
    training <- data[[split$partition_field]] == "train"; holdout <- !training
    record$flow$n_training <- sum(training); record$flow$n_holdout <- if (operation == "train") sum(holdout) else 0L
    if (operation != "infer") {
      record$flow$missing_outcome_n <- 0L
      if (spec$family == "binomial") {
        outcomes <- data[[spec$outcome]]; evaluation <- if (operation == "train") holdout else rep(TRUE, nrow(data))
        record$flow$n_training_events <- sum(outcomes[training] == 1); record$flow$n_training_non_events <- sum(outcomes[training] == 0)
        record$flow$n_holdout_events <- if (operation == "train") sum(outcomes[holdout] == 1) else 0L
        record$flow$n_holdout_non_events <- if (operation == "train") sum(outcomes[holdout] == 0) else 0L
        record$flow$n_evaluation_events <- sum(outcomes[evaluation] == 1); record$flow$n_evaluation_non_events <- sum(outcomes[evaluation] == 0)
      }
    }
    stage <- "runtime"; runtime <- penalized_v08_runtime()
    add_counts <- function(counts, at, role, fold = NA_integer_) {
      record$preprocessing <<- c(record$preprocessing, lapply(counts, function(x) c(list(stage = at, fold = as.integer(fold), role = role), x)))
    }
    if (operation == "train") {
      penalized_v08_need(is.null(frozen_model), "PENALIZED_UNEXPECTED_FROZEN_MODEL")
      td <- data[training, , drop = FALSE]; y <- td[[spec$outcome]]
      lambdas <- penalized_v08_vector(spec$lambda_grid); losses <- numeric(length(lambdas))
      record$flow$n_cv_folds <- as.integer(split$cv_folds)
      for (fold in seq_len(split$cv_folds)) {
        validation <- td[[split$fold_field]] == fold
        stage <- "cv_preprocessing"; prep <- penalized_v08_prepare(td[!validation, , drop = FALSE], spec$features, resource_budget = budget)
        add_counts(prep$counts, "cv", "fitting", fold)
        valid <- penalized_v08_prepare(td[validation, , drop = FALSE], spec$features, prep$model, resource_budget = budget)
        add_counts(valid$counts, "cv", "validation", fold)
        stage <- "cv_fit"; fit <- penalized_v08_fit(prep$x, y[!validation], spec$family, spec$alpha, lambdas)
        record$diagnostics$n_engine_fits <- record$diagnostics$n_engine_fits + 1L
        record$cv$folds[[fold]] <- list(fold = as.integer(fold), n_training = sum(!validation), n_validation = sum(validation),
          training_events = if (spec$family == "binomial") sum(y[!validation] == 1) else NA_integer_,
          training_non_events = if (spec$family == "binomial") sum(y[!validation] == 0) else NA_integer_,
          n_encoded_columns = ncol(prep$x), n_dropped_columns = length(prep$model$dropped_columns))
        stage <- "cv_validation"; predicted <- penalized_v08_predict(valid$x, fit$coefficients, fit$intercept, fit$response_transform, spec$family)
        fold_losses <- penalized_v08_loss(y[validation], predicted$prediction, predicted$linear_predictor, spec$family)
        losses <- losses + fold_losses
        for (k in seq_along(lambdas)) record$cv$fold_losses[[length(record$cv$fold_losses) + 1L]] <- list(
          fold = as.integer(fold), lambda_index = as.integer(k), lambda = lambdas[[k]], engine_lambda = fit$engine_lambda[[k]],
          loss_sum = fold_losses[[k]], n_validation = sum(validation), mean_loss = fold_losses[[k]] / sum(validation))
      }
      fold <- NA_integer_
      penalized_v08_need(all(is.finite(losses)), "PENALIZED_NONFINITE_LOSS")
      # Requested grid is strictly decreasing; which.min picks the largest lambda on exact ties.
      selected <- which.min(losses / nrow(td))
      record$cv$rows <- lapply(seq_along(lambdas), function(k) list(lambda_index = as.integer(k), lambda = lambdas[[k]],
        loss_sum = losses[[k]], n_validation = nrow(td), mean_loss = losses[[k]] / nrow(td), selected = k == selected))
      record$cv$status <- "completed"; record$cv["reason_code"] <- list(NULL)
      stage <- "final_preprocessing"; prep <- penalized_v08_prepare(td, spec$features, resource_budget = budget)
      add_counts(prep$counts, "final", "fitting")
      stage <- "final_fit"; fit <- penalized_v08_fit(prep$x, y, spec$family, spec$alpha, lambdas)
      record$diagnostics$n_engine_fits <- record$diagnostics$n_engine_fits + 1L
      model <- list(schema_version = "clinical-penalized-model@0.8.0-candidate1", method_id = penalized_v08_method(spec),
        spec = spec, semantics = semantics, engine = c(runtime, list(solver = penalized_v08_solver(), control = fit$control)),
        preprocessor = prep$model, response_transform = fit$response_transform, selected_lambda = lambdas[[selected]],
        selected_engine_lambda = fit$engine_lambda[[selected]], selected_lambda_index = as.integer(selected),
        intercept = fit$intercept[[selected]], coefficients = as.list(as.numeric(fit$coefficients[, selected])),
        training_outcome_mean = mean(y), training_subject_ids = as.list(td[[spec$id]]),
        training_group_ids = if (is.null(split$group_field)) list() else as.list(penalized_v08_sort(unique(td[[split$group_field]]))))
      for (k in seq_along(lambdas)) {
        coefficient_rows <- penalized_v08_coefficient_rows(prep$model$columns, fit$coefficients[, k], fit$intercept[[k]], "training")
        record$path <- c(record$path, lapply(coefficient_rows, function(x) c(list(lambda_index = as.integer(k), lambda = lambdas[[k]],
          engine_lambda = fit$engine_lambda[[k]]), x[setdiff(names(x), "source")])))
      }
      record$coefficients <- penalized_v08_coefficient_rows(prep$model$columns, penalized_v08_vector(model$coefficients), model$intercept, "training")
      stage <- "holdout_prediction"; hp <- penalized_v08_prepare(data[holdout, , drop = FALSE], spec$features, prep$model, resource_budget = budget)
      add_counts(hp$counts, "final", "holdout")
      x <- matrix(NA_real_, nrow(data), ncol(prep$x)); x[training, ] <- prep$x; x[holdout, ] <- hp$x
      predicted <- penalized_v08_predict(x, matrix(penalized_v08_vector(model$coefficients), ncol = 1L), model$intercept, model$response_transform, spec$family)
      stage <- "metrics"
      record$metrics <- penalized_v08_metrics(data[[spec$outcome]][holdout], as.numeric(predicted$prediction[holdout, ]),
        as.numeric(predicted$linear_predictor[holdout, ]), spec$family, model$training_outcome_mean, spec$clinical_threshold, "holdout")
      record$flow$n_evaluated <- sum(holdout)
    } else {
      stage <- "external_validation"; penalized_v08_validate_model(frozen_model, spec, semantics, data, runtime, budget); model <- frozen_model
      record$cv$reason_code <- "FROZEN_MODEL_NO_REFIT"
      stage <- "external_prediction"; prep <- penalized_v08_prepare(data, spec$features, model$preprocessor, resource_budget = budget)
      add_counts(prep$counts, "external", "external")
      predicted <- penalized_v08_predict(prep$x, matrix(penalized_v08_vector(model$coefficients), ncol = 1L),
        model$intercept, model$response_transform, spec$family)
      record$coefficients <- penalized_v08_coefficient_rows(prep$model$columns, penalized_v08_vector(model$coefficients), model$intercept, "frozen_training")
      if (operation == "evaluate") {
        stage <- "metrics"; record$metrics <- penalized_v08_metrics(data[[spec$outcome]], as.numeric(predicted$prediction),
          as.numeric(predicted$linear_predictor), spec$family, model$training_outcome_mean, spec$clinical_threshold, "external")
        record$flow$n_evaluated <- nrow(data)
      }
    }
    record$selected_lambda <- model$selected_lambda; record$selected_engine_lambda <- model$selected_engine_lambda
    record$selected_lambda_index <- as.integer(model$selected_lambda_index)
    record$flow$n_encoded_columns <- length(model$preprocessor$columns)
    record$flow$n_dropped_columns <- length(model$preprocessor$dropped_columns); record$flow$n_predicted <- nrow(data)
    individual <- data.frame(subject_id = data[[spec$id]], group_id = if (is.null(split$group_field)) NA_character_ else data[[split$group_field]],
      partition = data[[split$partition_field]], fold = as.integer(data[[split$fold_field]]),
      observed = if (operation == "infer") NA_real_ else data[[spec$outcome]], prediction = as.numeric(predicted$prediction),
      linear_predictor = as.numeric(predicted$linear_predictor), stringsAsFactors = FALSE)
    record$status <- "completed"; record["reason_code"] <- list(NULL)
    record$diagnostics$stage <- "complete"; record$diagnostics["code"] <- list(NULL)
    record$diagnostics$jerr <- if (operation == "train") 0L else NA_integer_
    list(ok = TRUE, reason_code = NULL, record = record, model = model, individual = individual)
  }, error = function(e) {
    code <- if ((inherits(e, "penalized_v08_blocked") || grepl("^RESOURCE_[A-Z_]+$", conditionMessage(e)))) conditionMessage(e) else "PENALIZED_NUMERIC_EXECUTION_FAILED"
    record$status <- "unavailable"; record$reason_code <- code; record$metrics <- list()
    record$diagnostics$stage <- stage; record$diagnostics$fold <- as.integer(fold); record$diagnostics$code <- code
    record$diagnostics["feature"] <- list(if (inherits(e, "penalized_v08_blocked")) e$feature else NULL)
    if (inherits(e, "penalized_v08_blocked")) {
      record$diagnostics$jerr <- e$jerr; record$diagnostics$warning_count <- e$warning_count
    }
    if (startsWith(stage, "cv_")) { record$cv$status <- "unavailable"; record$cv$reason_code <- code }
    list(ok = FALSE, reason_code = code, record = record, model = NULL, individual = penalized_v08_empty_individual())
  })
}
