"""Verify only current-version/union expectations changed in inherited tests."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'clinical-analysis-core-v0_5-dev-20261024'
CHANGES={
 'test_association_plan_acceptance.py':[("'clinical-analysis-result@0.5.0-candidate1' and result['core_version']=='0.5.0-candidate1'","'clinical-analysis-result@0.6.0-candidate1' and result['core_version']=='0.6.0-candidate1'")],
 'test_survival_acceptance.py':[("'clinical-analysis-result@0.5.0-candidate1' and result['core_version']=='0.5.0-candidate1'","'clinical-analysis-result@0.6.0-candidate1' and result['core_version']=='0.6.0-candidate1'")],
 'test_association_plan_contracts.py':[("test_five_version_schema_export_preserves_association_plan","test_six_version_schema_export_preserves_association_plan"),("len(c.input_union_schema()['anyOf']),5","len(c.input_union_schema()['anyOf']),6")],
 'test_survival_contracts.py':[("test_five_version_union","test_six_version_union"),("len(union['anyOf']),5","len(union['anyOf']),6")],
 'test_survival_v05_acceptance.py':[("result[\"schema_version\"]==\"clinical-analysis-result@0.5.0-candidate1\" and result[\"core_version\"]==\"0.5.0-candidate1\"","result[\"schema_version\"]==\"clinical-analysis-result@0.6.0-candidate1\" and result[\"core_version\"]==\"0.6.0-candidate1\"")],
 'test_survival_v05_contracts.py':[("len(schema[\"anyOf\"]), 5","len(schema[\"anyOf\"]), 6")],
 'test_survival_v05_result_schema.py':[("self.schema['$id'], 'clinical-analysis-result@0.5.0-candidate1'","self.schema['$id'], 'clinical-analysis-result@0.6.0-candidate1'"),("    # These fields did not exist in historical output versions.\n","    # These fields did not exist in historical output versions.\n    if version >= '0.6':\n        result['survival_evaluation'] = None\n")],
}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    checks=[]
    for old in sorted((OLD/'tests').glob('*')):
        if not old.is_file():continue
        new=ROOT/'tests'/old.name
        expected=old.read_text(encoding='utf-8')
        for a,b in CHANGES.get(old.name,[]):
            if expected.count(a)!=1:raise RuntimeError('OLD_ASSERTION_NOT_UNIQUE:'+old.name)
            expected=expected.replace(a,b)
        if new.read_text(encoding='utf-8')!=expected:raise RuntimeError('ADDITIONAL_TEST_CHANGE:'+old.name)
        checks.append({'test':old.name,'old_sha256':sha(old),'current_sha256':sha(new),'status':'PASS',
                       'changes':[{'old':a,'new':b} for a,b in CHANGES.get(old.name,[])]})
    receipt={'status':'PASS','scope':'All inherited tests compared to frozen v05. Seven files have only current-version/union expectations and the required nullable v06 field in the generic result fixture updated; model schema remains v05 and all numerical/rejection coverage retained.','modified_test_files':len(CHANGES),'checks':checks}
    (ROOT/'evidence/test-expectation-update-v06.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('TEST_EXPECTATIONS_PASS',len(checks),'INHERITED_FILES',len(CHANGES),'VERSION_ONLY_UPDATES')
if __name__=='__main__':main()
