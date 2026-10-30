"""Bounded read-only check of previous candidates' explicit checksum manifests."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SNAPSHOT=ROOT/'evidence/previous-candidates-start.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def observe():
    result={}
    for name in ['clinical-analysis-core-v0_1-dev-20261023','clinical-analysis-core-v0_2-dev-20261023','clinical-analysis-core-v0_3-dev-20261024','clinical-analysis-core-v0_4-dev-20261024','clinical-analysis-core-v0_5-dev-20261024','clinical-analysis-core-v0_6-dev-20261024','clinical-analysis-core-v0_7-dev-20261024','clinical-analysis-core-v0_8-dev-20261024','clinical-analysis-core-v0_9-dev-20261024']:
        base=ROOT.parent/name
        lines=(base/'CANDIDATE-SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()
        expected={p:h for h,p in (line.split('  ',1) for line in lines)}
        actual={p:sha(base/p) for p in expected}
        actual['CANDIDATE-SHA256SUMS.txt']=sha(base/'CANDIDATE-SHA256SUMS.txt')
        result[name]={'hashes':actual,'matches_own_manifest':all(actual[p]==h for p,h in expected.items())}
    return result
def main():
    observed=observe()
    if sys.argv[1:]==['snapshot']:
        with SNAPSHOT.open('x',encoding='utf-8') as f:json.dump(observed,f,indent=2)
        print(json.dumps({'snapshotted':{n:len(x['hashes']) for n,x in observed.items()}}))
    else:
        initial=json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        changed={n:[p for p,h in x['hashes'].items() if observed[n]['hashes'].get(p)!=h] for n,x in initial.items()}
        receipt={'unchanged':not any(changed.values()),'changed':changed,'current_manifest_valid':{n:x['matches_own_manifest'] for n,x in observed.items()}}
        (ROOT/'evidence/previous-candidates-preservation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(receipt))
        if not receipt['unchanged']:raise SystemExit(1)
if __name__=='__main__':main()
