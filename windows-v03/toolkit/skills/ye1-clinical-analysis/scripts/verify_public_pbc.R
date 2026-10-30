# Independent reference only; production estimates remain the Python owner's.
a <- commandArgs(trailingOnly=TRUE)
stopifnot(length(a)==3L, !file.exists(a[[3]]))
stopifnot(as.character(getRversion())=="4.6.1")
.libPaths(.Library, include.site=FALSE)
stopifnot(read.dcf(file.path(.Library,"survival","DESCRIPTION"), fields="Version")[[1]]=="3.8-6")
d <- read.csv(a[[1]])
grid <- read.csv(a[[2]])$time
stopifnot(identical(names(d), c("time","status")), nrow(d)==418L,
          !anyNA(d), all(d$time>0), all(d$status %in% 0:2),
          sum(d$status!=0)==186L)
fit <- survival::survfit(survival::Surv(time, status!=0)~1, data=d, conf.type="log-log")
s <- summary(fit, times=grid)
stopifnot(length(s$time)==length(grid))
options(digits=17)
write.csv(data.frame(time=s$time,n_at_risk=s$n.risk,survival=s$surv,
                     ci_lower=s$lower,ci_upper=s$upper), a[[3]], row.names=FALSE)
cat("Independent survival::survfit 3.8-6 log-log reference completed; no rows emitted.\n")
