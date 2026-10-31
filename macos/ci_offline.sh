#!/bin/bash
set -euo pipefail
TOOLKIT="$1"; CACHE="$2"; PROJECT="$3"; AREA="$4"
export LANG=en_US.UTF-8 LC_CTYPE=en_US.UTF-8
export YE1_CLINICAL_OFFLINE_CACHE="$CACHE"
mkdir -p "$PROJECT" "$AREA"
# Verify the per-process sandbox actually denies network before installing or
# analyzing. TEST-NET-1 is reserved; no customer data is sent.
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -I -B -c 'import errno,socket
try:
    s=socket.socket();s.settimeout(2);s.connect(("192.0.2.1",443))
except OSError as e:
    assert e.errno in (errno.EPERM,errno.EACCES), ("unexpected network denial",e.errno)
    print("PASS network denied by process sandbox")
else:
    raise SystemExit("network was not denied")'
bash "$TOOLKIT/setup-offline.sh" "$PROJECT" --all
MAIN="$PROJECT/.agents/skills/ye1-clinical-analysis"
PY="$MAIN/.runtime/python/bin/python3"
RS=/Library/Frameworks/R.framework/Resources/bin/Rscript
"$PY" -I -B -X utf8 "$MAIN/scripts/toolkit.py" doctor --method baseline.table1
"$PY" -I -B -X utf8 "$MAIN/scripts/toolkit.py" doctor --method prediction.binary.random_forest

# Repeated setup must reject existing named Skills without replacing them.
set +e
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -I -B -X utf8 "$TOOLKIT/setup_macos.py" --project "$PROJECT" --rscript "$RS" > "$AREA/repeat-setup.json" 2>&1
result=$?
set -e
[[ "$result" -eq 2 ]]
grep -q 'EXISTING_NAMED_SKILL_PRESERVED_USE_NEW_PROJECT_OR_REVIEW_UPDATE' "$AREA/repeat-setup.json"

# Existing installed dependencies are rechecked and can be reinstalled offline.
/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14 -I -B -X utf8 "$MAIN/scripts/install_macos.py" --rscript "$RS" --groups base --wheelhouse "$CACHE/wheels" --install

# Public survival PBC: only the registered time/status projection is generated.
"$RS" --vanilla "$MAIN/examples/make_public_pbc.R" "$AREA/pbc-time-status.csv" /Library/Frameworks/R.framework/Resources/library
# The Apple framework's Resources alias is a symlink. Use the canonical
# Rscript already bound and hash-checked by the installed runtime profile;
# the public-fixture adapter continues to reject links in all three inputs.
BOUND_RS=$("$PY" -I -B -c 'import json,sys; print(json.load(open(sys.argv[1],encoding="utf-8"))["rscript"])' "$MAIN/.runtime/toolkit-profile.json")
"$PY" -I -B -X utf8 macos/diagnose_fixture_paths.py --source "$AREA/pbc-time-status.csv" --output "$AREA/public-pbc" --rscript "$BOUND_RS"
"$PY" -I -B -X utf8 "$MAIN/scripts/toolkit.py" public-fixture --fixture survival-pbc-3.8-6-composite-km-v1 --source "$AREA/pbc-time-status.csv" --output "$AREA/public-pbc" --rscript "$BOUND_RS"

# Actual synthetic RF/HGB figure export, then the existing full method suites.
"$PY" -I -B -X utf8 tests/regression/test_module_forward.py --package "$MAIN" --area "$AREA/trees" --methods prediction.binary.random_forest prediction.binary.hist_gradient_boosting
"$PY" -I -B -X utf8 tests/run_regression.py --package "$MAIN" --area "$AREA/regression"
"$PY" -I -B -X utf8 tests/test_optional_exports_and_repeat.py --package "$MAIN" --workdir "$AREA/repeat-tests" -v
"$PY" -I -B -X utf8 macos/ci_verify.py "$AREA" "$MAIN"
