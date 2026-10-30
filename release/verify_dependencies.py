"""Read-only dependency/archive/license and optional installed-path audit."""
from pathlib import Path
import argparse,datetime,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1];MAIN=ROOT/'windows-v03/toolkit/skills/ye1-clinical-analysis'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def no_temp(path):return not any(part.lower() in {'temp','tmp'} for part in path.parts)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--wheelhouse',required=True);p.add_argument('--output',required=True);p.add_argument('--runtime-root');a=p.parse_args()
    cache=Path(a.wheelhouse).resolve();assert cache.is_dir() and no_temp(cache)
    assert not any(x.is_symlink() or (hasattr(x,'is_junction') and x.is_junction()) for x in (cache,*cache.parents))
    spec=load(MAIN/'runtime-spec.json');deps=load(MAIN/'references/DEPENDENCIES.json');assert deps['product_version']==spec['product_version']
    py=[];notices=0
    for package,entry in zip(spec['python_packages'],deps['python']):
        assert package['name']==entry['name'] and package['version']==entry['version']
        wheel=cache/package['filename'];assert sha(wheel)==entry['sha256']==package['sha256']
        assert entry['license_files']
        for item in entry['license_files']:assert sha(MAIN/item['path'])==item['sha256'];notices+=1
        py.append({'name':package['name'],'version':package['version'],'sha256':sha(wheel)})
    assert len(py)==26 and len(deps['python'])==len(py)
    r=[]
    for package,entry in zip(spec['r_packages'],deps['R']):
        assert package['name']==entry['name'] and package['license']==entry['license']
        for kind in ['binary','source']:
            archive=MAIN/'third-party/r'/package[kind]['filename'];assert sha(archive)==package[kind]['sha256']==entry[kind]['sha256']
        r.append(package['name'])
    assert len(r)==14 and (ROOT/'LICENSE').read_bytes()==(MAIN/'LICENSE').read_bytes()
    result={'status':'PASS','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'python_wheels':len(py),'python_license_files':notices,'R_binary_source_pairs':len(r),'downloaded':False,'installed_or_reinstalled':False,'cache_non_temp':True,'cache':str(cache),'MIT_scope':'own code only; third-party notices preserved','runtime_layout':None}
    if a.runtime_root:
        runtime_root=Path(a.runtime_root).resolve();profile=load(runtime_root/'.runtime/toolkit-profile.json')
        assert Path(profile['product_root']).resolve()==runtime_root
        foundation=[Path(profile['base_python']).resolve(),Path(profile['R_home']).resolve()]
        files={**profile['foundation_files'],**profile['config_files']}
        for group in profile['groups'].values():files.update(group['files'])
        outside=[]
        for raw in files:
            path=Path(raw).resolve()
            if not no_temp(path) or not (path.is_relative_to(runtime_root) or any(path.is_relative_to(base) for base in foundation)):outside.append(raw)
        assert not outside,outside
        config_paths=[]
        for raw in profile['config_files']:
            path=Path(raw)
            if path.suffix=='.json':
                def walk(x):
                    if isinstance(x,dict):
                        for k,v in x.items():walk(k);walk(v)
                    elif isinstance(x,list):
                        for v in x:walk(v)
                    elif isinstance(x,str) and re.match(r'^[A-Za-z]:[\\/]',x):
                        target=Path(x).resolve();assert no_temp(target)
                        assert target.is_relative_to(runtime_root) or any(target.is_relative_to(base) for base in foundation),x
                        config_paths.append(x)
                walk(load(path))
        result['runtime_layout']={'status':'PASS','installed_root':str(runtime_root),'installed_groups':profile['installed_groups'],'bound_paths_checked':len(files),'configuration_paths_checked':len(config_paths),'other_development_projects_or_temp_bindings':outside,'foundation_programs_are_external':True,'installed_package_bytes_not_rehashed_in_this_layout_only_audit':True}
    with Path(a.output).open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in {'runtime_layout','cache'}},ensure_ascii=False))

if __name__=='__main__':main()
