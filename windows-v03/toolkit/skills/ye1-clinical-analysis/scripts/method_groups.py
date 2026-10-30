"""Declarative method dependency closure, without importing statistical packages."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def spec():return json.loads((ROOT/"runtime-spec.json").read_text(encoding="utf-8"))
def closure(names):
    source=spec();result=[];active=set()
    def add(name):
        if name in result:return
        if name not in source["groups"] or name in active:raise ValueError("DEPENDENCY_GROUP_INVALID")
        active.add(name)
        for dependency in source["groups"][name]["requires"]:add(dependency)
        active.remove(name);result.append(name)
    for name in names:add(name)
    return result
def for_method(method):
    source=spec()
    if method not in source["method_groups"]:raise ValueError("METHOD_NOT_SUPPORTED")
    return closure(source["method_groups"][method])
