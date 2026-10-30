"""Read-only public/private, aggregate denominator, formula and provenance audit."""
from __future__ import annotations
import csv,hashlib,json,math,sys,traceback
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
ATOL=RTOL=1e-10
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def table(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as h:
        r=csv.DictReader(h);assert len(r.fieldnames)==len(set(r.fieldnames)),'duplicate CSV column';return list(r)
def close(a,b):
    assert a is not None and b is not None,'null scalar';a=float(a);b=float(b);assert math.isfinite(a) and math.isfinite(b),'nonfinite scalar';d=abs(a-b);assert d<=ATOL+RTOL*abs(b),'numeric discrepancy exceeds fixed atol+rtol 1e-10';return d
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
    view=task['views'][0];path=Path(view['local_ref']).resolve();assert path.is_relative_to(ROOT) and sha(path)==view['content_hash'];rows=[]
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
        text=p.read_text(encoding='utf-8-sig',errors='replace');assert 'SYNTHETIC-V09-' not in text,'individual identifier leaked'
        for key in ('training_subject_ids','training_group_ids','fitted_subject_ids','encoded_means','subject_ids_sha256','preprocessor','response_transform'):assert '"'+key+'"' not in text,'private frozen field exposed'
        counts['public_files_scanned']+=1
    for key in ('survival','cox_prediction','survival_evaluation','psm'):assert result[key] is None
def result_ids(value):
    found=set()
    if isinstance(value,dict):
        if 'result_id' in value:found.add(value['result_id'])
        for v in value.values():found|=result_ids(v)
    elif isinstance(value,list):
        for v in value:found|=result_ids(v)
    return found
def encode(row,model):
    fmap={f['name']:f for f in model['preprocessor']['features']};values=[]
    for col in model['preprocessor']['columns']:
        f=fmap[col['feature']];v=row[f['name']];v=f['impute'] if v is None else v
        if f['type']=='category':assert v in f['levels'];v=float(v==col['level'])
        values.append((v-col['center'])/col['scale'])
    return values
def link(x,family):return x if family=='gaussian' else 1/(1+math.exp(-x)) if x>=0 else math.exp(x)/(1+math.exp(x))
def parameters(model):
    t=model['response_transform'];scale=t['scale'] if model['spec']['family']=='gaussian' else 1;center=t['center'] if model['spec']['family']=='gaussian' else 0
    return center+scale*model['intercept'],[scale*b for b in model['coefficients']]
def projections(out,result,rec,datasets,counts,interpret):
    ids=result_ids(rec)|result_ids(result['metrics']);expected={}
    for name,rows in datasets.items():
        p=out/'tables'/(name+'.csv')
        if not rows and name!='penalized_nonzero':assert not p.exists(),'unexpected empty public table';continue
        actual=table(p);assert len(actual)==len(rows),'public row count mismatch'
        for a,b in zip(actual,rows):
            for k,v in b.items():equal(a[k],v)
            meta={'method_id':result['method_id'],'method_version':result['method_version'],'provider_version':result['provider']['version'],'core_version':result['core_version'],'run_id':result['run_id'],'test_only':True,'scientific_review':'pending','export_status':'local_only'}
            if interpret:meta.update(model_method_id=rec['model_method_id'],family=rec['family'],score_scale=rec['definition']['score_scale'],score_unit=result['provenance']['target_policy']['score_unit'],coalition_unit='raw_feature',background_definition='full_frozen_training_empirical',n_background=rec['flow']['n_background'],n_application=rec['flow']['n_application'],model_sha256=rec['model_sha256'],explainer_sha256=rec['explainer_sha256'])
            for k,v in meta.items():equal(a[k],v)
        expected[name]={r['result_id'] for r in rows} or {rec['result_id']};counts['public_csv_rows']+=len(actual)
    assert {a['artifact_id'] for a in result['tables']}==set(expected)
    for artifact in result['tables']+result['figures']:
        figure=artifact['kind']=='figure';p=out/('figures' if figure else 'tables')/(artifact['artifact_id']+('.png' if figure else '.csv'))
        assert sha(p)==artifact['data_hash'] and set(artifact['source_result_ids'])<=ids and artifact['caption'];assert artifact['ci'] is None and artifact['test_only'] is True
        if not figure:assert set(artifact['source_result_ids'])==expected[artifact['artifact_id']]
        if interpret and artifact['artifact_id']=='interpretation_global_importance':assert artifact['denominator']==rec['flow']['n_application']
        counts['artifact_hashes']+=1
    writing=load(out/'writing-references.json');assert set(writing['result_ids'])==ids,'writing result references mismatch';assert set(writing['artifact_ids'])=={a['artifact_id'] for a in result['tables']+result['figures']};assert writing['writing_eligible'] is False;counts['writing_reference_checks']+=1

def audit_training(out,result,task,counts,runtime):
    rec=result['penalized_prediction'];assert rec['status']=='completed' and rec['operation']=='train';subset(rec,load(out/'private/backend.json'));assert result['interpretation'] is None
    rows=source_rows(task);spec=task['analysis']['penalized_prediction']['spec'];training=sorted([r for r in rows if r['partition']=='train'],key=lambda r:r[spec['id']].encode('utf-8'))
    path=out/'private/penalized-model.json';wrapper=load(path);model=wrapper['model'];bundle=load(out/'private/linear-explainer.json')
    assert result['binding']['model_hash']==sha(path)==bundle['model_sha256'];assert wrapper['provider_version']==runtime['penalized_provider_version'];assert bundle['provider_version']==runtime['interpretation_provider_version']
    expected_runtime={'versions':runtime['penalized_runtime'],'package_paths':runtime['penalized_package_paths'],'dependency_hashes':runtime['penalized_dependency_hashes'],'rscript_engine':runtime['rscript_engine'],'rscript_sha256':runtime['executable_hashes'][runtime['rscript_engine']]};assert wrapper['runtime_binding']==expected_runtime
    assert wrapper['canonical_semantics']==model['semantics']==rec['semantics'];features=[f['name'] for f in model['spec']['features']];bg=[{k:r[k] for k in [spec['id']]+features} for r in training]
    assert bg==bundle['background']['rows'] and len(bg)==bundle['background']['n']==108;assert model['training_subject_ids']==[r[spec['id']] for r in training]
    matrix=[encode(r,model) for r in bg];means=[math.fsum(r[k] for r in matrix)/len(matrix) for k in range(len(model['coefficients']))];a,gamma=parameters(model)
    for observed,expected in zip(bundle['background']['encoded_means'],means):counts['max_formula_difference']=max(counts['max_formula_difference'],close(observed['mean'],expected))
    close(bundle['score']['base_value'],a+math.fsum(b*m for b,m in zip(gamma,means)))
    assert rec['flow']['n_training']==len(training) and rec['flow']['n_input']==len(rows) and rec['diagnostics']['n_engine_fits']==4
    assert len(rec['metrics'])==len(result['metrics'])
    for dedicated,generic in zip(rec['metrics'],result['metrics']):assert dedicated['metric']==generic['name'];equal(dedicated['value'],generic['value']);assert dedicated['n']==generic['evaluation_n']==36
    flowrows=[{'result_id':rec['result_id'],'count_name':k,'value':v,'count_semantics':'not_applicable_continuous_outcome' if 'events' in k and rec['family']=='gaussian' else 'explicit_subject_or_design_count'} for k,v in rec['flow'].items()]
    datasets={'penalized_flow':flowrows,'penalized_imputation':rec['preprocessing'],'penalized_cv':rec['cv']['rows'],'penalized_cv_folds':rec['cv']['folds'],'penalized_cv_fold_losses':rec['cv']['fold_losses'],'penalized_coefficient_path':rec['path'],'penalized_coefficients':rec['coefficients'],'penalized_metrics':rec['metrics'],'penalized_nonzero':[r for r in rec['coefficients'] if r['nonzero'] and r['type']!='intercept']}
    projections(out,result,rec,datasets,counts,False);counts['training_runs']+=1;counts['background_rows_checked']+=len(bg)

def audit_interpretation(out,result,task,counts,runtime):
    rec=result['interpretation'];subset(rec,load(out/'private/backend.json'));assert result['penalized_prediction'] is None and not result['metrics'] and not result['estimates'] and not result['tests']
    options=task['analysis']['interpretation'];modelpath=Path(options['model_ref']['local_ref']);bundlepath=Path(options['explainer_ref']['local_ref']);wrapper=load(modelpath);model=wrapper['model'];bundle=load(bundlepath)
    assert sha(modelpath)==options['model_ref']['content_hash']==rec['model_sha256'] and sha(bundlepath)==options['explainer_ref']['content_hash']==rec['explainer_sha256']
    assert rec['provider_version']==runtime['interpretation_provider_version'] and rec['diagnostics']['refit'] is False and rec['diagnostics']['outcomes_used'] is False and rec['diagnostics']['background_sampling'] is False
    assert rec['definition']['coalition_unit']=='raw_feature' and rec['definition']['conditional'] is False and rec['definition']['probability_scale'] is False and rec['definition']['causal'] is False
    assert rec['definition']['score_unit']==(model['semantics']['outcome']['unit'] if model['spec']['family']=='gaussian' else '1')
    for key in ('model_n','evaluation_n','evaluation_events','evaluation_nonevents','missing_outcome_n'):assert result['counts'][key] is None
    assert not (out/'private/penalized-model.json').exists() and not (out/'private/linear-explainer.json').exists()
    private=table(out/'private/interpretation-individual-contributions.csv');encoded=table(out/'private/interpretation-encoded-contributions.csv');points=table(out/'private/interpretation-individual-points.csv')
    if rec['status']=='completed':
        source=source_rows(task);source.sort(key=lambda r:r[model['spec']['id']].encode('utf-8'));byid={r[model['spec']['id']]:r for r in source};n=len(source);bg=bundle['background']['rows'];assert rec['flow']['n_background']==len(bg)==108 and rec['flow']['n_application']==n
        assert result['counts']['prediction_n']==n and rec['background_sha256']==bundle['background']['rows_sha256'] and rec['transform_sha256']==bundle['transform_sha256']
        assert not set(byid)&set(model['training_subject_ids']);features=[f['name'] for f in model['spec']['features']];cols=model['preprocessor']['columns'];a,gamma=parameters(model);matrix=[encode(r,model) for r in bg];means=[math.fsum(row[k] for row in matrix)/len(bg) for k in range(len(cols))]
        base=a+math.fsum(b*m for b,m in zip(gamma,means));close(rec['shap']['base_value'],base)
        index={(r['subject_id'],r['feature']):r for r in private};encoded_index={(r['subject_id'],r['term']):r for r in encoded};point_index={(r['subject_id'],r['feature']):r for r in points};assert len(private)==len(index)==n*len(features) and len(encoded)==len(encoded_index)==n*len(cols) and len(points)==len(point_index)==n*len(features)
        grouped={f:[] for f in features}
        for sid,row in byid.items():
            z=encode(row,model);score=a+math.fsum(b*x for b,x in zip(gamma,z));pred=link(score,model['spec']['family']);allphi=[];allpoints=[]
            for f in features:
                positions=[k for k,col in enumerate(cols) if col['feature']==f];phi=math.fsum(gamma[k]*(z[k]-means[k]) for k in positions);component=math.fsum(gamma[k]*z[k] for k in positions);allphi.append(phi);grouped[f].append(phi);observed=index[sid,f]
                for key,value in [('phi',phi),('base_value',base),('score',score),('prediction',pred)]:counts['max_formula_difference']=max(counts['max_formula_difference'],close(observed[key],value))
                domain=next(d for d in rec['nomogram']['domains'] if d['feature']==f);q=0 if rec['nomogram']['constant_model'] else 100*(component-domain['score_min'])/rec['nomogram']['points_denominator'];allpoints.append(q);p=point_index[sid,f];close(p['points'],q);close(p['score_contribution'],component)
                for k in positions:
                    e=encoded_index[sid,cols[k]['term']];equal(e['feature'],f)
                    for key,value in [('encoded_value',z[k]),('background_mean',means[k]),('coefficient',gamma[k]),('phi',gamma[k]*(z[k]-means[k]))]:close(e[key],value)
            close(base+math.fsum(allphi),score);total=math.fsum(allpoints);back=rec['nomogram']['score_at_zero']+(rec['nomogram']['score_per_point'] or 0)*total
            for f in features:
                p=point_index[sid,f];close(p['total_points'],total);close(p['reconstructed_score'],back);close(p['reconstructed_prediction'],link(back,model['spec']['family']))
            counts['max_nomogram_backcheck_difference']=max(counts['max_nomogram_backcheck_difference'],close(back,score))
        for row in rec['shap']['global_importance']:
            values=grouped[row['feature']];assert row['n']==n;close(row['sum_abs_shap'],math.fsum(abs(x) for x in values));close(row['mean_abs_shap'],math.fsum(abs(x) for x in values)/n);close(row['mean_shap'],math.fsum(values)/n);close(row['min_shap'],min(values));close(row['max_shap'],max(values))
        for f,observed in rec['flow']['missing_by_feature'].items():assert observed=={'n_background_missing':sum(r[f] is None for r in bg),'n_application_missing':sum(r[f] is None for r in source)}
        for domain,fm in zip(rec['nomogram']['domains'],model['preprocessor']['features']):
            assert domain['feature']==fm['name'] and domain['fitted_levels']==fm['levels'] and domain['fitted_reference']==fm['reference'];equal(domain['impute_value'],fm['impute'])
            if fm['type']=='number':present=[r[fm['name']] for r in bg if r[fm['name']] is not None];close(domain['observed_min'],min(present));close(domain['observed_max'],max(present))
        if rec['nomogram']['constant_model']:assert rec['nomogram']['score_per_point'] is None and rec['nomogram']['points_denominator']==rec['nomogram']['max_total_points']==0 and len(rec['nomogram']['total_axis'])==1
        assert rec['shap']['additivity']['passed'] and rec['nomogram']['backcheck']['passed'] and len(result['figures'])==2;counts['completed_interpretations']+=1
    else:
        assert result['execution_status']=='blocked' and rec['reason_code'] and not private and not encoded and not points and not result['figures'];counts['numerical_refusals']+=1
    flowrows=[{'result_id':rec['result_id'],'count_name':k,'value':v,'count_semantics':'synthetic_subject_or_frozen_design_count'} for k,v in rec['flow'].items() if k!='missing_by_feature']
    missingrows=[{'result_id':rec['result_id'],'feature':k,**v} for k,v in rec['flow']['missing_by_feature'].items()]
    datasets={'interpretation_flow':flowrows,'interpretation_missingness':missingrows,'interpretation_global_importance':rec['shap']['global_importance'],'nomogram_domains':rec['nomogram']['domains'],'nomogram_axes':rec['nomogram']['axes'],'nomogram_mapping':rec['nomogram']['total_axis']}
    projections(out,result,rec,datasets,counts,True);counts['private_grouped_rows']+=len(private);counts['private_encoded_rows']+=len(encoded);counts['private_point_rows']+=len(points)

def audit(suite):
    receipt=load(suite/'acceptance-receipt.json');assert receipt['status']=='PASS' and receipt['summary']['failed']==0;assert sha(ROOT/'runtime-lock.json')==receipt['runtime_lock_sha256'];assert all(sha(ROOT/p)==v for p,v in receipt['source_sha256'].items())
    runtime=load(ROOT/'runtime-lock.json');counts={k:0 for k in ('runs','training_runs','completed_interpretations','numerical_refusals','contract_refusals','public_files_scanned','public_csv_rows','background_rows_checked','private_grouped_rows','private_encoded_rows','private_point_rows','artifact_hashes','writing_reference_checks')};counts.update(max_formula_difference=0.,max_nomogram_backcheck_difference=0.)
    for item in receipt['runs']:
        out=Path(item['output_dir']).resolve();assert out.is_relative_to(suite);result=load(out/'result.json');task=load(item['task_path']);assert result['binding']['input_hash']==sha(item['task_path']);privacy(out,result,counts)
        if result['interpretation'] is not None:audit_interpretation(out,result,task,counts,runtime)
        elif result['penalized_prediction'] is not None:audit_training(out,result,task,counts,runtime)
        else:
            assert result['execution_status']=='blocked' and not result['tables'] and not result['figures'];assert not load(out/'writing-references.json')['result_ids'];counts['contract_refusals']+=1;counts['writing_reference_checks']+=1
        counts['runs']+=1
    assert counts['training_runs']>=13 and counts['completed_interpretations']>=16 and counts['numerical_refusals']>=12 and counts['contract_refusals']>=12,'planned coverage absent'
    return {'status':'PASS',**counts,'runtime_lock_sha256':receipt['runtime_lock_sha256'],'acceptance_receipt_sha256':sha(suite/'acceptance-receipt.json'),'tolerance':{'absolute':ATOL,'relative':RTOL},'scope':'Local frozen formula and grouped attribution/points consistency, aggregate denominators and CSV arrays, artifact hashes/references, full training background and privacy. Synthetic engineering only.'}
def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT);target=suite/'export-audit.json';assert not target.exists(),'audit receipt exists'
    try:result=audit(suite)
    except Exception as exc:
        result={'status':'FAIL','reason':type(exc).__name__+': '+str(exc)};(suite/'export-audit-trace.txt').write_text(traceback.format_exc(),encoding='utf-8')
    result['audit_script_sha256']=sha(__file__);target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');print(json.dumps(result),flush=True);return int(result['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
