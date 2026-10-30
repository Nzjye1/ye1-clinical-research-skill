"""Project-admitted source transport for the unchanged Cox module owners.

This context is created by the root transport. It is not a JSON permission,
host isolation guarantee, clinical approval, or a way to upgrade old models.
"""
from __future__ import annotations
import hashlib,importlib.util,json,math,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
MODULE=HERE.parent
CORE=MODULE.parents[1]/'integration/core'
METHODS=('evaluation.survival.cox.penalized.ipcw','interpretation.survival.cox.penalized.interventional')

class AdmissionError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
def need(value,code):
    if not value:raise AdmissionError(code)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def owner():
    sys.path.insert(0,str(MODULE))
    name='cox_admitted_original_module_api'
    if name not in sys.modules:
        spec=importlib.util.spec_from_file_location(name,MODULE/'module_api.py');v=importlib.util.module_from_spec(spec);sys.modules[name]=v;spec.loader.exec_module(v)
    return sys.modules[name]
def schema(name):return json.loads((HERE/'schemas'/name).read_text(encoding='utf-8-sig'))
def validate(value,name,code):
    sys.path.insert(0,str(CORE/'python'))
    from clinical_methods.contracts import validate_schema
    try:validate_schema(value,schema(name))
    except (ValueError,TypeError,KeyError):raise AdmissionError(code) from None
def context_for(request,context):
    callback=getattr(context,'require_request',None)
    need(callable(callback),'CE_REAL_CONTEXT_REQUIRED')
    need(isinstance(request,dict),'CE_REAL_REQUEST_INVALID')
    need(callback(request.get('method_id'),request.get('operation'),request.get('payload')) is not False,'CE_REAL_CONTEXT_REJECTED')
    origin={k:getattr(context,k,None) for k in ('data_origin','task_purpose','test_only','scientific_review')}
    need(origin['data_origin'] in ('real','synthetic') and origin['task_purpose'] in ('engineering_test','research_analysis')
         and type(origin['test_only']) is bool and origin['test_only']==(origin['task_purpose']=='engineering_test')
         and origin['scientific_review']=='pending','CE_REAL_CONTEXT_METADATA_INVALID')
    need(origin['data_origin']!='synthetic' or origin['task_purpose']=='engineering_test','CE_SYNTHETIC_ENGINEERING_REQUIRED')
    project=getattr(context,'project_root',None)
    need(isinstance(project,(str,Path)) and Path(project).is_dir(),'CE_REAL_PROJECT_REQUIRED')
    return origin,Path(project).resolve()
def validate_request(request,context):
    origin,project=context_for(request,context)
    validate(request,'request.schema.json','CE_REAL_REQUEST_INVALID')
    validate(request['payload'],'payload.schema.json','CE_REAL_PAYLOAD_INVALID')
    need(request['method_id'] in METHODS,'CE_REAL_METHOD_NOT_REGISTERED')
    need((request['method_id']==METHODS[0] and request['operation']=='evaluate') or
         (request['method_id']==METHODS[1] and request['operation'] in ('fit_explainer','explain')),'CE_REAL_METHOD_OPERATION_INVALID')
    return origin,project
def analyze(request,context):
    api=owner();d=api.diagnostics('root_admission')
    try:
        origin,project=validate_request(request,context)
        # No label mutation or old numerical envelope is used to obtain access.
        budget_accessor=getattr(context,'resource_limits',None)
        limits=budget_accessor() if callable(budget_accessor) else None
        result=api.analyze(request,origin_context=origin,project_root=project,resource_budget=limits)
        validate(result,'response.schema.json','CE_REAL_RESPONSE_INVALID')
        validate(result['diagnostics'],'diagnostics.schema.json','CE_REAL_DIAGNOSTICS_INVALID')
        if result['ok']:validate(result['public_record'],'public_record.schema.json','CE_REAL_PUBLIC_INVALID')
        validate(result['private_record'],'private_record.schema.json','CE_REAL_PRIVATE_INVALID')
        context.require_request(request['method_id'],request['operation'],request['payload'])
        return result
    except Exception as error:
        code=getattr(error,'code',str(error))
        import re
        if not isinstance(code,str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,159}',code):code='CE_REAL_EXECUTION_REJECTED'
        return {'api_version':'clinical-module-response@1.0','ok':False,'reason_code':code,'diagnostics':d,'public_record':None,'private_record':None}
def project(response,output_dir,context,request=None):
    need(request is not None,'CE_REAL_PROJECTION_REQUEST_REQUIRED')
    origin,root=validate_request(request,context);validate(response,'response.schema.json','CE_REAL_RESPONSE_INVALID')
    validate(response['public_record'],'public_record.schema.json','CE_REAL_PUBLIC_INVALID')
    need(response['ok'] is True and response['diagnostics']['common_bindings']==request['bindings'],'CE_REAL_PROJECTION_BINDING_MISMATCH')
    need(all(response['public_record'][k]==v for k,v in origin.items()),'CE_REAL_PROJECTION_ORIGIN_MISMATCH')
    out=Path(output_dir).resolve()
    need(out!=root and out.is_relative_to(root) and not out.exists() and out.parent.is_dir(),'CE_REAL_FRESH_PROJECTION_REQUIRED')
    need('private' in out.relative_to(root).parts[:-1],'CE_REAL_PRIVATE_PROJECTION_REQUIRED')
    projection_context={'result_id':'ce-'+canonical(response['public_record'])[:24],'binding':request['bindings']}
    result=owner().project(response,out,projection_context,origin_context=origin,project_root=root)
    need(result['ok'] is True,'CE_REAL_PROJECTION_FAILED')
    for artifact in result['artifacts']:
        path=(out/artifact['path']).resolve()
        need(path.is_relative_to(out) and 'private' not in path.relative_to(out).parts and path.is_file(),'CE_REAL_PROJECTED_PATH_INVALID')
    return result
