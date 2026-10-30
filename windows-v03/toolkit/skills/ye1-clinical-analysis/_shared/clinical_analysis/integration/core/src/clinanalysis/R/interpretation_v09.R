# Exact affine explanations of frozen v0.8 models. No fitting or alternate predictor.

interpretation_v09_definition <- function(family, outcome_unit) {
  list(method = "exact_affine_grouped_interventional_shap", background = "full_frozen_training_empirical",
    coalition_unit = "raw_feature", missing_policy = "frozen_training_median_mode",
    score_scale = if (identical(family, "gaussian")) "signed_original_outcome" else "logit",
    score_unit = if (identical(family, "gaussian")) outcome_unit else "1",
    conditional = FALSE, probability_scale = FALSE, causal = FALSE)
}

interpretation_v09_empty_record <- function(model, model_hash, provider_version, n_application = 0L) {
  list(method_id = "interpretation.linear.interventional", model_method_id = model$method_id, family = model$spec$family,
    status = "unavailable", reason_code = "NOT_RUN", model_sha256 = model_hash, explainer_sha256 = NULL,
    provider_version = provider_version, background_sha256 = NULL, transform_sha256 = NULL,
    definition = interpretation_v09_definition(model$spec$family, model$semantics$outcome$unit),
    flow = list(n_background = NA_integer_, n_application = as.integer(n_application), n_features = length(model$spec$features),
      n_encoded_columns = length(model$preprocessor$columns), n_background_groups = length(model$training_group_ids),
      missing_by_feature = structure(list(), names = character())),
    shap = list(base_value = NA_real_, global_importance = list(),
      additivity = list(atol = 1e-10, rtol = 1e-10, max_abs_error = NA_real_, passed = FALSE)),
    nomogram = list(domain_policy = "frozen_training_observed", constant_model = NA,
      score_at_zero = NA_real_, score_per_point = NA_real_, points_denominator = NA_real_, max_total_points = NA_real_,
      domains = list(), axes = list(), total_axis = list(),
      backcheck = list(atol = 1e-10, rtol = 1e-10, max_score_abs_error = NA_real_, max_prediction_abs_error = NA_real_, passed = FALSE)),
    diagnostics = list(stage = "input", feature = NULL, refit = FALSE, outcomes_used = FALSE, background_sampling = FALSE),
    limitations = as.list(c("SYNTHETIC_ENGINEERING_ONLY", "INTERVENTIONAL_NOT_CONDITIONAL_SHAP", "NOT_PROBABILITY_SCALE_SHAP",
      "NO_CAUSAL_INTERPRETATION", "NO_CLINICAL_VALIDATION", "FROZEN_TRAINING_DOMAIN_ONLY")))
}

interpretation_v09_row_shapes <- function() {
  list(global_importance = list(feature = "x", type = "number", n = 1L, sum_abs_shap = 0, mean_abs_shap = 0, mean_shap = 0, min_shap = 0, max_shap = 0),
    domain = list(feature = "x", type = "number", unit = "1", observed_min = 0, observed_max = 1,
      fitted_levels = list(), fitted_reference = NULL, impute_value = .5, missing_policy = "frozen_training_median_mode",
      encoding_rule = "identity_numeric", n_encoded_columns = 1L, score_min = 0, score_max = 1, score_range = 1),
    axis = list(feature = "x", type = "number", unit = "1", input_kind = "value", value = 0, resolved_value = 0,
      score_contribution = 0, points = 0),
    total_axis = list(total_points = 0, score = 0, prediction = 0))
}

interpretation_v09_empty_private <- function() {
  list(individual = data.frame(subject_id = character(), feature = character(), phi = double(), base_value = double(),
      score = double(), prediction = double(), stringsAsFactors = FALSE),
    encoded_individual = data.frame(subject_id = character(), term = character(), feature = character(), encoded_value = double(),
      background_mean = double(), coefficient = double(), phi = double(), stringsAsFactors = FALSE),
    nomogram_individual = data.frame(subject_id = character(), feature = character(), score_contribution = double(), points = double(),
      total_points = double(), reconstructed_score = double(), reconstructed_prediction = double(),
      score_error = double(), prediction_error = double(), stringsAsFactors = FALSE))
}

interpretation_v09_need <- function(ok, code, feature = NULL) {
  if (!isTRUE(ok)) stop(structure(list(message = code, call = NULL, feature = feature),
    class = c("interpretation_v09_blocked", "error", "condition")))
}

interpretation_v09_canonical <- function(x) {
  if (!is.list(x)) return(x)
  if (!is.null(names(x))) {
    interpretation_v09_need(!anyDuplicated(names(x)), "INTERPRETATION_DUPLICATE_OBJECT_KEYS")
    x <- x[order(penalized_v08_key(names(x)), method = "radix")]
  }
  lapply(x, interpretation_v09_canonical)
}

interpretation_v09_hash <- function(x) {
  interpretation_v09_need(requireNamespace("jsonlite", quietly = TRUE) && requireNamespace("digest", quietly = TRUE),
    "INTERPRETATION_JSON_HASH_ENGINE_UNAVAILABLE")
  json <- jsonlite::toJSON(interpretation_v09_canonical(x), auto_unbox = TRUE, null = "null", na = "null", digits = 17, pretty = FALSE)
  digest::digest(enc2utf8(as.character(json)), algo = "sha256", serialize = FALSE)
}

interpretation_v09_hash_string <- function(x) is.character(x) && length(x) == 1L && !is.na(x) && grepl("^[0-9a-f]{64}$", x)

interpretation_v09_transform <- function(model) {
  list(preprocessor = model$preprocessor, response_transform = model$response_transform, coefficients = model$coefficients,
    intercept = model$intercept, features = model$spec$features, feature_semantics = model$semantics$features)
}

interpretation_v09_check_model <- function(model, model_hash, provider_version, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  need <- interpretation_v09_need
  need(interpretation_v09_hash_string(model_hash) && interpretation_v09_hash_string(provider_version), "INTERPRETATION_HASH_BINDING_INVALID")
  methods <- c("prediction.continuous.signed.lasso", "prediction.continuous.signed.elasticnet", "prediction.binary.lasso", "prediction.binary.elasticnet")
  need(is.list(model) && model$method_id %in% methods && length(model$method_id) == 1L, "INTERPRETATION_MODEL_METHOD_UNSUPPORTED")
  # Reuse the old frozen-model validator with an empty application identity set;
  # the interpretation background itself is the training population.
  spec <- model$spec; spec$cohort_id <- paste0(spec$cohort_id, "__interpretation_validation")
  empty <- setNames(list(character()), spec$id)
  if (!is.null(spec$split$group_field)) empty[[spec$split$group_field]] <- character()
  tryCatch(penalized_v08_validate_model(model, spec, model$semantics, as.data.frame(empty, stringsAsFactors = FALSE), penalized_v08_runtime(), budget),
    error = function(e) need(FALSE, if (grepl("^RESOURCE_[A-Z_]+$", conditionMessage(e)))
      conditionMessage(e) else "INTERPRETATION_FROZEN_MODEL_INVALID"))
  need(model$spec$family %in% c("gaussian", "binomial") && length(model$spec$features) <= 12L &&
    length(model$preprocessor$columns) <= 60L, "INTERPRETATION_FROZEN_MODEL_INVALID")
  need(penalized_v08_string(model$semantics$outcome$unit), "INTERPRETATION_FROZEN_MODEL_INVALID")
  invisible(TRUE)
}

interpretation_v09_check_data <- function(data, model, resource_budget = NULL, kind = "input") {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  need <- interpretation_v09_need
  need(is.data.frame(data) && nrow(data) >= 1L && !anyDuplicated(names(data)), "INTERPRETATION_DATA_INVALID")
  clinical_resource_check_rows(nrow(data), budget, kind)
  clinical_resource_check_design(nrow(data), length(model$preprocessor$columns), budget)
  features <- vapply(model$spec$features, `[[`, "", "name")
  need(all(c(model$spec$id, features) %in% names(data)), "INTERPRETATION_REQUIRED_COLUMN_ABSENT")
  ids <- data[[model$spec$id]]
  need(is.character(ids) && !anyNA(ids) && !anyDuplicated(ids) && all(nzchar(trimws(ids))) && all(validUTF8(enc2utf8(ids))),
    "INTERPRETATION_UNIQUE_STRING_IDS_REQUIRED")
  for (f in model$spec$features) {
    x <- data[[f$name]]
    # JSON/CSV readers can lose declared storage type when every value is null.
    # Restore only ordinary, entirely missing vectors; never coerce observations.
    untyped_missing <- (is.logical(x) || is.numeric(x)) && !is.complex(x) &&
      !is.object(x) && is.null(dim(x)) && all(is.na(x)) && !any(is.nan(x))
    if (untyped_missing && (f$type == "category" || is.logical(x))) {
      x <- rep(if (f$type == "category") NA_character_ else NA_real_, length(x))
      data[[f$name]] <- x
    }
    if (f$type == "number") need(is.numeric(x) && !is.complex(x) && !any(is.nan(x)) && all(is.finite(x[!is.na(x)])),
      "INTERPRETATION_NUMERIC_FEATURE_INVALID", f$name)
    else need(is.character(x) || is.factor(x), "INTERPRETATION_CATEGORY_FEATURE_INVALID", f$name)
  }
  data <- data[order(penalized_v08_key(ids), method = "radix"), , drop = FALSE]
  rownames(data) <- NULL
  data
}

interpretation_v09_prepare <- function(data, model, resource_budget = NULL, row_kind = "input") {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  tryCatch(penalized_v08_prepare(data, model$spec$features, fitted = model$preprocessor, resource_budget = budget, row_kind = row_kind), error = function(e) {
    code <- if (grepl("^RESOURCE_[A-Z_]+$", conditionMessage(e))) conditionMessage(e) else if (identical(conditionMessage(e), "PENALIZED_UNKNOWN_OBSERVED_CATEGORY")) "INTERPRETATION_UNKNOWN_CATEGORY" else "INTERPRETATION_FROZEN_PREPROCESSING_FAILED"
    interpretation_v09_need(FALSE, code, if (inherits(e, "penalized_v08_blocked")) e$feature else NULL)
  })
}

interpretation_v09_score_parameters <- function(model) {
  gamma <- penalized_v08_vector(model$coefficients); intercept <- model$intercept
  if (model$spec$family == "gaussian") {
    gamma <- model$response_transform$scale * gamma
    intercept <- model$response_transform$center + model$response_transform$scale * intercept
  }
  interpretation_v09_need(all(is.finite(gamma)) && is.finite(intercept), "INTERPRETATION_NONFINITE_SCORE_PARAMETERS")
  list(gamma = gamma, intercept = intercept)
}

interpretation_v09_group_scores <- function(x, model, gamma) {
  names <- vapply(model$spec$features, `[[`, "", "name")
  owners <- vapply(model$preprocessor$columns, `[[`, "", "feature")
  weighted <- sweep(x, 2L, gamma, `*`)
  interpretation_v09_need(all(is.finite(weighted)), "INTERPRETATION_NONFINITE_CONTRIBUTION")
  result <- do.call(cbind, lapply(names, function(name) {
    columns <- which(owners == name)
    if (length(columns)) rowSums(weighted[, columns, drop = FALSE]) else rep(0, nrow(x))
  }))
  colnames(result) <- names
  interpretation_v09_need(all(is.finite(result)), "INTERPRETATION_NONFINITE_CONTRIBUTION")
  result
}

interpretation_v09_rows <- function(data, model) {
  fields <- c(model$spec$id, vapply(model$spec$features, `[[`, "", "name"))
  lapply(seq_len(nrow(data)), function(i) {
    values <- lapply(fields, function(field) {
      value <- data[[field]][[i]]
      if (is.factor(value)) value <- as.character(value)
      if (is.na(value) || (is.character(value) && !nzchar(value))) NULL else value
    })
    names(values) <- fields
    values
  })
}

interpretation_v09_rows_data <- function(rows, model, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  need <- interpretation_v09_need
  need(is.list(rows) && length(rows) >= 1L, "INTERPRETATION_BACKGROUND_ROWS_INVALID")
  clinical_resource_check_rows(length(rows), budget, "background")
  clinical_resource_check_design(length(rows), length(model$preprocessor$columns), budget)
  fields <- c(model$spec$id, vapply(model$spec$features, `[[`, "", "name"))
  need(all(vapply(rows, function(row) penalized_v08_keys(row, fields), TRUE)), "INTERPRETATION_BACKGROUND_ROWS_INVALID")
  columns <- setNames(list(vapply(rows, function(row) {
    need(penalized_v08_string(row[[model$spec$id]]), "INTERPRETATION_BACKGROUND_ROWS_INVALID")
    row[[model$spec$id]]
  }, "")), model$spec$id)
  for (f in model$spec$features) {
    columns[[f$name]] <- vapply(rows, function(row) {
      value <- row[[f$name]]
      if (is.null(value)) return(if (f$type == "number") NA_real_ else NA_character_)
      need(if (f$type == "number") penalized_v08_number(value) else penalized_v08_string(value),
        "INTERPRETATION_BACKGROUND_ROWS_INVALID", f$name)
      value
    }, if (f$type == "number") 0 else "")
  }
  as.data.frame(columns, stringsAsFactors = FALSE, check.names = FALSE)
}

interpretation_v09_nomogram <- function(background, model, parameters) {
  domains <- axes <- list(); coefficients <- parameters$gamma
  owners <- vapply(model$preprocessor$columns, `[[`, "", "feature")
  for (j in seq_along(model$spec$features)) {
    feature <- model$spec$features[[j]]; fm <- model$preprocessor$features[[j]]
    raw <- background[[feature$name]]; if (feature$type == "category") raw <- as.character(raw)
    missing <- is.na(raw) | if (feature$type == "category") raw == "" else FALSE
    interpretation_v09_need(any(!missing), "INTERPRETATION_ALL_MISSING_BACKGROUND_FEATURE", feature$name)
    if (feature$type == "number") {
      low <- min(raw[!missing]); high <- max(raw[!missing])
      fractions <- seq(0, 1, length.out = 5L)
      values <- as.list(unique((1 - fractions) * low + fractions * high))
      interpretation_v09_need(fm$impute >= low && fm$impute <= high, "INTERPRETATION_BACKGROUND_TRANSFORM_MISMATCH", feature$name)
    } else {
      low <- high <- NULL; values <- fm$levels
      interpretation_v09_need(identical(penalized_v08_sort(unique(raw[!missing])), penalized_v08_vector(fm$levels)),
        "INTERPRETATION_BACKGROUND_TRANSFORM_MISMATCH", feature$name)
    }
    axis_values <- c(values, list(NULL)); n_axis <- length(axis_values)
    reference_data <- lapply(model$preprocessor$features, function(f) rep(f$impute, n_axis))
    names(reference_data) <- vapply(model$spec$features, `[[`, "", "name")
    reference_data[[feature$name]] <- vapply(axis_values, function(value) {
      if (is.null(value)) if (feature$type == "number") NA_real_ else NA_character_ else value
    }, if (feature$type == "number") 0 else "")
    reference_data <- as.data.frame(reference_data, stringsAsFactors = FALSE, check.names = FALSE)
    transformed <- interpretation_v09_prepare(reference_data, model)$x
    contributions <- interpretation_v09_group_scores(transformed, model, coefficients)[, j]
    minimum <- min(contributions); maximum <- max(contributions); spread <- maximum - minimum
    interpretation_v09_need(is.finite(spread) && spread >= 0, "INTERPRETATION_NONFINITE_NOMOGRAM_DOMAIN", feature$name)
    unit <- model$semantics$features[[j]]$unit
    domains[[j]] <- list(feature = feature$name, type = feature$type, unit = unit, observed_min = low, observed_max = high,
      fitted_levels = fm$levels, fitted_reference = fm$reference, impute_value = fm$impute,
      missing_policy = "frozen_training_median_mode", encoding_rule = if (feature$type == "number") "identity_numeric" else "treatment_utf8_observed_reference_first",
      n_encoded_columns = sum(owners == feature$name), score_min = minimum, score_max = maximum, score_range = spread)
    for (i in seq_along(axis_values)) axes[[length(axes) + 1L]] <- list(feature = feature$name, type = feature$type, unit = unit,
      input_kind = if (is.null(axis_values[[i]])) "missing" else "value", value = axis_values[[i]],
      resolved_value = if (is.null(axis_values[[i]])) fm$impute else axis_values[[i]], score_contribution = contributions[[i]], points = NA_real_)
  }
  ranges <- vapply(domains, `[[`, 0, "score_range"); denominator <- max(ranges); constant <- denominator == 0
  per_point <- if (constant) NULL else denominator / 100
  interpretation_v09_need(constant || (is.finite(per_point) && per_point > 0), "INTERPRETATION_NOMOGRAM_SCALE_UNREPRESENTABLE")
  score_zero <- parameters$intercept + sum(vapply(domains, `[[`, 0, "score_min"))
  max_points <- if (constant) 0 else sum((ranges / denominator) * 100)
  interpretation_v09_need(is.finite(score_zero) && is.finite(max_points), "INTERPRETATION_NONFINITE_NOMOGRAM_DOMAIN")
  for (i in seq_along(axes)) {
    axis <- axes[[i]]; j <- match(axis$feature, vapply(domains, `[[`, "", "feature"))
    axes[[i]]$points <- if (constant) 0 else ((axis$score_contribution - domains[[j]]$score_min) / denominator) * 100
    interpretation_v09_need(is.finite(axes[[i]]$points) && axes[[i]]$points >= 0, "INTERPRETATION_NONFINITE_NOMOGRAM_POINTS", axis$feature)
  }
  total_points <- if (constant) 0 else seq(0, max_points, length.out = 5L)
  total_axis <- lapply(total_points, function(points) {
    score <- if (constant) score_zero else score_zero + per_point * points
    prediction <- if (model$spec$family == "gaussian") score else stats::plogis(score)
    interpretation_v09_need(is.finite(score) && is.finite(prediction), "INTERPRETATION_NONFINITE_NOMOGRAM_DOMAIN")
    list(total_points = points, score = score, prediction = prediction)
  })
  list(domain_policy = "frozen_training_observed", constant_model = constant, score_at_zero = score_zero,
    score_per_point = per_point, points_denominator = denominator, max_total_points = max_points,
    domains = domains, axes = axes, total_axis = total_axis)
}

interpretation_v09_build <- function(background, model, model_hash, provider_version, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  background <- interpretation_v09_check_data(background, model, budget, "background")
  interpretation_v09_need(identical(as.list(background[[model$spec$id]]), model$training_subject_ids), "INTERPRETATION_BACKGROUND_SUBJECT_SET_MISMATCH")
  prep <- interpretation_v09_prepare(background, model, budget, "background")
  means <- colMeans(prep$x)
  interpretation_v09_need(all(is.finite(means)), "INTERPRETATION_NONFINITE_BACKGROUND_MEAN")
  parameters <- interpretation_v09_score_parameters(model)
  base <- parameters$intercept + sum(parameters$gamma * means)
  interpretation_v09_need(is.finite(base), "INTERPRETATION_NONFINITE_BASE_VALUE")
  rows <- interpretation_v09_rows(background, model)
  columns <- model$preprocessor$columns
  list(schema_version = "clinical-frozen-interpretation@0.9.0-candidate1", method_id = "interpretation.linear.interventional",
    model_method_id = model$method_id, model_sha256 = model_hash, model_content_sha256 = interpretation_v09_hash(model),
    provider_version = provider_version, transform_sha256 = interpretation_v09_hash(interpretation_v09_transform(model)),
    definition = interpretation_v09_definition(model$spec$family, model$semantics$outcome$unit),
    background = list(scope = "full_training", n = nrow(background), subject_ids_sha256 = interpretation_v09_hash(model$training_subject_ids),
      training_groups_sha256 = interpretation_v09_hash(model$training_group_ids), rows_sha256 = interpretation_v09_hash(rows), rows = rows,
      encoded_means = lapply(seq_along(columns), function(i) list(term = columns[[i]]$term, mean = means[[i]]))),
    score = list(intercept = parameters$intercept, coefficients = lapply(seq_along(columns), function(i)
      list(term = columns[[i]]$term, feature = columns[[i]]$feature, coefficient = parameters$gamma[[i]])), base_value = base),
    nomogram = interpretation_v09_nomogram(background, model, parameters))
}

interpretation_v09_freeze <- function(data, model, model_hash, provider_version, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  interpretation_v09_check_model(model, model_hash, provider_version, budget)
  interpretation_v09_need(is.data.frame(data) && model$spec$split$partition_field %in% names(data), "INTERPRETATION_TRAINING_PARTITION_REQUIRED")
  clinical_resource_check_rows(nrow(data), budget)
  partition <- data[[model$spec$split$partition_field]]
  interpretation_v09_need(is.character(partition) && !anyNA(partition) && all(partition %in% c("train", "holdout")),
    "INTERPRETATION_TRAINING_PARTITION_REQUIRED")
  training <- data[partition == model$spec$split$training_value, , drop = FALSE]
  training <- interpretation_v09_check_data(training, model, budget, "background")
  if (!is.null(model$spec$split$group_field)) {
    field <- model$spec$split$group_field
    interpretation_v09_need(field %in% names(training), "INTERPRETATION_BACKGROUND_GROUP_SET_MISMATCH")
    groups <- training[[field]]
    interpretation_v09_need(is.character(groups) && !anyNA(groups) && all(nzchar(trimws(groups))) &&
      identical(as.list(penalized_v08_sort(unique(groups))), model$training_group_ids), "INTERPRETATION_BACKGROUND_GROUP_SET_MISMATCH")
  }
  interpretation_v09_build(training, model, model_hash, provider_version, budget)
}

interpretation_v09_validate_bundle <- function(explainer, model, model_hash, provider_version, resource_budget = NULL) {
  budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
  keys <- c("schema_version", "method_id", "model_method_id", "model_sha256", "model_content_sha256", "provider_version",
    "transform_sha256", "definition", "background", "score", "nomogram")
  interpretation_v09_need(penalized_v08_keys(explainer, keys), "INTERPRETATION_EXPLAINER_FIELDS_INVALID")
  interpretation_v09_need(identical(explainer$model_sha256, model_hash) && identical(explainer$provider_version, provider_version),
    "INTERPRETATION_EXPLAINER_BINDING_MISMATCH")
  interpretation_v09_need(penalized_v08_keys(explainer$background, c("scope", "n", "subject_ids_sha256", "training_groups_sha256", "rows_sha256", "rows", "encoded_means")),
    "INTERPRETATION_EXPLAINER_FIELDS_INVALID")
  background <- interpretation_v09_rows_data(explainer$background$rows, model, budget)
  interpretation_v09_need(identical(as.list(background[[model$spec$id]]), model$training_subject_ids), "INTERPRETATION_BACKGROUND_SUBJECT_SET_MISMATCH")
  expected <- interpretation_v09_build(background, model, model_hash, provider_version, budget)
  interpretation_v09_need(penalized_v08_equal(explainer, expected), "INTERPRETATION_EXPLAINER_DERIVED_CONTENT_MISMATCH")
  list(background = background, expected = expected)
}

interpretation_v09_check_domain <- function(data, domains) {
  for (domain in domains) {
    x <- data[[domain$feature]]
    if (domain$type == "number") interpretation_v09_need(all(x[!is.na(x)] >= domain$observed_min & x[!is.na(x)] <= domain$observed_max),
      "INTERPRETATION_NUMERIC_OUT_OF_DOMAIN", domain$feature)
    else {
      x <- as.character(x); present <- !is.na(x) & x != ""
      interpretation_v09_need(all(x[present] %in% penalized_v08_vector(domain$fitted_levels)), "INTERPRETATION_UNKNOWN_CATEGORY", domain$feature)
    }
  }
}

interpretation_v09_close <- function(a, b) all(is.finite(a)) && all(is.finite(b)) &&
  all(abs(a - b) <= 1e-10 + 1e-10 * pmax(abs(a), abs(b)))

interpretation_v09_analyze <- function(data, model, explainer, model_hash, provider_version, resource_budget = NULL) {
  record <- interpretation_v09_empty_record(model, model_hash, provider_version, if (is.data.frame(data)) nrow(data) else 0L)
  empty <- interpretation_v09_empty_private(); stage <- "model_validation"
  tryCatch({
    budget <- clinical_resource_budget(resource_budget, "interpretation.linear.interventional")
    interpretation_v09_check_model(model, model_hash, provider_version, budget)
    stage <- "bundle_validation"; validated <- interpretation_v09_validate_bundle(explainer, model, model_hash, provider_version, budget)
    # Exact derived-content validation precedes canonical native scalar storage.
    # JSON has one number type whereas R may reload integral doubles as integers.
    explainer <- validated$expected
    stage <- "application_validation"; data <- interpretation_v09_check_data(data, model, budget)
    interpretation_v09_need(!any(data[[model$spec$id]] %in% penalized_v08_vector(model$training_subject_ids)), "INTERPRETATION_TRAINING_SUBJECT_OVERLAP")
    if (!is.null(model$spec$split$group_field)) {
      field <- model$spec$split$group_field
      interpretation_v09_need(field %in% names(data) && is.character(data[[field]]) && !anyNA(data[[field]]) &&
        all(nzchar(trimws(data[[field]]))) && !any(data[[field]] %in% penalized_v08_vector(model$training_group_ids)), "INTERPRETATION_TRAINING_GROUP_OVERLAP")
    }
    interpretation_v09_check_domain(data, explainer$nomogram$domains)
    stage <- "frozen_prediction"; prep <- interpretation_v09_prepare(data, model, budget)
    background_prep <- interpretation_v09_prepare(validated$background, model, budget, "background")
    predicted <- penalized_v08_predict(prep$x, matrix(penalized_v08_vector(model$coefficients), ncol = 1L),
      model$intercept, model$response_transform, model$spec$family)
    score <- as.numeric(if (model$spec$family == "gaussian") predicted$prediction else predicted$linear_predictor)
    prediction <- as.numeric(predicted$prediction)
    record$flow$n_background <- nrow(validated$background)
    for (i in seq_along(model$spec$features)) record$flow$missing_by_feature[[model$spec$features[[i]]$name]] <- list(
      n_background_missing = background_prep$counts[[i]]$n_missing, n_application_missing = prep$counts[[i]]$n_missing)
    record$background_sha256 <- explainer$background$rows_sha256; record$transform_sha256 <- explainer$transform_sha256
    stage <- "shap"; gamma <- vapply(explainer$score$coefficients, `[[`, 0, "coefficient")
    means <- vapply(explainer$background$encoded_means, `[[`, 0, "mean")
    encoded_phi <- sweep(sweep(prep$x, 2L, means, `-`), 2L, gamma, `*`)
    phi <- interpretation_v09_group_scores(sweep(prep$x, 2L, means, `-`), model, gamma)
    base <- explainer$score$base_value; reconstructed <- base + rowSums(phi)
    interpretation_v09_need(interpretation_v09_close(reconstructed, score), "INTERPRETATION_SHAP_ADDITIVITY_FAILED")
    record$shap$base_value <- base; record$shap$additivity$max_abs_error <- max(abs(reconstructed - score)); record$shap$additivity$passed <- TRUE
    record$shap$global_importance <- lapply(seq_along(model$spec$features), function(j) {
      values <- phi[, j]; total <- sum(abs(values))
      interpretation_v09_need(is.finite(total), "INTERPRETATION_NONFINITE_CONTRIBUTION", model$spec$features[[j]]$name)
      list(feature = model$spec$features[[j]]$name, type = model$spec$features[[j]]$type, n = nrow(data),
        sum_abs_shap = total, mean_abs_shap = total / nrow(data), mean_shap = mean(values), min_shap = min(values), max_shap = max(values))
    })
    stage <- "nomogram"; nomogram <- explainer$nomogram
    group_scores <- interpretation_v09_group_scores(prep$x, model, gamma)
    minimum <- vapply(nomogram$domains, `[[`, 0, "score_min")
    points <- if (nomogram$constant_model) matrix(0, nrow(data), length(model$spec$features)) else
      (sweep(group_scores, 2L, minimum, `-`) / nomogram$points_denominator) * 100
    interpretation_v09_need(all(is.finite(points)) && all(points >= 0), "INTERPRETATION_NONFINITE_NOMOGRAM_POINTS")
    totals <- rowSums(points)
    mapped_score <- if (nomogram$constant_model) rep(nomogram$score_at_zero, nrow(data)) else nomogram$score_at_zero + nomogram$score_per_point * totals
    mapped_prediction <- if (model$spec$family == "gaussian") mapped_score else stats::plogis(mapped_score)
    interpretation_v09_need(interpretation_v09_close(mapped_score, score) && interpretation_v09_close(mapped_prediction, prediction),
      "INTERPRETATION_NOMOGRAM_BACKCHECK_FAILED")
    record$nomogram <- c(nomogram, list(backcheck = list(atol = 1e-10, rtol = 1e-10,
      max_score_abs_error = max(abs(mapped_score - score)), max_prediction_abs_error = max(abs(mapped_prediction - prediction)), passed = TRUE)))
    ids <- data[[model$spec$id]]; n <- nrow(data); p <- length(model$spec$features); k <- ncol(prep$x)
    individual <- data.frame(subject_id = rep(ids, each = p), feature = rep(vapply(model$spec$features, `[[`, "", "name"), n),
      phi = as.numeric(t(phi)), base_value = base, score = rep(score, each = p), prediction = rep(prediction, each = p), stringsAsFactors = FALSE)
    encoded_individual <- data.frame(subject_id = rep(ids, each = k), term = rep(vapply(model$preprocessor$columns, `[[`, "", "term"), n),
      feature = rep(vapply(model$preprocessor$columns, `[[`, "", "feature"), n), encoded_value = as.numeric(t(prep$x)),
      background_mean = rep(means, n), coefficient = rep(gamma, n), phi = as.numeric(t(encoded_phi)), stringsAsFactors = FALSE)
    nomogram_individual <- data.frame(subject_id = rep(ids, each = p), feature = rep(vapply(model$spec$features, `[[`, "", "name"), n),
      score_contribution = as.numeric(t(group_scores)), points = as.numeric(t(points)), total_points = rep(totals, each = p),
      reconstructed_score = rep(mapped_score, each = p), reconstructed_prediction = rep(mapped_prediction, each = p),
      score_error = rep(mapped_score - score, each = p), prediction_error = rep(mapped_prediction - prediction, each = p), stringsAsFactors = FALSE)
    record$status <- "completed"; record["reason_code"] <- list(NULL); record$diagnostics$stage <- "complete"
    list(ok = TRUE, reason_code = NULL, record = record, individual = individual,
      encoded_individual = encoded_individual, nomogram_individual = nomogram_individual)
  }, error = function(e) {
    code <- if ((inherits(e, "interpretation_v09_blocked") || grepl("^RESOURCE_[A-Z_]+$", conditionMessage(e)))) conditionMessage(e) else "INTERPRETATION_NUMERIC_EXECUTION_FAILED"
    if (stage == "shap") record$shap <- interpretation_v09_empty_record(model, model_hash, provider_version)$shap
    if (stage == "nomogram") record$nomogram <- interpretation_v09_empty_record(model, model_hash, provider_version)$nomogram
    record$status <- "unavailable"; record$reason_code <- code; record$diagnostics$stage <- stage
    record$diagnostics["feature"] <- list(if (inherits(e, "interpretation_v09_blocked")) e$feature else NULL)
    c(list(ok = FALSE, reason_code = code, record = record), empty)
  })
}
