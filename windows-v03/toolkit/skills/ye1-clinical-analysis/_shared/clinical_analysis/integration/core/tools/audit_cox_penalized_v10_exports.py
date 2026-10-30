"""Read-only local Cox artifact audit: every aggregate row, source, scale and ID."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,statistics,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as h:
        reader=csv.DictReader(h);assert len(reader.fieldnames)==len(set(reader.fieldnames)),'duplicate CSV columns';return list(reader)
def close(a,b,tol=1e-12):
    assert a is not None and b is not None,'null scalar';a=float(a);b=float(b);assert math.isfinite(a) and math.isfinite(b),'nonfinite scalar';d=abs(a-b);assert d<=tol,f'absolute difference {d:.17g} exceeds fixed {tol:g}';return d
def equal(a,b):
    if b is None:assert a in (None,'','NA'),'null mismatch'
    elif isinstance(b,bool):assert str(a).lower()==str(b).lower(),'boolean mismatch'
    elif type(b) in (int,float):close(a,b)
    elif isinstance(b,(list,dict)):assert (json.loads(a) if isinstance(a,str) else a)==b,'nested projection mismatch'
    else:assert a==b,'text mismatch'
def subset(a,b):
    if isinstance(b,dict):
        assert isinstance(a,dict),'object required'
        for k,v in b.items():assert k in a,'missing field '+k;subset(a[k],v)
    elif isinstance(b,list):
        assert isinstance(a,list) and len(a)==len(b),'array length mismatch'
        for x,y in zip(a,b):subset(x,y)
    else:equal(a,b)
def source_rows(task):
    view=task['views'][0];path=Path(view['local_ref']).resolve();assert path.is_relative_to(ROOT) and sha(path)==view['content_hash']
    options=task['analysis']['cox_penalized_prediction'];spec=options['spec'];infer=options['operation']=='infer';rows=[]
    for source in table(path):
        row={}
        for v in task['variables']:
            if infer and v['name'] in (spec['duration'],spec['event']):row[v['name']]=None;continue
            value=source[view['column_map'][v['name']]]
            if value in v['missing_codes']:value=None
            elif v['dtype']=='number':value=float(value)*v['conversion']['scale']+v['conversion']['offset']
            elif v['dtype']=='category':value=v['codes'][value]
            row[v['name']]=value
        rows.append(row)
    return sorted(rows,key=lambda row:row[spec['id']].encode('utf-8'))
def privacy(out,result,counts):
    assert result['test_only'] is True and result['scientific_review']=='pending' and result['export_status']=='local_only'
    for path in out.rglob('*'):
        if not path.is_file() or 'private' in path.relative_to(out).parts or path.suffix not in ('.json','.csv','.html','.md','.txt'):continue
        content=path.read_text(encoding='utf-8-sig',errors='replace');assert 'SYNTHETIC-V10-' not in content,'subject/group identity publicly exposed'
        for field in ('training_subject_ids','training_group_ids','fitted_subject_ids','individual_predictions','preprocessor'):assert '"'+field+'"' not in content,'private data publicly exposed'
        counts['public_files_scanned']+=1
    assert not result['estimates'] and not result['tests'] and not result['metrics'] and not result['model_results'],'unsupported inference or performance claims'
    for field in ('survival','cox_prediction','survival_evaluation','psm','penalized_prediction','interpretation'):assert result[field] is None
def eta_formula(row,model):
    features={f['name']:f for f in model['preprocessor']['features']};terms=[]
    for col,beta in zip(model['preprocessor']['columns'],model['coefficients']):
        f=features[col['feature']];value=row[f['name']];value=f['impute'] if value is None else value
        if f['type']=='category':assert value in f['levels'];value=float(value==col['level'])
        terms.append((value-col['center'])/col['scale']*beta)
    return math.fsum(terms)
def risk_formula(eta,horizon,model):
    baseline=model['baseline'];h=0
    for t,value in zip(baseline['event_times'],baseline['cumulative_hazard']):
        if t<=horizon:h=value
    if h==0:return 0.
    z=math.log(h)+eta-baseline['center'];return 1. if z>math.log(sys.float_info.max) else -math.expm1(-math.exp(z))
def check_preprocessor(training,model,counts):
    prep=model['preprocessor'];columns=[];dropped=[];expected={}
    for i,f in enumerate(prep['features'],1):
        present=[r[f['name']] for r in training if r[f['name']] is not None];assert present
        if f['type']=='number':impute=statistics.median(present);equal(f['impute'],impute);assert f['levels']==[] and f['reference'] is None;levels=[None]
        else:
            seen=sorted(set(present),key=lambda x:x.encode('utf-8'));mode=max(seen,key=lambda x:present.count(x));assert f['impute']==mode and f['levels']==seen and f['reference']==seen[0];impute=mode;levels=seen[1:]
        full=[impute if r[f['name']] is None else r[f['name']] for r in training]
        for j,level in enumerate(levels,2):
            term=f'X{i:04d}' if f['type']=='number' else f'X{i:04d}L{j:04d}';x=full if level is None else [float(v==level) for v in full]
            center=math.fsum(x)/len(x);scale=math.sqrt(math.fsum((v-center)**2 for v in x)/len(x))
            if scale==0:dropped.append(term)
            else:columns.append(term);expected[term]=(center,scale)
    assert columns==[r['term'] for r in prep['columns']] and dropped==[r['term'] for r in prep['dropped_columns']]
    for col in prep['columns']:close(col['center'],expected[col['term']][0]);close(col['scale'],expected[col['term']][1])
    assert all(col['reason_code']=='ZERO_VARIANCE' for col in prep['dropped_columns'])
    eta=[eta_formula(r,model) for r in training];center=math.fsum(eta)/len(eta);counts['max_baseline_formula_difference']=max(counts['max_baseline_formula_difference'],close(model['baseline']['center'],center,2e-8))
    spec=model['spec'];times=sorted({r[spec['duration']] for r in training if r[spec['event']]==1});assert times==model['baseline']['event_times'];total=0
    for t,actual in zip(times,model['baseline']['cumulative_hazard']):
        d=sum(r[spec['duration']]==t and r[spec['event']]==1 for r in training);riskset=math.fsum(math.exp(z-center) for r,z in zip(training,eta) if r[spec['duration']]>=t);total+=d/riskset
        counts['max_baseline_formula_difference']=max(counts['max_baseline_formula_difference'],close(actual,total,2e-8))
    support=model['training_support'];assert support=={'n_training':len(training),'events':sum(r[spec['event']] for r in training),'censored':sum(r[spec['event']]==0 for r in training),'min_time':min(r[spec['duration']] for r in training),'max_followup':max(r[spec['duration']] for r in training),'last_event_time':max(times),'horizon_min':0,'horizon_max':max(r[spec['duration']] for r in training)}
def audit_record(out,result,task,counts,lock):
    rec=result['cox_penalized_prediction'];subset(rec,load(out/'private/backend.json'));options=task['analysis']['cox_penalized_prediction'];spec=options['spec'];train=options['operation']=='train';complete=rec['status']=='completed'
    source=source_rows(task);byid={r[spec['id']]:r for r in source};assert len(source)==len(byid)
    training=[r for r in source if r[spec['split']['partition_field']]=='train'];holdout=[r for r in source if r[spec['split']['partition_field']]=='holdout'];flow=rec['flow']
    assert flow['n_input']==len(source) and flow['n_training']==len(training) and flow['n_holdout']==(len(holdout) if train else 0)
    assert result['counts']['source_rows']==result['counts']['subjects']==len(source) and result['counts']['excluded_missing']==result['counts']['prediction_clipped_n']==0
    assert result['provider']['version']==lock['cox_penalized_provider_version'] and result['provider']['code_hash']==lock['cox_penalized_provider_version']
    assert rec['coefficient_scale']=='standardized_x_log_relative_hazard' and rec['prediction_scale']=='cumulative_event_probability' and rec['family']=='cox'
    for name,pop in [('training',training),('holdout',holdout)]:
        for suffix,value in [('events',sum(r[spec['event']] for r in pop) if train else None),('censored',sum(r[spec['event']]==0 for r in pop) if train else None)]:equal(flow[f'n_{name}_{suffix}'],value)
    for field in ('missing_duration_n','missing_event_n'):equal(flow[field],0 if train else None)
    private=table(out/'private/cox-penalized-individual-predictions.csv');counts['private_prediction_rows']+=len(private)
    if complete:
        assert flow['n_predicted']==len(source) and len(private)==len(source)*len(spec['horizons'])
        assert len({(r['subject_id'],float(r['horizon'])) for r in private})==len(private)
        path=out/'private/cox-penalized-model.json' if train else Path(options['model_ref']['local_ref']);bundle=load(path);model=bundle['model'];assert result['binding']['model_hash']==sha(path)
        assert bundle['schema_version']=='clinical-frozen-cox-penalized@0.10.0-candidate1' and bundle['provider_version']==lock['cox_penalized_provider_version']
        assert bundle['runtime_binding']=={'versions':lock['cox_penalized_runtime'],'package_paths':lock['cox_penalized_package_paths'],'dependency_hashes':lock['cox_penalized_dependency_hashes'],'rscript_engine':lock['rscript_engine'],'rscript_sha256':lock['executable_hashes'][lock['rscript_engine']],'preprocessing_version':lock['cox_penalized_preprocessing_version']}
        assert len(bundle['runtime_binding']['dependency_hashes'])==15 and bundle['canonical_semantics']==model['semantics']==rec['semantics']
        assert model['schema_version']=='clinical-cox-penalized-model@0.10.0-candidate1' and model['method_id']==result['method_id']
        assert model['source']=={'coefficient_owner':'glmnet::glmnet','baseline_owner':'survival::coxph_offset_and_survfit','preprocessing_owner':'penalized_v08_prepare'}
        if train:
            assert model['training_subject_ids']==[r[spec['id']] for r in training];groups=sorted({r[spec['split']['group_field']] for r in training},key=lambda x:x.encode('utf-8')) if spec['split']['group_field'] else []
            assert model['training_group_ids']==groups;check_preprocessor(training,model,counts);assert rec['diagnostics']['n_engine_fits']==spec['split']['cv_folds']+1
        else:
            assert not (out/'private/cox-penalized-model.json').exists() and rec['diagnostics']['n_engine_fits']==0 and rec['cv']['reason_code']=='FROZEN_MODEL_NO_REFIT'
            assert not set(byid)&set(model['training_subject_ids']) and spec['cohort_id']!=model['spec']['cohort_id']
            assert not rec['path'] and not rec['cv']['rows'] and not rec['cv']['folds'] and not rec['cv']['fold_losses']
        for row in private:
            raw=byid[row['subject_id']];eta=eta_formula(raw,model);risk=risk_formula(eta,float(row['horizon']),model)
            counts['max_linear_predictor_formula_difference']=max(counts['max_linear_predictor_formula_difference'],close(row['linear_predictor'],eta,2e-7),close(row['centered_linear_predictor'],eta-model['baseline']['center'],2e-7))
            counts['max_risk_formula_difference']=max(counts['max_risk_formula_difference'],close(row['risk'],risk,2e-8),close(row['survival'],1-risk,2e-8))
            equal(row['duration'],raw[spec['duration']] if train else None);equal(row['event'],raw[spec['event']] if train else None)
            equal(row['fold'],raw[spec['split']['fold_field']]);equal(row['partition'],raw[spec['split']['partition_field']]);equal(row['group_id'],raw[spec['split']['group_field']] if spec['split']['group_field'] else None)
        for row in rec['horizons']:
            values=[float(r['risk']) for r in private if float(r['horizon'])==row['horizon'] and (not train or r['partition']==('train' if row['population']=='training' else 'holdout'))]
            assert row['n_predicted']==len(values) and row['time_unit']==spec['survival']['time_unit'];close(row['min_risk'],min(values));close(row['max_risk'],max(values));close(row['mean_risk'],math.fsum(values)/len(values))
        for key in ('selected_lambda','selected_engine_lambda','selected_lambda_index'):assert rec[key]==model[key]
        assert model['selected_lambda']==spec['lambda_grid'][model['selected_lambda_index']-1]
        assert rec['diagnostics']['warning_count']==0 and (rec['diagnostics']['jerr']==0 if train else rec['diagnostics']['jerr'] is None)
        assert len(rec['coefficients'])==len(model['coefficients'])
        for row,beta in zip(rec['coefficients'],model['coefficients']):close(row['coefficient'],beta);assert row['nonzero']==(beta!=0) and row['term']!='(Intercept)' and row['source']==('training' if train else 'frozen_training')
        equal(rec['baseline']['reference_center'],model['baseline']['center']);assert rec['baseline']['event_time_count']==len(model['baseline']['event_times'])
        assert rec['baseline']['last_event_time']==model['training_support']['last_event_time'] and rec['baseline']['max_followup']==model['training_support']['max_followup'] and rec['baseline']['coefficient_updates']==0
        counts['completed_runs']+=1
    else:
        assert result['execution_status']=='blocked' and rec['reason_code'] and not private and not (out/'private/cox-penalized-model.json').exists() and not result['figures'];counts['numerical_refusals']+=1
    for row in rec['preprocessing']:
        if row['stage']=='cv':population=[r for r in training if (r[spec['split']['fold_field']]==row['fold'])==(row['role']=='validation')];fitting=[r for r in training if r[spec['split']['fold_field']]!=row['fold']]
        elif row['stage']=='final':population=training if row['role']=='fitting' else holdout;fitting=training
        else:assert row['stage']=='external' and row['role']=='external';population=source;fitting=None
        missing=sum(r[row['feature']] is None for r in population);assert row['n_rows']==len(population) and row['n_missing']==row['n_imputed']==missing
        if row['type']=='number':assert row['fitted_levels']==[] and row['fitted_reference'] is None and row['encoding_rule']=='identity_numeric'
        else:
            levels=next(f['levels'] for f in model['preprocessor']['features'] if f['name']==row['feature']) if fitting is None else sorted({r[row['feature']] for r in fitting if r[row['feature']] is not None},key=lambda x:x.encode('utf-8'))
            assert row['fitted_levels']==levels and row['fitted_reference']==levels[0] and row['encoding_rule']=='treatment_utf8_observed_reference_first'
        counts['fitted_preprocessing_rows']+=1
    if complete and train:
        cv=rec['cv'];assert cv['weighting']=='validation_event_count' and cv['scope']=='training_only_tuning' and cv['loss_name']=='heldout_only_breslow_partial_likelihood_deviance'
        assert [r['lambda'] for r in cv['rows']]==spec['lambda_grid'] and rec['selected_lambda_index']==min(range(len(cv['rows'])),key=lambda i:cv['rows'][i]['deviance_per_event'])+1
        for row in cv['rows']:
            related=[r for r in cv['fold_losses'] if r['lambda_index']==row['lambda_index']];assert len(related)==spec['split']['cv_folds']
            assert sum(r['validation_events'] for r in related)==row['validation_events']==flow['n_training_events'];close(row['deviance_sum'],math.fsum(r['deviance_sum'] for r in related));close(row['deviance_per_event'],row['deviance_sum']/row['validation_events'])
            for loss in related:close(loss['deviance_per_event'],loss['deviance_sum']/loss['validation_events']);assert abs(loss['engine_lambda']-loss['lambda'])<=32*sys.float_info.epsilon*abs(loss['lambda'])
        for row in cv['folds']:
            fitting=[r for r in training if r[spec['split']['fold_field']]!=row['fold']];validation=[r for r in training if r[spec['split']['fold_field']]==row['fold']]
            for name,pop in [('training',fitting),('validation',validation)]:assert row['n_'+name]==len(pop) and row[name+'_events']==sum(r[spec['event']] for r in pop) and row[name+'_censored']==sum(r[spec['event']]==0 for r in pop)
            assert row['training_events']>=8 and row['validation_events']>=3 and row['jerr']==row['warning_count']==0
        assert len(rec['path'])==len(spec['lambda_grid'])*len(rec['coefficients'])
        for a,b in zip([r for r in rec['path'] if r['lambda_index']==rec['selected_lambda_index']],rec['coefficients']):subset(a,{k:b[k] for k in ('term','feature','type','level','coefficient','nonzero')})
    null_names={'n_training_events','n_training_censored','n_holdout_events','n_holdout_censored','missing_duration_n','missing_event_n'}
    flowrows=[{'result_id':rec['result_id'],'count_name':k,'value':v,'count_semantics':'outcomes_not_read_in_infer' if not train and k in null_names else 'explicit_subject_or_design_count'} for k,v in flow.items()]
    datasets={'cox_penalized_flow':flowrows,'cox_penalized_imputation':rec['preprocessing'],'cox_penalized_cv':rec['cv']['rows'],'cox_penalized_cv_folds':rec['cv']['folds'],'cox_penalized_cv_fold_losses':rec['cv']['fold_losses'],'cox_penalized_coefficient_path':rec['path'],'cox_penalized_coefficients':rec['coefficients'],'cox_penalized_baseline':[rec['baseline']],'cox_penalized_horizons':rec['horizons']}
    if rec['coefficients']:datasets['cox_penalized_nonzero']=[r for r in rec['coefficients'] if r['nonzero']]
    metadata={'method_id':result['method_id'],'method_version':result['method_version'],'provider_version':result['provider']['version'],'preprocessing_version':lock['cox_penalized_preprocessing_version'],'core_version':result['core_version'],'run_id':result['run_id'],'operation':rec['operation'],'family':rec['family'],'penalty':rec['penalty'],'alpha':rec['alpha'],'coefficient_scale':rec['coefficient_scale'],'prediction_scale':rec['prediction_scale'],'duration_unit':rec['semantics']['survival']['time_unit'],'source_input_hash':result['binding']['input_hash'],'source_plan_hash':result['binding']['plan_hash'],'scientific_review':'pending','export_status':'local_only','test_only':True}
    expected={};ids=[rec['result_id'],rec['baseline']['result_id']]
    for rows in (rec['preprocessing'],rec['cv']['rows'],rec['cv']['folds'],rec['cv']['fold_losses'],rec['path'],rec['coefficients'],rec['horizons']):ids.extend(r['result_id'] for r in rows)
    assert len(ids)==len(set(ids)),'duplicate result IDs'
    for name,rows in datasets.items():
        path=out/'tables'/(name+'.csv')
        if not rows and name!='cox_penalized_nonzero':assert not path.exists();continue
        exported=table(path);assert len(exported)==len(rows)
        for actual,row in zip(exported,rows):
            assert set(actual)==set(metadata)|set(row),'CSV field set mismatch'
            for key,value in {**metadata,**row}.items():equal(actual[key],value)
        expected[name]=(path,{r['result_id'] for r in rows} or {rec['result_id']});counts['public_csv_rows']+=len(exported)
    assert set(expected)=={r['artifact_id'] for r in result['tables']}
    for artifact in result['tables']:
        path,source_ids=expected[artifact['artifact_id']];assert sha(path)==artifact['data_hash'] and set(artifact['source_result_ids'])==source_ids and artifact['caption'] and artifact['ci'] is None and artifact['test_only'] is True;counts['artifact_hashes']+=1
    figures=[]
    if complete:
        figures.append(('cox_penalized_horizons',rec['horizons'],None))
        if train:figures.extend([('cox_penalized_cv',rec['cv']['rows'],flow['n_training_events']),('cox_penalized_coefficient_path',rec['path'],flow['n_training'])])
    assert {r['artifact_id'] for r in result['figures']}=={r[0] for r in figures}
    for name,rows,denominator in figures:
        artifact=next(a for a in result['figures'] if a['artifact_id']==name);path=out/'figures'/(name+'.png')
        assert path.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n' and sha(path)==artifact['data_hash'];assert set(artifact['source_result_ids'])=={r['result_id'] for r in rows} and artifact['denominator']==denominator and artifact['ci'] is None and artifact['caption'];counts['artifact_hashes']+=1
    counts['record_runs']+=1;return set(ids)
def audit(suite):
    receipt=load(suite/'acceptance-receipt.json');assert receipt['runtime_lock_sha256']==sha(ROOT/'runtime-lock.json') and all(sha(ROOT/p)==v for p,v in receipt['source_sha256'].items())
    lock=load(ROOT/'runtime-lock.json');counts={k:0 for k in ('runs','record_runs','completed_runs','numerical_refusals','contract_refusals','public_files_scanned','private_prediction_rows','public_csv_rows','artifact_hashes','writing_reference_checks','fitted_preprocessing_rows')};counts.update(max_linear_predictor_formula_difference=0.,max_risk_formula_difference=0.,max_baseline_formula_difference=0.);checks=[]
    for item in receipt['runs']:
        try:
            out=Path(item['output_dir']).resolve();assert out.is_relative_to(suite);result=load(out/'result.json');task=load(item['task_path']);assert result['binding']['input_hash']==sha(item['task_path']);assert load(out/'private/result-validation.json')['ok'] is True
            privacy(out,result,counts);ids=set()
            if result['cox_penalized_prediction'] is not None:ids=audit_record(out,result,task,counts,lock)
            else:assert result['execution_status']=='blocked' and not result['tables'] and not result['figures'];counts['contract_refusals']+=1
            assert set(load(out/'writing-references.json')['result_ids'])==ids;counts['writing_reference_checks']+=1;counts['runs']+=1;checks.append({'label':item['label'],'status':'PASS'})
        except Exception as e:checks.append({'label':item['label'],'status':'FAIL','reason':type(e).__name__+': '+str(e)})
    status='PASS' if all(c['status']=='PASS' for c in checks) and receipt['status']=='PASS' else 'FAIL'
    return {'status':status,**counts,'checks':checks,'runtime_lock_sha256':receipt['runtime_lock_sha256'],'acceptance_receipt_sha256':sha(suite/'acceptance-receipt.json'),'tolerances':{'projection_absolute':1e-12,'linear_predictor_formula_absolute':2e-7,'baseline_risk_formula_absolute':2e-8},'scope':'Synthetic local-only source/preprocessing/manual Breslow/frozen formula, every public CSV row, source hashes, scales, counts, unique IDs, artifact hashes and privacy. No clinical validation.'}
def main(args):
    suite=args.suite.resolve();assert suite.is_relative_to(ROOT);target=args.out or suite/'export-audit.json';assert not target.exists(),'existing audit preserved'
    try:result=audit(suite)
    except Exception as e:result={'status':'FAIL','reason':type(e).__name__+': '+str(e)}
    result['audit_script_sha256']=sha(__file__);target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps({'status':result['status'],'receipt':str(target),'runs':result.get('runs'),'failed':sum(r['status']=='FAIL' for r in result.get('checks',[]))}),flush=True);return int(result['status']!='PASS')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('suite',type=Path);parser.add_argument('--workdir',type=Path,default=ROOT);parser.add_argument('--out',type=Path);args=parser.parse_args();ROOT=args.workdir.resolve();raise SystemExit(main(args))
