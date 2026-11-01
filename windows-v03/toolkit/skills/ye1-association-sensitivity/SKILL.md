---
name: ye1-association-sensitivity
description: "处理预设敏感性分析请求；按已明确的连续或二分类结局选择OLS/Logistic叶路由，不自动进行变量筛选或改变预设方案。"
---

# 预设敏感性分析

先读同级[总入口](../ye1-clinical-analysis/SKILL.md)的安装、数据与权限规则。只加载本方法的schema/说明，不强跑完整流程。用户不手写JSON；缺结局、单位、参考类别、样本/时间或设计先集中澄清，不为显著性换模型。真实患者行/标识留本地，根据用户指定的本地文件和任务参数直接调用，不创建确认记录。


先读主 Skill 的 references/LOCAL-DRAFTS.md。Agent 只处理需求和数据字典，按明确映射生成本地草稿，通过 scripts/prepare_task.py --draft 读取文件，再调用 toolkit.py。private 任务含规范行，真实数据时不得读回模型。

此Skill组织两个叶路由别名：`association.sensitivity.linear`、`association.sensitivity.logistic`。它们复用原linear.plan/logistic.plan，不计为额外算法。先describe/schema/doctor对应ID，再用总入口toolkit.py单项调用；结局类型未确认先问，不能为了可用而换模型。已完成登记路径的本地合成例，逐项证据和未测操作见总Skill的references/CAPABILITIES.json；未声明科学或真实患者验证。

只需读取所选方法的说明与schema。实际安装版本、已测操作、限制和未测项以总Skill的 references/CAPABILITIES.md 为准；先按 references/LOCAL-DRAFTS.md 准备本地元数据。
