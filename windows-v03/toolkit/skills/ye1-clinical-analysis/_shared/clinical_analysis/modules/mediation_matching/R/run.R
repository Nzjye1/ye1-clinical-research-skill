args <- commandArgs(trailingOnly=TRUE)
if(!length(args)%in%c(4L,5L))stop("MM_RUN_ARGUMENTS_INVALID",call.=FALSE)
module <- normalizePath(args[1],winslash="/",mustWork=TRUE)
if(.Platform$OS.type=="windows")suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
.libPaths(readLines(file.path(args[[4]],"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
source(file.path(module,"R/provider.R"),encoding="UTF-8")
source(file.path(module,"R/adapter.R"),encoding="UTF-8")
spec_path <- args[2]; out <- normalizePath(args[3],winslash="/",mustWork=TRUE); base <- args[4]
if(is.null(getOption("clinanalysis.resource_profile_file",NULL)))options(clinanalysis.resource_profile_file=file.path(base,"config/resource-budget-profiles.json"))
mm_need(startsWith(tolower(out),paste0(tolower(module),"/")),"MM_DEV_OUTPUT_OUTSIDE_MODULE")
spec <- jsonlite::fromJSON(spec_path,simplifyVector=FALSE)
inp <- file.path(out,"private","canonical.csv")
d <- utils::read.csv(inp,colClasses="character",check.names=FALSE,stringsAsFactors=FALSE,na.strings="",fileEncoding="UTF-8")
categories <- if(spec$method_id==mm_methods[1])character() else names(spec$options$categorical)
numeric_fields <- setdiff(names(d),c(spec$fields$subject,categories))
for(n in numeric_fields) {
  raw <- d[[n]]; parsed <- suppressWarnings(as.numeric(raw))
  mm_need(!any(!is.na(raw)&is.na(parsed)),"MM_NONNUMERIC_CELL")
  d[[n]] <- parsed
}
resource_budget <- if(length(args)==5L)jsonlite::fromJSON(args[[5L]],simplifyVector=FALSE) else NULL
value <- mm_analyze(d,spec,base,resource_budget)
source_binding <- jsonlite::fromJSON(file.path(out,"private","source-binding.json"),simplifyVector=FALSE)
rec <- mm_write_bundle(value,out,c(source_binding,list(input_sha256=mm_hash_file(inp),spec_sha256=mm_hash_file(spec_path),
  provider_sha256=mm_hash_file(file.path(module,"R/provider.R")),adapter_sha256=mm_hash_file(file.path(module,"R/adapter.R")),
  R=as.character(getRversion()),stats=as.character(utils::packageVersion("stats")),
  survival=if(spec$method_id==mm_methods[3]&&"survival"%in%loadedNamespaces())as.character(utils::packageVersion("survival")) else NULL)))
cat(jsonlite::toJSON(list(status=rec$status,reason_code=rec$reason_code,method_id=rec$method_id),auto_unbox=TRUE,null="null"),"\n")
