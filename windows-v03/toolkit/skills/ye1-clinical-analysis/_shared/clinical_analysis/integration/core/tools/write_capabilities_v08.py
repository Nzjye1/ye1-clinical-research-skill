"""Four bounded glmnet methods; keep old Ridge providers and target policies."""
import copy,json
from pathlib import Path
from write_capabilities_v07 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]

def build_capabilities(lock):
    if lock['core_version']!='0.8.0-candidate1':raise ValueError('V08_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.7.0-candidate1'
    value=legacy(old);value['core_version']=lock['core_version']
    value['schema_version']='clinical-method-capabilities@0.8.0-candidate1'
    for method in value['methods']:method['result_schema']='clinical-analysis-result@0.8.0-candidate1'
    for family,scope in [('gaussian','continuous.signed'),('binomial','binary')]:
        for penalty in ('lasso','elasticnet'):
            value['methods'].append({
              'method_id':f'prediction.{scope}.{penalty}','method_version':'1.0.0-candidate1',
              'provider_id':'clinanalysis.penalized_v08','provider_version':lock['penalized_provider_version'],
              'provider_code_path':'src/clinanalysis/R/penalized_v08.R',
              'provider_version_scope':'single preprocessing/CV/fitting/inference owner plus separately hashed fixed glmnet and Matrix dependencies',
              'input_schema':'clinical-study-input@0.8.0-candidate1','result_schema':'clinical-analysis-result@0.8.0-candidate1',
              'supported_view_kinds':['subject_wide'],'supported_designs':['iid'],'supported_weights':['none'],
              'required_fields':['unique canonical string patient ID','explicit feature roles/units/availability','preassigned patient/group partition and nonempty CV folds','complete labels for train/evaluate','same canonical identity namespace and frozen pipeline for external application'],
              'supported_options':{
                'family':family,'penalty':penalty,'alpha':'exactly 1' if penalty=='lasso' else 'one prespecified value strictly between 0 and 1',
                'lambda':'2..30 positive strictly decreasing prespecified values; same requested grid in every fit; returned path checked with machine representation tolerance and selected by column index',
                'selection':'minimum total out-of-fold loss / total CV validation subjects; exact ties choose largest lambda',
                'cv':'3..5 prespecified nonempty folds confined by canonical subject/group; no holdout use',
                'preprocessing':'fold-training numeric median/categorical mode, observed UTF-8 category dictionary, treatment coding and population-SD scaling; final training-only refit',
                'missing':'training-fitted feature imputation; all-missing training features refused; complete train/evaluate labels required',
                'unknown_categories':'reject with fit scope/feature/fold; declared but unobserved level is not a trained category',
                'response':'training mean/population-SD transform and inverse transform; signed outputs without clipping' if family=='gaussian' else 'explicit 0/1 with 1 event; probability is logistic of frozen linear score',
                'minimum_fit_design':'two nonconstant encoded columns; all-zero fitted slopes are supported',
                'class_counts':'at least 8 per class in every fit subset' if family=='binomial' else 'not applicable',
                'inference':'frozen coefficients and transformations, no refitting or glmnet predict interpolation',
                'evaluation':'holdout or disjoint synthetic external; row-appropriate metric denominators; no postselection coefficient p-values',
                'maximum_synthetic_subjects':200,'maximum_raw_features':12,'maximum_encoded_columns_before_variance_filter':60},
              'unsupported_conditions':['alpha grid search','outcome-adaptive splits/lambda grids or test tuning','temporal split/CV','nested-CV performance estimation','real database and clinical external validation','survey/weighted sampling','postselection inferential p-values or causal variable claims','SHAP and other ML engines','Cox-LASSO','prediction or calibration uncertainty'],
              'runtime_requirements':{'versions':lock['penalized_runtime'],'package_paths':lock['penalized_package_paths'],'dependency_hashes':lock['penalized_dependency_hashes']},
              'private_outputs':'full frozen transform/model and training IDs/groups; fold and individual predictions stay local only',
              'reference_scope':'independent preprocessing and direct installed glmnet calls, plus frozen-coefficient formula inference; not a second optimization engine',
              'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE',
              'test_only':True,'scientific_review':'pending','export_status':'local_only'})
    removed={'signed_continuous_prediction','LASSO_SHAP'}
    value['unregistered_capabilities']=[x for x in value['unregistered_capabilities'] if x['method_group'] not in removed]
    value['unregistered_capabilities'] += [{'method_group':name,'integration_status':'not_implemented_in_shared_core','followup_required':True} for name in [
      'SHAP_other_ML_and_nomograms','Cox_LASSO','penalized_multi_alpha_search_temporal_nested_CV',
      'valid_postselection_inference_and_selection_stability','penalized_prediction_uncertainty_and_calibration',
      'signed_continuous_Ridge_without_legacy_clipping']]
    return value

def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
