# 旧分析资产迁入决定

源提交e506c155f50d1624d6746cc1189ba03470ac8bb2，仅只读检查源码与已完成盘点，不读取历史患者或样例行。

|原资产|本版决定|理由及实际边界|
|---|---|---|
|33登记后端、8别名、11既有视图|完整接入登记入口|共享原数值owner；每项保留中文名、机器ID、schema和原守卫。数量不代表不同算法或全面科学验证。|
|skills/ye1-association/scripts/stats_worker.R 的5项compare|迁入5项compat.test入口|Welch、配对t、渐近连续性校正Wilcoxon、2×2 Fisher和Pearson卡方。原worker字节不变；外围补显式独立单位、组序、配对宽表、缺失、设计和原准入。|
|同一worker的4项sample_size|迁入4项compat.sample_size入口|均值/比例精度、等分配两均值/两比例。均值精度/比例相关公式采用原正态近似；two_mean使用R power.t.test双侧strict功效、共同SD和等分配，并非Welch规划。失访与来源显式；不从结果算事后功效。|
|同一worker的kind=linear/logistic旧执行路径|不新增平行旧后端|已有登记OLS HC3/Logistic及计划owner承担本版对应关联能力；不复制第二套旧拟合。旧linear还允许classical协方差，此选项未在本版登记公开，不能说与HC3数值等同。若需恢复classical，应明确版本化合同及参考验收。|
|同一worker的kind=prediction未惩罚Logistic单次分层holdout|未作为本版新增入口|这是另一个旧实现，与本版ridge/树预测并非算法等价；未带完整现行冻结模型/来源/时间/评估合同。本版不把它暗中改成ridge、不声称已完整迁入该旧操作。需另立登记合同后恢复，不能绕开原公开方法目录。|
|core/python/clinical_methods/survival.py及相关R桥中的AJ/CIF、原因特异Cox兼容源码|原源码保留，未开放客户入口|原稳定目录没有完整登记该设计；普通KM/Cox不等同竞争风险支持。另定竞争事件码、删失/风险集/估计量和产物合同后接入。|
|legacy/scripts/clinical/trajectory.py及clinical_engine.py的窗口汇总/斜率/规则表型/轨迹特征探索|保留研发资产，不恢复强制前处理|这些是派生/探索流程，不是正式LPA/LCGA；本版已迁入登记的正式高斯模型。需要额外指标/窗口/缺失和单位定义，不能按名称偷换。|
|legacy/scripts/clinical/{association,prediction,survival,clustering,plots}.py旧流水线|仅随必要共享引用保留，不新增重复客户端入口|登记后端与展示使用当前受控owner；不恢复数据库→清洗→模型→论文的旧强制流程，也不把历史合成/real协议模拟当本版患者验证。|
|原35显示项中的复合指标与部分“拟合曲线”等宽泛名称|逐行限制/待定义|ORIGINAL-35.md保留旧16限定、18部分、1待定义；公式、截点、设计和图意未明时不凭空研发。新增统计方法由根协调，不阻断已定义部分的本地交付。|
|数据库、文献、整篇写作/投稿、内部批量平台|不迁入|用户明确范围排除。|

因此“已完整接回”只适用于已核登记的33后端与必要别名/视图，以及明确迁入的9项兼容操作。上列旧classical选项、旧未惩罚holdout预测、竞争风险与派生规则不作完整支持承诺；这属于明确列出的后续合同/产品决策，不能被总数量遮掩。
