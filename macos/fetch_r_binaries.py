"""Fetch the clinical fixed R package versions from CRAN macOS arm64."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse, hashlib, io, json, tarfile, urllib.request

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'windows-v03/toolkit/skills/ye1-clinical-analysis/runtime-spec.json'


def fetch(package, directory):
    name, version = package['name'], package['version']
    source_version = package.get('source_version', version)
    filename = f'{name}_{source_version}.tgz'
    url = 'https://cran.r-project.org/bin/macosx/sonoma-arm64/contrib/4.6/' + filename
    path = directory / filename
    try:
        with urllib.request.urlopen(url, timeout=90) as response:
            raw = response.read()
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
            descriptions = [m for m in archive.getmembers() if m.name == f'{name}/DESCRIPTION']
            if len(descriptions) != 1:
                raise ValueError('DESCRIPTION missing')
            description = archive.extractfile(descriptions[0]).read().decode('utf-8', 'replace')
        fields = dict(line.split(':', 1) for line in description.splitlines() if ': ' in line and not line.startswith((' ', '\t')))
        if fields.get('Package', '').strip() != name or fields.get('Version', '').strip() != source_version:
            raise ValueError('R package identity mismatch')
        with path.open('xb') as out:
            out.write(raw)
        return {'name': name, 'version': version, 'filename': filename, 'url': url,
                'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                'license': fields.get('License', '').strip(), 'status': 'PASS'}
    except Exception as error:
        return {'name': name, 'version': version, 'url': url, 'status': 'FAILED',
                'error': f'{type(error).__name__}: {error}'}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--directory', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    p.add_argument('--names', nargs='+')
    args = p.parse_args()
    args.directory.mkdir(parents=True, exist_ok=False)
    packages = json.loads(SPEC.read_text(encoding='utf-8'))['r_packages']
    if args.names:
        packages = [item for item in packages if item['name'] in args.names]
        if set(args.names) != {item['name'] for item in packages}:
            raise ValueError('unknown package')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda package: fetch(package, args.directory), packages))
    with args.report.open('x', encoding='utf-8') as out:
        json.dump({'schema': 'clinical-macos-r-fetch@1.0', 'artifacts': results}, out, ensure_ascii=False, indent=2)
        out.write('\n')
    failures = [item for item in results if item['status'] != 'PASS']
    print(json.dumps({'passed': len(results)-len(failures), 'failed': failures}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
