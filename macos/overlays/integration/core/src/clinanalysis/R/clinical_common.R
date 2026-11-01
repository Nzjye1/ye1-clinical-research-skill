# Candidate common-contract branch. Numerical ownership remains table1.R and
# python/clinical_methods/association.py; this file contains no fitting code.
.clinical_common <- new.env(parent=emptyenv())
.clinical_common_version <- "0.10.0-candidate1"
.clinical_input_version <- "clinical-study-input@0.1.0-candidate1"
.clinical_input_versions <- c(.clinical_input_version,"clinical-study-input@0.2.0-candidate1","clinical-study-input@0.3.0-candidate1","clinical-study-input@0.4.0-candidate1","clinical-study-input@0.5.0-candidate1","clinical-study-input@0.6.0-candidate1","clinical-study-input@0.7.0-candidate1","clinical-study-input@0.8.0-candidate1","clinical-study-input@0.9.0-candidate1","clinical-study-input@0.10.0-candidate1")
 .clinical_input_versions <- c(.clinical_input_versions,"clinical-study-input@1.0")
.clinical_result_version <- "clinical-analysis-result@0.10.0-candidate1"
common_object <- function() structure(list(),names=character())

common_json_write <- function(x, path) {
  # glmnet pipelines bind exact requested lambda and canonical semantics.
  # jsonlite digits=NA prints only 15 significant digits on this pinned host.
  # Preserve full double round trips for the new methods; historical methods
  # retain their previous serialization, numerical owners and model formats.
  method <- if(is.list(x))x$method_id %||% if(is.list(x$analysis))x$analysis$method_id else NULL else NULL
  precision <- if(is.character(method)&&length(method)==1L&&!is.na(method)&&method%in%c("prediction.continuous.signed.lasso",
    "prediction.continuous.signed.elasticnet","prediction.binary.lasso","prediction.binary.elasticnet",
    "interpretation.linear.interventional","prediction.survival.cox.lasso","prediction.survival.cox.elasticnet"))17L else NA_integer_
  if(is.list(x)&&identical(x$schema_version,"clinical-frozen-interpretation@0.9.0-candidate1")) precision <- 17L
  jsonlite::write_json(x,path,auto_unbox=TRUE,pretty=TRUE,digits=precision,
    null="null",na="null",dataframe="rows")
}
common_json_read <- function(path) jsonlite::fromJSON(path, simplifyVector=FALSE)
common_sha <- function(path) {
  size <- file.info(path)$size
  if(is.na(size)||size>8388608) stop("HASH_INPUT_LIMIT",call.=FALSE)
  # This host's file.access ACL probe is unreliable even for readable source.
  # Explicit bounded binary reads retain SHA-256 semantics without ACL changes.
  bytes <- readBin(path,"raw",n=size)
  digest::digest(bytes,algo="sha256",serialize=FALSE)
}
common_executable_sha <- common_sha
common_hash <- function(x) digest::digest(jsonlite::toJSON(x, auto_unbox=TRUE, null="null", digits=NA), algo="sha256", serialize=FALSE)
common_path <- function(path) normalizePath(path, winslash="/", mustWork=FALSE)
common_inside <- function(path, root) {
  p <- tolower(common_path(path)); r <- tolower(common_path(root))
  startsWith(p, paste0(r,"/"))
}

register_clinical_common <- function(root, runtime) {
  .clinical_common$root <- common_path(root)
  .clinical_common$runtime <- runtime
  common_task_validator <- function(x) {
    if (!(x$schema_version %in% .clinical_input_versions)) stop("SCHEMA_VERSION_UNSUPPORTED",call.=FALSE)
    d <- tempfile("contract-check-",tmpdir=file.path(.clinical_common$root,"evidence"))
    if(!dir.create(d,recursive=FALSE)) stop("VALIDATION_DIRECTORY_UNAVAILABLE",call.=FALSE)
    taskpath <- file.path(d,"task.json");outpath <- file.path(d,"validation.json")
    common_json_write(x,taskpath)
    if(!common_python(file.path(.clinical_common$root,"python/clinical_methods/contracts.py"),c("validate",taskpath,outpath,.clinical_common$root),file.path(d,"validator.log")) || !file.exists(outpath)) stop("VALIDATOR_PROCESS_FAILED",call.=FALSE)
    v <- common_json_read(outpath)
    if(!isTRUE(v$ok)) stop(v$reason_code %||% "TASK_CONTRACT_INVALID",call.=FALSE)
    invisible(TRUE)
  }
  for(version in .clinical_input_versions) register_task_contract(version,common_task_validator)
  register_result_contract(.clinical_result_version, validate_clinical_common_result)
  register_result_contract("clinical-analysis-result@1.0",validate_clinical_common_result)
  for (id in c("baseline.table1", "association.linear", "association.logistic","association.linear.plan","association.logistic.plan","prediction.continuous.nonnegative.ridge","prediction.binary.ridge","survival.kaplan_meier","survival.cox.association","prediction.survival.cox","evaluation.survival.cox.ipcw","causal.psm.att.continuous","prediction.continuous.signed.lasso","prediction.continuous.signed.elasticnet","prediction.binary.lasso","prediction.binary.elasticnet","interpretation.linear.interventional","prediction.survival.cox.lasso","prediction.survival.cox.elasticnet")) {
    register_analysis_plugin(id, run_clinical_common_provider)
  }
  invisible(TRUE)
}

common_python <- function(script, arguments, log_path) {
  runtime <- .clinical_common$runtime
  # Only frozen executables and argument arrays; no shell command strings.
  old <- Sys.getenv("PYTHONDONTWRITEBYTECODE", unset=NA_character_)
  Sys.setenv(PYTHONDONTWRITEBYTECODE="1")
  on.exit(if (is.na(old)) Sys.unsetenv("PYTHONDONTWRITEBYTECODE") else Sys.setenv(PYTHONDONTWRITEBYTECODE=old))
  captured <- tryCatch(suppressWarnings(system2(runtime$python, args=vapply(c("-B", script, arguments), shQuote, character(1)),
    stdout=TRUE, stderr=TRUE)),error=function(e)structure("SUBPROCESS_INVOCATION_FAILED",status=127L))
  # Capture first; never ask a shell to redirect into a Unicode path.
  tryCatch(writeLines(captured,log_path,useBytes=TRUE),error=function(e)NULL)
  status <- attr(captured,"status") %||% 0L
  identical(as.integer(status),0L)
}

common_verify_runtime <- function() {
  lock <- .clinical_common$runtime
  if(!isTRUE(l10n_info()[["UTF-8"]])) return("UTF8_PROCESS_LOCALE_REQUIRED")
  rscript_name <- if (.Platform$OS.type == "windows") "Rscript.exe" else "Rscript"
  if (!identical(common_path(file.path(R.home("bin"), rscript_name)), common_path(lock$rscript_engine))) return("RSCRIPT_BINDING_MISMATCH")
  for(p in names(lock$executable_hashes)) if(!file.exists(p)||!identical(common_executable_sha(p),lock$executable_hashes[[p]])) return("RUNTIME_EXECUTABLE_DRIFT")
  if (!identical(as.character(getRversion()),lock$versions$R)) return("R_VERSION_DRIFT")
  for (p in c("jsonlite", "digest")) {
    if (!requireNamespace(p,quietly=TRUE)) return("R_DEPENDENCY_UNAVAILABLE")
    if (!identical(as.character(utils::packageVersion(p)),lock$versions[[p]])) return("R_DEPENDENCY_VERSION_DRIFT")
    if (!identical(common_path(find.package(p)),common_path(lock$r_package_paths[[p]]))) return("R_LIBRARY_BINDING_MISMATCH")
  }
  if (!file.exists(lock$python)) return("PYTHON_RUNTIME_UNAVAILABLE")
  for (p in names(lock$code_hashes)) {
    f <- file.path(.clinical_common$root,p)
    if (!file.exists(f) || !identical(common_sha(f),lock$code_hashes[[p]])) return("CORE_CODE_DRIFT")
  }
  NULL
}

common_empty_result <- function(task, run_id) {
  value <- list(schema_version=.clinical_result_version, core_version=.clinical_common_version,
    study_id="unvalidated", run_id=run_id,
    method_id="unvalidated", method_version="1.0.0-candidate1",
    provider=list(id="unselected",version="unselected",code_hash=NULL,runtime=common_object()),
    binding=list(input_hash=NULL, plan_hash=NULL, code_hash=NULL,runtime_hash=NULL,model_hash=NULL),
    execution_status="blocked", applicability_status="fail",scientific_review="pending",export_status="local_only",test_only=TRUE,
    counts=common_object(), estimates=list(),metrics=list(),model_results=list(),tests=list(),survival=NULL,cox_prediction=NULL,survival_evaluation=NULL,psm=NULL,penalized_prediction=NULL,interpretation=NULL,cox_penalized_prediction=NULL,diagnostics=common_object(),warnings=list(),
    limitations=list("SYNTHETIC_TEST_ONLY: software acceptance is not clinical scientific review.",
      "Candidate common analysis subset; synthetic engineering validation only, no real database connection or verified clinical/causal assumptions."),
    tables=list(),figures=list(),source_refs=list(),provenance=common_object(),local_artifacts=list(),
    completed_parts=list(),unsupported_requests=list(),next_actions=list(),reason_code=NULL,stage="binding")
  study_result_context(value,task)
}

common_artifact <- function(id, kind, file, result, result_ids, denominator, units, caption, ci=NULL) {
  value <- list(artifact_id=id,kind=kind,source_result_ids=result_ids,data_hash=common_sha(file),
    method=result$method_id,options=common_object(),denominator=denominator,units=units,caption=caption,
    ci=ci,language="en",version=result$run_id,scientific_review="pending",export_status="local_only",test_only=TRUE)
  study_artifact_context(value,result)
}

common_rows_df <- function(rows, variables=NULL) {
  fields <- names(rows[[1L]])
  declared <- if(is.null(variables)) NULL else setNames(lapply(variables,`[[`,"dtype"),vapply(variables,`[[`,"","name"))
  as.data.frame(setNames(lapply(fields, function(f) {
    vals <- lapply(rows,`[[`,f)
    if(!is.null(declared)) {
      dtype <- declared[[f]]
      if(is.null(dtype) || !dtype%in%c("id","category","number")) stop("NORMALIZED_FIELD_TYPE_REQUIRED",call.=FALSE)
      # Use the validated declaration even when all cells are JSON null. Do not
      # infer the type from surviving values or coerce malformed observed cells.
      is_valid <- function(v) is.null(v) || (length(v)==1L && if(dtype=="number")
        is.numeric(v) && !is.complex(v) && !is.na(v) && is.finite(v) else is.character(v) && !is.na(v))
      if(!all(vapply(vals,is_valid,logical(1)))) stop("NORMALIZED_FIELD_TYPE_MISMATCH",call.=FALSE)
      if(dtype%in%c("id","category")) return(vapply(vals,function(v) if(is.null(v)) NA_character_ else v,character(1)))
      return(vapply(vals,function(v) if(is.null(v)) NA_real_ else as.numeric(v),numeric(1)))
    }
    if (any(vapply(vals,is.character,logical(1)))) return(vapply(vals,function(v) if(is.null(v)) NA_character_ else as.character(v),character(1)))
    vapply(vals,function(v) if(is.null(v)) NA_real_ else as.numeric(v),numeric(1))
  }),fields), stringsAsFactors=FALSE,check.names=FALSE)
}

common_v1_family <- function(task) {
  if(!study_is_task(task)) return(NULL)
  method <- task$analysis$method_id
  family <- .clinical_common$normalized$core_family
  if(method%in%c("baseline.table1","association.linear","association.logistic")) {
    if(!is.null(family)) stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
    return(NULL)
  }
  if(!is.list(family)||!is.character(family$name)||length(family$name)!=1L||is.na(family$name))
    stop("V1_FAMILY_DISPATCH_REQUIRED",call.=FALSE)
  methods <- switch(family$name,
    association_plan=c("association.linear.plan","association.logistic.plan"),
    psm_v07=c("causal.psm.att.continuous"),
    penalized_v08=c("prediction.binary.lasso","prediction.binary.elasticnet","prediction.continuous.signed.lasso","prediction.continuous.signed.elasticnet"),
    interpretation_v09=c("interpretation.linear.interventional"),
    cox_penalized_v10=c("prediction.survival.cox.lasso","prediction.survival.cox.elasticnet"),
    prediction=c("prediction.binary.ridge","prediction.continuous.nonnegative.ridge"),
    survival=c("survival.kaplan_meier","survival.cox.association"),
    survival_v05=c("survival.cox.association","prediction.survival.cox"),
    survival_v06=c("evaluation.survival.cox.ipcw"),NULL)
  if(is.null(methods)||!method%in%methods||!identical(family$method_id,method))
    stop("REAL_FAMILY_NOT_INTEGRATED",call.=FALSE)
  if(family$name%in%c("association_plan","psm_v07")&&!identical(family$operation,"analyze"))
    stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
  if(identical(family$name,"prediction")&&!identical(family$operation,task$analysis$prediction$operation))
    stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
  if(identical(family$name,"penalized_v08")&&(!family$operation%in%c("train","evaluate","infer")||!identical(family$operation,task$analysis$penalized_prediction$operation)))
    stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
  if(identical(family$name,"interpretation_v09")&&!identical(family$operation,"infer"))
    stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
  if(identical(family$name,"cox_penalized_v10")&&(!family$operation%in%c("train","infer")||!identical(family$operation,task$analysis$cox_penalized_prediction$operation)))
    stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
  if(identical(family$name,"survival")&&(!is.null(family$operation)||!is.null(task$analysis$survival$ph_test)))
    stop("REAL_FAMILY_NOT_INTEGRATED",call.=FALSE)
  if(identical(family$name,"survival_v05")) {
    if(identical(method,"survival.cox.association")) {
      if(!is.null(family$operation)||is.null(task$analysis$survival$ph_test))
        stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
    } else {
      if(!is.character(family$operation)||length(family$operation)!=1L||is.na(family$operation)||
          !family$operation%in%c("train","infer")||!identical(family$operation,task$analysis$cox_prediction$operation))
        stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
    }
  }
  if(identical(family$name,"survival_v06")&&
      (!identical(family$operation,"infer")||!identical(task$analysis$cox_prediction$operation,"infer")))
    stop("V1_FAMILY_DISPATCH_MISMATCH",call.=FALSE)
  family
}

common_result_label <- function(result) {
  context <- result$origin_context
  if(!is.null(context)) {
    if(!is.list(context)||!(identical(context$data_origin,"real")||identical(context$data_origin,"synthetic"))||
       !(identical(context$task_purpose,"engineering_test")||identical(context$task_purpose,"research_analysis"))||
       !identical(context$scientific_review,"pending")||
       !identical(context$test_only,identical(context$task_purpose,"engineering_test")))
      stop("RESULT_ORIGIN_CONTEXT_INVALID",call.=FALSE)
    return(paste(toupper(context$data_origin),context$task_purpose,"scientific review pending",sep=" | "))
  }
  if(identical(result$schema_version,"clinical-analysis-result@1.0")) {
    return(paste(toupper(result$data_origin),result$task_purpose,"scientific review pending",sep=" | "))
  }
  "SYNTHETIC TEST ONLY"
}

run_clinical_common_provider <- function(task, data, output_dir) {
  family <- common_v1_family(task)
  if(!is.null(family)) {
    if(identical(family$name,"prediction")) return(run_common_prediction_provider(task,data,output_dir))
    if(identical(family$name,"survival")) return(run_common_survival_provider(task,data,output_dir))
    if(identical(family$name,"survival_v05")) {
      if(identical(task$analysis$method_id,"survival.cox.association"))
        return(run_common_survival_provider(task,data,output_dir))
      return(run_common_cox_prediction_provider(task,data,output_dir))
    }
    if(identical(family$name,"survival_v06"))
      return(run_common_survival_evaluation_provider(task,data,output_dir))
  }
  if(task$analysis$method_id%in%.cox_penalized_v10_methods) return(run_common_cox_penalized_provider(task,data,output_dir))
  if(identical(task$analysis$method_id,"interpretation.linear.interventional")) return(run_common_interpretation_provider(task,data,output_dir))
  if(task$analysis$method_id%in%.penalized_v08_methods) return(run_common_penalized_provider(task,data,output_dir))
  if(identical(task$analysis$method_id,"causal.psm.att.continuous")) return(run_common_psm_provider(task,data,output_dir))
  if(identical(task$analysis$method_id,"evaluation.survival.cox.ipcw")) return(run_common_survival_evaluation_provider(task,data,output_dir))
  if(identical(task$analysis$method_id,"prediction.survival.cox")) return(run_common_cox_prediction_provider(task,data,output_dir))
  if(startsWith(task$analysis$method_id,"survival.")) return(run_common_survival_provider(task,data,output_dir))
  if(task$analysis$method_id%in%c("association.linear.plan","association.logistic.plan")) return(run_common_association_plan_provider(task,data,output_dir))
  if(startsWith(task$analysis$method_id,"prediction.")) return(run_common_prediction_provider(task,data,output_dir))
  if (identical(task$analysis$method_id,"baseline.table1")) {
    baseline <- task$analysis$baseline
    legacy_task <- if(study_is_task(task)&&is.null(baseline$group)) NULL else list(tfl=list(table1=c(list(enabled=TRUE),baseline)),
      analysis=list(exposure=baseline$group,exposure_levels=as.list(sort(unique(data[[baseline$group]])))))
    return(list(ok=TRUE,table1=if(study_is_task(task)&&is.null(baseline$group)) study_overall_table1(task,data) else build_table1(legacy_task,data),
      provider=list(id="clinanalysis.table1",version=common_sha(file.path(.clinical_common$root,"src/clinanalysis/R/table1.R")),code_hash=common_sha(file.path(.clinical_common$root,"src/clinanalysis/R/table1.R")),runtime=list(R=as.character(getRversion())))))
  }
  preflight <- file.path(output_dir,"private","provider-preflight.json")
  if(!common_python(file.path(.clinical_common$root,"python/clinical_methods/bridge.py"),c("--preflight",preflight),file.path(output_dir,"private","preflight.log")) || !file.exists(preflight)) return(list(ok=FALSE,reason_code="PROVIDER_PREFLIGHT_FAILED"))
  pre <- common_json_read(preflight)
  if(!isTRUE(pre$ok)) return(pre)
  expected <- .clinical_common$runtime$python_versions
  for(p in names(expected)) if(!identical(pre$runtime[[p]],expected[[p]])) return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  request <- file.path(output_dir,"private","provider-request.json")
  response <- file.path(output_dir,"private","provider-response.json")
  private_request <- list(rows=.clinical_common$normalized$rows,spec=task$analysis$spec)
  if(study_is_task(task)) private_request <- c(private_request,list(schema_version="clinical-association-request@1.0",limits=list(max_rows=task$execution$max_rows,max_input_bytes=task$execution$max_decoded_bytes)))
  common_json_write(private_request,request)
  if (!common_python(file.path(.clinical_common$root,"python/clinical_methods/bridge.py"),c(request,response,if(study_is_task(task))as.character(task$execution$max_decoded_bytes) else character()),file.path(output_dir,"private","provider.log")) || !file.exists(response))
    return(list(ok=FALSE,reason_code="PROVIDER_PROCESS_FAILED"))
  x <- common_json_read(response)
  if (!isTRUE(x$ok)) return(x)
  expected <- .clinical_common$runtime$python_versions
  for (p in names(expected)) if (!identical(x$runtime[[p]],expected[[p]])) return(list(ok=FALSE,reason_code="PYTHON_DEPENDENCY_VERSION_DRIFT"))
  x$provider <- list(id="clinical_methods.association",version=x$provider_version,
    code_hash=common_sha(file.path(.clinical_common$root,"python/clinical_methods/association.py")),runtime=x$runtime)
  x
}

common_estimates <- function(record, result, task) {
  out <- list()
  collect <- function(r, label) {
    if (is.null(r$coefficients)) return(NULL)
    lapply(seq_along(r$coefficients), function(i) {
      e <- r$coefficients[[i]]
      logistic <- identical(r$model,"logistic")
      intercept <- identical(e$term,"intercept")
      termfield <- sub("\\[.*$", "", e$term)
      variable <- Filter(function(v) identical(v$name,termfield), task$variables)
      unit <- if (logistic) "dimensionless" else {
        yvar <- Filter(function(v) identical(v$name,task$analysis$spec$outcome), task$variables)
        if(length(yvar)) yvar[[1L]]$unit else "outcome units"
      }
      list(result_id=paste0(result$run_id,"-",label,"-",i),term=e$term,
        estimate=if(logistic) e$odds_ratio else e$estimate,
        standard_error=e$standard_error,
        ci=list(lower=if(logistic)e$or_ci95[[1L]] else e$ci95[[1L]],upper=if(logistic)e$or_ci95[[2L]] else e$ci95[[2L]],level=0.95,
          method=if(logistic)"Wald normal on log odds, exponentiated" else "Wald t"),
        p=e$p,effect_scale=if(logistic)if(intercept)"baseline_odds" else "odds_ratio" else if(intercept)"conditional_mean" else "mean_difference",
        standard_error_scale=if(logistic)"log_odds" else "outcome_units",
        interpretation=if(intercept)"Intercept at numeric predictors zero and categorical reference levels; no exposure contrast." else if(logistic)"Odds ratio per one predictor unit or explicit categorical contrast." else "Outcome-unit coefficient per one predictor unit or explicit categorical contrast.",
        unit=unit,predictor_unit=if(length(variable))variable[[1L]]$unit else "constant",
        exposure_unit=Filter(function(v)identical(v$name,task$analysis$spec$exposure),task$variables)[[1L]]$unit,
        reference=if(length(variable))variable[[1L]]$reference %||% NULL else NULL,
        estimand=task$estimand,population=task$cohort$target_population,analysis_unit=task$identity$analysis_unit,
        evaluation_set=label,denominator=r$n_used)
    })
  }
  out <- collect(record,"main") %||% list()
  for (i in seq_along(record$sensitivity)) {
    r <- record$sensitivity[[i]]
    out <- c(out,collect(r,paste0("sensitivity",i)) %||% list())
  }
  out
}

common_write_effects <- function(result, output_dir) {
  if (!length(result$estimates)) return(result)
  rows <- lapply(result$estimates,function(e) data.frame(result_id=e$result_id,term=e$term,estimate=e$estimate,
    standard_error=e$standard_error,ci_lower=e$ci$lower,ci_upper=e$ci$upper,p=e$p,effect_scale=e$effect_scale,
    standard_error_scale=e$standard_error_scale,denominator=e$denominator,evaluation_set=e$evaluation_set,stringsAsFactors=FALSE))
  table <- do.call(rbind,rows)
  if(identical(result$schema_version,"clinical-analysis-result@1.0")) {
    for(key in c("unit","predictor_unit","exposure_unit","analysis_unit")) table[[key]] <- vapply(result$estimates,`[[`,"",key)
  }
  path <- file.path(output_dir,"tables","effect_estimates.csv")
  utils::write.csv(table,path,row.names=FALSE,na="")
  ids <- lapply(result$estimates,`[[`,"result_id")
  result$tables <- list(common_artifact("effect-estimates","table",path,result,ids,NULL,"explicit per estimate", "Prespecified associations; each row carries its model denominator; pending scientific review.",list(level=0.95,method="Wald")))
  # Intercepts are reference-profile parameters, not exposure contrasts.
  # Keep them in the table with explicit scales; draw only contrast estimates.
  table <- table[table$term!="intercept",,drop=FALSE]
  ids <- as.list(table$result_id)
  figpath <- file.path(output_dir,"figures","effects.png")
  status <- tryCatch({
    grDevices::png(figpath,width=1100,height=max(500,80*nrow(table)))
    on.exit(grDevices::dev.off(),add=TRUE)
    graphics::par(mar=c(5,18,3,2))
    yrange <- seq_len(nrow(table))
    graphics::plot(table$estimate,yrange,xlim=range(c(table$ci_lower,table$ci_upper)),yaxt="n",ylab="",xlab=table$effect_scale[[1L]],pch=19,
      main=paste(if(identical(result$schema_version,"clinical-analysis-result@1.0")) paste(toupper(result$data_origin),result$task_purpose,"review pending",sep=" | ") else "SYNTHETIC TEST ONLY","- associations (95% CI)"))
    graphics::axis(2,at=yrange,labels=table$term,las=1)
    graphics::segments(table$ci_lower,yrange,table$ci_upper,yrange)
    graphics::abline(v=if(table$effect_scale[[1L]]%in%c("odds_ratio","hazard_ratio"))1 else 0,lty=2,col="grey50")
    grDevices::dev.off()
    on.exit(NULL,add=FALSE)
    TRUE
  },error=function(e)FALSE)
  if (isTRUE(status)) study_stamp_png(figpath,result)
  if (isTRUE(status)) result$figures <- list(common_artifact("association-forest","figure",figpath,result,ids,
    NULL,"explicit per estimate",paste(if(identical(result$schema_version,"clinical-analysis-result@1.0")) paste(result$data_origin,result$task_purpose,"review pending",sep=" | ") else "SYNTHETIC TEST ONLY",". Wald 95% intervals; model denominators in linked table."),list(level=0.95,method="Wald"))) else {
    result$warnings <- c(result$warnings,list(list(code="FIGURE_FAILED",stage="figures")))
    result$execution_status <- "partial"
  }
  result
}

validate_clinical_common_result <- function(x) {
  required <- c("schema_version","run_id","method_id","provider","binding","execution_status","applicability_status",
    "scientific_review","export_status","test_only","counts","estimates","tables","figures","reason_code","stage")
  if(length(setdiff(required,names(x)))) stop("RESULT_CONTRACT_REQUIRED_FIELDS",call.=FALSE)
  new_study <- identical(x$schema_version,"clinical-analysis-result@1.0")
  if(new_study && (!x$data_origin%in%c("real","synthetic") || !x$task_purpose%in%c("engineering_test","research_analysis") || !identical(x$test_only,identical(x$task_purpose,"engineering_test")))) stop("RESULT_ORIGIN_PURPOSE_INVALID",call.=FALSE)
  if((!new_study && (!identical(x$schema_version,.clinical_result_version) || !isTRUE(x$test_only))) ||
    !identical(x$scientific_review,"pending") || !identical(x$export_status,"local_only")) stop("RESULT_CONTRACT_STATUS",call.=FALSE)
  check <- function(v) {
    if(is.numeric(v) && any(!is.finite(v))) stop("RESULT_NONFINITE",call.=FALSE)
    if(is.list(v)) invisible(lapply(v,check))
  }
  check(x)
  if(x$execution_status %in% c("complete","partial")) {
    if(!is.null(x$reason_code) && x$execution_status=="complete") stop("RESULT_STATUS_INCONSISTENT",call.=FALSE)
    if(!identical(x$provider$version,x$provider$code_hash)) stop("RESULT_PROVIDER_BINDING_INVALID",call.=FALSE)
    for(h in c("input_hash","plan_hash","code_hash","runtime_hash")) if(is.null(x$binding[[h]])) stop("RESULT_BINDING_MISSING",call.=FALSE)
  }
  ids <- c(vapply(x$estimates,`[[`,character(1),"result_id"),vapply(x$metrics %||% list(),`[[`,character(1),"result_id"),vapply(x$tests %||% list(),`[[`,character(1),"result_id"))
  ids <- c(ids,vapply(x$survival$curves %||% list(),`[[`,character(1),"result_id"))
  ids <- c(ids,vapply(x$survival$ph_score_test$tests %||% list(),`[[`,character(1),"result_id"),
    vapply(x$cox_prediction$prediction_summary %||% list(),`[[`,character(1),"result_id"))
  ids <- c(ids,common_survival_evaluation_ids(x),common_psm_ids(x),common_penalized_ids(x),common_interpretation_ids(x),common_cox_penalized_ids(x))
  if(anyDuplicated(ids)) stop("RESULT_ID_DUPLICATE",call.=FALSE)
  if(!is.null(x$survival)) validate_common_survival_result(x)
  if(!is.null(x$cox_prediction)) validate_common_cox_prediction_result(x)
  if(!is.null(x$survival_evaluation)) validate_common_survival_evaluation_result(x)
  if(!is.null(x$psm)) validate_common_psm_result(x)
  if(!is.null(x$penalized_prediction)) validate_common_penalized_result(x)
  if(!is.null(x$interpretation)) validate_common_interpretation_result(x)
  if(!is.null(x$cox_penalized_prediction)) validate_common_cox_penalized_result(x)
  for(e in x$estimates) {
    reference_point <- identical(e$component,"rcs_curve") && isTRUE(e$standard_error==0)
    if(is.null(e$estimate)||is.null(e$standard_error)||e$standard_error<0||(!reference_point&&e$standard_error==0)||(!is.null(e$p)&&(e$p<0||e$p>1))||e$ci$lower>e$ci$upper) stop("RESULT_INFERENCE_INVALID",call.=FALSE)
    if(identical(x$method_id,"association.logistic") && (!identical(e$effect_scale,if(identical(e$term,"intercept"))"baseline_odds" else "odds_ratio")||!identical(e$standard_error_scale,"log_odds"))) stop("RESULT_SCALE_INVALID",call.=FALSE)
  }
  for(t in x$tests %||% list()) {
    if(identical(t$status,"COMPUTED")&&(is.null(t$p)||is.null(t$statistic)||t$p<0||t$p>1||t$statistic<0)) stop("RESULT_TEST_INVALID",call.=FALSE)
    if(!identical(t$status,"COMPUTED")&&is.null(t$reason_code)) stop("RESULT_TEST_REASON_REQUIRED",call.=FALSE)
  }
  if(identical(x$method_id,"prediction.binary.ridge")&&length(x$metrics %||% list())&&
     (is.null(x$counts$evaluation_events)||is.null(x$counts$evaluation_nonevents))) stop("RESULT_BINARY_EVALUATION_EVENTS_REQUIRED",call.=FALSE)
  if(identical(x$provenance$prediction_operation,"infer")&&
     (length(x$metrics %||% list())||!is.null(x$counts$evaluation_n)||!is.null(x$counts$evaluation_events)||!is.null(x$counts$evaluation_nonevents))) stop("RESULT_INFERENCE_EVALUATION_FIELDS_INVALID",call.=FALSE)
  for(m in x$metrics %||% list()) {
    if(is.null(m$value)&&is.null(m$reason_code)) stop("RESULT_METRIC_REASON_REQUIRED",call.=FALSE)
    if(!is.null(m$denominator)&&(m$denominator<0||m$denominator!=floor(m$denominator))) stop("RESULT_METRIC_DENOMINATOR_INVALID",call.=FALSE)
    for(k in c("evaluation_n","evaluation_events","evaluation_nonevents"))
      if(!isTRUE(all.equal(m[[k]],x$counts[[k]]))) stop("RESULT_METRIC_EVALUATION_COUNT_MISMATCH",call.=FALSE)
    if(is.null(m$evaluation_n)) stop("RESULT_METRIC_EVALUATION_N_REQUIRED",call.=FALSE)
    if(identical(m$denominator_semantics,"not_a_count_ratio")) {
      if(!is.null(m$denominator)||!is.null(m$numerator)) stop("RESULT_METRIC_NONRATIO_COUNTS_INVALID",call.=FALSE)
    } else {
      if(is.null(m$denominator)||is.null(m$numerator)||m$numerator<0||m$numerator>m$denominator||m$denominator>m$evaluation_n) stop("RESULT_METRIC_RATIO_COUNTS_INVALID",call.=FALSE)
      if(m$denominator==0) {
        if(!is.null(m$value)||!identical(m$reason_code,"ZERO_RATIO_DENOMINATOR")) stop("RESULT_METRIC_ZERO_DENOMINATOR_INVALID",call.=FALSE)
      } else if(is.null(m$value)||abs(m$value-m$numerator/m$denominator)>1e-12) stop("RESULT_METRIC_RATIO_VALUE_MISMATCH",call.=FALSE)
      expected_n<-switch(m$denominator_semantics,events=m$evaluation_events,nonevents=m$evaluation_nonevents,evaluated_labels=m$evaluation_n,NULL)
      if(!is.null(expected_n)&&m$denominator!=expected_n) stop("RESULT_METRIC_RATIO_SCOPE_MISMATCH",call.=FALSE)
    }
  }
  if(!is.null(x$counts$evaluation_events)||!is.null(x$counts$evaluation_nonevents)) {
    if(is.null(x$counts$evaluation_events)||is.null(x$counts$evaluation_nonevents)||is.null(x$counts$evaluation_n)||
       x$counts$evaluation_events+x$counts$evaluation_nonevents!=x$counts$evaluation_n) stop("RESULT_EVALUATION_EVENTS_INVALID",call.=FALSE)
  }
  for(a in c(x$tables,x$figures)) {
    if(!identical(a$version,x$run_id)||!all(unlist(a$source_result_ids,use.names=FALSE)%in%ids)||!identical(a$test_only,x$test_only) || (new_study && (!identical(a$data_origin,x$data_origin)||!identical(a$task_purpose,x$task_purpose)))) stop("RESULT_ARTIFACT_BINDING_INVALID",call.=FALSE)
  }
  invisible(TRUE)
}

run_clinical_common <- function(task, data=NULL, output_dir=NULL, original_task_path=NULL) {
  root <- .clinical_common$root
  output_dir <- output_dir %||% task$execution$output_dir
  if(is.null(output_dir) || !common_inside(output_dir,if(study_is_task(task))task$project_root else root)) stop("OUTPUT_OUTSIDE_ISOLATED_ROOT",call.=FALSE)
  if(file.exists(output_dir) || dir.exists(output_dir)) stop("OUTPUT_DIRECTORY_EXISTS",call.=FALSE)
  if(!dir.exists(dirname(output_dir))) stop("OUTPUT_PARENT_REQUIRED",call.=FALSE)
  if(!dir.create(output_dir,recursive=FALSE,showWarnings=FALSE)) stop("OUTPUT_DIRECTORY_CLAIM_FAILED",call.=FALSE)
  for(p in c("private","tables","figures")) dir.create(file.path(output_dir,p))
  run_id <- paste0("run-",format(Sys.time(),"%Y%m%dT%H%M%OS6",tz="UTC"),"-",Sys.getpid())
  run_id <- gsub("[.:]","",run_id)
  result <- common_empty_result(task,run_id)
  tryCatch({
    runtime_error <- common_verify_runtime()
    if(!is.null(runtime_error)) stop(runtime_error,call.=FALSE)
    if(!is.null(data)) stop("INLINE_DATA_NOT_SUPPORTED",call.=FALSE)
    if(is.null(original_task_path)) stop("BOUND_TASK_FILE_REQUIRED",call.=FALSE)
    if(!identical(common_path(task$execution$output_dir),common_path(output_dir))) stop("OUTPUT_BINDING_MISMATCH",call.=FALSE)
    snapshot_path <- file.path(output_dir,"private","task-snapshot.json")
    task_bytes <- attr(task,"common_task_bytes")
    if(is.null(task_bytes)) stop("BOUND_TASK_BYTES_REQUIRED",call.=FALSE)
    writeBin(task_bytes,snapshot_path)
    # Retain the submitted bytes even when semantic/schema validation refuses
    # the task. A raw input hash does not assert that its plan is valid.
    result$binding$input_hash <- common_sha(snapshot_path)
    normalized_path <- file.path(output_dir,"private","normalized.json")
    if(!common_python(file.path(root,"python/clinical_methods/contracts.py"),c("validate",snapshot_path,normalized_path,root,if(study_is_task(task))task$project_root else character()),file.path(output_dir,"private","validation.log")) || !file.exists(normalized_path)) stop("VALIDATOR_PROCESS_FAILED",call.=FALSE)
    validated <- common_json_read(normalized_path)
    if(!isTRUE(validated$ok)) {
      result$reason_code <- validated$reason_code
      result$stage <- validated$stage
      result$diagnostics <- list(missing_requirements=validated$missing_requirements,completed_parts=validated$completed_parts)
    } else {
      .clinical_common$normalized <- validated
      on.exit(.clinical_common$normalized <- NULL,add=TRUE)
      task <- validated$task
      result$study_id <- task$study_id
      result$method_id <- task$analysis$method_id
      result$completed_parts <- list("input_contract","source_plan_binding","selected_view_semantics")
      result$binding <- list(input_hash=common_sha(snapshot_path),plan_hash=task$plan_hash,
        code_hash=common_hash(.clinical_common$runtime$code_hashes),runtime_hash=common_sha(file.path(root,"runtime-lock.json")),model_hash=NULL)
      result$source_refs <- lapply(task$sources,function(s) list(source_id=s$source_id,database=s$database,source_fingerprint=s$source_fingerprint,recipe_version=s$recipe_version))
      result$provenance <- list(adapter_version=if(study_is_task(task))"declared-local-view@1.0" else "synthetic-mapping@0.1.0-candidate1",view_hash=validated$selected_view$content_hash,
        transformation_ledger=validated$ledger,host_isolation_evidence="not_established",authorization_scope=if(study_is_task(task))"project-bound local task and source bytes; no identity or isolation guarantee" else "delegated_synthetic_local_only")
      result$counts <- list(source_rows=validated$ledger$source_rows,subjects=validated$ledger$subjects,eligible=length(validated$rows),model_n=NULL,excluded_missing=NULL)
        result$stage <- "compute"
      data <- common_rows_df(validated$rows,task$variables)
      family <- common_v1_family(task)
      if(!is.null(family)) result$provenance$core_family <- family
      plugin <- get_analysis_plugin(task$analysis$method_id)
      calculated <- plugin(task,data,output_dir)
      if(!isTRUE(calculated$ok)) stop(calculated$reason_code %||% "PROVIDER_FAILED",call.=FALSE)
      result$provider <- calculated$provider
      if(!is.null(family)&&identical(family$name,"prediction")) {
        result <- common_prediction_result(calculated,result,task,output_dir)
      } else if(!is.null(family)&&identical(family$name,"survival")) {
        result <- common_survival_result(calculated,result,task,output_dir)
      } else if(!is.null(family)&&identical(family$name,"survival_v05")) {
        if(identical(task$analysis$method_id,"survival.cox.association")) {
          result <- common_survival_result(calculated,result,task,output_dir)
        } else {
          result <- common_cox_prediction_result(calculated,result,task,output_dir)
        }
      } else if(!is.null(family)&&identical(family$name,"survival_v06")) {
        result <- common_survival_evaluation_result(calculated,result,task,output_dir)
      } else if(task$analysis$method_id%in%.cox_penalized_v10_methods) {
        result <- common_cox_penalized_result(calculated,result,task,output_dir)
      } else if(identical(task$analysis$method_id,"interpretation.linear.interventional")) {
        result <- common_interpretation_result(calculated,result,task,output_dir)
      } else if(task$analysis$method_id%in%.penalized_v08_methods) {
        result <- common_penalized_result(calculated,result,task,output_dir)
      } else if(identical(task$analysis$method_id,"causal.psm.att.continuous")) {
        result <- common_psm_result(calculated,result,task,output_dir)
      } else if(identical(task$analysis$method_id,"evaluation.survival.cox.ipcw")) {
        result <- common_survival_evaluation_result(calculated,result,task,output_dir)
      } else if(identical(task$analysis$method_id,"prediction.survival.cox")) {
        result <- common_cox_prediction_result(calculated,result,task,output_dir)
      } else if(startsWith(task$analysis$method_id,"survival.")) {
        result <- common_survival_result(calculated,result,task,output_dir)
      } else if(task$analysis$method_id%in%c("association.linear.plan","association.logistic.plan")) {
        result <- common_association_plan_result(calculated,result,task,output_dir)
      } else if(startsWith(task$analysis$method_id,"prediction.")) {
        result <- common_prediction_result(calculated,result,task,output_dir)
      } else if(identical(task$analysis$method_id,"baseline.table1")) {
        tb <- calculated$table1
        common_json_write(tb,file.path(output_dir,"private","backend.json"))
        result$diagnostics <- list(backend_status=tb$status,group_missing_n=tb$group_missing_n %||% NULL)
        if(!identical(tb$status,"COMPLETE")) stop(tb$code %||% "BASELINE_FAILED",call.=FALSE)
        p1 <- file.path(output_dir,"tables","table1.csv")
        p2 <- file.path(output_dir,"tables","table1_statistics.csv")
        if(study_is_task(task)) {
          units <- setNames(vapply(task$variables,`[[`,"","unit"),vapply(task$variables,`[[`,"","name"))
          roles <- setNames(vapply(task$variables,`[[`,"","role"),vapply(task$variables,`[[`,"","name"))
          tb$statistics$unit <- unname(units[tb$statistics$variable])
          tb$statistics$role <- unname(roles[tb$statistics$variable])
        }
        utils::write.csv(tb$formatted,p1,row.names=FALSE,na="")
        utils::write.csv(tb$statistics,p2,row.names=FALSE,na="")
        result$counts$model_n <- nrow(data)-tb$group_missing_n
        result$counts$excluded_missing <- tb$group_missing_n
        denominator_policy <- tb$categorical_denominator
        overall_only <- study_is_task(task)&&is.null(task$analysis$baseline$group)
        group_note <- if(overall_only) "; no grouping variable; all selected records retained." else "; rows missing the group are excluded."
        result$tables <- list(common_artifact("table1-formatted","table",p1,result,list(),result$counts$model_n,"per variable",
            paste0(study_label(task),": baseline; categorical denominator policy=",denominator_policy,group_note)),
          common_artifact("table1-statistics","table",p2,result,list(),result$counts$model_n,"per variable",
            paste0("Full-precision baseline statistics; categorical denominator policy=",denominator_policy,"; variable missingness and denominators retained.")))
        for(i in seq_along(result$tables)) result$tables[[i]]$options <- list(categorical_denominator=denominator_policy,group_missing_policy=if(overall_only)"not_applicable" else "exclude")
        if(study_is_task(task)) {
          figure_path <- file.path(output_dir,"figures","baseline.png")
          shown <- tryCatch({study_table1_figure(tb,task,figure_path,study_label(task));TRUE},error=function(e)FALSE)
          if(isTRUE(shown)) study_stamp_png(figure_path,result)
          if(isTRUE(shown)) result$figures <- list(common_artifact("baseline-display","figure",figure_path,result,list(),result$counts$model_n,"variable units","Display of the linked computed baseline table; no additional estimation."))
          else result$warnings <- c(result$warnings,list(list(code="FIGURE_FAILED",stage="figures")))
        }
        result$execution_status <- "complete"
      } else {
        rec <- calculated$record
        common_json_write(rec,file.path(output_dir,"private","backend.json"))
        result$diagnostics <- list(backend_status=rec$status,backend=rec$diagnostics %||% common_object(),
          sensitivity=rec$sensitivity %||% list(),nonlinearity_test=rec$nonlinearity_test %||% NULL,interaction_test=rec$interaction_test %||% NULL)
        result$counts$model_n <- rec$n_used %||% NULL
        result$counts$excluded_missing <- rec$n_excluded_missing %||% NULL
        result$counts$missing_by_field <- rec$missing_by_field %||% list()
        result$counts$events <- rec$events %||% NULL
        result$counts$non_events <- rec$non_events %||% NULL
        result$counts$predictor_parameters <- rec$predictor_parameters %||% NULL
        result$limitations <- c(result$limitations,rec$limitations %||% list())
        if(!identical(rec$status,"COMPUTED_REVIEW_PENDING")) stop(rec$reason %||% "ESTIMATION_UNAVAILABLE",call.=FALSE)
        result$estimates <- common_estimates(rec,result,task)
        result$execution_status <- if(any(vapply(rec$sensitivity,function(x)!identical(x$status,"COMPUTED_REVIEW_PENDING"),logical(1)))) "partial" else "complete"
        result <- common_write_effects(result,output_dir)
      }
      if(result$execution_status%in%c("complete","partial")) {
        result$applicability_status <- if(result$execution_status=="partial")"limited" else "pass"
        result$stage <- "result_contract"
        result$completed_parts <- c(result$completed_parts,list("fixed_provider_compute","tables"))
        if(result$execution_status=="complete") result["reason_code"] <- list(NULL)
      }
      result$local_artifacts <- c(result$local_artifacts,list(list(artifact_id="private-run-manifest",kind="private_metadata")))
    }
  },error=function(e) {
    code <- conditionMessage(e)
    if(!grepl("^[A-Z][A-Z0-9_]+$",code)) code <- "COMMON_EXECUTION_FAILED"
    result$reason_code <<- code
    result$execution_status <<- if(length(result$estimates)||length(result$tables))"partial" else "blocked"
    result$applicability_status <<- if(result$stage=="compute")"limited" else "fail"
  })
  if(!is.null(result$reason_code)) result$unsupported_requests <- list(list(reason_code=result$reason_code,stage=result$stage))
  validate_registered_result_contract(result)
  candidate_result <- file.path(output_dir,"private","result-candidate.json")
  common_json_write(result,candidate_result)
  checked_result <- file.path(output_dir,"private","result-validation.json")
  valid_result <- common_python(file.path(root,"python/clinical_methods/contracts.py"),c("validate-result",candidate_result,checked_result,root,if(study_is_task(task))task$project_root else character()),file.path(output_dir,"private","result-validation.log"))
  if(!valid_result || !file.exists(checked_result) || !isTRUE(common_json_read(checked_result)$ok)) {
    # Preserve raw calculation privately, publish only a stable failure receipt.
    result <- common_empty_result(task,run_id)
    result$execution_status <- "failed";result$reason_code <- "RESULT_SCHEMA_INVALID";result$stage <- "result_contract"
  }
  common_json_write(result,file.path(output_dir,"result.json"))
  # Local-only reference bundle: no row access, model, path or private payload.
  reference_bundle <- list(schema_version="clinical-writing-references@0.1.0-candidate1",run_id=result$run_id,
    test_only=result$test_only,scientific_review="pending",export_status="local_only",execution_status=result$execution_status,
    result_ids=c(lapply(result$estimates,`[[`,"result_id"),lapply(result$metrics,`[[`,"result_id"),lapply(result$tests,`[[`,"result_id"),lapply(result$survival$curves %||% list(),`[[`,"result_id"),lapply(result$survival$ph_score_test$tests %||% list(),`[[`,"result_id"),lapply(result$cox_prediction$prediction_summary %||% list(),`[[`,"result_id"),as.list(common_survival_evaluation_ids(result)),as.list(common_psm_ids(result)),as.list(common_penalized_ids(result)),as.list(common_interpretation_ids(result)),as.list(common_cox_penalized_ids(result))),artifact_ids=lapply(c(result$tables,result$figures),`[[`,"artifact_id"),
    limitations=result$limitations,writing_eligible=FALSE)
  if(study_is_task(task)) reference_bundle <- c(reference_bundle,list(data_origin=result$data_origin,task_purpose=result$task_purpose))
  common_json_write(reference_bundle,file.path(output_dir,"writing-references.json"))
  private_files <- list.files(file.path(output_dir,"private"),full.names=TRUE)
  private_files <- private_files[!dir.exists(private_files)]
  private_index <- lapply(private_files,function(p)study_artifact_context(list(artifact_id=paste0("private-",basename(p)),
    relative_path=paste0("private/",basename(p)),sha256=common_sha(p),classification="LOCAL_ONLY",
    test_only=result$test_only,scientific_review="pending",export_status="local_only"),result))
  private_manifest <- list(run_id=result$run_id,output_dir=common_path(output_dir),task_path=original_task_path,
    test_only=result$test_only,scientific_review="pending",export_status="local_only",artifacts=private_index,
    binding=result$binding,backend="private/backend.json",runtime=.clinical_common$runtime)
  if(study_is_task(task)) private_manifest <- c(private_manifest,list(data_origin=result$data_origin,task_purpose=result$task_purpose))
  common_json_write(private_manifest,file.path(output_dir,"private","manifest.json"))
  result
}
