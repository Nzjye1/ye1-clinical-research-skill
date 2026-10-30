# Shared private module interface. Sources one numerical owner; no registration.
.mm_entry_file <- sys.frame(1)$ofile
if(is.null(.mm_entry_file))stop("MM_SOURCE_PATH_REQUIRED",call.=FALSE)
.mm_module_root <- normalizePath(file.path(dirname(.mm_entry_file),".."),winslash="/",mustWork=TRUE)
source(file.path(.mm_module_root,"R/provider.R"),local=TRUE,encoding="UTF-8")
source(file.path(.mm_module_root,"R/adapter.R"),local=TRUE,encoding="UTF-8")
.mm_baseline_root <- normalizePath(file.path(.mm_module_root,"..","..","integration","core"),winslash="/",mustWork=TRUE)
if(is.null(getOption("clinanalysis.resource_profile_file",NULL)))options(clinanalysis.resource_profile_file=file.path(.mm_baseline_root,"config/resource-budget-profiles.json"))

mm_api_diagnostics <- function(stage,status="unavailable") list(module_id="mediation_matching",stage=stage,
  numerical_owner="R/provider.R",status=status,causal_assumptions_verified=FALSE)

mm_payload_data <- function(p,method,resource_budget=NULL) {
  mm_need(mm_keys(p,c("spec","structure","variables","rows")),"MM_PAYLOAD_KEYS_INVALID")
  s<-p$spec;fs<-s$fields;z<-s$semantics;cv<-mm_vec(s$covariates)
  mm_need(identical(s$method_id,method),"MM_PAYLOAD_METHOD_MISMATCH")
  st<-p$structure
  mm_need(mm_keys(st,c("grain","subject_key","record_keys","cluster_key","weights","missingness","time_origin","time_unit","analysis_as_of")),"MM_STRUCTURE_KEYS_INVALID")
  mm_need(identical(st$grain,"subject_wide")&&identical(st$subject_key,fs$subject)&&
    identical(mm_vec(st$record_keys),fs$subject)&&is.null(st$cluster_key)&&identical(st$weights,"none")&&
    identical(st$missingness,s$options$missingness),"MM_STRUCTURE_UNSUPPORTED")
  mm_need(mm_num(st$time_origin)&&st$time_origin==z$exposure_time&&identical(st$time_unit,z$time_unit)&&
    mm_num(st$analysis_as_of)&&st$analysis_as_of>st$time_origin,"MM_STRUCTURE_TIME_INVALID")
  vars<-p$variables;rows<-p$rows
  mm_need(is.list(vars)&&is.list(rows)&&length(rows)>0,"MM_PAYLOAD_DATA_INVALID")
  budget<-clinical_resource_budget(resource_budget,method)
  clinical_resource_check_rows(length(rows),budget)
  used<-c(mm_vec(Filter(Negate(is.null),fs)),cv)
  mm_need(length(vars)==length(used)&&all(vapply(vars,function(v)mm_keys(v,c("name","dtype","role","unit","time_role","measured_at","available_at")),TRUE)),"MM_VARIABLE_KEYS_INVALID")
  vnames<-vapply(vars,function(v)if(mm_text(v$name))v$name else "","")
  mm_need(!anyDuplicated(vnames)&&setequal(vnames,used),"MM_VARIABLE_SET_MISMATCH")
  categories<-if(method==mm_methods[1])character() else names(s$options$categorical)
  for(v in vars) {
    name<-v$name;role<-if(name%in%cv)"covariate" else names(fs)[match(name,vapply(fs,function(x)if(is.null(x))"" else x,""))]
    dtype<-if(role=="subject")"id" else if(name%in%categories)"category" else "number"
    tr<-switch(role,subject="identifier",exposure="exposure",covariate="baseline",mediator="mediator",outcome="outcome",time="followup_duration",event="event_at_followup")
    mm_need(identical(v$role,role)&&identical(v$dtype,dtype)&&identical(v$time_role,tr)&&mm_text(v$unit),"MM_VARIABLE_ROLE_TYPE_MISMATCH")
    if(role%in%c("exposure","event")||(role=="outcome"&&method==mm_methods[2]))mm_need(identical(v$unit,"1"),"MM_VARIABLE_UNIT_MISMATCH")
    if(role=="time")mm_need(identical(v$unit,z$time_unit),"MM_VARIABLE_UNIT_MISMATCH")
    if(role=="outcome")mm_need(identical(v$unit,z$outcome_unit),"MM_VARIABLE_UNIT_MISMATCH")
    if(role%in%c("subject","time","event")) mm_need(is.null(v$measured_at)&&is.null(v$available_at),"MM_VARIABLE_TIME_INVALID")
    else {
      mm_need(mm_num(v$measured_at)&&mm_num(v$available_at)&&v$measured_at<=v$available_at&&v$available_at<=st$analysis_as_of,"MM_VARIABLE_AVAILABILITY_INVALID")
      if(role=="covariate")mm_need(v$available_at<=z$covariate_latest_time,"MM_PRETREATMENT_COVARIATES_REQUIRED")
      else {
        target<-switch(role,exposure=z$exposure_time,mediator=z$mediator_time,outcome=z$outcome_time)
        mm_need(mm_num(target)&&v$measured_at==target,"MM_VARIABLE_TIME_INVALID")
        if(role=="exposure")mm_need(v$available_at==target,"MM_EXPOSURE_TIMING_INVALID")
        if(role=="mediator")mm_need(v$available_at<z$outcome_time,"MM_MEDIATOR_AVAILABILITY_INVALID")
      }
    }
  }
  for(row in rows) {
    mm_need(mm_keys(row,c("subject_id","exposure","mediator","outcome","time","event","covariates")),"MM_ROW_KEYS_INVALID")
    mm_need(mm_text(row$subject_id)&&mm_num(row$exposure)&&length(row$covariates)==length(cv)&&is.list(row$covariates),"MM_ROW_VALUES_INVALID")
    for(n in c("mediator","outcome","time","event")) {
      val<-row[[n]]
      mm_need(if(is.null(fs[[n]]))is.null(val) else is.null(val)||mm_num(val),"MM_ROW_ENDPOINT_INVALID")
    }
    if(method==mm_methods[3])mm_need(mm_num(row$time)&&row$time+st$time_origin<=st$analysis_as_of,"MM_FOLLOWUP_NOT_MATURE")
    for(j in seq_along(cv)) {
      val<-row$covariates[[j]]
      mm_need(is.null(val)||if(cv[j]%in%categories)mm_text(val) else mm_num(val),"MM_ROW_COVARIATE_INVALID")
    }
  }
  d<-data.frame(stringsAsFactors=FALSE)
  for(role in names(fs))if(!is.null(fs[[role]])) {
    key<-if(role=="subject")"subject_id" else role
    value<-if(role=="subject")vapply(rows,`[[`,"",key) else vapply(rows,function(r)if(is.null(r[[key]]))NA_real_ else r[[key]],0.0)
    if(ncol(d)==0)d<-data.frame(value,stringsAsFactors=FALSE) else d[[fs[[role]]]]<-value
    if(ncol(d)==1)names(d)[1]<-fs[[role]]
  }
  for(j in seq_along(cv)) d[[cv[j]]]<-if(cv[j]%in%categories)vapply(rows,function(r)if(is.null(r$covariates[[j]]))NA_character_ else r$covariates[[j]],"") else
    vapply(rows,function(r)if(is.null(r$covariates[[j]]))NA_real_ else r$covariates[[j]],0.0)
  mm_validate(d,s,resource_budget)
  d
}

analyze <- function(request,resource_budget=NULL) {
  stage<-"request_contract"
  tryCatch({
    mm_need(mm_keys(request,c("api_version","method_id","operation","payload","bindings")),"MM_REQUEST_KEYS_INVALID")
    mm_need(identical(request$api_version,"clinical-module-request@1.0"),"MM_API_VERSION_UNSUPPORTED")
    mm_need(mm_text(request$method_id)&&request$method_id%in%mm_methods,"MM_METHOD_UNSUPPORTED")
    mm_need(identical(request$operation,"analyze"),"MM_OPERATION_UNSUPPORTED")
    bn<-request$bindings
    mm_need(mm_keys(bn,c("input_sha256","plan_sha256","code_sha256","runtime_sha256","model_sha256"))&&
      all(vapply(bn[c("input_sha256","plan_sha256","code_sha256","runtime_sha256")],function(x)mm_text(x)&&grepl("^[0-9a-f]{64}$",x),TRUE))&&is.null(bn$model_sha256),"MM_BINDINGS_INVALID")
    schemas<-file.path(.mm_module_root,"contracts",c("payload.schema.json","diagnostics.schema.json","public_record.schema.json","private_record.schema.json"))
    mm_need(all(file.exists(schemas)),"MM_METHOD_SCHEMA_MISSING")
    stage<-"payload_contract";d<-mm_payload_data(request$payload,request$method_id,resource_budget)
    stage<-"analysis";v<-mm_analyze(d,request$payload$spec,.mm_baseline_root,resource_budget)
    if(v$record$status=="unavailable")return(list(api_version="clinical-module-response@1.0",ok=FALSE,reason_code=v$record$reason_code,
      diagnostics=mm_api_diagnostics(stage),public_record=NULL,private_record=NULL))
    pub<-v$record;pub$schema_version<-NULL
    list(api_version="clinical-module-response@1.0",ok=TRUE,reason_code=NULL,
      diagnostics=mm_api_diagnostics(stage,pub$status),public_record=pub,
      private_record=list(format="R_serialize_v3_base64",media_type="application/x-r-serialized",
        blob=jsonlite::base64_enc(serialize(v$private,NULL,version=3))))
  },error=function(e)list(api_version="clinical-module-response@1.0",ok=FALSE,
    reason_code=if(inherits(e,"mm_blocked")||inherits(e,"clinical_resource_blocked"))conditionMessage(e) else "MM_API_EXECUTION_FAILED",
    diagnostics=mm_api_diagnostics(stage),public_record=NULL,private_record=NULL))
}

project <- function(response,output_dir,context) {
  mm_need(mm_keys(response,c("api_version","ok","reason_code","diagnostics","public_record","private_record"))&&
    identical(response$api_version,"clinical-module-response@1.0")&&isTRUE(response$ok),"MM_PROJECTION_REQUIRES_VALIDATED_SUCCESS")
  mm_need(mm_keys(context,c("result_id","binding"))&&mm_text(context$result_id),"MM_PROJECTION_CONTEXT_INVALID")
  mm_need(identical(response$private_record$format,"R_serialize_v3_base64"),"MM_PRIVATE_FORMAT_INVALID")
  priv<-unserialize(jsonlite::base64_dec(response$private_record$blob))
  pub<-response$public_record;pub$schema_version<-"mediation-matching-result@1.0.0"
  mm_write_bundle(list(record=pub,private=priv),output_dir,context$binding,result_id=context$result_id)
}
