"""Verify exact-reference KiCad STEP model exports against recovered local CAD.

Requires CadQuery/OCP, but not pcbnew. Checks the saved native footprint poses
and model attributes independently. No free registration or model scaling is
allowed. Passing establishes export geometry, not physical component fit.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import cadquery as cq
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TDocStd import TDocStd_Document
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TDataStd import TDataStd_Name
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.IFSelect import IFSelect_RetDone
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def parse_sexpr(text):
    stack = []
    result = None
    for token in TOKEN.findall(text):
        if token == '(':
            item = []
            if stack:
                stack[-1].append(item)
            stack.append(item)
        elif token == ')':
            result = stack.pop()
        else:
            stack[-1].append(json.loads(token) if token.startswith('"') else token)
    assert not stack
    return result


def children(node, key):
    return [item for item in node if isinstance(item, list) and item and item[0] == key]


def one(node, key):
    values = children(node, key)
    assert len(values) == 1, (key, len(values))
    return values[0]


def no_models(text):
    tokens = list(TOKEN.finditer(text))
    spans = []
    for index, token in enumerate(tokens):
        if token.group() != '(' or index + 1 == len(tokens) or tokens[index + 1].group() != 'model':
            continue
        depth = 0
        for tail in tokens[index:]:
            if tail.group() == '(':
                depth += 1
            elif tail.group() == ')':
                depth -= 1
            if depth == 0:
                spans.append((token.start(), tail.end()))
                break
    for start, end in reversed(spans):
        text = text[:start] + text[end:]
    return re.sub(r'\s+', ' ', text).strip()


def bounds(shape):
    box = Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped, box, False, False)
    return list(box.Get())


def shape_compare(expected, actual, label):
    assert expected.isValid() and actual.isValid(), (label, 'invalid shape')
    expected_solids, actual_solids = len(expected.Solids()), len(actual.Solids())
    assert expected_solids == actual_solids > 0, (label, 'solid-count mismatch', expected_solids, actual_solids)
    bbox_error = max(abs(x-y) for x, y in zip(bounds(expected), bounds(actual)))
    volume_error = abs(expected.Volume() - actual.Volume())
    volume_tolerance = max(1e-6, abs(expected.Volume()) * 1e-7)
    assert bbox_error < 1e-5, (label, 'bbox error', bbox_error)
    assert volume_error < volume_tolerance, (label, 'volume error', volume_error)
    missing, extra = expected.cut(actual), actual.cut(expected)
    assert missing.isValid() and extra.isValid(), (label, 'invalid Boolean result')
    missing_volume, extra_volume = abs(missing.Volume()), abs(extra.Volume())
    assert missing_volume < volume_tolerance and extra_volume < volume_tolerance, (label, 'Boolean mismatch', missing_volume, extra_volume, volume_tolerance)
    return {'solids': actual_solids, 'bounds_mm': bounds(actual), 'bbox_max_error_mm': bbox_error,
            'volume_mm3': actual.Volume(), 'volume_error_mm3': volume_error,
            'expected_minus_actual_mm3': missing_volume, 'actual_minus_expected_mm3': extra_volume,
            'volume_tolerance_mm3': volume_tolerance, 'passed': True}


def labelname(label):
    attr = TDataStd_Name()
    return attr.Get().ToExtString() if label.FindAttribute(TDataStd_Name.GetID_s(), attr) else ''


def exported_instances(path):
    doc = TDocStd_Document(TCollection_ExtendedString('verify_export'))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    assert reader.ReadFile(str(path)) == IFSelect_RetDone and reader.Transfer(doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    free = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free)
    assert free.Length() == 1
    root = free.Value(1)
    assert shape_tool.GetLocation_s(root).IsIdentity(), 'Unexpected export root transform'
    sequence = TDF_LabelSequence()
    shape_tool.GetComponents_s(root, sequence, False)
    result = {}
    for index in range(1, sequence.Length()+1):
        label = sequence.Value(index)
        referred = TDF_Label()
        assert shape_tool.GetReferredShape_s(label, referred)
        name = labelname(label)
        transform = shape_tool.GetLocation_s(label).Transformation()
        assert name not in result, ('duplicate instance reference', name)
        result[name] = {'shape': cq.Shape.cast(shape_tool.GetShape_s(label)),
                        'definition': labelname(referred),
                        'matrix': [[transform.Value(i, j) for j in range(1, 5)] for i in range(1, 4)]}
    # Keep XCAF document alive while its shapes are inspected.
    return doc, result


def expected_matrix(xy, angle, bottom, z):
    co, si = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    matrix = [[co, -si, 0, xy[0]], [si, co, 0, xy[1]], [0, 0, 1, z]]
    if bottom:
        for row in matrix:
            row[1] *= -1
            row[2] *= -1
    return matrix


def transform_local(shape, xy, angle, bottom, z):
    if bottom:
        shape = shape.rotate((0, 0, 0), (1, 0, 0), 180)
    if angle:
        shape = shape.rotate((0, 0, 0), (0, 0, 1), angle)
    return shape.translate((xy[0], xy[1], z))


def verify_calibration(cal):
    assert cal['native_version'] == '10.0.7'
    assert len(cal['inputs']) == 4
    for path, digest in cal['fixture_files'].items():
        assert sha(ROOT/path) == digest
    byname = {row['name']: row for row in cal['results']}
    for item in cal['inputs']:
        z = cal['bottom_model_datum_mm'] if item['bottom'] else cal['fixture_nominal_thickness_mm'] + cal['top_datum_minus_nominal_thickness_mm']
        expected = expected_matrix([item['x'], -item['y']], item['angle'], item['bottom'], z)
        actual = byname[item['reference']]['matrix']
        assert max(abs(expected[i][j]-actual[i][j]) for i in range(3) for j in range(4)) < 1e-10
    local = cq.importers.importStep(str(ROOT/'audit/model-frame-calibration/asymmetric.step')).val()
    document, instances = exported_instances(ROOT/'audit/model-frame-calibration/fixture.step')
    for item in cal['inputs']:
        z = cal['bottom_model_datum_mm'] if item['bottom'] else cal['fixture_nominal_thickness_mm'] + cal['top_datum_minus_nominal_thickness_mm']
        expected = transform_local(local,[item['x'],-item['y']],item['angle'],item['bottom'],z)
        shape_compare(expected,instances[item['reference']]['shape'],'synthetic calibration '+item['reference'])
    # Negative control: a fixed 0.1mm displacement must be rejected.
    try:
        shape_compare(local,local.translate((.1,0,0)),'synthetic negative control')
    except AssertionError:
        pass
    else:
        raise AssertionError('Intentional model displacement was accepted')


def verify_candidate(candidate, cal):
    folder = ROOT/'editing/kicad-models-attached'/candidate
    auditpath = folder/'model-attachment-audit.json'
    audit = read_json(auditpath)
    assert audit['attached'] and audit['local_geometry_generated'] and audit['non_model_board_data_unchanged']
    assert audit['native_version'] == cal['native_version']
    base = audit['base_candidate']
    boardpath = folder/(base+'.kicad_pcb')
    assert sha(boardpath) == audit['board_sha256']
    parent = ROOT/audit['parent_board']
    assert sha(parent) == audit['parent_board_sha256']
    assert no_models(boardpath.read_text(encoding='utf-8')) == no_models(parent.read_text(encoding='utf-8'))
    for name, digest in audit['unchanged_project_files'].items():
        assert sha(folder/name) == digest
    posepath = ROOT/'audit/model-pose-independent-review.json'
    assert sha(posepath) == audit['pose_review_sha256']
    pose = next(x for x in read_json(posepath)['boards'] if x['candidate'] == base)
    replay = ROOT/'editing/recovered-community'/base/'replayed-project.json'
    assert sha(replay) == pose['source_replay_sha256']
    manifestpath = ROOT/'recovered/author-step-components'/base/'component-manifest.json'
    assert sha(manifestpath) == audit['component_manifest_sha256'] == pose['source_component_manifest_sha256']
    manifest = read_json(manifestpath)
    assert sha(ROOT/manifest['source_step']) == manifest['source_step_sha256']
    pose_byref = {row['reference']: row for row in pose['placed_instances']}
    saved_board = parse_sexpr(boardpath.read_text(encoding='utf-8'))
    fps = {}
    for fp in children(saved_board, 'footprint'):
        ref = next(prop[2] for prop in children(fp, 'property') if prop[1] == 'Reference')
        assert ref not in fps
        fps[ref] = fp
    refs = {row['reference'] for row in audit['models']}
    assert refs == set(pose_byref) == {row['reference'] for row in manifest['components']}
    assert audit['missing_models'] == (['J3'] if base == 'imu_to_dxl_1V0A' else [])
    skipped = set(fps)-refs
    assert skipped <= {'SOURCE_BOARD_PADS', *audit['missing_models']}
    for ref in skipped:
        assert not children(fps[ref], 'model'), (ref, 'unexpected skipped model')
    if audit['missing_models']:
        missing = next(x for x in pose['missing_instances'] if x['reference'] == 'J3')
        assert missing['placed_model_attribute_overrides']['3D Model Title'] == ''
    exportpath = folder/audit['step_export']['file']
    assert sha(exportpath) == audit['step_export']['sha256']
    assert sha(folder/audit['glb_export']['file']) == audit['glb_export']['sha256']
    doc, instances = exported_instances(exportpath)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    free = TDF_LabelSequence()
    shape_tool.GetFreeShapes(free)
    assembly_shape = cq.Shape.cast(shape_tool.GetShape_s(free.Value(1)))
    assembly_bounds = bounds(assembly_shape)
    assert refs <= set(instances), ('Missing exported references', refs-set(instances))
    assert not (set(audit['missing_models']) & set(instances))
    assert 'SOURCE_BOARD_PADS' not in instances
    top = audit['nominal_native_board_thickness_mm'] + cal['top_datum_minus_nominal_thickness_mm']
    bottom = cal['bottom_model_datum_mm']
    local_library_sha256 = {}
    rows = []
    for row in audit['models']:
        ref = row['reference']
        p = pose_byref[ref]
        assert row['author_footprint_origin_mm'] == p['source_frame_origin_author_mm']
        assert row['source_model_id'] == p['model_id'] and row['source_model_title'] == p['model_title']
        fp = fps[ref]
        at = one(fp, 'at')
        xy = [float(at[1]), -float(at[2])]
        angle = float(at[3]) if len(at)>3 else 0.0
        is_bottom = one(fp, 'layer')[1] == 'B.Cu'
        assert is_bottom == row['bottom'] == (p['source_layer'] == 2)
        assert angle == row['native_angle_degrees']
        assert max(abs(x-y) for x,y in zip(xy, row['native_xy_export_mm'])) < 1e-9
        assert max(abs(xy[i]-p['source_xy_mil'][i]*.0254) for i in range(2)) <= .00000051
        model = one(fp, 'model')
        assert model[1] == row['model_path'] == '${KIPRJMOD}/'+row['local_model_file']
        for key, expected in [('offset', [0.0]*3), ('rotate', [0.0]*3), ('scale', [1.0]*3)]:
            actual = [float(x) for x in one(one(model,key), 'xyz')[1:]]
            assert actual == expected, (ref, 'nondefault model transform', key, actual)
        assert 'hide' not in model
        libpath = folder/'RecoveredLayout.pretty'/(ref+'.kicad_mod')
        lib = parse_sexpr(libpath.read_text(encoding='utf-8'))
        libmodel = one(lib,'model')
        assert libmodel == model, (ref,'library model definition differs')
        local_library_sha256[str(libpath.relative_to(folder))] = sha(libpath)
        localpath = folder/row['local_model_file']
        sourcepath = ROOT/row['source_placed_step']
        assert sha(localpath) == row['local_model_sha256']
        assert sha(sourcepath) == row['source_placed_sha256']
        local = cq.importers.importStep(str(localpath)).val()
        original = cq.importers.importStep(str(sourcepath)).val()
        expected_local = original.translate(tuple(-x for x in row['author_footprint_origin_mm']))
        if is_bottom:
            expected_local = expected_local.rotate((0,0,0),(1,0,0),180)
        local_result = shape_compare(expected_local, local, ref+' local')
        z = bottom if is_bottom else top
        matrix = expected_matrix(xy, angle, is_bottom, z)
        actual = instances[ref]['matrix']
        matrix_error = max(abs(matrix[i][j]-actual[i][j]) for i in range(3) for j in range(4))
        assert matrix_error < 1e-9, (ref, 'export placement differs', matrix, actual)
        expected_shape = transform_local(local, xy, angle, is_bottom, z)
        export_result = shape_compare(expected_shape, instances[ref]['shape'], ref+' native export')
        rows.append({'reference': ref, 'source_model_id': row['source_model_id'],
                     'source_placed_sha256': row['source_placed_sha256'], 'local_model_sha256': row['local_model_sha256'],
                     'bottom': is_bottom, 'expected_native_export_matrix': matrix,
                     'actual_native_export_matrix': actual, 'placement_matrix_max_error': matrix_error,
                     'author_nominal_surface_Z_mm': audit['author_source_surface_mm']['bottom' if is_bottom else 'top'],
                     'native_export_model_datum_Z_mm': z,
                     'native_minus_author_model_surface_mm': z-audit['author_source_surface_mm']['bottom' if is_bottom else 'top'],
                     'source_to_local_geometry': local_result, 'local_to_native_export_geometry': export_result})
        print(json.dumps({'candidate':candidate,'reference':ref,'geometry_passed':True}),flush=True)
    result = {'schema': 'microduck-kicad-model-export-validation/v1', 'candidate': candidate,
              'passed': True, 'models_verified': len(rows), 'missing_models_preserved': audit['missing_models'],
              'skipped_footprints': sorted(skipped), 'board_sha256': sha(boardpath),
              'attachment_audit_sha256': sha(auditpath), 'step_export_sha256': sha(exportpath),
              'glb_export_sha256':audit['glb_export']['sha256'],
              'geometry_verifier_sha256':sha(Path(__file__)),
              'local_library_sha256':local_library_sha256,
              'calibration_sha256': sha(ROOT/'audit/kicad-model-frame-calibration.json'),
              'pose_review_sha256': sha(posepath), 'actual_native_version': audit['native_version'],
              'nominal_native_board_thickness_mm': audit['nominal_native_board_thickness_mm'],
              'native_export_assembly_bounds_mm':assembly_bounds,
              'native_export_assembly_dimensions_mm':[assembly_bounds[i+3]-assembly_bounds[i] for i in range(3)],
              'native_export_model_datums_mm': {'top': top, 'bottom': bottom},
              'export_alignment_policy': audit['coordinate_policy'],
              'comparison_method': 'Exact XCAF reference; fixed saved footprint XY/angle/side and calibrated native Z. Both directional Boolean differences; analytic bounds, solid count, volume, hashes. No free registration.',
              'non_model_board_data_unchanged': True, 'models': rows,
              'physical_fit_qualified': False, 'manufacturing_ready': False}
    (folder/'model-export-validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', action='append')
    parser.add_argument('--no-summary',action='store_true',help='Write only per-project receipts, for independent parallel candidate checks')
    args = parser.parse_args()
    cal = read_json(ROOT/'audit/kicad-model-frame-calibration.json')
    verify_calibration(cal)
    candidates = args.candidate or ['imu_to_dxl', 'imu_to_dxl_1V0A', 'imu_to_dxl_1V0A-transition-hypothesis', 'wire_hub_1V0A', 'POGO_PIN_1V0A']
    results = []
    for candidate in candidates:
        result = verify_candidate(candidate,cal)
        results.append(result)
        print(json.dumps({'candidate': candidate, 'models_verified':result['models_verified'], 'passed':True}), flush=True)
    summary = {'schema':'microduck-kicad-model-export-suite/v1', 'passed':True,
               'candidates':len(results), 'models_verified_including_hypothesis':sum(r['models_verified'] for r in results),
               'physical_fit_qualified':False, 'manufacturing_ready':False,
               'results':[{k:r[k] for k in ['candidate','models_verified','missing_models_preserved','step_export_sha256','board_sha256','native_export_model_datums_mm']} for r in results]}
    if not args.no_summary:
        (ROOT/'audit/kicad-model-export-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
