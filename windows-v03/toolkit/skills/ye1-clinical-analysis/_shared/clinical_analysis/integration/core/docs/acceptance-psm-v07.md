# v0_7 prespecified synthetic PSM acceptance

This design is fixed before the first numerical preflight and full candidate run. It concerns the new `causal.psm.att.continuous` route only. All earlier candidates and their evidence remain read-only. A passing engineering suite is not clinical, causal or publication approval.

## Reference and tolerances

The independent reference uses the installed R `stats::glm` binomial-logit MLE, an independently written distance-table implementation of the declared greedy matching rule, `stats::t.test(..., paired=TRUE)` plus explicit paired variance/covariance identities, and source-formula balance calculations. It never sources or imports the production numerical provider. MatchIt is unavailable in the configured libraries; no package installation is authorized. This is independent implementation/formula-reference validation, not validation against a specialist matching package or independent clinical review.

The following tolerances are declared before results and will not be relaxed:

- GLM coefficients and individual logit/propensity scores: absolute 1e-8 plus relative 1e-8.
- Matched means, contrast, paired variance, covariance, SE, t/df, CI, P value, SMD and public export scalars: absolute 1e-10 plus relative 1e-10.
- Same-semantic adapter, row permutation and outcome-perturbation propensity comparisons: absolute 1e-12 plus relative 1e-12.
- Subject and pair identities, counts, statuses, reasons, options, missingness classification, table/result references and preserved old numerical sources: exact.

Numeric SMDs use the sample SD (n-1) from the complete-case treated cohort before support selection. Every declared categorical-level indicator uses the fixed Bernoulli SD sqrt(pT*(1-pT)) in that same cohort. A numeric covariate taking values 0/1 remains numeric and uses sample SD. The before/after denominator is identical; zero reference variance yields a null SMD with a reason.

## Fixtures and hand checks

The nominal cohort has 120 synthetic patient-wide rows with numeric age/severity, a prespecified two-level sex factor, numeric binary treatment, and a signed continuous post-index endpoint. Five rows have prespecified missing propensity covariates. Two adapters encode the same cohort with canonical versus source column names, age in years versus months, severity in canonical units versus percent units, numeric treatment-code conversion, and fixed category mapping. No real source database is read, and different adapter names do not establish external validity.

Hand matching cases fix exact expected pairs for descending treated scores, exact-score ID ties, exact-distance control ID ties, UTF-8 byte ID ordering, inclusive caliper equality, the immediately larger floating-point distance, no epsilon merging of near ties, zero caliper/zero logit-SD, min/max support boundaries, no common support, no eligible pairs, and one retained pair. Full string identifiers include leading zeros and large numeric strings in local hand evidence.

The explicit covariance counterexample uses treated outcomes (10,20,30,40) and controls (8,19,27,38). Pair differences are (2,1,3,2), mean 2, sample difference variance 2/3, and paired SE sqrt(1/6). Treated variance is 500/3, control variance 482/3, and covariance 490/3; their variance identity gives 2/3. An independent-sample SE would use sqrt(982/12), which is not the intended estimator. Zero pairs, one pair and constant pair differences must preserve defined descriptive values while leaving unavailable inference null with precise reasons.

Balance hand examples distinguish fixed numeric versus Bernoulli indicator denominators and ensure the original treated denominator is reused after matching, including zero-variance and absent-level indicators. Overlap bins remain the declared [0,.1,...,1] grid, with the final right edge inclusive.

## Full entry and refusal coverage

The full suite will compare both real R-entry adapters with the independent R reference, including exact pair membership, individual PS/logit values, support bounds and retained population, caliper SD/width, missingness flow, matched outcome moments, paired inference, SMD and aggregate overlap.

Changing outcomes, permuting source rows or switching same-semantic adapters must preserve PS and pair membership. Outcome changes may alter private pair outcomes/differences and effect estimates. Matching and the PS fit must never use outcome values. No refit after support discarding, control replacement, adaptive caliper, alternate weighting or hidden independent-sample SE is allowed.

A high-baseline endpoint adds 1e12 to the source outcomes. Expected inference uses the actually representable private pair differences and independent paired t reference; exact translation invariance of floating-point outcomes is not assumed. Subtracting two large arm means or decomposing variance into arm variances and covariance is diagnostic, not an authoritative acceptance identity.

Refusals and unavailable cases include missing treatment/outcome (even with a missing covariate), nonbinary treatment, rank deficiency, complete/quasi-separation stress inputs under conservative numerical guards, no common support/pairs, one pair, zero difference variance, duplicated patients, future/identifier/outcome/treatment covariates, unknown variables/options/categories, unsupported outcome or design, and altered input/provider version bindings. Formal separation detection is not claimed.

## Audit and run discipline

Public tables are `psm_flow.csv`, `psm_balance.csv`, `psm_overlap.csv`, and `psm_effect.csv`; figures are `psm_balance.png` and `psm_overlap.png`. Private pairs, subject PS/statuses and fitted model remain in the local run/private directory. The audit reconstructs source canonicalization, missingness and arm denominators, support/matching/unmatched counts, retained treated target population, paired covariance/SE identity, fixed SMD scales, overlap-bin counts and artifact provenance. Binary event counts must remain not-applicable/null. Public exports must not contain patient identities, individual scores, pair membership, outcomes/differences or coefficients.

Full execution requires the root's explicit GO and final production-lock SHA-256. The owned fixture, oracle, harness, audit and this document are hashed and remain unchanged during each complete run. Every attempt uses a new unique evidence directory; failed attempts and their actual reasons remain intact. After a necessary test/provider repair, a complete run must use the final unchanged lock. Old numerical sources and old locks are checked read-only.

Unresolved scientific limits include unmeasured confounding, clinical relevance, real-data external validity, uncertainty from PS estimation or match selection, population-wide ATT beyond retained matched treated subjects, and unavailable specialist-package validation. Matching balance is descriptive; neither a 0.1 SMD reference line nor this suite verifies causal assumptions.
