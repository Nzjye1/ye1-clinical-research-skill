"""Materialize only declared synthetic fixture templates against an explicit local lock."""
from pathlib import Path
import hashlib,json,sys,subprocess
ROOT=Path(__file__).resolve().parent;CORE=ROOT/"integration/core"
def load(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def main():
 runtime=load(CORE/"runtime-lock.json");manifest=load(CORE/"fixture-templates/manifest.json")
 packages={**runtime["r_package_paths"],**runtime.get("penalized_package_paths",{}),**runtime.get("cox_penalized_package_paths",{})}
 def hydrate(x):
  if isinstance(x,dict):return {hydrate(k):hydrate(v) for k,v in x.items()}
  if isinstance(x,list):return [hydrate(v) for v in x]
  if not isinstance(x,str):return x
  for prefix,base in [("core://",CORE),("backend://",ROOT)]:
   if x.startswith(prefix):
    p=(base/x[len(prefix):]).resolve()
    if not p.is_relative_to(base.resolve()):raise ValueError("FIXTURE_PATH_ESCAPE")
    return str(p)
  if x.startswith("runtime://"):return runtime[x[len("runtime://"):]]
  if x.startswith("package://"):
   name,_,tail=x[len("package://"):].partition("/");return str(Path(packages[name])/tail)
  return x
 sys.path.insert(0,str(CORE/"python"));from clinical_methods.contracts import seal_task
 for entry in manifest["templates"]:
  source=CORE/"fixture-templates"/entry["template"]
  if hashlib.sha256(source.read_bytes()).hexdigest()!=entry["sha256"]:raise ValueError("FIXTURE_TEMPLATE_DRIFT")
  # v06 owns a byte-frozen reference model. Its original factory must
  # copy that model and seal its dependent tasks; never hydrate/reserialize it.
  if entry["target"].startswith("survival-v06/"):continue
  value=hydrate(load(source));target=CORE/"fixtures"/entry["target"]
  if entry["seal_synthetic_task"]:
   if value.get("purpose")!="SYNTHETIC_TEST_ONLY":raise ValueError("FIXTURE_NOT_SYNTHETIC")
   seal_task(value,CORE)
  target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 factory=CORE/"tools/make_survival_v06_fixtures.py"
 subprocess.run([sys.executable,"-B","-X","utf8",str(factory)],cwd=CORE,check=True,capture_output=True)
 print(json.dumps({"status":"SYNTHETIC_FIXTURES_MATERIALIZED","templates":len(manifest["templates"]),"byte_frozen_group_owner":"make_survival_v06_fixtures.py","real_data_read":False}))
if __name__=="__main__":main()
