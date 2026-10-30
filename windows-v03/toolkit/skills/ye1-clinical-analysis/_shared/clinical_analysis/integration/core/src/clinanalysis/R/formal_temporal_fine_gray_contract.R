.formal_temporal_fg_task_version <- "1.0.0"
.formal_temporal_fg_task_versions <- c("1.0.0", "2.0.0")

formal_temporal_fg_contract <- function() {
  predictors <- c(
    "age", "female", "ami_type", "admission_context", "dementia_history",
    "alcohol_use_history", "early_cardiac_arrest", "heart_rate_max_0_12h",
    "systolic_bp_min_0_12h", "respiratory_rate_max_0_12h",
    "temperature_max_0_12h", "spo2_min_0_12h", "gcs_min_0_12h",
    "rass_min_0_12h", "lactate_max_0_12h", "ph_min_0_12h",
    "glucose_max_0_12h", "sodium_latest_0_12h", "creatinine_max_0_12h",
    "bun_max_0_12h", "wbc_max_0_12h", "mechanical_ventilation_0_12h",
    "vasoactive_support_0_12h", "sedative_exposure_0_12h",
    "opioid_exposure_0_12h"
  )
  transformations <- list(
    age = "RCS_DEVELOPMENT_P10_P50_P90_2DF",
    female = "BINARY_INDICATOR",
    ami_type = "TREATMENT_CODING_NSTEMI_REFERENCE_2DF",
    admission_context = "BINARY_INDICATOR",
    dementia_history = "BINARY_INDICATOR",
    alcohol_use_history = "BINARY_INDICATOR",
    early_cardiac_arrest = "BINARY_INDICATOR",
    heart_rate_max_0_12h = "LINEAR_PER_10",
    systolic_bp_min_0_12h = "LINEAR_PER_10",
    respiratory_rate_max_0_12h = "LINEAR_PER_5",
    temperature_max_0_12h = "LINEAR_PER_1",
    spo2_min_0_12h = "LINEAR_PER_5",
    gcs_min_0_12h = "LINEAR_PER_1",
    rass_min_0_12h = "LINEAR_PER_1",
    lactate_max_0_12h = "NATURAL_LOG_AFTER_UNIT_HARMONIZATION",
    ph_min_0_12h = "LINEAR_PER_0.1",
    glucose_max_0_12h = "NATURAL_LOG_AFTER_UNIT_HARMONIZATION",
    sodium_latest_0_12h = "LINEAR_PER_5",
    creatinine_max_0_12h = "NATURAL_LOG_AFTER_UNIT_HARMONIZATION",
    bun_max_0_12h = "NATURAL_LOG_AFTER_UNIT_HARMONIZATION",
    wbc_max_0_12h = "NATURAL_LOG_AFTER_UNIT_HARMONIZATION",
    mechanical_ventilation_0_12h = "BINARY_INDICATOR",
    vasoactive_support_0_12h = "BINARY_INDICATOR",
    sedative_exposure_0_12h = "BINARY_INDICATOR",
    opioid_exposure_0_12h = "BINARY_INDICATOR"
  )
  outputs <- c(
    "TABLE.CVCC-PRED-ISO-001.MAIN.1", "TABLE.CVCC-PRED-ISO-001.MAIN.2",
    "TABLE.CVCC-PRED-ISO-001.MAIN.3", "FIGURE.CVCC-PRED-ISO-001.MAIN.1",
    "FIGURE.CVCC-PRED-ISO-001.MAIN.2", "FIGURE.CVCC-PRED-ISO-001.MAIN.3",
    "FIGURE.CVCC-PRED-ISO-001.MAIN.4", "FIGURE.CVCC-PRED-ISO-001.MAIN.5",
    "RESULT.CVCC-PRED-ISO-001.STRUCTURED.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.DEFINITIONS.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.VARIABLES.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.MISSINGNESS.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.MODEL-SPEC.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.OBSERVATION.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.LINEAGE.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.SENSITIVITY.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.CALIBRATION-GATE.V1",
    "SUPPLEMENT.CVCC-PRED-ISO-001.REPRODUCIBILITY.V1"
  )
  list(
    candidate_id = "CVCC-PRED-ISO-001",
    landmark_hours = 12,
    horizon_hours = 84,
    primary_model_id = "MODEL.CVCC-PRED-ISO-001.FG-CLINICAL-27DF.V1",
    baseline_model_id = "MODEL.CVCC-PRED-ISO-001.FG-AGE-SEX-BASELINE.V1",
    primary_predictors = predictors,
    baseline_predictors = c("age", "female"),
    parameter_df = 27L,
    transformations = transformations,
    transformation_map_sha256 = digest::digest(
      jsonlite::toJSON(transformations, auto_unbox = TRUE, null = "null"),
      algo = "sha256", serialize = FALSE
    ),
    sensitivity_ids = c(
      "SENS.CVCC-PRED-ISO-001.COMPLETE-OBSERVATION.V1",
      "SENS.CVCC-PRED-ISO-001.ASSESSMENT-IPCW.V1"
    ),
    metric_ids = c(
      "TIME_DEPENDENT_AUC_AT_84H", "IPCW_BRIER_AT_84H", "SCALED_BRIER_VS_NULL",
      "OE_RATIO_AT_84H", "CALIBRATION_IN_THE_LARGE_CLOGLOG", "CALIBRATION_SLOPE",
      "FLEXIBLE_CALIBRATION_CURVE", "ICI", "DECILE_ABSOLUTE_ERROR"
    ),
    expected_output_ids = outputs
  )
}

formal_temporal_fg_contract_v4 <- function() {
  legacy <- formal_temporal_fg_contract()
  predictors <- setdiff(legacy$primary_predictors, "ami_type")
  transformations <- legacy$transformations[predictors]
  legacy$primary_model_id <- "MODEL.CVCC-PRED-ISO-001.FG-CLINICAL-25DF.V2"
  legacy$primary_predictors <- predictors
  legacy$parameter_df <- 25L
  legacy$transformations <- transformations
  legacy$transformation_map_sha256 <-
    "bf8c4b9d36427c35ccbcefe008969516786872fd2def864c74830a8d60382f74"
  legacy$sap_id <- "SAP.CVCC-PRED-ISO-001.FROZEN.V3"
  legacy$sap_sha256 <- "2f291c79486422d474eeaa97c2b6a8fd94dfd140b4050f463b71b21003f0f515"
  legacy$task_id <- "TASK.CVCC-PRED-ISO-001.FORMAL-FG.V4"
  legacy$task_sha256 <- "d2c40ea609d4c450caa9089806cf8a768b043f17bb60678b6c780f997d398f9f"
  legacy$dataset_id <- "DATASET.CVCC-PRED-ISO-001.ANALYSIS-READY.V2"
  legacy$dataset_sha256 <- "d9d79eb2f9521b6e1c909c533f09ffe6a94514ebfc1600a4d948b5849a676801"
  legacy
}

formal_temporal_fg_contract_for_task <- function(task) {
  version <- task$schema_version %||% ""
  if (identical(version, "1.0.0")) return(formal_temporal_fg_contract())
  if (identical(version, "2.0.0")) return(formal_temporal_fg_contract_v4())
  stop(contract_error(sprintf(
    "Unsupported FORMAL temporal Fine-Gray schema_version '%s'",
    version
  )))
}

formal_temporal_fg_contract_for_analysis <- function(analysis) {
  if (identical(
    analysis$model_plan$primary_model_id,
    formal_temporal_fg_contract_v4()$primary_model_id
  )) return(formal_temporal_fg_contract_v4())
  formal_temporal_fg_contract()
}

formal_fg_exact_names <- function(x, allowed, label, required = allowed) {
  if (!is.list(x)) return(sprintf("%s must be an object", label))
  c(
    sprintf("%s missing field: %s", label, setdiff(required, names(x))),
    sprintf("%s unknown field: %s", label, setdiff(names(x), allowed))
  )
}

formal_fg_semantically_identical <- function(actual, expected) {
  if (is.null(expected)) return(is.null(actual))

  expected_is_object <- is.list(expected) &&
    length(expected) > 0L &&
    !is.null(names(expected)) &&
    all(nzchar(names(expected)))
  if (expected_is_object) {
    if (!is.list(actual) || is.data.frame(actual) || is.null(names(actual)) ||
        any(!nzchar(names(actual))) || anyDuplicated(names(actual)) ||
        length(actual) != length(expected) ||
        !setequal(names(actual), names(expected))) return(FALSE)
    return(all(vapply(
      names(expected),
      function(name) formal_fg_semantically_identical(actual[[name]], expected[[name]]),
      logical(1)
    )))
  }

  expected_is_sequence <- (is.list(expected) && !expected_is_object) || length(expected) > 1L
  if (expected_is_sequence) {
    if (!(is.list(actual) || is.atomic(actual)) || is.data.frame(actual) ||
        !is.null(dim(actual)) || length(actual) != length(expected)) return(FALSE)
    if (!is.null(names(actual)) && any(nzchar(names(actual)))) return(FALSE)
    actual_items <- if (is.list(actual)) actual else as.list(actual)
    expected_items <- if (is.list(expected)) expected else as.list(expected)
    if (any(vapply(actual_items, function(x) is.list(x) || length(x) != 1L, logical(1)))) {
      return(FALSE)
    }
    return(all(vapply(
      seq_along(expected_items),
      function(i) formal_fg_semantically_identical(actual_items[[i]], expected_items[[i]]),
      logical(1)
    )))
  }

  if (is.numeric(expected)) {
    return(is.numeric(actual) && length(actual) == 1L && is.finite(actual) &&
      is.finite(expected) && actual == expected)
  }
  length(actual) == 1L && identical(actual, expected)
}

formal_fg_sha256 <- function(x) is.character(x) && length(x) == 1L && grepl("^[a-f0-9]{64}$", x)

formal_fg_forbidden_payload_problems <- function(x, trail = "task") {
  problems <- character()
  if (!is.list(x)) {
    if (is.character(x) && length(x) == 1L &&
        (grepl("^(~?/|[A-Za-z]:[/\\\\])", x) || grepl("analysis[-_]?ready\\.csv|mimic", x, ignore.case = TRUE))) {
      problems <- c(problems, sprintf("Physical path or real-data reference is forbidden at %s", trail))
    }
    return(problems)
  }
  forbidden_keys <- c("path", "file", "directory", "payload", "rows", "records", "patient_level_data")
  bad <- intersect(names(x), forbidden_keys)
  if (length(bad)) problems <- c(problems, sprintf("Forbidden shared-task field at %s: %s", trail, bad))
  for (name in names(x)) {
    problems <- c(problems, formal_fg_forbidden_payload_problems(x[[name]], paste0(trail, ".", name)))
  }
  problems
}

#' Validate the strict temporal Fine-Gray FORMAL-capability task contract
#'
#' FORMAL tasks are contract-valid only with a frozen SAP binding and a
#' separate human execution authorization. Contract validation never grants
#' execution authorization.
#'
#' @param task Versioned task list.
#' @return Invisibly returns TRUE or raises a contract error.
#' @export
validate_formal_temporal_fine_gray_task <- function(task) {
  contract <- formal_temporal_fg_contract_for_task(task)
  problems <- formal_fg_exact_names(
    task,
    c("schema_version", "analysis_id", "seed", "data", "binding", "analysis", "readiness", "outputs"),
    "task",
    c("schema_version", "analysis_id", "seed", "data", "binding", "analysis", "readiness", "outputs")
  )
  if (!(task$schema_version %in% .formal_temporal_fg_task_versions)) {
    problems <- c(problems, "FORMAL temporal Fine-Gray tasks require schema_version 1.0.0 or 2.0.0")
  }
  if (!formal_fg_semantically_identical(task$seed, 20260722L)) problems <- c(problems, "task seed must remain 20260722")
  problems <- c(problems, formal_fg_forbidden_payload_problems(task))

  data_allowed <- c("dataset_id", "sha256", "dataset_tag")
  problems <- c(problems, formal_fg_exact_names(task$data, data_allowed, "data"))
  if (!formal_fg_sha256(task$data$sha256)) problems <- c(problems, "data.sha256 must be lowercase SHA-256")

  binding_allowed <- c("candidate_id", "sap_id", "sap_sha256", "sap_status", "formal_authorization")
  problems <- c(problems, formal_fg_exact_names(
    task$binding, binding_allowed, "binding",
    c("candidate_id", "sap_id", "sap_sha256", "sap_status")
  ))
  if (!identical(task$binding$candidate_id, contract$candidate_id)) problems <- c(problems, "candidate_id mismatch")
  if (!formal_fg_sha256(task$binding$sap_sha256)) problems <- c(problems, "binding.sap_sha256 must be lowercase SHA-256")

  analysis_allowed <- c(
    "method", "execution_mode", "candidate_id", "patient_id", "time", "event", "competing_event",
    "outcome_observed", "last_observation_time", "observation_state", "split", "development_value",
    "validation_value", "landmark_hours", "horizon_hours", "event_semantics", "model_plan", "imputation",
    "internal_validation", "temporal_validation", "metric_ids", "calibration_gate", "sensitivity_ids",
    "expected_output_ids", "qc_variables", "pilot_only"
  )
  problems <- c(problems, formal_fg_exact_names(task$analysis, analysis_allowed, "analysis"))
  a <- task$analysis
  if (!identical(a$method, "temporal_fine_gray_prediction")) problems <- c(problems, "Only temporal_fine_gray_prediction is allowed")
  if (!(a$execution_mode %in% c("FORMAL", "SYNTHETIC_TEST"))) problems <- c(problems, "execution_mode must be FORMAL or SYNTHETIC_TEST")
  if (!identical(a$candidate_id, contract$candidate_id)) problems <- c(problems, "analysis.candidate_id mismatch")
  expected_fields <- list(
    patient_id = "record_id", time = "followup_hours", event = "delirium_event",
    competing_event = "competing_event", outcome_observed = "outcome_observed",
    last_observation_time = "outcome_observation_time_hours",
    observation_state = "outcome_observation_state", split = "anchor_era_split",
    development_value = "development", validation_value = "validation"
  )
  if (!formal_fg_semantically_identical(a[names(expected_fields)], expected_fields)) problems <- c(problems, "standardized field binding or anchor-era labels mismatch")
  if (!formal_fg_semantically_identical(a$landmark_hours, contract$landmark_hours)) problems <- c(problems, "landmark must remain 12 hours")
  if (!formal_fg_semantically_identical(a$horizon_hours, contract$horizon_hours)) problems <- c(problems, "horizon must remain 84 hours")
  if (!identical(a$pilot_only, FALSE)) problems <- c(problems, "FORMAL-capability tasks require pilot_only=false")
  if (identical(a$development_value, a$validation_value)) problems <- c(problems, "development and validation values must differ")

  semantics <- list(
    estimand = "84_HOUR_DOCUMENTED_STRUCTURED_DELIRIUM_POSITIVE_CUMULATIVE_INCIDENCE_ABSOLUTE_RISK",
    primary_event = "FIRST_QUALIFYING_STRUCTURED_OVERALL_DELIRIUM_POSITIVE_AFTER_LANDMARK",
    competing_events = c("ICU_EXIT", "DEATH"),
    simultaneous_event_priority = c("DELIRIUM_POSITIVE", "DEATH", "ICU_EXIT"),
    outcome_unobserved_rule = "RIGHT_CENSOR_AT_LAST_KNOWN_OUTCOME_OBSERVATION_TIME_NEVER_RECODE_AS_NO_EVENT",
    patient_isolation = "ONE_RECORD_PER_PATIENT_FIRST_ICU_STAY",
    split_strategy = "PATIENT_ISOLATED_ANCHOR_ERA_TEMPORAL_SPLIT",
    validation_refit = FALSE,
    validation_recalibration = FALSE,
    logistic_fallback = FALSE
  )
  if (!formal_fg_semantically_identical(a$event_semantics, semantics)) problems <- c(problems, "event_semantics mismatch against frozen contract")

  plan <- a$model_plan
  plan_fields <- c(
    "engine", "primary_model_id", "baseline_model_id", "primary_predictors", "baseline_predictors",
    "parameter_df", "transformation_map_sha256", "automatic_selection", "extra_models", "interactions",
    "tuning", "validation_refit", "validation_recalibration", "logistic_substitution"
  )
  if (identical(task$schema_version, "2.0.0")) {
    plan_fields <- c(plan_fields, "transformation_map")
  }
  problems <- c(problems, formal_fg_exact_names(plan, plan_fields, "analysis.model_plan"))
  expected_plan <- list(
    engine = "FINE_GRAY_SUBDISTRIBUTION_HAZARDS",
    primary_model_id = contract$primary_model_id,
    baseline_model_id = contract$baseline_model_id,
    primary_predictors = as.list(contract$primary_predictors),
    baseline_predictors = as.list(contract$baseline_predictors),
    parameter_df = contract$parameter_df,
    transformation_map_sha256 = contract$transformation_map_sha256,
    automatic_selection = FALSE, extra_models = 0L, interactions = FALSE, tuning = FALSE,
    validation_refit = FALSE, validation_recalibration = FALSE, logistic_substitution = FALSE
  )
  if (identical(task$schema_version, "2.0.0")) {
    expected_plan$transformation_map <- contract$transformations
    expected_plan <- expected_plan[plan_fields]
  }
  if (!formal_fg_semantically_identical(plan, expected_plan)) problems <- c(problems, "model_plan mismatch, expansion, or transformation drift")

  if (identical(task$schema_version, "2.0.0") &&
      identical(a$execution_mode, "FORMAL")) {
    if (!identical(task$data$dataset_id, contract$dataset_id) ||
        !identical(task$data$sha256, contract$dataset_sha256)) {
      problems <- c(problems, "V4 requires the exact immutable V2 dataset binding")
    }
    if (!identical(task$binding$sap_id, contract$sap_id) ||
        !identical(task$binding$sap_sha256, contract$sap_sha256)) {
      problems <- c(problems, "V4 requires the exact frozen SAP V3 binding")
    }
  }

  imputation <- list(
    method = "MULTIPLE_IMPUTATION_BY_CHAINED_EQUATIONS", m = 40L, iterations = 20L,
    seed = 20260722L, development_fit_only = TRUE, validation_outcomes_used = FALSE,
    continuous_method = "PREDICTIVE_MEAN_MATCHING", binary_method = "LOGISTIC_REGRESSION",
    categorical_method = "MULTINOMIAL_LOGISTIC_REGRESSION",
    include_development_event_and_followup = TRUE,
    pool_coefficients = "RUBIN_RULES_WHERE_DEFINED", pool_predictions = "MEAN_CUMULATIVE_INCIDENCE_RISK"
  )
  if (!formal_fg_semantically_identical(a$imputation, imputation)) problems <- c(problems, "imputation plan must remain m=40 and development-fitted only")
  internal_validation <- list(
    method = "PATIENT_LEVEL_BOOTSTRAP_FULL_PIPELINE", replicates = 1000L, seed = 20260722L,
    optimism = "BOOTSTRAP_APPARENT_MINUS_TEST_OPTIMISM",
    shrinkage = "MIN_ONE_AND_BOOTSTRAP_CORRECTED_CALIBRATION_SLOPE",
    baseline_hazard_reestimated_from = "DEVELOPMENT_ONLY"
  )
  if (!formal_fg_semantically_identical(a$internal_validation, internal_validation)) problems <- c(problems, "internal bootstrap plan must remain 1000 full-pipeline replicates")
  temporal_validation <- list(
    method = "VALIDATION_ONLY_FIXED_MODEL_PATIENT_BOOTSTRAP", replicates = 2000L,
    seed = 20260723L, interval = "PERCENTILE_95_CI", refit = FALSE, recalibrate = FALSE
  )
  if (!formal_fg_semantically_identical(a$temporal_validation, temporal_validation)) problems <- c(problems, "temporal validation must remain 2000 fixed-model replicates")
  if (!formal_fg_semantically_identical(a$metric_ids, contract$metric_ids)) problems <- c(problems, "metric_ids mismatch")

  gate <- list(
    generation_rule = "ALL_CALIBRATION_CONDITIONS_MUST_PASS",
    oe_ratio_range = list(0.8, 1.25), calibration_slope_range = list(0.8, 1.2),
    maximum_ici = 0.05, maximum_decile_absolute_error = 0.1,
    thresholds = list(0.05, 0.1, 0.15, 0.2, 0.25),
    failed_output = "NOT_GENERATED_GATE_FAILED"
  )
  if (!formal_fg_semantically_identical(a$calibration_gate, gate)) problems <- c(problems, "calibration gate mismatch")
  if (!formal_fg_semantically_identical(a$sensitivity_ids, contract$sensitivity_ids)) problems <- c(problems, "exactly the two frozen sensitivity IDs are required")
  if (!formal_fg_semantically_identical(a$expected_output_ids, contract$expected_output_ids)) problems <- c(problems, "expected_output_ids mismatch")
  if (!formal_fg_semantically_identical(a$qc_variables, list(future_predictor_violation = "future_predictor_violation"))) problems <- c(problems, "qc_variables mismatch")

  if (identical(a$execution_mode, "FORMAL")) {
    if (identical(task$data$dataset_tag, "SYNTHETIC_TEST")) problems <- c(problems, "FORMAL cannot use dataset_tag=SYNTHETIC_TEST")
    if (!identical(task$binding$sap_status, "FROZEN")) problems <- c(problems, "FORMAL requires sap_status=FROZEN")
    auth <- task$binding$formal_authorization
    if (is.null(auth)) {
      problems <- c(problems, "binding.formal_authorization is required for FORMAL execution")
    } else if (!is.list(auth)) {
      problems <- c(problems, "binding.formal_authorization must be an object")
    } else {
      auth_fields <- c("reference", "scope", "candidate_id", "sap_sha256", "dataset_sha256")
      problems <- c(problems, formal_fg_exact_names(auth, auth_fields, "binding.formal_authorization"))
      if (!identical(auth$scope, "FORMAL_ANALYSIS_EXECUTION")) problems <- c(problems, "FORMAL authorization scope mismatch")
      if (!identical(auth$candidate_id, contract$candidate_id) ||
          !identical(auth$sap_sha256, task$binding$sap_sha256) ||
          !identical(auth$dataset_sha256, task$data$sha256)) problems <- c(problems, "FORMAL authorization binding mismatch")
      if (!is.character(auth$reference) || length(auth$reference) != 1L || !nzchar(auth$reference)) problems <- c(problems, "FORMAL authorization reference is required")
    }
  } else {
    if (!identical(task$data$dataset_tag, "SYNTHETIC_TEST")) problems <- c(problems, "SYNTHETIC_TEST requires dataset_tag=SYNTHETIC_TEST")
    if (!identical(task$binding$sap_status, "DRAFT_CAPABILITY_FIXTURE")) problems <- c(problems, "SYNTHETIC_TEST must not claim a frozen SAP")
    if (!is.null(task$binding$formal_authorization)) problems <- c(problems, "SYNTHETIC_TEST must not carry FORMAL authorization")
  }

  output_expected <- list(
    aggregate_only = TRUE, patient_level_output = FALSE,
    physical_paths_in_output = FALSE, source = "ONE_CHECKSUM_BOUND_STRUCTURED_RESULT"
  )
  if (!formal_fg_semantically_identical(task$outputs, output_expected)) problems <- c(problems, "outputs must be aggregate-only, path-free, and single-source")
  if (!formal_fg_semantically_identical(task$readiness, list(min_development_events = 400L, min_validation_events = 200L))) problems <- c(problems, "readiness gates must remain 400 development and 200 validation events")
  if (length(problems)) stop(contract_error(unique(problems[nzchar(problems)])))
  invisible(TRUE)
}

make_synthetic_formal_temporal_fg_task <- function() {
  contract <- formal_temporal_fg_contract()
  list(
    schema_version = "1.0.0",
    analysis_id = "CVCC-PRED-ISO-001-FORMAL-CAPABILITY-SYNTHETIC-TEST",
    seed = 20260722L,
    data = list(
      dataset_id = "DATASET.CVCC-PRED-ISO-001.SYNTHETIC-TEST.V1",
      sha256 = paste(rep("a", 64L), collapse = ""), dataset_tag = "SYNTHETIC_TEST"
    ),
    binding = list(
      candidate_id = contract$candidate_id, sap_id = "SAP.CVCC-PRED-ISO-001.DRAFT.V1",
      sap_sha256 = "9271cae141a00aafc4d23a2ebaa1848612b8f32e83c3cc75aca863ecf01ef843",
      sap_status = "DRAFT_CAPABILITY_FIXTURE"
    ),
    analysis = list(
      method = "temporal_fine_gray_prediction", execution_mode = "SYNTHETIC_TEST",
      candidate_id = contract$candidate_id, patient_id = "record_id", time = "followup_hours",
      event = "delirium_event", competing_event = "competing_event",
      outcome_observed = "outcome_observed", last_observation_time = "outcome_observation_time_hours",
      observation_state = "outcome_observation_state", split = "anchor_era_split",
      development_value = "development", validation_value = "validation",
      landmark_hours = 12, horizon_hours = 84,
      event_semantics = list(
        estimand = "84_HOUR_DOCUMENTED_STRUCTURED_DELIRIUM_POSITIVE_CUMULATIVE_INCIDENCE_ABSOLUTE_RISK",
        primary_event = "FIRST_QUALIFYING_STRUCTURED_OVERALL_DELIRIUM_POSITIVE_AFTER_LANDMARK",
        competing_events = c("ICU_EXIT", "DEATH"),
        simultaneous_event_priority = c("DELIRIUM_POSITIVE", "DEATH", "ICU_EXIT"),
        outcome_unobserved_rule = "RIGHT_CENSOR_AT_LAST_KNOWN_OUTCOME_OBSERVATION_TIME_NEVER_RECODE_AS_NO_EVENT",
        patient_isolation = "ONE_RECORD_PER_PATIENT_FIRST_ICU_STAY",
        split_strategy = "PATIENT_ISOLATED_ANCHOR_ERA_TEMPORAL_SPLIT",
        validation_refit = FALSE, validation_recalibration = FALSE, logistic_fallback = FALSE
      ),
      model_plan = list(
        engine = "FINE_GRAY_SUBDISTRIBUTION_HAZARDS", primary_model_id = contract$primary_model_id,
        baseline_model_id = contract$baseline_model_id, primary_predictors = as.list(contract$primary_predictors),
        baseline_predictors = as.list(contract$baseline_predictors), parameter_df = 27L,
        transformation_map_sha256 = contract$transformation_map_sha256,
        automatic_selection = FALSE, extra_models = 0L, interactions = FALSE, tuning = FALSE,
        validation_refit = FALSE, validation_recalibration = FALSE, logistic_substitution = FALSE
      ),
      imputation = list(
        method = "MULTIPLE_IMPUTATION_BY_CHAINED_EQUATIONS", m = 40L, iterations = 20L,
        seed = 20260722L, development_fit_only = TRUE, validation_outcomes_used = FALSE,
        continuous_method = "PREDICTIVE_MEAN_MATCHING", binary_method = "LOGISTIC_REGRESSION",
        categorical_method = "MULTINOMIAL_LOGISTIC_REGRESSION",
        include_development_event_and_followup = TRUE,
        pool_coefficients = "RUBIN_RULES_WHERE_DEFINED", pool_predictions = "MEAN_CUMULATIVE_INCIDENCE_RISK"
      ),
      internal_validation = list(
        method = "PATIENT_LEVEL_BOOTSTRAP_FULL_PIPELINE", replicates = 1000L, seed = 20260722L,
        optimism = "BOOTSTRAP_APPARENT_MINUS_TEST_OPTIMISM",
        shrinkage = "MIN_ONE_AND_BOOTSTRAP_CORRECTED_CALIBRATION_SLOPE",
        baseline_hazard_reestimated_from = "DEVELOPMENT_ONLY"
      ),
      temporal_validation = list(
        method = "VALIDATION_ONLY_FIXED_MODEL_PATIENT_BOOTSTRAP", replicates = 2000L,
        seed = 20260723L, interval = "PERCENTILE_95_CI", refit = FALSE, recalibrate = FALSE
      ),
      metric_ids = as.list(contract$metric_ids),
      calibration_gate = list(
        generation_rule = "ALL_CALIBRATION_CONDITIONS_MUST_PASS", oe_ratio_range = list(0.8, 1.25),
        calibration_slope_range = list(0.8, 1.2), maximum_ici = 0.05,
        maximum_decile_absolute_error = 0.1, thresholds = list(0.05, 0.1, 0.15, 0.2, 0.25),
        failed_output = "NOT_GENERATED_GATE_FAILED"
      ),
      sensitivity_ids = as.list(contract$sensitivity_ids), expected_output_ids = as.list(contract$expected_output_ids),
      qc_variables = list(future_predictor_violation = "future_predictor_violation"), pilot_only = FALSE
    ),
    readiness = list(min_development_events = 400L, min_validation_events = 200L),
    outputs = list(
      aggregate_only = TRUE, patient_level_output = FALSE,
      physical_paths_in_output = FALSE, source = "ONE_CHECKSUM_BOUND_STRUCTURED_RESULT"
    )
  )
}

make_synthetic_formal_temporal_fg_task_v4 <- function() {
  task <- make_synthetic_formal_temporal_fg_task()
  contract <- formal_temporal_fg_contract_v4()
  task$schema_version <- "2.0.0"
  task$analysis_id <- "CVCC-PRED-ISO-001-TASK-V4-CAPABILITY-SYNTHETIC-TEST"
  task$analysis$model_plan$primary_model_id <- contract$primary_model_id
  task$analysis$model_plan$primary_predictors <- as.list(contract$primary_predictors)
  task$analysis$model_plan$parameter_df <- contract$parameter_df
  task$analysis$model_plan$transformation_map_sha256 <-
    contract$transformation_map_sha256
  task$analysis$model_plan$transformation_map <- contract$transformations
  task
}
