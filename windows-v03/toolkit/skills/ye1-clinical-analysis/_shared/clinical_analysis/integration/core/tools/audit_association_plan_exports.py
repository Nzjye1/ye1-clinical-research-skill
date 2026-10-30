"""Read existing synthetic outputs; compare all exported flow/test scalars and hashes."""
from __future__ import annotations
import csv,hashlib,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rows(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def equal(value,expected):
    if expected is None:assert value=='','null was not exported as empty cell'
    elif type(expected) in (int,float):
        got=float(value);assert math.isfinite(got) and abs(got-expected)<=1e-8,'export scalar mismatch'
    else:assert value==expected,'export text mismatch'
def audit(suite):
    n_runs=n_flow=n_tests=n_artifacts=n_effects=n_subgroups=n_missing_fields=0
    for result_path in sorted(suite.glob('*/result.json')):
        out=result_path.parent;result=load(result_path)
        if not result.get('model_results'):continue
        backend=load(out/'private/backend.json');models={m['model_id']:m for m in result['model_results']}
        raw_models={m['model_id']:m['record'] for m in backend['models']}
        for key,model in models.items():
            assert model['missing_by_field']==raw_models[key].get('missing_by_field',{})
            assert model['subgroup_counts']==raw_models[key].get('subgroup_counts',[])
            n_missing_fields+=len(model['missing_by_field'])
        flowrows=rows(out/'tables/model_flow.csv');assert len(flowrows)==len(models)
        for row in flowrows:
            model=models[row['model_id']]
            for key in ['label','role','status','reason_code','events','non_events']:equal(row[key],model[key])
            equal(row['covariates'],';'.join(model['covariates']))
            for key,value in model['flow'].items():equal(row[key],value)
            n_flow+=1
        allgroups=[(mid,group) for mid,model in models.items() for group in model['subgroup_counts']]
        if allgroups:
            groups=rows(out/'tables/subgroup_counts.csv');assert len(groups)==len(allgroups)
            indexed={(mid,group['level']):group for mid,group in allgroups}
            for row in groups:
                model=models[row['model_id']];group=indexed[(row['model_id'],row['level'])]
                equal(row['status'],model['status']);equal(row['reason_code'],model['reason_code'])
                for key in ['level','n_used','events','non_events']:equal(row[key],group[key])
                n_subgroups+=1
        tests={t['result_id']:t for t in result['tests']};testrows=rows(out/'tables/model_tests.csv');assert len(testrows)==len(tests)
        for row in testrows:
            test=tests[row['result_id']]
            assert set(row)==set(test)
            for key,value in test.items():equal(row[key],value)
            n_tests+=1
        estimates={e['result_id']:e for e in result['estimates']}
        if estimates:
            effectrows=rows(out/'tables/association_effects.csv');assert len(effectrows)==len(estimates)
            for row in effectrows:
                e=estimates[row['result_id']]
                for key in ['model_id','component','term','contrast','exposure_value','reference','estimate','standard_error','p','effect_scale','standard_error_scale','denominator']:
                    equal(row[key],e.get(key))
                equal(row['ci_lower'],e['ci']['lower']);equal(row['ci_upper'],e['ci']['upper'])
                equal(row['fit_denominator'],e.get('fit_denominator',e['denominator']))
                for key in ['events','non_events','subgroup_level','subgroup_reference']:equal(row[key],e.get(key))
                if e['component']=='subgroup_effect':assert e['reference'] is None and e['subgroup_reference'] is not None
                n_effects+=1
        ids=set(tests)|set(estimates)
        table_files={'model-flow':'model_flow.csv','model-tests':'model_tests.csv','association-plan-effects':'association_effects.csv','subgroup-counts':'subgroup_counts.csv'}
        for art in result['tables']+result['figures']:
            file=out/'tables'/table_files[art['artifact_id']] if art['kind']=='table' else out/'figures'/(art['artifact_id']+'.png')
            assert file.is_file() and sha(file)==art['data_hash'],'artifact file/hash mismatch'
            assert set(art['source_result_ids'])<=ids
            if art['kind']=='figure':
                mid=art['options']['model_id'];linked={key for key,e in estimates.items() if e['model_id']==mid}
                assert linked==set(art['source_result_ids']),'figure data references mismatch'
                raw=next(m['record'] for m in backend['models'] if m['model_id']==mid)
                curve=raw['reporting']['curve']
                if curve:
                    for key in ['knots','reference','domain','observed_domain','grid']:assert art['options'][key]==curve[key]
                    assert 'pointwise' in art['caption'].lower()
            n_artifacts+=1
        writing=load(out/'writing-references.json')
        assert 'SYNTHETIC-V03-' not in json.dumps(writing),'identity in writing references'
        n_runs+=1
    assert n_runs>=14,'incomplete suite export audit'
    return {'status':'PASS','model_runs':n_runs,'model_flow_rows':n_flow,'joint_test_rows':n_tests,'effect_rows':n_effects,'subgroup_count_rows':n_subgroups,'missing_field_counts':n_missing_fields,'artifact_hashes':n_artifacts,'scalar_atol':1e-8,
      'scope':'read-only CSV/result/figure hashes and linkage audit, no fitting'}
def main():
    suite=Path(sys.argv[1]).resolve();assert suite.is_relative_to(ROOT)
    try:
        receipt=load(suite/'acceptance-receipt.json')
        assert receipt['runtime_lock_sha256']==sha(ROOT/'runtime-lock.json'),'current production lock differs from acceptance'
        result={**audit(suite),'runtime_lock_sha256':receipt['runtime_lock_sha256'],'acceptance_receipt_sha256':sha(suite/'acceptance-receipt.json')}
    except Exception as exc:result={'status':'FAIL','reason':type(exc).__name__+': '+str(exc)}
    result['audit_script_sha256']=sha(Path(__file__))
    (suite/'export-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result));return int(result['status']!='PASS')
if __name__=='__main__':raise SystemExit(main())
