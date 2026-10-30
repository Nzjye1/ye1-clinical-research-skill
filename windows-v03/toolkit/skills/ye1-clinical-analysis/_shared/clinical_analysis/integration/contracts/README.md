# 模块接口 1.0：供三个独立模块立即使用

这是现有 clinanalysis 入口与独立数值模块之间的私有接口，不是第二套公共引擎。父会话派发的三个模块及集成方 Cox 模块使用同一协议。公共 StudySpec/result 仍由唯一集成负责人适配、注册和生成。

请求固定五键：api_version=`clinical-module-request@1.0`、method_id、operation、payload、bindings。bindings 固定 input_sha256/plan_sha256/code_sha256/runtime_sha256/model_sha256；训练时 model_sha256 可为 null，冻结推理/评价/解释须由方法契约要求有效绑定。模块入口为 analyze(request)，Python 返回 dict，R 返回 list。

返回固定六键：api_version=`clinical-module-response@1.0`、ok、reason_code、diagnostics、public_record、private_record。成功 reason_code=null；拒绝 ok=false、reason_code 为稳定大写机器代码、public_record=null。有效但部分指标不可识别时可 ok=true，并在方法自有 public_record 中逐项标记 unavailable/原因，不能伪造数值。

模块必须提供 payload、diagnostics、public_record、private_record 四份方法自有 JSON Schema。通用包络的 object 类型本身不是有效载荷验证：没有注册方法和四份 schema 必须拒绝。schema 只允许同文档内部 $ref，不联网解析。所有请求/结果禁止 NaN/Inf、未知公共键；payload 和各记录的未知字段由自有闭合 schema/声明字段表拒绝，不能放开 arbitrary extras。

payload 的具体字段由模块决定，但必须显式声明行粒度（患者、患者-访视等）、记录/患者/组键、字段类型/角色/单位、时间起点及测量/可用时间、事件编码、缺失与权重策略。时间/权重不适用也要明确；长表单独契约，不放松旧单患者约束。输入 schema 与运行时一致性守卫共同检查动态行字段。baseline 描述分组的 outcome_summary/stratification_label 与预测 feature/covariate 必须区分。

public_record 只放可公开聚合结果及语义；患者行/ID、配对、逐人预测/贡献、训练身份及完整模型进入 private_record，由集成入口写 local private/。模块可提供投影/表图/说明函数与独立参考；投影只能消费已验证记录，不再次拟合或改数值。最终公共版本、来源、分母/尺度和 result_id 由共用入口统一注入。每个指标都需真实分子/分母或明示非比率定义，不能默认总人数。

模块根目录交付 integration-request.json，符合 integration-request.schema.json。entrypoint/projection_entrypoint 和所有 schema、provider_files、evidence 路径均相对该模块根目录，禁止越界路径；由集成负责人验证、哈希并接入。数值 owner 必须唯一且版本固定，不失败换算法。方法 ID 可提出新 ID，集成方检查冲突后注册；现有方法不被覆盖。

开发期保留现有失败案例并完成模块独立参考、双合成适配器、表图及说明检查和受影响回归。不会为每个模块跑全531；最终统一冻结节点仍必须跑完整套件与指定真实数据端到端验证。已实现的 module_contract.py 只负责契约验证，不执行方法或选择算法。
# 当前实际校验能力与绑定语义（2026-10-24）

公共验证已移除未安装的 `jsonschema` 导入，复用 `core/python/clinical_methods/contracts.py::validate_schema`。这不是完整 Draft 2020-12 验证器。注册前逐节点拒绝未实现关键字，包含未被当前数据命中的 union 分支；本地/远程 `$ref`、`$dynamicRef`、`oneOf`、`not`、`format`、`patternProperties`、`unevaluatedProperties` 均不支持且拒绝，不会联网解析或静默忽略。

当前受限方言支持 type、const、enum、properties、required、additionalProperties（false 或有类型的变量键映射）、items、min/maxItems、min/maxLength、pattern、minimum/maximum、anyOf，以及本次有针对性测试的 allOf、if/then/else、uniqueItems。支持 title/description/$comment/$schema/$id 注释；`$schema` 标签不构成完整标准符合性声明。原有校验器的严格数值/布尔区分保留。

四份模块 owned schema 的根必须是闭合对象或显式闭合分支；递归对象不能使用未限定 additionalProperties。合法变量键映射必须有其值 schema，列名/键集合还须由模块与声明字段表核对。公共信封中的 payload、diagnostics、record 对象仅是第一层，必须再通过已注册的 owned schema 和语义检查。

五个 binding 由公共入口从可信执行上下文生成并比对：input_sha256 是提交任务的原始字节；plan_sha256 是移除输出目录后的完整计划；code_sha256 是锁定模块源/schema/manifest 快照；runtime_sha256 是当前核心运行时锁原文；model_sha256 使用相应 provider 的已验证模型标识。模型原文件字节 hash 另单列，不将 canonical bundle checksum 冒充原文件 hash。模块内部需要 rows/数值 owner/运行时摘要时，必须独立命名，不能重用这五字段表达另一套含义。

新增公共任务 `clinical-module-task@1.0` 当前仅支持明确声明的 `synthetic_inline_normalized` 私有载荷；不声称已验证真实数据库抽取、join 或临床来源。最终真实数据端到端仍须得到明确本地源、队列和字段范围后接入。
