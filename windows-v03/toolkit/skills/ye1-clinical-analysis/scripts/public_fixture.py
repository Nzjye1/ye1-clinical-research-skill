"""Offline acceptance adapter for one explicitly allowlisted public fixture.

This is a separate caller of the unchanged survival numerical owner. It does
not create or impersonate a customer study task, consent, or export grant.
"""
from pathlib import Path
import csv
import hashlib
import importlib.metadata
import io
import json
import math
import platform
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "survival-pbc-3.8-6-composite-km-v1"
SOURCE_SHA256 = "92cc9dc9f6e8b95e2bedc9f7bab201755e761795374765bdd3c466b2d516d151"
OWNER = ROOT / "_shared/clinical_analysis/integration/core/python/clinical_methods/survival.py"
OWNER_SHA256 = "c2742f940e44f440b2d064ae1cd51c300c8e35e1a54253620b074b2b4239684d"
GRID = [0, 365, 730, 1095, 1825, 3650]
SOURCE_URL = "https://github.com/therneau/survival"
LICENSE = "LGPL (>= 2), survival 3.8-6 package DESCRIPTION; no separate pbc license recorded"


class FixtureBlocked(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(ok, code):
    if not ok:
        raise FixtureBlocked(code)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(path):
    path = Path(path).absolute()
    need(not any(p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction())
                 for p in (path, *path.parents)), "PUBLIC_FIXTURE_LINKED_PATH_REJECTED")
    return path.resolve()


def save(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def table(path, columns, rows):
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(rows)


def compare_reference(actual, reference):
    """Compare every observed time and prespecified time, including risk sets."""
    with reference.open(encoding="utf-8", newline="") as stream:
        expected = list(csv.DictReader(stream))
    need(len(actual) == len(expected), "PUBLIC_FIXTURE_REFERENCE_LENGTH_MISMATCH")
    maximum = 0.0
    for point, row in zip(actual, expected):
        want = [float(row[k]) for k in ("time", "n_at_risk", "survival", "ci_lower", "ci_upper")]
        need(point[:2] == want[:2], "PUBLIC_FIXTURE_REFERENCE_RISK_OR_TIME_MISMATCH")
        for value, target in zip(point[2:], want[2:]):
            need(math.isfinite(target) and abs(value-target) <= 1e-12,
                 "PUBLIC_FIXTURE_REFERENCE_NUMERICAL_MISMATCH")
            maximum = max(maximum, abs(value-target))
    return {"rows_compared": len(actual), "probability_ci_cells_compared": len(actual)*3,
            "absolute_tolerance": 1e-12, "max_absolute_difference": maximum,
            "time_and_risk_sets_exact": True}


def run(fixture, source, output, rscript):
    need(fixture == FIXTURE, "PUBLIC_FIXTURE_NOT_ALLOWLISTED")
    source = safe(source)
    need(source.is_file() and source.stat().st_size == 2845, "PUBLIC_FIXTURE_BYTES_MISMATCH")
    # Hash before decode, schema inspection or source rows. No fallback to real
    # admission, no filename-based trust, and no user-supplied hash or protocol.
    raw = source.read_bytes()
    need(hashlib.sha256(raw).hexdigest() == SOURCE_SHA256, "PUBLIC_FIXTURE_BYTES_MISMATCH")
    need(sha(OWNER) == OWNER_SHA256, "PUBLIC_FIXTURE_NUMERICAL_OWNER_DRIFT")
    output = safe(output)
    need(not output.exists() and output.parent.is_dir() and
         not output.is_relative_to(ROOT) and not source.is_relative_to(output),
         "PUBLIC_FIXTURE_FRESH_EXTERNAL_OUTPUT_REQUIRED")
    rscript = safe(rscript)
    need(rscript.is_file(), "PUBLIC_FIXTURE_EXPLICIT_RSCRIPT_REQUIRED")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8")))
    need(reader.fieldnames == ["time", "status"], "PUBLIC_FIXTURE_SCHEMA_MISMATCH")
    records = list(reader)
    need(len(records) == 418, "PUBLIC_FIXTURE_ROW_COUNT_MISMATCH")
    # Public case identifiers and all other clinical columns were excluded by
    # the deterministic local fixture generator. Ordinals remain in memory.
    rows = [{"ordinal": str(i), "time": r["time"],
             "event": "1" if r["status"] in {"1", "2"} else "0"}
            for i, r in enumerate(records)]
    spec = dict(method="kaplan_meier", subject_id="ordinal", time="time", status="event",
                time_unit="day", time_zero_definition="Registration in the Mayo PBC study",
                event_definition="First death or liver transplantation; source status 1 or 2",
                censoring_definition="Source status 0: no composite event at recorded follow-up end; study analysis July 1986",
                event_code="1", censor_code="0", independent_subjects=True,
                missing_policy="complete_case", covariates=[], evaluation_times=GRID)
    sys.path.insert(0, str(OWNER.parents[1]))
    from clinical_methods import survival
    result = survival.analyze(rows, spec)
    need(result.get("status") == "COMPUTED_REVIEW_PENDING", "PUBLIC_FIXTURE_OWNER_REJECTED")
    display_spec = {**spec, "evaluation_times": sorted({0, *[float(r["time"]) for r in rows]})}
    display = survival.analyze(rows, display_spec)
    need(display.get("status") == "COMPUTED_REVIEW_PENDING", "PUBLIC_FIXTURE_DISPLAY_REJECTED")
    output.mkdir()
    result.update(schema_version="ye1-public-fixture-result@1.0", data_origin="public_fixture",
                  fixture_id=FIXTURE, task_purpose="public_fixture_acceptance", test_only=True,
                  source_sha256=SOURCE_SHA256, numerical_owner_sha256=OWNER_SHA256,
                  method_id="survival.kaplan_meier", scientific_review="pending",
                  ordinary_customer_admission_exercised=False, export_grants_added=0)
    save(output / "result.json", result)
    columns = ["time", "n_at_risk", "survival", "ci_lower", "ci_upper"]
    def values(points):
        return [[p["time"], p["at_risk_before_time"], p["event_free_probability"],
                 *p["event_free_ci95"]] for p in points]
    table(output / "survival_curve.csv", columns, values(result["curves"]))
    table(output / "km-step.csv", columns, values(display["curves"]))
    censor_times = {float(r["time"]) for r in rows if r["event"] == "0"}
    table(output / "censor-marks.csv", ["time", "survival"],
          [[p["time"], p["event_free_probability"]] for p in display["curves"] if p["time"] in censor_times])
    plot = ROOT / "scripts/plot_km.R"
    command = [str(rscript), "--vanilla", str(plot), str(output / "km-step.csv"),
               str(output / "censor-marks.csv"), str(output / "km-step.png"), "day", "public_fixture"]
    from runtime_windows import env
    with (output / "plot.log").open("xb") as log:
        done = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=log,
                              stderr=subprocess.STDOUT, env=env(), timeout=60)
    save(output / "plot-command.json", {"command": command, "exit_code": done.returncode})
    need(done.returncode == 0 and (output / "km-step.png").is_file(), "PUBLIC_FIXTURE_PLOT_FAILED")
    reference_script = ROOT / "scripts/verify_public_pbc.R"
    # Include the analysis grid as well as every observed time. No extrapolation.
    all_points = survival.analyze(rows, {**spec, "evaluation_times": sorted({*GRID, *display_spec["evaluation_times"]})})
    reference_grid = output / "reference-grid.csv"
    table(reference_grid, columns, values(all_points["curves"]))
    reference = output / "r-survfit-reference.csv"
    reference_command = [str(rscript), "--vanilla", str(reference_script), str(source), str(reference_grid), str(reference)]
    with (output / "reference.log").open("xb") as log:
        checked = subprocess.run(reference_command, stdin=subprocess.DEVNULL, stdout=log,
                                 stderr=subprocess.STDOUT, env=env(), timeout=60)
    save(output / "reference-command.json", {"command": reference_command, "exit_code": checked.returncode})
    need(checked.returncode == 0 and reference.is_file(), "PUBLIC_FIXTURE_REFERENCE_FAILED")
    need(sha(source) == SOURCE_SHA256, "PUBLIC_FIXTURE_SOURCE_CHANGED")
    comparison = compare_reference(values(all_points["curves"]), reference)
    png = (output / "km-step.png").read_bytes()
    need(len(png) > 1000 and png[:8] == b"\x89PNG\r\n\x1a\n" and
         struct.unpack(">II", png[16:24]) == (1300, 820), "PUBLIC_FIXTURE_PNG_INVALID")
    lines = ["# 公开固定夹具 KM 软件验收", "", "survival::pbc 3.8-6；公开教学数据，非合成数据。", "",
             "从登记日起计算死亡或肝移植复合事件未发生概率；不是死亡单一终点或治疗比较。", "",
             "仅检验固定夹具的数值与产物；普通客户确认全链、临床适用性及可发表性仍未由本次证明。", "",
             "418条记录包括312名随机试验参与者及106名未随机随访者；这里仅汇总随访，不比较治疗或推断因果。", "",
             f"输入/使用 {result['n_total']}/{result['n_used']}；事件 {result['target_events']}；删失 {result['censored']}；缺失排除 {result['n_excluded_missing']}。", "",
             "时间零点：Mayo PBC研究登记日。原结局1=移植、2=死亡均作为复合事件，0=右删失。", "",
             "随访时间来自登记日至死亡、移植或1986年7月研究分析；完整案例，不填补。", "",
             "|天|风险集|事件未发生概率|95%CI下界|95%CI上界|", "|---:|---:|---:|---:|---:|"]
    for p in values(result["curves"]):
        lines.append("|" + "|".join(format(x, ".10g") for x in p) + "|")
    lines += ["", "[完整精度表](survival_curve.csv)", "", "![完整KM阶梯图](km-step.png)", "",
              "风险集在时点事件处理前计数；同刻先事件后删失。Greenwood log-log逐点95%区间。", "",
              "需独立右删失假设；没有因果或临床有效性结论。移植未被当作死亡分析的普通删失。", "",
              "来源、许可与再生方法见工具箱 references/PUBLIC-FIXTURES.md。", "",
              f"来源：{SOURCE_URL}；survival 3.8-6 / pbc；包声明许可 LGPL (>= 2)。", "",
              f"固定两列CSV SHA-256：`{SOURCE_SHA256}`。", "",
              "独立核对：R survival::survfit 3.8-6，log-log 95%区间；预定时点及全部观察时点逐项比较，绝对容差1e-12。", "",
              "软件验收通过须同时满足独立数值比较与产物结构检查；该状态不等于人工图表审阅或科学复核完成。", "",
              "科学复核 pending；本次不创建人工确认记录或外发授权，不自动上传任何产物。", ""]
    with (output / "报告.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    save(output / "acceptance.json", {
        "schema_version": "ye1-public-fixture-acceptance@1.0",
        "status": "PUBLIC_FIXTURE_ACCEPTANCE_PASSED", "test_only": True,
        "fixture_id": FIXTURE, "source_sha256": SOURCE_SHA256,
        "source_url": SOURCE_URL, "license": LICENSE,
        "numerical_comparison": comparison, "png_dimensions": [1300, 820],
        "report_created": True, "scientific_review": "pending",
        "human_visual_review": "not_automated", "ordinary_customer_admission_exercised": False,
        "reference_implementation": "R survival::survfit 3.8-6 conf.type=log-log",
        "reference_script_sha256": sha(reference_script)})
    files = {p.name: sha(p) for p in output.iterdir() if p.is_file()}
    save(output / "receipt.json", dict(schema_version="ye1-public-fixture-receipt@1.0", fixture_id=FIXTURE,
         source_sha256=SOURCE_SHA256, specification=spec, data_origin="public_fixture", test_only=True,
         owner_path=OWNER.relative_to(ROOT).as_posix(), numerical_owner_sha256=sha(OWNER),
         adapter_sha256=sha(Path(__file__)), plot_script_sha256=sha(plot),
         reference_script_sha256=sha(reference_script), source_url=SOURCE_URL, license=LICENSE,
         python=dict(version=platform.python_version(), executable=sys.executable,
                     executable_sha256=sha(sys.executable),
                     packages={p: importlib.metadata.version(p) for p in ("numpy", "scipy")}),
         rscript=dict(path=str(rscript), sha256=sha(rscript)), platform=platform.platform(), files=files,
         network_action=False, network_isolation="not_provided", human_confirmation_created=False,
         customer_data_accepted=False, export_grants_added=0))
    return {"status": "PUBLIC_FIXTURE_ACCEPTANCE_PASSED", "fixture_id": FIXTURE,
            "output": str(output), "scientific_review": "pending", "data_sent": False}
