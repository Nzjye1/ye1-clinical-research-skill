"""Inspect linked dylibs in the CI-produced Apple arm64 glmnet binary."""
import argparse, hashlib, json, struct, tarfile
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('archive', type=Path)
p.add_argument('sha_file', type=Path)
args = p.parse_args()
digest = hashlib.sha256(args.archive.read_bytes()).hexdigest()
assert digest == args.sha_file.read_text(encoding='utf-8').split()[0]
with tarfile.open(args.archive, 'r:gz') as archive:
    libraries = [m for m in archive.getmembers() if m.name.endswith('/glmnet.so')]
    assert len(libraries) == 1 and libraries[0].isfile()
    raw = archive.extractfile(libraries[0]).read()
assert raw[:4] == bytes.fromhex('cffaedfe') and struct.unpack_from('<I', raw, 4)[0] == 0x100000c
ncmds = struct.unpack_from('<I', raw, 16)[0]
offset = 32
linked = []
for _ in range(ncmds):
    command, size = struct.unpack_from('<II', raw, offset)
    assert size >= 8 and offset + size <= len(raw)
    if command & 0x7fffffff in (12, 24, 31, 35):
        position = offset + struct.unpack_from('<I', raw, offset + 8)[0]
        linked.append(raw[position:raw.index(b'\0', position)].decode('utf-8'))
    offset += size
print(json.dumps({'status': 'PASS', 'sha256': digest, 'bytes': args.archive.stat().st_size,
                  'cpu': 'arm64', 'library': libraries[0].name, 'linked_dylibs': linked}, indent=2))
