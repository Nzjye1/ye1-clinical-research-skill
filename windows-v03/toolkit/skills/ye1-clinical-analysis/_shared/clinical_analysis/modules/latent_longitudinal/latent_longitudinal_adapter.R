# Thin opt-in adapter. No shared registry or common result schema mutation.
# task$analysis$latent_longitudinal holds the module-private request without rows.
run_latent_longitudinal_module <- function(task, data, output_dir, config) {
  stopifnot(is.list(config),is.character(config$python),is.character(config$module_root))
  if(dir.exists(output_dir)||file.exists(output_dir)) stop("OUTPUT_ALREADY_EXISTS",call.=FALSE)
  options <- task$analysis$latent_longitudinal
  if(is.null(options)) stop("MODULE_OPTIONS_REQUIRED",call.=FALSE)
  request <- options
  request$method_id <- task$analysis$method_id
  request$rows <- lapply(seq_len(nrow(data)),function(i)as.list(data[i,,drop=FALSE]))
  # Transport request lives next to the new output, not in any frozen baseline.
  parent <- dirname(output_dir)
  if(!dir.exists(parent)) dir.create(parent,recursive=TRUE)
  request_file <- tempfile("ll-adapter-request-",tmpdir=parent,fileext=".json")
  jsonlite::write_json(request,request_file,auto_unbox=TRUE,pretty=FALSE,digits=17L,null="null",na="null")
  old <- Sys.getenv("PYTHONDONTWRITEBYTECODE",unset=NA_character_)
  Sys.setenv(PYTHONDONTWRITEBYTECODE="1")
  on.exit(if(is.na(old))Sys.unsetenv("PYTHONDONTWRITEBYTECODE")else Sys.setenv(PYTHONDONTWRITEBYTECODE=old))
  argv <- c("-B",file.path(config$module_root,"module.py"),request_file,output_dir)
  if(!is.null(config$runtime_json)) argv <- c(argv,config$runtime_json)
  captured <- suppressWarnings(system2(config$python,args=vapply(argv,shQuote,character(1)),stdout=TRUE,stderr=TRUE))
  result_file <- file.path(output_dir,"result.json")
  if(!file.exists(result_file)) stop("MODULE_ADAPTER_PROCESS_FAILED",call.=FALSE)
  result <- jsonlite::fromJSON(result_file,simplifyVector=FALSE)
  if(!identical(result$schema_version,"latent-longitudinal-result/1")) stop("MODULE_RESULT_VERSION_INVALID",call.=FALSE)
  if(identical(result$status,"complete")&&!identical(as.integer(attr(captured,"status") %ll_or% 0L),0L))
    stop("MODULE_ADAPTER_STATUS_MISMATCH",call.=FALSE)
  result
}
`%ll_or%` <- function(x,y) if(is.null(x))y else x
