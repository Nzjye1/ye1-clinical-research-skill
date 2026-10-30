---
name: ye1-compat-sample-size-proportion-precision
description: "单独调用比例估计精度样本量，复用旧版R工作器并检查已登记设计边界，不作未验证的通用统计或临床结论承诺。"
---

# 比例估计精度样本量

先读同级[总入口](../ye1-clinical-analysis/SKILL.md)的安装、数据与权限规则。只加载本方法的schema/说明，不强跑完整流程。用户不手写JSON；缺结局、单位、参考类别、样本/时间或设计先集中澄清，不为显著性换模型。真实患者行/标识留本地，真实数据由用户本人确认，不能把合成演练当真人授权。


先读主 Skill 的 references/LOCAL-DRAFTS.md。Agent 只处理需求和数据字典，按明确映射生成本地草稿，通过 scripts/prepare_task.py --draft 读取文件，再调用 toolkit.py。private 任务含规范行，真实数据时不得读回模型。

稳定方法 ID：`compat.sample_size.proportion_precision`。这是旧 stats_worker.R 的已实现受限操作；不复制或另写求解器。先 describe/schema/doctor 对应 ID。仅接预期效应/精度、设计、损耗及假设来源，不接患者行。Agent 写本地假设文件，调用 toolkit.py plan --method compat.sample_size.proportion_precision --assumptions <本地假设> --output <新目录>。不能由观察P值反推样本量，不能把简单独立设计公式套到生存、聚类、配对或预测建模。

只需读取所选方法的说明与schema。实际安装版本、已测操作、限制和未测项以总Skill的 references/CAPABILITIES.md 为准；先按 references/LOCAL-DRAFTS.md 准备本地元数据。
