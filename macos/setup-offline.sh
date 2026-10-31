#!/bin/bash
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd -P)
[[ $# -ge 1 ]] || { echo 'Usage: bash setup-offline.sh EXISTING_PROJECT [--method METHOD | --all]' >&2; exit 2; }
PROJECT="$1"; shift
CACHE=${YE1_CLINICAL_OFFLINE_CACHE:-"$SRC/../offline-cache"}
[[ -d "$CACHE/bootstrap" && -d "$CACHE/wheels" ]] || { echo 'Complete offline-cache is required.' >&2; exit 2; }
export YE1_CLINICAL_OFFLINE_CACHE="$CACHE"
exec bash "$SRC/setup-online.sh" "$PROJECT" --wheelhouse "$CACHE/wheels" "$@"
