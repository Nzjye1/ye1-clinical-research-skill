"""Generate owned closed schemas; shared envelopes are read, never changed."""
import copy
import json
from pathlib import Path
from contracts import SPEC, existing
import provider as p

ROOT = Path(__file__).resolve().parent
N = {'type': 'number'}; S = {'type': 'string'}; B = {'type': 'boolean'}
NN = {'type': ['number', 'null']}; NS = {'type': ['string', 'null']}
HASH = {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}
NAME = copy.deepcopy(existing.NAME)
def obj(props, required=None):
    return {'type': 'object', 'properties': props, 'required': list(props) if required is None else required, 'additionalProperties': False}
def arr(item): return {'type': 'array', 'items': item}
def nullable(value): return {'anyOf': [value, {'type': 'null'}]}

rf = obj({'n_estimators': N, 'max_depth': N, 'min_samples_leaf': N, 'max_features': {'type': ['string', 'number']}})
hgb = obj({'max_iter': N, 'max_leaf_nodes': N, 'min_samples_leaf': N, 'learning_rate': N, 'l2_regularization': N})
params = {'anyOf': [rf, hgb]}
spec = copy.deepcopy(SPEC)
spec['properties']['tuning']['properties']['candidates']['items'] = params
field = obj({'name': NAME, 'dtype': {'enum': ['id', 'number', 'category', 'time']},
             'role': {'enum': ['id', 'feature', 'outcome', 'split', 'time', 'label_time']},
             'unit': {'type': 'string', 'minLength': 1}, 'occurred_at': N, 'available_at': N})
data_contract = obj({'grain': {'const': 'subject'}, 'subject_key': NAME, 'record_keys': arr(NAME),
    'group_key': nullable(NAME), 'identity_namespace': {'type': 'string', 'minLength': 1},
    'fields': arr(field), 'independent_subjects': {'const': True},
    'time': obj({'unit': {'enum': ['hour', 'day']}, 'origin': {'type': 'string', 'minLength': 1},
                 'prediction_at': N, 'outcome_start': N, 'outcome_end': N, 'analysis_as_of': N}),
    'missing': obj({'strategy': {'const': 'train_median_mode'}, 'fit_scope': {'enum': ['training_only', 'frozen_only']}}),
    'weights': obj({'kind': {'const': 'none'}, 'field': {'type': 'null'}})})
payload = obj({'rows': {'type': 'array', 'minItems': 1, 'maxItems': 100000,
    'items': {'type': 'object', 'additionalProperties': {'type': ['string', 'number', 'null']},
              'description': 'Dynamic row names MUST exactly follow the fields declaration at runtime; unknown row keys are rejected.'}},
    'spec': spec, 'data_contract': data_contract, 'frozen_model_json': NS, 'explain_with_outcomes': B,
    'application_scope': {'enum':['development','external','development_holdout']}})

count_keys = ['total_n','total_events','total_nonevents','missing_outcome_n','missing_feature_excluded_n','analyzable_n',
    'analyzable_events','analyzable_nonevents','training_n','training_events','training_nonevents','holdout_n','holdout_events',
    'holdout_nonevents','model_fit_n','model_fit_events','model_fit_nonevents','calibration_n','calibration_events',
    'calibration_nonevents','prediction_n','evaluation_n','source_rows','evaluation_events','evaluation_nonevents']
counts = obj({k: {'type': ['integer', 'null'], 'minimum': 0} for k in count_keys}, [])
sample = obj({k: N for k in ['n','events','nonevents']})
runtime = obj({k:S for k in p.runtime()})
fit = obj({'transformed_feature_count': N, 'epv_status': S, 'calibration': obj({'method': S,'sample':sample}),
           'native_freeze_max_abs_difference': N, 'early_stopping': B, 'selected_parameters': params})
diagnostics = obj({'stage': S, 'provider_version': HASH, 'runtime': runtime, 'counts': counts, 'fit_metadata': nullable(fit),
    'bindings_checked': S, 'model_refitted': B, 'preprocessing_refitted': B, 'calibration_refitted': B})
calibration = obj({'intercept_in_large': NN, 'intercept': NN, 'slope': NN, 'status': S, 'note': S},
                  ['intercept_in_large','intercept','slope','status'])
bootstrap = obj({'requested': N,'successful': N,'method': S,'independent_subjects_explicitly_declared': B,
    'cluster_resampling': B,'group_split_note': S,'intervals95': obj({k:nullable(arr(N)) for k in ['auc','average_precision','brier']}),
    'calibration_intervals': {'type':'null'}})
point = obj({**{k:N for k in ['threshold','n','true_positive','false_positive','true_negative','false_negative','sensitivity','specificity','accuracy']},
             'positive_predictive_value': NN,'negative_predictive_value': NN,'positive_rule': S,'threshold_source': S,'clinical_use_note': S})
threshold = obj({'dca_role': S,'clinical_decision_threshold': NN,'threshold_search_performed': B,'external_policy': S})
metrics = obj({'auc': N,'average_precision':N,'brier':N,'calibration':calibration,'bootstrap':bootstrap,
    'calibration_bins':arr(obj({'n':N,'predicted_mean':N,'observed_fraction':N})),
    'aggregate_roc_pr':arr(obj({'threshold':N,'tpr':N,'fpr':N,'recall':N,'precision':NN,'selected_n':N})),
    'plot_contract':S,'dca_thresholds':arr(N),'decision_curve':arr(obj({'threshold':N,'net_benefit':N,'treat_all':N,'treat_none':N})),
    'decision_curve_note':S,'threshold_policy':threshold,'clinical_operating_point':nullable(point)})
cv = obj({'status':S,'folds':N,'tuning_metric':S,'candidates':arr(obj({'candidate_index':N,'parameters':params,
    'weighted_log_loss':N,'folds':arr(obj({'training_n':N,'validation_n':N,'log_loss':N}))})),
    'selected_candidate_index':N,'tie_break':S,'scope':S,'performance_role':S})
explanation = obj({'method':S,'shap_status':S,'evaluation_n':N,'model_refitted':B,
    'permutation':arr(obj({'feature':S,'increase_in_log_loss_mean':N,'repeat_sd':N,'repeats':N})),
    'partial_dependence':arr(obj({'feature':S,'value':{'type':['string','number']},'mean_probability':N,'n':N,'grid_source':S})),
    'scope':S,'limitations':arr(S),'evaluation_set':S})
public = obj({'status': {'enum':['ESTIMATED','INFERENCE_COMPLETE','EXPLAINED']},'counts':counts,'validation':S,
              'metrics':nullable(metrics),'internal_cv':nullable(cv),'explanation':nullable(explanation),'limitations':arr(S)})
private = obj({'frozen_model_json': S,'individual':arr(obj({'row_index':{'type':'integer','minimum':0},
    'prediction':{'type':'number','minimum':0,'maximum':1},'partition':{'enum':['model_fit','calibration','holdout','evaluate','infer']}}))})
(ROOT/'schemas').mkdir(exist_ok=True)
for name,value in [('payload',payload),('diagnostics',diagnostics),('public-record',public),('private-record',private)]:
    value={'$schema':'https://json-schema.org/draft/2020-12/schema', **value}
    (ROOT/'schemas'/f'{name}.schema.json').write_text(json.dumps(value,indent=2),encoding='utf-8')

manifest={'schema_version':'clinical-module-integration@1.0','module_id':'nonlinear_prediction',
    'owner':'MODULE_NONLINEAR_PREDICTION','language':'python','entrypoint':{'path':'interface.py','function':'analyze'},
    'projection_entrypoint':{'path':'projection.R','function':'project_nonlinear_module'},
    'provider_files':['provider.py','adapter.py','contracts.py','interface.py','projection.R','run_module.py','tests/render.R'],
    'dependencies':[{'name':k,'version':v,'role':'numerical_owner' if k=='sklearn' else 'runtime'} for k,v in p.runtime().items()]+[
        {'name':'R','version':'4.6.1','role':'runtime'},{'name':'jsonlite','version':'2.0.0','role':'runtime'},
        {'name':'digest','version':'0.6.39','role':'runtime'}],
    'methods':[{'method_id':method,'method_version':'1.0.0-module','operations':['train','evaluate','infer','explain'],
        'numerical_owner':'sklearn.'+('ensemble.RandomForestClassifier' if kind=='random_forest' else 'ensemble.HistGradientBoostingClassifier')+'@1.9.1; sigmoid=sklearn.CalibratedClassifierCV; evaluation=clinical_methods.prediction',
        'schemas':{'payload':'schemas/payload.schema.json','diagnostics':'schemas/diagnostics.schema.json',
                   'public_record':'schemas/public-record.schema.json','private_record':'schemas/private-record.schema.json'}} for method,kind in p.METHODS.items()],
    'shared_change_requests':[{'target':'method registry and shared prediction contract',
        'reason':'Register both methods and the owned schemas; call analyze only after trusted expected-bindings validation.',
        'affected_methods':list(p.METHODS),'required_regression':['module facade contract tests','existing prediction rejection branches']},
        {'target':'clinical_prediction_common.R binary predicate/model_role and result extension',
        'reason':'Use shared binary metrics/figures without ridge-only identity; preserve base-fit/calibration counts and explanation artifacts.',
        'affected_methods':list(p.METHODS)+['prediction.binary.ridge'],
        'required_regression':['binary denominators and no-operating-point tests','nonlinear R projection and export audit']}],
    'evidence':['evidence/validation-20261024T033701081933Z/receipt.json','evidence/interface-validation.json']}
import importlib.metadata
for pkg in ['threadpoolctl']:
    manifest['dependencies'].append({'name':pkg,'version':importlib.metadata.version(pkg),'role':'runtime'})
(ROOT/'integration-request.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('OWNED_SCHEMAS_AND_MANIFEST_WRITTEN')
