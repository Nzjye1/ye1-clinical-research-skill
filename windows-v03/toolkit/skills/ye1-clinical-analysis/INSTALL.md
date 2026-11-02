# Windows安装与首次使用

版本 0.3.2-windows-local-noninteractive1。适用于 Windows x64 与 Codex。请以 v0.3.2 发布页提供的包名及 SHA256 清单核验下载文件；Python 和 R 基础程序需要另行准备。安装 Skill 和依赖会写入所选研究项目。

## 1. 准备基础程序与研究目录

使用官方 Python **3.14.5 x64**（https://www.python.org/downloads/release/python-3145/）和 R **4.6.1 x64**（https://cran.r-project.org/bin/windows/base/old/4.6.1/）。严格按本版已验版本，不自动升级。R需包含推荐库 Matrix 1.7.5、survival 3.8.6、nlme 3.1.169；自检会核版本及实际加载路径。保留一个新研究目录，例如 `D:\我的研究`。其他版本尚未适配；缺基础程序时请支持人员协助安装，不改全局环境凑通过。

## 2. 解压与核包

将ZIP解压到独立文件夹。用交接的SHA256核对下载包（PowerShell `Get-FileHash -Algorithm SHA256 <ZIP路径>`）。不要覆盖旧包或旧研究。`toolkit-manifest.json`还会核所有Skill文件；缺文件或字节不符时停止并重新获取原包。

在Codex中打开准备的研究目录，将解压目录告诉它：

> 请按这套工具箱INSTALL.md安装到当前项目，先只装base，使用我已有的Python 3.14.5和R 4.6.1。先说明安装位置和依赖，再执行自检。

安装助手或支持人员可在解压的toolkit目录执行下列PowerShell命令。替换路径，Python使用明确的3.14.5程序路径，不能误用其他版本：

```powershell
& "C:\你的路径\python.exe" -I -B .\setup_windows.py --project "D:\我的研究" --rscript "C:\你的路径\R-4.6.1\bin\Rscript.exe"
```

这是预检，只显示安装计划；核对后在同一命令末尾加 `--install` 执行。将复制48个Skill目录到研究目录的 `.agents/skills`，依赖仅写其中主Skill的 `.runtime`；不改Codex全局设置、代理、系统库或原数据。不覆盖同名Skill，其他已有Skill保留。

Python依赖从官方 `files.pythonhosted.org` 下载，精确版本/SHA锁定；R二进制及匹配源码已随包。需要网络下载但不要求内部账号。离线已有官方wheel可加 `--wheelhouse "D:\官方wheel缓存"`，仍强制核hash，不使用别的项目已安装环境。下载/缺库/版本失败时保留 install-logs，排除前提后重跑同一依赖安装器，不修改统计代码。

## 3. 自检与按需加装

在该研究项目使用 `$ye1-clinical-analysis`，先要求“自检基线分析”。运行入口为 `.agents/skills/ye1-clinical-analysis/scripts/toolkit.py doctor --method baseline.table1`。项目下应出现主入口与单项Skill；若当前会话未刷新，重新打开该研究项目/新会话再试。目录和元数据已验证，实际Codex GUI发现本轮未测；无法发现时把SKILL.md路径交支持核对。

base支持基线、OLS/Logistic计划、KM/Cox及兼容检验/规划等登记路径。高级方法缺组时返回 `DEPENDENCY_GROUP_NOT_INSTALLED` 并列所需组，不阻塞基线。Agent应按所选方法用主Skill `scripts/install_windows.py --rscript <Rscript> --method <方法ID>` 预检，再经用户允许加 `--install`；要全部安装可加 `--all`。不要第二次运行setup覆盖Skill。8组为base/ml/plot/penalized/formal_latent/shap/growth/matching，具体由方法自动解析。

安装中断留下本地日志与部分目录；同一主Skill依赖安装器可继续其自有安装。源码更新/移动安装后因路径和字节绑定需要在新项目重新安装；不手改profile、授权或hash。原项目/冻结模型保留给支持评估兼容，不能静默重训。

若Skill已复制完成、依赖安装中断，在研究项目内运行以下命令恢复（替换基础程序路径）；不要重新运行setup覆盖Skill，也不要删除`.runtime`或历史日志：

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 .agents/skills/ye1-clinical-analysis/scripts/install_windows.py --rscript '<R-4.6.1/bin/Rscript.exe>' --groups base --install
```

使用离线官方wheel时仍加原来的`--wheelhouse`。安装器会核对自有venv并检测pip；缺pip时使用Python自带的`ensurepip`离线补齐，再继续原hash锁定依赖安装。每次尝试在新的`install-logs/<时间戳>/`保留`python-venv-create.log`（创建时）、`python-venv-check.log`和`python-pip-check.log`；恢复时另有`python-ensurepip.log`及`python-pip-recheck.log`。`LOCAL_VENV_CREATION_FAILED`、`LOCAL_VENV_INVALID`或`LOCAL_PIP_BOOTSTRAP_FAILED`时保留这些日志，交支持检查基础程序或执行权限，不改全局设置。

## 4. 用普通语言开始

> 我的CSV在本地。请先核对研究设计和变量字典，做两组基线描述，再分析一个二分类结局。不要把患者行读到聊天；缺定义先问我。

也可用 `$ye1-association-logistic` 等单项入口。给出文件路径、列名/单位/编码、研究单位、分组顺序/参考组、结局定义、发生/可知时间与缺失约定；生存再给时间起点、单位、事件码和删失含义。中文/中英混合表头及中文路径支持，逐字映射不改原CSV。重复表头/映射碰撞/不存在列要纠正数据字典，不能静默猜测。输入CSV需UTF-8（可BOM），gzip CSV亦按登记边界读取。

Agent只写元数据草稿，调用prepare_task在本地读取与规范。合成工程练习须如实标synthetic/engineering_test；真实研究须如实标real/research_analysis。根据指定的本地文件和任务参数非交互准备，不需要旧版交互终端确认。无需内部凭据。项目选择与研究授权不等于允许行数据进入模型或允许导出。真实研究结果仍需研究者复核；保密要求若不允许宿主接触原始行，应暂停当前宿主处理，不伪造隔离证明。

## 5. 检查结果与恢复

每次使用新输出目录。看样本流、完整案例、结局/事件码、估计量尺度、置信区间、图和说明是否与问题一致。无显著性不是失败。输出冲突时保留旧结果改用新目录；不得自动删结果。冻结模型定义/身份/版本不符应澄清、补齐原模型来源或交支持，不能换模型求成功。

如果Codex的执行边界阻止本地R探针，自检可能返回 RUNTIME_PROBE_FAILED 并留下私有诊断。由Agent先核实是否属于执行权限限制，再按宿主规则申请仅针对本项目命令的本地运行；获准才重试，拒绝或结果不确定则停下并交支持。不改变系统安全设置、不假造自检通过，也不要求用户修代码。

错误时把固定reason_code、版本和日志路径交支持；日志、private任务、模型和逐行预测先留本地，由有权限的人检查脱敏。不要直接上传全部目录。缺结局/时间/单位不编造；资源超限不抽样截断；不支持设计明确停止。安装版不是通用统计软件包，也不承诺每种参数、实际临床科学结论或真实患者流程已验证。

## 6. 公开案例

固定 PBC 示例的输入与运行方法见[公开案例说明](references/PUBLIC-FIXTURES.md)。示例用于理解和验证工具的适用行为，真实研究仍需核对研究设计与结果。
