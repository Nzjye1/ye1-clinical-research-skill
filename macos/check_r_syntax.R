args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args) == 1L, dir.exists(args[[1L]]))
paths <- list.files(args[[1L]], pattern='\\.[rR]$', full.names=TRUE, recursive=TRUE)
failures <- character()
for (path in paths) {
  tryCatch(parse(file=path, encoding='UTF-8'), error=function(error) {
    failures <<- c(failures, paste(path, conditionMessage(error), sep=': '))
  })
}
cat('R files checked:', length(paths), '\n')
if (length(failures)) {
  cat(paste(failures, collapse='\n'), '\n')
  quit(status=1L)
}
cat('PASS R syntax\n')
