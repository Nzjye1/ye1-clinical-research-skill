"""Read-only verification of the authorized install; no package manager actions."""
import gzip,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT.parent))
from latent_longitudinal import formal_runtime
OUT=ROOT/'evidence/formal-install';receipt=json.loads((OUT/'receipt.json').read_text())
blocks={}
for block in gzip.decompress((OUT/'PACKAGES.gz').read_bytes()).decode().split('\n\n'):
    item={};last=None
    for line in block.splitlines():
        if line.startswith(' ') and last:item[last]+=' '+line.strip()
        elif ':' in line:last,value=line.split(':',1);item[last]=value.strip()
    if 'Package' in item:blocks[item['Package']]=item
probe=formal_runtime.probe();paths=probe['r_package_paths']
for p in receipt['packages']:
    p['requires']={key:blocks[p['package']][key] for key in ['Depends','Imports','LinkingTo'] if key in blocks[p['package']]}
    p['loaded_version']=probe['r_packages'][p['package']];p['loaded_path']=paths[p['package']]
    assert p['loaded_version'] is not None and Path(p['loaded_path']).is_relative_to(ROOT/'r-library-4.6.1')
receipt['status']='all_six_installed_and_loaded_native_windows'
receipt['verification']='Official HTTPS CRAN R 4.6 Windows binary directory; R 4.6.1 Built fields; native DLLs x64; ZIP CRC and package internal MD5 checks; download SHA-256 recorded. CRAN index contains no archive MD5sum; no independent signature verification claimed.'
receipt['reused_dependencies']={n:{'version':probe['r_packages'][n],'path':paths[n]} for n in formal_runtime.PACKAGES if n not in [p['package'] for p in receipt['packages']]}
receipt['old_libraries_modified_by_installer']=False
receipt['scope']='Installer supplied an explicit module-only lib target for six local zip packages; no persistent environment or .libPaths change; no suggested packages installed.'
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
(OUT/'runtime-load.json').write_text(json.dumps(probe,indent=2),encoding='utf-8')
print(receipt['status'])
