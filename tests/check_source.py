"""Check local product identity, manifest, discoverability and inherited owners."""
from pathlib import Path
import argparse,collections,hashlib,importlib.util,json,subprocess,sys

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    root=Path(__file__).resolve().parents[1];toolkit=root/'windows-v03/toolkit';main=toolkit/'skills/ye1-clinical-analysis'
    def load(p):return json.loads(p.read_text(encoding='utf-8'))
    manifest=load(toolkit/'toolkit-manifest.json');spec=load(main/'runtime-spec.json');cap=load(main/'references/CAPABILITIES.json');index=load(main/'references/ENTRY-INDEX.json')
    version=manifest['version'];assert version=='0.3.1-windows-local-noninteractive1'
    assert spec['product_version']==cap['version']==index['version']==version
    for relative,digest in manifest['files'].items():assert hashlib.sha256((toolkit/relative).read_bytes()).hexdigest()==digest,relative
    counts=dict(collections.Counter(x['kind'] for x in cap['entries']))
    assert counts=={'backend':33,'alias':8,'existing_result_view':11,'compat_test':5,'compat_planning':4,'legacy_restricted':1},counts
    assert len(list((toolkit/'skills').glob('*/SKILL.md')))==48
    assert not (main/'.runtime').exists()
    sys.path.insert(0,str(main/'scripts'))
    import toolkit as api
    schemas=[]
    for method in api.catalog()['methods']:
        if api.kind(method)=='legacy_restricted':continue
        schema=api.schema(method);assert schema['method_id']==method['method_id']
        # Planning operations expose parameter schemas, without patient tasks.
        assert schema['parameters'] if method['task_family']=='compat_planning' else schema['task_envelope']
        schemas.append(method['method_id'])
    base='8c244c3f54e47f0655a4e4054b741ad17d2d98d7'
    changed=subprocess.check_output(['git','-C',str(root),'diff',base,'--name-only'],text=True).splitlines()
    protected=[name for name in changed if '/_shared/' in name or '/requirements/' in name or '/third-party/' in name or name.endswith('/scripts/install_windows.py')]
    assert not protected,protected
    ancestors={}
    for commit in ['a59cf22c84deea332a99f06beb8d5ab6315b143e','64ec8ed9a6a98bea8c3d8a034c79db34e32f83c1',base]:
        done=subprocess.run(['git','-C',str(root),'merge-base','--is-ancestor',commit,'HEAD']);assert done.returncode==0
        ancestors[commit]=True
    done=subprocess.run([sys.executable,'-I','-B',str(main/'scripts/toolkit.py'),'doctor','--method','baseline.table1'],capture_output=True,text=True,encoding='utf-8')
    assert done.returncode==2 and json.loads(done.stdout)['reason_code']=='TOOLKIT_INSTALLATION_REQUIRED'
    result={'status':'PASS','version':version,'manifest_files_verified':len(manifest['files']),'capability_counts':counts,'skills':48,'schemas':len(schemas),'ancestors':ancestors,'numerical_installer_and_package_locks_unchanged':True,'facade_and_method_dependency_declarations_may_change_with_regressions':True,'source_uninstalled_doctor_refusal':True}
    with Path(a.output).open('x',encoding='utf-8') as stream:json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps(result))

if __name__=='__main__':main()
