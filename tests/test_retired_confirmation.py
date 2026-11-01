"""Regression: retired legacy routes require no confirmation and read no sources."""
from pathlib import Path
import importlib.util, json, subprocess, sys, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
MAIN=ROOT/'windows-v03/toolkit/skills/ye1-clinical-analysis'
INTEGRATION=MAIN/'_shared/clinical_analysis/integration'
CORE=INTEGRATION/'core'
sys.path[:0]=[str(INTEGRATION),str(CORE/'python')]
from clinical_methods import contracts
import captured_study

class RetiredConfirmation(unittest.TestCase):
 def test_old_confirmation_engine_absent(self):
  base=MAIN/'_shared/clinical_analysis/legacy/scripts'
  self.assertFalse((base/'clinical_engine.py').exists())
  self.assertFalse((base/'confirmation_evidence.py').exists())
  self.assertNotIn('confirmation',captured_study._layout(CORE)['files'])
 def test_retired_engine_refuses_without_reading(self):
  result=subprocess.run([sys.executable,'-I','-B',str(INTEGRATION/'real_engineering.py'),'prepare','--task','missing-source','--output','missing-output'],stdin=subprocess.DEVNULL,capture_output=True,text=True,encoding='utf8')
  self.assertEqual(result.returncode,2)
  self.assertEqual(json.loads(result.stdout)['reason_code'],'LEGACY_ENGINEERING_RETIRED')
 def test_explicit_external_file_binding_needs_no_confirmation_fields(self):
  auth={'external_files':[{'path':'/declared/file.csv','sha256':'a'*64}]}
  schema=contracts.STUDY_SCHEMA['properties']['authorization']
  contracts.validate_schema(auth,schema)
  published=json.loads((INTEGRATION/'contracts/module-task-origin.schema.json').read_text(encoding='utf8'))
  self.assertEqual(published['properties']['authorization'],schema)
  core_schema=json.loads((CORE/'schemas/study-input.schema.json').read_text(encoding='utf8'))
  self.assertEqual(core_schema['properties']['authorization'],schema)
  with self.assertRaises(ValueError):contracts.validate_schema({'external_files':[{'path':'/declared/file.csv','sha256':'bad'}]},schema)
 def test_existing_choice_does_not_require_old_confirmation_file(self):
  with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
   project=Path(directory).resolve();state=project/'.ye1-privacy';state.mkdir()
   layout=captured_study._layout(CORE);privacy=captured_study._privacy(layout)
   choice={'schema':'ye1-data-choice/1','mode':'B','attachment_history':[],'grants':[]}
   item={'revision':1,'previous':None,'choice':choice,'evidence':{'kind':'direct_user','path':'missing-old-record'},'test_only':False,'at':'historical'}
   item['sha256']=privacy.digest(privacy.encoded(item))
   (state/'choice.json').write_bytes(privacy.encoded(choice));(state/'history.json').write_bytes(privacy.encoded([item]))
   self.assertEqual(captured_study._choice(project,layout)['mode'],'B')
   choice['mode']='A';item['choice']=choice;item.pop('sha256');item['sha256']=privacy.digest(privacy.encoded(item))
   (state/'choice.json').write_bytes(privacy.encoded(choice));(state/'history.json').write_bytes(privacy.encoded([item]))
   with self.assertRaisesRegex(ValueError,'EXISTING_STRICT_MODE_REQUIRES_REVIEW'):captured_study._choice(project,layout)
   item['sha256']='0'*64;(state/'history.json').write_bytes(privacy.encoded([item]))
   with self.assertRaisesRegex(ValueError,'PROJECT_CHOICE_CHANGED'):captured_study._choice(project,layout)

if __name__=='__main__':unittest.main()
