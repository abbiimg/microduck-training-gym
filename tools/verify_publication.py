"""Verify hydrated publication files against their SHA256 inventory."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'PUBLICATION-MANIFEST.json').read_text(encoding='utf-8'))
failures=[]
for row in manifest['files']:
    path=root/row['path']
    if not path.is_file():failures.append({'path':row['path'],'reason':'missing'});continue
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    if path.stat().st_size!=row['bytes'] or h.hexdigest()!=row['sha256']:
        failures.append({'path':row['path'],'reason':'size/hash mismatch; check git lfs pull and checkout line endings'})
print(json.dumps({'files_checked':len(manifest['files']),'passed':not failures,'failures':failures},indent=2))
sys.exit(bool(failures))
