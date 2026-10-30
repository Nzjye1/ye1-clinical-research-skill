# Dedicated formal numerical owners: mclust::me and lcmm::hlme.
# No installation, hidden fallback, or evaluation-set fitting.
ll_fit_count <- 0L

ll_need <- function(ok,code) if(!isTRUE(ok))stop(code,call.=FALSE)
ll_rows <- function(x) lapply(seq_len(nrow(x)),function(i)as.list(x[i,,drop=FALSE]))
ll_matrix <- function(x) do.call(rbind,lapply(x,function(z)unlist(z,use.names=FALSE)))
ll_json_matrix <- function(x) lapply(seq_len(nrow(x)),function(i)as.list(unname(x[i,])))
ll_logsum <- function(x) {m<-max(x);m+log(sum(exp(x-m)))}
ll_ari <- function(a,b) {
  tab<-table(a,b);choose2<-function(x)x*(x-1)/2
  n<-sum(tab);observed<-sum(choose2(tab));ra<-sum(choose2(rowSums(tab)));cb<-sum(choose2(colSums(tab)))
  expected<-ra*cb/choose2(n);denom<-(ra+cb)/2-expected
  if(abs(denom)<1e-12)return(if(identical(as.integer(factor(a)),as.integer(factor(b))))1 else 0)
  (observed-expected)/denom
}
ll_classes <- function(prob,min_n=5L,min_fraction=.05,enforce=TRUE) {
  k<-ncol(prob);label<-max.col(prob,ties.method="first");n<-nrow(prob)
  sizes<-tabulate(label,nbins=k)
  if(enforce)ll_need(all(sizes>=max(min_n,ceiling(min_fraction*n))),"FORMAL_SMALL_OR_EMPTY_CLASS")
  list(label=label,summary=ll_rows(data.frame(class=seq_len(k),n=sizes,denominator=n,
    fraction=sizes/n,mean_max_posterior=vapply(seq_len(k),function(i)if(sizes[i])mean(prob[label==i,i])else NA_real_,numeric(1)))),
    entropy=if(k>1)1+sum(prob*log(pmax(prob,1e-300)))/(n*log(k))else NULL)
}

ll_lpa_score <- function(x,model) {
  mean<-ll_matrix(model$centers);variance<-ll_matrix(model$variances);pro<-unlist(model$weights)
  logp<-sapply(seq_len(nrow(mean)),function(k)log(pro[k])+rowSums(matrix(vapply(seq_len(ncol(x)),function(j)
    stats::dnorm(x[,j],mean[k,j],sqrt(variance[k,j]),log=TRUE),numeric(nrow(x))),nrow=nrow(x))))
  logp<-matrix(logp,nrow=nrow(x),ncol=nrow(mean))
  normalizer<-apply(logp,1,ll_logsum)
  list(prob=exp(logp-normalizer),loglik=sum(normalizer))
}

ll_lpa_candidate <- function(x,k,covariance,starts,seed,max_iter=600L,tol=1e-7) {
  ll_need(requireNamespace("mclust",quietly=TRUE),"FORMAL_DEPENDENCY_UNAVAILABLE")
  # me() evaluates its method name in its caller; bind only the two approved methods.
  meEEI<-mclust::meEEI;meVVI<-mclust::meVVI
  p<-ncol(x);n<-nrow(x);records<-list();accepted<-list()
  for(s in seq_len(if(k==1L)1L else starts)) {
    use_seed<-as.integer((seed+s*104729)%%2147483646);set.seed(use_seed)
    row<-list(k=k,start=s,seed=use_seed,status="rejected",reason_code=NULL,log_likelihood=NULL,iterations=NULL)
    result<-tryCatch({
      if(k==1L)z<-matrix(1,n,1) else {
        label<-stats::kmeans(x,centers=k,nstart=1L,iter.max=50L)$cluster
        z<-matrix(.05/(k-1L),n,k);z[cbind(seq_len(n),label)]<-.95
      }
      notes<-character()
      ll_fit_count <<- ll_fit_count+1L
      fit<-withCallingHandlers(mclust::me(x,modelName=covariance,z=z,warn=TRUE,
         control=mclust::emControl(eps=1e-8,tol=c(tol,tol),itmax=c(max_iter,max_iter),equalPro=FALSE)),
         warning=function(w){notes<<-c(notes,conditionMessage(w));invokeRestart("muffleWarning")})
      ll_need(!length(notes)&&is.null(attr(fit,"WARNING"))&&identical(as.numeric(attr(fit,"returnCode")),0),
              "FORMAL_EM_NOT_CONVERGED")
      ll_need(is.finite(fit$loglik),"FORMAL_NONFINITE_LIKELIHOOD")
      info<-attr(fit,"info");row$iterations<-if(length(info))as.integer(info[1])else NULL
      sigma<-fit$parameters$variance$sigma
      if(is.null(sigma))sigma<-array(rep(fit$parameters$variance$Sigma,k),c(p,p,k))
      variance<-t(vapply(seq_len(k),function(j)diag(sigma[,,j]),numeric(p)))
      mean<-t(matrix(fit$parameters$mean,p,k))
      pro<-as.numeric(fit$parameters$pro)
      ll_need(all(is.finite(c(variance,mean,pro)))&&min(variance)>1e-6&&max(variance)/min(variance)<1e8,
              "FORMAL_VARIANCE_DEGENERATE")
      ll_need(min(pro)>=.05,"FORMAL_NEGLIGIBLE_CLASS_WEIGHT")
      ord<-do.call(base::order,as.data.frame(mean));mean<-mean[ord,,drop=FALSE];variance<-variance[ord,,drop=FALSE];pro<-pro[ord]
      model<-list(centers=ll_json_matrix(mean),variances=ll_json_matrix(variance),weights=as.list(pro),
                  covariance_model=covariance,distribution="conditional_independent_Gaussian")
      scored<-ll_lpa_score(x,model);classes<-ll_classes(scored$prob)
      ll_need(abs(scored$loglik-fit$loglik)<1e-6*max(1,abs(fit$loglik)),"FORMAL_DENSITY_RECONSTRUCTION_MISMATCH")
      ll_need(max(abs(scored$prob-fit$z[,ord,drop=FALSE]))<1e-6,"FORMAL_POSTERIOR_RECONSTRUCTION_MISMATCH")
      list(model=model,loglik=fit$loglik,prob=scored$prob,classes=classes)
    },error=function(e){cat("LPA start rejected: ",conditionMessage(e),"\n",file=stderr());list(error=if(grepl("^FORMAL_",conditionMessage(e)))conditionMessage(e)else"FORMAL_ENGINE_FAILURE")})
    if(is.null(result$error)) {
      row$status<-"accepted";row$log_likelihood<-result$loglik;accepted[[length(accepted)+1L]]<-result
    } else row$reason_code<-result$error
    records[[s]]<-row
  }
  if(!length(accepted))return(list(ok=FALSE,reason_code="FORMAL_ALL_STARTS_REJECTED",starts=records))
  likelihood<-vapply(accepted,`[[`,numeric(1),"loglik");best<-accepted[[which.max(likelihood)]]
  repeated<-sum(abs(likelihood-max(likelihood))<=1e-6*max(1,abs(max(likelihood))))
  if(k>1L&&repeated<2L)return(list(ok=FALSE,reason_code="FORMAL_BEST_NOT_REPLICATED",starts=records))
  parameters<-k*p+(k-1L)+if(covariance=="EEI")p else k*p
  best$ok<-TRUE;best$starts<-records
  best$selection<-list(k=k,log_likelihood=best$loglik,n_parameters=parameters,
    AIC=-2*best$loglik+2*parameters,BIC=-2*best$loglik+parameters*log(n),
    independent_units=n,replicated_best_starts=repeated,status="accepted",reason_code=NULL)
  best
}

ll_trajectory_candidate <- function(data,k,degree,random,starts,seed,max_iter=600L,tol=1e-6) {
  ll_need(requireNamespace("lcmm",quietly=TRUE),"FORMAL_DEPENDENCY_UNAVAILABLE")
  fixed<-if(degree==1L)yy~tt else yy~tt+tt2
  mix<-if(degree==1L)~tt else ~tt+tt2
  random_formula<-switch(random,none=~-1,intercept=~1,intercept_slope=~tt)
  q<-switch(random,none=0L,intercept=1L,intercept_slope=2L)
  records<-list();accepted<-list()
  # One-class model supplies starts only. It does not replace a failed mixture.
  ll_fit_count <<- ll_fit_count+1L
  base<-lcmm::hlme(fixed=fixed,random=random_formula,subject="id",ng=1L,data=data,
      maxiter=max_iter,convB=tol,convL=tol,convG=tol,nproc=1L,partialH=FALSE,returndata=FALSE)
  ll_need(base$conv==1L&&all(base$gconv<=tol),"FORMAL_ONE_CLASS_INITIALIZER_NOT_CONVERGED")
  # hlme evaluates random(model) in its enclosing namespace search path. This
  # private single-request R process provides the initializer through .GlobalEnv.
  assign(".ll_hlme_initializer",base,envir=.GlobalEnv)
  on.exit(rm(".ll_hlme_initializer",envir=.GlobalEnv),add=TRUE)
  for(s in seq_len(if(k==1L)1L else starts)) {
    use_seed<-as.integer((seed+s*104729)%%2147483646);set.seed(use_seed)
    row<-list(k=k,start=s,seed=use_seed,status="rejected",reason_code=NULL,log_likelihood=NULL,iterations=NULL)
    result<-tryCatch({
      notes<-character()
      if(k>1L)ll_fit_count <<- ll_fit_count+1L
      fit<-withCallingHandlers(if(k==1L)base else
        lcmm::hlme(fixed=fixed,mixture=mix,random=random_formula,classmb=~1,subject="id",ng=k,data=data,
          B=random(.ll_hlme_initializer),idiag=FALSE,nwg=FALSE,maxiter=max_iter,convB=tol,convL=tol,convG=tol,
          nproc=1L,partialH=FALSE,returndata=FALSE),
        warning=function(w){notes<<-c(notes,conditionMessage(w));invokeRestart("muffleWarning")})
      row$iterations<-fit$niter
      ll_need(!length(notes)&&fit$conv==1L&&all(fit$gconv<=tol),"FORMAL_TRAJECTORY_NOT_CONVERGED")
      ll_need(all(is.finite(c(fit$best,fit$V,fit$loglik))),"FORMAL_NONFINITE_PARAMETERS")
      count<-length(fit$best);hessian_cov<-matrix(0,count,count)
      hessian_cov[upper.tri(hessian_cov,diag=TRUE)]<-fit$V
      hessian_cov[lower.tri(hessian_cov)]<-t(hessian_cov)[lower.tri(hessian_cov)]
      ll_need(min(eigen(hessian_cov,symmetric=TRUE,only.values=TRUE)$values)>1e-10,"FORMAL_HESSIAN_DEGENERATE")
      offset<-k-1L;logits<-c(if(k>1L)fit$best[seq_len(offset)]else numeric(),0)
      pro<-exp(logits-max(logits));pro<-pro/sum(pro)
      beta<-matrix(fit$best[offset+seq_len(k*(degree+1L))],nrow=k)
      offset<-offset+k*(degree+1L)
      D<-matrix(0,q,q)
      if(q) {
        D[lower.tri(D,diag=TRUE)]<-fit$best[offset+seq_len(q*(q+1L)/2L)]
        D[upper.tri(D)]<-t(D)[upper.tri(D)]
      }
      residual<-tail(fit$best,1)^2
      ll_need(residual>1e-8&&min(pro)>=.05,"FORMAL_VARIANCE_OR_WEIGHT_DEGENERATE")
      if(q)ll_need(min(eigen(D,symmetric=TRUE,only.values=TRUE)$values)>1e-6*max(c(diag(D),residual)),
                    "FORMAL_RANDOM_EFFECTS_DEGENERATE")
      ord<-do.call(base::order,as.data.frame(beta));beta<-beta[ord,,drop=FALSE];pro<-pro[ord]
      model<-list(beta=ll_json_matrix(beta),weights=as.list(unname(pro)),random_covariance=if(q)ll_json_matrix(D)else list(),
        residual_variance=as.numeric(residual),degree=degree,random=random)
      scored<-ll_trajectory_score(data,model)
      classes<-ll_classes(scored$prob)
      posterior<-fit$pprob[match(scored$id,fit$pprob[,1]),2L+ord,drop=FALSE]
      ll_need(max(abs(scored$prob-as.matrix(posterior)))<1e-5,"FORMAL_POSTERIOR_RECONSTRUCTION_MISMATCH")
      ll_need(abs(scored$loglik-fit$loglik)<1e-5*max(1,abs(fit$loglik)),"FORMAL_DENSITY_RECONSTRUCTION_MISMATCH")
      list(model=model,loglik=fit$loglik,prob=scored$prob,classes=classes,n_parameters=length(fit$best))
    },error=function(e){cat("Trajectory start rejected: ",conditionMessage(e),"\n",file=stderr());list(error=if(grepl("^FORMAL_",conditionMessage(e)))conditionMessage(e)else"FORMAL_ENGINE_FAILURE")})
    if(is.null(result$error)) {
      row$status<-"accepted";row$log_likelihood<-result$loglik;accepted[[length(accepted)+1L]]<-result
    }else row$reason_code<-result$error
    records[[s]]<-row
  }
  if(!length(accepted))return(list(ok=FALSE,reason_code="FORMAL_ALL_STARTS_REJECTED",starts=records))
  likelihood<-vapply(accepted,`[[`,numeric(1),"loglik");best<-accepted[[which.max(likelihood)]]
  repeated<-sum(abs(likelihood-max(likelihood))<=1e-6*max(1,abs(max(likelihood))))
  if(k>1L&&repeated<2L)return(list(ok=FALSE,reason_code="FORMAL_BEST_NOT_REPLICATED",starts=records))
  n<-length(unique(data$id));parameters<-best$n_parameters
  best$ok<-TRUE;best$starts<-records
  best$selection<-list(k=k,log_likelihood=best$loglik,n_parameters=parameters,
    AIC=-2*best$loglik+2*parameters,BIC=-2*best$loglik+parameters*log(n),
    independent_units=n,replicated_best_starts=repeated,status="accepted",reason_code=NULL)
  best
}

ll_trajectory_score <- function(data,model) {
  beta<-ll_matrix(model$beta);pro<-unlist(model$weights);k<-nrow(beta);degree<-model$degree
  q<-switch(model$random,none=0L,intercept=1L,intercept_slope=2L)
  D<-if(q)ll_matrix(model$random_covariance)else matrix(0,0,0)
  ids<-sort(unique(data$id));prob<-matrix(NA_real_,length(ids),k);loglik<-0
  for(i in seq_along(ids)) {
    d<-data[data$id==ids[i],,drop=FALSE]
    X<-vapply(0:degree,function(power)d$tt^power,numeric(nrow(d)))
    V<-diag(model$residual_variance,nrow(d))
    if(q) {Z<-if(q==1L)matrix(1,nrow(d),1)else cbind(1,d$tt);V<-V+Z%*%D%*%t(Z)}
    C<-chol(V)
    lp<-vapply(seq_len(k),function(c) {
      residual<-d$yy-as.vector(X%*%beta[c,]);u<-forwardsolve(t(C),residual)
      log(pro[c])-.5*(nrow(d)*log(2*pi)+2*sum(log(diag(C)))+sum(u^2))
    },numeric(1))
    total<-ll_logsum(lp);prob[i,]<-exp(lp-total);loglik<-loglik+total
  }
  list(id=ids,prob=prob,loglik=loglik)
}
