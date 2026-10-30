"""Fresh declared-group installs and real synthetic export/status regressions.

No --all or manual --groups plot workaround. Uses a new project, original
installers and the supplied hash-locked wheel cache. Outputs/logs never reused.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,os,subprocess,sys

REPO=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workdir',required=True);p.add_argument('--rscript',required=True);p.add_argument('--wheelhouse',required=True);a=p.parse_args()
    area=Path(a.workdir).resolve();area.mkdir(parents=True,exist_ok=False);project=area/'中文 独立研究';project.mkdir()
    toolkit=REPO/'windows-v03/toolkit';main=project/'.agents/skills/ye1-clinical-analysis';records=[]
    env=os.environ.copy()
    for key in list(env):
        if key=='LANG' or key.startswith('LC_'):env.pop(key)
    env['PYTHONDONTWRITEBYTECODE']='1'
    def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
    def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
    def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def run(label,command,expected=0):
        command=list(map(str,command));start=datetime.datetime.now(datetime.timezone.utc).isoformat()
        done=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,env=env,timeout=1800)
        (area/(label+'.stdout')).write_bytes(done.stdout);(area/(label+'.stderr')).write_bytes(done.stderr)
        records.append({'label':label,'command':command,'started_utc':start,'returncode':done.returncode,'expected':expected});save(area/'commands.json',records)
        print(json.dumps({'step':label,'returncode':done.returncode}),flush=True);assert done.returncode==expected,label
        return done
    foundation=[sys.executable,'-I','-B','-X','utf8'];options=['--rscript',a.rscript,'--wheelhouse',a.wheelhouse,'--install']
    run('fresh-base-ml',foundation+[toolkit/'setup_windows.py','--project',project,'--groups','base','ml',*options])
    python=main/'.runtime/python/Scripts/python.exe';base=[python,'-I','-B','-X','utf8'];profile=main/'.runtime/toolkit-profile.json'
    initial=load(profile)['installed_groups'];assert set(initial)=={'base','ml'}
    probe=run('pillow-absent-before-method',base+['-c',"import importlib.util,json;print(json.dumps({'PIL_available':importlib.util.find_spec('PIL') is not None}))"])
    assert json.loads(probe.stdout)['PIL_available'] is False
    x=run('rf-requires-plot-before-execution',base+[main/'scripts/toolkit.py','doctor','--method','prediction.binary.random_forest'],expected=2)
    blocked=json.loads(x.stdout);assert blocked['reason_code']=='DEPENDENCY_GROUP_NOT_INSTALLED' and blocked['missing_groups']==['plot']
    # The ordinary baseline still succeeds without the optional plot group.
    scripts=REPO/'tests/regression';baseline_area=area/'baseline-base-ml'
    run('baseline-without-plot',base+[scripts/'test_core_forward.py','--package',main,'--area',baseline_area,'--methods','baseline.table1'])
    baseline=load(baseline_area/'receipt.json')['results'][0];assert baseline['status']=='PASS'
    out=Path(baseline['output']);before={str(f):sha(f) for f in out.rglob('*') if f.is_file()}
    peers=out.parent/'private';before.update({str(f):sha(f) for f in peers.glob(out.name+'.*') if f.is_file()})
    x=run('baseline-repeat-specific-status',base+[main/'scripts/toolkit.py','run','--method','baseline.table1','--task',baseline['task']],expected=2)
    response=json.loads(x.stdout);assert response['status']=='blocked' and response['reason_code']=='OUTPUT_ALREADY_EXISTS' and response['analysis_executed'] is False
    assert all(sha(Path(f))==h for f,h in before.items())
    # Previous failed-attempt fixture: preserve it and refuse before engine work.
    draft=load(next(baseline_area.glob('*/*-draft.json')));owner=Path(draft['project_root']);failed=owner/'runs'/'失败快照 保留'
    draft['task']['execution']['output_dir']=str(failed);draft_path=owner/'retry-snapshot-draft.json';save(draft_path,draft)
    x=run('prepare-snapshot-fixture',base+[main/'scripts/prepare_task.py','--draft',draft_path]);prepared=json.loads(x.stdout)['task']
    sentinel=failed.parent/'private'/(failed.name+'.task.json');sentinel.parent.mkdir(exist_ok=True);sentinel.write_bytes(b'old failed attempt; never overwrite\n');marker=sha(sentinel)
    x=run('failed-snapshot-specific-status',base+[main/'scripts/toolkit.py','run','--method','baseline.table1','--task',prepared],expected=2)
    response=json.loads(x.stdout);assert response['reason_code']=='OUTPUT_SNAPSHOT_ALREADY_EXISTS' and response['analysis_executed'] is False and not failed.exists() and sha(sentinel)==marker
    # This is the corrected declared-method install, not a manual plot add-on.
    run('install-rf-by-method',foundation+[main/'scripts/install_windows.py','--method','prediction.binary.random_forest',*options])
    declared=load(profile)['installed_groups'];assert set(declared)=={'base','ml','plot'}
    run('rf-doctor-after-declared-install',base+[main/'scripts/toolkit.py','doctor','--method','prediction.binary.random_forest'])
    run('rf-hgb-actual-exports',base+[scripts/'test_module_forward.py','--package',main,'--area',area/'trees','--methods','prediction.binary.random_forest','prediction.binary.hist_gradient_boosting'])
    tree_records=load(area/'trees/receipt.json')['results'];assert len(tree_records)==2 and all(r['status']=='PASS' for r in tree_records)
    exported=[]
    for item in tree_records:
        output=Path(item['output']);result=load(output/'result.json');assert result['execution_status']=='complete'
        assert len([f for f in result['artifacts'] if f['kind']=='figure'])==3
        for f in result['artifacts']:assert sha(output/f['relative_path'])==f['sha256']
        exported.append({'method':item['method'],'status':'complete','registered_artifacts':len(result['artifacts']),'output':str(output)})
    save(area/'declared-method-export-proof.json',{'status':'PASS','initial_groups':initial,'PIL_initially_absent':True,'RF_initial_doctor_refused_plot':True,'groups_after_method_install':declared,'manual_plot_install_used':False,'exports':exported,'baseline_repeat_and_failed_snapshot_preserved':True})
    # Other affected methods use the same publisher; install by their own IDs.
    for label,method in [('matching','mediation.linear.binary_exposure'),('penalized','prediction.survival.cox.lasso'),('shap','explanation.binary.random_forest.tree_shap')]:
        run('install-'+label+'-by-method',foundation+[main/'scripts/install_windows.py','--method',method,*options])
    run('matching-actual-exports',base+[scripts/'test_module_forward.py','--package',main,'--area',area/'matching','--methods','causal.psm.att.binary','causal.psm.matched.survival','mediation.linear.binary_exposure'])
    core=area/'core-models'
    run('frozen-model-prerequisites',base+[scripts/'test_core_forward.py','--package',main,'--area',core,'--methods','prediction.continuous.signed.lasso','prediction.survival.cox','prediction.survival.cox.lasso'])
    run('affected-frozen-exports',base+[scripts/'test_frozen_forward.py','--package',main,'--area',area/'frozen','--core-area',core,'--rf-area',area/'trees','--hgb-area',area/'trees'])
    results={}
    for label in ['matching','core-models','frozen']:
        result=load(area/label/'receipt.json')['results'];assert result and all(r['status']=='PASS' for r in result);results[label]=len(result)
    proof=load(area/'declared-method-export-proof.json')
    result={'status':'PASS','installed_main':str(main),'declared_method_export_proof':proof,'affected_suites':results,'final_groups':load(profile)['installed_groups'],'fresh_new_project':True,'old_acceptance_project_modified':False,'real_patient_data_used':False,'ordinary_PBC_baseline':'NOT_TESTED','fresh_GUI_discovery':'NOT_TESTED','scientific_review':'pending','commands':str(area/'commands.json')}
    save(area/'result.json',result);print(json.dumps({k:v for k,v in result.items() if k not in {'declared_method_export_proof'}},ensure_ascii=False))

if __name__=='__main__':main()
