"""Read-only guard for the independently reviewed previous candidate."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PREVIOUS=ROOT.parent/'clinical-analysis-core-v0_1-dev-20261023'
SNAPSHOT=ROOT/'evidence/v0_1-start-hashes.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def observed():
    lock=json.loads((PREVIOUS/'runtime-lock.json').read_text(encoding='utf-8'))
    paths=sorted(set(lock['code_hashes'])|{'runtime-lock.json','method-capabilities.json','CANDIDATE-SHA256SUMS.txt','evidence/final-manifest.json'})
    return {'previous_root':str(PREVIOUS),'hashes':{p:sha(PREVIOUS/p) for p in paths},
            'code_matches_previous_lock':all(sha(PREVIOUS/p)==v for p,v in lock['code_hashes'].items())}
def main():
    current=observed()
    if sys.argv[1:] == ['snapshot']:
        with SNAPSHOT.open('x',encoding='utf-8') as f:json.dump(current,f,indent=2)
        print('PREVIOUS_CANDIDATE_READ_ONLY_SNAPSHOT',len(current['hashes']))
    else:
        original=json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        changes=[p for p,v in original['hashes'].items() if current['hashes'].get(p)!=v]
        result={'previous_candidate_unchanged':not changes,'changed_files':changes,
                'previous_lock_valid_at_start':original['code_matches_previous_lock'],
                'previous_lock_valid_now':current['code_matches_previous_lock']}
        (ROOT/'evidence/v0_1-preservation-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result))
        if changes:raise SystemExit(1)
if __name__=='__main__':main()
