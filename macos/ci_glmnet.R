args <- commandArgs(trailingOnly=TRUE)
cache <- args[[1]]
lib <- args[[2]]
source <- args[[3]]
dir.create(lib, recursive=TRUE, showWarnings=FALSE)
.libPaths(c(lib, .Library), include.site=FALSE)
stopifnot(as.character(getRversion()) == '4.6.1', R.version$arch %in% c('aarch64', 'arm64'))
for (file in c('Rcpp_1.1.2.tgz', 'RcppEigen_0.3.4.0.2.tgz', 'iterators_1.0.14.tgz', 'foreach_1.5.2.tgz', 'shape_1.4.6.1.tgz')) {
  install.packages(file.path(cache, file), repos=NULL, type='mac.binary', lib=lib, quiet=FALSE)
}
install.packages(source, repos=NULL, type='source', lib=lib, quiet=FALSE)
stopifnot(as.character(packageVersion('glmnet')) == '5.1', requireNamespace('glmnet', quietly=TRUE))
set.seed(20261031)
x <- matrix(rnorm(200), nrow=50)
y <- rep(c(0, 1), 25)
fit <- glmnet::glmnet(x, y, family='binomial', alpha=1)
stopifnot(length(fit$lambda) > 1, all(is.finite(as.numeric(predict(fit, x, s=fit$lambda[2], type='response')))))
cat('PASS: Apple Silicon glmnet 5.1 compiled from locked clinical source; synthetic calculation completed\n')
