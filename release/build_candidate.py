"""Plan candidate packages from tracked source; build only with explicit --build.

Uses the existing static-candidate ZIP/manifest layout. Does not run installers,
download dependencies, change repository files, or publish. Plans do not create
ZIPs or stage a customer installation.
"""
from pathlib import Path,PurePosixPath
import argparse,datetime,fnmatch,hashlib,json,re,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
TOOLKIT='windows-v03/toolkit/'
MAIN=TOOLKIT+'skills/ye1-clinical-analysis/'

def sha(raw):return hashlib.sha256(raw).hexdigest()
def canonical(value):return (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args],text=True,encoding='utf-8').strip()
def matches(path,patterns):return any(fnmatch.fnmatchcase(path,p) for p in patterns)
def read_json(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def safe_output(path):
    if not path.is_absolute():raise ValueError('ABSOLUTE_OUTPUT_DIRECTORY_REQUIRED')
    if any(p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()) for p in (path,*path.parents)):raise ValueError('LINKED_OUTPUT_UNSUPPORTED')
    path=path.resolve()
    if path==ROOT or path.is_relative_to(ROOT) or ROOT.is_relative_to(path):raise ValueError('INDEPENDENT_OUTPUT_DIRECTORY_REQUIRED')
    if any(p.lower() in {'temp','tmp'} for p in path.parts):raise ValueError('NON_TEMP_OUTPUT_REQUIRED')
    if not path.is_dir():raise ValueError('EXISTING_OUTPUT_DIRECTORY_REQUIRED')
    return path

def validate_dependency_closure(files):
    prefix='skills/ye1-clinical-analysis/_shared/clinical_analysis/'
    req=read_json(MAIN+'_shared/clinical_analysis/runtime-requirements.json')
    core=prefix+'integration/core/'
    required=set(core+p for p in req['code_files'])|set(core+p for p in req['protected_source_hashes'])
    for relative,digest in req['protected_source_hashes'].items():
        if core+relative not in files or sha(files[core+relative])!=digest:raise ValueError('PROTECTED_RUNTIME_SOURCE_DRIFT: '+relative)
    for path in files:
        if any(path.startswith(core+d+'/') for d in ['src/clinanalysis','python/clinical_methods','schemas']):required.add(path)
    lock=read_json(MAIN+'_shared/clinical_analysis/integration/module-lock.json')
    for module in lock['modules']:
        base=prefix+'modules/'+module['directory']+'/'
        required.add(base+module['manifest_path'])
        if sha(files.get(base+module['manifest_path'],b''))!=module['manifest_sha256']:raise ValueError('MODULE_MANIFEST_DRIFT: '+module['directory'])
        for key in ['files_sha256','supplementary_files_sha256']:
            for relative in module.get(key,{}):
                if '/_vendor/' not in '/'+relative:
                    required.add(base+relative)
                    if sha(files.get(base+relative,b''))!=module[key][relative]:raise ValueError('MODULE_RUNTIME_SOURCE_DRIFT: '+base+relative)
    missing=sorted(required-set(files))
    if missing:raise ValueError('REQUIRED_RUNTIME_SOURCE_EXCLUDED: '+','.join(missing))
    return len(required)

def payload(kind,tracked,policy):
    toolkit={p[len(TOOLKIT):]:(ROOT/p).read_bytes() for p in tracked if p.startswith(TOOLKIT)}
    original=read_json(TOOLKIT+'toolkit-manifest.json')
    for path,digest in original['files'].items():
        if path not in toolkit or sha(toolkit[path])!=digest:raise ValueError('SOURCE_DISTRIBUTION_MANIFEST_MISMATCH: '+path)
    if kind=='client':
        selected={p:raw for p,raw in toolkit.items() if not matches(p,policy['client_exclude']) or p in policy['client_keep_required']}
        selected.pop('toolkit-manifest.json',None)
        closure=validate_dependency_closure(selected)
        output={'toolkit/'+p:raw for p,raw in selected.items()}
        manifest={**original,'files':{p:sha(raw) for p,raw in sorted(selected.items()) if p.startswith('skills/')},'delivery_status':'candidate archive; independent package acceptance pending'}
        output['toolkit/toolkit-manifest.json']=canonical(manifest)
        excluded=sorted(set(toolkit)-set(selected)-{'toolkit-manifest.json'})
    else:
        allowed={'LICENSE',*policy['source_release_files']}
        selected={p:(ROOT/p).read_bytes() for p in tracked if (p in allowed or p.startswith('tests/') or p.startswith(TOOLKIT)) and not matches(p,policy['source_exclude'])}
        # Portable source instructions replace the local integration handoff.
        selected['README.md']=(ROOT/'release/SOURCE-README.md').read_bytes()
        main_files={p[len(TOOLKIT):]:raw for p,raw in selected.items() if p.startswith(TOOLKIT) and p!=TOOLKIT+'toolkit-manifest.json'}
        closure=validate_dependency_closure(main_files)
        selected[TOOLKIT+'toolkit-manifest.json']=canonical({**original,'files':{p:sha(raw) for p,raw in sorted(main_files.items()) if p.startswith('skills/')},'delivery_status':'source archive; installed runtime not included'})
        output={'source/'+p:raw for p,raw in selected.items()}
        excluded=sorted(set(tracked)-set(selected))
    for name in output:
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or set(rel.parts)&set(policy['forbidden_parts']):raise ValueError('FORBIDDEN_PACKAGE_PATH: '+name)
        if rel.suffix.lower() in policy['forbidden_suffixes']:raise ValueError('FORBIDDEN_PACKAGE_EXTENSION: '+name)
    # Actual personal paths and build-machine runtime paths are forbidden.
    # Generic Windows tutorial placeholders and source redaction regex literals
    # are intentionally retained; they are not environment bindings.
    forbidden=[rb'(?i)[a-z]:[\\/]+Users[\\/]+(?!<)[^\\/\r\n" ]+',rb'(?i)[a-z]:[\\/]+SKILL',rb'(?i)AppData[\\/]+Local[\\/]+Temp']
    leaks=[]
    for name,raw in output.items():
        if PurePosixPath(name).suffix.lower() in {'.md','.json','.py','.r','.txt','.yaml','.yml','.lock'} and any(re.search(p,raw) for p in forbidden):leaks.append(name)
    if leaks:raise ValueError('DEVELOPER_OR_PERSONAL_PATH_IN_PACKAGE: '+','.join(leaks))
    return output,excluded,closure

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kind',choices=['source','client'],required=True);p.add_argument('--output-root',required=True);p.add_argument('--expected-commit');p.add_argument('--plan',action='store_true');p.add_argument('--build',action='store_true');a=p.parse_args()
    if a.plan and a.build:raise ValueError('CHOOSE_PLAN_OR_BUILD')
    dest=safe_output(Path(a.output_root));commit=git('rev-parse','HEAD');dirty=bool(git('status','--porcelain'))
    if a.build and (dirty or a.expected_commit!=commit):raise ValueError('CLEAN_EXACT_COMMIT_REQUIRED_TO_BUILD')
    policy=read_json('release/PACKAGING-POLICY.json');version=read_json(policy['version_source'])['product_version']
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z._-]{0,100}',version):raise ValueError('SAFE_PRODUCT_VERSION_REQUIRED')
    tracked=git('ls-files').splitlines();files,excluded,closure=payload(a.kind,tracked,policy)
    revision={'schema_version':'ye1-source-revision@1.0','commit':commit,'product_version':version,'package_kind':a.kind,'source_dirty_when_planned':dirty,'package_acceptance':'pending','physical_cold_pc_tested':False}
    files[('toolkit/' if a.kind=='client' else 'source/')+'SOURCE-REVISION.json']=canonical(revision)
    stem=f'ye1-clinical-{a.kind}-{version}-{commit[:8]}'
    receipt=dest/(stem+('.build.json' if a.build else '.plan.json'))
    if receipt.exists() or (a.build and (dest/(stem+'.zip')).exists()):raise ValueError('EXISTING_CANDIDATE_OR_RECEIPT_PRESERVED')
    record={'schema_version':'ye1-candidate-plan@1.0','status':'PLANNED_ONLY','kind':a.kind,'version':version,'commit':commit,'source_dirty':dirty,'archive_name':stem+'.zip','required_runtime_sources_checked':closure,'members':len(files),'uncompressed_bytes':sum(len(v) for v in files.values()),'files':{n:{'bytes':len(raw),'sha256':sha(raw)} for n,raw in sorted(files.items())},'excluded_source_paths':excluded,'installed_runtime_bundled':False,'patient_data_bundled':False,'independent_install_acceptance':'PENDING_NEXT_TASK','remote_actions':False}
    if a.build:
        archive=dest/(stem+'.zip')
        with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name,raw in sorted(files.items()):
                info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
                z.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:raise ValueError('ARCHIVE_CRC_FAILED')
        record.update(status='BUILT_NOT_ACCEPTED',archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size)
    with receipt.open('xb') as f:f.write(canonical(record))
    print(json.dumps({k:v for k,v in record.items() if k not in {'files','excluded_source_paths'}},ensure_ascii=False))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,subprocess.CalledProcessError) as error:
        print(json.dumps({'status':'NOT_COMPLETE','reason':str(error)},ensure_ascii=False));raise SystemExit(2)
