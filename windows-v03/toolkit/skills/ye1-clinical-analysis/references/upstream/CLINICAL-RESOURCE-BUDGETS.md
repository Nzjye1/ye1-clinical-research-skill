# Clinical analysis resource budgets

本地候选已将当前生产通路中的200/500行工程常量提取为有限资源预算。旧范围内数值等价；不抽样、不截断、不换特征、不降低精度。算法、收敛、最小事件数、完整案例、未知类别、冻结模型和来源校验保持有效。新规模证据仅为合成工程验证，科学审核仍待定。

## One request budget

For current `clinical-study-input@1.0` and `clinical-module-task@1.1`, the project request owns `execution` budgets. Keep existing source, design and authorization declarations. Core V1 requires row/raw/decoded limits; module V1.1 permits them optionally and resolves missing limits from the method profile. `describe METHOD` exposes the profile. Explicit lower bounds are never enlarged.

```json
{
  "max_rows": 10000,
  "max_bytes": 16777216,
  "max_decoded_bytes": 67108864,
  "resource_budget": {
    "max_design_columns": 128,
    "max_work_units": 250000000,
    "max_candidate_pairs": 4000000,
    "max_background_rows": 10000
  }
}
```

The shared source of defaults and hard ceilings is `_shared/clinical_analysis/integration/core/config/resource-budget-profiles.json`, consumed by both Python and R admission helpers. The example is for a tabular/linear family; use the appropriate method defaults below. Fields must be finite positive integers, never booleans, floats, numeric strings, NaN, infinity or negative values. Unknown budget fields are rejected. These settings change no environment, OS permission or dependency.

| Family | Default / maximum input rows | Additional finite cost bound |
|---|---:|---|
| Baseline, OLS/Logistic, plans, signed LASSO/Elastic Net | 10,000 / 100,000 | Declared design and fitting-work budget; original feature/encoded-column and CV support remain |
| Continuous/binary/survival PSM | 2,000 / 20,000 | Candidate treated×control pairs default4M, maximum100M; preflight before design/propensity fit; no matching or caliper change |
| Ordinary and penalized frozen Cox prediction | 5,000 / 20,000 | Conservative quadratic risk-set/design work; frozen preprocessing and baseline hazards retained |
| Cox IPCW evaluation | 5,000 / 20,000 | Horizon-dependent quadratic work estimate; censoring assumptions/positivity and empty-bin rules unchanged |
| Formal PH | 1,000 / 5,000 | Additional quadratic design work; no scientific PH-pass claim |
| Linear/Cox affine interpretation | 5,000 / 20,000 | Full-training background separately defaults10,000, hard100,000; no background subsampling |
| RF/HGB training | 10,000 / 100,000 | Existing30 raw/80 encoded feature support; background cap default200, hard2,000 |
| RF/HGB TreeSHAP application | 1,000 / 5,000 | Background cap default200, hard2,000; conservative application×background×tree-node work |

Training history has a separate finite100,000-identity bound; a one-row application is not rejected because its frozen training population exceeded the application-row budget. Background size and analysis population N are distinct. TreeSHAP's existing trusted post-training capture still selects100 by default; a background budget is a ceiling, not an instruction to silently change capture size. Explicit larger trusted captures must satisfy the original training-partition/lineage bindings. The10-row statistical/support minimum is unchanged.

Other method-specific support remains explicit: latent methods retain their existing3,000 training-subject and20,000 source-row limits; encoded dimensions, candidate counts, exact vector shapes and optimization support are not mechanically relaxed by this change. Legacy synthetic fixture constructors still generate their original200 rows; this no longer limits current V1 numerical owners.

## Bounds, refusals and observations

Raw/decoded defaults are16/64MiB with256MiB absolute caps; private serialized provider requests have their own finite bound. The existing metadata task-entry size check also remains. Declared design defaults128 columns (hard1,024); estimated work defaults250M units (hard10B). These are conservative admission estimates, **not OS-enforced memory or wall-clock limits**. Raising a budget is an explicit project action within the published ceiling, never a statistical adequacy claim or guarantee of speed.

For PSM, if a1,000-row cohort's candidate-pair estimate exceeds a100,000-pair request budget, it is rejected before propensity fitting; explicitly raising the pair budget within100M can allow the same unchanged cohort. No source rows are discarded to fit a budget. Full-training linear explanation similarly rejects a background that exceeds its separate cap rather than taking a hidden subset.

Errors include `RESOURCE_ROW_BUDGET_EXCEEDED`, `RESOURCE_CANDIDATE_PAIR_BUDGET_EXCEEDED`, `RESOURCE_BACKGROUND_BUDGET_EXCEEDED`, `RESOURCE_HISTORY_BUDGET_EXCEEDED`, `RESOURCE_DESIGN_BUDGET_EXCEEDED`, `RESOURCE_WORK_BUDGET_EXCEEDED`, and `RESOURCE_BUDGET_INVALID`. Output schemas use finite population/pair counter bounds instead of old200/500 fixture maxima; count relationships and statistical minima remain validated.

Numerical owner tests cover old-boundary exact equivalence, boundary+1 and1,000-row train/apply/evaluate/explain representatives. Previous common-plan10,000-row observation remains20.9s and roughly328MiB sampled process-tree working set on this machine; it is not a promise for the costly families. New public-call receipts state complete/partial/refused separately. Empty IPCW calibration bins remain `partial` even when other metrics compute.

Guard extraction changes genuine source digests. Frozen models and explainers retain strict version/hash checks: no model is silently upgraded or relabelled. New models freeze/reload under the newly bound code; old artifacts requiring the previous code identity must use their pinned runtime or a separately reviewed migration.

No new actual-real clinical E2E, dependency installation, full regression, Git staging, commit, push, PR, release or ZIP was performed in this short batch. Final integrated/clean-environment acceptance and the original35-item scientific scope remain separate.
