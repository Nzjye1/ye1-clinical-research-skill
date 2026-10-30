# Independent preprocessing/CV implementation using direct installed glmnet calls.
# This file never sources the candidate numerical or preprocessing provider.
if(.Platform$OS.type=="windows")suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
stopifnot(requireNamespace("glmnet",quietly=TRUE),requireNamespace("Matrix",quietly=TRUE),requireNamespace("jsonlite",quietly=TRUE))
stopifnot(as.character(utils::packageVersion("glmnet"))=="5.1",as.character(utils::packageVersion("Matrix"))=="1.7.5")
args<-commandArgs(TRUE);Encoding(args)<-"UTF-8";stopifnot(length(args)==2)
input<-jsonlite::fromJSON(args[1],simplifyVector=FALSE)
flatten<-function(x)unlist(x,use.names=FALSE)
bytes<-function(x)vapply(enc2utf8(x),function(s)paste(sprintf("%02x",as.integer(charToRaw(s))),collapse=""),"")
byte_sort<-function(x)x[order(bytes(x),method="radix")]
missing_value<-function(x)is.null(x)||length(x)==0L||identical(x,"")
frame_rows<-function(rows,spec) {
  names<-unique(c(spec$id,spec$outcome,spec$split$partition_field,spec$split$fold_field,spec$split$group_field,vapply(spec$features,`[[`,"","name")))
  strings<-c(spec$id,spec$split$partition_field,spec$split$group_field,vapply(Filter(function(f)f$type=="category",spec$features),`[[`,"","name"))
  data<-as.data.frame(setNames(lapply(names,function(name) {
    if(name %in% strings)vapply(rows,function(row)if(missing_value(row[[name]]))NA_character_ else as.character(row[[name]]),"")
    else vapply(rows,function(row)if(missing_value(row[[name]]))NA_real_ else as.numeric(row[[name]]),0)
  }),names),stringsAsFactors=FALSE,check.names=FALSE)
  data[order(bytes(data[[spec$id]]),method="radix"),,drop=FALSE]
}

# Learn each feature only from the supplied fitting rows. Fitted categories
# are observed categories, not declared-but-unobserved codebook entries.
learn_transform<-function(data,features) {
  learned<-lapply(seq_along(features),function(j) {
    f<-features[[j]];value<-data[[f$name]];observed<-value[!is.na(value)];stopifnot(length(observed)>0)
    if(f$type=="number")list(name=f$name,type=f$type,impute=stats::median(observed),levels=list(),reference=NULL,
      columns=list(list(term=sprintf("X%04d",j),feature=f$name,type=f$type,level=NULL)))
    else {
      levels<-byte_sort(unique(as.character(observed)));counts<-vapply(levels,function(level)sum(observed==level),0L)
      mode<-levels[which.max(counts)]
      list(name=f$name,type=f$type,impute=mode,levels=as.list(levels),reference=levels[1],
        columns=lapply(seq_along(levels)[-1L],function(k)list(term=sprintf("X%04dL%04d",j,k),feature=f$name,type=f$type,level=levels[k])))
    }
  })
  unscaled<-encode(data,learned);center<-colMeans(unscaled);deviation<-sweep(unscaled,2,center,"-");scale<-sqrt(colMeans(deviation^2))
  stopifnot(all(is.finite(center)),all(is.finite(scale)));keep<-which(scale>0);stopifnot(length(keep)>=2L)
  metadata<-unlist(lapply(learned,`[[`,"columns"),recursive=FALSE)
  list(features=learned,all_columns=metadata,center=as.list(center),scale=as.list(scale),
    retained=as.list(colnames(unscaled)[keep]),dropped=as.list(colnames(unscaled)[scale==0]),n_fitting=nrow(data))
}
encode<-function(data,learned) {
  columns<-list()
  for(f in learned) {
    value<-data[[f$name]];value[is.na(value)]<-f$impute
    if(f$type=="number")columns[[f$columns[[1L]]$term]]<-as.numeric(value)
    else {
      stopifnot(all(value %in% as.character(flatten(f$levels))))
      for(column in f$columns)columns[[column$term]]<-as.numeric(value==column$level)
    }
  }
  if(!length(columns))return(matrix(numeric(),nrow=nrow(data),ncol=0L))
  result<-do.call(cbind,columns);storage.mode(result)<-"double";result
}
apply_transform<-function(data,prep) {
  x<-encode(data,prep$features);kept<-as.character(flatten(prep$retained));center<-unlist(prep$center);scale<-unlist(prep$scale)
  sweep(sweep(x[,kept,drop=FALSE],2,center[kept],"-"),2,scale[kept],"/")
}
imputation_counts<-function(data,features) {
  lapply(features,function(f)list(feature=f$name,type=f$type,n_rows=nrow(data),n_missing=sum(is.na(data[[f$name]])),n_imputed=sum(is.na(data[[f$name]]))))
}
response_transform<-function(y,family) {
  stopifnot(all(is.finite(y)))
  if(family=="binomial") {
    stopifnot(all(y %in% c(0,1)),sum(y==0)>=8L,sum(y==1)>=8L)
    list(kind="identity",center=0,scale=1)
  } else {
    average<-mean(y);scale<-sqrt(mean((y-average)^2));stopifnot(is.finite(scale),scale>0)
    list(kind="training_center_scale",center=average,scale=scale)
  }
}
solver_control<-function(p)list(fdev=0,eps=1e-6,big=9.9e35,mnlam=5L,devmax=1,pmin=1e-9,exmx=250,
  itrace=0L,prec=1e-10,mxit=100L,epsnr=1e-6,mxitnr=25L,thresh=1e-10,maxit=100000L,
  dfmax=as.integer(p+1L),pmax=as.integer(p),trace.it=0L)
fit_path<-function(x,y,spec) {
  response<-response_transform(y,spec$family);standard_y<-(y-response$center)/response$scale
  requested<-as.numeric(flatten(spec$lambda_grid));warnings<-character();control<-solver_control(ncol(x))
  fit<-withCallingHandlers(glmnet::glmnet(x=x,y=standard_y,family=spec$family,alpha=spec$alpha,lambda=requested,
    standardize=FALSE,intercept=TRUE,penalty.factor=rep(1,ncol(x)),relax=FALSE,
    type.gaussian="covariance",type.logistic="Newton",control=control),
    warning=function(w){warnings<<-c(warnings,conditionMessage(w));invokeRestart("muffleWarning")})
  stopifnot(length(warnings)==0L,fit$jerr==0L,length(fit$lambda)==length(requested))
  stopifnot(all(abs(fit$lambda-requested)<=32*.Machine$double.eps*abs(requested)))
  # No predict(s=...), interpolation, nearest-value matching or lambda lookup.
  coefficients<-as.matrix(stats::coef(fit));stopifnot(ncol(coefficients)==length(requested),all(is.finite(coefficients)))
  list(coefficients=coefficients,engine_lambda=as.numeric(fit$lambda),response=response,control=control)
}
path_predictions<-function(x,fit,family) {
  eta<-sweep(x%*%fit$coefficients[-1L,,drop=FALSE],2,fit$coefficients[1L,],"+")
  prediction<-if(family=="gaussian")fit$response$center+fit$response$scale*eta else stats::plogis(eta)
  stopifnot(all(is.finite(eta)),all(is.finite(prediction)))
  list(eta=eta,prediction=prediction)
}
loss_values<-function(y,prediction,eta,family) {
  if(family=="gaussian")(y-prediction)^2 else pmax(eta,0)-y*eta+log1p(exp(-abs(eta)))
}
path_rows<-function(fit,prep,spec) {
  meta<-Filter(function(column)column$term %in% flatten(prep$retained),prep$all_columns)
  meta<-c(list(list(term="(Intercept)",feature=NULL,type="intercept",level=NULL)),meta)
  grid<-as.numeric(flatten(spec$lambda_grid));answer<-list()
  for(j in seq_along(grid))for(k in seq_along(meta))answer[[length(answer)+1L]]<-c(list(lambda_index=j,lambda=grid[j],engine_lambda=fit$engine_lambda[j]),meta[[k]],list(coefficient=unname(fit$coefficients[k,j]),nonzero=fit$coefficients[k,j]!=0))
  answer
}
metrics_reference<-function(y,prediction,eta,family,training_mean,threshold=NULL) {
  n<-length(y);if(!n)return(list())
  if(family=="gaussian")return(list(n=n,mae=mean(abs(y-prediction)),rmse=sqrt(mean((y-prediction)^2)),mse=mean((y-prediction)^2),
    comparator_mae=mean(abs(y-training_mean)),comparator_rmse=sqrt(mean((y-training_mean)^2))))
  cases<-which(y==1);controls<-which(y==0);comparison<-outer(eta[cases],eta[controls],"-")
  auc<-if(length(cases)&&length(controls))mean((comparison>0)+.5*(comparison==0)) else NA_real_
  result<-list(n=n,events=length(cases),non_events=length(controls),auc=auc,brier=mean((y-prediction)^2),log_loss=mean(loss_values(y,prediction,eta,family)))
  if(!is.null(threshold)) {
    positive<-prediction>=threshold;tp<-sum(positive&y==1);fp<-sum(positive&y==0);tn<-sum(!positive&y==0);fn<-sum(!positive&y==1)
    result$threshold<-threshold;result$tp<-tp;result$fp<-fp;result$tn<-tn;result$fn<-fn
    result$sensitivity<-if(tp+fn)tp/(tp+fn) else NA_real_;result$specificity<-if(tn+fp)tn/(tn+fp) else NA_real_
    result$ppv<-if(tp+fp)tp/(tp+fp) else NA_real_;result$npv<-if(tn+fn)tn/(tn+fn) else NA_real_
  }
  result
}
train_reference<-function(input) {
  spec<-input$spec;data<-frame_rows(input$rows,spec);sp<-spec$split;training<-data[data[[sp$partition_field]]==sp$training_value,,drop=FALSE]
  holdout<-data[data[[sp$partition_field]]==sp$holdout_value,,drop=FALSE];grid<-as.numeric(flatten(spec$lambda_grid));n_lambda<-length(grid)
  total_loss<-numeric(n_lambda);validation_n<-0L;fold_details<-list();fold_losses<-list()
  for(k in seq_len(sp$cv_folds)) {
    fitting<-training[training[[sp$fold_field]]!=k,,drop=FALSE];validation<-training[training[[sp$fold_field]]==k,,drop=FALSE]
    prep<-learn_transform(fitting,spec$features);fit<-fit_path(apply_transform(fitting,prep),fitting[[spec$outcome]],spec)
    prediction<-path_predictions(apply_transform(validation,prep),fit,spec$family)
    losses<-vapply(seq_along(grid),function(j)sum(loss_values(validation[[spec$outcome]],prediction$prediction[,j],prediction$eta[,j],spec$family)),0)
    total_loss<-total_loss+losses;validation_n<-validation_n+nrow(validation)
    for(j in seq_along(grid))fold_losses[[length(fold_losses)+1L]]<-list(fold=k,lambda_index=j,lambda=grid[j],engine_lambda=fit$engine_lambda[j],loss_sum=losses[j],n_validation=nrow(validation),mean_loss=losses[j]/nrow(validation))
    fold_details[[k]]<-list(fold=k,n_training=nrow(fitting),n_validation=nrow(validation),preprocessor=prep,response_transform=fit$response,
      fitted_subject_ids=as.list(fitting[[spec$id]]),validation_subject_ids=as.list(validation[[spec$id]]),
      imputation_fitting=imputation_counts(fitting,spec$features),imputation_validation=imputation_counts(validation,spec$features),path=path_rows(fit,prep,spec))
  }
  mean_loss<-total_loss/validation_n;selected<-which.min(mean_loss)
  prep<-learn_transform(training,spec$features);fit<-fit_path(apply_transform(training,prep),training[[spec$outcome]],spec)
  predicted<-path_predictions(apply_transform(holdout,prep),fit,spec$family)
  cv<-lapply(seq_along(grid),function(j)list(lambda_index=j,lambda=grid[j],loss_sum=total_loss[j],n_validation=validation_n,mean_loss=mean_loss[j],selected=j==selected))
  individual<-data.frame(subject_id=holdout[[spec$id]],observed=holdout[[spec$outcome]],prediction=predicted$prediction[,selected],linear_predictor=predicted$eta[,selected],stringsAsFactors=FALSE)
  list(selected_lambda_index=selected,selected_lambda=grid[selected],selected_engine_lambda=fit$engine_lambda[selected],
    preprocessor=prep,response_transform=fit$response,control=fit$control,cv=cv,fold_losses=fold_losses,folds=fold_details,path=path_rows(fit,prep,spec),
    intercept=unname(fit$coefficients[1L,selected]),coefficients=as.list(setNames(as.numeric(fit$coefficients[-1L,selected]),rownames(fit$coefficients)[-1L])),
    training_outcome_mean=mean(training[[spec$outcome]]),training_subject_ids=as.list(training[[spec$id]]),
    training_group_ids=if(is.null(sp$group_field))list() else as.list(byte_sort(unique(training[[sp$group_field]]))),
    imputation_training=imputation_counts(training,spec$features),imputation_holdout=imputation_counts(holdout,spec$features),individual=individual,
    metrics=metrics_reference(individual$observed,individual$prediction,individual$linear_predictor,spec$family,mean(training[[spec$outcome]]),spec$clinical_threshold))
}
formula_reference<-function(input) {
  # The harness supplies the frozen JSON fields under this explicit reference
  # shape. Parameters come only from the saved model, never the new outcomes.
  data<-frame_rows(input$rows,input$spec);x<-apply_transform(data,input$preprocessor);beta<-as.numeric(flatten(input$coefficients))
  eta<-as.numeric(input$intercept+x%*%beta);response<-input$response_transform
  prediction<-if(input$spec$family=="gaussian")response$center+response$scale*eta else stats::plogis(eta)
  list(individual=data.frame(subject_id=data[[input$spec$id]],prediction=prediction,linear_predictor=eta),
    imputation=imputation_counts(data,input$spec$features))
}
hand_reference<-function() {
  x<-cbind(X0001=rep(c(-1,-1,1,1),10),X0002=rep(c(-1,1,-1,1),10));y<-.6*x[,1]-.8*x[,2]
  gaussian<-lapply(c(1,.5),function(alpha) {
    spec<-list(family="gaussian",alpha=alpha,lambda_grid=list(2,.2));fit<-fit_path(x,y,spec)
    list(alpha=alpha,coefficients=unname(fit$coefficients),engine_lambda=as.list(fit$engine_lambda),response_transform=fit$response)
  })
  d<-expand.grid(repetition=seq_len(12),z1=c(-1,1),z2=c(-1,1),y=c(0,1));x<-as.matrix(d[c("z1","z2")]);colnames(x)<-c("X0001","X0002")
  losses<-numeric(3);fold_losses<-list();spec<-list(family="binomial",alpha=.5,lambda_grid=list(2,.2,.02))
  for(k in 1:3) {
    v<-which((d$repetition-1)%%3+1==k);f<-setdiff(seq_len(nrow(d)),v);fit<-fit_path(x[f,,drop=FALSE],d$y[f],spec);p<-path_predictions(x[v,,drop=FALSE],fit,"binomial")
    part<-vapply(1:3,function(j)sum(loss_values(d$y[v],p$prediction[,j],p$eta[,j],"binomial")),0);losses<-losses+part;fold_losses[[k]]<-as.list(part)
  }
  fit<-fit_path(x,d$y,spec);p<-path_predictions(x,fit,"binomial")
  saturation<-lapply(list(c(1000,999),c(999,1000),c(1000,1000)),function(eta)metrics_reference(c(1,0),stats::plogis(eta),eta,"binomial",.5,.5))
  list(orthogonal_gaussian=gaussian,balanced_binomial=list(coefficients=unname(fit$coefficients),prediction_range=as.list(range(p$prediction)),
    mean_losses=as.list(losses/nrow(d)),selected_lambda_index=which.min(losses),metrics=metrics_reference(d$y,p$prediction[,1],p$eta[,1],"binomial",.5,.5)),saturated_auc=saturation)
}
answer<-switch(input$mode,train=train_reference(input),formula=formula_reference(input),hands=hand_reference(),stop("REFERENCE_MODE_INVALID"))
answer$reference_metadata<-list(scope="Independent preprocessing/CV and direct glmnet calls; shared glmnet engine, not independent optimizer or clinical validation",
  R=as.character(getRversion()),glmnet=as.character(utils::packageVersion("glmnet")),Matrix=as.character(utils::packageVersion("Matrix")),
  glmnet_path=find.package("glmnet"),Matrix_path=find.package("Matrix"),candidate_functions_called=FALSE)
jsonlite::write_json(answer,args[2],auto_unbox=TRUE,dataframe="rows",digits=17,pretty=TRUE,null="null",na="null")
