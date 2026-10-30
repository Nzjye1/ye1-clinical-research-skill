"""One bounded affine interpretation method; no generalized SHAP claim."""
import copy,json
from pathlib import Path
from write_capabilities_v08 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]
def build_capabilities(lock):
    if lock['core_version']!='0.9.0-candidate1':raise ValueError('V09_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.8.0-candidate1'
    value=legacy(old);value['core_version']=lock['core_version']
    value['schema_version']='clinical-method-capabilities@0.9.0-candidate1'
    for method in value['methods']:
        method['result_schema']='clinical-analysis-result@0.9.0-candidate1'
        if method['method_id'].endswith(('.lasso','.elasticnet')):
            method['unsupported_conditions']=[x for x in method['unsupported_conditions'] if x!='SHAP and other ML engines']
            method['unsupported_conditions'].append('General, conditional or probability-scale SHAP and other ML engines; bounded affine interpretation is a separate v09 method')
    value['methods'].append({
      'method_id':'interpretation.linear.interventional','method_version':'1.0.0-candidate1',
      'provider_id':'clinanalysis.interpretation_v09','provider_version':lock['interpretation_provider_version'],
      'provider_code_path':'src/clinanalysis/R/interpretation_v09.R',
      'provider_version_scope':'single grouped interventional affine contribution and nomogram owner; existing frozen preprocessing and prediction are reused',
      'input_schema':'clinical-study-input@0.9.0-candidate1','result_schema':'clinical-analysis-result@0.9.0-candidate1',
      'supported_view_kinds':['subject_wide'],'supported_designs':['iid'],'supported_weights':['none'],
      'required_fields':['frozen v08 penalized model','v09 training-only frozen explainer','same canonical semantics and disjoint synthetic application subjects','explicit feature units/availability'],
      'supported_options':{'models':['prediction.continuous.signed.lasso','prediction.continuous.signed.elasticnet','prediction.binary.lasso','prediction.binary.elasticnet'],
        'definition':'raw-feature-grouped interventional linear SHAP, full equal-weight empirical training background',
        'score_scales':['signed original continuous outcome units','raw log odds'],
        'background':'full final-training partition; frozen transformation applied without learning; stable private bundle',
        'importance':'application-population mean of absolute grouped contribution; sum within feature before absolute value',
        'nomogram':'frozen original-unit/category domains and missing-value path; numeric score and separate identity/logistic output backcheck',
        'constant_model':'zero contributions and points with a constant score/output map',
        'extrapolation':'reject outside frozen per-feature numeric domain; domain box does not prove joint support',
        'maximum_synthetic_subjects':200,'maximum_raw_features':12},
      'unsupported_conditions':['conditional or probability-scale SHAP','nonlinear models','Cox/Ridge/association interpretation and nomograms','causal importance','training patient explanation through this disjoint application contract','uncertainty and selection inference','real clinical validation'],
      'runtime_requirements':{'R':lock['versions']['R'],'frozen_model_runtime':lock['penalized_runtime']},
      'private_outputs':'training background, individual grouped/encoded contributions and per-subject nomogram points',
      'reference_scope':'independent complete raw-feature Shapley coalition enumeration and affine/points formulas; not official SHAP or rms runtime execution',
      'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE',
      'test_only':True,'scientific_review':'pending','export_status':'local_only'})
    value['unregistered_capabilities']=[x for x in value['unregistered_capabilities'] if x['method_group']!='SHAP_other_ML_and_nomograms']
    value['unregistered_capabilities'] += [dict(method_group=n,integration_status='not_implemented_in_shared_core',followup_required=True) for n in [
      'conditional_probability_scale_and_nonlinear_SHAP','Cox_Ridge_association_nomograms_and_explanations','binary_and_survival_matched_outcome_inference']]
    value['original_35_row_crosswalk']='docs/CAPABILITY-CROSSWALK-V09.json'
    return value
def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
