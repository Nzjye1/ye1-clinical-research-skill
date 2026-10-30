"""Prepare reviewable candidate only; no shared registry or active manifest writes."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'integration-request.json').read_text(encoding='utf-8'))
manifest['entrypoint']={'path':'dispatch_api.py','function':'analyze'}
manifest['projection_entrypoint']={'path':'dispatch_api.py','function':'project'}
manifest['provider_files'] += [n for n in ['dispatch_api.py','formal_api.py','formal_provider.py','formal_runtime.py','formal_models.R','formal_engine.R','formal_artifacts.py'] if n not in manifest['provider_files']]
for method in manifest['methods']:
    if method['method_id'] not in ['latent.profile.gaussian','latent.trajectory.gaussian']:continue
    profile=method['method_id']=='latent.profile.gaussian'
    method['method_version']='1.1.0-development'
    method['numerical_owner']='formal_models.R: mclust::me (EEI/VVI Gaussian LPA)' if profile else 'formal_models.R: lcmm::hlme (Gaussian LCGA/shared-covariance growth mixture)'
    method['schemas']={'payload':'formal_schemas/'+('profile' if profile else 'trajectory')+'.payload.schema.json',
      **{k:'formal_schemas/'+k+'.schema.json' for k in ['diagnostics','public_record','private_record']}}
receipt=json.loads((ROOT/'evidence/formal-install/receipt.json').read_text())
for package in receipt['packages']:
    manifest['dependencies'].append({'name':package['package'],'version':package['loaded_version'],
      'role':'numerical_owner' if package['package'] in ['mclust','lcmm'] else 'runtime'})
manifest['shared_change_requests']=[{'target':'integration/module_worker.py:load_python and the development module lock',
  'reason':'Honor manifest.entrypoint.path when importing latent_longitudinal as a package; dispatch_api routes to existing api or new formal_api. Formal payload adds split, controls and explicit time origin/scale. Existing three provider code/schema bytes remain unchanged.',
  'affected_methods':['latent.profile.gaussian','latent.trajectory.gaussian'],
  'required_regression':['five method IDs route to their sole owners','formal training subject/holdout boundary','private frozen artifact persisted verbatim',
    'subject-time branch cannot relax existing subject-only guards','strict own payload/result schemas','zero-fit frozen assignment','common provenance and aggregate-only projection']}]
manifest['evidence'] += ['FORMAL-IMPLEMENTATION.md','formal-integration-change-request.json','evidence/formal-install/receipt.json',
  'tests/formal_acceptance.py','tests/formal_references.py','tests/reference_formal_lme4.R']
(ROOT/'integration-request.formal-candidate.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Prepared candidate manifest; current integration-request.json unchanged.')
