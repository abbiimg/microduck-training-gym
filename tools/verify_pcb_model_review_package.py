"""Verify portable KiCad/Blender review files and unchanged native DRC counts.

Fast standard-library check; heavy CAD receipts are checked separately by
verify_kicad_model_integrity.py. Mesh bounds are not a physical-fit test.
"""
from pathlib import Path
import argparse,collections,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def no_models(text):
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text)
    result=[];i=0
    while i<len(tokens):
        if tokens[i]=='(' and i+1<len(tokens) and tokens[i+1]=='model':
            depth=1;i+=2
            while depth:
                if tokens[i]=='(':depth+=1
                elif tokens[i]==')':depth-=1
                i+=1
        else:result.append(tokens[i]);i+=1
    return result
def verify(candidate):
    folder=ROOT/'editing/kicad-models-attached'/candidate;audit=read(folder/'model-attachment-audit.json');base=audit['base_candidate']
    assert no_models((folder/(base+'.kicad_pcb')).read_text())==no_models((ROOT/audit['parent_board']).read_text())
    fresh=read(folder/'drc-models.json');parent=read(ROOT/'editing/kicad-integrated'/candidate/'drc-silkscreen.json')
    counts=lambda report:dict(collections.Counter(v['type'] for v in report['violations']))
    assert counts(fresh)==counts(parent) and not fresh['unconnected_items'] and not fresh['schematic_parity']
    blenderpath=folder/'blender-model-review.json';blender=read(blenderpath);receipt=read(folder/'model-export-validation.json')
    assert blender['source_glb_sha256']==audit['glb_export']['sha256']==sha(folder/blender['source_glb'])
    assert sha(folder/blender['blend_file'])==blender['blend_sha256'] and sha(folder/blender['preview_file'])==blender['preview_sha256']
    visual=read(ROOT/'audit/pcb-model-visual-review.json')
    viewed=next(v for v in visual['previews'] if v['candidate']==candidate)
    assert viewed['sha256']==blender['preview_sha256'] and viewed['framing_and_visible_geometry_reviewed']
    assert blender['unit_scale']==1 and blender['coordinate_units']=='metres' and blender['mesh_objects']>0
    exact=receipt['native_export_assembly_bounds_mm'];mesh=blender['imported_world_bounds_mm'][0]+blender['imported_world_bounds_mm'][1]
    error=max(abs(x-y) for x,y in zip(exact,mesh));assert error<.02,(candidate,'GLB/Blender bounds discrepancy',error)
    return {'candidate':candidate,'models':len(audit['models']),'drc_counts':counts(fresh),'airwires':0,'schematic_parity':0,
        'blender_mesh_objects':blender['mesh_objects'],'blender_vs_step_max_bounds_difference_mm':error,
        'blender_review_sha256':sha(blenderpath),'drc_report_sha256':sha(folder/'drc-models.json'),'passed':True}
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',action='append');a=p.parse_args()
results=[verify(c) for c in (a.candidate or ['imu_to_dxl','imu_to_dxl_1V0A','imu_to_dxl_1V0A-transition-hypothesis','wire_hub_1V0A','POGO_PIN_1V0A'])]
report={'schema':'microduck-pcb-model-review-package/v1','passed':True,'projects':results,'bounds_tolerance_mm':.02,
    'scope':'Exact non-model PCB tokens, unchanged native DRC counts, portable model/export hashes and Blender/STEP bounds; CAD geometry receipts verified separately',
    'source_geometry_and_physical_fit_qualified':False,'manufacturing_ready':False}
(ROOT/'audit/pcb-model-review-package-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
