"""Regression for optional module exports and fresh-output status semantics.

Unit cases mock only doctor/child execution; actual fresh method installation
and complete synthetic exports are separately exercised by the repair driver.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tempfile,unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--package',default=str(ROOT/'windows-v03/toolkit/skills/ye1-clinical-analysis'));p.add_argument('--workdir',required=True)
args,remaining=p.parse_known_args();MAIN=Path(args.package).resolve();WORK=Path(args.workdir).resolve();WORK.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(MAIN/'scripts'));import toolkit as api;import method_groups

class Regression(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(dir=WORK);self.project=Path(self.temporary.name);self.out=self.project/'runs'/'result';self.out.parent.mkdir()
        self.task=self.project/'task.json';self.task.write_text(json.dumps({'schema_version':'clinical-study-input@1.0','data_origin':'synthetic','task_purpose':'engineering_test','project_root':str(self.project),'execution':{'output_dir':str(self.out)}}),encoding='utf-8')
    def tearDown(self):self.temporary.cleanup()
    def fake_failure(self,command,**kwargs):
        kwargs['stdout'].write(b'{"status":"blocked","reason_code":"FRESH_OUTPUT_INSIDE_BACKEND_CORE_REQUIRED"}\n')
        return subprocess.CompletedProcess(command,2)
    def snapshot(self):
        return {p.relative_to(self.project).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in self.project.rglob('*') if p.is_file()}
    def test_every_registered_module_declares_shared_figure_dependencies(self):
        for entry in api.catalog()['methods']:
            if entry['task_family']=='module':
                with self.subTest(method=entry['method_id']):self.assertIn('plot',method_groups.for_method(entry['method_id']))
    def test_existing_complete_result_is_not_this_invocation(self):
        self.out.mkdir();(self.out/'result.json').write_text('{"execution_status":"complete"}',encoding='utf-8');before=self.snapshot()
        with patch.object(api,'doctor'),patch.object(api.subprocess,'run',side_effect=self.fake_failure) as child:
            response,code=api.execute('baseline.table1',self.task)
        self.assertEqual(code,2);self.assertEqual(response['status'],'blocked');self.assertEqual(response['reason_code'],'OUTPUT_ALREADY_EXISTS')
        self.assertFalse(response['analysis_executed']);child.assert_not_called();self.assertEqual(before,self.snapshot())
    def test_existing_partial_result_is_preserved_and_not_reexecuted(self):
        self.out.mkdir();(self.out/'result.json').write_text('{"execution_status":"partial"}',encoding='utf-8');before=self.snapshot()
        with patch.object(api,'doctor'),patch.object(api.subprocess,'run',side_effect=self.fake_failure) as child:
            response,code=api.execute('baseline.table1',self.task)
        self.assertEqual((response['status'],response['reason_code'],code),('blocked','OUTPUT_ALREADY_EXISTS',2));child.assert_not_called();self.assertEqual(before,self.snapshot())
    def test_failed_attempt_snapshot_gets_specific_status_without_overwrite(self):
        private=self.out.parent/'private';private.mkdir();(private/(self.out.name+'.task.json')).write_bytes(b'old failed attempt bytes');before=self.snapshot()
        with patch.object(api,'doctor'),patch.object(api.subprocess,'run',side_effect=self.fake_failure) as child:
            response,code=api.execute('baseline.table1',self.task)
        self.assertEqual((response['status'],response['reason_code'],code),('blocked','OUTPUT_SNAPSHOT_ALREADY_EXISTS',2));self.assertFalse(response['analysis_executed']);child.assert_not_called();self.assertEqual(before,self.snapshot())
    def test_native_preexecution_rejection_cannot_be_masked_by_a_result(self):
        def race(command,**kwargs):
            self.out.mkdir();(self.out/'result.json').write_text('{"execution_status":"complete"}',encoding='utf-8')
            return self.fake_failure(command,**kwargs)
        with patch.object(api,'doctor'),patch.object(api.subprocess,'run',side_effect=race):response,code=api.execute('baseline.table1',self.task)
        self.assertEqual((response['status'],response['reason_code'],code),('blocked','FRESH_OUTPUT_INSIDE_BACKEND_CORE_REQUIRED',2))
    def test_new_partial_result_with_native_execution_receipt_still_reports_review(self):
        def partial(command,**kwargs):
            self.out.mkdir();(self.out/'result.json').write_text('{"execution_status":"partial"}',encoding='utf-8')
            record={'executed_task_count':1,'selected_method_id':'baseline.table1','execution_status':'partial','result':str(self.out/'result.json')}
            kwargs['stdout'].write((json.dumps(record)+'\n').encode());return subprocess.CompletedProcess(command,1)
        with patch.object(api,'doctor'),patch.object(api.subprocess,'run',side_effect=partial):response,code=api.execute('baseline.table1',self.task)
        self.assertEqual((response['status'],code),('ANALYSIS_COMPUTED_ARTIFACT_REVIEW_REQUIRED',2))
    def test_validation_rejection_never_reports_old_computation(self):
        self.out.mkdir();(self.out/'result.json').write_text('{"execution_status":"complete"}',encoding='utf-8')
        with patch.object(api,'doctor'),patch.object(api.subprocess,'run',side_effect=self.fake_failure):response,code=api.execute('baseline.table1',self.task,validate_only=True)
        self.assertEqual((response['status'],code),('blocked',2))

if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining])
