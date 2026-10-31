# Private numerical transport. It never calls the synthetic-only API/projector.
args <- commandArgs(trailingOnly=TRUE)
if(length(args)!=4L)stop("MM_REAL_TRANSPORT_ARGUMENTS_INVALID",call.=FALSE)
script <- sub("^--file=","",grep("^--file=",commandArgs(),value=TRUE)[[1L]])
if (.Platform$OS.type != "windows" && !file.exists(script)) script <- gsub("~+~", " ", script, fixed=TRUE)
module <- normalizePath(file.path(dirname(script),".."),winslash="/",mustWork=TRUE)
core <- normalizePath(args[[1L]],winslash="/",mustWork=TRUE)
if(is.null(getOption("clinanalysis.resource_profile_file",NULL)))options(clinanalysis.resource_profile_file=file.path(core,"config/resource-budget-profiles.json"))
.libPaths(readLines(file.path(core,"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
stopifnot(requireNamespace("jsonlite",quietly=TRUE),requireNamespace("digest",quietly=TRUE))
source(file.path(module,"R/provider.R"),local=TRUE,encoding="UTF-8")
mm_need(identical(mm_hash_file(args[[2L]]),args[[4L]]),"MM_REAL_REQUEST_BYTES_CHANGED")
mm_need(identical(as.character(getRversion()),"4.6.1")&&identical(as.character(packageVersion("stats")),"4.6.1")&&
        identical(as.character(packageVersion("jsonlite")),"2.0.0")&&identical(as.character(packageVersion("digest")),"0.6.39"),"MM_REAL_RUNTIME_MISMATCH")
request <- jsonlite::fromJSON(args[[2L]],simplifyVector=FALSE)
p <- request$payload;s <- p$spec;fs <- s$fields;cv <- mm_vec(s$covariates);rows <- p$rows
mm_need(request$method_id%in%mm_methods&&identical(request$operation,"analyze")&&identical(request$method_id,s$method_id),"MM_REAL_METHOD_INVALID")
mm_need(is.null(s$execution),"MM_REAL_CONTEXT_METADATA_MUST_NOT_BE_PAYLOAD")
if(request$method_id==mm_methods[[3L]])mm_need(requireNamespace("survival",quietly=TRUE)&&identical(as.character(packageVersion("survival")),"3.8.6"),"MM_REAL_SURVIVAL_RUNTIME_MISMATCH")
d <- data.frame(stringsAsFactors=FALSE)
for(role in names(fs))if(!is.null(fs[[role]])) {
  key <- if(role=="subject")"subject_id" else role
  values <- if(role=="subject")vapply(rows,`[[`,"",key) else vapply(rows,function(r)if(is.null(r[[key]]))NA_real_ else r[[key]],0.0)
  if(ncol(d)==0)d <- data.frame(values,stringsAsFactors=FALSE) else d[[fs[[role]]]] <- values
  if(ncol(d)==1)names(d)[[1L]] <- fs[[role]]
}
categories <- names(s$options$categorical)
for(j in seq_along(cv))d[[cv[[j]]]] <- if(cv[[j]]%in%categories)vapply(rows,function(r)if(is.null(r$covariates[[j]]))NA_character_ else r$covariates[[j]],"") else
  vapply(rows,function(r)if(is.null(r$covariates[[j]]))NA_real_ else r$covariates[[j]],0.0)
d <- d[order(mm_utf8(d[[fs$subject]]),method="radix"),,drop=FALSE];rownames(d) <- NULL
# Initialize only numerical contract fields. No synthetic-only metadata is made
# and subsequently relabelled; V1 provenance is supplied separately by the root.
rec <- list(method_id=s$method_id,status="unavailable",reason_code="NOT_RUN",causal_assumptions_verified=FALSE,
  semantics=s$semantics,options=s$options,counts=mm_object(),effects=list(),diagnostics=mm_object(),warnings=list(),
  limitations=list("IDENTIFICATION_ASSUMPTIONS_UNVERIFIED","ROOT_ADMITTED_INPUT_NOT_CLINICAL_OR_CAUSAL_CERTIFICATION"))
budget <- clinical_resource_budget(request$resource_budget,s$method_id)
clinical_resource_check_rows(nrow(d),budget)
if(s$method_id!=mm_methods[[1L]])clinical_resource_check_pairs(sum(d[[fs$exposure]]==1),sum(d[[fs$exposure]]==0),budget)
value <- if(s$method_id==mm_methods[[1L]])mm_med_analyze(d,s,rec) else mm_match_analyze(d,s,rec,core,request$resource_budget)
out <- list(public_record=value$record,private_record=list(format="R_serialize_v3_base64",media_type="application/x-r-serialized",
  blob=jsonlite::base64_enc(serialize(value$private,NULL,version=3))))
mm_need(!file.exists(args[[3L]]),"MM_REAL_RESPONSE_EXISTS")
jsonlite::write_json(out,args[[3L]],auto_unbox=TRUE,pretty=TRUE,digits=17,null="null",na="null")
cat("MM_REAL_NUMERICAL_TRANSPORT_COMPLETE\n")
