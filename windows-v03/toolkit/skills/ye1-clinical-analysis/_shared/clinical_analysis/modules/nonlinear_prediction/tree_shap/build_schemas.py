"""Generate only this extension's closed JSON schemas; no shared writes."""
import copy
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SCHEMAS=ROOT/'schemas'
SCHEMAS.mkdir(exist_ok=True)
def obj(props): return {'type':'object','properties':props,'required':list(props),'additionalProperties':False}
def arr(items,minimum=0,maximum=100000): return {'type':'array','items':items,'minItems':minimum,'maxItems':maximum}
S={'type':'string'}; N={'type':'number'}; I={'type':'integer','minimum':0}; B={'type':'boolean'}
H={'type':'string','pattern':'^[0-9a-f]{64}$'}
NULL={'type':'null'}
def nullable(value): return {'anyOf':[value,NULL]}
def const(value): return {'const':value}
def save(name,schema):
    (SCHEMAS/(name+'.schema.json')).write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema',**schema},indent=2)+'\n',encoding='utf-8')
base=json.loads((ROOT.parent/'schemas/payload.schema.json').read_text())
payload={k:copy.deepcopy(v) for k,v in base['properties'].items() if k!='explain_with_outcomes'}
payload['rows']['maxItems']=5000
payload['frozen_model_json']={'type':'string','minLength':1}
payload['application_scope']={'enum':['external','development_holdout']}
payload.update(background_artifact_json={'type':'string','minLength':1},background_sha256=H,feature_perturbation=const('interventional'))
save('payload',obj(payload))
binding=obj({k:nullable(H) if k=='model_sha256' else H for k in ['input_sha256','plan_sha256','code_sha256','runtime_sha256','model_sha256']})
background=obj({'schema_version':const('clinical-tree-shap-background@1.0'), 'prediction_method_id':{'enum':['prediction.binary.random_forest','prediction.binary.hist_gradient_boosting']},
    'model_sha256':H,'prediction_provider_version':H,'sha256':H,
    'source':obj({'origin':const('actual_successful_training_request_and_response'),'cohort_id':S,'identity_namespace':S,
                  'canonical_rows_sha256':H,'training_request_sha256':H,'training_response_sha256':H,'training_bindings':binding,
                  'source_n':I,'outcome_missing_n':I}),
    'partition':obj({'role':const('model_fit'),'model_fit_id_digests':arr(H,1),'calibration_id_digests':arr(H),
                     'holdout_id_digests':arr(H,1),'excluded_outcome_id_digests':arr(H)}),
    'sampling':obj({'method':const('uniform_without_replacement'),'seed':I,'n':{'type':'integer','minimum':10,'maximum':2000},'row_indices':arr(I,10,2000)}),
    'rows':arr({'type':'object','additionalProperties':{'type':['string','number','null']}},10,2000),
    'classification':const('LOCAL_PRIVATE_TRAINING_BACKGROUND'),
    'authenticity':const('hashes_and_partition_checks_are_integrity_only; common_owner_verifies_trusted_original_run')})
save('background',background)
numerics=obj({k:N for k in ['frozen_prediction_max_abs_error','base_additivity_max_abs_error','output_additivity_max_abs_error','probability_reconstruction_max_abs_error']})
runtime=obj({k:S for k in ['python','numpy','scipy','statsmodels','sklearn','pandas','shap','slicer','tqdm','colorama']})
diag=obj({'stage':S,'prediction_provider_version':H,'explanation_provider_version':H,'runtime':nullable(runtime),
          'model_refitted':const(False),'preprocessing_refitted':const(False),'calibration_refitted':const(False),
          'counts':obj({k:nullable(I) for k in ['source_rows','explained_n','background_n']}),'numerical_checks':nullable(numerics),'bindings_checked':S})
save('diagnostics',diag)
public=obj({'status':const('EXPLAINED'),'algorithm':const('official_shap.TreeExplainer'),'feature_perturbation':const('interventional'),
            'output_scale':{'enum':['uncalibrated_probability','uncalibrated_log_odds','calibrated_log_odds']},'base_value':N,'n_explained':I,'n_background':I,
            'encoded_importance':arr(obj({'feature':S,'sum_absolute_contribution':N,'mean_absolute_contribution':N,'n':I}),1,80),
            'variable_aggregates':arr(obj({'variable':S,'encoded_columns':arr(S),'sum_absolute_aggregated_contribution':N,
              'mean_absolute_aggregated_contribution':N,'n':I,'interpretation':const('sum_of_encoded_column_SHAP_not_group_Shapley')}),1,30),
            'importance_definition':S,'limitations':arr(S)})
save('public-record',public)
individual=obj({'row_index':I,'prediction':N,'base_score':N,'explained_output':N,'base_score_shap':arr(N,1,80),
                'contributions':arr(N,1,80),'variable_aggregates':arr(N,1,30),'encoded_values':arr(N,1,80)})
save('private-record',obj({'individual':arr(individual,1,5000),'encoded_features':arr(S,1,80),'variables':arr(S,1,30),
                           'base_score_expected_value':N,'model_sha256':H,'background_sha256':H}))
