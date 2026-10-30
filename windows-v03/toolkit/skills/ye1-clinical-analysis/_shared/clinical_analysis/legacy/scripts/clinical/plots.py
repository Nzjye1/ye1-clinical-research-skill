"""Small aggregate-only clinical figures. No patient points, ID labels or model refits."""
from __future__ import annotations
import os
from pathlib import Path


def render(record, output, language='zh'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cache = output/'.plot-cache'
    cache.mkdir(exist_ok=True)
    old_cache = os.environ.get('MPLCONFIGDIR')
    os.environ['MPLCONFIGDIR'] = str(cache.resolve())
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.font_manager import FontProperties
        from font_support import select
        chinese = language == 'zh'
        text = '合成测试研究审阅关联效应估计置信区间轨迹窗口组中位数累计发生概率随访时间聚类特征风险预测观察校准假阳性真阳性' if chinese else 'Synthetic clinical review aggregate figures'
        font = select(text, scratch_root=output)
        prop = FontProperties(fname=font['path'])
        result = record['result']
        module = record['module']
        names = []

        def save(fig, name, title, xlabel, ylabel):
            label = ('合成测试 · ' if chinese else 'SYNTHETIC TEST · ') if record['test_only'] else ''
            ax = fig.axes[0]
            ax.set_title(label+title,fontproperties=prop)
            ax.set_xlabel(xlabel,fontproperties=prop)
            ax.set_ylabel(ylabel,fontproperties=prop)
            actual_text = ' '.join(t.get_text() for t in fig.findobj(matplotlib.text.Text))
            actual_font = select(actual_text, scratch_root=output)
            actual_prop = FontProperties(fname=actual_font['path'])
            for item in fig.findobj(matplotlib.text.Text):
                item.set_fontproperties(actual_prop)
            ax.grid(alpha=.15)
            fig.tight_layout()
            path = output/(name+'.png')
            fig.savefig(path,dpi=150)
            plt.close(fig)
            names.append(path.name)

        if module == 'association' and result.get('coefficients'):
            coefficients = [c for c in result['coefficients'] if c['term'] != 'intercept']
            fig,ax = plt.subplots(figsize=(7,4))
            for i,c in enumerate(coefficients):
                estimate = c['odds_ratio'] if result['model']=='logistic' else c['estimate']
                interval = c['or_ci95'] if result['model']=='logistic' else c['ci95']
                ax.errorbar(estimate,i,xerr=[[estimate-interval[0]],
                                           [interval[1]-estimate]],fmt='o',capsize=3)
            ax.set_yticks(range(len(coefficients)),[c['term'] for c in coefficients],fontproperties=prop)
            ax.axvline(1 if result['model']=='logistic' else 0,color='gray',ls='--')
            save(fig,'association-effects','关联效应及置信区间' if chinese else 'Association estimates and intervals',
                 '估计及95%区间' if chinese else 'Estimate and 95% interval','变量' if chinese else 'Variable')
        elif module == 'prediction' and result.get('metrics'):
            metrics = result['metrics']
            curve = metrics.get('aggregate_roc_pr',[])
            if curve:
                fig,ax = plt.subplots(figsize=(5,4))
                ax.plot([p['fpr'] for p in curve],[p['tpr'] for p in curve])
                ax.plot([0,1],[0,1],ls='--',color='gray')
                ax.set(xlim=(0,1),ylim=(0,1))
                validation_title = ('内部留出ROC' if 'internal' in result.get('validation','') else '冻结外部验证ROC') if chinese else result.get('validation','Validation')+' ROC'
                save(fig,'prediction-roc',validation_title,
                     '假阳性率' if chinese else 'False positive rate','真阳性率' if chinese else 'True positive rate')
            bins = metrics.get('calibration_bins',[])
            if bins:
                fig,ax = plt.subplots(figsize=(5,4))
                ax.plot([p['predicted_mean'] for p in bins],[p['observed_fraction'] for p in bins],'o-')
                ax.plot([0,1],[0,1],ls='--',color='gray')
                ax.set(xlim=(0,1),ylim=(0,1))
                save(fig,'prediction-calibration','校准分组描述' if chinese else 'Descriptive grouped calibration',
                     '平均预测概率' if chinese else 'Mean predicted probability','观察比例' if chinese else 'Observed proportion')
        elif module == 'survival' and result.get('curves'):
            points = result['curves']
            fig,ax = plt.subplots(figsize=(6,4))
            competing = 'cumulative_incidence' in points[0]
            ys = [p['cumulative_incidence'][0] if competing else p['event_free_probability'] for p in points]
            # Prespecified grid summaries joined as points; no invented exact step times.
            ax.plot([p['time'] for p in points],ys,'o-')
            ax.set_ylim(0,1)
            save(fig,'survival-grid','预定时点累计发生' if competing and chinese else
                 ('预定时点生存描述' if chinese else 'Prespecified time-grid probability'),
                 '随访时间 ('+result['time_unit']+')' if chinese else 'Follow-up ('+result['time_unit']+')',
                 '概率' if chinese else 'Probability')
        elif module == 'trajectory' and result.get('profiles'):
            fig,ax = plt.subplots(figsize=(6,4))
            groups = sorted({p['group'] for p in result['profiles']})
            for group in groups:
                profiles = [p for p in result['profiles'] if p['group']==group and p.get('summary')]
                ax.plot([p['window_index']+1 for p in profiles],
                        [p['summary']['median'] for p in profiles],'o-',
                        label={'falling':'下降','stable':'稳定','rising':'上升'}.get(group,group) if chinese else group)
            ax.legend()
            save(fig,'trajectory-windows','规则轨迹窗口中位数' if chinese else 'Rule trajectory window medians',
                 '窗口' if chinese else 'Window',result['value_unit'])
        elif module == 'clustering' and result.get('candidates'):
            for candidate in result['candidates']:
                if not candidate.get('profiles'):
                    continue
                profiles = candidate['profiles']
                features = result['features']
                fig,ax = plt.subplots(figsize=(7,4))
                for profile in profiles:
                    ax.plot(features,[profile['features'][f]['median'] for f in features],
                            'o-',label=profile['cluster']+' n='+str(profile['n']))
                ax.legend()
                save(fig,'cluster-profiles-k'+str(candidate['k']),
                     '探索性聚类特征中位数' if chinese else 'Exploratory cluster feature medians',
                     '特征' if chinese else 'Feature','原单位中位数' if chinese else 'Median in original units')
        return {'status':'GENERATED_REVIEW_PENDING' if names else 'NOT_APPLICABLE',
                'files':names,'source':'analysis.json aggregate result only',
                'visual_acceptance':False,'patient_rows_plotted':False,
                'notes':'Grid curves are summaries; clinical and privacy review required before sharing'}
    finally:
        if old_cache is None:
            os.environ.pop('MPLCONFIGDIR',None)
        else:
            os.environ['MPLCONFIGDIR']=old_cache
