# 中介与匹配后结局完整模块

交付范围是可运行、可独立验证、可接入的本地合成工程模块。共享入口已接入，最终GitHub候选验收见仓库根分析更新说明。没有改冻结 v0.10、旧 Skill、其他模块、数据库或长期 library；没有安装依赖、上传或发布。

支持边界见 [SCOPE.md](SCOPE.md)，数学定义及参考见 [METHODS.md](METHODS.md)，公共接入清单见 [integration-request.json](integration-request.json)。

## 已实现的三条链

- 二元暴露→连续中介→连续结局：固定线性条件均值模型，预定 A×M 交互可开关；完整案例标准化，联合重拟合两模型的主体 bootstrap，逐次失败保留；ACME(0/1)、ADE(0/1)、总对比。
- 二分类 PSM：冻结匹配 owner 的 1:1、无放回、预定 caliper 设计；配对风险差与近似 t 区间、精确 McNemar 二项检验、配对条件 OR 的精确区间。
- 生存 PSM：同一冻结匹配设计；合并风险集的 treatment-only Cox，Efron ties，按匹配对聚类 sandwich；明确右删失、事件计数、风险集和 log-HR 方差；预定时点风险表。

自然效应解释需要未验证的识别假设；系数分解不自动等于因果证据。HR、条件 OR 和 ATT 风险差分别命名。缺失指标用 null/稳定原因，0/无穷边界明确保留，不悄悄改算法。

## 运行

使用已有 Windows Python 3.12 和 R 4.6.1。数值运行只需 R stats、survival、jsonlite、digest；Python 适配器只用标准库。独立测试另用已有 numpy、scipy、statsmodels。不用 WSL、mediation 或 lavaan。

```powershell
# 从仓库根运行，$Python 为已配置的固定隔离环境
& $Python -B -X utf8 skills/ye1-association/scripts/analysis_call.py describe mediation.linear.binary_exposure
& $Python -B -X utf8 skills/ye1-association/scripts/analysis_call.py schema causal.psm.att.binary
```

输出目录必须是本模块内尚不存在的新目录。A/B 两套原始列名和显式单位转换都已提供；源 CSV SHA256 不匹配、重复映射、二元编码转换或历史输出覆盖会拒绝。未知字段/不支持输入由闭合 schema 和 R 守卫拒绝。

## 供集成调用

在独立 R environment 中 source `R/module_api.R`，调用 `analyze(request)`。固定 request 包络：`api_version, method_id, operation, payload, bindings`；operation 只支持 `analyze`，没有 train/evaluate/explain 混用。payload 必须通过 `contracts/payload.schema.json` 和运行时一致性检查，声明单主体粒度、键、字段类型/角色/单位/时序、完整标签截止、缺失与无权重策略。

response 六键与共享接口一致。可计算但部分指标不可识别时，`ok=true`、包络 reason=null，public_record 内逐指标保留原因。拒绝时 `ok=false`、public_record=null。public_record 不注入公共版本/来源/result_id；private_record 是本地 R serialize v3 的 base64 字符串，里面才有患者映射、匹配对、bootstrap 样本索引和完整模型。

共用入口验证记录后可调用 `project(response, output_dir, context)`，context 提供 `result_id` 和 provenance `binding`；投影不再拟合。`mm_analyze(data,spec,baseline_root)` 是内部同一数值 owner 的便利接口，不是新公共注册机制。开发 CLI 只用于本模块工程样例。

`bindings` 的五个哈希字段由共享入口按其规范计算并验证；模块检查形状与 analyze 操作的 model_sha256=null，不把字符串形式哈希声称为来源真实性证明。冻结匹配源另在数值入口按固定 SHA256 核对。

## 结果及证据

每个运行有 `result.json`、汇总 CSV、PNG、中文 `REPORT.md` 和本地 `private/`。表图带同一结果 ID、来源绑定、方法、尺度、真实分母/事件口径及文件哈希。标准误尺度：中介/风险差为差值单位；Cox 为 log-HR；精确 OR 不伪造标准误。

本地 `evidence/latest.json` 指向模块运行时产生的验收目录（不随Git提交）。验收包括 R 边界测试、双适配端到端、独立 bootstrap 重拟合、精确二项参考、独立 Efron/聚类方差、输入误用、CSV/JSON 精度、隐私字段、API/投影和冻结连续 PSM 受影响回归。早期失败证据保留，最终使用源哈希绑定的最新通过记录。

共享模块使用冻结的受限严格schema校验器与R语义守卫；支持的schema关键字实际校验，未支持关键词显式拒绝，不声明完整Draft202012兼容。无需另装jsonschema。模块局部通过不代替最终整合验收。
