# Ye1 numerical worker: existing R stats + jsonlite. No automatic method fallback.
suppressPackageStartupMessages(library(jsonlite))
args <- commandArgs(trailingOnly=TRUE)
input <- fromJSON(args[1], simplifyVector=FALSE)
`%or%` <- function(a,b) if(is.null(a)) b else a
need <- function(ok,msg) if(!isTRUE(ok)) stop(msg,call.=FALSE)
num <- function(x) as.numeric(unlist(x))
chars <- function(x) as.character(unlist(x))
finite <- function(x) all(is.finite(x))
safe <- function(f) tryCatch(f(),error=function(e) list(status='BLOCKED_ESTIMATION',reason=conditionMessage(e)))
warn_fit <- function(expr) {
  ws <- character(); fit <- withCallingHandlers(expr,warning=function(w) {ws <<- c(ws,conditionMessage(w));invokeRestart('muffleWarning')})
  list(fit=fit,warnings=ws)
}

sample_size <- function(s) {
  method <- s$method %or% ''; required <- switch(method,
    mean_precision=c('sd','half_width','confidence','design','assumption_source'),
    proportion_precision=c('proportion','half_width','confidence','design','assumption_source'),
    two_mean=c('sd','difference','alpha','power','design','assumption_source'),
    two_proportion=c('p1','p2','alpha','power','design','assumption_source'), character())
  if(!length(required)) return(list(status='PLAN_ONLY',reason='Choose supported method/design; no guessed sample size',supported=c('mean_precision','proportion_precision','two_mean','two_proportion')))
  missing <- required[vapply(required,function(k) is.null(s[[k]]) || identical(s[[k]],''),logical(1))]
  if(length(missing)) return(list(status='PLAN_ONLY',method=method,missing=missing,reason='Supply effect or precision assumptions and their provenance'))
  need(s$design=='independent_simple_random','Clustered, paired, survival, repeated or model-development design needs another method')
  confidence <- s$confidence %or% 0.95; alpha <- s$alpha %or% 0.05; power <- s$power %or% 0.8
  need(confidence>0 && confidence<1 && alpha>0 && alpha<1 && power>alpha && power<1,'Invalid confidence/alpha/power')
  if(method=='mean_precision') {
    need(s$sd>0 && s$half_width>0,'Positive SD and target half width required')
    n <- ceiling((qnorm((1+confidence)/2)*s$sd/s$half_width)^2)
    note <- 'Normal approximation for mean CI; assumed SD known/planning value, iid observations. Verify achieved precision and distribution.'
  }
  if(method=='proportion_precision') {
    need(s$proportion>0 && s$proportion<1 && s$half_width>0 && s$half_width<1,'Interior anticipated proportion and valid half width required')
    n <- ceiling(qnorm((1+confidence)/2)^2*s$proportion*(1-s$proportion)/s$half_width^2)
    note <- 'Wald normal-approximation planning only; not exact/Wilson assurance. Extreme proportions/small expected cells require exact planning.'
    need(n*s$proportion>=5 && n*(1-s$proportion)>=5,'Approximation too sparse; exact precision planning required')
  }
  if(method=='two_mean') {
    need(s$sd>0 && s$difference!=0,'Positive common SD and nonzero difference required')
    n <- ceiling(power.t.test(delta=abs(s$difference),sd=s$sd,sig.level=alpha,power=power,type='two.sample',alternative='two.sided',strict=TRUE)$n)
    note <- 'Equal allocation independent two-sample t test, common SD, two-sided strict power; n per group. Not Welch/paired/clustered design.'
  }
  if(method=='two_proportion') {
    need(s$p1>0 && s$p1<1 && s$p2>0 && s$p2<1 && s$p1!=s$p2,'Distinct interior anticipated proportions required')
    n <- ceiling(power.prop.test(p1=s$p1,p2=s$p2,sig.level=alpha,power=power,alternative='two.sided',strict=TRUE)$n)
    note <- 'Equal allocation normal approximation without continuity correction, two-sided strict power; n per group. Not exact or noninferiority design.'
  }
  loss <- s$loss_fraction %or% 0;need(loss>=0 && loss<1,'Loss fraction must be in [0,1)')
  list(status='COMPUTED_REVIEW_PENDING',method=method,assumptions=s,analyzable_n=as.integer(max(2,n)),recruit_n=as.integer(ceiling(max(2,n)/(1-loss))),unit=if(grepl('^two_',method)) 'per group; two groups' else 'total',limitations=note,posthoc_observed_power=FALSE)
}

if(!is.null(input$sample_size)) {
  result <- safe(function() sample_size(input$sample_size))
} else {
  fields <- setNames(input$dictionary$fields,vapply(input$dictionary$fields,function(f) f$name,character(1)))
  data <- as.data.frame(setNames(lapply(names(fields),function(n) {
    vals <- lapply(input$rows,function(r) r[[n]] %or% NA)
    x <- unlist(vals); f <- fields[[n]]
    if(f$type %in% c('number','integer')) as.numeric(x) else as.character(x)
  }),names(fields)),stringsAsFactors=FALSE,check.names=FALSE)
  N <- nrow(data)
  encode <- function(df, predictors, fitted=NULL, impute=FALSE) {
    parts <- list('(Intercept)'=rep(1,nrow(df)));parameters <- list()
    for(n in predictors) {
      f <- fields[[n]]; x <- df[[n]]
      need(f$type %in% c('number','integer','category','binary'),'Unsupported predictor type')
      if(f$type %in% c('number','integer')) {
        pp <- if(is.null(fitted)) list(median=median(x,na.rm=TRUE),center=mean(x,na.rm=TRUE),scale=sd(x,na.rm=TRUE)) else fitted[[n]]
        need(finite(unlist(pp)) && pp$scale>0,paste('No usable variation in',n))
        if(impute) x[is.na(x)] <- pp$median
        # Regression retains original units; prediction explicitly scales from training only.
        if(impute) x <- (x-pp$center)/pp$scale
        parts[[n]] <- x;parameters[[n]] <- pp
      } else {
        need(!anyNA(x),'Categorical missingness requires complete case; no implicit mode imputation')
        levels <- chars(f$levels);ref <- f$reference %or% levels[1]
        need(ref %in% levels,'Reference level absent')
        need(all(x %in% levels),'Unknown factor level')
        for(l in levels[levels!=ref]) parts[[paste0(n,'[',l,' vs ',ref,']')]] <- as.numeric(x==l)
        parameters[[n]] <- list(levels=levels,reference=ref)
      }
    }
    x <- do.call(cbind,parts);colnames(x)<-names(parts)
    need(finite(x),'Nonfinite design matrix');list(x=x,parameters=parameters)
  }
  logistic <- function(x,y) {
    p<-ncol(x);need(qr(x)$rank==p,'Rank-deficient model; no silently dropped variables')
    need(length(unique(y))==2,'Binary outcome has one class')
    ep<-min(sum(y==1),sum(y==0))/max(1,p-1)
    need(ep>=10,'Sparse effective events per predictor parameter (<10 conservative engine guard); expert method/validation required, not universal sufficiency rule')
    obj<-warn_fit(glm.fit(x=x,y=y,family=binomial(),control=glm.control(maxit=100,epsilon=1e-10)))
    fit<-obj$fit;need(fit$converged && !length(obj$warnings),'Logistic fit nonconverged/warned; separation or instability suspected')
    need(finite(fit$coefficients) && all(fit$fitted.values>1e-8 & fit$fitted.values<1-1e-8),'Separation/extreme fitted probabilities; MLE not accepted')
    h <- crossprod(x,x*as.numeric(fit$fitted.values*(1-fit$fitted.values)))
    need(rcond(h)>1e-10,'Ill-conditioned logistic information; no finite MLE claim')
    vc<-solve(h);se<-sqrt(diag(vc));need(finite(se) && all(se>0),'Invalid logistic standard errors')
    list(beta=fit$coefficients,se=se,vcov=vc,fit=fit,event_per_parameter=ep)
  }
  coeff_rows <- function(beta,se,critical,pval,logit=FALSE) {
    lapply(seq_along(beta),function(i) {
      lo<-beta[i]-critical*se[i];hi<-beta[i]+critical*se[i]
      rr<-list(term=names(beta)[i],estimate=unname(beta[i]),se=unname(se[i]),ci95=c(unname(lo),unname(hi)),p=unname(pval[i]),scale=if(logit)'log odds' else 'outcome units per predictor unit')
      if(logit) {need(hi<log(.Machine$double.xmax),'OR interval overflow; unstable model');rr$odds_ratio<-unname(exp(beta[i]));rr$or_ci95<-c(unname(exp(lo)),unname(exp(hi)))}
      rr
    })
  }
  run_task <- function(t) {
    kind<-t$kind;vars<-chars(t$variables);predictors<-chars(t$predictors)
    ci<-0.95
    if(kind=='describe') {
      need(length(vars)>0,'Select variables for description')
      grouped <- if(is.null(t$group)) list(All=seq_len(N)) else split(seq_len(N),data[[t$group]],drop=TRUE)
      output<-list()
      for(g in names(grouped)) for(n in vars) {
        v<-data[[n]][grouped[[g]]];f<-fields[[n]];nn<-sum(!is.na(v));v2<-v[!is.na(v)]
        r<-list(group=g,variable=n,n_total=length(v),n_observed=nn,n_missing=sum(is.na(v)),unit=f$unit %or% NULL)
        if(f$type %in% c('number','integer')) {
          r$mean<-if(nn)mean(v2) else NULL;r$sd<-if(nn>1)sd(v2) else NULL;r$quantile_type<-7
          r$quantiles<-if(nn)as.list(setNames(as.numeric(quantile(v2,c(0,.25,.5,.75,1),type=7)),c('min','q1','median','q3','max'))) else NULL
        } else {
          lev<-if(is.null(f$levels)) sort(unique(v2)) else chars(f$levels)
          r$levels<-lapply(lev,function(l)list(level=l,count=sum(v2==l),denominator=nn,percent=if(nn)100*mean(v2==l) else NULL))
        };output[[length(output)+1]]<-r
      }
      return(list(status='OK',kind=kind,statistics=output,group_missing=if(is.null(t$group))0 else sum(is.na(data[[t$group]])),missing_method='Variable-wise available records; no imputation'))
    }
    used<-unique(c(t$outcome,t$group,t$paired_with,predictors));need(length(used)>0,'No variables selected')
    cc<-complete.cases(data[,used,drop=FALSE]);d<-data[cc,,drop=FALSE];n<-nrow(d)
    if(kind=='prediction' && t$missing=='train_median') {
      catnames<-predictors[vapply(predictors,function(n) fields[[n]]$type %in% c('category','binary'),logical(1))]
      cc<-complete.cases(data[,c(t$outcome,catnames),drop=FALSE]);d<-data[cc,,drop=FALSE];n<-nrow(d)
    }
    base<-list(status='OK',kind=kind,n_total=N,n_used=n,n_excluded=N-n,missing_method=t$missing,source_rows=as.list(which(cc)+1L))
    need(n>=3,'Insufficient complete observations')
    if(kind=='compare') {
      method<-t$method; y<-d[[t$outcome]]
      if(method=='paired_t') {
        need(is.numeric(y) && is.numeric(d[[t$paired_with]]),'Paired t needs numeric paired columns')
        a<-y;b<-d[[t$paired_with]];f<-t.test(a,b,paired=TRUE,conf.level=ci)
        estimate<-mean(a-b);orientation<-paste(t$outcome,'minus',t$paired_with)
      } else {
        need(!is.null(t$group) && length(unique(d[[t$group]]))==2,'Comparison requires exactly two groups')
        lev<-chars(t$group_order);need(length(lev)==2 && setequal(lev,unique(d[[t$group]])),'Explicit group_order required')
        a<-y[d[[t$group]]==lev[1]];b<-y[d[[t$group]]==lev[2]];orientation<-paste(lev[1],'minus',lev[2]);estimate<-NULL
        if(method %in% c('welch_t','wilcoxon')) {
          need(is.numeric(y) && min(length(a),length(b))>=2,'Numeric observations and at least two per group required')
          if(method=='welch_t') {f<-t.test(a,b,var.equal=FALSE,conf.level=ci);estimate<-mean(a)-mean(b)}
          if(method=='wilcoxon') {f<-wilcox.test(a,b,exact=FALSE,correct=TRUE);orientation<-'Distribution/rank comparison; not automatically a test of medians'}
        } else if(method %in% c('fisher','chi_square')) {
          tab<-table(factor(d[[t$group]],levels=lev),factor(y,levels=chars(fields[[t$outcome]]$levels)))
          need(ncol(tab)>=2 && all(rowSums(tab)>0) && all(colSums(tab)>0),'Empty contingency margins')
          if(method=='fisher') {need(all(dim(tab)==2),'Only 2 by 2 Fisher supported');f<-fisher.test(tab);estimate<-unname(f$estimate);orientation<-'Conditional odds ratio for first outcome level, first group vs second group'}
          else {expected<-outer(rowSums(tab),colSums(tab))/sum(tab);need(all(expected>=5),'Chi-square expected counts <5; choose/confirm exact method explicitly');f<-chisq.test(tab,correct=FALSE)}
          base$counts<-unclass(tab);base$group_order<-lev;base$outcome_order<-chars(fields[[t$outcome]]$levels)
        } else stop('Unsupported comparison; no method chosen automatically')
      }
      need(finite(f$p.value),'Test statistic/p-value not estimable; no null masquerading as a result')
      extended<-function(z) lapply(z,function(v) if(is.infinite(v)) if(v>0)'positive_infinity' else 'negative_infinity' else unname(v))
      base$method<-f$method;base$p<-unname(f$p.value);base$estimate<-if(is.null(estimate))NULL else if(is.infinite(estimate))'positive_infinity' else estimate;base$ci95<-if(is.null(f$conf.int)) NULL else extended(f$conf.int);base$orientation<-orientation
      base$group_n<-c(length(a),length(b));return(base)
    }
    need(length(predictors)>0 && !t$outcome %in% predictors,'Select independent predictors, excluding outcome')
    if(kind=='linear') {
      need(is.numeric(d[[t$outcome]]),'Linear outcome must be numeric');enc<-encode(d,predictors);x<-enc$x;y<-d[[t$outcome]];p<-ncol(x)
      need(n>p+2 && qr(x)$rank==p && rcond(crossprod(x))>1e-12,'Insufficient residual degrees/rank or ill-conditioned design')
      need(var(y)>0,'Constant outcome; inferential model not estimable')
      fit<-lm.fit(x,y);df<-n-p;s2<-sum(fit$residuals^2)/df;need(sum(fit$residuals^2)>.Machine$double.eps*max(1,sum((y-mean(y))^2)),'Zero/numerically zero residual variance; inferential model not estimable')
      inv<-solve(crossprod(x));hat<-rowSums((x%*%inv)*x)
      covtype<-t$covariance %or% '';need(covtype %in% c('classical','HC3'),'Explicit covariance classical or HC3 required')
      vc<-if(covtype=='classical') s2*inv else {need(all(hat<1-1e-8),'HC3 leverage singularity');inv%*%crossprod(x,x*as.numeric(fit$residuals^2/(1-hat)^2))%*%inv}
      se<-sqrt(diag(vc));need(finite(se)&&all(se>0),'Invalid standard error');b<-fit$coefficients;pv<-2*pt(-abs(b/se),df)
      base$coefficients<-coeff_rows(b,se,qt(.975,df),pv);base$df<-df;base$covariance<-covtype;base$r_squared<-1-sum(fit$residuals^2)/sum((y-mean(y))^2)
      base$diagnostics<-list(max_leverage=max(hat),residual_sd=sqrt(s2),residuals=as.list(fit$residuals),fitted=as.list(fit$fitted.values),assumptions='Host inspect residual structure/linearity, selection, confounding and independence. HC3 does not cure bias/nonlinearity.')
      return(base)
    }
    need(fields[[t$outcome]]$type=='binary','Binary outcome dictionary required')
    event<-t$event;need(event %in% chars(fields[[t$outcome]]$levels),'Explicit event coding required');y<-as.numeric(d[[t$outcome]]==event)
    base$event<-event;base$events<-sum(y);base$non_events<-sum(1-y)
    if(kind=='logistic') {
      e<-encode(d,predictors);fit<-logistic(e$x,y);base$coefficients<-coeff_rows(fit$beta,fit$se,qnorm(.975),2*pnorm(-abs(fit$beta/fit$se)),TRUE)
      base$method<-'Unpenalized binomial logit MLE, Wald 95% CI';base$event_per_parameter<-fit$event_per_parameter;base$limitations<-'Conditional association; not risk ratio/causality. No automatic Firth/ridge substitution.';return(base)
    }
    need(kind=='prediction','Unsupported task')
    test_fraction<-t$test_fraction;need(is.numeric(test_fraction)&&test_fraction>=.2&&test_fraction<=.5,'Predeclare test fraction 0.2 to 0.5')
    need(is.numeric(t$seed)&&length(t$seed)==1,'Predeclare reproducible seed');set.seed(t$seed)
    idx<-seq_len(n);test<-sort(unlist(lapply(0:1,function(c) {pool<-idx[y==c];need(length(pool)>=10,'Too few per class for split');sample(pool,size=floor(length(pool)*test_fraction))})));train<-setdiff(idx,test)
    impute<-t$missing=='train_median';enc<-encode(d[train,,drop=FALSE],predictors,impute=impute)
    # With complete case, fitting and holdout use unscaled original units.
    enc_test<-encode(d[test,,drop=FALSE],predictors,fitted=enc$parameters,impute=impute)
    fit<-logistic(enc$x,y[train]);prob<-as.numeric(plogis(enc_test$x%*%fit$beta));obs<-y[test];nt<-length(test)
    need(finite(prob)&&min(sum(obs),sum(1-obs))>=5,'Holdout lacks enough events/non-events for basic evaluation')
    ranks<-rank(prob,ties.method='average');np<-sum(obs);nn<-nt-np;auc<-(sum(ranks[obs==1])-np*(np+1)/2)/(np*nn)
    thresholds<-c(Inf,sort(unique(prob),decreasing=TRUE),-Inf)
    roc<-lapply(thresholds,function(z)list(threshold=if(is.finite(z))z else NULL,endpoint=if(is.infinite(z))if(z>0)'none_positive' else 'all_positive' else NULL,tpr=sum(obs==1 & prob>=z)/np,fpr=sum(obs==0 & prob>=z)/nn))
    cuts<-unique(as.numeric(quantile(prob,seq(0,1,length.out=min(6,nt+1)),type=7)));bins<-if(length(cuts)<2)rep(1L,nt) else as.integer(cut(prob,cuts,include.lowest=TRUE))
    calibration<-lapply(sort(unique(bins)),function(b) {j<-which(bins==b);e<-sum(obs[j]);ci<-binom.test(e,length(j))$conf.int;list(bin=b,n=length(j),mean_prediction=mean(prob[j]),observed_fraction=mean(obs[j]),observed_ci95=unname(ci))})
    base$validation<-'Single prespecified stratified independent holdout; not external validation, no tuning on holdout'
    base$training_n<-length(train);base$test_n<-nt;base$train_source_rows<-as.list(which(cc)[train]+1L);base$test_source_rows<-as.list(which(cc)[test]+1L)
    base$training_preprocessing<-enc$parameters;base$coefficients<-as.list(fit$beta);base$metrics<-list(auc=auc,brier=mean((prob-obs)^2),log_loss=-mean(obs*log(pmax(prob,1e-15))+(1-obs)*log(pmax(1-prob,1e-15))),auc_ci=NULL,calibration_slope=NULL,calibration_note='Empirical holdout bins with exact binomial intervals; slope/intercept/CI not estimated')
    base$plot_payload<-list(kind='binary_prediction_holdout',y_true=as.list(obs),y_probability=as.list(prob),source_rows=base$test_source_rows,roc=roc,calibration=calibration,event=event,threshold_policy='No classification cutoff selected; no DCA computed')
    base$limitations<-'Single holdout is noisy; no external validation, clinical utility or transportability claim. Outcome missing rows excluded; category missing rows excluded. Numeric train-median assumption needs review.';base
  }
  results<-lapply(input$tasks,function(t) {r<-safe(function()run_task(t));r$id<-t$id;r})
  result<-list(results=results,r_version=R.version.string,jsonlite_version=as.character(packageVersion('jsonlite')))
}
write_json(result,args[2],auto_unbox=TRUE,pretty=TRUE,null='null',na='null',digits=16)
