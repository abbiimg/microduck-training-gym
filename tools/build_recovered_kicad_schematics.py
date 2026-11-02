"""Make editable KiCad electrical review schematics from recovered pin maps.
Generic symbols/layout; no claim of original graphics, footprints or PCB routing.
"""
from pathlib import Path
import json,uuid,collections,re
root=Path(__file__).resolve().parents[1]
def q(s): return json.dumps(str(s),ensure_ascii=False)
def uid(): return str(uuid.uuid4())
summary=[]
for source in sorted((root/'editing/recovered-community').iterdir()):
    if not source.is_dir(): continue
    comps=json.loads((source/'components.json').read_text(encoding='utf-8'))
    overrides=json.loads((source/'instance-attributes.json').read_text(encoding='utf-8')) if (source/'instance-attributes.json').exists() else {}
    pins={x['designator']:x for x in json.loads((source/'pinmap-0.json').read_text(encoding='utf-8'))}
    # Preserve unnamed direct-wire groups too. Do NOT use resolved_nets, which
    # intentionally traverses resistors and would incorrectly short components.
    lookup={}; parent={}
    for ref,entry in pins.items():
        for p in entry['pins']:
            key=(ref,str(p['number']));parent[key]=key
            lookup[ref+'.'+str(p['number'])]=key
            lookup[ref+'.'+str(p['pin'])]=key
    def find(k):
        while parent[k]!=k:k=parent[k]
        return k
    for ref,entry in pins.items():
        for p in entry['pins']:
            key=(ref,str(p['number']))
            if p.get('net'):continue
            for peer in p.get('wire_peers',[]):
                other=lookup.get(peer)
                if other:
                    op=next(z for z in pins[other[0]]['pins'] if str(z['number'])==other[1])
                    if not op.get('net'):parent[find(key)]=find(other)
    groups=collections.defaultdict(list)
    for key in parent:groups[find(key)].append(key)
    unnamed_labels={}
    for idx,members in enumerate(v for v in groups.values() if len(v)>1):
        for key in members:unnamed_labels[key]='RECOVERED_UNNAMED_'+str(idx+1)
    dest=root/'editing/kicad-recovered'/source.name
    dest.mkdir(parents=True,exist_ok=True)
    catalog={r['reference']:r for r in json.loads((dest/'parts-catalog.json').read_text(encoding='utf-8'))} if (dest/'parts-catalog.json').exists() else {}
    sheet=uid(); libs=[]; instances=[]; connections=[]; expected={}; skipped=[]
    for i,c in enumerate(comps):
        ref=c['designator']; entry=pins.get(ref)
        if not entry or not entry['pins']:
            skipped.append(ref); continue
        pp=entry['pins']; numbers=[str(p['number']) for p in pp]
        assert len(numbers)==len(set(numbers)),(ref,numbers)
        name='Recovered:'+ref
        n=len(pp); half=max(3.81,n*1.27+1.27)
        placed=overrides.get(ref,{})
        value=placed.get('Value') or placed.get('Manufacturer Part') or c.get('device') or c.get('title') or ref
        effects='(effects (font (size 1 1)))'
        props=f'(property "Reference" {q(ref)} (at 0 {half+2.54} 0) {effects}) (property "Value" {q(value)} (at 0 {-half-2.54} 0) {effects})'
        sympins=[]; x=75+(i%5)*150; y=50+(i//5)*90
        symbol_uuid=uid()
        expected[ref]={}
        for j,pin in enumerate(pp):
            number=str(pin['number']); py=(n-1)*1.27-j*2.54
            sympins.append(f'(pin passive line (at -12.7 {py} 0) (length 5.08) (name {q(pin.get("pin") or number)} {effects}) (number {q(number)} {effects}))')
            net=pin.get('net') or unnamed_labels.get((ref,number))
            expected[ref][number]=net or None
            if net:
                yy=y-py
                connections.append(f'(wire (pts (xy {x-17.78} {yy}) (xy {x-12.7} {yy})) (stroke (width 0) (type default)) (uuid {uid()}))')
                connections.append(f'(label {q(net)} (at {x-17.78} {yy} 0) (effects (font (size 1 1)) (justify right bottom)) (uuid {uid()}))')
            elif pin.get('not_connected'):
                connections.append(f'(no_connect (at {x-12.7} {y-py}) (uuid {uid()}))')
        libs.append(f'(symbol {q(name)} (pin_names (offset 0.5)) (in_bom yes) (on_board yes) {props} (symbol {q(ref+"_0_1")} (rectangle (start -7.62 {half}) (end 12.7 {-half}) (stroke (width 0.254) (type default)) (fill (type background)))) (symbol {q(ref+"_1_1")} {" ".join(sympins)}))')
        extras=''
        for field,val in {'Footprint':catalog.get(ref,{}).get('footprint'),'LCSC':placed.get('Supplier Part'),'Manufacturer Part':placed.get('Manufacturer Part')}.items():
            if val:extras+=f'(property {q(field)} {q(val)} (at {x} {y} 0) (effects (font (size 1 1)) (hide yes)))'
        instances.append(f'(symbol (lib_id {q(name)}) (at {x} {y} 0) (unit 1) (in_bom yes) (on_board yes) (dnp no) (uuid {symbol_uuid}) (property "Reference" {q(ref)} (at {x} {y-half-2.54} 0) {effects}) (property "Value" {q(value)} (at {x} {y+half+2.54} 0) {effects}) {extras} (instances (project {q(source.name)} (path {q("/"+sheet)} (reference {q(ref)}) (unit 1)))))')
    sch=f'(kicad_sch (version 20250114) (generator "recovered_review") (uuid {sheet}) (paper "A1") (lib_symbols {" ".join(libs)}) {" ".join(connections)} {" ".join(instances)})'
    sch=re.sub(r'\(uuid ([0-9a-f-]{36})\)',lambda m:'(uuid '+q(m[1])+')',sch)
    (dest/(source.name+'.kicad_sch')).write_text(sch,encoding='utf-8')
    (dest/'expected-pin-nets.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
    (dest/'README.txt').write_text('Recovered electrical review schematic. Generic passive-pin symbols; source graphics, electrical pin types, footprint mapping and PCB routing are NOT reconstructed. Do not use ERC as electrical validation. Source pinmap and expected-pin-nets.json retained for comparison. Reader-inferred connectivity remains subject to source/PDF verification. Unconnected pins are not assumed no-connect unless source says so.\n'+f'Entries without recovered pins: {skipped}\n',encoding='utf-8')
    summary.append({'candidate':source.name,'symbols':len(expected),'without_recovered_pins':skipped})
print(json.dumps(summary,indent=2))

