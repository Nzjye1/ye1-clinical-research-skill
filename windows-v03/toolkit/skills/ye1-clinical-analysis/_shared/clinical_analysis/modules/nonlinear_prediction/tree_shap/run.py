"""Local private request/response CLI for the independent explanation adapter."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tree_shap.interface import analyze
from tree_shap.runtime import bridge, prediction as p

def main():
    p.need(len(sys.argv)==3,'CLI_ARGUMENTS_INVALID')
    destination=Path(sys.argv[2])
    p.need(destination.parent.name=='private','SHAP_RESPONSE_MUST_STAY_PRIVATE')
    with destination.open('x',encoding='utf-8') as handle:
        response=analyze(bridge.strict_load(Path(sys.argv[1]).read_bytes()))
        json.dump(response,handle,ensure_ascii=False,allow_nan=False)
    print(json.dumps({'ok':response['ok'],'reason_code':response['reason_code']}))
    return 0 if response['ok'] else 2

if __name__=='__main__': raise SystemExit(main())
