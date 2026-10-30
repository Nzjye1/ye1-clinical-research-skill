def cluster_request(method='exploration.cluster.kmeans', seed=20261024):
    rng = np.random.default_rng(seed)
    rows = []
    for partition, count in [('train', 60), ('holdout', 12)]:
        for group, center in enumerate([[-3.0, -2.0], [3.0, 2.0]]):
            for j in range(count):
                x = rng.normal(center, [0.42, 0.55])
                rows.append({'sid': f's_{partition}_{group}_{j}', 'partition': partition, 'marker_a': float(x[0]), 'marker_b': float(x[1])})
    return {'schema_version': VERSION, 'method_id': method, 'operation': 'train', 'test_only': True, 'spec': {'subject_id': 'sid', 'cohort_id': 'synthetic_A', 'features': [{'name': 'marker_a', 'unit': 'mg/L'}, {'name': 'marker_b', 'unit': 'score'}], 'missing': 'train_median', 'candidate_k': [2, 3] if method.endswith('kmeans') else [1, 2, 3], 'selection': 'silhouette' if method.endswith('kmeans') else 'bic', 'seed': 42, 'starts': 4, 'max_iter': 400, 'tol': 1e-06, 'stability_reps': 6, 'min_class_n': 5, 'min_class_fraction': 0.05, 'covariance': 'none' if method.endswith('kmeans') else 'full', 'split': {'field': 'partition', 'train': 'train', 'holdout': 'holdout'}}, 'rows': rows}

def growth_request(seed=271828, random='intercept_slope', degree=1):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(60):
        intercept, slope = rng.multivariate_normal([0, 0], [[2.0, 0.22], [0.22, 0.35]])
        for t in [0.0, 0.7, 1.5, 2.4, 3.6, 5.0]:
            cov = float(rng.normal())
            y = 5 + 0.9 * t + (0.12 * t * t if degree == 2 else 0) + 0.4 * cov + intercept
            if random == 'intercept_slope':
                y += slope * t
            y += rng.normal(0, 0.65)
            rows.append({'sid': f'g_{i}', 'time_day': t, 'score': float(y), 'covariate': cov})
    return {'schema_version': VERSION, 'method_id': 'longitudinal.growth.gaussian', 'operation': 'train', 'test_only': True, 'rows': rows, 'spec': {'subject_id': 'sid', 'cohort_id': 'synthetic_growth_A', 'time': {'name': 'time_day', 'unit': 'day', 'origin': 0.0, 'scale': 1.0}, 'outcome': {'name': 'score', 'unit': 'score'}, 'covariates': [{'name': 'covariate', 'unit': 'score'}], 'degree': degree, 'random': random, 'estimation': 'ML', 'correlation': 'independent', 'missing': 'complete_case_rows', 'seed': 13, 'max_iter': 300}}