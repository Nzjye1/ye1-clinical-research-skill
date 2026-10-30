"""Validated transport, freeze and aggregate projection data for dedicated R owners."""
from __future__ import annotations
import copy,json,math,os,secrets,subprocess
from pathlib import Path
from .contracts import need,Blocked,number,digest,strict_json,frozen_definition
from . import module,formal_runtime
ROOT=Path(__file__).resolve().parent
MODEL_VERSION='latent-longitudinal-formal-frozen/1'

def prepare(rows,spec,operation,method,frozen=None):
    profile=method=='latent.profile.gaussian';subject=spec['subject_id'];d=spec['definition'];split=spec['split']
    ids={};partitions={};keys=set();kept={};train=[];evaluation=[];missing=0
    for i,row in enumerate(rows):
        sid=row[subject]
        need(isinstance(sid,str) and bool(sid.strip()),'SUBJECT_ID_INVALID')
        ids.setdefault(sid,len(ids)+1);uid=ids[sid]
        partition='external' if operation!='train' else ('training' if row[split['field']]==split['train'] else 'holdout')
        if operation=='train':need(row[split['field']] in [split['train'],split['holdout']],'FORMAL_PARTITION_INVALID')
        need(partitions.get(sid,partition)==partition,'SUBJECT_CROSSES_TRAIN_HOLDOUT')
        partitions[sid]=partition
        key=(sid,) if profile else (sid,row[d['time']['name']])
        need(key not in keys,'DUPLICATE_SUBJECT' if profile else 'DUPLICATE_SUBJECT_TIME');keys.add(key)
        if profile:
            values=[row[f['name']] for f in d['indicators']]
            need(all(v is None or number(v) for v in values),'FORMAL_INDICATORS_MUST_BE_NUMERIC')
            value=values
        else:
            time=row[d['time']['name']];y=row[d['outcome']['name']]
            need(number(time),'TIME_MUST_BE_FINITE_OBSERVED_NUMBER')
            need(y is None or number(y),'FORMAL_OUTCOME_MUST_BE_NUMERIC')
            tt=(time-d['time']['origin'])/d['time']['scale']
            need(math.isfinite(tt) and abs(tt)<1e6,'FORMAL_TIME_SCALE_INVALID')
            values=[y];value={'id':uid,'tt':tt,'tt2':tt*tt,'yy':y}
        if any(v is None for v in values):missing+=1;continue
        kept.setdefault(uid,{'row_indices':[],'partition':partition,'times':[]})['row_indices'].append(i)
        if not profile:kept[uid]['times'].append(row[d['time']['name']])
        (train if partition=='training' else evaluation).append(value)
    need(bool(kept),'NO_ANALYZABLE_ROWS')
    groups={part:[{'unit_index':uid,**item} for uid,item in sorted(kept.items()) if item['partition']==part]
            for part in ['training','holdout','external']}
    if operation=='train':
        n=len(groups['training']);need(30<=n<=3000,'FORMAL_TRAINING_SUBJECT_COUNT_OUTSIDE_VALIDATED_LIMIT')
        need(n>=10*max(spec['candidate_k']),'FORMAL_INSUFFICIENT_SUBJECTS_FOR_CANDIDATE_GRID')
        if not profile:
            mint=max(d['degree']+1,3 if d['random']=='intercept_slope' else 2)
            need(all(len(x['times'])>=mint for x in groups['training']),'INSUFFICIENT_WITHIN_SUBJECT_TIMES')
        time_range=None if profile else [min(t for x in groups['training'] for t in x['times']),max(t for x in groups['training'] for t in x['times'])]
    else:time_range=frozen['design']['time_range']
    if not profile:
        need(all(time_range[0]<=t<=time_range[1] for x in groups['holdout']+groups['external'] for t in x['times']),
             'EXTERNAL_TIME_EXTRAPOLATION_REJECTED')
        if operation=='train':
            need(max(x['yy'] for x in train)-min(x['yy'] for x in train)>1e-10,'CONSTANT_GROWTH_OUTCOME')
    counts={'input_rows':len(rows),'input_subjects':len(ids),'analysis_rows':len(rows)-missing,'analysis_subjects':len(kept),
            'excluded_missing_rows':missing,'excluded_subjects':len(ids)-len(kept),
            **{p+'_subjects':len(groups[p]) for p in groups}}
    return train,evaluation,groups,counts,{'time_range':time_range}

def freeze(method,spec,model,transform,design,rows,probe,admission=None):
    salt=secrets.token_hex(16)
    value={'schema_version':MODEL_VERSION if admission is None else 'latent-longitudinal-formal-admitted-frozen/1','method_id':method,'definition':frozen_definition(spec),
      'cohort_id':spec['cohort_id'],'provider_hash':digest(formal_runtime.source_hashes()),
      'runtime':formal_runtime.binding(probe),'test_only':True if admission is None else admission.test_only,'scientific_review':'pending','export_status':'local_only',
      'model':model,'transform':transform,'design':design,'subject_hash_salt':salt,
      'development_id_digests':sorted({digest([salt,r[spec['subject_id']]]) for r in rows})}
    if admission is not None:
        need(admission.scientific_review=='pending','ADMISSION_REVIEW_MUST_REMAIN_PENDING')
        value.update(data_origin=admission.data_origin,task_purpose=admission.task_purpose)
    value['sha256']=digest(value);return value

def validate_model(value,method,spec):
    model=value['model'];weights=model['weights'];k=len(weights)
    need(1<=k<=6 and all(number(w) and w>0 for w in weights) and abs(sum(weights)-1)<1e-8,'FROZEN_PARAMETERS_INVALID')
    if method=='latent.profile.gaussian':
        p=len(spec['definition']['indicators']);centers=model['centers'];var=model['variances'];t=value['transform']
        need(len(centers)==len(var)==k and len(t['mean'])==len(t['scale'])==p,'FROZEN_PARAMETERS_INVALID')
        need(all(len(x)==p for x in centers+var) and all(number(v) for x in centers+var for v in x)
             and all(v>0 for x in var for v in x) and all(number(v) for v in t['mean'])
             and all(number(v) and v>0 for v in t['scale']),'FROZEN_PARAMETERS_INVALID')
        need(model['covariance_model']==spec['definition']['covariance_model'],'FROZEN_PARAMETERS_INVALID')
    else:
        d=spec['definition'];q={'none':0,'intercept':1,'intercept_slope':2}[d['random']]
        need(model['degree']==d['degree'] and model['random']==d['random'] and len(model['beta'])==k
             and all(len(x)==d['degree']+1 and all(number(v) for v in x) for x in model['beta'])
             and number(model['residual_variance']) and model['residual_variance']>0,'FROZEN_PARAMETERS_INVALID')
        D=model['random_covariance']
        need(len(D)==q and all(len(x)==q and all(number(v) for v in x) for x in D),'FROZEN_PARAMETERS_INVALID')
        if q:
            need(D[0][0]>0 and (q==1 or D[1][1]>0 and abs(D[0][1]-D[1][0])<1e-10
                 and D[0][0]*D[1][1]-D[0][1]**2>0),'FROZEN_PARAMETERS_INVALID')
        r=value['design']['time_range'];need(len(r)==2 and all(number(x) for x in r) and r[0]<r[1],'FROZEN_PARAMETERS_INVALID')

def load_frozen(reference,method,spec,rows,probe,admission=None):
    path=Path(reference['path']);need(path.is_file() and path.stat().st_size<8*1024**2,'MODEL_FILE_UNAVAILABLE_OR_OVERSIZED')
    need(module.sha_file(path)==reference['sha256'],'MODEL_FILE_SHA256_MISMATCH')
    value=strict_json(path.read_text(encoding='utf-8'));checksum=value.pop('sha256',None)
    need(checksum==digest(value),'MODEL_CONTENT_SHA256_MISMATCH');value['sha256']=checksum
    version=MODEL_VERSION if admission is None else 'latent-longitudinal-formal-admitted-frozen/1'
    need(value['schema_version']==version and value['method_id']==method,'FROZEN_METHOD_MISMATCH')
    need(value['provider_hash']==digest(formal_runtime.source_hashes()),'FROZEN_SOURCE_DRIFT')
    need(value['runtime']==formal_runtime.binding(probe),'FROZEN_RUNTIME_DRIFT')
    if admission is None:
        need(value['test_only'] is True and value['scientific_review']=='pending' and value['export_status']=='local_only','FROZEN_CLASSIFICATION_MISMATCH')
    else:
        need(admission.scientific_review=='pending' and value['test_only'] is admission.test_only
             and value.get('data_origin')==admission.data_origin and value.get('task_purpose')==admission.task_purpose
             and value['scientific_review']=='pending' and value['export_status']=='local_only','FROZEN_CLASSIFICATION_MISMATCH')
    need(value['definition']==frozen_definition(spec),'FROZEN_DEFINITION_MISMATCH')
    need(value['cohort_id']!=spec['cohort_id'],'EXTERNAL_COHORT_MUST_DIFFER')
    incoming={digest([value['subject_hash_salt'],r[spec['subject_id']]]) for r in rows}
    need(not incoming & set(value['development_id_digests']),'EXTERNAL_SUBJECT_OVERLAP')
    validate_model(value,method,spec);return value

def call_engine(method,operation,spec,train,evaluation,frozen,work):
    rt=formal_runtime.runtime();env=os.environ.copy();env['R_LIBS']=';'.join(rt['r_libraries'])
    for key in ['LANG','LC_ALL','LC_COLLATE','LC_CTYPE','LC_MONETARY','LC_TIME']:env.pop(key,None)
    request={'method_id':method,'operation':operation,'spec':spec,'train':train,'evaluation':evaluation,'frozen':frozen}
    (work/'engine-request.json').write_text(json.dumps(request,allow_nan=False),encoding='utf-8')
    (work/'runtime.json').write_text(json.dumps(rt),encoding='utf-8')
    outpath=work/'engine-response.json'
    result=subprocess.run([rt['rscript'],'--vanilla',str(ROOT/'formal_engine.R'),str(work/'engine-request.json'),
      str(outpath),str(work/'runtime.json')],env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=600)
    (work/'engine.log').write_text(result.stdout+result.stderr,encoding='utf-8')
    need(result.returncode==0 and outpath.is_file(),'FORMAL_ENGINE_PROCESS_FAILED')
    out=strict_json(outpath.read_text(encoding='utf-8-sig'))
    if not out.get('ok'):
        details={key:out[key] for key in ['selection','initializations','stability'] if key in out}
        details.update(out.get('diagnostics',{}));raise Blocked(out.get('reason_code','FORMAL_ENGINE_RESULT_INVALID'),details)
    return out

def analyze(method,operation,payload,probe,admission=None):
    if admission is not None:admission.require_request(method,operation,payload)
    spec=payload['spec'];rows=payload['data'];work=Path(payload['work_dir'])
    need(not work.exists(),'OUTPUT_ALREADY_EXISTS');work.mkdir(parents=True)
    (work/'request.json').write_text(json.dumps(payload,allow_nan=False),encoding='utf-8')
    frozen=None if operation=='train' else load_frozen(payload['model_ref'],method,spec,rows,probe,admission=admission)
    train,evaluation,groups,counts,design=prepare(rows,spec,operation,method,frozen)
    out=call_engine(method,operation,spec,train,evaluation,frozen,work)
    model=out['model'];transform=out['transform'];d=spec['definition'];profile=method=='latent.profile.gaussian'
    classes=[];stats=[];individual=[]
    for key,partition in [('training','training'),('evaluation','holdout' if operation=='train' else 'external')]:
        scored=out[key]
        if scored is None:continue
        summary=scored['classes']
        classes += [{'partition':partition,**c} for c in summary['summary']]
        stats.append({'partition':partition,'log_likelihood':scored['log_likelihood'],'n_subjects':len(groups[partition]),
          'normalized_entropy':summary['entropy'],'scope':'frozen_model_scoring_not_clinical_validation',
          'likelihood_scale':'training_standardized_indicators' if profile else 'outcome_native_units_joint_subject_density'})
        for group,prob in zip(groups[partition],scored['posterior'],strict=True):
            individual.append({key:group[key] for key in ['unit_index','row_indices','partition']}|
              {'class':max(range(len(prob)),key=prob.__getitem__)+1,'posterior':prob})
    profiles=[];trajectories=[];params=[];prep=[]
    if profile:
        for j,f in enumerate(d['indicators']):
            prep.append({**{'feature':f['name'],'unit':f['unit']},'mean':transform['mean'][j],
                         'scale':transform['scale'][j],'fit_scope':'training_only'})
            for c in range(out['selected_k']):
                m=model['centers'][c][j];sd=math.sqrt(model['variances'][c][j])
                profiles.append({'class':c+1,'feature':f['name'],'unit':f['unit'],'standardized_mean':m,
                  'original_mean':m*transform['scale'][j]+transform['mean'][j],
                  'original_sd':sd*transform['scale'][j],'scope':'model_implied_class_mean','ci':None})
    else:
        low,high=design['time_range']
        for c,beta in enumerate(model['beta']):
            for power,b in enumerate(beta):params.append({'class':c+1,'term':['intercept','scaled_time','scaled_time_squared'][power],
              'estimate':b,'scale':d['outcome']['unit']+' per declared scaled-time power','ci':None})
            for i in range(41):
                time=low+(high-low)*i/40;tt=(time-d['time']['origin'])/d['time']['scale']
                trajectories.append({'class':c+1,'time':time,'estimate':sum(b*tt**j for j,b in enumerate(beta)),
                  'time_unit':d['time']['unit'],'outcome_unit':d['outcome']['unit'],'scope':'class_specific_marginal_mean','ci':None})
    analysis={'model_family':'LPA' if profile else ('LCGA' if d['family']=='lcga' else 'growth_mixture'),
       **{k:out[k] for k in ['selected_k','selection','initializations','stability','stability_summary']},
       'class_counts':classes,'fit_statistics':stats,'profiles':profiles,'trajectories':trajectories,'parameters':params,
       'preprocessing':prep,'counts':counts,'selection_scope':'training_only_BIC_lower_is_better'}
    warnings=[('SYNTHETIC_ENGINEERING_VALIDATION_ONLY' if admission is None else 'SOURCE_ADMISSION_IS_NOT_CLINICAL_SCIENTIFIC_VALIDATION'),'LATENT_CLASSES_ARE_MODEL_BASED_NOT_CLINICAL_ENTITIES',
       'CLASS_COUNT_BIC_AND_ENTROPY_DO_NOT_ESTABLISH_SCIENTIFIC_VALIDITY','NO_BLRT_LMR_OR_PARAMETER_CONFIDENCE_INTERVALS',
       'POSTERIOR_CLASS_UNCERTAINTY_MUST_NOT_BE_IGNORED_IN_DOWNSTREAM_ANALYSIS',
       'LOCAL_MAXIMUM_GUARDS_DO_NOT_PROVE_GLOBAL_OPTIMUM','FIXED_K_BOOTSTRAP_DOES_NOT_MEASURE_CLASS_SELECTION_UNCERTAINTY']
    warnings.append('COMPLETE_CASE_PROFILE_SELECTION_ASSUMPTIONS_UNVERIFIED' if profile else 'OBSERVED_OUTCOME_LIKELIHOOD_MAR_AND_DROPOUT_ASSUMPTIONS_UNVERIFIED')
    if out['selected_k']==1:warnings.append('ONE_CLASS_SELECTED_NO_LATENT_HETEROGENEITY_EVIDENCE')
    if out['stability_summary'] and out['stability_summary']['mean_ari']<.7:warnings.append('LOW_TRAINING_BOOTSTRAP_CLASS_STABILITY')
    if operation!='train':warnings.append('FROZEN_POSTERIOR_ASSIGNMENT_REQUIRES_OBSERVED_INDICATORS_OR_OUTCOMES_NOT_PROSPECTIVE_PREDICTION')
    model_text=None;model_sha=None
    if operation=='train':
        frozen=freeze(method,spec,model,transform,design,rows,probe,admission=admission);validate_model(frozen,method,spec)
        model_text=json.dumps(frozen,ensure_ascii=False,allow_nan=False);model_path=work/'model.json'
        model_path.write_text(model_text,encoding='utf-8');model_sha=module.sha_file(model_path)
    (work/'individual-results.json').write_text(json.dumps(individual,allow_nan=False),encoding='utf-8')
    (work/'runtime-probe.json').write_text(json.dumps(probe,indent=2),encoding='utf-8')
    return analysis,warnings,{'model_json':model_text,'model_sha256':model_sha,'individual_results':individual},out['diagnostics']
