"""Project evidenced source manufacturing minima into separate KiCad copies.

Only three limits are translated. SAFE pair clearances/mask/paste remain open.
"""
from pathlib import Path
import argparse,json,shutil,hashlib,subprocess,collections
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--overwrite-generated',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1]
evidence=root/'audit/source-manufacturing-minima.json'
rules={r['candidate']:r for r in json.loads(evidence.read_text())['candidates']}
source=root/'editing/kicad-copper-consolidated'/a.candidate
board=next(source.glob('*.kicad_pcb'));rule=rules[board.stem]
assert not rule['track_radius_selector_overrides'] and not rule['named_via_rule_overrides']
replay=root/'editing/recovered-community'/board.stem/'replayed-project.json'
pcb=next(d for d in json.loads(replay.read_text(encoding='utf-8'))['documents'] if d['head']['docType']=='PCB')
source_rules={tuple(json.loads(r['header']['id'])[1:]):r['data'] for r in pcb['records'] if r['header']['type']=='RULE'}
track=source_rules[('TRACK',rule['track_rule'])];radius=source_rules[('RADIUS',rule['radius_rule'])]
assert track['ruleState']=='DEFAULT' and radius['ruleState']=='DEFAULT'
assert track['ruleContext']['track']['content']==rule['track_layers']
assert radius['ruleContext']['minRadius']==rule['via_outer_radius_min_raw'] and radius['ruleContext']['minInner']==rule['via_drill_radius_min_raw']
for record in pcb['records']:
    if record['header']['type']=='RULE_SELECTOR':assert not {'TRACK','RADIUS'}.intersection(record['data'].get('ruleKeyValue',{}))
    if record['header']['type']=='VIA':assert not record['data'].get('ruleName')
dest=root/'editing/kicad-source-rules-projected'/a.candidate
if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve edits before --overwrite-generated')
shutil.copytree(source,dest,dirs_exist_ok=True)
project=dest/(board.stem+'.kicad_pro');data=json.loads(project.read_text())
quantize=lambda mm:round(mm*1e6)/1e6
values={'min_track_width':quantize(rule['track_min_mm']),'min_via_diameter':quantize(rule['via_diameter_min_mm']),'min_through_hole_diameter':quantize(rule['via_drill_min_mm'])}
data.setdefault('board',{}).setdefault('design_settings',{}).setdefault('rules',{}).update(values)
project.write_text(json.dumps(data,indent=2))
copied=dest/board.name;assert hashlib.sha256(copied.read_bytes()).digest()==hashlib.sha256(board.read_bytes()).digest()
drc=dest/'drc-source-minima.json'
run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(drc),str(copied)],capture_output=True,text=True,timeout=90)
assert run.returncode==0,run.stderr
report=json.loads(drc.read_text());assert not report['schematic_parity']
result={'candidate':a.candidate,'source_board':str(board.relative_to(root)),'board_sha256':hashlib.sha256(copied.read_bytes()).hexdigest(),'board_bytes_unchanged':True,'source_replay_sha256':hashlib.sha256(replay.read_bytes()).hexdigest(),'evidence_sha256':hashlib.sha256(evidence.read_bytes()).hexdigest(),'translated_rules_mm':values,'quantization':'nearest native integer nanometre, matching the geometry conversion','source_minima':rule,'scope':'global track and via diameter minima; KiCad through-hole minimum uses the evidenced source via-drill minimum, also affecting PTH pads; no existing PTH violation is hidden by that 1 nm quantization correction','untranslated':['SAFE pair-class matrix','netclass/custom rule selection outside TRACK/RADIUS','mask and paste','other hole/edge/clearance rules','maximum/default routing dimensions'],'schematic_parity':report['schematic_parity'],'drc_counts':dict(collections.Counter(v['type'] for v in report['violations'])),'unconnected':len(report['unconnected_items']),'manufacturing_ready':False}
(dest/'source-minima-audit.json').write_text(json.dumps(result,indent=2))
(dest/'README.txt').write_text('Partial source-rule projection engineering copy. Read ../../../COPPER-CONSOLIDATION.txt and source-minima-audit.json. Copper is unchanged from consolidated parent. Only track/via/through-hole minima are projected from installed-decoder evidence. All other source-rule semantics and manufacturing qualification remain open. Never refill static copper.\n')
print(json.dumps({key:result[key] for key in ['candidate','board_bytes_unchanged','translated_rules_mm','drc_counts','unconnected','manufacturing_ready']}))
