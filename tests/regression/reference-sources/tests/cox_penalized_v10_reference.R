# Independent fold preprocessing, direct glmnet Cox, and two Breslow references.
# Never sources or calls candidate code, helpers, or saved candidate coefficients in train mode.
if(.Platform$OS.type=="windows")suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
stopifnot(requireNamespace("glmnet",quietly=TRUE),requireNamespace("survival",quietly=TRUE),requireNamespace("jsonlite",quietly=TRUE))
stopifnot(as.character(utils::packageVersion("glmnet"))=="5.1",as.character(utils::packageVersion("survival"))=="3.8.6")
args<-commandArgs(TRUE);Encoding(args)<-"UTF-8";stopifnot(length(args)==2)
input<-jsonlite::fromJSON(args[1],simplifyVector=FALSE)
flat<-function(x)unlist(x,use.names=FALSE)
bytes<-function(x)vapply(enc2utf8(x),function(s)paste(sprintf("%02x",as.integer(charToRaw(s))),collapse=""),"")
sort_bytes<-function(x)x[order(bytes(x),method="radix")]
missing_value<-function(x)is.null(x)||length(x)==0L||identical(x,"")
frame_rows<-function(rows,spec) {
  names<-unique(c(spec$id,spec$duration,spec$event,spec$split$partition_field,spec$split$fold_field,spec$split$group_field,vapply(spec$features,`[[`,"","name")))
  strings<-c(spec$id,spec$split$partition_field,spec$split$group_field,vapply(Filter(function(f)f$type=="category",spec$features),`[[`,"","name"))
  data<-as.data.frame(setNames(lapply(names,function(name) {
    if(name %in% strings)vapply(rows,function(row)if(missing_value(row[[name]]))NA_character_ else as.character(row[[name]]),"")
    else vapply(rows,function(row)if(missing_value(row[[name]]))NA_real_ else as.numeric(row[[name]]),0)
  }),names),stringsAsFactors=FALSE,check.names=FALSE)
  data[order(bytes(data[[spec$id]]),method="radix"),,drop=FALSE]
}
encode<-function(data,learned) {
  columns<-list()
  for(f in learned) {
    value<-data[[f$name]];value[is.na(value)]<-f$impute
    if(f$type=="number")columns[[f$columns[[1L]]$term]]<-as.numeric(value)
    else {
      stopifnot(all(value %in% as.character(flat(f$levels))))
      for(column in f$columns)columns[[column$term]]<-as.numeric(value==column$level)
    }
  }
  if(!length(columns))return(matrix(numeric(),nrow=nrow(data),ncol=0L))
  result<-do.call(cbind,columns);storage.mode(result)<-"double";result
}
learn_transform<-function(data,features) {
  learned<-lapply(seq_along(features),function(j) {
    f<-features[[j]];value<-data[[f$name]];observed<-value[!is.na(value)];stopifnot(length(observed)>0)
    if(f$type=="number")list(name=f$name,type=f$type,impute=stats::median(observed),levels=list(),reference=NULL,
      columns=list(list(term=sprintf("X%04d",j),feature=f$name,type=f$type,level=NULL)))
    else {
      levels<-sort_bytes(unique(as.character(observed)));counts<-vapply(levels,function(level)sum(observed==level),0L)
      list(name=f$name,type=f$type,impute=levels[which.max(counts)],levels=as.list(levels),reference=levels[1],
        columns=lapply(seq_along(levels)[-1L],function(k)list(term=sprintf("X%04dL%04d",j,k),feature=f$name,type=f$type,level=levels[k])))
    }
  })
  raw<-encode(data,learned);center<-colMeans(raw);scale<-sqrt(colMeans(sweep(raw,2,center,"-")^2));keep<-which(scale>0)
  stopifnot(all(is.finite(center)),all(is.finite(scale)),length(keep)>=2L)
  list(features=learned,all_columns=unlist(lapply(learned,`[[`,"columns"),recursive=FALSE),center=as.list(center),scale=as.list(scale),
    retained=as.list(colnames(raw)[keep]),dropped=as.list(colnames(raw)[scale==0]),n_fitting=nrow(data))
}
apply_transform<-function(data,prep) {
  raw<-encode(data,prep$features);kept<-as.character(flat(prep$retained));center<-unlist(prep$center);scale<-unlist(prep$scale)
  sweep(sweep(raw[,kept,drop=FALSE],2,center[kept],"-"),2,scale[kept],"/")
}
solver_control<-function(p)list(fdev=0,eps=1e-6,big=9.9e35,mnlam=5L,devmax=1,pmin=1e-9,exmx=250,
  itrace=0L,prec=1e-10,mxit=100L,epsnr=1e-6,mxitnr=25L,thresh=1e-10,maxit=100000L,
  dfmax=as.integer(p+1L),pmax=as.integer(p),trace.it=0L)
fit_path<-function(x,time,event,spec) {
  stopifnot(all(is.finite(time)),all(time>0),all(event %in% c(0,1)),sum(event)>=8)
  grid<-as.numeric(flat(spec$lambda_grid));warnings<-character();control<-solver_control(ncol(x))
  # Cox has no intercept; the argument is intentionally omitted.
  fit<-withCallingHandlers(glmnet::glmnet(x=x,y=survival::Surv(time,event),family="cox",alpha=spec$alpha,
    lambda=grid,standardize=FALSE,penalty.factor=rep(1,ncol(x)),relax=FALSE,cox.ties="breslow",control=control),
    warning=function(w){warnings<<-c(warnings,conditionMessage(w));invokeRestart("muffleWarning")})
  stopifnot(!length(warnings),fit$jerr==0L,length(fit$lambda)==length(grid),all(abs(fit$lambda-grid)<=32*.Machine$double.eps*abs(grid)))
  coefficients<-as.matrix(stats::coef(fit));stopifnot(ncol(coefficients)==length(grid),nrow(coefficients)==ncol(x),all(is.finite(coefficients)))
  list(coefficients=coefficients,engine_lambda=as.numeric(fit$lambda),control=control,jerr=fit$jerr)
}
# Breslow partial likelihood and saturated tied-event likelihood, using risk t_i >= t.
manual_deviance<-function(time,event,eta) {
  event_times<-sort(unique(time[event==1]));loglik<-0;saturated<-0
  for(t in event_times) {
    who<-which(time==t & event==1);risk<-which(time>=t);d<-length(who);m<-max(eta[risk])
    loglik<-loglik+sum(eta[who])-d*(m+log(sum(exp(eta[risk]-m))))
    saturated<-saturated-d*log(d)
  }
  2*(saturated-loglik)
}
manual_baseline<-function(time,event,eta) {
  center<-mean(eta);q<-eta-center;times<-sort(unique(time[event==1]));increments<-numeric(length(times))
  for(i in seq_along(times))increments[i]<-sum(time==times[i]&event==1)/sum(exp(q[time>=times[i]]))
  list(center=center,event_times=as.list(times),cumulative_hazard=as.list(cumsum(increments)))
}
fixed_survival_baseline<-function(time,event,eta) {
  # Treat eta as one covariate with coefficient fixed at exactly 1 and zero iterations.
  # newdata explicitly asks for the training-mean linear predictor reference.
  d<-data.frame(time=time,event=event,linear=eta)
  fit<-survival::coxph(survival::Surv(time,event)~linear,data=d,init=1,ties="breslow",
    control=survival::coxph.control(iter.max=0,timefix=FALSE),model=TRUE,x=TRUE,y=TRUE)
  # coxph rescales init internally and back (observed 1 - 1.11e-16).
  # Zero iterations proves the coefficient was never optimized; the machine-
  # precision roundtrip check is tighter than every prespecified numeric tolerance.
  stopifnot(length(stats::coef(fit))==1L,fit$iter==0L,abs(unname(stats::coef(fit))-1)<=.Machine$double.eps)
  s<-survival::survfit(fit,newdata=data.frame(linear=mean(eta)),stype=2,ctype=1,se.fit=FALSE,censor=FALSE)
  list(center=mean(eta),event_times=as.list(as.numeric(s$time)),cumulative_hazard=as.list(as.numeric(s$cumhaz)),fixed_coefficient=1,internal_coefficient_roundtrip=unname(stats::coef(fit)),coefficient_updates=0)
}
offset_survival_baseline<-function(time,event,eta) {
  q<-eta-mean(eta);d<-data.frame(time=time,event=event,q=q)
  fit<-survival::coxph(survival::Surv(time,event)~offset(q),data=d,ties="breslow",control=survival::coxph.control(iter.max=0,timefix=FALSE))
  stopifnot(length(stats::coef(fit))==0L)
  s<-survival::survfit(fit,newdata=data.frame(q=0),stype=2,ctype=1,se.fit=FALSE,censor=FALSE)
  list(center=mean(eta),event_times=as.list(as.numeric(s$time)),cumulative_hazard=as.list(as.numeric(s$cumhaz)),coefficient_updates=0)
}
stable_risk<-function(h,q) {
  if(h==0)return(rep(0,length(q)))
  z<-log(h)+q;out<-numeric(length(z));high<-z>log(.Machine$double.xmax);out[high]<-1;out[!high]<- -expm1(-exp(z[!high]));out
}
prediction_rows<-function(data,spec,prep,beta,baseline,infer=FALSE) {
  eta<-as.numeric(apply_transform(data,prep)%*%beta);q<-eta-baseline$center;answer<-list();times<-as.numeric(flat(baseline$event_times));hazard<-as.numeric(flat(baseline$cumulative_hazard))
  for(i in seq_len(nrow(data)))for(horizon in as.numeric(flat(spec$horizons))) {
    at<-which(times<=horizon);h<-if(length(at))hazard[max(at)] else 0;risk<-stable_risk(h,q[i])
    answer[[length(answer)+1L]]<-list(subject_id=data[[spec$id]][i],group_id=if(is.null(spec$split$group_field))NULL else data[[spec$split$group_field]][i],
      partition=data[[spec$split$partition_field]][i],fold=data[[spec$split$fold_field]][i],duration=if(infer)NA_real_ else data[[spec$duration]][i],event=if(infer)NA_real_ else data[[spec$event]][i],
      linear_predictor=eta[i],centered_linear_predictor=q[i],horizon=horizon,survival=1-risk,risk=risk)
  }
  answer
}
path_rows<-function(fit,prep,spec) {
  meta<-Filter(function(x)x$term %in% flat(prep$retained),prep$all_columns);grid<-as.numeric(flat(spec$lambda_grid));answer<-list()
  for(j in seq_along(grid))for(k in seq_along(meta))answer[[length(answer)+1L]]<-c(list(lambda_index=j,lambda=grid[j],engine_lambda=fit$engine_lambda[j]),meta[[k]],list(coefficient=unname(fit$coefficients[k,j]),nonzero=fit$coefficients[k,j]!=0))
  answer
}
train_reference<-function(input) {
  spec<-input$spec;data<-frame_rows(input$rows,spec);sp<-spec$split;training<-data[data[[sp$partition_field]]==sp$training_value,,drop=FALSE]
  grid<-as.numeric(flat(spec$lambda_grid));loss_sum<-numeric(length(grid));events_sum<-0L;folds<-list();loss_rows<-list();manual_delta<-0
  for(k in seq_len(sp$cv_folds)) {
    fitting<-training[training[[sp$fold_field]]!=k,,drop=FALSE];valid<-training[training[[sp$fold_field]]==k,,drop=FALSE]
    stopifnot(sum(valid[[spec$event]])>=3);prep<-learn_transform(fitting,spec$features);fit<-fit_path(apply_transform(fitting,prep),fitting[[spec$duration]],fitting[[spec$event]],spec)
    eta<-apply_transform(valid,prep)%*%fit$coefficients
    losses<-as.numeric(glmnet::coxnet.deviance(pred=eta,y=survival::Surv(valid[[spec$duration]],valid[[spec$event]]),std.weights=FALSE,cox.ties="breslow"))
    manual<-vapply(seq_along(grid),function(j)manual_deviance(valid[[spec$duration]],valid[[spec$event]],eta[,j]),0)
    manual_delta<-max(manual_delta,max(abs(losses-manual)));stopifnot(max(abs(losses-manual))<=2e-7)
    events<-sum(valid[[spec$event]]);loss_sum<-loss_sum+losses;events_sum<-events_sum+events
    for(j in seq_along(grid))loss_rows[[length(loss_rows)+1L]]<-list(fold=k,lambda_index=j,lambda=grid[j],engine_lambda=fit$engine_lambda[j],deviance_sum=losses[j],validation_events=events,deviance_per_event=losses[j]/events)
    folds[[k]]<-list(fold=k,n_training=nrow(fitting),n_validation=nrow(valid),training_events=sum(fitting[[spec$event]]),training_censored=sum(fitting[[spec$event]]==0),validation_events=events,validation_censored=sum(valid[[spec$event]]==0),preprocessor=prep,path=path_rows(fit,prep,spec))
  }
  selected<-which.min(loss_sum/events_sum);prep<-learn_transform(training,spec$features);x<-apply_transform(training,prep)
  fit<-fit_path(x,training[[spec$duration]],training[[spec$event]],spec);beta<-fit$coefficients[,selected];eta<-as.numeric(x%*%beta)
  baseline<-manual_baseline(training[[spec$duration]],training[[spec$event]],eta)
  fixed<-fixed_survival_baseline(training[[spec$duration]],training[[spec$event]],eta);offset<-offset_survival_baseline(training[[spec$duration]],training[[spec$event]],eta)
  stopifnot(identical(baseline$event_times,fixed$event_times),identical(baseline$event_times,offset$event_times),max(abs(flat(baseline$cumulative_hazard)-flat(fixed$cumulative_hazard)))<=2e-8,max(abs(flat(baseline$cumulative_hazard)-flat(offset$cumulative_hazard)))<=2e-8)
  list(selected_lambda_index=selected,selected_lambda=grid[selected],selected_engine_lambda=fit$engine_lambda[selected],preprocessor=prep,control=fit$control,
    cv=lapply(seq_along(grid),function(j)list(lambda_index=j,lambda=grid[j],deviance_sum=loss_sum[j],validation_events=events_sum,deviance_per_event=loss_sum[j]/events_sum,selected=j==selected)),folds=folds,fold_losses=loss_rows,path=path_rows(fit,prep,spec),
    coefficients=as.list(unname(beta)),baseline=baseline,fixed_survival_baseline=fixed,offset_survival_baseline=offset,
    training_support=list(n_training=nrow(training),events=sum(training[[spec$event]]),censored=sum(training[[spec$event]]==0),min_time=min(training[[spec$duration]]),max_followup=max(training[[spec$duration]]),last_event_time=max(training[[spec$duration]][training[[spec$event]]==1]),horizon_min=0,horizon_max=max(training[[spec$duration]])),
    training_subject_ids=as.list(training[[spec$id]]),training_group_ids=if(is.null(sp$group_field))list() else as.list(sort_bytes(unique(training[[sp$group_field]]))),
    individual=prediction_rows(data,spec,prep,beta,baseline),max_engine_vs_manual_deviance_difference=manual_delta)
}
hands<-function() {
  time<-c(1,1,1,2,2,3);event<-c(1,1,0,1,0,0);eta<-c(.5,-.2,.7,.3,-.4,.9)
  engine<-as.numeric(glmnet::coxnet.deviance(pred=eta,y=survival::Surv(time,event),std.weights=FALSE,cox.ties="breslow"));manual<-manual_deviance(time,event,eta)
  baseline<-manual_baseline(time,event,eta);fixed<-fixed_survival_baseline(time,event,eta);offset<-offset_survival_baseline(time,event,eta)
  zero<-manual_baseline(time,event,rep(0,length(time)));zerofixed<-fixed_survival_baseline(time,event,rep(0,length(time)))
  stopifnot(abs(engine-manual)<=2e-7,max(abs(flat(baseline$cumulative_hazard)-flat(fixed$cumulative_hazard)))<=2e-8,max(abs(flat(zero$cumulative_hazard)-c(1/3,2/3)))<=2e-8)
  list(tied=list(engine_deviance=engine,manual_deviance=manual,baseline=baseline,fixed=fixed,offset=offset),zero=list(baseline=zero,fixed=zerofixed),
    stable_risk=list(q=as.list(c(-1000,-700,0,700,1000)),risk=as.list(stable_risk(.5,c(-1000,-700,0,700,1000))),at_zero=as.list(stable_risk(0,c(-1000,0,1000)))))
}
result<-switch(input$mode,train=train_reference(input),hands=hands(),formula={
  data<-frame_rows(input$rows,input$spec);list(individual=prediction_rows(data,input$spec,input$preprocessor,as.numeric(flat(input$coefficients)),input$baseline,isTRUE(input$infer)))
},stop("UNKNOWN_REFERENCE_MODE"))
result$reference_metadata<-list(candidate_functions_called=FALSE,independent_optimizer=FALSE,glmnet=as.character(utils::packageVersion("glmnet")),survival=as.character(utils::packageVersion("survival")),Matrix=as.character(utils::packageVersion("Matrix")),ties="breslow",risk_sets="duration >= event time",timefix=FALSE)
jsonlite::write_json(result,args[2],auto_unbox=TRUE,digits=17,pretty=TRUE,null="null",na="null",dataframe="rows")
