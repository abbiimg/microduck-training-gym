"""Read-only regression of recovered silk copies, source files, and copper state."""
from pathlib import Path
import argparse,json,hashlib,collections
import pcbnew as k
p=argparse.ArgumentParser();p.add_argument('--project-root',type=Path,default=Path('editing/kicad-integrated'));a=p.parse_args()
root=Path(__file__).resolve().parents[1];tree=a.project_root if a.project_root.is_absolute() else root/a.project_root
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def point(p):return p.x,p.y
def polygon(poly):
    def ring(r):return tuple(point(r.CPoint(i)) for i in range(r.PointCount()))
    return tuple((ring(poly.COutline(i)),tuple(ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i)))) for i in range(poly.OutlineCount()))
def graphic(g):
    result={'shape':int(g.GetShape()),'layer':int(g.GetLayer()),'width':g.GetWidth(),'fill_mode':int(g.GetFillMode())}
    if g.GetShape()==k.SHAPE_T_POLY:result['polygon']=polygon(g.GetPolyShape())
    else:
        result.update(start=point(g.GetStart()),end=point(g.GetEnd()))
        if g.GetShape()==k.SHAPE_T_ARC:result['mid']=point(g.GetArcMid())
    return result
def canonical(value):return json.dumps(value,sort_keys=True)
def copper(b):
    pads={pad.m_Uuid.AsString():(fp.GetReference(),pad.GetNumber(),pad.GetNetname(),point(pad.GetPosition()),point(pad.GetDrillSize()),pad.GetLayerSet().FmtHex(),pad.GetLocalSolderMaskMargin(),pad.GetLocalSolderPasteMargin(),pad.GetLocalSolderPasteMarginRatio(),tuple((layer,polygon(pad.GetEffectivePolygon(layer))) for layer in [k.F_Cu,k.B_Cu] if pad.IsOnLayer(layer))) for fp in b.GetFootprints() for pad in fp.Pads()}
    tracks={t.m_Uuid.AsString():(t.GetNetname(),int(t.GetLayer()),point(t.GetStart()),point(t.GetEnd()),t.GetWidth(k.F_Cu) if isinstance(t,k.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,k.PCB_VIA) else None,point(t.GetMid()) if isinstance(t,k.PCB_ARC) else None) for t in b.GetTracks()}
    zones={z.m_Uuid.AsString():(z.GetNetname(),int(z.GetLayer()),polygon(z.GetFilledPolysList(z.GetLayer()))) for z in b.Zones()}
    graphics={g.m_Uuid.AsString():graphic(g) for g in b.GetDrawings() if isinstance(g,k.PCB_SHAPE) and g.IsOnCopperLayer()}
    return pads,tracks,zones,graphics
results=[];plugin=k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP)
for folder in sorted(tree.iterdir()):
    if not folder.is_dir():continue
    audit=json.loads((folder/'silkscreen-recovery-audit.json').read_text(encoding='utf-8'));source=root/audit['parent_board'];path=folder/source.name;name=source.stem
    assert sha(source)==audit['parent_sha256'];assert sha(path)==audit['engineering_board_sha256']
    replay=root/'editing/recovered-community'/name/'replayed-project.json';assert sha(replay)==audit['replay_sha256']
    aux=[name+'.kicad_pro',name+'.kicad_sch',name+'.kicad_dru','fp-lib-table','sym-lib-table','Recovered.kicad_sym']
    for filename in aux:
        if (source.parent/filename).exists():assert sha(source.parent/filename)==sha(folder/filename),(folder,filename)
    before=k.LoadBoard(str(source));board=k.LoadBoard(str(path));assert copper(before)==copper(board),(folder,'Copper changed')
    native={g.m_Uuid.AsString():g for fp in board.GetFootprints() for g in fp.GraphicalItems() if isinstance(g,k.PCB_SHAPE)}
    for item in audit['native_graphic_objects']:assert canonical(graphic(native[item['native_uuid']]))==canonical(item['expected'])
    fps={fp.GetReference():fp for fp in board.GetFootprints()}
    for item in audit['references']:
        b=item['source_record']['data'];field=fps[item['reference']].Reference()
        assert field.GetText()==b['value'] and field.IsVisible() and point(field.GetPosition())==tuple(item['native_position_nm']) and int(field.GetLayer())==item['native_layer']
        assert point(field.GetTextSize())==(round(b['fontSize']*.0254*1e6),)*2 and field.GetTextThickness()==round(b['strokeWidth']*.0254*1e6)
        assert field.IsMirrored()==bool(b.get('mirror')) and field.IsBold()==bool(b.get('bold')) and field.IsItalic()==bool(b.get('italic'))
        assert field.GetHorizJustify()==k.GR_TEXT_H_ALIGN_LEFT and field.GetVertJustify()==k.GR_TEXT_V_ALIGN_BOTTOM
        assert abs((field.GetTextAngle().AsDegrees()-item['native_angle_degrees']+180)%360-180)<1e-7
    def silk(fp):return collections.Counter(canonical(graphic(g)) for g in fp.GraphicalItems() if isinstance(g,k.PCB_SHAPE) and g.GetLayer() in [k.F_SilkS,k.B_SilkS])
    for ref,fp in fps.items():
        if ref=='SOURCE_BOARD_PADS':continue
        loaded=plugin.FootprintLoad(str(folder/'RecoveredLayout.pretty'),ref);assert loaded;scratch=k.BOARD();scratch.Add(loaded);loaded.SetPosition(fp.GetPosition())
        if loaded.GetLayer()!=fp.GetLayer():loaded.Flip(fp.GetPosition(),k.FLIP_DIRECTION_TOP_BOTTOM)
        loaded.SetOrientation(fp.GetOrientation());assert silk(loaded)==silk(fp),(folder,ref,'Library graphics changed')
    drc=json.loads((folder/'drc-silkscreen.json').read_text());assert not drc['schematic_parity'] and not drc['unconnected_items']
    result={'candidate':folder.name,'copper_and_masks_unchanged':True,'source_project_rule_schematic_hashes_match':True,'native_graphics_checked':len(audit['native_graphic_objects']),'reference_styles_checked':len(audit['references']),'library_graphics_verified':True,'schematic_parity_findings':0,'airwires':0,'manufacturing_ready':False}
    (folder/'silkscreen-validation.json').write_text(json.dumps(result,indent=2));results.append(result)
assert len(results)==5,('Expected all five variants',len(results))
(tree/'silkscreen-validation-summary.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
