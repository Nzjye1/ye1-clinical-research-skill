# Ye1 临床分析：安装与使用

## 安装到你的 Agent

适用于 **Windows x64 或 Apple 芯片 Mac + Codex**。在 Codex 中打开你的研究项目，把下面整段发给 Agent：

```text
请先识别我的系统，从 GitHub 仓库 Nzjye1/ye1-clinical-research-skill 获取适用的 Ye1 临床分析 Skill 客户包，安装到我当前打开的研究项目。
请先阅读包内安装说明，检查并准备所需依赖，完成安装和基础自检。
完成后告诉我安装的版本、是否成功，以及如何开始使用。
```

[返回产品主页](../../README.md)

Apple 芯片 Mac 的联网和离线安装方式见 [Mac 安装说明](../../macos/INSTALL.md)。以下为 Windows 安装细节。

## 环境与手工安装细节

交付分为 Windows 客户 ZIP 和源码 ZIP。客户 ZIP 解压后从 `toolkit/START-HERE.md` 开始，完整操作说明位于 `toolkit/skills/ye1-clinical-analysis/INSTALL.md`。下载：[Windows 客户包](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.1/ye1-clinical-client-0.3.1-windows-local-noninteractive1-a4db8d94.zip) · [源码包](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.1/ye1-clinical-source-0.3.1-windows-local-noninteractive1-a4db8d94.zip) · [SHA256 校验清单](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.1/SHA256SUMS.txt)。正式版本见 [v0.3.1 发布页](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/tag/v0.3.1)；GitHub 自动生成的 Source code ZIP 是仓库快照。

### 环境准备与首次安装

准备 Windows x64 + Codex、已有 Python **3.14.5 x64**、R **4.6.1 x64**，以及已创建的独立研究目录。R 推荐库为 Matrix **1.7-5**、survival **3.8-6**、nlme **3.1-169**。Python/R 基础程序需另行安装。

1. 将客户 ZIP 解压到独立文件夹，用 PowerShell `Get-FileHash -Algorithm SHA256 '<ZIP路径>'` 与交付值核对。
2. 在 Codex 打开研究目录，把解压位置告诉 Agent，请它按包内 `INSTALL.md` 预检并安装。
3. 支持人员可从解压后的 `toolkit` 目录运行以下预检；路径替换为本机实际位置：

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 .\setup_windows.py --project '<已创建的研究目录>' --rscript '<R-4.6.1/bin/Rscript.exe>'
```

核对计划后，在同一命令末尾加 `--install` 执行。安装复制 48 个 Skill 目录到研究项目 `.agents/skills`，项目依赖写入主 Skill 的 `.runtime`。

## 按方法安装依赖与自检

首次可先装 base。高级方法由安装器自动解析依赖组，例如随机森林使用 `prediction.binary.random_forest`。在研究目录让 Agent 调用已安装的依赖安装器：

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 .agents/skills/ye1-clinical-analysis/scripts/install_windows.py --rscript '<R-4.6.1/bin/Rscript.exe>' --method prediction.binary.random_forest
```

核对预检后加 `--install`。再用主入口要求“自检所选方法”；例如 `scripts/toolkit.py doctor --method prediction.binary.random_forest`。共有 base/ml/plot/penalized/formal_latent/shap/growth/matching 八组，按方法需要安装。

Python 依赖按固定版本与 SHA256 从官方来源取得；R 附加包二进制及匹配源码随工具箱提供。已有官方 wheel 缓存时，在安装命令加 `--wheelhouse '<独立wheel缓存>'`。

## 开始分析

使用 `$ye1-clinical-analysis`，提供本地 CSV 位置、研究问题、结局和变量字典。UTF-8 CSV 可带 BOM；中文列名按字典映射。生存任务补充时间起点、单位、事件码与删失含义。

也可独立调用 `$ye1-baseline-table1`、`$ye1-survival-kaplan-meier`、`$ye1-association-logistic` 等单项 Skill。真实研究的首次准备按包内指引，在本地交互控制台阅读并确认文件和字段。

## 中断恢复与结果保留

Skill 已复制而依赖安装中断时，从研究目录重跑主 Skill 的 `scripts/install_windows.py`，保留相同的组或方法、R 路径及 wheel 缓存参数，并加 `--install`。安装器会核对本项目运行时；缺 pip 时使用基础 Python 的 ensurepip 恢复。保留 `.runtime` 和 `install-logs`。

重复 setup 遇到同名 Skill 会拒绝覆盖。每次分析使用新输出目录，检查表图、分母、事件定义和区间；反馈时提供版本与原因码，日志留本地供有权限的支持人员核对。

微信 `ye1aikeyan` · [ye1aikeyan@163.com](mailto:ye1aikeyan@163.com)
