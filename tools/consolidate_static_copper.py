"""Union same-net static copper in isolated native KiCad engineering copies.

No refill or source-rule changes. Literal geometry is retained by default. An
extra revised-IMU experiment explicitly excludes the ambiguous obsolete FILL.
"""
from pathlib import Path
import argparse,json,shutil,hashlib,collections,subprocess,re
import pcbnew as k
p=argparse.ArgumentParser();p.add_argument('--overwrite-generated',action='store_true');p.add_argument('--candidate',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];summaries=[]
def shape(poly):
    def ring(r):return tuple((r.CPoint(i).x,r.CPoint(i).y) for i in range(r.PointCount()))
    return tuple((ring(poly.COutline(i)),tuple(ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i)))) for i in range(poly.OutlineCount()))
def pads(board):
    return {pad.m_Uuid.AsString():(fp.GetReference(),pad.GetNumber(),pad.GetNetname(),pad.GetPosition().x,pad.GetPosition().y,pad.GetDrillSize().x,pad.GetDrillSize().y,tuple((layer,shape(pad.GetEffectivePolygon(layer))) for layer in [k.F_Cu,k.B_Cu] if pad.IsOnLayer(layer))) for fp in board.GetFootprints() for pad in fp.Pads()}
def tracks(board):
    return {item.m_Uuid.AsString():(item.GetNetname(),item.GetLayer(),item.GetStart().x,item.GetStart().y,item.GetEnd().x,item.GetEnd().y,item.GetWidth(k.F_Cu) if isinstance(item,k.PCB_VIA) else item.GetWidth(),item.GetDrillValue() if isinstance(item,k.PCB_VIA) else None, (item.GetMid().x,item.GetMid().y) if isinstance(item,k.PCB_ARC) else None) for item in board.GetTracks()}
def union(zones,layer):
    out=k.SHAPE_POLY_SET()
    for zone in zones:
        poly=k.SHAPE_POLY_SET(zone.GetFilledPolysList(layer));poly.Unfracture();out.BooleanAdd(poly)
    return out
def without_zones(text):
    # Avoid KiCad 10 SWIG Remove ownership failures. Remove only complete root
    # zone s-expressions in a generated COPY, then reload through native KiCad.
    depth=0;quoted=False;escaped=False;start=None;tag=None;cuts=[]
    for index,char in enumerate(text):
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
            continue
        if char=='"':quoted=True;continue
        if char=='(':
            if depth==1:
                start=index;match=re.match(r'\(\s*([^\s()]+)',text[index:]);tag=match[1]
            depth+=1
        elif char==')':
            depth-=1
            if depth==1 and tag=='zone':cuts.append((start,index+1));tag=None
    assert depth==0 and not quoted
    for start,end in reversed(cuts):text=text[:start]+text[end:]
    return text,len(cuts)
jobs=[(path,False) for path in sorted((root/'editing/kicad-paired').glob('*/*.kicad_pcb'))]
jobs += [(next(path for path,_ in jobs if path.stem=='imu_to_dxl_1V0A'),True)]
for source,hypothesis in jobs:
    name=source.stem;foldername=name+('-transition-hypothesis' if hypothesis else '')
    if foldername!=args.candidate:continue
    dest=root/'editing/kicad-copper-consolidated'/foldername
    if dest.exists() and not args.overwrite_generated:raise RuntimeError(f'Output exists; preserve edits before --overwrite-generated: {dest}')
    dest.mkdir(parents=True,exist_ok=True)
    for item in source.parent.iterdir():
        if item.name.endswith(('.kicad_sch','.kicad_pro','.kicad_sym')) or item.name in ['sym-lib-table','fp-lib-table']:
            shutil.copy2(item,dest/item.name)
        elif item.name.endswith('.pretty'):shutil.copytree(item,dest/item.name,dirs_exist_ok=True)
    board=k.LoadBoard(str(source));beforepads=pads(board);beforetracks=tracks(board)
    excluded=[];zones=list(board.Zones());allcount=len(zones)
    if hypothesis:
        for zone in list(zones):
            area=zone.GetFilledPolysList(zone.GetLayer()).Area()/1e12
            if zone.GetZoneName()=='Recovered 84a63625734e769f' and zone.GetLayer()==k.F_Cu and area>800:
                excluded.append({'uuid':zone.m_Uuid.AsString(),'source_primitive':'84a63625734e769f','area_mm2':area,'net':zone.GetNetname(),'reason':'explicit engineering type-transition hypothesis; identical-outline FILL ticket 40981 precedes POUR; no FILL tombstone observed'})
                zones.remove(zone)
        assert len(excluded)==1,excluded
    grouped=collections.defaultdict(list)
    for zone in zones:grouped[(zone.GetLayer(),zone.GetNetname())].append(zone)
    expected={};groups=[]
    for (layer,netname),items in grouped.items():
        geom=union(items,layer);expected[(layer,netname)]=geom
        groups.append({'layer':int(layer),'net':netname,'source_zone_count':len(items),'source_zone_names':[z.GetZoneName() for z in items],'source_zone_uuids':[z.m_Uuid.AsString() for z in items],'union_area_mm2':geom.Area()/1e12})
    original=board;output=dest/source.name
    bare,count=without_zones(source.read_text(encoding='utf-8'));assert count==allcount
    output.write_text(bare,encoding='utf-8');board=k.LoadBoard(str(output));assert len(board.Zones())==0
    for (layer,netname),geom in expected.items():
        for index in range(geom.OutlineCount()):
            # A native static zone has one connected filled region. Keeping
            # disconnected teardrops in separate zones avoids invalid island
            # bookkeeping while union still removes same-net overlaps.
            region=geom.UnitSet(index)
            z=k.ZONE(board);z.SetLayer(layer);z.SetNet(board.FindNet(netname));z.SetZoneName('Static union '+netname+' '+board.GetLayerName(layer)+' '+str(index))
            z.SetLocalClearance(0);z.SetMinThickness(k.FromMM(.001));z.SetPadConnection(k.ZONE_CONNECTION_FULL)
            z.Outline().Append(region);filled=k.SHAPE_POLY_SET(region);filled.Fracture()
            z.SetFilledPolysList(layer,filled);z.SetIsFilled(True);z.SetNeedRefill(False);board.Add(z)
    k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(output),board)
    reopened=k.LoadBoard(str(output));assert pads(reopened)==beforepads,'Saved pad geometry changed';assert tracks(reopened)==beforetracks,'Routing geometry changed'
    diffs=[]
    for (layer,netname),geom in expected.items():
        actual=union([z for z in reopened.Zones() if z.GetLayer()==layer and z.GetNetname()==netname],layer)
        xor=k.SHAPE_POLY_SET();xor.BooleanXor(geom,actual);diff=xor.Area()/1e12
        diffs.append({'layer':int(layer),'net':netname,'symmetric_difference_mm2':diff})
        assert diff<1e-8,(layer,netname,diff)
    drc=dest/'drc-parity.json'
    run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(drc),str(output)],capture_output=True,text=True,timeout=90)
    assert run.returncode==0,run.stderr
    report=json.loads(drc.read_text());assert not report['schematic_parity'],report['schematic_parity']
    audit={'candidate':foldername,'parent_board':str(source.relative_to(root)),'parent_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'source_zones':allcount,'result_zones':len(reopened.Zones()),'pads_checked':len(beforepads),'routing_items_checked':len(beforetracks),'pad_and_routing_geometry_preserved':True,'copper_symmetric_differences':diffs,'source_groups':groups,'excluded_source_geometry':excluded,'transition_hypothesis':hypothesis,'physical_equivalence_scope':'all literal saved copper' if not hypothesis else 'source copper after explicitly excluding one ambiguous FILL','schematic_parity':report['schematic_parity'],'drc_counts':dict(collections.Counter(v['type'] for v in report['violations'])),'unconnected':len(report['unconnected_items']),'source_rules_changed':False,'copper_refilled':False,'manufacturing_ready':False}
    (dest/'consolidation-audit.json').write_text(json.dumps(audit,indent=2))
    (dest/'README.txt').write_text('Static same-net copper union engineering copy. No refill or source-rule changes. Read ../../../COPPER-CONSOLIDATION.txt and consolidation-audit.json. A transition-hypothesis folder explicitly removes one ambiguous fill and is not literal source-equivalent. Manufacturing readiness remains false.\n')
    summary={key:audit[key] for key in ['candidate','source_zones','result_zones','pads_checked','routing_items_checked','transition_hypothesis','drc_counts','unconnected','manufacturing_ready']}
    summaries.append(summary);print(json.dumps(summary),flush=True)
assert len(summaries)==1,'Unknown candidate'
