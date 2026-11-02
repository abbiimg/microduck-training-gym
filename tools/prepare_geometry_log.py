"""Remove EDIT_HEAD author/edit envelopes for the strict geometry reader.
Keep every other record unchanged; preserve original recovered archive.
"""
import json,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
for folder in (root/'editing/recovered-community').iterdir():
    if not folder.is_dir():continue
    with zipfile.ZipFile(folder/(folder.name+'.epro2')) as z:
        name=next(n for n in z.namelist() if n.endswith('.epru'))
        lines=z.read(name).decode('utf-8').splitlines()
    kept=[];removed=0
    for line in lines:
        if not line.strip():continue
        header=json.JSONDecoder().raw_decode(line)[0]
        if header.get('type')=='EDIT_HEAD':removed+=1
        else:kept.append(line)
    (folder/'geometry-input.epru').write_text('\n'.join(kept)+'\n',encoding='utf-8')
    (folder/'geometry-input-normalization.json').write_text(json.dumps({'removed_record_type':'EDIT_HEAD','removed_count':removed,'kept_records':len(kept),'design_records_rewritten':False},indent=2))
    print(folder.name,removed,'edit envelopes omitted')
