# Method and interface definitions

## Prediction and IPCW

The genuine v10 wrapper is retained. `cox_penalized_v10_analyze(..., operation="infer")` validates frozen preprocessing, coefficients, CV metadata, baseline, training support and disjoint identities. Its private `risk`/`survival` values are renamed to the evaluator's `event_risk`/`survival_probability`; no prediction arithmetic is implemented in Python.

The unchanged evaluator requires complete numeric covariates in its validation view. That view contains the actual retained standardized columns produced by frozen `penalized_v08_prepare`, not dummy features. It is not another fitted-model schema. ID, time and event values come from validated normalized endpoint rows. The older Cox prediction bridge is never invoked.

Evaluation uses the existing marginal reverse-Kaplan-Meier IPCW owner. Censoring is estimated in the evaluation cohort as a nuisance distribution; the risk model stays frozen. Independent censoring of event time and model features is declared and remains unverified. Exact ties put events before censors. Cases are events at or before t and use G(U-); controls remain observed strictly after t and use G(t). Early-censored subjects have zero contribution and remain in the population denominator. G >= 0.05 and weight <= 20 are fixed guards, with no clipping. Existing estimability reasons, cumulative/dynamic AUC, Brier, fixed-bin Hajek calibration and population net benefit are preserved. No uncertainty intervals or clinical utility claim are added.

## Centered log-relative-hazard SHAP

Frozen training preprocessing imputes numeric values with the training median and categories with the training mode; it then treatment-encodes categories and centers/scales every retained column, including one-hot columns, using training population moments.

Let z_j=(raw_j-center_j)/scale_j and c be the stored baseline center. The score is q=sum(beta_j*z_j)-c. Its grouped interventional attribution is base=-c and phi_g=sum(beta_j*z_j) over columns belonging to original feature g. All original features are present, including zero contributions for dropped constant features. The analytically centered encoded first moment is zero. Only first moments are needed for this affine interventional game; no training or application background rows are used or claimed to have been recovered. Small finite-precision empirical centering residuals are covered by explicit numerical tolerance.

This explains q, not event probability, relative hazard itself, conditional SHAP, causal effects or post-selection coefficient inference. Categorical modes are not substituted for mean encoded backgrounds. Imputation is part of the frozen prediction function; a missing feature may have a nonzero attribution.

## Numerical nomogram

The v10 preprocessor does not save observed numeric training minima or maxima. The sidecar therefore uses `prespecified_display_domains`; training feature-range support is `unknown`. Domains include original units, externally declared numeric bounds or the complete frozen categorical levels, the missing-value route, and a provenance note. The application never expands the domain. Out-of-domain explanation requests fail explicitly.

Let g_j be each original feature's contribution, m_j its minimum on its display domain, d_j its range and D=max(d_j). Points are 100*(g_j-m_j)/D, zero-point score is -c+sum(m_j), and reconstructed score is zero-point score+(D/100)*total_points. D=0 is handled as constant on the display domain. It does not establish that arbitrary future values would yield a constant model. Domain combinations need not represent observed joint population support.

Separate horizon risk ticks use the frozen right-continuous Breslow H_ref(t): survival=exp(-H_ref(t)*exp(q)), risk=-expm1(-H_ref(t)*exp(q)). The display-only inverse link is numerically stabilized and checked on every application against the sole v10 predictor. Before the first event, including t=0, risk is zero although additive score contributions need not be zero. Requested horizons cannot exceed maximum observed training follow-up.

The explainer binds model bytes, its numerical implementation/dependencies, model runtime binding, ordered zero encoded means, fixed domains, horizons and derived axes. Reload recomputes and compares derived contents. Public output contains aggregate importance, axes and maximum check errors; individual rows stay in local private artifacts.
