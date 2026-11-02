"""Recheck the isolated subtractive hub repair from saved native geometry."""
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
import collections,hashlib,json,math,re
import pcbnew as k
from shapely.geometry import Polygon
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'editing/kicad-cache-repaired/wire_hub_1V0A';path=folder/'wire_hub_1V0A.kicad_pcb'
audit=json.loads((folder/'cache-repair-audit.json').read_text());parent=ROOT/audit['parent_board']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(path)==audit['engineering_board_sha256'] and sha(parent)==audit['parent_sha256']
assert not audit['manufacturing_ready'] and not audit['copper_refilled'] and not audit['source_rule_limits_changed']
evidence=ROOT/audit['source_history_evidence'];assert sha(evidence)==audit['source_history_evidence_sha256']
history=json.loads(evidence.read_text())['results']['wire_hub_1V0A'];assert history['cache_predates_component_first_appearance']
replay=ROOT/'editing/recovered-community/wire_hub_1V0A/replayed-project.json';assert sha(replay)==audit['source_replay_sha256']
rr=next(d['records'] for d in json.loads(replay.read_text(encoding='utf8'))['documents'] if d['head']['docType']=='PCB')
safe=next(r['data']['ruleContext'] for r in rr if r['header']['type']=='RULE' and json.loads(r['header']['id'])[1]=='SAFE' and r['data']['ruleState']=='DEFAULT')
tables={r['layerId']:r['content'] for r in safe['safeSpacing']};table=tables[1] if safe['isForAll']=='ALL' else tables.get(2,tables[1])
raw=Decimal(str(table[7][2]));required_nm=int((raw*Decimal('.0254')*Decimal(1000000)).to_integral_value(rounding=ROUND_CEILING))
assert audit['clearance']['required_native_nm']==required_nm==254000
for name,digest in audit['unchanged_project_schematic_rules_libraries'].items():assert sha(parent.parent/name)==sha(folder/name)==digest
uid=audit['changed_zone']['uuid']
def spans(text):
    depth=0;quoted=False;escaped=False;start=None;tag=None;zones={}
    for i,c in enumerate(text):
        if quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
            continue
        if c=='"':quoted=True;continue
        if c=='(':
            if depth==1:start=i;tag=re.match(r'\(\s*([^\s()]+)',text[i:])[1]
            depth+=1
        elif c==')':
            depth-=1
            if depth==1 and tag=='zone':
                chunk=text[start:i+1];key=re.search(r'\(uuid\s+"([^\"]+)"\)',chunk)[1];zones[key]=(start,i+1,chunk);tag=None
    assert depth==0
    return zones
oldtext=parent.read_text(encoding='utf8');newtext=path.read_text(encoding='utf8');oldsp=spans(oldtext);newsp=spans(newtext)
assert set(oldsp)==set(newsp)
assert all(oldsp[key][2]==newsp[key][2] for key in oldsp if key!=uid)
s,e,_=oldsp[uid];ss,ee,_=newsp[uid];assert oldtext[:s]+oldtext[e:]==newtext[:ss]+newtext[ee:]
before=k.LoadBoard(str(parent));after=k.LoadBoard(str(path));assert k.Version().startswith('10.0.7')
assert all(len(fp.Models())==0 for fp in after.GetFootprints())
oldzone=next(z for z in before.Zones() if z.m_Uuid.AsString()==uid);zone=next(z for z in after.Zones() if z.m_Uuid.AsString()==uid)
assert zone.GetNetname()==oldzone.GetNetname()=='/GND' and zone.GetLayer()==oldzone.GetLayer()==k.B_Cu
pad=next(p for fp in after.GetFootprints() if fp.GetReference()=='CN1' for p in fp.Pads() if p.GetNumber()=='1');assert pad.GetNetname()=='/Battery'
def geom(poly):
    poly=k.SHAPE_POLY_SET(poly);poly.Unfracture()
    def ring(r):return [(r.CPoint(i).x/1e6,r.CPoint(i).y/1e6) for i in range(r.PointCount())]
    return unary_union([Polygon(ring(poly.COutline(i)),[ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]) for i in range(poly.OutlineCount())])
g0=geom(oldzone.GetFilledPolysList(k.B_Cu));g1=geom(zone.GetFilledPolysList(k.B_Cu));poly=k.SHAPE_POLY_SET();pad.TransformShapeToPolygon(poly,k.B_Cu,0,1,k.ERROR_OUTSIDE);padg=geom(poly)
gap=padg.distance(g1);assert gap>=required_nm/1e6 and padg.intersection(g1).area==0 and padg.intersection(g0).area>0
oldpoly=k.SHAPE_POLY_SET(oldzone.GetFilledPolysList(k.B_Cu));oldpoly.Unfracture()
newpoly=k.SHAPE_POLY_SET(zone.GetFilledPolysList(k.B_Cu));newpoly.Unfracture()
native_added=k.SHAPE_POLY_SET();native_added.BooleanSubtract(newpoly,oldpoly);assert native_added.Area()==0
added_outside_band=g1.difference(g0.buffer(.000002)).area;assert added_outside_band<1e-12
# GEOS independently generates the circular pad offset; its high-resolution
# chords deviate less than1nm. Check discrepancy is confined to2nm native grid.
clearance=(required_nm+2)/1e6;segments=math.ceil(math.pi/(4*math.acos(1-.0000005/clearance)))
expected=g0.difference(padg.buffer(clearance,quad_segs=segments))
outside=g1.difference(expected.buffer(.000002)).area+expected.difference(g1.buffer(.000002)).area
assert outside<1e-12,('Unexpected copper removal outside2nm offset band',outside)
assert sha(folder/'drc-cache-repaired.json')==audit['drc_report_sha256']
report=json.loads((folder/'drc-cache-repaired.json').read_text());prior=json.loads((parent.parent/'drc-silkscreen.json').read_text())
assert report['kicad_version']=='10.0.7' and not report['schematic_parity'] and not report['unconnected_items']
oldcounts=collections.Counter(v['type'] for v in prior['violations']);newcounts=collections.Counter(v['type'] for v in report['violations'])
expectedcounts=oldcounts.copy();expectedcounts['clearance']-=1;assert +expectedcounts==+newcounts
assert newcounts['clearance']==0
def signature(v):return (v['type'],v['severity'],v['description'],tuple(sorted(i['uuid'] for i in v['items'])))
assert collections.Counter(signature(v) for v in prior['violations'] if v['type']!='clearance')==collections.Counter(signature(v) for v in report['violations'])
result={'candidate':'wire_hub_1V0A','board_sha256':sha(path),'parent_sha256':sha(parent),'fresh_saved_native_geometry_checked':True,'all_board_text_outside_one_ground_zone_identical':True,'project_schematic_rules_library_hashes_identical':True,'subtractive_only_on_native_integer_grid':True,'coordinate_precision_band_nm':2,'native_added_copper_mm2':native_added.Area()/1e12,'independent_added_copper_raw_mm2':g1.difference(g0).area,'independent_added_copper_outside_2nm_band_mm2':added_outside_band,'source_clearance_mm':required_nm/1e6,'measured_saved_gap_mm':gap,'independent_offset_difference_outside_2nm_band_mm2':outside,'copper_removed_mm2':g0.difference(g1).area,'positive_Battery_GND_overlap_removed':True,'drc_counts':dict(newcounts),'all_other_DRC_findings_unchanged':True,'schematic_parity':0,'airwires':0,'model_attachments':0,'manufacturing_ready':False}
(folder/'cache-repair-validation.json').write_text(json.dumps(result,indent=2))
(ROOT/'editing/cache-repair-validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
