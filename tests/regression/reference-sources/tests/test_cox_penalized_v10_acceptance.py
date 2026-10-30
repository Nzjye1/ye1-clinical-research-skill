def close(a, b, tol=1e-12):
    assert a is not None and b is not None, 'null scalar'
    a = float(a)
    b = float(b)
    assert math.isfinite(a) and math.isfinite(b), 'nonfinite scalar'
    delta = abs(a - b)
    assert delta <= tol, f'absolute difference {delta:.17g} > fixed {tol:g}'
    return delta

def subset(a, b, path='root', tol=1e-12):
    delta = 0.0
    if isinstance(b, dict):
        assert isinstance(a, dict), path + ': object required'
        for k, v in b.items():
            assert k in a, path + ': missing ' + k
            delta = max(delta, subset(a[k], v, path + '.' + k, tol))
    elif isinstance(b, list):
        assert isinstance(a, list) and len(a) == len(b), path + ': array length mismatch'
        for i, (x, y) in enumerate(zip(a, b)):
            delta = max(delta, subset(x, y, f'{path}[{i}]', tol))
    elif type(b) in (int, float):
        try:
            delta = close(a, b, tol)
        except AssertionError as e:
            raise AssertionError(path + ': ' + str(e)) from e
    else:
        assert a == b, path + ': metadata mismatch'
    return delta

def table(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def predictions(info):
    rows = table(info['out'] / 'private/cox-penalized-individual-predictions.csv')
    for row in rows:
        for k in ('fold', 'duration', 'event', 'linear_predictor', 'centered_linear_predictor', 'horizon', 'survival', 'risk'):
            row[k] = None if row[k] in ('', 'NA') else float(row[k])
        if row.get('group_id') in ('', 'NA'):
            row['group_id'] = None
    return rows

def model_path(info):
    return info['out'] / 'private/cox-penalized-model.json'

def bundle(info):
    return load(model_path(info))

def compare_reference(info, ref):
    rec = info['result']['cox_penalized_prediction']
    model = bundle(info)['model']
    delta = 0.0
    baseline_delta = 0.0
    lp_delta = 0.0
    risk_delta = 0.0
    assert rec['status'] == 'completed'
    for key in ('selected_lambda', 'selected_lambda_index'):
        assert rec[key] == model[key] == ref[key]
    for name, actual in [('path', rec['path']), ('cv', rec['cv']['rows']), ('fold_losses', rec['cv']['fold_losses']), ('coefficients', model['coefficients'])]:
        delta = max(delta, subset(actual, ref[name], name, 2e-07))
    delta = max(delta, close(rec['selected_engine_lambda'], ref['selected_engine_lambda'], 2e-07), subset(model['engine']['control'], ref['control']))
    assert model['training_subject_ids'] == ref['training_subject_ids'] and model['training_group_ids'] == ref['training_group_ids']
    pp = model['preprocessor']
    rp = ref['preprocessor']
    assert [r['term'] for r in pp['columns']] == rp['retained'] and [r['term'] for r in pp['dropped_columns']] == rp['dropped']
    for a, b in zip(pp['features'], rp['features']):
        delta = max(delta, subset(a, {k: b[k] for k in ('name', 'type', 'impute', 'levels', 'reference')}))
    for row in pp['columns']:
        delta = max(delta, close(row['center'], rp['center'][row['term']]), close(row['scale'], rp['scale'][row['term']]))
    baseline_delta = max(subset(model['baseline'], ref['baseline'], tol=2e-08), subset(ref['fixed_survival_baseline'], ref['baseline'], tol=2e-08), subset(ref['offset_survival_baseline'], ref['baseline'], tol=2e-08))
    subset(model['training_support'], ref['training_support'])
    actual = {(r['subject_id'], r['horizon']): r for r in predictions(info)}
    assert len(actual) == len(ref['individual'])
    for row in ref['individual']:
        a = actual[row['subject_id'], row['horizon']]
        for key in ('linear_predictor', 'centered_linear_predictor'):
            lp_delta = max(lp_delta, close(a[key], row[key], 2e-07))
        for key in ('survival', 'risk'):
            risk_delta = max(risk_delta, close(a[key], row[key], 2e-08))
        for key in ('group_id', 'partition', 'fold', 'duration', 'event'):
            subset(a[key], row[key], key)
    assert rec['diagnostics']['n_engine_fits'] == len(ref['folds']) + 1 and rec['diagnostics']['warning_count'] == 0 and (rec['diagnostics']['jerr'] == 0)
    for a, b in zip(rec['cv']['folds'], ref['folds']):
        for key in ('fold', 'n_training', 'n_validation', 'training_events', 'training_censored', 'validation_events', 'validation_censored'):
            assert a[key] == b[key]
        assert a['n_encoded_columns'] == len(b['preprocessor']['retained']) and a['n_dropped_columns'] == len(b['preprocessor']['dropped'])
    return {'max_coefficient_cv_difference': delta, 'max_baseline_difference': baseline_delta, 'max_linear_predictor_difference': lp_delta, 'max_risk_difference': risk_delta, 'max_engine_manual_deviance_difference': ref['max_engine_vs_manual_deviance_difference'], 'selected_lambda': rec['selected_lambda']}