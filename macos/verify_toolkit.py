"""Read-only check of the assembled Mac toolkit and its source bindings."""
from pathlib import Path
import argparse, hashlib, json


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('toolkit', type=Path)
    args = p.parse_args()
    root = args.toolkit.resolve()
    main = root / 'skills/ye1-clinical-analysis'
    shared = main / '_shared/clinical_analysis'
    core = shared / 'integration/core'
    manifest = json.loads((root / 'toolkit-manifest.json').read_text(encoding='utf-8'))
    for rel, expected in manifest['files'].items():
        path = root / rel
        if not path.is_file() or sha(path) != expected:
            raise ValueError('distribution file drift: ' + rel)
    requirements = json.loads((shared / 'runtime-requirements.json').read_text(encoding='utf-8'))
    for rel, expected in requirements['protected_source_hashes'].items():
        if not (core / rel).is_file() or sha(core / rel) != expected:
            raise ValueError('protected source binding drift: ' + rel)
    original = json.loads((shared / 'integration/module-lock.json').read_text(encoding='utf-8'))
    admitted = json.loads((shared / 'integration/admitted-module-lock.json').read_text(encoding='utf-8'))['modules']
    for module in original['modules']:
        directory = shared / 'modules' / module['directory']
        if sha(directory / module['manifest_path']) != module['manifest_sha256']:
            raise ValueError('module manifest drift: ' + module['registration_id'])
        for key in ('files_sha256', 'supplementary_files_sha256'):
            for rel, expected in module.get(key, {}).items():
                if '/_vendor/' in '/' + rel:
                    continue
                path = directory / rel
                if not path.is_file() or sha(path) != expected:
                    raise ValueError('module source binding drift: ' + module['registration_id'] + '/' + rel)
        entry = admitted[module['registration_id']]
        if entry['legacy_registration_sha256'] != canonical(module):
            raise ValueError('canonical registration drift: ' + module['registration_id'])
        if sha(directory / entry['manifest_path']) != entry['manifest_sha256']:
            raise ValueError('admitted manifest drift: ' + module['registration_id'])
        for rel, expected in entry.get('files_sha256', {}).items():
            path = directory / rel
            if not path.is_file() or sha(path) != expected:
                raise ValueError('admitted source binding drift: ' + module['registration_id'] + '/' + rel)
    print(json.dumps({'status': 'PASS', 'manifest_files': len(manifest['files']),
                      'protected_sources': len(requirements['protected_source_hashes']),
                      'module_registrations': len(original['modules'])}))


if __name__ == '__main__':
    main()
