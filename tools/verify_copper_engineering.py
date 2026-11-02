"""Check engineering-copy copper through independent GEOS union/XOR geometry."""
from pathlib import Path
import json,hashlib,collections
import pcbnew as k
from shapely.geometry import Polygon
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[1];results=[]
def geometry(board,excluded=()):
    groups=collections.defaultdict(list)
    for zone in board.Zones():
        if zone.m_Uuid.AsString() in excluded:continue
        layer=zone.GetLayer();poly=k.SHAPE_POLY_SET(zone.GetFilledPolysList(layer));poly.Unfracture()
        def ring(r):return [(r.CPoint(i).x/1e6,r.CPoint(i).y/1e6) for i in range(r.PointCount())]
        for index in range(poly.OutlineCount()):
            g=Polygon(ring(poly.COutline(index)),[ring(poly.CHole(index,j)) for j in range(poly.HoleCount(index))])
            assert g.is_valid,('Invalid saved polygon requires separate review',zone.GetZoneName())
            groups[(int(layer),zone.GetNetname())].append(g)
    return {key:unary_union(items) for key,items in groups.items()}
for folder in sorted((root/'editing/kicad-copper-consolidated').iterdir()):
    if not folder.is_dir():continue
    audit=json.loads((folder/'consolidation-audit.json').read_text());parent=root/audit['parent_board'];board=next(folder.glob('*.kicad_pcb'))
    assert hashlib.sha256(parent.read_bytes()).hexdigest()==audit['parent_sha256']
    before=geometry(k.LoadBoard(str(parent)),{item['uuid'] for item in audit['excluded_source_geometry']});after=geometry(k.LoadBoard(str(board)))
    assert before.keys()==after.keys()
    differences=[]
    for key in before:
        area=before[key].symmetric_difference(after[key]).area
        # KiCad clips intersections on its integer-nanometre grid. GEOS uses
        # floating intersections; require all discrepancy within two native
        # coordinate units, rather than accepting an arbitrary total area.
        tolerance=2e-6
        outside=before[key].difference(after[key].buffer(tolerance)).area+after[key].difference(before[key].buffer(tolerance)).area
        differences.append({'layer':key[0],'net':key[1],'symmetric_difference_mm2':area,'outside_native_precision_band_mm2':outside})
        assert outside<1e-12,(folder,key,area,outside)
    result={'candidate':folder.name,'geometry_engine':'Shapely/GEOS independent of native KiCad union','coordinate_comparison_tolerance_nm':2,'physical_equivalence_scope':audit['physical_equivalence_scope'],'copper_differences':differences,'max_difference_mm2':max((r['symmetric_difference_mm2'] for r in differences),default=0),'manufacturing_ready':False}
    (folder/'independent-copper-validation.json').write_text(json.dumps(result,indent=2));results.append(result)
for folder in sorted((root/'editing/kicad-source-rules-projected').iterdir()):
    if not folder.is_dir():continue
    audit=json.loads((folder/'source-minima-audit.json').read_text());source=root/audit['source_board'];copy=folder/source.name
    replay=root/'editing/recovered-community'/source.stem/'replayed-project.json'
    assert hashlib.sha256(replay.read_bytes()).hexdigest()==audit['source_replay_sha256']
    assert hashlib.sha256(copy.read_bytes()).hexdigest()==audit['board_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    project=json.loads(copy.with_suffix('.kicad_pro').read_text())
    actual=project['board']['design_settings']['rules']
    assert all(actual[key]==value for key,value in audit['translated_rules_mm'].items())
package=json.loads((root/'audit/pcb-tools/ti-buffer-package/results.json').read_text());assert package['all_passed'] and package['checks_passed']==22
ringfolder=root/'editing/kicad-graphic-corrected/POGO_PIN_1V0A';ringaudit=json.loads((ringfolder/'graphic-restoration-audit.json').read_text())
ringboard=ringfolder/'POGO_PIN_1V0A.kicad_pcb';assert hashlib.sha256(ringboard.read_bytes()).hexdigest()==ringaudit['engineering_board_sha256']
assert not ringaudit['schematic_parity'] and not ringaudit['drc_counts'] and ringaudit['unconnected']==0
summary={'consolidated_candidates':len(results),'coordinate_comparison_tolerance_nm':2,'independent_copper_results':[{key:r[key] for key in ['candidate','max_difference_mm2','physical_equivalence_scope']} for r in results],'source_projection_board_and_replay_hashes_passed':True,'pogo_graphic_copy_hash_and_checks_passed':True,'buffer_package_checks_passed':22,'manufacturing_ready':False}
(root/'editing/copper-engineering-validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
