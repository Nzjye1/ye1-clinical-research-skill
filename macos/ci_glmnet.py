"""Prepare locked R binaries for a real Apple Silicon glmnet build probe."""
from pathlib import Path
import hashlib, json, os, urllib.request

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / 'macos/r-arm64-lock.json').read_text(encoding='utf-8'))
cache = Path(os.environ['RUNNER_TEMP']) / 'clinical-glmnet-cache'
cache.mkdir(exist_ok=False)
needed = {'Rcpp', 'foreach', 'iterators', 'shape'}
items = [a for a in lock['binary_packages'] if a['name'] in needed] + lock['build_dependencies']
assert len(items) == 5
for item in items:
    url = item['url']
    assert url.startswith('https://cran.r-project.org/')
    with urllib.request.urlopen(url, timeout=120) as response:
        raw = response.read()
    assert hashlib.sha256(raw).hexdigest() == item['sha256']
    with (cache / item['filename']).open('xb') as out:
        out.write(raw)
    print(item['name'], item['version'], 'official binary verified', flush=True)
source = root / 'windows-v03/toolkit/skills/ye1-clinical-analysis/third-party/r/glmnet_5.1.tar.gz'
assert hashlib.sha256(source.read_bytes()).hexdigest() == lock['source_build_required'][0]['source']['sha256']
print('glmnet source verified', flush=True)
