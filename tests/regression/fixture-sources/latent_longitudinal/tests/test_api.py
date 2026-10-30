def make_request(local, work):
    s = local['spec']
    method = local['method_id']
    operation = local['operation']
    rows = copy.deepcopy(local['rows'])
    fields = [{'name': s['subject_id'], 'dtype': 'id', 'role': 'subject_id', 'unit': '1', 'measured_at': None, 'available_at': None}]
    long = method in {'longitudinal.growth.gaussian', 'latent.trajectory.gaussian'}
    if not long:
        selected = s['features'] if method.startswith('exploration.') else s['definition']['indicators']
        for f in selected:
            fields.append({**f, 'dtype': 'number', 'role': 'indicator', 'measured_at': 0.0, 'available_at': 0.0})
        if method.startswith('exploration.') and operation == 'train':
            fields.append({'name': s['split']['field'], 'dtype': 'category', 'role': 'partition', 'unit': '1', 'measured_at': None, 'available_at': None})
        time = {'unit': None, 'origin': None, 'scale': None, 'measurement_time_field': None, 'availability': 'declared_per_field'}
        keys = [s['subject_id']]
    else:
        d = s if method == 'longitudinal.growth.gaussian' else s['definition']
        selected = [({k: v for k, v in d['time'].items() if k in ['name', 'unit']}, 'time')]
        if operation == 'train' or method == 'latent.trajectory.gaussian':
            selected.append((d['outcome'], 'outcome'))
        selected += [(f, 'covariate') for f in d.get('covariates', [])]
        for f, role in selected:
            fields.append({**f, 'dtype': 'number', 'role': role, 'measured_at': 'row_time', 'available_at': 'row_time'})
        time = {'unit': d['time']['unit'], 'origin': d['time'].get('origin', 0), 'scale': d['time'].get('scale', 1), 'measurement_time_field': d['time']['name'], 'availability': 'row_time'}
        keys = [s['subject_id'], d['time']['name']]
    allowed = {f['name'] for f in fields}
    rows = [{k: v for k, v in row.items() if k in allowed} for row in rows]
    payload = {'spec': copy.deepcopy(s), 'semantics': {'grain': 'subject_time' if long else 'subject', 'subject_key': s['subject_id'], 'record_keys': keys, 'group_key': None, 'independence': 'independent_subjects', 'event_coding': None, 'fields': fields, 'time': time, 'weights': {'kind': 'none', 'field': None}, 'missing_policy': s.get('missing', s.get('definition', {}).get('missing'))}, 'data': rows, 'test_only': True, 'model_ref': local.get('model_ref'), 'work_dir': str(work)}
    return {'api_version': 'clinical-module-request@1.0', 'method_id': method, 'operation': operation, 'payload': payload, 'bindings': {'input_sha256': digest(rows), 'plan_sha256': digest(s), 'code_sha256': digest(module.source_hashes()), 'runtime_sha256': 'b' * 64, 'model_sha256': local.get('model_ref', {}).get('sha256')}}