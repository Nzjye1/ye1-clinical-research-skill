def close(a, b, tol=1e-10):
    assert a is not None and b is not None, 'null scalar'
    a = float(a)
    b = float(b)
    assert math.isfinite(a) and math.isfinite(b), 'nonfinite scalar'
    delta = abs(a - b)
    assert delta <= tol + tol * abs(b), f'delta {delta:.17g} exceeds {tol:g} + {tol:g}*abs(reference)'
    return delta

def subset(a, b, path='root', tol=1e-10):
    delta = 0.0
    if isinstance(b, dict):
        assert isinstance(a, dict), path + ': expected object'
        for k, v in b.items():
            assert k in a, path + ': missing ' + k
            delta = max(delta, subset(a[k], v, path + '.' + k, tol))
    elif isinstance(b, list):
        assert isinstance(a, list) and len(a) == len(b), path + ': array length'
        for i, (x, y) in enumerate(zip(a, b)):
            delta = max(delta, subset(x, y, f'{path}[{i}]', tol))
    elif type(b) in (int, float):
        try:
            delta = close(a, b, tol)
        except AssertionError as exc:
            raise AssertionError(path + ': ' + str(exc)) from exc
    else:
        assert a == b, path + ': text/null mismatch'
    return delta

def table(p):
    with Path(p).open(encoding='utf-8-sig', newline='') as h:
        return list(csv.DictReader(h))

def individual(p):
    rows = table(p)
    for row in rows:
        for k in ('fold', 'observed', 'prediction', 'linear_predictor'):
            row[k] = None if row[k] in ('', 'NA') else float(row[k])
    return rows

def loaded_model(info):
    return load(info['out'] / 'private/penalized-model.json')

def model_path(info):
    return info['out'] / 'private/penalized-model.json'

def predictions(info):
    return individual(info['out'] / 'private/penalized-individual-predictions.csv')

def compare_reference(info, ref):
    rec = info['result']['penalized_prediction']
    assert rec is not None and rec['status'] == 'completed', info['result'].get('reason_code')
    model = loaded_model(info)['model']
    delta = 0.0
    metrics_delta = 0.0
    for key in ('selected_lambda', 'selected_lambda_index'):
        assert rec[key] == model[key] == ref[key]
    delta = max(delta, close(rec['selected_engine_lambda'], ref['selected_engine_lambda'], 1e-08), subset(rec['path'], ref['path'], tol=1e-08), subset(rec['cv']['rows'], ref['cv'], tol=1e-08), subset(rec['cv']['fold_losses'], ref['fold_losses'], tol=1e-08))
    assert model['training_subject_ids'] == ref['training_subject_ids'] and model['training_group_ids'] == ref['training_group_ids']
    pp = model['preprocessor']
    rp = ref['preprocessor']
    assert [r['term'] for r in pp['columns']] == rp['retained'] and [r['term'] for r in pp['dropped_columns']] == rp['dropped']
    for a, b in zip(pp['features'], rp['features']):
        delta = max(delta, subset(a, {k: b[k] for k in ('name', 'type', 'impute', 'levels', 'reference')}))
    for row in pp['columns']:
        delta = max(delta, close(row['center'], rp['center'][row['term']]), close(row['scale'], rp['scale'][row['term']]))
    assert model['response_transform']['method'] == ref['response_transform']['kind']
    delta = max(delta, subset(model['response_transform'], {k: ref['response_transform'][k] for k in ('center', 'scale')}), subset(model['engine']['control'], ref['control']), close(model['intercept'], ref['intercept'], 1e-08), subset(model['coefficients'], list(ref['coefficients'].values()), tol=1e-08), close(model['training_outcome_mean'], ref['training_outcome_mean']))
    actual = {r['subject_id']: r for r in predictions(info)}
    for row in ref['individual']:
        delta = max(delta, subset(actual[row['subject_id']], row, tol=1e-08))
    metric_map = {r['metric']: r for r in rec['metrics']}
    mapping = {'training_mean_mae': 'comparator_mae', 'training_mean_rmse': 'comparator_rmse'}
    for name, row in metric_map.items():
        key = mapping.get(name, name)
        if key in ref['metrics']:
            if ref['metrics'][key] is None:
                assert row['value'] is None and row['reason_code']
            else:
                metrics_delta = max(metrics_delta, close(row['value'], ref['metrics'][key]))
    assert rec['cv']['weighting'] == 'validation_subject_count' and rec['cv']['scope'] == 'training_only_tuning'
    assert rec['diagnostics']['n_engine_fits'] == len(ref['folds']) + 1 and rec['diagnostics']['warning_count'] == 0 and (rec['diagnostics']['jerr'] == 0)
    for a, b in zip(rec['cv']['folds'], ref['folds']):
        for key in ('fold', 'n_training', 'n_validation'):
            assert a[key] == b[key]
        assert a['n_encoded_columns'] == len(b['preprocessor']['retained']) and a['n_dropped_columns'] == len(b['preprocessor']['dropped'])
    for k, engine in enumerate(rec['cv']['fold_losses']):
        assert abs(engine['engine_lambda'] - engine['lambda']) <= 32 * sys.float_info.epsilon * abs(engine['lambda'])
    return {'max_glm_difference': delta, 'max_reference_metric_difference': metrics_delta, 'selected_lambda': rec['selected_lambda'], 'n_training': len(ref['training_subject_ids'])}