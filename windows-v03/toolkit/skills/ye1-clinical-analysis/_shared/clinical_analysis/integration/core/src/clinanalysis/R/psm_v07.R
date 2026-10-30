# Sole v0.7 PSM numerical owner. Model, scores, identities, and pairs are private.
# No alternative estimator, probability clipping, or adaptive caliper is used.
if (!exists("clinical_resource_budget", mode = "function", inherits = TRUE)) {
  .psm_resource_sources <- Filter(Negate(is.null), lapply(sys.frames(), function(frame) frame$ofile))
  if (!length(.psm_resource_sources)) stop("RESOURCE_HELPER_REQUIRED", call. = FALSE)
  .psm_resource_source <- .psm_resource_sources[[length(.psm_resource_sources)]]
  source(file.path(dirname(.psm_resource_source), "clinical_resource_budget.R"), local = TRUE, encoding = "UTF-8")
}

psm_v07_empty_effect <- function(reason = "MATCHING_NOT_RUN") {
  list(status = "unavailable", reason_code = reason,
    inference_status = "unavailable", inference_reason_code = reason,
    estimand = "ATT_retained_matched_treated", measure = "matched_mean_difference",
    direction = "treated_minus_control", n_pairs = 0L,
    treated_mean = NA_real_, control_mean = NA_real_, estimate = NA_real_,
    paired_difference_variance = NA_real_, standard_error = NA_real_, df = NA_integer_,
    ci_level = 0.95, ci_lower = NA_real_, ci_upper = NA_real_,
    t_statistic = NA_real_, p_value = NA_real_,
    treated_variance = NA_real_, control_variance = NA_real_,
    treated_control_covariance = NA_real_, variance_identity_difference = NA_real_,
    conditioning = "formed_matched_pairs", ps_estimation_uncertainty_included = FALSE)
}

psm_v07_empty_record <- function(options, semantics, n_input = 0L) {
  semantics <- c(semantics, list(outcome_type = "continuous",
    event_count_semantics = "not_applicable_continuous_outcome", causal_assumptions_verified = FALSE))
  list(method_id = "causal.psm.att.continuous", status = "unavailable",
    reason_code = "NOT_RUN", options = options, semantics = semantics,
    flow = list(n_input = as.integer(n_input), n_input_treated = NA_integer_,
      n_input_control = NA_integer_, n_excluded_missing_covariates = NA_integer_,
      n_excluded_missing_treated = NA_integer_, n_excluded_missing_control = NA_integer_,
      missing_by_field = structure(list(), names = character()), n_complete_case = NA_integer_,
      n_complete_case_treated = NA_integer_, n_complete_case_control = NA_integer_,
      n_support_retained = NA_integer_, n_support_treated = NA_integer_, n_support_control = NA_integer_,
      n_discarded_support_treated = NA_integer_, n_discarded_support_control = NA_integer_,
      n_matched_pairs = 0L, n_matched_subjects = 0L,
      n_unmatched_support_treated = NA_integer_, n_unmatched_support_control = NA_integer_),
    propensity = list(status = "not_run", reason_code = "NOT_RUN", engine = "stats::glm",
      family = "binomial", link = "logit", fit_scope = "complete_case_pre_support",
      converged = NA, boundary = NA, iterations = NA_integer_,
      n_parameters = NA_integer_, design_rank = NA_integer_,
      probability_min = NA_real_, probability_max = NA_real_,
      logit_min = NA_real_, logit_max = NA_real_, warning_count = 0L,
      numerical_guard_status = "not_run", separation_detection = "numerical_guards_only",
      formal_separation_checked = FALSE),
    support = list(status = "not_run", reason_code = "NOT_RUN", strategy = "minmax_both",
      boundary = "inclusive", refit = FALSE, treated_logit_min = NA_real_, treated_logit_max = NA_real_,
      control_logit_min = NA_real_, control_logit_max = NA_real_, lower = NA_real_, upper = NA_real_,
      overlap_exists = NA, n_retained_treated = NA_integer_, n_retained_control = NA_integer_,
      logit_sd = NA_real_, caliper_multiplier = NA_real_, caliper_width = NA_real_, zero_scale = NA),
    effect = psm_v07_empty_effect(), balance = list(), overlap = list(), warnings = list(),
    limitations = as.list(c("SYNTHETIC_ENGINEERING_ONLY", "ASSUMPTIONS_NOT_VERIFIED",
      "TARGET_RETAINED_MATCHED_TREATED", "INFERENCE_CONDITIONAL_ON_FORMED_PAIRS",
      "PS_ESTIMATION_AND_MATCH_SELECTION_UNCERTAINTY_NOT_INCLUDED",
      "FORMAL_SEPARATION_DETECTION_NOT_IMPLEMENTED", "AGGREGATE_SMALL_CELLS_REQUIRE_REVIEW",
      "PAIR_DIFFERENCES_INDEPENDENCE_AND_T_ASSUMPTIONS_UNVERIFIED")))
}

psm_v07_empty_pairs <- function() {
  data.frame(pair_id = character(), treated_subject_id = character(), control_subject_id = character(),
    treated_ps = double(), control_ps = double(), treated_logit = double(), control_logit = double(),
    logit_distance = double(), treated_outcome = double(), control_outcome = double(), difference = double(),
    stringsAsFactors = FALSE)
}

psm_v07_empty_subjects <- function() {
  data.frame(subject_id = character(), treatment = double(), outcome = double(), complete_case = logical(),
    propensity_score = double(), logit_ps = double(), support_retained = logical(), matched = logical(),
    pair_id = character(), match_role = character(), status = character(), stringsAsFactors = FALSE)
}

psm_v07_need <- function(condition, code) {
  if (!isTRUE(condition)) stop(structure(list(message = code, call = NULL),
    class = c("psm_v07_blocked", "error", "condition")))
}

psm_v07_number <- function(x) {
  is.numeric(x) && !is.complex(x) && length(x) == 1L && !is.na(x) && is.finite(x)
}

psm_v07_string <- function(x) is.character(x) && length(x) == 1L && !is.na(x) && nzchar(trimws(x))

psm_v07_keys <- function(x, keys) {
  is.list(x) && length(x) == length(keys) && !anyDuplicated(names(x)) && setequal(names(x), keys)
}

psm_v07_utf8_key <- function(ids) {
  vapply(enc2utf8(ids), function(x) paste(sprintf("%02x", as.integer(charToRaw(x))), collapse = ""), "")
}

psm_v07_validate <- function(data, options, semantics, resource_budget = NULL) {
  need <- psm_v07_need
  need(psm_v07_keys(options, c("treatment", "outcome", "covariates", "categorical",
    "propensity_model", "link", "estimand", "ratio", "replacement", "distance", "caliper",
    "common_support", "ordering", "inference", "diagnostics", "guards", "prespecified")), "PSM_OPTIONS_INVALID")
  need(psm_v07_keys(semantics, c("subject_id", "treatment_definition", "outcome_definition",
    "outcome_unit", "index_time", "time_unit", "target_population")), "PSM_SEMANTICS_INVALID")
  need(all(vapply(semantics[setdiff(names(semantics), "index_time")], psm_v07_string, TRUE)) &&
    psm_v07_number(semantics$index_time), "PSM_SEMANTICS_INVALID")
  need(psm_v07_string(options$treatment) && psm_v07_string(options$outcome), "PSM_COLUMNS_INVALID")
  need((is.list(options$covariates) || is.character(options$covariates)) &&
    length(options$covariates) >= 1L && length(options$covariates) <= 8L &&
    all(vapply(as.list(options$covariates), psm_v07_string, TRUE)), "PSM_COVARIATES_INVALID")
  covariates <- unlist(options$covariates, use.names = FALSE)
  need(!anyDuplicated(covariates) && !any(covariates %in% c(semantics$subject_id, options$treatment, options$outcome)) &&
    length(unique(c(semantics$subject_id, options$treatment, options$outcome))) == 3L, "PSM_FORBIDDEN_OR_DUPLICATE_COVARIATE")
  need(is.list(options$categorical) && (!length(options$categorical) ||
    (!is.null(names(options$categorical)) && !anyDuplicated(names(options$categorical)) &&
      all(names(options$categorical) %in% covariates))), "PSM_CATEGORICAL_INVALID")
  for (name in names(options$categorical)) {
    entry <- options$categorical[[name]]
    need(psm_v07_keys(entry, c("levels", "reference")) &&
      (is.list(entry$levels) || is.character(entry$levels)) && length(entry$levels) >= 2L &&
      all(vapply(as.list(entry$levels), psm_v07_string, TRUE)) && psm_v07_string(entry$reference), "PSM_CATEGORICAL_INVALID")
    levels <- unlist(entry$levels, use.names = FALSE)
    need(!anyDuplicated(levels) && entry$reference %in% levels, "PSM_CATEGORICAL_INVALID")
  }
  constants <- list(propensity_model = "logistic_mle", link = "logit", estimand = "ATT_retained_matched_treated", distance = "logit_ps")
  need(all(vapply(names(constants), function(k) identical(options[[k]], constants[[k]]), TRUE)) &&
    psm_v07_number(options$ratio) && options$ratio == 1 && identical(options$replacement, FALSE) &&
    identical(options$prespecified, TRUE), "PSM_OPTIONS_UNSUPPORTED")
  cal <- options$caliper
  need(psm_v07_keys(cal, c("width", "scale", "sd_scope", "ddof", "boundary")) &&
    psm_v07_number(cal$width) && cal$width >= 0 && cal$width <= 2 &&
    identical(cal$scale, "sd_logit_ps") && identical(cal$sd_scope, "common_support_retained") &&
    psm_v07_number(cal$ddof) && cal$ddof == 1 && identical(cal$boundary, "inclusive"), "PSM_CALIPER_INVALID")
  support <- options$common_support
  need(psm_v07_keys(support, c("strategy", "boundary", "refit")) &&
    identical(support$strategy, "minmax_both") && identical(support$boundary, "inclusive") && identical(support$refit, FALSE),
    "PSM_SUPPORT_OPTIONS_INVALID")
  ordering <- options$ordering
  need(psm_v07_keys(ordering, c("treated", "control_tie", "row_order")) &&
    identical(ordering$treated, "descending_logit_ps_then_subject_id_utf8") &&
    identical(ordering$control_tie, "subject_id_utf8_ascending") &&
    identical(ordering$row_order, "subject_id_utf8_ascending"), "PSM_ORDERING_INVALID")
  inference <- options$inference
  need(psm_v07_keys(inference, c("method", "ci_level", "variance", "conditioning")) &&
    identical(inference$method, "paired_t") && psm_v07_number(inference$ci_level) && inference$ci_level == 0.95 &&
    identical(inference$variance, "sample_variance_of_pair_differences") &&
    identical(inference$conditioning, "formed_matched_pairs"), "PSM_INFERENCE_INVALID")
  diag <- options$diagnostics
  need(psm_v07_keys(diag, c("smd_denominator", "indicator_sd", "standardize_binary", "ps_overlap_edges", "balance_reference")) &&
    identical(diag$smd_denominator, "pre_support_complete_case_treated_sample_sd") &&
    identical(diag$indicator_sd, "bernoulli_p1mp") && identical(diag$standardize_binary, TRUE) &&
    psm_v07_number(diag$balance_reference) && diag$balance_reference == 0.1, "PSM_DIAGNOSTICS_INVALID")
  edges <- diag$ps_overlap_edges
  need((is.list(edges) || is.numeric(edges)) && length(edges) == 11L &&
    all(vapply(as.list(edges), psm_v07_number, TRUE)) &&
    identical(as.numeric(unlist(edges, use.names = FALSE)), (0:10) / 10), "PSM_OVERLAP_EDGES_INVALID")
  guards <- options$guards
  need(psm_v07_keys(guards, c("min_arm_n", "min_probability", "max_glm_iterations", "glm_epsilon", "separation_detection")) &&
    all(vapply(guards[c("min_arm_n", "min_probability", "max_glm_iterations", "glm_epsilon")], psm_v07_number, TRUE)) &&
    guards$min_arm_n == 2 && guards$min_probability == 1e-6 && guards$max_glm_iterations == 100 && guards$glm_epsilon == 1e-10 &&
    identical(guards$separation_detection, "numerical_guards_only"), "PSM_GUARDS_INVALID")
  need(is.data.frame(data) && nrow(data) > 0L && !anyDuplicated(names(data)), "PSM_DATA_INVALID")
  clinical_resource_check_rows(nrow(data), clinical_resource_budget(resource_budget, "causal.psm.att.continuous"))
  required <- c(semantics$subject_id, options$treatment, options$outcome, covariates)
  need(all(required %in% names(data)), "PSM_REQUIRED_COLUMN_ABSENT")
  ids <- data[[semantics$subject_id]]
  need(is.character(ids) && !anyNA(ids) && all(nzchar(trimws(ids))) && all(validUTF8(enc2utf8(ids))) && !anyDuplicated(ids),
    "PSM_CANONICAL_UNIQUE_SUBJECT_IDS_REQUIRED")
  treatment <- data[[options$treatment]]
  outcome <- data[[options$outcome]]
  need(is.numeric(treatment) && !is.complex(treatment) && !anyNA(treatment) &&
    all(is.finite(treatment)) && all(treatment %in% c(0, 1)), "PSM_TREATMENT_REQUIRED_BINARY_NUMERIC")
  need(is.numeric(outcome) && !is.complex(outcome) && !anyNA(outcome) && all(is.finite(outcome)), "PSM_CONTINUOUS_OUTCOME_REQUIRED_FINITE")
  for (name in covariates) {
    value <- data[[name]]
    if (name %in% names(options$categorical)) {
      need(is.character(value) || is.factor(value), "PSM_CATEGORY_TYPE_INVALID")
      value <- as.character(value)
      observed <- !is.na(value) & value != ""
      need(all(value[observed] %in% unlist(options$categorical[[name]]$levels, use.names = FALSE)), "PSM_UNDECLARED_CATEGORY")
    } else {
      need(is.numeric(value) && !is.complex(value) && !any(is.nan(value)) && all(is.finite(value[!is.na(value)])),
        "PSM_NUMERIC_COVARIATE_INVALID")
    }
  }
  covariates
}

psm_v07_greedy <- function(subject_ids, treatment, logit_ps, eligible, caliper_width) {
  n <- length(subject_ids)
  psm_v07_need(is.character(subject_ids) && !anyNA(subject_ids) && !anyDuplicated(subject_ids) &&
    is.numeric(treatment) && !is.complex(treatment) && length(treatment) == n && !anyNA(treatment) && all(treatment %in% c(0, 1)) &&
    is.numeric(logit_ps) && !is.complex(logit_ps) && length(logit_ps) == n && all(is.finite(logit_ps)) &&
    is.logical(eligible) && length(eligible) == n && !anyNA(eligible) &&
    psm_v07_number(caliper_width) && caliper_width >= 0, "PSM_MATCHING_INPUT_INVALID")
  keys <- psm_v07_utf8_key(subject_ids)
  treated <- which(eligible & treatment == 1)
  treated <- treated[order(-logit_ps[treated], keys[treated], method = "radix")]
  available <- eligible & treatment == 0
  ti <- ci <- integer(); distances <- double()
  for (i in treated) {
    controls <- which(available)
    if (!length(controls)) next
    distance <- abs(logit_ps[i] - logit_ps[controls])
    candidates <- which(is.finite(distance) & distance <= caliper_width)
    if (!length(candidates)) next
    nearest <- min(distance[candidates])
    tied <- controls[candidates[distance[candidates] == nearest]]
    j <- tied[order(keys[tied], method = "radix")][[1L]]
    ti <- c(ti, i); ci <- c(ci, j); distances <- c(distances, nearest)
    available[j] <- FALSE
  }
  data.frame(treated_index = ti, control_index = ci, distance = distances)
}

psm_v07_match <- function(subject_ids, treatment, logit_ps, caliper_multiplier) {
  psm_v07_need(psm_v07_number(caliper_multiplier) && caliper_multiplier >= 0 && caliper_multiplier <= 2,
    "PSM_CALIPER_INVALID")
  # Also validate every input when support is empty and greedy would not run.
  empty <- psm_v07_greedy(subject_ids, treatment, logit_ps, rep(FALSE, length(subject_ids)), 0)
  psm_v07_need(any(treatment == 1) && any(treatment == 0), "PSM_MATCHING_BOTH_ARMS_REQUIRED")
  lower <- max(min(logit_ps[treatment == 1]), min(logit_ps[treatment == 0]))
  upper <- min(max(logit_ps[treatment == 1]), max(logit_ps[treatment == 0]))
  eligible <- logit_ps >= lower & logit_ps <= upper
  result <- list(pairs = empty, support_mask = eligible, lower = lower, upper = upper,
    logit_sd = NA_real_, caliper_width = NA_real_, reason_code = NULL)
  if (lower > upper) { result$reason_code <- "NO_COMMON_SUPPORT"; return(result) }
  # Use the same canonical order as the fitting cohort before SD summation.
  retained <- which(eligible)
  retained <- retained[order(psm_v07_utf8_key(subject_ids[retained]), method = "radix")]
  if (length(retained) >= 2L) {
    result$logit_sd <- stats::sd(logit_ps[retained])
    result$caliper_width <- caliper_multiplier * result$logit_sd
    psm_v07_need(is.finite(result$logit_sd) && is.finite(result$caliper_width), "PSM_CALIPER_SCALE_NONFINITE")
  }
  if (!any(eligible & treatment == 1) || !any(eligible & treatment == 0)) {
    result$reason_code <- "COMMON_SUPPORT_ARM_EMPTY"; return(result)
  }
  result$pairs <- psm_v07_greedy(subject_ids, treatment, logit_ps, eligible, result$caliper_width)
  if (!nrow(result$pairs)) result$reason_code <- "NO_MATCHED_PAIRS"
  result
}

psm_v07_effect <- function(treated_outcomes, control_outcomes) {
  psm_v07_need(is.numeric(treated_outcomes) && !is.complex(treated_outcomes) &&
    is.numeric(control_outcomes) && !is.complex(control_outcomes) &&
    length(treated_outcomes) == length(control_outcomes) &&
    all(is.finite(treated_outcomes)) && all(is.finite(control_outcomes)), "PSM_PAIRED_OUTCOMES_INVALID")
  result <- psm_v07_empty_effect("NO_MATCHED_PAIRS")
  m <- length(treated_outcomes); result$n_pairs <- as.integer(m)
  if (!m) return(result)
  differences <- treated_outcomes - control_outcomes
  means <- c(mean(treated_outcomes), mean(control_outcomes), mean(differences))
  if (any(!is.finite(differences)) || any(!is.finite(means))) {
    result$reason_code <- result$inference_reason_code <- "NONFINITE_PAIRED_MOMENTS"; return(result)
  }
  result$treated_mean <- means[[1L]]; result$control_mean <- means[[2L]]; result$estimate <- means[[3L]]
  result$df <- as.integer(m - 1L)
  result$status <- "partial"
  if (m < 2L) {
    result$reason_code <- result$inference_reason_code <- "INSUFFICIENT_MATCHED_PAIRS"; return(result)
  }
  components <- c(stats::var(differences), stats::var(treated_outcomes), stats::var(control_outcomes),
    stats::cov(treated_outcomes, control_outcomes))
  if (any(!is.finite(components))) {
    result$reason_code <- result$inference_reason_code <- "NONFINITE_PAIRED_MOMENTS"; return(result)
  }
  result$paired_difference_variance <- components[[1L]]
  result$treated_variance <- components[[2L]]; result$control_variance <- components[[3L]]
  result$treated_control_covariance <- components[[4L]]
  identity_difference <- components[[1L]] - (components[[2L]] + components[[3L]] - 2 * components[[4L]])
  if (!is.finite(identity_difference)) {
    result$reason_code <- result$inference_reason_code <- "NONFINITE_PAIRED_MOMENTS"; return(result)
  }
  result$variance_identity_difference <- identity_difference
  result$standard_error <- sqrt(components[[1L]] / m)
  if (components[[1L]] == 0) {
    result$reason_code <- result$inference_reason_code <- "ZERO_PAIRED_VARIANCE"; return(result)
  }
  statistic <- result$estimate / result$standard_error
  critical <- stats::qt(0.975, df = result$df)
  interval <- result$estimate + c(-1, 1) * critical * result$standard_error
  p_value <- 2 * stats::pt(-abs(statistic), df = result$df)
  if (any(!is.finite(c(statistic, interval, p_value)))) {
    result$reason_code <- result$inference_reason_code <- "NONFINITE_PAIRED_INFERENCE"; return(result)
  }
  result$status <- result$inference_status <- "completed"
  result["reason_code"] <- list(NULL); result["inference_reason_code"] <- list(NULL)
  result$t_statistic <- statistic; result$ci_lower <- interval[[1L]]; result$ci_upper <- interval[[2L]]
  result$p_value <- p_value
  result
}

psm_v07_balance <- function(data, options, matched_indices = integer(), after_reason = "MATCHING_NOT_RUN") {
  treatment <- data[[options$treatment]]
  before_t <- which(treatment == 1); before_c <- which(treatment == 0)
  after_t <- matched_indices[treatment[matched_indices] == 1]
  after_c <- matched_indices[treatment[matched_indices] == 0]
  rows <- list()
  for (name in unlist(options$covariates, use.names = FALSE)) {
    categorical <- name %in% names(options$categorical)
    levels <- if (categorical) unlist(options$categorical[[name]]$levels, use.names = FALSE) else NA_character_
    for (level in levels) {
      x <- if (categorical) as.numeric(as.character(data[[name]]) == level) else data[[name]]
      mt <- if (length(before_t)) mean(x[before_t]) else NA_real_
      mc <- if (length(before_c)) mean(x[before_c]) else NA_real_
      sd_ref <- if (categorical && length(before_t)) sqrt(mt * (1 - mt)) else
        if (!categorical && length(before_t) >= 2L) stats::sd(x[before_t]) else NA_real_
      reason_before <- if (!is.finite(sd_ref)) "REFERENCE_SD_UNAVAILABLE" else
        if (sd_ref == 0) "ZERO_REFERENCE_SD" else if (!length(before_c)) "BEFORE_CONTROL_ARM_EMPTY" else NULL
      ma_t <- if (length(after_t)) mean(x[after_t]) else NA_real_
      ma_c <- if (length(after_c)) mean(x[after_c]) else NA_real_
      reason_after <- if (!length(after_t) || !length(after_c)) after_reason else reason_before
      smd_before <- if (is.null(reason_before)) (mt - mc) / sd_ref else NA_real_
      smd_after <- if (is.null(reason_after)) (ma_t - ma_c) / sd_ref else NA_real_
      if (!is.na(smd_before) && !is.finite(smd_before)) { smd_before <- NA_real_; reason_before <- "SMD_NUMERIC_RANGE" }
      if (!is.na(smd_after) && !is.finite(smd_after)) { smd_after <- NA_real_; reason_after <- "SMD_NUMERIC_RANGE" }
      rows[[length(rows) + 1L]] <- list(covariate = name, kind = if (categorical) "indicator" else "numeric",
        level = if (categorical) level else NULL, is_reference = categorical && identical(level, options$categorical[[name]]$reference),
        sd_kind = if (categorical) "bernoulli_p1mp" else "sample_n_minus_1",
        denominator_scope = "pre_support_complete_case_treated", reference_sd = if (is.finite(sd_ref)) sd_ref else NA_real_,
        n_before_treated = length(before_t), n_before_control = length(before_c),
        mean_before_treated = mt, mean_before_control = mc, smd_before = smd_before, smd_before_reason = reason_before,
        n_after_treated = length(after_t), n_after_control = length(after_c), mean_after_treated = ma_t, mean_after_control = ma_c,
        smd_after = smd_after, smd_after_reason = reason_after)
    }
  }
  rows
}

psm_v07_overlap <- function(ps, treatment, support_mask, matched_mask, edges) {
  rows <- list()
  populations <- list(ps_fit = rep(TRUE, length(ps)), support_retained = support_mask, matched = matched_mask)
  for (population in names(populations)) for (arm in c("treated", "control")) {
    selected <- populations[[population]] & treatment == if (arm == "treated") 1 else 0
    denominator <- sum(selected)
    for (i in seq_len(length(edges) - 1L)) {
      inclusive <- i == length(edges) - 1L
      in_bin <- ps >= edges[[i]] & if (inclusive) ps <= edges[[i + 1L]] else ps < edges[[i + 1L]]
      count <- sum(selected & in_bin)
      rows[[length(rows) + 1L]] <- list(population = population, arm = arm, bin_index = i,
        lower = edges[[i]], upper = edges[[i + 1L]], right_inclusive = inclusive,
        n = as.integer(count), denominator = as.integer(denominator),
        proportion = if (denominator) count / denominator else NA_real_)
    }
  }
  rows
}

psm_v07_analyze <- function(data, options, semantics, resource_budget = NULL) {
  record <- psm_v07_empty_record(options, semantics, if (is.data.frame(data)) nrow(data) else 0L)
  private <- list(pairs = psm_v07_empty_pairs(), subjects = psm_v07_empty_subjects(), model = list())
  tryCatch({
    budget <- clinical_resource_budget(resource_budget, "causal.psm.att.continuous")
    covariates <- psm_v07_validate(data, options, semantics, budget)
    # Bound worst-case candidate comparisons before design allocation or PS fit.
    clinical_resource_check_pairs(sum(data[[options$treatment]] == 1), sum(data[[options$treatment]] == 0), budget)
    declared_columns <- 1 + sum(vapply(covariates, function(name)
      if (name %in% names(options$categorical)) length(options$categorical[[name]]$levels) - 1 else 1, 0.0))
    clinical_resource_check_design(nrow(data), declared_columns, budget)
    ids <- data[[semantics$subject_id]]
    data <- data[order(psm_v07_utf8_key(ids), method = "radix"), , drop = FALSE]
    rownames(data) <- NULL
    ids <- data[[semantics$subject_id]]; treatment <- data[[options$treatment]]
    missing <- lapply(covariates, function(name) {
      x <- data[[name]]; is.na(x) | if (name %in% names(options$categorical)) as.character(x) == "" else FALSE
    }); names(missing) <- covariates
    excluded <- Reduce(`|`, missing)
    complete <- !excluded
    cc <- data[complete, , drop = FALSE]; ct <- cc[[options$treatment]]
    record$flow$n_input_treated <- sum(treatment == 1); record$flow$n_input_control <- sum(treatment == 0)
    record$flow$n_excluded_missing_covariates <- sum(excluded)
    record$flow$n_excluded_missing_treated <- sum(excluded & treatment == 1)
    record$flow$n_excluded_missing_control <- sum(excluded & treatment == 0)
    record$flow$missing_by_field <- lapply(missing, function(x) list(n_missing = sum(x),
      n_missing_treated = sum(x & treatment == 1), n_missing_control = sum(x & treatment == 0)))
    record$flow$n_complete_case <- nrow(cc); record$flow$n_complete_case_treated <- sum(ct == 1)
    record$flow$n_complete_case_control <- sum(ct == 0)
    private$subjects <- data.frame(subject_id = ids, treatment = treatment, outcome = data[[options$outcome]], complete_case = complete,
      propensity_score = NA_real_, logit_ps = NA_real_, support_retained = FALSE, matched = FALSE,
      pair_id = NA_character_, match_role = NA_character_, status = ifelse(complete, "fit_not_completed", "excluded_missing_covariates"),
      stringsAsFactors = FALSE)
    record$balance <- psm_v07_balance(cc, options)
    psm_v07_need(sum(ct == 1) >= options$guards$min_arm_n && sum(ct == 0) >= options$guards$min_arm_n,
      "PSM_INSUFFICIENT_COMPLETE_CASE_ARM_N")
    fit_data <- data.frame(.psm_treatment = ct)
    aliases <- paste0(".psm_x", seq_along(covariates)); contrasts <- list()
    for (i in seq_along(covariates)) {
      name <- covariates[[i]]; alias <- aliases[[i]]
      if (name %in% names(options$categorical)) {
        declaration <- options$categorical[[name]]; levels <- unlist(declaration$levels, use.names = FALSE)
        fit_data[[alias]] <- factor(as.character(cc[[name]]), levels = levels)
        contrasts[[alias]] <- stats::contr.treatment(levels, base = match(declaration$reference, levels))
      } else fit_data[[alias]] <- cc[[name]]
    }
    formula <- stats::reformulate(aliases, response = ".psm_treatment", intercept = TRUE)
    design <- stats::model.matrix(formula, data = fit_data, contrasts.arg = if (length(contrasts)) contrasts else NULL)
    record$propensity$n_parameters <- ncol(design)
    record$propensity$design_rank <- qr(design)$rank
    psm_v07_need(record$propensity$design_rank == ncol(design), "PROPENSITY_RANK_DEFICIENT")
    fit_warnings <- character()
    fit <- withCallingHandlers(stats::glm(formula, data = fit_data, family = stats::binomial(link = "logit"),
      contrasts = if (length(contrasts)) contrasts else NULL,
      control = stats::glm.control(epsilon = options$guards$glm_epsilon, maxit = options$guards$max_glm_iterations),
      model = FALSE, x = TRUE, y = TRUE), warning = function(w) {
        fit_warnings <<- c(fit_warnings, conditionMessage(w)); invokeRestart("muffleWarning")
      })
    ps <- unname(fit$fitted.values); logit <- unname(fit$linear.predictors)
    record$propensity$converged <- isTRUE(fit$converged); record$propensity$boundary <- isTRUE(fit$boundary)
    record$propensity$iterations <- as.integer(fit$iter); record$propensity$design_rank <- as.integer(fit$rank)
    record$propensity$warning_count <- length(fit_warnings)
    if (all(is.finite(ps))) { record$propensity$probability_min <- min(ps); record$propensity$probability_max <- max(ps) }
    if (all(is.finite(logit))) { record$propensity$logit_min <- min(logit); record$propensity$logit_max <- max(logit) }
    private$model <- list(schema_version = "clinical-psm-model@0.7.0-candidate1", method_id = "causal.psm.att.continuous",
      engine = "stats::glm", family = "binomial", link = "logit", fit_scope = "complete_case_pre_support",
      design_columns = as.list(colnames(design)), covariates = as.list(covariates), categorical = options$categorical,
      coefficients = lapply(as.list(stats::coef(fit)), function(x) if (is.finite(x)) x else NA_real_),
      fitted_subject_ids = as.list(cc[[semantics$subject_id]]),
      converged = isTRUE(fit$converged), boundary = isTRUE(fit$boundary), iterations = as.integer(fit$iter),
      rank = as.integer(fit$rank), warning_messages = as.list(fit_warnings))
    if (length(fit_warnings)) record$warnings <- list("PROPENSITY_GLM_WARNING")
    psm_v07_need(fit$rank == ncol(design), "PROPENSITY_RANK_DEFICIENT")
    psm_v07_need(all(is.finite(stats::coef(fit))), "PROPENSITY_COEFFICIENT_NONFINITE")
    psm_v07_need(isTRUE(fit$converged), "PROPENSITY_NONCONVERGENCE")
    psm_v07_need(!isTRUE(fit$boundary), "PROPENSITY_BOUNDARY_FIT")
    psm_v07_need(!length(fit_warnings), "PROPENSITY_GLM_WARNING")
    psm_v07_need(length(ps) == nrow(cc) && length(logit) == nrow(cc) && all(is.finite(ps)) && all(is.finite(logit)),
      "PROPENSITY_PREDICTION_NONFINITE")
    psm_v07_need(all(ps > options$guards$min_probability & ps < 1 - options$guards$min_probability), "PROPENSITY_EXTREME_PROBABILITY")
    record$propensity$status <- "completed"; record$propensity["reason_code"] <- list(NULL); record$propensity$numerical_guard_status <- "passed"
    cc_rows <- which(complete)
    private$subjects$propensity_score[cc_rows] <- ps; private$subjects$logit_ps[cc_rows] <- logit
    matched <- psm_v07_match(cc[[semantics$subject_id]], ct, logit, options$caliper$width)
    retained <- matched$support_mask
    record$support$treated_logit_min <- min(logit[ct == 1]); record$support$treated_logit_max <- max(logit[ct == 1])
    record$support$control_logit_min <- min(logit[ct == 0]); record$support$control_logit_max <- max(logit[ct == 0])
    record$support$lower <- matched$lower; record$support$upper <- matched$upper
    record$support$overlap_exists <- matched$lower <= matched$upper
    record$support$n_retained_treated <- sum(retained & ct == 1); record$support$n_retained_control <- sum(retained & ct == 0)
    record$support$logit_sd <- matched$logit_sd; record$support$caliper_multiplier <- options$caliper$width
    record$support$caliper_width <- matched$caliper_width
    record$support$zero_scale <- if (is.finite(matched$logit_sd)) matched$logit_sd == 0 else NA
    support_reason <- if (!is.null(matched$reason_code) && matched$reason_code != "NO_MATCHED_PAIRS") matched$reason_code else NULL
    record$support$status <- if (is.null(support_reason)) "completed" else "unavailable"
    record$support["reason_code"] <- list(support_reason)
    record$flow$n_support_retained <- sum(retained); record$flow$n_support_treated <- sum(retained & ct == 1)
    record$flow$n_support_control <- sum(retained & ct == 0)
    record$flow$n_discarded_support_treated <- sum(!retained & ct == 1); record$flow$n_discarded_support_control <- sum(!retained & ct == 0)
    pairs <- matched$pairs; m <- nrow(pairs)
    selected <- c(pairs$treated_index, pairs$control_index)
    selected_mask <- seq_len(nrow(cc)) %in% selected
    record$flow$n_matched_pairs <- m; record$flow$n_matched_subjects <- 2L * m
    record$flow$n_unmatched_support_treated <- sum(retained & ct == 1) - m
    record$flow$n_unmatched_support_control <- sum(retained & ct == 0) - m
    private$subjects$support_retained[cc_rows] <- retained
    private$subjects$status[cc_rows] <- ifelse(retained, "unmatched_support", "discarded_common_support")
    if (m) {
      ti <- pairs$treated_index; ci <- pairs$control_index
      pair_ids <- sprintf("P%06d", seq_len(m))
      yt <- cc[[options$outcome]][ti]; yc <- cc[[options$outcome]][ci]
      private$pairs <- data.frame(pair_id = pair_ids, treated_subject_id = cc[[semantics$subject_id]][ti],
        control_subject_id = cc[[semantics$subject_id]][ci], treated_ps = ps[ti], control_ps = ps[ci],
        treated_logit = logit[ti], control_logit = logit[ci], logit_distance = pairs$distance,
        treated_outcome = yt, control_outcome = yc, difference = yt - yc, stringsAsFactors = FALSE)
      # An unrepresentable difference is explicitly unavailable in effect;
      # retain the finite observed outcomes and a null private derived value.
      private$pairs$difference[!is.finite(private$pairs$difference)] <- NA_real_
      private$subjects$matched[cc_rows[selected]] <- TRUE
      private$subjects$pair_id[cc_rows[ti]] <- pair_ids; private$subjects$pair_id[cc_rows[ci]] <- pair_ids
      private$subjects$match_role[cc_rows[ti]] <- "treated"; private$subjects$match_role[cc_rows[ci]] <- "control"
      private$subjects$status[cc_rows[selected]] <- "matched"
      record$effect <- psm_v07_effect(yt, yc)
    } else record$effect <- psm_v07_empty_effect(if (is.null(matched$reason_code)) "NO_MATCHED_PAIRS" else matched$reason_code)
    record$balance <- psm_v07_balance(cc, options, selected, after_reason = if (m) NULL else "NO_MATCHED_PAIRS")
    record$overlap <- psm_v07_overlap(ps, ct, retained, selected_mask, unlist(options$diagnostics$ps_overlap_edges, use.names = FALSE))
    record$status <- if (record$effect$status == "completed") "completed" else "partial"
    record["reason_code"] <- list(record$effect$reason_code)
    list(record = record, private = private)
  }, error = function(e) {
    code <- if (inherits(e, "psm_v07_blocked") || inherits(e, "clinical_resource_blocked")) conditionMessage(e) else "PSM_NUMERIC_EXECUTION_FAILED"
    failed <- record; failed$status <- "unavailable"; failed$reason_code <- code
    if (grepl("^PROPENSITY_", code) || code == "PSM_NUMERIC_EXECUTION_FAILED") {
      failed$propensity$status <- "unavailable"; failed$propensity$reason_code <- code
      failed$propensity$numerical_guard_status <- "failed"
    }
    failed$effect <- psm_v07_empty_effect(code)
    list(record = failed, private = private)
  })
}
