"""Save only our platform guard edits as Mac overlays; restore source bytes from HEAD."""
from pathlib import Path
import argparse, subprocess

root = Path(__file__).resolve().parents[1]
prefix = Path('windows-v03/toolkit/skills/ye1-clinical-analysis/_shared/clinical_analysis')
files = [
    'integration/core/src/clinanalysis/R/clinical_common.R',
    'integration/core/src/clinanalysis/R/clinical_cox_penalized_v10.R',
    'integration/core/tools/probe_runtime_v08.R',
    'integration/core/tools/probe_runtime_v10.R',
    'modules/latent_longitudinal/formal_runtime.py',
    'modules/latent_longitudinal/module.py',
    'configure_runtime.py',
]
overlay = root / 'macos/overlays'
if overlay.exists():
    raise ValueError('existing overlay preserved')
parser = argparse.ArgumentParser()
parser.add_argument('--evidence', type=Path, required=True)
args = parser.parse_args()
patch = subprocess.check_output(['git', '-C', str(root), 'diff', '--binary', '--', *(str(prefix / p) for p in files)])
with args.evidence.open('xb') as out:
    out.write(patch)
for relative in files:
    path = root / prefix / relative
    original = subprocess.check_output(['git', '-C', str(root), 'show', 'HEAD:' + (prefix / relative).as_posix()])
    changed = path.read_bytes()
    if changed == original:
        raise ValueError('expected platform guard change missing: ' + relative)
    destination = overlay / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as out:
        out.write(changed)
    path.write_bytes(original)
    assert path.read_bytes() == original
print('Saved seven Mac platform-guard overlays; restored shared backend source bytes from branch HEAD.')
