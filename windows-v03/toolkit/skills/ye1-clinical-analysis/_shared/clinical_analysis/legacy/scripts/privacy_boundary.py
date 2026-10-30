"""Project choices and fail-closed local export gate. No network or host sandbox.
Only a separately controlled host adapter can make this the exclusive data outlet.
"""
import argparse, hashlib, json, math, os, re, shutil, sys, tempfile, zipfile
from pathlib import Path
from datetime import datetime, timezone
from contextlib import contextmanager

class Denied(ValueError): pass
def need(ok, code):
    if not ok: raise Denied(code)
def digest(b): return hashlib.sha256(b).hexdigest()
def encoded(x): return (json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
def read(p): return json.loads(Path(p).read_text(encoding='utf8'))
def inside(root, rel):
    need(isinstance(rel,str) and rel and not Path(rel).is_absolute() and '..' not in Path(rel).parts, 'UNSAFE_PATH')
    p=Path(root).resolve()/rel
    need(not any(q.is_symlink() for q in [p,*p.parents]) and p.resolve().is_relative_to(Path(root).resolve()), 'UNSAFE_PATH')
    return p

def evidence(root, e, test_only=False):
    need(isinstance(e,dict) and set(e)<={'kind','path','sha256','locator','quote','scope_sha256'},'UNSUPPORTED_EVIDENCE_FIELD')
    need(isinstance(e,dict) and e.get('kind') in ({'direct_user','synthetic'} if test_only else {'direct_user'}), 'USER_EVIDENCE_REQUIRED')
    p=inside(root,e.get('path'));b=p.read_bytes()
    need(e.get('sha256')==digest(b) and e.get('locator') and e.get('quote') and e['quote'] in b.decode('utf8'), 'EVIDENCE_CHANGED_OR_MISSING')
    # Quotable local provenance is not identity authentication. Host must protect it.

def validate_choice(c):
    need(isinstance(c,dict) and set(c)<={'schema','mode','attachment_history','grants'},'UNSUPPORTED_CHOICE_FIELD')
    need(c.get('schema')=='ye1-data-choice/1' and c.get('mode') in {'A','B'}, 'CHOICE_SCHEMA')
    need(isinstance(c.get('attachment_history'),list), 'ATTACHMENT_FACTS_REQUIRED')
    grants=c.get('grants');need(isinstance(grants,list), 'GRANTS_REQUIRED')
    keys=[]
    for g in grants:
        need(isinstance(g,dict) and set(g)<={'path','sha256','platform','model','purpose','classification','review'},'UNSUPPORTED_GRANT_FIELD')
        if 'review' in g:
            need(isinstance(g['review'],dict) and set(g['review'])<={'no_row_data','identifiers_checked','free_text_checked','small_cells_checked','extremes_checked','labels_checked','linkability_checked','difference_queries_checked','filenames_checked','metadata_checked','minimum_cell_n','evidence'},'UNSUPPORTED_REVIEW_FIELD')
            if 'evidence' in g['review']:
                ev=g['review']['evidence'];need(isinstance(ev,dict) and set(ev)<={'kind','path','sha256','locator','quote','scope_sha256'},'UNSUPPORTED_EVIDENCE_FIELD')
        need(all(isinstance(g.get(k),str) and g[k] for k in ('path','sha256','platform','model','purpose','classification')), 'GRANT_SCOPE_REQUIRED')
        need(re.fullmatch('[0-9a-f]{64}',g['sha256']), 'GRANT_HASH_REQUIRED')
        need(g['classification'] in {'aggregate','reviewed_document','reviewed_figure','specified_data'}, 'GRANT_CLASSIFICATION')
        need(c['mode']=='B' or g['classification']!='specified_data', 'A_FORBIDS_ROW_DATA')
        keys.append((g['path'],g['platform'],g['model'],g['purpose']))
    need(len(keys)==len(set(keys)), 'CONFLICTING_GRANTS')

def load(root):
    d=Path(root)/'.ye1-privacy';need(not d.is_symlink(),'UNSAFE_STATE');state=read(d/'choice.json');chain=read(d/'history.json')
    need(chain and state==chain[-1]['choice'], 'CHOICE_CONFLICT')
    previous=None
    for i,item in enumerate(chain,1):
        need(item['revision']==i and item['previous']==previous, 'HISTORY_CONFLICT')
        body={k:v for k,v in item.items() if k!='sha256'}
        need(item['sha256']==digest(encoded(body)), 'HISTORY_CHANGED')
        previous=item['sha256']
    validate_choice(state)
    need(chain[-1]['test_only'] is False or os.environ.get('YE1_PRIVACY_SYNTHETIC_TEST')=='1', 'TEST_CHOICE_FORBIDDEN')
    latest=next((i for i in reversed(chain) if i['evidence'].get('kind')!='tightening'),None)
    need(latest is not None,'USER_EVIDENCE_REQUIRED')
    evidence(root,latest['evidence'],os.environ.get('YE1_PRIVACY_SYNTHETIC_TEST')=='1')
    return state,chain

def save_choice(root,c,e=None,test_only=False):
    root=Path(root).resolve();need(root.is_dir(),'PROJECT_REQUIRED');validate_choice(c)
    d=root/'.ye1-privacy';need(not d.is_symlink(),'UNSAFE_STATE');d.mkdir(exist_ok=True)
    with project_transaction(root):
        old=None;chain=[]
        if (d/'choice.json').exists() or (d/'history.json').exists():old,chain=load(root)
        if old==c:return {'status':'UNCHANGED','revision':len(chain)}
        # Tightening requires no repeat confirmation; any broadening/change of recipient,
        # purpose, bytes or review gets fresh version-bound user evidence.
        tightening=bool(old and (old['mode']==c['mode'] or (old['mode']=='B' and c['mode']=='A')) and all(g in old['grants'] for g in c['grants']) and c['attachment_history']==old['attachment_history'])
        if not tightening:
            evidence(root,e,test_only)
            need(e.get('scope_sha256')==digest(encoded(c)), 'CONFIRM_EXACT_CHOICE')
        item={'revision':len(chain)+1,'previous':chain[-1]['sha256'] if chain else None,'choice':c,'evidence':e if not tightening else {'kind':'tightening'},'test_only':bool(test_only or (tightening and any(i['test_only'] for i in chain))),'at':datetime.now(timezone.utc).isoformat()}
        item['sha256']=digest(encoded(item));chain.append(item)
        # History first: interruption yields conflict/deny, never an expanded silent choice.
        for name,value in [('history.json',chain),('choice.json',c)]:
            tmp=d/(name+'.tmp');tmp.write_bytes(encoded(value));os.replace(tmp,d/name)
        return {'status':'RECORDED','revision':len(chain),'prior_sends_recalled':False}


def host_check(root,mode,test_only=False):
    h=read(Path(root)/'.ye1-privacy/host.json')
    need(h.get('schema')=='ye1-controlled-host/1' and h.get('adapter_id') and h.get('assessment_reference'), 'HOST_UNASSESSED')
    need(h.get('exclusive_gateway') is True and h.get('protected_state') is True and h.get('protected_evidence') is True, 'HOST_CANNOT_ENFORCE')
    if mode=='A':need(h.get('raw_files_inaccessible_to_agent') is True and h.get('local_compute') is True and h.get('attachments_controlled') is True, 'STRICT_LOCAL_UNSUPPORTED')
    need(not h.get('synthetic') or (test_only and os.environ.get('YE1_PRIVACY_SYNTHETIC_TEST')=='1'), 'TEST_HOST_FORBIDDEN')
    # This descriptor is an integration assertion, not proof or permission modification.
    return h

ROW_KEYS={'rows','source_row','person','patient_id','y_true','y_probability','residuals','before','after','plot_payload'}
def has_rows(x):
    if isinstance(x,dict):return bool(ROW_KEYS&set(x)) or any(has_rows(v) for v in x.values())
    if isinstance(x,list):return any(has_rows(v) for v in x)
    return False

def inspect_a(root,rel,b,g,test_only):
    suffix=Path(rel).suffix.lower()
    need(suffix not in {'.csv','.tsv','.xlsx','.xls','.log','.zip'}, 'A_STRUCTURED_OR_LOG_REQUIRES_SAFE_DERIVATIVE')
    if suffix=='.json':
        x=json.loads(b);need(not has_rows(x),'ROW_LEVEL_CONTENT')
    checks=g.get('review',{})
    need(all(checks.get(k) is True for k in ('no_row_data','identifiers_checked','free_text_checked','small_cells_checked','extremes_checked','labels_checked','linkability_checked','difference_queries_checked','filenames_checked','metadata_checked')), 'SUMMARY_REVIEW_REQUIRED')
    evidence(root,checks.get('evidence'),test_only)
    if g['classification']=='aggregate':
        need(suffix=='.json','AGGREGATE_TYPED_JSON_REQUIRED')
        need(set(x)=={'schema','metrics'} and x['schema']=='ye1-reviewed-summary/1' and isinstance(x['metrics'],list) and x['metrics'], 'SUMMARY_SCHEMA')
        for m in x['metrics']:
            need(set(m)=={'metric','value','n'},'SUMMARY_FIELDS')
            need(re.fullmatch('[a-z][a-z0-9_]{0,63}',m['metric']) and m['metric'] not in {'min','max','minimum','maximum'},'SUMMARY_METRIC')
            need(isinstance(m['value'],(int,float)) and not isinstance(m['value'],bool) and math.isfinite(m['value']), 'SUMMARY_NUMERIC')
            minimum=checks.get('minimum_cell_n')
            need(type(minimum) is int and minimum>=2 and type(m['n']) is int and m['n']>=minimum,'SMALL_CELL_BLOCKED')
    else:need(g['classification'] in {'reviewed_document','reviewed_figure'},'A_CLASSIFICATION')


def authorize(root,rel,platform,model,purpose,test_only=False):
    c,history=load(root);host_check(root,c['mode'],test_only)
    p=inside(root,rel);need(p.is_file(),'FILE_REQUIRED');b=p.read_bytes()
    grants=[g for g in c['grants'] if all(g[k]==v for k,v in [('path',rel),('platform',platform),('model',model),('purpose',purpose)])]
    need(len(grants)==1,'SCOPE_NOT_AUTHORIZED');g=grants[0];need(digest(b)==g['sha256'],'VERSION_CHANGED')
    if c['mode']=='A':inspect_a(root,rel,b,g,test_only)
    return b,{'status':'AUTHORIZED_LOCAL_GATE','revision':len(history),'sha256':digest(b),'mode':c['mode'],'sent':False}

@contextmanager
def project_transaction(root):
    """One lock for choices and every artifact publisher; no mixed revisions."""
    d=Path(root).resolve()/'.ye1-privacy'
    need(d.is_dir() and not d.is_symlink(),'PROJECT_CHOICE_REQUIRED')
    lock=d/'lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:raise Denied('CHOICE_BUSY')
    os.close(fd)
    try:yield
    finally:lock.unlink()

def _capture_locked(root,rels,platform,model,purpose,test_only,names=None,expected=None):
    need(rels and len(rels)==len(set(rels)),'FILES_REQUIRED')
    need(names is None or set(names)==set(rels),'MEMBER_MAP_REQUIRED')
    need(expected is None or set(expected)==set(rels),'EXPECTED_HASHES_REQUIRED')
    payload={};revision=None
    for rel in rels:
        b,r=authorize(root,rel,platform,model,purpose,test_only)
        need(Path(rel).suffix.lower()!='.zip','NESTED_ARCHIVE_FORBIDDEN')
        if expected is not None:need(digest(b)==expected[rel],'CONFIRMED_BYTES_CHANGED')
        name=names[rel] if names is not None else rel
        need(isinstance(name,str) and name and not Path(name).is_absolute() and '..' not in Path(name).parts and name not in payload,'UNSAFE_MEMBER')
        need(Path(name).suffix.lower()==Path(rel).suffix.lower(),'MEMBER_TYPE_CHANGED')
        need(revision is None or revision==r['revision'],'CHOICE_CONFLICT')
        revision=r['revision'];payload[name]=b
    return payload,revision

def _publish_locked(root,payload,out,revision,*,tree=False,validator=None):
    target=Path(out);need(not target.exists() and not target.is_symlink(),'PRESERVE_EXPORT')
    need(not target.resolve().is_relative_to((Path(root)/'.ye1-privacy').resolve()),'PROTECTED_STATE')
    target.parent.mkdir(parents=True,exist_ok=True)
    # Stage only captured approved bytes. No source path is read after capture.
    tmp=Path(tempfile.mkdtemp(dir=target.parent,prefix='.ye1-export-')) if tree else None
    if not tree:
        fd,name=tempfile.mkstemp(dir=target.parent,prefix='.ye1-export-');os.close(fd);tmp=Path(name)
    try:
        if tree:
            for rel,b in payload.items():
                dest=tmp/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
        else:
            with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
                for rel,b in payload.items():z.writestr(rel,b)
            # Verify actual archive member bytes before publishing, never optional.
            with zipfile.ZipFile(tmp) as z:
                need(len(z.namelist())==len(payload) and set(z.namelist())==set(payload),'ARCHIVE_MEMBERS_CHANGED')
                need(all(z.read(rel)==b for rel,b in payload.items()),'ARCHIVE_BYTES_CHANGED')
        validation=validator(tmp) if validator else None
        need(not target.exists() and not target.is_symlink(),'PRESERVE_EXPORT')
        if tree:os.rename(tmp,target)  # same filesystem; project lock serializes cooperative publishers
        else:os.link(tmp,target)  # no-overwrite atomic publication
        return {'status':'LOCAL_EXPORT_READY','member_count':len(payload),'sent':False,'revision':revision,'validation':validation,
                'sha256':None if tree else digest(target.read_bytes())}
    finally:
        if tmp.is_dir():shutil.rmtree(tmp)
        else:tmp.unlink(missing_ok=True)

def export(root,rels,out,platform,model,purpose,test_only=False,*,names=None,expected=None,tree=False,validator=None):
    # Legacy review preparation and packaging use this same capture/lock/publication.
    with project_transaction(root):
        payload,revision=_capture_locked(root,rels,platform,model,purpose,test_only,names,expected)
        return _publish_locked(root,payload,out,revision,tree=tree,validator=validator)


def run_local(root,argv,test_only=False):
    """Controlled adapter API; argv must be fixed by adapter, never model arbitrary shell.
    Tool streams/logs remain local even on failure; no command/output/path echoed.
    """
    import subprocess
    c,_=load(root);host_check(root,c['mode'],test_only)
    need(isinstance(argv,list) and argv and all(isinstance(a,str) for a in argv),'COMMAND_REQUIRED')
    logdir=Path(root)/'.ye1-privacy/local-logs';logdir.mkdir(exist_ok=True)
    fd,name=tempfile.mkstemp(dir=logdir,prefix='run-',suffix='.log')
    with os.fdopen(fd,'wb') as f:
        try:
            env={**os.environ,'YE1_PRIVACY_CONTROLLED_RUN':'1','YE1_PRIVACY_PROJECT':str(Path(root).resolve())}
            r=subprocess.run(argv,stdout=f,stderr=f,timeout=300,cwd=root,env=env);code=r.returncode
        except (OSError,subprocess.SubprocessError):code=-1
    return {'status':'LOCAL_COMPLETED' if code==0 else 'LOCAL_FAILED','returncode':code,'streams_exposed':False}

def cli_local_entry():
    """All product Python CLIs except --help run behind captured local streams.
    The env marker is routing, never a sandbox or authentication mechanism.
    """
    try:
        need(os.environ.get('YE1_PRIVACY_CONTROLLED_RUN')=='1','CONTROLLED_ADAPTER_REQUIRED')
        root=os.environ.get('YE1_PRIVACY_PROJECT');need(root,'PROJECT_CHOICE_REQUIRED')
        c,_=load(root);host_check(root,c['mode'],os.environ.get('YE1_PRIVACY_SYNTHETIC_TEST')=='1')
    except Exception:
        print(json.dumps({'status':'BLOCKED_PRIVACY','code':'CONTROLLED_ADAPTER_AND_CHOICE_REQUIRED','sent':False}))
        raise SystemExit(4)


def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self,message):
            print(json.dumps({'status':'BLOCKED_PRIVACY','code':'INVALID_ARGUMENTS','sent':False}));raise SystemExit(4)
    p=SafeParser(description=__doc__);p.add_argument('--project',required=True);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('choose');a.add_argument('--choice',required=True);a.add_argument('--evidence');a.add_argument('--test-only',action='store_true')
    s.add_parser('status')
    for name in ('check','export'):
        a=s.add_parser(name);a.add_argument('--file',action='append',required=True);a.add_argument('--platform',required=True);a.add_argument('--model',required=True);a.add_argument('--purpose',required=True);a.add_argument('--test-only',action='store_true')
        if name=='export':a.add_argument('--out',required=True)
    a=p.parse_args()
    try:
        if a.cmd=='choose':r=save_choice(a.project,read(a.choice),read(a.evidence) if a.evidence else None,a.test_only)
        elif a.cmd=='status':
            c,h=load(a.project);r={'status':'CHOICE_PRESENT','mode':c['mode'],'revision':len(h),'grant_count':len(c['grants']),'host_verified':False}
        elif a.cmd=='check':
            for f in a.file:_,r=authorize(a.project,f,a.platform,a.model,a.purpose,a.test_only)
        else:r=export(a.project,a.file,a.out,a.platform,a.model,a.purpose,a.test_only)
        print(json.dumps(r));return 0
    except Exception as e:
        # No exception text, filenames, user-controlled field names, or traceback to model.
        code=str(e) if isinstance(e,Denied) and re.fullmatch('[A-Z_]+',str(e)) else 'LOCAL_CHECK_FAILED'
        print(json.dumps({'status':'BLOCKED_PRIVACY','code':code,'sent':False}));return 4
if __name__=='__main__':sys.exit(main())
