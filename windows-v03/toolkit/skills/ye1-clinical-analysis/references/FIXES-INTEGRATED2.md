# integrated2：模块导出依赖与重复运行状态

内部版本 `0.3.0-windows-local-integrated2`，来源基线 `b87bb57a`。旧版客户独审结果为 NOT_PASSED，不能把手动补装 plot 后的恢复称为旧包已经修复。

固定修复：随机森林、HGB、惩罚 Cox 的评价/解释，以及二分类 PSM、配对生存 PSM、中介共 7 个模块方法明确依赖现有 plot 组。公共图导出需要 Pillow 和 matplotlib 字体支持；安装器按 `--method` 自动解析，doctor 实际探测这些导入，不增加算法或软件发行包。base 自检仍只要求 base。

普通 run 在输出已存在时返回 `OUTPUT_ALREADY_EXISTS`，此前失败的同名快照/回执/日志存在时返回 `OUTPUT_SNAPSHOT_ALREADY_EXISTS`；均明确 `analysis_executed=false`，保留旧文件并使用全新输出名。原生失败后，只有对应方法/输出的本次执行摘要才可将新生成的 partial 结果报告为待复核，不能根据旧 result.json 推定本次计算成功。验证调用不能报告旧计算。

公开 PBC 生成器按 Windows 进程内 UTF-8 处理命令行参数，不改系统区域设置；它仍只生成原有固定 time/status 投影，不包含标识或扩大白名单。既有公开 KM 回归与普通 PBC 基线研究分别记录；后者和全新 Codex GUI 发现仍未验证。

本次针对性实跑、首失败、复验、新 ZIP 与独立验收状态以包外修复回执为准。源码合成回归不替代新包独审、普通真人确认正向全链或临床科学审核。
