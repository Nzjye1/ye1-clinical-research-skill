.clinanalysis_plugins <- new.env(parent = emptyenv())
.clinanalysis_task_contracts <- new.env(parent = emptyenv())
.clinanalysis_result_contracts <- new.env(parent = emptyenv())

#' Register a deterministic analysis plugin
#'
#' @param name Stable method identifier.
#' @param plugin Function accepting `(task, data, output_dir)`.
#' @export
register_analysis_plugin <- function(name, plugin) {
  stopifnot(is.character(name), length(name) == 1L, nzchar(name), is.function(plugin))
  assign(name, plugin, envir = .clinanalysis_plugins)
  invisible(name)
}

#' List registered analysis plugins
#'
#' @export
analysis_plugin_registry <- function() {
  as.list.environment(.clinanalysis_plugins, all.names = TRUE)
}

get_analysis_plugin <- function(name) {
  if (!exists(name, envir = .clinanalysis_plugins, inherits = FALSE)) {
    stop(contract_error(sprintf("Unregistered analysis method '%s'", name)))
  }
  get(name, envir = .clinanalysis_plugins, inherits = FALSE)
}

#' Register a versioned runtime task contract
#'
#' @param schema_version Exact task schema version.
#' @param validator Function accepting one object and raising a contract error
#'   when the task is not safe to execute.
#' @export
register_task_contract <- function(schema_version, validator) {
  stopifnot(
    is.character(schema_version), length(schema_version) == 1L,
    nzchar(schema_version), is.function(validator)
  )
  assign(schema_version, validator, envir = .clinanalysis_task_contracts)
  invisible(schema_version)
}

#' List registered runtime task contracts
#'
#' @export
task_contract_registry <- function() {
  as.list.environment(.clinanalysis_task_contracts, all.names = TRUE)
}

#' Validate an object with its registered runtime task contract
#'
#' @param object Task object containing schema_version.
#' @return Invisibly returns TRUE or raises a contract error.
#' @export
validate_registered_task_contract <- function(object) {
  version <- if (is.list(object)) object$schema_version else NULL
  if (!is.character(version) || length(version) != 1L || !nzchar(version)) {
    stop(contract_error("A registered task schema_version is required"))
  }
  if (!exists(version, envir = .clinanalysis_task_contracts, inherits = FALSE)) {
    stop(contract_error(sprintf("Unregistered task contract '%s'", version)))
  }
  get(version, envir = .clinanalysis_task_contracts, inherits = FALSE)(object)
}

#' Register a versioned runtime result contract
#'
#' @param schema_version Exact structured-result or bundle-manifest version.
#' @param validator Function accepting one object and raising a contract error
#'   when it is not safe to write.
#' @export
register_result_contract <- function(schema_version, validator) {
  stopifnot(
    is.character(schema_version), length(schema_version) == 1L,
    nzchar(schema_version), is.function(validator)
  )
  assign(schema_version, validator, envir = .clinanalysis_result_contracts)
  invisible(schema_version)
}

#' List registered runtime result contracts
#'
#' @export
result_contract_registry <- function() {
  as.list.environment(.clinanalysis_result_contracts, all.names = TRUE)
}

#' Validate an object with its registered runtime result contract
#'
#' @param object Structured result or output manifest containing schema_version.
#' @return Invisibly returns TRUE or raises a contract error.
#' @export
validate_registered_result_contract <- function(object) {
  version <- if (is.list(object)) object$schema_version else NULL
  if (!is.character(version) || length(version) != 1L || !nzchar(version)) {
    stop(contract_error("A registered result schema_version is required before write-out"))
  }
  if (!exists(version, envir = .clinanalysis_result_contracts, inherits = FALSE)) {
    stop(contract_error(sprintf("Unregistered result contract '%s'", version)))
  }
  get(version, envir = .clinanalysis_result_contracts, inherits = FALSE)(object)
}
