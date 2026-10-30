# 固定公开案例验收：PBC KM

这是继承的固定公开案例源码适配；新候选包构建/安装验收以包外回执为准，未正式发布。只支持 `survival-pbc-3.8-6-composite-km-v1`，不增加统计方法数。它独立调用未改动的 `clinical_methods.survival.analyze`，不制造普通客户研究任务、人工确认或外发授权。

## 来源、许可与固定身份

数据为 R 推荐包 survival **3.8-6** 的 `pbc`，维护者 Terry M Therneau；上游为 <https://github.com/therneau/survival>，CRAN 包页为 <https://cran.r-project.org/package=survival>。本次使用既有本地 R 4.6.1 推荐库，读取其 DESCRIPTION、pbc 帮助和数据后生成两列投影；未重新联网下载或声称验证远端归档。来源记录见 [机器可读清单](public-fixture-pbc.json)。

该版本 DESCRIPTION 声明 `LGPL (>= 2)`；本地包中未记录 pbc 单独许可。按该包声明将其用于本地教学软件验收，保留来源与许可说明；这不是对其他临床数据库许可、患者隐私或宿主隔离能力的概括保证。LGPL-2 文本见 `third-party/licenses/LGPL-2`。仓库和分发 manifest 不包含数据行，仅包含生成器、适配器与测试。

生成器仅导出原顺序 `time,status`，不导出病例标识、治疗或其他临床变量。精确字节为 UTF-8、LF、首行 `"time","status"`；**2845 bytes、418条记录**，SHA-256 为 `92cc9dc9f6e8b95e2bedc9f7bab201755e761795374765bdd3c466b2d516d151`。程序先核 fixture ID、大小和 hash，再解码；相同文件名、任意自报来源/许可/hash、改一字节均不获得公开案例资格。

## 预先固定的统计问题

时间零点是 Mayo PBC 研究登记日，单位为天，观察到死亡、移植或1986年7月研究分析。原 status 0 为右删失、1 为移植、2 为死亡。这里把1或2定义为**首次死亡或肝移植复合事件**，不是死亡单一终点，也不是把移植当作死亡分析的普通删失。418人中含312名随机试验参与者及106名未随机随访者；不做治疗比较或因果解释。

每行一个独立受试者；完整案例、不填补。独立右删失是方法假设，不因软件通过而得到验证。不支持延迟进入、重复事件、时变协变量、区间删失、聚类或权重。预定汇总时点为0、365、730、1095、1825、3650天；图表单独扩展至全部观察时点，不外推。

## 本地运行（供 Agent / 支持）

先按 INSTALL.md 准备 Python 3.14.5/base 与 R 4.6.1；本案例独立参考额外要求 R 自带 survival 3.8-6。既有库只读，输出使用新目录；不需要重新安装或修改长期库。在主 Skill 目录执行，替换明确的本地路径：

```powershell
& '<Rscript.exe>' --vanilla examples/make_public_pbc.R '<新目录>/pbc-time-status.csv' '<R-4.6.1>/library'
& '<base环境/python.exe>' -I -B -X utf8 scripts/toolkit.py public-fixture --fixture survival-pbc-3.8-6-composite-km-v1 --source '<新目录>/pbc-time-status.csv' --output '<新目录>/km-1' --rscript '<Rscript.exe>'
```

source 和 output 拒绝符号链接/目录联接。output 必须不存在、父目录已存在且位于 Skill 目录之外；已存在的输出原样保留。失败留下局部产物供支持检查，修复后改用新输出目录，不能删除旧证据或忽略失败重写状态。已安装主 Skill 会优先使用自身 `.runtime` Python；开发源码检验可显式指定已有 base 环境，不据此宣称新机安装通过。

## 自动验收与状态解释

`verify_public_pbc.R` 用独立的 `survival::survfit(Surv(time,status!=0)~1, conf.type="log-log")` 生成参考；在预定时点和全部观察时点的并集逐项比较时间、风险集、KM概率及95%CI。时间/风险集精确一致，概率/区间绝对误差须≤1e-12；同刻事件先于删失。PNG还需存在、有效签名、1300×820，报告与CSV实际生成。上述通过后返回 `PUBLIC_FIXTURE_ACCEPTANCE_PASSED`，并写 `acceptance.json`、参考表/日志、命令回执和文件 hash。

数值 `result.json` 仍为原 owner 的 `COMPUTED_REVIEW_PENDING`，`scientific_review` 仍为 pending。自动验收不冒充人工图表审阅、独立源码复验或临床结论批准。本次开发由Codex查看了图题、轴/单位、阶梯曲线、区间、删失符号、图例和报告/分母，结果见 [开发检查记录](VERIFICATION-SCOPE.md)。每次真实研究仍需自身科学复核。

## 普通客户边界

普通客户继续 `prepare_task.py → toolkit.py run`，real/research_analysis 需要原本地交互确认、捕获准入和结果回传授权。公开案例入口不接受真实客户文件、用户自选 hash、时间起点、事件码或其他方法，不改变 real/synthetic 合同。它不会通过重标为 synthetic 或 public_fixture 绕过确认；真实患者行、私有任务和日志仍留本地。

既有12项维护准入回归位于源码包 tests/public_fixture（客户包不含测试工具），覆盖任意CSV、同大小篡改、未知ID、owner漂移、已有/内部输出、数值不一致、非交互real确认、practice真实授权、直接real无准备回执及普通入口伪造public来源。三项内部准入测试仅替代依赖安装预检，真实确认检测及拒绝逻辑未替代；未测试真实客户交互确认到结果全链、物理新机、Mac/WorkBuddy或全局网络隔离。
