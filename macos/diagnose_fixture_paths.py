"""Report which public-fixture path and ancestor is linked, without data rows."""
from pathlib import Path
import argparse, json

p = argparse.ArgumentParser()
p.add_argument('--source', required=True)
p.add_argument('--output', required=True)
p.add_argument('--rscript', required=True)
a = p.parse_args()
records = []
for label in ('source', 'output', 'rscript'):
    path = Path(getattr(a, label)).absolute()
    links = [str(part) for part in (path, *path.parents)
             if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction())]
    records.append({'kind': label, 'exists': path.exists(), 'linked_components': links,
                    'resolved_path': str(path.resolve())})
print(json.dumps({'schema': 'clinical-fixture-path-diagnostic@1.0', 'paths': records}, ensure_ascii=False))
