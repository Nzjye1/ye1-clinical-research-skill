"""Write local candidate navigation and boundaries; no acceptance claims."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DOCS={
'README.md':'''# Shared clinical analysis core v0_6 local candidate

This isolated Windows candidate adds prespecified censoring-aware evaluation of the unchanged v0_5 frozen Cox risk model. It is a local engineering candidate, not a released Skill or a clinically validated complete analysis suite.

Use the existing single task entry, `tools/run_core.R` -> `clinanalysis::run_analysis_task`. The registered new method is `evaluation.survival.cox.ipcw`. Input and result contracts are versioned `0.6.0-candidate1`; five historical input/result branches remain available. The frozen model format and its numerical producer remain `clinical-frozen-survival-cox@0.5.0-candidate1`.

The new evaluator provides cumulative/dynamic IPCW AUC and fixed-grid ROC, IPCW Brier, descriptive fixed-bin Hajek calibration, and IPCW net benefit with treat-all/none. Evaluation-cohort reverse KM estimates the censoring nuisance distribution; the risk model, preprocessing and baseline are never refitted. All grids, horizons and thresholds are declared before evaluation. No-case/control, sparse bins and positivity failures are explicit partial/unavailable results.

- [Actual acceptance receipt](ACCEPTANCE.md) and [machine evidence](evidence/final-manifest.json)
- [Independent review entry](REVIEW-HANDOFF.md)
- [Fixed implementation and methods](docs/IMPLEMENTATION-V06.md)
- [Exact provider interface](docs/V06-PROVIDER-CONTRACT.json)
- [Ownership](OWNERSHIP.md), [gaps](GAPS.md), [capability registration](method-capabilities.json)
- [Input schema](schemas/input.schema.json), [result schema](schemas/result.schema.json)

Small artificial cohorts and two same-semantics database mappings are included. Their labels do not certify real database adapters, independent real external cohorts, transportability or clinical utility. Patient-level models, predictions and weights stay in local private run artifacts. No upload, install, system change, old candidate change, GitHub operation or publication is performed.

Use the fixed read-only Python and R paths in runtime-lock.json. Do not run freeze_core.py during verification: it is an explicit development operation. The read-only integrity entry is `python -B tools/verify_candidate.py`. Further independent runs should use a separate development/review copy or fresh output paths and must retain the candidate checksum manifest.
''',
'OWNERSHIP.md':'''# v0_6 source and verification ownership

The only execution mechanism remains the existing clinanalysis task registry. `clinical_common.R` routes versioned input and common output. `clinical_survival_v06.R` transports requests, checks output semantics and projects aggregate tables/figures; it does not fit a risk or censoring model.

`python/clinical_methods/survival.py`, `cox_prediction_bridge.py`, and `survival_v05_contracts.py` are byte-identical to the frozen v0_5 candidate. They alone own the existing Cox fit, formal PH extension, transformation chain, coefficients and Breslow baseline. Frozen model producer version 0.5 is deliberately separate from calling core version 0.6. Ridge, baseline and association numerical owners are also unchanged.

The sole new evaluation numerical owner is `survival_evaluation.py`. Its bridge calls unchanged `cox_prediction_bridge.invoke` with infer; there is no alternative fitter, rebuilt baseline, ordinary binary-metric fallback or adaptive algorithm. Evaluation-cohort marginal reverse KM is an explicitly documented nuisance estimate. The provider hash binds both evaluation files and both frozen Cox owner/bridge files.

`survival_v06_contracts.py` adds a closed input branch, explicit evaluation options and complete-label/support checks while reusing v0_5 model/identity/semantic validation. BOM model text is rejected with a named reason because stripping it would violate exact file-byte preservation; ordinary UTF-8 text, CRLF and terminal newlines remain preserved. Schema generation owns structural result validation; R checks denominator/count/projection identities.

The R reference in tests is independently written for acceptance, uses survival::survfit for the ordered censoring construction and source formulas for metrics, and is never a production fallback. Specialist timeROC/dcurves/pec packages were unavailable. This is not specialist-package metric validation.

Task ownership was split between input contract, numerical evaluator, output schema, independent reference/acceptance and root integration. Production files stop changing while their locked acceptance runs execute. This is run scheduling, not a permanent restriction on the user. A needed change requires a new explicit lock and relevant regression, with earlier outcomes preserved. Old frozen directories are not edited.
''',
'GAPS.md':'''# v0_6 capability boundaries and outstanding work

This batch is one bounded survival evaluation loop, not completion of the shared clinical platform. See final-manifest.json for actual passed/failed/not-tested evidence and method-capabilities.json for registration.

Supported statistical scope: one right-censored event, unique independent subjects, fixed v0_5 Cox predictions and complete evaluation features/follow-up labels. Marginal evaluation-cohort reverse KM assumes censoring independent of event time and model features. This assumption is declared, not verified. Positivity/weight guards and ESS do not establish clinical adequacy.

Still unimplemented or unvalidated:

- Conditional/informative censoring models, externally supplied censoring models, stabilized/clipped weights, survey/case weights and clustered evaluation.
- Metric confidence intervals, calibration slope/intercept or tests, smoothing, within-bin KM calibration, integrated Brier and incident/dynamic AUC. Calibration here is descriptive fixed-bin Hajek. DCA here uses IPCW population moments, not dcurves positive-group KM.
- Competing risks, delayed entry, recurrent events, interval censoring and time-varying covariates; these are not silently ordinary right censoring.
- Real database adapters, real patient evaluation, source independence, transportability, clinical benefit and causal interpretation.
- Disclosure control for small aggregate cells. A singleton bin's descriptive predicted mean can equal one synthetic subject's risk; min_bin_n controls observed calibration estimability, not anonymization. Outputs remain local/synthetic and carry no de-identification guarantee.
- General signed continuous prediction, LASSO/SHAP, outstanding subgroup/RCS combinations, longitudinal/survey/causal/trajectory methods and post-index outcome descriptive baseline roles. Such baseline stratification is not inherently leakage; the role-aware use remains outside this candidate.
- Full clinical Skill integration, Mac deployment, installer/distribution packages, licenses, push/tag/release and publication.

Formal PH and basic frozen Cox absolute risk from v0_5 remain included and regression-tested. No PH P value establishes proportional hazards. Survival evaluation charts are not evidence that all survival methods or their uncertainty are implemented.

Existing R survival is used as a censoring-estimator reference; source-formula metric comparisons and hand calculations are explicit evidence, not validation by unavailable specialist packages. All clinical scientific review remains pending.
''',
'REVIEW-HANDOFF.md':'''# Independent v0_6 review entry

Candidate: historical-reference:clinical-analysis-core-v0_6-dev-20261024. Start with evidence/final-manifest.json and ACCEPTANCE.md; confirm freeze_status and actual suite counts. Read docs/IMPLEMENTATION-V06.md before interpreting estimates. Keep v0_1..v0_5 and original Skills read-only.

1. Read-only integrity: use the fixed Python path in runtime-lock.json with `-B tools/verify_candidate.py`. Confirm every delivery checksum and 139 production code bindings. Do not run freeze_core.py or rewrite manifests during independent verification.
2. Inspect schemas/input.schema.json and schemas/result.schema.json. Earlier five branches must equal their frozen versions. New method is evaluation.survival.cox.ipcw, model producer stays v0_5. Check the version-only inherited-test diff receipt.
3. Review tests/survival_v06_reference.R and tests/test_survival_v06_acceptance.py. R reverse KM uses two ordered phases for exact event/censor ties; source formulas use event U<=t, control U>t and early censor weight zero. Formula references are independent of production imports; specialist metric packages were not used.
4. Review the frozen v0_5 model file provenance in fixtures/survival-v06/fixture-manifest.json. Evaluations must preserve its bytes, coefficient/baseline/transform contents and individual risks after outcome perturbation. Training overlap, unknown category, future feature, invalid times/status, missing labels, support extrapolation and unsupported semantics are refused.
5. Run the new suite in a fresh isolated review copy if execution is desired: the existing test program creates unique run folders. The candidate's evidence already contains its completed run and public export audit. Keep its fixed tolerances atol+rtol=1e-10; do not relax tolerances to match production.
6. Audit public CSV denominators, raw counts, weighted sums, ESS, scales, source/version fields and artifact IDs/hashes. Public figures only show fixed grids, bins and aggregate counts; full censoring grid, individual predictions and contributions stay private. Check t=0/no-case, no-control, early-censor and exact G=.05/weight20 equality versus violation. Empty/small bins and unavailable horizons must retain reasons.
7. Confirm old baseline, association plan, Ridge, survival and v0_5 PH/Cox suites, prediction-output corrections, unit log, source protection, visual review and execution history all refer to the same current production lock.

The final manifest deliberately records independent personnel review as pending. Engineering checks, including independent R formula comparison, do not constitute clinical scientific acceptance. Two nonessential method-review sidecar writes were denied under that research subtask's original read-only scope; they were not retried or created, and the history preserves the exact targets and outcome.
'''
}
def main():
    for name,text in DOCS.items():(ROOT/name).write_text(text,encoding='utf-8')
    print('V06_DELIVERY_DOCS_WRITTEN',len(DOCS))
if __name__=='__main__':main()
