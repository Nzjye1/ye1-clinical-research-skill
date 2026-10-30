"""Two explicitly bounded Cox penalized methods; no automatic downstream support."""
import copy,json
from pathlib import Path
from write_capabilities_v09 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]
def build_capabilities(lock):
    if lock['core_version']!='0.10.0-candidate1':raise ValueError('V10_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.9.0-candidate1'
    value=legacy(old);value.update(core_version=lock['core_version'],schema_version='clinical-method-capabilities@0.10.0-candidate1')
    for method in value['methods']:method['result_schema']='clinical-analysis-result@0.10.0-candidate1'
    for penalty in ('lasso','elasticnet'):
        value['methods'].append({
          'method_id':'prediction.survival.cox.'+penalty,'method_version':'1.0.0-candidate1',
          'provider_id':'clinanalysis.cox_penalized_v10','provider_version':lock['cox_penalized_provider_version'],
          'provider_code_path':'src/clinanalysis/R/cox_penalized_v10.R',
          'provider_version_scope':'glmnet is the sole coefficient optimizer; installed survival estimates only a fixed-offset training baseline; unchanged v08 preprocessing owner',
          'input_schema':'clinical-study-input@0.10.0-candidate1','result_schema':'clinical-analysis-result@0.10.0-candidate1',
          'supported_view_kinds':['subject_wide'],'supported_designs':['iid'],'supported_weights':['none'],
          'required_fields':['unique patient and optional group identities','positive duration and exact event=1/censor=0 in training','pre-index feature semantics','preset partitions/folds/alpha/lambda/horizons','training-bound frozen baseline and preprocessing for inference'],
          'supported_options':{'operations':['train','infer'],'penalty':penalty,
            'alpha':1 if penalty=='lasso' else 'single prespecified value strictly between zero and one',
            'ties':'breslow_explicit','censoring':'single_event_right_censored',
            'cv':'sum heldout-only fold Breslow deviance divided by total validation events; largest lambda on exact loss ties',
            'preprocessing':'fit-fold median/mode, observed categories, treatment encoding, population SD',
            'baseline':'fixed eta-mean(eta) offset only; no coefficient refitting; right-continuous Breslow step',
            'prediction_scales':['log_relative_hazard','centered_log_relative_hazard','horizon_specific_event_probability'],
            'support':'prespecified nonnegative horizons through maximum observed training follow-up; no extrapolation',
            'maximum_synthetic_subjects':200,'maximum_raw_features':12,'maximum_horizons':8},
          'unsupported_conditions':['competing/recurrent events, delayed entry, strata or time-varying features','weights or clustered inference','temporal or nested CV and multi-alpha tuning','unseen observed category','new Cox-penalized IPCW evaluation bridge','selection-adjusted inference, p-values, intervals and formal PH tests','Cox explanation, SHAP and nomograms','real clinical external validation'],
          'runtime_requirements':lock['cox_penalized_runtime'],
          'private_outputs':'full frozen pipeline including subject/group identity provenance, individual scores and risks',
          'reference_scope':'independent preprocessing and direct calls share glmnet solver; independent Breslow formulas and fixed-coefficient survival baseline/risk references; not independent optimizer or clinical validation',
          'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE',
          'test_only':True,'scientific_review':'pending','export_status':'local_only'})
    value['unregistered_capabilities']=[row for row in value['unregistered_capabilities'] if row['method_group']!='Cox_LASSO']
    value['unregistered_capabilities'].append(dict(method_group='penalized_Cox_IPCW_PH_explanations_nomograms_uncertainty',integration_status='not_implemented_in_shared_core',followup_required=True))
    value['original_35_row_crosswalk']='docs/CAPABILITY-CROSSWALK-V10.json'
    return value
def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
