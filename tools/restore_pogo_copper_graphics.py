"""Restore source POLY ring classification in a separate KiCad POGO copy."""
from pathlib import Path
import argparse,json,re,shutil,subprocess,hashlib,collections
import pcbnew as k
p=argparse.ArgumentParser();p.add_argument('--overwrite-generated',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];name='POGO_PIN_1V0A'
source=root/'editing/kicad-source-rules-projected'/name
dest=root/'editing/kicad-graphic-corrected'/name
if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve edits before --overwrite-generated')
shutil.copytree(source,dest,dirs_exist_ok=True)
path=source/(name+'.kicad_pcb');original=k.LoadBoard(str(path))
arcs=[t for t in original.GetTracks() if isinstance(t,k.PCB_ARC)]
assert len(arcs)==4
def v(p):return (p.x,p.y)
def arc_signature(item,graphic=False):return (v(item.GetStart()),v(item.GetArcMid() if graphic else item.GetMid()),v(item.GetEnd()),item.GetWidth(),int(item.GetLayer()),item.GetNetname())
for arc in arcs:assert arc.GetLayer()==k.F_Cu and arc.GetWidth()==100000
text=path.read_text();depth=0;quoted=False;escaped=False;tag=None;start=None;cuts=[]
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
        if depth==1 and tag=='arc':cuts.append((start,index+1));tag=None
assert depth==0 and len(cuts)==4
for start,end in reversed(cuts):text=text[:start]+text[end:]
output=dest/path.name;output.write_text(text);board=k.LoadBoard(str(output));assert len(board.GetTracks())==5
mapping=[]
for arc in arcs:
    graphic=k.PCB_SHAPE(board);graphic.SetShape(k.SHAPE_T_ARC);graphic.SetArcGeometry(arc.GetStart(),arc.GetMid(),arc.GetEnd());graphic.SetLayer(arc.GetLayer());graphic.SetWidth(arc.GetWidth());graphic.SetNet(board.FindNet(arc.GetNetname()));board.Add(graphic)
    mapping.append({'parent_track_uuid':arc.m_Uuid.AsString(),'graphic_uuid':graphic.m_Uuid.AsString(),'geometry':arc_signature(arc),'source_class':'unnamed-net F.Cu POLY NORMAL circle; two arcs per circle','native_net_assignment':'derived from recovered connectivity, not an explicit source POLY label'})
k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(output),board);saved=k.LoadBoard(str(output))
graphics={g.m_Uuid.AsString():g for g in saved.GetDrawings()}
for entry in mapping:assert arc_signature(graphics[entry['graphic_uuid']],True)==entry['geometry']
def pads(b):return {p.m_Uuid.AsString():(f.GetReference(),p.GetNumber(),v(p.GetPosition()),v(p.GetDrillSize()),p.GetNetname()) for f in b.GetFootprints() for p in f.Pads()}
assert pads(original)==pads(saved)
beforelines={t.m_Uuid.AsString():(v(t.GetStart()),v(t.GetEnd()),t.GetWidth(),t.GetNetname()) for t in original.GetTracks() if not isinstance(t,k.PCB_ARC)}
afterlines={t.m_Uuid.AsString():(v(t.GetStart()),v(t.GetEnd()),t.GetWidth(),t.GetNetname()) for t in saved.GetTracks()}
assert beforelines==afterlines
reportpath=dest/'drc-restored-graphics.json'
run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--schematic-parity','--format','json','--output',str(reportpath),str(output)],capture_output=True,text=True,timeout=90)
assert run.returncode==0,run.stderr
report=json.loads(reportpath.read_text());assert not report['schematic_parity']
audit={'candidate':name,'parent_board':str(path.relative_to(root)),'parent_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'engineering_board_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'source_evidence':'audit/pogo-copper-ring-review.json','reclassified_arcs':mapping,'physical_arc_geometry_unchanged':True,'pads_and_trace_segments_unchanged':True,'source_circles':2,'native_graphic_arcs':4,'native_track_segments':5,'schematic_parity':report['schematic_parity'],'drc_counts':dict(collections.Counter(v['type'] for v in report['violations'])),'unconnected':len(report['unconnected_items']),'manufacturing_ready':False}
(dest/'graphic-restoration-audit.json').write_text(json.dumps(audit,indent=2))
(dest/'README.txt').write_text('Engineering source-graphic correction: two source copper POLY circles are four native net-assigned gr_arc items, preserving geometry/contacts. Read ../../../COPPER-CONSOLIDATION.txt and graphic-restoration-audit.json. Zero DRC does not qualify dimensions, mask, manufacturing or hardware.\n')
print(json.dumps({key:audit[key] for key in ['candidate','physical_arc_geometry_unchanged','drc_counts','unconnected','manufacturing_ready']}))
