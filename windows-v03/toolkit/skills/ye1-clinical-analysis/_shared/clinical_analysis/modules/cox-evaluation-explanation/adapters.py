"""Explicit synthetic table adapters. No database reader or learned mapping."""
from __future__ import annotations
import math

def normalize_source(rows, spec, column_map, conversions=None, category_maps=None, missing_codes=None):
    conversions=conversions or {};category_maps=category_maps or {};missing_codes=missing_codes or {}
    fields=[spec["id"],spec["duration"],spec["event"]]+[f["name"] for f in spec["features"]]
    group=spec["split"]["group_field"]
    if group is not None: fields.append(group)
    if set(column_map)!=set(fields) or len(set(column_map.values()))!=len(fields):
        raise ValueError("CE_ADAPTER_MAPPING_INVALID")
    if (set(conversions)|set(category_maps)|set(missing_codes))-set(fields):
        raise ValueError("CE_ADAPTER_EXTRA_DECLARATION")
    result=[]
    for row in rows:
        if set(row)!=set(column_map.values()): raise ValueError("CE_ADAPTER_ROW_FIELDS_INVALID")
        values={}
        for target,source in column_map.items():
            value=row[source]
            if value is None or any(type(value) is type(code) and value==code for code in missing_codes.get(target,[])):
                value=None
            elif target in category_maps:
                if value not in category_maps[target]: raise ValueError("CE_ADAPTER_CATEGORY_UNDECLARED")
                value=category_maps[target][value]
            elif target in conversions:
                conversion=conversions[target]
                if set(conversion)!={"scale","offset","source_unit","target_unit"}:raise ValueError("CE_ADAPTER_UNIT_RULE_INVALID")
                if type(value) not in (int,float) or not math.isfinite(value):raise ValueError("CE_ADAPTER_NUMERIC_INVALID")
                value=value*conversion["scale"]+conversion["offset"]
                if not math.isfinite(value):raise ValueError("CE_ADAPTER_NUMERIC_INVALID")
            values[target]=value
        result.append({"subject_id":values[spec["id"]],"group_id":None if group is None else values[group],
            "values":[values[f["name"]] for f in spec["features"]],"duration":values[spec["duration"]],"event":values[spec["event"]]})
    return result
