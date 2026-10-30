# 方法定义、可解释范围与参考

## 中介

令 A∈{0,1}、M/Y 为连续变量、C 为处理前数值混杂集。固定模型：

`E(M|A,C)=alpha0+alphaA*A+alphaC*C`

`E(Y|A,M,C)=beta0+betaA*A+betaM*M+betaC*C+[betaAM*A*M]`

方括号项仅在预先指定 interaction=true 时存在，不根据 P 值选择。对完整案例的 C 经验分布，计算 `Q(a,b)=mean_C E[Y|A=a,M=E(M|A=b,C),C]`。因为结果模型对 M 线性，代入条件均值恰好完成该线性模型下的积分，不需要模拟正态中介。

- ACME(0)=Q(0,1)−Q(0,0)，ACME(1)=Q(1,1)−Q(1,0)。
- ADE(0)=Q(1,0)−Q(0,0)，ADE(1)=Q(1,1)−Q(0,1)。
- TOTAL=Q(1,1)−Q(0,0)=ADE(0)+ACME(1)=ADE(1)+ACME(0)。

这是指定条件均值模型的标准化分解。把它解释为自然因果效应还要求一致性/无干扰、暴露及中介正值性、无未测 A–M/A–Y/M–Y 混杂、无处理诱发的 M–Y 混杂、时序和正确模型。研究声明这些条件不等于验证成立，随机化暴露也不自动随机化中介。[Imai、Keele、Yamamoto 原论文](https://imai.fas.harvard.edu/research/files/mediation.pdf)给出识别及敏感性讨论。本模块没有实现敏感性分析。

完整案例同时覆盖两模型全部变量；目标限定于该案例集，不自动识别源总体。主体 bootstrap 以同一抽样索引联合重拟合两模型，在每个重抽样经验 C 分布上标准化，固定 Mersenne-Twister/Inversion/Rejection、种子和 B。95%区间用 R type=7 百分位数。B≥200仅为工程下限，不代表尾部分位数或小样本覆盖可靠；正式研究应预先设定更充分的重抽样预算并评估稳定性。至少 max(200,ceil(0.9B)) 次成功才提供区间，任何失败均记录并令整体 partial；不重试到凑够成功，不给失败 replicate 填0，不输出比例中介或 bootstrap P 值。

数值上使用 stats::lm.fit 的 QR 求解；秩亏、暴露单臂、几乎零残差方差和极度病态设计明确阻断。bootstrap 不处理未测混杂、测量误差、选择偏倚或错误模型。独立验证使用 numpy least squares + 另写标准化矩阵和 statsmodels OLS，不把另一个优化器作为生产回退。

## 二分类匹配后推断

冻结 v0.7 的完整案例倾向评分、共同支持和 1:1 无放回匹配保持原样。为了不复制匹配器，调用其连续结局旧接口时只传内部恒定占位量，丢弃该旧效应；真实结局只在匹配对形成后按精确字符 ID 合并。所有设计诊断沿用原 owner。

令 D_j=Y_tj−Y_cj，m 为匹配对数，风险差为 mean(D)，方差为 sample_var(D)/m，区间采用 t_(m−1) 临界值。二元 D 的 t 区间是近似区间，未截断到[-1,1]，少量对/稀少不一致对可能不可靠；零差值方差时不伪造区间或显著性。因果 ATT 解释限于保留匹配处理组，并要求无未测混杂、正值性、一致性和匹配后可交换性。

b=处理有事件/对照无事件的对数，c=相反对数。条件于 b+c，b 的零假设概率为1/2，使用 stats::binom.test 两侧精确检验。条件配对 OR=b/c，区间由不一致方向概率的 Clopper–Pearson 区间经 p/(1−p) 转换。[R 精确二项文档](https://stat.ethz.ch/R-manual/R-patched/library/stats/html/binom.test.html)说明该区间构造。b+c=0无信息；c=0的无穷估计/上端用 null 和 positive_infinity 标记；b=0的0边界保留。此 OR 与边际 OR、RR、ATT 风险差不同。

二分类要求所有纳入主体在共同指定的结局时点有成熟标签；未完成随访不能当无事件。必须明确二元端点定义，例如终点前死亡的处理属于研究端点定义，不能由程序推断。

## 生存匹配后推断

每人一行，基线治疗固定、随访>0、首次目标事件0/1，事件之外只有右删失。延迟入组、竞争/复发事件、时变治疗/协变量、权重及额外簇结构拒绝。`Surv(time,event) ~ A` 使用匹配总体的合并风险集，Efron ties、timefix=false，`cluster=pair, robust=true`。模型没有对 pair 分层，不能把结果称为匹配对内条件 HR。

事件 t 前风险集 R(t)={i:T_i≥t}，同一时刻先计事件、再退出删失者。预定时点风险表记录 at_risk、events_before、censors_before 和实际臂分母；图上的连接线仅连接计数，不估计生存率。不存在外推的基线风险或绝对风险。

方差来自按匹配对求和的 score residual sandwich，报告 SE(log-HR)，在 log-HR 上用正态临界值，再指数变换区间。它估计匹配人群的工作边际比例风险参数；HR不可折叠，不能直接叫 ATT 风险或存活获益。识别和推断要求独立匹配对、该风险集下的比例风险及条件于治疗的独立右删失；这些条件未被验证。少于30对标记小簇警告，没有声称有限样本可靠。无事件、某治疗臂无事件、provider警告和不可用方差明确保留原因。其他单调似然问题仅做数值防护，不宣称完整分离检测。

[survival::coxph 原生文档](https://stat.ethz.ch/R-manual/R-devel/library/survival/html/coxph.html)说明 cluster 方差、ties及无限系数问题；本机验收固定的是已安装 survival 3.8.6，而非网页最新版本。独立测试直接实现 Efron partial-score/root、风险集信息量及按对聚类的 score residual 方差，在有/无并列事件和实际匹配样例上比较。参考实现仅用于测试，不是生产 fallback。

## 共同限制

PSM 推断条件于形成的匹配对，不计倾向评分估计、共同支持剔除、匹配选择的不确定性，也不做普通重匹配 bootstrap。平衡/SMD、运行成功和名义 CI 都不能证明研究可发表。所有数据为小型合成数据，科学审阅 pending、出口 local_only，未做真实患者数据或临床覆盖率验证。
