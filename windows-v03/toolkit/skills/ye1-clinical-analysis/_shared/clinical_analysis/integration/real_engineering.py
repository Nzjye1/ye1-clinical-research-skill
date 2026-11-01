"""Retired internal engineering-only entry; use the registered customer methods.

No source file, permission record, or output is read or created by this stub.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from module_contract import ContractError

def _retired(*args, **kwargs):
    raise ContractError("LEGACY_ENGINEERING_RETIRED")

inspect = prepare = finish = _retired

if __name__ == "__main__":
    print(json.dumps({"status": "blocked", "reason_code": "LEGACY_ENGINEERING_RETIRED"}))
    raise SystemExit(2)
