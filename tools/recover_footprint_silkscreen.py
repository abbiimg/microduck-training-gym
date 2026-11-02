"""Recover explicit source silk geometry/positioned references in engineering copies.

Copper, mask, paste and model layers are untouched. Source typography is mapped
to editable KiCad stroke text; exact source glyph metrics remain unqualified.
"""
from pathlib import Path
import argparse,collections,hashlib,json,math,shutil,subprocess,sys
import pcbnew as k
from shapely.geometry import Point
from shapely import affinity
p=argparse.ArgumentParser();p.add_argument('--reader',required=True,type=Path);p.add_argument('--candidate',required=True);p.add_argument('--overwrite-generated',action='store_true');p.add_argument('--source-root',type=Path);p.add_argument('--destination-root',type=Path);p.add_argument('--drc-timeout',type=int,default=180);a=p.parse_args()
sys.path.insert(0,str(a.reader.resolve()))
from lceda_pcb_geometry import transform,polygon,arc_points
root=Path(__file__).resolve().parents[1];MIL=.0254
name=a.candidate.removesuffix('-transition-hypothesis')
source=(a.source_root if a.source_root.is_absolute() else root/a.source_root)/a.candidate if a.source_root else root/'editing'/('kicad-graphic-corrected' if name=='POGO_PIN_1V0A' else 'kicad-source-rules-projected')/a.candidate
assert name in ['imu_to_dxl','imu_to_dxl_1V0A','wire_hub_1V0A','POGO_PIN_1V0A']
dest=((a.destination_root if a.destination_root.is_absolute() else root/a.destination_root) if a.destination_root else root/'editing/kicad-silkscreen-recovered')/a.candidate
if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve edits before --overwrite-generated')
shutil.copytree(source,dest,dirs_exist_ok=True)
boardpath=source/(name+'.kicad_pcb');board=k.LoadBoard(str(boardpath));original=k.LoadBoard(str(boardpath))
replay=root/'editing/recovered-community'/name/'replayed-project.json'
docs=json.loads(replay.read_text(encoding='utf-8'))['documents'];pcb=next(d for d in docs if d['head']['docType']=='PCB');docmap={d['head']['uuid']:d for d in docs}
attrs=collections.defaultdict(dict);designators={}
for record in pcb['records']:
    if record['header']['type']=='ATTR':
        b=record['data'];attrs[b.get('parentId')][b['key']]=b.get('value')
        if b.get('key')=='Designator':designators[b.get('parentId')]=record
override=json.loads((replay.parent/'instance-attributes.json').read_text(encoding='utf-8'))
uidrefs={value.get('Unique ID'):ref for ref,value in override.items() if value.get('Unique ID')}
fps={fp.GetReference():fp for fp in board.GetFootprints()};audit={'candidate':a.candidate,'parent_board':str(boardpath.relative_to(root)),'parent_sha256':hashlib.sha256(boardpath.read_bytes()).hexdigest(),'replay_sha256':hashlib.sha256(replay.read_bytes()).hexdigest(),'recovered_source_objects':[],'native_graphic_objects':[],'references':[],'skipped':[],'copper_mask_paste_changed':False,'manufacturing_ready':False,'typography':'KiCad stroke-font substitution; source content/position/style/anchor/angle/mirror retained; glyph metrics/font parity unqualified'}
def vec(x,y):return k.VECTOR2I(round(x*1e6),round(y*1e6))
def pos(x,y):return vec(x*MIL,-y*MIL)
def world(local,component):
    q=transform(Point(*local),component,component['layerId']==2);return pos(q.x,q.y)
def ring_shape(poly):
    def chain(c):return tuple((c.CPoint(i).x,c.CPoint(i).y) for i in range(c.PointCount()))
    return tuple((chain(poly.COutline(i)),tuple(chain(poly.CHole(i,j)) for j in range(poly.HoleCount(i)))) for i in range(poly.OutlineCount()))
def graphic_shape(g):
    result={'shape':int(g.GetShape()),'layer':int(g.GetLayer()),'width':g.GetWidth(),'fill_mode':int(g.GetFillMode())}
    if g.GetShape()==k.SHAPE_T_POLY:result['polygon']=ring_shape(g.GetPolyShape())
    else:
        result.update(start=(g.GetStart().x,g.GetStart().y),end=(g.GetEnd().x,g.GetEnd().y))
        if g.GetShape()==k.SHAPE_T_ARC:result['mid']=(g.GetArcMid().x,g.GetArcMid().y)
    return result
def canonical(value):return json.dumps(value,sort_keys=True)
def copper_state(b):
    pads={p.m_Uuid.AsString():(fp.GetReference(),p.GetNumber(),p.GetNetname(),p.GetPosition().x,p.GetPosition().y,p.GetDrillSize().x,p.GetDrillSize().y,tuple((layer,ring_shape(p.GetEffectivePolygon(layer))) for layer in [k.F_Cu,k.B_Cu] if p.IsOnLayer(layer))) for fp in b.GetFootprints() for p in fp.Pads()}
    tracks={t.m_Uuid.AsString():(t.GetNetname(),int(t.GetLayer()),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(k.F_Cu) if isinstance(t,k.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,k.PCB_VIA) else None,(t.GetMid().x,t.GetMid().y) if isinstance(t,k.PCB_ARC) else None) for t in b.GetTracks()}
    zones={z.m_Uuid.AsString():(z.GetNetname(),int(z.GetLayer()),ring_shape(z.GetFilledPolysList(z.GetLayer()))) for z in b.Zones()}
    graphics={g.m_Uuid.AsString():graphic_shape(g) for g in b.GetDrawings() if isinstance(g,k.PCB_SHAPE) and g.IsOnCopperLayer()}
    layer_masks={fp.GetReference():[(p.GetNumber(),p.GetLayerSet().FmtHex()) for p in fp.Pads()] for fp in b.GetFootprints()}
    return pads,tracks,zones,graphics,layer_masks
before=copper_state(original)
def add_shape(fp,shape,ref,record):
    fp.Add(shape)
    audit['native_graphic_objects'].append({'reference':ref,'source_type':record['header']['type'],'source_id':record['header']['id'],'native_uuid':shape.m_Uuid.AsString(),'expected':graphic_shape(shape)})
def strokes(path):
    if isinstance(path[0],list):
        for sub in path:yield from strokes(sub)
        return
    if isinstance(path[0],str):raise ValueError('Unexpected special stroke path '+path[0])
    point=tuple(path[:2]);index=2;command='L'
    while index<len(path):
        if isinstance(path[index],str):command=path[index];index+=1
        n=2 if command=='L' else 3;values=path[index:index+n];assert len(values)==n
        end=tuple(values if n==2 else values[1:]);angle=0 if n==2 else values[0]
        if math.dist(point,end)>1e-9:yield point,end,angle
        point=end;index+=n
def make_polyset(geometry):
    out=k.SHAPE_POLY_SET();oi=out.NewOutline()
    for x,y in list(geometry.exterior.coords)[:-1]:out.Append(vec(x,y),oi,-1)
    for interior in geometry.interiors:
        hi=out.NewHole(oi)
        for x,y in list(interior.coords)[:-1]:out.Append(vec(x,y),oi,hi)
    return out
for component_record in pcb['records']:
    if component_record['header']['type']!='COMPONENT':continue
    component=component_record['data'];cid=component_record['header']['id'];aa={**component.get('attrs',{}),**attrs[cid]}
    ref=aa.get('Designator') or uidrefs.get(aa.get('Unique ID')) or 'UNNAMED_'+cid[:6]
    if ref not in fps:continue
    fp=fps[ref];bottom=component['layerId']==2;footprint=docmap[aa['Footprint']]
    layers={}
    for rr in footprint['records']:
        if rr['header']['type']=='LAYER':
            lid=rr['data'].get('layerId')
            if lid is None:lid=json.loads(rr['header']['id'])[1]
            layers[lid]=rr['data']['layerType']
    for record in footprint['records']:
        typ=record['header']['type'];b=record['data'];layer_type=layers.get(b.get('layerId'))
        if typ not in ['POLY','FILL'] or layer_type not in ['TOP_SILK','BOT_SILK']:continue
        if typ=='POLY':assert b.get('polyType','NORMAL')=='NORMAL','Unsupported silk POLY mode'
        top=(layer_type=='TOP_SILK')!=bottom;layer=k.F_SilkS if top else k.B_SilkS
        path=b['path'];paths=path if isinstance(path[0],list) else [path]
        if len(paths)==1 and paths[0][0]=='CIRCLE':
            _,cx,cy,r=paths[0];g=k.PCB_SHAPE(fp);g.SetShape(k.SHAPE_T_CIRCLE);g.SetStart(world((cx,cy),component));g.SetEnd(world((cx+r,cy),component));g.SetLayer(layer);g.SetWidth(round(b['width']*MIL*1e6));g.SetFilled(typ=='FILL');add_shape(fp,g,ref,record)
        elif typ=='FILL':
            assert b.get('fillStyle')=='SOLID'
            geometry=transform(polygon(path),component,bottom);geometry=affinity.scale(geometry,MIL,-MIL,origin=(0,0));assert geometry.is_valid
            g=k.PCB_SHAPE(fp);g.SetShape(k.SHAPE_T_POLY);g.SetPolyShape(make_polyset(geometry));g.SetLayer(layer);g.SetWidth(round(b['width']*MIL*1e6));g.SetFilled(True);add_shape(fp,g,ref,record)
        else:
            for start,end,angle in strokes(path):
                g=k.PCB_SHAPE(fp);g.SetLayer(layer);g.SetWidth(round(b['width']*MIL*1e6))
                if angle:
                    sample=arc_points(start,end,angle);g.SetShape(k.SHAPE_T_ARC);g.SetArcGeometry(world(start,component),world(sample[len(sample)//2],component),world(end,component))
                else:g.SetShape(k.SHAPE_T_SEGMENT);g.SetStart(world(start,component));g.SetEnd(world(end,component))
                add_shape(fp,g,ref,record)
        audit['recovered_source_objects'].append({'reference':ref,'footprint':aa['Footprint'],'type':typ,'source_id':record['header']['id'],'layer_type':layer_type})
    record=designators.get(cid)
    if record:
        b=record['data']
        if b.get('valueVisible') and b.get('layerId') in [3,4] and b.get('x') is not None and b.get('y') is not None and b.get('value')==ref and b.get('origin')=='LEFT_BOTTOM' and not b.get('reverse'):
            field=fp.Reference();field.SetPosition(pos(b['x'],b['y']));field.SetLayer(k.F_SilkS if b['layerId']==3 else k.B_SilkS);field.SetVisible(True);field.SetTextSize(vec(b['fontSize']*MIL,b['fontSize']*MIL));field.SetTextThickness(round(b['strokeWidth']*MIL*1e6));field.SetTextAngle(k.EDA_ANGLE((-b.get('angle',0))%360,k.DEGREES_T));field.SetMirrored(bool(b.get('mirror')));field.SetBold(bool(b.get('bold')));field.SetItalic(bool(b.get('italic')));field.SetHorizJustify(k.GR_TEXT_H_ALIGN_LEFT);field.SetVertJustify(k.GR_TEXT_V_ALIGN_BOTTOM)
            audit['references'].append({'reference':ref,'source_record':record,'native_position_nm':(field.GetPosition().x,field.GetPosition().y),'native_layer':int(field.GetLayer()),'native_angle_degrees':field.GetTextAngle().AsDegrees(),'typography_qualified':False})
        else:audit['skipped'].append({'reference':ref,'type':'Designator','reason':'Unsupported or unpositioned/hidden source text attributes'})
output=dest/boardpath.name;k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(output),board);saved=k.LoadBoard(str(output));assert copper_state(saved)==before,'Copper/pad/layer geometry changed'
savedfps={fp.GetReference():fp for fp in saved.GetFootprints()}
savedgraphics={g.m_Uuid.AsString():g for fp in saved.GetFootprints() for g in fp.GraphicalItems() if isinstance(g,k.PCB_SHAPE)}
for item in audit['native_graphic_objects']:assert canonical(graphic_shape(savedgraphics[item['native_uuid']]))==canonical(item['expected'])
for item in audit['references']:
    field=savedfps[item['reference']].Reference();assert (field.GetPosition().x,field.GetPosition().y)==tuple(item['native_position_nm']) and int(field.GetLayer())==item['native_layer'] and field.IsVisible()
    assert abs((field.GetTextAngle().AsDegrees()-item['native_angle_degrees']+180)%360-180)<1e-7
plugin=k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP)
def fp_graphics_signature(fp):return collections.Counter(canonical(graphic_shape(g)) for g in fp.GraphicalItems() if isinstance(g,k.PCB_SHAPE) and g.GetLayer() in [k.F_SilkS,k.B_SilkS])
for ref,fp in savedfps.items():
    if ref=='SOURCE_BOARD_PADS':continue
    libraryfp=k.FOOTPRINT(fp);libraryfp.SetPosition(k.VECTOR2I(0,0));libraryfp.SetPath(k.KIID_PATH());libraryfp.SetReference('REF**')
    for pad in libraryfp.Pads():pad.SetNetCode(0)
    plugin.FootprintSave(str(dest/'RecoveredLayout.pretty'),libraryfp)
    loaded=plugin.FootprintLoad(str(dest/'RecoveredLayout.pretty'),ref);scratch=k.BOARD();scratch.Add(loaded);loaded.SetPosition(fp.GetPosition())
    if loaded.GetLayer()!=fp.GetLayer():loaded.Flip(fp.GetPosition(),k.FLIP_DIRECTION_TOP_BOTTOM)
    loaded.SetOrientation(fp.GetOrientation())
    assert fp_graphics_signature(loaded)==fp_graphics_signature(fp),(ref,'Library graphic geometry differs')
audit['saved_copper_and_pad_geometry_verified']=True;audit['library_graphics_reload_verified']=True;audit['engineering_board_sha256']=hashlib.sha256(output.read_bytes()).hexdigest();audit['drc_status']='pending'
(dest/'silkscreen-recovery-audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
drc=dest/'drc-silkscreen.json'
try:run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(drc),str(output)],capture_output=True,text=True,timeout=a.drc_timeout)
except subprocess.TimeoutExpired:
    audit['drc_status']='timed_out';(dest/'silkscreen-recovery-audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8');raise
assert run.returncode==0,run.stderr
report=json.loads(drc.read_text());assert not report['schematic_parity']
audit['drc_counts']=dict(collections.Counter(v['type'] for v in report['violations']));audit['unconnected']=len(report['unconnected_items']);audit['schematic_parity']=report['schematic_parity'];audit['drc_status']='completed'
(dest/'silkscreen-recovery-audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding='utf-8')
(dest/'README.txt').write_text('Explicit source footprint silkscreen recovery copy. Copper/mask/paste/model geometry unchanged. Positioned source Designator content/anchors/style are mapped to KiCad stroke font; exact glyph metrics are unqualified. Source model/construction/paste-layer fills and layer5 board text are intentionally not reclassified. Read ../../../audit/footprint-graphics-review.txt and silkscreen-recovery-audit.json. Manufacturing readiness remains false.\n')
print(json.dumps({'candidate':a.candidate,'source_silk_objects':len(audit['recovered_source_objects']),'native_graphics':len(audit['native_graphic_objects']),'positioned_references':len(audit['references']),'copper_unchanged':True,'library_graphics_verified':True,'drc_counts':audit['drc_counts'],'unconnected':audit['unconnected'],'manufacturing_ready':False}))
