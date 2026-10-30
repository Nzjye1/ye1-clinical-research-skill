"""Installed font coverage with the existing plotting interpreter; no installs/settings edits."""
import json,os,subprocess,sys,tempfile,shutil,uuid
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def _scratch(prefix, root=None):
    """Windows child processes use ordinary project-inherited ACLs.

    Some managed Windows executors cannot use the current-user-only DACL made
    by tempfile's mode-0700 directories. Never change that DACL or retry it with
    elevated permissions: create a new cache inside the selected output/project.
    macOS/Linux retain their existing private temporary-directory behavior.
    """
    if os.name != 'nt':
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            yield temporary
        return
    parent=Path(root or os.environ.get('YE1_TASK_TMP') or Path.cwd()).resolve()
    if not parent.is_dir():raise OSError('Existing task/output scratch directory required')
    directory=parent/('.'+prefix+uuid.uuid4().hex)
    directory.mkdir()  # ordinary inherited project ACL; never chmod/ACL edits
    try:
        yield str(directory)
    finally:
        # Delete only this newly created, exact child, without recursive path
        # discovery, shell interpolation, chmod retries, or following a link.
        if directory.is_symlink() or directory.resolve().parent!=parent:
            raise OSError('Font scratch path changed; preserved for local review')
        shutil.rmtree(directory)

def installed_ttf(path,text):
    """Read Unicode cmap and family from an existing SFNT TTF/OTF using stdlib.
    Unsupported font containers are left to an optional existing font backend.
    """
    import struct
    raw=Path(path).read_bytes()
    if raw[:4] not in {b'\x00\x01\x00\x00',b'OTTO',b'true'}:raise ValueError('Unsupported font container')
    u16=lambda at:struct.unpack_from('>H',raw,at)[0]
    u32=lambda at:struct.unpack_from('>I',raw,at)[0]
    tables={raw[at:at+4]:(u32(at+8),u32(at+12)) for at in range(12,12+16*u16(4),16)}
    cmap=tables[b'cmap'][0];covered=set();needed={ord(c) for c in text if not c.isspace()}
    for i in range(u16(cmap+2)):
        entry=cmap+4+8*i;platform,encoding=u16(entry),u16(entry+2)
        if platform!=0 and not (platform==3 and encoding in {1,10}):continue
        sub=cmap+u32(entry+4);fmt=u16(sub)
        if fmt==12:
            groups=[(u32(k),u32(k+4),u32(k+8)) for k in range(sub+16,sub+16+12*u32(sub+12),12)]
            for cp in needed:
                if any(start<=cp<=end and glyph+cp-start!=0 for start,end,glyph in groups):covered.add(cp)
        elif fmt==4:
            n=u16(sub+6)//2;ends=sub+14;starts=ends+2*n+2;deltas=starts+2*n;ranges=deltas+2*n
            for cp in needed:
                if cp>65535:continue
                for k in range(n):
                    if u16(starts+2*k)<=cp<=u16(ends+2*k):
                        delta=u16(deltas+2*k);off=u16(ranges+2*k)
                        gid=u16(ranges+2*k+off+2*(cp-u16(starts+2*k))) if off else (cp+delta)%65536
                        if off and gid:gid=(gid+delta)%65536
                        if gid:covered.add(cp)
                        break
    if not needed<=covered:raise ValueError('Installed font lacks requested glyphs')
    at=tables[b'name'][0];storage=at+u16(at+4);families=[]
    for k in range(at+6,at+6+12*u16(at+2),12):
        platform,encoding,language,name,length,offset=struct.unpack_from('>6H',raw,k)
        if name==1:
            try:family=raw[storage+offset:storage+offset+length].decode('utf-16-be' if platform in {0,3} else 'mac_roman')
            except UnicodeError:continue
            families.append((language!=0x409,platform!=3,family))
    if not families:raise ValueError('Font family unavailable')
    return {'family':sorted(families)[0][2],'path':str(Path(path).resolve()),'glyphs_checked':len(needed),'coverage_backend':'stdlib SFNT cmap'}

def select(text, python=None, *, scratch_root=None):
    candidates=[os.environ.get('YE1_FONT_PATH')]
    if sys.platform=='darwin' and not os.environ.get('YE1_FONT_PATH'):candidates.append('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
    for candidate in candidates:
        if not candidate:continue
        try:return installed_ttf(candidate,text)
        except (OSError,ValueError,KeyError,__import__('struct').error):pass
    executable=python or os.environ.get('DOCTOR_PAPER_GRAPHICS_PYTHON') or sys.executable
    # An explicit existing interpreter is used, not a filesystem-wide runtime scan.
    code='''import json,sys
from matplotlib import font_manager,ft2font
from pathlib import Path
text=sys.stdin.read(); needed={ord(c) for c in text if not c.isspace()}
import os
candidates=[Path(os.environ['YE1_FONT_PATH'])] if os.environ.get('YE1_FONT_PATH') else []
if sys.platform=='darwin':candidates.append(Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
for name in ['Noto Sans CJK SC','Microsoft YaHei','SimHei','Arial Unicode MS','DejaVu Sans']:
 try:candidates.append(Path(font_manager.findfont(name,fallback_to_default=False)))
 except ValueError:pass
for path in dict.fromkeys(candidates):
 try:
  f=ft2font.FT2Font(str(path))
  if needed.issubset(f.get_charmap()):
   print(json.dumps({'family':f.family_name,'path':str(path.resolve()),'glyphs_checked':len(needed)}));sys.exit(0)
 except (RuntimeError,OSError):pass
sys.exit('No existing font covers all requested text')
'''
    with _scratch('ye1-font-probe-',scratch_root) as tmp:
        env={**os.environ,'MPLCONFIGDIR':tmp,'PYTHONIOENCODING':'utf-8'}
        result=subprocess.run([executable,'-B','-c',code],input=text,text=True,encoding='utf-8',capture_output=True,env=env,timeout=30)
    if result.returncode:raise OSError('Font coverage unavailable; retain text and leave DOCX/PDF pending: '+result.stderr.strip())
    return json.loads(result.stdout)

@contextmanager
def configured(font, *, scratch_root=None):
    """Scope fontconfig to this subprocess task, including the selected existing directory."""
    import xml.sax.saxutils
    with _scratch('ye1-fontconfig-',scratch_root) as tmp:
        dirs=[str(Path(font['path']).parent)]
        if sys.platform=='darwin':dirs+=['/System/Library/Fonts','/System/Library/Fonts/Supplemental']
        cfg=Path(tmp)/'fonts.conf'
        cfg.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "fonts.dtd"><fontconfig>'+''.join('<dir>'+xml.sax.saxutils.escape(d)+'</dir>' for d in dict.fromkeys(dirs))+'<cachedir>'+tmp+'/cache</cachedir></fontconfig>')
        old=os.environ.get('FONTCONFIG_FILE');os.environ['FONTCONFIG_FILE']=str(cfg)
        try:yield
        finally:
            if old is None:os.environ.pop('FONTCONFIG_FILE',None)
            else:os.environ['FONTCONFIG_FILE']=old
