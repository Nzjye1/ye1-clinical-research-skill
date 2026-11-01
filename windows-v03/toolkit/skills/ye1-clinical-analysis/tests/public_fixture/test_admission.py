"""Admission regression checks. No customer CSV is opened or consent created.

Run with a Python having the documented base dependencies. --source must name
the exact locally regenerated public fixture, never a customer file.
"""
from pathlib import Path
import argparse
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import public_fixture as fixture
import prepare_task
import toolkit


class Admission(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=WORKDIR)
        self.project = Path(self.temporary.name)
        self.output = self.project / "result"

    def tearDown(self):
        self.temporary.cleanup()

    def reject(self, code, fixture_id=None, source=None, output=None):
        with self.assertRaises(fixture.FixtureBlocked) as error:
            fixture.run(fixture_id or fixture.FIXTURE, source or SOURCE,
                        output or self.output, sys.executable)
        self.assertEqual(error.exception.code, code)
        self.assertFalse(self.output.exists())

    def draft(self, origin="real"):
        task = {"data_origin": origin, "task_purpose": "research_analysis",
                "project_root": str(self.project), "analysis": {"method_id": "survival.kaplan_meier"},
                "execution": {"output_dir": str(self.output)}}
        draft = {"schema_version": "ye1-toolkit-draft@1.0", "method_id": "survival.kaplan_meier",
                 "data_origin": origin, "task_purpose": "research_analysis",
                 "project_root": str(self.project), "local_tables": {}, "task": task}
        path = self.project / "draft.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        return path

    def test_unknown_fixture_rejected_before_source_read(self):
        self.reject("PUBLIC_FIXTURE_NOT_ALLOWLISTED", fixture_id="customer-file", source=self.project/"absent")

    def test_arbitrary_csv_rejected(self):
        source = self.project / "pbc-time-status.csv"
        source.write_bytes(b'"time","status"\n1,1\n')
        self.reject("PUBLIC_FIXTURE_BYTES_MISMATCH", source=source)

    def test_same_length_tampering_rejected(self):
        source = self.project / "same-size.csv"
        raw = bytearray(SOURCE.read_bytes()); raw[-2] = ord("9")
        source.write_bytes(raw)
        self.reject("PUBLIC_FIXTURE_BYTES_MISMATCH", source=source)

    def test_owner_drift_rejected(self):
        owner = self.project / "owner.py"; owner.write_text("# drift", encoding="utf-8")
        with patch.object(fixture, "OWNER", owner):
            self.reject("PUBLIC_FIXTURE_NUMERICAL_OWNER_DRIFT")

    def test_existing_output_preserved(self):
        old = self.project / "old"; old.mkdir(); marker = old / "evidence"; marker.write_bytes(b"keep")
        self.reject("PUBLIC_FIXTURE_FRESH_EXTERNAL_OUTPUT_REQUIRED", output=old)
        self.assertEqual(marker.read_bytes(), b"keep")

    def test_output_inside_skill_rejected(self):
        self.reject("PUBLIC_FIXTURE_FRESH_EXTERNAL_OUTPUT_REQUIRED", output=ROOT/"forbidden-output")

    def test_numerical_mismatch_rejected(self):
        ref = self.project / "reference.csv"
        ref.write_text("time,n_at_risk,survival,ci_lower,ci_upper\n0,418,0.5,1,1\n", encoding="utf-8")
        with self.assertRaisesRegex(fixture.FixtureBlocked, "REFERENCE_NUMERICAL_MISMATCH"):
            fixture.compare_reference([[0,418,1,1,1]], ref)

    def test_noninteractive_real_preparation_needs_no_confirmation(self):
        # Generated fixture bytes are routed through the real-input contract.
        core = ROOT / "_shared/clinical_analysis/integration/core"
        sys.path.insert(0, str(core / "python"))
        from clinical_methods import contracts
        source = self.project / "generated.csv"
        source.write_text("id,x,z,y\na,1,2,3\nb,2,3,4\n", encoding="utf-8")
        task = contracts.make_example_task(source, self.output, core, database="SELF_FILE")
        task.update(schema_version="clinical-study-input@1.0", data_origin="real",
                    task_purpose="research_analysis", project_root=str(self.project), authorization=None)
        task["execution"].update(mode="local", authorization_ref=None, privacy_profile="captured_local_process",
                                 max_rows=1000, max_bytes=2000000, max_decoded_bytes=4000000)
        task["time"]["policy"] = "ordered_observation"
        for item in task["sources"]:
            item.update(source_kind="user_clinical_file", verification_status="local_bytes_bound",
                        source_fingerprint={"$file_sha256": str(source)})
        for view in task["views"]:
            view.update(local_ref=str(source), format="csv", unselected_columns=[], location_policy="project_local",
                        content_hash={"$file_sha256": str(source)})
        draft = {"schema_version":"ye1-toolkit-draft@1.0", "method_id":"association.linear",
                 "data_origin":"real", "task_purpose":"research_analysis", "project_root":str(self.project),
                 "local_tables":{}, "task":task}
        path = self.project / "generated-draft.json"
        path.write_text(json.dumps(draft), encoding="utf-8")
        with patch.object(prepare_task, "check"):
            result = prepare_task.prepare(path)
        prepared = json.loads(Path(result["task"]).read_text(encoding="utf-8"))
        self.assertIsNone(prepared["authorization"])
        self.assertIsNone(prepared["execution"]["authorization_ref"])
        self.assertFalse((self.project / ".ye1-privacy").exists())

    def test_public_origin_not_accepted_by_customer_preparer(self):
        with self.assertRaises(ValueError) as error:
            prepare_task.prepare(self.draft("public_fixture"))
        self.assertEqual(error.exception.code, "ORIGIN_PURPOSE_CONFLICT")

    def test_practice_cannot_authorize_real(self):
        with self.assertRaises(ValueError) as error:
            prepare_task.prepare(self.draft(), practice=True)
        self.assertEqual(error.exception.code, "PRACTICE_CANNOT_AUTHORIZE_REAL_DATA")

    def test_direct_real_run_without_receipt_rejected(self):
        task = {"schema_version": "clinical-study-input@1.0", "data_origin": "real", "sources": []}
        path = self.project / "task.json"; path.write_text(json.dumps(task), encoding="utf-8")
        with patch.object(toolkit, "doctor"), patch.object(toolkit.subprocess, "run") as child:
            with self.assertRaises(toolkit.Blocked) as error:
                toolkit.execute("survival.kaplan_meier", path)
            self.assertEqual(error.exception.code, "LOCAL_PREPARATION_RECEIPT_REQUIRED")
            child.assert_not_called()

    def test_public_origin_not_accepted_by_ordinary_runner(self):
        task = {"schema_version": "clinical-study-input@1.0", "data_origin": "public_fixture"}
        path = self.project / "task.json"; path.write_text(json.dumps(task), encoding="utf-8")
        with patch.object(toolkit, "doctor"):
            with self.assertRaises(toolkit.Blocked) as error:
                toolkit.execute("survival.kaplan_meier", path)
            self.assertEqual(error.exception.code, "DATA_ORIGIN_REQUIRED")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--source", required=True)
    parser.add_argument("--workdir", required=True)
    args, remaining = parser.parse_known_args(); SOURCE = Path(args.source).resolve()
    WORKDIR = Path(args.workdir).resolve()
    if fixture.sha(SOURCE) != fixture.SOURCE_SHA256:
        raise SystemExit("exact public fixture required")
    unittest.main(argv=[sys.argv[0], *remaining])
