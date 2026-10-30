# Transport and aggregate artifacts only. The numerical owner is provider.R.
mm_json <- function(x,path) jsonlite::write_json(x,path,auto_unbox=TRUE,pretty=TRUE,digits=17,
  null="null",na="null",dataframe="rows")
mm_csv <- function(rows,path) {
  if(is.data.frame(rows)) d <- rows else {
    fields <- unique(unlist(lapply(rows,names),use.names=FALSE))
    if(!length(fields)) { utils::write.csv(data.frame(status=character()),path,row.names=FALSE);return(invisible(NULL)) }
    rr <- lapply(rows,function(r) as.data.frame(setNames(lapply(fields,function(k) {
      v <- r[[k]]
      if(is.null(v)) NA else if(is.list(v))as.character(jsonlite::toJSON(v,auto_unbox=TRUE,null="null",na="null",digits=17)) else v
    }),fields),stringsAsFactors=FALSE,check.names=FALSE))
    d <- do.call(rbind,rr)
  }
  d[] <- lapply(d,function(x)if(is.numeric(x))ifelse(is.na(x),NA_character_,formatC(x,format="g",digits=17)) else x)
  utils::write.csv(d,path,row.names=FALSE,na="",fileEncoding="UTF-8")
}

mm_project_common <- function(record) {
  # Fragment only: integrator sets the final root version/bindings and validates.
  list(method_id=record$method_id,execution_status=switch(record$status,completed="complete",partial="partial","blocked"),
    applicability_status=if(record$status=="completed")"limited" else "fail",scientific_review="pending",export_status="local_only",
    test_only=TRUE,reason_code=record$reason_code,stage="compute",mediation_matching=record,
    completed_parts=as.list(c("mediation_matching_applicability",if(length(record$effects))"mediation_matching_estimation")),
    limitations=record$limitations,warnings=lapply(record$warnings,function(w)list(code=w,stage="mediation_matching")))
}

# Pixel-aware wrapping also handles identifiers without spaces. Display only.
mm_plot_wrap <- function(label,width_inches,cex) {
  chars <- strsplit(enc2utf8(label),"",fixed=TRUE)[[1L]]
  lines <- character()
  while(length(chars)) {
    count <- 1L
    while(count<length(chars) && graphics::strwidth(paste0(chars[seq_len(count+1L)],collapse=""),
      units="inches",cex=cex)<=width_inches) count <- count+1L
    if(count<length(chars)) {
      spaces <- which(chars[seq_len(count)]==" ")
      if(length(spaces)&&max(spaces)>1L)count <- max(spaces)
    }
    lines <- c(lines,trimws(paste0(chars[seq_len(count)],collapse="")))
    chars <- chars[-seq_len(count)]
  }
  paste(lines,collapse="\n")
}

mm_plot_text <- function(x,y,label,cex,adj=c(.5,.5),xpd=FALSE) {
  graphics::text(x,y,label,cex=cex,adj=adj,xpd=xpd)
  xi <- graphics::grconvertX(x,from="user",to="inches")
  yi <- graphics::grconvertY(y,from="user",to="inches")
  w <- graphics::strwidth(label,units="inches",cex=cex)
  h <- graphics::strheight(label,units="inches",cex=cex)
  # Internal rendering evidence, never a numerical/public result field.
  invisible(list(text=label,left=xi-adj[1]*w,right=xi+(1-adj[1])*w,
    bottom=yi-adj[2]*h,top=yi+(1-adj[2])*h))
}

mm_effect_plot <- function(rec,path,disclosure_label="SYNTHETIC TEST ONLY") {
  ef <- rec$effects
  display <- c(paired_risk_difference="Risk difference",conditional_matched_odds_ratio="Matched OR",matched_cox_hazard_ratio="Treatment HR")
  panels <- if(rec$method_id==mm_methods[2])lapply(seq_along(ef),function(i)ef[i]) else list(ef)
  labels_for <- function(es) {
    labels <- vapply(es,`[[`,"","effect_id")
    labels[labels%in%names(display)] <- display[labels[labels%in%names(display)]]
    labels
  }
  xlabel_for <- function(es) if(es[[1]]$scale%in%c("odds_ratio","hazard_ratio"))paste(es[[1]]$scale,"(log axis)") else
    paste("Difference (",rec$semantics$outcome_unit,")")
  grDevices::png(path,width=1300,height=780,res=130,pointsize=13)
  on.exit(grDevices::dev.off())
  if(!length(ef)) { graphics::plot.new();graphics::text(.5,.6,paste0(disclosure_label," - analysis unavailable"));graphics::text(.5,.4,rec$reason_code);return() }
  configure <- function(bottom_margin) {
    if(rec$method_id==mm_methods[2]) {
      graphics::par(mfrow=c(1,2),mar=c(bottom_margin,6,4,2),oma=c(4,0,1,0))
    } else graphics::par(mar=c(bottom_margin,9,4,2),oma=c(4,0,1,0))
  }
  configure(5)
  # Measure with the real Windows graphics device and font. Width is fixed, so
  # wrapped text measurements remain valid when only the canvas height changes.
  panel_labels <- lapply(panels,function(es)vapply(labels_for(es),mm_plot_wrap,"",
    width_inches=max(.35,graphics::par("mai")[2]-.25),cex=.85))
  panel_rows <- lapply(panel_labels,function(labels)pmax(.85,graphics::strheight(labels,units="inches",cex=.85)+.28))
  panel_xlines <- lapply(panels,function(es)strsplit(mm_plot_wrap(xlabel_for(es),
    graphics::par("pin")[1]*.92,.9),"\n",fixed=TRUE)[[1L]])
  bottom_inches <- .52+.18*(max(lengths(panel_xlines))-1)+.22
  bottom_margin <- max(5,bottom_inches/(graphics::par("csi")*graphics::par("mex")))
  configure(bottom_margin)
  height <- max(780,ceiling(130*(max(vapply(panel_rows,sum,0.0))+
    sum(graphics::par("mai")[c(1,3)])+sum(graphics::par("omi")[c(1,3)]))))
  if(height!=780) {
    grDevices::dev.off()
    grDevices::png(path,width=1300,height=height,res=130,pointsize=13)
    configure(bottom_margin)
  }
  layout <- list()
  for(panel_index in seq_along(panels)) {
    es <- panels[[panel_index]]
    est <- vapply(es,`[[`,0.0,"estimate"); lo <- vapply(es,`[[`,0.0,"ci_lower"); hi <- vapply(es,`[[`,0.0,"ci_upper")
    ratio <- es[[1]]$scale%in%c("odds_ratio","hazard_ratio")
    vals <- c(est,lo,hi,if(ratio)1 else 0); vals <- vals[is.finite(vals)&(!ratio|vals>0)]
    if(!length(vals))vals <- c(.1,10)
    if(ratio) { lim <- exp(range(log(vals))+c(-.35,.35)); lim[1] <- max(lim[1],1e-8) }
    else { lim <- range(vals); delta <- max(diff(lim)*.15,.1);lim <- lim+c(-delta,delta) }
    labels <- panel_labels[[panel_index]]
    row_height <- panel_rows[[panel_index]]
    yy <- sum(row_height)-cumsum(row_height)+row_height/2
    graphics::plot(NA,xlim=lim,ylim=c(0,sum(row_height)),log=if(ratio)"x" else "",yaxt="n",ylab="",xlab="",
      main=if(rec$method_id==mm_methods[1])"Model-based natural contrasts" else "Matched outcome inference")
    graphics::axis(2,at=yy,labels=FALSE); graphics::abline(v=if(ratio)1 else 0,lty=2,col="#777777")
    # NPC midpoint is visually central for both linear and logarithmic axes.
    center <- graphics::grconvertX(.5,from="npc",to="user")
    left <- graphics::grconvertX(0,from="npc",to="inches")
    label_x <- graphics::grconvertX(left-.12,from="inches",to="user")
    page <- grDevices::dev.size("in")
    panel <- list(plot_bounds=c(graphics::grconvertX(c(0,1),from="npc",to="inches"),
      graphics::grconvertY(c(0,1),from="npc",to="inches")),
      figure_bounds=graphics::par("fig")*rep(page,each=2),labels=list(),annotations=list(),x_labels=list())
    xlines <- panel_xlines[[panel_index]]
    for(j in seq_along(xlines)) {
      y_in <- graphics::grconvertY(0,from="npc",to="inches")-.52-(j-1)*.18
      panel$x_labels[[j]] <- mm_plot_text(center,graphics::grconvertY(y_in,from="inches",to="user"),xlines[j],.9,xpd=TRUE)
    }
    for(i in seq_along(es)) {
      panel$labels[[i]] <- mm_plot_text(label_x,yy[i],labels[i],.85,adj=c(1,.5),xpd=TRUE)
      if(is.finite(lo[i])&&is.finite(hi[i])&&(!ratio||lo[i]>0)) graphics::segments(lo[i],yy[i],hi[i],yy[i],col="#087F8C",lwd=3)
      if(is.finite(est[i])&&(!ratio||est[i]>0))graphics::points(est[i],yy[i],pch=19,col="#087F8C",cex=1.2)
      if(!is.finite(lo[i])||!is.finite(hi[i])||(!is.na(lo[i])&&ratio&&lo[i]==0)) {
        note <- mm_plot_wrap("Interval unavailable / boundary: see table",graphics::par("pin")[1]*.88,.7)
        panel$annotations[[length(panel$annotations)+1L]] <- mm_plot_text(center,yy[i]-.2*row_height[i],note,.7)
      }
    }
    layout[[length(layout)+1L]] <- panel
  }
  graphics::mtext(paste0(disclosure_label," | identification assumptions unverified | local review pending"),side=1,outer=TRUE,line=1,cex=.8)
  graphics::mtext(if(rec$method_id==mm_methods[1])"95% subject-bootstrap percentile intervals; no causal certification" else
    "Inference conditional on formed pairs; propensity and matching-selection uncertainty excluded",side=1,outer=TRUE,line=2.3,cex=.78)
  invisible(layout)
}

mm_risk_plot <- function(rec,path,disclosure_label="SYNTHETIC TEST ONLY") {
  rows <- rec$diagnostics$outcome$risk_table
  grDevices::png(path,width=1200,height=700,res=120,pointsize=13);on.exit(grDevices::dev.off())
  graphics::par(mar=c(5,5,4,2),oma=c(3,0,0,0))
  times <- sort(unique(vapply(rows,`[[`,0.0,"time")))
  mx <- max(vapply(rows,`[[`,0.0,"at_risk"),1)
  graphics::plot(NA,xlim=range(times),ylim=c(0,mx*1.1),xlab=paste("Follow-up (",rec$semantics$time_unit,")"),ylab="Matched subjects at risk",
    main="Prespecified risk table - before events at each time")
  for(a in c("control","treated")) {
    r <- Filter(function(x)x$arm==a,rows); col <- if(a=="treated")"#087F8C" else "#B2473E"
    graphics::lines(vapply(r,`[[`,0.0,"time"),vapply(r,`[[`,0.0,"at_risk"),type="b",pch=if(a=="treated")19 else 17,col=col,lwd=2)
  }
  graphics::legend("topright",legend=c("Treated","Control"),pch=c(19,17),col=c("#087F8C","#B2473E"),bty="n")
  graphics::mtext(paste0(disclosure_label,". Counts at declared times; connecting lines do not estimate survival."),side=1,outer=TRUE,line=1,cex=.8)
}

mm_write_bundle <- function(value,output_dir,binding,result_id=NULL) {
  targets <- file.path(output_dir,c("result.json","REPORT.md","integration-fragment.json","private/analysis.rds",
    "tables/effects.csv","tables/flow.csv","tables/balance.csv","tables/overlap.csv","tables/risk.csv","figures/effects.png","figures/risk.png"))
  mm_need(!any(file.exists(targets)),"MM_OUTPUT_ALREADY_EXISTS")
  rec <- value$record; rec$binding <- binding
  rec$result_id <- if(is.null(result_id))paste0("mm-",substr(binding$input_sha256,1,12),"-",substr(binding$spec_sha256,1,12)) else result_id
  for(i in seq_along(rec$effects)) rec$effects[[i]]$result_id <- paste0(rec$result_id,"-",rec$effects[[i]]$effect_id)
  for(p in c("tables","figures","private")) dir.create(file.path(output_dir,p),showWarnings=FALSE,recursive=TRUE)
  saveRDS(value$private,file.path(output_dir,"private","analysis.rds"))
  if(!is.null(value$private$pairs))mm_csv(value$private$pairs,file.path(output_dir,"private","pairs.csv"))
  if(!is.null(value$private$subjects))mm_csv(value$private$subjects,file.path(output_dir,"private","subjects.csv"))
  if(!is.null(value$private$bootstrap_effects))mm_csv(as.data.frame(value$private$bootstrap_effects),file.path(output_dir,"private","bootstrap_effects.csv"))
  if(!is.null(value$private$bootstrap_indices))mm_csv(as.data.frame(value$private$bootstrap_indices),file.path(output_dir,"private","bootstrap_indices.csv"))
  if(!is.null(value$private$canonical_complete_data))mm_csv(value$private$canonical_complete_data,file.path(output_dir,"private","mediation_complete.csv"))
  if(!is.null(value$private$survival))mm_csv(value$private$survival,file.path(output_dir,"private","survival_matched.csv"))
  meta <- list(method_id=rec$method_id,test_only=TRUE,scientific_review="pending",export_status="local_only",source_result_id=rec$result_id)
  datasets <- list(effects=lapply(rec$effects,function(e)c(meta,e)),flow=list(c(meta,rec$counts)))
  if(length(rec$diagnostics$balance))datasets$balance <- lapply(rec$diagnostics$balance,function(e)c(meta,e))
  if(length(rec$diagnostics$overlap))datasets$overlap <- lapply(rec$diagnostics$overlap,function(e)c(meta,e))
  if(length(rec$diagnostics$outcome$risk_table))datasets$risk <- lapply(rec$diagnostics$outcome$risk_table,function(e)c(meta,e))
  rec$artifacts <- list()
  add <- function(name,kind,path,caption) {
    rec$artifacts[[length(rec$artifacts)+1L]] <<- list(artifact_id=paste0(rec$result_id,"-",name),kind=kind,
      source_result_ids=as.list(c(rec$result_id,vapply(rec$effects,`[[`,"","result_id"))),sha256=mm_hash_file(path),
      relative_path=paste0(if(kind=="table")"tables/" else "figures/",basename(path)),caption=caption,
      test_only=TRUE,scientific_review="pending",export_status="local_only")
  }
  for(n in names(datasets)) {
    p <- file.path(output_dir,"tables",paste0(n,".csv"));mm_csv(datasets[[n]],p)
    add(n,"table",p,"Synthetic aggregate evidence. Finite values or explicit missingness; consult reasons and effect-specific scales.")
  }
  p <- file.path(output_dir,"figures","effects.png")
  tryCatch({mm_effect_plot(rec,p);add("effects","figure",p,"Synthetic effect estimates and available 95% intervals; unavailable and unbounded intervals are labelled.")},error=function(e) {
    rec$status <<- "partial";rec$reason_code <<- "MM_FIGURE_FAILED";rec$warnings <<- c(rec$warnings,list("MM_EFFECT_FIGURE_FAILED"))
  })
  if(length(rec$diagnostics$outcome$risk_table)) {
    p <- file.path(output_dir,"figures","risk.png")
    tryCatch({mm_risk_plot(rec,p);add("risk","figure",p,"At-risk counts at prespecified times. Pooled risk sets; counts are not survival probabilities.")},error=function(e) {
      rec$status <<- "partial";rec$reason_code <<- "MM_FIGURE_FAILED";rec$warnings <<- c(rec$warnings,list("MM_RISK_FIGURE_FAILED"))
    })
  }
  report <- c("# 中介与匹配结局模块报告（合成工程验证）","",paste0("方法：`",rec$method_id,"`；状态：`",rec$status,"`。"),
    "", "本结果只说明限定方法在合成数据上的工程运行情况，科学审阅仍待完成。患者标识、逐行数据及模型对象仅保存在本地 private 目录。",
    "",if(rec$method_id==mm_methods[1])"中介效应来自四组嵌套条件均值的标准化。自然效应解释要求无未测混杂、无处理诱发的中介-结局混杂、时间先后、正值性和模型正确；这些假设未验证。Bootstrap 联合重拟合两模型，失败次数见 JSON。未实施敏感性分析，不输出中介比例。" else
      "匹配后推断以已形成的匹配对为条件，未计入倾向评分估计、共同支持限制和匹配选择不确定性。匹配平衡不能证明无混杂。",
    "",if(rec$method_id==mm_methods[2])"风险差使用配对差值方差和近似 t 区间，未截断到 [-1,1]；不一致对精确二项检验与配对条件 OR 区间单独列出，二者不是同一效应尺度。" else
      if(rec$method_id==mm_methods[3])"Cox 使用全部匹配样本的合并风险集、Efron 并列事件处理及按匹配对聚类的 sandwich 方差。标准误在 log-HR 尺度。HR 不是风险差、存活概率或一般性的 ATT；独立右删失和比例风险假设未验证。风险集在事件时间之前纳入随访时间大于等于该时刻者。" else "所有结果以完整案例经验人群为目标，不自动代表原始总体。",
    "",paste0("缺失/失败原因：",if(is.null(rec$reason_code))"无执行阻断；方法局限仍适用" else rec$reason_code),
    "", "结果表：tables/；图：figures/；精确数值、失败原因、来源绑定：result.json；私有中间结果：private/。",
    "", "未完成：共享入口/schema/注册接入、集中全量验收、真实临床科学与隐私审阅、发布。")
  writeLines(enc2utf8(report),file.path(output_dir,"REPORT.md"),useBytes=TRUE)
  mm_json(rec,file.path(output_dir,"result.json"))
  mm_json(mm_project_common(rec),file.path(output_dir,"integration-fragment.json"))
  rec
}
