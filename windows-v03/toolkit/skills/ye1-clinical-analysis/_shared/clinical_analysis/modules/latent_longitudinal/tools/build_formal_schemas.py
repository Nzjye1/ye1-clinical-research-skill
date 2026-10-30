"""Independent formal fragments; deliberately leaves all accepted schemas intact."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'formal_schemas';OUT.mkdir(exist_ok=True)
S={'type':'string'};N={'type':'number'};I={'type':'integer'};NULL={'type':'null'}
NAME={'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_]{0,63}$'}
HASH={'type':'string','pattern':'^[0-9a-f]{64}$'}
def const(v):return {'const':v}
def en(*x):return {'enum':list(x)}
def nullable(x):return {'anyOf':[x,NULL]}
def arr(x,minn=0,maxn=None):
 d={'type':'array','items':x,'minItems':minn}
 if maxn is not None:d['maxItems']=maxn
 return d
def obj(x,required=None):return {'type':'object','properties':x,'required':list(x) if required is None else required,'additionalProperties':False}
def bounded(t,lo,hi):return {'type':t,'minimum':lo,'maximum':hi}
def write(name,value):(OUT/(name+'.schema.json')).write_text(json.dumps({'$schema':'https://json-schema.org/draft/2020-12/schema',**value},indent=2)+'\n',encoding='utf-8')
field=obj({'name':NAME,'unit':{'type':'string','minLength':1}})
common={'subject_id':NAME,'cohort_id':{'type':'string','minLength':1},
 'candidate_k':{**arr(bounded('integer',1,6),1,6),'uniqueItems':True},'seed':bounded('integer',0,2**31-1),
 'starts':bounded('integer',20,200),'split':obj({'field':NAME,'train':S,'holdout':S}),
 'controls':obj({'max_iter':bounded('integer',1,2000),'tol':bounded('number',1e-8,1e-5),
                 'stability_reps':bounded('integer',5,30),'min_class_n':const(5),'min_class_fraction':const(.05)})}
profile=obj({**common,'definition':obj({'indicators':arr(field,2,20),'covariance_model':en('EEI','VVI'),'missing':const('complete_case')})})
trajectory=obj({**common,'definition':obj({'family':en('lcga','growth_mixture'),
 'time':obj({'name':NAME,'unit':S,'origin':N,'scale':bounded('number',1e-12,1e12)}),'outcome':field,
 'degree':en(1,2),'random':en('none','intercept','intercept_slope'),'missing':const('observed_likelihood_mar')})})
old=json.loads((ROOT/'schemas/profile.payload.schema.json').read_text())
for name,spec in [('profile',profile),('trajectory',trajectory)]:
 payload=obj({**old['properties'],'spec':spec});write(name+'.payload',payload)
selection=obj({'k':I,'status':en('accepted','rejected'),'reason_code':nullable(S),'log_likelihood':N,
 'n_parameters':I,'AIC':N,'BIC':N,'independent_units':I,'replicated_best_starts':I},['k','status','reason_code'])
starts=obj({'k':I,'start':I,'seed':I,'status':en('accepted','rejected'),'reason_code':nullable(S),
 'log_likelihood':nullable(N),'iterations':nullable(I)})
stability=obj({'replicate':I,'seed':I,'status':en('accepted','rejected'),'reason_code':nullable(S),'ari':nullable(N),'n_engine_fits':I})
summary=nullable(obj({'requested':I,'valid':I,'mean_ari':N,'p10_ari':N,'p90_ari':N,'class_selection_repeated':const(False),
 'scope':const('training_subject_bootstrap_fixed_selected_k'),'uncertainty':const('descriptive_quantiles_not_confidence_intervals')}))
count=obj({key:I for key in ['input_rows','input_subjects','analysis_rows','analysis_subjects','excluded_missing_rows','excluded_subjects','training_subjects','holdout_subjects','external_subjects']})
classes=arr(obj({'partition':en('training','holdout','external'),'class':I,'n':I,'denominator':I,'fraction':N,'mean_max_posterior':nullable(N)}))
fit_stats=arr(obj({'partition':en('training','holdout','external'),'log_likelihood':N,'n_subjects':I,
 'normalized_entropy':nullable(N),'scope':const('frozen_model_scoring_not_clinical_validation'),
 'likelihood_scale':en('training_standardized_indicators','outcome_native_units_joint_subject_density')}))
profiles=arr(obj({'class':I,'feature':S,'unit':S,'standardized_mean':N,'original_mean':N,
 'original_sd':N,'scope':const('model_implied_class_mean'),'ci':NULL}))
curves=arr(obj({'class':I,'time':N,'estimate':N,'time_unit':S,'outcome_unit':S,'scope':const('class_specific_marginal_mean'),'ci':NULL}))
parameters=arr(obj({'class':I,'term':S,'estimate':N,'scale':S,'ci':NULL}))
prep=arr(obj({'feature':S,'unit':S,'mean':N,'scale':N,'fit_scope':const('training_only')}))
analysis=obj({'model_family':en('LPA','LCGA','growth_mixture'),'selected_k':I,'selection':arr(selection),
 'initializations':arr(starts),'class_counts':classes,'fit_statistics':fit_stats,'stability':arr(stability),
 'stability_summary':summary,'profiles':profiles,'trajectories':curves,'parameters':parameters,
 'preprocessing':prep,'counts':count,'selection_scope':const('training_only_BIC_lower_is_better')})
public=obj({'method_id':en('latent.profile.gaussian','latent.trajectory.gaussian'),'operation':en('train','assign','predict'),
 'test_only':const(True),'scientific_review':const('pending'),'export_status':const('local_only'),
 'definition':{'anyOf':[profile,trajectory]},'analysis':analysis,'warnings':arr(S)})
public['anyOf']=[{'properties':{'method_id':const('latent.profile.gaussian'),'operation':en('train','assign'),
 'definition':profile,'analysis':{'properties':{'model_family':const('LPA'),'profiles':{'minItems':2}}}}},
 {'properties':{'method_id':const('latent.trajectory.gaussian'),'operation':en('train','predict'),
 'definition':trajectory,'analysis':{'properties':{'model_family':en('LCGA','growth_mixture'),'trajectories':{'minItems':2}}}}}]
write('public_record',public)
details=obj({'n_engine_fits':I,'model_refitted':{'type':'boolean'},'transform_refitted':{'type':'boolean'},
 'selection':arr(selection),'initializations':arr(starts),'stability':arr(stability)},[])
write('diagnostics',obj({'stage':en('validation','analysis','execution','complete'),'provider_hash':HASH,'runtime_hash':HASH,'details':details},['stage','details']))
individual=obj({'unit_index':I,'row_indices':arr(I,1),'partition':en('training','holdout','external'),'class':I,'posterior':arr(N,1,6)})
write('private_record',obj({'model_json':nullable(S),'model_sha256':nullable(HASH),'individual_results':arr(individual)}))
print('Wrote five new formal schema fragments; existing schemas untouched.')
