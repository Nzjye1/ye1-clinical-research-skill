"""Read-only audit of completed survival outputs; writes an audit receipt only."""
from __future__ import annotations
import csv,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def equal(text,value):
    if value is None:assert text in ['', 'NA']
    elif isinstance(value,bool):assert text.lower()==str(value).lower()
    elif isinstance(value,(int,float)):assert math.isfinite(float(text)) and abs(float(text)-value)<=1e-8
    else:assert text==value
def audit(suite):
    receipt=load(suite/'acceptance-receipt.json');lock=load(ROOT/'runtime-lock.json')
    assert receipt['runtime_lock_sha256']==sha(ROOT/'runtime-lock.json'),'production lock differs from suite'
    totals={'survival_results':0,'curve_csv_rows':0,'summary_csv_rows':0,'hr_csv_rows':0,'ph_csv_rows':0,'artifact_hashes':0,'noevent_counts_retained':0,'source_support_checks':0}
    files={'survival-curve-risk-table':'tables/survival_curve.csv','survival-summary':'tables/survival_summary.csv',
      'ph-descriptive-diagnostics':'tables/ph_diagnostics.csv','effect-estimates':'tables/effect_estimates.csv',
      'survival-curve':'figures/survival.png','association-forest':'figures/effects.png'}
    for path in sorted(suite.glob('*/result.json')):
        result=load(path);out=path.parent;s=result.get('survival')
        if s is None:continue
        totals['survival_results']+=1
        assert result['provider']['id']=='clinical_methods.survival'
        assert result['provider']['version']==lock['survival_provider_version']==result['provider']['code_hash']
        assert s['ph_assumption_verified'] is False and 'formal' in s['ph_note'].lower()
        assert all('p' not in d for d in s['ph_diagnostics'])
        if s['support'] is not None:
            # Reconstruct only the declared source fields from the original
            # synthetic CSV, independently of private normalized/provider rows.
            task=load(suite/(out.name.removeprefix('中文 路径 ')+'.json'));spec=task['analysis']['survival'];view=task['views'][0]
            source=Path(view['local_ref']).resolve();assert source.is_relative_to(ROOT)
            source_rows=table(source);variables={v['name']:v for v in task['variables']}
            fields=[spec['time'],spec['status']]+[v['name'] for v in spec['covariates']];normalized=[]
            for row in source_rows:
                values={}
                for field in fields:
                    v=variables[field];value=row[view['column_map'][field]]
                    values[field]=None if value in v['missing_codes'] else v['codes'][value] if v['dtype']=='category' else float(value)*v['conversion']['scale']+v['conversion']['offset']
                normalized.append(values)
            complete=[row for row in normalized if all(row[field] is not None for field in fields)]
            times=[row[spec['time']] for row in complete];events=[row[spec['time']] for row in complete if row[spec['status']]==spec['event_code']]
            support=s['support'];assert support['complete_case_followup_min']==min(times) and support['complete_case_followup_max']==max(times)
            assert support['last_target_event_time']==(max(events) if events else None) and support['evaluation_times']==spec['evaluation_times'] and support['time_unit']==spec['time_unit']
            counts=result['counts'];assert counts['source_rows']==len(source_rows) and counts['model_n']==len(complete)
            assert counts['events']==len(events) and counts['censored']==len(complete)-len(events)
            missing={field:sum(row[field] is None for row in normalized) for field in fields};missing={k:v for k,v in missing.items() if v}
            assert counts['missing_by_field']==missing
            for point in s['curves']:assert point['n_at_risk']==sum(t>=point['time'] for t in times)
            totals['source_support_checks']+=1
        if result['reason_code']=='NO_TARGET_EVENTS':
            assert result['counts']['events']==0 and result['counts']['model_n']==result['counts']['censored']
            assert not s['curves'] and not result['estimates'] and not result['figures'];totals['noevent_counts_retained']+=1
        points={p['result_id']:p for p in s['curves']};estimates={p['result_id']:p for p in result['estimates']}
        ids=set(points)|set(estimates)
        if points:
            rows=table(out/'tables/survival_curve.csv');assert len(rows)==len(points)
            for row in rows:
                p=points[row['result_id']]
                for key in ['time','n_at_risk','estimate','denominator','events','censored','denominator_semantics']:equal(row[key],p[key])
                for key in ['lower','upper']:equal(row['ci_'+key],p['ci'][key])
                equal(row['time_unit'],s['time_unit']);equal(row['ci_method'],p['ci']['method']);totals['curve_csv_rows']+=1
            rows=table(out/'tables/survival_summary.csv');assert len(rows)==1;row=rows[0];counts=result['counts']
            for key,target in [('n_total','source_rows'),('n_used','model_n'),('n_excluded_missing','excluded_missing'),('events','events'),('censored','censored')]:equal(row[key],counts[target])
            for key in ['time_unit','time_zero_definition','event_definition','censoring_definition','event_code','censor_code','missing_policy','model_status','model_reason','cox_ties']:equal(row[key],s[key])
            assert row['ph_diagnostic_kind']=='descriptive_only';equal(row['ph_assumption_verified'],False);totals['summary_csv_rows']+=1
        if estimates:
            rows=table(out/'tables/effect_estimates.csv');assert len(rows)==len(estimates)
            for row in rows:
                p=estimates[row['result_id']]
                for key in ['term','estimate','standard_error','p','effect_scale','standard_error_scale','denominator','evaluation_set']:equal(row[key],p[key])
                for key in ['lower','upper']:equal(row['ci_'+key],p['ci'][key])
                assert p['effect_scale']=='hazard_ratio' and p['standard_error_scale']=='log_hazard';assert abs(math.log(p['estimate'])-p['log_hazard_ratio'])<1e-8
                totals['hr_csv_rows']+=1
        if s['ph_diagnostics']:
            rows=table(out/'tables/ph_diagnostics.csv');assert len(rows)==len(s['ph_diagnostics'])
            for row,p in zip(rows,s['ph_diagnostics']):
                assert set(row)=={'term','rho','diagnostic_kind','ph_assumption_verified'}
                for key in row:equal(row[key],p[key])
                totals['ph_csv_rows']+=1
        for artifact in result['tables']+result['figures']:
            file=out/files[artifact['artifact_id']];assert file.is_file() and sha(file)==artifact['data_hash']
            assert set(artifact['source_result_ids'])<=ids
            if artifact['artifact_id'] in ['survival-curve','survival-curve-risk-table']:
                assert set(artifact['source_result_ids'])==set(points)
                assert 'unadjusted km' in artifact['caption'].lower() and 'complete-case' in artifact['caption'].lower()
            totals['artifact_hashes']+=1
        writing=load(out/'writing-references.json');assert set(writing['result_ids'])==ids
        assert 'SYNTHETIC-V04-' not in json.dumps(writing) and 'SYNTHETIC-HAND-' not in json.dumps(writing)
    assert totals['survival_results']>=14 and totals['noevent_counts_retained']==2,'incomplete completed suite'
    return {'status':'PASS',**totals,'runtime_lock_sha256':receipt['runtime_lock_sha256'],'acceptance_receipt_sha256':sha(suite/'acceptance-receipt.json'),'scalar_atol':1e-8,'scope':'Existing public JSON/CSV, source IDs, caption semantics and artifact hashes; no fitting or image rendering'}
def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT)
    try:result=audit(suite)
    except Exception as exc:result={'status':'FAIL','reason':type(exc).__name__+': '+str(exc)}
    result['audit_script_sha256']=sha(Path(__file__));(suite/'export-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result));return int(result['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
