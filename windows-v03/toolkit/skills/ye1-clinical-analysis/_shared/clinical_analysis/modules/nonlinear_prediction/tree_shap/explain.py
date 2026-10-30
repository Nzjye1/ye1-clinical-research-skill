"""Official TreeExplainer is the sole SHAP numerical owner.

RF trees store positive-class probabilities, HGB stores margin contributions.
Sigmoid calibration is an affine transform ONLY on the explained log-odds scale.
"""
import json
import numpy as np
from scipy.special import expit
from threadpoolctl import threadpool_limits
from .runtime import prediction as p, load_shap
from clinical_methods import resource_budget as budgets


def resource_limits(resource_budget=None, method_id='explanation.binary.random_forest.tree_shap'):
    """Root-admitted limits or finite defaults; never a statistical rule."""
    return (budgets.request_limits({}, method_id) if resource_budget is None else
            budgets.validate_limits(resource_budget, method_id))


def resource_guard(rows, model, background_n, resource_budget=None):
    """Check row, design and tree/background work before design/SHAP allocation."""
    method = 'explanation.binary.' + model['kind'] + '.tree_shap'
    limits = resource_limits(resource_budget, method)
    budgets.check_rows(len(rows), limits)
    width = len(model['feature_names'])
    p.need(1 <= width <= 80, 'SHAP_RESOURCE_BOUND')
    if width > limits['max_design_columns']:
        raise budgets.BudgetError('RESOURCE_DESIGN_BUDGET_EXCEEDED')
    p.need(10 <= background_n <= limits['max_background_rows'], 'SHAP_BACKGROUND_RESOURCE_BOUND')
    input_bytes = len(json.dumps(rows, ensure_ascii=False, allow_nan=False).encode('utf-8')) + background_n * width * 8
    if input_bytes > limits['max_input_bytes']:
        raise budgets.BudgetError('RESOURCE_INPUT_BYTE_BUDGET_EXCEEDED')
    # Conservative work proxy for interventional tree traversal, not runtime.
    work = len(rows) * background_n * sum(len(t['leaf']) for t in model['trees'])
    if work > limits['max_work_units']:
        raise budgets.BudgetError('RESOURCE_WORK_BUDGET_EXCEEDED', {'estimated_work_units': work})
    return limits


def tree_dictionary(model):
    p.check_model(model)
    forest = model['kind'] == 'random_forest'; trees = []
    for tree in model['trees']:
        leaf = np.asarray(tree['leaf'], bool)
        left = np.where(leaf, -1, tree['left']).astype(np.int32)
        right = np.where(leaf, -1, tree['right']).astype(np.int32)
        trees.append({'children_left': left, 'children_right': right,
                      # All inputs are transformed/imputed to finite numbers before
                      # SHAP; missing routing is never invoked or inferred here.
                      'children_default': left.copy(), 'features': np.where(leaf, -1, tree['feature']).astype(np.int32),
                      'thresholds': np.asarray(tree['threshold'], float),
                      'values': np.asarray(tree['value'], float)[:, None] / (len(model['trees']) if forest else 1),
                      # Official SingleTree recomputes covers from supplied background.
                      # These are not original training covers; path-dependent mode is not exposed.
                      'node_sample_weight': np.zeros(len(leaf), dtype=float)})
    return {'trees': trees, 'base_offset': 0. if forest else model['baseline'],
            'input_dtype': np.float32 if forest else np.float64, 'internal_dtype': np.float64,
            'objective': 'binary_crossentropy', 'tree_output': 'probability' if forest else 'log_odds'}


def grouped_columns(model):
    cursor = 0; groups = []
    for trans in model['transforms']:
        n = 1 if trans['type'] == 'number' else len(trans['levels']) - 1
        groups.append((trans['name'], list(range(cursor, cursor+n))))
        cursor += n
    p.need(cursor == len(model['feature_names']), 'SHAP_COLUMN_GROUP_MISMATCH')
    return groups


def equivalent_threshold_bins(model, x, background):
    """Exact featurewise representation, not a learned or approximate model.

    SHAP 0.54.1's interventional C++ Node stores thresholds as float32 even
    when the frozen model's thresholds are float64. For feature j let T_j be
    the sorted unique frozen split thresholds and r_j(z)=# {t in T_j: t<z}.
    For every split t=T_j[k], z<=t iff r_j(z)<=k. All k fit exactly in float32.
    Featurewise mapping commutes with coalition substitution, so this preserves
    every coalition's leaf/prediction, not only the observed full prediction.
    Official TreeExplainer and its additivity check remain enabled and unchanged.
    """
    dictionary = tree_dictionary(model)
    boundaries = [sorted({tree['threshold'][i] for tree in model['trees'] for i, leaf in enumerate(tree['leaf'])
                          if not leaf and tree['feature'][i] == j}) for j in range(x.shape[1])]
    p.need(all(len(t) < 2**24 for t in boundaries), 'SHAP_BIN_EXACT_INTEGER_LIMIT')
    def encode(matrix):
        return np.column_stack([np.searchsorted(t, matrix[:, j], side='left') for j, t in enumerate(boundaries)]).astype(np.float64)
    mapped_x = encode(x); mapped_background = encode(background)
    combined = np.concatenate((x.astype(np.float64), background.astype(np.float64)))
    encoded = np.concatenate((mapped_x, mapped_background))
    for source, tree in zip(model['trees'], dictionary['trees']):
        for i, leaf in enumerate(source['leaf']):
            if leaf:
                continue
            j = source['feature'][i]; threshold = source['threshold'][i]
            rank = int(np.searchsorted(boundaries[j], threshold, side='left'))
            tree['thresholds'][i] = rank
            p.need(np.array_equal(combined[:, j] <= threshold, encoded[:, j] <= rank), 'SHAP_BIN_BRANCH_EQUIVALENCE_FAILED')
    dictionary['input_dtype'] = np.float64
    return dictionary, mapped_x, mapped_background


def explain(rows, positions, model, background, resource_budget=None):
    resource_guard(rows, model, len(background), resource_budget)
    shap = load_shap()
    x, names = p.common._transform(rows, model['transforms'])
    p.need(names == model['feature_names'] and len(set(names)) == len(names), 'SHAP_FEATURE_NAMES_INVALID')
    x = x.astype(model['input_dtype'])
    p.need(len(x) == len(rows) and 1 <= len(names) <= 80, 'SHAP_RESOURCE_BOUND')
    p.need(np.isfinite(x).all() and np.isfinite(background).all(), 'SHAP_NONFINITE_INPUT')
    dictionary, shap_x, shap_background = equivalent_threshold_bins(model, x, background)
    with threadpool_limits(1):
        # Avoid Independent(masker)'s default 100-row downsampling; preserve the
        # exact audited background chosen by capture_training_background.
        masker = shap.maskers.Independent(shap_background, max_samples=len(shap_background))
        explainer = shap.TreeExplainer(dictionary, data=masker, feature_perturbation='interventional', model_output='raw')
        base_values = np.asarray(explainer.expected_value, dtype=float).reshape(-1)
        result = explainer(shap_x, check_additivity=True, approximate=False)
    values = np.asarray(result.values, dtype=float)
    p.need(values.shape == x.shape and len(base_values) == 1 and np.isfinite(values).all(), 'SHAP_OUTPUT_LAYOUT_INVALID')
    base = float(base_values[0]); scores = p.scores(rows, model); probability = p.predict(rows, model)
    dict_scores = np.asarray(explainer.model.predict(shap_x)).reshape(-1)
    prediction_error = float(np.max(np.abs(dict_scores - scores)))
    p.need(prediction_error <= 1e-12, 'SHAP_TREE_PREDICTION_MISMATCH')
    bg_expectation = float(np.mean(explainer.model.predict(shap_background)))
    p.need(abs(base-bg_expectation) <= 1e-12, 'SHAP_BACKGROUND_BASELINE_MISMATCH')
    base_additivity = float(np.max(np.abs(base+values.sum(axis=1)-scores)))
    p.need(base_additivity <= 1e-6, 'SHAP_BASE_ADDITIVITY_MISMATCH')
    calibration = model['calibration']
    if calibration['method'] == 'sigmoid':
        factor = -calibration['a']; offset = -calibration['b']
        scale = 'calibrated_log_odds'
    else:
        factor = 1.; offset = 0.
        scale = 'uncalibrated_probability' if model['kind'] == 'random_forest' else 'uncalibrated_log_odds'
    output_values = factor * values; output_base = factor * base + offset
    explained_score = factor * scores + offset
    reconstructed = output_base + output_values.sum(axis=1)
    output_error = float(np.max(np.abs(reconstructed-explained_score)))
    rebuilt_probability = reconstructed if scale == 'uncalibrated_probability' else expit(reconstructed)
    probability_error = float(np.max(np.abs(rebuilt_probability-probability)))
    p.need(output_error <= 1e-6 and probability_error <= 1e-6, 'SHAP_OUTPUT_RECONSTRUCTION_MISMATCH')
    groups = grouped_columns(model)
    group_values = np.column_stack([output_values[:, columns].sum(axis=1) for _, columns in groups])
    importance = [{'feature': name, 'sum_absolute_contribution': float(np.abs(output_values[:, i]).sum()),
                   'mean_absolute_contribution': float(np.abs(output_values[:, i]).mean()), 'n': len(rows)} for i, name in enumerate(names)]
    aggregated = [{'variable': name, 'encoded_columns': [names[i] for i in columns],
                   'sum_absolute_aggregated_contribution': float(np.abs(group_values[:, j]).sum()),
                   'mean_absolute_aggregated_contribution': float(np.abs(group_values[:, j]).mean()), 'n': len(rows),
                   'interpretation': 'sum_of_encoded_column_SHAP_not_group_Shapley'} for j, (name, columns) in enumerate(groups)]
    public = {'status': 'EXPLAINED', 'algorithm': 'official_shap.TreeExplainer', 'feature_perturbation': 'interventional',
              'output_scale': scale, 'base_value': output_base, 'n_explained': len(rows), 'n_background': len(background),
              'encoded_importance': importance, 'variable_aggregates': aggregated,
              'importance_definition': 'sum(abs(contribution))/n_explained; descriptive attribution, not a confidence interval',
              'limitations': ['SYNTHETIC_TEST_ONLY; scientific_review=pending; local_only.',
                'Reference distribution is the frozen sampled base-model fitting subset, not a population or causal estimand.',
                'Interventional encoded-feature coalitions can break correlated or one-hot feature relationships; aggregated columns are not grouped Shapley values.',
                'RF uncalibrated output is probability; HGB uncalibrated output is log odds. Sigmoid-calibrated models are explained on calibrated log odds only.',
                'Calibration probabilities are reconstructed from the complete sum; individual values are not probability-point contributions.',
                'No support for arbitrary estimators, multiclass, survival, isotonic calibration, causal explanations or SHAP interaction values.']}
    individual = [{'row_index': positions[i], 'prediction': float(probability[i]), 'base_score': float(scores[i]),
                   'explained_output': float(explained_score[i]), 'base_score_shap': values[i].tolist(),
                   'contributions': output_values[i].tolist(), 'variable_aggregates': group_values[i].tolist(),
                   'encoded_values': x[i].astype(float).tolist()} for i in range(len(rows))]
    private = {'individual': individual, 'encoded_features': names, 'variables': [name for name, _ in groups],
               'base_score_expected_value': base}
    numerics = {'frozen_prediction_max_abs_error': prediction_error, 'base_additivity_max_abs_error': base_additivity,
                'output_additivity_max_abs_error': output_error, 'probability_reconstruction_max_abs_error': probability_error}
    return public, private, numerics
