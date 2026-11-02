"""Verify library reload geometry independently of board/schematic parity."""
from pathlib import Path
import json,collections
import pcbnew as k
root=Path(__file__).resolve().parents[1];reports=[]
plugin=k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP)
def point(p):return (p.x,p.y)
def signature(fp):
    out=[]
    for pad in fp.Pads():
        layers=[]
        for layer in [k.F_Cu,k.B_Cu]:
            if pad.IsOnLayer(layer):
                poly=pad.GetEffectivePolygon(layer)
                rings=[]
                for i in range(poly.OutlineCount()):
                    ring=tuple(point(poly.COutline(i).CPoint(j)) for j in range(poly.COutline(i).PointCount()))
                    variants=[]
                    for seq in [ring,tuple(reversed(ring))]:
                        start=min(range(len(seq)),key=lambda n:seq[n]);variants.append(seq[start:]+seq[:start])
                    rings.append(min(variants))
                rings=tuple(sorted(rings))
                layers.append((int(layer),rings))
        out.append((pad.GetNumber(),point(pad.GetPosition()),point(pad.GetDrillSize()),tuple(layers)))
    return collections.Counter(out)
for path in sorted((root/'editing/kicad-paired').glob('*/*.kicad_pcb')):
    board=k.LoadBoard(str(path));errors=[];count=0
    for fp in board.GetFootprints():
        if fp.GetReference()=='SOURCE_BOARD_PADS':continue
        loaded=plugin.FootprintLoad(str(path.parent/'RecoveredLayout.pretty'),fp.GetReference());assert loaded
        scratch=k.BOARD();scratch.Add(loaded)
        loaded.SetPosition(fp.GetPosition())
        if loaded.GetLayer()!=fp.GetLayer():loaded.Flip(fp.GetPosition(),k.FLIP_DIRECTION_TOP_BOTTOM)
        loaded.SetOrientation(fp.GetOrientation())
        if signature(loaded)!=signature(fp):errors.append({'reference':fp.GetReference(),'issue':'pad geometry differs after library reload and standard board-side flip'})
        count+=1
    report={'candidate':path.stem,'footprints_checked':count,'library_geometry_errors':errors}
    path.with_name('library-validation.json').write_text(json.dumps(report,indent=2));reports.append(report)
print(json.dumps(reports,indent=2))
if any(r['library_geometry_errors'] for r in reports):raise SystemExit(1)
