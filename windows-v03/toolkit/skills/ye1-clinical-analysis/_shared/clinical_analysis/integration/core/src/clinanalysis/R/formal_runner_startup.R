.formal_runner_startup_diagnostic_version <-
  "formal-runner-startup-diagnostic@1.0.0"

.formal_runner_startup_codes <- list(
  PROJECT_ENVIRONMENT_NOT_ACTIVE =
    "The project dependency environment is not active.",
  DEPENDENCY_MISSING =
    "One or more required project dependencies are unavailable.",
  NAMESPACE_LOAD_FAILED =
    "The analysis package namespace could not be loaded.",
  PLUGIN_LOOKUP_FAILED =
    "The registered FORMAL plugin is unavailable.",
  TASK_CONTRACT_REGISTRY_MISSING =
    "The FORMAL task contract is unavailable.",
  RESULT_CONTRACT_REGISTRY_MISSING =
    "A required FORMAL result contract is unavailable.",
  STARTUP_TIMEOUT =
    "The bounded FORMAL startup check did not complete in time.",
  STARTUP_REQUEST_INVALID =
    "The FORMAL startup request is invalid."
)

.formal_runner_startup_check_names <- c(
  "project_environment", "dependencies", "namespace", "plugin",
  "task_contract", "result_contracts"
)

formal_runner_startup_checks <- function() {
  stats::setNames(
    as.list(rep("NOT_RUN", length(.formal_runner_startup_check_names))),
    .formal_runner_startup_check_names
  )
}

formal_runner_startup_execution_boundary <- function() {
  list(
    v2_opened = FALSE,
    patient_data_opened = FALSE,
    formal_authorization_created_or_consumed = FALSE,
    formal_runner_called = FALSE,
    model_called = FALSE,
    imputation_called = FALSE,
    bootstrap_called = FALSE
  )
}

new_formal_runner_startup_diagnostic <- function(
    code = NULL,
    checks = formal_runner_startup_checks()) {
  status <- if (is.null(code)) "PASS" else "FAILED"
  diagnostic <- list(
    schema_version = .formal_runner_startup_diagnostic_version,
    status = status,
    aggregate_only = TRUE,
    patient_level_payload = FALSE,
    physical_paths_in_diagnostic = FALSE,
    failure_stage = if (is.null(code)) NULL else "RUNNER_INITIALIZATION",
    error_code = code,
    safe_message = if (is.null(code)) {
      "FORMAL runner startup checks passed."
    } else {
      unname(.formal_runner_startup_codes[[code]] %||% "")
    },
    checks = checks,
    execution_boundary = formal_runner_startup_execution_boundary()
  )
  validate_formal_runner_startup_diagnostic(diagnostic)
  diagnostic
}

validate_formal_runner_startup_diagnostic <- function(diagnostic) {
  top_fields <- c(
    "schema_version", "status", "aggregate_only", "patient_level_payload",
    "physical_paths_in_diagnostic", "failure_stage", "error_code",
    "safe_message", "checks", "execution_boundary"
  )
  problems <- formal_fg_result_exact_object(
    diagnostic, top_fields, "startup_diagnostic"
  )
  if (!is.list(diagnostic)) stop(contract_error(problems))
  if (!identical(
    diagnostic$schema_version,
    .formal_runner_startup_diagnostic_version
  )) {
    problems <- c(problems, "Unsupported FORMAL runner startup schema_version")
  }
  if (!diagnostic$status %in% c("PASS", "FAILED") ||
      !identical(diagnostic$aggregate_only, TRUE) ||
      !identical(diagnostic$patient_level_payload, FALSE) ||
      !identical(diagnostic$physical_paths_in_diagnostic, FALSE)) {
    problems <- c(
      problems,
      "Startup diagnostics must be aggregate-only, patient-free, and path-free"
    )
  }
  if (identical(diagnostic$status, "PASS")) {
    if (!is.null(diagnostic$failure_stage) ||
        !is.null(diagnostic$error_code) ||
        !identical(
          diagnostic$safe_message,
          "FORMAL runner startup checks passed."
        )) {
      problems <- c(
        problems,
        "Passing startup diagnostics cannot carry a failure"
      )
    }
  } else {
    if (!identical(diagnostic$failure_stage, "RUNNER_INITIALIZATION") ||
        !diagnostic$error_code %in% names(.formal_runner_startup_codes) ||
        !identical(
          diagnostic$safe_message,
          unname(.formal_runner_startup_codes[[diagnostic$error_code]])
        )) {
      problems <- c(
        problems,
        "Startup failure must use an allowlisted code and safe message"
      )
    }
  }
  problems <- c(
    problems,
    formal_fg_result_exact_object(
      diagnostic$checks,
      .formal_runner_startup_check_names,
      "startup_diagnostic.checks"
    ),
    formal_fg_result_exact_object(
      diagnostic$execution_boundary,
      c(
        "v2_opened", "patient_data_opened",
        "formal_authorization_created_or_consumed", "formal_runner_called",
        "model_called", "imputation_called", "bootstrap_called"
      ),
      "startup_diagnostic.execution_boundary"
    )
  )
  if (is.list(diagnostic$checks)) {
    check_values <- unlist(diagnostic$checks, use.names = FALSE)
    if (length(check_values) != length(.formal_runner_startup_check_names) ||
        !all(check_values %in% c("PASS", "FAIL", "NOT_RUN"))) {
      problems <- c(problems, "Startup checks contain an invalid status")
    }
    if (identical(diagnostic$status, "PASS") &&
        !all(check_values == "PASS")) {
      problems <- c(problems, "All startup checks must pass")
    }
  }
  if (is.list(diagnostic$execution_boundary) &&
      !all(vapply(
        diagnostic$execution_boundary,
        identical,
        logical(1),
        FALSE
      ))) {
    problems <- c(
      problems,
      "Startup checks cannot read data, consume authority, or invoke models"
    )
  }
  rendered <- jsonlite::toJSON(
    diagnostic, auto_unbox = TRUE, null = "null"
  )
  forbidden <- c(
    "(^|[^A-Za-z])[A-Za-z]:[/\\\\]", "(/Users/|/private/|/tmp/|~/)",
    "patient[_ -]?id", "subject[_ -]?id", "record[_ -]?id",
    "row[_ -]?[0-9]", "call stack", "traceback"
  )
  if (any(vapply(
    forbidden, grepl, logical(1),
    x = rendered, ignore.case = TRUE, perl = TRUE
  ))) {
    problems <- c(
      problems,
      "Startup diagnostic contains forbidden path, identifier, row, or stack"
    )
  }
  problems <- unique(problems[nzchar(problems)])
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

formal_runner_startup_self_check <- function(
    project_environment_verified,
    dependency_environment_verified,
    plugin_registry = analysis_plugin_registry,
    result_registry = result_contract_registry,
    task_factory = make_synthetic_formal_temporal_fg_task_v4,
    task_validator = validate_analysis_task,
    dispatch_probe = formal_temporal_fg_registered_dispatch_probe) {
  checks <- formal_runner_startup_checks()
  if (!identical(project_environment_verified, TRUE)) {
    checks$project_environment <- "FAIL"
    return(new_formal_runner_startup_diagnostic(
      "PROJECT_ENVIRONMENT_NOT_ACTIVE", checks
    ))
  }
  checks$project_environment <- "PASS"
  if (!identical(dependency_environment_verified, TRUE)) {
    checks$dependencies <- "FAIL"
    return(new_formal_runner_startup_diagnostic(
      "DEPENDENCY_MISSING", checks
    ))
  }
  checks$dependencies <- "PASS"
  checks$namespace <- "PASS"

  plugins <- tryCatch(plugin_registry(), error = function(e) NULL)
  if (!is.list(plugins) ||
      !is.function(plugins[["temporal_fine_gray_prediction"]])) {
    checks$plugin <- "FAIL"
    return(new_formal_runner_startup_diagnostic(
      "PLUGIN_LOOKUP_FAILED", checks
    ))
  }

  task <- tryCatch(task_factory(), error = function(e) NULL)
  task_valid <- is.list(task) &&
    identical(task$schema_version, "2.0.0") &&
    isTRUE(tryCatch(task_validator(task), error = function(e) FALSE))
  if (!task_valid) {
    checks$task_contract <- "FAIL"
    return(new_formal_runner_startup_diagnostic(
      "TASK_CONTRACT_REGISTRY_MISSING", checks
    ))
  }
  checks$task_contract <- "PASS"
  dispatch_valid <- tryCatch(
    dispatch_probe(plugins[["temporal_fine_gray_prediction"]], task),
    error = function(e) FALSE
  )
  if (!identical(dispatch_valid, TRUE)) {
    checks$plugin <- "FAIL"
    return(new_formal_runner_startup_diagnostic(
      "PLUGIN_LOOKUP_FAILED", checks
    ))
  }
  checks$plugin <- "PASS"

  contracts <- tryCatch(result_registry(), error = function(e) NULL)
  required <- c(
    "formal-temporal-fine-gray-result@2.0.0",
    "formal-temporal-fine-gray-output-manifest@1.1.0",
    "formal-temporal-fine-gray-failure-diagnostic@1.0.0",
    "formal-temporal-fine-gray-failure-diagnostic@1.1.0",
    "formal-temporal-fine-gray-failure-diagnostic@1.2.0",
    "formal-temporal-fine-gray-failure-diagnostic@1.3.0",
    "formal-runner-startup-diagnostic@1.0.0"
  )
  if (!is.list(contracts) ||
      !all(vapply(
        required,
        function(name) is.function(contracts[[name]]),
        logical(1)
      ))) {
    checks$result_contracts <- "FAIL"
    return(new_formal_runner_startup_diagnostic(
      "RESULT_CONTRACT_REGISTRY_MISSING", checks
    ))
  }
  checks$result_contracts <- "PASS"
  new_formal_runner_startup_diagnostic(checks = checks)
}
