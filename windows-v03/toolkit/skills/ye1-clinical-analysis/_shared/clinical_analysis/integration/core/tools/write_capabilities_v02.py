"""Describe only registered methods; final evidence binding is separate."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
lock=json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8'))
methods=[]
definitions=[
 ('baseline.table1','clinanalysis.table1','src/clinanalysis/R/table1.R',{'categorical_denominator':['nonmissing','all'],'summary':['mean_sd','median_iqr']}),
 ('association.linear','clinical_methods.association','python/clinical_methods/association.py',{'model':'linear','covariance':'HC3','missing':'complete_case','ci_level':0.95}),
 ('association.logistic','clinical_methods.association','python/clinical_methods/association.py',{'model':'logistic','covariance':'model','missing':'complete_case','ci_level':0.95}),
 ('prediction.binary.ridge','clinical_methods.prediction.binary','python/clinical_methods/prediction.py',{'operations':['train','evaluate','infer'],'split':['random','group','temporal'],'preprocessing':'training_fold_only','unknown_categories':'reject','thresholds':'prespecified_and_frozen','algorithm':'fixed_Ridge_Logistic'}),
 ('prediction.continuous.nonnegative.ridge','clinical_methods.prediction.continuous','python/clinical_methods/continuous_ridge/prediction_engine.py',{'operations':['train','evaluate','infer'],'split':['group'],'target_policy':{'domain':'nonnegative','transform':'identity','inverse_transform':'identity','output_policy':'clip_lower_zero','lower_bound':0},'preprocessing':'training_fold_only','unknown_categories':'reject','algorithm':'fixed_Ridge','inner_CV_minimums':{'train_subjects':100,'validation_subjects':30}}),
]
for method,provider,file,options in definitions:
    prediction=method.startswith('prediction.')
    methods.append({'method_id':method,'method_version':'1.0.0-candidate1','provider_id':provider,
      'provider_version':lock['prediction_provider_versions'][method] if prediction else lock['code_hashes'][file],
      'provider_code_path':file,'provider_version_scope':'composite_adapter_and_fixed_numerical_sources' if prediction else 'numerical_source_file',
      'input_schema':'clinical-study-input@'+('0.2.0-candidate1' if prediction else '0.1.0-candidate1'),
      'result_schema':'clinical-analysis-result@0.2.0-candidate1',
      'supported_view_kinds':['subject_wide','encounter_wide'],'supported_designs':['iid'],'supported_weights':['none'],
      'required_fields':['explicit character subject/record keys','declared units/coding/timing/missingness','bound source/plan/code','explicit denominator and method scale'],
      'supported_options':options,
      'unsupported_conditions':['real-data execution','unreconciled repeated subjects','joins without reconstructed evidence','unselected covariance or algorithm','unknown categories','undeclared units or future features'],
      'runtime_requirements':{'core_R':lock['versions'],'python':lock['prediction_python_versions'] if prediction else lock['python_versions']},
      'validation_evidence':[],'integration_status':'integration_pending','scope':'SYNTHETIC_TEST_ONLY_LOCAL_CANDIDATE','test_only':True,'scientific_review':'pending','export_status':'local_only'})
value={'schema_version':'clinical-method-capabilities@0.2.0-candidate1','core_version':lock['core_version'],
 'registration_owner':'clinanalysis::register_clinical_common','single_task_entry':'clinanalysis::run_analysis_task','methods':methods,
 'unregistered_capabilities':[{'method_group':x,'integration_status':'integration_pending'} for x in ['signed_continuous_prediction','LASSO/SHAP/Cox_prediction','RCS/interaction/sensitivity','survival','survey','longitudinal','causal','trajectory/clustering','postindex_outcome_descriptive_baseline_roles']],
 'publication_status':'NOT_RELEASED','real_database_adapters':'NOT_VALIDATED','clinical_scientific_acceptance':'NOT_PERFORMED'}
(ROOT/'method-capabilities.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
print('METHOD_CAPABILITIES_WRITTEN',len(methods))
