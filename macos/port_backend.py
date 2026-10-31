"""Apply platform guards and their transitive source bindings to a Mac copy."""
from pathlib import Path
import hashlib, json

ROOT = Path(__file__).resolve().parents[1]
OVERLAYS = ROOT / 'macos/overlays'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return sha(raw)


def apply(target):
    shared = target / 'skills/ye1-clinical-analysis/_shared/clinical_analysis'
    module_path = shared / 'integration/module-lock.json'
    admitted_path = shared / 'integration/admitted-module-lock.json'
    original_modules = json.loads(module_path.read_text(encoding='utf-8'))['modules']
    original_admitted = json.loads(admitted_path.read_text(encoding='utf-8'))['modules']
    previous = {m['registration_id']: canonical(m) for m in original_modules}
    for name, old in previous.items():
        if original_admitted[name]['legacy_registration_sha256'] != old:
            raise ValueError('pre-existing module binding mismatch: ' + name)

    mappings = []
    changed = set()
    for overlay in sorted(OVERLAYS.rglob('*')):
        if not overlay.is_file():
            continue
        relative = overlay.relative_to(OVERLAYS)
        destination = shared / relative
        before, after = destination.read_bytes(), overlay.read_bytes()
        if before == after:
            raise ValueError('Mac overlay did not change its source: ' + str(relative))
        destination.write_bytes(after)
        mappings.append((sha(before), sha(after)))
        changed.add(destination.relative_to(target).as_posix())

    # The Cox admission wrapper pins its existing core runtime guards as literal
    # hashes. Change only those bindings; estimation code is untouched.
    wrapper = shared / 'modules/cox-evaluation-explanation/module_api.py'
    before = wrapper.read_bytes()
    after = before
    for old, new in mappings:
        after = after.replace(old.encode(), new.encode())
    if before != after:
        wrapper.write_bytes(after)
        mappings.append((sha(before), sha(after)))
        changed.add(wrapper.relative_to(target).as_posix())

    metadata = [p for p in (target / 'skills').rglob('*.json') if p.is_file()]
    seen = set()
    def propagate():
        while mappings:
            old, new = mappings.pop(0)
            if old == new or (old, new) in seen:
                continue
            seen.add((old, new))
            if len(seen) > 500:
                raise ValueError('cyclic source binding updates')
            for path in metadata:
                before = path.read_bytes()
                if old.encode() not in before:
                    continue
                after = before.replace(old.encode(), new.encode())
                path.write_bytes(after)
                changed.add(path.relative_to(target).as_posix())
                mappings.append((sha(before), sha(after)))

    propagate()
    # Module registration IDs are hashes of canonical JSON objects, not file
    # bytes. Recalculate the canonical references after literal-hash updates.
    for _ in range(10):
        current = {m['registration_id']: canonical(m) for m in json.loads(module_path.read_text(encoding='utf-8'))['modules']}
        differences = [(previous[k], v) for k, v in current.items() if previous[k] != v]
        if not differences:
            break
        previous = current
        mappings.extend(differences)
        propagate()
    else:
        raise ValueError('module registration bindings did not converge')
    admitted = json.loads(admitted_path.read_text(encoding='utf-8'))['modules']
    assert all(admitted[name]['legacy_registration_sha256'] == value for name, value in previous.items())
    return sorted(changed)
