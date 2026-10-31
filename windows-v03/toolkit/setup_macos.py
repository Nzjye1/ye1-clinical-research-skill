"""Install this verified Skill collection into one project, preserving peers."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,os,platform,subprocess,sys,uuid
ROOT=Path(__file__).resolve().parent
class InstallBlocked(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)
def need(ok,code):
    if not ok:raise InstallBlocked(code)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def safe(path):
    need(not any(x.is_symlink() or (hasattr(x,"is_junction") and x.is_junction()) for x in (path,*path.parents)),"LINKED_INSTALL_PATH_UNSUPPORTED");return path.resolve()
def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)
def main():
    need(platform.system()=="Darwin" and platform.machine().lower() in {"arm64","aarch64"},"MACOS_ARM64_REQUIRED")
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',required=True);p.add_argument('--rscript');p.add_argument('--groups',nargs='+',default=['base']);p.add_argument('--method');p.add_argument('--all',action='store_true');p.add_argument('--wheelhouse');p.add_argument('--install',action='store_true');a=p.parse_args()
    manifest=json.loads((ROOT/'toolkit-manifest.json').read_text(encoding='utf-8'));need(manifest['schema_version']=='ye1-toolkit-distribution@1.0',"DISTRIBUTION_MANIFEST_INVALID")
    files=manifest['files'];skills=set()
    for relative,digest in files.items():
        rel=PurePosixPath(relative);need(not rel.is_absolute() and '..' not in rel.parts and len(rel.parts)>2 and rel.parts[0]=='skills',"DISTRIBUTION_PATH_INVALID")
        source=safe(ROOT/relative);need(source.is_relative_to(ROOT) and source.is_file() and sha(source)==digest,"DISTRIBUTION_BYTES_CHANGED");skills.add(rel.parts[1])
    project=safe(Path(a.project));need(project.is_dir(),"EXISTING_PROJECT_DIRECTORY_REQUIRED");target=safe(project/'.agents/skills')
    need(not any((target/name).exists() for name in skills),"EXISTING_NAMED_SKILL_PRESERVED_USE_NEW_PROJECT_OR_REVIEW_UPDATE")
    result={'status':'READY_TO_INSTALL','project':str(project),'target':str(target),'skill_directories':len(skills),'statistical_algorithm_count':"See capability matrix; Skill count is not algorithm count",'groups':a.groups,'all_groups':a.all,'global_configuration_changed':False,'user_data_bundled':False}
    if not a.install:print(json.dumps(result));return 0
    need(a.rscript is not None,"EXPLICIT_RSCRIPTPATH_REQUIRED")
    target.mkdir(parents=True,exist_ok=True);staging=safe(target/('.ye1-install-staging-'+uuid.uuid4().hex));staging.mkdir()
    state=staging/'installation-source.json';save(state,{'distribution_sha256':sha(ROOT/'toolkit-manifest.json'),'project':str(project),'status':'copying','existing_peer_skills_preserved':True})
    for relative,digest in files.items():
        rel=PurePosixPath(relative);destination=staging/Path(*rel.parts[1:]);destination.parent.mkdir(parents=True,exist_ok=True)
        with destination.open('xb') as out:out.write((ROOT/relative).read_bytes())
        need(sha(destination)==digest,"INSTALLED_COPY_HASH_MISMATCH")
    # A failed install leaves its staged files and evidence for support. No
    # foreign directories or existing Skills are moved, removed or overwritten.
    for name in sorted(skills):
        destination=safe(target/name);need(not destination.exists() and destination.is_relative_to(target),"TARGET_SKILL_APPEARED_DURING_INSTALL")
        (staging/name).rename(destination)
    main=target/'ye1-clinical-analysis';command=[sys.executable,'-I','-B','-X','utf8',str(main/'scripts/install_macos.py'),'--rscript',a.rscript,'--groups',*a.groups,'--install']
    if a.method:command+=['--method',a.method]
    if a.all:command+=['--all']
    if a.wheelhouse:command+=['--wheelhouse',str(Path(a.wheelhouse).resolve())]
    done=subprocess.run(command,stdin=subprocess.DEVNULL,cwd=main)
    save(staging/'installation-result.json',{'status':'complete' if done.returncode==0 else 'dependencies_incomplete','returncode':done.returncode,'main_skill':str(main),'source_manifest_sha256':sha(ROOT/'toolkit-manifest.json')})
    if done.returncode:return done.returncode
    print(json.dumps({**result,'status':'PROJECT_SKILLS_INSTALLED_AND_RUNTIME_VERIFIED','main_skill':str(main),'next':'Open this project in macOS Codex; use $ye1-clinical-analysis or a named individual Skill. Retain local install logs.'}));return 0
if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError) as error:
        print(json.dumps({'status':'PROJECT_INSTALLATION_NOT_COMPLETE','reason_code':getattr(error,'code','LOCAL_INSTALLATION_FAILED'),'action':'Keep the archive, staged copy and logs for support; do not edit scientific code, dependency locks or existing Skills.'}));raise SystemExit(2)
