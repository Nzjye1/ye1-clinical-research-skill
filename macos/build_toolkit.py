"""Assemble a separate macOS toolkit from the locked clinical source."""
from pathlib import Path
import argparse, hashlib, json, shutil, sys, tarfile
sys.path.insert(0, str(Path(__file__).resolve().parent))
from port_backend import apply as apply_backend_port

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'windows-v03/toolkit'
MAIN = Path('skills/ye1-clinical-analysis')


def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def write_json(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def canonical(name):
    return name.lower().replace('_', '-')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--r-cache', type=Path, action='append', required=True)
    args = p.parse_args()
    target = args.output.resolve()
    if target.exists() or target.is_relative_to(ROOT.resolve()):
        raise ValueError('new independent output directory required')
    source_spec = json.loads((SOURCE / MAIN / 'runtime-spec.json').read_text(encoding='utf-8'))
    py_lock = json.loads((ROOT / 'macos/python-arm64-lock.json').read_text(encoding='utf-8'))
    r_lock = json.loads((ROOT / 'macos/r-arm64-lock.json').read_text(encoding='utf-8'))
    old_binaries = {a['binary']['filename'] for a in source_spec['r_packages']}
    target.mkdir(parents=True)
    copied = 0
    for source in SOURCE.rglob('*'):
        if not source.is_file():
            continue
        rel = source.relative_to(SOURCE)
        if source.is_symlink() or set(rel.parts) & {'.runtime', '.clinical-local', 'install-logs', '__pycache__', '.git'}:
            raise ValueError(f'unsafe source path: {rel}')
        if rel == Path('setup_windows.py') or rel.name == 'CANDIDATE-SHA256SUMS.txt' or (rel.parent == MAIN / 'third-party/r' and rel.name in old_binaries):
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied += 1

    by_python = {canonical(a['name']): a for a in py_lock['artifacts']}
    for pkg in source_spec['python_packages']:
        chosen = by_python[canonical(pkg['name'])]
        if chosen['version'] != pkg['version']:
            raise ValueError('Python package version mismatch: ' + pkg['name'])
        for key in ('filename', 'url', 'sha256', 'bytes'):
            pkg[key] = chosen[key]

    by_r = {item['name']: item for item in r_lock['binary_packages']}
    glmnet = r_lock['source_build_required'][0]
    if glmnet['status'] != 'MAC_BINARY_BUILT_AND_SYNTHETICALLY_TESTED':
        raise ValueError('verified arm64 glmnet binary required')
    by_r['glmnet'] = {'name': 'glmnet', 'version': glmnet['version'], **glmnet['binary']}
    for pkg in source_spec['r_packages']:
        entry = by_r[pkg['name']]
        if entry['version'] != pkg['version']:
            raise ValueError('R package version mismatch: ' + pkg['name'])
        if pkg['name'] == 'glmnet':
            source = ROOT / 'macos/artifacts' / entry['filename']
        else:
            matches = [d / entry['filename'] for d in args.r_cache if (d / entry['filename']).is_file()]
            if not matches:
                raise ValueError('missing R binary: ' + entry['filename'])
            source = matches[0]
        if digest(source) != entry['sha256'] or source.stat().st_size != entry['bytes']:
            raise ValueError('R binary hash/size mismatch: ' + entry['filename'])
        with tarfile.open(source, 'r:gz') as archive:
            expected = pkg['name'] + '/DESCRIPTION'
            if not any(m.name == expected and m.isfile() for m in archive.getmembers()):
                raise ValueError('R binary package identity missing: ' + pkg['name'])
        dest = target / MAIN / 'third-party/r' / entry['filename']
        shutil.copy2(source, dest)
        pkg['binary'] = {k: entry[k] for k in ('filename', 'sha256', 'bytes')}
        pkg['binary']['url'] = entry.get('url', 'bundled:github-actions-arm64-build')

    source_spec['product_version'] = '0.3.0-macos-arm64-candidate1'
    write_json(target / MAIN / 'runtime-spec.json', source_spec)
    write_json(target / MAIN / 'references/MACOS-DEPENDENCIES.json',
               {'python': py_lock, 'R': r_lock, 'R_foundation': '4.6.1 arm64',
                'license_scope': 'Original third-party notices and the 14 matching R sources are retained.'})
    for name in ('setup-online.sh', 'setup-offline.sh'):
        shutil.copy2(ROOT / 'macos' / name, target / name)
    (target / 'README.md').write_text('''# Ye1 临床分析 — Apple 芯片 Mac

## 安装到你的 Agent

> 请先识别我的系统并阅读这个工具箱的安装说明；如果适用，就把 Ye1 临床分析 Skill 安装到当前研究项目，准备依赖并完成自检，告诉我结果和开始方式。

适用于 Apple 芯片 macOS 14 或更新版本。将本地 CSV 和研究问题交给 Agent，生成统计表、图和结果说明。见[安装说明](START-HERE.md)。
''', encoding='utf-8', newline='\n')
    (target / 'START-HERE.md').write_text('''# 安装到你的 Agent

适用于 Apple 芯片 macOS 14 或更新版本。将工具箱解压到独立目录，在 Codex 中打开研究项目并告诉 Agent：

> 请先识别我的系统并阅读这个工具箱的安装说明；如果适用，就把 Ye1 临床分析 Skill 安装到当前研究项目，准备依赖并完成自检，告诉我结果和开始方式。

联网时运行 `bash setup-online.sh <已有研究目录>`；完整离线包从 `toolkit` 目录运行 `bash setup-offline.sh <已有研究目录>`。按需在命令末尾添加 `--method <方法ID>` 或 `--all`。首次预检和恢复等细节见主 Skill 的 `INSTALL.md`。
''', encoding='utf-8', newline='\n')
    (target / MAIN / 'INSTALL.md').write_text('''# Apple 芯片 Mac 安装与恢复

要求 macOS 14+ arm64、官方 Python 3.14.5 与 R 4.6.1。`setup-online.sh` 校验官方文件的 SHA256 和签名；缺少基础程序时会请求系统安装授权。Python/R 基础程序位于系统框架目录，分析依赖写入当前项目的 `.agents/skills/ye1-clinical-analysis/.runtime`。

在已创建的研究项目使用 `bash setup-online.sh <项目路径>`。离线交付解压后使用 `bash setup-offline.sh <项目路径>`；离线缓存包含固定 Python wheel、基础程序和许可证。可追加 `--method <方法ID>` 或 `--all`。安装器不覆盖同名 Skill；依赖中断后保留 `.runtime` 与 install-logs，从已安装主 Skill 的 `scripts/install_macos.py` 按原组或方法加 `--install` 恢复。已有结果使用新输出目录。

使用 `$ye1-clinical-analysis` 或单项 Skill，提供本地 CSV 路径、研究问题与变量定义，先自检方法。真实研究的首次本地准备按产品确认规则由用户在控制台核对。

固定公开 PBC 案例使用安装时 `.runtime/toolkit-profile.json` 中已解析并绑定的 `rscript` 真实路径。案例输入、输出和 Rscript 路径仍按原规则检查链接及文件身份。
''', encoding='utf-8', newline='\n')
    skill = target / MAIN / 'SKILL.md'
    text = skill.read_text(encoding='utf-8')
    text = text.replace('0.3.0-windows-local-integrated2', '0.3.0-macos-arm64-candidate1', 1)
    skill.write_text(text, encoding='utf-8', newline='\n')

    ported = apply_backend_port(target)
    write_json(target / MAIN / 'references/MACOS-PORT.json',
               {'description': 'Platform executable and native library guards plus their source bindings; statistical implementations are unchanged.',
                'changed_files': ported})

    manifest_path = target / 'toolkit-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest['version'] = source_spec['product_version']
    manifest['foundation'] = 'Official Python 3.14.5 and R 4.6.1 Apple arm64 frameworks'
    manifest['delivery_status'] = 'macOS arm64 candidate; final acceptance tracked outside package'
    # WindowsPath sorting folds case while macOS PosixPath does not. Sort the
    # portable relative strings so the Windows-built and CI-built manifests
    # are byte-identical, including their JSON key order.
    paths = [p for p in (target / 'skills').rglob('*') if p.is_file()]
    manifest['files'] = {p.relative_to(target).as_posix(): digest(p)
                         for p in sorted(paths, key=lambda item:item.relative_to(target).as_posix())}
    write_json(manifest_path, manifest)

    backend = MAIN / '_shared/clinical_analysis'
    checked = 0
    for original in (SOURCE / backend).rglob('*'):
        if original.is_file():
            relative = original.relative_to(SOURCE).as_posix()
            if original.name == 'CANDIDATE-SHA256SUMS.txt':
                continue
            if relative not in ported:
                if digest(original) != digest(target / relative):
                    raise ValueError('analysis implementation differs: ' + str(original))
                checked += 1
    print(json.dumps({'status': 'PASS', 'target': str(target), 'source_files_copied': copied,
                      'manifest_files': len(manifest['files']), 'analysis_files_unchanged': checked,
                      'ported_guards_and_binding_files': len(ported)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
