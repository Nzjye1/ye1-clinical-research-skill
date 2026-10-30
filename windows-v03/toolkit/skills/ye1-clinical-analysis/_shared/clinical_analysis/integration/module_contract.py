"""Strict private module contract validation; no execution, fitting or fallback."""
from __future__ import annotations
import hashlib,json,math,importlib.util,re
from pathlib import Path
BASE=Path(__file__).resolve().parent
_source=BASE/"core/python/clinical_methods/contracts.py"
_spec=importlib.util.spec_from_file_location("clinical_module_shared_contract_owner",_source)
_contracts=importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contracts)
MAX_SCHEMA_BYTES=8*1024*1024
FROZEN_OPERATIONS=frozenset({"infer","predict","evaluate","explain","apply","assign","nomogram","fit_explainer"})
class ContractError(ValueError):
    def __init__(self,code,location=""):
        self.code=code;self.location=location;super().__init__(code+(":"+location if location else ""))
def _fail(code,location=""):raise ContractError(code,location)
def _pairs(items):
    result={}
    for key,value in items:
        if key in result:_fail("MODULE_JSON_DUPLICATE_KEY")
        result[key]=value
    return result
def read_json(path):
    p=Path(path)
    if not p.is_file() or p.stat().st_size>MAX_SCHEMA_BYTES:_fail("MODULE_SCHEMA_FILE_INVALID")
    try:return json.loads(p.read_text(encoding="utf-8-sig"),object_pairs_hook=_pairs,parse_constant=lambda value:_fail("MODULE_NONFINITE_JSON"))
    except ContractError:raise
    except (OSError,UnicodeError,json.JSONDecodeError):_fail("MODULE_JSON_INVALID")
def _finite(value,location=""):
    if value is None or isinstance(value,(str,bool,int)):return
    if isinstance(value,float):
        if not math.isfinite(value):_fail("MODULE_NONFINITE_VALUE",location)
        return
    if isinstance(value,list):
        for i,item in enumerate(value):_finite(item,location+"/"+str(i))
        return
    if isinstance(value,dict) and all(isinstance(key,str) for key in value):
        for key,item in value.items():_finite(item,location+"/"+key)
        return
    _fail("MODULE_NON_JSON_VALUE",location)
def _refs(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ("$ref","$dynamicRef") and (not isinstance(item,str) or not item.startswith("#")):_fail("MODULE_EXTERNAL_SCHEMA_REF_FORBIDDEN")
            _refs(item)
    elif isinstance(value,list):
        for item in value:_refs(item)
SCHEMA_KEYWORDS=frozenset({"$schema","$id","title","description","$comment","type","anyOf","allOf",
    "if","then","else","const","enum","properties","required","additionalProperties","items",
    "minItems","maxItems","minLength","maxLength","pattern","minimum","maximum","uniqueItems"})
SCHEMA_TYPES=frozenset({"object","array","string","number","integer","boolean","null"})
def _audit_schema(schema,owned=False,location="schema"):
    """Compile-time guard for the existing owner's explicitly bounded vocabulary.

    This is not a full Draft 2020-12 validator. Unsupported keywords, including
    local references, fail registration; there is no permissive fallback.
    Typed variable-key maps are allowed; their names need module semantic checks.
    """
    if not isinstance(schema,dict) or set(schema)-SCHEMA_KEYWORDS:_fail("MODULE_SCHEMA_KEYWORD_UNSUPPORTED",location)
    types=schema.get("type",[]);types=types if isinstance(types,list) else [types]
    if any(t not in SCHEMA_TYPES for t in types) or len(types)!=len(set(types)):_fail("MODULE_SCHEMA_INVALID",location)
    if "type" in schema and not types:_fail("MODULE_SCHEMA_INVALID",location)
    if owned and "object" in types and schema.get("additionalProperties") is not False and not isinstance(schema.get("additionalProperties"),dict):
        _fail("MODULE_OPEN_RECORD_SCHEMA",location)
    for key in ("properties",):
        if key in schema:
            if not isinstance(schema[key],dict):_fail("MODULE_SCHEMA_INVALID",location)
            for name,child in schema[key].items():_audit_schema(child,owned,location+"/properties/"+name)
    for key in ("anyOf","allOf"):
        if key in schema:
            if not isinstance(schema[key],list) or not schema[key]:_fail("MODULE_SCHEMA_INVALID",location)
            for i,child in enumerate(schema[key]):_audit_schema(child,owned,location+"/"+key+"/"+str(i))
    for key in ("items","if","then","else"):
        if key in schema:_audit_schema(schema[key],owned,location+"/"+key)
    if "additionalProperties" in schema:
        value=schema["additionalProperties"]
        if isinstance(value,dict):_audit_schema(value,owned,location+"/additionalProperties")
        elif type(value) is not bool:_fail("MODULE_SCHEMA_INVALID",location)
    if "required" in schema:
        value=schema["required"]
        if not isinstance(value,list) or any(not isinstance(x,str) for x in value) or len(value)!=len(set(value)):_fail("MODULE_SCHEMA_INVALID",location)
    for key in ("minItems","maxItems","minLength","maxLength"):
        if key in schema and (type(schema[key]) is not int or schema[key]<0):_fail("MODULE_SCHEMA_INVALID",location)
    for key in ("minimum","maximum"):
        if key in schema and type(schema[key]) not in (int,float):_fail("MODULE_SCHEMA_INVALID",location)
    for lower,upper in (("minItems","maxItems"),("minLength","maxLength"),("minimum","maximum")):
        if lower in schema and upper in schema and schema[lower]>schema[upper]:_fail("MODULE_SCHEMA_INVALID",location)
    if "uniqueItems" in schema and type(schema["uniqueItems"]) is not bool:_fail("MODULE_SCHEMA_INVALID",location)
    if "enum" in schema and (not isinstance(schema["enum"],list) or not schema["enum"]):_fail("MODULE_SCHEMA_INVALID",location)
    if "pattern" in schema:
        try:re.compile(schema["pattern"])
        except (TypeError,re.error):_fail("MODULE_SCHEMA_INVALID",location)

def _record_root(schema):
    if schema.get("type")=="object" and schema.get("additionalProperties") is False:return True
    return bool(schema.get("anyOf")) and all(_record_root(s) or s.get("type")=="null" for s in schema["anyOf"])

class _Validator:
    def __init__(self,schema):self.schema=schema

def _validator(schema,owned=False):
    _finite(schema);_refs(schema);_audit_schema(schema,owned)
    if owned and not _record_root(schema):_fail("MODULE_OPEN_RECORD_SCHEMA")
    return _Validator(schema)
def _check(validator,value,code):
    _finite(value)
    try:_contracts.validate_schema(value,validator.schema,"module")
    except _contracts.ContractBlocked as exc:_fail(code,exc.missing[0] if exc.missing else exc.code)
def bounded_file(root,relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:_fail("MODULE_PATH_OUTSIDE_OWNER")
    root=Path(root).resolve();p=(root/relative).resolve()
    if not p.is_relative_to(root) or not p.is_file():_fail("MODULE_PATH_OUTSIDE_OWNER")
    return p
class ModuleRegistry:
    """Registered own schemas are mandatory; envelope-only success is forbidden."""
    def __init__(self,reserved_methods=()):
        self.methods={};self.reserved=frozenset(reserved_methods)
        self.request_validator=_validator(read_json(BASE/"contracts/module-request.schema.json"))
        self.response_validator=_validator(read_json(BASE/"contracts/module-response.schema.json"))
        self.manifest_validator=_validator(read_json(BASE/"contracts/integration-request.schema.json"))
    def register_manifest(self,module_root,manifest_path="integration-request.json"):
        root=Path(module_root).resolve();manifest=read_json(bounded_file(root,manifest_path));_check(self.manifest_validator,manifest,"MODULE_MANIFEST_INVALID")
        files=set(manifest["provider_files"])
        for key in ("entrypoint","projection_entrypoint"):
            if manifest[key] is not None:files.add(manifest[key]["path"])
        for method in manifest["methods"]:files.update(method["schemas"].values())
        paths={name:bounded_file(root,name) for name in files}
        pending={}
        for method in manifest["methods"]:
            mid=method["method_id"]
            if mid in self.methods or mid in self.reserved or mid in pending:_fail("MODULE_METHOD_ALREADY_REGISTERED",mid)
            validators={name:_validator(read_json(paths[rel]),owned=True) for name,rel in method["schemas"].items()}
            pending[mid]={"module_id":manifest["module_id"],"method_version":method["method_version"],"operations":frozenset(method["operations"]),"validators":validators,"numerical_owner":method["numerical_owner"]}
        hashes={name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()}
        self.methods.update(pending)
        return {"module_id":manifest["module_id"],"methods":sorted(pending),"files_sha256":hashes,"execution_performed":False}
    def _method(self,request):
        mid=request.get("method_id") if isinstance(request,dict) else None
        if mid not in self.methods:_fail("MODULE_METHOD_NOT_REGISTERED")
        definition=self.methods[mid]
        if request.get("operation") not in definition["operations"]:_fail("MODULE_OPERATION_UNSUPPORTED")
        return definition
    def validate_request(self,request,expected_bindings):
        _check(self.request_validator,request,"MODULE_REQUEST_INVALID");definition=self._method(request)
        if not isinstance(expected_bindings,dict) or set(expected_bindings)!=set(request["bindings"]):_fail("MODULE_BINDING_CONTEXT_REQUIRED")
        if request["bindings"]!=expected_bindings:_fail("MODULE_BINDING_MISMATCH")
        if request["operation"] in FROZEN_OPERATIONS and request["bindings"]["model_sha256"] is None:_fail("MODULE_FROZEN_MODEL_BINDING_REQUIRED")
        _check(definition["validators"]["payload"],request["payload"],"MODULE_PAYLOAD_INVALID")
        return definition
    def validate_response(self,request,response):
        definition=self._method(request);_check(self.response_validator,response,"MODULE_RESPONSE_INVALID")
        _check(definition["validators"]["diagnostics"],response["diagnostics"],"MODULE_DIAGNOSTICS_INVALID")
        for name in ("public_record","private_record"):
            if response[name] is not None:_check(definition["validators"][name],response[name],"MODULE_"+name.upper()+"_INVALID")
        public=response["public_record"]
        if isinstance(public,dict):
            if "method_id" in public and public["method_id"]!=request["method_id"]:_fail("MODULE_RESULT_METHOD_MISMATCH")
            if "operation" in public and public["operation"]!=request["operation"]:_fail("MODULE_RESULT_OPERATION_MISMATCH")
        return response
