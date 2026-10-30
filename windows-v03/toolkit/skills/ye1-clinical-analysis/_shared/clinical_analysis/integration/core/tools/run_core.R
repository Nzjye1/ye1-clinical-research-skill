# Development bootstrap; one entry: clinanalysis run_analysis_task(). No install.
# Process-local encoding only; no OS locale, registry or environment settings.
if(.Platform$OS.type=="windows") {
  # Reuse the already reviewed build2 worker preamble: native UTF-8 first,
  # .UTF-8 only as a current-process fallback. No other locale categories.
  native_ctype <- suppressWarnings(Sys.setlocale("LC_CTYPE",""))
  if(!nzchar(native_ctype)||!isTRUE(l10n_info()[["UTF-8"]])) native_ctype <- suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
  if(!nzchar(native_ctype)||!isTRUE(l10n_info()[["UTF-8"]])) {cat("UTF8_PROCESS_LOCALE_UNAVAILABLE\n");quit(status=2)}
}
args <- commandArgs(trailingOnly=TRUE)
Encoding(args) <- "UTF-8"
script <- sub("^--file=", "", grep("^--file=",commandArgs(),value=TRUE)[[1L]])
Encoding(script) <- "UTF-8"
root <- normalizePath(file.path(dirname(script),".."),winslash="/",mustWork=TRUE)
lockpath <- file.path(root,"runtime-lock.json")
if(length(args)!=2L || !file.exists(lockpath)) {cat("RUNTIME_LOCK_OR_ARGUMENTS_REQUIRED\n");quit(status=2)}
# Fixed read-only library paths are bootstrapped before reading the JSON lock.
.libPaths(readLines(file.path(root,"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
if(!requireNamespace("jsonlite",quietly=TRUE)||!requireNamespace("digest",quietly=TRUE)) {cat("R_DEPENDENCY_UNAVAILABLE\n");quit(status=2)}
runtime <- jsonlite::fromJSON(lockpath,simplifyVector=FALSE)
.libPaths(unlist(runtime$r_libraries,use.names=FALSE))
for(f in sort(list.files(file.path(root,"src/clinanalysis/R"),pattern="\\.R$",full.names=TRUE))) sys.source(f,envir=.GlobalEnv)
.onLoad(NULL,NULL)
register_clinical_common(root,runtime)
options(clinanalysis.common_cli_only=TRUE)
status <- tryCatch({
  result <- run_analysis_task(args[[1L]],output_dir=args[[2L]])
  cat(paste0("CORE_STATUS ",result$execution_status," ",result$reason_code %||% "OK","\n"))
  0L
},error=function(e) {
  code <- conditionMessage(e)
  if(!grepl("^[A-Z][A-Z0-9_]+$",code)) code <- "TASK_OR_RUNTIME_INVALID"
  cat(paste0("CORE_REJECTED ",code,"\n"));2L
})
quit(status=status)
