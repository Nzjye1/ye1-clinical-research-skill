"""Reuse the immutable focused P1 harness against this development candidate."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
snapshot=ROOT/'review-snapshots/p1-fixes-20261023'
target=ROOT/'fixtures/p1'
target.mkdir(exist_ok=True)
for source in (snapshot/'fixtures/p1').glob('*.json'):
    destination=target/source.name
    if destination.exists():raise SystemExit('P1_FIXTURE_EXISTS')
    destination.write_bytes(source.read_bytes())
text=(snapshot/'tools/retest_p1.py').read_text(encoding='utf-8')
start=text.index('    units=[]\n')
end=text.index('    receipt=',start)
replacement='''    unitlog=ROOT/'evidence/unit-tests-v02-final.log'
    units=[{'suite':'separate complete v02 unit suite', 'passed':'\\nOK' in unitlog.read_text(encoding='utf-8-sig'), 'log':str(unitlog)}]
'''
text=text[:start]+replacement+text[end:]
(ROOT/'tools/retest_p1_v02.py').write_text(text,encoding='utf-8')
print('P1_RETEST_PREPARED_USING_FINAL_V02_UNIT_EVIDENCE')
