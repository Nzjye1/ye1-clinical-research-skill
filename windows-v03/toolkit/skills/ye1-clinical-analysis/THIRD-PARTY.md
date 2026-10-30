# 第三方组件与来源

自有源码与适配部分按 MIT 提供，范围见 LICENSE / LICENSE-SCOPE.md；继承原版权及第三方 license/notice。MIT 不覆盖下列第三方组件或数据，也不替全部依赖声明同一许可。实际归档、METADATA、许可文件及 SHA 见 references/DEPENDENCIES.json 和 licenses/python/，原声明逐字节保留。

Python与R基础程序不随包。Python26发行包（含隔离SHAP3项）从官方固定wheel安装，保留各.dist-info许可。R14项原CRAN二进制与对应源码tar.gz随包，原版权/许可保留。来源、hash与版本见runtime-spec.json。GPL文本在third-party/licenses。

|Python发行包|版本|获取方式|
|---|---|---|
|numpy|2.5.4|官方wheel；SHA锁定；许可随wheel保留|
|scipy|1.18.1|官方wheel；SHA锁定；许可随wheel保留|
|statsmodels|0.14.6|官方wheel；SHA锁定；许可随wheel保留|
|pandas|2.3.3|官方wheel；SHA锁定；许可随wheel保留|
|patsy|1.0.3|官方wheel；SHA锁定；许可随wheel保留|
|packaging|26.3|官方wheel；SHA锁定；许可随wheel保留|
|python-dateutil|3.0.0|官方wheel；SHA锁定；许可随wheel保留|
|pytz|2026.5|官方wheel；SHA锁定；许可随wheel保留|
|tzdata|2026.5|官方wheel；SHA锁定；许可随wheel保留|
|six|1.17.0|官方wheel；SHA锁定；许可随wheel保留|
|scikit-learn|1.9.1|官方wheel；SHA锁定；许可随wheel保留|
|joblib|1.6.0|官方wheel；SHA锁定；许可随wheel保留|
|cloudpickle|3.1.2|官方wheel；SHA锁定；许可随wheel保留|
|narwhals|2.27.1|官方wheel；SHA锁定；许可随wheel保留|
|threadpoolctl|3.7.0|官方wheel；SHA锁定；许可随wheel保留|
|colorama|0.4.6|官方wheel；SHA锁定；许可随wheel保留|
|matplotlib|3.11.2|官方wheel；SHA锁定；许可随wheel保留|
|contourpy|1.4.0|官方wheel；SHA锁定；许可随wheel保留|
|cycler|0.12.1|官方wheel；SHA锁定；许可随wheel保留|
|fonttools|4.67.0|官方wheel；SHA锁定；许可随wheel保留|
|kiwisolver|1.5.1|官方wheel；SHA锁定；许可随wheel保留|
|pillow|12.3.0|官方wheel；SHA锁定；许可随wheel保留|
|pyparsing|3.3.3|官方wheel；SHA锁定；许可随wheel保留|
|shap|0.54.1|官方wheel；SHA锁定；许可随wheel保留|
|slicer|0.0.8|官方wheel；SHA锁定；许可随wheel保留|
|tqdm|4.70.1|官方wheel；SHA锁定；许可随wheel保留|

|R包|版本|原声明许可|
|---|---|---|
|jsonlite|2.0.0|MIT + file LICENSE|
|digest|0.6.39|GPL (>= 2)|
|Rcpp|1.1.2|GPL (>= 2)|
|foreach|1.5.2|Apache License (== 2.0)|
|glmnet|5.1|GPL-2|
|iterators|1.0.14|Apache License (== 2.0)|
|shape|1.4.6.1|GPL (>= 3)|
|doParallel|1.0.17|GPL-2|
|lcmm|2.2.2|GPL (>= 2.0)|
|marqLevAlg|2.0.8|GPL (>= 2.0)|
|mclust|6.1.3|GPL (>= 2)|
|mvtnorm|1.4.2|GPL-2|
|numDeriv|2016.8.1.1|GPL-2|
|spacefillr|0.4.0|MIT + file LICENSE|

本版只将继承的科学实现接入本地工具箱；没有修改其统计算法。字体仅PDF嵌入/子集，不单独分发原字体文件。未附任何用户数据、客户模型、基础Python/R安装器或开发运行库。

固定PBC软件案例来自 survival 3.8-6 的 pbc（Terry M Therneau / survival上游），该包 DESCRIPTION 声明 LGPL (>= 2)，未见pbc单独许可记录。只提供本地两列生成器和适配/参考脚本，不分发数据行或已安装包；来源、固定hash与适用边界见 references/PUBLIC-FIXTURES.md。LGPL-2文本保留在 third-party/licenses/LGPL-2。
