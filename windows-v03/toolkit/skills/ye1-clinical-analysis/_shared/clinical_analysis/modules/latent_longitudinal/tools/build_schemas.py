"""Generate only module-owned closed JSON Schema fragments; no shared writes."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'schemas';OUT.mkdir(exist_ok=True)
S={'type':'string'};N={'type':'number'};I={'type':'integer'};B={'type':'boolean'};NULL={'type':'null'}
NAME={'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_]{0,63}$'}
HASH={'type':'string','pattern':'^[0-9a-f]{64}$'}
def en(*v):return {'enum':list(v)}
def const(v):return {'const':v}
def arr(items,minn=0,maxn=None):
 s={'type':'array','items':items,'minItems':minn}
 if maxn is not None:s['maxItems']=maxn
 return s
def obj(properties,required=None):
 return {'type':'object','properties':properties,'required':list(properties) if required is None else required,'additionalProperties':False}
def nullable(s):return {'anyOf':[s,NULL]}
FIELD=obj({'name':NAME,'unit':{'type':'string','minLength':1}})
identity={'subject_id':NAME,'cohort_id':{'type':'string','minLength':1}}
cluster=obj({**identity,'features':arr(FIELD,1,20),'missing':en('error','train_median'),
 'candidate_k':{**arr({'type':'integer','minimum':1,'maximum':6},1,6),'uniqueItems':True},
 'selection':en('silhouette','bic'),'seed':{'type':'integer','minimum':0,'maximum':2**31-1},
 'starts':{'type':'integer','minimum':3,'maximum':30},'max_iter':{'type':'integer','minimum':1,'maximum':3000},
 'tol':{'type':'number','minimum':1e-8,'maximum':1e-3},'stability_reps':{'type':'integer','minimum':5,'maximum':50},
 'min_class_n':{'type':'integer','minimum':5,'maximum':10000},
 'min_class_fraction':{'type':'number','minimum':.01,'maximum':.2},'covariance':en('none','diag','full'),
 'split':obj({'field':NAME,'train':S,'holdout':S})})
growth=obj({**identity,'time':obj({'name':NAME,'unit':S,'origin':N,'scale':N}),'outcome':FIELD,
 'covariates':arr(FIELD,0,10),'degree':en(1,2),'random':en('intercept','intercept_slope'),
 'estimation':const('ML'),'correlation':const('independent'),'missing':const('complete_case_rows'),
 'seed':{'type':'integer','minimum':0,'maximum':2**31-1},'max_iter':{'type':'integer','minimum':1,'maximum':2000}})
formal_common={**identity,'candidate_k':{**arr({'type':'integer','minimum':1,'maximum':6},1,6),'uniqueItems':True},
 'seed':{'type':'integer','minimum':0,'maximum':2**31-1},'starts':{'type':'integer','minimum':20,'maximum':200}}
profile=obj({**formal_common,'definition':obj({'indicators':arr(FIELD,2,20),'covariance_model':en('EEI','VVI'),'missing':const('complete_case')})})
trajectory=obj({**formal_common,'definition':obj({'family':en('lcga','growth_mixture'),'time':FIELD,'outcome':FIELD,
 'degree':en(1,2),'random':en('none','intercept','intercept_slope'),'missing':const('observed_likelihood_mar')})})
all_specs={'anyOf':[cluster,growth,profile,trajectory]}
semantics=obj({'grain':en('subject','subject_time'),'subject_key':NAME,'record_keys':arr(NAME,1,2),'group_key':NULL,
 'independence':const('independent_subjects'),'event_coding':NULL,
 'fields':arr(obj({'name':NAME,'dtype':en('id','number','category'),
  'role':en('subject_id','indicator','time','outcome','covariate','partition'),'unit':S,
  'measured_at':{'anyOf':[N,const('row_time'),NULL]},'available_at':{'anyOf':[N,const('row_time'),NULL]}}),1,24),
 'time':obj({'unit':nullable(S),'origin':nullable(N),'scale':nullable(N),'measurement_time_field':nullable(NAME),
             'availability':en('declared_per_field','row_time')}),
 'weights':obj({'kind':const('none'),'field':NULL}),'missing_policy':S})
model_ref=nullable(obj({'path':{'type':'string','minLength':1},'sha256':HASH}))
def write(name,schema):
 schema={'$schema':'https://json-schema.org/draft/2020-12/schema',**schema}
 (OUT/(name+'.schema.json')).write_text(json.dumps(schema,indent=2)+'\n',encoding='utf-8')
for name,spec in [('cluster',cluster),('growth',growth),('profile',profile),('trajectory',trajectory)]:
 payload=obj({'spec':spec,'semantics':semantics,'data':arr({'type':'object','additionalProperties':{'type':['number','string','null']}},1,20000),
              'test_only':const(True),'model_ref':model_ref,'work_dir':{'type':'string','minLength':1}})
 payload['description']='Dynamic data columns are additionally closed by api.check_semantics against the declared field list; no undeclared column is allowed.'
 write(name+'.payload',payload)

selection=obj({'k':I,'status':en('accepted','rejected'),'reason_code':nullable(S),'objective':nullable(N),
 'bic':nullable(N),'silhouette':nullable(N),'n_parameters':I,'best_replicated_starts':I,
 'selected_seed':I,'fit_scope':const('training_only')},
 ['k','status','reason_code','objective','bic','silhouette','fit_scope'])
initialization=obj({'k':I,'start':I,'seed':I,'status':en('accepted','rejected'),'reason_code':nullable(S),
                    'objective':nullable(N),'iterations':nullable(I)})
stability=obj({'replicate':I,'status':en('accepted','rejected'),'reason_code':nullable(S),'ari':nullable(N),
                'minimum_aligned_jaccard':nullable(N),'n_engine_fits':I})
counts=obj({k:I for k in ['input_rows','training_rows','holdout_rows','assigned_rows','training_missing_cells',
                          'analysis_rows','input_subjects','analysis_subjects','excluded_missing_rows']},[])
coeff=obj({'term':S,'estimate':N,'se':N,'df':N,'lower':N,'upper':N,'p_value':N,'ci_method':S,'scope':S})
curve=obj({'time':N,'estimate':N,'se':N,'lower':N,'upper':N,'ci_method':S,'scope':S})
availability=obj({'method_id':S,'required_provider':S,'installed_version':nullable(S),
                  'implementation':const('not_implemented'),'fitted':const(False)})
analysis=obj({'selected_k':I,'selection':arr(selection),'initializations':arr(initialization),
 'class_counts':arr(obj({'partition':en('training','holdout','external'),'class':I,'n':I,'denominator':I,
                        'fraction':N,'mean_max_posterior':nullable(N)})),
 'normalized_entropy':obj({'training':nullable(N),'holdout':nullable(N),'external':nullable(N)},[]),
 'stability':arr(stability),'stability_summary':nullable(obj({'requested':I,'valid':I,'mean_ari':N,'p10_ari':N,'p90_ari':N,
 'scope':S,'uncertainty':S,'class_selection_repeated':const(False)})),
 'profiles':arr(obj({'class':I,'feature':S,'unit':S,'standardized_center':N,'original_center':N,'scope':S,'ci':NULL})),
 'preprocessing':arr(obj({'feature':S,'unit':S,'median':N,'mean':N,'scale':N,'fit_scope':const('training_only')})),
 'counts':counts,'coefficients':arr(coeff),'trajectories':arr(curve),
 'fit_statistics':obj({'log_likelihood':N,'AIC':N,'BIC':N,'estimation':const('ML'),'residual_variance':N})},['counts'])
public=obj({'method_id':S,'operation':en('train','assign','predict'),'test_only':const(True),
 'scientific_review':const('pending'),'export_status':const('local_only'),'definition':all_specs,
 'analysis':analysis,'warnings':arr(S)})
public['anyOf']=[
 {'properties':{'method_id':en('exploration.cluster.kmeans','exploration.cluster.gmm'),
  'operation':en('train','assign'),'analysis':{'required':['selected_k','selection','initializations','class_counts',
       'normalized_entropy','stability','stability_summary','profiles','preprocessing','counts']}}},
 {'properties':{'method_id':const('longitudinal.growth.gaussian'),'operation':en('train','predict'),
  'analysis':{'required':['coefficients','trajectories','counts']}}}]
write('public_record',public)
details=obj({'n_engine_fits':I,'model_refitted':B,'transform_refitted':B,'reg_covar':nullable(N),
 'singular':B,'variance_hessian_positive_definite':B,
 'residuals':obj({'mean':N,'sd':N,'max_abs':N,'assumption_verified':const(False),'scope':S}),
 'prediction_kind':S,'selection':arr(selection),'initializations':arr(initialization),'starts':arr(initialization),
 'stability':arr(stability),'availability':arr(availability),'no_fallback':B,'minimum_primary_package':S,'error_type':S},[])
write('diagnostics',obj({'stage':en('validation','analysis','execution','complete'),'provider_hash':HASH,'runtime_hash':HASH,
                        'details':details},['stage','details']))
individual={'anyOf':[obj({'row_index':I,'partition':en('training','holdout','external'),'class':I,
 'posterior':nullable(arr(N,1)),'score':N}),obj({'row_index':I,'prediction':N,'lower':N,'upper':N})]}
write('private_record',obj({'model_json':nullable(S),'model_sha256':nullable(HASH),'individual_results':arr(individual)}))

methods=[]
for mid,kind,ops,owner in [
 ('exploration.cluster.kmeans','cluster',['train','assign'],'clustering.py: sklearn.cluster.KMeans'),
 ('exploration.cluster.gmm','cluster',['train','assign'],'clustering.py: sklearn.mixture.GaussianMixture'),
 ('longitudinal.growth.gaussian','growth',['train','predict'],'growth_engine.R: nlme::lme ML'),
 ('latent.profile.gaussian','profile',['train','assign'],'reserved mclust provider; currently unavailable'),
 ('latent.trajectory.gaussian','trajectory',['train','predict'],'reserved lcmm provider; currently unavailable')]:
 methods.append({'method_id':mid,'method_version':'1.0.0-development','operations':ops,'numerical_owner':owner,
  'schemas':{'payload':f'schemas/{kind}.payload.schema.json','diagnostics':'schemas/diagnostics.schema.json',
             'public_record':'schemas/public_record.schema.json','private_record':'schemas/private_record.schema.json'}})
manifest={'schema_version':'clinical-module-integration@1.0','module_id':'latent_longitudinal',
 'owner':'delegated latent_longitudinal module owner','language':'python','entrypoint':{'path':'api.py','function':'analyze'},
 'projection_entrypoint':{'path':'api.py','function':'project'},
 'provider_files':['__init__.py','api.py','schema_tools.py','module.py','contracts.py','clustering.py','growth.py',
                   'growth_engine.R','artifacts.py','latent_longitudinal_adapter.R'],
 'dependencies':[{'name':n,'version':v,'role':role} for n,v,role in [
 ('Python','3.12.15','runtime'),('R','4.6.1','runtime'),('numpy','2.5.4','runtime'),('scipy','1.18.1','runtime'),
 ('scikit-learn','1.9.1','numerical_owner'),('nlme','3.1.169','numerical_owner'),('jsonlite','2.0.0','runtime'),
 ('matplotlib','3.11.2','runtime'),('threadpoolctl','3.7.0','runtime'),('lme4','2.0.6','validation_reference')]],
 'methods':methods,'shared_change_requests':[{'target':'new registered method branches and aggregate projection',
 'reason':'Add opt-in module branch with strict subject/subject-time semantics; preserve all historical single-subject guards.',
 'affected_methods':[m['method_id'] for m in methods],
 'required_regression':['old duplicate subject and cross-fold rejection','frozen canonical units',
 'missing schema and unknown field rejection','public/private export audit','formal provider unavailable until verified']}],
 'evidence':['dependency-probe.json','FORMAL-METHODS-BOUNDARY.md','tests/run_tests.py','tests/affected_regression.py']}
(ROOT/'integration-request.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Generated 7 module-owned schemas and integration-request.json')
