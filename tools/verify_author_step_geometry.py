"""Check recovered STEP model geometry against every exact source definition.

Requires the installed CadQuery/OCP Python. Comparisons are performed in the
unchanged XCAF referred-definition frame: no registration, alignment or pose
optimization can hide a baked orientation difference. Sources and recovered
models are read only. This is a numerical solid-geometry verification, not a
claim of topological identity, vendor origin, or manufacturing qualification.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import time
from io import BytesIO

import cadquery as cq
import numpy as np
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepTools import BRepTools
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.TopAbs import TopAbs_IN, TopAbs_ON
from OCP.gp import gp_Pnt2d

ROOT = Path(__file__).resolve().parents[1]
VOLUME_ABS_TOL_MM3 = 1e-6
VOLUME_REL_TOL = 1e-9
SURFACE_TOL_MM = 1e-5
BBOX_TOL_MM = 1e-6
AREA_ABS_TOL_MM2 = 1e-5
AREA_REL_TOL = 1e-9


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def name(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else ''


def bbox(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    return list(box.Get())


def boundary_points(shape):
    """Exact vertices, exact edge samples, and trimmed-face UV samples.

    Sample points are on original BRep geometry, not triangle centroids. Face
    classifier rejects UV-grid points outside trimmed faces and inside holes.
    Finite sampling supplements the full-solid Boolean difference tests; it is
    not advertised as a certified global Hausdorff bound.
    """
    samples = {}
    counts = {'vertices': 0, 'edge_samples': 0, 'face_uv_samples': 0,
              'faces': len(shape.Faces()), 'faces_with_uv_sample': 0}

    def add(point, category):
        coords = point.toTuple() if isinstance(point, cq.Vector) else (point.X(), point.Y(), point.Z())
        assert all(math.isfinite(x) for x in coords)
        key = tuple(round(x, 10) for x in coords)
        if key not in samples:
            samples[key] = cq.Vector(*coords)
            counts[category] += 1

    for vertex in shape.Vertices():
        add(vertex.Center(), 'vertices')
    for edge in shape.Edges():
        for t in (.25, .5, .75):
            add(edge.positionAt(t), 'edge_samples')
    for face in shape.Faces():
        adaptor = BRepAdaptor_Surface(face.wrapped, True)
        u0,u1,v0,v1 = BRepTools.UVBounds_s(face.wrapped)
        found = False
        for fu in (.25, .5, .75):
            for fv in (.25, .5, .75):
                u,v = u0+(u1-u0)*fu, v0+(v1-v0)*fv
                classifier = BRepClass_FaceClassifier(face.wrapped, gp_Pnt2d(u,v), 1e-9)
                if classifier.State() in (TopAbs_IN, TopAbs_ON):
                    add(adaptor.Value(u,v), 'face_uv_samples')
                    found = True
        counts['faces_with_uv_sample'] += int(found)
    counts['unique_points'] = len(samples)
    return list(samples.values()), counts


def directed_boundary_distance(source, target):
    points, counts = boundary_points(source)
    # Query exact faces rather than the solid (interior points have solid
    # distance zero). Analytic face AABBs accelerate candidate selection without
    # introducing a tessellated substitute for the exact geometry.
    faces = target.Faces()
    boxes = np.asarray([bbox(face) for face in faces])
    worst = {'distance_mm': 0.0, 'point_mm': None}
    for point in points:
        p = np.asarray(point.toTuple())
        lower = np.linalg.norm(np.maximum(np.maximum(boxes[:,:3]-p,p-boxes[:,3:]),0),axis=1)
        vertex = cq.Vertex.makeVertex(*point.toTuple())
        distance = math.inf
        for index in np.argsort(lower):
            if lower[index] > distance + BBOX_TOL_MM:
                break
            distance = min(distance, faces[index].distance(vertex))
            if distance <= 1e-10:
                break
        assert math.isfinite(distance) and distance >= 0
        if distance > worst['distance_mm']:
            worst = {'distance_mm': distance, 'point_mm': list(point.toTuple())}
    return {'sampling': counts, 'maximum_sampled_distance_mm': worst['distance_mm'],
            'worst_sample_mm': worst['point_mm'], 'within_tolerance': worst['distance_mm'] <= SURFACE_TOL_MM,
            'distance_policy':'minimum exact-face distance with analytic AABB pruning; distances <=1e-10mm stop at a numerical-zero upper bound'}


def compare(a, b):
    assert a.isValid() and b.isValid() and a.Solids() and b.Solids()
    am, bm = bbox(a), bbox(b)
    error = max(abs(x-y) for x,y in zip(am,bm))
    av,bv = a.Volume(),b.Volume()
    area_a,area_b = a.Area(),b.Area()
    # Both directed cuts are needed: equal volumes alone can hide disjoint,
    # mirrored, rotated, or spatially rearranged asymmetric features.
    a_minus_b, b_minus_a = a.cut(b), b.cut(a)
    cuts_valid = a_minus_b.isValid() and b_minus_a.isValid()
    va = sum(abs(s.Volume()) for s in a_minus_b.Solids())
    vb = sum(abs(s.Volume()) for s in b_minus_a.Solids())
    volume_limit = max(VOLUME_ABS_TOL_MM3, max(abs(av),abs(bv))*VOLUME_REL_TOL)
    area_limit = max(AREA_ABS_TOL_MM2, max(abs(area_a),abs(area_b))*AREA_REL_TOL)
    forward = directed_boundary_distance(a,b)
    reverse = directed_boundary_distance(b,a)
    passed = (cuts_valid and len(a.Solids())==len(b.Solids()) and error <= BBOX_TOL_MM
              and va <= volume_limit and vb <= volume_limit
              and abs(area_a-area_b) <= area_limit
              and forward['within_tolerance'] and reverse['within_tolerance'])
    return {'passed':passed, 'valid_input_solids':True, 'directed_cut_shapes_valid':cuts_valid,
            'solid_counts':[len(a.Solids()),len(b.Solids())],
            'max_bbox_difference_mm':error, 'volumes_mm3':[av,bv],
            'directed_difference_volumes_mm3':[va,vb],
            'symmetric_difference_volume_mm3':va+vb,
            'allowed_each_direction_volume_mm3':volume_limit,
            'surface_areas_mm2':[area_a,area_b], 'surface_area_difference_mm2':abs(area_a-area_b),
            'allowed_surface_area_difference_mm2':area_limit,
            'source_boundary_to_recovered_boundary':forward,
            'recovered_boundary_to_source_boundary':reverse}


def controls():
    base = cq.Workplane('XY').box(3,3,1,centered=False).val()
    notch = cq.Workplane('XY').box(2,2,2,centered=False).translate((1,1,-.5)).val()
    asymmetric = base.cut(notch)
    rotated = asymmetric.rotate((1.5,1.5,0),(1.5,1.5,1),180)
    assert abs(asymmetric.Volume()-rotated.Volume())<1e-10
    assert max(abs(x-y) for x,y in zip(bbox(asymmetric),bbox(rotated)))<1e-10
    good, bad = compare(asymmetric,asymmetric.copy()),compare(asymmetric,rotated)
    assert good['passed'] and not bad['passed']
    assert bad['symmetric_difference_volume_mm3']>1 and max(
        bad['source_boundary_to_recovered_boundary']['maximum_sampled_distance_mm'],
        bad['recovered_boundary_to_source_boundary']['maximum_sampled_distance_mm'])>.1
    return {'identical_asymmetric_positive':good,
            'equal_bbox_volume_rotated_asymmetric_negative':bad,
            'controls_passed':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'audit/author-model-geometry-validation.json')
    args=parser.parse_args()
    started=time.time()
    indexpath=ROOT/'recovered/author-step-model-definitions/model-definition-index.json'
    index=json.loads(indexpath.read_text(encoding='utf-8'))
    test_controls=controls()
    print(json.dumps({'controls_passed':True}),flush=True)
    documents={}
    source_hashes={}
    for source in index['sources']:
        path=ROOT/source['source_step']
        assert sha(path)==source['sha256']
        doc=TDocStd_Document(TCollection_ExtendedString('geometry_verification'))
        reader=STEPCAFControl_Reader(); reader.SetNameMode(True)
        assert reader.ReadFile(str(path))==IFSelect_RetDone and reader.Transfer(doc)
        st=XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
        free=TDF_LabelSequence(); st.GetFreeShapes(free)
        assert free.Length()==1 and st.GetLocation_s(free.Value(1)).IsIdentity()
        children=TDF_LabelSequence(); assert st.GetComponents_s(free.Value(1),children,False)
        shapes={}
        for i in range(1,children.Length()+1):
            component=children.Value(i); definition=TDF_Label()
            assert st.GetReferredShape_s(component,definition)
            key=(name(component),name(definition))
            assert key not in shapes
            shapes[key]=cq.Shape.cast(st.GetShape_s(definition))
        documents[source['candidate']]=(doc,reader,st,shapes)
        source_hashes[source['source_step']]=source['sha256']
    results=[]
    recovered_hashes={}
    comparison_cache={}
    full_comparisons=0
    for model in index['models']:
        for variant in model['variants']:
            path=ROOT/variant['step_file']
            assert sha(path)==variant['step_sha256']
            recovered_hashes[variant['step_file']]=variant['step_sha256']
            recovered=cq.importers.importStep(str(path)).val()
            for instance in variant['instances']:
                shapes=documents[instance['candidate']][3]
                source=shapes[(instance['source_instance_label'],instance['source_definition_label'])]
                stream=BytesIO(); assert source.exportBrep(stream)
                serialized=stream.getvalue()
                fingerprint=hashlib.sha256(serialized).hexdigest()
                cachekey=(variant['step_sha256'],fingerprint,len(serialized))
                cached=comparison_cache.get(cachekey)
                try:
                    if cached is not None and cached[0]==serialized:
                        result={**cached[1], 'comparison_reused_from':cached[2],
                                'reuse_basis':'exact serialized source BRep byte equality, including geometry/topology/locations; same recovered STEP hash'}
                    else:
                        result=compare(source,recovered)
                        full_comparisons+=1
                        comparison_cache[cachekey]=(serialized,result,{'candidate':instance['candidate'],'reference':instance['reference']})
                except Exception as error:
                    # Preserve failed kernel/comparison evidence and continue
                    # checking other definitions; a partial run must not pass.
                    result={'passed':False,'geometry_comparison_error':type(error).__name__+': '+str(error)}
                row={'model_id':model['model_id'],'variant_number':variant['variant_number'],
                     'candidate':instance['candidate'],'reference':instance['reference'],
                     'source_step':instance['source_step'],
                     'source_definition_label':instance['source_definition_label'],
                     'source_brep_sha256':fingerprint,'source_brep_bytes':len(serialized),
                     'recovered_step':variant['step_file'], **result}
                results.append(row)
                print(json.dumps({'candidate':row['candidate'],'reference':row['reference'],
                                  'passed':row['passed'],'difference_mm3':row.get('symmetric_difference_volume_mm3'),
                                  'boundary_error_mm':max(row.get('source_boundary_to_recovered_boundary',{}).get('maximum_sampled_distance_mm',math.inf),
                                                          row.get('recovered_boundary_to_source_boundary',{}).get('maximum_sampled_distance_mm',math.inf))
                                  if 'geometry_comparison_error' not in row else None,
                                  'comparison_error':row.get('geometry_comparison_error')}),flush=True)
    sources_unchanged=all(sha(ROOT/path)==value for path,value in source_hashes.items())
    models_unchanged=all(sha(ROOT/path)==value for path,value in recovered_hashes.items())
    passed=all(r['passed'] for r in results) and len(results)==index['source_instances_checked'] and sources_unchanged and models_unchanged
    report={'schema':'microduck-author-model-geometry/v1','passed':passed,
            'source_model_ids':len(index['models']),'source_definitions_checked':len(results),
            'full_boolean_boundary_comparisons':full_comparisons,
            'exact_brep_duplicate_comparisons':sum('comparison_reused_from' in r for r in results),
            'recovered_variants_checked':len(recovered_hashes),'failures':[r for r in results if not r['passed']],
            'index_file':str(indexpath.relative_to(ROOT)),'index_sha256':sha(indexpath),
            'source_hashes':source_hashes,'recovered_model_hashes':recovered_hashes,
            'sources_unchanged':sources_unchanged,'recovered_models_unchanged':models_unchanged,
            'comparison_frame':'exact XCAF referred PRODUCT-DEFINITION local, unchanged; no fitting, registration, or alignment',
            'tolerances':{'bbox_absolute_mm':BBOX_TOL_MM,'directed_volume_absolute_mm3':VOLUME_ABS_TOL_MM3,
                          'directed_volume_relative':VOLUME_REL_TOL,'sampled_boundary_distance_mm':SURFACE_TOL_MM,
                          'surface_area_absolute_mm2':AREA_ABS_TOL_MM2,'surface_area_relative':AREA_REL_TOL},
            'method':'each unique source BRep/recovered STEP pair: valid BRep solids, exact solid counts, two directed full-solid Boolean cuts, surface area, deterministic exact-boundary samples in both directions; repeated sources reuse only after exact serialized BRep byte equality including geometry/topology/locations and identical recovered STEP hash',
            'boundary_sampling':'all vertices, edge quarter/mid/three-quarter points, 3x3 UV grids per trimmed face; exact target-face distances with analytic AABB pruning and numerical-zero stopping <=1e-10mm',
            'limitations':['numerical kernel verification within stated tolerances, not mathematical or topological identity',
                           'finite boundary sampling is not a certified global Hausdorff bound',
                           'no original vendor/native KiCad origin, board placement, package dimensions, pin-1 direction, or manufacturing qualification'],
            'controls':test_controls,'results':results,'elapsed_seconds':time.time()-started,
            'kicad_attachment_performed':False,'manufacturing_ready':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'passed':passed,'definitions':len(results),'failures':len(report['failures']),
                      'output':str(args.output),'elapsed_seconds':report['elapsed_seconds']}),flush=True)
    raise SystemExit(0 if passed else 1)


if __name__=='__main__':
    main()
