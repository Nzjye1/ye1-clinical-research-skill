# Real engineering summary adapter. Table1 remains the sole numerical owner.
run_real_engineering_task <- function(task,output_dir,original_task_path) {
  root<-.clinical_common$root
  if(!identical(task$method_id,"baseline.summary")||!identical(task$purpose,"local_engineering_e2e"))stop("REAL_METHOD_NOT_SUPPORTED",call.=FALSE)
  if(!common_inside(output_dir,root)||file.exists(output_dir)||!dir.exists(dirname(output_dir)))stop("REAL_FRESH_OUTPUT_REQUIRED",call.=FALSE)
  reason<-common_verify_runtime();if(!is.null(reason))stop(reason,call.=FALSE)
  if(is.null(attr(task,"common_task_bytes")))stop("BOUND_TASK_BYTES_REQUIRED",call.=FALSE)
  dir.create(output_dir);dir.create(file.path(output_dir,"private"))
  snapshot<-file.path(output_dir,"private/task-snapshot.json");writeBin(attr(task,"common_task_bytes"),snapshot)
  worker<-file.path(dirname(root),"real_engineering.py")
  if(!common_python(worker,c("prepare",snapshot,output_dir),file.path(output_dir,"private/real-prepare.log")))stop("REAL_PREPARATION_REJECTED",call.=FALSE)
  prepared<-common_json_read(file.path(output_dir,"private/real-prepared.json"))
  data<-utils::read.csv(file.path(output_dir,"private/selected.csv"),colClasses="character",check.names=FALSE,na.strings="",fileEncoding="UTF-8")
  projection<-file.path(output_dir,"private/provider-projection");dir.create(projection);dir.create(file.path(projection,"tables"));dir.create(file.path(projection,"figures"))
  summaries<-list()
  for(v in prepared$variables) {
    values<-as.numeric(data[[v$column]])
    summary<-table1_group_summary(values,"continuous","median_iqr",NULL,"nonmissing")
    row<-table1_stat_row(v$name,paste0(v$name," [",v$unit,"]"),"continuous",NULL,"Overall",summary)
    row$unit<-v$unit;row$summary_scale<-"median_and_interquartile_range_not_confidence_interval"
    summaries[[length(summaries)+1L]]<-row
  }
  table<-do.call(rbind,summaries)
  utils::write.csv(table,file.path(projection,"tables/overall_summary.csv"),row.names=FALSE,na="",fileEncoding="UTF-8")
  grDevices::png(file.path(projection,"figures/overall_summary.png"),width=1500,height=600,res=150)
  tryCatch({graphics::par(mfrow=c(1,3),mar=c(6,4,5,1))
    for(i in seq_len(nrow(table))) {
      r<-table[i,,drop=FALSE];limits<-range(c(r$q1,r$median,r$q3),finite=TRUE)
      if(!all(is.finite(limits))) {graphics::plot.new();graphics::text(.5,.5,"Not estimable");next}
      if(diff(limits)==0)limits<-limits+c(-.5,.5)
      graphics::plot(r$median,1,xlim=limits,ylim=c(.5,1.5),yaxt="n",pch=19,xlab=r$label,ylab="",main="REAL DATA | descriptive")
      graphics::segments(r$q1,1,r$q3,1,lwd=3,col="#176B6B")
      graphics::points(r$median,1,pch=19);graphics::mtext(paste0("n = ",r$n,"; median [Q1,Q3]"),side=3,line=.5,cex=.8)
      graphics::mtext("Local engineering E2E; scientific review pending",side=1,line=4,cex=.65)
    }
  },finally=grDevices::dev.off())
  if(!common_python(worker,c("finish",snapshot,output_dir),file.path(output_dir,"private/real-finish.log")))stop("REAL_EXPORT_REJECTED",call.=FALSE)
  invisible(common_json_read(file.path(output_dir,"result.json")))
}
