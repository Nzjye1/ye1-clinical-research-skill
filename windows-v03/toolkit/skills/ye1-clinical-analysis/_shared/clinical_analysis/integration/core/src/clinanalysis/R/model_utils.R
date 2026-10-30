model_terms <- function(analysis, include_exposure = TRUE) {
  covariates <- unlist(analysis$covariates %||% list(), use.names = FALSE)
  spline_covariates <- unlist(analysis$spline_covariates %||% list(), use.names = FALSE)
  spline_df <- as.integer(analysis$spline_df %||% 3L)
  terms <- vapply(covariates, function(variable) {
    if (variable %in% spline_covariates) sprintf("splines::ns(%s, df = %d)", variable, spline_df) else variable
  }, character(1))
  if (isTRUE(include_exposure)) terms <- c(analysis$exposure, terms)
  modifiers <- unlist(analysis$effect_modifiers %||% list(), use.names = FALSE)
  if (length(modifiers)) {
    terms <- c(terms, paste(analysis$exposure, modifiers, sep = ":"))
  }
  unique(terms[!is.na(terms) & nzchar(terms)])
}

normalize_seed_for_r <- function(seed) {
  seed <- as.numeric(seed)
  if (length(seed) != 1L || !is.finite(seed) || seed < 1 || seed != floor(seed)) {
    stop("missing_data.seed must be one positive finite integer", call. = FALSE)
  }
  # R's set.seed() accepts only a signed 32-bit integer. Preserve an
  # arbitrarily large frozen master seed through a deterministic modulo map.
  as.integer(((seed - 1) %% .Machine$integer.max) + 1)
}

model_formula <- function(analysis, response = analysis$outcome, include_exposure = TRUE) {
  stats::reformulate(model_terms(analysis, include_exposure), response = response)
}

robust_model_vcov <- function(fit, data, cluster_id = NULL) {
  if (!is.null(cluster_id) && nzchar(cluster_id)) {
    return(sandwich::vcovCL(fit, cluster = data[[cluster_id]], type = "HC1", cadjust = TRUE))
  }
  sandwich::vcovHC(fit, type = "HC0")
}

coefficient_rows <- function(beta, variance, confidence_level = 0.95, exponentiate = FALSE,
                             measure = "coefficient", multiplicity = "none") {
  beta <- beta[is.finite(beta)]
  variance <- variance[names(beta), names(beta), drop = FALSE]
  se <- sqrt(pmax(diag(variance), 0))
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  p <- 2 * stats::pnorm(-abs(beta / se))
  p_adjusted <- if (identical(multiplicity, "none")) p else stats::p.adjust(p, method = multiplicity)
  estimate <- if (exponentiate) exp(beta) else beta
  low <- if (exponentiate) exp(beta - z * se) else beta - z * se
  high <- if (exponentiate) exp(beta + z * se) else beta + z * se
  data.frame(
    term = names(beta), measure = measure, estimate = unname(estimate),
    ci_low = unname(low), ci_high = unname(high), standard_error = unname(se),
    p_value = unname(p), p_adjusted = unname(p_adjusted),
    confidence_level = confidence_level, stringsAsFactors = FALSE
  )
}

pool_model_coefficients <- function(fits, vcovs, confidence_level, exponentiate, measure, multiplicity) {
  common <- Reduce(intersect, lapply(fits, function(x) {
    beta <- stats::coef(x)
    names(beta)[is.finite(beta)]
  }))
  rows <- lapply(common, function(term) {
    beta <- vapply(fits, function(x) unname(stats::coef(x)[[term]]), numeric(1))
    within_values <- vapply(vcovs, function(x) unname(x[term, term]), numeric(1))
    m <- length(beta)
    qbar <- mean(beta)
    within <- mean(within_values)
    between <- if (m > 1L) stats::var(beta) else 0
    total <- within + (1 + 1 / m) * between
    se <- sqrt(total)
    df <- if (m > 1L && between > 0) (m - 1) * (1 + within / ((1 + 1 / m) * between))^2 else Inf
    critical <- if (is.finite(df)) stats::qt(1 - (1 - confidence_level) / 2, df) else stats::qnorm(1 - (1 - confidence_level) / 2)
    p <- if (is.finite(df)) 2 * stats::pt(-abs(qbar / se), df) else 2 * stats::pnorm(-abs(qbar / se))
    data.frame(
      term = term, measure = measure,
      estimate = if (exponentiate) exp(qbar) else qbar,
      ci_low = if (exponentiate) exp(qbar - critical * se) else qbar - critical * se,
      ci_high = if (exponentiate) exp(qbar + critical * se) else qbar + critical * se,
      standard_error = se, p_value = p, degrees_freedom = if (is.finite(df)) df else NA_real_,
      imputations = m, confidence_level = confidence_level, stringsAsFactors = FALSE
    )
  })
  output <- do.call(rbind, rows)
  output$p_adjusted <- if (identical(multiplicity, "none")) output$p_value else stats::p.adjust(output$p_value, method = multiplicity)
  output
}

prepare_regression_datasets <- function(data, analysis, variables) {
  variables <- unique(c(variables, unlist(analysis$missing_data$auxiliary_variables %||% list(), use.names = FALSE)))
  input <- data[variables]
  method <- analysis$missing_data$method %||% "complete_case"
  if (identical(method, "complete_case")) {
    complete <- input[stats::complete.cases(input[setdiff(variables, unlist(analysis$missing_data$auxiliary_variables %||% list(), use.names = FALSE))]), , drop = FALSE]
    return(list(datasets = list(complete), diagnostics = list(method = method, m = 1L, input_n = nrow(data), analysis_n = nrow(complete))))
  }
  m <- as.integer(analysis$missing_data$m %||% 20L)
  maxit <- as.integer(analysis$missing_data$maxit %||% 15L)
  init <- mice::mice(input, m = 1L, maxit = 0L, printFlag = FALSE)
  methods <- init$method
  methods[colSums(is.na(input)) == 0L] <- ""
  methods[methods != ""] <- analysis$missing_data$continuous_method %||% "pmm"
  master_seed <- analysis$missing_data$seed %||% 20260717L
  r_seed <- normalize_seed_for_r(master_seed)
  imputed <- mice::mice(
    input, m = m, maxit = maxit, method = methods,
    predictorMatrix = init$predictorMatrix,
    seed = r_seed, printFlag = FALSE
  )
  list(
    datasets = lapply(seq_len(m), function(i) mice::complete(imputed, i)),
    diagnostics = list(
      method = method, engine = "mice", m = m, maxit = maxit,
      master_seed = format(master_seed, scientific = FALSE, trim = TRUE),
      seed = r_seed,
      seed_mapping = "((master_seed - 1) %% 2147483647) + 1",
      predictor_matrix_event_policy = "MICE_DEFAULT_LOGGED_AND_REPORTED",
      imputed_variables = as.list(names(methods)[methods != ""]),
      initial_logged_events = as.list(init$loggedEvents %||% data.frame()),
      logged_events = as.list(imputed$loggedEvents %||% data.frame())
    )
  )
}

write_csv_artifact <- function(data, output_dir, filename, source) {
  path <- file.path(output_dir, filename)
  utils::write.csv(data, path, row.names = FALSE)
  list(path = normalizePath(path, mustWork = TRUE), source = source)
}

effect_forest_plot <- function(rows, x_label, null = 1) {
  rows <- rows[rows$term != "(Intercept)", , drop = FALSE]
  rows$term <- factor(rows$term, levels = rev(rows$term))
  p <- ggplot2::ggplot(rows, ggplot2::aes(x = estimate, y = term)) +
    ggplot2::geom_vline(xintercept = null, color = "#5B6570", linetype = "22", linewidth = 0.45) +
    ggplot2::geom_segment(ggplot2::aes(x = ci_low, xend = ci_high, y = term, yend = term), color = publication_palette[[1L]], linewidth = 0.7) +
    ggplot2::geom_point(shape = 21, fill = publication_palette[[1L]], color = "black", stroke = 0.25, size = 2.2) +
    publication_theme() + ggplot2::theme(legend.position = "none") +
    ggplot2::labs(x = x_label, y = NULL)
  if (identical(null, 1)) p <- p + ggplot2::scale_x_log10()
  p
}

as_result_rows <- function(data) {
  lapply(seq_len(nrow(data)), function(i) as.list(data[i, , drop = FALSE]))
}
