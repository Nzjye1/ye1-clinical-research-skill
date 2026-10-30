from pathlib import Path
import json
import sys
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from schema_defs import all_schemas
for name,schema in all_schemas().items():
    (root/"contracts"/(name+".schema.json")).write_text(json.dumps(schema,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
print("Closed Cox module schemas written; no $ref or unsupported schema vocabulary.")

# The admitted envelope embeds its closed leaf schemas; do not leave a stale
# 200-row transport bound after regenerating an owner resource schema.
admitted=root/"real_admission"/"schemas"
if admitted.is_dir():
    for envelope in ("request", "response"):
        path=admitted/(envelope+".schema.json")
        value=json.loads(path.read_text(encoding="utf-8"))
        for name in ("payload", "diagnostics", "public_record", "private_record"):
            leaf=admitted/(name+".schema.json")
            if name in value["properties"] and leaf.is_file():
                value["properties"][name]=json.loads(leaf.read_text(encoding="utf-8"))
        path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
