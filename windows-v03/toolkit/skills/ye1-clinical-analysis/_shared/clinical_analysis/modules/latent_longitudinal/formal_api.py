"""Shared request/response adapter for the two formal providers only."""
import copy,json,re,subprocess
from pathlib import Path
from .contracts import Blocked,need,exact,digest
from .schema_tools import validate
from . import formal_provider,formal_runtime
ROOT=Path(__file__).resolve().parent
METHODS={'latent.profile.gaussian','latent.trajectory.gaussian'}
def schema_validate(value,name):
    path=ROOT/'formal_schemas'/(name+'.schema.json');need(path.is_file(),'MODULE_SCHEMA_MISSING')
    validate(value,json.loads(path.read_text(encoding='utf-8')))
def check_request(request):
    exact(request,['api_version','method_id','operation','payload','bindings'])
    need(request['api_version']=='clinical-module-request@1.0','MODULE_API_VERSION_UNSUPPORTED')
    method=request['method_id'];op=request['operation'];p=request['payload']
    need(method in METHODS,'MODULE_METHOD_NOT_REGISTERED');profile=method=='latent.profile.gaussian'
    need(op in ({'train','assign'} if profile else {'train','predict'}),'OPERATION_UNSUPPORTED')
    schema_validate(p,'profile.payload' if profile else 'trajectory.payload')
    b=request['bindings'];exact(b,['input_sha256','plan_sha256','code_sha256','runtime_sha256','model_sha256'])
    for k,v in b.items():need((k=='model_sha256' and v is None) or isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v),'MODULE_BINDING_INVALID')
    need((p['model_ref'] is None)==(op=='train'),'MODULE_FROZEN_MODEL_BINDING_REQUIRED')
    need(b['model_sha256']==(p['model_ref']['sha256'] if p['model_ref'] else None),'MODULE_MODEL_BINDING_MISMATCH')
    s=p['spec'];d=s['definition'];sem=p['semantics'];split=s['split']
    need(bool(s['cohort_id'].strip()),'IDENTITY_DEFINITION_INVALID')
    defined_fields=d['indicators'] if profile else [d['time'],d['outcome']]
    need(all(bool(f['unit'].strip()) for f in defined_fields),'FEATURE_DEFINITION_INVALID')
    need(1 in s['candidate_k'],'FORMAL_ONE_CLASS_BASELINE_REQUIRED')
    need(bool(split['train']) and bool(split['holdout']) and split['train']!=split['holdout'],'SPLIT_INVALID')
    need(sem['subject_key']==s['subject_id'] and sem['missing_policy']==d['missing'],'SEMANTIC_IDENTITY_OR_MISSINGNESS_MISMATCH')
    expected={s['subject_id']:('id','subject_id','1')}
    names=[s['subject_id'],split['field']]
    if op=='train':expected[split['field']]=('category','partition','1')
    if profile:
        names += [f['name'] for f in d['indicators']]
        expected.update({f['name']:('number','indicator',f['unit']) for f in d['indicators']})
        need(sem['grain']=='subject' and sem['record_keys']==[s['subject_id']],'CROSS_SECTIONAL_GRAIN_MISMATCH')
        time={'unit':None,'origin':None,'scale':None,'measurement_time_field':None,'availability':'declared_per_field'}
    else:
        names += [d['time']['name'],d['outcome']['name']]
        need((d['family']=='lcga' and d['random']=='none') or (d['family']=='growth_mixture' and d['random'] in ['intercept','intercept_slope']),'FORMAL_TRAJECTORY_DEFINITION_UNSUPPORTED')
        expected.update({d['time']['name']:('number','time',d['time']['unit']),d['outcome']['name']:('number','outcome',d['outcome']['unit'])})
        need(sem['grain']=='subject_time' and sem['record_keys']==[s['subject_id'],d['time']['name']],'LONGITUDINAL_GRAIN_MISMATCH')
        time={k:d['time'][k] for k in ['unit','origin','scale']}|{'measurement_time_field':d['time']['name'],'availability':'row_time'}
    need(len(set(names))==len(names),'ROLE_COLLISION');need(sem['time']==time,'TIME_SEMANTICS_MISMATCH')
    observed=sem['fields'];need(len(observed)==len(expected) and len({f['name'] for f in observed})==len(observed),'FIELD_ROLE_DECLARATION_MISMATCH')
    for f in observed:
        need(expected.get(f['name'])==(f['dtype'],f['role'],f['unit']),'FIELD_ROLE_DECLARATION_MISMATCH')
        if f['role'] in ['subject_id','partition']:need(f['measured_at'] is None and f['available_at'] is None,'IDENTITY_TIME_NOT_APPLICABLE')
        elif profile:need(type(f['measured_at']) in [int,float] and type(f['available_at']) in [int,float] and f['available_at']>=f['measured_at'],'CROSS_SECTIONAL_FIELD_TIMING_INVALID')
        else:need(f['measured_at']=='row_time' and f['available_at']=='row_time','LONGITUDINAL_FIELD_TIMING_MISMATCH')
    need(all(set(r)==set(expected) for r in p['data']),'UNDECLARED_OR_MISSING_DATA_COLUMN')

def analyze(request):
    response={'api_version':'clinical-module-response@1.0','ok':False,'reason_code':None,
      'diagnostics':{'stage':'validation','details':{}},'public_record':None,'private_record':None}
    stage='validation'
    try:
        check_request(request);p=request['payload'];method=request['method_id'];op=request['operation'];stage='analysis'
        probe=formal_runtime.probe();need(all(probe['r_packages'].get(n) for n in formal_runtime.PACKAGES),'FORMAL_DEPENDENCY_UNAVAILABLE')
        analysis,warnings,private,details=formal_provider.analyze(method,op,p,probe)
        response.update(ok=True,public_record={'method_id':method,'operation':op,'test_only':True,
          'scientific_review':'pending','export_status':'local_only','definition':copy.deepcopy(p['spec']),
          'analysis':analysis,'warnings':warnings},private_record=private,
          diagnostics={'stage':'complete','provider_hash':digest(formal_runtime.source_hashes()),
                       'runtime_hash':digest(formal_runtime.binding(probe)),'details':details})
        schema_validate(response['public_record'],'public_record');schema_validate(private,'private_record')
    except Blocked as error:
        response.update(ok=False,reason_code=error.code,public_record=None,private_record=None,
                        diagnostics={'stage':stage,'details':error.diagnostics})
    except (KeyError,TypeError,ValueError,OSError,subprocess.TimeoutExpired):
        response.update(ok=False,reason_code='FORMAL_API_EXECUTION_ERROR',public_record=None,private_record=None,
                        diagnostics={'stage':'execution','details':{}})
    schema_validate(response['diagnostics'],'diagnostics')
    return response

def project(response,output_dir):
    need(response.get('ok') is True,'CANNOT_PROJECT_BLOCKED_MODULE')
    schema_validate(response['public_record'],'public_record')
    from .formal_artifacts import write_artifacts
    return write_artifacts(response['public_record'],output_dir)
