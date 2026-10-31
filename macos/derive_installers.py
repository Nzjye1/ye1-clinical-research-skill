"""Derive Mac installer entry points from the existing Windows implementation.

The exact replacement guards make source changes fail explicitly rather than
silently generating an installer with stale behavior. Statistical code is not
copied or rewritten here.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLKIT = ROOT / 'windows-v03/toolkit'
SCRIPTS = TOOLKIT / 'skills/ye1-clinical-analysis/scripts'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'installer template does not contain exactly one {old!r}')
    return text.replace(old, new, 1)


def write_new(path, text):
    with path.open('x', encoding='utf-8', newline='\n') as out:
        out.write(text)


def main():
    setup = (TOOLKIT / 'setup_windows.py').read_text(encoding='utf-8')
    setup = replace_once(setup, 'import argparse,hashlib,json,os,subprocess,sys,uuid',
                         'import argparse,hashlib,json,os,platform,subprocess,sys,uuid')
    setup = replace_once(setup, 'def main():\n',
                         'def main():\n    need(platform.system()=="Darwin" and platform.machine().lower() in {"arm64","aarch64"},"MACOS_ARM64_REQUIRED")\n')
    setup = replace_once(setup, "main/'scripts/install_windows.py'", "main/'scripts/install_macos.py'")
    setup = replace_once(setup, 'Open this project in Windows Codex', 'Open this project in macOS Codex')

    installer = (SCRIPTS / 'install_windows.py').read_text(encoding='utf-8')
    installer = replace_once(installer, 'directory=runtime/"python";python=directory/"Scripts/python.exe"',
                             'directory=runtime/"python";python=directory/"bin/python3"')
    installer = replace_once(installer, '[directory,python.parent,python]', '[directory,python.parent]')
    installer = replace_once(installer,
        'need(platform.system()=="Windows" and platform.machine().upper() in {"AMD64","X86_64"},"WINDOWS_X64_REQUIRED")',
        'need(platform.system()=="Darwin" and platform.machine().lower() in {"arm64","aarch64"},"MACOS_ARM64_REQUIRED")')
    installer = replace_once(installer, 'PYTHON_3_14_5_X64_REQUIRED', 'PYTHON_3_14_5_ARM64_REQUIRED')
    installer = replace_once(installer, 'cat(as.character(getRversion()))',
                             "cat(as.character(getRversion()),R.version$arch,sep='|')")
    installer = replace_once(installer,
        'need(done.returncode==0 and done.stdout.strip()==spec["R"],"R_4_6_1_X64_REQUIRED")',
        'need(done.returncode==0 and done.stdout.strip().split("|")[0]==spec["R"] and done.stdout.strip().split("|")[-1] in {"arm64","aarch64"},"R_4_6_1_ARM64_REQUIRED")')
    # venv python is a symlink on macOS; the subprocess probe verifies the
    # venv prefix and must also bind it to this installer's foundation Python.
    installer = replace_once(installer,
        "sys.prefix!=sys.base_prefix and platform.python_version()==sys.argv[2]",
        "sys.prefix!=sys.base_prefix and Path(sys._base_executable).resolve()==Path(sys.argv[3]).resolve() and platform.python_version()==sys.argv[2]")
    installer = replace_once(installer, 'str(directory),version],logdir/"python-venv-check.log"',
                             'str(directory),version,sys.executable],logdir/"python-venv-check.log"')
    write_new(TOOLKIT / 'setup_macos.py', setup)
    write_new(SCRIPTS / 'install_macos.py', installer)
    print('Derived Mac installers; existing Windows installer remains unchanged.')


if __name__ == '__main__':
    main()
