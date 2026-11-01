---
name: ye1-prediction-binary-lasso
description: "完成二分类 LASSO 冻结预测；适用于该方法及其已登记操作。使用共享数值底座，不承担数据库获取、论文写作或未支持模型族。"
---

# 二分类 LASSO 冻结预测

先读同级[总入口](../ye1-clinical-analysis/SKILL.md)的安装、数据与权限规则。只加载本方法的schema/说明，不强跑完整流程。用户不手写JSON；缺结局、单位、参考类别、样本/时间或设计先集中澄清，不为显著性换模型。真实患者行/标识留本地，根据用户指定的本地文件和任务参数直接调用，不创建确认记录。


先读主 Skill 的 references/LOCAL-DRAFTS.md。Agent 只处理需求和数据字典，按明确映射生成本地草稿，通过 scripts/prepare_task.py --draft 读取文件，再调用 toolkit.py。private 任务含规范行，真实数据时不得读回模型。

稳定方法ID：`prediction.binary.lasso`；已有操作：`train / evaluate / infer`。这些操作共享原owner，不是新增多套算法。

使用主Skill的scripts/toolkit.py：先`describe --method prediction.binary.lasso`与`schema --method prediction.binary.lasso`，再`doctor --method prediction.binary.lasso`。Agent按原版本契约准备本地task，然后`run --method prediction.binary.lasso --task <项目私有task>`。单独调用只执行这项；需要多个已确认步骤时由总入口组合并保留模型/来源绑定。

当前v0.3处于迁入验收，不把已有源码、schema发现或历史测试当本版功能/临床验收通过；实测状态以最终能力矩阵为准。表图解释以实际结果和method限制为准，科学复核pending。

只需读取所选方法的说明与schema。实际安装版本、已测操作、限制和未测项以总Skill的 references/CAPABILITIES.md 为准；先按 references/LOCAL-DRAFTS.md 准备本地元数据。
