"""Recover exact XCAF referred definitions, grouped by source metadata model ID.

Requires installed CadQuery/OCP. No guessed origin, footprint placement, board
modification or KiCad attachment. Definitions retain their STEP product frame.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
import cadquery as cq

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stl', action='store_true')
parser.add_argument('--overwrite-generated', action='store_true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
dest = root/'recovered/author-step-model-definitions'
if dest.exists() and not args.overwrite_generated:
    raise RuntimeError('Output exists; preserve user edits before --overwrite-generated')
dest.mkdir(parents=True, exist_ok=True)
BBOX_TOL_MM = 1e-7
VOLUME_ABS_TOL_MM3 = 1e-6
VOLUME_REL_TOL = 1e-7

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def labelname(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else ''

def matrix(location):
    t = location.Transformation()
    return [[t.Value(i,j) for j in range(1,5)] for i in range(1,4)]

def metrics(shape):
    assert shape.isValid() and shape.Solids()
    b = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, b, False, False)
    x0,y0,z0,x1,y1,z1 = b.Get()
    return {'valid': True, 'solids': len(shape.Solids()),
            'bounds_mm': [[x0,y0,z0],[x1,y1,z1]], 'volume_mm3': shape.Volume()}

def difference(a, b):
    error = max(abs(x-y) for axes_a,axes_b in zip(a['bounds_mm'],b['bounds_mm']) for x,y in zip(axes_a,axes_b))
    volerror = abs(a['volume_mm3']-b['volume_mm3'])
    return {'max_bbox_difference_mm': error, 'volume_difference_mm3': volerror,
            'solid_counts_equal': a['solids']==b['solids'],
            'metrics_agree': a['solids']==b['solids'] and error<=BBOX_TOL_MM and
            volerror<=max(VOLUME_ABS_TOL_MM3,abs(b['volume_mm3'])*VOLUME_REL_TOL)}

groups = {}
source_documents = []  # Keep XCAF definitions alive until every export completes.
source_rows = []
for manifestpath in sorted((root/'recovered/author-step-components').glob('*/component-manifest.json')):
    placed = json.loads(manifestpath.read_text(encoding='utf-8'))
    source = root/placed['source_step']
    assert sha(source)==placed['source_step_sha256']
    doc = TDocStd_Document(TCollection_ExtendedString('model_definitions'))
    reader = STEPCAFControl_Reader(); reader.SetNameMode(True)
    assert reader.ReadFile(str(source))==IFSelect_RetDone and reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    free = TDF_LabelSequence(); st.GetFreeShapes(free)
    assert free.Length()==1 and st.GetLocation_s(free.Value(1)).IsIdentity()
    children = TDF_LabelSequence(); assert st.GetComponents_s(free.Value(1),children,False)
    labels = []
    for index in range(1,children.Length()+1):
        label = children.Value(index); definition = TDF_Label()
        assert st.GetReferredShape_s(label,definition)
        labels.append((label,definition,labelname(label),labelname(definition)))
    for component in placed['components']:
        ref = component['reference']; model_id = component['metadata_model_id']
        found = [x for x in labels if x[2]==ref or x[3].startswith(ref+'~')]
        assert len(found)==1, (placed['candidate'],ref,'ambiguous reference')
        label,definition,instance_name,definition_name = found[0]
        assert definition_name.startswith(ref+'~') and component['metadata_model_title'] in definition_name
        # Dereference the instance. Do not invert, zero, infer, or reapply any
        # locations: the referred PRODUCT definition is the requested frame.
        shape = cq.Shape.cast(st.GetShape_s(definition))
        metric = metrics(shape)
        provenance = {'candidate': placed['candidate'], 'reference': ref,
                      'source_step': placed['source_step'], 'source_step_sha256': placed['source_step_sha256'],
                      'source_instance_label': instance_name, 'source_definition_label': definition_name,
                      'source_instance_location_matrix': matrix(st.GetLocation_s(label)),
                      'source_definition_location_matrix': matrix(st.GetLocation_s(definition)),
                      'definition_metrics': metric}
        group = groups.setdefault(model_id, {'model_id': model_id,'model_title': component['metadata_model_title'],'variants': []})
        assert group['model_title']==component['metadata_model_title'], (model_id,'title conflict')
        matching = [(v,difference(metric,v['metrics'])) for v in group['variants']]
        matched = next(((v,d) for v,d in matching if d['metrics_agree']), None)
        if matched is None:
            variant = {'variant_number': len(group['variants'])+1, 'metrics': metric,
                       'representative': provenance, 'instances': [], '_shape': shape}
            group['variants'].append(variant); comparison = difference(metric,metric)
        else:
            variant,comparison = matched
        provenance['comparison_to_variant_representative'] = comparison
        variant['instances'].append(provenance)
    source_rows.append({'candidate':placed['candidate'],'source_step':placed['source_step'],
                        'sha256':placed['source_step_sha256'],'instances_checked':len(placed['components'])})
    source_documents.append((doc,reader,st))
    print(json.dumps({'source_read':placed['candidate'],'instances':len(placed['components'])}),flush=True)

allrows = []
for model_id,group in sorted(groups.items()):
    safe = re.sub(r'[^A-Za-z0-9_-]+','_',model_id)
    assert safe and safe not in {'.','..'}
    folder = dest/safe; folder.mkdir(parents=True,exist_ok=True)
    multiple = len(group['variants'])>1
    for variant in group['variants']:
        sub = folder/('variant-%02d'%variant['variant_number']) if multiple else folder
        sub.mkdir(parents=True,exist_ok=True)
        shape = variant.pop('_shape')
        out = sub/'model.step'; cq.exporters.export(shape,str(out),exportType='STEP')
        reopened = cq.importers.importStep(str(out)).val()
        check = difference(metrics(reopened),variant['metrics']); assert check['metrics_agree'], (model_id,check)
        variant.update(step_file=str(out.relative_to(root)),step_sha256=sha(out),step_roundtrip=check)
        if args.stl:
            stl = sub/'model.stl'; cq.exporters.export(shape,str(stl),exportType='STL',tolerance=.02,angularTolerance=.1)
            data=stl.read_bytes(); triangles=struct.unpack_from('<I',data,80)[0]
            assert triangles>0 and len(data)==84+50*triangles
            variant.update(stl_file=str(stl.relative_to(root)),stl_sha256=sha(stl),stl_triangles=triangles,
                           stl_linear_deflection_mm=.02,stl_angular_deflection_rad=.1,
                           stl_units='unitless STL; numeric coordinates are millimetres')
    group.update(variant_count=len(group['variants']),
                 definition_metric_consistency='different variants preserved; equivalence unresolved' if multiple else 'all checked definition-local bounds, volumes and solid counts agree within stated tolerances',
                 full_brep_equivalence_proven=False,
                 canonical_equivalence='metric-only; unqualified for asymmetric geometry or baked orientation equivalence',
                 representative_selection='first exact source definition in deterministic board/ref order within each model-ID metric group; all exact source definitions remain retrievable through per-instance source hash/ref/definition-label provenance',
                 coordinate_frame='exact XCAF referred PRODUCT-DEFINITION local frame in millimetres; not original vendor/native KiCad model-local',
                 metadata_uuid_embedded_in_step=False,
                 identity_basis='metadata model ID grouped only after exact reference and matching title identity was established')
    (folder/'model-manifest.json').write_text(json.dumps(group,indent=2),encoding='utf-8')
    (folder/'PROVENANCE.txt').write_text('Recovered XCAF referred PRODUCT-DEFINITION shapes from preserved author PCB STEP. Instance placement was omitted by dereferencing the exact labeled component, not by estimating an origin. Frame is author STEP product-definition local, not vendor-native model-local or a qualified KiCad footprint-model frame. See model-manifest.json for exact source hashes, labels and all contributing instances. Bounds/volume/solid agreement is a bounded consistency check, not proof of full BRep equivalence. Source repository/model rights still apply. No board edit or KiCad attachment performed.\n',encoding='utf-8')
    allrows.append(group)
    print(json.dumps({'model':model_id,'variants':len(group['variants']),'instances':sum(len(v['instances']) for v in group['variants'])}),flush=True)

for source in source_rows:
    assert sha(root/source['source_step'])==source['sha256']
report={'source_model_ids':len(allrows),'source_instances_checked':sum(s['instances_checked'] for s in source_rows),
        'definition_variants':sum(len(g['variants']) for g in allrows),
        'ids_with_different_definition_variants':[g['model_id'] for g in allrows if len(g['variants'])>1],
        'comparison_tolerances':{'bbox_absolute_mm':BBOX_TOL_MM,'volume_absolute_mm3':VOLUME_ABS_TOL_MM3,'volume_relative':VOLUME_REL_TOL,'solid_count':'exact'},
        'coordinate_frame':'exact XCAF PRODUCT-DEFINITION local; no original vendor/KiCad origin qualification',
        'original_sources_unchanged':True,'sources':source_rows,'models':allrows,
        'kicad_attachment_performed':False,'revised_imu_J3_placement_recovered':False,
        'full_brep_equivalence_proven':False,
        'canonical_equivalence':'metric-only; unqualified for asymmetric geometry or baked orientation equivalence',
        'manufacturing_ready':False}
(dest/'model-definition-index.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
(root/'audit/author-model-definition-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:report[k] for k in ['source_model_ids','source_instances_checked','definition_variants','ids_with_different_definition_variants','original_sources_unchanged']}),flush=True)
