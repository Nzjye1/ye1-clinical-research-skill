# Presentation only. Input is the validated public aggregate record.
args<-commandArgs(trailingOnly=TRUE)
if(length(args)!=4L)quit(status=2L)
core<-normalizePath(args[[1]],winslash="/",mustWork=TRUE);out<-args[[4]]
.libPaths(readLines(file.path(core,"runtime-libraries.txt"),warn=FALSE,encoding="UTF-8"))
if(.Platform$OS.type=="windows")suppressWarnings(Sys.setlocale("LC_CTYPE",".UTF-8"))
`%||%`<-function(a,b)if(is.null(a))b else a
for(name in c("clinical_common.R","clinical_interpretation_v09.R","clinical_survival_v06.R"))source(file.path(core,"src/clinanalysis/R",name),local=TRUE,encoding="UTF-8")
response<-tryCatch({
  value<-jsonlite::fromJSON(args[[2]],simplifyVector=FALSE);rec<-value$record;context<-value$context
  origin<-value$origin_context
  disclosure<-if(is.null(origin))"synthetic test only" else paste0(toupper(origin$data_origin)," | ",origin$task_purpose," | scientific review pending")
  artifacts<-list()
  add<-function(path,kind)artifacts[[length(artifacts)+1L]]<<-list(path=gsub("\\\\","/",substring(path,nchar(out)+2L)),kind=kind)
  common_artifact<-function(id,kind,path,result,source_ids,denominator,unit,caption)list(artifact_id=id,kind=kind,path=path,caption=caption)
  write_table<-function(rows,name) {
    path<-file.path(out,"tables",paste0(name,".csv"))
    utils::write.csv(common_interpretation_frame(rows),path,row.names=FALSE,na="",fileEncoding="UTF-8")
    add(path,"table")
  }
  if(!is.null(rec$evaluation)) {
    evaluation<-rec$evaluation;evaluation$semantics<-rec$semantics
    # Presentation identifies the new method; the original numerical-owner
    # record remains unchanged in public.json and its private result receipt.
    evaluation$method_id<-rec$method_id
    evaluation$horizon_results<-lapply(seq_along(evaluation$horizon_results),function(i) {
      h<-evaluation$horizon_results[[i]];h$result_id<-paste0(context$result_id,"-h",i)
      for(section in c("metrics","roc","calibration","dca"))h[[section]]<-lapply(seq_along(h[[section]]),function(j) {
        r<-h[[section]][[j]];r$result_id<-paste0(h$result_id,"-",section,"-",j);r
      });h
    })
    view<-list(survival_evaluation=evaluation,method_version="1.0.0-module",core_version="modular-candidate",
      provider=list(version=context$binding$code_sha256 %||% paste(rep("0",64),collapse="")),
      source_refs=list(list(source_id="unchanged-survival-evaluation-owner")),
      counts=list(training_n=rec$training_summary$n,training_events=rec$training_summary$events,training_censored=rec$training_summary$censored),
      tables=list(),figures=list(),warnings=list(),execution_status="complete")
    if(!is.null(origin)) {
      view$data_origin<-origin$data_origin;view$task_purpose<-origin$task_purpose
      view$test_only<-origin$test_only;view$scientific_review<-"pending"
      view$origin_context<-origin
    }
    written<-common_write_survival_evaluation(view,out)
    if(length(written$warnings))stop("CE_EVALUATION_PLOT_FAILED",call.=FALSE)
    for(a in c(written$tables,written$figures))add(a$path,a$kind)
  }
  if(!is.null(rec$explanation)) {
    e<-rec$explanation;nomo<-e$nomogram
    for(name in c("domains","axes","total_axis"))write_table(nomo[[name]],paste0("cox_nomogram_",name))
    if(length(e$global_importance)) {
      write_table(e$global_importance,"cox_shap_global")
      path<-file.path(out,"figures","cox_shap_global.png")
      grDevices::png(path,width=1300,height=850,res=150)
      graphics::par(mar=c(5,10,5,2));vals<-vapply(e$global_importance,`[[`,0.0,"mean_abs_shap")
      labels<-vapply(e$global_importance,function(r)common_interpretation_plot_wrap(r$feature,24L),"")
      graphics::barplot(vals,names.arg=labels,horiz=TRUE,las=1,col="#176B6B",xlab="Mean absolute contribution (centered log-relative-hazard)",main="Frozen Cox grouped interventional SHAP")
      graphics::mtext(paste0("Application population; analytic training-centering reference | ",disclosure),side=3,line=.7,cex=.8)
      grDevices::dev.off();add(path,"figure")
    }
    plan<-common_interpretation_nomogram_plan(list(nomogram=nomo))
    path<-file.path(out,"figures","cox_nomogram_features.png")
    grDevices::png(path,width=1600,height=max(800,as.integer(length(plan$groups)*290)),res=150)
    graphics::par(mfrow=c(length(plan$groups),1),mar=c(2.4,9,2.1,2),oma=c(3,0,3.5,0))
    for(g in plan$groups) {
      labels<-g$labels
      widths<-pmax(4,vapply(strsplit(labels,"\n",fixed=TRUE),function(z)max(nchar(z))*1.1,0.0))
      lanes<-common_interpretation_plot_lanes(g$points,widths)
      graphics::plot(c(-12,112),c(-.8,max(lanes)+1),type="n",axes=FALSE,xlab="",ylab="")
      graphics::axis(1,at=seq(0,100,20));graphics::mtext(g$feature_label,side=2,line=2.4,las=1,cex=.8)
      graphics::segments(min(g$points),0,max(g$points),0,col="#4D6868",lwd=2)
      graphics::points(g$points,rep(0,length(g$points)),pch=ifelse(g$missing,1,19),col="#176B6B")
      for(i in seq_along(g$points)) {
        graphics::segments(g$points[[i]],.05,g$points[[i]],lanes[[i]]-.15,col="grey70")
        graphics::text(g$points[[i]],lanes[[i]],labels[[i]],cex=.72)
      }
      graphics::box()
    }
    graphics::mtext("Frozen Cox numerical nomogram: prespecified display domains",outer=TRUE,side=3,line=1.6,font=2)
    graphics::mtext(paste0("Observed training feature ranges unknown | frozen imputation | ",disclosure),outer=TRUE,side=3,line=.1,cex=.8)
    graphics::mtext("Feature points (each feature uses the same 0-100 ruler)",outer=TRUE,side=1,line=1,cex=.85)
    grDevices::dev.off();add(path,"figure")
    path<-file.path(out,"figures","cox_nomogram_total.png")
    grDevices::png(path,width=1600,height=800,res=150);graphics::par(mfrow=c(1,2),mar=c(5,5,4,2),oma=c(3,0,2,0))
    axis<-nomo$total_axis;first<-Filter(function(r)r$horizon==axis[[1]]$horizon,axis)
    x<-vapply(first,`[[`,0.0,"total_points");y<-vapply(first,`[[`,0.0,"score")
    graphics::plot(x,y,type="b",pch=19,col="#176B6B",xlab="Total points",ylab="Centered log-relative-hazard",main="Points to additive score")
    horizons<-sort(unique(vapply(axis,`[[`,0.0,"horizon")));cols<-grDevices::hcl.colors(length(horizons),"Dark 3")
    xr<-range(x);if(diff(xr)==0)xr<-xr+c(-.5,.5)
    graphics::plot(xr,c(0,1),type="n",xlab="Total points",ylab="Frozen cumulative event probability",main="Separate horizon-specific risk ticks")
    for(k in seq_along(horizons)) {
      rows<-Filter(function(r)r$horizon==horizons[[k]],axis)
      graphics::points(vapply(rows,`[[`,0.0,"total_points"),vapply(rows,`[[`,0.0,"event_risk"),pch=k,col=cols[[k]],cex=1.1)
    }
    graphics::legend("topleft",legend=paste("t =",horizons,rec$semantics$time_unit),pch=seq_along(horizons),col=cols,bty="n",cex=.75)
    graphics::mtext("Risk ticks use the frozen Breslow baseline. Contributions are not probability SHAP.",outer=TRUE,side=1,line=1,cex=.8)
    graphics::mtext(disclosure,outer=TRUE,side=3,line=.5,cex=.85)
    grDevices::dev.off();add(path,"figure")
  }
  list(ok=TRUE,artifacts=artifacts)
},error=function(e) {
  if(grDevices::dev.cur()>1L)grDevices::dev.off()
  list(ok=FALSE,reason_code="CE_PROJECTION_FAILED")
})
jsonlite::write_json(response,args[[3]],auto_unbox=TRUE,null="null",na="null",digits=17)
