"""Private JSON numerical adapter. Authorization and view binding belong to R/core.

No fitting formula is implemented here. Raw binary and continuous providers are
version locked; external evaluation and inference use only frozen coefficients.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd

if __package__:
    from . import prediction as binary
    from . import real_family_admission as study_origin
    from .continuous_ridge import prediction_engine as continuous
    from .continuous_ridge import prediction_metrics as continuous_metrics
    from .continuous_ridge.core import StudyError
else:
    import prediction as binary
    import real_family_admission as study_origin
    from continuous_ridge import prediction_engine as continuous
    from continuous_ridge import prediction_metrics as continuous_metrics
    from continuous_ridge.core import StudyError

CONTINUOUS_VERSION = 'clinical-continuous-ridge-adapter/0.2.0'
CONTINUOUS_METHOD = 'prediction.continuous.nonnegative.ridge'
TARGET_POLICY = {'domain': 'nonnegative', 'transform': 'identity', 'inverse_transform': 'identity',
                 'output_policy': 'clip_lower_zero', 'lower_bound': 0}
METHODS = {'prediction.binary.ridge', CONTINUOUS_METHOD}


def need(condition, code):
    if not condition:
        raise binary.PredictionBlocked(code)


def provider_versions():
    base = Path(__file__).parent
    files = ['prediction.py', 'prediction_bridge.py', 'real_family_admission.py', 'continuous_ridge/__init__.py',
             'continuous_ridge/core.py', 'continuous_ridge/prediction_engine.py',
             'continuous_ridge/prediction_metrics.py']
    hashes = {name: hashlib.sha256((base/name).read_bytes()).hexdigest() for name in files}
    # Each method pins its numerical provider and the adapter that interprets it.
    return {'prediction.binary.ridge': binary._digest({n: hashes[n] for n in ['prediction.py', 'prediction_bridge.py', 'real_family_admission.py']}),
            CONTINUOUS_METHOD: binary._digest(hashes)}


def provider_version():
    return binary._digest(provider_versions())


def runtime():
    result = {'python': platform.python_version()}
    for name in ['numpy', 'scipy', 'statsmodels', 'sklearn', 'pandas']:
        try:
            result[name] = importlib.metadata.version('scikit-learn' if name == 'sklearn' else name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def seal(bundle, version=None):
    result = copy.deepcopy(bundle)
    result.pop('sha256', None)
    result['sha256'] = binary._digest(result)
    return result


def verify_bundle(bundle, version, method, study_context=None):
    need(isinstance(bundle, dict), 'FROZEN_MODEL_REQUIRED')
    check = copy.deepcopy(bundle)
    expected = check.pop('sha256', None)
    need(expected == binary._digest(check), 'MODEL_BUNDLE_HASH_MISMATCH')
    need(check.get('schema_version') == 'clinical-frozen-prediction/0.2.0', 'UNSUPPORTED_MODEL_BUNDLE')
    need(check.get('method_id') == method, 'MODEL_METHOD_MISMATCH')
    need(check.get('provider_version') == version, 'MODEL_PROVIDER_VERSION_MISMATCH')
    if study_context is None:
        need(check.get('test_only') is True and check.get('scientific_review') == 'pending' and
             check.get('export_status') == 'local_only', 'MODEL_CLASSIFICATION_MISMATCH')
    else:
        study_origin.frozen_context(study_context, check,
            lambda condition, code, stage="binding": need(condition, code))
    need(check.get('target_policy') == (TARGET_POLICY if method == CONTINUOUS_METHOD else None), 'FROZEN_TARGET_POLICY_MISMATCH')
    inner = copy.deepcopy(check.get('bundle', {})); inner_expected = inner.pop('sha256', None)
    need(inner_expected == binary._digest(inner), 'MODEL_BUNDLE_HASH_MISMATCH')


def frozen_binary_spec(bundle, spec):
    need(bundle.get('schema_version') == binary.VERSION and
         bundle.get('classification') == 'LOCAL_ONLY_MODEL_BUNDLE', 'UNSUPPORTED_MODEL_BUNDLE')
    binary._validate_spec(spec)
    grid, threshold = binary._threshold_policy(spec)
    for key, value in bundle['definitions'].items():
        actual = grid if key == 'dca_thresholds' else threshold if key == 'clinical_decision_threshold' else spec.get(key, 'train_median_mode' if key == 'missing' else None)
        need(actual == value, 'EXTERNAL_DEFINITIONS_DIFFER_FROM_FROZEN_MODEL')
    need(spec.get('cohort_id') != bundle['development_cohort_id'], 'EXTERNAL_COHORT_MUST_DIFFER')
    need({'dca_thresholds', 'clinical_decision_threshold'} <= set(bundle['definitions']), 'FROZEN_THRESHOLD_POLICY_REQUIRED')


def binary_inference_rows(rows, spec):
    # Validate predictors identically to _rows, while deliberately allowing no label.
    binary._validate_spec(spec)
    binary._reject_reserved_names(name for row in rows for name in row)
    required = {spec['id'], *(f['name'] for f in spec['features'])}
    need(all(required <= set(r) for r in rows), 'REQUIRED_COLUMN_ABSENT')
    need(all(not binary._missing(r[spec['id']]) for r in rows), 'IDENTIFIER_MISSING')
    need(len({binary._id_digest(r[spec['id']]) for r in rows}) == len(rows), 'DUPLICATE_SUBJECT_IN_INDEPENDENT_PREDICTION')
    data, positions = [], []
    for index, source in enumerate(rows):
        row = dict(source)
        missing = False
        for feature in spec['features']:
            name = feature['name']; value = row[name]
            if binary._missing(value):
                row[name] = None; missing = True
            elif feature['type'] == 'number':
                try:
                    row[name] = float(value)
                except (ValueError, TypeError, OverflowError):
                    raise binary.PredictionBlocked('INVALID_NUMERIC_FEATURE') from None
                need(math.isfinite(row[name]), 'NONFINITE_FEATURE')
            else:
                row[name] = str(value)
                need(row[name] in {str(v) for v in feature['levels']}, 'UNKNOWN_CATEGORY')
        if spec.get('missing', 'train_median_mode') == 'complete_case' and missing:
            continue
        data.append(row); positions.append(index)
    need(bool(data), 'NO_ANALYZABLE_PREDICTORS')
    return data, positions


def private_predictions(positions, values, partition):
    return [{'row_index': int(i), 'prediction': float(p), 'partition': partition} for i, p in zip(positions, values)]


def run_binary(operation, rows, spec, bundle, version):
    if operation == 'train':
        record = binary.analyze(rows, spec)
        bundle = record.pop('model_bundle', None)
        if bundle is None:
            record['reason_code'] = record.get('reason', 'ESTIMATION_BLOCKED')
            return record, None, []
        data, _ = binary._rows(rows, spec, training=True)
        train, test = binary._split(data, spec)
        positions = {binary._id_digest(r[spec['id']]): i for i, r in enumerate(rows)}
        individual = []
        for indices, partition in [(train, 'training'), (test, 'holdout')]:
            selected = [data[i] for i in indices]
            individual += private_predictions([positions[binary._id_digest(r[spec['id']])] for r in selected], binary._probabilities(selected, bundle['model']), partition)
    else:
        frozen_binary_spec(bundle, spec)
        need(not ({binary._id_digest(r.get(spec['id'])) for r in rows} & set(bundle['development_id_digests'])), 'EXTERNAL_SUBJECT_OVERLAP')
        if operation == 'evaluate':
            record = binary.validate_external(rows, bundle, spec)
            data, _ = binary._rows(rows, spec, training=False)
            lookup = {binary._id_digest(r[spec['id']]): i for i, r in enumerate(rows)}
            positions = [lookup[binary._id_digest(r[spec['id']])] for r in data]
        else:
            data, positions = binary_inference_rows(rows, spec)
            record = {'status': 'PREDICTED', 'counts': {'total_n': len(rows), 'analyzable_n': len(data), 'missing_feature_excluded_n': len(rows)-len(data)},
                      'metrics': None, 'model_refitted': False, 'preprocessing_refitted': False,
                      'limitations': ['Inference only; outcomes are not evaluated and no performance is inferred.']}
        individual = private_predictions(positions, binary._probabilities(data, bundle['model']), operation)
    record.setdefault('internal_cv', None)
    record['model_sha256'] = bundle['sha256']
    record['unknown_category_policy'] = 'reject'
    record['limitations'].append('This adapter acceptance covers synthetic technical application only; real external independence is not established.')
    return record, bundle, individual


def continuous_spec(spec):
    for key in ['id', 'outcome', 'cohort_id', 'prediction_time', 'outcome_window']:
        need(isinstance(spec.get(key), str) and bool(spec[key].strip()), 'PREDICTION_DEFINITION_REQUIRED')
    need(spec.get('task') == 'continuous', 'CONTINUOUS_TASK_REQUIRED')
    need(spec.get('outcome_domain') == 'nonnegative' and spec.get('outcome_transform') == 'identity', 'NONNEGATIVE_IDENTITY_OUTCOME_REQUIRED')
    need(spec.get('target_policy', TARGET_POLICY) == TARGET_POLICY, 'TARGET_POLICY_UNSUPPORTED')
    features = spec.get('features')
    need(isinstance(features, list) and bool(features) and all(isinstance(f, dict) for f in features), 'EXPLICIT_FEATURE_DEFINITIONS_REQUIRED')
    split = spec.get('split', {})
    need(split.get('method') == 'group' and isinstance(split.get('group'), str) and bool(split['group']), 'CONTINUOUS_GROUP_SPLIT_REQUIRED')
    names = [f.get('variable') for f in features]
    need(all(isinstance(n, str) and n for n in names) and len(set(names)) == len(names), 'UNIQUE_FEATURE_NAMES_REQUIRED')
    need(not (set(names) & {spec['id'], spec['outcome'], split['group'], 'group_id', 'outcome'}), 'LEAKAGE_ROLE_IN_FEATURES')
    for f in features:
        need(f.get('available_at_prediction') is True, 'PREDICTOR_TIMING_NOT_CONFIRMED')
        need(f.get('kind') in {'continuous', 'binary', 'categorical'}, 'UNSUPPORTED_FEATURE_TYPE')
        need(isinstance(f.get('step', 1), (float, int)) and not isinstance(f.get('step', 1), bool) and math.isfinite(f.get('step', 1)) and f.get('step', 1) > 0, 'FEATURE_STEP_INVALID')
        if f['kind'] == 'categorical':
            levels = f.get('levels')
            need(isinstance(levels, list) and len(levels) >= 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in levels) and len(set(levels)) == len(levels) and f.get('reference') in levels, 'PREDECLARED_CATEGORY_LEVELS_REQUIRED')
    need(isinstance(split.get('seed'), int) and not isinstance(split['seed'], bool) and 0 <= split['seed'] < 2**32, 'REPRODUCIBLE_SEED_REQUIRED')
    need(isinstance(split.get('test_fraction'), (float, int)) and .2 <= split['test_fraction'] <= .5, 'TEST_FRACTION_OUTSIDE_02_05')
    need(isinstance(split.get('cv_folds'), int) and not isinstance(split['cv_folds'], bool) and 2 <= split['cv_folds'] <= 10, 'CV_FOLDS_INVALID')
    grid = spec.get('tuning', {}).get('ridge_grid')
    need(isinstance(grid, list) and 1 <= len(grid) <= 20 and all(isinstance(a, (int, float)) and not isinstance(a, bool) and math.isfinite(a) and a > 0 for a in grid) and len(set(grid)) == len(grid), 'POSITIVE_PREDECLARED_RIDGE_GRID_REQUIRED')
    evaluation = spec.get('evaluation', {})
    need(evaluation.get('threshold') == .5, 'CONTINUOUS_UNUSED_THRESHOLD_MUST_BE_05')
    reps = evaluation.get('bootstrap_repetitions')
    need(isinstance(reps, int) and not isinstance(reps, bool) and (reps == 0 or 50 <= reps <= 2000), 'BOOTSTRAP_REPS_INVALID')


def continuous_rows(rows, spec, operation):
    required = {spec['id'], spec['split']['group'], *(f['variable'] for f in spec['features'])}
    if operation != 'infer':
        required.add(spec['outcome'])
    need(all(required <= set(r) for r in rows), 'REQUIRED_COLUMN_ABSENT')
    need(all(not binary._missing(r[spec['id']]) and not binary._missing(r[spec['split']['group']]) for r in rows), 'IDENTIFIER_MISSING')
    need(len({binary._id_digest(r[spec['id']]) for r in rows}) == len(rows), 'DUPLICATE_SUBJECT_IN_INDEPENDENT_PREDICTION')
    records, positions = [], []
    for index, source in enumerate(rows):
        row = dict(source)
        if operation != 'infer':
            if binary._missing(row[spec['outcome']]):
                continue
            try:
                y = float(row[spec['outcome']])
            except (ValueError, TypeError, OverflowError):
                raise binary.PredictionBlocked('INVALID_NUMERIC_OUTCOME') from None
            need(math.isfinite(y), 'NONFINITE_OUTCOME')
            need(y >= 0, 'NEGATIVE_OUTCOME_NOT_SUPPORTED')
            row['outcome'] = y
        for f in spec['features']:
            name = f['variable']; value = row[name]
            if binary._missing(value):
                row[name] = np.nan
                continue
            try:
                row[name] = float(value)
            except (ValueError, TypeError, OverflowError):
                raise binary.PredictionBlocked('INVALID_NUMERIC_FEATURE') from None
            need(math.isfinite(row[name]), 'NONFINITE_FEATURE')
            if f['kind'] in {'binary', 'categorical'}:
                need(row[name] in ([0, 1] if f['kind'] == 'binary' else f['levels']), 'UNKNOWN_CATEGORY')
        row['group_id'] = str(source[spec['split']['group']])
        records.append(row); positions.append(index)
    need(bool(records), 'NO_ANALYZABLE_PREDICTORS' if operation == 'infer' else 'NO_ANALYZABLE_OUTCOMES')
    return pd.DataFrame(records), positions


def run_continuous(operation, rows, spec, bundle, version):
    continuous_spec(spec)
    definitions = {k: copy.deepcopy(v) for k, v in spec.items() if k != 'cohort_id'}
    if operation != 'train':
        need(bundle.get('schema_version') == CONTINUOUS_VERSION and bundle.get('classification') == 'LOCAL_ONLY_MODEL_BUNDLE', 'UNSUPPORTED_MODEL_BUNDLE')
        need(definitions == bundle['definitions'], 'EXTERNAL_DEFINITIONS_DIFFER_FROM_FROZEN_MODEL')
        need(spec['cohort_id'] != bundle['development_cohort_id'], 'EXTERNAL_COHORT_MUST_DIFFER')
        need(not ({binary._id_digest(r.get(spec['id'])) for r in rows} & set(bundle['development_id_digests'])), 'EXTERNAL_SUBJECT_OVERLAP')
        need(not ({binary._id_digest(r.get(spec['split']['group'])) for r in rows} & set(bundle['development_group_digests'])), 'EXTERNAL_GROUP_OVERLAP')
    frame, positions = continuous_rows(rows, spec, operation)
    counts = {'total_n': len(rows), 'analyzable_n': len(frame), 'missing_outcome_n': len(rows)-len(frame) if operation != 'infer' else None}
    if operation == 'train':
        train, holdout = continuous.split_groups(frame.group_id, spec['split']['seed'], spec['split']['test_fraction'])
        counts.update(training_n=int(train.sum()), holdout_n=int(holdout.sum()),
                      training_patient_n=int(frame.loc[train, 'group_id'].nunique()),
                      holdout_patient_n=int(frame.loc[holdout, 'group_id'].nunique()))
        try:
            result = continuous.fit_internal_holdout(frame, spec)
        except StudyError as exc:
            return {'status': 'BLOCKED_ESTIMATION', 'reason': str(exc), 'reason_code': str(exc),
                    'counts': counts, 'metrics': None, 'internal_cv': None, 'baseline_metrics': None,
                    'evaluation': None, 'unknown_category_policy': 'reject',
                    'diagnostics': {'output_policy': copy.deepcopy(TARGET_POLICY)},
                    'limitations': ['Original provider training requirements blocked estimation; no model or predictions were created.',
                                    'Original inner patient fold minimums (100 training, 30 validation) are unchanged.']}, None, []
        model = result['model']; train = result['train_mask']; holdout = result['test_mask']
        bundle = seal({'schema_version': CONTINUOUS_VERSION, 'classification': 'LOCAL_ONLY_MODEL_BUNDLE',
                       'development_cohort_id': spec['cohort_id'], 'definitions': definitions,
                       'development_id_digests': sorted(binary._id_digest(r[spec['id']]) for r in rows),
                       'development_group_digests': sorted({binary._id_digest(r[spec['split']['group']]) for r in rows}),
                       'model': model, 'training_predictions': result['training_predictions'].tolist()}, version)
        individual = private_predictions(np.array(positions)[train], result['training_predictions'], 'training') + private_predictions(np.array(positions)[holdout], result['heldout_predictions'], 'holdout')
        assessed = frame.loc[holdout]; values = result['heldout_predictions']
        counts.update(training_n=int(train.sum()), holdout_n=int(holdout.sum()), training_patient_n=int(frame.loc[train, 'group_id'].nunique()), holdout_patient_n=int(assessed.group_id.nunique()))
        cv = {'status': 'ESTIMATED', 'folds': spec['split']['cv_folds'], 'tuning_metric': model['tuning_metric'], 'candidates': model['training_patient_CV'], 'selected_ridge_alpha': model['ridge_alpha']}
    else:
        assessed = frame; model = bundle['model']; values = continuous.predict(frame, model)
        individual = private_predictions(positions, values, operation); cv = None
    # Diagnostic trace of the original provider's design -> linear -> identity -> clip.
    # Actual predictions above still come from the unchanged source predict function.
    linear = continuous.transform(frame, model['preprocessor']) @ np.array(model['coefficients'])
    linear_by_position = dict(zip(positions, linear))
    for item in individual:
        raw = float(linear_by_position[item['row_index']])
        item.update(linear_output=raw, inverse_transformed_output=raw, clipped=raw < 0)
    counts['prediction_clipped_n'] = sum(item['clipped'] for item in individual)
    evaluation = None if operation == 'infer' else continuous_metrics.evaluate(assessed.outcome.to_numpy(float), values, assessed.group_id.to_numpy(), model, np.array(bundle['training_predictions']), spec)
    record = {'status': 'PREDICTED' if operation == 'infer' else 'ESTIMATED', 'counts': counts,
              'metrics': evaluation['metrics'] if evaluation else None, 'internal_cv': cv,
              'baseline_metrics': evaluation['baseline_metrics'] if evaluation else None,
              'evaluation': evaluation, 'model_sha256': bundle['sha256'], 'unknown_category_policy': 'reject',
              'diagnostics': {'output_policy': copy.deepcopy(TARGET_POLICY), 'clipping_count_scope': 'all returned individual predictions'},
              'model_refitted': operation == 'train', 'preprocessing_refitted': operation == 'train',
              'limitations': ['Only nonnegative continuous outcomes with identity transform are supported; source predictions are clipped at zero.',
                              'Training median constant comparator and errors use original outcome units.',
                              'Synthetic technical application does not establish real external independence or clinical usefulness.',
                              'Original inner patient fold minimums (100 training, 30 validation) are unchanged.']}
    if operation == 'infer':
        record['limitations'].append('Inference only; outcomes are not evaluated and no performance is inferred.')
    return record, bundle, individual


def request_study_context(value):
    # Classification metadata only; R/core still owns source and plan admission.
    if value is None:
        return None
    fields = {'provenance_version', 'data_origin', 'task_purpose', 'test_only', 'scientific_review', 'export_status'}
    need(isinstance(value, dict) and set(value) == fields, 'STUDY_CONTEXT_INVALID')
    need(value['provenance_version'] == study_origin.PROVENANCE_VERSION
         and value['data_origin'] in {'real', 'synthetic'}
         and value['task_purpose'] in {'engineering_test', 'research_analysis'}
         and value['test_only'] is (value['task_purpose'] == 'engineering_test')
         and value['scientific_review'] == 'pending' and value['export_status'] == 'local_only',
         'STUDY_CONTEXT_INVALID')
    need(value['data_origin'] != 'synthetic' or value['task_purpose'] == 'engineering_test', 'STUDY_CONTEXT_INVALID')
    return copy.deepcopy(value)


def execute(request):
    required = {'operation', 'method_id', 'rows', 'spec', 'model_bundle'}
    need(isinstance(request, dict) and required <= set(request) and set(request) <= required | {'model_ref', 'canonical_semantics', 'study_context'}, 'REQUEST_SCHEMA_INVALID')
    operation = request['operation']; method = request['method_id']
    need(operation in {'train', 'evaluate', 'infer'}, 'OPERATION_UNSUPPORTED')
    need(method in METHODS, 'METHOD_UNSUPPORTED')
    version = provider_versions()[method]
    rows = request['rows']; spec = request['spec']; bundle = request['model_bundle']
    need(isinstance(rows, list) and bool(rows) and all(isinstance(r, dict) for r in rows), 'NONEMPTY_TABLE_REQUIRED')
    need(isinstance(spec, dict), 'SPEC_INVALID')
    study_context = request_study_context(request.get('study_context'))
    frozen_wrapper = None
    canonical_semantics = request.get('canonical_semantics')
    need(canonical_semantics is None or isinstance(canonical_semantics, dict), 'CANONICAL_SEMANTICS_INVALID')
    model_ref = request.get('model_ref')
    if model_ref is not None:
        need(operation != 'train' and bundle is None, 'MODEL_REFERENCE_REQUIRES_NULL_INLINE_BUNDLE')
        need(isinstance(model_ref, dict) and set(model_ref) == {'local_ref', 'content_hash'} and
             isinstance(model_ref['local_ref'], str) and isinstance(model_ref['content_hash'], str), 'MODEL_REFERENCE_INVALID')
        raw = Path(model_ref['local_ref']).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == model_ref['content_hash'], 'MODEL_FILE_HASH_MISMATCH')
        bundle = json.loads(raw.decode('utf-8-sig'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    group_guard = None
    if operation == 'train':
        need(bundle is None, 'TRAIN_REQUIRES_NULL_MODEL')
        if method == 'prediction.binary.ridge' and spec.get('split', {}).get('method') == 'group':
            field = spec['split'].get('group')
            need(isinstance(field, str) and all(field in r and not binary._missing(r[field]) for r in rows), 'GROUP_DEFINITION_REQUIRED')
            group_guard = {'field': field, 'development_group_digests': sorted({binary._id_digest(r[field]) for r in rows})}
    else:
        verify_bundle(bundle, version, method, study_context)
        frozen_wrapper = copy.deepcopy(bundle)
        need(canonical_semantics == bundle.get('canonical_semantics'), 'FROZEN_CANONICAL_SEMANTICS_MISMATCH')
        canonical_semantics = copy.deepcopy(bundle.get('canonical_semantics'))
        group_guard = bundle.get('group_guard')
        if method == 'prediction.binary.ridge' and group_guard is not None:
            field = group_guard['field']
            need(all(field in r and not binary._missing(r[field]) for r in rows), 'EXTERNAL_GROUP_COLUMN_REQUIRED')
            need(not ({binary._id_digest(r[field]) for r in rows} & set(group_guard['development_group_digests'])), 'EXTERNAL_GROUP_OVERLAP')
        bundle = bundle['bundle']
    fn = run_binary if method == 'prediction.binary.ridge' else run_continuous
    record, bundle, individual = fn(operation, rows, spec, bundle, version)
    if bundle is not None:
        if study_context is not None and operation != 'train':
            # Keep the bound original classification and canonical model hash.
            # External application never upgrades or reseals a legacy wrapper.
            bundle = frozen_wrapper
        else:
            wrapper = {'schema_version': 'clinical-frozen-prediction/0.2.0', 'method_id': method,
                       'test_only': True, 'scientific_review': 'pending', 'export_status': 'local_only',
                       'provider_version': version, 'target_policy': copy.deepcopy(TARGET_POLICY) if method == CONTINUOUS_METHOD else None,
                       'group_guard': group_guard, 'canonical_semantics': copy.deepcopy(canonical_semantics), 'bundle': bundle}
            if study_context is not None:
                wrapper.update(study_context)
            bundle = seal(wrapper)
        record['model_sha256'] = bundle['sha256']
    if study_context is not None:
        record.update({key: study_context[key] for key in ('data_origin', 'task_purpose', 'scientific_review')})
        record['limitations'] = [
            'Project-bound technical application does not establish clinical transportability or usefulness.'
            if note == 'Synthetic technical application does not establish real external independence or clinical usefulness.'
            else note for note in record.get('limitations', [])]
    if record['status'] == 'PREDICTED':
        record['backend_status'] = record['status']; record['status'] = 'INFERENCE_COMPLETE'
    counts = record['counts']; counts['source_rows'] = len(rows)
    for key in ['missing_outcome_n', 'analyzable_n', 'training_n', 'holdout_n', 'evaluation_n']:
        counts.setdefault(key, None)
    counts['prediction_n'] = len(individual)
    if operation == 'evaluate':
        counts['evaluation_n'] = counts['analyzable_n']
    elif operation == 'train':
        counts['evaluation_n'] = counts['holdout_n'] if record.get('metrics') is not None else None
    else:
        counts['evaluation_n'] = None
    return {'ok': True, 'record': record, 'model_bundle': bundle, 'individual': individual,
            'runtime': runtime(), 'provider_version': version}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(json.dumps({'ok': False, 'reason_code': 'CLI_ARGUMENTS_INVALID'})); return 2
    destination = Path(argv[1])
    try:
        # Reserve response before reading input or executing provider; never overwrite.
        with destination.open('x', encoding='utf-8') as output:
            try:
                if argv[0] == '--preflight':
                    result = {'ok': True, 'runtime': runtime(), 'provider_version': provider_version(), 'provider_versions': provider_versions(), 'methods': sorted(METHODS)}
                else:
                    request = json.loads(Path(argv[0]).read_text(encoding='utf-8-sig'), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    result = execute(request)
                    # R must not deserialize/reserialize the frozen object: 1.0 -> 1
                    # would change canonical hashes. Preserve original Python JSON.
                    artifacts = [('individual-predictions.json', result['individual'])]
                    if result['model_bundle'] is not None:
                        artifacts.insert(0, ('model-bundle.json', result['model_bundle']))
                    need(not any((destination.parent/name).exists() for name, _ in artifacts), 'PRIVATE_ARTIFACT_ALREADY_EXISTS')
                    handles = []
                    try:
                        for name, artifact in artifacts:
                            handle = (destination.parent/name).open('x', encoding='utf-8')
                            handles.append(handle)
                        for handle, (_, artifact) in zip(handles, artifacts):
                            handle.write(json.dumps(artifact, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')
                    finally:
                        for handle in handles:
                            handle.close()
                payload = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
            except (binary.PredictionBlocked, StudyError) as exc:
                code = str(exc)
                # Only provider-owned constant reason codes may escape.
                if not code or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code):
                    code = 'PROVIDER_BLOCKED'
                result = {'ok': False, 'reason_code': code}; payload = json.dumps(result)
            except Exception:
                result = {'ok': False, 'reason_code': 'PROVIDER_INPUT_OR_RUNTIME_ERROR'}; payload = json.dumps(result)
            output.write(payload + '\n')
        print(json.dumps({'ok': result['ok'], **({} if result['ok'] else {'reason_code': result['reason_code']})}))
        return 0 if result['ok'] else 2
    except FileExistsError:
        print(json.dumps({'ok': False, 'reason_code': 'OUTPUT_ALREADY_EXISTS'})); return 2
    except OSError:
        print(json.dumps({'ok': False, 'reason_code': 'OUTPUT_UNAVAILABLE'})); return 2


if __name__ == '__main__':
    raise SystemExit(main())
