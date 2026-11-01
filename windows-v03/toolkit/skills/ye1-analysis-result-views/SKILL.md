---
name: ye1-analysis-result-views
description: "从已有来源绑定的分析结果提取基线、效应、ROC、校准、DCA、列线图、重要性或PH表图；不重新拟合或计算新指标。"
---

# 已有结果表图提取

先读同级[总入口](../ye1-clinical-analysis/SKILL.md)的安装、数据与权限规则。只加载本方法的schema/说明，不强跑完整流程。用户不手写JSON；缺结局、单位、参考类别、样本/时间或设计先集中澄清，不为显著性换模型。真实患者行/标识留本地，根据用户指定的本地文件和任务参数直接调用，不创建确认记录。


先读主 Skill 的 references/LOCAL-DRAFTS.md。Agent 只处理需求和数据字典，按明确映射生成本地草稿，通过 scripts/prepare_task.py --draft 读取文件，再调用 toolkit.py。private 任务含规范行，真实数据时不得读回模型。

单项视图ID：`result.binary.calibration`、`result.binary.dca`、`result.binary.roc`、`result.importance`、`result.nomogram`、`result.survival.calibration`、`result.survival.dca`、`result.survival.ph`、`result.survival.roc`、`result.baseline.table`、`result.association.effects`。先核原result/manifest和授权，再schema/doctor/run指定ID。export_existing只提取已有产物；缺新指标时应回到对应后端，不能用视图名称冒称已完成评价。已完成登记路径的本地合成例，逐项证据和未测操作见总Skill的references/CAPABILITIES.json；未声明科学或真实患者验证。

只需读取所选方法的说明与schema。实际安装版本、已测操作、限制和未测项以总Skill的 references/CAPABILITIES.md 为准；先按 references/LOCAL-DRAFTS.md 准备本地元数据。
