# v0.10 transport, public aggregate projection and audit artifacts only.
# Numerical fitting, preprocessing, CV, baseline estimation and prediction are
# owned by cox_penalized_v10.R and its explicitly pinned native dependencies.
.cox_penalized_v10_methods <- c("prediction.survival.cox.lasso", "prediction.survival.cox.elasticnet")

common_cox_penalized_runtime_reason <- function() {
  root <- .clinical_common$root; lock <- .clinical_common$runtime
  source <- file.path(root, "src/clinanalysis/R/cox_penalized_v10.R")
  preprocessing <- file.path(root, "src/clinanalysis/R/penalized_v08.R")
  if (!file.exists(source) || !identical(common_sha(source), lock$cox_penalized_provider_version))
    return("COX_PENALIZED_PROVIDER_VERSION_DRIFT")
  if (!file.exists(preprocessing) || !identical(common_sha(preprocessing), lock$cox_penalized_preprocessing_version))
    return("COX_PENALIZED_PREPROCESSING_VERSION_DRIFT")
  packages <- c("glmnet", "Matrix", "survival")
  if (!is.list(lock$cox_penalized_runtime) || !setequal(names(lock$cox_penalized_runtime), c("R", packages)) ||
      anyDuplicated(names(lock$cox_penalized_runtime))) return("COX_PENALIZED_RUNTIME_BINDING_REQUIRED")
  if (!is.list(lock$cox_penalized_package_paths) || !setequal(names(lock$cox_penalized_package_paths), packages) ||
      anyDuplicated(names(lock$cox_penalized_package_paths))) return("COX_PENALIZED_LIBRARY_BINDING_REQUIRED")
  for (p in packages) {
    if (!requireNamespace(p, quietly=TRUE)) return("COX_PENALIZED_ENGINE_UNAVAILABLE")
    if (!identical(as.character(utils::packageVersion(p)), lock$cox_penalized_runtime[[p]]))
      return("COX_PENALIZED_ENGINE_VERSION_MISMATCH")
    if (!identical(common_path(find.package(p)), common_path(lock$cox_penalized_package_paths[[p]])))
      return("COX_PENALIZED_LIBRARY_BINDING_MISMATCH")
  }
  if (!identical(as.character(getRversion()), lock$cox_penalized_runtime$R))
    return("COX_PENALIZED_ENGINE_VERSION_MISMATCH")
  hashes <- lock$cox_penalized_dependency_hashes
  expected <- unlist(lapply(packages, function(p) file.path(lock$cox_penalized_package_paths[[p]],
    c("DESCRIPTION", paste0("R/", p), paste0("R/", p, ".rdb"), paste0("R/", p, ".rdx"),
      if (.Platform$OS.type == "windows") paste0("libs/x64/", p, ".dll") else paste0("libs/", p, ".so")))), use.names=FALSE)
  if (!is.list(hashes) || length(hashes) != 15L || is.null(names(hashes)) || anyDuplicated(names(hashes)) ||
      !setequal(vapply(names(hashes), common_path, ""), vapply(expected, common_path, "")))
    return("COX_PENALIZED_DEPENDENCY_BINDING_REQUIRED")
  for (p in names(hashes))
    if (!file.exists(p) || !identical(common_sha(p), hashes[[p]])) return("COX_PENALIZED_DEPENDENCY_DRIFT")
  engine <- lock$rscript_engine
  if (!is.character(engine) || length(engine) != 1L ||
      !identical(common_path(file.path(R.home("bin"), if (.Platform$OS.type == "windows") "Rscript.exe" else "Rscript")), common_path(engine)))
    return("COX_PENALIZED_RSCRIPT_BINDING_MISMATCH")
  if (is.null(lock$executable_hashes[[engine]]) || !file.exists(engine) ||
      !identical(common_executable_sha(engine), lock$executable_hashes[[engine]]))
    return("COX_PENALIZED_RSCRIPT_DRIFT")
  NULL
}

common_cox_penalized_finite <- function(value, allow_na=FALSE) {
  if (is.numeric(value)) return(!is.complex(value) && !any(is.nan(value)) &&
    all(is.finite(value) | (allow_na & is.na(value))))
  if (is.list(value)) return(all(vapply(value, common_cox_penalized_finite, TRUE, allow_na=allow_na)))
  TRUE
}

run_common_cox_penalized_provider <- function(task, data, output_dir) {
  reason <- common_cox_penalized_runtime_reason()
  if (!is.null(reason)) return(list(ok=FALSE, reason_code=reason))
  lock <- .clinical_common$runtime; normalized <- .clinical_common$normalized
  options <- normalized$cox_penalized_options; bundle <- normalized$frozen_cox_penalized_model
  version <- lock$cox_penalized_provider_version
  value <- cox_penalized_v10_analyze(data, options, normalized$cox_penalized_semantics,
    frozen_model=if (is.null(bundle)) NULL else bundle$model,resource_budget=normalized$resource_limits)
  if (!is.list(value$record)) return(list(ok=FALSE, reason_code=value$reason_code %||% "COX_PENALIZED_PROVIDER_FAILED"))
  value$record <- common_penalized_origin_record(value$record,task)
  if (!common_cox_penalized_finite(value, allow_na=TRUE))
    return(list(ok=FALSE, reason_code="COX_PENALIZED_NONFINITE_BACKEND"))
  if (!identical(isTRUE(value$ok), identical(value$record$status, "completed")))
    return(list(ok=FALSE, reason_code="COX_PENALIZED_PROVIDER_STATUS_MISMATCH"))
  private <- file.path(output_dir, "private")
  backend <- file.path(private, "backend.json")
  common_json_write(value$record, backend)
  record <- common_json_read(backend)
  if (!is.null(value$individual))
    common_psm_write_frame(value$individual, file.path(private, "cox-penalized-individual-predictions.csv"))
  model_hash <- NULL
  if (isTRUE(value$ok)) {
    if (identical(options$operation, "train")) {
      if (!is.list(value$model)) return(list(ok=FALSE, reason_code="COX_PENALIZED_FROZEN_MODEL_MISSING"))
      frozen <- list(schema_version="clinical-frozen-cox-penalized@0.10.0-candidate1",
        method_id=task$analysis$method_id, provider_version=version,
        canonical_semantics=normalized$cox_penalized_semantics, model=value$model,
        runtime_binding=list(versions=lock$cox_penalized_runtime,
          package_paths=lock$cox_penalized_package_paths, dependency_hashes=lock$cox_penalized_dependency_hashes,
          rscript_engine=lock$rscript_engine, rscript_sha256=lock$executable_hashes[[lock$rscript_engine]],
          preprocessing_version=lock$cox_penalized_preprocessing_version),
        test_only=TRUE, scientific_review="pending", export_status="local_only")
      frozen <- common_penalized_wrap_origin(frozen,task)
      modelpath <- file.path(private, "cox-penalized-model.json")
      common_json_write(frozen, modelpath); model_hash <- common_sha(modelpath)
    } else model_hash <- options$model_ref$content_hash
  }
  list(ok=TRUE, record=record, model_hash=model_hash,
    individual_written=!is.null(value$individual),
    provider=list(id="clinanalysis.cox_penalized_v10", version=version, code_hash=version,
      runtime=lock$cox_penalized_runtime))
}

common_cox_penalized_ids <- function(result) {
  rec <- result$cox_penalized_prediction
  if (is.null(rec)) return(character())
  rows <- c(rec$preprocessing, rec$cv$rows, rec$cv$folds, rec$cv$fold_losses,
    rec$path, rec$coefficients, rec$horizons)
  c(rec$result_id, rec$baseline$result_id, vapply(rows, `[[`, character(1), "result_id"))
}

common_cox_penalized_result <- function(calculated, result, task, output_dir) {
  rec <- calculated$record
  rec$result_id <- paste0(result$run_id, "-cox-penalized")
  with_ids <- function(rows, label) lapply(seq_along(rows), function(i) {
    row <- rows[[i]]; row$result_id <- paste0(rec$result_id, "-", label, "-", i); row
  })
  for (name in c("preprocessing", "path", "coefficients", "horizons")) rec[[name]] <- with_ids(rec[[name]], name)
  for (name in c("rows", "folds", "fold_losses")) rec$cv[[name]] <- with_ids(rec$cv[[name]], paste0("cv-", name))
  rec$baseline$result_id <- paste0(rec$result_id, "-baseline")
  result$cox_penalized_prediction <- rec
  flow <- rec$flow; train <- identical(rec$operation, "train"); complete <- identical(rec$status, "completed")
  result$counts <- list(source_rows=flow$n_input, subjects=flow$n_input, eligible=flow$n_input,
    model_n=if (train && complete) flow$n_training else NULL, excluded_missing=0L,
    training_n=if (train) flow$n_training else NULL, training_events=if (train) flow$n_training_events else NULL,
    training_censored=if (train) flow$n_training_censored else NULL,
    holdout_n=if (train) flow$n_holdout else NULL, holdout_events=if (train) flow$n_holdout_events else NULL,
    holdout_censored=if (train) flow$n_holdout_censored else NULL,
    evaluation_n=NULL, evaluation_events=NULL, evaluation_nonevents=NULL,
    missing_duration_n=flow$missing_duration_n, missing_event_n=flow$missing_event_n,
    missing_feature_excluded_n=0L, prediction_n=flow$n_predicted, prediction_clipped_n=0L)
  result$binding["model_hash"] <- list(calculated$model_hash)
  result$diagnostics <- list(backend_status=rec$status, backend=list(cox_penalized=rec$diagnostics))
  result$provenance$prediction_operation <- rec$operation
  result$provenance$fit_scope <- if (train) "training_partition_and_inner_training_folds_only" else "frozen_no_refit"
  result$provenance$validation_scope <- if (train) "training_cv_tuning_and_descriptive_frozen_predictions" else "new_data_frozen_inference"
  result$provenance$target_policy <- list(domain="single_event_right_censored",
    linear_predictor_scale="log_relative_hazard", centered_linear_predictor="eta_minus_frozen_training_mean_eta",
    inverse_transform="1-exp(-H_ref(t)*exp(eta-c))", output_policy="event_probability_no_clipping",
    baseline_reference="centered_linear_predictor_zero", time_unit=rec$semantics$survival$time_unit,
    horizon_support="zero_through_frozen_max_observed_training_followup",
    event_boundary="include_events_at_horizon")
  result$limitations <- unique(c(result$limitations, rec$limitations, as.list(c(
    "Selected nonzero slopes refer to encoded columns; categorical predictors are not selected as penalized groups.",
    "Coefficient paths are standardized log-relative-hazard slopes without intercept, p-values, confidence intervals or selection-adjusted inference.",
    "CV is prespecified event-weighted held-out partial-likelihood tuning using fold-local risk sets; it is not nested CV, cv.glmnet grouped subtraction, absolute-risk validation or unbiased external performance.",
    "The offset-only Breslow baseline subroutine estimates no coefficient terms. Frozen inference does not fit preprocessing, coefficients or baseline and does not read outcome labels.",
    "Risk summaries describe frozen predictions, not observed outcome performance, calibration, discrimination, clinical utility or causal effects.",
    "Formal proportional-hazards testing, ordinary-Cox IPCW evaluation, SHAP, explanation and nomogram interfaces are unsupported for these new methods.",
    "The baseline is a step function including events at the horizon. A plateau after the last event is supported only through maximum observed training follow-up; extrapolation is refused.",
    "Identity disjointness is checked within the declared canonical namespace and does not establish real external cohort independence."))))
  result$metrics <- list()
  result$execution_status <- if (complete) "complete" else "blocked"
  result$applicability_status <- if (complete) "pass" else "limited"
  result["reason_code"] <- list(rec$reason_code); result$stage <- "compute"
  if (complete) result$completed_parts <- c(result$completed_parts,
    list("frozen_cox_penalized_prediction_contract", "prespecified_horizon_risk_summaries"),
    if (train) list("fold_local_preprocessing_and_event_weighted_lambda_tuning", "training_offset_breslow_baseline_estimation")
    else list("frozen_no_refit_application", "frozen_baseline_application"))
  if (isTRUE(calculated$individual_written)) result$local_artifacts <- c(result$local_artifacts,
    list(list(artifact_id="cox-penalized-individual-predictions", kind="private_predictions")))
  if (train && complete) result$local_artifacts <- c(result$local_artifacts,
    list(list(artifact_id="cox-penalized-model", kind="private_frozen_pipeline")))
  validate_common_cox_penalized_result(result)
  common_write_cox_penalized_outputs(result, output_dir)
}

validate_common_cox_penalized_result <- function(result) {
  rec <- result$cox_penalized_prediction
  if (is.null(rec)) return(invisible(TRUE))
  need <- function(ok, code) if (!isTRUE(ok)) stop(code, call.=FALSE)
  same <- function(a, b) isTRUE(all.equal(a, b, tolerance=1e-12, check.attributes=FALSE))
  number <- function(x) is.numeric(x) && length(x) == 1L && !is.complex(x) && is.finite(x)
  count <- function(x) number(x) && x >= 0 && x == floor(x)
  string <- function(x) is.character(x) && length(x) == 1L && !is.na(x) && nzchar(x)
  closed <- function(x, fields) is.list(x) && !is.null(names(x)) && !anyDuplicated(names(x)) &&
    length(x) == length(fields) && setequal(names(x), fields)
  need(closed(rec, c("result_id", "method_id", "operation", "status", "reason_code", "family", "penalty", "alpha",
    "selected_lambda", "selected_engine_lambda", "selected_lambda_index", "coefficient_scale", "prediction_scale",
    "semantics", "flow", "preprocessing", "cv", "path", "coefficients", "baseline", "horizons", "diagnostics", "limitations")),
    "RESULT_COX_PENALIZED_RECORD_FIELDS_INVALID")
  need(common_cox_penalized_finite(rec), "RESULT_COX_PENALIZED_NONFINITE")
  need(result$method_id %in% .cox_penalized_v10_methods && identical(result$method_id, rec$method_id),
    "RESULT_COX_PENALIZED_METHOD_MISMATCH")
  need(rec$operation %in% c("train", "infer") && rec$status %in% c("completed", "unavailable"),
    "RESULT_COX_PENALIZED_STATUS_INVALID")
  need(identical(rec$family, "cox") && number(rec$alpha) && rec$alpha > 0 && rec$alpha <= 1 &&
    identical(rec$penalty, if (rec$alpha == 1) "lasso" else "elasticnet") &&
    identical(rec$method_id, paste0("prediction.survival.cox.", rec$penalty)), "RESULT_COX_PENALIZED_PENALTY_INVALID")
  need(identical(rec$coefficient_scale, "standardized_x_log_relative_hazard") &&
    identical(rec$prediction_scale, "cumulative_event_probability"), "RESULT_COX_PENALIZED_SCALE_INVALID")
  need(!length(result$estimates) && !length(result$tests) && !length(result$metrics) && !length(result$model_results),
    "RESULT_COX_PENALIZED_UNSUPPORTED_INFERENCE_FORBIDDEN")
  need(is.null(result$survival) && is.null(result$cox_prediction) && is.null(result$survival_evaluation) &&
    is.null(result$interpretation), "RESULT_COX_PENALIZED_UNSUPPORTED_ADAPTER_FORBIDDEN")
  need((if(is.null(result$data_origin)) isTRUE(result$test_only) else
      is.logical(result$test_only)&&length(result$test_only)==1L&&!is.na(result$test_only)&&
      identical(result$test_only,identical(result$task_purpose,"engineering_test"))) &&
    identical(result$scientific_review, "pending") && identical(result$export_status, "local_only"),
    "RESULT_COX_PENALIZED_REVIEW_STATUS_INVALID")
  flow <- rec$flow
  need(closed(flow, c("n_input", "n_training", "n_holdout", "n_predicted", "n_cv_folds", "n_features", "n_encoded_columns",
    "n_dropped_columns", "n_training_events", "n_training_censored", "n_holdout_events", "n_holdout_censored",
    "missing_duration_n", "missing_event_n")), "RESULT_COX_PENALIZED_FLOW_FIELDS_INVALID")
  need(all(vapply(flow, function(x) is.null(x) || count(x), TRUE)), "RESULT_COX_PENALIZED_COUNT_INVALID")
  for (name in c("source_rows", "subjects", "eligible"))
    need(same(result$counts[[name]], flow$n_input), "RESULT_COX_PENALIZED_COUNT_MISMATCH")
  need(same(result$counts$prediction_n, flow$n_predicted) && same(result$counts$prediction_clipped_n, 0) &&
    same(result$counts$missing_duration_n, flow$missing_duration_n) && same(result$counts$missing_event_n, flow$missing_event_n),
    "RESULT_COX_PENALIZED_COUNT_MISMATCH")
  need(is.null(result$counts$evaluation_n) && is.null(result$counts$evaluation_events) && is.null(result$counts$evaluation_nonevents),
    "RESULT_COX_PENALIZED_OUTCOME_EVALUATION_FORBIDDEN")
  row_fields <- list(
    preprocessing=c("stage", "fold", "role", "feature", "type", "n_rows", "n_missing", "n_imputed", "fitted_levels", "fitted_reference", "encoding_rule"),
    cv_row=c("lambda_index", "lambda", "deviance_sum", "validation_events", "deviance_per_event", "selected"),
    cv_fold=c("fold", "n_training", "n_validation", "training_events", "training_censored", "validation_events", "validation_censored", "n_encoded_columns", "n_dropped_columns", "dropped_columns", "jerr", "warning_count"),
    cv_fold_loss=c("fold", "lambda_index", "lambda", "engine_lambda", "deviance_sum", "validation_events", "deviance_per_event"),
    coefficient=c("term", "feature", "type", "level", "coefficient", "nonzero", "source"),
    path=c("lambda_index", "lambda", "engine_lambda", "term", "feature", "type", "level", "coefficient", "nonzero"),
    horizon=c("population", "horizon", "time_unit", "n_predicted", "min_risk", "max_risk", "mean_risk"))
  groups <- list(preprocessing=rec$preprocessing, cv_row=rec$cv$rows, cv_fold=rec$cv$folds,
    cv_fold_loss=rec$cv$fold_losses, coefficient=rec$coefficients, path=rec$path, horizon=rec$horizons)
  for (name in names(groups)) {
    need(is.list(groups[[name]]), "RESULT_COX_PENALIZED_ROWS_INVALID")
    for (row in groups[[name]]) need(closed(row, c("result_id", row_fields[[name]])) && string(row$result_id),
      "RESULT_COX_PENALIZED_ROW_FIELDS_INVALID")
  }
  need(closed(rec$cv, c("status", "reason_code", "selection_rule", "loss_name", "weighting", "scope", "rows", "folds", "fold_losses")) &&
    identical(rec$cv$selection_rule, "min_deviance_per_event_largest_lambda_tie") &&
    identical(rec$cv$loss_name, "heldout_only_breslow_partial_likelihood_deviance") &&
    identical(rec$cv$weighting, "validation_event_count") && identical(rec$cv$scope, "training_only_tuning"),
    "RESULT_COX_PENALIZED_CV_SEMANTICS_INVALID")
  need(closed(rec$baseline, c("result_id", "method", "reference_center", "event_time_count", "last_event_time", "max_followup",
    "time_unit", "ties", "event_boundary", "coefficient_updates")), "RESULT_COX_PENALIZED_BASELINE_FIELDS_INVALID")
  need(identical(rec$baseline$method, "offset_only_breslow") && identical(rec$baseline$event_boundary, "event_at_t_included") &&
    same(rec$baseline$coefficient_updates, 0) && identical(rec$baseline$ties, "breslow") &&
    identical(rec$baseline$time_unit, rec$semantics$survival$time_unit), "RESULT_COX_PENALIZED_BASELINE_SEMANTICS_INVALID")
  need(closed(rec$diagnostics, c("stage", "fold", "feature", "code", "warning_count", "jerr", "n_engine_fits", "solver")),
    "RESULT_COX_PENALIZED_DIAGNOSTIC_FIELDS_INVALID")
  need(same(rec$diagnostics$solver, cox_penalized_v10_solver()), "RESULT_COX_PENALIZED_SOLVER_SEMANTICS_INVALID")
  for (row in rec$preprocessing) {
    need(count(row$n_rows) && count(row$n_missing) && count(row$n_imputed) && row$n_missing <= row$n_rows &&
      same(row$n_imputed, row$n_missing), "RESULT_COX_PENALIZED_IMPUTATION_COUNTS_INVALID")
    levels <- row$fitted_levels
    need(is.list(levels), "RESULT_COX_PENALIZED_FITTED_LEVELS_INVALID")
    if (identical(row$type, "number")) {
      need(!length(levels) && is.null(row$fitted_reference) && identical(row$encoding_rule, "identity_numeric"),
        "RESULT_COX_PENALIZED_NUMERIC_ENCODING_INVALID")
    } else {
      need(identical(row$type, "category") && length(levels) > 0L && all(vapply(levels, string, TRUE)),
        "RESULT_COX_PENALIZED_FITTED_LEVELS_INVALID")
      values <- unlist(levels, use.names=FALSE)
      need(!anyDuplicated(values) && identical(values, penalized_v08_sort(values)) &&
        identical(row$fitted_reference, values[[1L]]) && identical(row$encoding_rule, "treatment_utf8_observed_reference_first"),
        "RESULT_COX_PENALIZED_CATEGORY_ENCODING_INVALID")
    }
  }
  for (row in c(rec$path, rec$coefficients)) need(string(row$term) && row$term != "(Intercept)" &&
    string(row$feature) && row$type %in% c("number", "category") && number(row$coefficient) &&
    identical(row$nonzero, row$coefficient != 0), "RESULT_COX_PENALIZED_COEFFICIENT_INVALID")
  for (row in rec$coefficients) need(identical(row$source, if (rec$operation == "train") "training" else "frozen_training"),
    "RESULT_COX_PENALIZED_COEFFICIENT_SOURCE_INVALID")
  ids <- common_cox_penalized_ids(result)
  need(all(vapply(as.list(ids), string, TRUE)) && !anyDuplicated(ids), "RESULT_COX_PENALIZED_ID_INVALID")
  if (rec$status == "completed") {
    need(is.null(rec$reason_code) && string(result$binding$model_hash) && result$execution_status == "complete",
      "RESULT_COX_PENALIZED_COMPLETION_INVALID")
    need(same(flow$n_predicted, flow$n_input), "RESULT_COX_PENALIZED_PREDICTION_COUNT_INVALID")
    need(same(rec$diagnostics$warning_count, 0) &&
      if (rec$operation == "train") same(rec$diagnostics$jerr, 0) else is.null(rec$diagnostics$jerr),
      "RESULT_COX_PENALIZED_ENGINE_DIAGNOSTIC_INVALID")
    need(number(rec$selected_lambda) && rec$selected_lambda > 0 && number(rec$selected_engine_lambda) &&
      rec$selected_engine_lambda > 0 && abs(rec$selected_lambda - rec$selected_engine_lambda) <=
      32 * .Machine$double.eps * abs(rec$selected_lambda), "RESULT_COX_PENALIZED_LAMBDA_INVALID")
    need(length(rec$coefficients) == flow$n_encoded_columns && flow$n_encoded_columns >= 2 &&
      !anyDuplicated(vapply(rec$coefficients, `[[`, "", "term")), "RESULT_COX_PENALIZED_COEFFICIENT_COUNT_INVALID")
    need(number(rec$baseline$reference_center) && count(rec$baseline$event_time_count) && rec$baseline$event_time_count > 0 &&
      number(rec$baseline$last_event_time) && rec$baseline$last_event_time > 0 && number(rec$baseline$max_followup) &&
      rec$baseline$max_followup >= rec$baseline$last_event_time, "RESULT_COX_PENALIZED_BASELINE_SUPPORT_INVALID")
    if (rec$operation == "train") {
      for (pair in list(c("training_n", "n_training"), c("training_events", "n_training_events"),
        c("training_censored", "n_training_censored"), c("holdout_n", "n_holdout"),
        c("holdout_events", "n_holdout_events"), c("holdout_censored", "n_holdout_censored")))
        need(same(result$counts[[pair[[1L]]]], flow[[pair[[2L]]]]), "RESULT_COX_PENALIZED_COUNT_MISMATCH")
      need(same(flow$n_training + flow$n_holdout, flow$n_input) && flow$n_training > 0 && flow$n_holdout > 0 &&
        same(flow$n_training_events + flow$n_training_censored, flow$n_training) &&
        same(flow$n_holdout_events + flow$n_holdout_censored, flow$n_holdout) &&
        same(flow$missing_duration_n, 0) && same(flow$missing_event_n, 0), "RESULT_COX_PENALIZED_TRAINING_FLOW_INVALID")
      need(rec$cv$status == "completed" && is.null(rec$cv$reason_code) && length(rec$cv$rows) >= 2L && length(rec$cv$rows) <= 30L &&
        flow$n_cv_folds %in% 3:5 && length(rec$cv$folds) == flow$n_cv_folds,
        "RESULT_COX_PENALIZED_CV_INCOMPLETE")
      need(same(rec$diagnostics$n_engine_fits, flow$n_cv_folds + 1), "RESULT_COX_PENALIZED_ENGINE_FIT_COUNT_INVALID")
      need(same(sum(vapply(rec$cv$folds, `[[`, 0, "n_validation")), flow$n_training) &&
        same(sum(vapply(rec$cv$folds, `[[`, 0, "validation_events")), flow$n_training_events),
        "RESULT_COX_PENALIZED_CV_DENOMINATOR_INVALID")
      lambdas <- vapply(rec$cv$rows, `[[`, 0, "lambda")
      need(all(is.finite(lambdas)) && all(lambdas > 0) && all(diff(lambdas) < 0), "RESULT_COX_PENALIZED_CV_GRID_INVALID")
      selected <- which(vapply(rec$cv$rows, `[[`, TRUE, "selected"))
      need(length(selected) == 1L && same(selected, rec$selected_lambda_index) &&
        selected == which.min(vapply(rec$cv$rows, `[[`, 0, "deviance_per_event")) &&
        same(lambdas[[selected]], rec$selected_lambda), "RESULT_COX_PENALIZED_CV_SELECTION_INVALID")
      for (i in seq_along(rec$cv$rows)) {
        row <- rec$cv$rows[[i]]
        losses <- Filter(function(x) same(x$lambda_index, i), rec$cv$fold_losses)
        need(same(row$lambda_index, i) && same(row$validation_events, flow$n_training_events) &&
          row$validation_events > 0 && row$deviance_sum >= 0 && same(row$deviance_per_event, row$deviance_sum / row$validation_events) &&
          length(losses) == flow$n_cv_folds && same(sum(vapply(losses, `[[`, 0, "deviance_sum")), row$deviance_sum) &&
          same(sum(vapply(losses, `[[`, 0, "validation_events")), row$validation_events), "RESULT_COX_PENALIZED_CV_LOSS_INVALID")
      }
      for (fold in rec$cv$folds) {
        need(count(fold$fold) && fold$fold %in% seq_len(flow$n_cv_folds) &&
          same(fold$n_training + fold$n_validation, flow$n_training) &&
          same(fold$training_events + fold$training_censored, fold$n_training) &&
          same(fold$validation_events + fold$validation_censored, fold$n_validation) &&
          fold$training_events >= 8 && fold$validation_events >= 3 && same(fold$jerr, 0) && same(fold$warning_count, 0) &&
          is.list(fold$dropped_columns) && length(fold$dropped_columns) == fold$n_dropped_columns,
          "RESULT_COX_PENALIZED_CV_FOLD_INVALID")
        for (column in fold$dropped_columns) need(closed(column, c("term", "feature", "type", "level", "reason_code")) &&
          identical(column$reason_code, "ZERO_VARIANCE"), "RESULT_COX_PENALIZED_DROPPED_COLUMNS_INVALID")
      }
      need(!anyDuplicated(vapply(rec$cv$folds, `[[`, 0, "fold")) &&
        length(rec$cv$fold_losses) == length(lambdas) * flow$n_cv_folds, "RESULT_COX_PENALIZED_CV_FOLD_INVALID")
      for (loss in rec$cv$fold_losses) {
        fold <- Filter(function(x) same(x$fold, loss$fold), rec$cv$folds)
        need(length(fold) == 1L && count(loss$lambda_index) && loss$lambda_index %in% seq_along(lambdas) &&
          same(loss$lambda, lambdas[[loss$lambda_index]]) && number(loss$engine_lambda) &&
          abs(loss$lambda - loss$engine_lambda) <= 32 * .Machine$double.eps * abs(loss$lambda) &&
          same(loss$validation_events, fold[[1L]]$validation_events) && loss$deviance_sum >= 0 &&
          same(loss$deviance_per_event, loss$deviance_sum / loss$validation_events), "RESULT_COX_PENALIZED_CV_FOLD_LOSS_INVALID")
      }
      loss_keys <- vapply(rec$cv$fold_losses, function(x) paste(x$fold, x$lambda_index, sep=":"), "")
      need(!anyDuplicated(loss_keys), "RESULT_COX_PENALIZED_CV_FOLD_LOSS_INVALID")
      need(length(rec$path) == length(lambdas) * length(rec$coefficients), "RESULT_COX_PENALIZED_PATH_INCOMPLETE")
      for (i in seq_along(lambdas)) {
        rows <- Filter(function(x) same(x$lambda_index, i), rec$path)
        need(length(rows) == length(rec$coefficients) && identical(vapply(rows, `[[`, "", "term"),
          vapply(rec$coefficients, `[[`, "", "term")), "RESULT_COX_PENALIZED_PATH_INCOMPLETE")
        for (row in rows) need(same(row$lambda, lambdas[[i]]) && number(row$engine_lambda) &&
          abs(row$lambda - row$engine_lambda) <= 32 * .Machine$double.eps * abs(row$lambda), "RESULT_COX_PENALIZED_PATH_LAMBDA_INVALID")
        if (i == selected) need(same(vapply(rows, `[[`, 0, "coefficient"),
          vapply(rec$coefficients, `[[`, 0, "coefficient")), "RESULT_COX_PENALIZED_SELECTED_PATH_MISMATCH")
      }
    } else need(same(rec$diagnostics$n_engine_fits, 0) && rec$cv$status == "not_run" &&
      !length(rec$cv$rows) && !length(rec$cv$folds) && !length(rec$cv$fold_losses) && !length(rec$path),
      "RESULT_COX_PENALIZED_EXTERNAL_REFIT_FORBIDDEN")
    populations <- if (rec$operation == "train") c("training", "holdout") else "external"
    need(length(rec$horizons) >= length(populations), "RESULT_COX_PENALIZED_HORIZONS_INCOMPLETE")
    for (population in populations) {
      rows <- Filter(function(row) identical(row$population, population), rec$horizons)
      times <- vapply(rows, `[[`, 0, "horizon")
      need(length(times) >= 1L && length(times) <= 8L && all(diff(times) > 0), "RESULT_COX_PENALIZED_HORIZONS_INVALID")
    }
    if (rec$operation == "train") need(identical(vapply(Filter(function(x) x$population == "training", rec$horizons), `[[`, 0, "horizon"),
      vapply(Filter(function(x) x$population == "holdout", rec$horizons), `[[`, 0, "horizon")), "RESULT_COX_PENALIZED_POPULATION_HORIZONS_MISMATCH")
    for (row in rec$horizons) {
      expected_n <- switch(row$population, training=flow$n_training, holdout=flow$n_holdout, external=flow$n_input, NULL)
      need(row$population %in% populations && number(row$horizon) && row$horizon >= 0 && row$horizon <= rec$baseline$max_followup &&
        identical(row$time_unit, rec$baseline$time_unit) && same(row$n_predicted, expected_n) && row$n_predicted > 0 &&
        number(row$min_risk) && number(row$mean_risk) && number(row$max_risk) && row$min_risk >= 0 && row$max_risk <= 1 &&
        row$min_risk <= row$mean_risk && row$mean_risk <= row$max_risk, "RESULT_COX_PENALIZED_HORIZON_SUMMARY_INVALID")
    }
  } else need(string(rec$reason_code) && result$execution_status == "blocked" && is.null(result$binding$model_hash),
    "RESULT_COX_PENALIZED_REFUSAL_INVALID")
  if (rec$operation == "infer") need(all(vapply(flow[c("n_training_events", "n_training_censored", "n_holdout_events",
    "n_holdout_censored", "missing_duration_n", "missing_event_n")], is.null, TRUE)),
    "RESULT_COX_PENALIZED_INFER_OUTCOME_READING_FORBIDDEN")
  invisible(TRUE)
}

# This frame builder only serializes already calculated aggregates. Null/NA are
# missing cells; NaN/Inf, mixed scalar types and undeclared nested values fail.
common_cox_penalized_frame <- function(rows) {
  if (!length(rows)) return(data.frame())
  fields <- names(rows[[1L]])
  if (is.null(fields) || anyDuplicated(fields) || any(vapply(rows, function(x)
      !is.list(x) || !setequal(names(x), fields) || anyDuplicated(names(x)) > 0L, TRUE)))
    stop("COX_PENALIZED_EXPORT_COLUMNS_INVALID", call.=FALSE)
  nested <- c("fitted_levels", "dropped_columns")
  as.data.frame(setNames(lapply(fields, function(field) {
    values <- lapply(rows, function(row) row[[field]])
    if (field %in% nested) {
      if (!all(vapply(values, is.list, TRUE)) || !common_cox_penalized_finite(values))
        stop("COX_PENALIZED_EXPORT_NESTED_INVALID", call.=FALSE)
      return(vapply(values, function(value) {
        if (field == "fitted_levels") {
          if (!all(vapply(value, function(x) is.character(x) && length(x) == 1L && !is.na(x), TRUE)))
            stop("COX_PENALIZED_EXPORT_FITTED_LEVELS_INVALID", call.=FALSE)
          value <- as.character(unlist(value, use.names=FALSE))
          return(as.character(jsonlite::toJSON(value, auto_unbox=FALSE, null="null", digits=17)))
        }
        as.character(jsonlite::toJSON(unname(value), auto_unbox=TRUE, null="null", digits=17))
      }, ""))
    }
    if (any(vapply(values, function(x) !is.null(x) && (is.list(x) || length(x) != 1L || is.complex(x)), TRUE)) ||
        !common_cox_penalized_finite(values, allow_na=TRUE))
      stop("COX_PENALIZED_EXPORT_SCALAR_INVALID", call.=FALSE)
    present <- Filter(Negate(is.null), values)
    if (length(present) && all(vapply(present, is.character, TRUE)))
      return(vapply(values, function(x) if (is.null(x)) NA_character_ else x, ""))
    if (length(present) && all(vapply(present, is.logical, TRUE)))
      return(vapply(values, function(x) if (is.null(x)) NA else x, TRUE))
    if (length(present) && !all(vapply(present, is.numeric, TRUE)))
      stop("COX_PENALIZED_EXPORT_MIXED_TYPES", call.=FALSE)
    vapply(values, function(x) if (is.null(x)) NA_real_ else as.numeric(x), 0)
  }), fields), stringsAsFactors=FALSE, check.names=FALSE)
}

common_write_cox_penalized_outputs <- function(result, output_dir) {
  rec <- result$cox_penalized_prediction
  metadata <- list(method_id=result$method_id, method_version=result$method_version,
    provider_version=result$provider$version,
    preprocessing_version=.clinical_common$runtime$cox_penalized_preprocessing_version,
    core_version=result$core_version, run_id=result$run_id, operation=rec$operation, family=rec$family,
    penalty=rec$penalty, alpha=rec$alpha, coefficient_scale=rec$coefficient_scale,
    prediction_scale=rec$prediction_scale, duration_unit=rec$semantics$survival$time_unit,
    source_input_hash=result$binding$input_hash, source_plan_hash=result$binding$plan_hash,
    scientific_review="pending", export_status="local_only", test_only=result$test_only)
  if(!is.null(result$data_origin)) metadata <- c(metadata,list(data_origin=result$data_origin,task_purpose=result$task_purpose))
  table <- function(name, rows, caption, denominator=NULL, units="explicit per field") {
    if (!length(rows)) return(invisible(NULL))
    if (any(names(metadata) %in% names(rows[[1L]]))) stop("COX_PENALIZED_EXPORT_METADATA_COLLISION", call.=FALSE)
    data <- common_cox_penalized_frame(lapply(rows, function(row) c(metadata, row)))
    file <- file.path(output_dir, "tables", paste0(name, ".csv")); common_psm_write_frame(data, file)
    ids <- lapply(rows, function(row) row$result_id %||% rec$result_id)
    result$tables[[length(result$tables) + 1L]] <<- common_artifact(name, "table", file, result,
      ids, denominator, units, caption)
  }
  flowrows <- lapply(names(rec$flow), function(name) list(result_id=rec$result_id, count_name=name,
    value=rec$flow[[name]], count_semantics=if (rec$operation == "infer" &&
      name %in% c("n_training_events", "n_training_censored", "n_holdout_events", "n_holdout_censored", "missing_duration_n", "missing_event_n"))
      "outcomes_not_read_in_infer" else "explicit_subject_or_design_count"))
  table("cox_penalized_flow", flowrows,
    paste0(common_penalized_source_label(result),". Unique-subject flow with training/holdout event and censor counts. Missing outcomes refuse training; features use fitting-scope imputation. Null is unavailable or not read, never zero."))
  table("cox_penalized_imputation", rec$preprocessing,
    paste0(common_penalized_source_label(result),". Missingness and fitted encoding by fold/role. fitted_levels is an observed-training-level JSON array in UTF8 order; fitted_reference is its first level. Application rows reuse frozen fitting encoding; the declared codebook reference is not the fitted reference."))
  table("cox_penalized_cv", rec$cv$rows,
    paste0(common_penalized_source_label(result),". Sum of held-out Cox partial-likelihood deviances divided by total held-out events, using each fold's own risk sets and Breslow ties. Exact ties select the largest prespecified lambda. Training tuning only; no CI or external performance claim."), rec$flow$n_training_events, "Cox deviance per held-out event")
  table("cox_penalized_cv_folds", rec$cv$folds,
    paste0(common_penalized_source_label(result),". Prespecified fitting and validation subject/event/censor counts. Each fold independently learns preprocessing. Dropped columns and engine status are explicit; support thresholds are engineering rules."))
  table("cox_penalized_cv_fold_losses", rec$cv$fold_losses,
    paste0(common_penalized_source_label(result),". Every prespecified lambda has each held-out fold's deviance numerator and event denominator. Requested and returned engine lambda are distinct fields; no path interpolation."), NULL, "Cox deviance and held-out events")
  table("cox_penalized_coefficient_path", rec$path,
    paste0(common_penalized_source_label(result),". Full outer-training standardized log-relative-hazard slope path, without intercept or coefficient p-values/CI. Encoded-column selection carries no causal or postselection inference."), if (rec$operation == "train") rec$flow$n_training else NULL)
  table("cox_penalized_coefficients", rec$coefficients,
    paste0(common_penalized_source_label(result),". Frozen selected standardized log-relative-hazard slopes. No intercept, p-values, confidence intervals or formal proportional-hazards test."))
  selected <- Filter(function(row) isTRUE(row$nonzero), rec$coefficients)
  if (length(selected)) table("cox_penalized_nonzero", selected,
    paste0(common_penalized_source_label(result),". Nonzero encoded slope columns at the selected lambda; no grouped-variable or postselection inference."))
  else if (length(rec$coefficients)) {
    if (any(names(metadata) %in% names(rec$coefficients[[1L]]))) stop("COX_PENALIZED_EXPORT_METADATA_COLLISION", call.=FALSE)
    empty <- common_cox_penalized_frame(lapply(rec$coefficients, function(row) c(metadata, row)))[FALSE, , drop=FALSE]
    file <- file.path(output_dir, "tables", "cox_penalized_nonzero.csv"); common_psm_write_frame(empty, file)
    result$tables[[length(result$tables) + 1L]] <- common_artifact("cox_penalized_nonzero", "table", file,
      result, list(rec$result_id), 0L, "encoded slope columns",
      paste0(common_penalized_source_label(result),". Header-only table: no nonzero slopes at the selected lambda. The training Breslow baseline still defines an all-zero-coefficient Cox prediction model."))
  }
  table("cox_penalized_baseline", list(rec$baseline),
    paste0(common_penalized_source_label(result),". Training-only offset Cox Breslow baseline reference: c=mean(training eta), q=eta-c, H_ref at q=0. No coefficient updates. Last event and maximum follow-up are distinct; horizon lookup includes events at t."),
    if (rec$operation == "train") rec$flow$n_training else NULL, "reference log hazard and declared time unit")
  table("cox_penalized_horizons", rec$horizons,
    paste0(common_penalized_source_label(result),". Aggregate frozen event-probability summaries by population and prespecified horizon. These are prediction descriptions, not observed outcome metrics or confidence intervals; every horizon is inside frozen follow-up support."), NULL, "event probability [0,1] and declared time unit")
  figure <- function(name, ids, caption, draw, denominator=NULL, units="explicit axes") {
    file <- file.path(output_dir, "figures", paste0(name, ".png"))
    grDevices::png(file, width=1400, height=850, res=150)
    done <- FALSE
    tryCatch({draw(); done <- TRUE}, finally=grDevices::dev.off())
    if (!done) stop("COX_PENALIZED_FIGURE_FAILED", call.=FALSE)
    result$figures[[length(result$figures) + 1L]] <<- common_artifact(name, "figure", file, result,
      ids, denominator, units, caption)
  }
  if (rec$status == "completed" && rec$operation == "train") {
    figure("cox_penalized_cv", lapply(rec$cv$rows, `[[`, "result_id"),
      paste0(common_penalized_source_label(result),". Training tuning curve: held-out partial-likelihood deviance per held-out event, fold-local risk sets and Breslow ties. Vertical line is selected lambda; no confidence band."), function() {
        grid <- vapply(rec$cv$rows, `[[`, 0, "lambda"); loss <- vapply(rec$cv$rows, `[[`, 0, "deviance_per_event")
        graphics::par(mar=c(5, 5, 4, 2)); graphics::plot(log(grid), loss, type="b", pch=19, col="#176B6B", lwd=2,
          xlab="log(requested lambda)", ylab="Held-out Cox deviance / held-out events",
          main=paste0("Training Cox tuning: ", rec$penalty, " (alpha = ", rec$alpha, ")"))
        graphics::abline(v=log(rec$selected_lambda), lty=2, col="#A84432")
        graphics::mtext(paste0("Training events = ", rec$flow$n_training_events, "; folds = ", rec$flow$n_cv_folds, paste0("; ",common_penalized_source_label(result))), side=3, line=.3, cex=.8)
      }, rec$flow$n_training_events)
    figure("cox_penalized_coefficient_path", lapply(rec$path, `[[`, "result_id"),
      paste0(common_penalized_source_label(result),". Outer-training standardized log-relative-hazard slope path. No intercept, p-values, CI or formal PH test; selection applies to encoded columns."), function() {
        terms <- unique(vapply(rec$path, `[[`, "", "term")); grid <- vapply(rec$cv$rows, `[[`, 0, "lambda")
        y <- vapply(terms, function(term) vapply(Filter(function(row) row$term == term, rec$path), `[[`, 0, "coefficient"), numeric(length(grid)))
        colors <- grDevices::hcl.colors(length(terms), "Dark 3")
        graphics::par(mar=c(5, 5, 4, 2)); graphics::matplot(log(grid), y, type="l", lty=1, lwd=2, col=colors,
          xlab="log(requested lambda)", ylab="Standardized log-relative-hazard slope", main=paste0("Outer-training Cox coefficient path: ", rec$penalty))
        graphics::abline(v=log(rec$selected_lambda), lty=2, col="#A84432"); graphics::abline(h=0, col="#BBBBBB")
        if (length(terms) <= 12L) graphics::legend("topright", legend=terms, col=colors, lty=1, cex=.65, bty="n")
        graphics::mtext(paste0("Term-to-feature mapping is retained in the coefficient table; ",common_penalized_source_label(result)), side=3, line=.3, cex=.75)
      }, rec$flow$n_training)
  }
  if (rec$status == "completed" && length(rec$horizons)) {
    figure("cox_penalized_horizons", lapply(rec$horizons, `[[`, "result_id"),
      paste0(common_penalized_source_label(result),". Mean frozen event probabilities at prespecified horizons, separated by population. Points are the requested horizons; no interpolation, outcome performance, uncertainty band or extrapolation."), function() {
        populations <- unique(vapply(rec$horizons, `[[`, "", "population"))
        colors <- grDevices::hcl.colors(length(populations), "Dark 3")
        symbols <- c(1L, 4L, 3L)[seq_along(populations)]
        xrange <- range(vapply(rec$horizons, `[[`, 0, "horizon"))
        if (diff(xrange) == 0) xrange <- xrange + c(-.5, .5)
        graphics::par(mar=c(5, 5, 4, 2)); graphics::plot(NA_real_, NA_real_, xlim=xrange, ylim=c(0, 1),
          xlab=paste0("Prespecified horizon (", rec$semantics$survival$time_unit, ")"),
          ylab="Mean frozen event probability", main="Descriptive frozen Cox risk summaries")
        for (i in seq_along(populations)) {
          rows <- Filter(function(row) row$population == populations[[i]], rec$horizons)
          graphics::points(vapply(rows, `[[`, 0, "horizon"), vapply(rows, `[[`, 0, "mean_risk"),
            pch=symbols[[i]], cex=1.3, lwd=2, col=colors[[i]])
        }
        graphics::legend("topleft", legend=populations, col=colors, pch=symbols, pt.lwd=2, pt.cex=1.3, bty="n")
        graphics::mtext(paste0("Separate populations; no observed-outcome evaluation; ",common_penalized_source_label(result)), side=3, line=.3, cex=.8)
      }, NULL, "event probability [0,1] and declared time unit")
  }
  result
}
