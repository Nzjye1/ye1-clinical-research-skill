"""Lightweight quotable decision evidence. Host classification is not identity authentication."""
import hashlib
from pathlib import Path

def validate(record,quote_key='quote',*,simulated=False):
    kind='simulated' if simulated else record.get('source_kind','unknown')
    if kind=='simulated':return {'kind':'simulated','identity_authenticated':False,'scope':'TEST_ONLY'}
    if kind!='direct_user':raise ValueError('Confirmation source unknown; keep pending and obtain an actual quotable user answer')
    p=Path(record.get('source_path') or '')
    quote=record.get(quote_key)
    if not p.is_file() or p.is_symlink() or not record.get('source_locator') or not quote:raise ValueError('Direct confirmation needs source file, message locator and quote')
    if quote not in p.read_text(encoding='utf8'):raise ValueError('Confirmation quote absent from actual source record')
    return {'kind':kind,'source_path':str(p.resolve()),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'source_locator':record['source_locator'],'quote':quote,'identity_authenticated':False}
