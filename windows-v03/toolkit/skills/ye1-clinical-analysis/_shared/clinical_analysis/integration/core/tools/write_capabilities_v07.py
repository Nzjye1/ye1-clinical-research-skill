"""Register bounded PSM separately from legacy propensity weighting."""
import copy,json
from pathlib import Path
from write_capabilities_v06 import build_capabilities as legacy
ROOT=Path(__file__).resolve().parents[1]

def build_capabilities(lock):
    if lock['core_version']!='0.7.0-candidate1':raise ValueError('V07_RUNTIME_LOCK_REQUIRED')
    old=copy.deepcopy(lock);old['core_version']='0.6.0-candidate1'
    value=legacy(old);value['core_version']=lock['core_version']
    value['schema_version']='clinical-method-capabilities@0.7.0-candidate1'
    for method in value['methods']:
        method['result_schema']='clinical-analysis-result@0.7.0-candidate1'
    value['methods'].append({
      'method_id':'causal.psm.att.continuous','method_version':'1.0.0-candidate1',
      'provider_id':'clinanalysis.psm_v07','provider_version':lock['psm_provider_version'],
      'provider_code_path':'src/clinanalysis/R/psm_v07.R','provider_version_scope':'sole_PSM_numerical_owner',
      'input_schema':'clinical-study-input@0.7.0-candidate1','result_schema':'clinical-analysis-result@0.7.0-candidate1',
      'supported_view_kinds':['patient_wide'],'supported_designs':['iid'],'supported_weights':['none'],
      'required_fields':['unique string subject ID','binary 0/1 treatment at index','1..8 declared pre-treatment PS covariates','complete signed continuous post-index outcome with unit','prespecified matching and inference options'],
      'supported_options':{
        'propensity':'single unpenalized stats::glm binomial logit MLE; explicit categories and fixed controls',
        'missing':'complete-case PS covariates; missing treatment or outcome refused before any filtering',
        'distance':'raw fitted logit PS, no clipping',
        'support':'inclusive observed minmax intersection, discard both arms, no PS refit',
        'caliper':'preset multiplier default 0.2 times support-retained combined sample SD; inclusive boundary',
        'matching':'1:1 greedy without replacement; descending treated logit; exact ties by UTF-8 ID bytes',
        'target':'complete-covariate support-retained matched treated; not original full-cohort ATT',
        'effect':'treated-minus-control mean pair difference; conditional paired t inference',
        'variance':'sample variance of pair differences / pair count; no independent-sample SE',
        'degenerate':'<2 pairs or zero difference variance retains defined descriptive contrast with null CI/p and reason',
        'balance':'fixed pre-support complete-case treated SD; numeric sample SD, categorical Bernoulli indicator SD',
        'overlap':'prespecified probability bins for fit, support-retained and matched populations',
        'separation':'numerical guards only; no formal complete/quasi-separation proof',
        'maximum_synthetic_subjects':200},
      'unsupported_conditions':['binary or survival outcomes','imputation or missing outcomes/treatment','multilevel or time-varying treatment','replacement or other ratios/optimal matching','adaptive calipers or balance/significance tuning','survey/clustered samples','full-cohort ATT after treatment discard','PS-estimation and matching-selection uncertainty','formal separation diagnosis','real database/clinical causal validation'],
      'runtime_requirements':{'R_stats':lock['psm_runtime'],'core_R':lock['versions']},
      'private_outputs':'individual PS/status, pair relations with outcome differences, and fitted coefficients/design; local only',
      'reference_scope':'independent R glm/design and source-formula matcher plus paired t.test; MatchIt unavailable and not installed',
      'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE',
      'test_only':True,'scientific_review':'pending','export_status':'local_only'})
    value['unregistered_capabilities']=[x for x in value['unregistered_capabilities'] if x['method_group']!='causal']
    value['unregistered_capabilities'] += [{'method_group':x,'integration_status':'not_implemented_in_shared_core','followup_required':True} for x in [
      'shared_IPTW_other_causal_methods','PSM_binary_survival_other_ratios_and_designs',
      'formal_propensity_separation_detection','PS_estimation_matching_selection_uncertainty']]
    return value

def main():
    value=build_capabilities(json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8')))
    (ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print('METHOD_CAPABILITIES_WRITTEN',len(value['methods']))
if __name__=='__main__':main()
