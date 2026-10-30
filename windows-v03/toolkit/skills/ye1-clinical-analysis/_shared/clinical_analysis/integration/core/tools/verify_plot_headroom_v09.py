"""Check the bounded plot-only change against the two real entry smokes."""
import argparse, csv, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'evidence/smoke-v09-20261024-073344'
NEW = ROOT / 'evidence/smoke-v09-20261024-074129'
OUT = ROOT / 'evidence/plot-label-fix-v09/verification-final.json'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def ref(p):
    return {'local_ref': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--visual-confirmed', action='store_true')
    args = parser.parse_args()
    if not args.visual_confirmed:
        raise SystemExit('An actual human/model visual inspection must precede this receipt.')
    if OUT.exists():
        raise SystemExit('VERIFICATION_ALREADY_EXISTS')
    checks, bound = [], [Path(__file__).resolve(), ROOT/'runtime-lock.json',
        ROOT/'src/clinanalysis/R/clinical_interpretation_v09.R',
        ROOT/'evidence/plot-label-fix-v09/clinical_interpretation_v09.before.R',
        ROOT/'evidence/plot-label-fix-v09/runtime-lock.before.json', OLD/'receipt.json', NEW/'receipt.json']
    for family in ('gaussian', 'binomial'):
        for name in ('penalized-model.json', 'linear-explainer.json'):
            a, b = [d/f'{family}-train/private/{name}' for d in (OLD, NEW)]
            checks.append({'case': f'{family}/{name}', 'comparison': 'exact SHA256', 'pass': sha(a)==sha(b)})
            bound += [a,b]
        for a in sorted((OLD/f'{family}-interpret/tables').glob('*.csv')):
            b = NEW/f'{family}-interpret/tables'/a.name
            def rows(p):
                with p.open(encoding='utf-8-sig', newline='') as stream:
                    values=[]
                    for row in csv.DictReader(stream):
                        run_id=row.pop('run_id')
                        assert row['result_id'].startswith(run_id+'-')
                        row['result_id']=row['result_id'][len(run_id):]
                        values.append(row)
                    return values
            checks.append({'case': f'{family}/tables/{a.name}', 'comparison': 'all fields exact after normalizing run_id and its required result_id prefix; result_id suffix preserved',
                'pass': rows(a)==rows(b)})
            bound += [a,b]
        for name in ('interpretation-encoded-contributions.csv','interpretation-individual-contributions.csv','interpretation-individual-points.csv'):
            a,b = [d/f'{family}-interpret/private/{name}' for d in (OLD,NEW)]
            checks.append({'case':f'{family}/private/{name}', 'comparison':'exact SHA256, values remain local', 'pass':sha(a)==sha(b)})
            bound += [a,b]
    image = NEW/'binomial-interpret/figures/nomogram.png'
    bound.append(image)
    ok=all(c['pass'] for c in checks)
    result={'status':'PASS' if ok else 'FAIL','runtime_lock_sha256':sha(ROOT/'runtime-lock.json'),
        'scope':'Upper plot headroom only; no numerical/provider change',
        'initial_comparison':'verification.json retained: only run_id and its embedded result_id prefix differed. The corrected comparison checks and removes that prefix, retaining the entire result_id suffix.',
        'numerical_outputs_unchanged':ok,'repaired_image_visually_inspected':True,
        'visual_observation':'The highest probability annotation p=0.9881 is fully within the plotting region; axes, scales and all five probability labels are readable.',
        'checks':checks,'bound_files':[ref(p) for p in bound]}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'passed':sum(c['pass'] for c in checks),
        'failed':[c['case'] for c in checks if not c['pass']],'receipt':str(OUT)}))
    raise SystemExit(0 if ok else 1)

if __name__ == '__main__':
    main()
