# 能力与限制

下表保留final8既有方法与合成工程验证口径；本开发分支另增[固定公开PBC软件案例验收](PUBLIC-FIXTURES.md)及[实际检查记录](VERIFICATION-SCOPE.md)。它复用原KM方法，不增加方法数，也不扩大真实客户或临床科学验证声明。

版本：0.3.1-windows-local-noninteractive1。Windows + Codex 本地候选。总入口 `$ye1-clinical-analysis`；下面每行可按稳定 ID 点名。

33 个原生数值后端、8 个共享后端的别名、11 个既有结果视图、5 项旧兼容检验及4项样本量/精度规划。另保留1个旧受限入口并拒绝公开执行。48个Skill目录用于发现和组织，不能解释为48种独立算法。

本地合成路径已经运行的证据如下；每个后端至少一次主要操作完成不等于该后端全部参数组合通过。所有方法的真实患者端到端、正式科学评审、物理冷机、Mac/WorkBuddy与真实Codex界面发现均未验证。最终归档的实际验收与SHA见包外最终回执。

|中文名称 / 稳定ID|类型及单独入口|操作 / 必要依赖组|合成执行证据|
|---|---|---|---|
|预设调整模型（linear）<br>`association.adjusted.linear`|alias<br>$ye1-association-adjusted|analyze<br>base|alias-views-1|
|预设调整模型（logistic）<br>`association.adjusted.logistic`|alias<br>$ye1-association-adjusted|analyze<br>base|alias-views-1|
|独立样本 OLS 关联<br>`association.linear`|backend<br>$ye1-association-linear|analyze<br>base|core-forward-4|
|预设 OLS 模型方案<br>`association.linear.plan`|backend<br>$ye1-association-linear-plan|analyze<br>base|core-forward-4|
|二分类 Logistic 关联<br>`association.logistic`|backend<br>$ye1-association-logistic|analyze<br>base|core-forward-4|
|预设 Logistic 模型方案<br>`association.logistic.plan`|backend<br>$ye1-association-logistic-plan|analyze<br>base|core-forward-4|
|固定结点 RCS（linear）<br>`association.rcs.linear`|alias<br>$ye1-association-rcs|analyze<br>base|alias-views-1|
|固定结点 RCS（logistic）<br>`association.rcs.logistic`|alias<br>$ye1-association-rcs|analyze<br>base|alias-views-1|
|预设敏感性分析（linear）<br>`association.sensitivity.linear`|alias<br>$ye1-association-sensitivity|analyze<br>base|alias-views-1|
|预设敏感性分析（logistic）<br>`association.sensitivity.logistic`|alias<br>$ye1-association-sensitivity|analyze<br>base|alias-views-1|
|亚组效应与交互检验（linear）<br>`association.subgroup.linear`|alias<br>$ye1-association-subgroup|analyze<br>base|alias-views-1|
|亚组效应与交互检验（logistic）<br>`association.subgroup.logistic`|alias<br>$ye1-association-subgroup|analyze<br>base|alias-views-1|
|基线描述表与明确分母<br>`baseline.table1`|backend<br>$ye1-baseline-table1|analyze<br>base|core-forward-4|
|探索性 Gaussian mixture 与冻结赋类<br>`exploration.cluster.gmm`|backend<br>$ye1-exploration-cluster-gmm|train/assign<br>base,ml,plot|module-forward-2|
|探索性 KMeans 与冻结赋类<br>`exploration.cluster.kmeans`|backend<br>$ye1-exploration-cluster-kmeans|train/assign<br>base,ml,plot|module-forward-1|
|普通 Cox 的 IPCW 时点评价<br>`evaluation.survival.cox.ipcw`|backend<br>$ye1-evaluation-survival-cox-ipcw|evaluate<br>base|frozen-forward-1|
|惩罚 Cox 的 IPCW 时点评价<br>`evaluation.survival.cox.penalized.ipcw`|backend<br>$ye1-evaluation-survival-cox-penalized-ipcw|evaluate<br>base,penalized,plot|frozen-forward-1|
|二分类已有校准（仅提取）<br>`result.binary.calibration`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|二分类已有 DCA（仅提取）<br>`result.binary.dca`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|二分类已有 ROC/AUC（仅提取）<br>`result.binary.roc`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|已有全局加性贡献重要性（仅提取）<br>`result.importance`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1/importance-retest3.json|
|已有冻结惩罚模型列线图（仅提取）<br>`result.nomogram`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|普通 Cox 已有 IPCW 校准（仅提取）<br>`result.survival.calibration`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|普通 Cox 已有 IPCW DCA（仅提取）<br>`result.survival.dca`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|已有正式 PH 检验（仅提取）<br>`result.survival.ph`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|普通 Cox 已有 IPCW ROC（仅提取）<br>`result.survival.roc`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|HGB interventional TreeSHAP<br>`explanation.binary.hist_gradient_boosting.tree_shap`|backend<br>$ye1-explanation-binary-hist-gradient-boosting-tree-shap|explain<br>base,ml,plot,shap|frozen-guard-retest-2|
|随机森林 interventional TreeSHAP<br>`explanation.binary.random_forest.tree_shap`|backend<br>$ye1-explanation-binary-random-forest-tree-shap|explain<br>base,ml,plot,shap|frozen-guard-retest-2|
|冻结惩罚线性模型 interventional 贡献与列线图<br>`interpretation.linear.interventional`|backend<br>$ye1-interpretation-linear-interventional|explain<br>base,penalized|frozen-guard-retest-2|
|惩罚 Cox 链接尺度贡献与列线图<br>`interpretation.survival.cox.penalized.interventional`|backend<br>$ye1-interpretation-survival-cox-penalized-interventional|fit_explainer/explain<br>base,penalized,plot|frozen-forward-1|
|Gaussian LCGA 或共享协方差增长混合<br>`latent.trajectory.gaussian`|backend<br>$ye1-latent-trajectory-gaussian|train/predict<br>base,ml,plot,formal_latent|module-forward-2|
|Gaussian 普通混合增长模型<br>`longitudinal.growth.gaussian`|backend<br>$ye1-longitudinal-growth-gaussian|train/predict<br>base,ml,plot,growth|module-forward-2|
|PSM 后配对二分类风险差与条件 OR<br>`causal.psm.att.binary`|backend<br>$ye1-causal-psm-att-binary|analyze<br>base,matching,plot|module-forward-2|
|1:1 PSM 与配对连续结局推断<br>`causal.psm.att.continuous`|backend<br>$ye1-causal-psm-att-continuous|analyze<br>base|core-forward-4|
|PSM 后 Cox 配对聚类方差<br>`causal.psm.matched.survival`|backend<br>$ye1-causal-psm-matched-survival|analyze<br>base,matching,plot|module-forward-2|
|限定线性中介与联合 bootstrap<br>`mediation.linear.binary_exposure`|backend<br>$ye1-mediation-linear-binary-exposure|analyze<br>base,matching,plot|module-forward-1|
|二分类 Elastic Net 冻结预测<br>`prediction.binary.elasticnet`|backend<br>$ye1-prediction-binary-elasticnet|train/evaluate/infer<br>base,penalized|core-forward-4；reload-operations-3|
|二分类 HGB 冻结预测<br>`prediction.binary.hist_gradient_boosting`|backend<br>$ye1-prediction-binary-hist-gradient-boosting|train/evaluate/infer/explain<br>base,ml,plot|module-forward-2|
|二分类 LASSO 冻结预测<br>`prediction.binary.lasso`|backend<br>$ye1-prediction-binary-lasso|train/evaluate/infer<br>base,penalized|core-forward-4；reload-operations-3|
|二分类随机森林冻结预测<br>`prediction.binary.random_forest`|backend<br>$ye1-prediction-binary-random-forest|train/evaluate/infer/explain<br>base,ml,plot|module-forward-1；reload-operations-3|
|二分类 Ridge 冻结预测<br>`prediction.binary.ridge`|backend<br>$ye1-prediction-binary-ridge|train/evaluate/infer<br>base,ml|core-forward-4；reload-operations-3|
|非负连续结局 Ridge 冻结预测<br>`prediction.continuous.nonnegative.ridge`|backend<br>$ye1-prediction-continuous-nonnegative-ridge|train/evaluate/infer<br>base,ml|core-forward-4；reload-operations-3|
|有符号连续结局 Elastic Net<br>`prediction.continuous.signed.elasticnet`|backend<br>$ye1-prediction-continuous-signed-elasticnet|train/evaluate/infer<br>base,penalized|core-forward-4；reload-operations-3|
|有符号连续结局 LASSO<br>`prediction.continuous.signed.lasso`|backend<br>$ye1-prediction-continuous-signed-lasso|train/evaluate/infer<br>base,penalized|core-forward-4；reload-operations-3|
|限定 EEI/VVI Gaussian LPA<br>`latent.profile.gaussian`|backend<br>$ye1-latent-profile-gaussian|train/assign<br>base,ml,plot,formal_latent|module-forward-1|
|普通 Cox 冻结绝对风险<br>`prediction.survival.cox`|backend<br>$ye1-prediction-survival-cox|train/infer<br>base|core-forward-4；reload-operations-3|
|惩罚 Cox Elastic Net 与冻结风险<br>`prediction.survival.cox.elasticnet`|backend<br>$ye1-prediction-survival-cox-elasticnet|train/infer<br>base,penalized|core-forward-4；reload-operations-3|
|惩罚 Cox LASSO 与冻结风险<br>`prediction.survival.cox.lasso`|backend<br>$ye1-prediction-survival-cox-lasso|train/infer<br>base,penalized|core-forward-4；reload-operations-3|
|右删失 Cox 关联与指定 PH 诊断<br>`survival.cox.association`|backend<br>$ye1-survival-cox-association|analyze<br>base|core-forward-4|
|右删失 KM 与风险表<br>`survival.kaplan_meier`|backend<br>$ye1-survival-kaplan-meier|analyze<br>base|core-forward-4|
|真实切片总体描述（仅本地工程验证）<br>`baseline.summary`|legacy_restricted<br>无客户入口|describe<br>|旧工程占位，拒绝执行|
|已有总体或分组基线表<br>`result.baseline.table`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|已有OLS或Logistic效应表图<br>`result.association.effects`|existing_result_view<br>$ye1-analysis-result-views|export_existing<br>base|alias-views-1|
|独立两组 Welch t 检验<br>`compat.test.welch_t`|compat_test<br>$ye1-compat-test-welch-t|compare<br>base|legacy-forward-2|
|配对 t 检验（每对一行）<br>`compat.test.paired_t`|compat_test<br>$ye1-compat-test-paired-t|compare<br>base|legacy-forward-2|
|两独立组 Wilcoxon 秩和检验<br>`compat.test.wilcoxon_rank_sum`|compat_test<br>$ye1-compat-test-wilcoxon-rank-sum|compare<br>base|legacy-forward-2|
|2×2 Fisher 精确检验<br>`compat.test.fisher_2x2`|compat_test<br>$ye1-compat-test-fisher-2x2|compare<br>base|legacy-forward-2|
|两组列联表 Pearson 卡方检验<br>`compat.test.chi_square`|compat_test<br>$ye1-compat-test-chi-square|compare<br>base|legacy-forward-2|
|均值估计精度样本量<br>`compat.sample_size.mean_precision`|compat_planning<br>$ye1-compat-sample-size-mean-precision|plan<br>base|legacy-forward-2|
|比例估计精度样本量<br>`compat.sample_size.proportion_precision`|compat_planning<br>$ye1-compat-sample-size-proportion-precision|plan<br>base|legacy-forward-2|
|独立两组均值差样本量<br>`compat.sample_size.two_mean`|compat_planning<br>$ye1-compat-sample-size-two-mean|plan<br>base|legacy-forward-2|
|独立两组比例差样本量<br>`compat.sample_size.two_proportion`|compat_planning<br>$ye1-compat-sample-size-two-proportion|plan<br>base|legacy-forward-2|

## 各方法的边界

`toolkit.py describe --method ID` 返回原始适用条件与不支持条件；`schema` 返回真实登记参数，Agent按需读取。完整机器矩阵见 CAPABILITIES.json。用户无需写JSON。

- 基线：总体/分组描述和明确分母，不把基线P值当因果、预测筛选或平衡证明。OLS/Logistic：原固定HC3/GLM合同；计划模型上限、完整案例、预设敏感性、交互和RCS域守卫原样保留。
- KM/Cox：独立对象、明确时间起点/单位/事件码/删失、无未登记竞争风险/复发/延迟进入；关联Cox与冻结预测Cox分开。PH诊断不通过不自动换模型。
- 惩罚回归/树预测：仅登记的结局、损失、切分、训练内预处理及冻结操作；不做任意算法搜索。冻结模型依赖精确来源、版本、定义与身份范围；失败时不能静默重训。
- IPCW：冻结Cox/惩罚Cox的登记时点评估，显式删失独立性、支持度和权重限制；不自动裁权或推断未登记时点。
- 匹配：现有ATT匹配/配对结局与匹配生存合同；无未测混杂、重叠性、可识别性仍需研究判断。中介限定二元暴露、线性模型和已登记时序/交互及假设，不承诺因果已识别。
- 聚类、正式高斯LPA/LCGA、增长：保留原模型、收敛/成员数/协方差/固定效应/多起点和冻结应用限制；不能把一般聚类或规则斜率命名为正式潜类别轨迹。
- 解释：线性interventional与惩罚Cox的冻结解释域；树SHAP限定RF/HGB已冻结模型和训练背景。解释不证明因果，不能换背景/范围后沿用旧解释器。
- 兼容检验：Welch独立双组、宽表配对t、渐近连续性校正Wilcoxon秩和、Fisher 2×2、期望频数符合登记门槛的Pearson卡方。显式组顺序/缺失/独立单位。无自动换检验。Wilcoxon不一概解释为中位数检验。
- 规划：均值/比例精度及两比例的原正态近似；两均值使用R power.t.test的共同SD、等分配双侧strict功效（不是Welch规划）；预设效应/精度/功效/失访和来源。不是生存、整群、配对、预测建模或事后功效计算。

## 结果视图不是新的计算

11个视图的操作均为 export_existing，只能提取允许来源已有的表/图，复制字节且新拟合数为0。部分视图只有已有表。importance和nomogram仅接受 interpretation.linear.interventional；二分类ROC/校准/DCA仅接受登记的ridge/RF/HGB来源；生存ROC/校准/DCA仅接受登记的普通冻结Cox IPCW来源。不能拿其他结果替代或现场补算指标。

## 尚未作为客户方法迁入的旧资产

- 旧AJ累计发生率与原因特异Cox：共享兼容桥有源码，但没有完整登记的独立用户准入、输出合同和本版验收；保留原研发资产，不将普通KM/Cox冒充竞争风险支持。需另行明确科学合同后接入。
- 旧规则表型、时间窗中位数/斜率、轨迹特征聚类：原工作流的派生/探索资产，不是正式LPA/LCGA。未恢复为强制清洗或独立统计方法；若客户需要，另定指标、时间窗和单位合同。
- 文献/数据库获取、整篇写作投稿、MIMIC/FAERS原库、内部批量平台不迁入。没有新增未定义算法。复合指标公式/截点、部分截图中的“拟合曲线”等含义仍需研究定义；详见 ORIGINAL-35.md。


## 已执行操作与仍未验证的范围

机器矩阵逐项列tested_operations与untested_operations，均来自已完成的合成例，不推断全部参数/设计覆盖。最终归档重验与包SHA由包外回执绑定。真实患者、真人确认全链、科学评审、物理冷机、GUI发现和跨宿主均未验证。

[旧资产逐项迁入决定](LEGACY-ASSET-DECISIONS.md)还明确列出未公开登记的旧classical协方差选项、旧未惩罚Logistic单次holdout、AJ/原因特异Cox与派生规则；它们不被本版33后端的完成声明覆盖。
