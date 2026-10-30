# Private transport only. Public entry remains clinanalysis::run_analysis_task.
if(.Platform$OS.type=="windows") {
  suppressWarnings(Sys.setlocale("LC_CTYPE",""))
  if(!isTRUE(l10n_info()[["UTF-8"]])) suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
}
args <- commandArgs(trailingOnly=TRUE);Encoding(args)<-"UTF-8"
if(length(args)!=7L)stop("MODULE_TRANSPORT_ARGUMENTS_REQUIRED",call.=FALSE)
mode<-args[[1]];module<-args[[2]];core<-args[[3]];request_path<-args[[4]];response_path<-args[[5]];output<-args[[6]];context_path<-args[[7]]
.libPaths(readLines(file.path(core,"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
if(!requireNamespace("jsonlite",quietly=TRUE))stop("MODULE_JSON_DEPENDENCY_MISSING",call.=FALSE)
runtime<-jsonlite::fromJSON(file.path(core,"runtime-lock.json"),simplifyVector=FALSE)
.libPaths(unlist(runtime$r_libraries,use.names=FALSE))
manifest<-jsonlite::fromJSON(file.path(module,"integration-request.json"),simplifyVector=FALSE)
request<-jsonlite::fromJSON(request_path,simplifyVector=FALSE)
context<-jsonlite::fromJSON(context_path,simplifyVector=FALSE)
if(mode=="analyze") {
  if(manifest$module_id!="mediation_matching")stop("MODULE_R_ENTRY_NOT_INTEGRATED",call.=FALSE)
  env<-new.env(parent=.GlobalEnv)
  source(file.path(module,manifest$entrypoint$path),local=env,encoding="UTF-8")
  env$.mm_baseline_root<-core
  for(dep in manifest$dependencies) if(dep$name%in%c("stats","survival","jsonlite","digest")) {
    if(!requireNamespace(dep$name,quietly=TRUE)||as.character(packageVersion(dep$name))!=dep$version)stop("MODULE_R_DEPENDENCY_DRIFT",call.=FALSE)
  }
  response<-env[[manifest$entrypoint[["function"]]]](request)
  jsonlite::write_json(response,response_path,auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
} else if(mode=="project") {
  response<-jsonlite::fromJSON(response_path,simplifyVector=FALSE)
  if(!isTRUE(response$ok))stop("MODULE_PROJECTION_REQUIRES_SUCCESS",call.=FALSE)
  if(manifest$module_id=="mediation_matching") {
    env<-new.env(parent=.GlobalEnv)
    source(file.path(module,manifest$projection_entrypoint$path),local=env,encoding="UTF-8")
    env$.mm_baseline_root<-core
    env[[manifest$projection_entrypoint[["function"]]]](response,output,list(result_id=context$result_id,binding=context$binding))
  } else if(manifest$module_id=="nonlinear_prediction") {
    for(f in sort(list.files(file.path(core,"src/clinanalysis/R"),pattern="\\.R$",full.names=TRUE)))sys.source(f,envir=.GlobalEnv)
    source(file.path(module,manifest$projection_entrypoint$path),local=.GlobalEnv,encoding="UTF-8")
    dir.create(output,recursive=FALSE,showWarnings=FALSE)
    for(p in c("tables","figures","private"))dir.create(file.path(output,p),showWarnings=FALSE)
    task<-list(analysis=list(method_id=request$method_id,prediction=list(operation=request$operation,spec=request$payload$spec),ci_level=.95))
    if(!is.null(context$origin_context)) task$study_id<-context$task$study_id
    result<-if(is.null(context$origin_context)) get(manifest$projection_entrypoint[["function"]])(response,task,output,context$result_id) else
      get(manifest$projection_entrypoint[["function"]])(response,task,output,context$result_id,origin_context=context$origin_context)
    jsonlite::write_json(result,file.path(output,"projection-result.json"),auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
  } else stop("MODULE_R_PROJECTION_NOT_INTEGRATED",call.=FALSE)
} else stop("MODULE_TRANSPORT_MODE_INVALID",call.=FALSE)
cat("MODULE_TRANSPORT_COMPLETE\n")
