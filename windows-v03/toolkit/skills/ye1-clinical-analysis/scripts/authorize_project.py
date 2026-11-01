"""Compatibility entry for existing local plan callers; no user confirmation is recorded."""
from pathlib import Path
import argparse, json, subprocess, sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze
import ingestion

def run(plan_path, practice=False):
    path = Path(plan_path).resolve()
    plan = analyze.load(path)
    project = Path(plan["project"]).resolve()
    ingestion.need(project.is_dir() and path.is_relative_to(project), "PLAN_INSIDE_PROJECT_REQUIRED")
    ingestion.confined(plan["source"], project)
    if practice:
        ingestion.need(plan.get("data_origin") == "synthetic", "PRACTICE_CANNOT_AUTHORIZE_REAL_DATA")
    analyze.build(plan)
    return {"status": "LOCAL_PLAN_READY", "plan": str(path), "data_sent": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True)
    p.add_argument("--practice", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(run(args.plan, args.practice), ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "LOCAL_PLAN_INVALID", "reason_code": getattr(error, "code", "LOCAL_PLAN_INVALID")}))
        raise SystemExit(2)
if __name__ == "__main__":
    from runtime_platform import runtime_python
    from runtime_windows import ROOT, env
    selected = runtime_python(ROOT)
    if selected.is_file() and Path(sys.executable).resolve() != selected.resolve():
        raise SystemExit(subprocess.run([str(selected), "-I", "-B", "-X", "utf8", str(Path(__file__).resolve()), *sys.argv[1:]], env=env()).returncode)
    main()
