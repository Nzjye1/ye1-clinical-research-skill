"""Formal runtime binding, isolated R library prepended only for this provider."""
import copy
import json
import platform
from pathlib import Path
from . import module
from .contracts import need,digest
ROOT=Path(__file__).resolve().parent
PACKAGES=['mclust','lcmm','mvtnorm','spacefillr','marqLevAlg','doParallel','nlme','survival','numDeriv','Rcpp','foreach','iterators','jsonlite']
FILES=['formal_api.py','formal_runtime.py','formal_provider.py','formal_models.R','formal_engine.R',
       'formal_artifacts.py','contracts.py','schema_tools.py','module.py']
def runtime():
    result=copy.deepcopy(module.DEFAULT_RUNTIME)
    local=json.loads((ROOT.parents[1]/'integration/module-runtime.json').read_text(encoding='utf-8-sig'))
    result['r_libraries'].insert(0,local['latent_r_library'])
    return result
def probe():
    result=module.runtime_probe(runtime())
    rbin=Path(runtime()['rscript']).parent
    files=([('R/bin/exec/R',rbin/'exec/R'),('R/lib/libR.dylib',rbin.parent/'lib/libR.dylib')]
           if platform.system()=='Darwin' else [('R/bin/x64/'+name,rbin/'x64'/name) for name in ['R.dll','Rblas.dll','Rlapack.dll','Rscript.exe']])
    for key,path in files:
        if path.is_file():result['files_sha256'][key]=module.sha_file(path)
    for name in PACKAGES:
        path=result.get('r_package_paths',{}).get(name)
        if not path:continue
        native='libs/'+name+'.so' if platform.system()=='Darwin' else 'libs/x64/'+name+'.dll'
        for suffix in ['DESCRIPTION','R/'+name+'.rdb','R/'+name+'.rdx',native]:
            p=Path(path)/suffix
            if p.is_file():result['files_sha256']['R/'+name+'/'+suffix]=module.sha_file(p)
    return result
def binding(p):
    return {'R':p['R'],'platform':p['platform'],'python':p['python'],
      'packages':{n:p['r_packages'].get(n) for n in PACKAGES},
      'files_sha256':{k:v for k,v in p['files_sha256'].items() if k.startswith('R/') or k in ['rscript_executable','python_executable']}}
def source_hashes():
    return {f:module.sha_file(ROOT/f) for f in FILES+sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'formal_schemas').glob('*.json'))}
