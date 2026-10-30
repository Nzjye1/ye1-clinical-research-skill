# 二分类非线性预测完整模块

交付目录仅为 `modules/nonlinear_prediction`。未改冻结 v0.10、integration、其他模块、旧 Skill 或运行环境。未安装依赖，未使用 WSL，未读取真实数据库，未上传、发布或打包累积候选。

当前可运行：规范化输入 → 防泄漏分区 → 两种树模型之一 → 训练内调参 → 可选独立 sigmoid 校准 → JSON 冻结/重载 → 外部评价或无标签推理 → 公共指标表、ROC/校准/DCA → 置换重要性/PDP → 方法结果说明。公共入口已注册，最终整合验收另见仓库分析更新说明；本目录输出标识为 `nonlinear-module-preview/1.0.0`，不能当作最终统一 schema 验收。

## 入口与文件

- `run_module.py`：单命令完整运行，输出目录必须不存在。
- `interface.analyze(request)`：对齐 `clinical-module-request@1.0` 的主集成门面，返回固定六键响应，训练/评价/推理/解释分开。
- `integration-request.json` 与 `schemas/`：机器可读注册请求及 payload、diagnostics、public_record、private_record 四份封闭 schema。
- `adapter.execute(request)` / `adapter.py REQUEST PRIVATE_RESPONSE`：与既有 prediction_bridge 一致的较低层私有 provider envelope；`run_module.py` 是这一层的完整工程演示。
- `contracts.SPEC` / `contract_fragment()`：交给集成 owner 的契约片段，不自动写公共 schema。
- `provider.py`：模型、调参和冻结预测；公共评价直接调用 `clinical_methods.prediction._metrics`。
- `projection.R`：调用冻结 `clinical_prediction_common.R` 的指标表/三张评价图；附加模型解释表图与说明。
- `tests/run_validation.py`：新建小证据目录，运行模块与四项受影响回归，核对冻结生产文件不变。

Windows 完整合成演示（在任意目录运行；下列输出目录必须尚不存在）：

```powershell
# 从仓库根运行，输出路径必须是模块内尚不存在的新目录
& $Python -B -X utf8 _shared/clinical_analysis/modules/nonlinear_prediction/run_module.py `
  --demo --algorithm random_forest `
  --output _shared/clinical_analysis/modules/nonlinear_prediction/evidence/demo-new
```

将 `--demo --algorithm ...` 换为 `--request LOCAL_REQUEST.json` 可执行已经规范化并受授权边界控制的 provider 请求。此私有数值入口不是实际患者数据准入接口。真实来源读取、授权、原始字节/视图绑定、单位转换与研究时点核验属于上游共用核心；本模块没有声称接入真实 MIMIC/eICU。

集成迁移时在导入前设置 `CLINICAL_CORE_ROOT` 指向唯一集成树。默认使用当前仓库相对的 `integration/core`。按脚本路径调用最直接；不要让同名 `contracts.py` 覆盖公共 `clinical_methods.contracts`。

## 固定接口

主集成接口为 `interface.analyze({api_version,method_id,operation,payload,bindings})`。共享包络文件从 `integration/contracts/` 只读加载，可用 `CLINICAL_MODULE_CONTRACTS` 指定目录。共用入口必须先把 input/plan/code/runtime 绑定与可信执行上下文比对；本门面不把调用者自报 hash 当作授权。模型 hash 在模块内另行比对，并验证模型自身与 provider 源码/版本/运行时锁。

payload 必须提供 rows、spec、data_contract、frozen_model_json、explain_with_outcomes、application_scope。data_contract 明示 subject 粒度、患者键/记录键/组键、身份命名空间、字段 dtype/role/unit/occurred_at/available_at、时间单位/起点/窗口/可分析时点、缺失 fit_scope、独立患者与无权重策略。行字段依据声明表逐项检查；未知列、未知选项、错误粒度、未来变量、未成熟标签和权重要求拒绝。

application_scope 在训练时为 `development`；后续为 `external` 或 `development_holdout`。留出应用严格限制为冻结模型中记录的原留出成员；训练/校准成员不得借此进入重评价。外部应用要求异于开发 cohort，且无主体或组重叠。

主接口 train/evaluate 不计算解释；explain 不计算或重选评价指标，允许带结局的置换+PDP，或无结局的 PDP。冻结 JSON 用字符串放在 `private_record.frozen_model_json`，便于 R 不重新序列化浮点而保留原 SHA；个体轨迹同样只在 private_record。公开聚合记录不注入最终来源、版本、result_id，由共用入口负责。可运行请求示例工厂见 `tests/test_interface.py::facade_request`。

方法 ID：`prediction.binary.random_forest`、`prediction.binary.hist_gradient_boosting`。operation：`train`、`evaluate`、`infer`。

请求键：`operation, method_id, rows, spec, model_bundle`，可加 `model_ref={local_ref,content_hash}` 和必须提供的非空 `canonical_semantics`。训练时模型为空；evaluate/infer 使用内联冻结 bundle 或有原字节 SHA-256 的本地 JSON。上游应使用公共 canonical semantics 并保留一致身份命名空间，不能把重新命名 ID 当成外部独立性的证据。

spec 沿用公共二分类 id/outcome/event/non_event、预测时点/窗口、feature 定义、预声明分类水平、split、missing、bootstrap、阈值配置。特有字段：

- `tuning.metric="log_loss"`；显式有序 candidates，1–8 个，2–5 折，按验证人数加权 log loss 最小选择，平分选首个。方法族由调用者预定，未做跨算法择优。
- RF 参数必须且仅为 n_estimators 20–300、max_depth 1–8、min_samples_leaf 5–100、max_features `sqrt/log2/1.0`。
- HGB 参数必须且仅为 max_iter 20–300、max_leaf_nodes 2–15、min_samples_leaf 5–100、learning_rate .01–.3、l2_regularization 0–100。内部 early stopping 关闭；类别经共用编码后作为数值列。
- `calibration={method:"sigmoid",fraction:.2–.4}`，或 `{method:"none",fraction:null}`。
- `explanation={permutation_repeats:0–20,pdp_features:[预声明字段]}`，最多 5 个 PDP 字段；SHAP 和其他未知键拒绝。
- `selection="none"`：候选变量预定；仅调参选择，不做单变量筛选、递归筛选或基于留出结果重选。

已覆盖随机、分组、时间拆分。每人一行、ID 不重复；分组训练/校准/留出及各 CV 折无组交叠。时间拆分保持同一预测时点在同区，并检查训练标签在验证开始前成熟。独立外部数据还拒绝开发主体或组重叠。改变实际来源身份编码可能逃过字面重叠检测，上游不能省略身份核验。

每次训练先隔离最终留出，再隔离校准集，之后只在 base-fit 部分调参。各折重拟合共同的中位数/众数与标准化/哑编码。最终基础模型只用 base-fit；sigmoid 只用校准集，之后不再重拟合基础模型。最终留出不参加预处理、参数选择、校准、阈值或 PDP 网格选择。CV 获胜分数是选择诊断，不能当无偏验证性能。

## 输出与解释

`private/` 保存完整请求、provider response、模型 JSON 和个体预测；model_fit/calibration/holdout 分区保存在私有轨迹。公共预览只保留聚合。所有产物保持 `TEST_ONLY / scientific_review=pending / local_only`，聚合不自动等于匿名或允许外发。

`result.json` 与 `tables/prediction_metrics.csv` 使用既有公共评价 owner，包含有明确定义的分母/比率；`nonlinear-extension.json` 保存调参、解释及附加表图的 manifest；`METHODS-AND-RESULTS.md` 给出实际计数、方法、评价和边界。完整训练输出 4 张 CSV 表、5 张 PNG 图；外部评价不产生调参表。推理没有性能指标。阻断输出保留可计算分母及固定原因，不编造模型。

ROC 使用既有 101 个预定概率阈值聚合网格，AUC 另按完整分数计算；校准图是聚合诊断；DCA 使用冻结阈值列表。DCA 阈值不等于操作阈值，`clinical_decision_threshold=null` 时不生成操作点指标。Bootstrap 仅沿用公共独立主体重采样；分组拆分不自动产生组稳健区间。

置换重要性是留出/外部评价上逐个原始变量打乱后的 log loss 增量，整个分类变量一起打乱；允许负值。重复标准差只表示置换随机波动。PDP 对预先指定字段做替换后平均预测，网格仅从 base-fit 的数值分位数或预声明类别冻结。两者可用于冻结后审计，不能据此重选本次模型；相关特征会影响解释。本预测owner不直接计算SHAP或列线图；独立注册的 `tree_shap/` 解释owner处理可信训练背景与局部归因。本接口不提供因果效应或临床使用批准。

JSON 包含树、转换和校准参数；训练由 sklearn 负责，安全重载预测遍历 JSON 数组，不执行 pickle。RF 推理保留 sklearn 的 float32 比较语义；HGB 保留 float64 阈值与已含学习率的叶贡献。每次冻结与 native estimator/校准器核对 `1e-12` 容差；图结构、版本、代码、运行时、定义及阈值漂移拒绝。JSON 摘要是完整性校验，不是身份签名。实现依赖已核验的 sklearn 内部导出布局，不支持未经复验的版本迁移。

树模型不存在本模块可宣称的回归系数 EPV；结果明确 epv/parameter_count=null，另报 transformed_feature_count。训练至少 40、每类至少 10、CV 验证每类至少 5、校准每类至少 10 等均为工程门槛，不是临床样本量充分性证明。稀疏/常数/全缺失特征、未知类别、未来变量、非法角色、非有限数据和超界参数明确拒绝，不偷偷更换算法。

## 依赖与验收

新增安装需求：**零**。实际使用 Windows Python 3.12.15，numpy 2.5.4、scipy 1.18.1、statsmodels 0.14.6、sklearn 1.9.1、pandas 2.3.3；线程限制使用已有 threadpoolctl。R 4.6.1 的 base graphics、jsonlite 2.0.0 与 digest 0.6.39 提供投影和哈希。TreeSHAP扩展另使用已隔离的官方SHAP依赖；本预测owner不使用skops/XGBoost/LightGBM/CatBoost；R ranger/randomForest/xgboost 不可加载；已有 rpart 未选作生产 owner。

最终模块验收：`evidence/validation-20261024T034446101855Z/receipt.json`，**35 PASS / 0 FAIL / 0 ERROR**，包括 6 项统一门面验收和 4 个只在内存运行的受影响旧 provider 回归；没有跑所有旧模块。测试期间模块源码稳定，153 个受核对冻结基线生产文件/锁/清单不变。机器摘要在 本地 `evidence/interface-validation.json`（不随Git提交）。

两套冻结合成 adapter 输入各 200 行在只读契约校验后产生完全一致结果；新生非线性合成数据 600 行，结局可分析 598，训练 448、base-fit 323、校准 125、最终留出 150。外部合成 180 行，评价 178 行；不代表真实独立临床外验。

独立 native sklearn 重建（训练转换由测试手算）与冻结概率最大差 2.22e-16；AUC/AP/Brier 的独立 base R 误差至多 2.22e-16，DCA 0；诊断校准系数差至多 1.78e-9，独立 Platt sigmoid 概率差至多 1.09e-7。预定容差分别为 1e-8 / 1e-5。测试覆盖训练/校准/留出扰动不泄漏、时间并列/标签成熟、分类、冻结/哈希/版本/语义/组重叠、原生参考、解释定义、CSV/分母/隐私出口、无标签推理、完整 CLI 外部应用和阻断，以及严格共享门面、冻结留出解释和实际 R 投影。

历史尝试保留：`validation-20261024T033410882794Z` 是最初 27 项通过；`validation-20261024T033626659739Z/private/test.log` 是加入严格依赖锁后发现 runtime 清单漏列 statsmodels 的失败轮次，另发现失败路径 receipt 生成未防守 setUp 失败。两项已修复，最终 29 项重跑通过；没有把失败轮次改写为通过。

未完成项限于集成 owner 的公共 schema/入口/注册/最终全量冻结验收；真实数据准入和科学临床审核、Mac、SHAP、其他算法、发布均未执行。无需安装依赖来完成当前限定模块。

集成环境事实：`integration/module_contract.py` 引用的 jsonschema 在已检查的冻结 Python 3.12 与系统 Python 3.14 都不可导入。本模块已复用冻结 core 的 validator，并显式保留共享包络 maxLength/allOf 语义检查，35 项实际通过。尚未运行依赖 jsonschema 的集成注册器；其运行时选择由 owner 解决，未安装包、未改该文件。依赖盘点见 `evidence/dependency-inventory.json`。

## 方法来源

- [sklearn ensemble 官方文档](https://scikit-learn.org/stable/modules/ensemble.html)：现有 RF/HGB owner 的定义与参数。
- [sklearn probability calibration](https://scikit-learn.org/stable/modules/calibration.html)：FrozenEstimator 校准要求模型拟合数据与校准数据分离；sigmoid 的适用假设不保证在所有人群成立。
- [sklearn permutation importance](https://scikit-learn.org/stable/modules/permutation_importance.html)：验证集置换可以描述冻结模型依赖，强相关特征可稀释各自重要性。
- [sklearn partial dependence](https://scikit-learn.org/stable/modules/partial_dependence.html)：平均替换预测是边际描述，相关变量可能产生数据中缺乏支持的组合。

上述在线文档于本轮核验；数值证据来自实际本地运行，不以文档代替测试。
