.categorical_gcomp_task_version <- "categorical-transfer-gcomp-task@1.1.0"
.categorical_gcomp_task_versions <- c(
  "categorical-transfer-gcomp-task@1.0.0",
  "categorical-transfer-gcomp-task@1.1.0",
  "categorical-transfer-gcomp-task@1.2.0"
)
.categorical_gcomp_method <- "categorical_logistic_g_computation"
.categorical_gcomp_seed <- 80320260724
.categorical_gcomp_full_task_version <- "categorical-transfer-gcomp-task@1.2.0"
.categorical_gcomp_sensitivity_ids <- c(
  "S1_RECENT_PRIOR_TRANSFER_1H",
  "S2_EXCLUDE_OTHER_ICU"
)
.categorical_gcomp_output_ids <- c(
  "OUT_COHORT",
  "OUT_PRIMARY_UNADJUSTED",
  "OUT_PRIMARY_ADJUSTED",
  "OUT_DEEPENING",
  "OUT_CREDIBILITY",
  "OUT_DIAGNOSTICS"
)
.categorical_gcomp_result_versions <- c(
  "categorical-gcomp-cohort-flow@1.0.0",
  "categorical-gcomp-unadjusted-source-risks@1.0.0",
  "categorical-gcomp-adjusted-risks@1.0.0",
  "categorical-gcomp-first-event-composition@1.0.0",
  "categorical-gcomp-credibility-results@1.0.0",
  "categorical-gcomp-diagnostics@1.0.0",
  "categorical-gcomp-result-bundle@1.0.0",
  "categorical-gcomp-result-bundle@1.1.0",
  "categorical-gcomp-failure-diagnostic@1.0.0"
)
.categorical_gcomp_full_result_bundle_version <- "categorical-gcomp-result-bundle@1.1.0"
.categorical_gcomp_full_output_manifest_version <- "full-article-tfl-bundle@1.0.0"
.categorical_gcomp_full_article_target_id <- "ARTICLE_TARGET.FULL_ORIGINAL_APPROX_SCI6.V1"
.categorical_gcomp_full_article_profile_checksum <- "sha256:70d6f71a83c5482fef659ea4e267fede5e4fcfc3192468aee126aacbd72fbd30"
.categorical_gcomp_full_output_ids <- c(
  "OUT_COHORT",
  "OUT_PRIMARY_UNADJUSTED",
  "OUT_PRIMARY_ADJUSTED",
  "OUT_DEEPENING",
  "OUT_CREDIBILITY",
  "OUT_DIAGNOSTICS",
  "TABLE1",
  "TABLE_PRIMARY_ESTIMATES",
  "TABLE_DEEPENING_CREDIBILITY",
  "FIGURE_COHORT_FLOW",
  "FIGURE_PRIMARY_EFFECT",
  "FIGURE_CLINICAL_DEEPENING_FIRST_EVENT_COMPOSITION"
)
.categorical_gcomp_full_display_contract_version <- "planned-full-article-display-contract@1.0.0"
.categorical_gcomp_full_raw_source_label <- "non-display"
.categorical_gcomp_full_display_source_label <- "display"
.categorical_gcomp_full_display_output_specs <- list(
  TABLE1 = list(
    filename = "table1.csv",
    role = "BASELINE_CHARACTERISTICS",
    scientific_domain = "MAIN_ANSWER",
    source_result_id = "DISPLAY.SOURCE.RESULT.TABLE1"
  ),
  TABLE_PRIMARY_ESTIMATES = list(
    filename = "primary_estimates.csv",
    role = "PRIMARY_ESTIMATES",
    scientific_domain = "MAIN_ANSWER",
    source_result_id = "DISPLAY.SOURCE.RESULT.PRIMARY_ESTIMATES"
  ),
  TABLE_DEEPENING_CREDIBILITY = list(
    filename = "deepening_credibility.csv",
    role = "CREDIBILITY",
    scientific_domain = "CREDIBILITY",
    source_result_id = "DISPLAY.SOURCE.RESULT.DEEPENING_CREDIBILITY"
  ),
  FIGURE_COHORT_FLOW = list(
    filename = "figure_cohort_flow.png",
    role = "COHORT_FLOW",
    scientific_domain = "MAIN_ANSWER",
    source_result_id = "DISPLAY.SOURCE.RESULT.COHORT_FLOW"
  ),
  FIGURE_PRIMARY_EFFECT = list(
    filename = "figure_primary_effect.png",
    role = "PRIMARY_EFFECT",
    scientific_domain = "MAIN_ANSWER",
    source_result_id = "DISPLAY.SOURCE.RESULT.PRIMARY_EFFECT"
  ),
  FIGURE_CLINICAL_DEEPENING_FIRST_EVENT_COMPOSITION = list(
    filename = "figure_clinical_deepening_first_event_composition.png",
    role = "CLINICAL_DEEPENING",
    scientific_domain = "CLINICAL_DEEPENING",
    source_result_id = "DISPLAY.SOURCE.RESULT.FIRST_EVENT_COMPOSITION"
  )
)
.categorical_gcomp_full_display_output_ids <- names(.categorical_gcomp_full_display_output_specs)
.categorical_gcomp_failure_codes <- c(
  "TASK_CONTRACT_INVALID",
  "DATA_SEMANTICS_INVALID",
  "UNKNOWN_SOURCE_VALUE",
  "DUPLICATE_RECORD_ID",
  "MISSING_REFERENCE_SUPPORT",
  "MODEL_NONCONVERGENCE",
  "NONFINITE_ESTIMATE",
  "INVALID_COVARIANCE",
  "NONFINITE_PREDICTION",
  "RESULT_CONTRACT_INVALID",
  "OUTPUT_ALREADY_EXISTS",
  "FULL_ARTICLE_TARGET_MISMATCH",
  "NOT_ESTIMABLE",
  "INTERNAL_ERROR"
)

categorical_gcomp_is_full_article_target <- function(task) {
  full_target <- task$analysis$full_article_target_id %||% NULL
  is.character(full_target) && length(full_target) == 1L &&
    !is.na(full_target) && full_target == .categorical_gcomp_full_article_target_id
}

categorical_gcomp_is_prefixed_sha256 <- function(value) {
  categorical_gcomp_scalar_string(value) && grepl("^sha256:[a-f0-9]{64}$", value)
}

categorical_gcomp_make_manifest_id <- function(candidate_id, task_id) {
  paste("MANIFEST", candidate_id, task_id, sep = ".")
}

categorical_gcomp_full_research_bindings <- function(task, execution_binding) {
  list(
    candidate_id = task$binding$candidate_id,
    candidate_sha256 = task$binding$candidate_sha256,
    sap_id = task$binding$sap_id,
    sap_sha256 = task$binding$sap_sha256,
    analysis_task_id = task$task_id,
    analysis_task_sha256 = execution_binding$task_sha256,
    value_set_id = task$binding$value_set_id,
    value_set_sha256 = task$binding$value_set_sha256,
    source_snapshot_id = task$data$dataset_id,
    source_snapshot_sha256 = task$data$sha256
  )
}

categorical_gcomp_canonicalize_json_object <- function(value) {
  if (is.null(value)) return(NULL)
  if (is.list(value)) {
    if (is.null(names(value))) {
      return(lapply(value, categorical_gcomp_canonicalize_json_object))
    }
    ordered <- value[order(names(value))]
    return(lapply(ordered, categorical_gcomp_canonicalize_json_object))
  }
  if (is.atomic(value) || is.null(value)) return(value)
  value
}

categorical_gcomp_display_contract_checksum <- function(plan) {
  payload <- categorical_gcomp_canonicalize_json_object(plan)
  rendered <- jsonlite::toJSON(
    payload,
    auto_unbox = TRUE,
    null = "null",
    digits = NA
  )
  paste0("sha256:", digest::digest(rendered, algo = "sha256", serialize = FALSE))
}

categorical_gcomp_validate_planned_display_contract <- function(planned_display_contract, task = NULL) {
  expected_display_pairs <- vapply(
    .categorical_gcomp_full_display_output_ids,
    function(output_id) {
      spec <- .categorical_gcomp_full_display_output_specs[[output_id]]
      output_kind <- if (startsWith(output_id, "TABLE")) "TABLE" else "FIGURE"
      paste(output_kind, spec$role, sep = "::")
    },
    character(1L)
  )
  required <- c(
    "schema_version",
    "contract_id",
    "candidate_id",
    "target_profile",
    "target_profile_sha256",
    "prior_result_exposure",
    "confirmatory_claim_allowed",
    "displays",
    "table1_required",
    "figure_manifest_required",
    "all_displays_from_single_structured_result",
    "synthetic_tfl_acceptance_required",
    "result_driven_replacement_allowed"
  )
  problems <- character()
  if (!is.list(planned_display_contract)) {
    stop(contract_error("planned_display_contract must be an object"))
  }
  if (!identical(planned_display_contract$schema_version, .categorical_gcomp_full_display_contract_version)) {
    problems <- c(problems, sprintf("planned_display_contract.schema_version must be %s", .categorical_gcomp_full_display_contract_version))
  }
  missing <- setdiff(required, names(planned_display_contract))
  if (length(missing)) {
    problems <- c(
      problems,
      sprintf(
        "planned_display_contract missing required fields: %s",
        paste(missing, collapse = ", ")
      )
    )
  }
  allowed <- required
  extra <- setdiff(names(planned_display_contract), allowed)
  if (length(extra)) {
    problems <- c(
      problems,
      sprintf("planned_display_contract has unexpected fields: %s", paste(extra, collapse = ", "))
    )
  }
  if (!categorical_gcomp_scalar_string(planned_display_contract$candidate_id) ||
      !grepl("^[A-Z0-9][A-Z0-9._-]{2,127}$", planned_display_contract$candidate_id)) {
    problems <- c(problems, "planned_display_contract.candidate_id must be a logical id")
  }
  if (!categorical_gcomp_scalar_string(planned_display_contract$contract_id)) {
    problems <- c(problems, "planned_display_contract.contract_id must be one non-empty string")
  }
  if (!is.list(planned_display_contract$target_profile)) {
    problems <- c(problems, "planned_display_contract.target_profile must be an object")
  } else {
    target_profile <- planned_display_contract$target_profile
    required_profile <- c(
      "profile_id",
      "schema_version",
      "automatic_volume_gate_required",
      "compact_article_allowed",
      "human_volume_detection_required",
      "minimum_figure_count",
      "minimum_table_count",
      "minimum_total_display_count",
      "required_figure_roles",
      "required_table_roles",
      "required_scientific_domains",
      "result_driven_replacement_allowed",
      "submission_authorized",
      "target_positioning"
    )
    missing_profile <- setdiff(required_profile, names(target_profile))
    if (length(missing_profile)) {
      problems <- c(
        problems,
        sprintf(
          "planned_display_contract.target_profile missing required fields: %s",
          paste(missing_profile, collapse = ", ")
        )
      )
    }
    extra_profile <- setdiff(names(target_profile), required_profile)
    if (length(extra_profile)) {
      problems <- c(
        problems,
        sprintf(
          "planned_display_contract.target_profile has unexpected fields: %s",
          paste(extra_profile, collapse = ", ")
        )
      )
    }
    if (length(missing_profile) == 0L && length(extra_profile) == 0L) {
      if (!is.null(target_profile$schema_version) &&
          !identical(target_profile$schema_version, "full-article-target-profile@1.0.0")) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile.schema_version must be full-article-target-profile@1.0.0"
        )
      }
      target_profile_expected_figure_roles <- c(
        "COHORT_FLOW",
        "PRIMARY_EFFECT",
        "CLINICAL_DEEPENING"
      )
      target_profile_required_table_roles <- c(
        "BASELINE_CHARACTERISTICS",
        "PRIMARY_ESTIMATES",
        "CREDIBILITY"
      )
      target_profile_required_domains <- c(
        "MAIN_ANSWER",
        "CLINICAL_DEEPENING",
        "CREDIBILITY"
      )
      if (!isTRUE(all.equal(target_profile$required_figure_roles, as.list(target_profile_expected_figure_roles))) ||
          !isTRUE(all.equal(target_profile$required_table_roles, as.list(target_profile_required_table_roles))) ||
          !isTRUE(all.equal(target_profile$required_scientific_domains, as.list(target_profile_required_domains))) ||
          !identical(target_profile$target_positioning, "FULL_ORIGINAL_APPROX_SCI6") ||
          !isTRUE(target_profile$automatic_volume_gate_required) ||
          !isFALSE(target_profile$compact_article_allowed) ||
          !isFALSE(target_profile$human_volume_detection_required) ||
          !identical(target_profile$minimum_figure_count, 3L) ||
          !identical(target_profile$minimum_table_count, 3L) ||
          !identical(target_profile$minimum_total_display_count, 6L) ||
          !isFALSE(target_profile$result_driven_replacement_allowed) ||
          !isFALSE(target_profile$submission_authorized)) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile must match canonical full-article target profile bindings"
        )
      }
      if (!is.character(target_profile$profile_id) || !nzchar(target_profile$profile_id)) {
        problems <- c(problems, "planned_display_contract.target_profile.profile_id must be a non-empty string")
      } else if (!grepl("^[A-Z0-9][A-Z0-9._-]{2,127}$", target_profile$profile_id)) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile.profile_id must be a logical id"
        )
      }
      if (!is.list(target_profile$required_figure_roles) ||
          any(!vapply(target_profile$required_figure_roles, categorical_gcomp_scalar_string, logical(1L)))) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile.required_figure_roles must be a list of role names"
        )
      }
      if (!is.list(target_profile$required_table_roles) ||
          any(!vapply(target_profile$required_table_roles, categorical_gcomp_scalar_string, logical(1L)))) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile.required_table_roles must be a list of role names"
        )
      }
      if (!is.list(target_profile$required_scientific_domains) ||
          any(!vapply(target_profile$required_scientific_domains, categorical_gcomp_scalar_string, logical(1L)))) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile.required_scientific_domains must be a list of domain names"
        )
      }
      expected_profile_checksum <- categorical_gcomp_display_contract_checksum(target_profile)
      if (!identical(expected_profile_checksum, planned_display_contract$target_profile_sha256)) {
        problems <- c(
          problems,
          "planned_display_contract.target_profile_sha256 must be canonical hash of target_profile"
        )
      }
    }
  }
  if (!categorical_gcomp_is_prefixed_sha256(planned_display_contract$target_profile_sha256)) {
    problems <- c(
      problems,
      "planned_display_contract.target_profile_sha256 must be prefixed SHA-256"
    )
  }
  if (!is.logical(planned_display_contract$table1_required) || !identical(planned_display_contract$table1_required, TRUE)) {
    problems <- c(problems, "planned_display_contract.table1_required must be TRUE")
  }
  if (!is.logical(planned_display_contract$figure_manifest_required) || !identical(planned_display_contract$figure_manifest_required, TRUE)) {
    problems <- c(problems, "planned_display_contract.figure_manifest_required must be TRUE")
  }
  if (!is.logical(planned_display_contract$all_displays_from_single_structured_result) ||
      !identical(planned_display_contract$all_displays_from_single_structured_result, TRUE)) {
    problems <- c(problems, "planned_display_contract.all_displays_from_single_structured_result must be TRUE")
  }
  if (!is.logical(planned_display_contract$synthetic_tfl_acceptance_required) ||
      !identical(planned_display_contract$synthetic_tfl_acceptance_required, TRUE)) {
    problems <- c(problems, "planned_display_contract.synthetic_tfl_acceptance_required must be TRUE")
  }
  if (!is.logical(planned_display_contract$result_driven_replacement_allowed) ||
      !identical(planned_display_contract$result_driven_replacement_allowed, FALSE)) {
    problems <- c(problems, "planned_display_contract.result_driven_replacement_allowed must be FALSE")
  }
  if (!categorical_gcomp_scalar_logical(planned_display_contract$prior_result_exposure)) {
    problems <- c(
      problems,
      "planned_display_contract.prior_result_exposure must be a logical value"
    )
  }
  if (!categorical_gcomp_scalar_logical(planned_display_contract$confirmatory_claim_allowed)) {
    problems <- c(
      problems,
      "planned_display_contract.confirmatory_claim_allowed must be a logical value"
    )
  }
  if (isTRUE(planned_display_contract$prior_result_exposure) &&
      isTRUE(planned_display_contract$confirmatory_claim_allowed)) {
    problems <- c(
      problems,
      "planned_display_contract.confirmatory_claim_allowed must be false when prior_result_exposure is true"
    )
  }
  if (!is.list(planned_display_contract$displays) || is.data.frame(planned_display_contract$displays)) {
    problems <- c(problems, "planned_display_contract.displays must be a list")
  } else {
    if (length(planned_display_contract$displays) != length(expected_display_pairs)) {
      problems <- c(problems, "planned_display_contract.displays must contain exactly six outputs")
    }
    display_ids <- character()
    display_pairs <- character()
    for (entry in planned_display_contract$displays) {
      problems <- c(
        problems,
        categorical_gcomp_exact_names(
          entry,
          c(
            "display_id",
            "kind",
            "role",
            "scientific_domain",
            "source_result_id",
            "required",
            "aggregate_only",
            "nonredundant",
            "cosmetic_only"
          ),
          "planned_display_contract.displays entry"
        )
      )
      if (!categorical_gcomp_scalar_string(entry$display_id) || !nzchar(entry$display_id)) {
        problems <- c(problems, "planned_display_contract.displays output entry requires display_id")
      } else {
        display_ids <- c(display_ids, entry$display_id)
        if (!grepl("^(FIGURE|TABLE)\\.[A-Z0-9][A-Z0-9._-]{2,127}$", entry$display_id)) {
          problems <- c(problems, "planned_display_contract.displays display_id must use FIGURE.* or TABLE.* logical id format")
        }
      }
      if (!entry$kind %in% c("FIGURE", "TABLE")) {
        problems <- c(problems, "planned_display_contract.displays kind must be FIGURE or TABLE")
      }
      if (!entry$role %in% c(
        "COHORT_FLOW",
        "PRIMARY_EFFECT",
        "CLINICAL_DEEPENING",
        "BASELINE_CHARACTERISTICS",
        "PRIMARY_ESTIMATES",
        "CREDIBILITY"
      )) {
        problems <- c(problems, sprintf("planned_display_contract displlays has unsupported role: %s", entry$role))
      }
      if (entry$kind == "TABLE" && !entry$role %in% c(
        "BASELINE_CHARACTERISTICS",
        "PRIMARY_ESTIMATES",
        "CREDIBILITY"
      )) {
        problems <- c(problems, sprintf("planned_display_contract display role invalid for TABLE: %s", entry$role))
      }
      if (entry$kind == "FIGURE" && !entry$role %in% c(
        "COHORT_FLOW",
        "PRIMARY_EFFECT",
        "CLINICAL_DEEPENING"
      )) {
        problems <- c(problems, sprintf("planned_display_contract display role invalid for FIGURE: %s", entry$role))
      }
      if (!entry$scientific_domain %in% c(
        "MAIN_ANSWER",
        "CLINICAL_DEEPENING",
        "CREDIBILITY"
      )) {
        problems <- c(
          problems,
          sprintf(
            "planned_display_contract displlays scientific_domain must be MAIN_ANSWER|CLINICAL_DEEPENING|CREDIBILITY: %s",
            entry$scientific_domain
          )
        )
      }
      if (!isTRUE(entry$required)) {
        problems <- c(problems, "planned_display_contract displays required must be TRUE")
      }
      if (!isTRUE(entry$aggregate_only)) {
        problems <- c(problems, "planned_display_contract displays aggregate_only must be TRUE")
      }
      if (!isTRUE(entry$nonredundant)) {
        problems <- c(problems, "planned_display_contract displays nonredundant must be TRUE")
      }
      if (!isFALSE(entry$cosmetic_only)) {
        problems <- c(problems, "planned_display_contract displays cosmetic_only must be FALSE")
      }
      if (!categorical_gcomp_scalar_string(entry$source_result_id)) {
        problems <- c(problems, "planned_display_contract.displays source_result_id must be a logical id")
      }
      pair <- paste(entry$kind, entry$role, sep = "::")
      display_pairs <- c(display_pairs, pair)
      if (!pair %in% expected_display_pairs) {
        problems <- c(problems, sprintf("planned_display_contract unsupported kind/role pair: %s/%s", entry$kind, entry$role))
      }
    }
    if (anyDuplicated(display_ids)) {
      problems <- c(problems, "planned_display_contract.displays must not duplicate display_id")
    }
    if (length(unique(display_pairs)) != length(display_pairs)) {
      problems <- c(problems, "planned_display_contract.displays must not duplicate kind-role mappings")
    }
    if (length(setdiff(expected_display_pairs, unique(display_pairs)))) {
      problems <- c(
        problems,
        sprintf(
          "planned_display_contract displlays missing required kind-role mappings: %s",
          paste(setdiff(expected_display_pairs, unique(display_pairs)), collapse = ", ")
        )
      )
    }
  }
  if (!is.null(task)) {
    if (!categorical_gcomp_scalar_string(task$binding$candidate_id) ||
        !identical(task$binding$candidate_id, planned_display_contract$candidate_id)) {
      problems <- c(
        problems,
        "planned_display_contract.candidate_id must match task.binding$candidate_id"
      )
    }
    if (!identical(task$analysis$full_article_target_id, planned_display_contract$target_profile$profile_id)) {
      problems <- c(
        problems,
        "planned_display_contract.target_profile.profile_id must match task.analysis$full_article_target_id"
      )
    }
    if (!identical(task$analysis$full_article_profile_checksum, planned_display_contract$target_profile_sha256)) {
      problems <- c(
        problems,
        "planned_display_contract.target_profile_sha256 must match task.analysis$full_article_profile_checksum"
      )
    }
    if (!identical(task$analysis$prior_result_exposure, planned_display_contract$prior_result_exposure)) {
      problems <- c(
        problems,
        "planned_display_contract.prior_result_exposure must match task.analysis$prior_result_exposure"
      )
    }
    if (!identical(task$analysis$confirmatory_claim_allowed, planned_display_contract$confirmatory_claim_allowed)) {
      problems <- c(
        problems,
        "planned_display_contract.confirmatory_claim_allowed must match task.analysis$confirmatory_claim_allowed"
      )
    }
    expected_checksum <- categorical_gcomp_display_contract_checksum(planned_display_contract)
    if (!identical(task$analysis$planned_display_contract_sha256, expected_checksum)) {
      problems <- c(
        problems,
        "task.analysis.planned_display_contract_sha256 must match planned display contract checksum"
      )
    }
  }
  if (length(problems)) stop(contract_error(unique(problems[nzchar(problems)])))
  planned_display_contract
}

categorical_gcomp_build_display_contract_metadata <- function(planned_display_contract) {
  metadata <- list()
  for (entry in planned_display_contract$displays) {
    key <- paste(entry$kind, entry$role, sep = "::")
    metadata[[key]] <- list(
      display_id = entry$display_id,
      role = entry$role,
      scientific_domain = entry$scientific_domain,
      source_result_id = entry$source_result_id
    )
  }
  metadata
}

categorical_gcomp_validate_execution_authorization_binding <- function(
  execution_binding,
  task
) {
  if (!identical(task$schema_version, .categorical_gcomp_full_task_version)) {
    return(NULL)
  }
  if (!is.list(execution_binding)) {
    stop(contract_error("execution_binding must be an object for v1.2 tasks"))
  }
  validate_registered_result_contract(execution_binding)
  if (!identical(task$execution_mode, "FORMAL")) {
    return(execution_binding)
  }
  categorical_gcomp_validate_formal_execution_binding(execution_binding)
  required <- c(
    "schema_version",
    "task_id",
    "task_sha256",
    "authorization_id",
    "authorization_sha256",
    "candidate_id"
  )
  problems <- character()
  if (!is.list(execution_binding)) {
    problems <- c(problems, "execution_binding must be an object for FORMAL v1.2 tasks")
  } else {
    problems <- c(
      problems,
      categorical_gcomp_exact_names(
        execution_binding,
        required,
        "execution_binding"
      )
    )
    if (!identical(execution_binding$task_id, task$task_id)) {
      problems <- c(problems, "execution_binding.task_id must match task.task_id")
    }
    if (!categorical_gcomp_is_prefixed_sha256(execution_binding$task_sha256)) {
      problems <- c(problems, "execution_binding.task_sha256 must be prefixed SHA-256")
    }
    if (!categorical_gcomp_scalar_string(execution_binding$authorization_id)) {
      problems <- c(problems, "execution_binding.authorization_id must be one non-empty string")
    }
    if (!categorical_gcomp_is_prefixed_sha256(execution_binding$authorization_sha256)) {
      problems <- c(problems, "execution_binding.authorization_sha256 must be prefixed SHA-256")
    }
    if (!identical(execution_binding$candidate_id, task$binding$candidate_id)) {
      problems <- c(problems, "execution_binding.candidate_id must match task.binding$candidate_id")
    }
    if (is.null(task$binding$formal_authorization)) {
      problems <- c(problems, "formal task requires task.binding$formal_authorization")
    } else if (!identical(
      execution_binding$authorization_id,
      task$binding$formal_authorization$reference
    )) {
      problems <- c(
        problems,
        "execution_binding.authorization_id must match task.binding$formal_authorization$reference"
      )
    }
  }
  if (length(problems)) stop(contract_error(unique(problems[nzchar(problems)])))
  execution_binding
}

categorical_gcomp_validate_formal_execution_binding <- function(execution_binding) {
  required <- c(
    "schema_version",
    "task_id",
    "task_sha256",
    "authorization_id",
    "authorization_sha256",
    "candidate_id"
  )
  problems <- character()
  if (!is.list(execution_binding)) {
    problems <- c(problems, "execution_binding must be an object")
  } else {
    problems <- c(
      problems,
      categorical_gcomp_exact_names(
        execution_binding,
        required,
        "execution_binding"
      )
    )
    if (!identical(
      execution_binding$schema_version,
      "categorical-gcomp-formal-execution-binding@1.0.0"
    )) {
      problems <- c(
        problems,
        "execution_binding.schema_version must be categorical-gcomp-formal-execution-binding@1.0.0"
      )
    }
    if (!categorical_gcomp_scalar_string(execution_binding$task_id)) {
      problems <- c(problems, "execution_binding.task_id must be one non-empty string")
    }
    if (!categorical_gcomp_is_prefixed_sha256(execution_binding$task_sha256)) {
      problems <- c(problems, "execution_binding.task_sha256 must be prefixed SHA-256")
    }
    if (!categorical_gcomp_scalar_string(execution_binding$authorization_id)) {
      problems <- c(problems, "execution_binding.authorization_id must be one non-empty string")
    }
    if (!categorical_gcomp_is_prefixed_sha256(execution_binding$authorization_sha256)) {
      problems <- c(problems, "execution_binding.authorization_sha256 must be prefixed SHA-256")
    }
    if (!categorical_gcomp_scalar_string(execution_binding$candidate_id)) {
      problems <- c(problems, "execution_binding.candidate_id must be one non-empty string")
    }
  }
  if (length(problems)) stop(contract_error(unique(problems[nzchar(problems)])))
  execution_binding
}

validate_categorical_gcomp_formal_execution_binding <- categorical_gcomp_validate_formal_execution_binding

categorical_gcomp_full_output_ids <- function() {
  .categorical_gcomp_full_output_ids
}

categorical_gcomp_failure <- function(code, stage) {
  if (!(code %in% .categorical_gcomp_failure_codes)) code <- "INTERNAL_ERROR"
  structure(
    list(message = code, code = code, stage = stage),
    class = c("categorical_gcomp_failure", "error", "condition")
  )
}

categorical_gcomp_stop <- function(code, stage) {
  stop(categorical_gcomp_failure(code, stage))
}

categorical_gcomp_exact_names <- function(value, expected, label) {
  if (!is.list(value) || is.data.frame(value) ||
      is.null(names(value)) || any(!nzchar(names(value))) ||
      anyDuplicated(names(value)) || !identical(names(value), expected)) {
    return(sprintf("%s has missing, unknown, or reordered fields", label))
  }
  character()
}

categorical_gcomp_scalar_string <- function(x) {
  is.character(x) && length(x) == 1L && !is.na(x) && nzchar(x)
}

categorical_gcomp_scalar_logical <- function(x) {
  is.logical(x) && length(x) == 1L && !is.na(x)
}

categorical_gcomp_sha256 <- function(x) {
  categorical_gcomp_scalar_string(x) && grepl("^[a-f0-9]{64}$", x)
}

categorical_gcomp_sha256_prefixed <- function(x) {
  categorical_gcomp_scalar_string(x) && grepl("^sha256:[a-f0-9]{64}$", x)
}

categorical_gcomp_sequence <- function(x) {
  if (is.list(x)) {
    if (!is.null(names(x)) && any(nzchar(names(x)))) return(NULL)
    if (!length(x)) return(character())
    return(unlist(x, use.names = FALSE))
  }
  if (is.atomic(x) && is.null(dim(x))) return(unname(x))
  NULL
}

categorical_gcomp_forbidden_payload <- function(value, trail = "task") {
  problems <- character()
  if (!is.list(value)) {
    if (is.character(value) && any(grepl("^(~?/|[A-Za-z]:[/\\\\])", value))) {
      problems <- c(problems, sprintf("physical path forbidden at %s", trail))
    }
    return(problems)
  }
  forbidden <- c(
    "path", "physical_path", "subject_id", "hadm_id", "stay_id",
    "raw_timestamp", "rows", "records", "traceback", "exception"
  )
  bad <- intersect(names(value), forbidden)
  if (length(bad)) {
    problems <- c(
      problems,
      sprintf("forbidden shared field at %s: %s", trail, paste(bad, collapse = ", "))
    )
  }
  for (name in names(value)) {
    problems <- c(
      problems,
      categorical_gcomp_forbidden_payload(value[[name]], paste0(trail, ".", name))
    )
  }
  problems
}

categorical_gcomp_expected_formula <- function(analysis) {
  paste(
    analysis$outcome,
    "~",
    paste(c(analysis$exposure, categorical_gcomp_sequence(analysis$covariates)), collapse = " + ")
  )
}

# Strict, candidate-neutral operational task contract for categorical source
# standardization. Candidate and checksum values are runtime bindings rather
# than constants in the implementation.
validate_categorical_gcomp_task <- function(task) {
  is_full_task_schema <- identical(task$schema_version, .categorical_gcomp_full_task_version)
  full_profile <- is_full_task_schema && categorical_gcomp_is_full_article_target(task)
  checksum_checker <- if (
    identical(task$schema_version, "categorical-transfer-gcomp-task@1.2.0")
  ) {
    categorical_gcomp_sha256_prefixed
  } else {
    categorical_gcomp_sha256
  }
  task_fields <- c(
    "schema_version", "task_id", "analysis_id", "execution_mode",
    "source_module_id", "target_module_id", "authority", "binding",
    "data", "analysis", "outputs"
  )
  if (full_profile) task_fields <- c(task_fields, "tfl")
  problems <- categorical_gcomp_exact_names(task, task_fields, "task")
  if (!(task$schema_version %in% .categorical_gcomp_task_versions)) {
    problems <- c(problems, "unsupported categorical g-computation task schema")
  }
  for (field in c("task_id", "analysis_id")) {
    if (!categorical_gcomp_scalar_string(task[[field]])) {
      problems <- c(problems, sprintf("%s must be one non-empty string", field))
    }
  }
  if (!(task$execution_mode %in% c("SYNTHETIC_TEST", "FORMAL"))) {
    problems <- c(problems, "execution_mode must be SYNTHETIC_TEST or FORMAL")
  }
  if (!identical(task$source_module_id, "research-topic-module") ||
      !identical(task$target_module_id, "clinical-analysis-module")) {
    problems <- c(problems, "logical module routing mismatch")
  }
  problems <- c(problems, categorical_gcomp_forbidden_payload(task))

  problems <- c(problems, categorical_gcomp_exact_names(
    task$authority,
    c(
      "sap_frozen", "task_issued", "materialization_authorized",
      "formal_execution_authorized"
    ),
    "authority"
  ))
  if (is.list(task$authority)) {
    for (field in c(
      "sap_frozen", "task_issued", "materialization_authorized",
      "formal_execution_authorized"
    )) {
      if (!categorical_gcomp_scalar_logical(task$authority[[field]])) {
        problems <- c(problems, sprintf("authority.%s must be boolean", field))
      }
    }
  }

  binding_fields <- c(
    "candidate_id", "candidate_sha256", "sap_id", "sap_sha256",
    "capability_contract_id", "capability_contract_sha256",
    "formal_authorization"
  )
  if (full_profile) binding_fields <- c(binding_fields, "value_set_id", "value_set_sha256")
  problems <- c(problems, categorical_gcomp_exact_names(
    task$binding,
    binding_fields,
    "binding"
  ))
  if (is.list(task$binding)) {
    for (field in c("candidate_id", "sap_id", "capability_contract_id")) {
      if (!categorical_gcomp_scalar_string(task$binding[[field]])) {
        problems <- c(problems, sprintf("binding.%s must be one non-empty string", field))
      }
    }
    for (field in c(
      "candidate_sha256", "sap_sha256", "capability_contract_sha256"
    )) {
      if (!checksum_checker(task$binding[[field]])) {
        problems <- c(problems, sprintf("binding.%s must be lowercase SHA-256", field))
      }
    }
    if (full_profile && !categorical_gcomp_sha256_prefixed(task$binding$value_set_sha256)) {
      problems <- c(
        problems,
        "binding.value_set_sha256 must be a prefixed lowercase SHA-256"
      )
    }
    if (full_profile && !categorical_gcomp_scalar_string(task$binding$value_set_id)) {
      problems <- c(problems, "binding.value_set_id must be one non-empty string")
    }
  }

  problems <- c(problems, categorical_gcomp_exact_names(
    task$data,
    c("dataset_id", "sha256", "dataset_tag"),
    "data"
  ))
  if (is.list(task$data)) {
    if (!categorical_gcomp_scalar_string(task$data$dataset_id)) {
      problems <- c(problems, "data.dataset_id must be one non-empty logical id")
    }
    if (!checksum_checker(task$data$sha256)) {
      problems <- c(problems, "data.sha256 must be lowercase SHA-256")
    }
    if (!categorical_gcomp_scalar_string(task$data$dataset_tag)) {
      problems <- c(problems, "data.dataset_tag must be one non-empty string")
    }
  }

  a <- task$analysis
  analysis_fields <- c(
    "method", "record_id", "outcome", "exposure", "exposure_levels",
    "reference", "covariates", "binary_covariates",
    "sensitivity_source_field", "first_event", "first_event_levels",
    "first_event_tie_priority", "formula", "family", "link", "estimator",
    "variance_method", "standardization", "draw_distribution", "draw_count",
    "seed", "interval_method", "confidence_level", "complete_case",
    "sensitivity_ids", "expected_output_ids"
  )
  if (full_profile) analysis_fields <- c(
    analysis_fields,
    "full_article_target_id",
    "full_article_profile_checksum",
    "planned_display_contract_id",
    "planned_display_contract_sha256",
    "prior_result_exposure",
    "confirmatory_claim_allowed"
  )
  problems <- c(problems, categorical_gcomp_exact_names(a, analysis_fields, "analysis"))
  if (is.list(a)) {
    scalar_fields <- c(
      "record_id", "outcome", "exposure", "reference",
      "sensitivity_source_field", "first_event", "formula"
    )
    for (field in scalar_fields) {
      if (!categorical_gcomp_scalar_string(a[[field]])) {
        problems <- c(problems, sprintf("analysis.%s must be one non-empty string", field))
      }
    }
    exposure_levels <- categorical_gcomp_sequence(a$exposure_levels)
    covariates <- categorical_gcomp_sequence(a$covariates)
    binary_covariates <- categorical_gcomp_sequence(a$binary_covariates)
    first_event_levels <- categorical_gcomp_sequence(a$first_event_levels)
    tie_priority <- categorical_gcomp_sequence(a$first_event_tie_priority)
    sensitivities <- categorical_gcomp_sequence(a$sensitivity_ids)
    expected_outputs <- categorical_gcomp_sequence(a$expected_output_ids)
    if (!identical(a$method, .categorical_gcomp_method)) {
      problems <- c(problems, "method substitution is forbidden")
    }
    if (is.null(exposure_levels) || length(exposure_levels) < 2L ||
        any(!nzchar(exposure_levels)) || anyDuplicated(exposure_levels)) {
      problems <- c(problems, "exposure_levels must contain unique non-empty levels")
    } else if (!(a$reference %in% exposure_levels)) {
      problems <- c(problems, "reference must be declared in exposure_levels")
    }
    if (is.null(covariates) || !length(covariates) ||
        any(!nzchar(covariates)) || anyDuplicated(covariates)) {
      problems <- c(problems, "covariates must be a unique non-empty sequence")
    }
    if (is.null(binary_covariates) ||
        length(setdiff(binary_covariates, covariates))) {
      problems <- c(problems, "binary_covariates must be a subset of covariates")
    }
    if (is.null(first_event_levels) ||
        !identical(first_event_levels[[1L]], "NO_EVENT") ||
        anyDuplicated(first_event_levels)) {
      problems <- c(problems, "first_event_levels must start with NO_EVENT and be unique")
    }
    if (is.null(tie_priority) ||
        !identical(tie_priority, setdiff(first_event_levels, "NO_EVENT"))) {
      problems <- c(problems, "first_event_tie_priority must exactly order event components")
    }
    if (!identical(a$formula, categorical_gcomp_expected_formula(a))) {
      problems <- c(problems, "formula does not match the frozen outcome, exposure, and covariates")
    }
    frozen_method <- list(
      family = "binomial",
      link = "logit",
      estimator = "maximum_likelihood",
      variance_method = "HC0",
      standardization = "ALL_COMPLETE_CASE_ROWS_PAIRED",
      draw_distribution = "MULTIVARIATE_NORMAL_ROBUST_COEFFICIENTS",
      interval_method = "PERCENTILE_95",
      complete_case = TRUE
    )
    for (field in names(frozen_method)) {
      if (!identical(a[[field]], frozen_method[[field]])) {
        problems <- c(problems, sprintf("analysis.%s semantic drift", field))
      }
    }
    if (!is.numeric(a$draw_count) || length(a$draw_count) != 1L ||
        a$draw_count != 2000) {
      problems <- c(problems, "draw_count must remain 2000")
    }
    if (!is.numeric(a$seed) || length(a$seed) != 1L ||
        a$seed != .categorical_gcomp_seed) {
      problems <- c(problems, "seed must remain 80320260724")
    }
    if (!is.numeric(a$confidence_level) || length(a$confidence_level) != 1L ||
        a$confidence_level != 0.95) {
      problems <- c(problems, "confidence_level must remain 0.95")
    }
    if (!identical(sensitivities, .categorical_gcomp_sensitivity_ids)) {
      problems <- c(problems, "exactly the two registered sensitivities are required")
    }
    expected_output_spec <- if (full_profile) .categorical_gcomp_full_output_ids else .categorical_gcomp_output_ids
    if (!identical(expected_outputs, expected_output_spec)) {
      problems <- c(problems, "expected_output_ids mismatch")
    }
    if (full_profile && !isTRUE(a$full_article_target_id %in% .categorical_gcomp_full_article_target_id)) {
      problems <- c(problems, "analysis.full_article_target_id must match the registered full article target")
    }
    if (full_profile && !identical(a$full_article_profile_checksum, .categorical_gcomp_full_article_profile_checksum)) {
      problems <- c(problems, "analysis.full_article_profile_checksum must match full article profile checksum")
    }
    if (full_profile && !categorical_gcomp_safe_basename(a$planned_display_contract_id)) {
      problems <- c(problems, "analysis.planned_display_contract_id must be a safe logical id")
    }
    if (full_profile && !categorical_gcomp_sha256_prefixed(a$planned_display_contract_sha256)) {
      problems <- c(problems, "analysis.planned_display_contract_sha256 must be sha256 prefixed")
    }
    if (full_profile && !categorical_gcomp_scalar_logical(a$prior_result_exposure)) {
      problems <- c(problems, "analysis.prior_result_exposure must be a logical value")
    }
    if (full_profile && !categorical_gcomp_scalar_logical(a$confirmatory_claim_allowed)) {
      problems <- c(problems, "analysis.confirmatory_claim_allowed must be a logical value")
    }
    if (full_profile &&
        isTRUE(a$prior_result_exposure) &&
        isTRUE(a$confirmatory_claim_allowed)) {
      problems <- c(problems, "analysis.confirmatory_claim_allowed must be false when prior_result_exposure is true")
    }
    if (!full_profile && !is.null(a$full_article_target_id)) {
      problems <- c(problems, "analysis.full_article_target_id is unsupported without a full article target")
    }
    if (is_full_task_schema && !full_profile) {
      problems <- c(problems, "categorical-transfer-gcomp-task@1.2.0 requires a registered full article target")
    }
    if (!is_full_task_schema && (
      is.character(a$full_article_target_id) ||
      is.character(a$full_article_profile_checksum) ||
      is.character(a$planned_display_contract_id) ||
      is.character(a$planned_display_contract_sha256) ||
      !is.null(a$prior_result_exposure) ||
      !is.null(a$confirmatory_claim_allowed)
    )) {
      problems <- c(problems, "full article fields are unsupported for pre-1.2 task schema")
    }
  }

  problems <- c(problems, categorical_gcomp_exact_names(
    task$outputs,
    c(
      "aggregate_only", "patient_level_output", "physical_paths_in_output",
      "validate_complete_bundle_before_write"
    ),
    "outputs"
  ))
  if (!identical(
    task$outputs,
    list(
      aggregate_only = TRUE,
      patient_level_output = FALSE,
      physical_paths_in_output = FALSE,
      validate_complete_bundle_before_write = TRUE
    )
  )) {
    problems <- c(problems, "outputs must remain aggregate-only, path-free, and prewrite-validated")
  }
  if (!full_profile && !is.null(task$tfl)) {
    problems <- c(problems, "tfl is unsupported without a full article target")
  }
  if (full_profile) {
    table1 <- task$tfl %||% list()
    if (!is.list(table1) || !is.list(table1$table1)) {
      problems <- c(problems, "full article target requires task.tfl$table1 with enabled=TRUE, group, and variables")
    }
  }

  if (identical(task$execution_mode, "SYNTHETIC_TEST")) {
    if (!identical(task$data$dataset_tag, "SYNTHETIC_TEST")) {
      problems <- c(problems, "SYNTHETIC_TEST requires dataset_tag=SYNTHETIC_TEST")
    }
    if (any(vapply(task$authority, isTRUE, logical(1)))) {
      problems <- c(problems, "SYNTHETIC_TEST cannot claim task, materialization, or FORMAL authority")
    }
    if (!is.null(task$binding$formal_authorization)) {
      problems <- c(problems, "SYNTHETIC_TEST cannot carry FORMAL authorization")
    }
  }
  if (identical(task$execution_mode, "FORMAL")) {
    if (identical(task$data$dataset_tag, "SYNTHETIC_TEST")) {
      problems <- c(problems, "FORMAL cannot use a synthetic dataset tag")
    }
    if (!all(vapply(task$authority, isTRUE, logical(1)))) {
      problems <- c(problems, "FORMAL requires frozen SAP, issued task, materialization, and execution authority")
    }
    auth <- task$binding$formal_authorization
    auth_fields <- c(
      "reference", "scope", "candidate_id", "sap_sha256", "dataset_sha256"
    )
    problems <- c(problems, categorical_gcomp_exact_names(auth, auth_fields, "formal_authorization"))
    if (is.list(auth)) {
      if (!checksum_checker(auth$sap_sha256) ||
          !checksum_checker(auth$dataset_sha256)) {
        problems <- c(problems, "formal_authorization checksums must match task contract version")
      }
      if (!identical(auth$scope, "FORMAL_ANALYSIS_EXECUTION") ||
          !identical(auth$candidate_id, task$binding$candidate_id) ||
          !identical(auth$sap_sha256, task$binding$sap_sha256) ||
          !identical(auth$dataset_sha256, task$data$sha256) ||
          !categorical_gcomp_scalar_string(auth$reference)) {
        problems <- c(problems, "FORMAL authorization binding mismatch")
      }
    }
  }
  if (length(problems)) stop(contract_error(unique(problems[nzchar(problems)])))
  invisible(TRUE)
}

categorical_gcomp_required_columns <- function(task) {
  unique(c(
    task$analysis$record_id,
    task$analysis$outcome,
    task$analysis$exposure,
    task$analysis$sensitivity_source_field,
    task$analysis$first_event,
    categorical_gcomp_sequence(task$analysis$covariates)
  ))
}

categorical_gcomp_validate_data <- function(task, data) {
  if (!is.data.frame(data)) categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "DATA_SEMANTICS")
  required <- categorical_gcomp_required_columns(task)
  if (length(setdiff(required, names(data)))) {
    categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "DATA_SEMANTICS")
  }
  id <- data[[task$analysis$record_id]]
  if (anyNA(id) || anyDuplicated(id)) {
    categorical_gcomp_stop("DUPLICATE_RECORD_ID", "DATA_SEMANTICS")
  }
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  primary <- as.character(data[[task$analysis$exposure]])
  if (anyNA(primary) || any(!nzchar(primary)) ||
      length(setdiff(unique(primary), levels))) {
    categorical_gcomp_stop("UNKNOWN_SOURCE_VALUE", "DATA_SEMANTICS")
  }
  sensitivity <- as.character(data[[task$analysis$sensitivity_source_field]])
  sensitivity_nonmissing <- sensitivity[!is.na(sensitivity)]
  sensitivity_invalid <- any(!nzchar(sensitivity_nonmissing)) ||
    length(setdiff(unique(sensitivity_nonmissing), levels))
  if (identical(
        task$schema_version,
        "categorical-transfer-gcomp-task@1.0.0"
      ) && anyNA(sensitivity)) {
    sensitivity_invalid <- TRUE
  }
  if (sensitivity_invalid) {
    categorical_gcomp_stop("UNKNOWN_SOURCE_VALUE", "DATA_SEMANTICS")
  }
  outcome <- data[[task$analysis$outcome]]
  if (anyNA(outcome) || !all(outcome %in% c(0, 1))) {
    categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "DATA_SEMANTICS")
  }
  event <- as.character(data[[task$analysis$first_event]])
  event_levels <- categorical_gcomp_sequence(task$analysis$first_event_levels)
  if (anyNA(event) || length(setdiff(unique(event), event_levels)) ||
      any((outcome == 0) != (event == "NO_EVENT"))) {
    categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "DATA_SEMANTICS")
  }
  covariates <- categorical_gcomp_sequence(task$analysis$covariates)
  binaries <- categorical_gcomp_sequence(task$analysis$binary_covariates)
  for (field in covariates) {
    value <- data[[field]]
    if (!is.numeric(value) || any(!is.finite(value[!is.na(value)]))) {
      categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "DATA_SEMANTICS")
    }
    if (field %in% binaries && any(!(value[!is.na(value)] %in% c(0, 1)))) {
      categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "DATA_SEMANTICS")
    }
  }
  invisible(TRUE)
}

categorical_gcomp_population_counts <- function(task, data) {
  categorical_gcomp_validate_data(task, data)
  primary_fields <- c(
    task$analysis$outcome,
    task$analysis$exposure,
    categorical_gcomp_sequence(task$analysis$covariates)
  )
  primary_eligible <- stats::complete.cases(data[, primary_fields, drop = FALSE])
  sensitivity <- as.character(data[[task$analysis$sensitivity_source_field]])
  sensitivity_nonmissing <- sensitivity[!is.na(sensitivity)]
  s1_eligible <- primary_eligible & !is.na(sensitivity)
  primary_source <- as.character(data[[task$analysis$exposure]])
  s2_eligible <- primary_eligible & primary_source != "OTHER_ICU"
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  list(
    input_n = as.integer(nrow(data)),
    primary_analysis_n = as.integer(sum(primary_eligible)),
    s1_analysis_n = as.integer(sum(s1_eligible)),
    s2_analysis_n = as.integer(sum(s2_eligible)),
    s1_missing_source_excluded_n =
      as.integer(sum(primary_eligible & is.na(sensitivity))),
    s1_unknown_nonmissing_n =
      as.integer(sum(!is.na(sensitivity) & !(sensitivity %in% levels))),
    primary_source_missing_n = as.integer(sum(is.na(primary_source))),
    primary_source_unknown_nonmissing_n =
      as.integer(sum(!is.na(primary_source) & !(primary_source %in% levels))),
    primary_observed_levels =
      as.list(levels[levels %in% unique(primary_source)]),
    s1_observed_nonmissing_levels =
      as.list(levels[levels %in% unique(sensitivity_nonmissing)]),
    model_entry_reached = FALSE,
    attempts_started = 0L
  )
}

categorical_gcomp_wilson <- function(events, n, confidence_level = 0.95) {
  if (n == 0L) return(c(estimate = NA_real_, low = NA_real_, high = NA_real_))
  z <- stats::qnorm(1 - (1 - confidence_level) / 2)
  p <- events / n
  denominator <- 1 + z^2 / n
  center <- (p + z^2 / (2 * n)) / denominator
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / denominator
  c(estimate = p, low = max(0, center - half), high = min(1, center + half))
}

categorical_gcomp_unadjusted <- function(task, data) {
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  outcome <- data[[task$analysis$outcome]]
  source <- as.character(data[[task$analysis$exposure]])
  rows <- lapply(levels, function(level) {
    keep <- source == level
    n <- sum(keep)
    events <- sum(outcome[keep])
    interval <- categorical_gcomp_wilson(events, n, task$analysis$confidence_level)
    list(
      source = level,
      status = if (n) "ESTIMATED" else "NOT_ESTIMABLE_EMPTY_SOURCE",
      n = as.integer(n),
      events = as.integer(events),
      risk = if (n) unname(interval[["estimate"]]) else NULL,
      risk_ci_low = if (n) unname(interval[["low"]]) else NULL,
      risk_ci_high = if (n) unname(interval[["high"]]) else NULL,
      confidence_level = task$analysis$confidence_level,
      interval_method = "WILSON_SCORE"
    )
  })
  list(
    schema_version = "categorical-gcomp-unadjusted-source-risks@1.0.0",
    rows = rows
  )
}

categorical_gcomp_complete_rows <- function(task, data, source_field) {
  fields <- c(
    task$analysis$outcome,
    source_field,
    categorical_gcomp_sequence(task$analysis$covariates)
  )
  stats::complete.cases(data[, fields, drop = FALSE])
}

categorical_gcomp_prepare_model_data <- function(task, data, source_field) {
  keep <- categorical_gcomp_complete_rows(task, data, source_field)
  model_data <- data[keep, , drop = FALSE]
  observed <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  observed <- observed[observed %in% as.character(model_data[[source_field]])]
  if (!(task$analysis$reference %in% observed)) {
    categorical_gcomp_stop("MISSING_REFERENCE_SUPPORT", "PRIMARY_FIT")
  }
  ordered_levels <- c(task$analysis$reference, setdiff(observed, task$analysis$reference))
  prepared <- data.frame(
    .outcome = model_data[[task$analysis$outcome]],
    .source = factor(as.character(model_data[[source_field]]), levels = ordered_levels),
    check.names = FALSE
  )
  for (field in categorical_gcomp_sequence(task$analysis$covariates)) {
    prepared[[field]] <- model_data[[field]]
  }
  list(
    keep = keep,
    raw = model_data,
    prepared = prepared,
    observed = observed,
    empty = setdiff(categorical_gcomp_sequence(task$analysis$exposure_levels), observed)
  )
}

categorical_gcomp_validate_fit <- function(fit) {
  if (!isTRUE(fit$converged)) {
    categorical_gcomp_stop("MODEL_NONCONVERGENCE", "PRIMARY_FIT")
  }
  beta <- stats::coef(fit)
  if (!length(beta) || any(!is.finite(beta))) {
    categorical_gcomp_stop("NONFINITE_ESTIMATE", "PRIMARY_FIT")
  }
  invisible(TRUE)
}

categorical_gcomp_validate_covariance <- function(covariance) {
  if (!is.matrix(covariance) || nrow(covariance) != ncol(covariance) ||
      !nrow(covariance) || any(!is.finite(covariance))) {
    categorical_gcomp_stop("INVALID_COVARIANCE", "PRIMARY_FIT")
  }
  covariance <- (covariance + t(covariance)) / 2
  eig <- eigen(covariance, symmetric = TRUE)
  tolerance <- 1e-8 * max(1, max(abs(eig$values)))
  if (min(eig$values) < -tolerance) {
    categorical_gcomp_stop("INVALID_COVARIANCE", "PRIMARY_FIT")
  }
  list(
    covariance = covariance,
    values = pmax(eig$values, 0),
    vectors = eig$vectors,
    tolerance = tolerance
  )
}

categorical_gcomp_effective_seed <- function(seed) {
  effective <- seed %% .Machine$integer.max
  if (effective == 0) effective <- 1
  as.integer(effective)
}

categorical_gcomp_coefficient_draws <- function(beta, covariance, draw_count, seed) {
  decomp <- categorical_gcomp_validate_covariance(covariance)
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
  RNGkind("Mersenne-Twister", "Inversion", "Rejection")
  set.seed(categorical_gcomp_effective_seed(seed))
  z <- matrix(stats::rnorm(draw_count * length(beta)), nrow = draw_count)
  root <- decomp$vectors %*% diag(sqrt(decomp$values), nrow = length(beta))
  sweep(z %*% t(root), 2L, beta, "+")
}

categorical_gcomp_counterfactual_matrix <- function(fit, prepared, source) {
  counterfactual <- prepared
  counterfactual$.source <- factor(
    rep(source, nrow(prepared)),
    levels = levels(prepared$.source)
  )
  matrix <- stats::model.matrix(stats::delete.response(stats::terms(fit)), counterfactual)
  matrix[, names(stats::coef(fit)), drop = FALSE]
}

categorical_gcomp_draw_risks <- function(matrix, draws, chunk_size = 100L) {
  output <- numeric(nrow(draws))
  starts <- seq.int(1L, nrow(draws), by = chunk_size)
  for (start in starts) {
    end <- min(nrow(draws), start + chunk_size - 1L)
    linear <- matrix %*% t(draws[start:end, , drop = FALSE])
    output[start:end] <- colMeans(stats::plogis(linear))
  }
  if (any(!is.finite(output))) {
    categorical_gcomp_stop("NONFINITE_PREDICTION", "STANDARDIZATION")
  }
  output
}

categorical_gcomp_fit <- function(task, data, source_field, stage = "PRIMARY_FIT") {
  prepared <- categorical_gcomp_prepare_model_data(task, data, source_field)
  covariates <- categorical_gcomp_sequence(task$analysis$covariates)
  formula <- stats::reformulate(c(".source", covariates), response = ".outcome")
  fit <- tryCatch(
    stats::glm(formula, data = prepared$prepared, family = stats::binomial(link = "logit")),
    error = function(e) categorical_gcomp_stop("MODEL_NONCONVERGENCE", stage)
  )
  categorical_gcomp_validate_fit(fit)
  covariance <- tryCatch(
    sandwich::vcovHC(fit, type = "HC0"),
    error = function(e) categorical_gcomp_stop("INVALID_COVARIANCE", stage)
  )
  categorical_gcomp_validate_covariance(covariance)
  beta <- stats::coef(fit)
  draws <- categorical_gcomp_coefficient_draws(
    beta,
    covariance,
    task$analysis$draw_count,
    task$analysis$seed
  )
  source_draw_risks <- list()
  point_risks <- list()
  for (source in prepared$observed) {
    matrix <- categorical_gcomp_counterfactual_matrix(fit, prepared$prepared, source)
    point <- mean(stats::plogis(drop(matrix %*% beta)))
    if (!is.finite(point)) categorical_gcomp_stop("NONFINITE_PREDICTION", stage)
    point_risks[[source]] <- point
    source_draw_risks[[source]] <- categorical_gcomp_draw_risks(matrix, draws)
  }
  list(
    fit = fit,
    covariance = covariance,
    beta = beta,
    complete_case_n = nrow(prepared$prepared),
    complete_rows = prepared$keep,
    observed = prepared$observed,
    empty = prepared$empty,
    point_risks = point_risks,
    draw_risks = source_draw_risks,
    source_counts = as.list(stats::setNames(
      as.integer(table(factor(
        as.character(prepared$raw[[source_field]]),
        levels = categorical_gcomp_sequence(task$analysis$exposure_levels)
      ))),
      categorical_gcomp_sequence(task$analysis$exposure_levels)
    )),
    converged = isTRUE(fit$converged),
    finite = all(is.finite(beta)) && all(is.finite(covariance)),
    covariance_valid = TRUE
  )
}

categorical_gcomp_adjusted_rows <- function(task, fit_result) {
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  reference <- task$analysis$reference
  reference_draws <- fit_result$draw_risks[[reference]]
  lapply(levels, function(source) {
    if (!(source %in% fit_result$observed)) {
      return(list(
        source = source,
        reference = reference,
        status = "NOT_ESTIMABLE_EMPTY_SOURCE",
        analysis_n = as.integer(fit_result$complete_case_n),
        standardized_risk = NULL,
        risk_ci_low = NULL,
        risk_ci_high = NULL,
        risk_difference = NULL,
        risk_difference_ci_low = NULL,
        risk_difference_ci_high = NULL,
        variance_method = "HC0",
        draw_count = as.integer(task$analysis$draw_count),
        seed = task$analysis$seed
      ))
    }
    source_draws <- fit_result$draw_risks[[source]]
    risk_interval <- stats::quantile(source_draws, c(0.025, 0.975), names = FALSE, type = 7)
    difference_draws <- source_draws - reference_draws
    difference_interval <- stats::quantile(
      difference_draws, c(0.025, 0.975), names = FALSE, type = 7
    )
    list(
      source = source,
      reference = reference,
      status = "ESTIMATED",
      analysis_n = as.integer(fit_result$complete_case_n),
      standardized_risk = unname(fit_result$point_risks[[source]]),
      risk_ci_low = unname(risk_interval[[1L]]),
      risk_ci_high = unname(risk_interval[[2L]]),
      risk_difference = unname(
        fit_result$point_risks[[source]] - fit_result$point_risks[[reference]]
      ),
      risk_difference_ci_low = unname(difference_interval[[1L]]),
      risk_difference_ci_high = unname(difference_interval[[2L]]),
      variance_method = "HC0",
      draw_count = as.integer(task$analysis$draw_count),
      seed = task$analysis$seed
    )
  })
}

categorical_gcomp_adjusted <- function(task, fit_result) {
  list(
    schema_version = "categorical-gcomp-adjusted-risks@1.0.0",
    rows = categorical_gcomp_adjusted_rows(task, fit_result)
  )
}

categorical_gcomp_resolve_first_event <- function(data, time_fields, tie_priority) {
  if (!is.list(time_fields) || !identical(names(time_fields), tie_priority) ||
      length(setdiff(unlist(time_fields, use.names = FALSE), names(data)))) {
    categorical_gcomp_stop("DATA_SEMANTICS_INVALID", "FIRST_EVENT")
  }
  vapply(seq_len(nrow(data)), function(i) {
    times <- vapply(
      unlist(time_fields, use.names = FALSE),
      function(field) data[[field]][[i]],
      numeric(1)
    )
    finite <- is.finite(times)
    if (!any(finite)) return("NO_EVENT")
    minimum <- min(times[finite])
    tie_priority[which(finite & times == minimum)[[1L]]]
  }, character(1))
}

categorical_gcomp_first_event <- function(task, data) {
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  components <- categorical_gcomp_sequence(task$analysis$first_event_tie_priority)
  source <- as.character(data[[task$analysis$exposure]])
  outcome <- data[[task$analysis$outcome]]
  first_event <- as.character(data[[task$analysis$first_event]])
  rows <- unlist(lapply(levels, function(level) {
    source_rows <- source == level
    all_n <- sum(source_rows)
    event_n <- sum(source_rows & outcome == 1)
    lapply(components, function(component) {
      count <- sum(source_rows & outcome == 1 & first_event == component)
      interval <- categorical_gcomp_wilson(
        count, event_n, task$analysis$confidence_level
      )
      status <- if (!all_n) {
        "NOT_ESTIMABLE_EMPTY_SOURCE"
      } else if (!event_n) {
        "NOT_ESTIMABLE_NO_COMPOSITE_EVENTS"
      } else {
        "ESTIMATED"
      }
      list(
        source = level,
        first_event = component,
        status = status,
        count = as.integer(count),
        source_composite_event_denominator = as.integer(event_n),
        source_all_row_denominator = as.integer(all_n),
        proportion = if (event_n) unname(interval[["estimate"]]) else NULL,
        ci_low = if (event_n) unname(interval[["low"]]) else NULL,
        ci_high = if (event_n) unname(interval[["high"]]) else NULL,
        interval_method = "WILSON_SCORE"
      )
    })
  }), recursive = FALSE)
  list(
    schema_version = "categorical-gcomp-first-event-composition@1.0.0",
    rows = rows
  )
}

categorical_gcomp_risk_vectors <- function(task, fit_result) {
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  reference <- task$analysis$reference
  standardized <- stats::setNames(vector("list", length(levels)), levels)
  differences <- stats::setNames(vector("list", length(levels)), levels)
  for (source in fit_result$observed) {
    standardized[[source]] <- unname(fit_result$point_risks[[source]])
    differences[[source]] <- unname(
      fit_result$point_risks[[source]] - fit_result$point_risks[[reference]]
    )
  }
  list(standardized = standardized, differences = differences)
}

categorical_gcomp_credibility_assessment <- function(
    analysis_id,
    primary_risks,
    primary_differences,
    sensitivity_risks,
    sensitivity_differences,
    source_counts,
    n,
    converged = TRUE,
    finite = TRUE,
    noninformative_reason = NULL) {
  if (!is.null(noninformative_reason)) {
    return(list(
      analysis_id = analysis_id,
      status = "NON_INFORMATIVE_EMPTY_SOURCE",
      n = as.integer(n),
      source_counts = source_counts,
      converged = converged,
      finite = finite,
      standardized_risks = sensitivity_risks,
      risk_differences = sensitivity_differences,
      maximum_absolute_standardized_risk_change = NULL,
      risk_difference_sign_reversal = FALSE,
      threshold_assessment = "NOT_ASSESSED_NONINFORMATIVE",
      noninformative_reason = noninformative_reason
    ))
  }
  common_risks <- intersect(
    names(primary_risks)[vapply(primary_risks, is.numeric, logical(1))],
    names(sensitivity_risks)[vapply(sensitivity_risks, is.numeric, logical(1))]
  )
  risk_change <- if (length(common_risks)) {
    max(abs(
      unlist(sensitivity_risks[common_risks], use.names = FALSE) -
        unlist(primary_risks[common_risks], use.names = FALSE)
    ))
  } else {
    NA_real_
  }
  common_differences <- intersect(
    names(primary_differences)[vapply(primary_differences, is.numeric, logical(1))],
    names(sensitivity_differences)[vapply(sensitivity_differences, is.numeric, logical(1))]
  )
  reversal <- any(vapply(common_differences, function(source) {
    primary <- primary_differences[[source]]
    sensitivity <- sensitivity_differences[[source]]
    abs(primary) >= 0.02 && primary * sensitivity < 0
  }, logical(1)))
  threshold_failed <- !is.finite(risk_change) || risk_change > 0.05 || reversal
  list(
    analysis_id = analysis_id,
    status = if (threshold_failed) "TECHNICAL_THRESHOLD_FAILED" else "ESTIMATED",
    n = as.integer(n),
    source_counts = source_counts,
    converged = converged,
    finite = finite,
    standardized_risks = sensitivity_risks,
    risk_differences = sensitivity_differences,
    maximum_absolute_standardized_risk_change =
      if (is.finite(risk_change)) unname(risk_change) else NULL,
    risk_difference_sign_reversal = reversal,
    threshold_assessment = if (threshold_failed) "FAIL" else "PASS",
    noninformative_reason = NULL
  )
}

categorical_gcomp_credibility <- function(task, data, primary_fit) {
  primary <- categorical_gcomp_risk_vectors(task, primary_fit)
  sensitivity_source <- as.character(
    data[[task$analysis$sensitivity_source_field]]
  )
  s1_eligible <- primary_fit$complete_rows & !is.na(sensitivity_source)
  s1_data <- data[s1_eligible, , drop = FALSE]
  s1_fit <- categorical_gcomp_fit(
    task,
    s1_data,
    task$analysis$sensitivity_source_field,
    stage = "SENSITIVITY_1"
  )
  s1 <- categorical_gcomp_risk_vectors(task, s1_fit)
  s1_entry <- categorical_gcomp_credibility_assessment(
    "S1_RECENT_PRIOR_TRANSFER_1H",
    primary$standardized,
    primary$differences,
    s1$standardized,
    s1$differences,
    s1_fit$source_counts,
    s1_fit$complete_case_n,
    s1_fit$converged,
    s1_fit$finite
  )

  other_icu <- "OTHER_ICU"
  primary_other_n <- primary_fit$source_counts[[other_icu]] %||% 0L
  if (primary_other_n == 0L) {
    s2_entry <- categorical_gcomp_credibility_assessment(
      "S2_EXCLUDE_OTHER_ICU",
      primary$standardized,
      primary$differences,
      primary$standardized,
      primary$differences,
      primary_fit$source_counts,
      primary_fit$complete_case_n,
      primary_fit$converged,
      primary_fit$finite,
      "OTHER_ICU_EMPTY_IN_PRIMARY"
    )
  } else {
    restricted <- data[
      primary_fit$complete_rows &
        as.character(data[[task$analysis$exposure]]) != other_icu,
      ,
      drop = FALSE
    ]
    s2_fit <- categorical_gcomp_fit(
      task, restricted, task$analysis$exposure, stage = "SENSITIVITY_2"
    )
    s2 <- categorical_gcomp_risk_vectors(task, s2_fit)
    s2_entry <- categorical_gcomp_credibility_assessment(
      "S2_EXCLUDE_OTHER_ICU",
      primary$standardized,
      primary$differences,
      s2$standardized,
      s2$differences,
      s2_fit$source_counts,
      s2_fit$complete_case_n,
      s2_fit$converged,
      s2_fit$finite
    )
  }
  list(
    schema_version = "categorical-gcomp-credibility-results@1.0.0",
    rows = list(s1_entry, s2_entry)
  )
}

categorical_gcomp_cohort <- function(task, data, primary_fit) {
  fields <- setdiff(
    categorical_gcomp_required_columns(task),
    task$analysis$record_id
  )
  missingness <- as.list(stats::setNames(
    vapply(fields, function(field) as.integer(sum(is.na(data[[field]]))), integer(1)),
    fields
  ))
  source <- as.character(data[[task$analysis$exposure]])
  levels <- categorical_gcomp_sequence(task$analysis$exposure_levels)
  source_counts <- as.list(stats::setNames(
    as.integer(table(factor(source, levels = levels))),
    levels
  ))
  list(
    schema_version = "categorical-gcomp-cohort-flow@1.0.0",
    candidate_id = task$binding$candidate_id,
    dataset_id = task$data$dataset_id,
    dataset_sha256 = task$data$sha256,
    input_n = as.integer(nrow(data)),
    eligible_n = as.integer(nrow(data)),
    classified_n = as.integer(sum(!is.na(source))),
    source_counts = source_counts,
    unclassified_n = as.integer(sum(is.na(source))),
    conflicting_latest_source_n = 0L,
    model_complete_case_n = as.integer(primary_fit$complete_case_n),
    missingness_by_field = missingness
  )
}

categorical_gcomp_diagnostics <- function(task, primary_fit) {
  list(
    schema_version = "categorical-gcomp-diagnostics@1.0.0",
    formula = task$analysis$formula,
    reference = task$analysis$reference,
    analysis_n = as.integer(primary_fit$complete_case_n),
    model_parameters = as.integer(length(primary_fit$beta)),
    converged = primary_fit$converged,
    finite = primary_fit$finite,
    covariance_method = "HC0",
    covariance_valid = primary_fit$covariance_valid,
    observed_source_levels = as.list(primary_fit$observed),
    empty_source_levels = as.list(primary_fit$empty),
    failure_codes = list(),
    draw_count = as.integer(task$analysis$draw_count),
    requested_seed = task$analysis$seed,
    effective_r_seed = categorical_gcomp_effective_seed(task$analysis$seed),
    paired_contrasts = TRUE,
    separate_marginal_intervals_subtracted = FALSE
  )
}

categorical_gcomp_privacy_problems <- function(value, trail = "bundle") {
  problems <- character()
  if (!is.list(value)) {
    if (is.character(value) && any(grepl("^(~?/|[A-Za-z]:[/\\\\])", value))) {
      problems <- c(problems, sprintf("physical path at %s", trail))
    }
    return(problems)
  }
  forbidden <- c(
    "record_id", "subject_id", "hadm_id", "stay_id", "raw_timestamp",
    "physical_path", "path", "rows_raw", "traceback", "exception", "message"
  )
  bad <- intersect(names(value), forbidden)
  if (length(bad)) {
    problems <- c(problems, sprintf("forbidden key at %s: %s", trail, paste(bad, collapse = ", ")))
  }
  for (name in names(value)) {
    problems <- c(
      problems,
      categorical_gcomp_privacy_problems(value[[name]], paste0(trail, ".", name))
    )
  }
  problems
}

categorical_gcomp_validate_rows <- function(object, fields, label) {
  problems <- categorical_gcomp_exact_names(object, c("schema_version", "rows"), label)
  if (!is.list(object$rows) || is.data.frame(object$rows)) {
    return(c(problems, sprintf("%s.rows must be an array", label)))
  }
  for (i in seq_along(object$rows)) {
    problems <- c(
      problems,
      categorical_gcomp_exact_names(object$rows[[i]], fields, sprintf("%s.rows[%d]", label, i))
    )
  }
  problems
}

categorical_gcomp_nested_value_problems <- function(
    value,
    label,
    allowed_list_fields = character()) {
  if (!is.list(value)) return(sprintf("%s must be an object", label))
  bad <- setdiff(
    names(value)[vapply(value, is.list, logical(1))],
    allowed_list_fields
  )
  if (length(bad)) {
    return(sprintf(
      "%s contains nested object or array in scalar field: %s",
      label,
      paste(bad, collapse = ", ")
    ))
  }
  character()
}

categorical_gcomp_named_scalar_map_problems <- function(
    value,
    label,
    numeric_only = TRUE) {
  if (!is.list(value) || is.data.frame(value) ||
      is.null(names(value)) || any(!nzchar(names(value))) ||
      anyDuplicated(names(value))) {
    return(sprintf("%s must be a named object", label))
  }
  bad <- vapply(value, function(item) {
    if (is.null(item)) return(FALSE)
    if (is.list(item) || length(item) != 1L) return(TRUE)
    numeric_only && !is.numeric(item)
  }, logical(1))
  if (any(bad)) return(sprintf("%s values must be scalar", label))
  character()
}

validate_categorical_gcomp_cohort <- function(object) {
  fields <- c(
    "schema_version", "candidate_id", "dataset_id", "dataset_sha256",
    "input_n", "eligible_n", "classified_n", "source_counts",
    "unclassified_n", "conflicting_latest_source_n", "model_complete_case_n",
    "missingness_by_field"
  )
  problems <- categorical_gcomp_exact_names(object, fields, "cohort")
  if (!identical(object$schema_version, "categorical-gcomp-cohort-flow@1.0.0")) {
    problems <- c(problems, "cohort schema mismatch")
  }
  problems <- c(
    problems,
    categorical_gcomp_nested_value_problems(
      object,
      "cohort",
      c("source_counts", "missingness_by_field")
    ),
    categorical_gcomp_named_scalar_map_problems(
      object$source_counts,
      "cohort.source_counts"
    ),
    categorical_gcomp_named_scalar_map_problems(
      object$missingness_by_field,
      "cohort.missingness_by_field"
    )
  )
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_unadjusted <- function(object) {
  problems <- categorical_gcomp_validate_rows(
    object,
    c(
      "source", "status", "n", "events", "risk", "risk_ci_low",
      "risk_ci_high", "confidence_level", "interval_method"
    ),
    "unadjusted"
  )
  if (!identical(
    object$schema_version,
    "categorical-gcomp-unadjusted-source-risks@1.0.0"
  )) problems <- c(problems, "unadjusted schema mismatch")
  for (i in seq_along(object$rows)) {
    problems <- c(
      problems,
      categorical_gcomp_nested_value_problems(
        object$rows[[i]],
        sprintf("unadjusted.rows[%d]", i)
      )
    )
  }
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_adjusted <- function(object) {
  problems <- categorical_gcomp_validate_rows(
    object,
    c(
      "source", "reference", "status", "analysis_n", "standardized_risk",
      "risk_ci_low", "risk_ci_high", "risk_difference",
      "risk_difference_ci_low", "risk_difference_ci_high",
      "variance_method", "draw_count", "seed"
    ),
    "adjusted"
  )
  if (!identical(object$schema_version, "categorical-gcomp-adjusted-risks@1.0.0")) {
    problems <- c(problems, "adjusted schema mismatch")
  }
  for (i in seq_along(object$rows)) {
    problems <- c(
      problems,
      categorical_gcomp_nested_value_problems(
        object$rows[[i]],
        sprintf("adjusted.rows[%d]", i)
      )
    )
  }
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_first_event <- function(object) {
  problems <- categorical_gcomp_validate_rows(
    object,
    c(
      "source", "first_event", "status", "count",
      "source_composite_event_denominator", "source_all_row_denominator",
      "proportion", "ci_low", "ci_high", "interval_method"
    ),
    "first_event"
  )
  if (!identical(
    object$schema_version,
    "categorical-gcomp-first-event-composition@1.0.0"
  )) problems <- c(problems, "first-event schema mismatch")
  for (i in seq_along(object$rows)) {
    problems <- c(
      problems,
      categorical_gcomp_nested_value_problems(
        object$rows[[i]],
        sprintf("first_event.rows[%d]", i)
      )
    )
  }
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_credibility <- function(object) {
  problems <- categorical_gcomp_validate_rows(
    object,
    c(
      "analysis_id", "status", "n", "source_counts", "converged", "finite",
      "standardized_risks", "risk_differences",
      "maximum_absolute_standardized_risk_change",
      "risk_difference_sign_reversal", "threshold_assessment",
      "noninformative_reason"
    ),
    "credibility"
  )
  if (!identical(
    object$schema_version,
    "categorical-gcomp-credibility-results@1.0.0"
  )) problems <- c(problems, "credibility schema mismatch")
  if (length(object$rows) != 2L ||
      !identical(
        vapply(object$rows, `[[`, character(1), "analysis_id"),
        .categorical_gcomp_sensitivity_ids
      )) {
    problems <- c(problems, "credibility must contain exactly the two registered sensitivities")
  }
  for (i in seq_along(object$rows)) {
    row <- object$rows[[i]]
    problems <- c(
      problems,
      categorical_gcomp_nested_value_problems(
        row,
        sprintf("credibility.rows[%d]", i),
        c("source_counts", "standardized_risks", "risk_differences")
      ),
      categorical_gcomp_named_scalar_map_problems(
        row$source_counts,
        sprintf("credibility.rows[%d].source_counts", i)
      ),
      categorical_gcomp_named_scalar_map_problems(
        row$standardized_risks,
        sprintf("credibility.rows[%d].standardized_risks", i)
      ),
      categorical_gcomp_named_scalar_map_problems(
        row$risk_differences,
        sprintf("credibility.rows[%d].risk_differences", i)
      )
    )
  }
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_diagnostics <- function(object) {
  fields <- c(
    "schema_version", "formula", "reference", "analysis_n", "model_parameters",
    "converged", "finite", "covariance_method", "covariance_valid",
    "observed_source_levels", "empty_source_levels", "failure_codes",
    "draw_count", "requested_seed", "effective_r_seed", "paired_contrasts",
    "separate_marginal_intervals_subtracted"
  )
  problems <- categorical_gcomp_exact_names(object, fields, "diagnostics")
  if (!identical(object$schema_version, "categorical-gcomp-diagnostics@1.0.0")) {
    problems <- c(problems, "diagnostics schema mismatch")
  }
  if (!identical(object$paired_contrasts, TRUE) ||
      !identical(object$separate_marginal_intervals_subtracted, FALSE)) {
    problems <- c(problems, "paired contrast diagnostic mismatch")
  }
  problems <- c(
    problems,
    categorical_gcomp_nested_value_problems(
      object,
      "diagnostics",
      c("observed_source_levels", "empty_source_levels", "failure_codes")
    )
  )
  for (field in c(
    "observed_source_levels", "empty_source_levels", "failure_codes"
  )) {
    sequence <- categorical_gcomp_sequence(object[[field]])
    if (is.null(sequence) || (length(sequence) && !is.character(sequence))) {
      problems <- c(problems, sprintf("diagnostics.%s must be a string array", field))
    }
  }
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_failure <- function(object) {
  fields <- c(
    "schema_version", "status", "failure_code", "stage", "synthetic_only",
    "authority", "data_access", "aggregate_counts"
  )
  problems <- categorical_gcomp_exact_names(object, fields, "failure")
  if (!identical(
    object$schema_version,
    "categorical-gcomp-failure-diagnostic@1.0.0"
  ) || !identical(object$status, "BLOCKED") ||
      !(object$failure_code %in% .categorical_gcomp_failure_codes)) {
    problems <- c(problems, "failure diagnostic identity mismatch")
  }
  problems <- c(
    problems,
    categorical_gcomp_nested_value_problems(
      object,
      "failure",
      c("authority", "data_access", "aggregate_counts")
    ),
    categorical_gcomp_nested_value_problems(object$authority, "failure.authority"),
    categorical_gcomp_nested_value_problems(object$data_access, "failure.data_access"),
    categorical_gcomp_nested_value_problems(object$aggregate_counts, "failure.aggregate_counts")
  )
  if (isTRUE(object$synthetic_only) &&
      (isTRUE(object$data_access$real_data_read) ||
       isTRUE(object$data_access$patient_level_data_read) ||
       isTRUE(object$authority$materialization_authorized) ||
       isTRUE(object$authority$formal_execution_authorized) ||
       isTRUE(object$authority$formal_authorization_consumed))) {
    problems <- c(problems, "synthetic failure diagnostic cannot claim real-data or execution authority")
  }
  problems <- c(problems, categorical_gcomp_privacy_problems(object))
  if (length(problems)) stop(contract_error(problems))
  invisible(TRUE)
}

validate_categorical_gcomp_bundle <- function(object) {
  checksum_checker <- if (
    identical(object$schema_version, "categorical-gcomp-result-bundle@1.1.0")
  ) {
    categorical_gcomp_sha256_prefixed
  } else {
    categorical_gcomp_sha256
  }
  fields <- c(
    "schema_version", "status", "analysis_id", "task_id", "candidate_id",
    "dataset_id", "dataset_sha256", "synthetic_only", "authority",
    "data_access", "cohort", "unadjusted", "adjusted",
    "first_event_composition", "credibility", "diagnostics"
  )
  problems <- categorical_gcomp_exact_names(object, fields, "bundle")
  if (!is.character(object$schema_version) ||
      !object$schema_version %in% c(
        "categorical-gcomp-result-bundle@1.0.0",
        "categorical-gcomp-result-bundle@1.1.0"
      ) ||
      !identical(object$status, "COMPLETE")) {
    problems <- c(problems, "bundle identity mismatch")
  }
  if (!checksum_checker(object$dataset_sha256)) {
    problems <- c(problems, "bundle.dataset_sha256 has invalid checksum format")
  }
  problems <- c(
    problems,
    categorical_gcomp_nested_value_problems(
      object,
      "bundle",
      c(
        "authority", "data_access", "cohort", "unadjusted", "adjusted",
        "first_event_composition", "credibility", "diagnostics"
      )
    ),
    categorical_gcomp_nested_value_problems(object$authority, "bundle.authority"),
    categorical_gcomp_nested_value_problems(object$data_access, "bundle.data_access")
  )
  if (isTRUE(object$synthetic_only) &&
      (isTRUE(object$data_access$real_data_read) ||
       isTRUE(object$data_access$patient_level_data_read) ||
       isTRUE(object$authority$materialization_authorized) ||
       isTRUE(object$authority$formal_execution_authorized) ||
       isTRUE(object$authority$formal_authorization_consumed))) {
    problems <- c(problems, "synthetic bundle cannot claim real-data or execution authority")
  }
  validators <- list(
    cohort = validate_categorical_gcomp_cohort,
    unadjusted = validate_categorical_gcomp_unadjusted,
    adjusted = validate_categorical_gcomp_adjusted,
    first_event_composition = validate_categorical_gcomp_first_event,
    credibility = validate_categorical_gcomp_credibility,
    diagnostics = validate_categorical_gcomp_diagnostics
  )
  for (name in names(validators)) {
    tryCatch(
      validators[[name]](object[[name]]),
      clinanalysis_contract_error = function(e) {
        problems <<- c(problems, e$problems)
      }
    )
  }
  problems <- c(problems, categorical_gcomp_privacy_problems(object))
  if (length(problems)) stop(contract_error(unique(problems)))
  invisible(TRUE)
}

categorical_gcomp_failure_diagnostic <- function(task, code, stage, data = NULL) {
  synthetic <- is.list(task) && identical(task$execution_mode, "SYNTHETIC_TEST")
  real_data_supplied <- !synthetic && is.data.frame(data)
  diagnostic <- list(
    schema_version = "categorical-gcomp-failure-diagnostic@1.0.0",
    status = "BLOCKED",
    failure_code = if (code %in% .categorical_gcomp_failure_codes) code else "INTERNAL_ERROR",
    stage = stage,
    synthetic_only = synthetic,
    authority = list(
      materialization_authorized = if (synthetic) FALSE else isTRUE(task$authority$materialization_authorized),
      formal_execution_authorized = if (synthetic) FALSE else isTRUE(task$authority$formal_execution_authorized),
      formal_authorization_consumed = FALSE
    ),
    data_access = list(
      real_data_read = real_data_supplied,
      patient_level_data_read = real_data_supplied,
      synthetic_fixture_rows_processed = synthetic && is.data.frame(data)
    ),
    aggregate_counts = list(
      input_n = if (is.data.frame(data)) as.integer(nrow(data)) else 0L
    )
  )
  validate_categorical_gcomp_failure(diagnostic)
  diagnostic
}

categorical_gcomp_build_bundle <- function(task, data) {
  categorical_gcomp_validate_data(task, data)
  is_full <- identical(task$schema_version, .categorical_gcomp_full_task_version) &&
    categorical_gcomp_is_full_article_target(task)
  bundle_schema_version <- if (
    is_full
  ) .categorical_gcomp_full_result_bundle_version else "categorical-gcomp-result-bundle@1.0.0"
  primary_fit <- categorical_gcomp_fit(
    task, data, task$analysis$exposure, stage = "PRIMARY_FIT"
  )
  bundle <- list(
    schema_version = bundle_schema_version,
    status = "COMPLETE",
    analysis_id = task$analysis_id,
    task_id = task$task_id,
    candidate_id = task$binding$candidate_id,
    dataset_id = task$data$dataset_id,
    dataset_sha256 = task$data$sha256,
    synthetic_only = identical(task$execution_mode, "SYNTHETIC_TEST"),
    authority = list(
      materialization_authorized =
        if (identical(task$execution_mode, "SYNTHETIC_TEST")) FALSE else task$authority$materialization_authorized,
      formal_execution_authorized =
        if (identical(task$execution_mode, "SYNTHETIC_TEST")) FALSE else task$authority$formal_execution_authorized,
      formal_authorization_consumed =
        identical(task$execution_mode, "FORMAL")
    ),
    data_access = list(
      real_data_read = identical(task$execution_mode, "FORMAL"),
      patient_level_data_read = identical(task$execution_mode, "FORMAL"),
      synthetic_fixture_rows_processed =
        identical(task$execution_mode, "SYNTHETIC_TEST")
    ),
    cohort = categorical_gcomp_cohort(task, data, primary_fit),
    unadjusted = categorical_gcomp_unadjusted(task, data),
    adjusted = categorical_gcomp_adjusted(task, primary_fit),
    first_event_composition = categorical_gcomp_first_event(task, data),
    credibility = categorical_gcomp_credibility(task, data, primary_fit),
    diagnostics = categorical_gcomp_diagnostics(task, primary_fit)
  )
  validate_categorical_gcomp_bundle(bundle)
  bundle
}

categorical_gcomp_rows_to_data_frame <- function(rows) {
  if (!length(rows)) {
    return(data.frame(stringsAsFactors = FALSE))
  }
  fields <- names(rows[[1L]])
  output <- lapply(fields, function(field) {
    values <- lapply(rows, `[[`, field)
    default <- NA
    for (value in values) {
      if (!is.null(value)) {
        default <- value
        break
      }
    }
    vapply(values, function(value) {
      if (is.null(value)) NA else value
    }, FUN.VALUE = default)
  })
  names(output) <- fields
  as.data.frame(output, stringsAsFactors = FALSE, check.names = FALSE)
}

categorical_gcomp_list_to_checksum_map <- function(output_artifacts) {
  lapply(output_artifacts, function(artifact) list(
    output_id = artifact$output_id,
    filename = artifact$filename,
    sha256 = artifact$sha256
  ))
}

categorical_gcomp_safe_basename <- function(value) {
  is.character(value) &&
    length(value) == 1L &&
    nzchar(value) &&
    !grepl("(^/|[A-Za-z]:[\\\\/]|[\\\\/]|^\\.|\\.\\.)", value) &&
    grepl("^[A-Za-z0-9._-]+$", value)
}

categorical_gcomp_build_full_table_rows <- function(task, data) {
  table1 <- build_table1(task, data)
  if (!is.list(table1) || !identical(table1$status, "COMPLETE")) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "TABLE1_BUILD")
  }
  if (!is.data.frame(table1$formatted) || !nrow(table1$formatted)) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "TABLE1_BUILD")
  }
  list(
    formatted = as.data.frame(table1$formatted, stringsAsFactors = FALSE)
  )
}

categorical_gcomp_build_full_primary_estimates <- function(bundle) {
  scalar_or_na <- function(value) {
    if (is.null(value)) NA_real_ else value
  }
  rows <- lapply(bundle$adjusted$rows, function(row) {
    data.frame(
      source = row$source,
      reference = row$reference,
      status = row$status,
      analysis_n = row$analysis_n,
      standardized_risk = scalar_or_na(row$standardized_risk),
      risk_ci_low = scalar_or_na(row$risk_ci_low),
      risk_ci_high = scalar_or_na(row$risk_ci_high),
      risk_difference = scalar_or_na(row$risk_difference),
      risk_difference_ci_low = scalar_or_na(row$risk_difference_ci_low),
      risk_difference_ci_high = scalar_or_na(row$risk_difference_ci_high),
      variance_method = row$variance_method,
      draw_count = row$draw_count,
      seed = row$seed,
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

categorical_gcomp_build_full_credibility_table <- function(bundle) {
  scalar_or_na <- function(value) {
    if (is.null(value)) NA else value
  }
  rows <- lapply(bundle$credibility$rows, function(row) {
    source_counts <- jsonlite::toJSON(
      row$source_counts,
      auto_unbox = TRUE,
      null = "null"
    )
    data.frame(
      analysis_id = row$analysis_id,
      status = row$status,
      n = row$n,
      converged = row$converged,
      finite = row$finite,
      source_counts = source_counts,
      maximum_absolute_standardized_risk_change =
        scalar_or_na(row$maximum_absolute_standardized_risk_change),
      risk_difference_sign_reversal =
        scalar_or_na(row$risk_difference_sign_reversal),
      threshold_assessment = scalar_or_na(row$threshold_assessment),
      noninformative_reason = if (is.null(row$noninformative_reason)) NA_character_ else row$noninformative_reason,
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

categorical_gcomp_build_full_cohort_flow_figure <- function(bundle) {
  source_counts <- bundle$cohort$source_counts
  if (!length(source_counts)) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FIGURE_BUILD")
  }
  counts <- data.frame(
    source = names(source_counts),
    n = as.integer(unlist(source_counts)),
    stringsAsFactors = FALSE
  )
  if (!nrow(counts)) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FIGURE_BUILD")
  }
  counts$source_label <- gsub("_", " ", counts$source, fixed = TRUE)
  counts$source_label <- factor(
    counts$source_label,
    levels = rev(counts$source_label)
  )
  x_breaks <- pretty(c(0, max(counts$n)), n = 4L)
  x_breaks <- x_breaks[x_breaks <= max(counts$n)]
  ggplot2::ggplot(counts, ggplot2::aes_string(x = "n", y = "source_label")) +
    ggplot2::geom_col(width = 0.68, fill = "#0072B2", color = "black") +
    ggplot2::geom_text(
      ggplot2::aes_string(label = "n"),
      hjust = -0.15,
      size = 3
    ) +
    ggplot2::scale_x_continuous(
      breaks = x_breaks,
      labels = function(value) format(
        value,
        big.mark = ",",
        scientific = FALSE,
        trim = TRUE
      ),
      expand = ggplot2::expansion(mult = c(0, 0.12))
    ) +
    ggplot2::labs(x = "Patients", y = "Transfer source") +
    ggplot2::theme_classic(base_family = "sans", base_size = 9)
}

categorical_gcomp_build_full_primary_effect_figure <- function(bundle) {
  complete <- Filter(function(x) identical(x$status, "ESTIMATED"), bundle$adjusted$rows)
  if (!length(complete)) {
    categorical_gcomp_stop("NOT_ESTIMABLE", "FIGURE_BUILD")
  }
  points <- data.frame(
    source = vapply(complete, `[[`, character(1), "source"),
    risk = vapply(complete, `[[`, numeric(1), "standardized_risk"),
    low = vapply(complete, `[[`, numeric(1), "risk_ci_low"),
    high = vapply(complete, `[[`, numeric(1), "risk_ci_high"),
    stringsAsFactors = FALSE
  )
  if (!all(is.finite(points$low)) || !all(is.finite(points$high)) || !all(is.finite(points$risk))) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FIGURE_BUILD")
  }
  points$source_label <- gsub("_", " ", points$source, fixed = TRUE)
  points$source_label <- factor(
    points$source_label,
    levels = rev(points$source_label)
  )
  ggplot2::ggplot(
    points,
    ggplot2::aes_string(x = "risk", y = "source_label")
  ) +
    ggplot2::geom_errorbarh(
      ggplot2::aes_string(xmin = "low", xmax = "high"),
      height = 0.14,
      linewidth = 0.6,
      color = "#0072B2"
    ) +
    ggplot2::geom_point(size = 2.4, shape = 21, fill = "white", color = "black") +
    ggplot2::scale_x_continuous(
      labels = function(value) sprintf("%.0f%%", 100 * value),
      expand = ggplot2::expansion(mult = c(0.08, 0.08))
    ) +
    ggplot2::labs(x = "Standardized 24-hour risk (95% CI)", y = "Transfer source") +
    ggplot2::theme_classic(base_family = "sans", base_size = 9)
}

categorical_gcomp_build_full_clinical_deepening_first_event_figure <- function(bundle) {
  rows <- bundle$first_event_composition$rows
  if (!length(rows)) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FIGURE_BUILD")
  }
  rows <- Filter(function(x) identical(x$status, "ESTIMATED"), rows)
  points <- data.frame(
    source = vapply(rows, `[[`, character(1), "source"),
    first_event = vapply(rows, `[[`, character(1), "first_event"),
    count = vapply(rows, `[[`, numeric(1), "count"),
    proportion = vapply(rows, `[[`, numeric(1), "proportion"),
    stringsAsFactors = FALSE
  )
  if (!nrow(points) || !all(is.finite(points$count)) || !all(is.finite(points$proportion))) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FIGURE_BUILD")
  }
  points$first_event <- factor(
    points$first_event,
    levels = c(
      "ICU_DEATH",
      "NEW_INVASIVE_VENTILATION",
      "NEW_VASOPRESSOR",
      "NEW_RRT"
    ),
    labels = c(
      "ICU death",
      "New invasive ventilation",
      "New vasopressor",
      "New RRT"
    )
  )
  points$source_label <- gsub("_", " ", points$source, fixed = TRUE)
  ggplot2::ggplot(
    points,
    ggplot2::aes_string(
      x = "source_label",
      y = "proportion",
      fill = "first_event"
    )
  ) +
    ggplot2::geom_col(color = "black", linewidth = 0.25, width = 0.68) +
    ggplot2::scale_fill_manual(
      values = c("#0072B2", "#E69F00", "#009E73", "#CC79A7"),
      drop = FALSE
    ) +
    ggplot2::scale_y_continuous(
      labels = function(value) sprintf("%.0f%%", 100 * value),
      limits = c(0, 1),
      expand = c(0, 0)
    ) +
    ggplot2::labs(
      x = "Transfer source",
      y = "Proportion of composite events",
      fill = "First event"
    ) +
    ggplot2::theme_classic(base_family = "sans", base_size = 9) +
    ggplot2::theme(
      legend.position = "bottom",
      legend.title = ggplot2::element_text(size = 8),
      legend.text = ggplot2::element_text(size = 8)
    )
}

categorical_gcomp_output_file_hash <- function(path) {
  digest::digest(file = path, algo = "sha256", serialize = FALSE)
}

categorical_gcomp_build_full_output_manifest <- function(
  task,
  bundle,
  bundle_sha256,
  artifacts,
  execution_binding
) {
  manifest_id <- categorical_gcomp_make_manifest_id(
    task$binding$candidate_id,
    task$task_id
  )
  list(
    schema_version = .categorical_gcomp_full_output_manifest_version,
    manifest_id = manifest_id,
    result_bundle_schema_version = .categorical_gcomp_full_result_bundle_version,
    candidate_id = task$binding$candidate_id,
    task_id = task$task_id,
    analysis_result_manifest_id = manifest_id,
    research_bindings = categorical_gcomp_full_research_bindings(task, execution_binding),
    execution_authorization_binding = list(
      schema_version = "categorical-gcomp-formal-execution-binding@1.0.0",
      authorization_id = execution_binding$authorization_id,
      authorization_sha256 = execution_binding$authorization_sha256,
      task_id = execution_binding$task_id,
      task_sha256 = execution_binding$task_sha256,
      candidate_id = execution_binding$candidate_id
    ),
    full_article_target_id = task$analysis$full_article_target_id,
    full_article_profile_checksum = task$analysis$full_article_profile_checksum,
    planned_display_contract_id = task$analysis$planned_display_contract_id,
    planned_display_contract_sha256 = task$analysis$planned_display_contract_sha256,
    prior_result_exposure = task$analysis$prior_result_exposure,
    confirmatory_claim_allowed = task$analysis$confirmatory_claim_allowed,
    source_result_sha256 = bundle_sha256,
    artifacts = artifacts
  )
}

validate_categorical_gcomp_full_output_manifest <- function(manifest) {
  expected <- .categorical_gcomp_full_output_ids
  expected_sources <- c(
    rep(.categorical_gcomp_full_raw_source_label, 6L),
    rep(.categorical_gcomp_full_display_source_label, 6L)
  )
  problems <- character()
  if (!is.list(manifest)) {
    problems <- c(problems, "manifest must be an object")
  } else {
    research_bindings <- manifest$research_bindings %||% list()
    problems <- c(
      problems,
      categorical_gcomp_exact_names(
        manifest,
        c(
          "schema_version",
          "manifest_id",
          "result_bundle_schema_version",
          "candidate_id",
          "task_id",
          "analysis_result_manifest_id",
          "research_bindings",
          "execution_authorization_binding",
          "full_article_target_id",
          "full_article_profile_checksum",
          "planned_display_contract_id",
          "planned_display_contract_sha256",
          "prior_result_exposure",
          "confirmatory_claim_allowed",
          "source_result_sha256",
          "artifacts"
        ),
        "manifest"
      )
    )
    if (!is.character(manifest$schema_version) ||
        !identical(manifest$schema_version, .categorical_gcomp_full_output_manifest_version)) {
      problems <- c(problems, "manifest schema mismatch")
    }
    if (!categorical_gcomp_safe_basename(manifest$manifest_id)) {
      problems <- c(problems, "manifest manifest_id must be a safe logical id")
    }
    if (!is.character(manifest$result_bundle_schema_version) ||
        !identical(
          manifest$result_bundle_schema_version,
          .categorical_gcomp_full_result_bundle_version
        )) {
      problems <- c(
        problems,
        "manifest result_bundle_schema_version must reference categorical-gcomp-result-bundle@1.1.0"
      )
    }
    if (!categorical_gcomp_scalar_string(manifest$candidate_id)) {
      problems <- c(problems, "manifest candidate_id must be a non-empty string")
    }
    if (!categorical_gcomp_scalar_string(manifest$task_id)) {
      problems <- c(problems, "manifest task_id must be a non-empty string")
    }
    if (!isTRUE(identical(manifest$analysis_result_manifest_id, manifest$manifest_id))) {
      problems <- c(
        problems,
        "manifest analysis_result_manifest_id must match manifest_id"
      )
    }
    if (!is.character(research_bindings$candidate_id) || !nzchar(research_bindings$candidate_id)) {
      problems <- c(problems, "manifest.research_bindings.candidate_id must be a non-empty string")
    }
    if (!categorical_gcomp_sha256_prefixed(research_bindings$candidate_sha256)) {
      problems <- c(
        problems,
        "manifest.research_bindings.candidate_sha256 must be prefixed SHA-256"
      )
    }
    if (!is.character(research_bindings$sap_id) || !nzchar(research_bindings$sap_id)) {
      problems <- c(problems, "manifest.research_bindings.sap_id must be a non-empty string")
    }
    if (!categorical_gcomp_sha256_prefixed(research_bindings$sap_sha256)) {
      problems <- c(
        problems,
        "manifest.research_bindings.sap_sha256 must be prefixed SHA-256"
      )
    }
    if (!is.character(research_bindings$analysis_task_id) || !nzchar(research_bindings$analysis_task_id)) {
      problems <- c(
        problems,
        "manifest.research_bindings.analysis_task_id must be a non-empty string"
      )
    }
    if (!categorical_gcomp_sha256_prefixed(research_bindings$analysis_task_sha256)) {
      problems <- c(
        problems,
        "manifest.research_bindings.analysis_task_sha256 must be prefixed SHA-256"
      )
    }
    if (!is.character(research_bindings$value_set_id) || !nzchar(research_bindings$value_set_id)) {
      problems <- c(
        problems,
        "manifest.research_bindings.value_set_id must be a non-empty string"
      )
    }
    if (!categorical_gcomp_sha256_prefixed(research_bindings$value_set_sha256)) {
      problems <- c(
        problems,
        "manifest.research_bindings.value_set_sha256 must be prefixed SHA-256"
      )
    }
    if (!is.character(research_bindings$source_snapshot_id) || !nzchar(research_bindings$source_snapshot_id)) {
      problems <- c(
        problems,
        "manifest.research_bindings.source_snapshot_id must be a non-empty string"
      )
    }
    if (!categorical_gcomp_sha256_prefixed(research_bindings$source_snapshot_sha256)) {
      problems <- c(
        problems,
        "manifest.research_bindings.source_snapshot_sha256 must be prefixed SHA-256"
      )
    }
    execution_authorization_binding <- manifest$execution_authorization_binding %||% list()
    if (!is.list(execution_authorization_binding)) {
      problems <- c(
        problems,
        "manifest.execution_authorization_binding must be an object"
      )
    } else {
      if (!categorical_gcomp_scalar_string(
        execution_authorization_binding$authorization_id
      )) {
        problems <- c(
          problems,
          "manifest.execution_authorization_binding.authorization_id must be a non-empty string"
        )
      }
      if (!categorical_gcomp_is_prefixed_sha256(
        execution_authorization_binding$authorization_sha256
      )) {
        problems <- c(
          problems,
          "manifest.execution_authorization_binding.authorization_sha256 must be prefixed SHA-256"
        )
      }
      if (!categorical_gcomp_scalar_string(
        execution_authorization_binding$schema_version
      )) {
        problems <- c(
          problems,
          "manifest.execution_authorization_binding.schema_version must be a non-empty string"
        )
      }
      if (!categorical_gcomp_scalar_string(
        execution_authorization_binding$candidate_id
      )) {
        problems <- c(
          problems,
          "manifest.execution_authorization_binding.candidate_id must be a non-empty string"
        )
      }
      if (!identical(execution_authorization_binding$candidate_id, manifest$candidate_id)) {
        problems <- c(
          problems,
          "manifest.execution_authorization_binding.candidate_id must match manifest$candidate_id"
        )
      }
    }
    if (!categorical_gcomp_safe_basename(manifest$full_article_target_id)) {
      problems <- c(problems, "manifest full_article_target_id must be a safe logical id")
    }
    if (!categorical_gcomp_sha256_prefixed(manifest$full_article_profile_checksum)) {
      problems <- c(problems, "manifest full_article_profile_checksum must be prefixed SHA-256")
    }
    if (!categorical_gcomp_safe_basename(manifest$planned_display_contract_id)) {
      problems <- c(problems, "manifest planned_display_contract_id must be a safe logical id")
    }
    if (!categorical_gcomp_sha256_prefixed(manifest$planned_display_contract_sha256)) {
      problems <- c(problems, "manifest planned_display_contract_sha256 must be prefixed SHA-256")
    }
    if (!categorical_gcomp_scalar_logical(manifest$prior_result_exposure)) {
      problems <- c(problems, "manifest prior_result_exposure must be a logical value")
    }
    if (!categorical_gcomp_scalar_logical(manifest$confirmatory_claim_allowed)) {
      problems <- c(problems, "manifest confirmatory_claim_allowed must be a logical value")
    }
    if (isTRUE(manifest$prior_result_exposure) && isTRUE(manifest$confirmatory_claim_allowed)) {
      problems <- c(problems, "manifest confirmatory_claim_allowed must be false when prior_result_exposure is true")
    }
    if (!categorical_gcomp_sha256_prefixed(manifest$source_result_sha256)) {
      problems <- c(problems, "manifest source_result_sha256 must be sha256 prefixed")
    }
    if (!is.list(manifest$artifacts)) {
      problems <- c(problems, "manifest.artifacts must be an array")
    } else {
      if (length(manifest$artifacts) != length(expected)) {
        problems <- c(problems, sprintf("manifest.artifacts must contain exactly %d artifacts", length(expected)))
      }
      ids <- vapply(
        manifest$artifacts,
        function(x) {
          if (is.list(x) && !is.null(x$output_id)) x$output_id else ""
        },
        character(1)
      )
      if (anyDuplicated(ids) || !identical(ids, expected)) {
        problems <- c(problems, "manifest.artifacts output ids mismatch")
      }
      n_artifacts <- min(length(manifest$artifacts), length(expected))
      for (i in seq_len(n_artifacts)) {
        artifact <- manifest$artifacts[[i]]
        if (!is.list(artifact)) {
          problems <- c(problems, sprintf("manifest.artifacts[%d] must be an object", i))
          next
        }
    artifact_fields <- c(
      "output_id",
      "filename",
      "source",
      "source_result_sha256",
      "sha256",
      "aggregate_only"
    )
        if (identical(artifact$source, .categorical_gcomp_full_display_source_label)) {
          artifact_fields <- c(
            artifact_fields,
            "display_id",
            "role",
            "scientific_domain",
            "source_result_id"
          )
        } else if (!identical(artifact$source, .categorical_gcomp_full_raw_source_label)) {
          problems <- c(
            problems,
            sprintf("manifest.artifacts[%d].source must be display or non-display", i)
          )
        } else if (is.list(artifact) && any(names(artifact) %in% c("display_id", "role", "scientific_domain", "source_result_id"))) {
          problems <- c(
            problems,
            sprintf("manifest.artifacts[%d] has unexpected raw-display fields", i)
          )
        }
        problems <- c(
          problems,
          categorical_gcomp_exact_names(
            artifact,
            artifact_fields,
            sprintf("manifest.artifacts[%d]", i)
          )
        )
        if (!isTRUE(artifact$aggregate_only)) {
          problems <- c(problems, sprintf("manifest.artifacts[%d].aggregate_only must be true", i))
        }
        if (!identical(artifact$output_id, expected[[i]])) {
          problems <- c(problems, sprintf("manifest.artifacts[%d].output_id mismatch", i))
        }
        expected_spec <- .categorical_gcomp_full_display_output_specs[[artifact$output_id]]
        if (is.character(artifact$source) &&
            identical(artifact$source, .categorical_gcomp_full_display_source_label)) {
          if (is.null(expected_spec)) {
            problems <- c(
              problems,
              sprintf("manifest.artifacts[%d] has no matching output spec", i)
            )
          } else {
            if (!identical(artifact$filename, expected_spec$filename)) {
              problems <- c(
                problems,
                sprintf("manifest.artifacts[%d].filename mismatch expected display mapping", i)
              )
            }
            if (!identical(artifact$role, expected_spec$role)) {
              problems <- c(
                problems,
                sprintf("manifest.artifacts[%d].role mismatch expected display mapping", i)
              )
            }
            if (!identical(artifact$scientific_domain, expected_spec$scientific_domain)) {
              problems <- c(
                problems,
                sprintf("manifest.artifacts[%d].scientific_domain mismatch expected display mapping", i)
              )
            }
            if (!identical(artifact$source_result_id, expected_spec$source_result_id)) {
              problems <- c(
                problems,
                sprintf("manifest.artifacts[%d].source_result_id mismatch expected display mapping", i)
              )
            }
          }
        }
        if (!identical(artifact$source, expected_sources[[i]])) {
          problems <- c(
            problems,
            sprintf("manifest.artifacts[%d].source mismatch", i)
          )
        }
        if (!categorical_gcomp_safe_basename(artifact$filename)) {
          problems <- c(problems, sprintf("manifest.artifacts[%d].filename unsafe", i))
        }
        if (!identical(artifact$source_result_sha256, manifest$source_result_sha256)) {
          problems <- c(problems, sprintf("manifest.artifacts[%d].source_result_sha256 mismatch", i))
        }
        if (!categorical_gcomp_sha256_prefixed(artifact$sha256)) {
          problems <- c(problems, sprintf("manifest.artifacts[%d].sha256 mismatch", i))
        }
        if (identical(artifact$source, .categorical_gcomp_full_display_source_label)) {
          if (!categorical_gcomp_safe_basename(artifact$display_id)) {
            problems <- c(
              problems,
              sprintf("manifest.artifacts[%d].display_id must be a safe logical id", i)
            )
          }
          if (!is.character(artifact$role) || !nzchar(artifact$role)) {
            problems <- c(
              problems,
              sprintf("manifest.artifacts[%d].role must be non-empty", i)
            )
          }
          if (!is.character(artifact$scientific_domain) || !nzchar(artifact$scientific_domain)) {
            problems <- c(
              problems,
              sprintf("manifest.artifacts[%d].scientific_domain must be non-empty", i)
            )
          }
          if (!categorical_gcomp_safe_basename(artifact$source_result_id)) {
            problems <- c(
              problems,
              sprintf("manifest.artifacts[%d].source_result_id must be a safe logical id", i)
            )
          }
        }
      }
    }
  }
  if (length(problems)) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "OUTPUT_MANIFEST")
  }
  invisible(TRUE)
}

categorical_gcomp_prepare_full_outputs <- function(task, data, bundle) {
  adjusted_statuses <- vapply(bundle$adjusted$rows, `[[`, character(1), "status")
  if (any(grepl("^NOT_ESTIMABLE", adjusted_statuses))) {
    categorical_gcomp_stop("NOT_ESTIMABLE", "FULL_TARGET_ESTIMABILITY")
  }
  table_output <- categorical_gcomp_build_full_table_rows(task, data)
  primary_estimates <- categorical_gcomp_build_full_primary_estimates(bundle)
  deepening_credibility <- categorical_gcomp_build_full_credibility_table(bundle)
  safe_figure <- function(builder) {
    tryCatch(
      builder(),
      categorical_gcomp_failure = function(e) {
        if (is.list(e) && !is.null(e$code) && is.character(e$code) &&
            e$code %in% .categorical_gcomp_failure_codes) {
          stop(e)
        }
        categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FIGURE_BUILD")
      },
      error = function(e) {
        msg <- conditionMessage(e)
        code <- if (
          is.character(msg) &&
          length(msg) == 1L &&
          msg %in% .categorical_gcomp_failure_codes
        ) {
          msg
        } else {
          "FULL_ARTICLE_TARGET_MISMATCH"
        }
        stage <- if (is.list(e) && is.character(e$stage) && length(e$stage) == 1L) e$stage else "FIGURE_BUILD"
        categorical_gcomp_stop(code, stage)
      }
    )
  }
  figures <- list(
    cohort = safe_figure(function() categorical_gcomp_build_full_cohort_flow_figure(bundle)),
    primary = safe_figure(function() categorical_gcomp_build_full_primary_effect_figure(bundle)),
    deepening = safe_figure(function() categorical_gcomp_build_full_clinical_deepening_first_event_figure(bundle))
  )
  if (!nrow(primary_estimates) || !nrow(deepening_credibility)) {
    categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FULL_OUTPUT_BUILD")
  }
  list(
    table_outputs = table_output,
    primary_estimates = primary_estimates,
    deepening_credibility = deepening_credibility,
    figures = figures
  )
}

write_categorical_gcomp_bundle <- function(
  bundle,
  output_dir,
  full_task = FALSE,
  data = NULL,
  task = NULL,
  execution_binding = NULL,
  planned_display_contract = NULL
) {
  result_bundle <- bundle
  validate_categorical_gcomp_bundle(bundle)
  if (dir.exists(output_dir) || file.exists(output_dir)) {
    categorical_gcomp_stop("OUTPUT_ALREADY_EXISTS", "PREWRITE_VALIDATION")
  }
  parent <- dirname(output_dir)
  dir.create(parent, recursive = TRUE, showWarnings = FALSE)
  stage <- tempfile(".categorical-gcomp-stage-", tmpdir = parent)
  dir.create(stage, recursive = FALSE, showWarnings = FALSE)
  on.exit(if (dir.exists(stage)) unlink(stage, recursive = TRUE), add = TRUE)

  jsonlite::write_json(
    bundle$cohort,
    file.path(stage, "cohort_flow.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null", digits = NA
  )
  utils::write.csv(
    categorical_gcomp_rows_to_data_frame(bundle$unadjusted$rows),
    file.path(stage, "unadjusted_source_risks.csv"),
    row.names = FALSE, na = ""
  )
  utils::write.csv(
    categorical_gcomp_rows_to_data_frame(bundle$adjusted$rows),
    file.path(stage, "adjusted_standardized_risks_and_differences.csv"),
    row.names = FALSE, na = ""
  )
  utils::write.csv(
    categorical_gcomp_rows_to_data_frame(bundle$first_event_composition$rows),
    file.path(stage, "first_event_composition.csv"),
    row.names = FALSE, na = ""
  )
  jsonlite::write_json(
    bundle$credibility,
    file.path(stage, "credibility_results.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null", digits = NA
  )
  jsonlite::write_json(
    bundle$diagnostics,
    file.path(stage, "diagnostics.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null", digits = NA
  )
  jsonlite::write_json(
    bundle,
    file.path(stage, "result_bundle.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null", digits = NA
  )

  result_bundle_sha256 <- paste0(
    "sha256:",
    categorical_gcomp_output_file_hash(file.path(stage, "result_bundle.json"))
  )

  artifact_specs <- list(
    list(
      output_id = "OUT_COHORT",
      filename = "cohort_flow.json",
      source = .categorical_gcomp_full_raw_source_label,
      source_result_sha256 = result_bundle_sha256,
      aggregate_only = TRUE
    ),
    list(
      output_id = "OUT_PRIMARY_UNADJUSTED",
      filename = "unadjusted_source_risks.csv",
      source = .categorical_gcomp_full_raw_source_label,
      source_result_sha256 = result_bundle_sha256,
      aggregate_only = TRUE
    ),
    list(
      output_id = "OUT_PRIMARY_ADJUSTED",
      filename = "adjusted_standardized_risks_and_differences.csv",
      source = .categorical_gcomp_full_raw_source_label,
      source_result_sha256 = result_bundle_sha256,
      aggregate_only = TRUE
    ),
    list(
      output_id = "OUT_DEEPENING",
      filename = "first_event_composition.csv",
      source = .categorical_gcomp_full_raw_source_label,
      source_result_sha256 = result_bundle_sha256,
      aggregate_only = TRUE
    ),
    list(
      output_id = "OUT_CREDIBILITY",
      filename = "credibility_results.json",
      source = .categorical_gcomp_full_raw_source_label,
      source_result_sha256 = result_bundle_sha256,
      aggregate_only = TRUE
    ),
    list(
      output_id = "OUT_DIAGNOSTICS",
      filename = "diagnostics.json",
      source = .categorical_gcomp_full_raw_source_label,
      source_result_sha256 = result_bundle_sha256,
      aggregate_only = TRUE
    )
  )

  if (full_task) {
    if (!is.list(execution_binding)) {
      categorical_gcomp_stop("TASK_CONTRACT_INVALID", "TASK_CONTRACT")
    }
    if (!is.list(task)) {
      categorical_gcomp_stop("TASK_CONTRACT_INVALID", "TASK_CONTRACT")
    }
    if (!is.list(data)) {
      categorical_gcomp_stop("FULL_ARTICLE_TARGET_MISMATCH", "FULL_OUTPUT_BUILD")
    }
    if (!is.list(planned_display_contract)) {
      categorical_gcomp_stop("TASK_CONTRACT_INVALID", "TASK_CONTRACT")
    }
    display_metadata <- categorical_gcomp_build_display_contract_metadata(planned_display_contract)
    full_outputs <- categorical_gcomp_prepare_full_outputs(task, data, bundle)
    full_artifact_specs <- lapply(.categorical_gcomp_full_display_output_ids, function(output_id) {
      spec <- .categorical_gcomp_full_display_output_specs[[output_id]]
      display_key <- paste(
        if (startsWith(output_id, "TABLE")) "TABLE" else "FIGURE",
        spec$role,
        sep = "::"
      )
      display <- display_metadata[[display_key]]
      if (is.null(display)) {
        categorical_gcomp_stop("TASK_CONTRACT_INVALID", "TASK_CONTRACT")
      }
      list(
        output_id = output_id,
        filename = spec$filename,
        source = .categorical_gcomp_full_display_source_label,
        source_result_sha256 = result_bundle_sha256,
        aggregate_only = TRUE,
        display_id = display$display_id,
        role = display$role,
        scientific_domain = display$scientific_domain,
        source_result_id = display$source_result_id
      )
    })
    artifact_specs <- c(artifact_specs, full_artifact_specs)

    utils::write.csv(
      full_outputs$table_outputs$formatted,
      file.path(stage, "table1.csv"),
      row.names = FALSE,
      na = ""
    )
    utils::write.csv(
      full_outputs$primary_estimates,
      file.path(stage, "primary_estimates.csv"),
      row.names = FALSE,
      na = ""
    )
    utils::write.csv(
      full_outputs$deepening_credibility,
      file.path(stage, "deepening_credibility.csv"),
      row.names = FALSE,
      na = ""
    )
    ggplot2::ggsave(
      file.path(stage, "figure_cohort_flow.png"),
      plot = full_outputs$figures$cohort,
      width = 8,
      height = 5,
      dpi = 300,
      bg = "white"
    )
    ggplot2::ggsave(
      file.path(stage, "figure_primary_effect.png"),
      plot = full_outputs$figures$primary,
      width = 8,
      height = 5,
      dpi = 300,
      bg = "white"
    )
    ggplot2::ggsave(
      file.path(stage, "figure_clinical_deepening_first_event_composition.png"),
      plot = full_outputs$figures$deepening,
      width = 8,
      height = 5,
      dpi = 300,
      bg = "white"
    )
    output_artifacts <- lapply(artifact_specs, function(spec) {
      output_path <- file.path(stage, spec$filename)
      if (!file.exists(output_path)) {
        categorical_gcomp_stop("RESULT_CONTRACT_INVALID", "OUTPUT_BUILD")
      }
      artifact <- list(
        output_id = spec$output_id,
        filename = spec$filename,
        source = spec$source,
        source_result_sha256 = spec$source_result_sha256,
        sha256 = paste0(
          "sha256:",
          categorical_gcomp_output_file_hash(output_path)
        ),
        aggregate_only = TRUE
      )
      if (identical(spec$source, .categorical_gcomp_full_display_source_label)) {
        artifact$display_id <- spec$display_id
        artifact$role <- spec$role
        artifact$scientific_domain <- spec$scientific_domain
        artifact$source_result_id <- spec$source_result_id
      }
      artifact
    })
    manifest <- categorical_gcomp_build_full_output_manifest(
      task,
      result_bundle,
      result_bundle_sha256,
      output_artifacts,
      execution_binding
    )
    validate_categorical_gcomp_full_output_manifest(manifest)
    jsonlite::write_json(
      manifest,
      file.path(stage, "output_manifest.json"),
      auto_unbox = TRUE, pretty = TRUE, null = "null"
    )
    jsonlite::write_json(
      categorical_gcomp_list_to_checksum_map(manifest$artifacts),
      file.path(stage, "artifact_checksums.json"),
      auto_unbox = TRUE, pretty = TRUE, null = "null"
    )
  }

  for (i in seq_along(artifact_specs)) {
    output_path <- file.path(stage, artifact_specs[[i]]$filename)
    if (!file.exists(output_path)) {
      categorical_gcomp_stop("RESULT_CONTRACT_INVALID", "OUTPUT_BUILD")
    }
    artifact_specs[[i]]$sha256 <- paste0(
      "sha256:",
      categorical_gcomp_output_file_hash(output_path)
    )
    if (!is.character(artifact_specs[[i]]$sha256) ||
        !categorical_gcomp_sha256_prefixed(artifact_specs[[i]]$sha256) ||
        !categorical_gcomp_sha256_prefixed(artifact_specs[[i]]$source_result_sha256) ||
        !isTRUE(artifact_specs[[i]]$aggregate_only %||% TRUE) ||
        !categorical_gcomp_safe_basename(artifact_specs[[i]]$filename) ||
        !identical(artifact_specs[[i]]$source_result_sha256, result_bundle_sha256)) {
      categorical_gcomp_stop("RESULT_CONTRACT_INVALID", "OUTPUT_BUILD")
    }
  }

  if (!file.rename(stage, output_dir)) {
    categorical_gcomp_stop("INTERNAL_ERROR", "OUTPUT_COMMIT")
  }
  invisible(output_dir)
}

run_categorical_logistic_g_computation <- function(
  task,
  data,
  output_dir = NULL,
  execution_binding = NULL,
  planned_display_contract = NULL
) {
  tryCatch(
    {
      validate_categorical_gcomp_task(task)
      execution_binding <- categorical_gcomp_validate_execution_authorization_binding(
        execution_binding = execution_binding,
        task = task
      )
      full_profile <- categorical_gcomp_is_full_article_target(task)
      if (full_profile) {
        planned_display_contract <- categorical_gcomp_validate_planned_display_contract(
          planned_display_contract,
          task = task
        )
      }
      bundle <- tryCatch(
        categorical_gcomp_build_bundle(task, data),
        clinanalysis_contract_error = function(e) {
          categorical_gcomp_stop("RESULT_CONTRACT_INVALID", "RESULT_VALIDATION")
        }
      )
      if (!is.null(output_dir)) {
        write_categorical_gcomp_bundle(
          bundle,
          output_dir,
          full_task = full_profile,
          data = data,
          task = task,
          execution_binding = execution_binding,
          planned_display_contract = planned_display_contract
        )
      }
      bundle
    },
    clinanalysis_contract_error = function(e) {
      categorical_gcomp_failure_diagnostic(
        task, "TASK_CONTRACT_INVALID", "TASK_CONTRACT", data
      )
    },
    categorical_gcomp_failure = function(e) {
      categorical_gcomp_failure_diagnostic(task, e$code, e$stage, data)
    },
    error = function(e) {
      categorical_gcomp_failure_diagnostic(task, "INTERNAL_ERROR", "INTERNAL", data)
    }
  )
}
