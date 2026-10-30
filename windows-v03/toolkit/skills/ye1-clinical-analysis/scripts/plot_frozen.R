# Presentation only: no new fitting, evaluation statistic or identifier labels.
if(.Platform$OS.type=='windows')invisible(suppressWarnings(Sys.setlocale('LC_CTYPE','.UTF-8')))
a<-commandArgs(TRUE);Encoding(a)<-'UTF-8';stopifnot(length(a)==2L);.libPaths(c(a[[1]],.Library),include.site=FALSE)
v<-jsonlite::fromJSON(a[[2]],simplifyVector=TRUE)
d<-if(v$format %in% c('json','module_json'))jsonlite::fromJSON(v$source,simplifyDataFrame=TRUE) else read.csv(v$source,check.names=FALSE,stringsAsFactors=FALSE,fileEncoding='UTF-8-BOM')
if(v$format=='module_json')d<-d$private_record$individual
stopifnot(is.data.frame(d),v$prediction %in% names(d));p<-as.numeric(d[[v$prediction]]);valid<-is.finite(p);stopifnot(any(valid))
if(v$format %in% c('json','module_json')){
    n<-jsonlite::fromJSON(v$normalized,simplifyDataFrame=TRUE);if(v$format=='module_json')n<-list(rows=n$payload$rows)
    stopifnot(is.data.frame(n$rows),v$subject_key %in% names(n$rows),'row_index' %in% names(d),all(d$row_index==floor(d$row_index)),all(d$row_index>=0 & d$row_index<nrow(n$rows)))
    d<-cbind(subject_id=as.character(n$rows[[v$subject_key]][d$row_index+1L]),d,stringsAsFactors=FALSE)
}
write.csv(d,v$prediction_table,row.names=FALSE,fileEncoding='UTF-8',na='')
observed<-if(is.null(v$observed))NULL else as.numeric(d[[v$observed]]);paired<-if(is.null(observed))rep(FALSE,length(p)) else valid & is.finite(observed)
png(v$image,width=1200,height=820,res=120);par(mar=c(5,5,4,2)+.1)
if(v$kind=='continuous' && any(paired)){
    plot(p[paired],observed[paired],pch=19,cex=.6,col=grDevices::adjustcolor('#356f91',alpha.f=.5),xlab='Frozen prediction (original outcome units)',ylab='Observed outcome (original units)',main='External frozen predictions: identity line only')
    abline(a=0,b=1,col='#ae523b',lty=2,lwd=2)
    mtext(sprintf('n=%d complete prediction/outcome pairs; no fitted regression line',sum(paired)),side=3,line=.3,cex=.8)
}else if(v$kind=='risk' && 'horizon' %in% names(d)){
    horizons<-sort(unique(d$horizon));stopifnot(length(horizons)<=12L);par(mfrow=c(ceiling(length(horizons)/3),min(3,length(horizons))))
    for(t in horizons){selected<-valid & d$horizon==t;stopifnot(any(selected));hist(p[selected],breaks=seq(0,1,length.out=17),col='#79a8bf',border='white',main=paste('Horizon',t,v$time_unit),xlab='Frozen event risk',ylab='Prediction count')}
}else{
    if(v$kind %in% c('binary','risk')){stopifnot(all(p[valid]>=0 & p[valid]<=1));breaks<-seq(0,1,length.out=17)}else{breaks<-'Sturges'}
    hist(p[valid],breaks=breaks,col='#79a8bf',border='white',main=if(v$kind=='continuous')'Frozen prediction distribution' else 'Frozen probability distribution',xlab=if(v$kind=='continuous')'Prediction (original outcome units)' else 'Predicted probability',ylab='Record count')
    mtext(sprintf('n=%d finite predictions; descriptive display, no new evaluation metric',sum(valid)),side=3,line=.3,cex=.8)
}
invisible(dev.off());jsonlite::write_json(list(prediction_rows=nrow(d),finite_predictions=sum(valid),nonfinite_predictions=sum(!valid),paired_observed_predictions=sum(paired),display='scatter_identity_only_or_prediction_histogram',no_identifiers_plotted=TRUE),v$counts,auto_unbox=TRUE,digits=17)
