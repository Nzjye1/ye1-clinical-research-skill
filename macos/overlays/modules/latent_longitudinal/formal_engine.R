args<-commandArgs(trailingOnly=TRUE)
if(length(args)!=3L)stop("FORMAL_ENGINE_ARGUMENTS_INVALID")
runtime<-jsonlite::fromJSON(args[3],simplifyVector=FALSE)
.libPaths(c(unlist(runtime$r_libraries),.libPaths()))
engine_file<-sub("^--file=","",commandArgs()[grepl("^--file=",commandArgs())][1])
if (.Platform$OS.type != "windows" && !file.exists(engine_file)) engine_file <- gsub("~+~", " ", engine_file, fixed=TRUE)
source(file.path(dirname(engine_file),"formal_models.R"),local=TRUE)
input<-jsonlite::fromJSON(args[1],simplifyVector=FALSE)

ll_transform <- function(x) {
  center<-colMeans(x);scale<-sqrt(colMeans(sweep(x,2,center)^2))
  ll_need(all(is.finite(scale))&&min(scale)>1e-10,"FORMAL_CONSTANT_INDICATOR")
  list(mean=as.list(center),scale=as.list(scale),fit_scope="training_only")
}
ll_apply <- function(x,t) sweep(sweep(x,2,unlist(t$mean)),2,unlist(t$scale),"/")
ll_frame <- function(rows) {
  if(!length(rows))return(data.frame())
  out<-as.data.frame(do.call(rbind,lapply(rows,unlist)))
  for(n in names(out))out[[n]]<-as.numeric(out[[n]])
  out
}
ll_fit <- function(data,k,spec,seed) {
  c<-spec$controls
  if(input$method_id=="latent.profile.gaussian") {
    transform<-ll_transform(data)
    result<-ll_lpa_candidate(ll_apply(data,transform),k,spec$definition$covariance_model,
                             spec$starts,seed,c$max_iter,c$tol)
    result$transform<-transform
  }else result<-ll_trajectory_candidate(data,k,spec$definition$degree,spec$definition$random,
                                         spec$starts,seed,c$max_iter,c$tol)
  result
}
ll_score <- function(data,model,transform) {
  if(input$method_id=="latent.profile.gaussian")ll_lpa_score(ll_apply(data,transform),model)
  else ll_trajectory_score(data,model)
}
ll_safe_fit <- function(data,k,spec,seed)tryCatch(ll_fit(data,k,spec,seed),error=function(e)
 list(ok=FALSE,reason_code=if(grepl("^FORMAL_",conditionMessage(e)))conditionMessage(e)else"FORMAL_ENGINE_FAILURE",starts=list()))

out<-tryCatch({
  profile<-input$method_id=="latent.profile.gaussian"
  train<-if(profile)ll_matrix(input$train)else ll_frame(input$train)
  evaluation<-if(length(input$evaluation)){if(profile)ll_matrix(input$evaluation)else ll_frame(input$evaluation)}else NULL
  spec<-input$spec;selection<-list();initializations<-list();stability<-list();stability_summary<-NULL
  if(input$operation=="train") {
    fits<-list()
    for(k in sort(unlist(spec$candidate_k))) {
      fit<-ll_safe_fit(train,k,spec,as.integer((spec$seed+k*1009)%%2147483646))
      initializations<-c(initializations,fit$starts)
      ll_need(!identical(fit$reason_code,"FORMAL_ENGINE_FAILURE") &&
        !any(vapply(fit$starts,function(r)identical(r$reason_code,"FORMAL_ENGINE_FAILURE"),logical(1))),
        "FORMAL_PROVIDER_INTERNAL_FAILURE")
      if(isTRUE(fit$ok)) {selection[[length(selection)+1L]]<-fit$selection;fits[[as.character(k)]]<-fit}
      else selection[[length(selection)+1L]]<-list(k=k,status="rejected",reason_code=fit$reason_code)
    }
    ll_need(length(fits)>0L,"FORMAL_ALL_CANDIDATES_REJECTED")
    selected<-fits[[which.min(vapply(fits,function(f)f$selection$BIC,numeric(1)))]]
    model<-selected$model;transform<-selected$transform;k<-selected$selection$k
    scored<-ll_score(train,model,transform)
    units<-if(profile)seq_len(nrow(train))else sort(unique(train$id))
    for(b in seq_len(spec$controls$stability_reps)) {
      seed<-as.integer((spec$seed+b*7919+15485863)%%2147483646);set.seed(seed)
      sampled<-sample(units,length(units),replace=TRUE)
      if(profile)boot<-train[sampled,,drop=FALSE] else {
        boot<-do.call(rbind,lapply(seq_along(sampled),function(i){d<-train[train$id==sampled[i],,drop=FALSE];d$id<-i;d}))
      }
      before<-ll_fit_count
      fit<-ll_safe_fit(boot,k,spec,seed)
      ll_need(!identical(fit$reason_code,"FORMAL_ENGINE_FAILURE") &&
        !any(vapply(fit$starts,function(r)identical(r$reason_code,"FORMAL_ENGINE_FAILURE"),logical(1))),
        "FORMAL_PROVIDER_INTERNAL_FAILURE")
      row<-list(replicate=b,seed=seed,status="rejected",reason_code=fit$reason_code,ari=NULL,
                 n_engine_fits=ll_fit_count-before)
      if(isTRUE(fit$ok)) {
        check<-ll_score(train,fit$model,fit$transform)
        row$status<-"accepted";row["reason_code"]<-list(NULL);row$ari<-ll_ari(max.col(scored$prob),max.col(check$prob))
      }
      stability[[b]]<-row
    }
    valid<-vapply(stability,function(r)identical(r$status,"accepted"),logical(1))
    ll_need(sum(valid)>=ceiling(.8*spec$controls$stability_reps),"FORMAL_STABILITY_TOO_FEW_VALID_REPLICATES")
    aris<-vapply(stability[valid],`[[`,numeric(1),"ari")
    stability_summary<-list(requested=length(stability),valid=sum(valid),mean_ari=mean(aris),
       p10_ari=as.numeric(quantile(aris,.1)),p90_ari=as.numeric(quantile(aris,.9)),
       class_selection_repeated=FALSE,scope="training_subject_bootstrap_fixed_selected_k",
       uncertainty="descriptive_quantiles_not_confidence_intervals")
  }else {
    model<-input$frozen$model;transform<-input$frozen$transform
    k<-length(model$weights);scored<-NULL
  }
  external<-if(!is.null(evaluation))ll_score(evaluation,model,transform)else NULL
  result<-list(ok=TRUE,reason_code=NULL,model=model,transform=transform,selected_k=k,
    selection=selection,initializations=initializations,stability=stability,stability_summary=stability_summary,
    training=if(!is.null(scored))list(log_likelihood=scored$loglik,posterior=ll_json_matrix(scored$prob),
              classes=ll_classes(scored$prob,enforce=FALSE))else NULL,
    evaluation=if(!is.null(external))list(log_likelihood=external$loglik,posterior=ll_json_matrix(external$prob),
              classes=ll_classes(external$prob,enforce=FALSE))else NULL,
    diagnostics=list(n_engine_fits=ll_fit_count,model_refitted=input$operation=="train",
       transform_refitted=input$operation=="train"&&profile))
  result
},error=function(e)list(ok=FALSE,reason_code=if(grepl("^FORMAL_",conditionMessage(e)))conditionMessage(e)else"FORMAL_ENGINE_FAILURE",
  diagnostics=list(n_engine_fits=ll_fit_count),selection=if(exists("selection"))selection else list(),
  initializations=if(exists("initializations"))initializations else list(),stability=if(exists("stability"))stability else list()))
jsonlite::write_json(out,args[2],auto_unbox=TRUE,null="null",na="null",digits=16,pretty=TRUE)
