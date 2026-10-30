# Display only: all values were calculated by the unchanged Python KM owner.
if(.Platform$OS.type=="windows")invisible(suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8")))
args<-commandArgs(trailingOnly=TRUE);Encoding(args)<-"UTF-8";stopifnot(length(args)==5L)
d<-read.csv(args[[1]],check.names=FALSE);censor<-read.csv(args[[2]],check.names=FALSE)
grDevices::png(args[[3]],width=1300,height=820,res=150)
graphics::par(mar=c(4.2,4.5,4.6,1.3))
label<-if(args[[5]]=="synthetic")"SYNTHETIC | engineering_test" else if(args[[5]]=="public_fixture")"PUBLIC PBC FIXTURE | software acceptance" else "USER CSV | local analysis"
graphics::plot(d$time,d$survival,type="s",ylim=c(0,1),xlab=paste0("Time (",args[[4]],")"),ylab="Event-free probability",col="#126d85",lwd=1.6,main=paste0(label," | review pending\nFull observed-time Kaplan-Meier display"))
graphics::lines(d$time,d$ci_lower,type="s",col="#86b7c2",lty=2)
graphics::lines(d$time,d$ci_upper,type="s",col="#86b7c2",lty=2)
if(nrow(censor))graphics::points(censor$time,censor$survival,pch=3,col="#126d85",cex=.4)
graphics::legend("bottomleft",legend=c("Kaplan-Meier","Pointwise 95% CI","Censored"),lty=c(1,2,NA),pch=c(NA,NA,3),col=c("#126d85","#86b7c2","#126d85"),bty="n",cex=.78)
grDevices::dev.off()
