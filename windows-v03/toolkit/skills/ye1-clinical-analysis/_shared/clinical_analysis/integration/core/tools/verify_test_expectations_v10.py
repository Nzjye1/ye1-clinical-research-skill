"""Audited inherited-test version adaptations; historical/statistical checks retained."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'clinical-analysis-core-v0_9-dev-20261024'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def expected_text(name, original):
    changes=[];result=original
    for line in original.splitlines(keepends=True):
        replacement=line
        if 'assert result[' in line and 'schema_version' in line and 'core_version' in line:
            replacement=replacement.replace('clinical-analysis-result@0.9.0-candidate1','clinical-analysis-result@0.10.0-candidate1').replace("=='0.9.0-candidate1'","=='0.10.0-candidate1'").replace('=="0.9.0-candidate1"','=="0.10.0-candidate1"')
        if 'self.assertEqual' in line and '["$id"]' in line and 'clinical-study-input-union@0.9.0-candidate1' in line:
            replacement=replacement.replace('clinical-study-input-union@0.9.0-candidate1','clinical-study-input-union@0.10.0-candidate1')
        if 'self.assertEqual' in line and "self.schema['$id']" in line:
            replacement=replacement.replace('clinical-analysis-result@0.9.0-candidate1','clinical-analysis-result@0.10.0-candidate1')
            if name=='test_interpretation_v09_result_schema.py':replacement=replacement.replace("'clinical-analysis-result@' + VERSION","'clinical-analysis-result@0.10.0-candidate1'")
        if 'self.assertEqual(len(' in line and 'anyOf' in line:
            replacement=re.sub(r'([,) ]+)9\)',lambda m:m.group(1)+'10)',replacement)
        if replacement!=line:
            assert result.count(line)==1,(name,line)
            result=result.replace(line,replacement);changes.append({'old':line.rstrip('\n'),'new':replacement.rstrip('\n')})
    if name=='test_survival_v05_result_schema.py':
        a='    # These fields did not exist in historical output versions.\n'
        b=a+"    version_key = tuple(int(x) for x in version.split('-')[0].split('.')[:2])\n    if version_key >= (0, 10):\n        result['cox_penalized_prediction'] = None\n"
        assert result.count(a)==1;result=result.replace(a,b);changes.append({'old':a,'new':b})
        for op,minor in [('>=',9),('>=',8),('>=',7),('>=',6),('<',5),('<',4),('<',3),('<',2)]:
            a=f"    if version {op} '0.{minor}':";b=f"    if version_key {op} (0, {minor}):"
            assert result.count(a)==1;result=result.replace(a,b);changes.append({'old':a,'new':b})
    return result,changes
def main():
    apply=sys.argv[1:]==['--apply'];checks=[]
    if apply and (ROOT/'CANDIDATE-SHA256SUMS.txt').exists():raise RuntimeError('FROZEN_CANDIDATE')
    for old in sorted((OLD/'tests').glob('*')):
        if not old.is_file():continue
        new=ROOT/'tests'/old.name;original=old.read_text(encoding='utf-8');expected,changes=expected_text(old.name,original)
        if apply and changes:
            if new.read_text(encoding='utf-8') not in (original,expected):raise RuntimeError('UNEXPECTED_TEST_EDIT:'+old.name)
            if new.read_text(encoding='utf-8')!=expected:new.write_text(expected,encoding='utf-8')
        if new.read_text(encoding='utf-8')!=expected:raise RuntimeError('ADDITIONAL_TEST_CHANGE:'+old.name)
        checks.append({'test':old.name,'old_sha256':sha(old),'current_sha256':sha(new),'status':'PASS','changes':changes})
    receipt={'status':'PASS','scope':'Frozen v09 inherited tests retain methods, historical schema/model versions, statistical assertions and tolerances. Only current output/union versions/cardinality and generic latest-output nullable slot plus numeric version comparison for 0.10 are adapted. No test coverage removed.','modified_test_files':sum(bool(x['changes']) for x in checks),'checks':checks}
    (ROOT/'evidence/test-expectation-update-v10.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('TEST_EXPECTATIONS_PASS',len(checks),'INHERITED_FILES',receipt['modified_test_files'],'VERSION_ADAPTATIONS')
if __name__=='__main__':main()
