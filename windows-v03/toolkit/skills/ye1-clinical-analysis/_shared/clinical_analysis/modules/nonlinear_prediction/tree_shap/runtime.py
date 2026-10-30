"""Explicit isolated dependency path; never installs or changes shared packages."""
from pathlib import Path
import hashlib
import json
import importlib
import importlib.metadata as metadata
import sys

ROOT = Path(__file__).resolve().parent
PREDICTION_ROOT = ROOT.parent
_LOCAL_RUNTIME=json.loads((ROOT.parents[2]/'integration/module-runtime.json').read_text(encoding='utf-8-sig'))
VENDOR=Path(_LOCAL_RUNTIME['shap_library']).resolve()
sys.path.insert(0, str(PREDICTION_ROOT))
import provider as prediction
import adapter as bridge
import interface as facade

prediction.need(Path(prediction.__file__).resolve().parent == PREDICTION_ROOT, 'PREDICTION_IMPORT_COLLISION')
PINNED = {'shap': '0.54.1', 'slicer': '0.0.8', 'tqdm': '4.70.1'}
METHODS = {'explanation.binary.random_forest.tree_shap': 'prediction.binary.random_forest',
           'explanation.binary.hist_gradient_boosting.tree_shap': 'prediction.binary.hist_gradient_boosting'}


def load_shap():
    prediction.need(VENDOR.is_dir(), 'TREE_SHAP_DEPENDENCIES_UNAVAILABLE')
    installed = {d.metadata['Name'].lower(): d.version for d in metadata.distributions(path=[str(VENDOR)])}
    prediction.need(installed == PINNED, 'TREE_SHAP_DEPENDENCY_VERSION_DRIFT')
    for name in PINNED:
        if name in sys.modules:
            prediction.need(Path(sys.modules[name].__file__).resolve().is_relative_to(VENDOR), 'TREE_SHAP_IMPORT_COLLISION')
    if str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))
    shap = importlib.import_module('shap')
    prediction.need(shap.__version__ == PINNED['shap'], 'TREE_SHAP_DEPENDENCY_VERSION_DRIFT')
    return shap


def runtime():
    load_shap()
    return {**prediction.runtime(), **PINNED, 'colorama': metadata.version('colorama')}


def version():
    files = [ROOT/n for n in ('__init__.py', 'runtime.py', 'background.py', 'explain.py', 'interface.py', 'projection.py')]
    files += sorted((ROOT/'schemas').glob('*.json'))
    return prediction.common._digest({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files})


def validate(value, name):
    facade.validate_json(value, ROOT/'schemas'/f'{name}.schema.json')
