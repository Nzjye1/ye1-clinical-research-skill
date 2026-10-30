"""Strict shared module API facade. No estimator or evaluation implementation here."""
from __future__ import annotations
import copy
import json
import math
import os
from pathlib import Path

import adapter
import provider as p
from contracts import core_contracts

CONTRACTS_ROOT = Path(os.environ.get('CLINICAL_MODULE_CONTRACTS', str(p.MODULE_ROOT.parents[1] / 'integration/contracts')))
OWNED_SCHEMAS = p.MODULE_ROOT / 'schemas'


def validate_json(value, path):
    p.need(path.is_file(), 'MODULE_SCHEMA_MISSING')
    schema = adapter.strict_load(path.read_bytes())
    # Reuse the frozen core validator; the common integration owner validates the
    # full envelopes separately. The only two extra envelope keywords are checked
    # explicitly here before removal, never silently ignored.
    if path.name == 'module-request.schema.json':
        for name, definition in schema['properties'].items():
            limit = definition.pop('maxLength', None)
            if limit is not None:
                p.need(isinstance(value.get(name), str) and len(value[name]) <= limit, 'MODULE_ENVELOPE_LENGTH_INVALID')
    if path.name == 'module-response.schema.json':
        schema.pop('allOf')
        for definition in schema['properties']['reason_code']['anyOf']:
            limit = definition.pop('maxLength', None)
            if limit is not None and isinstance(value.get('reason_code'), str):
                p.need(len(value['reason_code']) <= limit, 'MODULE_REASON_LENGTH_INVALID')
        p.need((value.get('ok') is True and value.get('reason_code') is None and isinstance(value.get('public_record'), dict)) or
               (value.get('ok') is False and isinstance(value.get('reason_code'), str) and value.get('public_record') is None), 'MODULE_RESPONSE_SEMANTICS_INVALID')
    core_contracts.validate_schema(value, schema)
    # JSON encoding must never emit nonfinite numbers, including nested rows/models.
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        raise p.Blocked('MODULE_NONFINITE_OR_NONJSON_VALUE') from None


def semantics_and_guard(payload, operation):
    dc = payload['data_contract']; spec = payload['spec']; fields = dc['fields']
    by_name = {f['name']: f for f in fields}
    p.need(len(by_name) == len(fields), 'DUPLICATE_FIELD_DECLARATION')
    p.need(dc['subject_key'] == spec['id'] and dc['record_keys'] == [spec['id']], 'SUBJECT_GRAIN_CONTRACT_MISMATCH')
    p.need(dc['independent_subjects'] is True and spec['independent_subjects'] is True, 'INDEPENDENT_SUBJECTS_REQUIRED')
    group = spec['split'].get('group') if spec['split']['method'] == 'group' else None
    p.need(dc['group_key'] == group, 'GROUP_KEY_CONTRACT_MISMATCH')
    p.need(by_name.get(spec['id'], {}).get('role') == 'id' and by_name[spec['id']]['dtype'] == 'id', 'IDENTITY_FIELD_CONTRACT_INVALID')
    for row in payload['rows']:
        p.need(set(row) <= set(by_name), 'UNDECLARED_ROW_FIELD')
        p.need(isinstance(row.get(spec['id']), str) and row[spec['id']], 'SUBJECT_ID_CHARACTER_REQUIRED')
        for key, value in row.items():
            if value is None:
                continue
            dtype = by_name[key]['dtype']
            p.need((dtype in {'number', 'time'} and type(value) in (int, float) and math.isfinite(value)) or
                   (dtype in {'id', 'category'} and isinstance(value, str)), 'DECLARED_FIELD_TYPE_MISMATCH')
    t = dc['time']
    p.need(t['prediction_at'] <= t['outcome_start'] < t['outcome_end'], 'TIME_WINDOW_CONTRACT_INVALID')
    p.need(dc['missing']['fit_scope'] == ('training_only' if operation == 'train' else 'frozen_only'), 'MISSING_FIT_SCOPE_MISMATCH')
    p.need(dc['missing']['strategy'] == spec['missing'], 'MISSING_POLICY_MISMATCH')
    for f in fields:
        p.need(f['occurred_at'] <= f['available_at'], 'FIELD_AVAILABILITY_INVALID')
    for feature in spec['features']:
        f = by_name.get(feature['name'], {})
        p.need(f.get('role') == 'feature' and f.get('dtype') == feature['type'], 'FEATURE_ROLE_CONTRACT_MISMATCH')
        p.need(f['available_at'] <= t['prediction_at'], 'FUTURE_INFORMATION')
    outcome = by_name.get(spec['outcome'], {})
    p.need(outcome.get('role') == 'outcome' and outcome.get('dtype') == 'category', 'OUTCOME_FIELD_CONTRACT_MISMATCH')
    if operation in {'train', 'evaluate'} or (operation == 'explain' and payload['explain_with_outcomes']):
        p.need(t['outcome_start'] <= outcome['occurred_at'] <= t['outcome_end'] and
               max(t['outcome_end'], outcome['available_at']) <= t['analysis_as_of'], 'OUTCOME_LABEL_NOT_MATURE')
    if group:
        p.need(by_name.get(group, {}).get('role') == 'split', 'GROUP_FIELD_ROLE_INVALID')
    if spec['split']['method'] == 'temporal':
        p.need(by_name.get(spec['split']['time'], {}).get('role') == 'time' and
               by_name.get(spec['split']['label_available_time'], {}).get('role') == 'label_time', 'TEMPORAL_FIELD_ROLE_INVALID')
        p.need(all(by_name[name]['unit'] == t['unit'] for name in (spec['split']['time'],spec['split']['label_available_time'])), 'TEMPORAL_FIELD_UNIT_MISMATCH')
    semantics = copy.deepcopy(dc)
    semantics['time'].pop('analysis_as_of')
    semantics['missing'].pop('fit_scope')
    return semantics


def analyze(request):
    """Shared API. The caller MUST first verify bindings against its trusted context.

    input/plan/code/runtime hashes are opaque common-core bindings, not authorization
    inferred from caller-supplied data. This facade checks the frozen model hash and
    the existing numerical provider independently verifies frozen source/runtime.
    """
    counts = {}; stage = 'contract'
    try:
        validate_json(request, CONTRACTS_ROOT / 'module-request.schema.json')
        method = request['method_id']; op = request['operation']
        p.need(method in p.METHODS, 'MODULE_METHOD_NOT_REGISTERED')
        p.need(op in {'train', 'evaluate', 'infer', 'explain'}, 'MODULE_OPERATION_UNSUPPORTED')
        payload = request['payload']
        validate_json(payload, OWNED_SCHEMAS / 'payload.schema.json')
        for name in ('diagnostics', 'public-record', 'private-record'):
            p.need((OWNED_SCHEMAS / (name + '.schema.json')).is_file(), 'MODULE_SCHEMA_MISSING')
        semantics = semantics_and_guard(payload, op)
        model = adapter.strict_load(payload['frozen_model_json'].encode('utf-8')) if payload['frozen_model_json'] is not None else None
        model_hash = model.get('sha256') if isinstance(model, dict) else None
        p.need(request['bindings']['model_sha256'] == model_hash, 'MODULE_MODEL_BINDING_MISMATCH')
        p.need((op == 'train' and model is None) or (op != 'train' and model is not None), 'MODULE_FROZEN_MODEL_REQUIRED')
        p.need(op == 'explain' or not payload['explain_with_outcomes'], 'EXPLANATION_MUST_USE_EXPLAIN_OPERATION')
        scope = payload['application_scope']
        p.need((op == 'train' and scope == 'development') or
               (op != 'train' and scope in {'external','development_holdout'}), 'APPLICATION_SCOPE_MISMATCH')
        translated = {'method_id': method, 'operation': 'infer' if op == 'explain' else op,
                      'rows': payload['rows'], 'spec': payload['spec'], 'model_bundle': model, 'canonical_semantics': semantics}
        stage = 'compute'
        # Retain the common owner's row-flow counts even when a later metric or
        # estimation guard raises before adapter.execute can return its record.
        # This is descriptive accounting only; no fitting/evaluation is duplicated.
        if op in {'train', 'evaluate'} or (op == 'explain' and payload['explain_with_outcomes']):
            try:
                _, counts = p.common._rows(payload['rows'], payload['spec'], training=op == 'train')
            except p.Blocked as exc:
                if str(exc) == 'NO_ANALYZABLE_OUTCOMES':
                    # For the module's required imputation policy, common._rows
                    # reaches this guard only after validating all rows and finding
                    # every outcome missing. No usable-outcome count is invented.
                    if all(p.common._missing(row[payload['spec']['outcome']]) for row in payload['rows']):
                        counts = {'total_n': len(payload['rows']), 'total_events': 0, 'total_nonevents': 0,
                                  'missing_outcome_n': len(payload['rows']), 'missing_feature_excluded_n': 0,
                                  'analyzable_n': 0, 'analyzable_events': 0, 'analyzable_nonevents': 0,
                                  'source_rows': len(payload['rows']), 'prediction_n': None}
                        if op != 'train':
                            counts.update(evaluation_n=0, evaluation_events=0, evaluation_nonevents=0)
                raise
            counts['source_rows'] = len(payload['rows'])
            counts['prediction_n'] = None  # No completed prediction result yet.
            if op != 'train':
                counts.update(evaluation_n=counts['analyzable_n'], evaluation_events=counts['analyzable_events'],
                              evaluation_nonevents=counts['analyzable_nonevents'])
        calculated = adapter.execute(translated, include_explanation=False,
                                     application_scope='external' if scope == 'development' else scope)
        record = calculated['record']; counts = record['counts']
        p.need(record['status'] != 'BLOCKED_ESTIMATION', record.get('reason_code', 'ESTIMATION_BLOCKED'))
        if op == 'explain':
            if payload['explain_with_outcomes']:
                data, _ = p.common._rows(payload['rows'], payload['spec'], training=False)
                counts['evaluation_n'] = len(data)
                counts['evaluation_events'] = sum(r['_ye1_outcome'] for r in data)
                counts['evaluation_nonevents'] = len(data) - counts['evaluation_events']
            else:
                data, _ = p.common_bridge.binary_inference_rows(payload['rows'], payload['spec'])
            inner = calculated['model_bundle']['bundle']
            record['explanation'] = p.explain(data, inner['model'], payload['spec'],
                label_available=payload['explain_with_outcomes'], grids=inner['pdp_grids'])
            record['explanation']['evaluation_set'] = 'frozen_' + scope + '_explanation'
            record['status'] = 'EXPLAINED'
        public = {k: record.get(k) for k in ('status', 'counts', 'validation', 'metrics', 'internal_cv', 'explanation', 'limitations')}
        diagnostics = {'stage': 'complete', 'provider_version': calculated['provider_version'], 'runtime': calculated['runtime'],
                       'counts': counts, 'fit_metadata': record.get('diagnostics'),
                       'bindings_checked': 'model_hash_here; input_plan_code_runtime_expected_context_owned_by_common_entrypoint',
                       'model_refitted': op == 'train', 'preprocessing_refitted': op == 'train', 'calibration_refitted': op == 'train' and payload['spec']['calibration']['method'] == 'sigmoid'}
        private = {'frozen_model_json': json.dumps(calculated['model_bundle'], ensure_ascii=False, allow_nan=False, separators=(',', ':')),
                   'individual': calculated['individual']}
        response = {'api_version': 'clinical-module-response@1.0', 'ok': True, 'reason_code': None,
                    'diagnostics': diagnostics, 'public_record': public, 'private_record': private}
        validate_json(diagnostics, OWNED_SCHEMAS / 'diagnostics.schema.json')
        validate_json(public, OWNED_SCHEMAS / 'public-record.schema.json')
        validate_json(private, OWNED_SCHEMAS / 'private-record.schema.json')
        validate_json(response, CONTRACTS_ROOT / 'module-response.schema.json')
        return response
    except (p.Blocked, core_contracts.ContractBlocked) as exc:
        code = str(exc)
        if not code or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code):
            code = 'MODULE_CONTRACT_OR_ESTIMATION_BLOCKED'
    except Exception:
        code = 'MODULE_INPUT_OR_RUNTIME_ERROR'
    return {'api_version': 'clinical-module-response@1.0', 'ok': False, 'reason_code': code,
            'diagnostics': {'stage': stage, 'provider_version': p.provider_version(), 'runtime': p.runtime(),
                            'counts': counts, 'fit_metadata': None, 'bindings_checked': 'not_completed',
                            'model_refitted': False, 'preprocessing_refitted': False, 'calibration_refitted': False},
            'public_record': None, 'private_record': None}
