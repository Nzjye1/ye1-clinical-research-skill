"""Parse all Python sources in a staged toolkit without executing them."""
from pathlib import Path
import argparse, ast, json

parser = argparse.ArgumentParser()
parser.add_argument('root', type=Path)
args = parser.parse_args()
files = sorted(args.root.rglob('*.py'))
failures = []
for path in files:
    try:
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    except (SyntaxError, UnicodeError) as error:
        failures.append({'file': path.relative_to(args.root).as_posix(), 'error': str(error)})
print(json.dumps({'files': len(files), 'failures': failures}, ensure_ascii=False, indent=2))
raise SystemExit(bool(failures))
