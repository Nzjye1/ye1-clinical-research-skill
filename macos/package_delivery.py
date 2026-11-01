"""Build a new online or complete offline archive from independently checked inputs."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, re, zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=['online', 'offline'], required=True)
    parser.add_argument('--toolkit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--ci-url', required=True)
    parser.add_argument('--ci-proof', type=Path, required=True)
    parser.add_argument('--ci-toolkit-manifest', type=Path, required=True)
    parser.add_argument('--runtime-manifest', type=Path, required=True)
    parser.add_argument('--ci-runtime-manifest', type=Path, required=True)
    parser.add_argument('--offline-preparation', type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.with_suffix('.receipt.json').exists():
        raise ValueError('existing archive or receipt preserved')
    proof = json.loads(args.ci_proof.read_text(encoding='utf-8'))
    if proof['status'] != 'PASS':
        raise ValueError('successful actual CI proof is required')
    if proof.get('source_commit') != args.source_commit or proof.get('ci_url') != args.ci_url:
        raise ValueError('CI proof does not identify the requested source commit and run')
    if proof.get('schema_version') == 'clinical-noninteractive-proof@1.0':
        suites = proof.get('noninteractive_suites', [])
        if {r['suite'] for r in suites} != {'core', 'compat', 'module', 'legacy', 'retired'} or len(suites) != 5 or any(r['status'] != 'PASS' for r in suites):
            raise ValueError('all affected noninteractive suites must pass')
    elif (proof.get('public_pbc', {}).get('status') != 'PUBLIC_FIXTURE_ACCEPTANCE_PASSED' or
          len(proof.get('synthetic_regression_suites', [])) != 9 or
          any(r['status'] != 'PASS' for r in proof['synthetic_regression_suites'])):
        raise ValueError('full historical CI proof is required')
    if sha(args.toolkit / 'toolkit-manifest.json') != sha(args.ci_toolkit_manifest):
        raise ValueError('local toolkit differs from tested CI toolkit manifest')
    if sha(args.runtime_manifest) != sha(args.ci_runtime_manifest):
        raise ValueError('local locked runtime differs from tested CI runtime manifest')
    if not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
        raise ValueError('complete source commit required')

    files = {}
    for item in args.toolkit.rglob('*'):
        if item.is_file():
            rel = item.relative_to(args.toolkit)
            if item.is_symlink() or set(rel.parts) & {'.git', '.runtime', '.clinical-local', 'install-logs', '__pycache__'}:
                raise ValueError('unsafe toolkit content: ' + str(rel))
            files['toolkit/' + rel.as_posix()] = item
    if args.kind == 'offline':
        if not args.offline_preparation or not args.offline_preparation.is_dir():
            raise ValueError('complete verified offline preparation required')
        for item in args.offline_preparation.rglob('*'):
            if item.is_file():
                rel = item.relative_to(args.offline_preparation)
                if item.is_symlink() or '..' in rel.parts:
                    raise ValueError('unsafe offline content')
                files[rel.as_posix()] = item

    intro = ('# Ye1 临床分析 — Apple 芯片 Mac\n\n## 安装到你的 Agent\n\n'
             '> 请先识别我的系统并阅读 `toolkit/START-HERE.md`；如果适用，就把 Ye1 临床分析 Skill 安装到当前研究项目，准备依赖并完成自检，告诉我结果和开始方式。\n\n'
             + ('本包包括离线基础程序、依赖、许可与源码材料。\n' if args.kind == 'offline' else
                '本包联网获取固定官方 Python wheel 和缺失的基础程序。\n'))
    revision = {'schema': 'clinical-macos-delivery@1.0', 'kind': args.kind,
                'product_version': '0.3.2-macos-arm64-noninteractive1', 'source_commit': args.source_commit,
                'ci_url': args.ci_url, 'ci_toolkit_manifest_sha256': sha(args.ci_toolkit_manifest),
                'ci_runtime_manifest_sha256': sha(args.ci_runtime_manifest),
                'archive_directly_extracted_in_ci': False,
                'source_scope_note': ('GCC/OpenMP source candidates are included with correspondence limitations.'
                                      if args.kind == 'offline' else 'R package sources and original notices are included.')}
    generated = {'README.md': intro.encode('utf-8'),
                 'SOURCE-REVISION.json': (json.dumps(revision, ensure_ascii=False, indent=2)+'\n').encode(),
                 'RUNTIME-MANIFEST.json': args.runtime_manifest.read_bytes()}
    if set(files) & set(generated):
        raise ValueError('conflicting package names')

    manifest = {}
    for name, path in files.items():
        manifest[name] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
        if path.suffix.lower() in {'.py', '.r', '.sh', '.md', '.json', '.txt', '.yaml', '.yml'}:
            raw = path.read_bytes()
            if re.search(rb'(?i)[a-z]:[\\/]+(?:Users|SKILL)[\\/]|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----', raw):
                raise ValueError('personal path or credential pattern in ' + name)
    for name, raw in generated.items():
        manifest[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    generated['CONTENTS-SHA256.json'] = (json.dumps({'schema': 'clinical-package-contents@1.0', 'files': manifest}, ensure_ascii=False, indent=2)+'\n').encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'x', allowZip64=True) as archive:
        for name in sorted(set(files) | set(generated)):
            rel = PurePosixPath(name)
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError('unsafe archive member')
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED if name.endswith(('.tgz', '.tar.gz', '.tar.xz', '.whl', '.pkg', '.png', '.zip')) else zipfile.ZIP_DEFLATED
            with archive.open(info, 'w', force_zip64=True) as out:
                if name in generated:
                    out.write(generated[name])
                else:
                    with files[name].open('rb') as source:
                        for block in iter(lambda: source.read(1024 * 1024), b''):
                            out.write(block)
    with zipfile.ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise ValueError('archive CRC failed')
        for name, record in manifest.items():
            with archive.open(name) as source:
                h = hashlib.sha256()
                count = 0
                for block in iter(lambda: source.read(1024 * 1024), b''):
                    count += len(block)
                    h.update(block)
            if count != record['bytes'] or h.hexdigest() != record['sha256']:
                raise ValueError('archive member verification failed: ' + name)
    receipt = {**revision, 'archive': args.output.name, 'bytes': args.output.stat().st_size,
               'sha256': sha(args.output), 'members': len(manifest) + 1,
               'crc': 'PASS', 'all_member_hashes': 'PASS', 'ci_manifest_match': True}
    args.output.with_suffix('.receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
