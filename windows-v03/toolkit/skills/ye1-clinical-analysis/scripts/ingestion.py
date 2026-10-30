"""Explicit, bounded local file mapping. Never infer a scientific design."""
from pathlib import Path
import csv,gzip,hashlib,io,json,math,re

PREFIX="ye1-ingestion-v1:"
class InputBlocked(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
def need(ok,code):
    if not ok:raise InputBlocked(code)
def digest(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return digest(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode())
def pairs(items):
    result={}
    for key,value in items:need(key not in result,"DUPLICATE_JSON_KEY");result[key]=value
    return result
def decode(raw):
    return json.loads(raw.decode("utf-8-sig"),object_pairs_hook=pairs,parse_constant=lambda _:need(False,"NONFINITE_JSON"))
def confined(path,project):
    path=Path(path)
    if not path.is_absolute():path=project/path
    need(not any(p.is_symlink() or (hasattr(p,"is_junction") and p.is_junction()) for p in (path,*path.parents)),"UNSAFE_INPUT_PATH")
    path=path.resolve();need(path.is_relative_to(project),"INPUT_OUTSIDE_PROJECT");return path
def bounded(path,project,limit):
    path=confined(path,project);need(path.is_file() and path.stat().st_size<=limit,"INPUT_FILE_MISSING_OR_BYTE_BUDGET")
    with path.open("rb") as stream:raw=stream.read(limit+1)
    need(len(raw)<=limit,"INPUT_BYTE_BUDGET_EXCEEDED");return path,raw
def label(value):return isinstance(value,str) and bool(value.strip()) and re.fullmatch(r"[^\x00-\x1f\x7f-\x9f]{1,256}",value)
def shape(template,row):
    if isinstance(template,list):return [shape(x,row) for x in template]
    if not isinstance(template,dict):return template
    if "$field" in template:
        need(set(template)=={"$field"} and template["$field"] in row,"RECORD_FIELD_MAPPING_INVALID")
        return row[template["$field"]]
    return {k:shape(v,row) for k,v in template.items()}

def table(spec,project,limits):
    need(isinstance(spec,dict) and {"path","fields","unselected_columns","format"}<=set(spec) and set(spec)<={"path","fields","unselected_columns","format","record"},"TABLE_MAPPING_CLOSED_FIELDS_REQUIRED")
    fields=spec["fields"];excluded=spec["unselected_columns"]
    need(isinstance(fields,list) and fields and isinstance(excluded,list),"TABLE_FIELDS_REQUIRED")
    need(all(isinstance(f,dict) and set(f)=={"name","column","type","missing_codes"} for f in fields),"TABLE_FIELD_DEFINITION_INVALID")
    names=[f["name"] for f in fields];columns=[f["column"] for f in fields]
    need(all(isinstance(n,str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*",n) for n in names) and len(set(names))==len(names),"FIELD_NAMES_INVALID")
    need(all(label(x) for x in columns+excluded),"SOURCE_COLUMN_LABEL_INVALID")
    need(len(set(columns))==len(columns),"COLUMN_MAP_NOT_ONE_TO_ONE")
    need(len(set(excluded))==len(excluded) and not set(columns)&set(excluded),"COLUMN_PROJECTION_CONFLICT")
    need(all(f["type"] in {"number","integer","id","string","category"} and isinstance(f["missing_codes"],list) and all(isinstance(x,str) for x in f["missing_codes"]) for f in fields),"EXPLICIT_FIELD_TYPE_AND_MISSING_CODES_REQUIRED")
    path,raw=bounded(spec["path"],project,limits["max_bytes"])
    need(spec["format"] in {"csv","csv_gzip"},"UTF8_CSV_FORMAT_REQUIRED")
    if spec["format"]=="csv_gzip":
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:decoded=stream.read(limits["max_decoded_bytes"]+1)
    else:decoded=raw
    need(len(decoded)<=limits["max_decoded_bytes"],"DECODED_BYTE_BUDGET_EXCEEDED")
    try:text=decoded.decode("utf-8-sig")
    except UnicodeError:raise InputBlocked("UTF8_CSV_REQUIRED") from None
    rows=csv.reader(io.StringIO(text,newline=""));header=next(rows,None)
    need(header is not None and all(label(x) for x in header) and len(header)==len(set(header)),"CSV_HEADER_INVALID")
    need(set(header)==set(columns+excluded) and len(header)==len(columns+excluded),"CSV_UNDECLARED_OR_MISSING_COLUMN")
    indexes=[header.index(x) for x in columns];result=[]
    for row in rows:
        need(len(result)<limits["max_rows"],"ROW_BUDGET_EXCEEDED_NO_SAMPLING")
        need(len(row)==len(header),"CSV_ROW_WIDTH_INVALID");record={}
        for field,index in zip(fields,indexes):
            value=row[index]
            if value in field["missing_codes"]:value=None
            elif field["type"] in {"number","integer"}:
                need(value==value.strip() and value!="","NUMERIC_VALUE_INVALID")
                try:value=float(value)
                except ValueError:raise InputBlocked("NUMERIC_VALUE_INVALID") from None
                need(math.isfinite(value),"NONFINITE_INPUT_VALUE")
                if field["type"]=="integer":need(value.is_integer(),"INTEGER_VALUE_REQUIRED");value=int(value)
            record[field["name"]]=value
        result.append(shape(spec["record"],record) if "record" in spec else record)
    need(bool(result),"EMPTY_TABLE_NOT_SUPPORTED")
    return result,{"path":str(path),"sha256":digest(raw),"bytes":len(raw),"rows":len(result),"mapping":spec}

def materialize(template,tables,project,limits,records):
    if isinstance(template,list):return [materialize(x,tables,project,limits,records) for x in template]
    if not isinstance(template,dict):return template
    markers=set(template)&{"$csv_rows","$csv_values","$file_text","$file_json","$file_sha256","$json_value"}
    if markers:
        need(len(markers)==1 and len(template)==1,"SINGLE_INPUT_MARKER_REQUIRED");marker=next(iter(markers));value=template[marker]
        if marker=="$csv_rows":
            need(value in tables,"DECLARED_TABLE_REQUIRED");rows,receipt=table(tables[value],project,limits);records.append(receipt);return rows
        if marker=="$csv_values":
            need(isinstance(value,dict) and set(value)=={"table","field","where"} and value["table"] in tables and isinstance(value["where"],dict),"CSV_SELECTION_MAPPING_INVALID")
            rows,receipt=table(tables[value["table"]],project,limits);records.append(receipt)
            need(all(value["field"] in row and set(value["where"])<=set(row) for row in rows),"CSV_SELECTION_FIELD_MISSING")
            selected=[row[value["field"]] for row in rows if all(row[k]==v for k,v in value["where"].items())]
            need(selected and all(x is not None for x in selected),"CSV_SELECTION_EMPTY_OR_MISSING");return selected
        if marker=="$json_value":
            need(isinstance(value,dict) and set(value)=={"path","keys"} and isinstance(value["keys"],list) and all(isinstance(x,(str,int)) and not isinstance(x,bool) for x in value["keys"]),"JSON_VALUE_REFERENCE_INVALID")
            path,raw=bounded(value["path"],project,limits["max_bytes"]);records.append({"path":str(path),"sha256":digest(raw),"bytes":len(raw),"kind":marker});result=decode(raw)
            try:
                for key in value["keys"]:result=result[key]
            except (KeyError,IndexError,TypeError):raise InputBlocked("JSON_VALUE_REFERENCE_MISSING") from None
            return result
        path,raw=bounded(value,project,limits["max_bytes"]);records.append({"path":str(path),"sha256":digest(raw),"bytes":len(raw),"kind":marker})
        if marker=="$file_sha256":return digest(raw)
        if marker=="$file_text":return raw.decode("utf-8-sig")
        return decode(raw)
    return {k:materialize(v,tables,project,limits,records) for k,v in template.items()}

def verify(task,required=False):
    """Called after native admission, before a module uses normalized rows."""
    project=Path(task["project_root"]).resolve();refs=[x for s in task.get("sources",[]) for x in s.get("evidence_refs",[]) if x.startswith(PREFIX)]
    need(bool(refs) or not required,"LOCAL_PREPARATION_RECEIPT_REQUIRED")
    for ref in refs:
        parts=ref[len(PREFIX):].split(":",1);need(len(parts)==2 and re.fullmatch(r"[a-f0-9]{64}",parts[0]),"INPUT_RECEIPT_INVALID")
        path,raw=bounded(parts[1],project,2_000_000);need(digest(raw)==parts[0],"INPUT_RECEIPT_CHANGED")
        receipt=decode(raw);need(receipt.get("schema_version")=="ye1-local-ingestion@1.0","INPUT_RECEIPT_INVALID")
        for record in receipt["files"]:
            source,raw=bounded(record["path"],project,record["bytes"]);need(len(raw)==record["bytes"] and digest(raw)==record["sha256"],"SOURCE_CHANGED_AFTER_PREPARATION")
    return True
