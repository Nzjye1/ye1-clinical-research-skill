"""Thin routing adapter; all existing numerical providers remain byte unchanged."""
from . import api,formal_api
def analyze(request):
    return (formal_api if isinstance(request,dict) and request.get('method_id') in formal_api.METHODS else api).analyze(request)
def project(response,output_dir):
    method=(response.get('public_record') or {}).get('method_id')
    return (formal_api if method in formal_api.METHODS else api).project(response,output_dir)
