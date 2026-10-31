"""Keep existing regression fixtures while selecting the platform venv path."""
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'tests/regression'
old = b"MAIN/'.runtime/python/Scripts/python.exe'"
new = b"MAIN/('.runtime/python/bin/python3' if sys.platform=='darwin' else '.runtime/python/Scripts/python.exe')"
files = [path for path in root.glob('*.py') if old in path.read_bytes()]
if len(files) != 7:
    raise ValueError(f'expected seven unmodified regression paths, found {len(files)}')
for path in files:
    before = path.read_bytes()
    assert before.count(old) == 1
    path.write_bytes(before.replace(old, new, 1))
    print(path.name)
