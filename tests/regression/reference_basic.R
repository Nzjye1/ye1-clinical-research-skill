# Independent base R/survival computations; no candidate provider is sourced.
if(.Platform$OS.type=='windows')invisible(suppressWarnings(Sys.setlocale('LC_CTYPE','.UTF-8')))
args<-commandArgs(TRUE);Encoding(args)<-'UTF-8';.libPaths(c(args[[3]],.Library),include.site=FALSE)
d<-read.csv(args[[1]],check.names=FALSE,stringsAsFactors=FALSE,fileEncoding='UTF-8-BOM');d$group<-factor(d$group,levels=c('A','B'))
fit<-lm(y~x+z+group,data=d);X<-model.matrix(fit);iv<-solve(crossprod(X));hat<-rowSums((X%*%iv)*X);vc<-iv%*%crossprod(X,X*as.numeric(residuals(fit)^2/(1-hat)^2))%*%iv;se<-sqrt(diag(vc));beta<-coef(fit);df<-df.residual(fit)
linear<-data.frame(estimate=beta,standard_error=se,lower=beta-qt(.975,df)*se,upper=beta+qt(.975,df)*se,p=2*pt(-abs(beta/se),df))
f<-glm(binary~x+z+group,data=d,family=binomial(),control=glm.control(epsilon=1e-10,maxit=100));b<-coef(f);se<-sqrt(diag(vcov(f)));logistic<-data.frame(estimate=exp(b),standard_error=se,lower=exp(b-qnorm(.975)*se),upper=exp(b+qnorm(.975)*se),p=2*pnorm(-abs(b/se)))
cox<-survival::coxph(survival::Surv(time,as.numeric(status))~x+z+group,data=d,ties='breslow',control=survival::coxph.control(timefix=FALSE));b<-coef(cox);se<-sqrt(diag(vcov(cox)));coxrows<-data.frame(estimate=exp(b),standard_error=se,lower=exp(b-qnorm(.975)*se),upper=exp(b+qnorm(.975)*se),p=2*pnorm(-abs(b/se)))
ph<-survival::cox.zph(cox,transform='km',terms=TRUE,singledf=FALSE,global=TRUE)$table
km<-survival::survfit(survival::Surv(time,as.numeric(status))~1,data=d,conf.type='log-log',timefix=FALSE);grid<-c(0,5,10,20);k<-summary(km,times=grid);risk<-vapply(grid,function(t)sum(d$time>=t),0L);lo<-k$lower;hi<-k$upper;lo[grid==0]<-1;hi[grid==0]<-1
answer<-list(linear=linear,logistic=logistic,cox=coxrows,ph=as.data.frame(ph),km=data.frame(time=grid,estimate=k$surv,lower=lo,upper=hi,n_at_risk=risk),baseline=list(n=nrow(d),x_mean=mean(d$x),x_sd=sd(d$x),x_quantiles=as.list(quantile(d$x,c(.25,.5,.75),type=7)),group_counts=as.list(table(d$group))),reference=list(R=as.character(getRversion()),survival=as.character(packageVersion('survival')),candidate_functions_called=FALSE))
jsonlite::write_json(answer,args[[2]],digits=17,pretty=TRUE,auto_unbox=TRUE,dataframe='rows',null='null',na='null')
