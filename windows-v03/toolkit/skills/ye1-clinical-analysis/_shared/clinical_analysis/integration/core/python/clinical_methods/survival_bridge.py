"""Private transport to the sole right-censored survival provider.

Only KM and Cox association (with opt-in formal PH) are registered here. The R task core owns source
semantics, authorization, result schemas and export. No alternative estimator.
"""
from __future__ import annotations
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys
sys.dont_write_bytecode=True
MAX_INPUT_BYTES=2*1024*1024
MAX_ROWS=200
MAX_FORMAL_PH_ROWS=500
if __package__:
    from . import bridge as transport
else:
    import bridge as transport
REGISTERED_METHODS={'kaplan_meier','cox_ph'}
SPEC_FIELDS={'method','independent_subjects','missing_policy','subject_id','time','status',
    'time_unit','time_zero_definition','event_definition','censoring_definition','event_code',
    'censor_code','evaluation_times','covariates','ties','min_events_per_parameter',
    'competing_codes','competing_event_definitions','left_truncation','time_varying_covariates',
    'recurrent_events','interval_censoring','weights','strata','cluster','ph_test'}


def canonical_bytes(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')


def provider_version():
    root=Path(__file__).parent
    return hashlib.sha256(canonical_bytes({name:hashlib.sha256((root/name).read_bytes()).hexdigest()
        for name in ('survival.py','survival_bridge.py')})).hexdigest()


def _finite_tree(value):
    if isinstance(value,float):return math.isfinite(value)
    if isinstance(value,dict):return all(isinstance(k,str) and _finite_tree(v) for k,v in value.items())
    if isinstance(value,(list,tuple)):return all(_finite_tree(v) for v in value)
    return value is None or isinstance(value,(str,int,bool))


def _load():
    import numpy,scipy,statsmodels
    if __package__:
        from . import survival
    else:
        import survival
    return survival,{'python':platform.python_version(),'numpy':numpy.__version__,
        'scipy':scipy.__version__,'statsmodels':statsmodels.__version__}


def preflight():
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            _,runtime=_load()
        return {'ok':True,'runtime':runtime,'provider_version':provider_version()}
    except ImportError:return {'ok':False,'reason_code':'PROVIDER_DEPENDENCY_UNAVAILABLE'}
    except Exception:return {'ok':False,'reason_code':'PROVIDER_EXECUTION_FAILED'}


def _registered_record(survival,rows,spec):
    if not set(spec)<=SPEC_FIELDS:
        return {'status':'BLOCKED_METHOD','reason':'SURVIVAL_SPEC_FIELD_UNSUPPORTED',
            'n_total':len(rows),'computed':False,'patient_rows_returned':False}
    if spec.get('method') not in REGISTERED_METHODS:
        return {'status':'BLOCKED_METHOD','reason':'SURVIVAL_METHOD_NOT_REGISTERED',
            'n_total':len(rows),'computed':False,'patient_rows_returned':False}
    record=survival.analyze(rows,spec)
    record['original_status']=record['status']
    record['patient_rows_returned']=False
    record.setdefault('n_total',len(rows))
    record['support']=None
    if record['status']!='BLOCKED_METHOD':
        # The numerical owner's validator determines the exact same complete
        # cases. Only support metadata are added; curves and fit are not refitted.
        _,_,time,status,grid,_,_=survival._validate(rows,spec)
        event_times=[t for t,event in zip(time,status) if event==1]
        record['support']={
            'complete_case_followup_min':min(time),'complete_case_followup_max':max(time),
            'last_target_event_time':max(event_times) if event_times else None,
            'evaluation_times':grid,'time_unit':spec['time_unit'],
            'grid_kind':'prespecified_grid_not_complete_event_step_curve',
            'extrapolation':'forbidden_beyond_observed_complete_case_followup',
            'risk_set_definition':'at t-: subjects with observed followup >= t, including event and censoring at t',
            'survival_definition':'right-continuous survival at t after events at t',
            'ties_definition':'events_before_censoring_at_same_time',
            'ci_definition':'pointwise 95% Greenwood log-log; boundary endpoints descriptive, not certainty',
        }
        if record['target_events']==0:
            record['status']='BLOCKED_METHOD'
            record['reason']='NO_TARGET_EVENTS'
            record['computed']=False
            record['curves']=[]
            record['method_not_silently_replaced']=True
            if 'cox' in record:
                record['cox']['original_status']=record['cox']['status']
                record['cox']['original_reason']=record['cox'].get('reason')
                record['cox']['status']='NON_ESTIMABLE'
                record['cox']['reason']='NO_TARGET_EVENTS'
                record['cox']['terms']=[]
            if 'ph_test' in record:
                for test in record['ph_test']['table']:
                    test.update(chisq=None,p_value=None,status='unavailable',reason='NO_TARGET_EVENTS')
                record['ph_test']['status']='unavailable'
    return record


def invoke(request):
    if not (isinstance(request,dict) and set(request) in ({'rows','spec'},{'rows','spec','limits'})
            and isinstance(request['rows'],list) and 0<len(request['rows'])
            and all(isinstance(row,dict) for row in request['rows'])
            and isinstance(request['spec'],dict) and _finite_tree(request)):
        return {'ok':False,'reason_code':'PROVIDER_REQUEST_INVALID'}
    formal='ph_test' in request['spec']
    method='survival.cox.association' if request['spec'].get('method')=='cox_ph' else 'survival.kaplan_meier'
    reason=transport.resource_check(request,method+('.formal_ph' if formal else ''),
        MAX_FORMAL_PH_ROWS if formal else MAX_ROWS,'survival')
    if reason:return {'ok':False,'reason_code':reason}
    try:
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            survival,runtime=_load()
            record=_registered_record(survival,request['rows'],request['spec'])
        if not _finite_tree(record):return {'ok':False,'reason_code':'PROVIDER_NONFINITE_RESULT'}
        return {'ok':True,'record':record,'runtime':runtime,'provider_version':provider_version(),
            'request_sha256':hashlib.sha256(canonical_bytes(request)).hexdigest()}
    except ImportError:return {'ok':False,'reason_code':'PROVIDER_DEPENDENCY_UNAVAILABLE'}
    except Exception:return {'ok':False,'reason_code':'PROVIDER_EXECUTION_FAILED'}


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    try:byte_limit=transport.cli_byte_limit(args)
    except (ValueError,TypeError,OverflowError):
        print('PROVIDER_ARGUMENTS_INVALID');return 2
    if args[0]=='--preflight':response=preflight()
    else:
        try:
            path=Path(args[0])
            if path.stat().st_size>byte_limit:response={'ok':False,'reason_code':'PROVIDER_INPUT_LIMIT'}
            else:
                def reject_constant(_):raise ValueError('invalid numeric literal')
                response=invoke(json.loads(path.read_text(encoding='utf-8-sig'),parse_constant=reject_constant))
        except Exception:response={'ok':False,'reason_code':'PROVIDER_INPUT_UNREADABLE'}
    try:
        with Path(args[1]).open('x',encoding='utf-8',newline='\n') as stream:
            stream.write(canonical_bytes(response).decode('utf-8')+'\n')
    except Exception:
        print('PROVIDER_OUTPUT_UNAVAILABLE');return 3
    print('PROVIDER_RESPONSE_READY');return 0


if __name__=='__main__':raise SystemExit(main())
