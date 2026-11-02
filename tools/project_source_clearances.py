"""Project evidenced SAFE pair classes into isolated KiCad engineering rules.

Leaves unmapped native defaults intact. Mixed saved-zone classes and symmetric
two-drill checks use an explicitly conservative maximum, not full equivalence.
"""
from pathlib import Path
import argparse,json,shutil,hashlib,subprocess,collections,itertools
import pcbnew as k
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--overwrite-generated',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];parent=root/'editing/kicad-source-rules-projected'/a.candidate
if a.candidate=='POGO_PIN_1V0A':parent=root/'editing/kicad-graphic-corrected'/a.candidate
source=next(parent.glob('*.kicad_pcb'));name=source.stem
replay=root/'editing/recovered-community'/name/'replayed-project.json'
pcb=next(d for d in json.loads(replay.read_text(encoding='utf-8'))['documents'] if d['head']['docType']=='PCB');records=pcb['records']
get=lambda typ:[r for r in records if r['header']['type']==typ]
rules={tuple(json.loads(r['header']['id'])[1:]):r['data'] for r in get('RULE')}
safe=[(key,data) for key,data in rules.items() if key[0]=='SAFE' and data['ruleState']=='DEFAULT'];assert len(safe)==1
other=[data for key,data in rules.items() if key[0]=='OTHER' and data['ruleState']=='DEFAULT'];assert len(other)==1
for r in get('RULE_SELECTOR'):assert not {'SAFE','OTHER'}.intersection(r['data'].get('ruleKeyValue',{})),r
raw=safe[0][1]['ruleContext'];tables={row['layerId']:row['content'] for row in raw['safeSpacing']};assert 1 in tables
def table(layer):return tables[1] if raw['isForAll']=='ALL' else tables.get(layer,tables[1])
def number(matrix,x,y):return matrix[max(x,y)][min(x,y)]
quantize=lambda raw:round(raw*.0254*1e6)/1e6
def maximum(classes1,classes2,layer=None):
    matrices=[table(layer)] if layer else [tables[1]] if raw['isForAll']=='ALL' else list(tables.values())
    return quantize(max(number(matrix,x,y) for matrix in matrices for x in classes1 for y in classes2))
dest=root/'editing/kicad-source-clearances'/a.candidate
if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve edits before --overwrite-generated')
shutil.copytree(parent,dest,dirs_exist_ok=True)
board=k.LoadBoard(str(source));ca=json.loads((parent/'consolidation-audit.json').read_text())
old=k.LoadBoard(str(root/ca['parent_board']));excluded={e['uuid'] for e in ca['excluded_source_geometry']}
sourceclasses=collections.defaultdict(set)
for typ,cls in [('FILL',6),('TEARDROP',6),('POUR',7)]:
    for r in get(typ):sourceclasses[(r['header']['id'],r['data']['layerId'])].add(cls)
def poly(zone):
    out=k.SHAPE_POLY_SET(zone.GetFilledPolysList(zone.GetLayer()));out.Unfracture();return out
oldzones=[]
for z in old.Zones():
    if z.m_Uuid.AsString() in excluded:continue
    ident=z.GetZoneName().removeprefix('Recovered ');classes=sourceclasses[(ident,1 if z.GetLayer()==k.F_Cu else 2)];assert classes,ident
    oldzones.append((z,poly(z),classes))
zonegroups=collections.defaultdict(list);ownership=[]
for zone in board.Zones():
    region=poly(zone);contributors=[];classes=set()
    for previous,geom,cls in oldzones:
        if previous.GetLayer()!=zone.GetLayer() or previous.GetNetname()!=zone.GetNetname():continue
        overlap=k.SHAPE_POLY_SET();overlap.BooleanIntersection(region,geom)
        if overlap.Area()>0:
            classes.update(cls);contributors.append({'source_zone_uuid':previous.m_Uuid.AsString(),'source_name':previous.GetZoneName(),'source_classes':sorted(cls),'overlap_mm2':overlap.Area()/1e12})
    assert classes,(zone.GetZoneName(),'No source-class contributor')
    key=tuple(sorted(classes));zonegroups[key].append(zone.GetZoneName())
    ownership.append({'native_zone_uuid':zone.m_Uuid.AsString(),'native_zone_name':zone.GetZoneName(),'source_classes':list(key),'contributors':contributors,'conservative_class_collapse':len(key)>1})
documents=json.loads(replay.read_text(encoding='utf-8'))['documents'];footprints={d['head']['uuid']:d for d in documents if d['head']['docType']=='FOOTPRINT'}
attributes=collections.defaultdict(dict)
for r in get('ATTR'):attributes[r['data'].get('parentId')][r['data']['key']]=r['data'].get('value')
for component in get('COMPONENT'):
    attrs={**component['data'].get('attrs',{}),**attributes[component['header']['id']]}
    for r in footprints[attrs['Footprint']]['records']:
        if r['header']['type']=='PAD':assert r['data'].get('padType','NORMAL')=='NORMAL','Placed test-pad classes need explicit mapping'
for r in get('PAD'):assert r['data'].get('padType','NORMAL')=='NORMAL','Standalone test-pad class needs explicit mapping'
# Test-pad source classes3/4 are not inferred from native pads. Their individual
# native names must be classified before adding them to this bounded projection.
categories=[('track',(0,),"X.Type == 'Track'"),('smd',(1,),"X.Type == 'Pad' && X.Pad_Type == 'SMD'"),('pth',(2,),"X.Type == 'Pad' && X.Pad_Type == 'Through-hole'"),('via',(5,),"X.Type == 'Via'"),('graphic',(9,),"X.Type == 'Graphic' && X.Layer != 'Edge.Cuts'")]
for classes,names in sorted(zonegroups.items()):
    assert all("'" not in n for n in names)
    expression="X.Type == 'Zone' && ("+' || '.join("X.Name == '"+n+"'" for n in names)+')'
    categories.append(('zone_'+'_'.join(map(str,classes)),classes,expression))
native=['(version 1)'];projected=[]
def emit(label,condition,constraint,value,layer=None,scope='source pair minimum'):
    native.append('(rule '+json.dumps(label)+'\n'+('  (layer '+json.dumps(layer)+')\n' if layer else '')+('  (condition '+json.dumps(condition)+')\n' if condition else '')+'  (constraint '+constraint+' (min '+format(value,'.6f')+'mm)))')
    projected.append({'name':label,'condition':condition,'constraint':constraint,'minimum_mm':value,'layer':layer,'scope':scope})
for source_layer,native_layer in [(1,'F.Cu'),(2,'B.Cu')]:
    for first,second in itertools.combinations_with_replacement(categories,2):
        n1,c1,e1=first;n2,c2,e2=second
        condition='('+e1.replace('X.','A.')+') && ('+e2.replace('X.','B.')+')'
        emit('Source SAFE '+native_layer+' '+n1+' to '+n2,condition,'clearance',maximum(c1,c2,source_layer),native_layer,'conservative maximum for source-class union' if len(c1)>1 or len(c2)>1 else 'source pair minimum')
for label,classes,expr in categories:
    emit('Source edge envelope '+label,expr.replace('X.','A.'),'edge_clearance',maximum(classes,(8,11)),scope='conservative maximum of source outline11/cutout8 across stored layers')
drilled=[cat for cat in categories if cat[0] in ['pth','via']]
for hole_owner in drilled:
    for copper in categories:
        label,c1,e1=hole_owner;n2,c2,e2=copper
        # Symmetric engine collapses the two directed drill-to-copper limits.
        values=[maximum((12,),c2)]
        if n2 in ['pth','via']:values.append(maximum((12,),c1))
        condition='('+e1.replace('X.','A.')+') && ('+e2.replace('X.','B.')+')'
        emit('Source drill envelope '+label+' to '+n2,condition,'hole_clearance',max(values),scope='conservative symmetric drill-to-copper envelope, layers maximized')
emit('Source drill to drill minimum',None,'hole_to_hole',quantize(other[0]['ruleContext']['holeClearance']),scope='source OTHER global drill-to-drill minimum; native provider selects drilled objects including vias')
dru=dest/(name+'.kicad_dru');dru.write_text('\n\n'.join(native)+'\n')
copied=dest/source.name;assert copied.read_bytes()==source.read_bytes(),'Copper/board bytes changed'
reportpath=dest/'drc-source-clearances.json'
run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(reportpath),str(copied)],capture_output=True,text=True,timeout=120)
(dest/'clearance-cli.log').write_text(run.stdout+run.stderr)
assert run.returncode==0,(run.stdout,run.stderr)
report=json.loads(reportpath.read_text());assert not report['schematic_parity']
result={'candidate':a.candidate,'parent_board':str(source.relative_to(root)),'board_sha256':hashlib.sha256(copied.read_bytes()).hexdigest(),'source_replay_sha256':hashlib.sha256(replay.read_bytes()).hexdigest(),'rules_sha256':hashlib.sha256(dru.read_bytes()).hexdigest(),'board_bytes_unchanged':True,'global_clearance_defaults_unchanged':True,'source_safe_rule':safe[0][0][1],'zone_class_ownership':ownership,'native_rules':projected,'full_rule_fidelity':False,'unmapped_scope':['NPTH mechanical object class','source test-pad classes3/4 without per-pad mapping','fallback source class10','mask/paste','regenerative copper rules','exact per-edge cutout/outline direction'],'schematic_parity':report['schematic_parity'],'drc_counts':dict(collections.Counter(v['type'] for v in report['violations'])),'unconnected':len(report['unconnected_items']),'manufacturing_ready':False}
(dest/'source-clearance-audit.json').write_text(json.dumps(result,indent=2))
(dest/'README.txt').write_text('Bounded source-clearance engineering copy. Copper/board bytes unchanged. Explicit supported SAFE pairs plus conservative zone/edge/drill envelopes; global defaults retained for unmapped objects. Full source-rule fidelity and manufacturing readiness remain false. Read ../../../SOURCE-CLEARANCE-PROGRESS.txt. Never refill static copper.\n')
print(json.dumps({key:result[key] for key in ['candidate','board_bytes_unchanged','drc_counts','unconnected','manufacturing_ready']}))
