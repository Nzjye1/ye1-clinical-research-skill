"""Metadata for the bounded v04 survival integration; no numerical execution."""
import copy,json
from pathlib import Path
from write_capabilities_v03 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]
def build_capabilities(lock):
    if lock['core_version']!='0.4.0-candidate1':raise ValueError('V04_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.3.0-candidate1'
    value=legacy(old);value['schema_version']='clinical-method-capabilities@0.4.0-candidate1';value['core_version']=lock['core_version']
    for m in value['methods']:m['result_schema']='clinical-analysis-result@0.4.0-candidate1'
    for method in ['survival.kaplan_meier','survival.cox.association']:
        value['methods'].append({'method_id':method,'method_version':'1.0.0-candidate1','provider_id':'clinical_methods.survival',
          'provider_version':lock['survival_provider_version'],'provider_code_path':'python/clinical_methods/survival.py',
          'provider_version_scope':'composite_byte_preserved_survival_source_and_registered_bridge',
          'input_schema':'clinical-study-input@0.4.0-candidate1','result_schema':'clinical-analysis-result@0.4.0-candidate1',
          'supported_view_kinds':['survival_subject'],'supported_designs':['iid'],'supported_weights':['none'],
          'required_fields':['unique character subject key','explicit origin/duration unit/event and censor codes','prespecified evaluation grid','complete-case missing policy','baseline-only prespecified Cox covariates'],
          'supported_options':{'outcome':'single event right censoring','time_units':['day','hour'],'curve':'unadjusted KM on method complete-case cohort',
            'risk_table':'t-minus, events before censoring at tied times','ci':'pointwise Greenwood log-log; boundary endpoints descriptive',
            'grid':'prespecified, inside complete-case followup; not full event-time staircase','cox_ties':'breslow','cox_ci':'normal Wald log HR, exponentiated',
            'cox_guard':'finite MLE, information conditioning, at least max(20, 10 per parameter) events; engineering guards not adequacy proof',
            'ph_diagnostic':'descriptive-only Schoenfeld residual vs log-time Spearman rho; no formal p or PH pass',
            'no_events':'NO_TARGET_EVENTS with counts; no curve or HR','failed_cox':'partial with exact reason and unadjusted KM; no algorithm fallback'},
          'unsupported_conditions':['competing risks','recurrent events','delayed entry','interval censoring','time-varying covariates','weights','clustered/stratified inference','individual absolute-risk prediction','formal PH test'],
          'runtime_requirements':{'core_R':lock['versions'],'python':lock['python_versions']},
          'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE','test_only':True,'scientific_review':'pending','export_status':'local_only'})
    value['unregistered_capabilities']=[x for x in value['unregistered_capabilities'] if x['method_group']!='survival']
    value['unregistered_capabilities'] += [{'method_group':x,'integration_status':'not_implemented_in_shared_core','followup_required':True} for x in ['formal_PH_test','survival_absolute_risk_external_validation_tdROC_calibration_DCA','competing_risk_survival','delayed_entry_recurrent_timevarying_survival']]
    return value
def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
