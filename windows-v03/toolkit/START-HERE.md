# Windows 客户候选：从这里开始

内部版本 `0.3.1-windows-local-noninteractive1`。当前为本地修复候选；是否已有实际 ZIP、包 hash 和独立安装验收，查看包外回执，不能套用旧 final8 包身份。正式发布未完成。

1. 阅读 [安装与首次使用](skills/ye1-clinical-analysis/INSTALL.md)，准备已有的 Python 3.14.5 x64、R 4.6.1 x64 与新研究目录。基础程序不随包。
2. 在该研究目录使用 Codex，让它从当前解压目录运行 `setup_windows.py` 的预检，再按本地授权安装。先只装 base；按方法加装可选组。离线 wheel 参数指向独立缓存，不是其他项目的 venv。
3. 安装完成使用 `$ye1-clinical-analysis` 或同级单项 Skill，自检所选方法后提供本地 CSV 路径与研究问题。患者行和标识不要粘贴到聊天；真实研究仍遵守本地确认规则。
4. 依赖中断后直接用已装主 Skill 的 `scripts/install_windows.py` 恢复，保留 `.runtime` 与日志；不要重复 setup 覆盖同名 Skill。

[能力与边界](skills/ye1-clinical-analysis/references/CAPABILITIES.md) · [验证范围](skills/ye1-clinical-analysis/references/VERIFICATION-SCOPE.md) · [自有代码 MIT 范围](skills/ye1-clinical-analysis/LICENSE-SCOPE.md) · [第三方许可](skills/ye1-clinical-analysis/THIRD-PARTY.md)

项目依赖只安装到主 Skill `.runtime`；无预装患者数据或客户模型。新包验收、物理冷机、GUI 发现、普通真实客户正向全链及临床科学批准分别记录，不以现有合成/公开案例通过代替。
