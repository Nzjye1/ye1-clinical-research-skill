# v0.9 transport, consistency validation and aggregate presentation only.
# All attribution/nomogram arithmetic belongs to interpretation_v09.R. No fit,
# outcome evaluation, coalition construction or attribution calculation lives here.
.interpretation_v09_method <- "interpretation.linear.interventional"

common_interpretation_provider_version <- function() {
  lock <- .clinical_common$runtime
  source <- file.path(.clinical_common$root,"src/clinanalysis/R/interpretation_v09.R")
  if(!file.exists(source)) stop("INTERPRETATION_PROVIDER_UNAVAILABLE",call.=FALSE)
  version <- common_sha(source)
  if(!is.character(lock$interpretation_provider_version)||
     !identical(version,lock$interpretation_provider_version)) stop("INTERPRETATION_PROVIDER_VERSION_DRIFT",call.=FALSE)
  if(!identical(as.character(getRversion()),lock$versions$R)) stop("INTERPRETATION_RUNTIME_VERSION_DRIFT",call.=FALSE)
  for(package in c("glmnet","Matrix")) {
    if(!requireNamespace(package,quietly=TRUE)) stop("PENALIZED_ENGINE_UNAVAILABLE",call.=FALSE)
    if(!identical(as.character(utils::packageVersion(package)),lock$penalized_runtime[[package]]))
      stop("PENALIZED_ENGINE_VERSION_MISMATCH",call.=FALSE)
    if(!identical(common_path(find.package(package)),common_path(lock$penalized_package_paths[[package]])))
      stop("PENALIZED_LIBRARY_BINDING_MISMATCH",call.=FALSE)
  }
  if(length(lock$penalized_dependency_hashes)!=10L) stop("PENALIZED_DEPENDENCY_BINDING_REQUIRED",call.=FALSE)
  for(path in names(lock$penalized_dependency_hashes))
    if(!file.exists(path)||!identical(common_sha(path),lock$penalized_dependency_hashes[[path]]))
      stop("PENALIZED_DEPENDENCY_DRIFT",call.=FALSE)
  # The numerical owner may apply the frozen v0.8 preprocessor, never fit it.
  if(!identical(common_sha(file.path(.clinical_common$root,"src/clinanalysis/R/penalized_v08.R")),lock$penalized_provider_version))
    stop("PENALIZED_PROVIDER_VERSION_DRIFT",call.=FALSE)
  version
}

run_common_interpretation_provider <- function(task,data,output_dir) {
  version <- common_interpretation_provider_version()
  normalized <- .clinical_common$normalized
  options <- normalized$interpretation_options
  model_bundle <- normalized$frozen_interpretation_model
  explainer <- normalized$frozen_explainer
  if(!is.list(options)||!is.list(model_bundle$model)||!is.list(explainer)||
     !is.list(normalized$interpretation_semantics)) return(list(ok=FALSE,reason_code="INTERPRETATION_NORMALIZED_BINDING_REQUIRED"))
  if(!isTRUE(all.equal(model_bundle$canonical_semantics,normalized$interpretation_semantics,
       tolerance=0,check.attributes=FALSE))) return(list(ok=FALSE,reason_code="INTERPRETATION_SEMANTICS_BINDING_MISMATCH"))
  numerical_explainer <- common_penalized_strip_explainer_origin(explainer)
  value <- interpretation_v09_analyze(data,model_bundle$model,numerical_explainer,options$model_ref$content_hash,version,
    resource_budget=normalized$resource_limits)
  if(!is.list(value$record)) return(list(ok=FALSE,reason_code=value$reason_code %||% "INTERPRETATION_PROVIDER_FAILED"))
  value$record <- common_penalized_origin_record(value$record,task)
  if(identical(task$schema_version,"clinical-study-input@1.0"))
    value$record$flow$scope <- normalized$ledger$interpretation$scope
  # The explainer's own file hash is transport metadata, not a self-reference
  # inside the stable frozen bundle or a recomputed attribution statistic.
  value$record$explainer_sha256 <- options$explainer_ref$content_hash
  path <- file.path(output_dir,"private","backend.json")
  common_json_write(value$record,path)
  record <- common_json_read(path)
  private <- list(individual="interpretation-individual-contributions.csv",
    encoded_individual="interpretation-encoded-contributions.csv",
    nomogram_individual="interpretation-individual-points.csv")
  for(name in names(private)) if(!is.null(value[[name]])) {
    if(!is.data.frame(value[[name]])) return(list(ok=FALSE,reason_code="INTERPRETATION_PRIVATE_FRAME_INVALID"))
    common_psm_write_frame(value[[name]],file.path(output_dir,"private",private[[name]]))
  }
  list(ok=TRUE,record=record,model_hash=options$model_ref$content_hash,
    explainer_hash=options$explainer_ref$content_hash,
    provider=list(id="clinanalysis.interpretation_v09",version=version,code_hash=version,
      runtime=list(R=as.character(getRversion()))))
}

common_interpretation_ids <- function(result) {
  rec <- result$interpretation
  if(is.null(rec)) return(character())
  rows <- c(rec$shap$global_importance,rec$nomogram$domains,rec$nomogram$axes,rec$nomogram$total_axis)
  c(rec$result_id,vapply(rows,`[[`,character(1),"result_id"))
}

common_interpretation_result <- function(calculated,result,task,output_dir) {
  rec <- calculated$record;rec$result_id <- paste0(result$run_id,"-interpretation")
  add_ids <- function(rows,section) lapply(seq_along(rows),function(i) {
    row <- rows[[i]];row$result_id <- paste0(rec$result_id,"-",section,"-",i);row
  })
  rec$shap$global_importance <- add_ids(rec$shap$global_importance,"global")
  for(name in c("domains","axes","total_axis")) rec$nomogram[[name]] <- add_ids(rec$nomogram[[name]],paste0("nomogram-",name))
  result$interpretation <- rec
  completed <- identical(rec$status,"completed")
  result$counts <- list(source_rows=rec$flow$n_application,subjects=rec$flow$n_application,
    eligible=rec$flow$n_application,model_n=NULL,excluded_missing=0L,
    evaluation_n=NULL,evaluation_events=NULL,evaluation_nonevents=NULL,missing_outcome_n=NULL,
    missing_feature_excluded_n=0L,prediction_n=if(completed)rec$flow$n_application else 0L,prediction_clipped_n=0L)
  result$binding["model_hash"] <- list(calculated$model_hash)
  result$diagnostics <- list(backend_status=rec$status,backend=list(interpretation=rec$diagnostics))
  result$provenance$prediction_operation <- "infer"
  result$provenance$fit_scope <- "frozen_no_refit"
  result$provenance$validation_scope <- "not_evaluation_interpretation"
  semantics <- .clinical_common$normalized$interpretation_semantics
  expected_score_unit <- if(rec$family=="gaussian")semantics$outcome$unit else "1"
  if(!identical(rec$definition$score_unit,expected_score_unit)) stop("RESULT_INTERPRETATION_SCORE_UNIT_MISMATCH",call.=FALSE)
  result$provenance$target_policy <- list(purpose="frozen_model_interpretation_only",
    score_scale=rec$definition$score_scale,score_unit=rec$definition$score_unit,
    prediction_scale=if(rec$family=="gaussian")"signed_original_outcome" else "event_probability",
    outcome_unit=semantics$outcome$unit,grouping="raw_feature",background="full_frozen_training_empirical",
    model_sha256=rec$model_sha256,explainer_sha256=rec$explainer_sha256)
  result$limitations <- unique(c(result$limitations,rec$limitations,as.list(c(
    "Grouped interventional affine SHAP uses the complete frozen training background; it does not preserve feature-group dependence and is not conditional SHAP.",
    "Gaussian attribution values use original signed outcome units. Binomial attribution values use raw log odds, not event-probability SHAP.",
    "Missing observations follow frozen training imputation; missingness does not remove a feature from a Shapley coalition.",
    "Global importance is the application-population mean absolute grouped contribution, not a sum of absolute encoded-column contributions.",
    "Nomogram axes use frozen observed training domains. Unknown categories and numeric extrapolation are refused, not clipped.",
    "No evaluation outcomes, fitting, model selection, calibration, causal inference or clinical scientific approval is performed.",
    "Numerical additivity and point backchecks are engineering consistency checks; all outputs remain local-only and scientific-review pending."))))
  result$execution_status <- if(completed)"complete" else "blocked"
  result$applicability_status <- if(completed)"pass" else "limited"
  result["reason_code"] <- list(rec$reason_code);result$stage <- "compute"
  if(completed) result$completed_parts <- c(result$completed_parts,
    list("frozen_affine_grouped_interventional_interpretation","nomogram_numeric_backcheck","no_refit_no_outcome_evaluation"))
  private <- c("interpretation-individual-contributions.csv","interpretation-encoded-contributions.csv","interpretation-individual-points.csv")
  for(name in private) if(file.exists(file.path(output_dir,"private",name))) result$local_artifacts <- c(result$local_artifacts,
    list(list(artifact_id=paste0("private-",tools::file_path_sans_ext(name)),kind="private_individual_interpretation")))
  validate_common_interpretation_result(result)
  common_write_interpretation_outputs(result,output_dir)
}

validate_common_interpretation_result <- function(result) {
  rec <- result$interpretation
  if(is.null(rec)) return(invisible(TRUE))
  need <- function(ok,code) if(!isTRUE(ok)) stop(code,call.=FALSE)
  number <- function(x) is.numeric(x)&&length(x)==1L&&!is.na(x)&&is.finite(x)
  same <- function(a,b) isTRUE(all.equal(a,b,tolerance=0,check.attributes=FALSE))
  close <- function(a,b) number(a)&&number(b)&&abs(a-b)<=1e-10+1e-10*max(abs(a),abs(b))
  hash <- function(x) is.character(x)&&length(x)==1L&&!is.na(x)&&grepl("^[0-9a-f]{64}$",x)
  need(identical(result$method_id,.interpretation_v09_method)&&identical(rec$method_id,.interpretation_v09_method),"RESULT_INTERPRETATION_METHOD_MISMATCH")
  need(rec$model_method_id%in%.penalized_v08_methods&&rec$family%in%c("gaussian","binomial"),"RESULT_INTERPRETATION_MODEL_FAMILY_INVALID")
  need(identical(startsWith(rec$model_method_id,"prediction.continuous.signed."),identical(rec$family,"gaussian")),"RESULT_INTERPRETATION_MODEL_FAMILY_INVALID")
  need(!length(result$estimates)&&!length(result$tests)&&!length(result$metrics),"RESULT_INTERPRETATION_EVALUATION_FORBIDDEN")
  need(is.null(result$counts$model_n)&&is.null(result$counts$evaluation_n)&&is.null(result$counts$evaluation_events)&&
    is.null(result$counts$evaluation_nonevents)&&is.null(result$counts$missing_outcome_n),"RESULT_INTERPRETATION_EVALUATION_FORBIDDEN")
  need(same(result$counts$source_rows,rec$flow$n_application)&&same(result$counts$subjects,rec$flow$n_application),"RESULT_INTERPRETATION_COUNT_MISMATCH")
  need(identical(rec$diagnostics$refit,FALSE)&&identical(rec$diagnostics$outcomes_used,FALSE)&&
    identical(rec$diagnostics$background_sampling,FALSE),"RESULT_INTERPRETATION_FROZEN_SCOPE_INVALID")
  definition <- list(method="exact_affine_grouped_interventional_shap",background="full_frozen_training_empirical",
    coalition_unit="raw_feature",missing_policy="frozen_training_median_mode",
    score_scale=if(rec$family=="gaussian")"signed_original_outcome" else "logit",
    score_unit=if(rec$family=="gaussian")result$provenance$target_policy$outcome_unit else "1",
    conditional=FALSE,probability_scale=FALSE,causal=FALSE)
  need(setequal(names(rec$definition),names(definition))&&same(rec$definition[names(definition)],definition),"RESULT_INTERPRETATION_DEFINITION_INVALID")
  need(identical(rec$nomogram$domain_policy,"frozen_training_observed"),"RESULT_INTERPRETATION_DOMAIN_INVALID")
  if(identical(rec$status,"completed")) {
    need(is.null(rec$reason_code)&&result$execution_status%in%c("complete","partial"),"RESULT_INTERPRETATION_COMPLETION_INVALID")
    need(all(vapply(list(rec$model_sha256,rec$explainer_sha256,rec$provider_version,rec$background_sha256,rec$transform_sha256),hash,logical(1))),"RESULT_INTERPRETATION_HASH_INVALID")
    need(identical(result$binding$model_hash,rec$model_sha256)&&identical(result$provider$version,rec$provider_version),"RESULT_INTERPRETATION_BINDING_MISMATCH")
    resource_limits <- clinical_resource_budget(.clinical_common$normalized$resource_limits,"interpretation.linear.interventional")
    need(number(rec$flow$n_background)&&rec$flow$n_background>0&&rec$flow$n_background<=resource_limits$max_background_rows&&
      number(rec$flow$n_application)&&rec$flow$n_application>0&&rec$flow$n_application<=resource_limits$max_rows&&
      same(result$counts$prediction_n,rec$flow$n_application),"RESULT_INTERPRETATION_FLOW_INVALID")
    need(length(rec$shap$global_importance)==rec$flow$n_features&&length(rec$nomogram$domains)==rec$flow$n_features,
      "RESULT_INTERPRETATION_FEATURE_COUNT_INVALID")
    features <- vapply(rec$nomogram$domains,`[[`,character(1),"feature")
    need(!anyDuplicated(features)&&identical(vapply(rec$shap$global_importance,`[[`,character(1),"feature"),features),
      "RESULT_INTERPRETATION_FEATURE_MAPPING_INVALID")
    for(row in rec$shap$global_importance) {
      need(same(row$n,rec$flow$n_application)&&number(row$mean_abs_shap)&&row$mean_abs_shap>=0&&
        number(row$sum_abs_shap)&&row$sum_abs_shap>=0,"RESULT_INTERPRETATION_GLOBAL_DENOMINATOR_INVALID")
      need(abs(row$mean_abs_shap-row$sum_abs_shap/row$n)<=1e-10+1e-10*max(abs(row$mean_abs_shap),abs(row$sum_abs_shap/row$n)),
        "RESULT_INTERPRETATION_GLOBAL_DENOMINATOR_INVALID")
      need(number(row$mean_shap)&&number(row$min_shap)&&number(row$max_shap)&&row$min_shap<=row$max_shap&&
        row$mean_shap>=row$min_shap-1e-10&&row$mean_shap<=row$max_shap+1e-10,
        "RESULT_INTERPRETATION_GLOBAL_RANGE_INVALID")
    }
    additive <- rec$shap$additivity;backcheck <- rec$nomogram$backcheck
    need(same(additive$atol,1e-10)&&same(additive$rtol,1e-10)&&identical(additive$passed,TRUE)&&
      number(additive$max_abs_error)&&additive$max_abs_error>=0,"RESULT_INTERPRETATION_ADDITIVITY_FAILED")
    need(same(backcheck$atol,1e-10)&&same(backcheck$rtol,1e-10)&&identical(backcheck$passed,TRUE)&&
      number(backcheck$max_score_abs_error)&&backcheck$max_score_abs_error>=0&&
      number(backcheck$max_prediction_abs_error)&&backcheck$max_prediction_abs_error>=0,"RESULT_INTERPRETATION_POINTS_BACKCHECK_FAILED")
    need(length(rec$nomogram$total_axis)>0L,"RESULT_INTERPRETATION_TOTAL_AXIS_REQUIRED")
    score_bound <- max(c(abs(rec$shap$base_value),abs(vapply(rec$nomogram$total_axis,`[[`,numeric(1),"score"))))
    prediction_bound <- if(rec$family=="binomial")1 else score_bound
    need(additive$max_abs_error<=1e-10+1e-10*score_bound,"RESULT_INTERPRETATION_ADDITIVITY_FAILED")
    need(backcheck$max_score_abs_error<=1e-10+1e-10*score_bound&&
      backcheck$max_prediction_abs_error<=1e-10+1e-10*prediction_bound,"RESULT_INTERPRETATION_POINTS_BACKCHECK_FAILED")
    need(is.logical(rec$nomogram$constant_model)&&length(rec$nomogram$constant_model)==1L&&!is.na(rec$nomogram$constant_model),"RESULT_INTERPRETATION_CONSTANT_FLAG_INVALID")
    if(isTRUE(rec$nomogram$constant_model)) {
      need(is.null(rec$nomogram$score_per_point)&&same(rec$nomogram$points_denominator,0)&&same(rec$nomogram$max_total_points,0),
        "RESULT_INTERPRETATION_CONSTANT_POINTS_INVALID")
      need(all(vapply(rec$nomogram$axes,function(row)same(row$points,0),logical(1)))&&
        all(vapply(rec$nomogram$total_axis,function(row)same(row$total_points,0)&&same(row$score,rec$nomogram$score_at_zero),logical(1))),
        "RESULT_INTERPRETATION_CONSTANT_POINTS_INVALID")
      predictions <- vapply(rec$nomogram$total_axis,`[[`,numeric(1),"prediction")
      need(all(predictions==predictions[[1L]]),"RESULT_INTERPRETATION_CONSTANT_PREDICTION_INVALID")
    } else need(number(rec$nomogram$score_per_point)&&rec$nomogram$score_per_point>0&&
      number(rec$nomogram$points_denominator)&&rec$nomogram$points_denominator>0,"RESULT_INTERPRETATION_POINTS_SCALE_INVALID")
    for(domain in rec$nomogram$domains) {
      need(number(domain$score_min)&&number(domain$score_max)&&domain$score_min<=domain$score_max&&
        close(domain$score_range,domain$score_max-domain$score_min),"RESULT_INTERPRETATION_DOMAIN_SCORE_INVALID")
      levels <- unlist(domain$fitted_levels,use.names=FALSE)
      if(identical(domain$type,"number")) {
        need(number(domain$observed_min)&&number(domain$observed_max)&&domain$observed_min<=domain$observed_max&&
          number(domain$impute_value)&&domain$impute_value>=domain$observed_min&&domain$impute_value<=domain$observed_max&&
          !length(levels)&&is.null(domain$fitted_reference),"RESULT_INTERPRETATION_DOMAIN_VALUES_INVALID")
      } else need(identical(domain$type,"category")&&is.list(domain$fitted_levels)&&length(levels)>0L&&
        !anyDuplicated(levels)&&identical(levels,penalized_v08_sort(levels))&&identical(domain$fitted_reference,levels[[1L]])&&
        domain$impute_value%in%levels&&is.null(domain$observed_min)&&is.null(domain$observed_max),
        "RESULT_INTERPRETATION_DOMAIN_VALUES_INVALID")
    }
    ranges <- vapply(rec$nomogram$domains,`[[`,numeric(1),"score_range")
    need(close(rec$nomogram$points_denominator,max(ranges)),"RESULT_INTERPRETATION_POINTS_SCALE_INVALID")
    if(!isTRUE(rec$nomogram$constant_model)) need(close(rec$nomogram$score_per_point,rec$nomogram$points_denominator/100)&&
      close(rec$nomogram$max_total_points,100*sum(ranges)/rec$nomogram$points_denominator),"RESULT_INTERPRETATION_POINTS_SCALE_INVALID")
    for(axis in rec$nomogram$axes) {
      index <- match(axis$feature,features)
      need(!is.na(index),"RESULT_INTERPRETATION_AXIS_FEATURE_INVALID")
      domain <- rec$nomogram$domains[[index]]
      need(identical(axis$type,domain$type)&&identical(axis$unit,domain$unit)&&number(axis$points)&&axis$points>=0&&
        number(axis$score_contribution),"RESULT_INTERPRETATION_AXIS_MAPPING_INVALID")
      if(identical(axis$input_kind,"missing")) need(is.null(axis$value)&&same(axis$resolved_value,domain$impute_value),
        "RESULT_INTERPRETATION_AXIS_MISSING_ROUTE_INVALID")
      else need(identical(axis$input_kind,"value")&&!is.null(axis$value)&&same(axis$value,axis$resolved_value),
        "RESULT_INTERPRETATION_AXIS_MAPPING_INVALID")
      if(identical(domain$type,"number")) need(number(axis$resolved_value)&&axis$resolved_value>=domain$observed_min&&
        axis$resolved_value<=domain$observed_max,"RESULT_INTERPRETATION_AXIS_DOMAIN_INVALID")
      else need(is.character(axis$resolved_value)&&length(axis$resolved_value)==1L&&axis$resolved_value%in%unlist(domain$fitted_levels,use.names=FALSE),
        "RESULT_INTERPRETATION_AXIS_DOMAIN_INVALID")
      need(axis$score_contribution>=domain$score_min-1e-10&&axis$score_contribution<=domain$score_max+1e-10,
        "RESULT_INTERPRETATION_AXIS_MAPPING_INVALID")
      expected <- if(isTRUE(rec$nomogram$constant_model))0 else 100*(axis$score_contribution-domain$score_min)/rec$nomogram$points_denominator
      need(close(axis$points,expected),"RESULT_INTERPRETATION_AXIS_POINTS_INVALID")
    }
    for(row in rec$nomogram$total_axis) {
      need(number(row$total_points)&&row$total_points>=0&&row$total_points<=rec$nomogram$max_total_points+1e-10,
        "RESULT_INTERPRETATION_TOTAL_POINTS_INVALID")
      expected <- if(isTRUE(rec$nomogram$constant_model))rec$nomogram$score_at_zero else
        rec$nomogram$score_at_zero+rec$nomogram$score_per_point*row$total_points
      need(close(row$score,expected)&&close(row$prediction,if(rec$family=="binomial")stats::plogis(row$score) else row$score),
        "RESULT_INTERPRETATION_TOTAL_MAPPING_INVALID")
    }
  } else need(identical(rec$status,"unavailable")&&!is.null(rec$reason_code)&&identical(result$execution_status,"blocked"),"RESULT_INTERPRETATION_REFUSAL_INVALID")
  invisible(TRUE)
}

common_interpretation_frame <- function(rows) {
  if(!length(rows)) return(data.frame())
  fields <- names(rows[[1L]])
  if(anyDuplicated(fields)||any(vapply(rows,function(row)!setequal(names(row),fields)||anyDuplicated(names(row))>0L,logical(1))))
    stop("INTERPRETATION_EXPORT_COLUMNS_INVALID",call.=FALSE)
  scalar_text <- function(v) {
    if(is.null(v)) return(NA_character_)
    if(is.list(v)) return(as.character(jsonlite::toJSON(unname(v),auto_unbox=TRUE,null="null",digits=17)))
    if(is.numeric(v)) return(formatC(v,format="g",digits=17))
    as.character(v)
  }
  as.data.frame(setNames(lapply(fields,function(name) {
    values <- lapply(rows,`[[`,name)
    if(any(vapply(values,function(v)is.character(v)||is.list(v),logical(1)))) return(vapply(values,scalar_text,character(1)))
    if(any(vapply(values,is.logical,logical(1)))) return(vapply(values,function(v)if(is.null(v))NA else as.logical(v),logical(1)))
    vapply(values,function(v)if(is.null(v))NA_real_ else as.numeric(v),numeric(1))
  }),fields),stringsAsFactors=FALSE,check.names=FALSE)
}

# Plot-only helpers. Preserve every category character, including long tokens
# without spaces; wrapping inserts line breaks and never abbreviates a level.
common_interpretation_plot_wrap <- function(value,width=26L) {
  pieces <- strsplit(enc2utf8(value),"",fixed=TRUE)[[1L]];lines <- character()
  while(length(pieces)>width) {
    candidates <- which(pieces[seq_len(width)]%in%c("_"," ","-","/"))
    candidates <- candidates[candidates>=floor(width*.4)]
    cut <- if(length(candidates))max(candidates) else width
    lines <- c(lines,paste0(pieces[seq_len(cut)],collapse=""));pieces <- pieces[-seq_len(cut)]
  }
  paste(c(lines,paste0(pieces,collapse="")),collapse="\n")
}

common_interpretation_plot_lanes <- function(x,widths) {
  lanes <- list();assignment <- integer(length(x))
  for(i in order(x,seq_along(x))) {
    interval <- c(x[[i]]-widths[[i]]/2,x[[i]]+widths[[i]]/2)
    lane <- 1L
    while(lane<=length(lanes)&&any(vapply(lanes[[lane]],function(other)
      interval[[1L]]<other[[2L]]+1.5&&interval[[2L]]>other[[1L]]-1.5,logical(1)))) lane <- lane+1L
    if(lane>length(lanes))lanes[[lane]] <- list()
    lanes[[lane]][[length(lanes[[lane]])+1L]] <- interval;assignment[[i]] <- lane
  }
  assignment
}

common_interpretation_nomogram_plan <- function(rec) {
  groups <- lapply(rec$nomogram$domains,function(domain) {
    rows <- Filter(function(row)identical(row$feature,domain$feature),rec$nomogram$axes)
    raw <- vapply(rows,function(row) {
      value <- if(identical(row$input_kind,"missing"))row$resolved_value else row$value
      text <- if(is.numeric(value))formatC(value,digits=4,format="g") else as.character(value)
      if(identical(row$input_kind,"missing"))paste0("missing -> ",text) else text
    },character(1))
    labels <- vapply(raw,common_interpretation_plot_wrap,character(1))
    lines <- strsplit(labels,"\n",fixed=TRUE);nlines <- lengths(lines)
    x <- vapply(rows,`[[`,numeric(1),"points")
    missing <- vapply(rows,function(row)identical(row$input_kind,"missing"),logical(1))
    # Conservative character-based planning bounds the image height before the
    # PNG is opened; actual device text widths decide collision-free lanes.
    widths <- vapply(lines,function(line)max(nchar(line,type="width"))*1.6,numeric(1))
    required <- .4
    for(indices in list(which(!missing),which(missing)))if(length(indices)) {
      lanes <- common_interpretation_plot_lanes(x[indices],widths[indices])
      required <- required+sum(vapply(seq_len(max(lanes)),function(lane)
        .20*max(nlines[indices[lanes==lane]])+.13,numeric(1)))
    }
    feature_label <- common_interpretation_plot_wrap(paste0(domain$feature," [",domain$unit,"]"))
    required <- max(required,.20*length(strsplit(feature_label,"\n",fixed=TRUE)[[1L]])+.3)
    list(feature=domain$feature,feature_label=feature_label,rows=rows,raw_labels=raw,labels=labels,
      points=x,missing=missing,required_inches=required)
  })
  upper <- max(4.6,sum(vapply(groups,`[[`,numeric(1),"required_inches"))+1.8)
  list(groups=groups,upper_inches=upper,height=as.integer(ceiling(150*(upper+3.2))))
}

common_interpretation_plot_nomogram_features <- function(rec,plan,source_label="SYNTHETIC TEST ONLY") {
  graphics::layout(matrix(c(1,2),2,1),heights=c(plan$upper_inches,3.2))
  font <- .78;feature_font <- .85
  labels <- vapply(plan$groups,`[[`,character(1),"feature_label")
  left <- max(1.1,max(graphics::strwidth(labels,units="inches",cex=feature_font))+.30)
  graphics::par(mai=c(.65,left,1.05,.35),mgp=c(2.2,.65,0),xaxs="i",yaxs="i")
  graphics::plot.new()
  all_labels <- unlist(lapply(plan$groups,`[[`,"labels"),use.names=FALSE)
  padding <- max(graphics::strwidth(all_labels,units="inches",cex=font))/2+.12
  pin <- graphics::par("pin");core_width <- pin[[1L]]-2*padding
  if(!is.finite(core_width)||core_width<=1)stop("INTERPRETATION_LABEL_LAYOUT_WIDTH",call.=FALSE)
  xpad <- 100*padding/core_width;xlim <- c(-xpad,100+xpad)
  prepared <- lapply(plan$groups,function(group) {
    group$widths <- graphics::strwidth(group$labels,units="inches",cex=font)*100/core_width
    group$heights <- graphics::strheight(group$labels,units="inches",cex=font)
    group$above <- group$below <- list(indices=integer(),lanes=integer(),heights=numeric(),height=0)
    for(side in c("above","below")) {
      indices <- which(if(side=="above")!group$missing else group$missing)
      if(!length(indices))next
      lanes <- common_interpretation_plot_lanes(group$points[indices],group$widths[indices])
      heights <- vapply(seq_len(max(lanes)),function(lane)max(group$heights[indices[lanes==lane]])+.12,numeric(1))
      group[[side]] <- list(indices=indices,lanes=lanes,heights=heights,height=sum(heights))
    }
    group$required <- max(group$above$height+group$below$height+.38,
      graphics::strheight(group$feature_label,units="inches",cex=feature_font)+.3)
    group
  })
  required <- sum(vapply(prepared,`[[`,numeric(1),"required"))
  if(!is.finite(required)||required>pin[[2L]])stop("INTERPRETATION_LABEL_LAYOUT_HEIGHT",call.=FALSE)
  graphics::plot.window(xlim=xlim,ylim=c(0,pin[[2L]]))
  graphics::axis(1,at=seq(0,100,20));graphics::box()
  graphics::title(main=if(isTRUE(rec$nomogram$constant_model))"Constant model: all feature points are zero" else "Frozen numerical nomogram",
    xlab="Feature points (frozen observed domain)")
  graphics::mtext(paste0(source_label," | ",rec$definition$score_scale,
    " | no extrapolation | scientific review pending"),side=3,line=.4,cex=.72)
  extra <- (pin[[2L]]-required)/max(length(prepared),1L);cursor <- 0;boxes <- list()
  for(group in prepared) {
    axis_y <- cursor+group$below$height+.19+extra/2
    graphics::text(xlim[[1L]]-.12*100/core_width,axis_y,group$feature_label,adj=1,cex=feature_font,xpd=NA)
    graphics::segments(min(group$points),axis_y,max(group$points),axis_y,col="#555555",lwd=2)
    graphics::points(group$points,rep(axis_y,length(group$points)),pch=ifelse(group$missing,1,19),col="#176B6B",cex=.8)
    group_boxes <- list()
    for(side in c("above","below")) {
      layout <- group[[side]]
      for(k in seq_along(layout$indices)) {
        j <- layout$indices[[k]];lane <- layout$lanes[[k]]
        center <- sum(layout$heights[seq_len(lane-1L)])+layout$heights[[lane]]/2+.10
        y <- axis_y+if(side=="above")center else -center
        half_height <- group$heights[[j]]/2;half_width <- group$widths[[j]]/2;x <- group$points[[j]]
        group_boxes[[length(group_boxes)+1L]] <- list(feature=group$feature,input_kind=group$rows[[j]]$input_kind,
          original=group$raw_labels[[j]],wrapped=group$labels[[j]],points=x,
          left=x-half_width,right=x+half_width,bottom=y-half_height,top=y+half_height,
          plot_left=xlim[[1L]],plot_right=xlim[[2L]],plot_bottom=0,plot_top=pin[[2L]])
        graphics::segments(x,axis_y,x,if(side=="above")y-half_height-.025 else y+half_height+.025,
          col="#A5B7B7",lwd=.7)
      }
    }
    # Labels cover leader lines behind them; no category or missing route is
    # shortened, elided, clipped at zero/100 or left to a separate CSV lookup.
    for(box in group_boxes) {
      graphics::rect(box$left-.15,box$bottom-.02,box$right+.15,box$top+.02,col="white",border=NA)
      graphics::text((box$left+box$right)/2,(box$bottom+box$top)/2,box$wrapped,cex=font)
    }
    boxes <- c(boxes,group_boxes);cursor <- cursor+group$required+extra
  }
  invisible(boxes)
}

common_interpretation_plot_nomogram_total <- function(rec,policy) {
  graphics::par(mar=c(5,7,4,2),xaxs="i",yaxs="i")
  graphics::plot.new()
  axis <- rec$nomogram$total_axis;points <- vapply(axis,`[[`,numeric(1),"total_points")
  scores <- vapply(axis,`[[`,numeric(1),"score");prediction <- vapply(axis,`[[`,numeric(1),"prediction")
  labels <- if(rec$family=="binomial")paste0("p=",formatC(prediction,digits=4,format="g")) else character()
  font <- .72;pin <- graphics::par("pin")
  widths <- if(length(labels))graphics::strwidth(labels,units="inches",cex=font) else 0
  heights <- if(length(labels))graphics::strheight(labels,units="inches",cex=font) else 0
  # Reserve physical space on both horizontal ends and above the highest
  # score. Device-measured annotation boxes, not percentage guesses, define
  # these plot limits; points and annotations use the unchanged provider data.
  xpad_inches <- max(.10,max(widths)/2+.10)
  bottom_inches <- .10;top_inches <- if(length(labels))max(heights)+.18 else .10
  core_width <- pin[[1L]]-2*xpad_inches;core_height <- pin[[2L]]-bottom_inches-top_inches
  if(core_width<=1||core_height<=.3)stop("INTERPRETATION_TOTAL_LABEL_LAYOUT",call.=FALSE)
  xrange <- range(points);if(diff(xrange)==0)xrange <- xrange+c(-.5,.5)
  yrange <- range(scores);if(diff(yrange)==0)yrange <- yrange+c(-.5,.5)
  xunits <- diff(xrange)/core_width;yunits <- diff(yrange)/core_height
  xlim <- xrange+c(-1,1)*xpad_inches*xunits
  ylim <- yrange+c(-bottom_inches,top_inches)*yunits
  graphics::plot.window(xlim=xlim,ylim=ylim);graphics::axis(1);graphics::axis(2);graphics::box()
  graphics::lines(points,scores,type="b",pch=19,col="#A84432")
  graphics::title(xlab="Total points",ylab=if(rec$family=="binomial")"Raw log odds (unit 1)" else paste0("Score (",policy$score_unit,")"),
    main="Total points -> frozen score / output")
  boxes <- list()
  if(length(labels))for(i in seq_along(labels)) {
    bottom <- scores[[i]]+.07*yunits;half_width <- widths[[i]]*xunits/2;height <- heights[[i]]*yunits
    graphics::text(points[[i]],bottom,labels[[i]],adj=c(.5,0),cex=font)
    boxes[[i]] <- list(label=labels[[i]],total_points=points[[i]],left=points[[i]]-half_width,
      right=points[[i]]+half_width,bottom=bottom,top=bottom+height,
      plot_left=xlim[[1L]],plot_right=xlim[[2L]],plot_bottom=ylim[[1L]],plot_top=ylim[[2L]])
  }
  graphics::mtext(if(rec$family=="binomial")"p = logistic(raw log odds); contributions above are not probability SHAP" else
    paste0("Output = signed score in ",policy$outcome_unit,"; no clipping"),side=3,line=.4,cex=.75)
  invisible(list(labels=boxes,markers=lapply(seq_along(points),function(i)list(x=points[[i]],y=scores[[i]],
    plot_left=xlim[[1L]],plot_right=xlim[[2L]],plot_bottom=ylim[[1L]],plot_top=ylim[[2L]]))))
}

common_write_interpretation_outputs <- function(result,output_dir) {
  rec <- result$interpretation;policy <- result$provenance$target_policy
  metadata <- list(method_id=result$method_id,method_version=result$method_version,provider_version=result$provider$version,
    core_version=result$core_version,run_id=result$run_id,model_method_id=rec$model_method_id,family=rec$family,
    score_scale=rec$definition$score_scale,score_unit=policy$score_unit,coalition_unit="raw_feature",
    background_definition="full_frozen_training_empirical",n_background=rec$flow$n_background,
    n_application=rec$flow$n_application,model_sha256=rec$model_sha256,explainer_sha256=rec$explainer_sha256,
    background_sha256=rec$background_sha256,transform_sha256=rec$transform_sha256,
    scientific_review="pending",export_status="local_only",test_only=result$test_only)
  if(!is.null(result$data_origin)) metadata <- c(metadata,list(data_origin=result$data_origin,task_purpose=result$task_purpose))
  table <- function(name,rows,caption,denominator=NULL,units="explicit per field") {
    if(!length(rows)) return(invisible(NULL))
    if(any(names(metadata)%in%names(rows[[1L]]))) stop("INTERPRETATION_EXPORT_METADATA_COLLISION",call.=FALSE)
    frame <- common_interpretation_frame(lapply(rows,function(row)c(metadata,row)))
    file <- file.path(output_dir,"tables",paste0(name,".csv"));common_psm_write_frame(frame,file)
    result$tables[[length(result$tables)+1L]] <<- common_artifact(name,"table",file,result,
      lapply(rows,function(row)row$result_id %||% rec$result_id),denominator,units,caption)
  }
  flowrows <- lapply(names(rec$flow)[names(rec$flow)!="missing_by_feature"],function(name)
    list(result_id=rec$result_id,count_name=name,value=rec$flow[[name]],count_semantics=if(is.null(result$data_origin))"synthetic_subject_or_frozen_design_count" else "explicit_subject_or_frozen_design_count"))
  table("interpretation_flow",flowrows,paste0(common_penalized_source_label(result),". Frozen training background and application denominators; no outcome evaluation."))
  missingrows <- lapply(names(rec$flow$missing_by_feature),function(name)c(list(result_id=rec$result_id,feature=name),rec$flow$missing_by_feature[[name]]))
  table("interpretation_missingness",missingrows,paste0(common_penalized_source_label(result),". Raw-feature missing counts. Missing values follow the frozen training imputation route."))
  table("interpretation_global_importance",rec$shap$global_importance,
    paste0(common_penalized_source_label(result),". Application mean absolute grouped interventional SHAP. Contributions are summed within each raw feature before absolute values; no conditional, probability-scale or causal SHAP claim."),
    rec$flow$n_application,policy$score_unit)
  table("nomogram_domains",rec$nomogram$domains,
    paste0(common_penalized_source_label(result),". Exact frozen observed training numeric domains or fitted category sets, original units and explicit imputation. Unknown categories and numeric extrapolation are refused."))
  table("nomogram_axes",rec$nomogram$axes,
    paste0(common_penalized_source_label(result),". Provider-generated feature points on original input units; missing values use the stated frozen route. Display rounding does not redefine the numeric mapping."))
  mapping <- lapply(rec$nomogram$total_axis,function(row)c(row,list(constant_model=rec$nomogram$constant_model,
    score_at_zero=rec$nomogram$score_at_zero,score_per_point=rec$nomogram$score_per_point,
    points_denominator=rec$nomogram$points_denominator,max_total_points=rec$nomogram$max_total_points,
    score_mapping="score_at_zero_plus_score_per_point_times_total_points_or_constant_score",
    prediction_link=if(rec$family=="binomial")"logistic" else "identity")))
  table("nomogram_mapping",mapping,
    paste0(common_penalized_source_label(result),". Frozen total-points to affine-score and prediction mapping. Binomial score is raw log odds and its probability link is separate."))
  if(!identical(rec$status,"completed")) return(result)
  figure <- function(name,ids,caption,draw,denominator=NULL,units="explicit axes",height=900L) {
    file <- file.path(output_dir,"figures",paste0(name,".png"));opened <- FALSE;completed <- FALSE
    tryCatch({grDevices::png(file,width=1800,height=height,res=150);opened<-TRUE;draw();completed<-TRUE},error=function(e)NULL,
      finally=if(opened)grDevices::dev.off())
    if(!completed) {
      result$warnings[[length(result$warnings)+1L]] <<- list(code="INTERPRETATION_FIGURE_FAILED",stage="figures")
      result$execution_status <<- "partial";result$applicability_status <<- "limited"
      result["reason_code"] <<- list("INTERPRETATION_FIGURE_FAILED")
      return(invisible(NULL))
    }
    result$figures[[length(result$figures)+1L]] <<- common_artifact(name,"figure",file,result,ids,denominator,units,caption)
  }
  figure("interpretation_global_importance",lapply(rec$shap$global_importance,`[[`,"result_id"),
    paste0(common_penalized_source_label(result),". Application-population mean absolute raw-feature-grouped interventional SHAP, on the declared score scale; empirical frozen training background. No uncertainty or causal claim."),function() {
      rows <- rec$shap$global_importance;values <- vapply(rows,`[[`,numeric(1),"mean_abs_shap")
      names <- vapply(rows,`[[`,character(1),"feature");order <- order(values)
      graphics::par(mar=c(5,13,5,2));graphics::barplot(values[order],names.arg=names[order],horiz=TRUE,las=1,
        xlim=c(0,if(max(values)>0)max(values)*1.15 else 1),col="#176B6B",border=NA,
        xlab=if(rec$family=="binomial")"Mean absolute grouped contribution (raw log odds; unit 1)" else
          paste0("Mean absolute grouped contribution (",policy$score_unit,")"),main="Frozen affine interpretation: global importance")
      graphics::mtext(paste0("Background n = ",rec$flow$n_background,"; application n = ",rec$flow$n_application,
        "; ",rec$definition$score_scale,paste0("; ",common_penalized_source_label(result),"; scientific review pending")),side=3,line=.4,cex=.72)
    },rec$flow$n_application,policy$score_unit)
  nomogram_plan <- common_interpretation_nomogram_plan(rec)
  figure("nomogram",lapply(c(rec$nomogram$axes,rec$nomogram$total_axis),`[[`,"result_id"),
    paste0(common_penalized_source_label(result),". Numerical nomogram on frozen training domains. Feature axes show original units and the frozen missing-value route. Total points reconstruct the score; probability conversion is shown only for binomial models. Full-precision backchecks, no extrapolation or clinical approval."),function() {
      common_interpretation_plot_nomogram_features(rec,nomogram_plan,common_penalized_source_label(result))
      common_interpretation_plot_nomogram_total(rec,policy)
    },units=paste0("points; ",policy$score_unit),height=nomogram_plan$height)
  result
}
