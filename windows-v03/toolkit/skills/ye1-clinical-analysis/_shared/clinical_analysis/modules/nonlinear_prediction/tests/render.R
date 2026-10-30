args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==3L)
core <- args[[1L]]; module <- args[[2L]]; output <- args[[3L]]
.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
`%||%` <- function(a,b) if(is.null(a))b else a
source(file.path(core,"src/clinanalysis/R/clinical_common.R"),encoding="UTF-8")
source(file.path(core,"src/clinanalysis/R/clinical_prediction_common.R"),encoding="UTF-8")
source(file.path(module,"projection.R"),encoding="UTF-8")
calculated <- common_json_read(file.path(output,"private/response.json"))
request <- common_json_read(file.path(output,"private/request.json"))
task <- list(analysis=list(method_id=request$method_id,prediction=list(operation=request$operation)),
  outcome=list(field=(request$spec %||% request$payload$spec)$outcome),variables=list(list(name=(request$spec %||% request$payload$spec)$outcome,unit="1")))
result <- if(identical(calculated$api_version,"clinical-module-response@1.0"))project_nonlinear_module(calculated,task,output) else project_nonlinear_prediction(calculated,task,output)
jsonlite::write_json(result,file.path(output,"result.json"),auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
stopifnot(result$execution_status=="complete")
cat("SHARED_R_PROJECTION_PASS\n")
