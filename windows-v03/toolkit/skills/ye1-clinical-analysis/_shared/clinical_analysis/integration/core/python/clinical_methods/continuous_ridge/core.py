"""Dependency shim: original StudyError and digest definitions only."""
import hashlib
import json

class StudyError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
