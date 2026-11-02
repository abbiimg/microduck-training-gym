"""Build separate KiCad projects with per-instance author STEP models.

Run prepare/attach with KiCad's pcbnew Python, geometry with CadQuery/OCP.
Preserves the integrated source projects and source geometry. Local dimensions
are unchanged; footprint origins map from author /39.37 to native exact mil.
"""
from pathlib import Path
import argparse,hashlib,json,math,re,shutil,subprocess,sys
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('stage',choices=['prepare','geometry','attach'])
p.add_argument('--candidate',required=True)
p.add_argument('--overwrite-generated',action='store_true')
a=p.parse_args();root=Path(__file__).resolve().parents[1]
base=a.candidate.removesuffix('-transition-hypothesis')
assert base in ['imu_to_dxl','imu_to_dxl_1V0A','wire_hub_1V0A','POGO_PIN_1V0A']
source=root/'editing/kicad-integrated'/a.candidate;dest=root/'editing/kicad-models-attached'/a.candidate
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2),encoding='utf-8')
def protect_generated_file(path,expected_hash,allow_overwrite):
    if not path.exists():return
    if expected_hash is not None and sha(path)==expected_hash:return
    if not allow_overwrite:raise RuntimeError('Generated file was edited or lacks a completed receipt; preserve it before --overwrite-generated: '+str(path))
def no_models(text):
    # Remove complete FP model expressions only; parentheses in strings ignored.
    tokens=list(re.finditer(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text));spans=[]
    for i,t in enumerate(tokens):
        if t.group()!='(' or i+1>=len(tokens) or tokens[i+1].group()!='model':continue
        depth=0
        for tail in tokens[i:]:
            if tail.group()=='(':depth+=1
            elif tail.group()==')':depth-=1
            if depth==0:spans.append((t.start(),tail.end()));break
    for start,end in reversed(spans):text=text[:start]+text[end:]
    return re.sub(r'\s+',' ',text).strip()
planpath=dest/'model-attachment-audit.json'
if a.stage=='prepare':
    import pcbnew as k
    if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve user edits before --overwrite-generated')
    shutil.copytree(source,dest,dirs_exist_ok=True)
    modeldir=dest/'models';modeldir.mkdir(exist_ok=True)
    board=k.LoadBoard(str(source/(base+'.kicad_pcb')))
    posepath=root/'audit/model-pose-independent-review.json';pose=next(b for b in json.loads(posepath.read_text())['boards'] if b['candidate']==base)
    cm_path=root/'recovered/author-step-components'/base/'component-manifest.json';cm=json.loads(cm_path.read_text())
    refs={f.GetReference():f for f in board.GetFootprints()};rows=[]
    for item in pose['placed_instances']:
        ref=item['reference'];fp=refs[ref];comp=next(c for c in cm['components'] if c['reference']==ref)
        assert len(fp.Models())==0 and abs(fp.GetOrientationDegrees())<1e-9,'Calibration limited to current baked-orientation footprints'
        assert fp.IsFlipped()==(item['source_layer']==2)
        xy=item['source_xy_mil'];native=[fp.GetPosition().x/1e6,-fp.GetPosition().y/1e6]
        assert max(abs(native[i]-xy[i]*.0254) for i in range(2))<=.00000051
        placed=root/'recovered/author-step-components'/base/comp['step_file'];assert sha(placed)==comp['step_sha256']
        rows.append({'reference':ref,'source_placed_step':str(placed.relative_to(root)),'source_placed_sha256':sha(placed),
            'source_model_id':comp['metadata_model_id'],'source_model_title':comp['metadata_model_title'],
            'author_footprint_origin_mm':item['source_frame_origin_author_mm'],
            'native_xy_export_mm':native,'native_angle_degrees':fp.GetOrientationDegrees(),'bottom':fp.IsFlipped(),
            'local_model_file':'models/'+ref+'.step','model_path':'${KIPRJMOD}/models/'+ref+'.step'})
    missing=cm['missing_references'];assert missing==(['J3'] if base=='imu_to_dxl_1V0A' else [])
    audit={'schema':'microduck-kicad-author-models/v1','candidate':a.candidate,'base_candidate':base,
        'parent_board':str((source/(base+'.kicad_pcb')).relative_to(root)),'parent_board_sha256':sha(source/(base+'.kicad_pcb')),
        'pose_review_sha256':sha(posepath),'component_manifest_sha256':sha(cm_path),
        'unchanged_project_files':{n:sha(source/n) for n in [base+'.kicad_pro',base+'.kicad_sch',base+'.kicad_dru','fp-lib-table','sym-lib-table']},
        'native_version':k.Version(),'nominal_native_board_thickness_mm':board.GetDesignSettings().GetBoardThickness()/1e6,
        'coordinate_policy':'Per-instance author geometry translated by negative author footprint surface origin; bottom inverse Rx180; native footprints currently have zero angle with source rotation baked in geometry. No scaling of local model dimensions. KiCad places local models at its native top/bottom model datum. XY origins use current exact-mil positions rather than globally scaling the author assembly.',
        'author_source_surface_mm':{'bottom':0,'top':pose['source_physical_stack_mm_div39_37']},
        'source_outline_fit_qualified':False,'vendor_dimensions_qualified':False,'manufacturing_ready':False,
        'missing_models':missing,'missing_model_reason':'Revised J3 absent from author STEP and placed 3D Model Title explicitly blank; device default not substituted' if missing else None,
        'models':rows,'attached':False}
    write(planpath,audit);print(json.dumps({'candidate':a.candidate,'planned':len(rows),'missing':missing}),flush=True)
elif a.stage=='geometry':
    import cadquery as cq
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    audit=json.loads(planpath.read_text())
    # Preflight every destination before changing any model. This protects
    # direct edits to local STEP files as well as interrupted earlier builds.
    for row in audit['models']:
        protect_generated_file(dest/row['local_model_file'],row.get('local_model_sha256'),a.overwrite_generated)
    def bounds(s):
        b=Bnd_Box();BRepBndLib.AddOptimal_s(s.wrapped,b,False,False);return list(b.Get())
    for row in audit['models']:
        src=root/row['source_placed_step'];assert sha(src)==row['source_placed_sha256']
        original=cq.importers.importStep(str(src)).val();o=row['author_footprint_origin_mm']
        local=original.translate(tuple(-v for v in o))
        if row['bottom']:local=local.rotate((0,0,0),(1,0,0),180)
        path=dest/row['local_model_file'];cq.exporters.export(local,str(path),exportType='STEP')
        reopened=cq.importers.importStep(str(path)).val();assert reopened.isValid() and len(reopened.Solids())==len(original.Solids())
        assert max(abs(x-y) for x,y in zip(bounds(local),bounds(reopened)))<1e-6
        assert abs(original.Volume()-reopened.Volume())<max(1e-6,abs(original.Volume())*1e-7)
        row.update(local_model_sha256=sha(path),local_model_bounds_mm=bounds(reopened),solids=len(reopened.Solids()),volume_mm3=reopened.Volume())
    audit['local_geometry_generated']=True;write(planpath,audit);print(json.dumps({'candidate':a.candidate,'local_models':len(audit['models'])}),flush=True)
else:
    import pcbnew as k
    audit=json.loads(planpath.read_text());assert audit['local_geometry_generated']
    if audit['attached']:assert sha(dest/(base+'.kicad_pcb'))==audit['board_sha256'],'Generated board was edited; preserve changes before rebuilding'
    assert sha(source/(base+'.kicad_pcb'))==audit['parent_board_sha256'],'Parent PCB changed; prepare a new plan before rebuilding'
    for n,h in audit['unchanged_project_files'].items():assert sha(dest/n)==h,'Project settings were edited; preserve changes before preparing a new copy'
    library_hashes=audit.get('generated_library_hashes',{})
    if not library_hashes and audit['attached'] and (dest/'model-export-validation.json').exists():
        library_hashes=json.loads((dest/'model-export-validation.json').read_text()).get('local_library_sha256',{})
    for n,h in library_hashes.items():protect_generated_file(dest/n,h,a.overwrite_generated)
    path=dest/(base+'.kicad_pcb');board=k.LoadBoard(str(source/path.name));fps={f.GetReference():f for f in board.GetFootprints()}
    for row in audit['models']:
        assert sha(dest/row['local_model_file'])==row['local_model_sha256']
        fp=fps[row['reference']];assert len(fp.Models())==0
        model=k.FP_3DMODEL();model.m_Filename=row['model_path'];fp.Models().push_back(model)
    # SaveBoard also expands/writes the project defaults; direct board-plugin
    # serialization keeps the source .pro byte-identical.
    k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(path),board)
    assert no_models(path.read_text())==no_models((source/path.name).read_text()),'Non-model PCB data changed'
    plugin=k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP)
    def model_signature(fp):return [(m.m_Filename,tuple(m.m_Offset),tuple(m.m_Rotation),tuple(m.m_Scale),m.m_Show) for m in fp.Models()]
    for ref,fp in fps.items():
        if ref=='SOURCE_BOARD_PADS':continue
        libfp=k.FOOTPRINT(fp);libfp.SetPosition(k.VECTOR2I(0,0));libfp.SetPath(k.KIID_PATH());libfp.SetReference('REF**')
        for pad in libfp.Pads():pad.SetNetCode(0)
        plugin.FootprintSave(str(dest/'RecoveredLayout.pretty'),libfp)
        loaded=plugin.FootprintLoad(str(dest/'RecoveredLayout.pretty'),ref);scratch=k.BOARD();scratch.Add(loaded);loaded.SetPosition(fp.GetPosition())
        if loaded.GetLayer()!=fp.GetLayer():loaded.Flip(fp.GetPosition(),k.FLIP_DIRECTION_TOP_BOTTOM)
        loaded.SetOrientation(fp.GetOrientation());assert model_signature(loaded)==model_signature(fp),(ref,'Library model reload differs')
    for n,h in audit['unchanged_project_files'].items():assert sha(dest/n)==h
    audit.update(attached=True,attached_models=len(audit['models']),non_model_board_data_unchanged=True,library_model_reload_verified=True,board_sha256=sha(path),
        generated_library_hashes={str(f.relative_to(dest)).replace('\\','/'):sha(f) for f in sorted((dest/'RecoveredLayout.pretty').glob('*.kicad_mod'))})
    write(planpath,audit)
    cli=Path(sys.executable).resolve().parent/'kicad-cli.exe'
    if not cli.exists():cli=Path('/usr/bin/kicad-cli')
    for fmt in ['step','glb']:
        output=dest/('assembly-review.'+fmt)
        run=subprocess.run([str(cli),'pcb','export',fmt,'--force','--user-origin','0x0mm','--output',str(output),str(path)],capture_output=True,text=True,timeout=180)
        (dest/('assembly-review-'+fmt+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8');assert run.returncode==0,run.stdout+run.stderr
        audit[fmt+'_export']={'file':output.name,'sha256':sha(output)}
    write(planpath,audit);print(json.dumps({'candidate':a.candidate,'attached':len(audit['models']),'board_data_unchanged':True}),flush=True)
