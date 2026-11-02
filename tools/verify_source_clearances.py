"""Verify source-rule projection provenance, native fixture outcomes and reports."""
from pathlib import Path
import json,hashlib,collections,subprocess,os
root=Path(__file__).resolve().parents[1]
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
probe=json.loads((root/'audit/native-clearance-rule-probes.json').read_text());cases={r['case']:r for r in probe['cases']}
version_cmd=['/usr/bin/kicad-cli','version']
if os.name=='nt':version_cmd=['wsl','-d','NVIDIA-Workbench','--',*version_cmd]
native_version=subprocess.check_output(version_cmd,text=True,timeout=30).strip()
assert native_version==probe['native_version'].split(',')[0],'Native KiCad changed; rerun rule fixtures before qualification'
assert cases['type_conditions']['drc_counts']['assertion_failure']==11
assert cases['type_conditions']['assertion_counts_by_rule']['Type test Track']==5
assert cases['no_custom']['drc_counts']['clearance']==3
assert cases['floor_02']['drc_counts']['clearance']==1
assert cases['layer_front_only']['drc_counts']['clearance']==2
assert cases['hole_board_only']['drc_counts']['hole_clearance']==1
assert not cases['hole_lower_than_board']['drc_counts'].get('hole_clearance')
assert not cases['edge_hole_rules']['drc_counts'].get('copper_edge_clearance')
assert cases['edge_hole_rules']['drc_counts']['hole_to_hole']==1
results=[]
for folder in sorted((root/'editing/kicad-source-clearances').iterdir()):
    if not folder.is_dir():continue
    audit=json.loads((folder/'source-clearance-audit.json').read_text());parent=root/audit['parent_board'];board=folder/parent.name
    assert digest(board)==digest(parent)==audit['board_sha256']
    assert board.with_suffix('.kicad_pro').read_bytes()==parent.with_suffix('.kicad_pro').read_bytes(),'Global project defaults changed'
    replay=root/'editing/recovered-community'/board.stem/'replayed-project.json'
    assert digest(replay)==audit['source_replay_sha256']
    dru=board.with_suffix('.kicad_dru');assert digest(dru)==audit['rules_sha256']
    assert '(severity ignore)' not in dru.read_text()
    holes=[r for r in audit['native_rules'] if r['constraint']=='hole_to_hole'];assert len(holes)==1 and holes[0]['condition'] is None,'Global source drill checks must include vias'
    for ownership in audit['zone_class_ownership']:
        assert ownership['source_classes'] in [[6],[7],[6,7]]
        assert ownership['contributors'] and all(c['overlap_mm2']>0 for c in ownership['contributors'])
        combined=sorted({v for c in ownership['contributors'] for v in c['source_classes']})
        assert combined==ownership['source_classes']
        assert ownership['conservative_class_collapse']==(len(combined)>1)
    report=json.loads((folder/'drc-source-clearances.json').read_text());counts=dict(collections.Counter(r['type'] for r in report['violations']))
    assert report['kicad_version']==native_version
    assert counts==audit['drc_counts'] and not report['schematic_parity'] and len(report['unconnected_items'])==audit['unconnected']
    result={'candidate':folder.name,'board_bytes_and_global_defaults_unchanged':True,'projected_native_rules':len(audit['native_rules']),'mixed_source_zone_regions':sum(x['conservative_class_collapse'] for x in audit['zone_class_ownership']),'drc_counts':counts,'total_drc_findings':sum(counts.values()),'unconnected':audit['unconnected'],'schematic_parity_findings':0,'full_rule_fidelity':False,'manufacturing_ready':False}
    results.append(result)
assert len(results)==5
summary={'native_version':native_version,'native_fixture_cases_verified':len(cases),'source_clearance_profiles':results,'all_provenance_checks_passed':True,'manufacturing_ready':False}
(root/'editing/source-clearance-validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
