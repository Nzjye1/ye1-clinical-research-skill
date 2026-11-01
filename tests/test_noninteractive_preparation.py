"""Non-interactive preparation of generated fixture data under real-data routing."""
from pathlib import Path
import copy, json, subprocess, sys, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'windows-v03/toolkit/skills/ye1-clinical-analysis'
CORE = MAIN / '_shared/clinical_analysis/integration/core'
sys.path[:0] = [str(MAIN/'scripts'), str(CORE/'python')]
import prepare_task
from clinical_methods import contracts

class Preparation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT.parent)
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name).resolve()
        self.source = self.project/'input.csv'
        self.source.write_text('id,x,z,y\na,1,2,3\nb,2,3,4\n', encoding='utf-8')
        task = contracts.make_example_task(self.source, self.project/'out', CORE, database='SELF_FILE')
        task.update(schema_version='clinical-study-input@1.0', data_origin='real', task_purpose='research_analysis', project_root=str(self.project), authorization=None)
        task['execution'].update(mode='local', authorization_ref=None, privacy_profile='captured_local_process', max_rows=1000, max_bytes=2000000, max_decoded_bytes=4000000)
        task['time']['policy'] = 'ordered_observation'
        for source in task['sources']:
            source.update(source_kind='user_clinical_file', verification_status='local_bytes_bound', source_fingerprint={'$file_sha256':str(self.source)})
        for view in task['views']:
            view.update(local_ref=str(self.source), format='csv', unselected_columns=[], location_policy='project_local', content_hash={'$file_sha256':str(self.source)})
        self.draft = {'schema_version':'ye1-toolkit-draft@1.0', 'method_id':'association.linear', 'data_origin':'real', 'task_purpose':'research_analysis', 'project_root':str(self.project), 'local_tables':{}, 'task':task}
        self.old_check = prepare_task.check
        prepare_task.check = lambda *_: None
        self.addCleanup(setattr, prepare_task, 'check', self.old_check)
    def write(self, draft):
        p=self.project/'draft.json';p.write_text(json.dumps(draft),encoding='utf-8');return p
    def test_real_routing_without_confirmation(self):
        result = prepare_task.prepare(self.write(self.draft))
        task = json.loads(Path(result['task']).read_text(encoding='utf-8'))
        self.assertIsNone(task['authorization'])
        self.assertIsNone(task['execution']['authorization_ref'])
        self.assertFalse((self.project/'.ye1-privacy').exists())
        self.assertFalse((self.project/'local-review').exists())
    def test_origin_and_path_rejected(self):
        bad=copy.deepcopy(self.draft);bad['task_purpose']='engineering_test'
        with self.assertRaisesRegex(ValueError,'ORIGIN_PURPOSE_CONFLICT'):prepare_task.prepare(self.write(bad))
        bad=copy.deepcopy(self.draft);bad['task']['views'][0]['local_ref']=str(self.project.parent/'outside.csv')
        with self.assertRaisesRegex(ValueError,'INPUT_OUTSIDE_PROJECT'):prepare_task.prepare(self.write(bad))
        bad=copy.deepcopy(self.draft);bad['task']['execution']['output_dir']=str(self.project.parent/'outside-output')
        with self.assertRaisesRegex(ValueError,'INPUT_OUTSIDE_PROJECT'):prepare_task.prepare(self.write(bad))

if __name__=='__main__':unittest.main()
