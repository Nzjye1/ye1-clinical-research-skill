"""Preserve the actual original 35 rows, including repeated group entries."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ROWS = [
 ('常用分析','基线资料对比','partial','baseline.table1','两合成映射的描述表与明确分母；按索引后结局分层的描述性角色尚未接入，不能称统计上禁止。'),
 ('常用分析','复合指标区间资料','definition_pending','','原表公式、切点及区间含义尚未明确；当前只有声明单位换算，不冒称通用派生指标完成。'),
 ('常用分析','线性回归','bounded','association.linear;association.linear.plan','OLS 固定连续结局关联范围；复杂抽样、聚类推断与因果解释未覆盖。'),
 ('常用分析','敏感性分析','partial','association.linear.plan;association.logistic.plan','预先指定方案及样本流已接通；不是任意方法/多重插补敏感性框架。'),
 ('常用分析','模型调整','partial','association.linear.plan;association.logistic.plan','预设调整模型、共同完整案例或逐模型案例策略；更复杂纵向/抽样设计未覆盖。'),
 ('常用分析','亚组分析','partial','association.linear.plan;association.logistic.plan','组内效应与交互检验明确区分；支持组合以现有闭合契约为准。'),
 ('常用分析','RCS曲线','partial','association.linear.plan;association.logistic.plan','固定结点/参考值/域及总体和非线性检验；全部模型族的RCS组合未完成。'),
 ('常用分析','中介分析','unregistered','','旧源能力不等于已接入共用契约；正式中介/因果假设与不确定性未验。'),
 ('常用分析','轨迹方程','unregistered','','按原注理解为纵向增长/潜类轨迹；特征轨迹聚类不能替代 GBTM/LCGA/增长混合。'),
 ('常用分析','剖面分析','unregistered','','按原注理解为正式 LPA；GMM/KMeans 不等于完整 LPA。'),
 ('常用分析','聚类分析','unregistered','','尚未接入共用聚类契约与独立验收。'),
 ('Logistic预测','基线资料对比','partial','baseline.table1','通用描述表可用，预测样本/分区语义需明确；合法结局分组角色尚未支持。'),
 ('Logistic预测','倾向性匹配','unregistered','','v0.7 仅连续结局的保留配对人群推断，不能覆盖二分类匹配后效应/配对方差。'),
 ('Logistic预测','单/多因素分析','bounded','association.logistic;association.logistic.plan','明确二元编码及预设调整的关联推断；不自动进行按p值筛选或作因果宣称。'),
 ('Logistic预测','LASSO回归','bounded','prediction.binary.lasso;prediction.binary.elasticnet','固定glmnet、训练内预处理/CV与冻结推理；无普通选择后p值、无多alpha搜索。'),
 ('Logistic预测','ROC','partial','prediction.binary.ridge;prediction.binary.lasso;prediction.binary.elasticnet','Ridge有ROC评价；penalized有原logit排序AUC指标，全部模型统一ROC曲线尚未覆盖。'),
 ('Logistic预测','拟合曲线','partial','prediction.binary.ridge','原表“拟合曲线”含义待确认；以下仅按校准用途暂定映射：现有描述分组不等于已验证校准斜率/区间，penalized校准仍缺。'),
 ('Logistic预测','DCA','partial','prediction.binary.ridge','既有Ridge预设阈值评价；penalized DCA尚未接入。'),
 ('Logistic预测','列线图','partial','interpretation.linear.interventional','v0.9只从冻结二分类LASSO/Elastic Net导出可反查列线图；Ridge/普通Logistic尚未纳入。'),
 ('Logistic预测','内外验证','partial','prediction.binary.ridge;prediction.binary.lasso;prediction.binary.elasticnet','内部留出及同语义外部合成冻结应用；未做真实临床外部验证或所有模型校准/不确定性。'),
 ('Logistic预测','KM曲线','bounded','survival.kaplan_meier','独立的单结局右删失生存描述；KM不是二分类预测概率解释或验证。'),
 ('Cox分析','基线资料对比','partial','baseline.table1','通用描述表可用；生存场景特定角色与样本流需单独声明。'),
 ('Cox分析','倾向性匹配','unregistered','','v0.7连续结局配对推断不能覆盖生存结局匹配后效应/配对或聚类方差。'),
 ('Cox分析','单/多因素分析','bounded','survival.cox.association','固定Breslow ties、HR/CI和正式PH检验；仅支持声明的单结局右删失语义。'),
 ('Cox分析','LASSO回归','unregistered','','Cox-LASSO尚未接入；二分类/连续glmnet不能替代。'),
 ('Cox分析','ROC','bounded','evaluation.survival.cox.ipcw','预设可识别时点的累计/动态IPCW ROC-AUC；条件删失与不确定性尚未覆盖。'),
 ('Cox分析','拟合曲线','partial','evaluation.survival.cox.ipcw','原表“拟合曲线”含义待确认；以下仅按校准用途暂定映射：删失感知描述性分组图，不声称校准斜率/区间或检验。'),
 ('Cox分析','DCA','bounded','evaluation.survival.cox.ipcw','预设时点和阈值的IPCW DCA及treat-all/none；仍依赖删失/positivity假设。'),
 ('Cox分析','列线图','unregistered','','Cox时点风险列线图仍缺；HR及线性预测值不能直接冒称绝对风险。'),
 ('Cox分析','内外验证','partial','prediction.survival.cox;evaluation.survival.cox.ipcw','冻结预处理/系数/基线累计风险的外部合成应用和限定IPCW评价；真实临床验证未做。'),
 ('Cox分析','KM曲线','bounded','survival.kaplan_meier','风险表及有效区间已接入；竞争风险/延迟进入/重复事件不能静默当普通右删失。'),
 ('机器学习','二分类机器学习','partial','prediction.binary.ridge;prediction.binary.lasso;prediction.binary.elasticnet','仅当前固定线性类预测；RF/HistGB/SVM等未接入，原截图尾部截断不推断全部算法。'),
 ('机器学习','SHAP与模型解释','partial','interpretation.linear.interventional','v0.9仅四种penalized affine模型的原始特征分组interventional linear SHAP；Cox/Ridge/conditional/概率尺度及非线性SHAP未覆盖。'),
 ('机器学习','变量重要性图','partial','interpretation.linear.interventional','解释目标队列的mean absolute grouped contribution；不是因果重要性/性能/显著性，未覆盖其他模型族。'),
 ('机器学习','训练/验证集拆分','partial','prediction.continuous.nonnegative.ridge;prediction.binary.ridge;prediction.survival.cox;prediction.continuous.signed.lasso;prediction.continuous.signed.elasticnet;prediction.binary.lasso;prediction.binary.elasticnet','依各方法契约的患者/组隔离；未宣称所有时间拆分、嵌套CV或真实外部人群独立性。'),
]

def main():
    assert len(ROWS) == 35
    rows = [dict(original_row=i, group=g, original_item=item, coverage=status,
                 registered_methods=methods.split(';') if methods else [], boundary=gap,
                 implementation_state=('implementation_in_progress' if 'interpretation.linear.interventional' in methods else 'inherited_implementation_pending_current_regression' if methods else 'not_implemented_or_definition_pending'),
                 acceptance='Use code-bound final manifest; mapping is not an acceptance receipt')
            for i,(g,item,status,methods,gap) in enumerate(ROWS,1)]
    value = {'schema_version':'clinical-original-capability-crosswalk@0.9.0-candidate1',
      'original_source':{'filename':'临床分析能力总表.xlsx','library_id':'libfile_50f7d90914088191818387cf71089ab2',
        'baseline':'old v0.5.0-rc1 build2, not the present candidate',
        'retrieval':'parent read Excel rows and supplied a trusted transcription in this delegation; this task did not independently download or hash the workbook',
        'groups':{'常用分析':11,'Logistic预测':10,'Cox分析':10,'机器学习':4}},
      'preserves_original_order_and_duplicates':True,'row_count':35,
      'scope':'local synthetic engineering subset; not all methods complete and not clinical approval',
      'rows':rows}
    (ROOT/'docs/CAPABILITY-CROSSWALK-V09.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    text=['# 原始35项能力与当前共用候选的对应','',
      '来源为《临床分析能力总表.xlsx》，Library ID `libfile_50f7d90914088191818387cf71089ab2`。父任务逐行读回并提供转录，本任务未独立下载或计算该工作簿哈希。原表核对的是旧 v0.5.0-rc1 build2，不能当作当前新候选的能力结论。保留原序及分组重复项。','',
      '下表的“限定支持”或“部分”仅描述本候选的限定范围；第19、33、34行属于本批开发范围，验收前不算通过；真实通过、失败、未测以最终验收回执为准。工程通过不等于临床科学通过。','',
      '| 原行 | 分组 | 原始项目 | 当前范围 | 边界与剩余差距 |','|---|---|---|---|---|']
    labels={'bounded':'限定支持','partial':'部分','unregistered':'未接入此需求','definition_pending':'定义待明确'}
    text += [f'| {r["original_row"]} | {r["group"]} | {r["original_item"]} | {labels[r["coverage"]]} | {r["boundary"]} |' for r in rows]
    (ROOT/'docs/CAPABILITY-CROSSWALK-V09.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print('ORIGINAL_CAPABILITY_ROWS',len(rows))
if __name__=='__main__':main()
