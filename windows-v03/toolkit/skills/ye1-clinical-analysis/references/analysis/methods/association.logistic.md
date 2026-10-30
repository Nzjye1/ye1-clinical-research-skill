# 二分类 Logistic 关联

Method: `association.logistic`\
数值入口: `association.logistic`\
Operation: analyze

## 使用前

- 明确患者/记录粒度、字符 ID、来源、单位、编码、时间可知性、缺失、权重和预设方案。
- 当前共享后端只允许合成工程任务；真实来源需独立契约，不得重标为 synthetic。

## 参数与结果

用 `schema association.logistic` 取得版本 `clinical-study-input@0.1.0-candidate1` 的原始参数约束；`validate` 调原语义校验，未知字段不会静默忽略。

数值 owner: clinical_methods.association

```json
{
  "model": "logistic",
  "covariance": "model",
  "missing": "complete_case",
  "ci_level": 0.95
}
```

核对结果的来源/方法版本、单位/尺度、有效 n、事件/删失、逐指标分母、缺失和不可估计原因。个人预测/划分/配对/模型/贡献背景留在本地 private。

## 单项示例与拒绝

只做二分类 Logistic 关联；沿用已确认研究设计，不运行其他分析。

```text
python scripts/analysis_call.py --runtime LOCAL_RUNTIME.json run association.logistic --task PREPARED_TASK.json
```

不支持操作/未知 method、所选功能与 task 不符、版本漂移、真实来源未接入均明确拒绝；原 provider 的方法资格拒绝码保持不变，不自动改算法。


## 真实输入 V1 检查点

本功能另接受 `clinical-study-input@1.0`。Agent声明来源real/synthetic、用途engineering_test/research_analysis、变量角色/单位/缺失/时间与患者粒度，使用项目数据选择和实际权限记录；真实工程测试保持real、科学审核pending。调用 `schema association.logistic --input-version clinical-study-input@1.0` 获取契约。仅本功能及另外两个基础方法开放本批真实准入，其他方法不因此自动开放；[完整边界](../../../../../_shared/clinical_analysis/REAL-INPUT-CONTRACT.md)。
