"""Restore hash-verified optional assets without overwriting edited files."""
from pathlib import Path
import argparse,hashlib,json,shutil,tempfile,urllib.request
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path);p.add_argument('--category',action='append');p.add_argument('--download-original-cad',action='store_true');a=p.parse_args()
manifest=json.loads((root/'DEFERRED-ASSETS.json').read_text(encoding='utf-8'))
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
rows=manifest['omitted_files']
if a.download_original_cad:rows=[r for r in rows if r['path']==manifest['original_CAD_archive']['path']]
elif a.category:rows=[r for r in rows if r['category'] in a.category]
source=a.source or Path(manifest['original_full_package'])
restored=present=0
for row in rows:
    rel=Path(row['path'])
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Invalid manifest path: '+str(rel))
    target=root/rel
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('Destination leaves the repository: '+str(target))
    if target.exists():
        if not target.is_file() or sha(target)!=row['sha256']:raise RuntimeError('Preserve modified destination before restoring: '+str(target))
        present+=1;continue
    target.parent.mkdir(parents=True,exist_ok=True)
    original=source/rel
    if original.is_file():
        if original.stat().st_size!=row['bytes'] or sha(original)!=row['sha256']:raise RuntimeError('Source size/hash mismatch: '+str(original))
        with original.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024)
    elif a.download_original_cad:
        with tempfile.TemporaryDirectory() as temp:
            download=Path(temp)/'original-cad.zip'
            with urllib.request.urlopen(manifest['original_CAD_archive']['release_url'],timeout=60) as src,download.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024)
            if download.stat().st_size!=row['bytes'] or sha(download)!=row['sha256']:raise RuntimeError('Downloaded archive did not match the recorded source')
            with download.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,4*1024*1024)
    else:raise FileNotFoundError('Provide the retained full package using --source; missing '+str(original))
    if target.stat().st_size!=row['bytes'] or sha(target)!=row['sha256']:raise RuntimeError('Restored file size/hash mismatch: '+str(target))
    restored+=1
print(json.dumps({'restored':restored,'already_present':present,'files_checked':len(rows),'overwritten_files':0},indent=2))
