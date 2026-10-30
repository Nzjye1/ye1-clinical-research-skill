# 独立 TreeSHAP 解释扩展

本目录在 `nonlinear_prediction` 已交预测模块之外提供新的 explain-only 方法。树训练、内层调参、冻结预处理、sigmoid 校准和预测数值 owner 仍为原模块；ROC、校准、DCA 仍归公共评价 owner。本扩展不把置换重要性、PDP 或树分裂重要性标作 SHAP。

拟注册 ID：`explanation.binary.random_forest.tree_shap`、`explanation.binary.hist_gradient_boosting.tree_shap`。入口 `tree_shap.interface.analyze(request)`，投影 `tree_shap.projection.project(response, destination)`；需把模块根目录加入 Python 搜索路径，以包方式导入。`run.py` 提供相同接口的独立本地私有 CLI。公共注册尚由集成 owner 执行。

## 依赖与安装边界

经用户明确授权，从官方 PyPI 的固定 wheel 安装到本目录 `_vendor/`：SHAP 0.54.1、slicer 0.0.8、tqdm 4.70.1。`requirements.txt` 锁定 SHA256，`install-report.json` 保存真实 wheel 地址和哈希。安装使用 `--no-deps --only-binary=:all: --require-hashes --target`；复用现有 Windows Python 3.12.15、sklearn 1.9.1、NumPy 2.5.4、SciPy 1.18.1、pandas 2.3.3、packaging 26.3、cloudpickle 3.1.2、colorama 0.4.6。未安装 GPU、Numba、llvmlite；未升级共享依赖。共享环境不把本目录加入全局路径。

首次沙箱网络访问返回 WinError 10013，确认目标目录和安装回执均未产生；获准使用网络权限后安装成功。最初命令行 smoke 探针有一次 shell 引号错误，随后独立 `smoke.py` 在原生 RF/HGB 上实际运行成功。这些并不等于所有数值输入已验证。

## 背景必须来自真实训练制品

训练完成后由可信公共 owner 调用：

```python
from tree_shap.background import capture_training_background
background = capture_training_background(
    original_training_request, original_training_response,
    trusted_run_hashes={
        "request_sha256": trusted_saved_request_hash,
        "response_sha256": trusted_saved_response_hash,
    },
    size=100, seed=1729,
)
```

上述期望哈希必须来自公共 owner 保存的真实运行，不能从用户提交的解释请求自证。此函数校验训练请求/响应、冻结模型与版本、私有逐人分区/预测记录；只重放共用确定性分区规划器，不拟合任何模型或预处理。它从真实 `model_fit` 行均匀无放回抽样，将背景行、原始行位置、训练请求/响应与 canonical rows 哈希、模型哈希、分区身份摘要保存在独立 `LOCAL_PRIVATE_TRAINING_BACKGROUND` 制品中。背景不含校准、留出、外部验证患者；不静默压缩超过 100 行的背景。

仅有旧冻结 JSON 时明确无法导出背景。必须保有原始可信训练请求和响应，或经训练 owner 另行训练并捕获；不能从节点计数、外部样本、当前解释队列猜测训练背景。已有冻结 JSON 无训练路径计数，本扩展只提供显式背景 `interventional`。哈希和分区检查提供一致性验证，不声称可以认证恶意伪造的调用者。

解释请求沿用五键共享包络，operation 固定 `explain`，bindings 绑定预测模型。payload 复用原来的 `rows/spec/data_contract/frozen_model_json/application_scope`，移除 `explain_with_outcomes`，新增 `background_artifact_json/background_sha256/feature_perturbation`，后者固定 `interventional`。公共 owner 还须把背景哈希和来源纳入自己的可信执行上下文。主体、记录、字段角色、单位、时间、缺失、无权重和冻结身份/分组重叠检查继续复用预测模块。解释不需要结局，也不计算评价指标。

## 已实测的官方阈值精度问题及等价表示

官方 SHAP 0.54.1 的 interventional C++ `Node` 将阈值和值保存为 float32。冻结 RF/HGB 的阈值是 float64；离散值/阈值附近可能改变分支。真实测试复现了 RF 加和误差约 0.053，另有原生 RF 加和通过但逐列归因相互抵消的误差。因此不能将原生 TreeExplainer 可导入或加和通过视为充分数值验证。

本适配器仅改变交给 SHAP 的树坐标表示，保持原冻结模型原样：对第 j 列的全部冻结阈值排序去重，定义 `r_j(x)=count(t < x)`。原分支 `x <= T_j[k]` 与 `r_j(x) <= k` 对所有输入严格等价。整数阈值限制为小于 2^24，可被 float32 精确表示；RF 输入先按冻结预测器规则转为 float32，HGB 保持 float64。该逐列变换与 interventional 特征替换交换，所以每个 coalition 的落叶和预测均保持相同。运行时检查所有解释/背景列值在每个分支上的等价性，并检查 SHAP 树预测与原冻结预测最大误差 <=1e-12。

SHAP 包、编译扩展和官方加和检查均未改写/关闭，`approximate=False`。独立测试用原浮点阈值的标量树遍历和全部 coalition 枚举作参考，不使用此整数表示或 SHAP 计算参考。该处理是版本固定的适配，需要随官方版本变化重验；不能推广为任意模型兼容保证。

## 输出尺度与分类变量

RF 基础分数是正事件未校准概率；HGB 基础分数是未校准 log-odds。若冻结 sigmoid 为 `q=expit(-a*s-b)`，校准 log-odds 的基线是 `-a*E[s]-b`，各 SHAP 贡献是 `-a*phi`，来自 Shapley 对仿射变换的线性性。对全部贡献相加再取 sigmoid 可重建 q；逐项取 sigmoid 不能得到概率贡献。本扩展不提供校准后概率尺度 Shapley。

多水平类别按冻结独热编码列解释。变量汇总是同一变量编码列贡献先求和，再计算绝对值均值，明确标记 `sum_of_encoded_column_SHAP_not_group_Shapley`。interventional 编码列组合可能离开真实类别支持集，也可能打破相关性；这不是条件 SHAP、分组 Shapley 或因果效应。常量/未参与树的编码列贡献为零。

public_record 只有聚合归因、分母、尺度和限制；逐人预测、编码值和贡献仅 private_record。投影输出两个聚合 CSV、一张聚合条形图，以及只在 `private/` 的个体贡献分布和单行贡献图。投影不重新拟合或计算 SHAP。图不包含公开患者标签。

## 验收和适用边界

运行 `tests.py`，每轮新建小证据目录并保留历史失败；最终回执由 `handoff.json` 指向。四组合为 RF/HGB × 无校准/sigmoid，合成数据 400 行、4 个编码特征、24 行训练背景、8 行解释；另测 120 行背景、冻结重载、留出、分类汇总、缺失/未知类别、模型/来源/分区/hash、非有限值与字段边界、正负/零校准系数、RF float32 阈值附近输入。穷举参考限制 <=6 个编码列，数值阈值预先设为 1e-6；这不是临床有效性、总体代表性、因果性或推断置信度证明。

独立解释资源边界：背景至少 10 行，默认最多 200 行、可配置上限 2000 行；解释默认最多 1000 行、可配置上限 5000 行；编码列最多 80。背景捕获仍默认 100 行，不会因应用预算调高而自动扩大。继承预测模块的树数量/深度/叶数限制，并检查共享工作量预算；这些不是耗时保证。参见仓库 `docs/CLINICAL-RESOURCE-BUDGETS.md`。不支持任意模型、多分类、生存、isotonic 校准、交互 SHAP、训练路径依赖或人口加权背景。旧预测模块自身 `explain` 仍是 PDP/置换方法，不由本扩展静默替换。

生产基线唯一获额外授权的修改是 `interface.py` 的 P1 失败分母传播；证据在 `../evidence/denominator-fix/`。该更改导致预测 provider_version 变化，旧版本冻结包继续被版本守卫拒绝，不能静默重签。

官方参考：[TreeExplainer](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html)、[0.54.1 源码](https://github.com/shap/shap/blob/v0.54.1/shap/explainers/_tree.py)、[C++ interventional 实现](https://github.com/shap/shap/blob/v0.54.1/shap/cext/tree_shap.h)、[依赖声明](https://github.com/shap/shap/blob/v0.54.1/pyproject.toml)。
