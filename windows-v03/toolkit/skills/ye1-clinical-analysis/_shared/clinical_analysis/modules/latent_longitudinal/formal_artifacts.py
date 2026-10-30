"""Aggregate scientific plots and tables only; contains no model fitting."""
import csv,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .contracts import need
from .module import sha_file
def write_artifacts(public,output_dir,admission=None):
    out=Path(output_dir);need(not out.exists(),'OUTPUT_ALREADY_EXISTS');out.mkdir(parents=True)
    tables=out/'tables';figures=out/'figures';tables.mkdir();figures.mkdir();artifacts=[]
    analysis=public['analysis']
    def record(path,kind):artifacts.append({'path':path.relative_to(out).as_posix(),'kind':kind,'sha256':sha_file(path)})
    for name in ['selection','initializations','class_counts','fit_statistics','stability','profiles','parameters','trajectories','preprocessing']:
        rows=analysis[name]
        if not rows:continue
        fields=list(dict.fromkeys(k for row in rows for k in row));path=tables/(name+'.csv')
        with path.open('x',encoding='utf-8-sig',newline='') as h:
            writer=csv.DictWriter(h,fields);writer.writeheader();writer.writerows(rows)
        record(path,'table')
    def save(fig,name):
        if admission is not None:
            fig.suptitle(f'{admission.data_origin.upper()} DATA | {admission.task_purpose} | scientific review pending',fontsize=10)
            fig.tight_layout(rect=(0,0,1,.93))
        else:fig.tight_layout()
        path=figures/(name+'.png');fig.savefig(path,dpi=160);plt.close(fig);record(path,'figure')
    if analysis['selection']:
        accepted=[x for x in analysis['selection'] if x['status']=='accepted'];fig,ax=plt.subplots(figsize=(7,4))
        ax.plot([r['k'] for r in accepted],[r['BIC'] for r in accepted],'-o');ax.set_xticks([r['k'] for r in analysis['selection']])
        ax.set(xlabel='Prespecified number of classes',ylabel='Training BIC (lower is better)',title=analysis['model_family']+' | model selection')
        save(fig,'class_selection')
    fig,ax=plt.subplots(figsize=(8,4.8))
    if analysis['profiles']:
        features=[f['name'] for f in public['definition']['definition']['indicators']]
        for c in range(1,analysis['selected_k']+1):
            rows=[r for r in analysis['profiles'] if r['class']==c]
            ax.plot(range(len(features)),[next(r['standardized_mean'] for r in rows if r['feature']==f) for f in features],'-o',label=f'Class {c}')
        ax.set_xticks(range(len(features)),features,rotation=20,ha='right');ax.set(ylabel='Mean in training standard deviations',title='LPA | model-implied profiles; no confidence bands')
    else:
        for c in range(1,analysis['selected_k']+1):
            rows=[r for r in analysis['trajectories'] if r['class']==c]
            ax.plot([r['time'] for r in rows],[r['estimate'] for r in rows],label=f'Class {c}')
        row=analysis['trajectories'][0];ax.set(xlabel='Time ('+row['time_unit']+')',ylabel='Marginal mean ('+row['outcome_unit']+')',
          title=analysis['model_family']+' | class-specific mean; no confidence bands')
    ax.legend(frameon=False);ax.grid(alpha=.2);save(fig,'class_means')
    if analysis['stability']:
        good=[r for r in analysis['stability'] if r['status']=='accepted'];fig,ax=plt.subplots(figsize=(7,4))
        ax.scatter([r['replicate'] for r in good],[r['ari'] for r in good]);ax.set_ylim(-1.05,1.05)
        ax.set(xlabel='Training subject bootstrap replicate',ylabel='Adjusted Rand index',title='Fixed selected K | descriptive stability, not confidence intervals')
        save(fig,'stability')
    scope='Conditional independence with equal indicator-specific variance across classes (EEI).' if public['definition']['definition'].get('covariance_model')=='EEI' else 'Class-specific diagonal indicator variances (VVI).'
    if analysis['model_family']!='LPA':scope='Gaussian repeated outcomes with independent residual errors conditional on class/random effects. Random covariance is shared across classes; class membership has intercept-only probabilities.'
    text=[f"# {analysis['model_family']} analysis",'',f"Selected classes: {analysis['selected_k']}. Operation: {public['operation']}. " +
      ('Synthetic engineering scope; scientific review pending; local only.' if admission is None else
       f'{admission.data_origin.upper()} DATA | {admission.task_purpose} | scientific review pending; local only.'),'',scope,'',
      'Training-only BIC compares the prespecified class counts. At least two accepted starts must reproduce the best mixture likelihood; this does not establish the global maximum. A one-class model has a single initialization and is not presented as replicated mixture evidence. Rejected candidates and initializations remain in the tables.','',
      'Bootstrap resamples training subjects and refits transformations and the selected class count. Its quantiles are descriptive, not confidence intervals; class selection uncertainty is not measured. Holdout/external scoring never refits or selects the model. Posterior membership requires observed indicators/outcomes; it is not prospective prediction or clinical validation.','',
      'Means and coefficients have no confidence bands or p-values. No BLRT/LMR test, causal interpretation, clinical class diagnosis, or treatment recommendation is produced. Hard assignment discards posterior uncertainty.','',
      'Missing profile indicators use complete cases. Trajectory likelihood uses available outcomes under MAR and the specified model; informative dropout and missing covariate imputation are not handled. Residual correlation, non-Gaussian outcomes, time-varying class membership and class-membership covariates are unsupported.','',
      'Warnings:']+['- '+w for w in public['warnings']]
    path=out/'report.md';path.write_text('\n'.join(text)+'\n',encoding='utf-8');record(path,'report')
    return {'tables':[a for a in artifacts if a['kind']=='table'],'figures':[a for a in artifacts if a['kind']=='figure'],
            'report':[a for a in artifacts if a['kind']=='report']}
