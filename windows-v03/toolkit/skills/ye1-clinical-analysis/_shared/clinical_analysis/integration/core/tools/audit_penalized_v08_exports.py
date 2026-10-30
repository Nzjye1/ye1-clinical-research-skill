"""Read-only v08 aggregate, private-formula, denominator and provenance audit."""
from __future__ import annotations
import csv,hashlib,json,math,statistics,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1];ATOL=RTOL=1e-10
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as h:
        reader=csv.DictReader(h);assert len(reader.fieldnames)==len(set(reader.fieldnames)),'duplicate CSV column';return list(reader)
def close(a,b):
    assert a is not None and b is not None,'null scalar';a=float(a);b=float(b);assert math.isfinite(a) and math.isfinite(b),'nonfinite scalar'
    d=abs(a-b);assert d<=ATOL+RTOL*abs(b),'numeric discrepancy exceeds fixed atol+rtol 1e-10';return d
def equal(a,b):
    if b is None:assert a in (None,'','NA'),'null projection mismatch'
    elif isinstance(b,bool):assert str(a).lower()==str(b).lower(),'boolean mismatch'
    elif type(b) in (int,float):close(a,b)
    elif isinstance(b,list):assert (json.loads(a) if isinstance(a,str) else a)==b,'array projection mismatch'
    else:assert a==b,'text mismatch'
def subset(a,b):
    if isinstance(b,dict):
        assert isinstance(a,dict),'expected object'
        for k,v in b.items():assert k in a,'missing field '+k;subset(a[k],v)
    elif isinstance(b,list):
        assert isinstance(a,list) and len(a)==len(b),'array mismatch'
        for x,y in zip(a,b):subset(x,y)
    else:equal(a,b)
def source_rows(task):
    view=task['views'][0];path=Path(view['local_ref']).resolve();assert path.is_relative_to(ROOT) and sha(path)==view['content_hash']
    rows=[]
    for source in table(path):
        row={}
        for v in task['variables']:
            value=source[view['column_map'][v['name']]]
            if value in v['missing_codes']:value=None
            elif v['dtype']=='number':value=float(value)*v['conversion']['scale']+v['conversion']['offset']
            elif v['dtype']=='category':value=v['codes'][value]
            row[v['name']]=value
        rows.append(row)
    return rows
def privacy(out,result,counts):
    assert result['test_only'] is True and result['scientific_review']=='pending' and result['export_status']=='local_only'
    for p in out.rglob('*'):
        if not p.is_file() or 'private' in p.relative_to(out).parts or p.suffix not in ('.json','.csv','.html','.md','.txt'):continue
        text=p.read_text(encoding='utf-8-sig',errors='replace');assert 'SYNTHETIC-V08-' not in text,'individual identity exposed in public artifact'
        for field in ('training_subject_ids','training_group_ids','fitted_subject_ids','linear_predictor','preprocessor','response_transform'):assert '"'+field+'"' not in text,'private field exposed'
        counts['public_files_scanned']+=1
    assert not result['estimates'] and not result['tests'],'unplanned postselection inference'
    for key in ('survival','cox_prediction','survival_evaluation','psm'):assert result[key] is None
def formula(row,model):
    pp=model['preprocessor'];fmap={f['name']:f for f in pp['features']};terms=[]
    for col,beta in zip(pp['columns'],model['coefficients']):
        f=fmap[col['feature']];value=row[f['name']];value=f['impute'] if value is None else value
        if f['type']=='category':assert value in f['levels'];value=float(value==col['level'])
        terms.append((value-col['center'])/col['scale']*beta)
    eta=model['intercept']+math.fsum(terms)
    if model['spec']['family']=='gaussian':pred=model['response_transform']['center']+model['response_transform']['scale']*eta
    else:pred=1/(1+math.exp(-eta)) if eta>=0 else math.exp(eta)/(1+math.exp(eta))
    return pred,eta
def check_final_preprocessor(training,model):
    pp=model['preprocessor'];numeric={};columns=[];dropped=[]
    for j,f in enumerate(pp['features'],1):
        values=[r[f['name']] for r in training];present=[x for x in values if x is not None];assert present
        if f['type']=='number':impute=statistics.median(present);equal(f['impute'],impute);assert f['levels']==[] and f['reference'] is None;levels=[None]
        else:
            levels_seen=sorted(set(present),key=lambda x:x.encode('utf-8'));freq={x:present.count(x) for x in levels_seen};mode=max(levels_seen,key=lambda x:freq[x])
            assert f['impute']==mode and f['levels']==levels_seen and f['reference']==levels_seen[0];impute=mode;levels=levels_seen[1:]
        full=[impute if x is None else x for x in values]
        for k,level in enumerate(levels,2):
            term=f'X{j:04d}' if f['type']=='number' else f'X{j:04d}L{k:04d}'
            x=full if level is None else [float(v==level) for v in full];center=math.fsum(x)/len(x);scale=math.sqrt(math.fsum((v-center)**2 for v in x)/len(x))
            if scale==0:dropped.append(term)
            else:columns.append(term);numeric[term]=(center,scale)
    assert columns==[r['term'] for r in pp['columns']] and dropped==[r['term'] for r in pp['dropped_columns']]
    for r in pp['columns']:close(r['center'],numeric[r['term']][0]);close(r['scale'],numeric[r['term']][1])
    assert all(r['reason_code']=='ZERO_VARIANCE' for r in pp['dropped_columns'])
    y=[r[model['spec']['outcome']] for r in training];avg=math.fsum(y)/len(y);close(model['training_outcome_mean'],avg)
    if model['spec']['family']=='gaussian':close(model['response_transform']['center'],avg);close(model['response_transform']['scale'],math.sqrt(math.fsum((v-avg)**2 for v in y)/len(y)))
    else:assert model['response_transform']=={'method':'identity','center':0,'scale':1}
def metric_expectations(rows,model,spec):
    y=[float(r['observed']) for r in rows];p=[float(r['prediction']) for r in rows];eta=[float(r['linear_predictor']) for r in rows];n=len(rows);out={}
    def add(name,num,den,ns,ds,root=False,reason=None,threshold=None,ranking=None):out[name]={'numerator':num,'denominator':den,'numerator_semantics':ns,'denominator_semantics':ds,'value':(math.sqrt(num/den) if root else num/den) if den else None,'reason_code':reason,'threshold':threshold,'ranking_score':ranking}
    if spec['family']=='gaussian':
        for prefix,values in [('',p),('training_mean_',[model['training_outcome_mean']]*n)]:
            add(prefix+'mae',math.fsum(abs(a-b) for a,b in zip(values,y)),n,'sum_absolute_error','evaluated_subjects')
            add(prefix+'rmse',math.fsum((a-b)**2 for a,b in zip(values,y)),n,'sum_squared_error','evaluated_subjects',root=True)
    else:
        case=[i for i,v in enumerate(y) if v==1];control=[i for i,v in enumerate(y) if v==0];concordant=sum((eta[i]>eta[j])+.5*(eta[i]==eta[j]) for i in case for j in control)
        add('auc',concordant,len(case)*len(control),'concordant_event_nonevent_pairs_plus_half_ties','event_nonevent_pairs',reason='NO_EVENTS' if not case else 'NO_NON_EVENTS' if not control else None,ranking='logit')
        add('brier',math.fsum((a-b)**2 for a,b in zip(p,y)),n,'sum_squared_probability_error','evaluated_subjects')
        add('log_loss',math.fsum(max(z,0)-v*z+math.log1p(math.exp(-abs(z))) for z,v in zip(eta,y)),n,'sum_binomial_log_loss','evaluated_subjects')
        threshold=spec['clinical_threshold']
        if threshold is not None:
            pos=[v>=threshold for v in p];tp=sum(pos[i] for i in case);tn=sum(not pos[i] for i in control);positive=sum(pos);negative=n-positive
            for name,num,den,ns,ds,reason in [('sensitivity',tp,len(case),'true_positives','actual_events','NO_EVENTS'),('specificity',tn,len(control),'true_negatives','actual_non_events','NO_NON_EVENTS'),('ppv',tp,positive,'true_positives','predicted_events','NO_PREDICTED_EVENTS'),('npv',tn,negative,'true_negatives','predicted_non_events','NO_PREDICTED_NON_EVENTS'),('accuracy',tp+tn,n,'correct_classifications','evaluated_subjects',None)]:add(name,num,den,ns,ds,reason=reason if not den else None,threshold=threshold)
    return out
def audit_record(out,result,task,counts,lock):
    rec=result['penalized_prediction'];subset(rec,load(out/'private/backend.json'));opt=task['analysis']['penalized_prediction'];spec=opt['spec'];train=opt['operation']=='train';infer=opt['operation']=='infer';complete=rec['status']=='completed'
    source=source_rows(task);source.sort(key=lambda r:r[spec['id']].encode('utf-8'));byid={r[spec['id']]:r for r in source};assert len(byid)==len(source)
    training=[r for r in source if r[spec['split']['partition_field']]=='train'];holdout=[r for r in source if r[spec['split']['partition_field']]=='holdout'];flow=rec['flow']
    assert flow['n_input']==len(source) and flow['n_training']==len(training) and flow['n_holdout']==(len(holdout) if train else 0)
    assert result['counts']['source_rows']==result['counts']['subjects']==len(source) and result['counts']['excluded_missing']==result['counts']['prediction_clipped_n']==0
    assert result['provider']['version']==lock['penalized_provider_version']
    private=table(out/'private/penalized-individual-predictions.csv');counts['private_prediction_rows']+=len(private)
    if complete:
        assert [r['subject_id'] for r in private]==[r[spec['id']] for r in source] and flow['n_predicted']==len(source)
        path=out/'private/penalized-model.json' if train else Path(opt['model_ref']['local_ref']);bundle=load(path);model=bundle['model'];assert sha(path)==result['binding']['model_hash']
        assert bundle['schema_version']=='clinical-frozen-penalized@0.8.0-candidate1' and bundle['provider_version']==lock['penalized_provider_version']
        expected_binding={'versions':lock['penalized_runtime'],'package_paths':lock['penalized_package_paths'],'dependency_hashes':lock['penalized_dependency_hashes'],'rscript_engine':lock['rscript_engine'],'rscript_sha256':lock['executable_hashes'][lock['rscript_engine']]}
        assert bundle['runtime_binding']==expected_binding,'frozen dependency binding mismatch'
        assert bundle['canonical_semantics']==model['semantics']==rec['semantics'];assert bundle['test_only'] is True and bundle['scientific_review']=='pending' and bundle['export_status']=='local_only'
        assert model['schema_version']=='clinical-penalized-model@0.8.0-candidate1' and model['method_id']==result['method_id']
        if train:
            assert model['training_subject_ids']==[r[spec['id']] for r in training]
            groups=sorted({r[spec['split']['group_field']] for r in training},key=lambda x:x.encode('utf-8')) if spec['split']['group_field'] else []
            assert model['training_group_ids']==groups;check_final_preprocessor(training,model)
            assert rec['diagnostics']['n_engine_fits']==spec['split']['cv_folds']+1 and rec['cv']['status']=='completed'
        else:
            assert not (out/'private/penalized-model.json').exists() and rec['diagnostics']['n_engine_fits']==0 and rec['cv']['reason_code']=='FROZEN_MODEL_NO_REFIT'
            assert not set(byid)&set(model['training_subject_ids'])
        for row in private:
            raw=byid[row['subject_id']];prediction,eta=formula(raw,model);counts['max_formula_difference']=max(counts['max_formula_difference'],close(row['prediction'],prediction),close(row['linear_predictor'],eta))
            equal(row['fold'],raw[spec['split']['fold_field']]);equal(row['partition'],raw[spec['split']['partition_field']]);equal(row['group_id'],raw[spec['split']['group_field']] if spec['split']['group_field'] else None)
            equal(row['observed'],None if infer else raw[spec['outcome']])
        evaluation=[r for r in private if r['partition']=='holdout'] if train else private
        assert flow['n_evaluated']==(0 if infer else len(evaluation))
        if infer:assert not rec['metrics'] and result['counts']['evaluation_n'] is None and flow['missing_outcome_n'] is None
        else:
            expected=metric_expectations(evaluation,model,spec);assert set(expected)=={r['metric'] for r in rec['metrics']}
            event=sum(float(r['observed'])==1 for r in evaluation) if spec['family']=='binomial' else None
            assert flow['n_evaluation_events']==event and flow['n_evaluation_non_events']==(len(evaluation)-event if event is not None else None)
            assert len(rec['metrics'])==len(result['metrics'])
            for row,mirror in zip(rec['metrics'],result['metrics']):
                subset(row,expected[row['metric']]);assert row['n']==len(evaluation) and row['events']==event and row['non_events']==flow['n_evaluation_non_events']
                equal(mirror['value'],row['value']);assert mirror['name']==row['metric'] and mirror['evaluation_n']==len(evaluation) and mirror['uncertainty'] is None
                assert mirror['evaluation_events']==row['events'] and mirror['evaluation_nonevents']==row['non_events']
                ratios={'sensitivity':'events','specificity':'nonevents','ppv':'predicted_positive','npv':'predicted_negative','accuracy':'evaluated_labels'}
                is_ratio=row['metric'] in ratios
                equal(mirror['numerator'],row['numerator'] if is_ratio else None);equal(mirror['denominator'],row['denominator'] if is_ratio else None)
                assert mirror['denominator_semantics']==(ratios[row['metric']] if is_ratio else 'not_a_count_ratio')
                assert mirror['reason_code']==('ZERO_RATIO_DENOMINATOR' if is_ratio and row['denominator']==0 else row['reason_code'])
                assert mirror['evaluation_set']==('internal_holdout' if train else 'synthetic_frozen_application')
                assert mirror['model_role']==('training_constant_comparator' if row['metric'].startswith('training_mean_') else 'frozen_penalized_model')
                assert mirror['unit']==('1' if rec['family']=='binomial' else rec['semantics']['outcome']['unit'])
                expected_scale='signed_original_outcome_units' if rec['family']=='gaussian' else 'squared_probability_error' if row['metric']=='brier' else 'mean_negative_natural_log_likelihood' if row['metric']=='log_loss' else 'dimensionless'
                assert mirror['scale']==expected_scale
                assert row['population']==('holdout' if train else 'external')
        for key in ('selected_lambda','selected_engine_lambda','selected_lambda_index'):assert rec[key]==model[key]
        assert model['selected_lambda']==spec['lambda_grid'][model['selected_lambda_index']-1]
        assert abs(model['selected_engine_lambda']-model['selected_lambda'])<=32*sys.float_info.epsilon*abs(model['selected_lambda'])
        assert rec['diagnostics']['warning_count']==0 and (rec['diagnostics']['jerr']==0 if train else rec['diagnostics']['jerr'] is None)
        assert len(rec['coefficients'])==len(model['coefficients'])+1
        for row,coefficient in zip(rec['coefficients'],[model['intercept']]+model['coefficients']):close(row['coefficient'],coefficient);assert row['nonzero']==(coefficient!=0) and row['source']==('training' if train else 'frozen_training')
        counts['completed_runs']+=1
    else:
        assert result['execution_status']=='blocked' and rec['reason_code'] and not private and not (out/'private/penalized-model.json').exists()
        assert not rec['metrics'] and not result['figures'] and result['binding']['model_hash'] is None;counts['numerical_refusals']+=1
    # Reconstruct missingness separately for each actual fit/validation scope.
    for row in rec['preprocessing']:
        if row['stage']=='cv':
            population=[r for r in training if (r[spec['split']['fold_field']]==row['fold'])==(row['role']=='validation')];fitting=[r for r in training if r[spec['split']['fold_field']]!=row['fold']]
        elif row['stage']=='final':population=training if row['role']=='fitting' else holdout;fitting=training
        else:assert row['stage']=='external' and row['role']=='external';population=source;fitting=None
        missing=sum(r[row['feature']] is None for r in population);assert row['n_rows']==len(population) and row['n_missing']==row['n_imputed']==missing
        assert isinstance(row['fitted_levels'],list),'fitted levels must remain an array'
        if row['type']=='number':assert row['fitted_levels']==[] and row['fitted_reference'] is None and row['encoding_rule']=='identity_numeric'
        else:
            if fitting is None:feature=next(f for f in model['preprocessor']['features'] if f['name']==row['feature']);levels=feature['levels'];reference=feature['reference']
            else:levels=sorted({r[row['feature']] for r in fitting if r[row['feature']] is not None},key=lambda v:v.encode('utf-8'));reference=levels[0]
            assert row['fitted_levels']==levels and row['fitted_reference']==reference and row['encoding_rule']=='treatment_utf8_observed_reference_first'
        counts['fitted_preprocessing_rows']+=1
    if complete and train:
        cv=rec['cv'];assert cv['scope']=='training_only_tuning' and cv['weighting']=='validation_subject_count'
        assert [r['lambda'] for r in cv['rows']]==spec['lambda_grid']
        assert rec['selected_lambda_index']==min(range(len(cv['rows'])),key=lambda i:cv['rows'][i]['mean_loss'])+1
        for row in cv['rows']:
            related=[r for r in cv['fold_losses'] if r['lambda_index']==row['lambda_index']];assert len(related)==spec['split']['cv_folds']
            assert sum(r['n_validation'] for r in related)==row['n_validation']==len(training);close(row['loss_sum'],math.fsum(r['loss_sum'] for r in related));close(row['mean_loss'],row['loss_sum']/len(training))
            for r in related:assert abs(r['engine_lambda']-r['lambda'])<=32*sys.float_info.epsilon*abs(r['lambda']);close(r['mean_loss'],r['loss_sum']/r['n_validation'])
        for row in cv['folds']:
            fitting=[r for r in training if r[spec['split']['fold_field']]!=row['fold']];assert row['n_training']==len(fitting) and row['n_validation']==len(training)-len(fitting)
            if spec['family']=='binomial':assert row['training_events']==sum(r[spec['outcome']]==1 for r in fitting) and row['training_non_events']==sum(r[spec['outcome']]==0 for r in fitting)
            else:assert row['training_events'] is None and row['training_non_events'] is None
        assert len(rec['path'])==len(spec['lambda_grid'])*len(rec['coefficients'])
        selected=[r for r in rec['path'] if r['lambda_index']==rec['selected_lambda_index']]
        for a,b in zip(selected,rec['coefficients']):subset(a,{k:b[k] for k in ('term','feature','type','level','coefficient','nonzero')})
    # Every public CSV is a field-preserving aggregate projection, with exact IDs.
    flowrows=[{'result_id':rec['result_id'],'count_name':k,'value':v,'count_semantics':'not_applicable_continuous_outcome' if 'events' in k and rec['family']=='gaussian' else 'not_read_in_infer' if k=='missing_outcome_n' and infer else 'explicit_subject_or_design_count'} for k,v in flow.items()]
    datasets={'penalized_flow':flowrows,'penalized_imputation':rec['preprocessing'],'penalized_cv':rec['cv']['rows'],'penalized_cv_folds':rec['cv']['folds'],'penalized_cv_fold_losses':rec['cv']['fold_losses'],'penalized_coefficient_path':rec['path'],'penalized_coefficients':rec['coefficients'],'penalized_metrics':rec['metrics']}
    if rec['coefficients']:datasets['penalized_nonzero']=[r for r in rec['coefficients'] if r['nonzero'] and r['type']!='intercept']
    expected_artifacts={};ids={rec['result_id']}
    for name,rows in datasets.items():
        path=out/'tables'/(name+'.csv')
        if not rows and name!='penalized_nonzero':assert not path.exists();continue
        exported=table(path);assert len(exported)==len(rows)
        for actual,expected in zip(exported,rows):
            for key,value in expected.items():equal(actual[key],value)
            for key,value in {'method_id':result['method_id'],'method_version':result['method_version'],'provider_version':result['provider']['version'],'core_version':result['core_version'],'run_id':result['run_id'],'operation':rec['operation'],'family':rec['family'],'penalty':rec['penalty'],'alpha':rec['alpha'],'coefficient_scale':rec['coefficient_scale'],'prediction_scale':rec['prediction_scale'],'outcome_unit':rec['semantics']['outcome']['unit'],'scientific_review':'pending','export_status':'local_only','test_only':True}.items():equal(actual[key],value)
        source_ids={r['result_id'] for r in rows} or {rec['result_id']};ids|=source_ids;expected_artifacts[name]=(path,source_ids);counts['public_csv_rows']+=len(exported)
    if complete and train:
        expected_artifacts['penalized_cv']=(out/'tables/penalized_cv.csv',{r['result_id'] for r in rec['cv']['rows']})
        for name,rows in [('penalized_cv',rec['cv']['rows']),('penalized_coefficient_path',rec['path'])]:
            artifacts=[a for a in result['figures'] if a['artifact_id']==name];assert len(artifacts)==1;artifact=artifacts[0];path=out/'figures'/(name+'.png')
            assert sha(path)==artifact['data_hash'] and set(artifact['source_result_ids'])=={r['result_id'] for r in rows} and artifact['denominator']==len(training);counts['artifact_hashes']+=1
    else:assert not result['figures']
    assert {r['artifact_id'] for r in result['tables']}==set(expected_artifacts)
    for artifact in result['tables']:
        path,source_ids=expected_artifacts[artifact['artifact_id']];assert sha(path)==artifact['data_hash'] and set(artifact['source_result_ids'])==source_ids and artifact['caption']
        assert artifact['ci'] is None and artifact['test_only'] is True;counts['artifact_hashes']+=1
    generic_ids={r['result_id'] for r in result['metrics']};assert len(generic_ids)==len(result['metrics']) and not generic_ids&ids
    counts['record_runs']+=1;return ids|generic_ids
def audit(suite):
    receipt=load(suite/'acceptance-receipt.json');assert receipt['summary']['failed']==0,'acceptance has failed checks'
    assert receipt['runtime_lock_sha256']==sha(ROOT/'runtime-lock.json') and all(sha(ROOT/p)==v for p,v in receipt['source_sha256'].items())
    lock=load(ROOT/'runtime-lock.json');counts={k:0 for k in ('runs','record_runs','completed_runs','numerical_refusals','contract_refusals','public_files_scanned','private_prediction_rows','public_csv_rows','artifact_hashes','writing_reference_checks','fitted_preprocessing_rows')};counts['max_formula_difference']=0.
    for item in receipt['runs']:
        out=Path(item['output_dir']).resolve();assert out.is_relative_to(suite);result=load(out/'result.json');task=load(item['task_path']);assert result['binding']['input_hash']==sha(item['task_path'])
        privacy(out,result,counts);ids=set()
        if result['penalized_prediction'] is not None:ids=audit_record(out,result,task,counts,lock)
        else:assert result['execution_status']=='blocked' and not result['tables'] and not result['figures'];counts['contract_refusals']+=1
        assert set(load(out/'writing-references.json')['result_ids'])==ids;counts['writing_reference_checks']+=1;counts['runs']+=1
    assert counts['completed_runs']>=28 and counts['contract_refusals']>=20 and counts['numerical_refusals']>=8,'required coverage absent'
    return {'status':'PASS',**counts,'runtime_lock_sha256':receipt['runtime_lock_sha256'],'acceptance_receipt_sha256':sha(suite/'acceptance-receipt.json'),'tolerance':{'absolute':ATOL,'relative':RTOL},'scope':'Local source/preprocessing/frozen formula, public aggregates and actual denominators, no-refit provenance, artifact hashes and privacy; synthetic only, not clinical validation'}
def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT);target=suite/'export-audit.json';assert not target.exists(),'audit receipt exists'
    try:result=audit(suite)
    except Exception as exc:result={'status':'FAIL','reason':type(exc).__name__+': '+str(exc)}
    result['audit_script_sha256']=sha(__file__);target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(result),flush=True);return int(result['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
