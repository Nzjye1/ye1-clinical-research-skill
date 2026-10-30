# Local regeneration from the explicitly selected, existing survival library.
# Does not download, install, or copy identifiers/other clinical variables.
if(.Platform$OS.type=="windows")invisible(suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8")))
a <- commandArgs(trailingOnly=TRUE); Encoding(a) <- "UTF-8"
stopifnot(length(a)==2L, !file.exists(a[[1]]))
.libPaths(c(a[[2]], .Library), include.site=FALSE)
stopifnot(read.dcf(file.path(a[[2]],"survival","DESCRIPTION"), fields="Version")[[1]]=="3.8-6")
stopifnot(read.dcf(file.path(a[[2]],"survival","DESCRIPTION"), fields="License")[[1]]=="LGPL (>= 2)")
e <- new.env()
utils::data("pbc", package="survival", lib.loc=a[[2]], envir=e)
d <- e$pbc[, c("time", "status")]
stopifnot(nrow(d)==418L, !anyNA(d), all(d$time>0), all(d$status %in% 0:2))
con <- file(a[[1]], open="wb")
writeLines(c('"time","status"', paste(d$time,d$status,sep=",")), con, sep="\n")
close(con)
cat("Fixed public fixture generated locally; no rows emitted.\n")
