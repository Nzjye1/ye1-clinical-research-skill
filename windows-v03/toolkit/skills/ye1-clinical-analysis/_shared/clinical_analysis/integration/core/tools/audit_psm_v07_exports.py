"""Read-only local source/private/public audit for the v07 PSM acceptance suite."""
from __future__ import annotations
import csv, hashlib, json, math, statistics, sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
ATOL=RTOL=1e-10

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def table(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as handle:return list(csv.DictReader(handle))
def close(a,b):
    assert a is not None and b is not None,'null scalar'
    assert math.isfinite(float(a)) and math.isfinite(float(b)),'nonfinite scalar'
    assert abs(float(a)-float(b))<=ATOL+RTOL*abs(float(b)),'scalar differs beyond fixed atol+rtol 1e-10'
def equal(a,b):
    if b is None:assert a in ('','NA',None),'null projection lost'
    elif isinstance(b,bool):assert str(a).lower()==str(b).lower(),'boolean differs'
    elif type(b) in (int,float):close(a,b)
    elif isinstance(b,(list,dict)):subset(loads(a) if isinstance(a,str) else a,b)
    else:assert a==b,'text semantics differ'
def loads(text):return json.loads(text)
def subset(a,b):
    if isinstance(b,dict):
        assert isinstance(a,dict),'object required'
        for key,value in b.items():assert key in a,'missing '+key;subset(a[key],value)
    elif isinstance(b,list):
        assert isinstance(a,list) and len(a)==len(b),'array length'
        for x,y in zip(a,b):subset(x,y)
    else:equal(a,b)
def source_rows(task):
    view=task['views'][0];path=Path(view['local_ref']).resolve();assert path.is_relative_to(ROOT)
    assert sha(path)==view['content_hash'];rows=[]
    for source in table(path):
        row={}
        for variable in task['variables']:
            name=variable['name'];value=source[view['column_map'][name]]
            if value in variable['missing_codes']:row[name]=None
            elif variable['dtype']=='number':row[name]=float(value)*variable['conversion']['scale']+variable['conversion']['offset']
            elif variable['dtype']=='category':row[name]=variable['codes'][value]
            else:row[name]=value
        rows.append(row)
    return rows
def privacy(out,result,counts):
    for path in out.rglob('*'):
        if not path.is_file() or 'private' in path.relative_to(out).parts or path.suffix.lower() not in ('.json','.csv','.html','.md','.txt'):continue
        text=path.read_text(encoding='utf-8-sig',errors='replace')
        assert 'SYNTHETIC-V07-' not in text,'private individual identity escaped'
        assert all('"'+key+'"' not in text for key in ('treated_subject_id','control_subject_id','fitted_subject_ids','coefficients','propensity_score','treated_outcome','control_outcome')),'private fields escaped'
        counts['public_files_scanned']+=1
    assert result['test_only'] is True and result['scientific_review']=='pending' and result['export_status']=='local_only'
    assert result['counts'].get('events') is None and result['counts'].get('non_events') is None
    assert not result['metrics'] and not result['estimates'] and result['survival'] is None and result['cox_prediction'] is None and result['survival_evaluation'] is None
def truth(value):return str(value).upper()=='TRUE'
def mean(values):return math.fsum(values)/len(values) if values else None
def variance(values):
    if len(values)<2:return None
    avg=mean(values);return math.fsum((x-avg)**2 for x in values)/(len(values)-1)

def audit_record(out,result,task,counts):
    rec=result['psm'];raw=load(out/'private/backend.json');subset(rec,raw)
    opt=task['analysis']['psm'];assert rec['options']==opt
    semantics=rec['semantics'];variables={v['name']:v for v in task['variables']};idcol=task['identity']['subject_key'];tcol=opt['treatment'];ycol=opt['outcome']
    assert semantics['subject_id']==idcol and semantics['treatment_definition']==variables[tcol]['concept']
    assert semantics['outcome_definition']==task['outcome']['definition'] and semantics['outcome_unit']==variables[ycol]['unit']
    assert semantics['index_time']==task['time']['index'] and semantics['time_unit']==task['time']['unit']
    assert semantics['target_population']==task['cohort']['target_population']
    assert semantics['event_count_semantics']=='not_applicable_continuous_outcome' and semantics['outcome_type']=='continuous' and semantics['causal_assumptions_verified'] is False
    assert rec['propensity']['formal_separation_checked'] is False and rec['propensity']['separation_detection']=='numerical_guards_only'
    assert result['provider']['version']==sha(ROOT/'src/clinanalysis/R/psm_v07.R')
    rows=source_rows(task);byid={row[idcol]:row for row in rows};assert len(rows)==len(byid)
    ordered=sorted(rows,key=lambda r:r[idcol].encode('utf-8'));complete=[r for r in ordered if all(r[k] is not None for k in opt['covariates'])]
    excluded=[r for r in ordered if any(r[k] is None for k in opt['covariates'])]
    flow=rec['flow'];n=len(rows);cc=len(complete);m=flow['n_matched_pairs']
    assert flow['n_input']==n and flow['n_input_treated']==sum(r[tcol]==1 for r in rows) and flow['n_input_control']==sum(r[tcol]==0 for r in rows)
    assert flow['n_complete_case']==cc and flow['n_excluded_missing_covariates']==len(excluded)
    for label,arm in [('treated',1),('control',0)]:
        assert flow['n_complete_case_'+label]==sum(r[tcol]==arm for r in complete)
        assert flow['n_excluded_missing_'+label]==sum(r[tcol]==arm for r in excluded)
    for name in opt['covariates']:
        entry=flow['missing_by_field'][name];assert entry['n_missing']==sum(r[name] is None for r in rows)
        assert entry['n_missing_treated']==sum(r[name] is None and r[tcol]==1 for r in rows)
        assert entry['n_missing_control']==sum(r[name] is None and r[tcol]==0 for r in rows)
    expected_counts={'source_rows':n,'subjects':n,'eligible':cc,'model_n':2*m,'excluded_missing':len(excluded),'events':None,'non_events':None}
    subset(result['counts'],expected_counts)
    subjects=table(out/'private/psm_subjects.csv');pairs=table(out/'private/psm_pairs.csv');model=load(out/'private/psm_model.json')
    assert [r['subject_id'] for r in subjects]==[r[idcol] for r in ordered]
    subjects_byid={r['subject_id']:r for r in subjects};complete_ids={r[idcol] for r in complete}
    for row in subjects:
        source=byid[row['subject_id']];equal(row['treatment'],source[tcol]);equal(row['outcome'],source[ycol])
        assert truth(row['complete_case'])==(row['subject_id'] in complete_ids)
        if not truth(row['complete_case']):
            assert row['propensity_score']==row['logit_ps']=='' and not truth(row['matched']) and not truth(row['support_retained'])
    assert len(pairs)==m and flow['n_matched_subjects']==2*m
    assert [r['pair_id'] for r in pairs]==[f'P{i+1:06d}' for i in range(m)]
    treated_ids=[r['treated_subject_id'] for r in pairs];control_ids=[r['control_subject_id'] for r in pairs]
    assert len(set(treated_ids))==len(set(control_ids))==m and not set(treated_ids).intersection(control_ids)
    differences=[]
    for pair in pairs:
        ti=pair['treated_subject_id'];ci=pair['control_subject_id'];tr=subjects_byid[ti];co=subjects_byid[ci]
        assert byid[ti][tcol]==1 and byid[ci][tcol]==0 and truth(tr['matched']) and truth(co['matched'])
        assert tr['pair_id']==co['pair_id']==pair['pair_id'] and tr['match_role']=='treated' and co['match_role']=='control'
        assert truth(tr['support_retained']) and truth(co['support_retained'])
        for prefix,subject in [('treated',tr),('control',co)]:
            equal(pair[prefix+'_ps'],float(subject['propensity_score']));equal(pair[prefix+'_logit'],float(subject['logit_ps']));equal(pair[prefix+'_outcome'],float(subject['outcome']))
        distance=abs(float(tr['logit_ps'])-float(co['logit_ps']));close(pair['logit_distance'],distance)
        assert distance<=rec['support']['caliper_width']+ATOL,'pair outside declared caliper'
        actual_difference=byid[ti][ycol]-byid[ci][ycol];close(pair['difference'],actual_difference)
        # The private pair values must retain sufficient digits to reconstruct
        # their stored difference even when the endpoint has a large baseline.
        close(float(pair['treated_outcome'])-float(pair['control_outcome']),actual_difference)
        differences.append(actual_difference)
    assert {r['subject_id'] for r in subjects if truth(r['matched'])}==set(treated_ids+control_ids)
    e=rec['effect'];assert e['n_pairs']==m and e['conditioning']=='formed_matched_pairs' and e['ps_estimation_uncertainty_included'] is False
    assert e['estimand']=='ATT_retained_matched_treated' and e['direction']=='treated_minus_control'
    if m:
        close(e['estimate'],mean(differences));close(e['treated_mean'],mean([byid[i][ycol] for i in treated_ids]));close(e['control_mean'],mean([byid[i][ycol] for i in control_ids]))
        assert e['df']==m-1
        if m>=2:
            v=variance(differences);close(e['paired_difference_variance'],v);close(e['standard_error'],math.sqrt(v/m))
            if v>0:
                assert e['inference_status']=='completed';close(e['t_statistic'],e['estimate']/e['standard_error'])
                assert e['ci_lower']<=e['estimate']<=e['ci_upper'] and 0<=e['p_value']<=1
            else:assert e['inference_reason_code']=='ZERO_PAIRED_VARIANCE'
        else:assert e['inference_reason_code']=='INSUFFICIENT_MATCHED_PAIRS' and e['standard_error'] is None
    else:assert e['estimate'] is None
    if e['inference_status']!='completed':assert all(e[k] is None for k in ('ci_lower','ci_upper','p_value','t_statistic')) and e['inference_reason_code']
    # Arm variance/covariance decomposition is diagnostic; large-baseline
    # cancellation must not replace the directly reconstructed pair variance.
    if rec['propensity']['status']=='completed':
        assert model['fitted_subject_ids']==[r[idcol] for r in complete]
        assert model['converged'] is True and model['boundary'] is False and model['warning_messages']==[]
        assert model['fit_scope']=='complete_case_pre_support' and model['rank']==len(model['coefficients'])
        fit=[subjects_byid[r[idcol]] for r in complete];support=rec['support']
        scores=[float(r['logit_ps']) for r in fit];ps=[float(r['propensity_score']) for r in fit]
        assert all(1e-6<p<1-1e-6 for p in ps)
        for p,lp in zip(ps,scores):close(p,1/(1+math.exp(-lp)))
        tr=[float(r['logit_ps']) for r in fit if float(r['treatment'])==1];co=[float(r['logit_ps']) for r in fit if float(r['treatment'])==0]
        lo=max(min(tr),min(co));hi=min(max(tr),max(co));close(support['lower'],lo);close(support['upper'],hi)
        retained=[r for r in fit if lo<=float(r['logit_ps'])<=hi]
        assert len(retained)==flow['n_support_retained']
        for label,arm in [('treated',1),('control',0)]:
            nr=sum(float(r['treatment'])==arm for r in retained)
            assert flow['n_support_'+label]==nr and flow['n_discarded_support_'+label]==flow['n_complete_case_'+label]-nr and flow['n_unmatched_support_'+label]==nr-m
        if support['logit_sd'] is not None:
            close(support['logit_sd'],math.sqrt(variance([float(r['logit_ps']) for r in retained])));close(support['caliper_width'],opt['caliper']['width']*support['logit_sd'])
    else:
        assert rec['support']['lower'] is None and rec['support']['upper'] is None and m==0
        assert all(r['propensity_score']==r['logit_ps']=='' for r in subjects)
    # Reconstruct every balance row from source values and actual matched IDs.
    for row in rec['balance']:
        name=row['covariate'];indicator=row['kind']=='indicator';level=row['level']
        value=lambda r:float(r[name]==level) if indicator else r[name]
        before_t=[value(r) for r in complete if r[tcol]==1];before_c=[value(r) for r in complete if r[tcol]==0]
        after_t=[value(byid[i]) for i in treated_ids];after_c=[value(byid[i]) for i in control_ids]
        assert row['n_before_treated']==len(before_t) and row['n_before_control']==len(before_c) and row['n_after_treated']==row['n_after_control']==m
        assert row['denominator_scope']=='pre_support_complete_case_treated'
        assert row['sd_kind']==('bernoulli_p1mp' if indicator else 'sample_n_minus_1')
        sd=math.sqrt(mean(before_t)*(1-mean(before_t))) if indicator and before_t else math.sqrt(variance(before_t)) if not indicator and len(before_t)>=2 else None
        equal(row['reference_sd'],sd)
        for when,t,c in [('before',before_t,before_c),('after',after_t,after_c)]:
            equal(row['mean_'+when+'_treated'],mean(t));equal(row['mean_'+when+'_control'],mean(c))
            if row['smd_'+when] is None:assert row['smd_'+when+'_reason']
            else:assert sd is not None and sd>0 and t and c;close(row['smd_'+when],(mean(t)-mean(c))/sd)
    for row in rec['overlap']:
        group=[r for r in subjects if truth(r['complete_case']) and float(r['treatment'])==(1 if row['arm']=='treated' else 0)]
        if row['population']=='support_retained':group=[r for r in group if truth(r['support_retained'])]
        elif row['population']=='matched':group=[r for r in group if truth(r['matched'])]
        assert row['denominator']==len(group)
        hit=[r for r in group if float(r['propensity_score'])>=row['lower'] and (float(r['propensity_score'])<=row['upper'] if row['right_inclusive'] else float(r['propensity_score'])<row['upper'])]
        assert row['n']==len(hit);equal(row['proportion'],len(hit)/len(group) if group else None)
    result_ids={rec['result_id'],e['result_id']}|{r['result_id'] for section in ('balance','overlap') for r in rec[section]}
    datasets={'flow':[{'result_id':rec['result_id'],'status':rec['status'],'reason_code':rec['reason_code'],'denominator':n,'denominator_semantics':'source_subjects',**flow}],
      'effect':[{**e,'denominator':m,'denominator_semantics':'matched_pairs','standard_error_scale':'outcome_units','effect_scale':'treated_minus_control_outcome_units'}],
      'balance':rec['balance'],'overlap':rec['overlap']}
    expected_artifacts={}
    for section,expected in datasets.items():
        path=out/'tables'/('psm_'+section+'.csv');exported=table(path);assert len(exported)==len(expected)
        by_result={r['result_id']:r for r in expected};assert set(by_result)=={r['result_id'] for r in exported}
        for row in exported:
            for key,value in by_result[row['result_id']].items():equal(row[key],value)
            for key,value in {'run_id':result['run_id'],'method_id':result['method_id'],'provider_version':result['provider']['version'],
              'core_version':result['core_version'],'input_hash':result['binding']['input_hash'],'view_hash':result['provenance']['view_hash'],
              'estimand':opt['estimand'],'target_population_scope':'complete_covariate_retained_matched_treated','outcome_unit':semantics['outcome_unit'],'event_count_semantics':'not_applicable_continuous_outcome',
              'scientific_review':'pending','export_status':'local_only','test_only':True}.items():equal(row[key],value)
        expected_artifacts['psm-'+section]=(path,set(by_result));counts[section+'_csv_rows']+=len(exported)
    for section in ('balance','overlap'):expected_artifacts['psm-'+section+'-figure']=(out/'figures'/('psm_'+section+'.png'),{r['result_id'] for r in rec[section]} or {rec['result_id']})
    assert {r['artifact_id'] for r in result['tables']+result['figures']}==set(expected_artifacts)
    for artifact in result['tables']+result['figures']:
        path,ids=expected_artifacts[artifact['artifact_id']];assert path.is_file() and sha(path)==artifact['data_hash']
        assert set(artifact['source_result_ids'])==ids and ids<=result_ids and artifact['caption']
        assert artifact['options']['psm']==opt and artifact['options']['assumptions_verified'] is False
        counts['artifact_hashes']+=1
    assert {r['artifact_id'] for r in result['local_artifacts']}=={'psm-pairs','psm-subjects','psm-model','private-run-manifest'}
    counts['psm_runs']+=1;counts['source_cohort_reconstructions']+=1;counts['private_subject_rows']+=len(subjects);counts['private_pair_rows']+=len(pairs)
    return result_ids

def audit(suite):
    receipt=load(suite/'acceptance-receipt.json');assert receipt['summary']['failed']==0,'acceptance contains failures'
    assert receipt['runtime_lock_sha256']==sha(ROOT/'runtime-lock.json')
    assert all(sha(ROOT/p)==v for p,v in receipt['source_sha256'].items()),'acceptance source binding changed'
    counts={key:0 for key in ('runs','psm_runs','public_files_scanned','source_cohort_reconstructions','private_subject_rows','private_pair_rows','artifact_hashes','writing_reference_checks','flow_csv_rows','balance_csv_rows','overlap_csv_rows','effect_csv_rows')}
    for item in receipt['runs']:
        out=Path(item['output_dir']).resolve();assert out.is_relative_to(suite)
        result=load(out/'result.json');task=load(item['task_path']);assert result['binding']['input_hash']==sha(item['task_path'])
        privacy(out,result,counts);ids=set()
        if result.get('psm') is not None:ids=audit_record(out,result,task,counts)
        else:assert result['execution_status']=='blocked' and not result['tables'] and not result['figures']
        assert set(load(out/'writing-references.json')['result_ids'])==ids
        counts['writing_reference_checks']+=1;counts['runs']+=1
    assert counts['psm_runs']>=14 and counts['private_pair_rows']>=200,'required coverage absent'
    return {'status':'PASS',**counts,'tolerance':{'absolute':ATOL,'relative':RTOL},'runtime_lock_sha256':receipt['runtime_lock_sha256'],
      'acceptance_receipt_sha256':sha(suite/'acceptance-receipt.json'),
      'scope':'Local canonical source, private pair/subject values, public denominators/SMD/overlap/paired difference inference, provenance and privacy; not clinical or specialist-package validation'}
def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT);target=suite/'export-audit.json';assert not target.exists(),'audit receipt exists'
    try:result=audit(suite)
    except Exception as exc:result={'status':'FAIL','reason':type(exc).__name__+': '+str(exc)}
    result['audit_script_sha256']=sha(__file__);target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result));return int(result['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
