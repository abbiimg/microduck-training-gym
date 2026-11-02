"""Intentionally clear stale hub GND cache around newly introduced Battery pad.

This is a separate, subtractive-only engineering copy. It is not source replay,
automatic copper refill, or manufacturing qualification.
"""
from pathlib import Path
from decimal import Decimal,ROUND_CEILING
import argparse,collections,hashlib,json,re,shutil,subprocess
import pcbnew as k
from shapely.geometry import Polygon
from shapely.ops import unary_union

p=argparse.ArgumentParser();p.add_argument('--overwrite-generated',action='store_true');a=p.parse_args()
ROOT=Path(__file__).resolve().parents[1]
parent=ROOT/'editing/kicad-integrated/wire_hub_1V0A';dest=ROOT/'editing/kicad-cache-repaired/wire_hub_1V0A'
source=parent/'wire_hub_1V0A.kicad_pcb';sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
def geom(poly):
    # Inputs here are already unfractured native sets. Calling Unfracture a
    # second time drops existing hole lists in KiCad10 and corrupts the audit.
    poly=k.SHAPE_POLY_SET(poly)
    def ring(r):return [(r.CPoint(i).x/1e6,r.CPoint(i).y/1e6) for i in range(r.PointCount())]
    return unary_union([Polygon(ring(poly.COutline(i)),[ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]) for i in range(poly.OutlineCount())])
evidence=ROOT/'audit/copper-overlap-source-review.json';review=json.loads(evidence.read_text())['results']['wire_hub_1V0A']
assert review['cache_predates_component_first_appearance']
replay=ROOT/'editing/recovered-community/wire_hub_1V0A/replayed-project.json';assert sha(replay)==review['source_replay_sha256']
rr=next(d['records'] for d in json.loads(replay.read_text(encoding='utf8'))['documents'] if d['head']['docType']=='PCB')
safe=next(r['data']['ruleContext'] for r in rr if r['header']['type']=='RULE' and json.loads(r['header']['id'])[1]=='SAFE' and r['data']['ruleState']=='DEFAULT')
tables={r['layerId']:r['content'] for r in safe['safeSpacing']};table=tables[1] if safe['isForAll']=='ALL' else tables.get(2,tables[1])
raw_mil=table[7][2];exact_nm=Decimal(str(raw_mil))*Decimal('.0254')*Decimal(1000000)
clearance_nm=int(exact_nm.to_integral_value(rounding=ROUND_CEILING));guard_nm=2
source_rule=json.loads((parent/'source-clearance-audit.json').read_text())
projected=next(r for r in source_rule['native_rules'] if r['name']=='Source SAFE B.Cu pth to zone_7')
assert abs(projected['minimum_mm']-float(exact_nm/Decimal(1000000)))<1e-12
if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve edits before --overwrite-generated')
shutil.copytree(parent,dest,dirs_exist_ok=True)
board=k.LoadBoard(str(source));assert all(len(fp.Models())==0 for fp in board.GetFootprints()),'Parent unexpectedly has model attachments'
pad=next(p for f in board.GetFootprints() if f.GetReference()=='CN1' for p in f.Pads() if p.GetNumber()=='1')
assert pad.GetNetname()=='/Battery' and pad.GetAttribute()==k.PAD_ATTRIB_PTH
zones=[z for z in board.Zones() if z.GetNetname()=='/GND' and z.GetLayer()==k.B_Cu];assert len(zones)==1
zone=zones[0];uid=zone.m_Uuid.AsString()
before=k.SHAPE_POLY_SET(zone.GetFilledPolysList(k.B_Cu));before.Unfracture()
exclusion=k.SHAPE_POLY_SET();pad.TransformShapeToPolygon(exclusion,k.B_Cu,0,1,k.ERROR_OUTSIDE);exclusion.Unfracture()
padg=geom(exclusion)  # Freeze coordinates before offsetting native cached shapes.
# Apply an explicit integer round offset, then measure the actual saved gap
# from a fresh board/pad object rather than reusing generated shape caches.
exclusion.Inflate(clearance_nm+guard_nm,k.CORNER_STRATEGY_ROUND_ALL_CORNERS,1)
after=k.SHAPE_POLY_SET();after.BooleanSubtract(before,exclusion)
assert after.OutlineCount()==1,'Repair unexpectedly splits static ground; separate review required'
added=k.SHAPE_POLY_SET();added.BooleanSubtract(after,before);assert added.Area()==0,'Subtractive repair added copper'
removed=k.SHAPE_POLY_SET();removed.BooleanSubtract(before,after)
expected_removed=k.SHAPE_POLY_SET();expected_removed.BooleanIntersection(before,exclusion)
xor=k.SHAPE_POLY_SET();xor.BooleanXor(removed,expected_removed);removed_expected_xor_mm2=xor.Area()/1e12
zone.Outline().RemoveAllContours();zone.Outline().Append(after)
filled=k.SHAPE_POLY_SET(after);filled.Fracture();zone.SetFilledPolysList(k.B_Cu,filled);zone.SetIsFilled(True);zone.SetNeedRefill(False)

def zone_spans(text):
    depth=0;quoted=False;escaped=False;start=None;tag=None;result={}
    for index,char in enumerate(text):
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
            continue
        if char=='"':quoted=True;continue
        if char=='(':
            if depth==1:start=index;tag=re.match(r'\(\s*([^\s()]+)',text[index:])[1]
            depth+=1
        elif char==')':
            depth-=1
            if depth==1 and tag=='zone':
                chunk=text[start:index+1];ident=re.search(r'\(uuid\s+"([^\"]+)"\)',chunk)[1];result[ident]=(start,index+1,chunk);tag=None
    assert depth==0 and not quoted
    return result

output=dest/source.name;native_save=dest/'cache-repair-native-save.kicad_pcb'
k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(native_save),board)
original_text=source.read_text(encoding='utf8');modified_text=native_save.read_text(encoding='utf8')
oldspans=zone_spans(original_text);newspans=zone_spans(modified_text);s,e,oldchunk=oldspans[uid];newchunk=newspans[uid][2]
assert oldchunk!=newchunk
output.write_text(original_text[:s]+newchunk+original_text[e:],encoding='utf8')
native_save.unlink()
saved_text=output.read_text(encoding='utf8');savedspans=zone_spans(saved_text);s2,e2,_=savedspans[uid]
assert saved_text[:s2]+saved_text[e2:]==original_text[:s]+original_text[e:],'Changed native text outside targeted GND zone'
assert set(savedspans)==set(oldspans)
assert all(savedspans[other][2]==chunk[2] for other,chunk in oldspans.items() if other!=uid)
saved=k.LoadBoard(str(output));assert all(len(fp.Models())==0 for fp in saved.GetFootprints())
savedzone=next(z for z in saved.Zones() if z.m_Uuid.AsString()==uid)
pad=next(p for f in saved.GetFootprints() if f.GetReference()=='CN1' for p in f.Pads() if p.GetNumber()=='1')
actual=k.SHAPE_POLY_SET(savedzone.GetFilledPolysList(k.B_Cu));actual.Unfracture();xor=k.SHAPE_POLY_SET();xor.BooleanXor(after,actual);assert xor.Area()==0

beforeg=geom(before);afterg=geom(actual);exclusiong=geom(exclusion)
gap=padg.distance(afterg)
assert gap>=clearance_nm/1e6,(gap,clearance_nm)
added_outside_band=afterg.difference(beforeg.buffer(.000002)).area
assert added_outside_band<1e-12,('Copper added outside2nm native precision band',added_outside_band)
expectedg=beforeg.difference(exclusiong)
outside_band=afterg.difference(expectedg.buffer(.000002)).area+expectedg.difference(afterg.buffer(.000002)).area
assert outside_band<1e-12,('Independent subtraction differs outside2nm native precision band',outside_band)
removedg=beforeg.difference(afterg);expected_removedg=beforeg.intersection(exclusiong)
raw_removed_outside_band=removedg.difference(expected_removedg.buffer(.000002)).area+expected_removedg.difference(removedg.buffer(.000002)).area
# Boolean/weak-polygon fracture can leave sub-nanometre slivers on an EXISTING
# zone boundary far from the pad. Bound their coordinates at that interface;
# an arbitrary allowance on total area would conceal an unrelated edit.
removed_outside_band=removedg.symmetric_difference(expected_removedg).difference(beforeg.boundary.buffer(.000002)).difference(exclusiong.boundary.buffer(.000002)).area
assert removed_outside_band<1e-12,('Unexpected removal away from both2nm clipping interfaces',removed_outside_band)
assert beforeg.intersection(padg).area>0 and afterg.intersection(padg).area==0
reportpath=dest/'drc-cache-repaired.json'
run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(reportpath),str(output)],capture_output=True,text=True,timeout=180)
(dest/'cache-repair-drc.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stderr
drc=json.loads(reportpath.read_text());assert not drc['schematic_parity'] and not drc['unconnected_items']
assert not any(v['type']=='clearance' for v in drc['violations']),drc['violations']
oldreport=json.loads((parent/'drc-silkscreen.json').read_text())
unchangedfiles={}
for path in parent.rglob('*'):
    if not path.is_file() or path==source or path.name=='README.txt':continue
    target=dest/path.relative_to(parent)
    if path.suffix in ['.kicad_pro','.kicad_sch','.kicad_dru','.kicad_sym','.kicad_mod'] or path.name in ['sym-lib-table','fp-lib-table']:
        assert sha(path)==sha(target);unchangedfiles[str(path.relative_to(parent))]=sha(path)
assert sha(source)==hashlib.sha256(original_text.encode()).hexdigest(),'Parent source bytes changed'
assert sha(replay)==review['source_replay_sha256']
audit={'candidate':'wire_hub_1V0A','kind':'intentional subtractive engineering repair of stale cache','parent_board':str(source.relative_to(ROOT)),'parent_sha256':sha(source),'engineering_board_sha256':sha(output),'source_replay_sha256':sha(replay),'source_history_evidence':str(evidence.relative_to(ROOT)),'source_history_evidence_sha256':sha(evidence),'source_cache_ticket':review['latest_cache_ticket'],'source_component_first_ticket':review['component_first_appearance_ticket'],'target_pad':{'reference':'CN1','number':'1','uuid':pad.m_Uuid.AsString(),'net':'/Battery','x_mm':pad.GetPosition().x/1e6,'y_mm':pad.GetPosition().y/1e6},'changed_zone':{'uuid':uid,'name':zone.GetZoneName(),'layer':'B.Cu','net':'/GND'},'clearance':{'source_classes':[2,7],'source_raw_mil':raw_mil,'source_exact_mm':float(exact_nm/Decimal(1000000)),'required_native_nm':clearance_nm,'outward_rounding_guard_nm':guard_nm,'polygon_max_error_nm':1,'operation':'native SHAPE_POLY_SET round-all-corners inflation of zero-clearance pad polygon; saved gap checked using a fresh native pad','measured_gap_mm':gap},'copper_change':{'before_mm2':beforeg.area,'after_mm2':afterg.area,'removed_mm2':beforeg.difference(afterg).area,'added_mm2':afterg.difference(beforeg).area,'native_added_area_mm2':added.Area()/1e12,'native_removed_vs_expected_xor_mm2':removed_expected_xor_mm2,'removal_difference_outside_2nm_precision_band_mm2':removed_outside_band,'independent_expected_after_xor_mm2':afterg.symmetric_difference(expectedg).area,'independent_after_difference_outside_2nm_precision_band_mm2':outside_band,'saved_vs_expected_xor_mm2':xor.Area()/1e12,'before_pad_overlap_mm2':beforeg.intersection(padg).area,'after_pad_overlap_mm2':afterg.intersection(padg).area},'board_text_outside_single_ground_zone_identical':True,'other_zone_text_identical':True,'unchanged_project_schematic_rules_libraries':unchangedfiles,'source_board_and_replay_unchanged':True,'source_rule_limits_changed':False,'nets_pads_tracks_vias_outline_silk_mask_paste_unchanged':True,'model_attachments':0,'copper_refilled':False,'drc_before':dict(collections.Counter(v['type'] for v in oldreport['violations'])),'drc_after':dict(collections.Counter(v['type'] for v in drc['violations'])),'schematic_parity':drc['schematic_parity'],'unconnected':len(drc['unconnected_items']),'manufacturing_ready':False}
audit['drc_report_sha256']=sha(reportpath)
audit['coordinate_precision_band_nm']=2
audit['copper_change']['raw_removal_difference_outside_exclusion_2nm_band_mm2']=raw_removed_outside_band
audit['copper_change']['independent_added_copper_outside_original_2nm_boundary_band_mm2']=added_outside_band
(dest/'cache-repair-audit.json').write_text(json.dumps(audit,indent=2))
(dest/'README.txt').write_text('Intentional engineering cache repair, not exact source recovery. CN1 was introduced after the last source GND pour cache. Only B.Cu GND static copper around pad 1 Battery was subtracted using the exact source PTH/pour clearance with a 2 nm outward guard. The integer-grid operation adds no copper; independent geometric discrepancies are confined to a 2 nm band at clipping interfaces. All other native text and project/schematic/rules/libraries are unchanged. No model attachments and no copper refill. Read cache-repair-audit.json, cache-repair-validation.json and drc-cache-repaired.json for CURRENT results. Other inherited audit/DRC files describe the parent stage and are historical. Manufacturing qualification remains false.\n')
print(json.dumps({key:audit[key] for key in ['kind','clearance','copper_change','drc_before','drc_after','unconnected','manufacturing_ready']},indent=2))
