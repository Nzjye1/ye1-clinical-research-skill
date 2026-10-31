# Harmless, bounded, process-local dependency probe. Never installs or fits.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=1L) stop("ONE_OUTPUT_PATH_REQUIRED")
script <- sub("^--file=", "", grep("^--file=",commandArgs(),value=TRUE)[[1L]])
root <- normalizePath(file.path(dirname(script),".."),winslash="/",mustWork=TRUE)
out <- normalizePath(args[[1L]],winslash="/",mustWork=FALSE)
if(!startsWith(tolower(out),paste0(tolower(root),"/evidence/"))||file.exists(out)) stop("NEW_LOCAL_EVIDENCE_PATH_REQUIRED")
.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
for(p in c("jsonlite","digest","glmnet","Matrix")) if(!requireNamespace(p,quietly=TRUE)) stop(paste0("DEPENDENCY_UNAVAILABLE_",p))
paths <- setNames(lapply(c("glmnet","Matrix"),function(p)normalizePath(find.package(p),winslash="/",mustWork=TRUE)),c("glmnet","Matrix"))
versions <- list(R=as.character(getRversion()),glmnet=as.character(utils::packageVersion("glmnet")),Matrix=as.character(utils::packageVersion("Matrix")))
hashes <- list()
for(p in names(paths)) for(rel in c("DESCRIPTION",paste0("R/",p),paste0("R/",p,".rdb"),paste0("R/",p,".rdx"),if(.Platform$OS.type=="windows")paste0("libs/x64/",p,".dll") else paste0("libs/",p,".so"))) {
  f <- file.path(paths[[p]],rel);size <- file.info(f)$size
  if(!file.exists(f)||is.na(size)||size>8388608) stop("DEPENDENCY_FILE_UNAVAILABLE")
  hashes[[f]] <- digest::digest(readBin(f,"raw",n=size),algo="sha256",serialize=FALSE)
}
value <- list(status="DEPENDENCIES_LOADABLE_NOT_NUMERICAL_ACCEPTANCE",versions=versions,paths=paths,
  dependency_hashes=hashes,glmnet_formal_names=as.list(names(formals(glmnet::glmnet))),
  glmnet_control_formal_names=as.list(names(formals(glmnet::glmnet.control))),
  installation_performed=FALSE,system_settings_changed=FALSE)
jsonlite::write_json(value,out,auto_unbox=TRUE,pretty=TRUE,null="null",digits=NA)
cat("V08_DEPENDENCY_PROBE_WRITTEN\n")
