# Presentation only: original summary numbers, no fitting or new intervals.
if(.Platform$OS.type=='windows')invisible(suppressWarnings(Sys.setlocale('LC_CTYPE','.UTF-8')))
a<-commandArgs(TRUE);Encoding(a)<-'UTF-8';stopifnot(length(a)==3L);.libPaths(c(a[[1]],.Library),include.site=FALSE)
v<-jsonlite::fromJSON(a[[2]]);png(a[[3]],width=1200,height=700,res=110)
par(mar=c(5,5,4,2)+.1)
if(!is.null(v$contrast)){
 par(mfrow=c(1,2));q<-v$contrast;domain<-range(c(q$lower,q$upper,q$estimate,q$null));span<-diff(domain);if(span==0)span<-1
 plot(q$estimate,1,xlim=domain+c(-.08,.08)*span,ylim=c(.5,1.5),yaxt='n',xlab=q$scale,ylab='',pch=19,col='#376b8d',main='Original contrast and 95% CI')
 arrows(q$lower,1,q$upper,1,angle=90,code=3,length=.08,col='#376b8d',lwd=2);abline(v=q$null,lty=2,col='#888888')
 mtext('Existing numerical output; no new interval computed',side=3,line=.3,cex=.7)
}
barplot(v$values,width=1,names.arg=v$labels,col='#376b8d',ylab='Records / planned sample size',main=v$title)
mtext(paste('Unit:',gsub('_',' ',v$unit,fixed=TRUE)),side=3,line=.2,cex=.8)
invisible(dev.off())
