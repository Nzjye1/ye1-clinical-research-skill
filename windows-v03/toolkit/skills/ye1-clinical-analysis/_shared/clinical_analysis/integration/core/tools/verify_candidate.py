"""Read-only integrity check of the explicitly checksummed candidate files."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    manifest=ROOT/'CANDIDATE-SHA256SUMS.txt'
    checked=0
    for line in manifest.read_text(encoding='utf-8').splitlines():
        expected,relative=line.split('  ',1)
        path=(ROOT/relative).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path)!=expected:
            raise SystemExit('CHECKSUM_MISMATCH:'+relative)
        checked+=1
    lock=json.loads((ROOT/'runtime-lock.json').read_text(encoding='utf-8'))
    if any(sha(ROOT/p)!=v for p,v in lock['code_hashes'].items()):raise SystemExit('PRODUCTION_LOCK_MISMATCH')
    print(json.dumps({'status':'PASS','checksum_files':checked,'production_files':len(lock['code_hashes']),'scope':'integrity_only_not_clinical_acceptance'}))
if __name__=='__main__':main()
