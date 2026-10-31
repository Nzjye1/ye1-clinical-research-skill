#!/bin/bash
# Install official foundations only when absent, then use the project installer.
set -euo pipefail
SRC=$(cd "$(dirname "$0")" && pwd -P)
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'Apple Silicon macOS is required.' >&2; exit 2; }
[[ $(sw_vers -productVersion | cut -d. -f1) -ge 14 ]] || { echo 'macOS 14 or newer is required.' >&2; exit 2; }
[[ $# -ge 1 && -d "$1" ]] || { echo 'Usage: bash setup-online.sh EXISTING_PROJECT [--method METHOD | --all]' >&2; exit 2; }
PROJECT=$(cd "$1" && pwd -P); shift
BOOT="$PROJECT/.ye1-clinical-bootstrap"
[[ ! -L "$BOOT" ]] || { echo 'Bootstrap path cannot be a symbolic link.' >&2; exit 2; }
if [[ -e "$BOOT" && ! -f "$BOOT/owner.txt" ]]; then echo 'Existing bootstrap directory is not owned by this installer.' >&2; exit 2; fi
mkdir -p "$BOOT/cache" "$BOOT/logs"
[[ ! -L "$BOOT/cache" ]] || { echo 'Cache path cannot be a symbolic link.' >&2; exit 2; }
if [[ -f "$BOOT/owner.txt" ]]; then
  [[ "$(cat "$BOOT/owner.txt")" == ye1-clinical-macos-arm64-v1 ]] || { echo 'Bootstrap owner mismatch.' >&2; exit 2; }
else
  printf '%s\n' ye1-clinical-macos-arm64-v1 > "$BOOT/owner.txt"
fi

acquire() {
  local url="$1" sha="$2" name="$3" target="$BOOT/cache/${2}_${3}" temp
  if [[ -f "$target" ]]; then
    [[ "$(shasum -a 256 "$target" | awk '{print $1}')" == "$sha" ]] || { echo "Cached hash mismatch: $name" >&2; return 2; }
    printf '%s' "$target"; return
  fi
  temp=$(mktemp "$BOOT/cache/.download.XXXXXXXX")
  if [[ -n "${YE1_CLINICAL_OFFLINE_CACHE:-}" ]]; then
    cp "$YE1_CLINICAL_OFFLINE_CACHE/bootstrap/${sha}_${name}" "$temp"
  else
    /usr/bin/curl --fail --silent --show-error --location --proto '=https' --tlsv1.2 "$url" -o "$temp"
  fi
  [[ "$(shasum -a 256 "$temp" | awk '{print $1}')" == "$sha" ]] || { echo "Download hash mismatch: $name; partial retained at $temp" >&2; return 2; }
  mv "$temp" "$target"
  printf '%s' "$target"
}

PY=/Library/Frameworks/Python.framework/Versions/3.14/bin/python3.14
RS=/Library/Frameworks/R.framework/Resources/bin/Rscript
if [[ -e "$PY" ]]; then
  [[ "$("$PY" -I -c 'import platform;print(platform.python_version())')" == 3.14.5 ]] || { echo 'Existing Python 3.14 framework differs; obtain support before changing it.' >&2; exit 2; }
else
  pkg=$(acquire 'https://www.python.org/ftp/python/3.14.5/python-3.14.5-macos11.pkg' b28a8dc33c456dd06c97024697d63ca916cfb494594c06fa3e4ef4d41fa82335 python-3.14.5-macos11.pkg)
  /usr/sbin/pkgutil --check-signature "$pkg" | tee "$BOOT/logs/python-signature.txt"
  grep -q 'Python Software Foundation' "$BOOT/logs/python-signature.txt"
  if [[ $(id -u) -eq 0 ]]; then /usr/sbin/installer -pkg "$pkg" -target /; else sudo /usr/sbin/installer -pkg "$pkg" -target /; fi
fi
if [[ -e "$RS" ]]; then
  [[ "$("$RS" --vanilla -e "cat(as.character(getRversion()),R.version\$arch,sep='|')")" == '4.6.1|aarch64' ]] || { echo 'Existing R framework differs; obtain support before changing it.' >&2; exit 2; }
else
  pkg=$(acquire 'https://cran.r-project.org/bin/macosx/sonoma-arm64/base/R-4.6.1-arm64.pkg' 67f6eea4ced4ce48f0a0d4fa3a1cac43d1859a05a88993ee3dff7c52e7edbc4b R-4.6.1-arm64.pkg)
  /usr/sbin/pkgutil --check-signature "$pkg" | tee "$BOOT/logs/r-signature.txt"
  grep -q 'Developer ID Installer: Simon Urbanek (VZLD955F6P)' "$BOOT/logs/r-signature.txt"
  if [[ $(id -u) -eq 0 ]]; then /usr/sbin/installer -pkg "$pkg" -target /; else sudo /usr/sbin/installer -pkg "$pkg" -target /; fi
fi

cert=$(acquire 'https://files.pythonhosted.org/packages/32/d1/a3652fe2c19134d0d15922177821d863cbd7e842d53a21bbe7e8e3a1b5ac/certifi-2026.10.23-py3-none-any.whl' e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1 certifi-2026.10.23-py3-none-any.whl)
"$PY" -I -B -c 'import sys,zipfile,pathlib; pathlib.Path(sys.argv[2]).write_bytes(zipfile.ZipFile(sys.argv[1]).read("certifi/cacert.pem"))' "$cert" "$BOOT/certifi.pem"
export SSL_CERT_FILE="$BOOT/certifi.pem"
exec "$PY" -I -B -X utf8 "$SRC/setup_macos.py" --project "$PROJECT" --rscript "$RS" "$@" --install
