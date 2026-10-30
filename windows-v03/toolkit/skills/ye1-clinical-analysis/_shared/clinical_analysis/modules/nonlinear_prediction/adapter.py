"""Local JSON bridge with the same envelope as the common prediction provider."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import provider as p
from contracts import validate


def strict_load(raw):
    from clinical_methods.contracts import read_json_bytes
    return read_json_bytes(raw)


def seal(value):
    result = copy.deepcopy(value)
    result.pop('sha256', None)
    result['sha256'] = p.common._digest(result)
    return result


def definitions(spec):
    return {k: copy.deepcopy(v) for k, v in spec.items() if k not in {'cohort_id', 'bootstrap', 'evaluation_seed'}}


def check_bundle(bundle, method, spec, semantics, *, application_scope='external'):
    p.need(isinstance(bundle, dict), 'FROZEN_MODEL_REQUIRED')
    p.need(set(bundle) == {'schema_version','method_id','provider_version','runtime','target_policy','canonical_semantics',
        'test_only','scientific_review','export_status','bundle','sha256'}, 'FROZEN_BUNDLE_UNKNOWN_FIELD')
    raw = copy.deepcopy(bundle); expected = raw.pop('sha256', None)
    p.need(expected == p.common._digest(raw), 'MODEL_BUNDLE_HASH_MISMATCH')
    p.need(bundle.get('schema_version') == 'clinical-frozen-prediction/0.2.0', 'UNSUPPORTED_MODEL_BUNDLE')
    p.need(bundle.get('method_id') == method, 'MODEL_METHOD_MISMATCH')
    p.need(bundle.get('provider_version') == p.provider_version(), 'MODEL_PROVIDER_VERSION_MISMATCH')
    p.need(bundle.get('runtime') == p.runtime(), 'MODEL_RUNTIME_VERSION_MISMATCH')
    p.need(bundle.get('test_only') is True and bundle.get('scientific_review') == 'pending' and
           bundle.get('export_status') == 'local_only', 'MODEL_CLASSIFICATION_MISMATCH')
    p.need(bundle.get('canonical_semantics') == semantics, 'FROZEN_CANONICAL_SEMANTICS_MISMATCH')
    inner = copy.deepcopy(bundle['bundle']); expected = inner.pop('sha256', None)
    p.need(expected == p.common._digest(inner) and inner.get('schema_version') == p.VERSION, 'MODEL_INNER_BUNDLE_MISMATCH')
    p.need(definitions(spec) == inner['definitions'], 'EXTERNAL_DEFINITIONS_DIFFER_FROM_FROZEN_MODEL')
    p.need(set(inner) == {'schema_version','classification','development_cohort_id','definitions','development_id_digests',
        'holdout_id_digests','group_guard','model','pdp_grids','fit_scope'}, 'FROZEN_INNER_UNKNOWN_FIELD')
    if application_scope == 'external':
        p.need(spec['cohort_id'] != inner['development_cohort_id'], 'EXTERNAL_COHORT_MUST_DIFFER')
    else:
        p.need(application_scope == 'development_holdout' and spec['cohort_id'] == inner['development_cohort_id'], 'DEVELOPMENT_HOLDOUT_SCOPE_MISMATCH')
    p.need(inner['model']['kind'] == p.METHODS[method], 'MODEL_ALGORITHM_MISMATCH')
    p.need(inner['model']['calibration']['method'] == spec['calibration']['method'], 'FROZEN_CALIBRATION_POLICY_MISMATCH')
    p.check_model(inner['model'])
    return bundle['bundle']


def build_bundle(model, method, spec, semantics, rows, fit_rows, holdout_rows):
    grids = {}
    for f in spec['features']:
        if f['name'] not in spec['explanation']['pdp_features']:
            continue
        if f['type'] == 'category':
            grids[f['name']] = [str(v) for v in f['levels']]
        else:
            values = [r[f['name']] for r in fit_rows if r[f['name']] is not None]
            grids[f['name']] = np.unique(np.quantile(values, [.1, .3, .5, .7, .9])).tolist()
    group = spec['split'].get('group') if spec['split']['method'] == 'group' else None
    inner = seal({'schema_version': p.VERSION, 'classification': 'LOCAL_ONLY_MODEL_BUNDLE',
                  'development_cohort_id': spec['cohort_id'], 'definitions': definitions(spec),
                  'development_id_digests': sorted(p.common._id_digest(r[spec['id']]) for r in rows),
                  'holdout_id_digests': sorted(p.common._id_digest(r[spec['id']]) for r in holdout_rows),
                  'group_guard': {'field': group, 'development_group_digests': sorted({p.common._id_digest(r[group]) for r in rows})} if group else None,
                  'model': model, 'pdp_grids': grids,
                  'fit_scope': 'base-fit subset only; calibration disjoint; final holdout excluded from all learning'})
    return seal({'schema_version': 'clinical-frozen-prediction/0.2.0', 'method_id': method,
                 'provider_version': p.provider_version(), 'runtime': p.runtime(), 'target_policy': None,
                 'canonical_semantics': copy.deepcopy(semantics), 'test_only': True, 'scientific_review': 'pending',
                 'export_status': 'local_only', 'bundle': inner})


def execute(request, *, include_explanation=True, application_scope='external'):
    locked_runtime = strict_load((p.CORE_ROOT / 'runtime-lock.json').read_bytes())['prediction_python_versions']
    p.need(p.runtime() == locked_runtime, 'NONLINEAR_DEPENDENCY_VERSION_DRIFT')
    required = {'operation', 'method_id', 'rows', 'spec', 'model_bundle'}
    p.need(isinstance(request, dict) and required <= set(request) and
           set(request) <= required | {'model_ref', 'canonical_semantics'}, 'REQUEST_SCHEMA_INVALID')
    operation = request['operation']; method = request['method_id']; spec = request['spec']; rows = request['rows']
    p.need(operation in {'train', 'evaluate', 'infer'} and method in p.METHODS, 'METHOD_OR_OPERATION_UNSUPPORTED')
    p.need(isinstance(rows, list) and 1 <= len(rows) <= 100000 and all(isinstance(r, dict) for r in rows), 'NONEMPTY_BOUNDED_TABLE_REQUIRED')
    validate(spec, method)
    p.need(isinstance(request.get('canonical_semantics'), dict) and bool(request['canonical_semantics']), 'CANONICAL_SEMANTICS_REQUIRED')
    semantics = request['canonical_semantics']
    bundle = request['model_bundle']; reference = request.get('model_ref')
    if reference is not None:
        p.need(operation != 'train' and bundle is None and isinstance(reference, dict) and
               set(reference) == {'local_ref', 'content_hash'}, 'MODEL_REFERENCE_INVALID')
        path = Path(reference['local_ref'])
        p.need(path.is_file() and path.stat().st_size <= 30000000, 'MODEL_FILE_UNAVAILABLE_OR_TOO_LARGE')
        raw = path.read_bytes()
        p.need(hashlib.sha256(raw).hexdigest() == reference['content_hash'], 'MODEL_FILE_HASH_MISMATCH')
        bundle = strict_load(raw)
    individual = []
    if operation == 'train':
        p.need(bundle is None, 'TRAIN_REQUIRES_NULL_MODEL')
        data, counts = p.common._rows(rows, spec, training=True)
        record, model, partitions = p.train(data, counts, spec, method)
        if model is not None:
            fit_rows = [data[i] for i in partitions['model_fit']]
            bundle = build_bundle(model, method, spec, semantics, rows, fit_rows, [data[i] for i in partitions['holdout']])
            lookup = {p.common._id_digest(r[spec['id']]): i for i, r in enumerate(rows)}
            for partition, indices in partitions.items():
                selected = [data[i] for i in indices]
                if selected:
                    positions = [lookup[p.common._id_digest(r[spec['id']])] for r in selected]
                    individual += p.common_bridge.private_predictions(positions, p.predict(selected, model), partition)
            assessed = [data[i] for i in partitions['holdout']]
            if include_explanation:
                record['explanation'] = p.explain(assessed, model, spec, label_available=True, grids=bundle['bundle']['pdp_grids'])
                record['explanation']['evaluation_set'] = 'internal_holdout'
    else:
        inner = check_bundle(bundle, method, spec, semantics, application_scope=application_scope)
        if application_scope == 'development_holdout':
            p.need({p.common._id_digest(r.get(spec['id'])) for r in rows} <= set(inner['holdout_id_digests']), 'FROZEN_HOLDOUT_MEMBERSHIP_REQUIRED')
        else:
            p.need(not ({p.common._id_digest(r.get(spec['id'])) for r in rows} & set(inner['development_id_digests'])), 'EXTERNAL_SUBJECT_OVERLAP')
        group_guard = inner.get('group_guard')
        if group_guard and application_scope == 'external':
            field = group_guard['field']
            p.need(all(field in r and not p.common._missing(r[field]) for r in rows), 'EXTERNAL_GROUP_COLUMN_REQUIRED')
            p.need(not ({p.common._id_digest(r[field]) for r in rows} & set(group_guard['development_group_digests'])), 'EXTERNAL_GROUP_OVERLAP')
        if operation == 'evaluate':
            data, counts = p.common._rows(rows, spec, training=False)
            lookup = {p.common._id_digest(r[spec['id']]): i for i, r in enumerate(rows)}
            positions = [lookup[p.common._id_digest(r[spec['id']])] for r in data]
        else:
            data, positions = p.common_bridge.binary_inference_rows(rows, spec)
            counts = {'total_n': len(rows), 'analyzable_n': len(data), 'missing_feature_excluded_n': len(rows) - len(data)}
        probabilities = p.predict(data, inner['model'])
        individual = p.common_bridge.private_predictions(positions, probabilities, operation)
        record = {'status': 'ESTIMATED' if operation == 'evaluate' else 'INFERENCE_COMPLETE', 'counts': counts,
                  'validation': ('frozen development holdout re-evaluation' if application_scope == 'development_holdout' else 'synthetic frozen external application') if operation == 'evaluate' else 'new data inference',
                  'metrics': p.common._metrics(data, probabilities, spec) if operation == 'evaluate' else None,
                  'model_refitted': False, 'preprocessing_refitted': False, 'calibration_refitted': False,
                  'internal_cv': None, 'limitations': list(p.LIMITATIONS)}
        if include_explanation:
            record['explanation'] = p.explain(data, inner['model'], spec, label_available=operation == 'evaluate', grids=inner['pdp_grids'])
            record['explanation']['evaluation_set'] = 'synthetic_frozen_application' if operation == 'evaluate' else 'new_data_inference'
    counts = record['counts']; counts['source_rows'] = len(rows); counts['prediction_n'] = len(individual)
    for name in ('training_n', 'training_events', 'training_nonevents', 'holdout_n', 'holdout_events', 'holdout_nonevents',
                 'model_fit_n', 'calibration_n', 'missing_outcome_n', 'missing_feature_excluded_n'):
        counts.setdefault(name, None)
    counts['evaluation_n'] = (counts['holdout_n'] if operation == 'train' else counts['analyzable_n']) if record['metrics'] is not None else None
    counts['evaluation_events'] = (counts.get('holdout_events') if operation == 'train' else counts.get('analyzable_events')) if record['metrics'] is not None else None
    counts['evaluation_nonevents'] = (counts.get('holdout_nonevents') if operation == 'train' else counts.get('analyzable_nonevents')) if record['metrics'] is not None else None
    record['model_sha256'] = bundle['sha256'] if bundle else None
    record['unknown_category_policy'] = 'reject'
    record['threshold_policy'] = {'source': 'prespecified_before_fit', 'searched': False}
    return {'ok': True, 'record': record, 'model_bundle': bundle, 'individual': individual,
            'runtime': p.runtime(), 'provider_version': p.provider_version()}


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        handle.write('\n')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print('{"ok":false,"reason_code":"CLI_ARGUMENTS_INVALID"}')
        return 2
    destination = Path(args[1])
    try:
        with destination.open('x', encoding='utf-8') as output:
            try:
                if args[0] == '--preflight':
                    result = {'ok': True, 'runtime': p.runtime(), 'provider_version': p.provider_version(), 'methods': sorted(p.METHODS)}
                else:
                    p.need(destination.parent.name == 'private', 'PROVIDER_RESPONSE_MUST_STAY_PRIVATE')
                    result = execute(strict_load(Path(args[0]).read_bytes()))
                    artifacts = [('individual-predictions.json', result['individual'])]
                    if result['model_bundle'] is not None:
                        artifacts.append(('model-bundle.json', result['model_bundle']))
                    p.need(not any((destination.parent / n).exists() for n, _ in artifacts), 'PRIVATE_ARTIFACT_ALREADY_EXISTS')
                    for name, value in artifacts:
                        write_json(destination.parent / name, value)
                code = 0
            except p.Blocked as exc:
                reason = str(exc)
                if not reason or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in reason):
                    reason = 'PROVIDER_BLOCKED'
                result = {'ok': False, 'reason_code': reason}; code = 2
            except Exception:
                result = {'ok': False, 'reason_code': 'PROVIDER_INPUT_OR_RUNTIME_ERROR'}; code = 2
            json.dump(result, output, ensure_ascii=False, allow_nan=False)
        print(json.dumps({'ok': result['ok'], **({'reason_code': result['reason_code']} if not result['ok'] else {})}))
        return code
    except FileExistsError:
        print('{"ok":false,"reason_code":"OUTPUT_ALREADY_EXISTS"}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
