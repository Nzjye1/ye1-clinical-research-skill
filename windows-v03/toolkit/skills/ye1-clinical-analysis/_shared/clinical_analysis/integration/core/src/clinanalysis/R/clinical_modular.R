# Module branch of the existing single-task executor. No numerical algorithms.
run_clinical_module <- function(task,data=NULL,output_dir=NULL,original_task_path=NULL) {
  root<-.clinical_common$root
  admitted<-identical(task$schema_version,"clinical-module-task@1.1")
  boundary<-if(admitted)task$project_root else root
  if(admitted&&(!is.character(boundary)||length(boundary)!=1L||!dir.exists(boundary)))stop("PROJECT_DIRECTORY_REQUIRED",call.=FALSE)
  output_dir<-output_dir %||% task$execution$output_dir
  if(is.null(output_dir)||!common_inside(output_dir,boundary))stop("OUTPUT_OUTSIDE_ISOLATED_ROOT",call.=FALSE)
  if(file.exists(output_dir)||dir.exists(output_dir))stop("OUTPUT_DIRECTORY_EXISTS",call.=FALSE)
  if(!dir.exists(dirname(output_dir)))stop("OUTPUT_PARENT_REQUIRED",call.=FALSE)
  if(!is.null(data))stop("INLINE_DATA_NOT_SUPPORTED",call.=FALSE)
  if(is.null(original_task_path)||is.null(attr(task,"common_task_bytes")))stop("BOUND_TASK_BYTES_REQUIRED",call.=FALSE)
  error<-common_verify_runtime();if(!is.null(error))stop(error,call.=FALSE)
  if(!identical(common_path(output_dir),common_path(task$execution$output_dir)))stop("OUTPUT_BINDING_MISMATCH",call.=FALSE)
  if(!dir.create(output_dir,showWarnings=FALSE))stop("OUTPUT_DIRECTORY_CLAIM_FAILED",call.=FALSE)
  dir.create(file.path(output_dir,"private"))
  snapshot<-file.path(output_dir,"private/task-snapshot.json")
  writeBin(attr(task,"common_task_bytes"),snapshot)
  worker<-file.path(dirname(root),"module_worker.py")
  if(!common_python(worker,c(snapshot,output_dir),file.path(output_dir,"private/integration.log")))stop("MODULE_WORKER_FAILED",call.=FALSE)
  resultpath<-file.path(output_dir,"result.json")
  if(!file.exists(resultpath))stop("MODULE_RESULT_REQUIRED",call.=FALSE)
  result<-common_json_read(resultpath)
  if(!result$schema_version%in%c("clinical-modular-result@1.0","clinical-module-rejection@1.0","clinical-modular-result@1.1","clinical-module-rejection@1.1"))stop("MODULE_RESULT_VERSION_INVALID",call.=FALSE)
  invisible(result)
}
