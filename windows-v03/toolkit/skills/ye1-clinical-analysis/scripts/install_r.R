if(.Platform$OS.type=="windows")invisible(suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8")))
args<-commandArgs(trailingOnly=TRUE);Encoding(args)<-"UTF-8"
stopifnot(length(args)>=2L,dir.exists(args[[1L]]),all(file.exists(args[-1L])))
.libPaths(c(args[[1L]],.Library),include.site=FALSE)
utils::install.packages(args[-1L],repos=NULL,type="win.binary",lib=args[[1L]],quiet=TRUE)
stopifnot(as.character(utils::packageVersion("jsonlite"))=="2.0.0",as.character(utils::packageVersion("digest"))=="0.6.39")
cat("LOCAL_R_LIBRARY_READY\n")
