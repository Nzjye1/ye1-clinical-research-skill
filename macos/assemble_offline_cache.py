"""Assemble independently locked offline runtime and third-party source material."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, shutil, zipfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def copy_verified(source, target, expected, size):
    if not source.is_file() or source.stat().st_size != size or digest(source) != expected:
        raise ValueError('source archive mismatch: ' + source.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('existing output preserved: ' + target.name)
    shutil.copy2(source, target)
    if digest(target) != expected:
        raise ValueError('copied archive mismatch: ' + target.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--bootstrap-source', type=Path, required=True)
    parser.add_argument('--wheel-source', type=Path, required=True)
    parser.add_argument('--python-source', type=Path, required=True)
    parser.add_argument('--certifi-source', type=Path, required=True)
    parser.add_argument('--certifi-report', type=Path, required=True)
    parser.add_argument('--foundation-source', type=Path, required=True)
    parser.add_argument('--supplement', type=Path, required=True)
    parser.add_argument('--meta-zip', type=Path, required=True)
    args = parser.parse_args()
    target = args.output.resolve()
    if target.exists() or target.is_relative_to(ROOT.resolve()):
        raise ValueError('new independent output required')
    target.mkdir(parents=True)
    records = []

    def item(source, relative, record, role):
        dest = target / relative
        copy_verified(source, dest, record['sha256'], record['bytes'])
        records.append({'path': relative.as_posix(), 'name': record.get('name', source.name),
                        'bytes': record['bytes'], 'sha256': record['sha256'],
                        'url': record.get('url'), 'role': role})

    bootstrap = json.loads((ROOT / 'macos/bootstrap-lock.json').read_text(encoding='utf-8'))['artifacts']
    wheels = json.loads((ROOT / 'macos/python-arm64-lock.json').read_text(encoding='utf-8'))['artifacts']
    sources = json.loads((ROOT / 'macos/python-source-lock.json').read_text(encoding='utf-8'))
    certifi = json.loads(args.certifi_report.read_text(encoding='utf-8'))
    if len(bootstrap) != 3 or len(wheels) != 26 or sources['failures'] or len(sources['sources']) != 26 or certifi['failures'] or len(certifi['sources']) != 1:
        raise ValueError('incomplete official runtime or source lock')
    for record in bootstrap:
        name = record['sha256'] + '_' + record['filename']
        item(args.bootstrap_source / name, Path('offline-cache/bootstrap') / name, record, 'foundation or CA bundle')
    for record in wheels:
        item(args.wheel_source / record['filename'], Path('offline-cache/wheels') / record['filename'], record, 'locked Python wheel')
    for record in sources['sources']:
        item(args.python_source / record['filename'], Path('thirdparty-sources/Python') / record['filename'], record, 'official Python dependency source')
    for record in certifi['sources']:
        item(args.certifi_source / record['filename'], Path('thirdparty-sources/Python') / record['filename'], record, 'official bootstrap CA source')

    foundation = json.loads((args.foundation_source / 'R-PYTHON-SOURCE-RECEIPTS.json').read_text(encoding='utf-8-sig'))
    for record in foundation:
        item(args.foundation_source / record['file'], Path('thirdparty-sources/foundations') / record['file'], record, 'official framework source')
    supplemental = json.loads((args.supplement / 'SOURCES.json').read_text(encoding='utf-8-sig'))
    for record in supplemental:
        item(args.supplement / record['filename'], Path('thirdparty-sources/foundations') / record['filename'], record,
             'candidate toolchain source; exact binary correspondence not established')
    shutil.copy2(args.supplement / 'SOURCES.json', target / 'thirdparty-sources/foundations/SOURCES.json')

    # RcppEigen supplies headers for the CI source build; the original source
    # archive is already present in the separately verified Meta offline ZIP.
    member = 'thirdparty-sources/R/RcppEigen_0.3.4.0.2.tar.gz'
    expected = 'ecad7ba2129fd48b7ebb825558d38492ed1f3a8934959e27fcd6688175e542bb'
    with zipfile.ZipFile(args.meta_zip) as archive:
        info = archive.getinfo(member)
        if info.file_size != 1761745:
            raise ValueError('RcppEigen source size mismatch')
        raw = archive.read(info)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('RcppEigen source hash mismatch')
    eigen = target / member
    eigen.parent.mkdir(parents=True, exist_ok=True)
    eigen.write_bytes(raw)
    records.append({'path': member, 'name': 'RcppEigen', 'bytes': len(raw), 'sha256': expected,
                    'url': 'https://cran.r-project.org/src/contrib/RcppEigen_0.3.4.0.2.tar.gz',
                    'role': 'glmnet build dependency source'})

    # Preserve actual license/notice files from each exact Mac wheel, not just
    # the notices from Windows wheels in the original toolkit.
    notices = 0
    for record in wheels + [next(item for item in bootstrap if item['name'].lower() == 'certifi')]:
        filename = record['filename']
        wheel = (target / 'offline-cache/wheels' / filename if record in wheels else
                 target / 'offline-cache/bootstrap' / (record['sha256'] + '_' + filename))
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                rel = PurePosixPath(name)
                if rel.is_absolute() or '..' in rel.parts or name.endswith('/'):
                    continue
                lower = name.lower()
                if '.dist-info/' not in lower or not ('/licenses/' in lower or rel.name.lower().startswith(('license', 'notice', 'copying'))):
                    continue
                out = target / 'thirdparty-notices/Python' / filename / Path(*rel.parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                with out.open('xb') as f:
                    f.write(archive.read(name))
                notices += 1
    if notices == 0:
        raise ValueError('wheel notices not found')

    (target / 'OFFLINE-CACHE-MANIFEST.json').write_text(json.dumps({'schema': 'clinical-macos-offline-inputs@1.0',
        'status': 'prepared; independent installation verification tracked separately', 'artifacts': records,
        'wheel_notice_files': notices, 'clinical_R_package_sources': 'contained in toolkit/skills/ye1-clinical-analysis/third-party/r',
        'toolchain_source_scope': 'GCC/OpenMP candidate source correspondence to bundled binary not established'}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'PASS', 'locked_archives': len(records), 'wheel_notice_files': notices,
                      'output': str(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
