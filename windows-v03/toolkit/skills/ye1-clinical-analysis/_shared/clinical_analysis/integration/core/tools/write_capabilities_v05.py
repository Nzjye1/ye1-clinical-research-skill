"""Bounded v05 capability metadata; no fitting or automatic fallback."""
import copy,json
from pathlib import Path
from write_capabilities_v04 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]

def build_capabilities(lock):
    if lock['core_version']!='0.5.0-candidate1':raise ValueError('V05_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.4.0-candidate1'
    value=legacy(old)
    value['schema_version']='clinical-method-capabilities@0.5.0-candidate1'
    value['core_version']=lock['core_version']
    for m in value['methods']:
        m['result_schema']='clinical-analysis-result@0.5.0-candidate1'
        if m['method_id'].startswith('survival.'):
            m['provider_version_scope']='single_survival_owner_and_registered_bridge'
        if m['method_id']=='survival.cox.association':
            m['input_schemas']=['clinical-study-input@0.4.0-candidate1','clinical-study-input@0.5.0-candidate1']
            m['supported_options']['ph_diagnostic']='v04 descriptive only; v05 explicit formal nuisance-adjusted score test, km or identity transform, terms=True/singledf=False/global=True, Breslow exact ties'
            m['supported_options']['ph_interpretation']='Asymptotic diagnostic test only; no P value verifies proportional hazards or clinical validity'
            m['unsupported_conditions'].remove('formal PH test')
    value['methods'].append({
      'method_id':'prediction.survival.cox','method_version':'1.0.0-candidate1','provider_id':'clinical_methods.survival.cox_prediction',
      'provider_version':lock['cox_prediction_provider_version'],'provider_code_path':'python/clinical_methods/survival.py',
      'provider_version_scope':'single_survival_owner_and_cox_prediction_bridge',
      'input_schema':'clinical-study-input@0.5.0-candidate1','result_schema':'clinical-analysis-result@0.5.0-candidate1',
      'supported_view_kinds':['survival_subject'],'supported_designs':['iid'],'supported_weights':['none'],
      'required_fields':['explicit disjoint full subject partition before complete-case selection','canonical identity namespace','time-zero/time-unit/event/censor definitions','prespecified horizons','fixed covariate roles/units/levels/references'],
      'supported_options':{'operations':['train','infer'],'fit_engine':'existing statsmodels.PHReg Breslow owner',
        'missing':'training complete cases only; application feature missingness rejected',
        'preprocessing':'freeze training design mean/std and declared categorical coding; no application fitting',
        'baseline':'right-continuous centered Breslow cumulative hazard, event times included',
        'risk':'1-exp(-H0(t)*exp((x-center) beta)); not HR-as-probability',
        'support':'0 through last training event, no extrapolation',
        'application':'same model/namespace/semantics, known training ID overlap rejected',
        'public_results':'prediction summaries and separate training/application event-censor counts; no individual identifiers',
        'private_results':'strict JSON frozen model and individual predictions; no pickle',
        'validation':'synthetic technical application and independent R reference only'},
      'unsupported_conditions':['time-dependent ROC/AUC','IPCW Brier','survival calibration','survival DCA','prediction confidence intervals','missing application features','unknown categories','time extrapolation','competing events','delayed entry','recurrent events','time-varying covariates','weights/clustered/stratified inference'],
      'runtime_requirements':{'core_R':lock['versions'],'python':lock['python_versions']},
      'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE',
      'test_only':True,'scientific_review':'pending','export_status':'local_only'})
    value['unregistered_capabilities']=[x for x in value['unregistered_capabilities'] if x['method_group'] not in ['formal_PH_test','survival_absolute_risk_external_validation_tdROC_calibration_DCA']]
    value['unregistered_capabilities'] += [{'method_group':x,'integration_status':'not_implemented_in_shared_core','followup_required':True} for x in ['survival_tdROC_IPCW_Brier_calibration_DCA','survival_prediction_uncertainty','real_external_survival_validation_and_transportability']]
    return value

def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
