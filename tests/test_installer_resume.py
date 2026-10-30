"""Windows CLI regression: fresh base install, repeat, and interrupted venv.

Requires the documented Python/R versions and official wheels (downloaded by
the installer or supplied with --wheelhouse). All attempts/evidence stay in a
new --workdir. No existing project is modified or removed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import subprocess
import sys

TOOLKIT = Path(__file__).resolve().parents[1] / "windows-v03/toolkit"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--rscript", required=True)
    parser.add_argument("--wheelhouse")
    args = parser.parse_args()
    work = Path(args.workdir).resolve()
    work.mkdir()  # Fail rather than reuse or overwrite previous evidence.
    records = []

    def run(name, command, expected=0):
        done = subprocess.run(command, stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=600)
        (work / (name + ".stdout")).write_bytes(done.stdout)
        (work / (name + ".stderr")).write_bytes(done.stderr)
        records.append({"step": name, "command": list(map(str, command)),
                        "returncode": done.returncode})
        (work / "commands.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
        print(json.dumps({"step": name, "returncode": done.returncode}), flush=True)
        assert done.returncode == expected, name
        return done

    base = [sys.executable, "-I", "-B", "-X", "utf8"]
    options = ["--rscript", args.rscript, "--groups", "base", "--install"]
    if args.wheelhouse:
        options += ["--wheelhouse", str(Path(args.wheelhouse).resolve())]

    def sentinels(project):
        keep = [project / "user-project.txt", project / ".agents/skills/user-peer/SKILL.md"]
        for p in keep:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"preserve user project and peer skill\n")
        return {p: sha(p) for p in keep}

    def preserved(snapshot):
        assert all(p.is_file() and sha(p) == digest for p, digest in snapshot.items())

    def skill(project):
        return project / ".agents/skills/ye1-clinical-analysis"

    project = work / "customer-project-clean"
    project.mkdir()
    keep = sentinels(project)
    done = run("fresh-install", base + [str(TOOLKIT / "setup_windows.py"),
                                      "--project", str(project), *options])
    assert b"PROJECT_SKILLS_INSTALLED_AND_RUNTIME_VERIFIED" in done.stdout
    main_skill = skill(project)
    assert len(list((project / ".agents/skills").glob("*/SKILL.md"))) == 49
    old_logs = {p: sha(p) for p in (main_skill / "install-logs").rglob("*") if p.is_file()}
    profile = json.loads((main_skill / ".runtime/toolkit-profile.json").read_text(encoding="utf-8"))
    bound = {Path(p): digest for p, digest in
             {**profile["foundation_files"], **profile["config_files"]}.items()}
    done = run("repeat-install", base + [str(main_skill / "scripts/install_windows.py"), *options])
    assert b"INSTALLED_AND_VERIFIED" in done.stdout
    preserved(keep); preserved(old_logs); preserved(bound)
    assert not list((main_skill / "install-logs").glob("*/python-ensurepip.log"))

    # Deterministic interruption fixture, after deployment and ownership state
    # creation but before venv's pip bootstrap. No completed runtime is borrowed.
    partial = work / "customer-project-partial"
    partial.mkdir()
    partial_keep = sentinels(partial)
    manifest = json.loads((TOOLKIT / "toolkit-manifest.json").read_text(encoding="utf-8"))
    for relative, digest in manifest["files"].items():
        source = TOOLKIT / relative
        assert sha(source) == digest
        destination = partial / ".agents" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    partial_skill = skill(partial)
    runtime = partial_skill / ".runtime"
    runtime.mkdir()
    state = {"schema_version": "ye1-toolkit-install-state@3.0",
             "product_root": str(partial_skill), "version": manifest["version"],
             "status": "installing", "groups": ["base"]}
    (runtime / "install-state.json").write_text(json.dumps(state), encoding="utf-8")
    run("partial-create", base + ["-m", "venv", "--without-pip", str(runtime / "python")])
    python = runtime / "python/Scripts/python.exe"
    done = run("partial-pip-missing", [str(python), "-I", "-m", "pip", "--version"], expected=1)
    assert b"No module named pip" in done.stderr
    partial_keep.update({p: sha(p) for p in [python, runtime / "python/pyvenv.cfg"]})
    historical_log = partial_skill / "install-logs/interrupted-attempt/evidence.txt"
    historical_log.parent.mkdir(parents=True)
    historical_log.write_bytes(b"previous failed attempt evidence\n")
    partial_keep[historical_log] = sha(historical_log)
    marker = runtime / "python/previous-attempt.txt"
    marker.write_bytes(b"preserve partial venv\n")
    partial_keep[marker] = sha(marker)
    done = run("partial-recover", base + [str(partial_skill / "scripts/install_windows.py"), *options])
    assert b"INSTALLED_AND_VERIFIED" in done.stdout
    preserved(partial_keep)
    assert json.loads((runtime / "install-state.json").read_text(encoding="utf-8"))["status"] == "complete"
    logs = next((partial_skill / "install-logs").glob("*/python-ensurepip.log")).parent
    assert b"No module named pip" in (logs / "python-pip-check.log").read_bytes()
    assert b"pip " in (logs / "python-pip-recheck.log").read_bytes()
    for label, installed in [("fresh", main_skill), ("recovered", partial_skill)]:
        done = run(label + "-doctor", base + [str(installed / "scripts/toolkit.py"),
                   "doctor", "--method", "survival.kaplan_meier"])
        assert b"WINDOWS_TOOLKIT_RUNTIME_READY" in done.stdout
    result = {"status": "PASS", "cases": ["fresh", "repeat", "missing-pip-recovery"],
              "project_data_peer_skills_partial_venv_and_previous_logs_preserved": True,
              "python": sys.version, "platform": platform.platform(),
              "power_shell_or_host_security_settings_changed": False}
    (work / "result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
