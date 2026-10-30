.libPaths(c(strsplit(Sys.getenv("CLINICAL_TEST_R_LIBRARIES"), .Platform$path.sep, fixed=TRUE)[[1]], .libPaths()))
cat(paste(.libPaths(), collapse="\n"), "\n")
for (p in c("jsonlite", "digest", "sandwich")) {
  cat(p, if (requireNamespace(p, quietly=TRUE)) as.character(packageVersion(p)) else "UNAVAILABLE", "\n")
}
versions <- lapply(c("jsonlite","digest"),function(p)as.character(packageVersion(p)))
names(versions)<-c("jsonlite","digest")
versions<-c(list(R=as.character(getRversion())),versions)
paths<-lapply(c("jsonlite","digest"),find.package);names(paths)<-c("jsonlite","digest")
jsonlite::write_json(list(versions=versions,paths=paths),commandArgs(TRUE)[1],auto_unbox=TRUE,pretty=TRUE)
