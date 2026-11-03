# Apple 芯片 Mac 安装

适用于 macOS 14 或更新版本的 Apple 芯片 Mac，以及 Codex。下载并解压 [Mac 联网安装包](https://github.com/Nzjye1/ye1-clinical-research-skill/releases/download/v0.3.2-license.20261104/ye1-clinical-0.3.2-macos-arm64-online-cc-by-nc-20261104.zip)，让 Agent 阅读包内 `toolkit/START-HERE.md` 并安装到当前研究项目。

联网安装从解压目录的 `toolkit` 中运行 `bash setup-online.sh <已有研究项目目录>`；可按需要添加 `--method <方法ID>` 或 `--all`。完整离线交付包解压后，在同一位置使用 `bash setup-offline.sh <已有研究项目目录>`。路径含空格时请加引号。

安装器使用固定的官方 Python 3.14.5 和 R 4.6.1；缺少基础程序时会请求系统安装授权。分析依赖安装在当前项目内。同名 Skill 已存在时安装器会保护已有目录；依赖安装中断的恢复步骤见包内主 Skill 的 `INSTALL.md`。
