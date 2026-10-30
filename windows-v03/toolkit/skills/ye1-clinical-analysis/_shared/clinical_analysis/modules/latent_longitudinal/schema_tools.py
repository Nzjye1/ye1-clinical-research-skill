"""Small closed-schema validator for this module's documented JSON Schema subset.

The integration owner independently validates the same files with Draft 2020-12.
No network refs, arbitrary plugin loading, schema fallback or dependency install.
"""
import json
import math
from pathlib import Path
import re
if __package__:
    from .contracts import Blocked, need
else:
    from contracts import Blocked, need


def validate(value, schema, root=None):
    root = root or schema
    if "$ref" in schema:
        ref = schema["$ref"]
        need(ref.startswith("#/"), "SCHEMA_EXTERNAL_REF_FORBIDDEN")
        target = root
        for key in ref[2:].split("/"):
            target = target[key]
        return validate(value,target,root)
    if "anyOf" in schema:
        for branch in schema["anyOf"]:
            try:
                validate(value,branch,root)
                break
            except Blocked:
                pass
        else:
            raise Blocked("MODULE_OWNED_SCHEMA_INVALID")
    types=schema.get("type",[])
    types=[types] if isinstance(types,str) else types
    checks={"object":isinstance(value,dict),"array":isinstance(value,list),"string":isinstance(value,str),
            "number":type(value) in [int,float] and math.isfinite(value),
            "integer":type(value) is int,"boolean":type(value) is bool,"null":value is None}
    need(not types or any(checks[t] for t in types),"MODULE_OWNED_SCHEMA_INVALID")
    if "const" in schema:need(value==schema["const"] and (type(value) is bool)==(type(schema["const"]) is bool),"MODULE_OWNED_SCHEMA_INVALID")
    if "enum" in schema:need(value in schema["enum"],"MODULE_OWNED_SCHEMA_INVALID")
    if isinstance(value,dict):
        need(set(schema.get("required",[]))<=set(value),"MODULE_OWNED_SCHEMA_INVALID")
        properties=schema.get("properties",{})
        for key,child in value.items():
            if key in properties:validate(child,properties[key],root)
            else:
                extra=schema.get("additionalProperties",True)
                need(extra is not False,"MODULE_OWNED_SCHEMA_INVALID")
                if isinstance(extra,dict):validate(child,extra,root)
    if isinstance(value,list):
        need(len(value)>=schema.get("minItems",0) and len(value)<=schema.get("maxItems",10**10),"MODULE_OWNED_SCHEMA_INVALID")
        if schema.get("uniqueItems"):need(len({json.dumps(x,sort_keys=True) for x in value})==len(value),"MODULE_OWNED_SCHEMA_INVALID")
        if "items" in schema:
            for child in value:validate(child,schema["items"],root)
    if isinstance(value,str):
        need(len(value)>=schema.get("minLength",0) and len(value)<=schema.get("maxLength",10**10),"MODULE_OWNED_SCHEMA_INVALID")
        if "pattern" in schema:need(re.search(schema["pattern"],value) is not None,"MODULE_OWNED_SCHEMA_INVALID")
    if type(value) in [int,float]:
        need(math.isfinite(value) and value>=schema.get("minimum",-math.inf)
             and value<=schema.get("maximum",math.inf),"MODULE_OWNED_SCHEMA_INVALID")


def file_validate(value, filename):
    path=Path(__file__).with_name("schemas")/filename
    need(path.is_file(),"MODULE_SCHEMA_MISSING")
    validate(value,json.loads(path.read_text(encoding="utf-8")))
