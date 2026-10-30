"""Common aggregate artifact disclosure; provider projections stay unmodified."""
from pathlib import Path
import csv,hashlib,json,re,io
from module_contract import ContractError
ORIGINS={"synthetic_inline_normalized":True,"real_local_normalized":False,"synthetic":True,"real":False}
def disclosure(origin):
    if not isinstance(origin,str) or origin not in ORIGINS:raise ContractError("MODULE_DATA_ORIGIN_UNKNOWN")
    synthetic=ORIGINS[origin]
    return {"core_data_origin":origin,"core_is_synthetic":synthetic},("SYNTHETIC DATA | engineering validation only" if synthetic else "REAL DATA | local analysis; scientific review required")

CSV_ENVELOPE_VERSION="clinical-csv-envelope@1.0"
def _table(path,expected_hash=None):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>8*1024*1024:raise ContractError("TABLE_BYTES_INVALID")
    raw=path.read_bytes()
    if len(raw)>8*1024*1024:raise ContractError("TABLE_BYTES_INVALID")
    digest=hashlib.sha256(raw).hexdigest()
    if expected_hash is not None and digest!=expected_hash:raise ContractError("TABLE_CSV_HASH_MISMATCH")
    with io.StringIO(raw.decode("utf-8-sig"),newline="") as handle:
        reader=csv.DictReader(handle,strict=True);fields=reader.fieldnames
        if not fields or len(fields)!=len(set(fields)):raise ContractError("TABLE_HEADER_INVALID")
        rows=list(reader)
    if any(None in row or any(v is None for v in row.values()) for row in rows):raise ContractError("TABLE_ROW_WIDTH_INVALID")
    return fields,rows,digest

def table_envelope(csv_path,origin,provenance,context=None):
    """The share unit is CSV plus this metadata report, including for zero rows.

    CSV consumers retain the same RFC-style header/data stream. No sentinel data
    row or comment is inserted. The parent artifact manifest binds both files.
    """
    csv_path=Path(csv_path);meta,_=disclosure(origin);fields,rows,csv_hash=_table(csv_path)
    expected={"result_id","method_id","method_version","input_sha256","plan_sha256"}
    if set(provenance)!=expected or any(not isinstance(v,str) or not v for v in provenance.values()):raise ContractError("TABLE_PROVENANCE_INVALID")
    record={"schema_version":CSV_ENVELOPE_VERSION,"csv_file":csv_path.name,
            "csv_sha256":csv_hash,"columns":fields,"row_count":len(rows),
            "data_origin":origin,"is_synthetic":meta["core_is_synthetic"],"provenance":provenance,
            "share_contract":"csv_and_metadata_required","scientific_review":"pending","export_status":"local_only"}
    if context is not None:
        if set(context)!={"task_purpose","test_only"} or context["task_purpose"] not in {"engineering_test","research_analysis"} or type(context["test_only"]) is not bool or context["test_only"]!=(context["task_purpose"]=="engineering_test"):raise ContractError("TABLE_PURPOSE_INVALID")
        record.update(schema_version="clinical-csv-envelope@1.1",**context)
    target=csv_path.with_name(csv_path.name+".metadata.json")
    with target.open("x",encoding="utf-8") as handle:json.dump(record,handle,ensure_ascii=False,indent=2,allow_nan=False);handle.write("\n")
    return target

def read_table_envelope(metadata_path,expected_sha256=None):
    """Verify the pair before exposing source metadata; never infer it from a filename.

    expected_sha256, when supplied, is the metadata hash from the parent manifest.
    File integrity alone does not authenticate a caller-supplied provenance claim.
    """
    metadata_path=Path(metadata_path)
    if not metadata_path.is_file():raise ContractError("TABLE_METADATA_REQUIRED")
    if metadata_path.stat().st_size>128*1024:raise ContractError("TABLE_METADATA_BYTE_LIMIT")
    raw=metadata_path.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ContractError("TABLE_METADATA_HASH_MISMATCH")
    def pairs(items):
        value={}
        for k,v in items:
            if k in value:raise ContractError("TABLE_METADATA_DUPLICATE_KEY")
            value[k]=v
        return value
    record=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=pairs)
    keys={"schema_version","csv_file","csv_sha256","columns","row_count","data_origin","is_synthetic","provenance","share_contract","scientific_review","export_status"}
    if isinstance(record,dict) and record.get("schema_version")=="clinical-csv-envelope@1.1":
        keys|={"task_purpose","test_only"}
        if record.get("task_purpose") not in {"engineering_test","research_analysis"} or type(record.get("test_only")) is not bool or record["test_only"]!=(record["task_purpose"]=="engineering_test"):raise ContractError("TABLE_PURPOSE_INVALID")
    if not isinstance(record,dict) or set(record)!=keys or record["schema_version"] not in {CSV_ENVELOPE_VERSION,"clinical-csv-envelope@1.1"}:raise ContractError("TABLE_METADATA_SCHEMA_INVALID")
    provenance=record["provenance"]
    if not isinstance(provenance,dict) or set(provenance)!={"result_id","method_id","method_version","input_sha256","plan_sha256"} or any(not isinstance(v,str) or not v for v in provenance.values()):raise ContractError("TABLE_PROVENANCE_INVALID")
    if any(re.fullmatch("[0-9a-f]{64}",provenance[k]) is None for k in ("input_sha256","plan_sha256")):raise ContractError("TABLE_PROVENANCE_INVALID")
    meta,_=disclosure(record["data_origin"])
    if type(record["is_synthetic"]) is not bool or record["is_synthetic"]!=meta["core_is_synthetic"]:raise ContractError("TABLE_ORIGIN_MISMATCH")
    name=record["csv_file"]
    if not isinstance(name,str) or not name or name in (".","..") or Path(name).name!=name or "/" in name or "\\" in name:raise ContractError("TABLE_METADATA_PATH_INVALID")
    if metadata_path.name!=name+".metadata.json":raise ContractError("TABLE_METADATA_PAIR_NAME_MISMATCH")
    path=metadata_path.parent/name
    if not path.is_file():raise ContractError("TABLE_CSV_HASH_MISMATCH")
    fields,rows,csv_hash=_table(path,record["csv_sha256"])
    if csv_hash!=record["csv_sha256"]:raise ContractError("TABLE_CSV_HASH_MISMATCH")
    if fields!=record["columns"] or type(record["row_count"]) is not int or record["row_count"]!=len(rows):raise ContractError("TABLE_METADATA_COUNTS_MISMATCH")
    if record["share_contract"]!="csv_and_metadata_required" or record["scientific_review"]!="pending" or record["export_status"]!="local_only":raise ContractError("TABLE_METADATA_SCHEMA_INVALID")
    for row in rows:
        if "core_data_origin" in fields and row["core_data_origin"]!=record["data_origin"]:raise ContractError("TABLE_ORIGIN_MISMATCH")
        if "core_is_synthetic" in fields and row["core_is_synthetic"]!=str(record["is_synthetic"]):raise ContractError("TABLE_ORIGIN_MISMATCH")
    return record,rows
def figure(source,destination,origin):
    from PIL import Image,ImageDraw,ImageFont,PngImagePlugin
    from matplotlib import font_manager
    meta,label=disclosure(origin)
    with Image.open(source) as original:
        original.load();image=original.convert("RGBA")
        font=ImageFont.truetype(font_manager.findfont("DejaVu Sans"),14)
        lines=[label,"Source: "+origin];scratch=ImageDraw.Draw(image)
        # Fit text by wrapping words; the original plot area is never cropped.
        wrapped=[]
        for line in lines:
            current=""
            for word in line.split():
                candidate=(current+" "+word).strip()
                if current and scratch.textlength(candidate,font=font)>image.width-20:wrapped.append(current);current=word
                else:current=candidate
            wrapped.append(current)
        footer=16+20*len(wrapped);canvas=Image.new("RGBA",(image.width,image.height+footer),"white");canvas.paste(image,(0,0))
        draw=ImageDraw.Draw(canvas);draw.line((0,image.height,image.width,image.height),fill="#9bafba",width=1)
        for i,line in enumerate(wrapped):draw.text((10,image.height+8+20*i),line,fill="#842b20" if meta["core_is_synthetic"] else "#16455d",font=font)
        png=PngImagePlugin.PngInfo();png.add_text("data_origin",origin);png.add_text("is_synthetic",str(meta["core_is_synthetic"]).lower());png.add_text("disclosure",label)
        Path(destination).parent.mkdir(parents=True,exist_ok=True)
        with Path(destination).open("xb") as handle:canvas.save(handle,format="PNG",pnginfo=png,dpi=original.info.get("dpi",(150,150)))
    return meta
