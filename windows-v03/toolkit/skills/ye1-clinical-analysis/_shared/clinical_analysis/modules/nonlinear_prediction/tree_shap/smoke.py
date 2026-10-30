"""One bounded native-estimator compatibility probe; no external data."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent / '_vendor'))
import shap
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits

x = np.random.default_rng(47).normal(size=(120, 3))
y = (x[:, 0] * x[:, 1] > 0).astype(int)
print('runtime', shap.__version__, sklearn.__version__, np.__version__)
with threadpool_limits(1):
    for cls in [RandomForestClassifier, HistGradientBoostingClassifier]:
        model = cls(random_state=47).fit(x, y)
        explainer = shap.TreeExplainer(model, x[:20], feature_perturbation='interventional')
        values = explainer(x[30:35])
        print(cls.__name__, values.values.shape, bool(np.isfinite(values.values).all()))
