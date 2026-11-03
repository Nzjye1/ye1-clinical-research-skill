# Ye1 临床分析 v0.3.2：Windows 安装入口

适用于 Windows x64 与 Codex。客户包版本为 `0.3.2-windows-local-noninteractive1`；请按 对应发布页提供的 SHA256 清单核验下载文件。Python 和 R 基础程序需另行准备。

1. 阅读 [安装与首次使用](skills/ye1-clinical-analysis/INSTALL.md)，准备已有的 Python 3.14.5 x64、R 4.6.1 x64 与新研究目录。基础程序不随包。
2. 在该研究目录使用 Codex，让它从当前解压目录运行 `setup_windows.py` 的预检，再按本地授权安装。先只装 base；按方法加装可选组。离线 wheel 参数指向独立缓存，不是其他项目的 venv。
3. 安装完成使用 `$ye1-clinical-analysis` 或同级单项 Skill，自检所选方法后提供本地 CSV 路径与研究问题。患者行和标识不要粘贴到聊天；按指定的本地文件和任务参数准备，不需要旧版交互终端确认。
4. 依赖中断后直接用已装主 Skill 的 `scripts/install_windows.py` 恢复，保留 `.runtime` 与日志；不要重复 setup 覆盖同名 Skill。

[能力与边界](skills/ye1-clinical-analysis/references/CAPABILITIES.md) · [验证范围](skills/ye1-clinical-analysis/references/VERIFICATION-SCOPE.md) · [Ye1 内容许可范围](skills/ye1-clinical-analysis/LICENSE-SCOPE.md) · [第三方许可](skills/ye1-clinical-analysis/THIRD-PARTY.md)

项目依赖只安装到主 Skill `.runtime`；无预装患者数据或客户模型。新包验收、物理冷机、GUI 发现、普通真实客户正向全链及临床科学批准分别记录，不以现有合成/公开案例通过代替。
