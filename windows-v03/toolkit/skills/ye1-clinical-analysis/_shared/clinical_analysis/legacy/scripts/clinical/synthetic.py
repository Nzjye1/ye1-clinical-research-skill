"""Built-in SYNTHETIC_TEST_ONLY fixtures; no external data inputs or real findings."""
import math
import random


def fixture(module):
    rng = random.Random(20261022)
    if module == 'association':
        rows = []
        for i in range(500):
            x, age = rng.gauss(0, 1), rng.uniform(20, 80)
            rows.append({'id':f'SYNTHETIC-{i}','x':x,'age':age,
                         'y':1.3+2*x+.2*age+rng.gauss(0,.4)})
        spec = {'model':'linear','row_unit':'one synthetic person','key':'id',
                'independent':True,'outcome':'y','exposure':'x','covariates':['age'],
                'missing':'complete_case','covariance':'HC3'}
    elif module == 'prediction':
        rows = []
        for i in range(900):
            age, lab = rng.gauss(50, 12), rng.gauss(0, 1)
            probability = 1/(1+math.exp(-(-.3+.055*(age-50)+.6*lab)))
            rows.append({'id':f'SYNTHETIC-{i}','age':age,
                         'lab':lab if i%11 else None,
                         'outcome':str(int(rng.random()<probability))})
        spec = {'id':'id','outcome':'outcome','event':'1','non_event':'0',
                'cohort_id':'SYNTHETIC-DEVELOPMENT','prediction_time':'synthetic baseline',
                'outcome_window':'synthetic 90-day binary followup',
                'features':[{'name':n,'type':'number','available_at_prediction':True}
                            for n in ['age','lab']],
                'split':{'method':'random','test_fraction':.3,'seed':731},
                'missing':'train_median_mode','C':1.,'min_epv':10,'independent_subjects':True,
                'cv_folds':3,'bootstrap':50,'decision_thresholds':[.1,.3,.5]}
    elif module == 'trajectory':
        rows = [{'person':f'SYNTHETIC-{g}-{i}','day':float(t),'known_day':t+.1,
                 'measurement':20+i*.001+slope*t,'unit':'arbitrary units'}
                for g,slope in enumerate([-1.,0.,1.]) for i in range(16)
                for t in [0,2,4,6,8,10]]
        spec = {'method':'window_median_change','subject_id':'person','time':'day',
                'availability_time':'known_day','value':'measurement',
                'time_zero':'synthetic baseline visit','time_unit':'day',
                'value_unit':'arbitrary units','unit_column':'unit','landmark':12,
                'windows':[[0,6],[6,12]],'min_observations_per_window':2,
                'min_time_gap':5,'change_threshold':2,'round_decimals':10,'min_group_size':2}
    elif module == 'clustering':
        rows = [{'id':f'SYNTHETIC-{g}-{i}','x':location+rng.gauss(0,.22),
                 'y':location+rng.gauss(0,.25)}
                for g,location in enumerate([-6.,0.,6.]) for i in range(35)]
        spec = {'method':'kmeans','id_column':'id','row_unit':'one synthetic person',
                'features':['x','y'],'feature_window':'synthetic baseline before outcome',
                'missing':'median','seed':7,'k':3,'n_init':5,'max_iter':250,
                'min_cluster_size':8,'bootstrap':10}
    elif module == 'survival':
        rows = []
        for i in range(700):
            x = rng.gauss(0,1)
            t, competing, censor = (rng.expovariate(.08*math.exp(.6*x)),
                                    rng.expovariate(.035), rng.uniform(6,18))
            elapsed = min(t,competing,censor)
            rows.append({'id':f'SYNTHETIC-{i}','followup':elapsed,
                         'event':1 if t==elapsed else (2 if competing==elapsed else 0),'x':x})
        spec = {'method':'aalen_johansen','subject_id':'id','time':'followup','status':'event',
                'time_unit':'days','time_zero_definition':'synthetic baseline visit',
                'event_definition':'synthetic target event','censoring_definition':'synthetic last followup',
                'event_code':1,'censor_code':0,'independent_subjects':True,
                'missing_policy':'complete_case','evaluation_times':[0,2,4,8,12],
                'competing_codes':[2],'competing_event_definitions':['synthetic competing event']}
    else:
        raise ValueError('UNSUPPORTED_MODULE')
    return rows, spec
