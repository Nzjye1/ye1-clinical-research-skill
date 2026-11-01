"""Small synthetic checks for archive identity and CI proof rejection."""
from pathlib import Path
from contextlib import nullcontext
import hashlib, json, subprocess, sys, zipfile

tool = Path(__file__).resolve().with_name('package_delivery.py')
target = Path(sys.argv[1]).resolve()
target.mkdir(parents=True, exist_ok=False)
with nullcontext(target) as directory:
    root = Path(directory)
    toolkit = root / 'toolkit'
    (toolkit / 'skills').mkdir(parents=True)
    (toolkit / 'toolkit-manifest.json').write_text('{"test":"synthetic"}\n', encoding='utf-8')
    (toolkit / 'skills/example.txt').write_text('synthetic-only\n', encoding='utf-8')
    (root / 'ci-toolkit.json').write_bytes((toolkit / 'toolkit-manifest.json').read_bytes())
    (root / 'runtime.json').write_text('{"inputs":"synthetic"}\n', encoding='utf-8')
    (root / 'ci-runtime.json').write_bytes((root / 'runtime.json').read_bytes())
    commit, url = 'f' * 40, 'https://example.invalid/actions/runs/1'
    proof = {'status':'PASS', 'source_commit':commit, 'ci_url':url,
             'public_pbc':{'status':'PUBLIC_FIXTURE_ACCEPTANCE_PASSED'},
             'synthetic_regression_suites':[{'status':'PASS'} for _ in range(9)]}
    (root / 'proof.json').write_text(json.dumps(proof), encoding='utf-8')
    offline = root / 'offline'
    (offline / 'offline-cache/wheels').mkdir(parents=True)
    (offline / 'offline-cache/wheels/example.whl').write_bytes(b'synthetic-wheel')
    common = [sys.executable, '-I', '-B', str(tool), '--toolkit', str(toolkit),
              '--source-commit', commit, '--ci-url', url, '--ci-proof', str(root/'proof.json'),
              '--ci-toolkit-manifest', str(root/'ci-toolkit.json'), '--runtime-manifest', str(root/'runtime.json'),
              '--ci-runtime-manifest', str(root/'ci-runtime.json')]
    for kind in ('online', 'offline'):
        output = root / (kind + '.zip')
        args = common + ['--kind', kind, '--output', str(output)]
        if kind == 'offline':
            args += ['--offline-preparation', str(offline)]
        subprocess.run(args, check=True, capture_output=True)
        receipt = json.loads(output.with_suffix('.receipt.json').read_text(encoding='utf-8'))
        assert receipt['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
        with zipfile.ZipFile(output) as archive:
            assert archive.testzip() is None and archive.read('toolkit/skills/example.txt') == (toolkit / 'skills/example.txt').read_bytes()
            if kind == 'offline':
                assert archive.read('offline-cache/wheels/example.whl') == b'synthetic-wheel'
    focused = {'status':'PASS', 'schema_version':'clinical-noninteractive-proof@1.0',
               'source_commit':commit, 'ci_url':url,
               'noninteractive_suites':[{'suite':s,'status':'PASS'} for s in ('core','compat','module','legacy','retired')]}
    (root / 'proof.json').write_text(json.dumps(focused), encoding='utf-8')
    subprocess.run(common + ['--kind','online','--output',str(root/'focused.zip')], check=True, capture_output=True)
    focused['noninteractive_suites'].pop()
    (root / 'proof.json').write_text(json.dumps(focused), encoding='utf-8')
    assert subprocess.run(common + ['--kind','online','--output',str(root/'incomplete.zip')], capture_output=True).returncode != 0
    (root / 'proof.json').write_text(json.dumps(proof), encoding='utf-8')
    (root / 'ci-runtime.json').write_text('changed\n', encoding='utf-8')
    refused = root / 'refused.zip'
    result = subprocess.run(common + ['--kind','online','--output',str(refused)], capture_output=True)
    assert result.returncode != 0 and not refused.exists()
print('PASS synthetic online/offline packaging and mismatched CI proof rejection')
