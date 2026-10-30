"""Read-only detail for the current result schema branch, no payload printing."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'python'))
from clinical_methods import contracts
def main():
    result=contracts.read_json(Path(sys.argv[1]));schema=contracts.read_json(ROOT/'schemas/result.schema.json')
    branch=next(x for x in schema['anyOf'] if x.get('properties',{}).get('schema_version',{}).get('const')=='clinical-analysis-result@0.5.0-candidate1')
    try:
        contracts.validate_schema(result,branch,'result')
        print('CURRENT_RESULT_SCHEMA_PASS')
    except contracts.ContractBlocked as exc:
        print(json.dumps(contracts.failure(exc)))
        return 1
    return 0
if __name__=='__main__':raise SystemExit(main())
