#!/bin/bash
set -euo pipefail
TOOLKIT="$1"; CACHE="$2"; PROJECT="$3"; AREA="$4"
export LANG=en_US.UTF-8 LC_CTYPE=en_US.UTF-8
export YE1_CLINICAL_OFFLINE_CACHE="$CACHE"
mkdir -p "$PROJECT" "$AREA"
# Preserve the successful all-groups installation evidence in its earlier
# run. This reproduction installs only the two tree methods' dependencies.
bash "$TOOLKIT/setup-offline.sh" "$PROJECT" --groups base ml plot
MAIN="$PROJECT/.agents/skills/ye1-clinical-analysis"
PY="$MAIN/.runtime/python/bin/python3"
"$PY" -I -B -X utf8 "$MAIN/scripts/toolkit.py" doctor --method prediction.binary.random_forest
"$PY" -I -B -X utf8 tests/regression/test_module_forward.py --package "$MAIN" --area "$AREA/trees" --methods prediction.binary.random_forest prediction.binary.hist_gradient_boosting
