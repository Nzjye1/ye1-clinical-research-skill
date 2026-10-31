# Native private aggregate projection. No estimation or private-model decoding.
if(.Platform$OS.type=="windows") {
  suppressWarnings(Sys.setlocale("LC_CTYPE",""))
  if(!isTRUE(l10n_info()[["UTF-8"]]))suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
}
args <- commandArgs(trailingOnly=TRUE)
Encoding(args)<-"UTF-8"
if(length(args)!=4L)stop("MM_REAL_PROJECT_ARGUMENTS_INVALID",call.=FALSE)
script <- sub("^--file=","",grep("^--file=",commandArgs(),value=TRUE)[[1L]])
if (.Platform$OS.type != "windows" && !file.exists(script)) script <- gsub("~+~", " ", script, fixed=TRUE)
module <- normalizePath(file.path(dirname(script),".."),winslash="/",mustWork=TRUE)
core <- normalizePath(args[[1L]],winslash="/",mustWork=TRUE)
.libPaths(readLines(file.path(core,"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
stopifnot(requireNamespace("jsonlite",quietly=TRUE),requireNamespace("digest",quietly=TRUE))
source(file.path(module,"R/provider.R"),local=TRUE,encoding="UTF-8")
source(file.path(module,"R/adapter.R"),local=TRUE,encoding="UTF-8")
mm_need("disclosure_label"%in%names(formals(mm_effect_plot))&&"disclosure_label"%in%names(formals(mm_risk_plot)),"MM_REAL_SOURCE_AWARE_PLOT_API_REQUIRED")
mm_need(identical(mm_hash_file(args[[2L]]),args[[4L]]),"MM_REAL_PROJECTION_REQUEST_CHANGED")
wire <- jsonlite::fromJSON(args[[2L]],simplifyVector=FALSE);rec <- wire$public_record;meta <- wire$provenance
mm_need(mm_keys(wire,c("public_record","provenance","disclosure_label","source_public_record_sha256")),"MM_REAL_PROJECT_WIRE_INVALID")
# JSON null means the existing numeric owner's NA, not a new estimate. Restore
# declared nullable numeric types for the unchanged vapply-based plot helpers.
for(i in seq_along(rec$effects))for(name in c("estimate","standard_error","ci_lower","ci_upper","p_value","df"))
  if(is.null(rec$effects[[i]][[name]]))rec$effects[[i]][[name]]<-NA_real_
mm_need(meta$data_origin%in%c("real","synthetic")&&meta$task_purpose%in%c("engineering_test","research_analysis")&&identical(meta$scientific_review,"pending"),"MM_REAL_PROJECT_METADATA_INVALID")
# The parent supplied exact UTF-8 wire is also the canonical Python hash source.
# Do not reconstruct a Python JSON hash through a different R serializer.
label <- wire$disclosure_label
mm_need(identical(label,paste0(toupper(meta$data_origin)," | ",meta$task_purpose," | review=pending")),"MM_REAL_PROJECT_LABEL_BINDING_INVALID")
output <- args[[3L]];mm_need(!dir.exists(output)&&!file.exists(output),"MM_REAL_PROJECT_OUTPUT_EXISTS")
dir.create(output,recursive=FALSE)
for(folder in c("tables","figures","reports","private"))dir.create(file.path(output,folder))
datasets <- list(effects=rec$effects,flow=list(rec$counts))
if(length(rec$diagnostics$balance))datasets$balance <- rec$diagnostics$balance
if(length(rec$diagnostics$overlap))datasets$overlap <- rec$diagnostics$overlap
if(length(rec$diagnostics$outcome$risk_table))datasets$risk <- rec$diagnostics$outcome$risk_table
artifacts <- list();errors <- list();layout <- list()
add <- function(path,kind) {
  relative <- substring(normalizePath(path,winslash="/",mustWork=TRUE),nchar(normalizePath(output,winslash="/",mustWork=TRUE))+2L)
  artifacts[[length(artifacts)+1L]] <<- list(relative_path=relative,kind=kind,sha256=mm_hash_file(path),bytes=unname(file.info(path)$size))
}
for(name in names(datasets)) {
  path <- file.path(output,"tables",paste0(name,".csv"));mm_csv(datasets[[name]],path);add(path,"table")
}
path <- file.path(output,"figures/effects.png")
tryCatch({layout$effects<-mm_effect_plot(rec,path,disclosure_label=label);add(path,"figure")},error=function(e)errors[[length(errors)+1L]]<<-"MM_REAL_EFFECT_FIGURE_FAILED")
if(length(rec$diagnostics$outcome$risk_table)) {
  path <- file.path(output,"figures/risk.png")
  tryCatch({mm_risk_plot(rec,path,disclosure_label=label);add(path,"figure")},error=function(e)errors[[length(errors)+1L]]<<-"MM_REAL_RISK_FIGURE_FAILED")
}
report <- c(label,"","Native aggregate module projection; global CSV metadata, file manifest and PNG provenance are added by the root.",
  "No new estimation, fitting, calibration or causal/scientific certification occurs here.",
  "Effect n and n_semantics remain effect-specific; complete cases, formed matched pairs and at-risk counts are distinct denominators.",
  "Paired risk difference uses sample variance of pair differences; conditional matched OR is not a marginal OR or risk ratio.",
  "Matched Cox uses pooled risk sets, Efron ties, pair-cluster sandwich variance and log-HR standard errors; PH and censoring assumptions remain unverified.",
  "Unavailable/unbounded intervals are retained and labelled by the original plotting owner.","",unlist(rec$limitations,use.names=FALSE))
path <- file.path(output,"reports/REPORT.md");writeLines(enc2utf8(report),path,useBytes=TRUE);add(path,"report")
jsonlite::write_json(list(disclosure_label=label,effects_layout=layout$effects),file.path(output,"private/layout-evidence.json"),auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
result <- list(status=if(length(errors))"partial" else "complete",reason_codes=errors,provenance=meta,
  numerical_execution_count=0L,artifacts=artifacts,root_global_provenance="ROOT_OWNED_NOT_ADDED_BY_MODULE")
# The response record hash is supplied separately without exposing private rows.
result$source_public_record_sha256 <- wire$source_public_record_sha256
jsonlite::write_json(result,file.path(output,"projection-manifest.json"),auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
cat("MM_REAL_PRIVATE_PROJECTION_COMPLETE\n")
