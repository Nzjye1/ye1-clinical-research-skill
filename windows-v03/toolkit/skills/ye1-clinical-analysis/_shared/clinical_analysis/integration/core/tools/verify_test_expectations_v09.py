"""Exact inherited test adaptations for v09; statistical assertions unchanged."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'clinical-analysis-core-v0_8-dev-20261024'
CHANGES={'test_association_plan_acceptance.py': [("        assert result['schema_version']=='clinical-analysis-result@0.8.0-candidate1' and "
                                          "result['core_version']=='0.8.0-candidate1'",
                                          "        assert result['schema_version']=='clinical-analysis-result@0.9.0-candidate1' and "
                                          "result['core_version']=='0.9.0-candidate1'")],
 'test_association_plan_contracts.py': [("        self.assertEqual(len(c.input_union_schema()['anyOf']),8)",
                                         "        self.assertEqual(len(c.input_union_schema()['anyOf']),9)")],
 'test_penalized_v08_acceptance.py': [("        assert result['schema_version']=='clinical-analysis-result@0.8.0-candidate1' and "
                                       "result['core_version']=='0.8.0-candidate1'",
                                       "        assert result['schema_version']=='clinical-analysis-result@0.9.0-candidate1' and "
                                       "result['core_version']=='0.9.0-candidate1'")],
 'test_penalized_v08_contracts.py': [('        self.assertEqual(union["$id"], "clinical-study-input-union@0.8.0-candidate1")',
                                      '        self.assertEqual(union["$id"], "clinical-study-input-union@0.9.0-candidate1")'),
                                     ('        self.assertEqual(len(union["anyOf"]), 8)',
                                      '        self.assertEqual(len(union["anyOf"]), 9)')],
 'test_penalized_v08_result_schema.py': [("        self.assertEqual(len(self.schema['anyOf']), 8)",
                                          "        self.assertEqual(len(self.schema['anyOf']), 9)"),
                                         ("        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@' + VERSION)",
                                          "        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.9.0-candidate1')")],
 'test_psm_v07_acceptance.py': [("        assert result['schema_version']=='clinical-analysis-result@0.8.0-candidate1' and "
                                 "result['core_version']=='0.8.0-candidate1'",
                                 "        assert result['schema_version']=='clinical-analysis-result@0.9.0-candidate1' and "
                                 "result['core_version']=='0.9.0-candidate1'")],
 'test_psm_v07_contracts.py': [('        self.assertEqual(union["$id"], "clinical-study-input-union@0.8.0-candidate1")',
                                '        self.assertEqual(union["$id"], "clinical-study-input-union@0.9.0-candidate1")'),
                               ('        self.assertEqual(len(union["anyOf"]), 8)', '        self.assertEqual(len(union["anyOf"]), 9)')],
 'test_psm_v07_result_schema.py': [("        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.8.0-candidate1')",
                                    "        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.9.0-candidate1')"),
                                   ("        self.assertEqual(len(self.schema['anyOf']), 8)",
                                    "        self.assertEqual(len(self.schema['anyOf']), 9)")],
 'test_survival_acceptance.py': [("        assert result['schema_version']=='clinical-analysis-result@0.8.0-candidate1' and "
                                  "result['core_version']=='0.8.0-candidate1'",
                                  "        assert result['schema_version']=='clinical-analysis-result@0.9.0-candidate1' and "
                                  "result['core_version']=='0.9.0-candidate1'")],
 'test_survival_contracts.py': [('        '
                                 "union=c.input_union_schema();self.assertEqual(len(union['anyOf']),8);c.validate_schema(self.task,union)",
                                 '        '
                                 "union=c.input_union_schema();self.assertEqual(len(union['anyOf']),9);c.validate_schema(self.task,union)")],
 'test_survival_v05_acceptance.py': [('        assert result["schema_version"]=="clinical-analysis-result@0.8.0-candidate1" and '
                                      'result["core_version"]=="0.8.0-candidate1"',
                                      '        assert result["schema_version"]=="clinical-analysis-result@0.9.0-candidate1" and '
                                      'result["core_version"]=="0.9.0-candidate1"')],
 'test_survival_v05_contracts.py': [('        self.assertEqual(len(schema["anyOf"]), 8)',
                                     '        self.assertEqual(len(schema["anyOf"]), 9)')],
 'test_survival_v05_result_schema.py': [("        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.8.0-candidate1')",
                                         "        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.9.0-candidate1')"),
                                        ('    # These fields did not exist in historical output versions.\n',
                                         '    # These fields did not exist in historical output versions.\n'
                                         "    if version >= '0.9':\n"
                                         "        result['interpretation'] = None\n")],
 'test_survival_v06_acceptance.py': [('        assert result["schema_version"]=="clinical-analysis-result@0.8.0-candidate1" and '
                                      'result["core_version"]=="0.8.0-candidate1"',
                                      '        assert result["schema_version"]=="clinical-analysis-result@0.9.0-candidate1" and '
                                      'result["core_version"]=="0.9.0-candidate1"')],
 'test_survival_v06_contracts.py': [('        self.assertEqual(union["$id"], "clinical-study-input-union@0.8.0-candidate1")',
                                     '        self.assertEqual(union["$id"], "clinical-study-input-union@0.9.0-candidate1")'),
                                    ('        self.assertEqual(len(union["anyOf"]), 8)',
                                     '        self.assertEqual(len(union["anyOf"]), 9)')],
 'test_survival_v06_result_schema.py': [("        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.8.0-candidate1')",
                                         "        self.assertEqual(self.schema['$id'], 'clinical-analysis-result@0.9.0-candidate1')"),
                                        ("        self.assertEqual(len(self.schema['anyOf']), 8)",
                                         "        self.assertEqual(len(self.schema['anyOf']), 9)")]}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    apply=sys.argv[1:]==['--apply']
    if apply and (ROOT/'CANDIDATE-SHA256SUMS.txt').exists():raise RuntimeError('FROZEN_CANDIDATE')
    checks=[]
    for old in sorted((OLD/'tests').glob('*')):
        if not old.is_file():continue
        new=ROOT/'tests'/old.name;original=old.read_text(encoding='utf-8');expected=original
        for a,b in CHANGES.get(old.name,[]):
            if expected.count(a)!=1:raise RuntimeError('EXPECTED_OLD_ASSERTION_NOT_UNIQUE:'+old.name)
            expected=expected.replace(a,b)
        if apply and old.name in CHANGES:
            if new.read_text(encoding='utf-8') not in (original,expected):raise RuntimeError('UNEXPECTED_EXISTING_EDIT:'+old.name)
            if new.read_text(encoding='utf-8')!=expected:new.write_text(expected,encoding='utf-8')
        if new.read_text(encoding='utf-8')!=expected:raise RuntimeError('ADDITIONAL_TEST_CHANGE:'+old.name)
        checks.append({'test':old.name,'old_sha256':sha(old),'current_sha256':sha(new),'status':'PASS',
                       'changes':[{'old':a,'new':b} for a,b in CHANGES.get(old.name,[])]})
    receipt={'status':'PASS','scope':'All inherited tests compared to frozen v08. Only current output version, union cardinality/branch location and the new nullable interpretation slot in a generic fixture are adapted; historical versions, numerical tolerances, tests and model-format guards remain unchanged.',
      'modified_test_files':len(CHANGES),'checks':checks}
    (ROOT/'evidence/test-expectation-update-v09.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print('TEST_EXPECTATIONS_PASS',len(checks),'INHERITED_FILES',len(CHANGES),'CURRENT_VERSION_ADAPTATIONS')
if __name__=='__main__':main()
