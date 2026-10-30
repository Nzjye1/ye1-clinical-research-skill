# 原35显示项逐项追踪

截图条目有重复与宽泛名称。旧实现盘点为16限定实现、18部分、1待定义；本版迁入已登记部分并不把宽泛行改标为完全支持。下表仅为能力映射，不采用历史real_e2e为本版证据。

|行|原分组 / 名称|旧覆盖边界|本版登记ID|限制|
|---|---|---|---|---|
|1|常用分析 / 基线资料对比|partial|`baseline.table1`|总体或分组描述、明确分母，区分结局描述/分层与预测特征；复杂抽样及不支持的设计仍拒绝。|
|2|常用分析 / 复合指标区间资料|definition_pending||原表公式、切点及区间含义尚未明确；当前只有声明单位换算，不冒称通用派生指标完成。|
|3|常用分析 / 线性回归|bounded|`association.linear`<br>`association.linear.plan`|OLS 固定连续结局关联范围；复杂抽样、聚类推断与因果解释未覆盖。|
|4|常用分析 / 敏感性分析|partial|`association.linear.plan`<br>`association.logistic.plan`|预先指定方案及样本流已接通；不是任意方法/多重插补敏感性框架。|
|5|常用分析 / 模型调整|partial|`association.linear.plan`<br>`association.logistic.plan`|预设调整模型、共同完整案例或逐模型案例策略；更复杂纵向/抽样设计未覆盖。|
|6|常用分析 / 亚组分析|partial|`association.linear.plan`<br>`association.logistic.plan`|组内效应与交互检验明确区分；支持组合以现有闭合契约为准。|
|7|常用分析 / RCS曲线|partial|`association.linear.plan`<br>`association.logistic.plan`|固定结点/参考值/域及总体和非线性检验；全部模型族的RCS组合未完成。|
|8|常用分析 / 中介分析|bounded|`mediation.linear.binary_exposure`|二元基线暴露、连续中介/结局、可选交互和联合bootstrap；反事实解释依赖明确假设，不覆盖任意中介模型族。|
|9|常用分析 / 轨迹方程|bounded|`longitudinal.growth.gaussian`<br>`latent.trajectory.gaussian`|普通Gaussian ML增长与正式Gaussian LCGA/共享协方差增长混合；线性/二次，随机截距或斜率。低稳定性bootstrap保留；冻结应用为已观测序列后验赋类，不是前瞻预测。|
|10|常用分析 / 剖面分析|bounded|`latent.profile.gaussian`|正式mclust EEI/VVI Gaussian LPA，训练内选择/转换/稳定性与冻结赋类；不以探索GMM替代LPA，不含BLRT/LMR或三步推断。|
|11|常用分析 / 聚类分析|bounded|`exploration.cluster.kmeans`<br>`exploration.cluster.gmm`|探索性KMeans/GMM、训练内转换/选择/稳定性与冻结赋类；分群不自动构成疾病亚型或临床有效性。|
|12|Logistic预测 / 基线资料对比|partial|`baseline.table1`|总体或分组描述、明确分母，区分结局描述/分层与预测特征；复杂抽样及不支持的设计仍拒绝。|
|13|Logistic预测 / 倾向性匹配|bounded|`causal.psm.att.binary`|沿既有1:1无放回匹配，二分类结局配对风险差和精确条件OR；仅保留配对人群，PS估计/选择不确定性未覆盖。OR无穷边界图注修复已获独立定向关闭。|
|14|Logistic预测 / 单/多因素分析|bounded|`association.logistic`<br>`association.logistic.plan`|明确二元编码及预设调整的关联推断；不自动进行按p值筛选或作因果宣称。|
|15|Logistic预测 / LASSO回归|bounded|`prediction.binary.lasso`<br>`prediction.binary.elasticnet`|固定glmnet、训练内预处理/CV与冻结推理；无普通选择后p值、无多alpha搜索。|
|16|Logistic预测 / ROC|partial|`prediction.binary.ridge`<br>`prediction.binary.lasso`<br>`prediction.binary.elasticnet`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`|Ridge有ROC评价；penalized有原logit排序AUC指标，全部模型统一ROC曲线尚未覆盖。 RF/HGB另有相应ROC、分组校准、预设阈值DCA及冻结合成外部评价；这不自动补齐线性惩罚模型的缺失接口。|
|17|Logistic预测 / 拟合曲线|partial|`prediction.binary.ridge`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`|原表“拟合曲线”含义待确认；以下仅按校准用途暂定映射：现有描述分组不等于已验证校准斜率/区间，penalized校准仍缺。 RF/HGB另有相应ROC、分组校准、预设阈值DCA及冻结合成外部评价；这不自动补齐线性惩罚模型的缺失接口。|
|18|Logistic预测 / DCA|partial|`prediction.binary.ridge`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`|既有Ridge预设阈值评价；penalized DCA尚未接入。 RF/HGB另有相应ROC、分组校准、预设阈值DCA及冻结合成外部评价；这不自动补齐线性惩罚模型的缺失接口。|
|19|Logistic预测 / 列线图|partial|`interpretation.linear.interventional`|v0.9只从冻结二分类LASSO/Elastic Net导出可反查列线图；Ridge/普通Logistic尚未纳入。|
|20|Logistic预测 / 内外验证|partial|`prediction.binary.ridge`<br>`prediction.binary.lasso`<br>`prediction.binary.elasticnet`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`|内部留出及同语义外部合成冻结应用；未做真实临床外部验证或所有模型校准/不确定性。 RF/HGB另有相应ROC、分组校准、预设阈值DCA及冻结合成外部评价；这不自动补齐线性惩罚模型的缺失接口。|
|21|Logistic预测 / KM曲线|bounded|`survival.kaplan_meier`|独立的单结局右删失生存描述；KM不是二分类预测概率解释或验证。|
|22|Cox分析 / 基线资料对比|partial|`baseline.table1`|总体或分组描述、明确分母，区分结局描述/分层与预测特征；复杂抽样及不支持的设计仍拒绝。|
|23|Cox分析 / 倾向性匹配|bounded|`causal.psm.matched.survival`|沿既有固定PS匹配，对单结局右删失使用按配对聚类的Cox方差；不声称独立样本SE或总体因果ATT。|
|24|Cox分析 / 单/多因素分析|bounded|`survival.cox.association`|固定Breslow ties、HR/CI和正式PH检验；仅支持声明的单结局右删失语义。|
|25|Cox分析 / LASSO回归|bounded|`prediction.survival.cox.lasso`<br>`prediction.survival.cox.elasticnet`|固定glmnet/Breslow，折内预处理/CV及冻结绝对风险；已新增IPCW和解释接线，仍无选择后有效推断或惩罚模型正式PH接口。|
|26|Cox分析 / ROC|bounded|`evaluation.survival.cox.ipcw`<br>`evaluation.survival.cox.penalized.ipcw`|普通和惩罚Cox的冻结风险接同一累计/动态IPCW ROC-AUC与Brier；预设可识别时点，边际删失假设，暂无不确定性。|
|27|Cox分析 / 拟合曲线|partial|`evaluation.survival.cox.ipcw`<br>`evaluation.survival.cox.penalized.ipcw`|拟合曲线仍暂按校准理解：普通与惩罚Cox可作删失感知描述分组图，不声称校准斜率/区间/检验。|
|28|Cox分析 / DCA|bounded|`evaluation.survival.cox.ipcw`<br>`evaluation.survival.cox.penalized.ipcw`|普通与惩罚Cox使用同一预设时点/阈值IPCW DCA和treat-all/none；保留删失/positivity边界。|
|29|Cox分析 / 列线图|partial|`interpretation.survival.cox.penalized.interventional`|惩罚Cox冻结系数/基线风险导出的时点风险列线图及数值反查；显示域预设，不冒称未保存的训练观测域；普通Cox/Ridge列线图未覆盖。|
|30|Cox分析 / 内外验证|partial|`prediction.survival.cox`<br>`prediction.survival.cox.lasso`<br>`prediction.survival.cox.elasticnet`<br>`evaluation.survival.cox.ipcw`<br>`evaluation.survival.cox.penalized.ipcw`|普通/惩罚Cox冻结外部合成推理、IPCW评价/重载接线；风险模型不在外部重拟合，删失分布来源另列；真实外部临床验证未做。|
|31|Cox分析 / KM曲线|bounded|`survival.kaplan_meier`|风险表及有效区间已接入；竞争风险/延迟进入/重复事件不能静默当普通右删失。|
|32|机器学习 / 二分类机器学习|bounded|`prediction.binary.ridge`<br>`prediction.binary.lasso`<br>`prediction.binary.elasticnet`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`|加入RF/HGB，训练内调参、独立sigmoid校准与冻结评价；不把原截断截图扩展为所有机器学习算法。|
|33|机器学习 / SHAP与模型解释|partial|`interpretation.linear.interventional`<br>`interpretation.survival.cox.penalized.interventional`<br>`explanation.binary.random_forest.tree_shap`<br>`explanation.binary.hist_gradient_boosting.tree_shap`|限定线性/Cox链接尺度及RF/HGB interventional TreeSHAP；可信模型拟合集背景独立冻结。sigmoid校准映射log-odds贡献，不是逐项概率贡献；onehot求和不冒充分组Shapley。TreeSHAP阈值等价表示通过限定独立边界复验；公共背景登记/完整集成另验。|
|34|机器学习 / 变量重要性图|partial|`interpretation.linear.interventional`<br>`interpretation.survival.cox.penalized.interventional`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`<br>`explanation.binary.random_forest.tree_shap`<br>`explanation.binary.hist_gradient_boosting.tree_shap`|支持相应目标队列平均绝对贡献、置换重要性/PDP、TreeSHAP汇总；保留方法/尺度/样本来源，不称因果重要性。|
|35|机器学习 / 训练/验证集拆分|partial|`prediction.continuous.nonnegative.ridge`<br>`prediction.binary.ridge`<br>`prediction.survival.cox`<br>`prediction.continuous.signed.lasso`<br>`prediction.continuous.signed.elasticnet`<br>`prediction.binary.lasso`<br>`prediction.binary.elasticnet`<br>`prediction.survival.cox.lasso`<br>`prediction.survival.cox.elasticnet`<br>`prediction.binary.random_forest`<br>`prediction.binary.hist_gradient_boosting`<br>`latent.profile.gaussian`<br>`latent.trajectory.gaussian`|按各方法显式患者/组/可用时间语义隔离；RF/HGB另隔离校准集，解释背景只来自模型拟合集；正式潜类方法有预设subject split。未声称所有方法支持全部时间拆分/嵌套CV。|
