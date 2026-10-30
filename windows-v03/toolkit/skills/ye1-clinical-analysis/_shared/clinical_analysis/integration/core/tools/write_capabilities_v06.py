"""Local v06 registration metadata, separate frozen model and evaluation owners."""
import copy,json
from pathlib import Path
from write_capabilities_v05 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]
def build_capabilities(lock):
    if lock['core_version']!='0.6.0-candidate1':raise ValueError('V06_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.5.0-candidate1'
    value=legacy(old);value['core_version']=lock['core_version'];value['schema_version']='clinical-method-capabilities@0.6.0-candidate1'
    for m in value['methods']:
        m['result_schema']='clinical-analysis-result@0.6.0-candidate1'
        if m['method_id']=='prediction.survival.cox':
            m['supported_options']['evaluation_entry']='Separate evaluation.survival.cox.ipcw consumes unchanged frozen inference; this method emits predictions only.'
    value['methods'].append({
      'method_id':'evaluation.survival.cox.ipcw','method_version':'1.0.0-candidate1',
      'provider_id':'clinical_methods.survival.evaluation','provider_version':lock['survival_evaluation_provider_version'],
      'provider_code_path':'python/clinical_methods/survival_evaluation.py',
      'provider_version_scope':'evaluation_owner_bridge_and_unchanged_frozen_Cox_owner_bridge',
      'frozen_model_provider_version':lock['cox_prediction_provider_version'],
      'input_schema':'clinical-study-input@0.6.0-candidate1','result_schema':'clinical-analysis-result@0.6.0-candidate1',
      'supported_view_kinds':['survival_subject'],'supported_designs':['iid'],'supported_weights':['none'],
      'required_fields':['hash-bound frozen v05 Cox model','complete features and followup labels','prespecified horizons and ROC/DCA grids and calibration bins','canonical identity namespace with training overlap check','explicit single-event right-censoring time/event semantics','declared independence of censoring from event time and model features'],
      'supported_options':{'censoring':'evaluation-cohort marginal reverse KM, original events before original censors',
        'cases':'event and U<=t; G(U-) weight','controls':'U>t; G(t) weight','early_censor':'zero contribution, retained in population n',
        'auc':'exact weighted cumulative/dynamic case-control rank; half exact-score ties',
        'roc':'prespecified grid plus all-negative boundary; not integrated for AUC',
        'brier':'IPCW squared error divided by all evaluation subjects',
        'calibration':'descriptive fixed bins, Hajek observed proportions; separate prediction n and weight denominators',
        'dca':'IPCW population moments, fixed thresholds, treat-all and none; not positive-group KM',
        'weight_guards':'G>=0.05, weight<=20; equality allowed, no clipping; engineering bounds only',
        'support':'0 through last training event; metric-specific no-case/control reasons',
        'uncertainty':'not_implemented','frozen_model_format':'clinical-frozen-survival-cox@0.5.0-candidate1'},
      'unsupported_conditions':['conditional or informative censoring','unknown categories or missing evaluation labels/features','data-adaptive horizon/threshold/bin selection','risk model refit or external baseline update','competing risks/delayed entry/recurrent events','survey or case weights','metric confidence intervals','calibration slope/intercept/test or smooth calibration','integrated Brier/incident-dynamic AUC','real database or clinical external validation'],
      'runtime_requirements':{'core_R':lock['versions'],'python':lock['python_versions']},
      'private_outputs':'frozen model, individual predictions, censoring time grid and IPCW contributions',
      'reference_scope':'R survival censoring construction and independent source-formula metrics, not specialist-package metric validation',
      'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE',
      'test_only':True,'scientific_review':'pending','export_status':'local_only'})
    value['unregistered_capabilities']=[x for x in value['unregistered_capabilities'] if x['method_group'] not in ['survival_tdROC_IPCW_Brier_calibration_DCA','LASSO/SHAP/Cox_prediction']]
    value['unregistered_capabilities'] += [{'method_group':x,'integration_status':'not_implemented_in_shared_core','followup_required':True} for x in ['LASSO_SHAP','conditional_censoring_IPCW','survival_calibration_slope_intercept_tests_intervals','survival_metric_uncertainty_and_integrated_scores']]
    return value
def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
