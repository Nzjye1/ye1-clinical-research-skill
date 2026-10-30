"""Bounded inherited test changes for version registration and owner extension."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'clinical-analysis-core-v0_4-dev-20261024'
CHANGES={
 'test_association_plan_acceptance.py':[("'clinical-analysis-result@0.4.0-candidate1' and result['core_version']=='0.4.0-candidate1'","'clinical-analysis-result@0.5.0-candidate1' and result['core_version']=='0.5.0-candidate1'")],
 'test_survival_acceptance.py':[("'clinical-analysis-result@0.4.0-candidate1' and result['core_version']=='0.4.0-candidate1'","'clinical-analysis-result@0.5.0-candidate1' and result['core_version']=='0.5.0-candidate1'")],
 'test_survival_contracts.py':[("test_four_version_union","test_five_version_union"),("self.assertEqual(len(union['anyOf']),4)","self.assertEqual(len(union['anyOf']),5)")],
 'test_association_plan_contracts.py':[("test_four_version_schema_export_preserves_association_plan","test_five_version_schema_export_preserves_association_plan"),("self.assertEqual(len(c.input_union_schema()['anyOf']),4)","self.assertEqual(len(c.input_union_schema()['anyOf']),5)")],
 'test_survival_provider.py':[("test_source_is_byte_identical","test_original_source_and_v04_remain_byte_identical"),("(ROOT/'python/clinical_methods/survival.py').read_bytes(),ORIGINAL.read_bytes()","(ROOT.parent/'clinical-analysis-core-v0_4-dev-20261024/python/clinical_methods/survival.py').read_bytes(),ORIGINAL.read_bytes()")],
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=[]
    for name,pairs in CHANGES.items():
        old=OLD/'tests'/name;new=ROOT/'tests'/name
        expected=old.read_text(encoding='utf-8')
        for a,b in pairs:
            if expected.count(a)!=1:raise RuntimeError('OLD_ASSERTION_NOT_UNIQUE:'+name)
            expected=expected.replace(a,b)
        if new.read_text(encoding='utf-8')!=expected:raise RuntimeError('ADDITIONAL_TEST_CHANGE:'+name)
        checks.append({'test':name,'old_sha256':sha(old),'current_sha256':sha(new),'status':'PASS','changes':[{'old':a,'new':b} for a,b in pairs]})
    receipt={'status':'PASS','scope':'Four isolated inherited version/union assertions updated. Old byte-preservation assertion now protects original and frozen v04 because v05 intentionally extends the sole owner; adjacent exact original KM/Cox numerical regression unchanged. All original numerical/rejection assertions retained.','checks':checks}
    (ROOT/'evidence/test-expectation-update-v05.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('TEST_EXPECTATIONS_PASS',len(checks))
if __name__=='__main__':main()
