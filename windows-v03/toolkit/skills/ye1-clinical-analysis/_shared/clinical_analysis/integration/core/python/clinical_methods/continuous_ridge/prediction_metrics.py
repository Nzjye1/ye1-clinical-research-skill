"""Held-out assessment only. Calibration fits never update model predictions."""
import numpy as np
from scipy.special import expit
from scipy.stats import rankdata
from .core import StudyError

def _ratio(a,b):return float(a/b) if b else None

def binary_calibration(y,p):
    if min(y.sum(),len(y)-y.sum())<10:return {'calibration_intercept':None,'calibration_slope':None,'calibration_status':'too_few_events_or_nonevents'}
    eta=np.log(p/(1-p));a=0.
    for _ in range(100):
        fitted=expit(a+eta);den=float((fitted*(1-fitted)).sum())
        if den<1e-10:break
        step=float((y-fitted).sum()/den);a+=float(np.clip(step,-2,2))
        if abs(step)<1e-9:break
    offset=a if abs(a)<30 else None
    x=np.column_stack([np.ones(len(y)),eta]);b=np.array([0.,1.])
    if np.var(eta)<1e-12:return {'calibration_intercept':offset,'calibration_slope':None,'calibration_status':'constant_predictions_slope_unidentified'}
    for _ in range(100):
        pred=expit(x@b);information=x.T@((pred*(1-pred))[:,None]*x)
        if np.linalg.cond(information)>1e10:return {'calibration_intercept':offset,'calibration_slope':None,'calibration_status':'slope_not_estimable'}
        delta=np.linalg.solve(information,x.T@(y-pred));b+=np.clip(delta,-2,2)
        if np.max(abs(delta))<1e-8:break
    else:return {'calibration_intercept':offset,'calibration_slope':None,'calibration_status':'slope_not_converged'}
    if not np.isfinite(b).all() or np.max(abs(b))>30:return {'calibration_intercept':offset,'calibration_slope':None,'calibration_status':'slope_unstable'}
    return {'calibration_intercept':float(offset) if offset is not None else None,'calibration_slope':float(b[1]),'joint_calibration_intercept':float(b[0]),'calibration_status':'estimated_diagnostic_only',
      'calibration_definition':'intercept_offset_logit_model_slope_fixed_1;slope_joint_logit_model_free_intercept;no_recalibration_applied'}

def binary_metrics(y,p,threshold=.5,calibration=True):
    y=np.asarray(y,float);p=np.clip(np.asarray(p,float),1e-12,1-1e-12);positive=int(y.sum());negative=len(y)-positive
    auc=float((rankdata(p)[y==1].sum()-positive*(positive+1)/2)/(positive*negative)) if positive and negative else None
    if positive:
        order=np.argsort(-p,kind='stable');ys=y[order];ps=p[order];tp=np.cumsum(ys);ends=np.r_[np.flatnonzero(ps[:-1]!=ps[1:]),len(y)-1]
        ap=float(np.sum(np.diff(np.r_[0,tp[ends]])/positive*tp[ends]/(ends+1)))
    else:ap=None
    selected=p>=threshold;tp=int(((y==1)&selected).sum());tn=int(((y==0)&~selected).sum());fp=negative-tn;fn=positive-tp
    result={'AUROC':auc,'average_precision':ap,'Brier':float(np.mean((p-y)**2)),'log_loss':float(np.mean(-y*np.log(p)-(1-y)*np.log1p(-p))),
      'observed_prevalence':float(y.mean()),'mean_predicted_probability':float(p.mean()),'sensitivity':_ratio(tp,tp+fn),'specificity':_ratio(tn,tn+fp),
      'PPV':_ratio(tp,tp+fp),'NPV':_ratio(tn,tn+fn),'threshold':threshold,'TP':tp,'TN':tn,'FP':fp,'FN':fn}
    if calibration:result.update(binary_calibration(y,p))
    return result

def continuous_metrics(y,p):
    y=np.asarray(y,float);p=np.asarray(p,float);error=y-p;variance=float(np.sum((y-y.mean())**2));pv=float(np.sum((p-p.mean())**2))
    slope=float(np.sum((p-p.mean())*(y-y.mean()))/pv) if pv>1e-12 else None
    return {'MAE':float(np.mean(abs(error))),'RMSE':float(np.sqrt(np.mean(error**2))),'R_squared':float(1-np.sum(error**2)/variance) if variance>1e-12 else None,
      'median_absolute_error':float(np.median(abs(error))),'mean_error_observed_minus_predicted':float(error.mean()),
      'calibration_slope':slope,'calibration_intercept':float(y.mean()-slope*p.mean()) if slope is not None else None,
      'calibration_status':'estimated_diagnostic_only' if slope is not None else 'constant_predictions_slope_unidentified'}

def calibration_bins(y,p,cuts,minimum=20):
    labels=np.searchsorted(cuts,p,side='right');bins=[]
    for i in range(len(cuts)+1):
        mask=labels==i;n=int(mask.sum());bins.append({'bin':i+1,'records_n':n,'mean_prediction':float(p[mask].mean()) if n>=minimum else None,
          'mean_observed':float(y[mask].mean()) if n>=minimum else None,'status':'reported' if n>=minimum else 'empty_or_small_bin_suppressed'})
    return bins

def bootstrap_metrics(y,p,groups,task,repetitions,seed,threshold):
    # Cluster resampling retains all operations/admissions from each sampled patient.
    group_values=np.asarray(groups,str);order=np.argsort(group_values,kind='stable');ordered=group_values[order]
    starts=np.flatnonzero(ordered[1:]!=ordered[:-1])+1;indices=np.split(order,starts);unique=np.arange(len(indices))
    rng=np.random.default_rng(seed+731);keys=['AUROC','average_precision','Brier','log_loss','calibration_intercept','calibration_slope'] if task=='binary' else ['MAE','RMSE','R_squared','mean_error_observed_minus_predicted','calibration_intercept','calibration_slope']
    samples={k:[] for k in keys}
    for _ in range(repetitions):
        chosen=rng.integers(0,len(unique),len(unique));rows=np.concatenate([indices[i] for i in chosen]);m=binary_metrics(y[rows],p[rows],threshold) if task=='binary' else continuous_metrics(y[rows],p[rows])
        for key in keys:
            value=m.get(key)
            if value is not None and np.isfinite(value):samples[key].append(float(value))
    result={}
    for key,values in samples.items():
        enough=len(values)>=max(40,int(.8*repetitions));result[key]={'lower95':float(np.quantile(values,.025)) if enough else None,'upper95':float(np.quantile(values,.975)) if enough else None,
          'valid_resamples_n':len(values),'requested_resamples_n':repetitions,'status':'estimated_percentile' if enough else 'insufficient_valid_bootstrap_resamples'}
    return result

def evaluate(y,p,groups,model,train_predictions,plan):
    y=np.asarray(y,float);p=np.asarray(p,float);task=plan['task'];threshold=plan['evaluation']['threshold']
    if not np.isfinite(p).all():raise StudyError('NONFINITE_HELDOUT_PREDICTIONS')
    metrics=binary_metrics(y,p,threshold) if task=='binary' else continuous_metrics(y,p)
    baseline=np.full(len(y),model['training_outcome_mean'] if task=='binary' else model['training_outcome_median'])
    baseline_metrics=binary_metrics(y,baseline,threshold,calibration=False) if task=='binary' else continuous_metrics(y,baseline)
    cuts=np.linspace(.1,.9,9) if task=='binary' else np.unique(np.quantile(train_predictions,[.2,.4,.6,.8]))
    bins=calibration_bins(y,p,cuts);ci=bootstrap_metrics(y,p,groups,task,plan['evaluation']['bootstrap_repetitions'],plan['split']['seed'],threshold)
    roc=[]
    if task=='binary':
        positive=int(y.sum());negative=len(y)-positive
        for cut in np.linspace(1,0,101):roc.append({'FPR':_ratio(int(((y==0)&(p>=cut)).sum()),negative),'TPR':_ratio(int(((y==1)&(p>=cut)).sum()),positive)})
    return {'metrics':metrics,'bootstrap95':ci,'baseline_metrics':baseline_metrics,'baseline_definition':'training_prevalence' if task=='binary' else 'training_median_original_units',
      'calibration_bins':bins,'calibration_cuts':cuts.tolist(),'bin_rule':'prespecified_probability_deciles' if task=='binary' else 'training_prediction_quintiles_locked_before_holdout',
      'roc_grid_101_prespecified_thresholds':roc,'uncertainty_scope':'patient_cluster_holdout_sampling_conditional_on_fixed_trained_model;not_entire_model_development_uncertainty',
      'evaluation_not_recalibration':True,'clinical_threshold_not_established':True}
