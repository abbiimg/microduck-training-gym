"""Independently check paired copies against parent boards and native parity."""
from pathlib import Path
import json,subprocess,collections
import pcbnew as k
root=Path(__file__).resolve().parents[1];results=[]
def netname(name):
    name=name.removeprefix('/')
    if name.startswith('unconnected-('):return ''
    return 'RECOVERED_UNNAMED_1' if name=='$1N175' else name
def width(item):return item.GetWidth(k.F_Cu) if isinstance(item,k.PCB_VIA) else item.GetWidth()
def shape(poly):
    def ring(r):return tuple((r.CPoint(i).x,r.CPoint(i).y) for i in range(r.PointCount()))
    return tuple((ring(poly.COutline(i)),tuple(ring(poly.CHole(i,j)) for j in range(poly.HoleCount(i)))) for i in range(poly.OutlineCount()))
for path in sorted((root/'editing/kicad-paired').glob('*/*.kicad_pcb')):
    audit=json.loads(path.with_name('pairing-audit.json').read_text());parent=k.LoadBoard(str(root/audit['parent_board']));board=k.LoadBoard(str(path))
    old={p.m_Uuid.AsString():p for f in parent.GetFootprints() for p in f.Pads()}
    errors=[];checked=0
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            before=old[pad.m_Uuid.AsString()];checked+=1
            if before.GetPosition()!=pad.GetPosition() or before.GetDrillSize()!=pad.GetDrillSize() or netname(before.GetNetname())!=netname(pad.GetNetname()):errors.append(['pad',fp.GetReference(),pad.GetNumber()])
            for layer in [k.F_Cu,k.B_Cu]:
                if before.IsOnLayer(layer)!=pad.IsOnLayer(layer):errors.append(['pad_layers',fp.GetReference(),pad.GetNumber()])
                elif before.IsOnLayer(layer) and shape(before.GetEffectivePolygon(layer))!=shape(pad.GetEffectivePolygon(layer)):errors.append(['pad_polygon',fp.GetReference(),pad.GetNumber(),layer])
    oldtracks={t.m_Uuid.AsString():t for t in parent.GetTracks()}
    assert len(oldtracks)==len(board.GetTracks())
    for item in board.GetTracks():
        before=oldtracks[item.m_Uuid.AsString()]
        if before.GetStart()!=item.GetStart() or before.GetEnd()!=item.GetEnd() or width(before)!=width(item) or netname(before.GetNetname())!=netname(item.GetNetname()):errors.append(['track',item.m_Uuid.AsString()])
    oldzones={z.m_Uuid.AsString():z for z in parent.Zones()};assert len(oldzones)==len(board.Zones())
    for item in board.Zones():
        before=oldzones[item.m_Uuid.AsString()]
        if shape(before.GetFilledPolysList(before.GetLayer()))!=shape(item.GetFilledPolysList(item.GetLayer())) or netname(before.GetNetname())!=netname(item.GetNetname()):errors.append(['zone',item.m_Uuid.AsString()])
    reportpath=path.with_name('drc-parity.json')
    run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(reportpath),str(path)],capture_output=True,text=True,timeout=90)
    assert run.returncode==0,(path,run.stderr)
    report=json.loads(reportpath.read_text())
    result={'candidate':path.stem,'pads_checked':checked,'geometry_or_net_errors':errors,'schematic_parity':report.get('schematic_parity',[]),'drc_counts':dict(collections.Counter(r['type'] for r in report['violations'])),'unconnected':len(report['unconnected_items']),'manufacturing_ready':False}
    path.with_name('paired-validation.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True);results.append(result)
(root/'editing/paired-validation-summary.json').write_text(json.dumps(results,indent=2))
if any(r['geometry_or_net_errors'] or r['schematic_parity'] for r in results):raise SystemExit(1)
