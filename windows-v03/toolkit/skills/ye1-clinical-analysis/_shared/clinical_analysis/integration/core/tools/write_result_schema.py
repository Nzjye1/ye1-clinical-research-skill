"""Generate closed v0.10 result contracts with exact legacy-version branches.

The public contracts contain aggregates and explicit numerical provenance.
Individual predictions, identities, model contents and local paths are private.
All keywords remain within the local stdlib validator's supported vocabulary.
"""
import copy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
S={'type':'string'}
N={'type':['number','null']}
C={'type':['integer','null'],'minimum':0}
P={'type':['number','null'],'minimum':0,'maximum':1}
H={'type':['string','null'],'pattern':'^[0-9a-f]{64}$'}
def obj(p,required=None):return {'type':'object','properties':p,'required':list(p) if required is None else required,'additionalProperties':False}
def arr(p):return {'type':'array','items':p}
ANY={'type':['object','array','string','number','boolean','null']}
O={'type':'object'}
CI=obj({'lower':N,'upper':N,'level':{'const':0.95},'method':S})
METRIC=obj({'result_id':S,'name':S,'value':N,'unit':S,'scale':S,'evaluation_set':S,'denominator':C,'numerator':C,
 'evaluation_n':C,'evaluation_events':C,'evaluation_nonevents':C,
 'denominator_semantics':{'enum':['events','nonevents','predicted_positive','predicted_negative','evaluated_labels','not_a_count_ratio']},
 'uncertainty':{'anyOf':[CI,{'type':'null'}]},'reason_code':{'type':['string','null']},
 'model_role':{'enum':['frozen_ridge_model','training_constant_comparator']}})
EST=obj({'result_id':S,'term':S,'estimate':N,'standard_error':N,'ci':CI,'p':P,
 'effect_scale':{'enum':['odds_ratio','baseline_odds','mean_difference','conditional_mean','hazard_ratio']},'standard_error_scale':{'enum':['log_odds','outcome_units','log_hazard']},
 'unit':S,'predictor_unit':S,'exposure_unit':S,'interpretation':S,'reference':{'type':['string','null']},'estimand':S,'population':S,
 'analysis_unit':{'enum':['subject','encounter']},'evaluation_set':S,'denominator':C})
EST['properties'].update({'log_hazard_ratio':N,'model_id':S,'component':{'enum':['exposure_effect','subgroup_effect','rcs_curve']},
 'contrast':{'type':['string','null']},'exposure_value':N,'fit_denominator':C,'events':C,'non_events':C,
 'subgroup_level':S,'subgroup_reference':S})
FLOW=obj({**{k:C for k in ['source_rows','common_complete_n','excluded_common_missing','n_before_filter','n_after_filter','excluded_filter','filter_missing_excluded','n_used','n_excluded_missing']},
 'sample_strategy':{'enum':['per_model_complete_case','common_complete_case']},'filter_missing_semantics':S})
MODEL=obj({'model_id':S,'label':S,'rationale':S,'role':{'enum':['primary','adjustment','sensitivity']},'status':S,
 'reason_code':{'type':['string','null']},'covariates':arr(S),'flow':FLOW,'nonlinear':{'type':['object','null']},'subgroup':{'type':['object','null']},
 'subgroup_counts':arr(obj({'level':S,'n_used':C,'events':C,'non_events':C})),
 'missing_by_field':{'type':'object','additionalProperties':C},
 'events':C,'non_events':C,'predictor_parameters':C})
TEST=obj({'result_id':S,'model_id':S,'name':{'enum':['overall_exposure','nonlinearity','interaction']},
 'status':{'enum':['COMPUTED','NOT_REQUESTED','NOT_ESTIMABLE']},'reason_code':{'type':['string','null']},'method':S,
 'statistic':N,'df_num':N,'df_denom':N,'p':P,'denominator':C,'scope':S,'multiplicity':{'const':'unadjusted_prespecified'}})
ART=obj({'artifact_id':S,'kind':{'enum':['table','figure']},'source_result_ids':arr(S),'data_hash':H,
 'method':S,'options':O,'denominator':N,'units':S,'caption':S,
 'ci':{'anyOf':[obj({'level':{'const':0.95},'method':S}),{'type':'null'}]},
 'language':S,'version':S,'scientific_review':{'const':'pending'},'export_status':{'const':'local_only'},'test_only':{'const':True}})
SURVIVAL=obj({**{k:S for k in ['method','time_unit','time_zero_definition','event_definition','censoring_definition','event_code','censor_code','missing_policy','curve_method','ties','interval_boundary_note','model_status','ph_note']},
 'support':{'type':['object','null']},'model_reason':{'type':['string','null']},'cox_ties':{'type':['string','null']},
 'ph_assumption_verified':{'const':False},'ph_diagnostics':arr(obj({'term':S,'rho':N,'diagnostic_kind':{'const':'descriptive_only_schoenfeld_log_time_spearman'},'ph_assumption_verified':{'const':False}})),
 'curves':arr(obj({'result_id':S,'time':{'type':'number','minimum':0},'n_at_risk':C,'estimate':P,'ci':CI,'denominator':C,'events':C,'censored':C,'denominator_semantics':S}))})
V04_SCHEMA={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'clinical-analysis-result@0.4.0-candidate1',**obj({
 'schema_version':{'const':'clinical-analysis-result@0.4.0-candidate1'},'core_version':{'const':'0.4.0-candidate1'},
 'study_id':S,'run_id':S,'method_id':S,'method_version':S,
 'provider':obj({'id':S,'version':S,'code_hash':H,'runtime':O}),
 'binding':obj({'input_hash':H,'plan_hash':H,'code_hash':H,'runtime_hash':H,'model_hash':H}),
 'execution_status':{'enum':['complete','partial','blocked','failed']},'applicability_status':{'enum':['pass','limited','fail','unknown']},
 'scientific_review':{'const':'pending'},'export_status':{'const':'local_only'},'test_only':{'const':True},
 'counts':obj({'source_rows':C,'subjects':C,'eligible':C,'model_n':C,'excluded_missing':C,'missing_by_field':{'type':'object','additionalProperties':C},'events':C,'censored':C,'non_events':C,'predictor_parameters':C,
 'training_n':C,'training_events':C,'training_nonevents':C,'holdout_n':C,'holdout_events':C,'holdout_nonevents':C,'evaluation_n':C,'evaluation_events':C,'evaluation_nonevents':C,
 'missing_outcome_n':C,'missing_feature_excluded_n':C,'prediction_n':C,'prediction_clipped_n':C},[]),
 'estimates':arr(EST),'metrics':arr(METRIC),'model_results':arr(MODEL),'tests':arr(TEST),'survival':{'anyOf':[SURVIVAL,{'type':'null'}]},
 'diagnostics':obj({'backend_status':S,'backend':O,'sensitivity':arr(O),'nonlinearity_test':{'type':['object','null']},
     'interaction_test':{'type':['object','null']},'group_missing_n':N,'missing_requirements':arr(S),'completed_parts':arr(S),
     'internal_cv':{'type':['object','array']},'calibration':O},[]),
 'warnings':arr(obj({'code':S,'stage':S})), 'limitations':arr(S),'tables':arr(ART),'figures':arr(ART),
 'source_refs':arr(obj({'source_id':S,'database':S,'source_fingerprint':H,'recipe_version':S})),
 'provenance':obj({'adapter_version':S,'view_hash':H,'transformation_ledger':O,'host_isolation_evidence':S,'authorization_scope':S,
     'prediction_operation':{'enum':['train','evaluate','infer']},'fit_scope':S,'validation_scope':S,'target_policy':{'type':['object','null']},
     'association_sample_strategy':{'enum':['per_model_complete_case','common_complete_case']}},[]),
 'local_artifacts':arr(obj({'artifact_id':S,'kind':S})), 'completed_parts':arr(S),
 'unsupported_requests':arr(obj({'reason_code':S,'stage':S})), 'next_actions':arr(S),
 'reason_code':{'type':['string','null']},'stage':S})}


def remove_fields(schema, names):
    """Remove fields from a copied historical object without widening it."""
    for name in names:
        schema['properties'].pop(name)
    schema['required'] = [name for name in schema['required'] if name not in names]


def with_version(schema, version):
    result = copy.deepcopy(schema)
    result['$id'] = 'clinical-analysis-result@' + version
    result['properties']['schema_version'] = {'const': result['$id']}
    result['properties']['core_version'] = {'const': version}
    return result


# Reconstruct the unchanged historical schemas without runtime reads from old
# releases. Version-specific branches prevent accepting a v0.5 field under a
# historical version label, or mismatching the schema and core versions.
V03_SCHEMA = with_version(V04_SCHEMA, '0.3.0-candidate1')
remove_fields(V03_SCHEMA, ['survival'])
remove_fields(V03_SCHEMA['properties']['counts'], ['censored'])
v03_estimate = V03_SCHEMA['properties']['estimates']['items']
remove_fields(v03_estimate, ['log_hazard_ratio'])
v03_estimate['properties']['effect_scale']['enum'].remove('hazard_ratio')
v03_estimate['properties']['standard_error_scale']['enum'].remove('log_hazard')

V02_SCHEMA = with_version(V03_SCHEMA, '0.2.0-candidate1')
remove_fields(V02_SCHEMA, ['model_results', 'tests'])
remove_fields(V02_SCHEMA['properties']['counts'], ['evaluation_events', 'evaluation_nonevents'])
remove_fields(V02_SCHEMA['properties']['estimates']['items'], [
    'model_id', 'component', 'contrast', 'exposure_value', 'fit_denominator',
    'events', 'non_events', 'subgroup_level', 'subgroup_reference'])
remove_fields(V02_SCHEMA['properties']['metrics']['items'], [
    'numerator', 'evaluation_n', 'evaluation_events', 'evaluation_nonevents', 'denominator_semantics'])
remove_fields(V02_SCHEMA['properties']['provenance'], ['association_sample_strategy'])

V01_SCHEMA = with_version(V02_SCHEMA, '0.1.0-candidate1')
remove_fields(V01_SCHEMA, ['metrics'])
remove_fields(V01_SCHEMA['properties']['counts'], [
    'training_n', 'training_events', 'training_nonevents', 'holdout_n', 'holdout_events',
    'holdout_nonevents', 'evaluation_n', 'missing_outcome_n', 'missing_feature_excluded_n',
    'prediction_n', 'prediction_clipped_n'])
remove_fields(V01_SCHEMA['properties']['diagnostics'], ['internal_cv', 'calibration'])
remove_fields(V01_SCHEMA['properties']['provenance'], [
    'prediction_operation', 'fit_scope', 'validation_scope', 'target_policy'])

TEXT = {'type': 'string', 'minLength': 1}
COUNT = {'type': 'integer', 'minimum': 0}
PROBABILITY = {'type': 'number', 'minimum': 0, 'maximum': 1}
NONNEGATIVE = {'type': 'number', 'minimum': 0}
SHA256 = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}


def ph_test_row(available):
    properties = {
        'result_id': TEXT, 'term': TEXT,
        'chisq': NONNEGATIVE if available else {'type': 'null'},
        'df': {'type': 'integer', 'minimum': 1},
        'p_value': PROBABILITY if available else {'type': 'null'},
        'status': {'const': 'completed' if available else 'unavailable'},
        'denominator': COUNT, 'events': COUNT,
        'reason': TEXT,
    }
    required = [key for key in properties if not (available and key == 'reason')]
    return obj(properties, required)


PH_SCORE_TEST = obj({
    'status': {'enum': ['completed', 'unavailable']},
    'method': {'const': 'cox_score'},
    'transform': {'enum': ['km', 'identity']},
    'terms': {'const': True}, 'singledf': {'const': False}, 'global': {'const': True},
    'ties': {'const': 'breslow'}, 'ph_assumption_verified': {'const': False},
    'tests': {'type': 'array', 'minItems': 1,
              'items': {'anyOf': [ph_test_row(True), ph_test_row(False)]}},
})

COX_PREDICTION_SUMMARY = obj({
    'result_id': TEXT, 'horizon': NONNEGATIVE,
    'n': {'type': 'integer', 'minimum': 1},
    **{name: PROBABILITY for name in (
        'survival_probability_min', 'survival_probability_mean', 'survival_probability_max',
        'event_risk_min', 'event_risk_mean', 'event_risk_max')},
})
COX_POPULATION = obj({
    **{name: COUNT for name in (
        'n_input', 'n_training_declared', 'n_training_complete', 'n_training_events',
        'n_training_censored', 'n_holdout', 'n_predicted', 'n_predicted_events',
        'n_predicted_censored', 'n_predicted_missing_time', 'n_predicted_missing_status',
        'n_dropped_training_missing')},
    'training_missing_by_field': {'type': 'object', 'additionalProperties': COUNT},
})
COX_HORIZONS = {'type': 'array', 'items': NONNEGATIVE, 'minItems': 1}
COX_PREDICTION = obj({
    'method_id': {'const': 'prediction.survival.cox'},
    'operation': {'enum': ['train', 'infer']},
    'analysis_population': COX_POPULATION,
    'horizons': COX_HORIZONS,
    'prediction_summary': {'type': 'array', 'items': COX_PREDICTION_SUMMARY, 'minItems': 1},
    'model_sha256': SHA256,
    'baseline_convention': {'const': 'right_continuous_breslow'},
    'fit_engine': {'const': 'statsmodels.PHReg'}, 'ties': {'const': 'breslow'},
    'extrapolation': {'const': 'forbidden'}, 'warnings': arr(TEXT),
    'support': obj({
        'last_event_time': NONNEGATIVE, 'max_observed_time': NONNEGATIVE,
        'time_unit': {'enum': ['day', 'hour']}, 'horizons': COX_HORIZONS,
        'extrapolation': {'const': 'forbidden_beyond_last_training_event'},
    }),
    'semantics': obj({
        'time_unit': {'enum': ['day', 'hour']},
        **{name: TEXT for name in ('time_zero_definition', 'event_definition',
                                  'censoring_definition', 'event_code', 'censor_code')},
    }),
    'uncertainty': {'const': 'not_implemented'},
    'summary_estimand': {'const': 'mean_frozen_predicted_absolute_event_risk'},
})

V05_SCHEMA = with_version(V04_SCHEMA, '0.5.0-candidate1')
V05_SCHEMA['properties']['survival']['anyOf'][0]['properties']['ph_score_test'] = {
    'anyOf': [PH_SCORE_TEST, {'type': 'null'}]}
V05_SCHEMA['properties']['cox_prediction'] = {'anyOf': [COX_PREDICTION, {'type': 'null'}]}
V05_SCHEMA['required'].append('cox_prediction')
V05_SCHEMA['properties']['counts']['properties'].update({
    name: C for name in ('training_censored', 'prediction_events', 'prediction_censored',
                        'prediction_missing_status', 'prediction_missing_time')})


# v06-provider-contract-1: the numerical provider owns the aggregate record.
# R adds only semantics and result_id on each horizon and each nested output row.
# Keep weighted sums separate from the legacy binary METRIC count ratios. All
# prior schemas above remain independent of these new definitions.
NULL = {'type': 'null'}
NUMBER = {'type': 'number'}
NULLABLE_NONNEGATIVE = {'type': ['number', 'null'], 'minimum': 0}
NULLABLE_PROBABILITY = {'type': ['number', 'null'], 'minimum': 0, 'maximum': 1}
POSITIVE_COUNT = {'type': 'integer', 'minimum': 1}
EVALUATION_COUNT = {'type': 'integer', 'minimum': 0, 'maximum': 500}
EVALUATION_N = {'type': 'integer', 'minimum': 1, 'maximum': 500}
UNIMPLEMENTED_UNCERTAINTY = {'const': 'not_implemented'}
IPCW_POSITIVITY_REASONS = [
    'CENSORING_SURVIVAL_NONPOSITIVE_AT_HORIZON',
    'CENSORING_SURVIVAL_BELOW_MIN_AT_HORIZON',
    'CASE_CENSORING_SURVIVAL_NONPOSITIVE',
    'CASE_CENSORING_SURVIVAL_BELOW_MIN',
    'IPCW_WEIGHT_ABOVE_MAX',
]
IPCW_AUC_REASONS = [
    'NO_CASES_AT_HORIZON', 'NO_CONTROLS_AT_HORIZON',
    'NO_CASES_OR_CONTROLS_AT_HORIZON',
]
IPCW_CALIBRATION_REASONS = [
    'CALIBRATION_BIN_EMPTY', 'CALIBRATION_BIN_BELOW_MIN_N',
    'CALIBRATION_BIN_ZERO_WEIGHT',
]
IPCW_REASONS = IPCW_POSITIVITY_REASONS + IPCW_AUC_REASONS + IPCW_CALIBRATION_REASONS


def bounded_array(items, minimum, maximum):
    return {'type': 'array', 'items': items, 'minItems': minimum, 'maxItems': maximum}


def evaluated_row(properties, available_values, unavailable_values, reasons):
    """Require the null/reason contract without changing validator vocabulary."""
    schema = obj({
        'result_id': TEXT,
        **properties,
        'status': {'enum': ['completed', 'unavailable']},
        'reason': {'anyOf': [{'enum': reasons}, NULL]},
    })
    schema['anyOf'] = [
        {'properties': {'status': {'const': 'completed'}, 'reason': NULL,
                        **available_values}},
        {'properties': {'status': {'const': 'unavailable'},
                        'reason': {'enum': reasons}, **unavailable_values}},
    ]
    return schema


def evaluation_summary(properties):
    schema = obj({
        **properties,
        'status': {'enum': ['completed', 'partial', 'unavailable']},
        'reason_codes': arr({'enum': IPCW_REASONS}),
    })
    schema['anyOf'] = [
        {'properties': {'status': {'const': 'completed'},
                        'reason_codes': {'maxItems': 0}}},
        {'properties': {'status': {'const': 'partial'},
                        'reason_codes': {'minItems': 1}}},
        {'properties': {'status': {'const': 'unavailable'},
                        'reason_codes': {'minItems': 1,
                                         'items': {'enum': IPCW_POSITIVITY_REASONS}}}},
    ]
    return schema


IPCW_OPTIONS = obj({
    'estimator': {'const': 'marginal_reverse_km_ipcw'},
    'censoring_source': {'const': 'evaluation_cohort'},
    'censoring_assumption': {'const': 'independent_of_event_time_and_model_features'},
    'tie_order': {'const': 'events_before_censoring'},
    'min_censoring_survival': {'type': 'number', 'minimum': 0.05, 'maximum': 0.05},
    'max_ipcw_weight': {'type': 'number', 'minimum': 20, 'maximum': 20},
    'positivity_policy': {'const': 'reject_no_clipping'},
    'roc_thresholds': bounded_array(PROBABILITY, 2, 51),
    'calibration': obj({
        'method': {'const': 'ipcw_hajek_fixed_bins'},
        'probability_edges': bounded_array(PROBABILITY, 2, 11),
        'min_bin_n': {'type': 'integer', 'minimum': 2, 'maximum': 500},
    }),
    'dca_thresholds': bounded_array(PROBABILITY, 1, 51),
    'uncertainty': UNIMPLEMENTED_UNCERTAINTY,
    'prespecified': {'const': True},
})


def ipcw_metric(metric):
    auc = metric == 'auc'
    numerator_definition = (
        'sum_case_control_weighted_concordance_with_half_exact_ties' if auc else
        'sum_case_weight_times_one_minus_risk_squared_plus_control_weight_times_risk_squared')
    denominator_definition = (
        'sum_case_weights_times_sum_control_weights' if auc else
        'all_evaluation_subjects_including_early_censoring')
    return evaluated_row({
        'metric': {'const': metric}, 'value': NULLABLE_PROBABILITY,
        'numerator': NULLABLE_NONNEGATIVE,
        'denominator': NULLABLE_NONNEGATIVE if auc else EVALUATION_N,
        'numerator_definition': {'const': numerator_definition},
        'denominator_definition': {'const': denominator_definition},
        'uncertainty': UNIMPLEMENTED_UNCERTAINTY,
    }, {
        'value': PROBABILITY, 'numerator': NONNEGATIVE,
        'denominator': NONNEGATIVE if auc else EVALUATION_N,
    }, {'value': NULL, 'numerator': NULL},
        IPCW_POSITIVITY_REASONS + IPCW_AUC_REASONS if auc else IPCW_POSITIVITY_REASONS)


IPCW_ROC_ROW = evaluated_row({
    'threshold': NULLABLE_PROBABILITY,
    'boundary': {'enum': ['above_all', 'fixed_grid']},
    'n_treated': EVALUATION_COUNT,
    'tp_weight': NULLABLE_NONNEGATIVE, 'fp_weight': NULLABLE_NONNEGATIVE,
    **{name: NULLABLE_PROBABILITY for name in (
        'sensitivity', 'false_positive_rate', 'specificity')},
}, {
    'tp_weight': NONNEGATIVE, 'fp_weight': NONNEGATIVE,
    **{name: PROBABILITY for name in ('sensitivity', 'false_positive_rate', 'specificity')},
}, {name: NULL for name in ('sensitivity', 'false_positive_rate', 'specificity')},
    IPCW_POSITIVITY_REASONS + IPCW_AUC_REASONS)
# Combine boundary and availability choices explicitly; the validator supports
# anyOf, so neither if/then nor an unimplemented allOf is needed.
IPCW_ROC_ROW['anyOf'] = [
    {'properties': {**state['properties'], **boundary}}
    for state in IPCW_ROC_ROW['anyOf']
    for boundary in (
        {'boundary': {'const': 'above_all'}, 'threshold': NULL, 'n_treated': {'const': 0}},
        {'boundary': {'const': 'fixed_grid'}, 'threshold': PROBABILITY},
    )
]

IPCW_CALIBRATION_ROW = evaluated_row({
    'bin_index': {'type': 'integer', 'minimum': 1, 'maximum': 10},
    'lower': PROBABILITY, 'upper': PROBABILITY, 'right_inclusive': {'type': 'boolean'},
    **{name: EVALUATION_COUNT for name in ('n', 'n_cases', 'n_controls', 'n_censored_by_horizon')},
    'predicted_risk_sum': NONNEGATIVE, 'mean_predicted_risk': NULLABLE_PROBABILITY,
    **{name: NULLABLE_NONNEGATIVE for name in (
        'sum_case_weights', 'sum_control_weights', 'sum_weights', 'ess')},
    'observed_risk': NULLABLE_PROBABILITY, 'uncertainty': UNIMPLEMENTED_UNCERTAINTY,
}, {
    'n': EVALUATION_N, 'mean_predicted_risk': PROBABILITY, 'observed_risk': PROBABILITY,
    **{name: NONNEGATIVE for name in ('sum_case_weights', 'sum_control_weights', 'sum_weights', 'ess')},
}, {'observed_risk': NULL}, IPCW_POSITIVITY_REASONS + IPCW_CALIBRATION_REASONS)

IPCW_DCA_ROW = evaluated_row({
    'threshold': PROBABILITY,
    **{name: EVALUATION_COUNT for name in (
        'n_treated', 'n_treated_cases', 'n_treated_controls', 'n_treated_censored_by_horizon')},
    **{name: NULLABLE_NONNEGATIVE for name in (
        'tp_weight', 'fp_weight', 'treated_weight_sum', 'treated_ess')},
    'threshold_odds': NONNEGATIVE, 'population_denominator': EVALUATION_N,
    **{name: N for name in (
        'numerator_model', 'numerator_all', 'net_benefit_model',
        'net_benefit_all', 'net_benefit_none')},
    'uncertainty': UNIMPLEMENTED_UNCERTAINTY,
}, {
    'tp_weight': NONNEGATIVE, 'fp_weight': NONNEGATIVE, 'treated_weight_sum': NONNEGATIVE,
    **{name: NUMBER for name in (
        'numerator_model', 'numerator_all', 'net_benefit_model', 'net_benefit_all')},
    'net_benefit_none': {'type': 'number', 'minimum': 0, 'maximum': 0},
}, {name: NULL for name in (
    'numerator_model', 'numerator_all', 'net_benefit_model', 'net_benefit_all', 'net_benefit_none')},
    IPCW_POSITIVITY_REASONS)

IPCW_HORIZON = evaluation_summary({
    'result_id': TEXT, 'horizon': NONNEGATIVE,
    'counts': obj({
        'n': EVALUATION_N,
        **{name: EVALUATION_COUNT for name in (
            'n_cases', 'n_controls', 'n_censored_by_horizon', 'n_at_risk_before_horizon',
            'n_events_at_horizon', 'n_censored_at_horizon')},
        'n_case_control_score_ties': COUNT,
    }),
    'weights': obj({
        'g_at_horizon': PROBABILITY, 'min_g_for_cases': NULLABLE_PROBABILITY,
        **{name: NULLABLE_NONNEGATIVE for name in (
            'sum_case_weights', 'sum_control_weights', 'sum_weights', 'max_weight',
            'ess', 'case_ess', 'control_ess')},
    }),
    'diagnostics': obj({
        'weight_mass_minus_n': N, 'km_event_probability': PROBABILITY,
        'weighted_case_probability': NULLABLE_PROBABILITY, 'km_identity_difference': N,
        'weight_mass_identity_ok': {'anyOf': [{'const': True}, NULL]},
        'km_identity_ok': {'anyOf': [{'const': True}, NULL]},
    }),
    'metrics': bounded_array({'anyOf': [ipcw_metric('auc'), ipcw_metric('brier')]}, 2, 2),
    'roc': bounded_array(IPCW_ROC_ROW, 3, 52),
    'calibration': bounded_array(IPCW_CALIBRATION_ROW, 1, 10),
    'dca': bounded_array(IPCW_DCA_ROW, 1, 51),
})

SURVIVAL_EVALUATION = evaluation_summary({
    'method_id': {'const': 'evaluation.survival.cox.ipcw'},
    'operation': {'const': 'evaluate'},
    'model_sha256': SHA256, 'frozen_model_provider_version': SHA256,
    'population': obj({
        'n_input': EVALUATION_N, 'n_evaluable': EVALUATION_N,
        'n_dropped_missing': {'const': 0},
        'n_events': EVALUATION_COUNT, 'n_censored': EVALUATION_COUNT,
        'n_horizons': {'type': 'integer', 'minimum': 1, 'maximum': 12},
    }),
    'options': IPCW_OPTIONS,
    'censoring_metadata': obj({
        'estimator': {'const': 'marginal_reverse_km_ipcw'},
        'source': {'const': 'evaluation_cohort'},
        'assumption': {'const': 'independent_of_event_time_and_model_features'},
        'assumption_verified': {'const': False},
        'tie_order': {'const': 'events_before_censoring'},
        'time_unit': {'enum': ['day', 'hour']}, 'full_grid_location': {'const': 'private'},
        'weight_clipping': {'const': False}, 'uncertainty': UNIMPLEMENTED_UNCERTAINTY,
    }),
    'semantics': copy.deepcopy(COX_PREDICTION['properties']['semantics']),
    'horizon_results': bounded_array(IPCW_HORIZON, 1, 12),
})

V06_SCHEMA = with_version(V05_SCHEMA, '0.6.0-candidate1')
V06_SCHEMA['properties']['survival_evaluation'] = {'anyOf': [SURVIVAL_EVALUATION, NULL]}
V06_SCHEMA['required'].append('survival_evaluation')


# v07 PSM options mirror the prespecified public interface. No production input
# module is imported, and none of the six historical schema objects is mutated.
PSM_NAME = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_]*$'}
PSM_COUNT = {'type': 'integer', 'minimum': 0, 'maximum': 200}
PSM_OPTIONS = obj({
    'treatment': PSM_NAME, 'outcome': PSM_NAME,
    'covariates': bounded_array(PSM_NAME, 1, 8),
    'categorical': {'type': 'object', 'additionalProperties': obj({
        'levels': {'type': 'array', 'items': TEXT, 'minItems': 2}, 'reference': TEXT,
    })},
    'propensity_model': {'const': 'logistic_mle'}, 'link': {'const': 'logit'},
    'estimand': {'const': 'ATT_retained_matched_treated'},
    'ratio': {'const': 1}, 'replacement': {'const': False}, 'distance': {'const': 'logit_ps'},
    'caliper': obj({
        'width': {'type': 'number', 'minimum': 0, 'maximum': 2},
        'scale': {'const': 'sd_logit_ps'}, 'sd_scope': {'const': 'common_support_retained'},
        'ddof': {'const': 1}, 'boundary': {'const': 'inclusive'},
    }),
    'common_support': obj({
        'strategy': {'const': 'minmax_both'}, 'boundary': {'const': 'inclusive'},
        'refit': {'const': False},
    }),
    'ordering': obj({
        'treated': {'const': 'descending_logit_ps_then_subject_id_utf8'},
        'control_tie': {'const': 'subject_id_utf8_ascending'},
        'row_order': {'const': 'subject_id_utf8_ascending'},
    }),
    'inference': obj({
        'method': {'const': 'paired_t'},
        'ci_level': {'type': 'number', 'minimum': 0.95, 'maximum': 0.95},
        'variance': {'const': 'sample_variance_of_pair_differences'},
        'conditioning': {'const': 'formed_matched_pairs'},
    }),
    'diagnostics': obj({
        'smd_denominator': {'const': 'pre_support_complete_case_treated_sample_sd'},
        'standardize_binary': {'const': True},
        'indicator_sd': {'const': 'bernoulli_p1mp'},
        'ps_overlap_edges': {
            **bounded_array(PROBABILITY, 11, 11),
            'const': [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1],
        },
        'balance_reference': {'type': 'number', 'minimum': 0.1, 'maximum': 0.1},
    }),
    'guards': obj({
        'min_arm_n': {'const': 2},
        'min_probability': {'type': 'number', 'minimum': 1e-6, 'maximum': 1e-6},
        'max_glm_iterations': {'const': 100},
        'glm_epsilon': {'type': 'number', 'minimum': 1e-10, 'maximum': 1e-10},
        'separation_detection': {'const': 'numerical_guards_only'},
    }),
    'prespecified': {'const': True},
})

PSM_NULLABLE_COUNT = {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 200}
PSM_PAIRS = {'type': 'integer', 'minimum': 0, 'maximum': 100}
PSM_NULLABLE_REASON = {'anyOf': [TEXT, NULL]}
PSM_NULLABLE_BOOLEAN = {'type': ['boolean', 'null']}
PSM_FLOW = obj({
    'n_input': PSM_COUNT,
    **{name: PSM_NULLABLE_COUNT for name in (
        'n_input_treated', 'n_input_control', 'n_excluded_missing_covariates',
        'n_excluded_missing_treated', 'n_excluded_missing_control',
        'n_complete_case', 'n_complete_case_treated', 'n_complete_case_control',
        'n_support_retained', 'n_support_treated', 'n_support_control',
        'n_discarded_support_treated', 'n_discarded_support_control',
        'n_unmatched_support_treated', 'n_unmatched_support_control')},
    'n_matched_pairs': PSM_PAIRS, 'n_matched_subjects': PSM_COUNT,
    'missing_by_field': {'type': 'object', 'additionalProperties': obj({
        'n_missing': PSM_COUNT, 'n_missing_treated': PSM_COUNT, 'n_missing_control': PSM_COUNT,
    })},
})


def psm_stage(properties):
    """Closed stage diagnostics retain nulls before that stage is reached."""
    schema = obj({
        **properties, 'status': {'enum': ['not_run', 'completed', 'unavailable']},
        'reason_code': PSM_NULLABLE_REASON,
    })
    schema['anyOf'] = [
        {'properties': {'status': {'const': 'completed'}, 'reason_code': NULL}},
        {'properties': {'status': {'enum': ['not_run', 'unavailable']}, 'reason_code': TEXT}},
    ]
    return schema


PSM_PROPENSITY = psm_stage({
    'engine': {'const': 'stats::glm'}, 'family': {'const': 'binomial'}, 'link': {'const': 'logit'},
    'fit_scope': {'const': 'complete_case_pre_support'},
    'converged': PSM_NULLABLE_BOOLEAN, 'boundary': PSM_NULLABLE_BOOLEAN,
    'iterations': C, 'n_parameters': C, 'design_rank': C,
    'probability_min': NULLABLE_PROBABILITY, 'probability_max': NULLABLE_PROBABILITY,
    'logit_min': N, 'logit_max': N, 'warning_count': COUNT,
    'numerical_guard_status': {'enum': ['not_run', 'passed', 'failed']},
    'separation_detection': {'const': 'numerical_guards_only'},
    'formal_separation_checked': {'const': False},
})
PSM_PROPENSITY['anyOf'][0]['properties'].update({
    'converged': {'const': True}, 'boundary': {'const': False},
    'iterations': POSITIVE_COUNT, 'n_parameters': POSITIVE_COUNT, 'design_rank': POSITIVE_COUNT,
    'probability_min': PROBABILITY, 'probability_max': PROBABILITY,
    'logit_min': NUMBER, 'logit_max': NUMBER, 'warning_count': {'const': 0},
    'numerical_guard_status': {'const': 'passed'},
})

PSM_SUPPORT = psm_stage({
    'strategy': {'const': 'minmax_both'}, 'boundary': {'const': 'inclusive'}, 'refit': {'const': False},
    **{name: N for name in ('treated_logit_min', 'treated_logit_max',
                           'control_logit_min', 'control_logit_max', 'lower', 'upper')},
    'overlap_exists': PSM_NULLABLE_BOOLEAN,
    'n_retained_treated': PSM_NULLABLE_COUNT, 'n_retained_control': PSM_NULLABLE_COUNT,
    'logit_sd': NULLABLE_NONNEGATIVE,
    'caliper_multiplier': {'type': ['number', 'null'], 'minimum': 0, 'maximum': 2},
    'caliper_width': NULLABLE_NONNEGATIVE, 'zero_scale': PSM_NULLABLE_BOOLEAN,
})

PSM_EFFECT = obj({
    'result_id': TEXT, 'status': {'enum': ['completed', 'partial', 'unavailable']},
    'reason_code': PSM_NULLABLE_REASON,
    'inference_status': {'enum': ['completed', 'unavailable']},
    'inference_reason_code': PSM_NULLABLE_REASON,
    'estimand': {'const': 'ATT_retained_matched_treated'},
    'measure': {'const': 'matched_mean_difference'}, 'direction': {'const': 'treated_minus_control'},
    'n_pairs': PSM_PAIRS,
    **{name: N for name in ('treated_mean', 'control_mean', 'estimate', 'ci_lower', 'ci_upper',
                           't_statistic', 'treated_control_covariance', 'variance_identity_difference')},
    **{name: NULLABLE_NONNEGATIVE for name in ('paired_difference_variance', 'standard_error',
                                              'treated_variance', 'control_variance')},
    'df': {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 99},
    'ci_level': {'type': 'number', 'minimum': 0.95, 'maximum': 0.95},
    'p_value': NULLABLE_PROBABILITY, 'conditioning': {'const': 'formed_matched_pairs'},
    'ps_estimation_uncertainty_included': {'const': False},
})
PSM_NO_INFERENCE = {
    'inference_status': {'const': 'unavailable'},
    **{name: NULL for name in ('ci_lower', 'ci_upper', 't_statistic', 'p_value')},
}
PSM_DESCRIPTIVE_MEANS = {name: NUMBER for name in ('treated_mean', 'control_mean', 'estimate')}
PSM_VARIANCE_COMPONENTS = {
    'treated_variance': NONNEGATIVE, 'control_variance': NONNEGATIVE,
    'treated_control_covariance': NUMBER, 'variance_identity_difference': NUMBER,
}
PSM_EFFECT['anyOf'] = [
    {'properties': {
        'status': {'const': 'completed'}, 'reason_code': NULL,
        'inference_status': {'const': 'completed'}, 'inference_reason_code': NULL,
        'n_pairs': {'type': 'integer', 'minimum': 2, 'maximum': 100},
        **PSM_DESCRIPTIVE_MEANS, **PSM_VARIANCE_COMPONENTS,
        'paired_difference_variance': NONNEGATIVE, 'standard_error': NONNEGATIVE,
        'df': {'type': 'integer', 'minimum': 1, 'maximum': 99},
        'ci_lower': NUMBER, 'ci_upper': NUMBER, 't_statistic': NUMBER, 'p_value': PROBABILITY,
    }},
    {'properties': {
        'status': {'const': 'partial'}, 'reason_code': {'const': 'INSUFFICIENT_MATCHED_PAIRS'},
        'inference_reason_code': {'const': 'INSUFFICIENT_MATCHED_PAIRS'},
        'n_pairs': {'const': 1}, 'df': {'const': 0},
        **PSM_DESCRIPTIVE_MEANS, **PSM_NO_INFERENCE,
        **{name: NULL for name in ('paired_difference_variance', 'standard_error',
                                   'treated_variance', 'control_variance',
                                   'treated_control_covariance', 'variance_identity_difference')},
    }},
    {'properties': {
        'status': {'const': 'partial'}, 'reason_code': {'const': 'ZERO_PAIRED_VARIANCE'},
        'inference_reason_code': {'const': 'ZERO_PAIRED_VARIANCE'},
        'n_pairs': {'type': 'integer', 'minimum': 2, 'maximum': 100},
        'df': {'type': 'integer', 'minimum': 1, 'maximum': 99},
        **PSM_DESCRIPTIVE_MEANS, **PSM_VARIANCE_COMPONENTS, **PSM_NO_INFERENCE,
        'paired_difference_variance': {'type': 'number', 'minimum': 0, 'maximum': 0},
        'standard_error': {'type': 'number', 'minimum': 0, 'maximum': 0},
    }},
    # The provider keeps the formed-pair count when a later numerical operation
    # overflows. Preserve only the moments calculated before the failure stage.
    {'properties': {
        'status': {'const': 'unavailable'},
        'reason_code': {'const': 'NONFINITE_PAIRED_MOMENTS'},
        'inference_reason_code': {'const': 'NONFINITE_PAIRED_MOMENTS'},
        'n_pairs': {'type': 'integer', 'minimum': 1, 'maximum': 100},
        **PSM_NO_INFERENCE,
        **{name: NULL for name in ('treated_mean', 'control_mean', 'estimate',
                                   'paired_difference_variance', 'standard_error', 'df',
                                   'treated_variance', 'control_variance',
                                   'treated_control_covariance', 'variance_identity_difference')},
    }},
    {'properties': {
        'status': {'const': 'partial'},
        'reason_code': {'const': 'NONFINITE_PAIRED_MOMENTS'},
        'inference_reason_code': {'const': 'NONFINITE_PAIRED_MOMENTS'},
        'n_pairs': {'type': 'integer', 'minimum': 2, 'maximum': 100},
        'df': {'type': 'integer', 'minimum': 1, 'maximum': 99},
        **PSM_DESCRIPTIVE_MEANS, **PSM_NO_INFERENCE,
        **{name: NULL for name in ('paired_difference_variance', 'standard_error',
                                   'treated_variance', 'control_variance',
                                   'treated_control_covariance', 'variance_identity_difference')},
    }},
    {'properties': {
        'status': {'const': 'partial'},
        'reason_code': {'const': 'NONFINITE_PAIRED_MOMENTS'},
        'inference_reason_code': {'const': 'NONFINITE_PAIRED_MOMENTS'},
        'n_pairs': {'type': 'integer', 'minimum': 2, 'maximum': 100},
        'df': {'type': 'integer', 'minimum': 1, 'maximum': 99},
        **PSM_DESCRIPTIVE_MEANS, **PSM_NO_INFERENCE,
        'paired_difference_variance': NONNEGATIVE,
        'treated_variance': NONNEGATIVE, 'control_variance': NONNEGATIVE,
        'treated_control_covariance': NUMBER,
        'variance_identity_difference': NULL, 'standard_error': NULL,
    }},
    {'properties': {
        'status': {'const': 'partial'},
        'reason_code': {'const': 'NONFINITE_PAIRED_INFERENCE'},
        'inference_reason_code': {'const': 'NONFINITE_PAIRED_INFERENCE'},
        'n_pairs': {'type': 'integer', 'minimum': 2, 'maximum': 100},
        'df': {'type': 'integer', 'minimum': 1, 'maximum': 99},
        **PSM_DESCRIPTIVE_MEANS, **PSM_VARIANCE_COMPONENTS, **PSM_NO_INFERENCE,
        'paired_difference_variance': NONNEGATIVE, 'standard_error': NONNEGATIVE,
    }},
    {'properties': {
        'status': {'const': 'unavailable'},
        'reason_code': {**TEXT, 'pattern': '^(?!NONFINITE_PAIRED_(?:MOMENTS|INFERENCE)$).+$'},
        'inference_reason_code': {**TEXT, 'pattern': '^(?!NONFINITE_PAIRED_(?:MOMENTS|INFERENCE)$).+$'},
        'n_pairs': {'const': 0}, **PSM_NO_INFERENCE,
        **{name: NULL for name in ('treated_mean', 'control_mean', 'estimate',
                                   'paired_difference_variance', 'standard_error', 'df',
                                   'treated_variance', 'control_variance',
                                   'treated_control_covariance', 'variance_identity_difference')},
    }},
]

PSM_BALANCE = obj({
    'result_id': TEXT, 'covariate': PSM_NAME, 'kind': {'enum': ['numeric', 'indicator']},
    'level': {'anyOf': [TEXT, NULL]}, 'is_reference': {'type': 'boolean'},
    'sd_kind': {'enum': ['sample_n_minus_1', 'bernoulli_p1mp']},
    'denominator_scope': {'const': 'pre_support_complete_case_treated'},
    'reference_sd': NULLABLE_NONNEGATIVE,
    **{name: PSM_COUNT for name in ('n_before_treated', 'n_before_control',
                                    'n_after_treated', 'n_after_control')},
    **{name: N for name in ('mean_before_treated', 'mean_before_control', 'smd_before',
                            'mean_after_treated', 'mean_after_control', 'smd_after')},
    'smd_before_reason': PSM_NULLABLE_REASON, 'smd_after_reason': PSM_NULLABLE_REASON,
})
PSM_BALANCE_BEFORE = [
    {'smd_before': NUMBER, 'smd_before_reason': NULL, 'reference_sd': NONNEGATIVE},
    {'smd_before': NULL, 'smd_before_reason': {'const': 'ZERO_REFERENCE_SD'},
     'reference_sd': {'type': 'number', 'minimum': 0, 'maximum': 0}},
    {'smd_before': NULL, 'smd_before_reason': {'const': 'REFERENCE_SD_UNAVAILABLE'},
     'reference_sd': NULL},
    {'smd_before': NULL, 'smd_before_reason': {'const': 'BEFORE_CONTROL_ARM_EMPTY'},
     'reference_sd': NONNEGATIVE, 'n_before_treated': {'type': 'integer', 'minimum': 2, 'maximum': 200},
     'n_before_control': {'const': 0}, 'mean_before_treated': NUMBER, 'mean_before_control': NULL,
     'n_after_treated': {'const': 0}, 'n_after_control': {'const': 0},
     'mean_after_treated': NULL, 'mean_after_control': NULL, 'smd_after': NULL,
     'smd_after_reason': {'enum': ['NO_MATCHED_PAIRS', 'MATCHING_NOT_RUN']}},
    {'smd_before': NULL, 'smd_before_reason': {'const': 'SMD_NUMERIC_RANGE'},
     'reference_sd': NONNEGATIVE, 'mean_before_treated': NUMBER, 'mean_before_control': NUMBER,
     'n_before_treated': POSITIVE_COUNT, 'n_before_control': POSITIVE_COUNT},
]
PSM_BALANCE_AFTER = [
    {'smd_after': NUMBER, 'smd_after_reason': NULL,
     'mean_after_treated': NUMBER, 'mean_after_control': NUMBER},
    {'smd_after': NULL, 'smd_after_reason': {'const': 'ZERO_REFERENCE_SD'},
     'reference_sd': {'type': 'number', 'minimum': 0, 'maximum': 0}},
    {'smd_after': NULL, 'smd_after_reason': {'const': 'REFERENCE_SD_UNAVAILABLE'}, 'reference_sd': NULL},
    {'smd_after': NULL, 'smd_after_reason': {'const': 'SMD_NUMERIC_RANGE'},
     'reference_sd': NONNEGATIVE, 'mean_after_treated': NUMBER, 'mean_after_control': NUMBER,
     'n_after_treated': POSITIVE_COUNT, 'n_after_control': POSITIVE_COUNT},
    {'smd_after': NULL, 'smd_after_reason': {'enum': ['NO_MATCHED_PAIRS', 'MATCHING_NOT_RUN']},
     'n_after_treated': {'const': 0}, 'n_after_control': {'const': 0},
     'mean_after_treated': NULL, 'mean_after_control': NULL},
]
PSM_BALANCE['anyOf'] = [
    {'properties': kind, 'anyOf': [
        {'properties': before, 'anyOf': [{'properties': after} for after in PSM_BALANCE_AFTER]}
        for before in PSM_BALANCE_BEFORE]}
    for kind in (
        {'kind': {'const': 'numeric'}, 'level': NULL, 'is_reference': {'const': False},
         'sd_kind': {'const': 'sample_n_minus_1'}},
        {'kind': {'const': 'indicator'}, 'level': TEXT, 'sd_kind': {'const': 'bernoulli_p1mp'}},
    )
]

PSM_OVERLAP = obj({
    'result_id': TEXT, 'population': {'enum': ['ps_fit', 'support_retained', 'matched']},
    'arm': {'enum': ['treated', 'control']},
    'bin_index': {'type': 'integer', 'minimum': 1, 'maximum': 10},
    'lower': PROBABILITY, 'upper': PROBABILITY, 'right_inclusive': {'type': 'boolean'},
    'n': PSM_COUNT, 'denominator': PSM_COUNT, 'proportion': NULLABLE_PROBABILITY,
})
PSM_OVERLAP['anyOf'] = [
    {'properties': {'denominator': {'const': 0}, 'n': {'const': 0}, 'proportion': NULL}},
    {'properties': {'denominator': {'type': 'integer', 'minimum': 1, 'maximum': 200},
                    'proportion': PROBABILITY}},
]

PSM = obj({
    'result_id': TEXT, 'method_id': {'const': 'causal.psm.att.continuous'},
    'status': {'enum': ['completed', 'partial', 'unavailable']}, 'reason_code': PSM_NULLABLE_REASON,
    'options': PSM_OPTIONS,
    'semantics': obj({
        'subject_id': PSM_NAME, 'treatment_definition': TEXT, 'outcome_definition': TEXT,
        'outcome_unit': TEXT, 'index_time': NUMBER, 'time_unit': TEXT, 'target_population': TEXT,
        'outcome_type': {'const': 'continuous'},
        'event_count_semantics': {'const': 'not_applicable_continuous_outcome'},
        'causal_assumptions_verified': {'const': False},
    }),
    'flow': PSM_FLOW, 'propensity': PSM_PROPENSITY, 'support': PSM_SUPPORT, 'effect': PSM_EFFECT,
    'balance': arr(PSM_BALANCE), 'overlap': bounded_array(PSM_OVERLAP, 0, 60),
    'warnings': arr(TEXT), 'limitations': {'type': 'array', 'items': TEXT, 'minItems': 1},
})
PSM['anyOf'] = [
    {'properties': {'status': {'const': 'completed'}, 'reason_code': NULL}},
    {'properties': {'status': {'enum': ['partial', 'unavailable']}, 'reason_code': TEXT}},
]

V07_SCHEMA = with_version(V06_SCHEMA, '0.7.0-candidate1')
V07_SCHEMA['properties']['psm'] = {'anyOf': [PSM, NULL]}
V07_SCHEMA['required'].append('psm')

# v0.8 definitions are isolated from the seven frozen branches above.  The
# provider owns arithmetic, cross-row matching and requested/returned lambda
# tolerance checks; this contract owns public shapes, states and null meanings.
PEN_NAME = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_]*$'}
PEN_COUNT = {'type': 'integer', 'minimum': 0, 'maximum': 200}
PEN_POSITIVE_COUNT = {'type': 'integer', 'minimum': 1, 'maximum': 200}
PEN_NULLABLE_COUNT = {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 200}
PEN_FOLD = {'type': 'integer', 'minimum': 1, 'maximum': 5}
PEN_INDEX = {'type': 'integer', 'minimum': 1, 'maximum': 30}
# The local validator accepts finite binary64 numbers.  These are the adjacent
# representable bounds, expressing open intervals without adding new keywords.
PEN_POSITIVE = {'type': 'number', 'minimum': 5e-324}
PEN_OPEN_PROBABILITY = {**PEN_POSITIVE, 'maximum': 0.9999999999999999}
PEN_FAILURE_CODES = [
    'PENALIZED_ALL_MISSING_FITTING_FEATURE', 'PENALIZED_BINARY_OUTCOME_REQUIRED',
    'PENALIZED_CATEGORY_FEATURE_INVALID', 'PENALIZED_CONSTANT_FITTING_RESPONSE',
    'PENALIZED_DATA_INVALID', 'PENALIZED_DISTINCT_EXTERNAL_COHORT_REQUIRED',
    'PENALIZED_ENCODED_LIMIT', 'PENALIZED_ENGINE_UNAVAILABLE', 'PENALIZED_ENGINE_VERSION_MISMATCH',
    'PENALIZED_EXTERNAL_PARTITION_REQUIRED', 'PENALIZED_FEATURES_INVALID', 'PENALIZED_FEATURE_LIMIT',
    'PENALIZED_FITTING_CLASS_COUNT_BELOW_EIGHT', 'PENALIZED_FORBIDDEN_OR_DUPLICATE_FEATURE',
    'PENALIZED_FROZEN_ENGINE_MISMATCH', 'PENALIZED_FROZEN_MODEL_INVALID',
    'PENALIZED_FROZEN_SEMANTICS_OR_SPEC_MISMATCH', 'PENALIZED_GLMNET_ERROR',
    'PENALIZED_GLMNET_JERR', 'PENALIZED_GLMNET_WARNING', 'PENALIZED_GROUP_IDS_REQUIRED',
    'PENALIZED_GROUP_PARTITION_OR_FOLD_LEAKAGE', 'PENALIZED_INSUFFICIENT_NONCONSTANT_COLUMNS',
    'PENALIZED_LAMBDA_GRID_INVALID', 'PENALIZED_NONFINITE_COEFFICIENTS',
    'PENALIZED_NONFINITE_DESIGN', 'PENALIZED_NONFINITE_FEATURE_SCALE',
    'PENALIZED_NONFINITE_LINEAR_PREDICTOR', 'PENALIZED_NONFINITE_LOSS',
    'PENALIZED_NONFINITE_METRIC', 'PENALIZED_NONFINITE_PREDICTION',
    'PENALIZED_NONFINITE_RESPONSE_SCALE', 'PENALIZED_NUMERIC_EXECUTION_FAILED',
    'PENALIZED_NUMERIC_FEATURE_INVALID', 'PENALIZED_OBSERVED_OUTCOME_REQUIRED',
    'PENALIZED_OPTIONS_INVALID', 'PENALIZED_PARTITION_OR_FOLD_INVALID',
    'PENALIZED_REQUESTED_LAMBDA_PATH_MISSING', 'PENALIZED_REQUIRED_COLUMN_ABSENT',
    'PENALIZED_SEMANTICS_INVALID', 'PENALIZED_SPEC_INVALID', 'PENALIZED_SPEC_UNSUPPORTED',
    'PENALIZED_SPLIT_INVALID', 'PENALIZED_THRESHOLD_INVALID', 'PENALIZED_TRAINING_GROUP_OVERLAP',
    'PENALIZED_TRAINING_SUBJECT_OVERLAP', 'PENALIZED_UNDECLARED_CATEGORY',
    'PENALIZED_UNEXPECTED_FROZEN_MODEL', 'PENALIZED_UNIQUE_STRING_IDS_REQUIRED',
    'PENALIZED_UNKNOWN_OBSERVED_CATEGORY',
]
PEN_FAILURE = {'enum': PEN_FAILURE_CODES}
PEN_FAILURE_OR_NULL = {'anyOf': [PEN_FAILURE, NULL]}
PEN_EMPTY = {'type': 'array', 'maxItems': 0}
PEN_VARIABLE_PROPERTIES = {
    'name': PEN_NAME, 'dtype': {'enum': ['number', 'category']},
    **{name: S for name in ('unit', 'dimension', 'concept', 'codebook_version')},
    'levels': arr(S), 'reference': {'type': ['string', 'null']},
}
PEN_SEMANTICS = obj({
    'identity': obj({'subject_id': PEN_NAME, 'group_id': {'anyOf': [PEN_NAME, NULL]},
                     'canonical_identity_namespace': TEXT}),
    'features': bounded_array(obj(PEN_VARIABLE_PROPERTIES), 1, 30),
    'outcome': obj({**PEN_VARIABLE_PROPERTIES, 'dtype': {'const': 'number'},
                    'type': {'enum': ['continuous', 'binary']}, 'definition': S,
                    'event': N, 'non_event': N}),
    'time': obj({'unit': {'const': 'hour'}, 'timezone': {'const': 'relative'},
                 'index': NUMBER, 'feature_cutoff': NUMBER,
                 'outcome_window': bounded_array(NUMBER, 2, 2),
                 'boundary': {'const': '[start,end]'}, 'delayed_entry': {'const': False}}),
})
PEN_EVENT_FIELDS = ('n_training_events', 'n_training_non_events', 'n_holdout_events',
                    'n_holdout_non_events', 'n_evaluation_events', 'n_evaluation_non_events')
PEN_FLOW = obj({
    **{name: PEN_COUNT for name in ('n_input', 'n_evaluated', 'n_predicted')},
    **{name: PEN_NULLABLE_COUNT for name in ('n_training', 'n_holdout', 'missing_outcome_n') + PEN_EVENT_FIELDS},
    'n_cv_folds': {'type': 'integer', 'minimum': 0, 'maximum': 5},
    'n_features': {'type': 'integer', 'minimum': 1, 'maximum': 30},
    'n_encoded_columns': C, 'n_dropped_columns': C,
})
PEN_PREPROCESSING = obj({
    'result_id': TEXT, 'stage': {'enum': ['cv', 'final', 'external']},
    'fold': {'anyOf': [PEN_FOLD, NULL]}, 'role': {'enum': ['fitting', 'validation', 'holdout', 'external']},
    'feature': PEN_NAME, 'type': {'enum': ['number', 'category']},
    'fitted_levels': {**arr(S), 'description': 'Fitted category levels are unique and UTF-8 ordered; '
                       'uniqueness and first-level reference are enforced by the semantic validator.'},
    'fitted_reference': {'anyOf': [TEXT, NULL]},
    'encoding_rule': {'enum': ['identity_numeric', 'treatment_utf8_observed_reference_first']},
    **{name: PEN_COUNT for name in ('n_rows', 'n_missing', 'n_imputed')},
})
PEN_PREPROCESSING['anyOf'] = [
    {'properties': {'stage': {'const': 'cv'}, 'fold': PEN_FOLD,
                    'role': {'enum': ['fitting', 'validation']}}},
    {'properties': {'stage': {'const': 'final'}, 'fold': NULL,
                    'role': {'enum': ['fitting', 'holdout']}}},
    {'properties': {'stage': {'const': 'external'}, 'fold': NULL, 'role': {'const': 'external'}}},
]
for pen_preprocessing_scope in PEN_PREPROCESSING['anyOf']:
    pen_preprocessing_scope['anyOf'] = [
        {'properties': {'type': {'const': 'number'}, 'fitted_levels': PEN_EMPTY,
                        'fitted_reference': NULL, 'encoding_rule': {'const': 'identity_numeric'}}},
        {'properties': {'type': {'const': 'category'}, 'fitted_levels': {'minItems': 1},
                        'fitted_reference': TEXT,
                        'encoding_rule': {'const': 'treatment_utf8_observed_reference_first'}}},
    ]
PEN_CV_ROW = obj({
    'result_id': TEXT, 'lambda_index': PEN_INDEX, 'lambda': PEN_POSITIVE,
    'loss_sum': NONNEGATIVE, 'n_validation': PEN_POSITIVE_COUNT,
    'mean_loss': NONNEGATIVE, 'selected': {'type': 'boolean'},
})
PEN_CV_FOLD = obj({
    'result_id': TEXT, 'fold': PEN_FOLD, 'n_training': PEN_POSITIVE_COUNT,
    'n_validation': PEN_POSITIVE_COUNT, 'training_events': PEN_NULLABLE_COUNT,
    'training_non_events': PEN_NULLABLE_COUNT,
    'n_encoded_columns': {'type': 'integer', 'minimum': 2}, 'n_dropped_columns': COUNT,
})
PEN_CV_FOLD_LOSS = obj({
    'result_id': TEXT, 'fold': PEN_FOLD, 'lambda_index': PEN_INDEX,
    'lambda': PEN_POSITIVE, 'engine_lambda': PEN_POSITIVE,
    'loss_sum': NONNEGATIVE, 'n_validation': PEN_POSITIVE_COUNT, 'mean_loss': NONNEGATIVE,
})
PEN_CV = obj({
    'status': {'enum': ['not_run', 'completed', 'unavailable']},
    'reason_code': {'anyOf': [PEN_FAILURE, {'enum': ['NOT_RUN', 'FROZEN_MODEL_NO_REFIT']}, NULL]},
    'selection_rule': {'const': 'min_mean_loss_largest_lambda_tie'},
    'loss_name': {'enum': ['mean_squared_error_original_outcome', 'binomial_log_loss']},
    'weighting': {'const': 'validation_subject_count'}, 'scope': {'const': 'training_only_tuning'},
    'rows': bounded_array(PEN_CV_ROW, 0, 30), 'folds': bounded_array(PEN_CV_FOLD, 0, 5),
    'fold_losses': bounded_array(PEN_CV_FOLD_LOSS, 0, 150),
})
PEN_CV['anyOf'] = [
    {'properties': {'status': {'const': 'not_run'},
                    'reason_code': {'enum': ['NOT_RUN', 'FROZEN_MODEL_NO_REFIT']},
                    **{key: PEN_EMPTY for key in ('rows', 'folds', 'fold_losses')}}},
    {'properties': {'status': {'const': 'completed'}, 'reason_code': NULL,
                    'rows': {'minItems': 2}, 'folds': {'minItems': 3}, 'fold_losses': {'minItems': 6}}},
    {'properties': {'status': {'const': 'unavailable'}, 'reason_code': PEN_FAILURE, 'rows': PEN_EMPTY}},
]
PEN_COEFFICIENT_PROPERTIES = {
    'result_id': TEXT, 'term': TEXT, 'feature': {'anyOf': [PEN_NAME, NULL]},
    'type': {'enum': ['intercept', 'number', 'category']}, 'level': {'type': ['string', 'null']},
    'coefficient': NUMBER, 'nonzero': {'type': 'boolean'},
}
PEN_COEFFICIENT_KINDS = [
    {'properties': {'type': {'const': 'intercept'}, 'term': {'const': '(Intercept)'},
                    'feature': NULL, 'level': NULL}},
    {'properties': {'type': {'const': 'number'}, 'term': {'pattern': '^X[0-9]{4}$'},
                    'feature': PEN_NAME, 'level': NULL}},
    {'properties': {'type': {'const': 'category'}, 'term': {'pattern': '^X[0-9]{4}L[0-9]{4}$'},
                    'feature': PEN_NAME, 'level': S}},
]
for pen_kind in PEN_COEFFICIENT_KINDS:
    pen_kind['anyOf'] = [
        {'properties': {'nonzero': {'const': False}, 'coefficient': {'type': 'number', 'minimum': 0, 'maximum': 0}}},
        {'properties': {'nonzero': {'const': True}, 'coefficient': {'anyOf': [
            PEN_POSITIVE, {'type': 'number', 'maximum': -5e-324}]}}},
    ]
PEN_COEFFICIENT = obj({**PEN_COEFFICIENT_PROPERTIES, 'source': {'enum': ['training', 'frozen_training']}})
PEN_COEFFICIENT['anyOf'] = PEN_COEFFICIENT_KINDS
PEN_PATH = obj({**PEN_COEFFICIENT_PROPERTIES, 'lambda_index': PEN_INDEX,
                'lambda': PEN_POSITIVE, 'engine_lambda': PEN_POSITIVE})
PEN_PATH['anyOf'] = PEN_COEFFICIENT_KINDS

# Error metrics retain raw floating loss sums; AUC retains concordant pairs
# including half-ties. Threshold counts are integers. Undefined ratios preserve
# their actual zero numerator/denominator and carry the specific null reason.
PEN_METRIC_DEFINITIONS = {
    'mae': ('sum_absolute_error', 'evaluated_subjects'),
    'rmse': ('sum_squared_error', 'evaluated_subjects'),
    'training_mean_mae': ('sum_absolute_error', 'evaluated_subjects'),
    'training_mean_rmse': ('sum_squared_error', 'evaluated_subjects'),
    'auc': ('concordant_event_nonevent_pairs_plus_half_ties', 'event_nonevent_pairs'),
    'brier': ('sum_squared_probability_error', 'evaluated_subjects'),
    'log_loss': ('sum_binomial_log_loss', 'evaluated_subjects'),
    'sensitivity': ('true_positives', 'actual_events'),
    'specificity': ('true_negatives', 'actual_non_events'),
    'ppv': ('true_positives', 'predicted_events'),
    'npv': ('true_negatives', 'predicted_non_events'),
    'accuracy': ('correct_classifications', 'evaluated_subjects'),
}
PEN_GAUSSIAN_METRICS = ['mae', 'rmse', 'training_mean_mae', 'training_mean_rmse']
PEN_THRESHOLD_REASONS = {
    'sensitivity': 'NO_EVENTS', 'specificity': 'NO_NON_EVENTS',
    'ppv': 'NO_PREDICTED_EVENTS', 'npv': 'NO_PREDICTED_NON_EVENTS',
}


def penalized_metric_row(name, numerator_semantics, denominator_semantics):
    gaussian = name in PEN_GAUSSIAN_METRICS
    threshold = name in (*PEN_THRESHOLD_REASONS, 'accuracy')
    denominator = {'type': 'integer', 'minimum': 0, 'maximum': 10000 if name == 'auc' else 200}
    row = obj({
        'result_id': TEXT, 'population': {'enum': ['holdout', 'external']}, 'metric': {'const': name},
        'value': N, 'numerator': PEN_COUNT if threshold else NONNEGATIVE, 'denominator': denominator,
        'numerator_semantics': {'const': numerator_semantics},
        'denominator_semantics': {'const': denominator_semantics}, 'reason_code': {'type': ['string', 'null']},
        'ranking_score': {'const': 'logit'} if name == 'auc' else NULL,
        'threshold': PEN_OPEN_PROBABILITY if threshold else NULL, 'n': PEN_POSITIVE_COUNT,
        'events': NULL if gaussian else PEN_COUNT, 'non_events': NULL if gaussian else PEN_COUNT,
    })
    available = {'properties': {
        'value': NONNEGATIVE if gaussian or name == 'log_loss' else PROBABILITY,
        'reason_code': NULL, 'denominator': {**denominator, 'minimum': 1},
    }}
    if name == 'auc':
        available['properties'].update(events=PEN_POSITIVE_COUNT, non_events=PEN_POSITIVE_COUNT)
    elif name == 'sensitivity':
        available['properties']['events'] = PEN_POSITIVE_COUNT
    elif name == 'specificity':
        available['properties']['non_events'] = PEN_POSITIVE_COUNT
    row['anyOf'] = [available]
    reasons = ['NO_EVENTS', 'NO_NON_EVENTS'] if name == 'auc' else [PEN_THRESHOLD_REASONS[name]] if name in PEN_THRESHOLD_REASONS else []
    for reason in reasons:
        unavailable = {'value': NULL, 'numerator': {'type': 'number', 'minimum': 0, 'maximum': 0},
                       'denominator': {'const': 0}, 'reason_code': {'const': reason}}
        if reason == 'NO_EVENTS':
            unavailable.update(events={'const': 0}, non_events=PEN_POSITIVE_COUNT)
        elif reason == 'NO_NON_EVENTS':
            unavailable.update(non_events={'const': 0}, events=PEN_POSITIVE_COUNT)
        row['anyOf'].append({'properties': unavailable})
    return row


PEN_METRIC = {'anyOf': [penalized_metric_row(name, *semantics)
                       for name, semantics in PEN_METRIC_DEFINITIONS.items()]}
PEN_SOLVER_VALUES = {
    'thresh': 1e-10, 'maxit': 100000, 'standardize': False, 'intercept': True,
    'penalty_factor': 'equal_one', 'relax': False, 'type_gaussian': 'covariance', 'type_logistic': 'Newton',
    'fdev': 0, 'devmax': 1, 'eps': 1e-6, 'big': 9.9e35, 'mnlam': 5, 'pmin': 1e-9,
    'exmx': 250, 'itrace': 0, 'prec': 1e-10, 'mxit': 100, 'epsnr': 1e-6, 'mxitnr': 25,
    'trace_it': 0, 'dfmax': 'n_encoded_plus_one', 'pmax': 'n_encoded',
    'lambda_epsilon_multiplier': 32,
}
PEN_SOLVER_INTEGERS = {'maxit', 'mnlam', 'itrace', 'mxit', 'mxitnr', 'trace_it', 'lambda_epsilon_multiplier'}
PEN_SOLVER = obj({name: ({'const': value} if type(value) in (bool, str) or name in PEN_SOLVER_INTEGERS
                        else {'type': 'number', 'minimum': value, 'maximum': value})
                  for name, value in PEN_SOLVER_VALUES.items()})
PEN_FAILURE_STAGES = ['input', 'runtime', 'cv_preprocessing', 'cv_fit', 'cv_validation',
                      'final_preprocessing', 'final_fit', 'holdout_prediction',
                      'external_validation', 'external_prediction', 'metrics']
PEN_DIAGNOSTICS = obj({
    'stage': {'enum': PEN_FAILURE_STAGES + ['complete']}, 'fold': {'anyOf': [PEN_FOLD, NULL]},
    'feature': {'anyOf': [PEN_NAME, NULL]}, 'code': PEN_FAILURE_OR_NULL,
    'warning_count': COUNT, 'jerr': {'type': ['integer', 'null']},
    'n_engine_fits': {'type': 'integer', 'minimum': 0, 'maximum': 6}, 'solver': PEN_SOLVER,
})
PEN_LIMITATIONS = [
    'SYNTHETIC_ENGINEERING_ONLY', 'CV_IS_TUNING_NOT_EXTERNAL_PERFORMANCE',
    'NO_COEFFICIENT_OR_POSTSELECTION_INFERENCE', 'NO_CAUSAL_CLAIM', 'NO_CLINICAL_VALIDATION',
    'PRESPECIFIED_SINGLE_ALPHA_AND_LAMBDA_GRID', 'STRICT_OBSERVED_CATEGORY_SUPPORT',
]
PENALIZED_PREDICTION = obj({
    'result_id': TEXT, 'method_id': TEXT, 'operation': {'enum': ['train', 'evaluate', 'infer']},
    'status': {'enum': ['completed', 'unavailable']}, 'reason_code': PEN_FAILURE_OR_NULL,
    'family': {'enum': ['gaussian', 'binomial']}, 'penalty': {'enum': ['lasso', 'elasticnet']},
    'alpha': {'type': 'number', 'minimum': 5e-324, 'maximum': 1},
    'selected_lambda': {'anyOf': [PEN_POSITIVE, NULL]}, 'selected_engine_lambda': {'anyOf': [PEN_POSITIVE, NULL]},
    'selected_lambda_index': {'anyOf': [PEN_INDEX, NULL]},
    'coefficient_scale': {'enum': ['standardized_x_standardized_y', 'standardized_x_log_odds']},
    'prediction_scale': {'enum': ['signed_original_outcome', 'event_probability']},
    'semantics': PEN_SEMANTICS, 'flow': PEN_FLOW, 'preprocessing': arr(PEN_PREPROCESSING),
    'cv': PEN_CV, 'path': arr(PEN_PATH), 'coefficients': arr(PEN_COEFFICIENT),
    'metrics': bounded_array(PEN_METRIC, 0, 8), 'diagnostics': PEN_DIAGNOSTICS,
    'limitations': {'const': PEN_LIMITATIONS},
})


def penalized_operation_schema(operation, completed, family):
    training = operation == 'train'
    properties = {'operation': {'const': operation}}
    properties['coefficients'] = {'items': {'properties': {'source': {'const': 'training' if training else 'frozen_training'}}}}
    properties['preprocessing'] = {'items': {'properties': {'stage': {'enum': ['cv', 'final']} if training else {'const': 'external'}}}}
    flow = {}
    if not training:
        properties['path'] = PEN_EMPTY
        properties['cv'] = {'properties': {'status': {'const': 'not_run'},
                            'reason_code': {'const': 'FROZEN_MODEL_NO_REFIT'} if completed else {'enum': ['NOT_RUN', 'FROZEN_MODEL_NO_REFIT']}}}
        flow['n_cv_folds'] = {'const': 0}
        properties['diagnostics'] = {'properties': {'n_engine_fits': {'const': 0},
                                     **({'jerr': NULL} if completed else {})}}
    elif completed:
        properties['cv'] = {'properties': {'status': {'const': 'completed'}}}
        properties['path'] = {'minItems': 6}
        flow['n_cv_folds'] = {'type': 'integer', 'minimum': 3, 'maximum': 5}
        properties['diagnostics'] = {'properties': {'n_engine_fits': {'type': 'integer', 'minimum': 4, 'maximum': 6},
                                                  'jerr': {'const': 0}}}
    else:
        properties['cv'] = {'properties': {'reason_code': {'anyOf': [PEN_FAILURE, NULL, {'const': 'NOT_RUN'}]}}}
    if operation == 'infer':
        properties['metrics'] = PEN_EMPTY
        flow.update(n_evaluated={'const': 0}, missing_outcome_n=NULL,
                    **{name: NULL for name in PEN_EVENT_FIELDS})
    elif completed:
        metric_count = {'minItems': 4, 'maxItems': 4} if family == 'gaussian' else {'anyOf': [
            {'minItems': 3, 'maxItems': 3}, {'minItems': 8, 'maxItems': 8}]}
        properties['metrics'] = {**metric_count, 'items': {'properties': {'population': {'const': 'holdout' if training else 'external'}}}}
        flow['missing_outcome_n'] = {'const': 0}
        flow['n_evaluated'] = PEN_POSITIVE_COUNT
        if family == 'binomial':
            flow.update({name: PEN_COUNT for name in PEN_EVENT_FIELDS})
            if not training:
                flow.update({name: {'const': 0} for name in PEN_EVENT_FIELDS[:4]})
    if completed:
        properties['coefficients']['minItems'] = 3
        properties['preprocessing']['minItems'] = 1
        flow.update(n_input=PEN_POSITIVE_COUNT, n_predicted=PEN_POSITIVE_COUNT,
                    n_training=PEN_POSITIVE_COUNT if training else {'const': 0},
                    n_holdout=PEN_POSITIVE_COUNT if training else {'const': 0},
                    n_encoded_columns={'type': 'integer', 'minimum': 2}, n_dropped_columns=COUNT)
    properties['flow'] = {'properties': flow}
    return {'properties': properties}


PENALIZED_PREDICTION['anyOf'] = []
for pen_family in ('gaussian', 'binomial'):
    for pen_penalty in ('lasso', 'elasticnet'):
        pen_gaussian = pen_family == 'gaussian'
        pen_method = ('prediction.continuous.signed.' if pen_gaussian else 'prediction.binary.') + pen_penalty
        pen_family_properties = {
            'method_id': {'const': pen_method}, 'family': {'const': pen_family}, 'penalty': {'const': pen_penalty},
            'alpha': {'type': 'number', 'minimum': 1, 'maximum': 1} if pen_penalty == 'lasso' else PEN_OPEN_PROBABILITY,
            'coefficient_scale': {'const': 'standardized_x_standardized_y' if pen_gaussian else 'standardized_x_log_odds'},
            'prediction_scale': {'const': 'signed_original_outcome' if pen_gaussian else 'event_probability'},
            'semantics': {'properties': {'outcome': {'properties': {
                'type': {'const': 'continuous' if pen_gaussian else 'binary'},
                'event': NULL if pen_gaussian else {'type': 'number', 'minimum': 1, 'maximum': 1},
                'non_event': NULL if pen_gaussian else {'type': 'number', 'minimum': 0, 'maximum': 0},
                **({} if pen_gaussian else {'unit': {'const': '1'}}),
            }}}},
            'cv': {'properties': {
                'loss_name': {'const': 'mean_squared_error_original_outcome' if pen_gaussian else 'binomial_log_loss'},
                'folds': {'items': {'properties': {key: NULL if pen_gaussian else {'type': 'integer', 'minimum': 8, 'maximum': 200}
                                                  for key in ('training_events', 'training_non_events')}}},
            }},
            'metrics': {'items': {'properties': {'metric': {'enum': PEN_GAUSSIAN_METRICS if pen_gaussian else
                             [key for key in PEN_METRIC_DEFINITIONS if key not in PEN_GAUSSIAN_METRICS]}}}},
        }
        if pen_gaussian:
            pen_family_properties['flow'] = {'properties': {key: NULL for key in PEN_EVENT_FIELDS}}
        pen_states = []
        for pen_completed in (True, False):
            pen_state = {
                'status': {'const': 'completed' if pen_completed else 'unavailable'},
                'reason_code': NULL if pen_completed else PEN_FAILURE,
                'selected_lambda': PEN_POSITIVE if pen_completed else NULL,
                'selected_engine_lambda': PEN_POSITIVE if pen_completed else NULL,
                'selected_lambda_index': PEN_INDEX if pen_completed else NULL,
                'diagnostics': {'properties': {
                    'stage': {'const': 'complete'} if pen_completed else {'enum': PEN_FAILURE_STAGES},
                    'code': NULL if pen_completed else PEN_FAILURE,
                    **({'fold': NULL, 'feature': NULL, 'warning_count': {'const': 0}} if pen_completed else {}),
                }},
            }
            if not pen_completed:
                pen_state['metrics'] = PEN_EMPTY
                pen_state['flow'] = {'properties': {'n_evaluated': {'const': 0}, 'n_predicted': {'const': 0},
                                                   'n_encoded_columns': NULL, 'n_dropped_columns': NULL}}
            pen_states.append({'properties': pen_state, 'anyOf': [
                penalized_operation_schema(operation, pen_completed, pen_family)
                for operation in ('train', 'evaluate', 'infer')]})
        PENALIZED_PREDICTION['anyOf'].append({'properties': pen_family_properties, 'anyOf': pen_states})

V08_SCHEMA = with_version(V07_SCHEMA, '0.8.0-candidate1')
V08_SCHEMA['properties']['penalized_prediction'] = {'anyOf': [PENALIZED_PREDICTION, NULL]}
V08_SCHEMA['required'].append('penalized_prediction')
V08_SCHEMA['properties']['metrics']['items']['properties']['model_role']['enum'].append('frozen_penalized_model')

# A frozen affine model has only a score interpretation. Probability conversion
# is separately reported by the binomial nomogram; local contributions, encoded
# background rows and individual identities never belong to these aggregates.
INTERPRETATION_METHODS = {
    'gaussian': ['prediction.continuous.signed.lasso', 'prediction.continuous.signed.elasticnet'],
    'binomial': ['prediction.binary.lasso', 'prediction.binary.elasticnet'],
}
INTERPRETATION_COUNT = {'type': 'integer', 'minimum': 0, 'maximum': 200}
INTERPRETATION_N = {'type': 'integer', 'minimum': 1, 'maximum': 200}
INTERPRETATION_ENCODED = {'type': 'integer', 'minimum': 0, 'maximum': 60}
INTERPRETATION_NAME = {'type': 'string', 'pattern': '^[A-Za-z][A-Za-z0-9_]*$'}
INTERPRETATION_TOLERANCE = {'type': 'number', 'minimum': 1e-10, 'maximum': 1e-10}
INTERPRETATION_FAILURE_CODES = [
    'INTERPRETATION_ALL_MISSING_BACKGROUND_FEATURE', 'INTERPRETATION_BACKGROUND_GROUP_SET_MISMATCH',
    'INTERPRETATION_BACKGROUND_ROWS_INVALID', 'INTERPRETATION_BACKGROUND_SUBJECT_SET_MISMATCH',
    'INTERPRETATION_BACKGROUND_TRANSFORM_MISMATCH',
    'INTERPRETATION_CATEGORY_FEATURE_INVALID', 'INTERPRETATION_DATA_INVALID',
    'INTERPRETATION_DUPLICATE_OBJECT_KEYS', 'INTERPRETATION_EXPLAINER_BINDING_MISMATCH',
    'INTERPRETATION_EXPLAINER_DERIVED_CONTENT_MISMATCH', 'INTERPRETATION_EXPLAINER_FIELDS_INVALID',
    'INTERPRETATION_FROZEN_MODEL_INVALID', 'INTERPRETATION_FROZEN_PREPROCESSING_FAILED',
    'INTERPRETATION_HASH_BINDING_INVALID', 'INTERPRETATION_JSON_HASH_ENGINE_UNAVAILABLE',
    'INTERPRETATION_MODEL_METHOD_UNSUPPORTED', 'INTERPRETATION_NOMOGRAM_BACKCHECK_FAILED',
    'INTERPRETATION_NOMOGRAM_SCALE_UNREPRESENTABLE', 'INTERPRETATION_NONFINITE_BACKGROUND_MEAN',
    'INTERPRETATION_NONFINITE_BASE_VALUE', 'INTERPRETATION_NONFINITE_CONTRIBUTION',
    'INTERPRETATION_NONFINITE_NOMOGRAM_DOMAIN', 'INTERPRETATION_NONFINITE_NOMOGRAM_POINTS',
    'INTERPRETATION_NONFINITE_SCORE_PARAMETERS', 'INTERPRETATION_NUMERIC_EXECUTION_FAILED',
    'INTERPRETATION_NUMERIC_FEATURE_INVALID', 'INTERPRETATION_NUMERIC_OUT_OF_DOMAIN',
    'INTERPRETATION_REQUIRED_COLUMN_ABSENT', 'INTERPRETATION_SHAP_ADDITIVITY_FAILED',
    'INTERPRETATION_TRAINING_GROUP_OVERLAP', 'INTERPRETATION_TRAINING_PARTITION_REQUIRED',
    'INTERPRETATION_TRAINING_SUBJECT_OVERLAP', 'INTERPRETATION_UNIQUE_STRING_IDS_REQUIRED',
    'INTERPRETATION_UNKNOWN_CATEGORY',
]
INTERPRETATION_FAILURE = {'enum': INTERPRETATION_FAILURE_CODES}
INTERPRETATION_DEFINITION = obj({
    'method': {'const': 'exact_affine_grouped_interventional_shap'},
    'background': {'const': 'full_frozen_training_empirical'},
    'coalition_unit': {'const': 'raw_feature'}, 'missing_policy': {'const': 'frozen_training_median_mode'},
    'score_scale': {'enum': ['signed_original_outcome', 'logit']},
    'score_unit': {**TEXT, 'description': 'Frozen outcome unit for Gaussian; dimensionless 1 for binomial log odds.'},
    'conditional': {'const': False}, 'probability_scale': {'const': False}, 'causal': {'const': False},
})
INTERPRETATION_FLOW = obj({
    'n_background': {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 200},
    'n_application': INTERPRETATION_COUNT,
    'n_features': {'type': 'integer', 'minimum': 1, 'maximum': 12},
    'n_encoded_columns': {'type': 'integer', 'minimum': 2, 'maximum': 60},
    'n_background_groups': INTERPRETATION_COUNT,
    'missing_by_feature': {'type': 'object', 'additionalProperties': obj({
        'n_background_missing': INTERPRETATION_COUNT, 'n_application_missing': INTERPRETATION_COUNT,
    })},
})
INTERPRETATION_IMPORTANCE = obj({
    'result_id': TEXT, 'feature': INTERPRETATION_NAME, 'type': {'enum': ['number', 'category']},
    'n': INTERPRETATION_N, 'sum_abs_shap': NONNEGATIVE, 'mean_abs_shap': NONNEGATIVE,
    **{name: NUMBER for name in ('mean_shap', 'min_shap', 'max_shap')},
})
INTERPRETATION_ADDITIVITY = obj({
    'atol': INTERPRETATION_TOLERANCE, 'rtol': INTERPRETATION_TOLERANCE,
    'max_abs_error': NULLABLE_NONNEGATIVE, 'passed': {'type': 'boolean'},
})
INTERPRETATION_SHAP = obj({
    'base_value': N, 'global_importance': bounded_array(INTERPRETATION_IMPORTANCE, 0, 12),
    'additivity': INTERPRETATION_ADDITIVITY,
})
INTERPRETATION_DOMAIN = obj({
    'result_id': TEXT, 'feature': INTERPRETATION_NAME, 'type': {'enum': ['number', 'category']}, 'unit': TEXT,
    'observed_min': N, 'observed_max': N,
    'fitted_levels': {**arr(TEXT), 'description': 'Unique UTF-8 ordered fitted levels. '
                       'The semantic validator verifies uniqueness and first-level reference.'},
    'fitted_reference': {'anyOf': [TEXT, NULL]}, 'impute_value': {'type': ['number', 'string']},
    'missing_policy': {'const': 'frozen_training_median_mode'},
    'encoding_rule': {'enum': ['identity_numeric', 'treatment_utf8_observed_reference_first']},
    'n_encoded_columns': INTERPRETATION_ENCODED, 'score_min': NUMBER, 'score_max': NUMBER,
    'score_range': NONNEGATIVE,
})
INTERPRETATION_DOMAIN['anyOf'] = [
    {'properties': {'type': {'const': 'number'}, 'observed_min': NUMBER, 'observed_max': NUMBER,
                    'fitted_levels': {'maxItems': 0}, 'fitted_reference': NULL, 'impute_value': NUMBER,
                    'encoding_rule': {'const': 'identity_numeric'},
                    'n_encoded_columns': {'type': 'integer', 'minimum': 0, 'maximum': 1}}},
    {'properties': {'type': {'const': 'category'}, 'observed_min': NULL, 'observed_max': NULL,
                    'fitted_levels': {'minItems': 1}, 'fitted_reference': TEXT, 'impute_value': TEXT,
                    'encoding_rule': {'const': 'treatment_utf8_observed_reference_first'}}},
]
INTERPRETATION_AXIS = obj({
    'result_id': TEXT, 'feature': INTERPRETATION_NAME, 'type': {'enum': ['number', 'category']}, 'unit': TEXT,
    'input_kind': {'enum': ['value', 'missing']}, 'value': {'type': ['number', 'string', 'null']},
    'resolved_value': {'type': ['number', 'string']}, 'score_contribution': NUMBER, 'points': NONNEGATIVE,
})
INTERPRETATION_AXIS['anyOf'] = [
    {'properties': {'type': {'const': kind}, 'resolved_value': value_type}, 'anyOf': [
        {'properties': {'input_kind': {'const': 'value'}, 'value': value_type}},
        {'properties': {'input_kind': {'const': 'missing'}, 'value': NULL}},
    ]}
    for kind, value_type in (('number', NUMBER), ('category', TEXT))
]
INTERPRETATION_TOTAL_AXIS = obj({
    'result_id': TEXT, 'total_points': NONNEGATIVE, 'score': NUMBER, 'prediction': NUMBER,
})
INTERPRETATION_BACKCHECK = obj({
    'atol': INTERPRETATION_TOLERANCE, 'rtol': INTERPRETATION_TOLERANCE,
    'max_score_abs_error': NULLABLE_NONNEGATIVE, 'max_prediction_abs_error': NULLABLE_NONNEGATIVE,
    'passed': {'type': 'boolean'},
})
INTERPRETATION_NOMOGRAM = obj({
    'domain_policy': {'const': 'frozen_training_observed'}, 'constant_model': {'type': ['boolean', 'null']},
    'score_at_zero': N, 'score_per_point': {'anyOf': [PEN_POSITIVE, NULL]},
    'points_denominator': NULLABLE_NONNEGATIVE, 'max_total_points': NULLABLE_NONNEGATIVE,
    'domains': bounded_array(INTERPRETATION_DOMAIN, 0, 12), 'axes': arr(INTERPRETATION_AXIS),
    'total_axis': arr(INTERPRETATION_TOTAL_AXIS), 'backcheck': INTERPRETATION_BACKCHECK,
})
INTERPRETATION_FAILURE_STAGES = ['input', 'model_validation', 'bundle_validation', 'application_validation',
                                 'frozen_prediction', 'shap', 'nomogram']
INTERPRETATION_DIAGNOSTICS = obj({
    'stage': {'enum': INTERPRETATION_FAILURE_STAGES + ['complete']},
    'feature': {'anyOf': [INTERPRETATION_NAME, NULL]},
    'refit': {'const': False}, 'outcomes_used': {'const': False}, 'background_sampling': {'const': False},
})
INTERPRETATION_LIMITATIONS = [
    'SYNTHETIC_ENGINEERING_ONLY', 'INTERVENTIONAL_NOT_CONDITIONAL_SHAP', 'NOT_PROBABILITY_SCALE_SHAP',
    'NO_CAUSAL_INTERPRETATION', 'NO_CLINICAL_VALIDATION', 'FROZEN_TRAINING_DOMAIN_ONLY',
]
INTERPRETATION = obj({
    'result_id': TEXT, 'method_id': {'const': 'interpretation.linear.interventional'},
    'model_method_id': {'enum': [method for methods in INTERPRETATION_METHODS.values() for method in methods]},
    'family': {'enum': ['gaussian', 'binomial']}, 'status': {'enum': ['completed', 'unavailable']},
    'reason_code': {'anyOf': [INTERPRETATION_FAILURE, NULL]},
    'model_sha256': SHA256, 'provider_version': SHA256,
    **{name: {'anyOf': [SHA256, NULL]} for name in ('explainer_sha256', 'background_sha256', 'transform_sha256')},
    'definition': INTERPRETATION_DEFINITION, 'flow': INTERPRETATION_FLOW, 'shap': INTERPRETATION_SHAP,
    'nomogram': INTERPRETATION_NOMOGRAM, 'diagnostics': INTERPRETATION_DIAGNOSTICS,
    'limitations': {'const': INTERPRETATION_LIMITATIONS},
})
INTERPRETATION_COMPLETED = {
    'status': {'const': 'completed'}, 'reason_code': NULL,
    **{name: SHA256 for name in ('explainer_sha256', 'background_sha256', 'transform_sha256')},
    'flow': {'properties': {'n_background': INTERPRETATION_N, 'n_application': INTERPRETATION_N}},
    'shap': {'properties': {'base_value': NUMBER, 'global_importance': {'minItems': 1},
                           'additivity': {'properties': {'max_abs_error': NONNEGATIVE, 'passed': {'const': True}}}}},
    'nomogram': {'properties': {'score_at_zero': NUMBER, 'domains': {'minItems': 1}, 'axes': {'minItems': 2},
                               'backcheck': {'properties': {'max_score_abs_error': NONNEGATIVE,
                                    'max_prediction_abs_error': NONNEGATIVE, 'passed': {'const': True}}}}},
    'diagnostics': {'properties': {'stage': {'const': 'complete'}, 'feature': NULL}},
}
INTERPRETATION_CONSTANT_STATES = [
    {'properties': {'nomogram': {'properties': {
        'constant_model': {'const': True}, 'score_per_point': NULL,
        'points_denominator': {'type': 'number', 'minimum': 0, 'maximum': 0},
        'max_total_points': {'type': 'number', 'minimum': 0, 'maximum': 0},
        'domains': {'items': {'properties': {'score_range': {'type': 'number', 'minimum': 0, 'maximum': 0}}}},
        'axes': {'items': {'properties': {'points': {'type': 'number', 'minimum': 0, 'maximum': 0}}}},
        'total_axis': {'minItems': 1, 'maxItems': 1,
                       'items': {'properties': {'total_points': {'type': 'number', 'minimum': 0, 'maximum': 0}}}},
    }}}},
    {'properties': {'nomogram': {'properties': {
        'constant_model': {'const': False}, 'score_per_point': PEN_POSITIVE,
        'points_denominator': PEN_POSITIVE, 'max_total_points': PEN_POSITIVE,
        'total_axis': {'minItems': 2},
    }}}},
]
INTERPRETATION_EMPTY_SHAP = {'properties': {
    'base_value': NULL, 'global_importance': {'maxItems': 0},
    'additivity': {'properties': {'max_abs_error': NULL, 'passed': {'const': False}}},
}}
INTERPRETATION_EMPTY_NOMOGRAM = {'properties': {
    **{name: NULL for name in ('constant_model', 'score_at_zero', 'score_per_point',
                               'points_denominator', 'max_total_points')},
    **{name: {'maxItems': 0} for name in ('domains', 'axes', 'total_axis')},
    'backcheck': {'properties': {'max_score_abs_error': NULL, 'max_prediction_abs_error': NULL,
                                 'passed': {'const': False}}},
}}
INTERPRETATION_UNAVAILABLE = {'properties': {
    'status': {'const': 'unavailable'}, 'reason_code': INTERPRETATION_FAILURE,
    'nomogram': INTERPRETATION_EMPTY_NOMOGRAM,
}, 'anyOf': [
    {'properties': {'diagnostics': {'properties': {'stage': {'enum': INTERPRETATION_FAILURE_STAGES[:-1]}}},
                    'shap': INTERPRETATION_EMPTY_SHAP}},
    {'properties': {'diagnostics': {'properties': {'stage': {'const': 'nomogram'}}},
                    'shap': INTERPRETATION_COMPLETED['shap']}},
]}
INTERPRETATION['anyOf'] = [
    {'properties': {
        'family': {'const': family}, 'model_method_id': {'enum': methods},
        'definition': {'properties': {'score_scale': {'const': 'signed_original_outcome' if family == 'gaussian' else 'logit'},
                                     'score_unit': TEXT if family == 'gaussian' else {'const': '1'}}},
        'nomogram': {'properties': {'total_axis': {'items': {'properties': {
            'prediction': NUMBER if family == 'gaussian' else PROBABILITY}}}}},
    }, 'anyOf': [
        {'properties': INTERPRETATION_COMPLETED, 'anyOf': INTERPRETATION_CONSTANT_STATES},
        INTERPRETATION_UNAVAILABLE,
    ]}
    for family, methods in INTERPRETATION_METHODS.items()
]

V09_SCHEMA = with_version(V08_SCHEMA, '0.9.0-candidate1')
V09_SCHEMA['properties']['interpretation'] = {'anyOf': [INTERPRETATION, NULL]}
V09_SCHEMA['required'].append('interpretation')

# v0.10 adds a separate right-censored Cox prediction aggregate.  Copies of
# shared shapes prevent even accidental widening of any historical branch.
COX_PEN_METHODS = ['prediction.survival.cox.lasso', 'prediction.survival.cox.elasticnet']
COX_PEN_FAILURE_CODES = ['COX_PENALIZED_' + code for code in [
    'ALL_MISSING_FITTING_FEATURE', 'BASELINE_COEFFICIENT_REFIT_FORBIDDEN', 'BASELINE_ERROR', 'BASELINE_INVALID',
    'BASELINE_RELATIVE_HAZARD_OUTSIDE_NUMERIC_SUPPORT', 'BASELINE_WARNING', 'BINARY_EVENT_REQUIRED',
    'CATEGORY_FEATURE_INVALID', 'DATA_INVALID', 'DEVIANCE_ERROR', 'DEVIANCE_WARNING',
    'DISTINCT_EXTERNAL_COHORT_REQUIRED', 'ENCODED_LIMIT', 'ENGINE_UNAVAILABLE', 'ENGINE_VERSION_MISMATCH',
    'EXTERNAL_PARTITION_REQUIRED', 'FEATURES_INVALID', 'FITTING_EVENTS_BELOW_EIGHT',
    'FORBIDDEN_OR_DUPLICATE_FEATURE', 'FROZEN_BASELINE_INVALID', 'FROZEN_CV_INVALID', 'FROZEN_ENGINE_MISMATCH',
    'FROZEN_MODEL_INVALID', 'FROZEN_PREPROCESSOR_INVALID', 'FROZEN_SEMANTICS_OR_SPEC_MISMATCH',
    'FROZEN_SOURCE_MISMATCH', 'FROZEN_TRAINING_SUPPORT_INVALID', 'GLMNET_ERROR', 'GLMNET_JERR', 'GLMNET_WARNING',
    'GROUP_IDS_REQUIRED', 'GROUP_PARTITION_OR_FOLD_LEAKAGE', 'HORIZONS_INVALID',
    'HORIZON_OUTSIDE_TRAINING_SUPPORT', 'INSUFFICIENT_NONCONSTANT_COLUMNS', 'INVALID_RISK_PREDICTION',
    'LAMBDA_GRID_INVALID', 'NONFINITE_COEFFICIENTS', 'NONFINITE_DESIGN', 'NONFINITE_FEATURE_SCALE',
    'NONFINITE_LINEAR_PREDICTOR', 'NONFINITE_OR_INVALID_DEVIANCE', 'NO_INFORMATIVE_RISK_SET_CONTRAST',
    'NUMERIC_EXECUTION_FAILED', 'NUMERIC_FEATURE_INVALID', 'OPTIONS_INVALID', 'PARTITION_OR_FOLD_INVALID',
    'POSITIVE_FINITE_DURATION_REQUIRED', 'REQUESTED_LAMBDA_PATH_MISSING', 'REQUIRED_COLUMN_ABSENT',
    'SEMANTICS_INVALID', 'SPEC_INVALID', 'SPEC_UNSUPPORTED', 'SPLIT_INVALID', 'SURVIVAL_SEMANTICS_UNSUPPORTED',
    'TRAINING_GROUP_OVERLAP', 'TRAINING_SUBJECT_OVERLAP', 'UNDECLARED_CATEGORY', 'UNEXPECTED_FROZEN_MODEL',
    'UNIQUE_STRING_IDS_REQUIRED', 'UNKNOWN_OBSERVED_CATEGORY', 'VALIDATION_EVENTS_BELOW_THREE',
]]
COX_PEN_FAILURE = {'enum': COX_PEN_FAILURE_CODES}
COX_PEN_FAILURE_OR_NULL = {'anyOf': [COX_PEN_FAILURE, NULL]}
COX_PEN_SURVIVAL = obj({
    'outcome_type': {'const': 'single_event_right_censored'}, 'time_unit': {'enum': ['day', 'hour']},
    'time_zero_definition': TEXT, 'event_definition': TEXT, 'censoring_definition': TEXT,
    'event_code': {'type': 'number', 'minimum': 1, 'maximum': 1},
    'censor_code': {'type': 'number', 'minimum': 0, 'maximum': 0}, 'ties': {'const': 'breslow'},
})
COX_PEN_SEMANTICS = obj({
    'identity': copy.deepcopy(PEN_SEMANTICS['properties']['identity']),
    'features': bounded_array(obj(copy.deepcopy(PEN_VARIABLE_PROPERTIES)), 1, 12),
    'duration': obj({**copy.deepcopy(PEN_VARIABLE_PROPERTIES), 'dtype': {'const': 'number'},
                     'unit': {'enum': ['day', 'hour']}, 'dimension': {'const': 'time'},
                     'levels': PEN_EMPTY, 'reference': NULL}),
    'event': obj({**copy.deepcopy(PEN_VARIABLE_PROPERTIES), 'dtype': {'const': 'number'},
                  'unit': {'const': '1'}, 'dimension': {'const': 'dimensionless'}, 'levels': PEN_EMPTY,
                  'reference': NULL, 'type': {'const': 'time_to_event'}, 'definition': TEXT,
                  'event': {'type': 'number', 'minimum': 1, 'maximum': 1},
                  'non_event': {'type': 'number', 'minimum': 0, 'maximum': 0}}),
    'time': obj({'unit': {'enum': ['day', 'hour']}, 'timezone': {'const': 'relative'},
        'index': {'type': 'number', 'minimum': 0, 'maximum': 0}, 'feature_cutoff': {'type': 'number', 'maximum': 0},
        'outcome_window': bounded_array(NUMBER, 2, 2), 'boundary': {'const': '(0,end]'},
        'delayed_entry': {'const': False}}),
    'survival': COX_PEN_SURVIVAL,
})
COX_PEN_EVENT_FIELDS = ('n_training_events', 'n_training_censored', 'n_holdout_events', 'n_holdout_censored')
COX_PEN_FLOW = obj({
    **{key: PEN_COUNT for key in ('n_input', 'n_predicted')},
    **{key: PEN_NULLABLE_COUNT for key in ('n_training', 'n_holdout', 'missing_duration_n', 'missing_event_n') + COX_PEN_EVENT_FIELDS},
    'n_cv_folds': {'type': 'integer', 'minimum': 0, 'maximum': 5},
    'n_features': {'type': 'integer', 'minimum': 1, 'maximum': 12},
    'n_encoded_columns': {'type': ['integer', 'null'], 'minimum': 2, 'maximum': 60},
    'n_dropped_columns': {'type': ['integer', 'null'], 'minimum': 0, 'maximum': 60},
})
COX_PEN_DROPPED = obj({'term': TEXT, 'feature': PEN_NAME, 'type': {'enum': ['number', 'category']},
    'level': {'type': ['string', 'null']}, 'reason_code': {'const': 'ZERO_VARIANCE'}})
COX_PEN_DROPPED['anyOf'] = [
    {'properties': {'type': {'const': 'number'}, 'term': {'pattern': '^X[0-9]{4}$'}, 'level': NULL}},
    {'properties': {'type': {'const': 'category'}, 'term': {'pattern': '^X[0-9]{4}L[0-9]{4}$'}, 'level': TEXT}},
]
COX_PEN_CV_ROW = obj({'result_id': TEXT, 'lambda_index': PEN_INDEX, 'lambda': PEN_POSITIVE,
    'deviance_sum': NONNEGATIVE, 'validation_events': PEN_POSITIVE_COUNT,
    'deviance_per_event': NONNEGATIVE, 'selected': {'type': 'boolean'}})
COX_PEN_CV_FOLD = obj({'result_id': TEXT, 'fold': PEN_FOLD, 'n_training': PEN_POSITIVE_COUNT,
    'n_validation': PEN_POSITIVE_COUNT, 'training_events': {'type': 'integer', 'minimum': 8, 'maximum': 200},
    'training_censored': PEN_COUNT, 'validation_events': PEN_COUNT, 'validation_censored': PEN_COUNT,
    'n_encoded_columns': {'type': 'integer', 'minimum': 2, 'maximum': 60},
    'n_dropped_columns': {'type': 'integer', 'minimum': 0, 'maximum': 60},
    'dropped_columns': bounded_array(COX_PEN_DROPPED, 0, 60), 'jerr': {'const': 0}, 'warning_count': {'const': 0}})
COX_PEN_CV_FOLD_LOSS = obj({'result_id': TEXT, 'fold': PEN_FOLD, 'lambda_index': PEN_INDEX,
    'lambda': PEN_POSITIVE, 'engine_lambda': PEN_POSITIVE, 'deviance_sum': NONNEGATIVE,
    'validation_events': {'type': 'integer', 'minimum': 3, 'maximum': 200}, 'deviance_per_event': NONNEGATIVE})
COX_PEN_CV = obj({'status': {'enum': ['not_run', 'completed', 'unavailable']},
    'reason_code': {'anyOf': [COX_PEN_FAILURE, {'enum': ['NOT_RUN', 'FROZEN_MODEL_NO_REFIT']}, NULL]},
    'selection_rule': {'const': 'min_deviance_per_event_largest_lambda_tie'},
    'loss_name': {'const': 'heldout_only_breslow_partial_likelihood_deviance'},
    'weighting': {'const': 'validation_event_count'}, 'scope': {'const': 'training_only_tuning'},
    'rows': bounded_array(COX_PEN_CV_ROW, 0, 30), 'folds': bounded_array(COX_PEN_CV_FOLD, 0, 5),
    'fold_losses': bounded_array(COX_PEN_CV_FOLD_LOSS, 0, 150)})
COX_PEN_CV['anyOf'] = [
    {'properties': {'status': {'const': 'not_run'}, 'reason_code': {'enum': ['NOT_RUN', 'FROZEN_MODEL_NO_REFIT']},
        **{key: PEN_EMPTY for key in ('rows', 'folds', 'fold_losses')}}},
    {'properties': {'status': {'const': 'completed'}, 'reason_code': NULL, 'rows': {'minItems': 2},
        'folds': {'minItems': 3, 'items': {'properties': {'validation_events': {'minimum': 3}}}},
        'fold_losses': {'minItems': 6}}},
    {'properties': {'status': {'const': 'unavailable'}, 'reason_code': COX_PEN_FAILURE, 'rows': PEN_EMPTY}},
]
COX_PEN_COEFFICIENT_PROPERTIES = {**copy.deepcopy(PEN_COEFFICIENT_PROPERTIES),
    'feature': PEN_NAME, 'type': {'enum': ['number', 'category']}}
COX_PEN_COEFFICIENT_KINDS = copy.deepcopy(PEN_COEFFICIENT_KINDS[1:])
COX_PEN_COEFFICIENT = obj({**COX_PEN_COEFFICIENT_PROPERTIES, 'source': {'enum': ['training', 'frozen_training']}})
COX_PEN_COEFFICIENT['anyOf'] = COX_PEN_COEFFICIENT_KINDS
COX_PEN_PATH = obj({**COX_PEN_COEFFICIENT_PROPERTIES, 'lambda_index': PEN_INDEX,
                    'lambda': PEN_POSITIVE, 'engine_lambda': PEN_POSITIVE})
COX_PEN_PATH['anyOf'] = copy.deepcopy(COX_PEN_COEFFICIENT_KINDS)
COX_PEN_BASELINE = obj({'result_id': TEXT, 'method': {'const': 'offset_only_breslow'},
    'reference_center': N, 'event_time_count': PEN_NULLABLE_COUNT,
    'last_event_time': {'anyOf': [PEN_POSITIVE, NULL]}, 'max_followup': {'anyOf': [PEN_POSITIVE, NULL]},
    'time_unit': {'enum': ['day', 'hour']}, 'ties': {'const': 'breslow'},
    'event_boundary': {'const': 'event_at_t_included'}, 'coefficient_updates': {'const': 0}})
COX_PEN_HORIZON = obj({'result_id': TEXT, 'population': {'enum': ['training', 'holdout', 'external']},
    'horizon': NONNEGATIVE, 'time_unit': {'enum': ['day', 'hour']}, 'n_predicted': PEN_POSITIVE_COUNT,
    'min_risk': PROBABILITY, 'max_risk': PROBABILITY, 'mean_risk': PROBABILITY})
COX_PEN_SOLVER_VALUES = {key: value for key, value in PEN_SOLVER_VALUES.items()
                         if key not in ('type_gaussian', 'type_logistic')}
COX_PEN_SOLVER_VALUES.update(intercept='none', family='cox', cox_ties='breslow')
COX_PEN_SOLVER = obj({name: ({'const': value} if type(value) in (bool, str) or name in PEN_SOLVER_INTEGERS
                            else {'type': 'number', 'minimum': value, 'maximum': value})
                      for name, value in COX_PEN_SOLVER_VALUES.items()})
COX_PEN_FAILURE_STAGES = ['input', 'runtime', 'cv_preprocessing', 'cv_fit', 'cv_validation',
    'final_preprocessing', 'final_fit', 'training_baseline', 'holdout_prediction', 'external_validation', 'external_prediction']
COX_PEN_DIAGNOSTICS = obj({'stage': {'enum': COX_PEN_FAILURE_STAGES + ['complete']},
    'fold': {'anyOf': [PEN_FOLD, NULL]}, 'feature': {'anyOf': [PEN_NAME, NULL]}, 'code': COX_PEN_FAILURE_OR_NULL,
    'warning_count': COUNT, 'jerr': {'type': ['integer', 'null']},
    'n_engine_fits': {'type': 'integer', 'minimum': 0, 'maximum': 6}, 'solver': COX_PEN_SOLVER})
COX_PEN_LIMITATIONS = ['SYNTHETIC_ENGINEERING_ONLY', 'CV_IS_TUNING_NOT_EXTERNAL_PERFORMANCE',
    'HELDOUT_ONLY_EVENT_WEIGHTED_CV_NOT_GROUPED_CV', 'ENGINEERING_SUPPORT_NOT_SAMPLE_SIZE_JUSTIFICATION',
    'NO_COEFFICIENT_OR_POSTSELECTION_INFERENCE', 'NO_CAUSAL_CLAIM', 'NO_CLINICAL_VALIDATION',
    'NO_FORMAL_PH_TEST_OR_IPCW_ADAPTER', 'NO_V09_SHAP_OR_NOMOGRAM_ADAPTER',
    'PRESPECIFIED_SINGLE_ALPHA_AND_LAMBDA_GRID', 'STRICT_OBSERVED_CATEGORY_SUPPORT',
    'NO_EXTRAPOLATION_BEYOND_TRAINING_FOLLOWUP']
COX_PENALIZED_PREDICTION = obj({'result_id': TEXT, 'method_id': {'enum': COX_PEN_METHODS},
    'operation': {'enum': ['train', 'infer']}, 'status': {'enum': ['completed', 'unavailable']},
    'reason_code': COX_PEN_FAILURE_OR_NULL, 'family': {'const': 'cox'}, 'penalty': {'enum': ['lasso', 'elasticnet']},
    'alpha': {'type': 'number', 'minimum': 5e-324, 'maximum': 1},
    'selected_lambda': {'anyOf': [PEN_POSITIVE, NULL]}, 'selected_engine_lambda': {'anyOf': [PEN_POSITIVE, NULL]},
    'selected_lambda_index': {'anyOf': [PEN_INDEX, NULL]},
    'coefficient_scale': {'const': 'standardized_x_log_relative_hazard'},
    'prediction_scale': {'const': 'cumulative_event_probability'}, 'semantics': COX_PEN_SEMANTICS,
    'flow': COX_PEN_FLOW, 'preprocessing': arr(copy.deepcopy(PEN_PREPROCESSING)), 'cv': COX_PEN_CV,
    'path': bounded_array(COX_PEN_PATH, 0, 1800), 'coefficients': bounded_array(COX_PEN_COEFFICIENT, 0, 60),
    'baseline': COX_PEN_BASELINE, 'horizons': bounded_array(COX_PEN_HORIZON, 0, 16),
    'diagnostics': COX_PEN_DIAGNOSTICS, 'limitations': {'const': COX_PEN_LIMITATIONS}})


def cox_penalized_operation_schema(operation, completed):
    training = operation == 'train'
    properties = {'operation': {'const': operation},
        'coefficients': {'items': {'properties': {'source': {'const': 'training' if training else 'frozen_training'}}}},
        'horizons': {'items': {'properties': {'population': {'enum': ['training', 'holdout'] if training else ['external']}}}},
        'preprocessing': {'items': {'properties': {'stage': {'enum': ['cv', 'final'] if training else ['external']}}}}}
    if training:
        properties['diagnostics'] = {'properties': {'n_engine_fits': {'minimum': 4} if completed else {}}}
        if completed:
            properties.update(cv={'properties': {'status': {'const': 'completed'}}}, path={'minItems': 4},
                horizons={'minItems': 2, **properties['horizons']})
            properties['flow'] = {'properties': {'n_training': PEN_POSITIVE_COUNT, 'n_holdout': PEN_POSITIVE_COUNT,
                'n_cv_folds': {'minimum': 3}, 'missing_duration_n': {'const': 0}, 'missing_event_n': {'const': 0},
                'n_training_events': {'minimum': 9}, **{key: PEN_COUNT for key in COX_PEN_EVENT_FIELDS[1:]}}}
            properties['diagnostics']['properties']['jerr'] = {'const': 0}
    else:
        properties.update(path=PEN_EMPTY, cv={'properties': {'status': {'const': 'not_run'},
            'reason_code': {'const': 'FROZEN_MODEL_NO_REFIT'} if completed else {'enum': ['NOT_RUN', 'FROZEN_MODEL_NO_REFIT']}}},
            flow={'properties': {'n_training': {'const': 0} if completed else PEN_NULLABLE_COUNT,
                'n_holdout': {'const': 0} if completed else PEN_NULLABLE_COUNT, 'n_cv_folds': {'const': 0},
                **{key: NULL for key in COX_PEN_EVENT_FIELDS + ('missing_duration_n', 'missing_event_n')}}},
            diagnostics={'properties': {'n_engine_fits': {'const': 0}, 'jerr': NULL}})
        if completed:
            properties['horizons'].update(minItems=1, maxItems=8)
    return {'properties': properties, 'anyOf': [{'properties': {
        'semantics': {'properties': {
            'duration': {'properties': {'unit': {'const': unit}}},
            'time': {'properties': {'unit': {'const': unit}}},
            'survival': {'properties': {'time_unit': {'const': unit}}}}},
        'baseline': {'properties': {'time_unit': {'const': unit}}},
        'horizons': {'items': {'properties': {'time_unit': {'const': unit}}}},
    }} for unit in ('day', 'hour')]}


COX_PEN_COMPLETED = {'status': {'const': 'completed'}, 'reason_code': NULL,
    'selected_lambda': PEN_POSITIVE, 'selected_engine_lambda': PEN_POSITIVE, 'selected_lambda_index': PEN_INDEX,
    'coefficients': {'minItems': 2}, 'preprocessing': {'minItems': 1},
    'flow': {'properties': {'n_input': PEN_POSITIVE_COUNT, 'n_predicted': PEN_POSITIVE_COUNT,
        'n_encoded_columns': {'type': 'integer', 'minimum': 2, 'maximum': 60},
        'n_dropped_columns': {'type': 'integer', 'minimum': 0, 'maximum': 60}}},
    'baseline': {'properties': {'reference_center': NUMBER, 'event_time_count': PEN_POSITIVE_COUNT,
        'last_event_time': PEN_POSITIVE, 'max_followup': PEN_POSITIVE}},
    'diagnostics': {'properties': {'stage': {'const': 'complete'}, 'fold': NULL, 'feature': NULL,
                                   'code': NULL, 'warning_count': {'const': 0}}}}
COX_PEN_UNAVAILABLE = {'status': {'const': 'unavailable'}, 'reason_code': COX_PEN_FAILURE,
    'selected_lambda': NULL, 'selected_engine_lambda': NULL, 'selected_lambda_index': NULL,
    'coefficients': PEN_EMPTY, 'horizons': PEN_EMPTY,
    'flow': {'properties': {'n_predicted': {'const': 0}, 'n_encoded_columns': NULL, 'n_dropped_columns': NULL}},
    'baseline': {'properties': {key: NULL for key in ('reference_center', 'event_time_count', 'last_event_time', 'max_followup')}},
    'diagnostics': {'properties': {'stage': {'enum': COX_PEN_FAILURE_STAGES}, 'code': COX_PEN_FAILURE}}}
COX_PENALIZED_PREDICTION['anyOf'] = []
for cox_penalty in ('lasso', 'elasticnet'):
    COX_PENALIZED_PREDICTION['anyOf'].append({'properties': {
        'method_id': {'const': 'prediction.survival.cox.' + cox_penalty}, 'penalty': {'const': cox_penalty},
        'alpha': {'type': 'number', 'minimum': 1, 'maximum': 1} if cox_penalty == 'lasso' else PEN_OPEN_PROBABILITY},
        'anyOf': [{'properties': state, 'anyOf': [cox_penalized_operation_schema(operation, completed)
            for operation in ('train', 'infer')]}
            for completed, state in ((True, COX_PEN_COMPLETED), (False, COX_PEN_UNAVAILABLE))]})

V10_SCHEMA = with_version(V09_SCHEMA, '0.10.0-candidate1')
V10_SCHEMA['properties']['cox_penalized_prediction'] = {'anyOf': [COX_PENALIZED_PREDICTION, NULL]}
V10_SCHEMA['required'].append('cox_penalized_prediction')
V10_SCHEMA['properties']['counts']['properties'].update({name: PEN_NULLABLE_COUNT for name in
    ('training_censored', 'holdout_censored', 'missing_duration_n', 'missing_event_n')})
V10_SCHEMA['anyOf'] = [
    {'properties': {'method_id': {'pattern': '^(?!prediction\\.survival\\.cox\\.(?:lasso|elasticnet)$).+$'},
                    'cox_penalized_prediction': NULL}},
    {'properties': {'method_id': {'enum': COX_PEN_METHODS}, 'cox_penalized_prediction': NULL,
                    'execution_status': {'enum': ['blocked', 'failed']}}},
] + [{'properties': {'method_id': {'const': method},
    'cox_penalized_prediction': {'type': 'object', 'properties': {'method_id': {'const': method}}},
    **{name: PEN_EMPTY for name in ('metrics', 'estimates', 'tests', 'model_results')},
    **{name: NULL for name in ('survival', 'cox_prediction', 'survival_evaluation', 'psm', 'penalized_prediction', 'interpretation')},
}, 'anyOf': [
    {'properties': {'cox_penalized_prediction': {'properties': {'status': {'const': 'completed'}}},
        'execution_status': {'const': 'complete'}, 'applicability_status': {'const': 'pass'},
        'reason_code': NULL, 'binding': {'properties': {'model_hash': SHA256}}}},
    {'properties': {'cox_penalized_prediction': {'properties': {'status': {'const': 'unavailable'}}},
        'execution_status': {'const': 'blocked'}, 'applicability_status': {'const': 'limited'},
        'reason_code': COX_PEN_FAILURE, 'binding': {'properties': {'model_hash': NULL}}}},
]} for method in COX_PEN_METHODS]

VERSION_SCHEMAS = {schema['properties']['core_version']['const']: schema for schema in (
    V01_SCHEMA, V02_SCHEMA, V03_SCHEMA, V04_SCHEMA, V05_SCHEMA, V06_SCHEMA, V07_SCHEMA, V08_SCHEMA, V09_SCHEMA, V10_SCHEMA)}
SCHEMA = {
    '$schema': 'https://json-schema.org/draft/2020-12/schema',
    '$id': V10_SCHEMA['$id'],
    'description': 'Closed v0.10 Cox penalized prediction aggregates and unchanged v0.1-v0.9 contracts. '
                   'Single-event right-censored risk uses training-only offset Breslow baseline and frozen support. '
                   'Event-weighted held-out risk-set deviance is tuning, without absolute-risk validation or PH testing. '
                   'Raw-feature interventional SHAP uses the full frozen training empirical background; '
                   'binomial attribution is on log odds and the nomogram separately transforms to probability. '
                   'CV and coefficient paths come only from training; external application uses a frozen model. '
                   'Signed Gaussian predictions retain original outcome units; no coefficient or postselection inference. '
                   'Matched contrasts target retained matched treated subjects only under unverified assumptions; '
                   'paired inference conditions on formed pairs and omits propensity and match-selection uncertainty. '
                   'IPCW evaluation keeps the risk model frozen and reports raw weighted denominators. '
                   'Censoring assumptions, clinical validity and uncertainty are not established. '
                   'PH tests do not verify proportional hazards; Cox prediction summaries are predictions.',
    'anyOf': [{key: value for key, value in schema.items() if key not in ('$schema', '$id')}
              for schema in (V10_SCHEMA, V09_SCHEMA, V08_SCHEMA, V07_SCHEMA, V06_SCHEMA, V05_SCHEMA, V04_SCHEMA, V03_SCHEMA, V02_SCHEMA, V01_SCHEMA)],
}


# Current V1 is maintained as a separately versioned source contract. Resource
# budgets must not mutate the frozen historical candidate schema branches.
STUDY_SCHEMA_PATH = ROOT / 'schemas/study-result.schema.json'
if STUDY_SCHEMA_PATH.is_file():
    STUDY_RESULT_SCHEMA = json.loads(STUDY_SCHEMA_PATH.read_text(encoding='utf-8'))
    SCHEMA['anyOf'].append({key:value for key,value in STUDY_RESULT_SCHEMA.items() if key not in ('$schema','$id')})


if __name__ == '__main__':
    (ROOT/'schemas/result.schema.json').write_text(json.dumps(SCHEMA, indent=2)+'\n', encoding='utf-8')
    print('RESULT_SCHEMA_WRITTEN')
