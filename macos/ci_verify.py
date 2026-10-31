"""Validate actual PBC and synthetic ML artifacts, emit only aggregate proof."""
from pathlib import Path
import hashlib, json, os, shutil, sys

area, main = map(Path, sys.argv[1:3])
pbc = json.loads((area / 'public-pbc/acceptance.json').read_text(encoding='utf-8'))
assert pbc['status'] == 'PUBLIC_FIXTURE_ACCEPTANCE_PASSED'
assert pbc['source_sha256'] == '92cc9dc9f6e8b95e2bedc9f7bab201755e761795374765bdd3c466b2d516d151'
assert pbc['png_dimensions'] == [1300, 820]
trees = json.loads((area / 'trees/receipt.json').read_text(encoding='utf-8'))['results']
assert len(trees) == 2 and all(x['status'] == 'PASS' and x['figures'] >= 3 for x in trees)
results = json.loads((area / 'regression/receipt.json').read_text(encoding='utf-8'))['results']
assert len(results) == 9 and all(x['status'] == 'PASS' for x in results)
public = area / 'public-proof'
public.mkdir()
shutil.copy2(area / 'public-pbc/km-step.png', public / 'public-pbc-km.png')
for result in trees:
    directory = Path(result['output']) / 'figures'
    for plot in directory.glob('*.png'):
        shutil.copy2(plot, public / (result['method'] + '-' + plot.name))
record = {'status': 'PASS', 'platform': 'macOS arm64', 'network': 'per-process sandbox denies network',
          'source_commit': os.environ['GITHUB_SHA'],
          'ci_url': os.environ['GITHUB_SERVER_URL'] + '/' + os.environ['GITHUB_REPOSITORY'] + '/actions/runs/' + os.environ['GITHUB_RUN_ID'],
          'public_pbc': {'status': pbc['status'], 'fixture': pbc['fixture_id'],
                         'numerical_comparison': pbc['numerical_comparison'], 'png_dimensions': pbc['png_dimensions']},
          'synthetic_ml': [{'method': x['method'], 'figures': x['figures']} for x in trees],
          'synthetic_regression_suites': [{'suite': x['suite'], 'status': x['status']} for x in results],
          'repeat_setup': 'preserved_existing_skills', 'scientific_review': 'pending'}
(public / 'RESULT.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
