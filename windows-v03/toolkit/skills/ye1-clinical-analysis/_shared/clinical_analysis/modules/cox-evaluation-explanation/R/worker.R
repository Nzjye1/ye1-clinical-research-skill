# Private transport only. The existing v10 infer remains the sole predictor.
args <- commandArgs(trailingOnly=TRUE)
if(!length(args)%in%c(3L,4L))quit(status=2L)
core <- normalizePath(args[[1]],winslash="/",mustWork=TRUE)
.libPaths(readLines(file.path(core,"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
if(.Platform$OS.type=="windows")suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
if(!requireNamespace("jsonlite",quietly=TRUE)||!requireNamespace("digest",quietly=TRUE))quit(status=3L)
source(file.path(core,"src/clinanalysis/R/clinical_common.R"),local=TRUE,encoding="UTF-8")
.clinical_common$root <- core
.clinical_common$runtime <- jsonlite::fromJSON(file.path(core,"runtime-lock.json"),simplifyVector=FALSE)
for(name in c("clinical_resource_budget.R","penalized_v08.R","cox_penalized_v10.R","interpretation_v09.R","clinical_cox_penalized_v10.R"))
  source(file.path(core,"src/clinanalysis/R",name),local=TRUE,encoding="UTF-8")
script <- sub("^--file=","",grep("^--file=",commandArgs(),value=TRUE)[[1]])
source(file.path(dirname(script),"provider.R"),local=TRUE,encoding="UTF-8")
stage <- "request"
response <- tryCatch({
  byte_limit <- if(length(args)==4L)suppressWarnings(as.numeric(args[[4L]])) else clinical_resource_budget()$max_input_bytes
  ce_need(length(byte_limit)==1L&&is.finite(byte_limit)&&byte_limit==floor(byte_limit)&&byte_limit>0&&
    byte_limit<=clinical_resource_profiles()$absolute$max_input_bytes,"RESOURCE_BUDGET_INVALID")
  ce_need(file.info(args[[2L]])$size<=byte_limit,"RESOURCE_INPUT_BUDGET_EXCEEDED")
  request <- jsonlite::fromJSON(args[[2]],simplifyVector=FALSE)
  stage <- "runtime"
  reason <- common_cox_penalized_runtime_reason()
  ce_need(is.null(reason),if(is.null(reason))"CE_RUNTIME_INVALID" else reason)
  ce_need(identical(as.character(utils::packageVersion("jsonlite")),"2.0.0")&&
    identical(as.character(utils::packageVersion("digest")),"0.6.39"),"CE_TRANSPORT_RUNTIME_MISMATCH")
  p <- request$payload;model <- request$wrapper$model
  spec <- model$spec;spec$cohort_id <- p$cohort_id;spec$horizons <- p$horizons
  model_file <- file.path(dirname(args[[3]]),"frozen-model.json")
  writeChar(enc2utf8(p$model_json),model_file,eos=NULL,useBytes=TRUE)
  ce_need(identical(common_sha(model_file),request$bindings$model_sha256),"CE_MODEL_BYTES_MISMATCH")
  options <- list(operation="infer",spec=spec,model_ref=list(local_ref=model_file,content_hash=request$bindings$model_sha256),unknown_category_policy="reject")
  empty <- setNames(list(character()),spec$id)
  if(!is.null(spec$split$group_field))empty[[spec$split$group_field]]<-character()
  stage <- "model_validation"
  cox_penalized_v10_validate_model(model,spec,model$semantics,as.data.frame(empty),cox_penalized_v10_runtime(),resource_budget=request$resource_limits)
  predictions <- encoded <- contributions <- nomogram_rows <- list();explanation <- NULL
  if(request$operation!="fit_explainer") {
    stage <- "data_construction"
    data <- ce_data(p$rows,model)
    stage <- "frozen_inference"
    actual <- cox_penalized_v10_analyze(data,options,model$semantics,frozen_model=model,resource_budget=request$resource_limits)
    ce_need(isTRUE(actual$ok)&&identical(actual$record$status,"completed"),actual$reason_code %ce_or% "CE_FROZEN_INFER_FAILED")
    ce_need(actual$record$diagnostics$n_engine_fits==0L,"CE_REFIT_FORBIDDEN")
    stage <- "private_projection"
    data <- data[order(penalized_v08_key(data[[spec$id]]),method="radix"),,drop=FALSE]
    x <- penalized_v08_prepare(data,spec$features,model$preprocessor,resource_budget=request$resource_limits)$x
    individual <- actual$individual
    predictions <- lapply(seq_len(nrow(individual)),function(i)list(subject_id=individual$subject_id[[i]],horizon=individual$horizon[[i]],
      linear_predictor=individual$linear_predictor[[i]],centered_linear_predictor=individual$centered_linear_predictor[[i]],
      survival_probability=individual$survival[[i]],event_risk=individual$risk[[i]]))
    encoded <- lapply(seq_len(nrow(x)),function(i)list(subject_id=data[[spec$id]][[i]],values=as.list(unname(x[i,]))))
  }
  if(request$operation!="evaluate") {
    stage <- "nomogram"
    nomogram <- ce_nomogram(model,request$domains,p$horizons,resource_budget=request$resource_limits)
    if(request$operation=="fit_explainer") explanation <- list(definition=ce_definition(),base_value=-model$baseline$center,
      global_importance=list(),nomogram=nomogram,checks=ce_checks())
    else {
      stage <- "explanation"
      explained <- ce_explain(data,x,model,nomogram,p$horizons)
      explanation <- explained$record;contributions <- explained$contributions;nomogram_rows <- explained$nomogram_rows
    }
  }
  list(ok=TRUE,reason_code=NULL,predictions=predictions,encoded=encoded,contributions=contributions,
    nomogram_rows=nomogram_rows,explanation=explanation)
},error=function(e) {
  code <- conditionMessage(e)
  if(!grepl("^[A-Z][A-Z0-9_]{0,159}$",code))code<-paste0("CE_R_",toupper(stage),"_FAILED")
  list(ok=FALSE,reason_code=code)
})
jsonlite::write_json(response,args[[3]],auto_unbox=TRUE,null="null",na="null",digits=17,pretty=FALSE)
