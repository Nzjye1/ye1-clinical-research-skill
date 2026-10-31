"""Platform-specific executable locations for the isolated project runtime."""
from pathlib import Path
import platform


def runtime_python(root, system=None):
    system = platform.system() if system is None else system
    suffix = 'bin/python3' if system == 'Darwin' else 'Scripts/python.exe'
    return Path(root) / '.runtime' / 'python' / suffix


def supported_platform(system=None, machine=None):
    system = platform.system() if system is None else system
    machine = (platform.machine() if machine is None else machine).lower()
    return (system == 'Windows' and machine in {'amd64', 'x86_64'}) or (system == 'Darwin' and machine in {'arm64', 'aarch64'})
