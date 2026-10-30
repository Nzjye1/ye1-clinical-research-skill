# PSM 后配对二分类风险差与条件 OR

Method: `causal.psm.att.binary`\
数值入口: `causal.psm.att.binary`\
Operation: analyze

## 使用前

- 明确患者/记录粒度、字符 ID、来源、单位、编码、时间可知性、缺失、权重和预设方案。
- V1.1 接受独立声明 real/synthetic、engineering_test/research_analysis 与科学审核 pending；真实任务必须满足当前项目来源/权限/角色/单位/时序契约，不能重标 synthetic。
- 明确处理/中介、时序、估计目标、保留匹配人群与识别假设；不因运行成功宣称因果。

## 参数与结果

用 `schema causal.psm.att.binary` 取得版本 `clinical-module-task@1.0` 的原始参数约束；`validate` 调原语义校验，未知字段不会静默忽略。

数值 owner: mediation_matching

```json
{
  "operations": [
    "analyze"
  ],
  "details": "Read the exact provider payload schema; no heuristic method substitution."
}
```

核对结果的来源/方法版本、单位/尺度、有效 n、事件/删失、逐指标分母、缺失和不可估计原因。个人预测/划分/配对/模型/贡献背景留在本地 private。

## 单项示例与拒绝

只做PSM 后配对二分类风险差与条件 OR；沿用已确认研究设计，不运行其他分析。

```text
python scripts/analysis_call.py --runtime LOCAL_RUNTIME.json run causal.psm.att.binary --task PREPARED_TASK.json
```

不支持操作/未知 method、所选功能与 task 不符、版本漂移、真实来源未接入均明确拒绝；原 provider 的方法资格拒绝码保持不变，不自动改算法。

## V1.1 来源契约

用 `schema causal.psm.att.binary --input-version clinical-module-task@1.1` 取得明确版本。原 V1.0 示例仍限合成任务。V1.1 通过共享注册锁调用同一数值 owner，结果为 `clinical-modular-result@1.1`。CSV 与可信父结果绑定的 metadata 一起交付；患者行/模型仍留本地 private。

本短批公共入口成功例使用合成工程数据；真实聚类曾实际准入并运行，但按预设规则拒绝 `NO_ADMISSIBLE_CLUSTER_MODEL`。不能据此宣称所有真实 E2E 或临床科学验证通过。
