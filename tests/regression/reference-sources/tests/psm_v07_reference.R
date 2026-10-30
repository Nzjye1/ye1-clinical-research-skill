# Independent stats/source-formula reference. Never sources the production code.
if(.Platform$OS.type=="windows")suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
args<-commandArgs(TRUE);Encoding(args)<-"UTF-8";stopifnot(length(args)==2)
.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
stopifnot(requireNamespace("jsonlite",quietly=TRUE))
input<-jsonlite::fromJSON(args[1],simplifyVector=FALSE)
vec<-function(x)unlist(x,use.names=FALSE)
byte_key<-function(x)vapply(enc2utf8(x),function(s)paste(sprintf("%02x",as.integer(charToRaw(s))),collapse=""),"")
empty_pairs<-function()data.frame(treated_index=integer(),control_index=integer(),distance=double())

# Build the full candidate-distance table before assigning available controls.
# This independent implementation follows the specified priority, not a model
# package's default ordering or an outcome-dependent matching criterion.
candidate_assignment<-function(ids,treatment,score,eligible,width) {
  ti<-which(eligible & treatment==1);ci<-which(eligible & treatment==0)
  if(!length(ti)||!length(ci))return(empty_pairs())
  priority<-ti[order(-score[ti],byte_key(ids[ti]),method="radix")]
  candidates<-expand.grid(treated_index=ti,control_index=ci,KEEP.OUT.ATTRS=FALSE)
  candidates$distance<-as.vector(abs(outer(score[ti],score[ci],"-")))
  candidates<-candidates[candidates$distance<=width,,drop=FALSE]
  candidates<-candidates[order(match(candidates$treated_index,priority),candidates$distance,
    byte_key(ids[candidates$control_index]),method="radix"),,drop=FALSE]
  chosen<-Reduce(function(state,treated) {
    possible<-candidates[candidates$treated_index==treated & !(candidates$control_index %in% state$used),,drop=FALSE]
    if(nrow(possible)) {
      state$rows[[length(state$rows)+1L]]<-possible[1L,,drop=FALSE]
      state$used<-c(state$used,possible$control_index[1L])
    }
    state
  },priority,init=list(rows=list(),used=integer()))
  if(!length(chosen$rows))empty_pairs() else {result<-do.call(rbind,chosen$rows);rownames(result)<-NULL;result}
}
match_reference<-function(ids,treatment,score,multiplier) {
  tr<-range(score[treatment==1]);co<-range(score[treatment==0]);lo<-max(tr[1],co[1]);hi<-min(tr[2],co[2])
  retained<-score>=lo & score<=hi
  answer<-list(lower=lo,upper=hi,support_mask=as.list(retained),logit_sd=NA_real_,caliper_width=NA_real_,pairs=empty_pairs(),reason_code=NULL)
  if(lo>hi){answer$reason_code<-"NO_COMMON_SUPPORT";return(answer)}
  if(sum(retained)>=2L) {
    answer$logit_sd<-stats::sd(score[retained]);answer$caliper_width<-multiplier*answer$logit_sd
  }
  if(!any(retained & treatment==1)||!any(retained & treatment==0)) {
    answer$reason_code<-"COMMON_SUPPORT_ARM_EMPTY";return(answer)
  }
  answer$pairs<-candidate_assignment(ids,treatment,score,retained,answer$caliper_width)
  if(!nrow(answer$pairs))answer$reason_code<-"NO_MATCHED_PAIRS"
  answer
}
effect_reference<-function(treated,control) {
  stopifnot(length(treated)==length(control));m<-length(treated)
  output<-list(n_pairs=m,treated_mean=NA_real_,control_mean=NA_real_,estimate=NA_real_,
    paired_difference_variance=NA_real_,standard_error=NA_real_,df=NA_integer_,ci_lower=NA_real_,ci_upper=NA_real_,
    t_statistic=NA_real_,p_value=NA_real_,treated_variance=NA_real_,control_variance=NA_real_,
    treated_control_covariance=NA_real_,variance_identity_difference=NA_real_,iid_standard_error=NA_real_,
    inference_status="unavailable",inference_reason_code=if(m==0)"NO_MATCHED_PAIRS" else "INSUFFICIENT_MATCHED_PAIRS")
  if(!m)return(output)
  difference<-treated-control
  output$treated_mean<-mean(treated);output$control_mean<-mean(control);output$estimate<-mean(difference)
  output$df<-m-1L
  if(m<2)return(output)
  output$paired_difference_variance<-sum((difference-mean(difference))^2)/(m-1)
  output$treated_variance<-stats::var(treated);output$control_variance<-stats::var(control)
  output$treated_control_covariance<-stats::cov(treated,control)
  output$variance_identity_difference<-output$paired_difference_variance-(output$treated_variance+output$control_variance-2*output$treated_control_covariance)
  output$iid_standard_error<-sqrt((output$treated_variance+output$control_variance)/m)
  output$df<-m-1L
  if(output$paired_difference_variance==0) {
    output$standard_error<-0;output$inference_reason_code<-"ZERO_PAIRED_VARIANCE";return(output)
  }
  # t.test is an independent base-R implementation; keep explicit covariance
  # moments alongside it to detect an iid-SE substitution.
  result<-stats::t.test(treated,control,paired=TRUE,conf.level=.95)
  output$standard_error<-sqrt(output$paired_difference_variance/m)
  output$t_statistic<-unname(result$statistic);output$p_value<-result$p.value
  output$ci_lower<-unname(result$conf.int[1]);output$ci_upper<-unname(result$conf.int[2])
  output$inference_status<-"available";output$inference_reason_code<-NULL
  output
}
balance_reference<-function(data,treatment,pairs,options) {
  before_t<-which(treatment==1);before_c<-which(treatment==0);after_t<-pairs$treated_index;after_c<-pairs$control_index
  measures<-list()
  for(name in vec(options$covariates)) {
    declaration<-options$categorical[[name]]
    if(is.null(declaration))measures[[length(measures)+1L]]<-list(name=name,kind="numeric",level=NULL,is_reference=FALSE,value=as.numeric(data[[name]]))
    else for(level in vec(declaration$levels))measures[[length(measures)+1L]]<-list(name=name,kind="indicator",level=level,is_reference=level==declaration$reference,value=as.numeric(data[[name]]==level))
  }
  lapply(measures,function(measure) {
    x<-measure$value;mt<-mean(x[before_t]);mc<-mean(x[before_c]);indicator<-measure$kind=="indicator"
    scale<-if(indicator)sqrt(mt*(1-mt)) else stats::sd(x[before_t])
    pre_reason<-if(!is.finite(scale))"REFERENCE_SD_UNAVAILABLE" else if(scale==0)"ZERO_REFERENCE_SD" else NULL
    post_reason<-if(!length(after_t))"NO_MATCHED_PAIRS" else pre_reason
    list(covariate=measure$name,kind=measure$kind,level=measure$level,is_reference=measure$is_reference,
      sd_kind=if(indicator)"bernoulli_p1mp" else "sample_n_minus_1",denominator_scope="pre_support_complete_case_treated",reference_sd=scale,
      n_before_treated=length(before_t),n_before_control=length(before_c),mean_before_treated=mt,mean_before_control=mc,
      smd_before=if(is.null(pre_reason))(mt-mc)/scale else NA_real_,smd_before_reason=pre_reason,
      n_after_treated=length(after_t),n_after_control=length(after_c),
      mean_after_treated=if(length(after_t))mean(x[after_t]) else NA_real_,mean_after_control=if(length(after_c))mean(x[after_c]) else NA_real_,
      smd_after=if(is.null(post_reason))(mean(x[after_t])-mean(x[after_c]))/scale else NA_real_,smd_after_reason=post_reason)
  })
}
overlap_reference<-function(ps,treatment,support,pairs,options) {
  edges<-as.numeric(vec(options$diagnostics$ps_overlap_edges));populations<-list(ps_fit=seq_along(ps),support_retained=which(support),matched=c(pairs$treated_index,pairs$control_index))
  output<-list()
  for(population in names(populations))for(arm in c("treated","control")) {
    members<-populations[[population]];members<-members[treatment[members]==if(arm=="treated")1 else 0]
    for(j in seq_len(length(edges)-1L)) {
      included<-ps[members]>=edges[j] & if(j==length(edges)-1L)ps[members]<=edges[j+1L] else ps[members]<edges[j+1L]
      count<-sum(included);denominator<-length(members)
      output[[length(output)+1L]]<-list(population=population,arm=arm,bin_index=j,lower=edges[j],upper=edges[j+1L],right_inclusive=j==length(edges)-1L,
        n=count,denominator=denominator,proportion=if(denominator)count/denominator else NA_real_)
    }
  }
  output
}
analyze_reference<-function(input) {
  opt<-input$options;sem<-input$semantics;raw<-input$rows;columns<-unique(c(sem$subject_id,opt$treatment,opt$outcome,vec(opt$covariates)))
  missing<-function(x)is.null(x)||length(x)==0||identical(x,"")
  frame<-as.data.frame(setNames(lapply(columns,function(name) {
    if(name==sem$subject_id||!is.null(opt$categorical[[name]]))vapply(raw,function(row)if(missing(row[[name]]))NA_character_ else as.character(row[[name]]),"")
    else vapply(raw,function(row)if(missing(row[[name]]))NA_real_ else as.numeric(row[[name]]),0)
  }),columns),stringsAsFactors=FALSE,check.names=FALSE)
  frame<-frame[order(byte_key(frame[[sem$subject_id]]),method="radix"),,drop=FALSE];rownames(frame)<-NULL
  treatment<-frame[[opt$treatment]];outcome<-frame[[opt$outcome]]
  stopifnot(all(is.finite(treatment)),all(treatment %in% c(0,1)),all(is.finite(outcome)),!anyDuplicated(frame[[sem$subject_id]]))
  covariates<-vec(opt$covariates);complete<-stats::complete.cases(frame[covariates]);fit_data<-frame[complete,,drop=FALSE]
  fit_t<-fit_data[[opt$treatment]];stopifnot(sum(fit_t==1)>=2,sum(fit_t==0)>=2)
  aliases<-paste0("feature",seq_along(covariates));design_data<-data.frame(response=fit_t)
  contrast<-list()
  for(j in seq_along(covariates)) {
    name<-covariates[j];declaration<-opt$categorical[[name]]
    if(is.null(declaration))design_data[[aliases[j]]]<-fit_data[[name]]
    else {
      levels<-as.character(vec(declaration$levels));design_data[[aliases[j]]]<-factor(fit_data[[name]],levels=levels)
      contrast[[aliases[j]]]<-stats::contr.treatment(levels,base=match(declaration$reference,levels))
    }
  }
  warnings<-character()
  fit<-withCallingHandlers(stats::glm(stats::reformulate(aliases,response="response"),data=design_data,family=stats::binomial(link="logit"),
    contrasts=if(length(contrast))contrast else NULL,control=stats::glm.control(epsilon=opt$guards$glm_epsilon,maxit=opt$guards$max_glm_iterations)),
    warning=function(w){warnings<<-c(warnings,conditionMessage(w));invokeRestart("muffleWarning")})
  stopifnot(fit$converged,!fit$boundary,length(warnings)==0,all(is.finite(stats::coef(fit))),fit$rank==length(stats::coef(fit)),
    all(fit$fitted.values>opt$guards$min_probability),all(fit$fitted.values<1-opt$guards$min_probability))
  ids<-fit_data[[sem$subject_id]];ps<-unname(fit$fitted.values);score<-unname(fit$linear.predictors)
  matched<-match_reference(ids,fit_t,score,opt$caliper$width);pairs<-matched$pairs
  pt<-pairs$treated_index;pc<-pairs$control_index;used<-c(pt,pc);support<-as.logical(vec(matched$support_mask))
  flow<-list(n_input=nrow(frame),n_input_treated=sum(treatment==1),n_input_control=sum(treatment==0),
    n_excluded_missing_covariates=sum(!complete),n_excluded_missing_treated=sum(!complete&treatment==1),n_excluded_missing_control=sum(!complete&treatment==0),
    missing_by_field=as.list(setNames(vapply(covariates,function(name)sum(is.na(frame[[name]])),0L),covariates)),
    n_complete_case=nrow(fit_data),n_complete_case_treated=sum(fit_t==1),n_complete_case_control=sum(fit_t==0),
    n_support_retained=sum(support),n_support_treated=sum(support&fit_t==1),n_support_control=sum(support&fit_t==0),
    n_discarded_support_treated=sum(!support&fit_t==1),n_discarded_support_control=sum(!support&fit_t==0),
    n_matched_pairs=nrow(pairs),n_matched_subjects=2*nrow(pairs),
    n_unmatched_support_treated=sum(support&fit_t==1)-nrow(pairs),n_unmatched_support_control=sum(support&fit_t==0)-nrow(pairs))
  pair_data<-data.frame(treated_subject_id=ids[pt],control_subject_id=ids[pc],treated_ps=ps[pt],control_ps=ps[pc],treated_logit=score[pt],control_logit=score[pc],
    logit_distance=pairs$distance,treated_outcome=fit_data[[opt$outcome]][pt],control_outcome=fit_data[[opt$outcome]][pc],difference=fit_data[[opt$outcome]][pt]-fit_data[[opt$outcome]][pc],stringsAsFactors=FALSE)
  scores<-data.frame(subject_id=ids,treatment=fit_t,propensity_score=ps,logit_ps=score,support_retained=support,matched=seq_along(ids)%in%used,stringsAsFactors=FALSE)
  # A valid support intersection can yield zero matches under its caliper.
  # That matching/effect reason does not make support construction unavailable.
  support_reason<-if(identical(matched$reason_code,"NO_MATCHED_PAIRS"))NULL else matched$reason_code
  list(flow=flow,coefficients=as.list(unname(stats::coef(fit))),coefficient_columns=as.list(names(stats::coef(fit))),
    glm=list(converged=fit$converged,boundary=fit$boundary,iterations=fit$iter,rank=fit$rank),
    support=list(lower=matched$lower,upper=matched$upper,logit_sd=matched$logit_sd,caliper_width=matched$caliper_width,reason_code=support_reason),
    scores=scores,pairs=pair_data,effect=effect_reference(pair_data$treated_outcome,pair_data$control_outcome),
    balance=balance_reference(fit_data,fit_t,pairs,opt),overlap=overlap_reference(ps,fit_t,support,pairs,opt))
}
hands_reference<-function(input) {
  matches<-lapply(input$matching,function(case) {
    ids<-as.character(vec(case$ids));treatment<-as.numeric(vec(case$treatment));score<-as.numeric(vec(case$logit))
    if(!is.null(case$absolute_caliper)) {
      result<-list(pairs=candidate_assignment(ids,treatment,score,as.logical(vec(case$eligible)),case$absolute_caliper))
    } else result<-match_reference(ids,treatment,score,case$caliper_multiplier)
    result$name<-case$name;result$pair_ids<-lapply(seq_len(nrow(result$pairs)),function(i)as.list(c(ids[result$pairs$treated_index[i]],ids[result$pairs$control_index[i]])))
    result
  })
  effects<-lapply(input$effects,function(case)c(list(name=case$name),effect_reference(as.numeric(vec(case$treated)),as.numeric(vec(case$control)))))
  b<-input$balance;number<-function(name)as.numeric(vec(b[[name]]));reference_sd<-stats::sd(number("treated_numeric"))
  bnumeric<-stats::sd(number("treated_binary_numeric"));indicator<-mean(number("treated_indicator"));indicator_sd<-sqrt(indicator*(1-indicator))
  balance<-list(numeric_reference_sd=reference_sd,numeric_smd_before=(mean(number("treated_numeric"))-mean(number("control_numeric")))/reference_sd,
    numeric_smd_after=(mean(number("matched_treated"))-mean(number("matched_control")))/reference_sd,
    post_treated_sd=stats::sd(number("matched_treated")),binary_numeric_reference_sd=bnumeric,
    binary_numeric_smd=(mean(number("treated_binary_numeric"))-mean(number("control_binary_numeric")))/bnumeric,
    indicator_reference_sd=indicator_sd,indicator_smd=(indicator-mean(number("control_indicator")))/indicator_sd,
    zero_variance_reference_sd=stats::sd(number("zero_variance_treated")),zero_variance_smd=NULL,zero_variance_reason="ZERO_REFERENCE_SD")
  list(matching=matches,effects=effects,balance=balance)
}
answer<-if(input$mode=="hands")hands_reference(input) else analyze_reference(input)
answer$reference_metadata<-list(scope="Independent stats::glm, distance-table matching, stats::t.test paired, and source-formula SMD; not MatchIt validation",
  R_version=as.character(getRversion()),stats_version=as.character(utils::packageVersion("stats")),specialist_package_validation=FALSE)
jsonlite::write_json(answer,args[2],auto_unbox=TRUE,dataframe="rows",digits=17,pretty=TRUE,null="null",na="null")
