"""Validated-record projection only. Individual figures are private/local."""
import csv
import json
from pathlib import Path
import numpy as np
from .runtime import prediction as p, validate


def project(response, destination, origin_context=None):
    p.need(response['ok'], 'SHAP_PROJECTION_REQUIRES_SUCCESS')
    for key, name in [('public_record', 'public-record'), ('private_record', 'private-record'), ('diagnostics', 'diagnostics')]:
        validate(response[key], name)
    label = None
    if origin_context is not None:
        p.need(isinstance(origin_context, dict) and
               origin_context.get('data_origin') in {'real', 'synthetic'} and
               origin_context.get('task_purpose') in {'engineering_test', 'research_analysis'} and
               origin_context.get('scientific_review') == 'pending' and
               type(origin_context.get('test_only')) is bool and
               origin_context['test_only'] == (origin_context['task_purpose'] == 'engineering_test') and
               (origin_context['data_origin'] != 'synthetic' or origin_context['task_purpose'] == 'engineering_test'),
               'SHAP_PROJECTION_ORIGIN_CONTEXT_INVALID')
        label = (origin_context['data_origin'].upper()+' | '+origin_context['task_purpose']+
                 ' | scientific review pending')
    def title(text):
        return text if label is None else text+'\n'+label
    image_metadata = {} if label is None else {'metadata': {'Description': label,
        'DataOrigin': origin_context['data_origin'], 'TaskPurpose': origin_context['task_purpose'],
        'ScientificReview': 'pending'}}
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=False)
    for folder in ('tables', 'figures', 'private'):
        (root/folder).mkdir()
    public = response['public_record']; private = response['private_record']
    for name, records in [('encoded-importance', public['encoded_importance']), ('variable-aggregates', public['variable_aggregates'])]:
        records = [{k: json.dumps(v, ensure_ascii=False) if isinstance(v,list) else v for k,v in row.items()} for row in records]
        with (root/'tables'/(name+'.csv')).open('x',newline='',encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    names = [r['feature'] for r in public['encoded_importance']]
    means = np.array([r['mean_absolute_contribution'] for r in public['encoded_importance']])
    order = np.argsort(means)[-20:]
    fig, ax = plt.subplots(figsize=(8, max(3, .35*len(order)+1.5)), layout='constrained')
    ax.barh([names[i] for i in order], means[order], color='#166d88')
    ax.set_xlabel('Mean |SHAP contribution| ('+public['output_scale']+')')
    ax.set_title(title('TreeSHAP: encoded features; n='+str(public['n_explained'])))
    fig.savefig(root/'figures'/'tree-shap-importance.png',dpi=150,**image_metadata); plt.close(fig)
    # No per-person values enter public figures/tables. The following plots and
    # their source response are explicitly kept under private/.
    individuals = private['individual']; contributions = np.array([row['contributions'] for row in individuals])
    fig, ax = plt.subplots(figsize=(8,max(3,.35*len(order)+1.5)),layout='constrained')
    rng = np.random.default_rng(1729)
    for j, i in enumerate(order):
        ax.scatter(contributions[:,i], j+rng.uniform(-.18,.18,len(individuals)),s=13,alpha=.65,color='#166d88')
    ax.set_yticks(range(len(order)),[names[i] for i in order]); ax.axvline(0,color='#999999',lw=.8)
    ax.set_xlabel('SHAP contribution ('+public['output_scale']+')'); ax.set_title(title('LOCAL PRIVATE: individual contributions'))
    fig.savefig(root/'private'/'tree-shap-individual-distribution.png',dpi=150,**image_metadata); plt.close(fig)
    one = contributions[0]; rank=np.argsort(np.abs(one))[-20:]
    fig, ax=plt.subplots(figsize=(8,max(3,.35*len(rank)+1.7)),layout='constrained')
    ax.barh([names[i] for i in rank],one[rank],color=['#b44545' if one[i]>0 else '#166d88' for i in rank])
    ax.axvline(0,color='#999999',lw=.8); ax.set_xlabel('Contribution ('+public['output_scale']+')')
    ax.set_title(title('LOCAL PRIVATE: first record; base='+format(public['base_value'],'.4g')+
                 ', output='+format(individuals[0]['explained_output'],'.4g')))
    fig.savefig(root/'private'/'tree-shap-local.png',dpi=150,**image_metadata);plt.close(fig)
    (root/'private'/'response.json').write_text(json.dumps(response,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    (root/'explanation.txt').write_text('TreeSHAP uses a frozen, uniformly sampled base-fit background.\n'
        'Scale: '+public['output_scale']+'. Base value plus all contributions reconstructs the explained output.\n'
        'Sigmoid of the complete log-odds sum reconstructs probability; individual log-odds contributions are not probability changes.\n'
        'Encoded-column sums are descriptive aggregates, not grouped Shapley values. Public figures contain aggregate means only.\n'
        + ('Synthetic validation only; no causal, clinical utility or real-patient validation claim.\n' if label is None else
         label+'. Local projection only; no causal, clinical utility, source-reconstruction or clinical validation claim.\n'),encoding='utf-8')
    if origin_context is not None:
        (root/'origin-context.json').write_text(json.dumps(origin_context,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
    return {'tables':2, 'public_figures':1, 'private_figures':2}
