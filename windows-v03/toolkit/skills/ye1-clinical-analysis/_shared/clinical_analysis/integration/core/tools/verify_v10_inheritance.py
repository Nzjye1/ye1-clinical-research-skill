"""Read-only bounded preservation check; writes only the v10 local receipt."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'clinical-analysis-core-v0_9-dev-20261024'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
    lock=load(ROOT/'runtime-lock.json');old=load(OLD/'runtime-lock.json')
    expected_changes={'src/clinanalysis/R/clinical_common.R','src/clinanalysis/R/clinical_interpretation_v09.R','python/clinical_methods/contracts.py','schemas/input.schema.json','schemas/result.schema.json'}
    changed={p for p,h in old['code_hashes'].items() if sha(ROOT/p)!=h}
    assert changed==expected_changes,('UNEXPECTED_OLD_PRODUCTION_DELTA',sorted(changed))
    providerkeys=[k for k in old if k.endswith('provider_version') or k=='prediction_provider_versions']
    assert all(lock[k]==old[k] for k in providerkeys),'OLD_PROVIDER_VERSION_CHANGED'
    for schema in ('input','result'):
        previous=load(OLD/f'schemas/{schema}.schema.json');current=load(ROOT/f'schemas/{schema}.schema.json')
        retained=current['anyOf'][:9] if schema=='input' else current['anyOf'][1:]
        assert len(previous['anyOf'])==9 and len(current['anyOf'])==10 and previous['anyOf']==retained,schema
    for p,h in lock['cox_penalized_dependency_hashes'].items():assert sha(p)==h,'DEPENDENCY_DRIFT'
    origins=load(OLD/'evidence/source-provenance.json')['source_tree_files']
    for row in origins:assert sha(row['original'])==row['original_hash'],'ORIGINAL_SOURCE_CHANGED'
    receipt={'status':'PASS','runtime_lock_sha256':sha(ROOT/'runtime-lock.json'),'old_candidate':'v0.9.0-candidate1',
      'old_production_files':len(old['code_hashes']),'old_production_unchanged':len(old['code_hashes'])-len(changed),
      'explicit_common_contract_changes':sorted(changed),'new_production_files':sorted(set(lock['code_hashes'])-set(old['code_hashes'])),
      'all_old_numerical_provider_versions_unchanged':True,'provider_keys':providerkeys,
      'old_input_and_result_schema_branches_exact':9,'bound_original_source_files_checked':len(origins),
      'native_dependency_hashes_checked':len(lock['cox_penalized_dependency_hashes']),
      'scope':'Only manifest-bound original files checked; common-contract additions and the specifically authorized v09 P1 plot-layout repair are allowed. Numerical owners remain unchanged. No raw database scan.'}
    (ROOT/'evidence/inheritance-v10.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))
if __name__=='__main__':main()
