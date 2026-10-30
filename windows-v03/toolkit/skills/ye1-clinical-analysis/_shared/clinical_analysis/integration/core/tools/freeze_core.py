"""Explicit local candidate lock generation; never invoked automatically by runs."""
import hashlib
import json
from pathlib import Path

from clinical_test_paths import configure_process, configured_reference, load_runtime, runtime_path
ROOT = Path(__file__).resolve().parents[1]
SOURCE_R = configured_reference("CLINICAL_TEST_LEGACY_SOURCE_R")
SOURCE_A = configured_reference("CLINICAL_TEST_LEGACY_SOURCE_ASSOCIATION")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    import platform, numpy, scipy, statsmodels, sklearn, pandas
    code = sorted(set(p for folder in ('src/clinanalysis','python/clinical_methods','schemas')
                      for p in (ROOT/folder).rglob('*')
                      if p.is_file() and '__pycache__' not in p.parts))
    code += [ROOT/'tools/run_core.R']
    hashes = {p.relative_to(ROOT).as_posix(): sha(p) for p in code}
    lock = {
      'core_version':'0.10.0-candidate1',
      'status':'LOCAL_CANDIDATE_NOT_RELEASED',
      'rscript':str(runtime_path('rscript')),
      'rscript_engine':str(runtime_path('rscript_engine')),
      'python':str(runtime_path("python")),
      'r_libraries':load_runtime()['r_libraries'],
      'versions':{'R':'4.6.1','jsonlite':'2.0.0','digest':'0.6.39'},
      'r_package_paths':load_runtime()['r_package_paths'],
      'python_versions':{'python':platform.python_version(),'numpy':numpy.__version__,
                         'scipy':scipy.__version__,'statsmodels':statsmodels.__version__},
      'prediction_python_versions':{'python':platform.python_version(),'numpy':numpy.__version__,
                         'scipy':scipy.__version__,'statsmodels':statsmodels.__version__,
                         'sklearn':sklearn.__version__,'pandas':pandas.__version__},
      'code_hashes':hashes,
      'installation_performed':False,
      'license_release_decision':'NOT_MADE',
      'host_isolation_claim':'NOT_ESTABLISHED',
    }
    lock['executable_hashes']={p:sha(Path(p)) for p in (lock['rscript'],lock['rscript_engine'],lock['python'])}
    # A numerical preflight supplies exact provider hashes, never a runtime
    # search for another algorithm or a fallback after fitting failure.
    import importlib.util
    prediction_bridge=ROOT/'python/clinical_methods/prediction_bridge.py'
    if prediction_bridge.exists():
        import sys
        sys.path.insert(0,str(prediction_bridge.parent))
        module_spec=importlib.util.spec_from_file_location('candidate_prediction_bridge',prediction_bridge)
        module=importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        lock['prediction_provider_versions']=module.provider_versions()
    plan_bridge=ROOT/'python/clinical_methods/association_plan_bridge.py'
    if plan_bridge.exists():
        module_spec=importlib.util.spec_from_file_location('candidate_association_plan_bridge',plan_bridge)
        module=importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        preflight=module.preflight()
        if not preflight['ok']:raise RuntimeError('ASSOCIATION_PLAN_PREFLIGHT_FAILED')
        lock['association_plan_provider_version']=preflight['provider_version']
    survival_bridge=ROOT/'python/clinical_methods/survival_bridge.py'
    if survival_bridge.exists():
        module_spec=importlib.util.spec_from_file_location('candidate_survival_bridge',survival_bridge)
        module=importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        preflight=module.preflight()
        if not preflight['ok']:raise RuntimeError('SURVIVAL_PREFLIGHT_FAILED')
        lock['survival_provider_version']=preflight['provider_version']
    cox_prediction_bridge=ROOT/'python/clinical_methods/cox_prediction_bridge.py'
    if cox_prediction_bridge.exists():
        module_spec=importlib.util.spec_from_file_location('candidate_cox_prediction_bridge',cox_prediction_bridge)
        module=importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        preflight=module.preflight()
        if not preflight['ok']:raise RuntimeError('COX_PREDICTION_PREFLIGHT_FAILED')
        lock['cox_prediction_provider_version']=preflight['provider_version']
    evaluation_bridge=ROOT/'python/clinical_methods/survival_evaluation_bridge.py'
    if evaluation_bridge.exists():
        module_spec=importlib.util.spec_from_file_location('candidate_survival_evaluation_bridge',evaluation_bridge)
        module=importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        preflight=module.preflight()
        if not preflight['ok']:raise RuntimeError('SURVIVAL_EVALUATION_PREFLIGHT_FAILED')
        lock['survival_evaluation_provider_version']=preflight['provider_version']
        if preflight['frozen_model_provider_version']!=lock['cox_prediction_provider_version']:
            raise RuntimeError('FROZEN_COX_PROVIDER_MISMATCH')
    psm_source=ROOT/'src/clinanalysis/R/psm_v07.R'
    if psm_source.exists():
        lock['psm_provider_version']=sha(psm_source)
        lock['psm_runtime']={'R':'4.6.1','stats':'4.6.1'}
    penalized_source=ROOT/'src/clinanalysis/R/penalized_v08.R'
    if penalized_source.exists():
        lock['penalized_provider_version']=sha(penalized_source)
        probe_path=ROOT/'evidence/runtime-probe-v09.json'
        if not probe_path.is_file():raise RuntimeError('PENALIZED_RUNTIME_PROBE_REQUIRED')
        probed=json.loads(probe_path.read_text(encoding='utf-8-sig'))
        if probed['versions']!={'R':'4.6.1','glmnet':'5.1','Matrix':'1.7.5'}:raise RuntimeError('PENALIZED_RUNTIME_VERSION_UNSUPPORTED')
        for path,digest in probed['dependency_hashes'].items():
            if sha(Path(path))!=digest:raise RuntimeError('PENALIZED_DEPENDENCY_DRIFT')
        lock['penalized_runtime']=probed['versions']
        lock['penalized_package_paths']=probed['paths']
        lock['penalized_dependency_hashes']=probed['dependency_hashes']
    interpretation_source=ROOT/'src/clinanalysis/R/interpretation_v09.R'
    if interpretation_source.exists():lock['interpretation_provider_version']=sha(interpretation_source)
    cox_penalized_source=ROOT/'src/clinanalysis/R/cox_penalized_v10.R'
    if cox_penalized_source.exists():
        probed=json.loads((ROOT/'evidence/runtime-probe-v10.json').read_text(encoding='utf-8-sig'))
        if probed['versions']!={'R':'4.6.1','glmnet':'5.1','Matrix':'1.7.5','survival':'3.8.6'}:
            raise RuntimeError('COX_PENALIZED_RUNTIME_VERSION_UNSUPPORTED')
        if len(probed['dependency_hashes'])!=15:raise RuntimeError('COX_PENALIZED_DEPENDENCY_BINDING_REQUIRED')
        for path,digest in probed['dependency_hashes'].items():
            if sha(Path(path))!=digest:raise RuntimeError('COX_PENALIZED_DEPENDENCY_DRIFT')
        lock['cox_penalized_provider_version']=sha(cox_penalized_source)
        lock['cox_penalized_preprocessing_version']=sha(penalized_source)
        lock['cox_penalized_runtime']=probed['versions']
        lock['cox_penalized_package_paths']=probed['paths']
        lock['cox_penalized_dependency_hashes']=probed['dependency_hashes']
    # Capture actual package paths from a saved harmless R probe instead of guessing.
    probe = ROOT/'evidence/runtime-probe.json'
    if probe.exists():
        evidence=json.loads(probe.read_text(encoding='utf-8-sig'))
        lock['r_package_paths']=evidence['paths']
        lock['versions']=evidence['versions']
    (ROOT/'runtime-lock.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    original = []
    for source in sorted(SOURCE_R.rglob('*')):
        if source.is_file():
            dest=ROOT/'src/clinanalysis'/source.relative_to(SOURCE_R)
            original.append({'original':source.as_posix(),'relative':dest.relative_to(ROOT).as_posix(),
                             'original_hash':sha(source),'candidate_hash':sha(dest),
                             'byte_preserved':sha(source)==sha(dest)})
    original.append({'original':SOURCE_A.as_posix(),'relative':'python/clinical_methods/association.py',
                     'original_hash':sha(SOURCE_A),'candidate_hash':sha(ROOT/'python/clinical_methods/association.py'),
                     'byte_preserved':sha(SOURCE_A)==sha(ROOT/'python/clinical_methods/association.py')})
    survival_source=SOURCE_A.with_name('survival.py')
    original.append({'original':survival_source.as_posix(),'relative':'python/clinical_methods/survival.py',
                     'original_hash':sha(survival_source),'candidate_hash':sha(ROOT/'python/clinical_methods/survival.py'),
                     'byte_preserved':sha(survival_source)==sha(ROOT/'python/clinical_methods/survival.py')})
    predsource=SOURCE_A.with_name('prediction.py')
    original.append({'original':predsource.as_posix(),'relative':'python/clinical_methods/prediction.py',
                     'original_hash':sha(predsource),'candidate_hash':sha(ROOT/'python/clinical_methods/prediction.py'),
                     'byte_preserved':sha(predsource)==sha(ROOT/'python/clinical_methods/prediction.py')})
    for filename in ('prediction_engine.py','prediction_metrics.py'):
        source=ROOT.parent/'periop-phenotyping-v0_11-dev-20261023/software/app'/filename
        dest=ROOT/'python/clinical_methods/continuous_ridge'/filename
        if dest.exists():original.append({'original':source.as_posix(),'relative':dest.relative_to(ROOT).as_posix(),
                     'original_hash':sha(source),'candidate_hash':sha(dest),'byte_preserved':sha(source)==sha(dest)})
    (ROOT/'evidence/source-provenance.json').write_text(json.dumps({
        'only_read_originals':True,'source_tree_files':original,
        'design_documents':{p.name:sha(p) for p in ROOT.parent.joinpath('clinical-analysis-core-design-20261023').glob('*.md')},
        'candidate_only':True},indent=2)+'\n',encoding='utf-8')
    print('CANDIDATE_LOCK_WRITTEN',len(hashes))

if __name__=='__main__':main()
