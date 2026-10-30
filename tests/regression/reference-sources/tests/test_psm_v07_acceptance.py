def close(actual, expected, tol=1e-10):
    assert actual is not None and expected is not None, 'null scalar'
    assert math.isfinite(float(actual)) and math.isfinite(float(expected)), 'nonfinite scalar'
    delta = abs(float(actual) - float(expected))
    assert delta <= tol + tol * abs(float(expected)), f'delta {delta:.17g} exceeds fixed {tol:g} + {tol:g}*abs(reference)'
    return delta

def subset(actual, expected, path='root', tol=1e-10):
    delta = 0.0
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path + ': object required'
        for key, value in expected.items():
            assert key in actual, path + ': missing ' + key
            delta = max(delta, subset(actual[key], value, path + '.' + key, tol))
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path + ': array length'
        for i, (a, b) in enumerate(zip(actual, expected)):
            delta = max(delta, subset(a, b, f'{path}[{i}]', tol))
    elif type(expected) in (int, float):
        try:
            delta = close(actual, expected, tol)
        except AssertionError as exc:
            raise AssertionError(path + ': ' + str(exc)) from exc
    else:
        assert actual == expected, path + ': text/null mismatch'
    return delta

def table(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def private_table(path):
    rows = table(path)
    text = {'subject_id', 'pair_id', 'treated_subject_id', 'control_subject_id', 'match_role', 'status'}
    boolean = {'complete_case', 'support_retained', 'matched'}
    for row in rows:
        for key, value in row.items():
            if key in text:
                continue
            if key in boolean:
                row[key] = value.upper() == 'TRUE'
            else:
                row[key] = None if value in ('', 'NA') else float(value)
    return rows

def effect_compare(actual, expected):
    delta = subset(actual, {key: expected[key] for key in EFFECT_NUMERIC})
    assert actual['inference_status'] == ('completed' if expected['inference_status'] == 'available' else 'unavailable')
    assert actual['inference_reason_code'] == expected.get('inference_reason_code')
    assert actual['conditioning'] == 'formed_matched_pairs' and actual['ps_estimation_uncertainty_included'] is False
    return delta

def compare_reference(info, ref):
    rec = info['result']['psm']
    delta = 0.0
    glm_delta = 0.0
    flow = copy.deepcopy(ref['flow'])
    missing = flow.pop('missing_by_field')
    delta = max(delta, subset(rec['flow'], flow))
    for key, value in missing.items():
        assert rec['flow']['missing_by_field'][key]['n_missing'] == value
    delta = max(delta, subset(rec['support'], ref['support']))
    scores = private_table(info['out'] / 'private/psm_subjects.csv')
    byid = {row['subject_id']: row for row in scores}
    assert len(scores) == ref['flow']['n_input'] and sum((r['complete_case'] for r in scores)) == len(ref['scores'])
    for expected in ref['scores']:
        actual = byid[expected['subject_id']]
        glm_delta = max(glm_delta, subset(actual, {k: expected[k] for k in ('propensity_score', 'logit_ps')}, tol=1e-08))
        assert actual['complete_case'] and all((actual[k] == expected[k] for k in ('treatment', 'support_retained', 'matched')))
    pairs = private_table(info['out'] / 'private/psm_pairs.csv')
    assert len(pairs) == len(ref['pairs'])
    for actual, expected in zip(pairs, ref['pairs']):
        assert actual['treated_subject_id'] == expected['treated_subject_id'] and actual['control_subject_id'] == expected['control_subject_id']
        for key, value in expected.items():
            if key.endswith('subject_id'):
                continue
            if key in ('treated_ps', 'control_ps', 'treated_logit', 'control_logit', 'logit_distance'):
                glm_delta = max(glm_delta, close(actual[key], value, 1e-08))
            else:
                delta = max(delta, close(actual[key], value))
    model = load(info['out'] / 'private/psm_model.json')
    glm_delta = max(glm_delta, subset(list(model['coefficients'].values()), ref['coefficients'], tol=1e-08))
    for key in ('converged', 'boundary', 'iterations', 'rank'):
        assert model[key] == ref['glm'][key]
    assert model['fitted_subject_ids'] == [row['subject_id'] for row in ref['scores']]
    delta = max(delta, effect_compare(rec['effect'], ref['effect']), subset(rec['balance'], ref['balance']), subset(rec['overlap'], ref['overlap']))
    return {'max_reference_difference': delta, 'max_glm_difference': glm_delta, 'matched_pairs': len(pairs)}
EFFECT_NUMERIC = ('n_pairs', 'treated_mean', 'control_mean', 'estimate', 'paired_difference_variance', 'standard_error', 'df', 'ci_lower', 'ci_upper', 't_statistic', 'p_value', 'treated_variance', 'control_variance', 'treated_control_covariance', 'variance_identity_difference')