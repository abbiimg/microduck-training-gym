"""Read-only source/cache/history attribution for recovered copper overlaps.

Run in the isolated WSL PCB Python with --reader pointing at the separately
installed, pinned community reader. No EasyEDA session/activation is used.
"""
from pathlib import Path
import argparse,collections,hashlib,json,sys
import pcbnew as k
from shapely import affinity
from shapely.geometry import Polygon
from shapely.ops import unary_union

p=argparse.ArgumentParser();p.add_argument('--reader',type=Path,required=True);p.add_argument('--decoder',type=Path);a=p.parse_args()
sys.path.insert(0,str(a.reader.resolve()))
from lceda_pcb_geometry import polygon,pad_shape,hole_shape,transform
ROOT=Path(__file__).resolve().parents[1];MIL=.0254;CACHE=.254
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
scale=lambda g,s:affinity.scale(g,s,s,origin=(0,0))
flip=lambda g:affinity.scale(g,1,-1,origin=(0,0))
def native(poly):
    poly=k.SHAPE_POLY_SET(poly);poly.Unfracture()
    def ring(r):return [(r.CPoint(i).x/1e6,r.CPoint(i).y/1e6) for i in range(r.PointCount())]
    result=[]
    for i in range(poly.OutlineCount()):
        g=Polygon(ring(poly.COutline(i)),[ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i))]);assert g.is_valid;result.append(g)
    return unary_union(result)
def zonegeom(z):return native(z.GetFilledPolysList(z.GetLayer()))
def padgeom(pad,layer):
    poly=k.SHAPE_POLY_SET();pad.TransformShapeToPolygon(poly,layer,0,1,k.ERROR_INSIDE);return native(poly)
def project(name):
    directory=ROOT/'editing/recovered-community'/name
    replay=directory/'replayed-project.json';data=json.loads(replay.read_text(encoding='utf8'))
    pcb=next(d for d in data['documents'] if d['head']['docType']=='PCB')
    return directory,data,pcb['records'],pcb['head']['uuid'],replay
def cache_geometry(owner,cache,boundary):
    assert all(f.get('fill') is True and f.get('strokeWidth',0)==0 for f in cache['data']['pourFill']), 'Targeted active cache dialect changed'
    raw=unary_union([scale(polygon(f['path'],scale=CACHE),CACHE) for f in cache['data']['pourFill']])
    width=owner['data']['pourType']['fineness']*MIL
    return raw.intersection(boundary),raw.buffer(width/2).intersection(boundary) if width else raw.intersection(boundary)
def history(path,doc,ids):
    result=[];current=None;segment=0;client=None
    for line_no,line in enumerate(path.read_text(encoding='utf8').splitlines(),1):
        head,text=line.split('||',1);head=json.loads(head)
        try:body=json.JSONDecoder().raw_decode(text)[0]
        except json.JSONDecodeError:body=None
        if head['type']=='DOCHEAD':
            current=body['uuid'];segment+=1;client=body.get('client')
        ident=head.get('id','')
        if current!=doc or not any(i==ident or i in ident for i in ids):continue
        if head['type'] not in ['FILL','POUR','POURED','COMPONENT','PAD_NET','ATTR']:continue
        summary={key:value for key,value in body.items() if key not in ['pourFill','path']} if isinstance(body,dict) else None
        if isinstance(body,dict) and 'path' in body:summary['path_sha256']=hashlib.sha256(json.dumps(body['path'],sort_keys=True).encode()).hexdigest()
        if isinstance(body,dict) and 'pourFill' in body:summary['cache_fill_count']=len(body['pourFill'])
        result.append({'type':head['type'],'id':ident,'ticket':head['ticket'],'line':line_no,'segment':segment,'client':client,'tombstone':body is None,'data_summary':summary,'record_line_sha256':hashlib.sha256(line.encode()).hexdigest()})
    return result
def recordsummary(r):return {key:r[key] for key in ['header','line','segment','client'] if key in r}
def outside_band(first,second):
    result=first.difference(second.buffer(.000002)).area+second.difference(first.buffer(.000002)).area
    assert result<1e-12,('Source/native geometry differs outside2nm band',result)
    return result

results={}
directory,data,rr,doc,replay=project('wire_hub_1V0A')
attrs=collections.defaultdict(dict)
for r in rr:
    if r['header']['type']=='ATTR':attrs[r['data'].get('parentId')][r['data']['key']]=r['data'].get('value')
comp=next(r for r in rr if r['header']['type']=='COMPONENT' and attrs[r['header']['id']].get('Designator')=='CN1')
cid=comp['header']['id'];fp=next(d for d in data['documents'] if d['head']['docType']=='FOOTPRINT' and d['head']['uuid']==attrs[cid]['Footprint'])
pad=next(r for r in fp['records'] if r['header']['type']=='PAD' and str(r['data'].get('num'))=='1')
pd=pad['data'];pad_source=scale(transform(pad_shape(pd),comp['data'],False),MIL)
hole_source=scale(transform(hole_shape(pd),comp['data'],False),MIL)
owner=next(r for r in rr if r['header']['type']=='POUR' and r['header']['id']=='6433fd3c96979807')
cache=next(r for r in rr if r['header']['type']=='POURED' and json.loads(r['header']['id'])[1]==owner['header']['id'])
boundary=scale(polygon(next(r for r in rr if r['header']['type']=='BOARD')['data']['path']),MIL)
raw,buffered=cache_geometry(owner,cache,boundary)
pairedpath=ROOT/'editing/kicad-paired/wire_hub_1V0A/wire_hub_1V0A.kicad_pcb';paired=k.LoadBoard(str(pairedpath))
npad=next(p for f in paired.GetFootprints() if f.GetReference()=='CN1' for p in f.Pads() if p.GetNumber()=='1')
nground=unary_union([zonegeom(z) for z in paired.Zones() if z.GetLayer()==k.B_Cu and z.GetZoneName()=='Recovered '+owner['header']['id']])
npadg=padgeom(npad,k.B_Cu)
h=history(directory/'geometry-input.epru',doc,[cid,owner['header']['id']])
first=next(r for r in h if r['type']=='COMPONENT' and not r['tombstone'])
result={
 'source_replay_sha256':sha(replay),'raw_history':str((directory/'geometry-input.epru').relative_to(ROOT)),'raw_history_sha256':sha(directory/'geometry-input.epru'),
 'source_component':recordsummary(comp),'source_pad':recordsummary(pad),'source_pour':recordsummary(owner),'source_cache':recordsummary(cache),
 'component_first_appearance_ticket':first['ticket'],'latest_component_ticket':comp['header']['ticket'],'latest_cache_ticket':cache['header']['ticket'],
 'cache_predates_component_first_appearance':cache['header']['ticket']<first['ticket'],
 'original_source_pad_center_mm':[pad_source.centroid.x,pad_source.centroid.y],'pad_copper_area_mm2':pad_source.area,'pad_hole_area_mm2':hole_source.area,
 'source_unexpanded_cache_to_pad':{'distance_mm':raw.distance(pad_source),'intersection_area_mm2':raw.intersection(pad_source).area,'physical_annulus_overlap_mm2':raw.intersection(pad_source.difference(hole_source)).area},
 'source_optimized_cache_to_pad':{'distance_mm':buffered.distance(pad_source),'intersection_area_mm2':buffered.intersection(pad_source).area,'physical_annulus_overlap_mm2':buffered.intersection(pad_source.difference(hole_source)).area},
 'preunion_native':{'board':str(pairedpath.relative_to(ROOT)),'sha256':sha(pairedpath),'pad_cache_intersection_area_mm2':npadg.intersection(nground).area,'source_pad_xor_mm2':flip(pad_source).symmetric_difference(npadg).area,'source_ground_xor_mm2':flip(buffered).symmetric_difference(nground).area,'pad_difference_outside_2nm_band_mm2':outside_band(flip(pad_source),npadg),'ground_difference_outside_2nm_band_mm2':outside_band(flip(buffered),nground)},
 'history':h,
 'attribution':'Latest source GND cache predates introduction of CN1 and its current Battery/GND pad assignments. Positive overlap exists directly in source cache/current source pad, including after drill subtraction, and in native paired board before consolidation. Neither union nor net repair creates it.',
 'recommended_copy_only_correction':'Intentional engineering subtraction of the new Battery pad exclusion from stale GND static copper using source PTH/pour clearance; preserve source and literal recovered candidates. Full source cache regeneration remains unqualified.'}
assert result['cache_predates_component_first_appearance']
assert result['source_optimized_cache_to_pad']['physical_annulus_overlap_mm2']>0
results['wire_hub_1V0A']=result

directory,data,rr,doc,replay=project('imu_to_dxl_1V0A')
vddid='746a86ec39ac9e6d';groundids=['9e6ef9e9729c8ee7','84a63625734e769f']
fill=next(r for r in rr if r['header']['type']=='FILL' and r['header']['id']==vddid)
vdd=scale(polygon(fill['data']['path']),MIL)
boundary=scale(polygon(next(r for r in rr if r['header']['type']=='BOARD')['data']['path']),MIL)
h=history(directory/'geometry-input.epru',doc,[vddid,*groundids])
vddhist=[r for r in h if r['id']==vddid and r['type'] in ['FILL','POUR']]
fillpathhash=vddhist[0]['data_summary']['path_sha256']
samepath=[r for r in vddhist if r['type']=='POUR' and not r['tombstone'] and r['data_summary']['path_sha256']==fillpathhash]
assert samepath
assert vddhist[-1]['type']=='POUR' and vddhist[-1]['tombstone']
sourcepairs=[];groundraw=[];groundbuffered=[]
for ident in groundids:
    owner=next(r for r in rr if r['header']['type']=='POUR' and r['header']['id']==ident)
    cache=next(r for r in rr if r['header']['type']=='POURED' and json.loads(r['header']['id'])[1]==ident)
    raw,buffered=cache_geometry(owner,cache,boundary);groundraw.append(raw);groundbuffered.append(buffered)
    sourcepairs.append({'source_pour':recordsummary(owner),'source_cache':recordsummary(cache),'owner_net':owner['data']['netName'],'raw_cache_fill_intersection_mm2':raw.intersection(vdd).area,'optimized_cache_fill_intersection_mm2':buffered.intersection(vdd).area})
pairedpath=ROOT/'editing/kicad-paired/imu_to_dxl_1V0A/imu_to_dxl_1V0A.kicad_pcb';paired=k.LoadBoard(str(pairedpath))
ca=json.loads((ROOT/'editing/kicad-integrated/imu_to_dxl_1V0A-transition-hypothesis/consolidation-audit.json').read_text());excluded={x['uuid'] for x in ca['excluded_source_geometry']}
nground=unary_union([zonegeom(z) for z in paired.Zones() if z.GetLayer()==k.F_Cu and z.GetZoneName() in ['Recovered '+i for i in groundids] and z.m_Uuid.AsString() not in excluded])
nvdd=unary_union([zonegeom(z) for z in paired.Zones() if z.GetLayer()==k.F_Cu and z.GetZoneName()=='Recovered '+vddid])
activecollisions=collections.defaultdict(list)
objecttypes={'LINE','ARC','CARC','POLY','FILL','POUR','PAD','VIA','COMPONENT','REGION','STRING','TEARDROP','HOLE','IMAGE'}
for r in rr:
    if r['header']['type'] in objecttypes:activecollisions[r['header']['id']].append(r['header']['type'])
results['imu_to_dxl_1V0A']={
 'source_replay_sha256':sha(replay),'raw_history':str((directory/'geometry-input.epru').relative_to(ROOT)),'raw_history_sha256':sha(directory/'geometry-input.epru'),
 'source_fill':recordsummary(fill),'source_fill_net':fill['data']['netName'],'source_fill_area_mm2':vdd.area,'source_fill_bridging_flag':fill['data'].get('isBridgingCopper'),'source_fill_networkList':fill['data'].get('networkList'),
 'same_id_identical_contour_FILL_to_POUR':samepath,'latest_same_id_shape_event':vddhist[-1],'source_ground_pairs':sourcepairs,
 'source_ground_union_overlap_unexpanded_mm2':unary_union(groundraw).intersection(vdd).area,
 'source_ground_union_overlap_optimized_mm2':unary_union(groundbuffered).intersection(vdd).area,
 'preunion_native':{'board':str(pairedpath.relative_to(ROOT)),'sha256':sha(pairedpath),'excluded_ambiguous_old_ground_fill_uuids':sorted(excluded),'ground_vdd_intersection_mm2':nground.intersection(nvdd).area,'source_vdd_xor_mm2':flip(vdd).symmetric_difference(nvdd).area,'source_ground_xor_mm2':flip(unary_union(groundbuffered)).symmetric_difference(nground).area,'vdd_difference_outside_2nm_band_mm2':outside_band(flip(vdd),nvdd),'ground_difference_outside_2nm_band_mm2':outside_band(flip(unary_union(groundbuffered)),nground)},
 'active_geometric_ids_with_multiple_record_types':{key:types for key,types in activecollisions.items() if len(set(types))>1},'history':h,
 'attribution':'Positive overlap exists in latest cached source ground versus an ancient FILL retained by typed replay, before union and without optimization expansion. The same source VDD contour later becomes a same-ID POUR and that POUR has an explicit tombstone. This supports a stale-FILL/type-transition interpretation; it does not prove global cross-type replay semantics.',
    'recommended_copy_only_interpretation':'Keep literal and existing old-GND-transition hypothesis untouched. A separate clearly labeled dual-transition hypothesis may omit ancient VDD FILL 746a86ec39ac9e6d as superseded/deleted after the same-ID, identical-contour POUR lifecycle. Do not claim confirmed source intent until the author or source client state resolves cross-type identity.'}

decoder_evidence=None
if a.decoder:
    text=a.decoder.read_text(encoding='utf8');tokens={'raw_fineness_divided_by10_in_POUR_decoder':'let d=i.fineness/10;r.optimizationValue=d','cached_copper_inherits_owner_layer_and_net':'let{layerId:a,net:o}=this.profile','solid_cached_copper_expands_each_primitive_by_optimization_width':'n.push(h.stroke(this.optimizationWidth,vn.ROUND,$e.CW))'}
    offsets={key:text.find(token) for key,token in tokens.items()};assert all(x>=0 for x in offsets.values()),'Installed decoder version changed; review evidence again'
    decoder_evidence={'path':str(a.decoder),'sha256':sha(a.decoder),'verified_semantic_token_offsets':offsets,'scope':'Local installed official decoder 4.1.67 only, read without running or activating the client. Recovered owner fineness 8 becomes internal 0.8 at a 0.01-inch scale; shape math adds a round stroke of that width. Cache layer/net inherit the current POUR owner. No global cross-type deletion semantics are established by these model-stage excerpts.'}
out={'read_only':True,'boards_edited':False,'rules_edited':False,'activation_used':False,'coordinate_profile':'source geometry mil; POURED cache0.01 inch; nativeglobalY flipped','source_cache_buffer_policy':'owner solid fineness/2 round boundary; raw unexpanded result also measured','installed_decoder_evidence':decoder_evidence,'results':results,'manufacturing_ready':False}
(ROOT/'audit/copper-overlap-source-review.json').write_text(json.dumps(out,indent=2))
(ROOT/'audit/copper-overlap-source-review.txt').write_text('''MicroDuck copper-overlap source/history review - 2026-10-27

No source, native board or rules were edited by this audit. Source coordinates,
cache polygons and current pad definitions were measured independently of the
KiCad consolidation. Native paired boards before union give the same overlaps;
source/native polygon discrepancies are confined to a 2 nm coordinate band.

Hub: demonstrably stale cache versus new connector
The current bottom GND POUR record 6433fd3c96979807 is ticket 47248; its last
POURED cache is ticket 47251. CN1 (ID a7ac844818530c4e) first appears later at
ticket 47725, initially with empty pad nets. It moves to source coordinates
x = 2305 mil, y = 915 mil, angle = 180 degrees at ticket 47940. Its current
pad 2 GND and pad 1 Battery assignments are tickets 47941 and 47942.
This cached copper could not account
for the subsequently added connector. Direct source/current-pad intersection
is 0.079409 mm2 even without optimization expansion, and 0.201673 mm2 with the documented
owner-fineness boundary stroke. Subtracting the actual drill leaves the same
positive annulus overlap. Original paired KiCad copper already overlaps; the
same-net union and earlier BATTERY/Battery repair did not introduce it.

An intentional engineering candidate may subtract the new Battery pad plus
its exact source PTH-pad/pour clearance from the stale GND copper. This is a
design correction derived from evidence, not exact source recovery or a full
cache refill. Keep all source and literal copies unchanged.

Revised IMU: stale typed FILL after same-ID conversion/deletion
VDD_BUS FILL record 746a86ec39ac9e6d is ticket 38492. The same ID with an
identical contour becomes a POUR record at ticket 44571. Its author-assigned
object name is "POUR5"; the suffix 5 is part of that name, not a copper layer.
The record is on source layer 1 (top copper). It receives POURED cache records
at tickets 44574 and 44593, then an explicit POUR tombstone at ticket 44594.
The typed (type, id) replay retains the earlier FILL because no FILL tombstone
is present. The latest GND caches at tickets 45215 and 45217 are later still.
The retained old FILL overlaps their union by 2.878691 mm2 without optimization
expansion, or 3.818385 mm2 with it; before-union native copper gives 3.818383 mm2.
This accounts for the two positive-overlap regions found in the existing
transition hypothesis. It is separate from old GND FILL 84a63625734e769f.

The VDD_BUS FILL has isBridgingCopper=false and an empty networkList. Cache net/layer
come from its owner POUR, and the cached geometry is already the pour result;
no verified hidden net override or priority operation was found that cancels
the retained old FILL. The later matching-ID POUR lifecycle strongly supports
an obsolete-FILL interpretation, but does not prove global cross-type replay
semantics. Other POLY/FILL shared IDs exist, so globally dropping older shapes
would be unjustified. Do not change the generic reader or existing candidates
on this inference.

Proposed next IMU experiment: preserve the literal and old-GND-only hypothesis,
then create a separately named dual-transition hypothesis that also omits
the demonstrably later-converted/deleted VDD_BUS FILL. Record the precise source
history and qualification boundary, and rerun copper diff, parity and DRC.

Installed official decoder inspection
The optional JSON evidence records exact local file SHA and semantic offsets.
POUR fineness is converted from mil to 0.01-inch internal units; solid cached
copper math includes a round boundary stroke of its optimization width. The
cache inherits owner layer and net. These observations support the measured
geometry profile; they do not establish cross-type record deletion behavior.
No client execution, account login or EasyEDA activation was required.

Repeatable read-only tool: tools/review_copper_overlap_sources.py --reader PATH
[--decoder installed-decodeWorker.js]. Run with the WSL PCB Python. The JSON
contains exact history line/ticket/client/segment hashes and source/native
areas. Within the raw history list, "segment" counts DOCHEAD entries across
the entire log. Active source record summaries retain the reader's own
per-document segment field; those are different counters. Line numbers and
record-line hashes identify the exact raw records in either representation.
All manufacturing qualification flags remain false.
''')
print(json.dumps({name:{key:value for key,value in result.items() if key in ['cache_predates_component_first_appearance','source_optimized_cache_to_pad','source_ground_union_overlap_optimized_mm2','preunion_native']} for name,result in results.items()},indent=2))
