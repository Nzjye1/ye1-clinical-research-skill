"""Capture an auditable LOCAL PRIVATE background from actual training artifacts.

No model fit, calibration, transform learning or imaginary historical background.
Integrity hashes do not authenticate an untrusted caller: the common entrypoint
must verify the training request/response against its own trusted stored run.
"""
import copy
import numpy as np
from .runtime import prediction as p, bridge, facade, validate

SCHEMA = 'clinical-tree-shap-background@1.0'


def capture_training_background(training_request, training_response, *, trusted_run_hashes, size=100, seed=1729, resource_budget=None):
    """Called after the existing train owner returns; captures a separate artifact.

    Both arguments must be the trusted original local artifacts of that run.
    trusted_run_hashes is injected by the common owner from its stored run, not
    accepted as a user-asserted provenance declaration in an explanation payload.
    Existing provider output and its frozen JSON are returned/kept unchanged.
    """
    q = training_request; r = training_response
    p.need(isinstance(q, dict) and isinstance(r, dict), 'SUCCESSFUL_TRAINING_ARTIFACTS_REQUIRED')
    p.need(isinstance(trusted_run_hashes, dict) and set(trusted_run_hashes) == {'request_sha256', 'response_sha256'},
           'TRUSTED_TRAINING_ARTIFACT_BINDINGS_REQUIRED')
    p.need(trusted_run_hashes['request_sha256'] == p.common._digest(q) and
           trusted_run_hashes['response_sha256'] == p.common._digest(r), 'TRAINING_ARTIFACT_BINDING_MISMATCH')
    facade.validate_json(q, facade.CONTRACTS_ROOT/'module-request.schema.json')
    facade.validate_json(q['payload'], facade.OWNED_SCHEMAS/'payload.schema.json')
    facade.validate_json(r, facade.CONTRACTS_ROOT/'module-response.schema.json')
    for key, name in [('diagnostics', 'diagnostics'), ('public_record', 'public-record'), ('private_record', 'private-record')]:
        facade.validate_json(r[key], facade.OWNED_SCHEMAS/(name+'.schema.json'))
    p.need(q['operation'] == 'train' and q['method_id'] in p.METHODS and r['ok'], 'SUCCESSFUL_TRAINING_ARTIFACTS_REQUIRED')
    p.need(q['payload']['application_scope'] == 'development' and q['payload']['frozen_model_json'] is None,
           'ORIGINAL_TRAINING_REQUEST_REQUIRED')
    from .explain import resource_limits
    limits = resource_limits(resource_budget, q['method_id'])
    p.need(type(size) is int and 10 <= size <= limits['max_background_rows'] and type(seed) is int and 0 <= seed < 2**32, 'BACKGROUND_SAMPLING_INVALID')
    payload = q['payload']; rows = payload['rows']; spec = payload['spec']
    semantics = facade.semantics_and_guard(payload, 'train')
    p.validate_spec(spec, q['method_id'])
    bundle = bridge.strict_load(r['private_record']['frozen_model_json'].encode())
    inner = bridge.check_bundle(bundle, q['method_id'], spec, semantics, application_scope='development_holdout')
    p.need(r['diagnostics']['provider_version'] == p.provider_version() and r['diagnostics']['runtime'] == p.runtime(),
           'TRAINING_RESPONSE_PROVIDER_MISMATCH')
    p.need(q['bindings']['model_sha256'] is None, 'TRAINING_MODEL_BINDING_MISMATCH')
    # Replay ONLY the common deterministic partition planner, never estimator fit.
    data, counts = p.common._rows(rows, spec, training=True)
    training_ix, holdout_ix = p.common._split(data, spec)
    training = [data[i] for i in training_ix]
    if spec['calibration']['method'] == 'sigmoid':
        cal_spec = copy.deepcopy(spec)
        cal_spec['split']['test_fraction'] = spec['calibration']['fraction']
        cal_spec['split']['seed'] = (spec['split']['seed'] + 1871) % 2**32
        fit_ix, cal_ix = p.common._split(training, cal_spec)
    else:
        fit_ix, cal_ix = list(range(len(training))), []
    partition_ix = {'model_fit': [training_ix[i] for i in fit_ix], 'calibration': [training_ix[i] for i in cal_ix], 'holdout': holdout_ix}
    lookup = {p.common._id_digest(row[spec['id']]): i for i, row in enumerate(rows)}
    expected = {lookup[p.common._id_digest(data[i][spec['id']])]: role for role, indices in partition_ix.items() for i in indices}
    trace = r['private_record']['individual']
    p.need(len(trace) == len(expected) and len({v['row_index'] for v in trace}) == len(trace), 'TRAINING_TRACE_COVERAGE_MISMATCH')
    p.need({v['row_index']: v['partition'] for v in trace} == expected, 'TRAINING_PARTITION_TRACE_MISMATCH')
    ordered = sorted(expected)
    predicted = p.predict([rows[i] for i in ordered], inner['model'])
    by_index = {v['row_index']: v['prediction'] for v in trace}
    p.need(np.max(np.abs(predicted - [by_index[i] for i in ordered])) <= 1e-12, 'TRAINING_TRACE_PREDICTION_MISMATCH')
    for role, indices in partition_ix.items():
        p.need(r['diagnostics']['counts'][role+'_n'] == len(indices), 'TRAINING_PARTITION_COUNTS_MISMATCH')
    fit_positions = sorted(i for i, role in expected.items() if role == 'model_fit')
    p.need(size <= len(fit_positions), 'BACKGROUND_SIZE_EXCEEDS_MODEL_FIT')
    chosen = sorted(np.random.default_rng(seed).choice(fit_positions, size, replace=False).tolist())
    identity = spec['id']; names = [f['name'] for f in spec['features']]
    partitions = {role: sorted(p.common._id_digest(data[i][identity]) for i in indices) for role, indices in partition_ix.items()}
    excluded = sorted(p.common._id_digest(rows[i][identity]) for i in range(len(rows)) if i not in expected)
    artifact = bridge.seal({'schema_version': SCHEMA, 'prediction_method_id': q['method_id'],
        'model_sha256': bundle['sha256'], 'prediction_provider_version': bundle['provider_version'],
        'source': {'origin': 'actual_successful_training_request_and_response', 'cohort_id': spec['cohort_id'],
                   'identity_namespace': semantics['identity_namespace'], 'canonical_rows_sha256': p.common._digest(rows),
                   'training_request_sha256': p.common._digest(q), 'training_response_sha256': p.common._digest(r),
                   'training_bindings': copy.deepcopy(q['bindings']), 'source_n': len(rows), 'outcome_missing_n': counts['missing_outcome_n']},
        'partition': {'role': 'model_fit', 'model_fit_id_digests': partitions['model_fit'],
                      'calibration_id_digests': partitions['calibration'], 'holdout_id_digests': partitions['holdout'],
                      'excluded_outcome_id_digests': excluded},
        'sampling': {'method': 'uniform_without_replacement', 'seed': seed, 'n': size, 'row_indices': chosen},
        'rows': [{identity: rows[i][identity], **{name: rows[i][name] for name in names}} for i in chosen],
        'classification': 'LOCAL_PRIVATE_TRAINING_BACKGROUND',
        'authenticity': 'hashes_and_partition_checks_are_integrity_only; common_owner_verifies_trusted_original_run'})
    check_background(artifact, bundle, spec, resource_budget=limits, budget_method=q['method_id'])
    return artifact


def check_background(artifact, bundle, spec, resource_budget=None, *, budget_method=None):
    from .explain import resource_limits
    method = bundle['method_id'].replace('prediction.', 'explanation.', 1) + '.tree_shap'
    # Capture budgets belong to the successful training run. Its row budget is
    # not an application-row budget; the separate background bound applies here.
    if budget_method is not None:
        p.need(budget_method == bundle['method_id'], 'BACKGROUND_BUDGET_METHOD_MISMATCH')
        method = budget_method
    limits = resource_limits(resource_budget, method)
    p.need(10 <= len(artifact.get('rows', [])) <= limits['max_background_rows'], 'SHAP_BACKGROUND_RESOURCE_BOUND')
    import json
    from clinical_methods.resource_budget import BudgetError
    if len(json.dumps(artifact, ensure_ascii=False, allow_nan=False).encode('utf-8')) > limits['max_input_bytes']:
        raise BudgetError('RESOURCE_INPUT_BYTE_BUDGET_EXCEEDED')
    validate(artifact, 'background')
    unsealed = copy.deepcopy(artifact); digest = unsealed.pop('sha256')
    p.need(digest == p.common._digest(unsealed), 'BACKGROUND_HASH_MISMATCH')
    p.need(artifact['model_sha256'] == bundle['sha256'] and artifact['prediction_method_id'] == bundle['method_id'],
           'BACKGROUND_MODEL_BINDING_MISMATCH')
    p.need(artifact['prediction_provider_version'] == bundle['provider_version'], 'BACKGROUND_PROVIDER_BINDING_MISMATCH')
    inner = bundle['bundle']; source = artifact['source']; part = artifact['partition']
    p.need(source['cohort_id'] == inner['development_cohort_id'] and
           source['identity_namespace'] == bundle['canonical_semantics']['identity_namespace'], 'BACKGROUND_SOURCE_BINDING_MISMATCH')
    sets = []
    for name in ('model_fit_id_digests', 'calibration_id_digests', 'holdout_id_digests', 'excluded_outcome_id_digests'):
        values = part[name]; p.need(len(set(values)) == len(values), 'BACKGROUND_DUPLICATE_PARTITION_ID')
        sets.append(set(values))
    p.need(all(a.isdisjoint(b) for i, a in enumerate(sets) for b in sets[i+1:]), 'BACKGROUND_PARTITION_OVERLAP')
    p.need(set.union(*sets) == set(inner['development_id_digests']) and sets[2] == set(inner['holdout_id_digests']),
           'BACKGROUND_PARTITION_MODEL_MISMATCH')
    p.need(source['source_n'] == sum(map(len, sets)) and source['outcome_missing_n'] == len(sets[3]), 'BACKGROUND_SOURCE_COUNTS_MISMATCH')
    p.need(bool(sets[1]) == (inner['model']['calibration']['method'] == 'sigmoid'), 'BACKGROUND_CALIBRATION_PARTITION_MISMATCH')
    rows = artifact['rows']; sampling = artifact['sampling']; identity = spec['id']
    keys = {identity, *(f['name'] for f in spec['features'])}
    p.need(all(set(row) == keys for row in rows), 'BACKGROUND_ROW_FIELDS_MISMATCH')
    p.need(all(isinstance(row[identity], str) and row[identity] for row in rows), 'BACKGROUND_ID_INVALID')
    ids = [p.common._id_digest(row[identity]) for row in rows]
    p.need(len(set(ids)) == len(ids) and set(ids) <= sets[0], 'BACKGROUND_NOT_FROM_MODEL_FIT')
    p.need(len(rows) == sampling['n'] == len(set(sampling['row_indices'])) and
           all(0 <= i < source['source_n'] for i in sampling['row_indices']), 'BACKGROUND_SAMPLING_COUNTS_MISMATCH')
    for feature in spec['features']:
        for row in rows:
            value = row[feature['name']]
            if value is None:
                continue
            p.need((feature['type'] == 'number' and type(value) in (int, float) and np.isfinite(value)) or
                   (feature['type'] == 'category' and isinstance(value, str) and value in feature['levels']), 'BACKGROUND_FEATURE_INVALID')
    x, names = p.common._transform(rows, inner['model']['transforms'])
    p.need(names == inner['model']['feature_names'], 'BACKGROUND_DESIGN_MISMATCH')
    return x.astype(inner['model']['input_dtype'])
