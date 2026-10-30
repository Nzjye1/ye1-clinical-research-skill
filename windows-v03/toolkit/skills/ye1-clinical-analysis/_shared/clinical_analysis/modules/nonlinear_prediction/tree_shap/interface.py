"""Independent explain-only shared-contract adapter; no model training owner."""
from .runtime import ROOT, METHODS, prediction as p, bridge, facade, runtime, version, validate
from .background import check_background
from .explain import explain


def analyze(request):
    diagnostics = {'stage': 'contract', 'prediction_provider_version': p.provider_version(), 'explanation_provider_version': version(),
                   'runtime': None, 'model_refitted': False, 'preprocessing_refitted': False, 'calibration_refitted': False,
                   'counts': {'source_rows': None, 'explained_n': None, 'background_n': None}, 'numerical_checks': None,
                   'bindings_checked': 'model_and_background_integrity_here; trusted_input_plan_code_runtime_and_background_origin_owned_by_common_entrypoint'}
    try:
        facade.validate_json(request, facade.CONTRACTS_ROOT/'module-request.schema.json')
        p.need(request['method_id'] in METHODS, 'MODULE_METHOD_NOT_REGISTERED')
        p.need(request['operation'] == 'explain', 'MODULE_OPERATION_UNSUPPORTED')
        payload = request['payload']; validate(payload, 'payload')
        diagnostics['counts']['source_rows'] = len(payload['rows'])
        for name in ('diagnostics', 'public-record', 'private-record', 'background'):
            p.need((ROOT/'schemas'/(name+'.schema.json')).is_file(), 'MODULE_SCHEMA_MISSING')
        semantics = facade.semantics_and_guard({**payload, 'explain_with_outcomes': False}, 'explain')
        bundle = bridge.strict_load(payload['frozen_model_json'].encode('utf-8'))
        p.need(request['bindings']['model_sha256'] == bundle.get('sha256'), 'MODULE_MODEL_BINDING_MISMATCH')
        base_method = METHODS[request['method_id']]
        diagnostics['runtime'] = runtime()
        diagnostics['stage'] = 'frozen_validation'
        # All original external identity/group, frozen runtime/model and feature
        # guards remain owned by the prediction adapter. Inference never refits.
        inferred = bridge.execute({'operation': 'infer', 'method_id': base_method, 'rows': payload['rows'],
                                   'spec': payload['spec'], 'model_bundle': bundle, 'canonical_semantics': semantics},
                                  include_explanation=False, application_scope=payload['application_scope'])
        background = bridge.strict_load(payload['background_artifact_json'].encode('utf-8'))
        p.need(background.get('sha256') == payload['background_sha256'], 'BACKGROUND_BINDING_MISMATCH')
        matrix = check_background(background, bundle, payload['spec'])
        data, positions = p.common_bridge.binary_inference_rows(payload['rows'], payload['spec'])
        diagnostics['counts'].update(explained_n=len(data), background_n=len(matrix))
        diagnostics['stage'] = 'explanation'
        public, private, numerics = explain(data, positions, bundle['bundle']['model'], matrix)
        p.need([v['row_index'] for v in private['individual']] == [v['row_index'] for v in inferred['individual']], 'SHAP_INFERENCE_POSITION_MISMATCH')
        diagnostics.update(stage='complete', numerical_checks=numerics)
        private.update(model_sha256=bundle['sha256'], background_sha256=background['sha256'])
        response = {'api_version': 'clinical-module-response@1.0', 'ok': True, 'reason_code': None,
                    'diagnostics': diagnostics, 'public_record': public, 'private_record': private}
        for key, name in [('diagnostics','diagnostics'), ('public_record','public-record'), ('private_record','private-record')]:
            validate(response[key], name)
        facade.validate_json(response, facade.CONTRACTS_ROOT/'module-response.schema.json')
        return response
    except (p.Blocked, facade.core_contracts.ContractBlocked) as exc:
        code = str(exc)
        if not code or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789' for c in code):
            code = 'TREE_SHAP_CONTRACT_BLOCKED'
    except ImportError:
        code = 'TREE_SHAP_DEPENDENCIES_UNAVAILABLE'
    except Exception:
        code = 'TREE_SHAP_INPUT_OR_RUNTIME_ERROR'
    return {'api_version': 'clinical-module-response@1.0', 'ok': False, 'reason_code': code,
            'diagnostics': diagnostics, 'public_record': None, 'private_record': None}
