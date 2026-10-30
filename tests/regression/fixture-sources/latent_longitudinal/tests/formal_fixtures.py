def request(kind='profile', random='none', degree=1, k=(1, 2), seed=13):
    rng = np.random.default_rng(seed)
    rows = []
    if kind == 'profile':
        for i in range(144):
            c = i % 2
            x = rng.normal(-3 if c == 0 else 3, 0.5, 3)
            rows.append({'sid': f'synthetic_profile_{i}', 'v1': float(x[0]), 'v2': float(x[1]), 'v3': float(x[2]), 'split': 'train' if i < 120 else 'holdout'})
        definition = {'indicators': [{'name': 'v' + str(i), 'unit': 'score'} for i in range(1, 4)], 'covariance_model': 'VVI', 'missing': 'complete_case'}
        mid = 'latent.profile.gaussian'
    else:
        for i in range(96):
            c = i % 2
            b = rng.normal(0, 0.55) if random != 'none' else 0
            slope = rng.normal(0, 0.2) if random == 'intercept_slope' else 0
            for t in [0.0, 0.6, 1.7, 2.8, 4.0]:
                y = (-3 + 0.6 * t if c == 0 else 3 - 0.4 * t) + b + slope * t + (0.15 * t * t if degree == 2 else 0) + rng.normal(0, 0.3)
                rows.append({'sid': f'synthetic_trajectory_{i}', 'time': t, 'y': float(y), 'split': 'train' if i < 80 else 'holdout'})
        definition = {'family': 'lcga' if random == 'none' else 'growth_mixture', 'time': {'name': 'time', 'unit': 'month', 'origin': 0.0, 'scale': 1.0}, 'outcome': {'name': 'y', 'unit': 'score'}, 'degree': degree, 'random': random, 'missing': 'observed_likelihood_mar'}
        mid = 'latent.trajectory.gaussian'
    spec = {'subject_id': 'sid', 'cohort_id': 'synthetic_development', 'definition': definition, 'candidate_k': list(k), 'seed': 730, 'starts': 20, 'split': {'field': 'split', 'train': 'train', 'holdout': 'holdout'}, 'controls': {'max_iter': 400, 'tol': 1e-06, 'stability_reps': 5, 'min_class_n': 5, 'min_class_fraction': 0.05}}
    return {'method_id': mid, 'operation': 'train', 'spec': spec, 'rows': rows}

def envelope(local, work):
    s = copy.deepcopy(local['spec'])
    profile = local['method_id'] == 'latent.profile.gaussian'
    op = local['operation']
    d = s['definition']
    fields = [{'name': s['subject_id'], 'dtype': 'id', 'role': 'subject_id', 'unit': '1', 'measured_at': None, 'available_at': None}]
    if op == 'train':
        fields.append({'name': s['split']['field'], 'dtype': 'category', 'role': 'partition', 'unit': '1', 'measured_at': None, 'available_at': None})
    if profile:
        for f in d['indicators']:
            fields.append({**f, 'dtype': 'number', 'role': 'indicator', 'measured_at': 0.0, 'available_at': 0.0})
        time = {'unit': None, 'origin': None, 'scale': None, 'measurement_time_field': None, 'availability': 'declared_per_field'}
        keys = [s['subject_id']]
    else:
        for f, role in [(d['time'], 'time'), (d['outcome'], 'outcome')]:
            fields.append({'name': f['name'], 'unit': f['unit'], 'dtype': 'number', 'role': role, 'measured_at': 'row_time', 'available_at': 'row_time'})
        time = {k: d['time'][k] for k in ['unit', 'origin', 'scale']} | {'measurement_time_field': d['time']['name'], 'availability': 'row_time'}
        keys = [s['subject_id'], d['time']['name']]
    names = {f['name'] for f in fields}
    rows = [{k: v for k, v in row.items() if k in names} for row in local['rows']]
    p = {'spec': s, 'semantics': {'grain': 'subject' if profile else 'subject_time', 'subject_key': s['subject_id'], 'record_keys': keys, 'group_key': None, 'independence': 'independent_subjects', 'event_coding': None, 'fields': fields, 'time': time, 'weights': {'kind': 'none', 'field': None}, 'missing_policy': d['missing']}, 'data': rows, 'test_only': True, 'model_ref': local.get('model_ref'), 'work_dir': str(work)}
    return {'api_version': 'clinical-module-request@1.0', 'method_id': local['method_id'], 'operation': op, 'payload': p, 'bindings': {'input_sha256': digest(rows), 'plan_sha256': digest(s), 'code_sha256': 'a' * 64, 'runtime_sha256': 'b' * 64, 'model_sha256': local.get('model_ref', {}).get('sha256')}}