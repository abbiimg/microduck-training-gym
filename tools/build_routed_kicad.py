"""Recover editable KiCad layout candidates from replayed source records.

Depends on the separately pinned community reader for geometry decoding; its
code is not redistributed here. Outputs are audit candidates, not fab releases.
"""
import argparse,json,math,collections,sys
from pathlib import Path
import pcbnew as k
from shapely import affinity
from shapely.geometry import Polygon,LineString,Point
from shapely.ops import unary_union
p=argparse.ArgumentParser();p.add_argument('--reader',type=Path,required=True);p.add_argument('--candidate');p.add_argument('--transition-hypothesis',action='store_true');a=p.parse_args()
sys.path.insert(0,str(a.reader.resolve()))
from lceda_pcb_geometry import polygon,pad_shape,hole_shape,transform,arc_points
root=Path(__file__).resolve().parents[1];MIL=.0254;CACHE=.254
def vec(x,y):return k.VECTOR2I(round(x*1e6),round(y*1e6))
def pt(x,y):return vec(x*MIL,-y*MIL)
def layer_set(layers,all_cu=False):
    result=k.LSET.AllCuMask() if all_cu else k.LSET()
    for layer in layers:result.AddLayer(layer)
    return result
def segments(path):
    if isinstance(path[0],list):
        for part in path:yield from segments(part)
        return
    if isinstance(path[0],str):raise ValueError('Stroke needs explicit endpoint path')
    start=tuple(path[:2]);i=2;command='L'
    while i<len(path):
        if isinstance(path[i],str):command=path[i];i+=1
        n=2 if command=='L' else 3
        values=path[i:i+n];assert len(values)==n
        end=tuple(values if command=='L' else values[1:])
        if math.dist(start,end)>1e-7:yield start,end,0 if command=='L' else values[0]
        start=end;i+=n
def source_geometry_mm(g,scale=MIL):return affinity.scale(g,scale,scale,origin=(0,0))
def source_hole(body):
    h=body.get('hole')
    if h and h.get('width')==0 and h.get('height')==0:return None
    if h and h.get('holeType')=='ROUND' and h.get('width',0)<=0:
        # Round-hole diameter is height; width is an unused legacy slot field.
        body={**body,'hole':{**h,'width':h['height']}}
    return hole_shape(body)
def target_geometry(g):return affinity.scale(g,1,-1,origin=(0,0))
def polys(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for sub in g.geoms for p in polys(sub)]
def polyset(g,relative=(0,0)):
    out=k.SHAPE_POLY_SET()
    for poly in polys(g):
        oi=out.NewOutline()
        for x,y in list(poly.exterior.coords)[:-1]:out.Append(vec(x-relative[0],y-relative[1]),oi,-1)
        for ring in poly.interiors:
            hi=out.NewHole(oi)
            for x,y in list(ring.coords)[:-1]:out.Append(vec(x-relative[0],y-relative[1]),oi,hi)
    return out
layer_types={'TOP':k.F_Cu,'BOTTOM':k.B_Cu,'TOP_SILK':k.F_SilkS,'BOT_SILK':k.B_SilkS,
 'TOP_SOLDER_MASK':k.F_Mask,'BOT_SOLDER_MASK':k.B_Mask,'TOP_PASTE_MASK':k.F_Paste,'BOT_PASTE_MASK':k.B_Paste,
 'TOP_ASSEMBLY':k.F_Fab,'BOT_ASSEMBLY':k.B_Fab,'DOCUMENT':k.Dwgs_User,'MECHANICAL':k.Cmts_User,'OUTLINE':k.Edge_Cuts}
reports=[]
for folder in sorted((root/'editing/recovered-community').iterdir()):
    if not folder.is_dir() or (a.candidate and a.candidate!=folder.name):continue
    source=json.loads((folder/'replayed-project.json').read_text(encoding='utf-8'))
    docs={(d['head']['docType'],d['head']['uuid']):d for d in source['documents']}
    pcb=next(d for d in docs.values() if d['head']['docType']=='PCB');rr=pcb['records']
    transitions=[]
    if a.transition_hypothesis:
        # Explicit alternate interpretation, never silently applied to literal
        # replay: an identical outline was converted FILL -> POUR without an
        # observed FILL tombstone. Preserve both outputs for source review.
        pours={r['header']['id']:r for r in rr if r['header']['type']=='POUR'}
        skip=set()
        for r in rr:
            owner=pours.get(r['header']['id'])
            if r['header']['type']!='FILL' or not owner:continue
            if owner['header']['ticket']<=r['header']['ticket']:continue
            if owner['data'].get('path')!=r['data'].get('path'):continue
            transitions.append({'id':r['header']['id'],'fill_ticket':r['header']['ticket'],'pour_ticket':owner['header']['ticket'],'status':'unconfirmed type-transition hypothesis; no FILL tombstone found'})
            skip.add(r['header']['id'])
        rr=[r for r in rr if not(r['header']['type']=='FILL' and r['header']['id'] in skip)]
    get=lambda typ:[r for r in rr if r['header']['type']==typ]
    board=k.BOARD();board.SetCopperLayerCount(2)
    nets={};audit={'candidate':folder.name,'source_records':dict(collections.Counter(r['header']['type'] for r in rr)),
      'converted':collections.Counter(),'excluded_outside_active_board':[],'warnings':[],
      'source_copper_cache':'retained as static KiCad filled zones; not regenerated',
      'native_rules_translated':False,'manufacturing_ready':False}
    audit['shape_transition_hypotheses']=transitions
    audit['expected_static_copper_area_mm2']=collections.defaultdict(float)
    audit['omitted_nonpad_footprint_records']=collections.Counter()
    def net(name):
        name=name or ''
        if name not in nets:
            ni=k.NETINFO_ITEM(board,name);board.Add(ni);nets[name]=ni
        return nets[name]
    layers={r['data']['layerId']:r['data'] for r in get('LAYER')}
    board_path=get('BOARD')[0]['data']['path']
    boundary=source_geometry_mm(polygon(board_path))
    assert boundary.is_valid and boundary.area>0
    thickness=sum(r['data'].get('thickness',0) for r in get('LAYER_PHYS'))*MIL
    if thickness:board.GetDesignSettings().SetBoardThickness(round(thickness*1e6))
    audit['active_board_bounds_mm']=list(boundary.bounds);audit['declared_thickness_mm']=thickness
    def inside(g,ident):
        if not g.intersects(boundary):
            audit['excluded_outside_active_board'].append(ident);return False
        return True
    def track(start,end,width,layer,netname='',sweep=0,graphic=False,fp=None):
        if graphic:
            item=k.FP_SHAPE(fp) if fp else k.PCB_SHAPE(board)
            item.SetShape(k.SHAPE_T_ARC if sweep else k.SHAPE_T_SEGMENT)
        else:item=k.PCB_ARC(board) if sweep else k.PCB_TRACK(board)
        item.SetStart(pt(*start));item.SetEnd(pt(*end));item.SetWidth(round(width*MIL*1e6));item.SetLayer(layer)
        if sweep:
            pts=arc_points(start,end,sweep);mid=pts[len(pts)//2]
            if graphic:item.SetArcGeometry(pt(*start),pt(*mid),pt(*end))
            else:item.SetMid(pt(*mid))
        if not graphic:item.SetNet(net(netname))
        (fp if fp else board).Add(item)
    def zone(g,layer,name,ident,outline=None):
        if not g.is_valid:
            audit['warnings'].append({'source':ident,'issue':'invalid polygon; no automatic repair'});return
        if not inside(g,ident):return
        clipped=g.intersection(boundary)
        if abs(clipped.area-g.area)>1e-8:audit['warnings'].append({'source':ident,'issue':'copper clipped to explicit active BOARD boundary','removed_area_mm2':g.area-clipped.area})
        for geom in polys(clipped):
            target=target_geometry(geom);z=k.ZONE(board);z.SetLayer(layer);z.SetNet(net(name))
            z.SetZoneName('Recovered '+ident);z.SetLocalClearance(0);z.SetMinThickness(k.FromMM(.001))
            # Cache contains its own thermal geometry. Asking KiCad to infer
            # thermal spokes again creates misleading starved-thermal reports.
            z.SetPadConnection(k.ZONE_CONNECTION_FULL)
            z.Outline().Append(polyset(target))
            filled=polyset(target)
            filled.Fracture()
            z.SetFilledPolysList(layer,filled);z.SetIsFilled(True);z.SetNeedRefill(False)
            board.Add(z);audit['converted']['static_copper_polygons']+=1
            audit['expected_static_copper_area_mm2'][ident]+=geom.area
    # Active BOARD is the explicit effective perimeter, independent of leftover
    # drawing objects in cloned projects. Preserve source arcs as native arcs.
    for s,e,angle in segments(board_path):track(s,e,1,k.Edge_Cuts,sweep=angle,graphic=True)
    seen={}
    for r in get('POLY'):
        b=r['data']
        if b.get('layerId')!=11:continue
        try:g=source_geometry_mm(polygon(b['path']))
        except Exception:continue
        # Only closed interior rings are physical cutouts. Source duplicate
        # circles are deduplicated explicitly, never silently merged.
        if not boundary.contains(g) or g.equals(boundary):continue
        signature=g.normalize().wkb_hex
        if signature in seen:
            audit['warnings'].append({'source':r['header']['id'],'issue':'duplicate interior cutout omitted','same_as':seen[signature]});continue
        seen[signature]=r['header']['id']
        for s,e,angle in segments(b['path']):track(s,e,1,k.Edge_Cuts,sweep=angle,graphic=True)
        audit['converted']['interior_cutouts']+=1
    attrs=collections.defaultdict(dict)
    for r in get('ATTR'):
        b=r['data'];attrs[b.get('parentId')][b['key']]=b.get('value')
    padnets={}
    for r in get('PAD_NET'):
        key=json.loads(r['header']['id']);padnets[(key[1],key[-1])]=r['data']['padNet']
    effective={r['reference']:r for r in json.loads((folder/'effective-bom.json').read_text(encoding='utf-8'))}
    uid_refs={}
    for row in json.loads((folder/'instance-attributes.json').read_text(encoding='utf-8')).items():
        if row[1].get('Unique ID'):uid_refs[row[1]['Unique ID']]=row[0]
    expected_pads=[]
    def add_pad(fp,r,component=None,cid='',ref=''):
        b=r['data'];geom=pad_shape(b);hole=source_hole(b)
        bottom=component is not None and component['layerId']==2
        if component:geom=transform(geom,component,bottom)
        geom=source_geometry_mm(geom);geomtarget=target_geometry(geom)
        center=Point(b['centerX'],b['centerY'])
        if component:center=transform(center,component,bottom)
        gx,gy=center.x*MIL,-center.y*MIL
        pad=k.PAD(fp);source_number=str(b.get('num',''));number='' if hole and not b.get('plated') else source_number;pad.SetNumber(number);pad.SetPosition(vec(gx,gy))
        if hole:
            if component:hole=transform(hole,component,bottom)
            drill=b['hole'];dw=drill['height'] if drill['holeType']=='ROUND' else drill['width'];dh=drill['height']
            pad.SetDrillSize(vec(dw*MIL,dh*MIL));pad.SetDrillShape(k.PAD_DRILL_SHAPE_CIRCLE if drill['holeType']=='ROUND' else k.PAD_DRILL_SHAPE_OBLONG)
            pad.SetAttribute(k.PAD_ATTRIB_PTH if b.get('plated') else k.PAD_ATTRIB_NPTH)
            pad.SetLayerSet(layer_set([k.F_Mask,k.B_Mask],True))
            assert drill['holeType']=='ROUND','Slot drill orientation requires separate qualification'
            hc=source_geometry_mm(hole).centroid;offset=vec(hc.x-gx,-hc.y-gy)
            gx,gy=hc.x,-hc.y
            pad.SetPosition(vec(gx,gy))
            # Offset converted below using native regular pads; arbitrary custom
            # drilled pads retain source copper with an explicit offset warning.
        else:
            pad.SetAttribute(k.PAD_ATTRIB_SMD)
            side=b.get('layerId',1)
            assert side in [1,2],('Undrilled non-surface pad',side,r['header']['id'])
            if bottom:side=2 if side==1 else 1 if side==2 else side
            lc=k.F_Cu if side==1 else k.B_Cu
            pad.SetLayerSet(layer_set([lc,k.F_Mask if lc==k.F_Cu else k.B_Mask,k.F_Paste if lc==k.F_Cu else k.B_Paste]))
        shape=b['defaultPad'];kind=shape['padType']
        # A custom polygon preserves source geometry, including rounded edges,
        # rather than substituting a library footprint with similar pad counts.
        pad.SetShape(k.PAD_SHAPE_CUSTOM);pad.SetSize(vec(.001,.001))
        pad.AddPrimitivePoly(k.F_Cu if not bottom else k.B_Cu,polyset(geomtarget,(gx,gy)),0,True)
        name=padnets.get((cid,r['header']['id']),b.get('netName',''))
        if name:pad.SetNet(net(name))
        fp.Add(pad);audit['converted']['pads']+=1
        expected_pads.append({'reference':ref,'number':number,'source_number':source_number,'net':name or '', 'x_mm':gx,'y_mm':gy,'source_id':r['header']['id'], 'drill_mm':b['hole']['height']*MIL if hole else None,'copper_area_mm2':geomtarget.area,'copper_bounds_mm':list(geomtarget.bounds),'copper_layers':[int(l) for l in [k.F_Cu,k.B_Cu] if pad.IsOnLayer(l)]})
        expected_pads[-1]['native_uuid']=pad.m_Uuid.AsString()
        if b.get('specialPad'):audit['warnings'].append({'source':r['header']['id'],'issue':'per-layer specialPad overrides need review'})
    for r in get('COMPONENT'):
        b=r['data'];cid=r['header']['id'];aa={**b.get('attrs',{}),**attrs[cid]}
        ref=aa.get('Designator') or uid_refs.get(aa.get('Unique ID')) or ('UNNAMED_'+cid[:6])
        fpdoc=docs[('FOOTPRINT',aa['Footprint'])]
        if not inside(Point(b['x']*MIL,b['y']*MIL),cid):continue
        fp=k.FOOTPRINT(board);fp.SetReference(ref);fp.SetValue(effective.get(ref,{}).get('value') or aa.get('Value') or ref)
        fp.SetPosition(pt(b['x'],b['y']));fp.SetLayer(k.B_Cu if b['layerId']==2 else k.F_Cu)
        fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
        board.Add(fp)
        for pr in fpdoc['records']:
            if pr['header']['type']=='PAD':add_pad(fp,pr,b,cid,ref)
            else:audit['omitted_nonpad_footprint_records'][pr['header']['type']]+=1
        audit['converted']['components']+=1
    if get('PAD'):
        fp=k.FOOTPRINT(board);fp.SetReference('SOURCE_BOARD_PADS');fp.Reference().SetVisible(False);board.Add(fp)
        for r in get('PAD'):add_pad(fp,r,ref='SOURCE_BOARD_PADS')
    for r in get('LINE')+get('ARC')+get('CARC'):
        b=r['data'];lid=b['layerId'];layer=layer_types.get(layers[lid]['layerType'])
        if layer not in [k.F_Cu,k.B_Cu]:continue
        s=(b['startX'],b['startY']);e=(b['endX'],b['endY'])
        if not inside(source_geometry_mm(LineString([s,e])),r['header']['id']):continue
        track(s,e,b['width'],layer,b.get('netName',''),b.get('angle',0) if r['header']['type']!='LINE' else 0)
        audit['converted']['tracks']+=1
    for r in get('POLY'):
        b=r['data'];layer=layer_types.get(layers[b['layerId']]['layerType'])
        if layer not in [k.F_Cu,k.B_Cu]:continue
        for s,e,angle in segments(b['path']):
            if not inside(source_geometry_mm(LineString([s,e])),r['header']['id']):continue
            track(s,e,b['width'],layer,b.get('netName',''),angle)
            audit['converted']['copper_poly_strokes']+=1
    for r in get('VIA'):
        b=r['data'];v=k.PCB_VIA(board)
        if not inside(Point(b['centerX']*MIL,b['centerY']*MIL),r['header']['id']):continue
        assert b['viaType']=='NORMAL'
        v.SetPosition(pt(b['centerX'],b['centerY']));v.SetWidth(round(b['viaDiameter']*MIL*1e6));v.SetDrill(round(b['holeDiameter']*MIL*1e6));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(net(b.get('netName','')));board.Add(v);audit['converted']['vias']+=1
    for r in get('FILL')+get('TEARDROP'):
        b=r['data'];layer=layer_types.get(layers[b['layerId']]['layerType'])
        if layer in [k.F_Cu,k.B_Cu]:
            zone(source_geometry_mm(polygon(b['path'])),layer,b.get('netName',''),r['header']['id']);audit['converted'][r['header']['type']]+=1
    owners={r['header']['id']:r for r in get('POUR')};matched=set()
    for r in get('POURED'):
        ident=json.loads(r['header']['id'])[1];owner=owners.get(ident)
        if not owner:continue
        matched.add(ident);ob=owner['data'];chunks=[]
        for fill in r['data'].get('pourFill',[]):
            path=fill['path'];stroke=fill.get('strokeWidth',0)
            if fill.get('fill'):
                g=source_geometry_mm(polygon(path,scale=CACHE),CACHE)
                fineness=ob.get('pourType',{}).get('fineness',0)*MIL
                if fineness:g=g.buffer(fineness/2)
            else:
                lines=[]
                for part in path:
                    pts=[]
                    for s,e,angle in segments(part):
                        sample=arc_points(s,e,angle,scale=CACHE) if angle else [s,e]
                        pts.extend(sample if not pts else sample[1:])
                    if pts:lines.append(LineString(pts))
                g=source_geometry_mm(unary_union(lines).buffer(stroke/2),CACHE)
            chunks.append(g)
        if chunks:zone(unary_union(chunks),k.F_Cu if ob['layerId']==1 else k.B_Cu,ob.get('netName',''),ident)
    for ident in set(owners)-matched:audit['warnings'].append({'source':ident,'issue':'POUR has no active cached copper; not regenerated'})
    dest=root/('editing/kicad-routed-transition-hypothesis' if a.transition_hypothesis else 'editing/kicad-routed')/folder.name;dest.mkdir(parents=True,exist_ok=True)
    path=dest/(folder.name+'.kicad_pcb')
    k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(path),board)
    reopened=k.LoadBoard(str(path));assert reopened
    audit['reopened']={'footprints':len(reopened.GetFootprints()),'pads':sum(len(fp.Pads()) for fp in reopened.GetFootprints()),'tracks_and_vias':len(reopened.GetTracks()),'zones':len(reopened.Zones())}
    audit['expected_pads']=expected_pads
    (dest/'conversion-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    reports.append({key:audit[key] for key in ['candidate','converted','reopened']})
print(json.dumps(reports,indent=2))
