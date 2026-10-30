# 临床分析总入口

版本 0.3.0-windows-local-integrated2。安装后在所选项目使用 `$ye1-clinical-analysis`，也可点名单项Skill；名称/机器ID/限制见 [能力矩阵](references/CAPABILITIES.md)。从 [安装与首次使用](INSTALL.md) 开始。

把本地数据路径、变量字典、研究问题交给Codex。缺单位、事件码、时间定义、独立单位或预设方案时先澄清。不要将患者行或标识粘贴到聊天；本地私有任务由脚本读取与转换，Agent不读取其行数据。详见 [隐私](references/PRIVACY.md)、[本地草稿接口](references/LOCAL-DRAFTS.md)。

结果目录包含原有 result.json、聚合 tables/、figures/、说明.md 与私有证据/模型。原冻结操作只返回私有预测时，额外的private/frozen-display只画已算出的预测、不重训；仅在本地查看。既有结果视图可只有表，不冒作新拟合或新指标。

单项方法仍保留原统计合同。33后端/8别名/11视图/兼容9操作分开列；真实患者流程、物理新机、GUI发现、Mac/WorkBuddy未测。不要将工程通过写成科学或临床有效性已认证。

修复候选 integrated2 的依赖声明、重复运行状态与公开生成器说明见[修复记录](references/FIXES-INTEGRATED2.md)。旧 b87bb57a 客户独审为 NOT_PASSED；当前包是否通过独立复验以新包外回执为准。
