"""Private transport and strict JSON serialization for the sole Cox owner.

The R adapter supplies a validated snapshot, never a filename to reread. Patient
identities, individual predictions and the frozen model stay in private files.
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import sys

sys.dont_write_bytecode = True
MAX_INPUT_BYTES = 2 * 1024 * 1024
if __package__:
    from . import bridge as transport
else:
    import bridge as transport
MAX_ROWS = transport.resource_budget.profile("prediction.survival.cox")["default_rows"]
SPEC_FIELDS = {'method','independent_subjects','missing_policy','subject_id','time','status',
    'time_unit','time_zero_definition','event_definition','censoring_definition','event_code',
    'censor_code','evaluation_times','covariates','ties','min_events_per_parameter',
    'competing_codes','competing_event_definitions','left_truncation','time_varying_covariates',
    'recurrent_events','interval_censoring','weights','strata','cluster'}


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def provider_version():
    root = Path(__file__).parent
    return hashlib.sha256(canonical_bytes({name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ('survival.py', 'cox_prediction_bridge.py', 'real_family_admission.py')})).hexdigest()


def _finite_tree(value):
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _finite_tree(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return all(_finite_tree(item) for item in value)
    return value is None or isinstance(value, (str, int, bool))


def _strict_json(text):
    def reject_constant(_):
        raise ValueError('invalid numeric literal')

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate object key')
            result[key] = value
        return result

    value = json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_pairs)
    if not _finite_tree(value):
        raise ValueError('nonfinite JSON')
    return value


def _load():
    import numpy, scipy, statsmodels
    if __package__:
        from . import survival
    else:
        import survival
    return survival, {'python': platform.python_version(), 'numpy': numpy.__version__,
                      'scipy': scipy.__version__, 'statsmodels': statsmodels.__version__}


def preflight():
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _, runtime = _load()
        return {'ok': True, 'runtime': runtime, 'provider_version': provider_version()}
    except ImportError:
        return {'ok': False, 'reason_code': 'PROVIDER_DEPENDENCY_UNAVAILABLE'}
    except Exception:
        return {'ok': False, 'reason_code': 'PROVIDER_EXECUTION_FAILED'}


def _study_context(value):
    fields = {'provenance_version', 'data_origin', 'task_purpose', 'test_only', 'scientific_review', 'export_status'}
    if not (isinstance(value, dict) and set(value) == fields
            and value['provenance_version'] == 'clinical-frozen-provenance@1.0'
            and value['data_origin'] in {'real', 'synthetic'}
            and value['task_purpose'] in {'engineering_test', 'research_analysis'}
            and value['test_only'] is (value['task_purpose'] == 'engineering_test')
            and value['scientific_review'] == 'pending' and value['export_status'] == 'local_only'
            and (value['data_origin'] != 'synthetic' or value['task_purpose'] == 'engineering_test')):
        raise ValueError('STUDY_CONTEXT_INVALID')
    return dict(value)


def invoke(request):
    if not isinstance(request, dict):
        return {'ok': False, 'reason_code': 'PROVIDER_REQUEST_INVALID'}
    expected = {'operation', 'rows', 'spec', 'prediction', 'feature_semantics'}
    if request.get('operation') == 'infer':
        expected.add('model_json')
    if 'study_context' in request:
        expected.add('study_context')
    if 'limits' in request:
        expected.add('limits')
    if not (set(request) == expected and request.get('operation') in {'train', 'infer'}
            and isinstance(request.get('rows'), list) and 0 < len(request['rows'])
            and all(isinstance(row, dict) for row in request['rows'])
            and isinstance(request.get('spec'), dict) and set(request['spec']) <= SPEC_FIELDS
            and isinstance(request.get('prediction'), dict)
            and request['prediction'].get('operation') == request['operation'] and _finite_tree(request)):
        return {'ok': False, 'reason_code': 'PROVIDER_REQUEST_INVALID'}
    reason = transport.resource_check(request, 'prediction.survival.cox', MAX_ROWS, 'cox_prediction')
    if reason:
        return {'ok': False, 'reason_code': reason}
    try:
        context = None
        if 'study_context' in request:
            try:
                context = _study_context(request['study_context'])
            except ValueError:
                return {'ok': False, 'reason_code': 'STUDY_CONTEXT_INVALID'}
        model = None
        if request['operation'] == 'infer':
            if not isinstance(request['model_json'], str):
                return {'ok': False, 'reason_code': 'MODEL_JSON_INVALID'}
            try:
                model = _strict_json(request['model_json'])
            except (TypeError, ValueError, OverflowError):
                return {'ok': False, 'reason_code': 'MODEL_JSON_INVALID'}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            survival, runtime = _load()
            version = provider_version()
            result = survival.cox_prediction(request['rows'], request['spec'], request['prediction'],
                request['feature_semantics'], version, runtime, model=model, study_context=context,
                resource_budget=request.get('limits'))
        if not _finite_tree(result):
            return {'ok': False, 'reason_code': 'PROVIDER_NONFINITE_RESULT'}
        result.update(runtime=runtime, provider_version=version,
                      request_sha256=hashlib.sha256(canonical_bytes(request)).hexdigest())
        return result
    except ImportError:
        return {'ok': False, 'reason_code': 'PROVIDER_DEPENDENCY_UNAVAILABLE'}
    except Exception:
        return {'ok': False, 'reason_code': 'PROVIDER_EXECUTION_FAILED'}


def _write_response(response, destination, artifacts, model_json=None):
    """Exclusive native serialization preserves the frozen model's own hash."""
    target = Path(destination)
    paths = [target]
    if artifacts and response.get('ok'):
        paths += [target.parent / 'frozen_cox_model.json', target.parent / 'individual_predictions.csv']
    if any(path.exists() for path in paths):
        raise FileExistsError('private output already exists')
    if len(paths) > 1 and model_json is not None:
        if not isinstance(model_json, str) or canonical_bytes(_strict_json(model_json)) != canonical_bytes(response['model_bundle']):
            raise ValueError('original model does not match validated bundle')
    created = []
    try:
        if len(paths) > 1:
            with paths[1].open('x', encoding='utf-8', newline='\n') as stream:
                created.append(paths[1])
                stream.write(model_json if model_json is not None else canonical_bytes(response['model_bundle']).decode('utf-8') + '\n')
            with paths[2].open('x', encoding='utf-8', newline='') as stream:
                created.append(paths[2])
                writer = csv.DictWriter(stream, fieldnames=['subject_id', 'horizon', 'survival_probability', 'event_risk'], lineterminator='\n')
                writer.writeheader()
                writer.writerows(response['individual_predictions'])
        with target.open('x', encoding='utf-8', newline='\n') as stream:
            created.append(target)
            stream.write(canonical_bytes(response).decode('utf-8') + '\n')
    except Exception:
        # Only files exclusively created by this invocation are rolled back.
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        byte_limit = transport.cli_byte_limit(args)
    except (ValueError, TypeError, OverflowError):
        print('PROVIDER_ARGUMENTS_INVALID')
        return 2
    artifacts = args[0] != '--preflight'
    model_json = None
    if not artifacts:
        response = preflight()
    else:
        try:
            path = Path(args[0])
            if path.stat().st_size > byte_limit:
                response = {'ok': False, 'reason_code': 'PROVIDER_INPUT_LIMIT'}
            else:
                request = _strict_json(path.read_text(encoding='utf-8-sig'))
                response = invoke(request)
                if response.get('ok') and 'study_context' in request and request['operation'] == 'infer':
                    model_json = request['model_json']
        except Exception:
            response = {'ok': False, 'reason_code': 'PROVIDER_INPUT_UNREADABLE'}
    try:
        _write_response(response, args[1], artifacts, model_json=model_json)
    except Exception:
        print('PROVIDER_OUTPUT_UNAVAILABLE')
        return 3
    print('PROVIDER_RESPONSE_READY')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
