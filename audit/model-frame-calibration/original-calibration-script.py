from pathlib import Path
import sys,json,subprocess
dest=Path(__file__).resolve().parent/'model-frame-calibration';dest.mkdir(exist_ok=True)
if sys.argv[1]=='shape':
 import cadquery as cq
 # An asymmetric solid with unambiguous axes and a displaced origin.
 shape=cq.Workplane('XY').box(2,3,4,centered=False).translate((1,2,3)).union(cq.Workplane('XY').box(1,1,1,centered=False).translate((3,4,6))).val()
 cq.exporters.export(shape,str(dest/'asymmetric.step'))
 print('shape',shape.BoundingBox())
elif sys.argv[1]=='board':
 import pcbnew as k
 b=k.BOARD();b.GetDesignSettings().SetBoardThickness(k.FromMM(1.6))
 def v(x,y):return k.VECTOR2I(k.FromMM(x),k.FromMM(y))
 for start,end in [((0,0),(120,0)),((120,0),(120,100)),((120,100),(0,100)),((0,100),(0,0))]:
  g=k.PCB_SHAPE();g.SetShape(k.SHAPE_T_SEGMENT);g.SetStart(v(*start));g.SetEnd(v(*end));g.SetWidth(k.FromMM(.05));g.SetLayer(k.Edge_Cuts);b.Add(g)
 rows=[]
 for ref,x,y,angle,bottom in [('F0',20,20,0,False),('F37',50,20,37,False),('B0',20,60,0,True),('B53',70,60,53,True)]:
  fp=k.FOOTPRINT(b);fp.SetReference(ref);b.Add(fp)
  if bottom:fp.Flip(v(0,0),False)
  fp.SetPosition(v(x,y));fp.SetOrientationDegrees(angle)
  m=k.FP_3DMODEL();m.m_Filename=str(dest/'asymmetric.step');fp.Models().push_back(m)
  rows.append(dict(reference=ref,x=x,y=y,angle=angle,bottom=bottom))
 k.SaveBoard(str(dest/'fixture.kicad_pcb'),b);(dest/'inputs.json').write_text(json.dumps(rows,indent=2))
elif sys.argv[1]=='inspect':
 import cadquery as cq
 from OCP.STEPCAFControl import STEPCAFControl_Reader
 from OCP.TDocStd import TDocStd_Document
 from OCP.TCollection import TCollection_ExtendedString
 from OCP.TDF import TDF_LabelSequence,TDF_Label
 from OCP.TDataStd import TDataStd_Name
 from OCP.XCAFDoc import XCAFDoc_DocumentTool
 from OCP.IFSelect import IFSelect_RetDone
 def name(l):
  attr=TDataStd_Name();return attr.Get().ToExtString() if l.FindAttribute(TDataStd_Name.GetID_s(),attr) else ''
 d=TDocStd_Document(TCollection_ExtendedString('test'));r=STEPCAFControl_Reader();r.SetNameMode(True);assert r.ReadFile(str(dest/'fixture.step'))==IFSelect_RetDone and r.Transfer(d)
 st=XCAFDoc_DocumentTool.ShapeTool_s(d.Main());free=TDF_LabelSequence();st.GetFreeShapes(free);rows=[]
 def walk(l):
  c=TDF_LabelSequence();st.GetComponents_s(l,c,False)
  for i in range(1,c.Length()+1):
   child=c.Value(i);ref=TDF_Label();st.GetReferredShape_s(child,ref)
   tr=st.GetLocation_s(child).Transformation();shape=cq.Shape.cast(st.GetShape_s(child));bb=shape.BoundingBox()
   rows.append({'name':name(child),'definition':name(ref),'matrix':[[tr.Value(x,y) for y in range(1,5)] for x in range(1,4)],'bbox':[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]});walk(ref)
 walk(free.Value(1));(dest/'result.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
