# Ye1 临床分析 v0.3.2 安装与首次使用

Windows x64 / Apple 芯片 Mac · 免费科研工具

## 复制这段话，交给 Codex

在 Codex 中打开已创建的研究项目，复制以下内容发送给 Agent：

```text
请识别我的系统，从 https://github.com/Nzjye1/ye1-clinical-research-skill 获取适用的 Ye1 临床分析 v0.3.2 客户包。Mac 如果已有离线包，请使用离线包。
请先阅读安装说明，准备所需依赖，将 Skill 安装到当前研究项目并完成基础自检。
完成后告诉我安装版本、自检结果和开始使用的方法。患者行和标识留在本地。
```

## 下载与准备

- [Windows x64 客户包](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.2-license.20261104/ye1-clinical-client-0.3.2-windows-cc-by-nc-20261104.zip)
- [Apple 芯片 Mac 联网包](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.2-license.20261104/ye1-clinical-0.3.2-macos-arm64-online-cc-by-nc-20261104.zip)
- [Apple 芯片 Mac 离线包](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.2-license.20261104/ye1-clinical-0.3.2-macos-arm64-offline-cc-by-nc-20261104.zip)
- [发布页与 SHA256 清单](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/tag/v0.3.2-license.20261104)

完整解压到独立文件夹，准备一个已创建的研究项目。Mac 要求 Apple 芯片及 macOS 14 或更新版本。Windows 客户包不含 Python 和 R 基础程序，Python 依赖默认需要联网；已有核验的官方 wheel 缓存时可指定 `--wheelhouse`，不应把此包当作完整离线环境。Mac 离线包含固定依赖缓存和基础程序；联网包在安装时获取所需组件。

## Windows 安装

准备 Python 3.14.5 x64 和 R 4.6.1 x64。在 Codex 打开研究项目，将解压路径告诉 Agent。支持人员可在解压后的 `toolkit` 目录，替换下面的路径后运行预检：

```powershell
& '<Python-3.14.5/python.exe>' -I -B -X utf8 .\setup_windows.py --project '<已创建的研究目录>' --rscript '<R-4.6.1/bin/Rscript.exe>'
```

在同一命令末尾加 `--install` 执行安装。默认先准备 base；高级方法可由 Agent 按方法补装。依赖写入研究项目的主 Skill `.runtime`。Windows 包内少量文档仍保留旧候选与终端确认文字；本指南对应 v0.3.2 当前流程。

## Apple 芯片 Mac 安装

解压所选包，在解压后的 `toolkit` 目录执行一条命令，将路径替换为已创建的研究项目路径：

```bash
# 联网包
bash setup-online.sh "已有研究项目路径"
# 完整离线包
bash setup-offline.sh "已有研究项目路径"
```

按需追加 `--method <方法ID>` 或 `--all`。缺少 Python 3.14.5 或 R 4.6.1 时，安装器可能请求系统安装授权；分析依赖安装在研究项目内。安装前可由 Agent 读取 `toolkit/START-HERE.md` 和主 Skill 的安装说明。

## 开始使用

安装并自检后，在研究项目中调用 `$ye1-clinical-analysis`。提供本地 CSV 路径、研究问题、观察单位、列名、单位、编码、分组及参考组、结局和缺失约定。生存分析还需时间起点、单位、事件码及删失定义。

例如：请先核对本地 CSV 的变量定义，为两组生成基线表，再按研究问题选择适用的分析；将结果保存到新目录。患者行和标识留在本地，缺少定义时先询问我。

检查结果中的样本数、分母、事件定义、缺失处理、估计值、区间和图表说明。结果内容随所选方法变化。

## 遇到问题

- 找不到 Skill：重新打开研究项目或新建会话，让 Agent 检查项目内 `.agents/skills/ye1-clinical-analysis/SKILL.md`。
- 安装中断：保留 `.runtime` 和安装日志；让 Agent 按包内恢复步骤继续，不要重复覆盖同名 Skill。
- 缺少方法依赖：让 Agent 按方法安装依赖并重新自检。已有分析结果使用新输出目录。
- 联系支持：微信 **ye1aikeyan**，邮箱 [ye1aikeyan@163.com](mailto:ye1aikeyan@163.com)。反馈版本、系统和脱敏错误摘要，患者行和标识留在本地。
