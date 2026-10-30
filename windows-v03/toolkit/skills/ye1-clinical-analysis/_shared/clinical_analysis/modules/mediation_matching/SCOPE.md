# Mediation and matched outcomes: acceptance boundary

Status: module development, synthetic engineering only, not a released clinical capability.
Owner: delegated mediation_matching task. The newer delegation combines two older DISPATCH entries and explicitly resumes development. Only this directory is writable; frozen v0.10 and other modules remain read-only.

## Public interfaces and numerical ownership

- `R/provider.R`: `mm_analyze(data, spec, baseline_root)` returns `list(record, private)`; no filesystem writes. One module numerical owner; R stats supplies OLS, exact binomial inference and survival supplies Cox optimization/cluster sandwich.
- `R/adapter.R`: input mapping, transport, aggregate CSV/PNG/report, local private files and shared-envelope projection. No second estimator.
- `python/adapter.py`: local manifest checks, literal column mappings and unit conversions; calls the R runner. No fitting or outcome-driven matching.
- Frozen `src/clinanalysis/R/psm_v07.R` owns all propensity fitting, support restriction, greedy 1:1 matching and balance/overlap. Its exact source hash is required. It is sourced read-only, never copied or patched.
- `integration-request.md` describes shared registry/schema integration. Shared registration and final integrated acceptance belong to the designated integrator.

## Supported methods

| Method ID | Scope | Inference and interpretation |
|---|---|---|
| `mediation.linear.binary_exposure` | Independent subjects; 0/1 exposure; one continuous mediator and continuous outcome; numeric pretreatment confounders; fixed OLS models; optional prespecified A*M interaction | Empirical standardization of four nested conditional mean predictions; ACME(0/1), ADE(0/1), total contrast. Subject bootstrap jointly refits both models, with failed replicates counted. Natural-effect labels require unverified sequential ignorability, consistency, positivity and model assumptions. |
| `causal.psm.att.binary` | Baseline 0/1 treatment, fully observed 0/1 endpoint at one common declared horizon; frozen 1:1 matching without replacement | Matched risk difference with pair-difference variance and approximate t interval; exact binomial McNemar test and exact conditional matched odds ratio interval. RD targets retained matched treated under assumptions; conditional OR is a distinct estimand, not an ATT risk ratio. |
| `causal.psm.matched.survival` | Baseline treatment, first event, positive follow-up, common time origin, single-event right censoring; no delayed entry | Treatment-only pooled Cox model, Efron ties, pair-cluster robust sandwich, normal log-HR interval. Pooled risk sets include subjects with follow-up >= event time; events precede censoring at tied times. Working marginal HR in matched population; not a risk difference, probability, or universal causal ATT. |

All matching inference conditions on formed pairs. It excludes uncertainty from propensity estimation, support restriction and match selection. Independent pairs and sufficient clusters are assumptions; fewer than 30 pairs triggers a small-cluster warning, not a claim of validity. No naive rematching bootstrap is used.

Mediation uses complete cases across both models, requires A before M before Y and pretreatment confounders, and resamples iid complete subjects. No significance-based path selection, total-effect prerequisite, or proportion-mediated output. The conditional mean formulas integrate the linear outcome exactly; normal mediator simulation is unnecessary. Bootstrap does not remove confounding or prove causality. Percentile intervals are engineering-validated, not guaranteed coverage in small samples.

## Explicitly unsupported

Mediation: nonbinary/continuous exposure, binary/count/survival mediator or outcome, multiple mediators, survey/cluster/repeated observations, treatment-induced mediator-outcome confounding, post-treatment adjustment, outcome/mediator missing-data identification beyond complete-case targeting, nonlinear models, mediator-confounder interactions, measurement error correction, sensitivity analysis and causal identification certification.

Matching: replacement, variable ratios, weights, external preformed pairs, extra clustering, missing endpoints, censoring before a binary endpoint horizon, left/interval censoring, delayed entry, recurrent/competing events, time-varying exposure/covariates, causal survival probabilities and PH verification.

## Acceptance plan

Two literal source mappings and declared unit conversions; iid OLS/g-computation independent Python reference, shared bootstrap indices compared with independent refits, direct exact binomial reference, manual Cox partial likelihood/risk-set/sandwich reference including ties; degeneracy and misuse rejections; fixed row-order/seed reproducibility; privacy aggregate checks; CSV/JSON precision, actual PNG visual inspection; frozen PSM targeted regression only. No full old suite or package duplication.

## Dependencies verified on this host

Windows R 4.6.1, stats 4.6.1, survival 3.8.6, jsonlite 2.0.0, digest 0.6.39. Python 3.12.15, numpy 2.5.4, scipy 1.18.1, statsmodels 0.14.6. R mediation/lavaan and Python jsonschema unavailable and not required. No installation.

The local `ye1-association` and `ye1-survival` skills were inspected for their time/estimand/privacy boundaries. No legacy Skill is edited or repackaged. Only small generated synthetic inputs are used.
