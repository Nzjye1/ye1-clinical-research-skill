# 预设 OLS 模型方案

Method: `association.linear.plan`\
数值入口: `association.linear.plan`\
Operation: analyze

## 使用前

- 明确患者/记录粒度、字符 ID、来源、单位、编码、时间可知性、缺失、权重和预设方案。
- V1 项目来源准入支持 real，来源/用途/scientific pending 分开；未知时钟可用于明确横断面关联，不冒充前瞻可知。

## 参数与结果

用 `schema association.linear.plan` 取得版本 `clinical-study-input@0.3.0-candidate1` 的原始参数约束；`validate` 调原语义校验，未知字段不会静默忽略。

数值 owner: clinical_methods.association.plan

```json
{
  "max_prespecified_models": 6,
  "roles": [
    "primary",
    "adjustment",
    "sensitivity"
  ],
  "primary_model": "exactly_one_first",
  "model_selection": "none",
  "multiplicity": "unadjusted_prespecified",
  "ci_level": 0.95,
  "sample_strategies": [
    "per_model_complete_case",
    "common_complete_case"
  ],
  "per_model_complete_case_order": [
    "prespecified_filter",
    "model_complete_cases"
  ],
  "common_complete_case_order": [
    "union_model_fields_complete_cases",
    "prespecified_filter"
  ],
  "common_union_fields": "all model outcomes, exposures, covariates and subgroup fields; filter-only fields excluded",
  "filter_missingness": "missing filter-only values excluded at filter step and counted separately",
  "same_sample_claim": "common eligibility does not imply equal samples after different sensitivity filters",
  "sensitivity": {
    "filters": [
      "eq",
      "ne",
      "lt",
      "le",
      "gt",
      "ge",
      "in"
    ],
    "filter_roles": [
      "exposure",
      "covariate",
      "group"
    ],
    "filters_only_in": "sensitivity models",
    "nested_legacy_sensitivity": "unsupported",
    "per_model_covariates": "explicit and prespecified",
    "flow": "source/common/filter/complete-case counts and exact blocked reasons"
  },
  "subgroup": {
    "moderator": "declared categorical levels and reference",
    "exposure": "numeric linear exposure only",
    "effect": "within-level exposure slope contrast from one pooled interaction model",
    "heterogeneity": "joint interaction Wald test, not comparison of within-level P values",
    "minimum_group_n": "explicit integer at least 5; engineering gate, not sufficient-sample guarantee",
    "no_events_or_nonevents": "exact model block with preserved group counts",
    "separate_subgroup_fits": false
  },
  "rcs": {
    "basis": "existing restricted cubic spline with linear tails",
    "knots": "3 to 7 finite strictly increasing prespecified values",
    "grid": "3 to 101 finite strictly increasing prespecified values",
    "reference": "explicit; within declared increasing domain",
    "support": "knots and declared domain within actual model complete-case exposure support; grid inside domain",
    "contrast": "exposure value versus fixed reference; full model covariance",
    "tests": [
      "overall exposure joint Wald",
      "nonlinear terms joint Wald"
    ],
    "confidence_intervals": "pointwise 95%; no simultaneous-band claim",
    "knot_or_reference_selection": "none; no outcome/significance-driven search",
    "extrapolation": "refused",
    "effect_scale": "mean_difference",
    "standard_error_scale": "outcome_units",
    "interval_method": "Wald t using full HC3 covariance"
  },
  "causal_interpretation": false,
  "automatic_fallback": false,
  "model": "linear",
  "covariance": "HC3"
}
```

核对结果的来源/方法版本、单位/尺度、有效 n、事件/删失、逐指标分母、缺失和不可估计原因。个人预测/划分/配对/模型/贡献背景留在本地 private。

## 单项示例与拒绝

只做预设 OLS 模型方案；沿用已确认研究设计，不运行其他分析。

```text
python scripts/analysis_call.py --runtime LOCAL_RUNTIME.json run association.linear.plan --task PREPARED_TASK.json
```

不支持操作/未知 method、所选功能与 task 不符、版本漂移、真实来源未接入均明确拒绝；原 provider 的方法资格拒绝码保持不变，不自动改算法。

## V1 关联计划准入

用 `--input-version clinical-study-input@1.0` 明确选择新版schema。实际分析仍调用原OLS/Logistic计划owner；调整、敏感性子集、RCS固定结点/参考和亚组联合交互检验均须预设，保留共同完整案例或逐模型案例策略。未知字段/ID预测/未来字段/重复患者不放行。当前provider最多200个已选行，是技术验证范围；超限精确拒绝，不静默选200人，也不是科学样本上限。

公共入口本批通过合成工程例；real分支协议模拟不等于实际真实E2E，scientific_review始终pending。实数值不作因果或自动科学通过宣称。
