# v0_6 prespecified synthetic acceptance

This is the acceptance design, written before the complete candidate run. It is not a release, clinical validation, or scientific acceptance. The root-owned final receipt records the executed result; this design remains unchanged during a run.

## Scope and independent reference

The method is `evaluation.survival.cox.ipcw`. The risk model is the actual saved v0_5 synthetic acceptance model, copied byte-for-byte from the completed v0_5 run into the new v0_6 fixture directory. The model's v0_5 schema, internal hash, coefficients, feature transforms, center, baseline and training identities remain frozen. Its source file SHA-256 is `b42b5bce34d978ec1937edea47c5c81d82da8e87e2a0466612b410cc76de9734`. The old production `survival.py`, `cox_prediction_bridge.py` and `survival_v05_contracts.py` must remain identical to v0_5.

The nominal fixture contains 100 new synthetic evaluation subjects. Its paired adapters represent the same cohort using days and canonical category codes versus hours and mapped source codes. Different adapter names do not establish external validity or independence. Declared horizons are 0, 1, 5, 10 and 20 days. All IDs, frozen model details, individual risks, full censoring grid, and individual IPCW contributions stay local in fixture/private evidence; they are excluded from public result artifacts.

`tests/survival_v06_reference.R` uses installed R 4.6.1 and survival 3.8.6 with `timefix=FALSE`. At each exact observed time, original events become reverse-KM censor removals at the first integer-ranked phase, and original censors become reverse-KM events at the second phase. `survival::survfit` therefore implements the prespecified original-event-before-original-censor ordering without an epsilon or near-tie merger. A separate original-event KM fit checks the weighted event-probability identity. Metrics are independent R implementations of the fixed source formulas in `IMPLEMENTATION-V06.md`; the reference does not import production numerical functions.

This is formula-reference validation. It is not specialist-package validation against timeROC, pec, riskRegression, dcurves, rmda, survAUC, rms, scikit-survival or lifelines. No packages are installed or downloaded. The independent R oracle receives supplied risks when checking evaluation; risk-model fitting was covered by the frozen v0_5 acceptance, and v0_6 must not refit it.

## Tolerances fixed before complete execution

For every deterministic reference, adapter, reload, public CSV and aggregate comparison, the rule is `abs(actual - reference) <= 1e-10 + 1e-10 * abs(reference)`. Model serialization comparisons use exact bytes. Count partitions, statuses, nullability, reason codes, fixed grids, artifact sets and result references compare exactly. Tolerances will not be relaxed after seeing a failure.

## Fixed formula and hand checks

Cases are events with U <= t, controls have U > t, and censoring at or before t contributes zero weight while remaining in population n. Case weights use G(U-); control weights use G(t). There is no clipping, normalization to conceal identity failure, horizon selection, outcome-adaptive threshold/bin choice or calibration refit.

Twelve hand scenarios provide independent fixed expectations and the following checks:

- No-censor binary limit: U=(1,2,4,5), all events, risks=(.9,.8,.2,.1), t=3 has AUC=1, Brier=.025, ESS=4, model net benefit=.5 and treat-all=0 at threshold .5.
- No cases at t=0 and no controls after all known events at t=6 retain valid Brier=.375 while AUC/ROC remain null with exact reasons. The latter has G=1 and is not refused merely for exceeding the observed evaluation maximum.
- Exact event/censor tie: U=(1,1,2,3), status=(1,0,1,0), risks=(.8,.9,.6,.2). At t=1, G=2/3, case weight sum=1, control weight sum=3, Brier=.16, ESS=32/11, model net benefit=-.125 at .5. At t=2, case/control sums are 2.5/1.5, Brier=.085 and net benefit=.625.
- Equal scores .5 receive half AUC credit, giving AUC=.5, Brier=.25 and inclusive-threshold treatment of every subject.
- Fractional-weight perfect ranking: U=(1,2,3,4,5,6), status=(0,1,1,0,0,0), risks=(.5,.8,.8,.2,.2,.2), t=3 has positive weights 6/5, case/control sums 12/5 and 18/5, AUC numerator and denominator both 216/25, and AUC exactly 1. Production AUC and Brier must also remain strictly within [0,1]. This case was added after independent review found an endpoint rounding defect; earlier receipts are preserved and superseded. The reference tolerance is unchanged, and the real entry repeats the endpoint using deterministic monotone synthetic features with the same unchanged model.
- Fractional-weight Brier and diagnostic endpoint: n=13, U=1..13, status=(0,0,1,0,1,0,0,0,1,1,1,1,1), t=13. The case weights are 13/11, 130/99 and five copies of 208/99, summing exactly to 13, with G=99/208. With supplied risks all zero, Brier is exactly 1; weighted case probability is exactly 1 for any risk vector. Direct formula checks and real frozen-model entry cover both endpoints without probability clipping or tolerance changes.
- Marginal-weight Hajek calibration is distinguished from within-bin KM: the two-subject upper bin with risks .8/.7 has mean=.75, observed ratio=.4 and ESS=25/13, whereas the within-bin KM event probability would be .5.
- Terminal censoring makes G=0 and all horizon estimates unavailable. Other horizons remain available.
- A cohort of 21 with one event and 19 censors at time 1 plus a future event has G=.05 and maximum weight=20 at t=1; equality is accepted, ESS=441/401 and Brier=.04. Adding one tied censor gives G=1/21 and maximum weight=21; both guard reasons are retained and estimates are null.
- Times 1 and 1+1e-12 remain distinct. G changes from 1 to 2/3 between these horizons; the first Brier is .3125.
- Fixed bins are left closed/right open with the last edge inclusive. Probabilities 0, .5, .5, 1 partition as 1/3 subjects and do not merge the small bin. The populated upper bin has predicted mean 2/3 and observed ratio 1/3.
- A bin containing only early-censored subjects retains its raw n but has zero weight, null ESS and null observed calibration with `CALIBRATION_BIN_ZERO_WEIGHT`.

The full harness repeats all twelve scenarios against the numerical API and the independent R oracle. Eight scenarios also pass through the real R entry with unchanged model risks, testing public boundary projection and private evidence. Supplied out-of-range risks are rejected explicitly.

## Entry, isolation and refusal checks

The full suite verifies both adapters through `run_core.R`, independent R aggregates and individual IPCW, exact old-model serialization, saved-model reload, aggregate/individual row-order equivalence, and unchanged risks/model bytes after evaluation follow-up and event labels change. The censoring grid and evaluation metrics must change in that perturbation.

Refusals cover missing time, status or features; unknown category or status encoding; negative follow-up; training-subject overlap; namespace drift; future features; event/censor-definition and reversed-code semantics; negative or unsupported horizons; unsorted or incomplete ROC grids; invalid/duplicate DCA thresholds; duplicate calibration edges; model file hash, internal hash and version tampering. UTF-8 BOM models are explicitly rejected because their bytes cannot meet the retained-text transport contract. Valid CRLF serialization must remain byte-identical through inference and produce the same risks. Existing output directories may not be overwritten.

The full run requires the root GO signal and an explicit SHA-256 of `runtime-lock.json`. The five owned acceptance files are hashed before execution, with an end-of-run unchanged check. Every run has a unique output directory and a durable progress/final receipt. Interrupted or failed attempts remain intact; they cannot count as a complete pass. Production fixes belong to the root/provider, and any harness repair requires a new unique run with its actual source hashes.

## Export audit

`tools/audit_survival_v06_exports.py` reads the successful acceptance receipt, original synthetic CSVs, private artifacts, public JSON and all five public table groups. It reconstructs canonical source values, event/censor populations, horizon case/control/early-censor partitions, exact-time counts, prediction membership, overall/case/control/bin/treated ESS, fixed thresholds and bins, and each subject-versus-weight denominator. It compares every exported scalar/status/reason with the public and native provider record under the fixed tolerance.

The audit verifies exact bound model bytes and native JSON text, internal model hash, inference-only operation, absence of model refitting claims, explicit unverified censoring assumption, no clipping or interval claims, unique result IDs, precise table/figure source-result sets, artifact SHA-256, writing references and the public/private privacy boundary. Figure rendering is inspected separately by the root after successful numerical and export checks.

Untested/unimplemented areas remain clinical validity, real source cohorts, transportability, informative or conditional censoring, uncertainty intervals, specialist-package finite-sample equivalence, formal or smooth calibration, competing risks, delayed entry, recurrent events and time-varying features. Passing this suite supports the stated engineering behavior only.
