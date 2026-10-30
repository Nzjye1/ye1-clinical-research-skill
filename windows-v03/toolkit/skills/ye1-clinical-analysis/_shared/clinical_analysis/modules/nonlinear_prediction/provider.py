"""Bounded binary tree provider. All common evaluation belongs to the frozen core.

Native sklearn owns training and sigmoid calibration. JSON tree traversal owns only
safe reload inference and is checked against the native estimator at each fit.
No pickle, external I/O, data acquisition, or causal/clinical-effect interpretation.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import math
import os
from pathlib import Path
import platform
import sys
import warnings

import numpy as np
from scipy.special import expit
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import log_loss
from sklearn.model_selection import GroupKFold, StratifiedKFold, TimeSeriesSplit
from threadpoolctl import threadpool_limits

MODULE_ROOT = Path(__file__).resolve().parent
CORE_ROOT = Path(os.environ.get('CLINICAL_CORE_ROOT', str(MODULE_ROOT.parents[1] / 'integration' / 'core'))).resolve()
sys.path.insert(0, str(CORE_ROOT / 'python'))
from clinical_methods import prediction as common
from clinical_methods import prediction_bridge as common_bridge

VERSION = 'clinical-nonlinear-prediction/1.0.0-module'
METHODS = {'prediction.binary.random_forest': 'random_forest',
           'prediction.binary.hist_gradient_boosting': 'hist_gradient_boosting'}
Blocked = common.PredictionBlocked
need = common._need
MIN_TRAIN = 40
MIN_TRAIN_CLASS = 10
LIMITATIONS = [
    'SYNTHETIC_TEST_ONLY; scientific_review=pending; outputs remain local_only.',
    'Inner CV selects hyperparameters only. Its winning score is not unbiased validation; final metrics use the untouched outer holdout.',
    'The calibration subset is separated before tuning. The base model is not refitted on calibration or holdout records.',
    'Fixed engineering sample/leaf bounds do not establish sample adequacy or clinical usefulness; coefficient EPV does not apply to trees.',
    'Predictor timing, outcome maturity, patient independence and external source independence require substantive review.',
    'Permutation importance and partial dependence describe model behavior, not causal effects; correlated predictors can distort both.',
    'SHAP is unavailable and is never approximated by feature importance.',
]


def runtime():
    return {'python': platform.python_version(), **{p: importlib.metadata.version('scikit-learn' if p == 'sklearn' else p)
            for p in ('numpy', 'scipy', 'statsmodels', 'sklearn', 'pandas')}}


def provider_version():
    files = [MODULE_ROOT / n for n in ('provider.py', 'adapter.py', 'contracts.py', 'interface.py')]
    files += sorted((MODULE_ROOT / 'schemas').glob('*.json'))
    files += [Path(common.__file__), Path(common_bridge.__file__)]
    return common._digest({str(p.relative_to(MODULE_ROOT)) if p.is_relative_to(MODULE_ROOT) else 'common/' + p.name:
                           hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


def validate_spec(spec, method):
    need(isinstance(spec, dict) and method in METHODS, 'METHOD_OR_SPEC_UNSUPPORTED')
    common._validate_spec(spec)
    need(spec.get('selection', 'none') == 'none', 'NONLINEAR_FEATURE_SELECTION_UNSUPPORTED')
    need(spec.get('missing') == 'train_median_mode', 'NONLINEAR_MISSING_POLICY_UNSUPPORTED')
    need(spec.get('independent_subjects') is True, 'INDEPENDENT_SUBJECTS_REQUIRED')
    need(1 <= len(spec['features']) <= 30, 'NONLINEAR_FEATURE_LIMIT')
    folds = spec.get('cv_folds')
    need(type(folds) is int and 2 <= folds <= 5, 'CV_FOLDS_INVALID')
    need(type(spec.get('bootstrap')) is int and (spec['bootstrap'] == 0 or 50 <= spec['bootstrap'] <= 100), 'BOOTSTRAP_REPS_INVALID')
    cal = spec.get('calibration')
    need(isinstance(cal, dict) and set(cal) == {'method', 'fraction'} and cal['method'] in {'none', 'sigmoid'}, 'CALIBRATION_POLICY_INVALID')
    need((cal['method'] == 'none' and cal['fraction'] is None) or
         (cal['method'] == 'sigmoid' and type(cal['fraction']) in (int, float) and .2 <= cal['fraction'] <= .4), 'CALIBRATION_FRACTION_INVALID')
    tuning = spec.get('tuning')
    need(isinstance(tuning, dict) and set(tuning) == {'metric', 'candidates'} and tuning['metric'] == 'log_loss', 'TUNING_POLICY_INVALID')
    candidates = tuning['candidates']
    need(isinstance(candidates, list) and 1 <= len(candidates) <= 8, 'TUNING_CANDIDATES_INVALID')
    need(len({common._digest(c) for c in candidates}) == len(candidates), 'DUPLICATE_TUNING_CANDIDATES')
    for params in candidates:
        validate_params(params, METHODS[method])
    explanation = spec.get('explanation', {'permutation_repeats': 0, 'pdp_features': []})
    need(isinstance(explanation, dict) and set(explanation) == {'permutation_repeats', 'pdp_features'}, 'EXPLANATION_POLICY_INVALID_OR_SHAP_UNAVAILABLE')
    need(type(explanation['permutation_repeats']) is int and 0 <= explanation['permutation_repeats'] <= 20, 'PERMUTATION_REPEATS_INVALID')
    names = [f['name'] for f in spec['features']]
    pdp = explanation['pdp_features']
    need(isinstance(pdp, list) and len(pdp) <= 5 and len(set(pdp)) == len(pdp) and set(pdp) <= set(names), 'PDP_FEATURES_INVALID')
    allowed = {'id', 'outcome', 'event', 'non_event', 'cohort_id', 'prediction_time', 'outcome_window', 'features', 'split',
               'missing', 'selection', 'independent_subjects', 'cv_folds', 'bootstrap', 'evaluation_seed', 'dca_thresholds',
               'clinical_decision_threshold', 'calibration', 'tuning', 'explanation', 'post_outcome_fields'}
    need(set(spec) <= allowed, 'NONLINEAR_UNKNOWN_OPTION')
    thresholds, _ = common._threshold_policy(spec)
    need(bool(thresholds) and thresholds == sorted(thresholds), 'DCA_THRESHOLDS_INVALID')


def validate_params(params, kind):
    need(isinstance(params, dict), 'CANDIDATE_INVALID')
    expected = {'n_estimators', 'max_depth', 'min_samples_leaf', 'max_features'} if kind == 'random_forest' else {
        'max_iter', 'max_leaf_nodes', 'min_samples_leaf', 'learning_rate', 'l2_regularization'}
    need(set(params) == expected, 'CANDIDATE_KEYS_INVALID')
    bounds = {'n_estimators': (20, 300), 'max_depth': (1, 8), 'min_samples_leaf': (5, 100),
              'max_iter': (20, 300), 'max_leaf_nodes': (2, 15)}
    for k, (lo, hi) in bounds.items():
        if k in params:
            need(type(params[k]) is int and lo <= params[k] <= hi, 'CANDIDATE_INTEGER_BOUND_INVALID')
    if kind == 'random_forest':
        need(params['max_features'] in ('sqrt', 'log2', 1.0) and type(params['max_features']) in (str, float), 'MAX_FEATURES_INVALID')
    else:
        need(type(params['learning_rate']) in (float, int) and .01 <= params['learning_rate'] <= .3, 'LEARNING_RATE_INVALID')
        need(type(params['l2_regularization']) in (float, int) and 0 <= params['l2_regularization'] <= 100, 'L2_INVALID')


def class_counts(rows):
    events = sum(r['_ye1_outcome'] for r in rows)
    return {'n': len(rows), 'events': events, 'nonevents': len(rows) - events}


def fold_indices(rows, spec):
    """CV orchestration only; common ridge's _cv does not expose a generic iterator."""
    y = np.array([r['_ye1_outcome'] for r in rows])
    k = spec['cv_folds']; split = spec['split']; method = split['method']
    if method == 'group':
        groups = [str(r[split['group']]) for r in rows]
        need(len(set(groups)) >= k, 'CV_GROUPS_INSUFFICIENT')
        pairs = list(GroupKFold(k).split(np.zeros(len(rows)), y, groups))
    elif method == 'temporal':
        times = common._times([r[split['time']] for r in rows]); unique = sorted(set(times))
        need(len(unique) > k, 'CV_TIMES_INSUFFICIENT')
        pairs = []
        for a, b in TimeSeriesSplit(k).split(unique):
            ta = {unique[int(i)] for i in a}; tb = {unique[int(i)] for i in b}
            pairs.append(([i for i, t in enumerate(times) if t in ta], [i for i, t in enumerate(times) if t in tb]))
    else:
        need(len(set(y)) == 2 and min(np.bincount(y)) >= k, 'CV_CLASSES_INSUFFICIENT')
        pairs = list(StratifiedKFold(k, shuffle=True, random_state=split['seed']).split(np.zeros(len(rows)), y))
    for a, b in pairs:
        common._temporal_label_check(rows, spec, a, b)
        if method == 'group':
            need({groups[int(i)] for i in a}.isdisjoint(groups[int(i)] for i in b), 'CV_GROUP_OVERLAP')
    return [(list(map(int, a)), list(map(int, b))) for a, b in pairs]


def fit_native(rows, spec, kind, params):
    counts = class_counts(rows)
    need(counts['n'] >= MIN_TRAIN and min(counts['events'], counts['nonevents']) >= MIN_TRAIN_CLASS, 'NONLINEAR_TRAINING_SAMPLE_GUARD')
    transforms = common._preprocess_fit(rows, spec['features'])
    x, names = common._transform(rows, transforms)
    need(len(names) <= 80, 'NONLINEAR_ENCODED_FEATURE_LIMIT')
    y = np.array([r['_ye1_outcome'] for r in rows])
    if kind == 'random_forest':
        model = RandomForestClassifier(**params, random_state=spec['split']['seed'], n_jobs=1)
    else:
        model = HistGradientBoostingClassifier(**params, random_state=spec['split']['seed'],
                                              early_stopping=False, categorical_features=None)
    with threadpool_limits(limits=1):
        model.fit(x, y)
    need(list(model.classes_) == [0, 1], 'MODEL_CLASS_ORDER_INVALID')
    return model, transforms, names


def export_native(native, kind, transforms, names):
    trees = []
    if kind == 'random_forest':
        for est in native.estimators_:
            t = est.tree_
            leaf = t.children_left == -1
            values = t.value[:, 0, :]
            probabilities = values[:, 1] / values.sum(axis=1)
            trees.append({'left': t.children_left.tolist(), 'right': t.children_right.tolist(), 'feature': t.feature.tolist(),
                          'threshold': t.threshold.tolist(), 'leaf': leaf.tolist(), 'value': probabilities.tolist()})
        baseline = None
    else:
        need(native.n_trees_per_iteration_ == 1, 'BINARY_TREE_LAYOUT_REQUIRED')
        for iteration in native._predictors:
            nodes = iteration[0].nodes
            need(not nodes['is_categorical'].any(), 'CATEGORICAL_NATIVE_TREE_UNSUPPORTED')
            trees.append({'left': nodes['left'].tolist(), 'right': nodes['right'].tolist(), 'feature': nodes['feature_idx'].tolist(),
                          'threshold': nodes['num_threshold'].tolist(), 'leaf': nodes['is_leaf'].astype(bool).tolist(),
                          'value': nodes['value'].tolist()})
        baseline = float(native._baseline_prediction[0, 0])
    return {'kind': kind, 'trees': trees, 'baseline': baseline, 'transforms': transforms, 'feature_names': names,
            'input_dtype': 'float32' if kind == 'random_forest' else 'float64', 'calibration': {'method': 'none'}}


def check_model(model):
    need(isinstance(model, dict) and set(model) == {'kind', 'trees', 'baseline', 'transforms', 'feature_names', 'input_dtype', 'calibration'}, 'FROZEN_MODEL_LAYOUT_INVALID')
    need(model.get('kind') in METHODS.values() and 1 <= len(model.get('trees', [])) <= 300, 'FROZEN_TREE_LAYOUT_INVALID')
    need(model['input_dtype'] == ('float32' if model['kind'] == 'random_forest' else 'float64'), 'FROZEN_INPUT_DTYPE_INVALID')
    need((model['kind'] == 'random_forest' and model['baseline'] is None) or
         (model['kind'] == 'hist_gradient_boosting' and type(model['baseline']) in (float, int) and math.isfinite(model['baseline'])), 'FROZEN_BASELINE_INVALID')
    cal = model['calibration']
    need(cal.get('method') in {'none', 'sigmoid'}, 'FROZEN_CALIBRATION_INVALID')
    if cal['method'] == 'sigmoid':
        need(all(type(cal.get(k)) in (int, float) and math.isfinite(cal[k]) for k in ('a', 'b')),
             'FROZEN_CALIBRATION_INVALID')
        need(cal.get('score') == ('probability' if model['kind'] == 'random_forest' else 'raw_margin'), 'FROZEN_CALIBRATION_SCORE_INVALID')
    nfeatures = len(model['feature_names'])
    for trans in model['transforms']:
        expected = {'name','type','impute','mean','scale'} if trans.get('type') == 'number' else {'name','type','impute','levels'}
        need(set(trans) == expected and trans['type'] in {'number','category'}, 'FROZEN_TRANSFORM_LAYOUT_INVALID')
    for t in model['trees']:
        need(set(t) == {'left','right','feature','threshold','leaf','value'}, 'FROZEN_TREE_UNKNOWN_FIELD')
        n = len(t['left'])
        need(1 <= n <= 10000 and all(len(t[k]) == n for k in ('right', 'feature', 'threshold', 'leaf', 'value')), 'FROZEN_TREE_LAYOUT_INVALID')
        visited = set(); stack = [0]
        while stack:
            node = stack.pop()
            need(type(node) is int and 0 <= node < n and node not in visited, 'FROZEN_TREE_GRAPH_INVALID')
            visited.add(node)
            need(type(t['leaf'][node]) is bool and math.isfinite(t['value'][node]), 'FROZEN_TREE_VALUE_INVALID')
            if not t['leaf'][node]:
                need(type(t['feature'][node]) is int and 0 <= t['feature'][node] < nfeatures and math.isfinite(t['threshold'][node]), 'FROZEN_TREE_FEATURE_INVALID')
                stack.extend((t['left'][node], t['right'][node]))
            if model['kind'] == 'random_forest':
                need(0 <= t['value'][node] <= 1, 'FROZEN_TREE_PROBABILITY_INVALID')
        need(len(visited) == n, 'FROZEN_TREE_UNREACHABLE_NODE')


def scores(rows, model):
    x, names = common._transform(rows, model['transforms'])
    need(names == model['feature_names'], 'FROZEN_DESIGN_MISMATCH')
    x = x.astype(model['input_dtype'])
    need(np.isfinite(x).all(), 'NONFINITE_TREE_INPUT')
    score = np.zeros(len(rows), dtype=float)
    for t in model['trees']:
        index = np.zeros(len(rows), dtype=int)
        leaf = np.asarray(t['leaf'], dtype=bool)
        left = np.asarray(t['left']); right = np.asarray(t['right']); feature = np.asarray(t['feature']); threshold = np.asarray(t['threshold'])
        active = ~leaf[index]
        steps = 0
        while active.any():
            positions = np.flatnonzero(active); node = index[positions]
            index[positions] = np.where(x[positions, feature[node]] <= threshold[node], left[node], right[node])
            active = ~leaf[index]; steps += 1
            need(steps <= len(leaf), 'FROZEN_TREE_GRAPH_INVALID')
        score += np.asarray(t['value'])[index]
    if model['kind'] == 'random_forest':
        score /= len(model['trees'])
    else:
        score += model['baseline']
    return score


def predict(rows, model):
    score = scores(rows, model)
    cal = model['calibration']
    p = expit(-(cal['a'] * score + cal['b'])) if cal['method'] == 'sigmoid' else (
        score if model['kind'] == 'random_forest' else expit(score))
    need(np.isfinite(p).all() and np.all((p >= 0) & (p <= 1)), 'NONFINITE_PREDICTION')
    return p


def train(data, counts, spec, method):
    train_ix, holdout_ix = common._split(data, spec)
    training = [data[i] for i in train_ix]; holdout = [data[i] for i in holdout_ix]
    for prefix, part in [('training', training), ('holdout', holdout)]:
        counts.update({prefix + '_' + k: v for k, v in class_counts(part).items()})
    record = {'status': 'BLOCKED_ESTIMATION', 'counts': counts, 'metrics': None, 'internal_cv': None,
              'candidate_parameter_count': None, 'predictor_parameter_count': None, 'epv': None,
              'validation': 'internal held-out ' + spec['split']['method'], 'limitations': list(LIMITATIONS)}
    try:
        if spec['calibration']['method'] == 'sigmoid':
            split_spec = copy.deepcopy(spec)
            split_spec['split']['test_fraction'] = spec['calibration']['fraction']
            split_spec['split']['seed'] = (spec['split']['seed'] + 1871) % (2**32)
            fit_ix, cal_ix = common._split(training, split_spec)
        else:
            fit_ix, cal_ix = list(range(len(training))), []
        fit_rows = [training[i] for i in fit_ix]; cal_rows = [training[i] for i in cal_ix]
        for prefix, part in [('model_fit', fit_rows), ('calibration', cal_rows)]:
            counts.update({prefix + '_' + k: v for k, v in class_counts(part).items()})
        if cal_rows:
            need(min(class_counts(cal_rows)[k] for k in ('events', 'nonevents')) >= 10, 'CALIBRATION_REQUIRES_10_PER_CLASS')
        folds = fold_indices(fit_rows, spec)
        candidates = []; kind = METHODS[method]
        for cindex, params in enumerate(spec['tuning']['candidates']):
            fold_results = []
            for a, b in folds:
                tr = [fit_rows[i] for i in a]; va = [fit_rows[i] for i in b]
                need(min(class_counts(va)[k] for k in ('events', 'nonevents')) >= 5, 'CV_VALIDATION_REQUIRES_5_PER_CLASS')
                native, transforms, _ = fit_native(tr, spec, kind, params)
                x, _ = common._transform(va, transforms)
                with threadpool_limits(limits=1):
                    p = native.predict_proba(x)[:, 1]
                loss = float(log_loss([r['_ye1_outcome'] for r in va], p, labels=[0, 1]))
                fold_results.append({'training_n': len(tr), 'validation_n': len(va), 'log_loss': loss})
            mean_loss = float(np.average([f['log_loss'] for f in fold_results], weights=[f['validation_n'] for f in fold_results]))
            candidates.append({'candidate_index': cindex, 'parameters': copy.deepcopy(params), 'weighted_log_loss': mean_loss, 'folds': fold_results})
        chosen = min(candidates, key=lambda c: (c['weighted_log_loss'], c['candidate_index']))
        native, transforms, names = fit_native(fit_rows, spec, kind, chosen['parameters'])
        model = export_native(native, kind, transforms, names)
        check_model(model)
        xfit, _ = common._transform(fit_rows, transforms)
        with threadpool_limits(limits=1):
            native_fit_p = native.predict_proba(xfit)[:, 1]
        difference = float(np.max(np.abs(predict(fit_rows, model) - native_fit_p)))
        need(difference <= 1e-12, 'FROZEN_PREDICTION_REFERENCE_MISMATCH')
        if cal_rows:
            xc, _ = common._transform(cal_rows, transforms)
            yc = [r['_ye1_outcome'] for r in cal_rows]
            calibrated = CalibratedClassifierCV(FrozenEstimator(native), method='sigmoid')
            with threadpool_limits(limits=1):
                calibrated.fit(xc, yc)
                native_p = calibrated.predict_proba(xfit)[:, 1]
            native_cal = calibrated.calibrated_classifiers_[0].calibrators[0]
            model['calibration'] = {'method': 'sigmoid', 'a': float(native_cal.a_), 'b': float(native_cal.b_),
                                    'score': 'probability' if kind == 'random_forest' else 'raw_margin',
                                    'owner': 'sklearn.CalibratedClassifierCV(FrozenEstimator)', 'fit_scope': 'disjoint_calibration_subset'}
            difference = max(difference, float(np.max(np.abs(predict(fit_rows, model) - native_p))))
            need(difference <= 1e-12, 'FROZEN_CALIBRATION_REFERENCE_MISMATCH')
        counts['prediction_n'] = len(data); counts['evaluation_n'] = len(holdout)
        metrics = common._metrics(holdout, predict(holdout, model), spec)
        cv = {'status': 'ESTIMATED', 'folds': spec['cv_folds'], 'tuning_metric': 'weighted_log_loss', 'candidates': candidates,
              'selected_candidate_index': chosen['candidate_index'], 'tie_break': 'first_prespecified_candidate',
              'scope': 'base-model fitting subset only; excludes calibration and final holdout; transforms refitted inside every fold',
              'performance_role': 'selection_diagnostic_not_unbiased_validation'}
        record.update(status='ESTIMATED', metrics=metrics, internal_cv=cv,
                      diagnostics={'transformed_feature_count': len(names), 'epv_status': 'NOT_DEFINED_FOR_TREE_MODELS',
                                   'calibration': {'method': spec['calibration']['method'], 'sample': class_counts(cal_rows)},
                                   'native_freeze_max_abs_difference': difference, 'early_stopping': False,
                                   'selected_parameters': chosen['parameters']})
        partitions = {'model_fit': [train_ix[i] for i in fit_ix], 'calibration': [train_ix[i] for i in cal_ix], 'holdout': holdout_ix}
        return record, model, partitions
    except Blocked as exc:
        record['reason'] = record['reason_code'] = str(exc)
        return record, None, {}


def explain(rows, model, spec, *, label_available, grids):
    policy = spec.get('explanation', {'permutation_repeats': 0, 'pdp_features': []})
    result = {'method': 'permutation_importance_and_partial_dependence', 'shap_status': 'UNAVAILABLE_NOT_REQUESTED',
              'evaluation_n': len(rows), 'model_refitted': False, 'permutation': [], 'partial_dependence': [],
              'scope': 'descriptive frozen-model audit only; must not be used to reselect this model',
              'limitations': ['Permutation destroys marginal feature relationships and may be misleading with correlated predictors.',
                              'PDP averages predictions under feature substitution; correlated-feature combinations may lack support. No causal effect or local attribution is estimated.',
                              'Permutation repeat SD describes Monte Carlo variation, not a confidence interval.']}
    if label_available and policy['permutation_repeats']:
        y = [r['_ye1_outcome'] for r in rows]
        base = float(log_loss(y, predict(rows, model), labels=[0, 1]))
        rng = np.random.default_rng(spec.get('evaluation_seed', 1729))
        for f in spec['features']:
            delta = []
            for _ in range(policy['permutation_repeats']):
                order = rng.permutation(len(rows))
                permuted = [dict(row, **{f['name']: rows[int(order[i])][f['name']]}) for i, row in enumerate(rows)]
                delta.append(float(log_loss(y, predict(permuted, model), labels=[0, 1])) - base)
            result['permutation'].append({'feature': f['name'], 'increase_in_log_loss_mean': float(np.mean(delta)),
                                          'repeat_sd': float(np.std(delta)), 'repeats': len(delta)})
    for name in policy['pdp_features']:
        for value in grids[name]:
            replaced = [dict(row, **{name: value}) for row in rows]
            result['partial_dependence'].append({'feature': name, 'value': value,
                'mean_probability': float(np.mean(predict(replaced, model))), 'n': len(rows), 'grid_source': 'frozen_model_fit_predictors'})
    return result
