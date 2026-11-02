from pathlib import Path
import json,math,collections,argparse
import pcbnew as k
root=Path(__file__).resolve().parents[1];results=[]
parser=argparse.ArgumentParser();parser.add_argument('--transition-hypothesis',action='store_true');parser.add_argument('--engineering',action='store_true');args=parser.parse_args()
tree='kicad-engineering' if args.engineering else 'kicad-routed-transition-hypothesis' if args.transition_hypothesis else 'kicad-routed'
for folder in sorted((root/'editing'/tree).iterdir()):
    if not folder.is_dir():continue
    audit=json.loads((folder/'conversion-audit.json').read_text(encoding='utf-8'))
    b=k.LoadBoard(str(folder/(folder.name+'.kicad_pcb')))
    pads=collections.defaultdict(list)
    for fp in b.GetFootprints():
        for pad in fp.Pads():pads[(fp.GetReference(),pad.GetNumber())].append(pad)
    errors=[]
    for expected in audit['expected_pads']:
        pp=pads[(expected['reference'],expected['number'])]
        found=[p for p in pp if math.hypot(p.GetPosition().x/1e6-expected['x_mm'],p.GetPosition().y/1e6-expected['y_mm'])<.000002 and (not expected.get('native_uuid') or p.m_Uuid.AsString()==expected['native_uuid'])]
        if not found:errors.append({'kind':'missing_or_shifted_pad','expected':expected});continue
        if not any(p.GetNetname()==expected['net'] for p in found):errors.append({'kind':'pad_net','expected':expected})
        if expected['drill_mm'] is not None and not any(abs(p.GetDrillSize().x/1e6-expected['drill_mm'])<.000002 and abs(p.GetDrillSize().y/1e6-expected['drill_mm'])<.000002 for p in found):errors.append({'kind':'drill_size','expected':expected})
        for layer in expected.get('copper_layers',[]):
            pad=next(p for p in found if p.GetNetname()==expected['net'])
            poly=pad.GetEffectivePolygon(layer);box=poly.BBox()
            bounds=[box.GetX()/1e6,box.GetY()/1e6,(box.GetX()+box.GetWidth())/1e6,(box.GetY()+box.GetHeight())/1e6]
            if abs(poly.Area()/1e12-expected['copper_area_mm2'])>.0001 or max(abs(x-y) for x,y in zip(bounds,expected['copper_bounds_mm']))>.000005:
                errors.append({'kind':'pad_copper_geometry','reference':expected['reference'],'number':expected['number'],'layer':layer,'area_mm2':poly.Area()/1e12,'expected_area_mm2':expected['copper_area_mm2'],'bounds_mm':bounds,'expected_bounds_mm':expected['copper_bounds_mm']})
    sourcepins=json.loads((root/'editing/recovered-community'/folder.name/'pinmap-0.json').read_text(encoding='utf-8'))
    electrical=[]
    for comp in sourcepins:
        if comp['designator'].startswith('PORT'):continue
        for pin in comp['pins']:
            if not pin.get('net'):continue
            pp=pads.get((comp['designator'],str(pin['number'])),[])
            if not pp or not any(p.GetNetname()==pin['net'] for p in pp):
                electrical.append({'reference':comp['designator'],'pin':str(pin['number']),'schematic_net':pin['net'],'pcb_nets':[p.GetNetname() for p in pp]})
    areas=collections.defaultdict(float)
    for z in b.Zones():areas[z.GetZoneName().removeprefix('Recovered ')]+=z.GetFilledPolysList(z.GetLayer()).Area()/1e12
    areaerrors=[]
    for name,area in audit['expected_static_copper_area_mm2'].items():
        if abs(areas[name]-area)>.0001:areaerrors.append({'source':name,'expected_mm2':area,'actual_mm2':areas[name]})
    result={'candidate':folder.name,'pads_checked':len(audit['expected_pads']),
      'pad_geometry_or_net_errors':errors,'schematic_to_pcb_named_pin_mismatches':electrical,
      'filled_copper_area_errors':areaerrors,'zone_fill_count':len(b.Zones()),
      'manufacturing_ready':False}
    (folder/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    results.append({key:len(value) if isinstance(value,list) else value for key,value in result.items()})
print(json.dumps(results,indent=2))
if any(row['pad_geometry_or_net_errors'] or row['filled_copper_area_errors'] for row in results):
    raise SystemExit(1)
