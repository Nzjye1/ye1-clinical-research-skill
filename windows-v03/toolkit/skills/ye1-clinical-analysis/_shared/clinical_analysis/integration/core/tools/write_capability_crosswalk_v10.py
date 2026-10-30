"""Exact original 35 entries, with only evidence-bounded v10 coverage changes."""
import json
from pathlib import Path
from write_capability_crosswalk_v09 import ROWS as OLD_ROWS
ROOT=Path(__file__).resolve().parents[1]
def main():
    rows=[]
    for i,(group,item,coverage,methods,boundary) in enumerate(OLD_ROWS,1):
        if i==25:
            coverage='bounded';methods='prediction.survival.cox.lasso;prediction.survival.cox.elasticnet'
            boundary='v0.10固定glmnet Cox、Breslow并列规则、折内预处理/CV及冻结线性预测值和绝对风险；不含选择后推断/PH、IPCW/解释/列线图的新模型接线。'
        elif i==30:
            methods+=';prediction.survival.cox.lasso;prediction.survival.cox.elasticnet'
            boundary+=' v0.10惩罚Cox另有冻结训练→留出/外部合成推理闭环，尚无该模型的IPCW评价接线；不把调参CV当外部验证。'
        elif i==35:
            methods+=';prediction.survival.cox.lasso;prediction.survival.cox.elasticnet'
            boundary+=' v0.10惩罚Cox亦按预设患者/组分区和折隔离。'
        elif i in (26,27,28):
            boundary+=' 该条现有评价桥接仍只接受v0.5普通Cox模型，不自动接受v0.10惩罚Cox。'
        rows.append(dict(original_row=i,group=group,original_item=item,coverage=coverage,registered_methods=methods.split(';') if methods else [],boundary=boundary,
            implementation_state='pending_current_acceptance' if methods else 'not_implemented_or_definition_pending',acceptance='Use final code-bound evidence; this mapping is not a pass receipt'))
    assert len(rows)==35 and [(r['group'],r['original_item']) for r in rows]==[(x[0],x[1]) for x in OLD_ROWS]
    value={'schema_version':'clinical-original-capability-crosswalk@0.10.0-candidate1','original_source':{'filename':'临床分析能力总表.xlsx','library_id':'libfile_50f7d90914088191818387cf71089ab2','baseline':'old v0.5.0-rc1 build2, not this candidate','retrieval':'parent supplied verified row transcription; this task did not download/hash original workbook','groups':{'常用分析':11,'Logistic预测':10,'Cox分析':10,'机器学习':4}},'preserves_original_order_and_duplicates':True,'row_count':35,'scope':'local synthetic engineering subset; not all methods complete and not clinical approval','rows':rows}
    (ROOT/'docs/CAPABILITY-CROSSWALK-V10.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    labels={'bounded':'限定支持','partial':'部分','unregistered':'未接入此需求','definition_pending':'定义待明确'}
    text=['# 原始35项与v0.10候选对应','','来源：父任务逐行核对《临床分析能力总表.xlsx》（Library libfile_50f7d90914088191818387cf71089ab2）后提供转录。本任务未重新下载或哈希工作簿。原表评估旧v0.5.0-rc1 build2，下面映射保留原序与分组重复项，不表示35项全部完成。实际通过/失败/未测以ACCEPTANCE.md及最终回执为准。','','| 原行 | 分组 | 原始项目 | 当前范围 | 边界及差距 |','|---|---|---|---|---|']
    text += [f'| {r["original_row"]} | {r["group"]} | {r["original_item"]} | {labels[r["coverage"]]} | {r["boundary"]} |' for r in rows]
    (ROOT/'docs/CAPABILITY-CROSSWALK-V10.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
    print('ORIGINAL_CAPABILITY_ROWS',len(rows))
if __name__=='__main__':main()
