# 通用研究输入契约首批（开发中，不公开）

单一数值owner、同一clinanalysis入口。`clinical-study-input@1.0`首批仅接baseline.table1、association.linear、association.logistic；既有synthetic版本保持原行为。任务由Agent准备，调用者不必写JSON。

- data_origin：real/synthetic；每源source_kind、原字节hash和明确本地视图独立绑定，hash只证明所读字节一致，不证明来源机构、去标识或医学定义真实性。
- task_purpose：engineering_test/research_analysis；与来源独立。scientific_review始终pending，不由任务调用者升格。
- real任务复用同一项目的.ye1-privacy选择、历史链及有来源的当次权限记录；不创建固定全客户授权，不以旧窄工程receipt替代研究确认。研究任务需真实用户方案确认；代理转达的工程指令只能支持engineering_test，不能批准研究。
- `captured_local_process` 是新登记的本次调用范围：固定Agent命令捕获stdout/stderr到项目私有日志，返回固定状态；任务、choice、源码及运行时绑定，结束后receipt失效。它不是全局宿主沙箱、网络隔离或用户身份认证。旧exclusive gateway仍保留原检查，没有失败自动切换。新项目可依据确有的当前用户指令建立自己的记录，不能伪造旧登记。
- 变量任意命名，声明类型/单位/类别/缺失/角色；描述可用descriptive_measure、stratification_label/outcome_summary，不把结局分层描述误判为预测泄漏。未知时间显式null；只有描述或明确横断面关联可用未定时序，不能声称预测/因果。
- 总体或分组描述；人数和人次分开。关联仅独立患者、无权重、完整案例、固定OLS HC3或Logistic model方差。重复患者、调查设计、竞争风险等按方法明确拒绝。
- 选定CSV/gzip视图、列映射、显式不参与列、单视图、不执行join。来源/项目/输出路径绑定，资源预算由任务明确声明，取消200人科学门槛。
- 允许项目内文件；外部本地视图须在当次权限记录逐文件绑定确切路径和hash，不扩大为目录权限，也不绕过执行器的文件访问权限。工程专用的一患者一记录选取必须显式声明键和UTF-8词典序，保留源人次→所选患者→完整案例流；它不等于临床首台手术，不可用于research_analysis定义研究队列。
- 输出采用clinical-analysis-result@1.0，来源、用途、审核状态与test_only各自传播至结果、CSV元数据、图注和清单；真实工程数据依然real。后续预测/生存/各模块必须先接同一契约再开放，不自动开放旧synthetic-only入口。

真实研究用例若缺临床定义，仅该用例pending；通用接口可继续开发。当前VitalDB字段字典不能替代OLS/Logistic研究确认。本批已有真实工程基线、OLS和Logistic闭环，全部保持real/engineering_test/pending；它们不复现既往患者聚类HC1方案，也不产生新的临床结论。独立R统计参考使用合成数据；真实数据闭环验证的是准入、执行、来源及样本流。最终整合后仍需统一全回归，其他共享方法的真实准入尚未接入。
