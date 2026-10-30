# 1:1 PSM 与配对连续结局推断

Method: `causal.psm.att.continuous`\
数值入口: `causal.psm.att.continuous`\
Operation: analyze

## 使用前

- 明确患者/记录粒度、字符 ID、来源、单位、编码、时间可知性、缺失、权重和预设方案。
- 使用明确V1来源契约：real/synthetic、engineering_test/research_analysis、scientific_review=pending分别声明；真实任务须满足本项目数据选择、来源/角色/单位/时序及方法资格，不能重标synthetic。
- 明确处理/中介、时序、估计目标、保留匹配人群与识别假设；不因运行成功宣称因果。

## 参数与结果

用 `schema causal.psm.att.continuous` 取得版本 `clinical-study-input@0.7.0-candidate1` 的原始参数约束；`validate` 调原语义校验，未知字段不会静默忽略。

数值 owner: clinanalysis.psm_v07

```json
{
  "propensity": "single unpenalized stats::glm binomial logit MLE; explicit categories and fixed controls",
  "missing": "complete-case PS covariates; missing treatment or outcome refused before any filtering",
  "distance": "raw fitted logit PS, no clipping",
  "support": "inclusive observed minmax intersection, discard both arms, no PS refit",
  "caliper": "preset multiplier default 0.2 times support-retained combined sample SD; inclusive boundary",
  "matching": "1:1 greedy without replacement; descending treated logit; exact ties by UTF-8 ID bytes",
  "target": "complete-covariate support-retained matched treated; not original full-cohort ATT",
  "effect": "treated-minus-control mean pair difference; conditional paired t inference",
  "variance": "sample variance of pair differences / pair count; no independent-sample SE",
  "degenerate": "<2 pairs or zero difference variance retains defined descriptive contrast with null CI/p and reason",
  "balance": "fixed pre-support complete-case treated SD; numeric sample SD, categorical Bernoulli indicator SD",
  "overlap": "prespecified probability bins for fit, support-retained and matched populations",
  "separation": "numerical guards only; no formal complete/quasi-separation proof",
  "maximum_synthetic_subjects": 200
}
```

核对结果的来源/方法版本、单位/尺度、有效 n、事件/删失、逐指标分母、缺失和不可估计原因。个人预测/划分/配对/模型/贡献背景留在本地 private。

## 单项示例与拒绝

只做1:1 PSM 与配对连续结局推断；沿用已确认研究设计，不运行其他分析。

```text
python scripts/analysis_call.py --runtime LOCAL_RUNTIME.json run causal.psm.att.continuous --task PREPARED_TASK.json
```

不支持操作/未知 method、所选功能与 task 不符、版本漂移、真实来源未接入均明确拒绝；原 provider 的方法资格拒绝码保持不变，不自动改算法。

## V1 真实来源接线

用 `--input-version clinical-study-input@1.0` 发现对应新版闭合参数schema，旧synthetic版本保留兼容。源真实性、任务用途和科学审核分开；工程用途的真实数据仍是real。冻结模型/解释器/转换链保留本次来源、用途、版本与单位；旧无来源制品不能靠改标记升级。TreeSHAP只能使用当前成功公共训练登记的训练背景，不能上传任意行声称训练背景；解释不重拟合预测模型。

本批该入口已有小合成公共调用，real标签仅人工协议测试，实际真实临床E2E未做。scientific_review始终pending。保留各方法资源/样本/事件/支持域/未知类别拒绝；core惩罚/PSM的200行工程限制尚待下一批产品化，不能把当前源码当几万行已验证的完整版本。
