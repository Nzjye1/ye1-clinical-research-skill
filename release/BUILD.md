# 临床候选包构建准备

本轮只完成许可、依赖布局、包成员计划与构建命令；没有构建完整候选 ZIP、没有执行独立安装验收或发布。产品版本由主 Skill `runtime-spec.json` 的 `product_version` 唯一取值，文件名再附实际 Git commit 前 8 位；包内 `SOURCE-REVISION.json` 和包外回执保留完整 commit。

构建器继承既有静态 ZIP / toolkit-manifest 布局，继续使用原 `setup_windows.py`、依赖安装器和锁；不改科学实现、自动安装基础程序或引入服务器。用干净 Git checkout 和已有 Python 3.14.5 执行。源 ZIP 供源码审阅与维护测试，不含 `.git`；需要 Git 继承检查或再次构建时使用对应完整提交的 checkout。

## 准备独立目录和离线依赖

选择源码树之外、非 Temp、非已有研究目录的输出根；只创建新计划/新包，不覆盖旧文件。Python wheel 缓存必须是独立目录内的 26 份原官方归档，`CACHE-MANIFEST.json` 记录文件名/大小/SHA/原 URL；不能借用别的项目已安装的 venv。主 Skill 已有 14 组 R 原二进制和对应源码，无需重装或另行下载。

```powershell
$FoundationPython = '<已有 Python 3.14.5 的 python.exe>'
$CandidateOutput = '<已创建的独立候选输出目录>'
$Wheelhouse = '<独立依赖缓存目录>/python'
& $FoundationPython -I -B -X utf8 release/verify_dependencies.py --wheelhouse $Wheelhouse --output '<新的核验JSON路径>'
```

核验只读归档、许可和可选运行时路径，不执行 pip/R 安装。没有离线 wheel 时，原安装器可按 `runtime-spec.json` 的固定 `files.pythonhosted.org` URL 下载并核 SHA；本轮未测试联网下载。离线缓存与安装日志各有自己的目录，均不进入客户 ZIP。

## 先生成两个成员计划（本轮执行范围）

```powershell
& $FoundationPython -I -B -X utf8 release/build_candidate.py --kind source --output-root $CandidateOutput --plan
& $FoundationPython -I -B -X utf8 release/build_candidate.py --kind client --output-root $CandidateOutput --plan
```

只生成 `.plan.json`：逐成员路径/大小/SHA、排除清单、原运行依赖源码闭合检查、版本与 commit；不写 ZIP、不复制客户 Skill、不安装依赖。脏工作树可规划，但标记 `source_dirty=true`，不能作为冻结构建。相同计划文件已存在时拒绝，保留旧回执后选择新输出目录。

## 后续独立任务中实际构建（本轮不执行）

先核对 clean checkout、成员计划和全部第三方原声明，再在新的空输出目录执行：

```powershell
$Revision = (git rev-parse HEAD).Trim()
git status --short
& $FoundationPython -I -B -X utf8 release/build_candidate.py --kind source --output-root $CandidateOutput --build --expected-commit $Revision
& $FoundationPython -I -B -X utf8 release/build_candidate.py --kind client --output-root $CandidateOutput --build --expected-commit $Revision
```

构建器拒绝脏树、提交不符、输出位于源码/Temp、目录联接、已有包、缺运行必需源文件或产品内开发者/个人路径。它使用稳定排序、固定 ZIP 成员时间戳和模式，生成包外 `.build.json` / SHA / 成员清单，并标记 `BUILT_NOT_ACCEPTED`。构建成功只证明归档生成与 CRC，不代表安装通过；版本/提交不变但构建器或压缩实现不同也不能凭假设宣称 ZIP 字节一致，须实际比较 hash。

## 解压后安装与恢复

客户从 `toolkit/START-HERE.md` → 主 Skill `INSTALL.md` 开始，使用包内真实 `setup_windows.py`。首次先预检，再经本地授权加 `--install`；48 个 Skill 复制到所选研究项目 `.agents/skills`。base 与可选组分开；Python/R 基础程序外部安装，项目依赖写主 Skill `.runtime`。

Skill 已复制而依赖中断时，用该项目主 Skill 的 `scripts/install_windows.py --groups base --rscript '<Rscript>' --install [--wheelhouse '<缓存>']` 恢复；不要再次 setup 覆盖同名 Skill，不删除 `.runtime` 或旧日志。原安装器核所有权/隔离 venv，缺 pip 使用基础 Python 自带 ensurepip，再按原 hash 锁继续。源代码或位置改变后在新项目重装，不能移植旧 profile 或静默改冻结模型。

下一项必须从新 ZIP 解压副本独立验包/安装，覆盖在线与离线、base 与全组、真实进程中断恢复、GUI 发现、基础程序和物理冷机；更新或另做正式 PDF 教程后渲染目视。普通真实客户正向确认全链、临床科学复核及任何远端仓库/Release 另行确认。本轮既有集成测试结果只作来源，不冒充新 ZIP 验收。
