# 本地输入与单项调用（供 Agent）

客户用自然语言提出问题、提供本地文件路径与数据字典。客户不需要填写 JSON、选择 schema 或修代码。Agent 只读需求、字典、方法元数据及允许查看的汇总；真实患者行、标识、模型中的训练背景、private 任务和日志不得读入模型或粘贴到对话。

固定公开教学案例走独立的 [public-fixture 验收入口](PUBLIC-FIXTURES.md)。普通分析按实际数据来源和用途填写任务参数。

## 正常顺序

1. 先运行主 Skill 的 `scripts/toolkit.py list`。对选中的稳定 ID 运行 `describe`、`schema`、`doctor --method <ID>`。schema 是原 owner 的科学合同，schema 成功不代表分析成功。缺依赖时根据安装教程说明实际来源和本项目安装位置，并按宿主权限规则处理；不能关闭校验或借开发目录。
2. 先明确数据来源、问题、观察单位、独立性/重复测量、变量单位与编码、结局/事件/删失、时间零点与可用时间、缺失规则。预测还要明确样本划分、训练内调参、时间成熟、身份空间和冻结模型；因果/中介还要明确处理前协变量及时间顺序。缺项集中澄清，不猜表头、事件码、默认模型或显著性目标。
3. 根据该方法 schema 和本次已经明确的信息，在客户项目内写元数据草稿。草稿不能包含由 Agent 读取的真实数据行。核心方法的 CSV 引用由原解析器读取；模块方法的行通过下述本地映射标记填入。所有文件均须在该项目内，拒绝链接/目录联接；原文件保持不变。
4. 运行 `scripts/prepare_task.py --draft <本地草稿>`。合成数据标为 `synthetic / engineering_test`，真实研究数据标为 `real / research_analysis`。准备过程非交互，不要求终端输入、上传史或固定确认句。文件和输出须在指定项目内；已有严格项目限制继续生效。
5. 准备器只回固定状态和私有任务路径。真实数据时不要打开该任务文件；它可能包含规范化患者行。用 `scripts/toolkit.py run --method <ID> --task <返回路径>` 调用。单项 Skill 和总入口使用同一入口与数值底座，组合时只执行客户问题确有必要的步骤，各自使用新目录，冻结应用不重训。
6. 检查实际 `result.json` 的状态、方法、分母、缺失和诊断，以及 CSV、PNG 和 `报告.md`。真实结果的本地查看/对话回传遵守原产物授权；本次分析同意不等于外发图表授权。只返回允许的状态、路径或经明确授权的汇总，不能以退出码 0 代替表图和科学检查。

## 草稿外壳

```json
{
  "schema_version": "ye1-toolkit-draft@1.0",
  "method_id": "原目录中的稳定方法ID",
  "data_origin": "real",
  "task_purpose": "research_analysis",
  "project_root": "客户本地项目绝对路径",
  "local_tables": {},
  "task": {}
}
```

`task` 按该方法当前 schema 准备：核心用 `clinical-study-input@1.0`，模块用 `clinical-module-task@1.1`，基础检验用 `ye1-compat-study@1.0`。`task` 的方法、来源、用途、项目必须与草稿一致。不要把旧示例的数据库、变量、单位、事件码、时钟、假设或 synthetic 许可直接套到客户文件。准备器生成本地任务与源文件字节绑定；不生成用户确认记录。

核心方法保留原 `variables/views/analysis` 等结构。每个 `view.local_ref` 是实际 CSV 路径，`column_map` 是“ASCII 规范字段名 → 原 CSV 实际表头”。`view.content_hash` 以及对应 `sources[].source_fingerprint` 可用 `{"$file_sha256":"项目内实际文件"}`。字段清单、视图、结局、分析配置应相互一致。准备器调用原 seal，不改变数值方法。

## 中文表头、类型和缺失

原列名可含中文、混合大小写、空格；`name` 保持 ASCII 字母开头的唯一机器字段。`column` 精确匹配实际表头。源标签不作去空格、大小写折叠、Unicode 归一化或自动重命名。重复原表头、规范名重复、两规范名映射同一源列、映射与排除重叠、缺列或未声明列均拒绝。请核对字典，不能静默保留第一列或修改原 CSV。

模块的 `local_tables` 示例（仅元数据）：

```json
{
  "input": {
    "path": "项目内原文件.csv",
    "format": "csv",
    "fields": [
      {"name":"subject","column":"受试者编号","type":"id","missing_codes":[""]},
      {"name":"age","column":"年龄（岁）","type":"number","missing_codes":["","NA"]}
    ],
    "unselected_columns": ["本次不使用的实际列名"]
  }
}
```

支持 UTF-8 / UTF-8 BOM CSV，以及显式 `csv_gzip`。类型仅 `number/integer/id/string/category`，缺失码必须明确；不把未知字符串改数字或隐式填补。原 owner 继续核对类别、单位、缺失和科学设计。

在模块原 schema 规定的 `payload.rows` 或 `payload.data` 放 `{"$csv_rows":"input"}`。若原 owner 规定嵌套记录，可在 table 加 `record`，逐字段声明：

```json
{"record":{"subject_id":{"$field":"subject"},"covariates":[{"$field":"age"}],"outcome":null}}
```

这只重排明确的字段，不计算新变量、不猜缺失、不选样本。`{"$csv_values":{"table":"input","field":"subject","where":{"partition":"train"}}}` 可把明确分区中的全部 ID 填入原 Cox 训练/留出 ID 清单；分区由用户计划预先给定，不根据结局自动选人，ID 不回显。

## 冻结模型与解释

`{"$file_text":"模型.json"}` 原样填入原 owner 要求的模型 JSON 文本；`$file_json` 仅用于要求 JSON 对象的字段，`$file_sha256` 给原始字节哈希。`{"$json_value":{"path":"背景.json","keys":["sha256"]}}` 只读取明确的元数据位置，不改变模型或解释背景。不得用 pickle 或修改旧模型来通过校验。

普通预测的训练、评估、推断，聚类的 train/assign，增长/轨迹的 train/predict，解释器的 fit_explainer/explain，均按登记操作调用。外部 ID 必须与训练/开发对象不重叠，字段、单位、编码、时序、类别、运行版本和原冻结定义必须一致。某些解释只支持冻结训练观测域内输入；域外拒绝是边界，不能自动裁剪。

树 SHAP 必须使用成功训练完成后，由原完成钩子保存并登记的 `private/training-background.json`。不能由客户/Agent 任选四行充当“已验证背景”，也不能关闭背景注册检查。源模型及背景文本通过本地标记读取；真实数据时不得把其中训练行读给模型。原树模型的解释配置也属于冻结定义，不能在应用时随意改动。

## 旧基础检验与样本量

5 个 `compat.test.*` 接口共享原 `stats_worker.R`。必须声明独立单位、研究问题、总体、estimand 和假设复核；两组检验显式给分组顺序。配对 t 仅支持每对一行的两数值列，必须明确配对含义和独立对。类别编码、唯一单位和 complete-case 分母被检查。Wilcoxon 是连续性校正的渐近秩和检验，不自动等于中位数检验；Fisher 只支持 2×2；卡方期望频数不足时拒绝，不自动换检验。

4 个 `compat.sample_size.*` 用 `toolkit.py plan --method <ID> --assumptions <本地假设文件> --output <新目录>`。只含预期参数、精度/效能、设计、损耗和假设来源，不接患者行，不存在 real/synthetic 重标记问题。先查看该方法 schema，客户不知道假设时先解释并澄清；禁止用本次观察 P 值补“预期效应”。这些是限定设计公式，不是通用样本量工具箱。

## 失败与证据

字段/映射、无效类型、预算、时序、冻结定义或科学合同不满足时，应停止对应计算并报告原因；不能静默截取前 N 行、去重、删异常、换方法、重新训练或修改锁文件。原 CSV、映射账本和失败日志保留本地。模块规范化快照绑定原文件 SHA；在原准入之后再次核对，源文件变更须重新准备。

源/解码字节和行数按原有限资源合同检查；规范化私有任务另有 2 MB 上限。这是本版传输限制，不是统计样本量充分性结论。更大输入应明确报失败并交支持，不能减少数据假装完成。`ANALYSIS_COMPUTED_ARTIFACT_REVIEW_REQUIRED` 表示计算或部分计算已经留存，但展示/部分产物仍需处理；不要当成完整交付。

任何报错由 Agent/支持保留日志、复现和修复，客户不需要修改代码、依赖锁、授权文件或科学合同。图表缺失、分母不一致、科学复核未完成应如实记录。Mac、WorkBuddy、全新物理电脑、真实患者端到端、新 Codex GUI 自动发现均只按实际证据表述。
