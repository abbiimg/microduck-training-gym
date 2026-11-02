"""Recover explicitly labeled component instances from author PCB STEP files.

Uses exact XCAF reference identity/assembly location, never bbox matching.
Outputs retain the whole author STEP coordinate frame, NOT model-local or KiCad
placement coordinates. Requires the installed CadQuery/OCP Python runtime.
"""
from pathlib import Path
import argparse,json,hashlib
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence,TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import cadquery as cq
p=argparse.ArgumentParser();p.add_argument('--candidate',required=True);p.add_argument('--stl',action='store_true');p.add_argument('--overwrite-generated',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1]
meta=next(item for item in json.loads((root/'audit/placed-device-model-metadata.json').read_text(encoding='utf-8')) if item['candidate']==a.candidate)
expected={m['reference']:m['metadata'] for m in meta['placed_device_models']}
matches=list((root/'community/microduck-replica/hardware').rglob(a.candidate+'-PCB.step'));assert len(matches)==1
source=matches[0];sourcehash=hashlib.sha256(source.read_bytes()).hexdigest()
dest=root/'recovered/author-step-components'/a.candidate
if dest.exists() and not a.overwrite_generated:raise RuntimeError('Output exists; preserve user edits before --overwrite-generated')
dest.mkdir(parents=True,exist_ok=True)
doc=TDocStd_Document(TCollection_ExtendedString('recovered_components'));reader=STEPCAFControl_Reader();reader.SetNameMode(True)
assert reader.ReadFile(str(source))==IFSelect_RetDone;assert reader.Transfer(doc)
st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main());free=TDF_LabelSequence();st.GetFreeShapes(free);assert free.Length()==1
top=free.Value(1);assert st.GetLocation_s(top).IsIdentity(),'Nonidentity root needs explicit additional review'
def labelname(label):
    attr=TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(),attr) else ''
def box(shape):
    # STL tessellation can populate a shared source TShape's mesh cache. Use
    # underlying analytic geometry rather than that cache for roundtrip checks.
    b=Bnd_Box();BRepBndLib.AddOptimal_s(shape.wrapped,b,False,False)
    x0,y0,z0,x1,y1,z1=b.Get();return [[x0,y0,z0],[x1,y1,z1]]
children=TDF_LabelSequence();st.GetComponents_s(top,children,False);instances=[]
for index in range(1,children.Length()+1):
    label=children.Value(index);referred=TDF_Label();assert st.GetReferredShape_s(label,referred)
    instances.append((label,labelname(label),labelname(referred)))
rows=[];missing=[]
for ref,md in sorted(expected.items()):
    found=[item for item in instances if item[1]==ref or item[2].startswith(ref+'~')]
    if not found:missing.append(ref);continue
    assert len(found)==1,(ref,'Ambiguous source instance')
    label,instance_name,definition_name=found[0]
    assert definition_name.startswith(ref+'~'),(ref,definition_name)
    assert md['3D Model Title'] in definition_name,(ref,'Model title mismatch',md['3D Model Title'],definition_name)
    shape=cq.Shape.cast(st.GetShape_s(label));assert shape.isValid() and shape.Solids(),(ref,'Missing/invalid labeled shape')
    before=box(shape);count=len(shape.Solids());volume=shape.Volume()
    path=dest/(ref+'.step');cq.exporters.export(shape,str(path),exportType='STEP')
    reopened=cq.importers.importStep(str(path)).val();assert reopened.isValid() and len(reopened.Solids())==count
    after=box(reopened);error=max(abs(x-y) for beforeaxis,afteraxis in zip(before,after) for x,y in zip(beforeaxis,afteraxis));assert error<1e-5,(ref,error)
    assert abs(reopened.Volume()-volume)<max(1e-6,abs(volume)*1e-7),(ref,'Volume mismatch')
    location=st.GetLocation_s(label).Transformation()
    row={'reference':ref,'source_instance_label':instance_name,'source_definition_label':definition_name,'metadata_model_id':md['3D Model'],'metadata_model_title':md['3D Model Title'],'identity_basis':'exact reference-name product/usage instance plus matching metadata model title; no geometry matching','model_uuid_embedded_in_step':False,'coordinate_frame':'whole author PCB STEP world frame in millimetres; source instance and nested assembly transforms already applied by XCAF GetShape','instance_location_matrix':[[location.Value(i,j) for j in range(1,5)] for i in range(1,4)],'solids':count,'valid':True,'bounds_mm':before,'volume_mm3':volume,'step_file':path.name,'step_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'roundtrip_max_bbox_error_mm':error}
    if a.stl:
        stl=dest/(ref+'.stl');cq.exporters.export(shape,str(stl),exportType='STL',tolerance=.02,angularTolerance=.1)
        row.update(stl_file=stl.name,stl_sha256=hashlib.sha256(stl.read_bytes()).hexdigest(),stl_linear_deflection_mm=.02,stl_angular_deflection_rad=.1,stl_units='unitless STL; stored numeric coordinates are millimetres')
    rows.append(row);print(json.dumps({'candidate':a.candidate,'reference':ref,'solids':count,'bbox_error_mm':error}),flush=True)
assert sourcehash==hashlib.sha256(source.read_bytes()).hexdigest()
report={'candidate':a.candidate,'source_step':str(source.relative_to(root)),'source_step_sha256':sourcehash,'source_step_unchanged':True,'metadata_source':'audit/placed-device-model-metadata.json','expected_references':len(expected),'recovered_references':len(rows),'missing_references':missing,'components':rows,'coordinates':'millimetres in whole author PCB STEP world frame; these are placed component snapshots, not unplaced package models','new_parametric_history_recovered':False,'kicad_placement_qualified':False,'manufacturing_ready':False}
(dest/'component-manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(dest/'PROVENANCE.txt').write_text('Exact labeled component snapshots extracted from the preserved community author PCB STEP. See component-manifest.json for parent hash and source assembly labels. Coordinates retain the WHOLE AUTHOR STEP world frame in millimetres, including exact XCAF instance/nested transforms. These are not local-origin package models and must not be attached to KiCad without a separate placement transformation review. Optional STL is unitless with numeric mm coordinates and stated tessellation tolerances. Source repository/model terms still apply; no new license or original factory/parametric-design status is claimed. J3 is missing from the revised IMU author STEP despite metadata. No model placement, geometry guess, or board edit was performed.\n',encoding='utf-8')
print(json.dumps({key:report[key] for key in ['candidate','expected_references','recovered_references','missing_references','manufacturing_ready']}),flush=True)
