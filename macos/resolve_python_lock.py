"""Bind already downloaded Apple Silicon wheels to official PyPI metadata."""
from concurrent.futures import ThreadPoolExecutor
from email.parser import BytesParser
from pathlib import Path
import argparse, hashlib, json, urllib.request, zipfile


def inspect(path):
    with zipfile.ZipFile(path) as archive:
        metadata = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        if len(metadata) != 1:
            raise ValueError(f'wheel metadata count: {path.name}')
        parsed = BytesParser().parsebytes(archive.read(metadata[0]))
    name, version = parsed['Name'], parsed['Version']
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    with urllib.request.urlopen(url, timeout=45) as response:
        data = json.load(response)
    entries = [x for x in data['urls'] if x['filename'] == path.name]
    if len(entries) != 1:
        raise ValueError(f'official PyPI filename unavailable: {path.name}')
    entry = entries[0]
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if entry['digests']['sha256'] != digest or entry['size'] != path.stat().st_size:
        raise ValueError(f'official PyPI bytes mismatch: {path.name}')
    return {'name': name, 'version': version, 'filename': path.name,
            'url': entry['url'], 'sha256': digest, 'bytes': entry['size']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--wheelhouse', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    wheels = sorted(args.wheelhouse.glob('*.whl'))
    if len(wheels) != 26 or args.output.exists():
        raise ValueError('expected 26 wheels and a new output file')
    with ThreadPoolExecutor(max_workers=6) as pool:
        artifacts = list(pool.map(inspect, wheels))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump({'schema': 'clinical-macos-arm64-python-wheels@1.0',
                   'python': '3.14.5', 'platform': 'macosx-arm64',
                   'artifacts': artifacts}, f, indent=2, ensure_ascii=False)
        f.write('\n')
    print(json.dumps({'status': 'PASS', 'official_metadata_matches': len(artifacts)}))


if __name__ == '__main__':
    main()
