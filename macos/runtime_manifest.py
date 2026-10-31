"""Verify and bind the exact offline installation inputs, without local paths."""
from pathlib import Path
import argparse, hashlib, json

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--toolkit', type=Path, required=True)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('existing output preserved')
    bootstrap = json.loads((ROOT / 'macos/bootstrap-lock.json').read_text(encoding='utf-8'))['artifacts']
    wheels = json.loads((ROOT / 'macos/python-arm64-lock.json').read_text(encoding='utf-8'))['artifacts']
    spec = json.loads((args.toolkit / 'skills/ye1-clinical-analysis/runtime-spec.json').read_text(encoding='utf-8'))
    records = []
    for entry in bootstrap:
        relative = 'bootstrap/' + entry['sha256'] + '_' + entry['filename']
        path = args.cache / relative
        if not path.is_file() or path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise ValueError('bootstrap drift: ' + entry['name'])
        records.append({'path': 'offline-cache/' + relative, 'bytes': entry['bytes'], 'sha256': entry['sha256']})
    for entry in wheels:
        relative = 'wheels/' + entry['filename']
        path = args.cache / relative
        if not path.is_file() or path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']:
            raise ValueError('wheel drift: ' + entry['name'])
        records.append({'path': 'offline-cache/' + relative, 'bytes': entry['bytes'], 'sha256': entry['sha256']})
    for entry in spec['r_packages']:
        value = entry['binary']
        relative = 'skills/ye1-clinical-analysis/third-party/r/' + value['filename']
        path = args.toolkit / relative
        if not path.is_file() or path.stat().st_size != value['bytes'] or sha(path) != value['sha256']:
            raise ValueError('R binary drift: ' + entry['name'])
        records.append({'path': 'toolkit/' + relative, 'bytes': value['bytes'], 'sha256': value['sha256']})
    for relative in ('README.md', 'START-HERE.md', 'setup_macos.py', 'setup-online.sh', 'setup-offline.sh', 'toolkit-manifest.json'):
        path = args.toolkit / relative
        records.append({'path': 'toolkit/' + relative, 'bytes': path.stat().st_size, 'sha256': sha(path)})
    result = {'schema': 'clinical-macos-runtime-manifest@1.0', 'product_version': spec['product_version'],
              'artifacts': sorted(records, key=lambda x:x['path'])}
    with args.output.open('x', encoding='utf-8', newline='\n') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps({'status': 'PASS', 'runtime_inputs': len(records), 'manifest_sha256': sha(args.output)}))


if __name__ == '__main__':
    main()
