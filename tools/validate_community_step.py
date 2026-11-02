from pathlib import Path
import hashlib,json,sys
import cadquery as cq
root=Path('outputs/microduck-assets').resolve()
repo=root/'community/microduck-step-reconstruction'
manifest=json.loads((repo/'docs/model_manifest.json').read_text(encoding='utf-8'))
results=[]
for part in manifest['parts']:
    path=repo/part['step']
    record={'part':part['name'],'file':str(path.relative_to(root)),
            'sha256_matches_author':hashlib.sha256(path.read_bytes()).hexdigest()==part['step_sha256']}
    try:
        shape=cq.importers.importStep(str(path)).val()
        box=shape.BoundingBox()
        record.update(valid=shape.isValid(),solids=len(shape.Solids()),volume_mm3=shape.Volume(),dimensions_mm=[box.xlen,box.ylen,box.zlen])
    except Exception as error:
        record['error']=str(error)
    results.append(record)
    print(part['name'],record.get('valid'),record.get('solids'),record['sha256_matches_author'],flush=True)
(root/'audit/community-step-validation.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('VALID_SOLIDS',sum(r.get('valid',False) and r.get('solids')==1 for r in results),'/',len(results),flush=True)
