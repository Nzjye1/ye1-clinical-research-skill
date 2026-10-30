def model_spec(kind, covariates):
    return {'model': kind, 'outcome': 'binary' if kind == 'logistic' else 'y', 'exposure': 'x', 'covariates': covariates, 'missing': 'complete_case', 'covariance': 'model' if kind == 'logistic' else 'HC3', 'categorical': {}, 'row_unit': 'subject', 'independent': True, 'key': ['id'], 'subject_id': 'id', 'sensitivity': [], **({'event': '1', 'non_event': '0'} if kind == 'logistic' else {})}

def model_entry(kind, model_id, role, covariates, where=None):
    return {'model_id': model_id, 'label': model_id, 'rationale': 'Prespecified synthetic acceptance model; no data-driven selection', 'role': role, 'where': where or [], 'spec': model_spec(kind, covariates), 'curve': None, 'subgroup_min_n': None}

def make_plan(kind, scenario='sequence', strategy='per_model_complete_case'):
    if scenario == 'sequence':
        models = [model_entry(kind, 'primary', 'primary', []), model_entry(kind, 'adjusted', 'adjustment', ['z']), model_entry(kind, 'restricted', 'sensitivity', ['z'], [{'field': 'group', 'op': 'eq', 'value': 'A'}])]
    elif scenario == 'rcs':
        models = [model_entry(kind, 'linear', 'primary', ['z']), model_entry(kind, 'spline', 'adjustment', ['z'])]
        models[1]['spec']['nonlinear'] = {'method': 'restricted_cubic', 'knots': [-2.0, 0.0, 2.0]}
        models[1]['curve'] = {'reference': 0.0, 'grid': [-2.0, -1.0, 0.0, 1.0, 2.0], 'domain': [-2.0, 2.0]}
    elif scenario == 'subgroup':
        models = [model_entry(kind, 'interaction', 'primary', ['z'])]
        models[0]['spec']['subgroup'] = {'field': 'group', 'levels': ['A', 'B'], 'reference': 'A'}
        models[0]['subgroup_min_n'] = 30
    else:
        raise ValueError('unknown synthetic scenario')
    return {'sample_strategy': strategy, 'multiplicity': 'unadjusted_prespecified', 'models': models}
