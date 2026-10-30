# No-fit dependency and function-contract probe; existing installed libraries only.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=1L) stop("ONE_OUTPUT_REQUIRED")
script <- sub("^--file=", "", grep("^--file=",commandArgs(),value=TRUE)[[1L]])
root <- normalizePath(file.path(dirname(script),".."),winslash="/",mustWork=TRUE)
out <- normalizePath(args[[1L]],winslash="/",mustWork=FALSE)
if(!startsWith(tolower(out),paste0(tolower(root),"/evidence/"))||file.exists(out)) stop("NEW_LOCAL_EVIDENCE_PATH_REQUIRED")
.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
for(p in c("jsonlite","digest","glmnet","Matrix","survival")) if(!requireNamespace(p,quietly=TRUE)) stop(paste0("DEPENDENCY_UNAVAILABLE_",p))
packages <- c("glmnet","Matrix","survival")
paths <- setNames(lapply(packages,function(p)normalizePath(find.package(p),winslash="/",mustWork=TRUE)),packages)
versions <- c(list(R=as.character(getRversion())),setNames(lapply(packages,function(p)as.character(utils::packageVersion(p))),packages))
hashes <- list()
for(p in packages) for(rel in c("DESCRIPTION",paste0("R/",p),paste0("R/",p,".rdb"),paste0("R/",p,".rdx"),paste0("libs/x64/",p,".dll"))) {
 f <- file.path(paths[[p]],rel);size <- file.info(f)$size
 if(!file.exists(f)||is.na(size)||size>16777216) stop("DEPENDENCY_FILE_UNAVAILABLE")
 hashes[[f]] <- digest::digest(readBin(f,"raw",n=size),algo="sha256",serialize=FALSE)
}
functions <- list(glmnet=glmnet::glmnet,coxnet_deviance=glmnet::coxnet.deviance,
 survfit_coxnet=getFromNamespace("survfit.coxnet","glmnet"),mycoxph=getFromNamespace("mycoxph","glmnet"),
 coxph=survival::coxph,coxph_control=survival::coxph.control,survfit_coxph=getFromNamespace("survfit.coxph","survival"))
observed <- lapply(functions,function(f)list(formals=as.list(names(formals(f))),body=paste(deparse(f),collapse="\n")))
value <- list(status="DEPENDENCIES_LOADABLE_NOT_NUMERICAL_ACCEPTANCE",versions=versions,paths=paths,
 dependency_hashes=hashes,function_contracts=observed,installation_performed=FALSE,system_settings_changed=FALSE)
jsonlite::write_json(value,out,auto_unbox=TRUE,pretty=TRUE,null="null",digits=17)
cat("V10_NO_FIT_DEPENDENCY_PROBE_WRITTEN\n")
