# Affine explanation and display arithmetic only. No fit, baseline estimation,
# outcome-based selection, or competing prediction implementation lives here.
`%ce_or%` <- function(a,b)if(is.null(a))b else a
ce_need <- function(ok,code)if(!isTRUE(ok))stop(code,call.=FALSE)
ce_definition <- function()list(method="exact_affine_grouped_interventional_shap",
  background="frozen_training_centering_first_moments",encoded_expectation="analytic_zero_after_training_centering",
  coalition_unit="original_feature",missing_policy="frozen_training_median_mode",
  score_scale="centered_log_relative_hazard",score_unit="1",conditional=FALSE,probability_scale=FALSE,causal=FALSE)
ce_checks <- function(n=0L,a=0,s=0,r=0)list(atol=1e-10,rtol=1e-10,max_additivity_error=a,
  max_score_backcheck_error=s,max_risk_backcheck_error=r,n_application_checked=as.integer(n),passed=TRUE)
ce_data <- function(rows,model) {
  spec<-model$spec;n<-length(rows)
  cols<-setNames(list(vapply(rows,`[[`,"","subject_id")),spec$id)
  if(!is.null(spec$split$group_field))cols[[spec$split$group_field]]<-vapply(rows,`[[`,"","group_id")
  for(j in seq_along(spec$features)) {
    f<-spec$features[[j]]
    cols[[f$name]]<-if(f$type=="number")vapply(rows,function(r)if(is.null(r$values[[j]]))NA_real_ else r$values[[j]],0.0) else
      vapply(rows,function(r)if(is.null(r$values[[j]]))NA_character_ else r$values[[j]],"")
  }
  cols[[spec$split$partition_field]]<-rep("holdout",n);cols[[spec$split$fold_field]]<-rep(0L,n)
  as.data.frame(cols,check.names=FALSE,stringsAsFactors=FALSE)
}
# Display-only inverse link for total-score axes, backchecked on every application
# against the sole cox_penalized_v10_predict owner. It never produces model rows.
ce_display_probability <- function(score,baseline,horizons) {
  times<-penalized_v08_vector(baseline$event_times);hazards<-penalized_v08_vector(baseline$cumulative_hazard)
  h<-c(0,hazards)[findInterval(horizons,times)+1L]
  out<-lapply(seq_along(h),function(i) {
    if(h[[i]]==0)return(list(survival_probability=1,event_risk=0))
    log_h<-log(h[[i]])+score
    cumulative<-if(log_h>log(.Machine$double.xmax))Inf else exp(log_h)
    list(survival_probability=exp(-cumulative),event_risk=-expm1(-cumulative))
  })
  ce_need(all(vapply(out,function(v)all(is.finite(unlist(v)))&&all(unlist(v)>=0&unlist(v)<=1),TRUE)),"CE_DISPLAY_RISK_NONFINITE")
  out
}
ce_nomogram <- function(model,declared,horizons,resource_budget=NULL) {
  features<-model$spec$features;columns<-model$preprocessor$columns
  ce_need(length(declared)==length(features),"CE_DOMAIN_FEATURE_SET_INVALID")
  ce_need(identical(vapply(declared,`[[`,"","feature"),vapply(features,`[[`,"","name")),"CE_DOMAIN_FEATURE_ORDER_INVALID")
  beta<-penalized_v08_vector(model$coefficients);domains<-axes<-list()
  for(j in seq_along(features)) {
    d<-declared[[j]];f<-features[[j]];fm<-model$preprocessor$features[[j]]
    ce_need(identical(d$type,f$type)&&identical(d$unit,model$semantics$features[[j]]$unit)&&isTRUE(d$prespecified)&&penalized_v08_string(d$source_note),"CE_DOMAIN_SEMANTICS_INVALID")
    if(f$type=="number") {
      ce_need(penalized_v08_number(d$minimum)&&penalized_v08_number(d$maximum)&&d$minimum<=d$maximum&&
        fm$impute>=d$minimum&&fm$impute<=d$maximum&&length(d$levels)==0L,"CE_NUMERIC_DOMAIN_INVALID")
      fractions<-seq(0,1,length.out=5L);values<-as.list(unique((1-fractions)*d$minimum+fractions*d$maximum))
    } else {
      ce_need(is.null(d$minimum)&&is.null(d$maximum)&&identical(d$levels,fm$levels),"CE_CATEGORY_DOMAIN_INVALID")
      values<-fm$levels
    }
    axis_values<-c(values,list(NULL));n<-length(axis_values)
    ref<-lapply(model$preprocessor$features,function(z)rep(z$impute,n));names(ref)<-vapply(features,`[[`,"","name")
    ref[[f$name]]<-vapply(axis_values,function(z)if(is.null(z))if(f$type=="number")NA_real_ else NA_character_ else z,if(f$type=="number")0.0 else "")
    x<-penalized_v08_prepare(as.data.frame(ref,check.names=FALSE,stringsAsFactors=FALSE),features,model$preprocessor,resource_budget=resource_budget)$x
    scores<-interpretation_v09_group_scores(x,model,beta)[,j]
    low<-min(scores);high<-max(scores);range<-high-low
    ce_need(is.finite(range)&&range>=0,"CE_NOMOGRAM_NONFINITE")
    domains[[j]]<-c(d,list(impute_value=fm$impute,n_encoded_columns=as.integer(sum(vapply(columns,function(z)z$feature==f$name,TRUE))),score_min=low,score_max=high,score_range=range))
    for(i in seq_along(axis_values))axes[[length(axes)+1L]]<-list(feature=f$name,type=f$type,unit=d$unit,
      input_kind=if(is.null(axis_values[[i]]))"missing" else "value",value=axis_values[[i]],
      resolved_value=axis_values[[i]] %ce_or% fm$impute,score_contribution=scores[[i]],points=0)
  }
  ranges<-vapply(domains,`[[`,0.0,"score_range");den<-max(ranges);constant<-den==0
  per<-if(constant)NULL else den/100
  zero<--model$baseline$center+sum(vapply(domains,`[[`,0.0,"score_min"))
  maximum<-if(constant)0 else sum(ranges/den)*100
  ce_need(is.finite(zero)&&is.finite(maximum)&&(constant||is.finite(per)&&per>0),"CE_NOMOGRAM_SCALE_INVALID")
  for(i in seq_along(axes)) {
    j<-match(axes[[i]]$feature,vapply(features,`[[`,"","name"))
    axes[[i]]$points<-if(constant)0 else (axes[[i]]$score_contribution-domains[[j]]$score_min)/den*100
  }
  ticks<-if(constant)0 else seq(0,maximum,length.out=5L);total<-list()
  for(points in ticks) {
    score<-if(constant)zero else zero+per*points
    risks<-ce_display_probability(score,model$baseline,penalized_v08_vector(horizons))
    for(k in seq_along(horizons))total[[length(total)+1L]]<-c(list(total_points=points,score=score,horizon=horizons[[k]]),risks[[k]])
  }
  list(domain_policy="prespecified_display_domains",training_feature_range_support="unknown",constant_on_display_domain=constant,
    score_at_zero=zero,score_per_point=per,points_denominator=den,max_total_points=maximum,domains=domains,axes=axes,total_axis=total)
}
ce_explain <- function(data,x,model,nomogram,horizons) {
  for(d in nomogram$domains) {
    v<-data[[d$feature]];present<-!is.na(v)
    if(d$type=="number")ce_need(all(v[present]>=d$minimum&v[present]<=d$maximum),"CE_OUTSIDE_DISPLAY_DOMAIN")
    else ce_need(all(v[present]%in%penalized_v08_vector(d$levels)),"CE_UNKNOWN_CATEGORY")
  }
  beta<-penalized_v08_vector(model$coefficients);phi<-interpretation_v09_group_scores(x,model,beta)
  base<--model$baseline$center;predicted<-cox_penalized_v10_predict(x,beta,model$baseline,penalized_v08_vector(horizons))
  score<-predicted$centered_linear_predictor;reconstructed<-base+rowSums(phi)
  ce_need(interpretation_v09_close(reconstructed,score),"CE_SHAP_ADDITIVITY_FAILED")
  minima<-vapply(nomogram$domains,`[[`,0.0,"score_min")
  points<-if(nomogram$constant_on_display_domain)matrix(0,nrow(x),length(model$spec$features)) else
    sweep(phi,2,minima,`-`)/nomogram$points_denominator*100
  ce_need(all(is.finite(points))&&all(points>=-1e-10),"CE_NOMOGRAM_POINTS_INVALID")
  totals<-rowSums(points)
  mapped<-if(nomogram$constant_on_display_domain)rep(nomogram$score_at_zero,nrow(x)) else nomogram$score_at_zero+nomogram$score_per_point*totals
  ce_need(interpretation_v09_close(mapped,score),"CE_NOMOGRAM_SCORE_BACKCHECK_FAILED")
  risk_error<-0
  for(i in seq_len(nrow(x))) {
    displayed<-ce_display_probability(mapped[[i]],model$baseline,penalized_v08_vector(horizons))
    risk<-vapply(displayed,`[[`,0.0,"event_risk");surv<-vapply(displayed,`[[`,0.0,"survival_probability")
    ce_need(interpretation_v09_close(risk,predicted$risk[i,])&&interpretation_v09_close(surv,predicted$survival[i,]),"CE_NOMOGRAM_RISK_BACKCHECK_FAILED")
    risk_error<-max(risk_error,abs(risk-predicted$risk[i,]),abs(surv-predicted$survival[i,]))
  }
  importance<-lapply(seq_along(model$spec$features),function(j) {
    v<-phi[,j];f<-model$spec$features[[j]]
    list(feature=f$name,type=f$type,n=nrow(x),sum_abs_shap=sum(abs(v)),mean_abs_shap=mean(abs(v)),mean_shap=mean(v),min_shap=min(v),max_shap=max(v))
  })
  contributions<-nomogram_rows<-list()
  for(i in seq_len(nrow(x)))for(j in seq_along(model$spec$features)) {
    contributions[[length(contributions)+1L]]<-list(subject_id=data[[model$spec$id]][[i]],feature=model$spec$features[[j]]$name,
      phi=phi[i,j],base_value=base,score=score[[i]])
    nomogram_rows[[length(nomogram_rows)+1L]]<-list(subject_id=data[[model$spec$id]][[i]],feature=model$spec$features[[j]]$name,
      score_contribution=phi[i,j],points=points[i,j],total_points=totals[[i]],reconstructed_score=mapped[[i]])
  }
  list(record=list(definition=ce_definition(),base_value=base,global_importance=importance,nomogram=nomogram,
    checks=ce_checks(nrow(x),max(abs(reconstructed-score)),max(abs(mapped-score)),risk_error)),
    contributions=contributions,nomogram_rows=nomogram_rows)
}
