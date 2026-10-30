"""Small CPU baselines. No preprocessing/tuning sees the held-out patients."""
import hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from .core import StudyError,digest

def group_order(groups,seed,namespace):
    unique=sorted(set(str(v) for v in groups))
    return sorted(unique,key=lambda value:hashlib.sha256((str(seed)+'|'+namespace+'|'+value).encode()).digest())

def split_groups(groups,seed,fraction):
    ordered=group_order(groups,seed,'outer');n_test=max(1,int(np.ceil(len(ordered)*fraction)));held=set(ordered[-n_test:]);test=np.array([str(v) in held for v in groups],dtype=bool)
    return ~test,test

def inner_folds(groups,seed,k):
    ordered=group_order(groups,seed,'training_inner');mapping={v:i%k for i,v in enumerate(ordered)}
    return np.array([mapping[str(v)] for v in groups])

def _feature_values(frame,s):
    v=frame[s['variable']].to_numpy(float).copy();v[~np.isfinite(v)]=np.nan
    if s['kind']=='categorical':v[~np.isin(v,s['levels'])]=np.nan
    elif s['kind']=='binary':v[~np.isin(v,[0,1])]=np.nan
    elif s['kind']=='threshold':v=np.where(np.isnan(v),np.nan,(v>=s['cutoff']).astype(float))
    return v

def fit_preprocessor(frame,specs):
    items=[]
    for s in specs:
        v=_feature_values(frame,s);valid=v[~np.isnan(v)]
        if not len(valid):raise StudyError('PREDICTOR_ALL_MISSING_IN_TRAINING')
        categorical=s['kind'] in {'categorical','binary','threshold'}
        if categorical:
            values,counts=np.unique(valid,return_counts=True);fill=float(values[np.argmax(counts)])
        else:fill=float(np.median(valid))
        items.append({'spec':s,'fill':fill,'strategy':'mode' if categorical else 'median','training_missing_n':int(np.isnan(v).sum())})
    prep={'items':items};raw,names=raw_design(frame,prep);mean=raw.mean(axis=0);sd=raw.std(axis=0);sd[sd<1e-12]=1.
    prep.update(mean=mean.tolist(),sd=sd.tolist(),columns=names,training_records_n=len(frame),training_patient_keys_n=int(frame.group_id.nunique()))
    return prep

def raw_design(frame,prep):
    cols=[];names=[]
    for i,item in enumerate(prep['items']):
        s=item['spec'];v=_feature_values(frame,s);missing=np.isnan(v);v=np.where(missing,item['fill'],v);prefix=str(i)+'_'+s['variable']
        if s['kind']=='categorical':
            for level in s['levels']:
                if level==s['reference']:continue
                cols.append((v==level).astype(float));names.append(prefix+'_level_'+str(level))
        else:cols.append(v/s.get('step',1));names.append(prefix)
        cols.append(missing.astype(float));names.append(prefix+'_missing')
    return np.column_stack(cols),names

def transform(frame,prep):
    raw,names=raw_design(frame,prep)
    if names!=prep['columns']:raise StudyError('PREDICTION_DESIGN_COLUMNS_CHANGED')
    x=(raw-np.array(prep['mean']))/np.array(prep['sd'])
    if not np.isfinite(x).all():raise StudyError('NONFINITE_PREDICTION_DESIGN')
    return np.column_stack([np.ones(len(frame)),x])

def fit_coefficients(x,y,alpha,task):
    penalty=np.ones(x.shape[1]);penalty[0]=0
    if task=='continuous':return np.linalg.solve(x.T@x+len(y)*alpha*np.diag(penalty),x.T@y)
    if len(np.unique(y))<2:raise StudyError('BINARY_TRAINING_ONE_CLASS')
    objective=lambda b:float(np.mean(np.logaddexp(0,x@b)-y*(x@b))+.5*alpha*(penalty*b*b).sum())
    gradient=lambda b:x.T@(expit(x@b)-y)/len(y)+alpha*penalty*b
    fitted=minimize(objective,np.zeros(x.shape[1]),jac=gradient,method='BFGS',options={'gtol':1e-7,'maxiter':600})
    if not np.isfinite(fitted.x).all() or np.max(abs(gradient(fitted.x)))>1e-5:raise StudyError('RIDGE_LOGISTIC_NOT_CONVERGED')
    return fitted.x

def prediction_from_design(x,beta,task,target_transform):
    z=x@beta
    if task=='binary':return np.clip(expit(z),1e-12,1-1e-12)
    if target_transform=='log1p':z=np.expm1(np.clip(z,-30,30))
    return np.maximum(0,z)

def fit_training(frame,plan):
    from .prediction_metrics import binary_metrics,continuous_metrics
    task=plan['task'];y=frame.outcome.to_numpy(float);folds=inner_folds(frame.group_id,plan['split']['seed'],plan['split']['cv_folds']);cv=[]
    # Fit once per inner training fold, then score the prespecified candidates.
    bundles=[]
    for fold in range(plan['split']['cv_folds']):
        train=frame.iloc[np.flatnonzero(folds!=fold)];val=frame.iloc[np.flatnonzero(folds==fold)]
        if train.group_id.nunique()<100 or val.group_id.nunique()<30:raise StudyError('INNER_PATIENT_FOLD_TOO_SMALL')
        if task=='binary' and min(train.outcome.sum(),len(train)-train.outcome.sum(),val.outcome.sum(),len(val)-val.outcome.sum())<10:raise StudyError('INNER_BINARY_EVENT_COVERAGE_INSUFFICIENT')
        prep=fit_preprocessor(train,plan['features']);xt=transform(train,prep);xv=transform(val,prep);yt=train.outcome.to_numpy(float)
        if plan['outcome_transform']=='log1p':yt=np.log1p(yt)
        bundles.append((xt,yt,xv,val.outcome.to_numpy(float)))
    for alpha in plan['tuning']['ridge_grid']:
        scores=[]
        for xt,yt,xv,yv in bundles:
            beta=fit_coefficients(xt,yt,alpha,task);pred=prediction_from_design(xv,beta,task,plan['outcome_transform'])
            scores.append(float(np.mean(-(yv*np.log(pred)+(1-yv)*np.log1p(-pred)))) if task=='binary' else float(np.mean(abs(yv-pred))))
        cv.append({'ridge_alpha':alpha,'fold_scores':scores,'mean_score':float(np.mean(scores))})
    chosen=min(cv,key=lambda r:(r['mean_score'],r['ridge_alpha']))['ridge_alpha'];prep=fit_preprocessor(frame,plan['features']);x=transform(frame,prep)
    target=np.log1p(y) if plan['outcome_transform']=='log1p' else y;beta=fit_coefficients(x,target,chosen,task)
    return {'preprocessor':prep,'coefficients':beta.tolist(),'ridge_alpha':chosen,'task':task,'outcome_transform':plan['outcome_transform'],'training_patient_CV':cv,
      'tuning_metric':'mean_log_loss' if task=='binary' else 'original_unit_MAE','training_outcome_mean':float(y.mean()),'training_outcome_median':float(np.median(y)),
      'only_training_data_used':True,'training_patient_digest':digest(sorted(set(frame.group_id.astype(str))))}

def predict(frame,model):return prediction_from_design(transform(frame,model['preprocessor']),np.array(model['coefficients']),model['task'],model['outcome_transform'])

def fit_internal_holdout(frame,plan):
    """One orchestration used by real workflow and held-out perturbation tests."""
    train_mask,test_mask=split_groups(frame.group_id,plan['split']['seed'],plan['split']['test_fraction'])
    train=frame.iloc[np.flatnonzero(train_mask)].copy();test=frame.iloc[np.flatnonzero(test_mask)].copy()
    if set(train.group_id)&set(test.group_id):raise StudyError('PATIENT_SPLIT_OVERLAP')
    model=fit_training(train,plan)
    return {'model':model,'train_mask':train_mask,'test_mask':test_mask,'training_predictions':predict(train,model),'heldout_predictions':predict(test,model)}
