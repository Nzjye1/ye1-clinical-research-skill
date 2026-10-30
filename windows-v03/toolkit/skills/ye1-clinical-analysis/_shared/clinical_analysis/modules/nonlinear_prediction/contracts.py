"""Contract fragment for the integration owner; does not mutate shared schemas."""
from __future__ import annotations
import copy

from provider import common, validate_spec, METHODS
from clinical_methods import prediction_contracts as existing
from clinical_methods import contracts as core_contracts

SPEC = copy.deepcopy(existing.BINARY_SPEC)
for key in ('C', 'min_epv'):
    SPEC['properties'].pop(key)
    SPEC['required'].remove(key)
SPEC['properties']['bootstrap'] = {'anyOf': [{'const': 0}, {'type': 'integer', 'minimum': 50, 'maximum': 100}]}
SPEC['properties']['calibration'] = existing.obj({'method': {'enum': ['none', 'sigmoid']},
    'fraction': {'type': ['number', 'null']}})
SPEC['properties']['tuning'] = existing.obj({'metric': {'const': 'log_loss'},
    'candidates': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': {'type': 'object'}}})
SPEC['properties']['explanation'] = existing.obj({'permutation_repeats': {'type': 'integer', 'minimum': 0, 'maximum': 20},
    'pdp_features': {'type': 'array', 'minItems': 0, 'maxItems': 5, 'items': existing.NAME}})
SPEC['required'] += ['selection', 'calibration', 'tuning', 'explanation']


def validate(spec, method):
    try:
        core_contracts.validate_schema(spec, SPEC)
    except core_contracts.ContractBlocked:
        raise common.PredictionBlocked('NONLINEAR_SPEC_SCHEMA_INVALID') from None
    validate_spec(spec, method)


def contract_fragment():
    return {'module_version': 'nonlinear-prediction-contract/1.0.0', 'method_ids': sorted(METHODS),
            'prediction_spec': copy.deepcopy(SPEC), 'operations': ['train', 'evaluate', 'infer'],
            'provider_envelope': ['ok', 'record', 'model_bundle', 'individual', 'runtime', 'provider_version'],
            'common_evaluation_owner': 'clinical_methods.prediction._metrics',
            'public_output_excludes': ['individual', 'model_bundle', 'development_id_digests', 'development_group_digests']}
