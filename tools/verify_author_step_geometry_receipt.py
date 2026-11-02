"""Check the expensive geometry verification receipt and all input hashes.

Uses ordinary Python. This checks freshness, complete definition coverage and
result consistency; it does not rerun the CadQuery/OCP geometric operations.
Run verify_author_step_geometry.py in the CAD Python to regenerate the receipt.
"""
from pathlib import Path
import hashlib
import json
import math

ROOT=Path(__file__).resolve().parents[1]
rel=lambda value: ROOT/value.replace('\\','/')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    assert isinstance(value,(int,float)) and math.isfinite(value)
    return value


def main():
    path=ROOT/'audit/author-model-geometry-validation.json'
    report=json.loads(path.read_text(encoding='utf-8'))
    indexpath=rel(report['index_file'])
    assert sha(indexpath)==report['index_sha256']
    index=json.loads(indexpath.read_text(encoding='utf-8'))
    assert report['schema']=='microduck-author-model-geometry/v1'
    assert report['passed'] is True and not report['failures']
    assert report['sources_unchanged'] and report['recovered_models_unchanged']
    assert report['kicad_attachment_performed'] is False and report['manufacturing_ready'] is False
    assert report['comparison_frame']=='exact XCAF referred PRODUCT-DEFINITION local, unchanged; no fitting, registration, or alignment'
    assert report['tolerances']=={'bbox_absolute_mm':1e-6,'directed_volume_absolute_mm3':1e-6,
                                  'directed_volume_relative':1e-9,'sampled_boundary_distance_mm':1e-5,
                                  'surface_area_absolute_mm2':1e-5,'surface_area_relative':1e-9}
    for relative,expected in {**report['source_hashes'],**report['recovered_model_hashes']}.items():
        assert sha(rel(relative))==expected, relative
    expected={}
    for model in index['models']:
        for variant in model['variants']:
            for instance in variant['instances']:
                key=(instance['candidate'],instance['reference'])
                assert key not in expected
                expected[key]=(model['model_id'],variant['variant_number'],variant['step_file'],
                               instance['source_step'],instance['source_definition_label'])
    seen={}
    max_boundary=0.0
    for row in report['results']:
        key=(row['candidate'],row['reference'])
        assert key not in seen
        assert expected[key]==(row['model_id'],row['variant_number'],row['recovered_step'],
                               row['source_step'],row['source_definition_label'])
        assert row['passed'] and row['valid_input_solids'] and row['directed_cut_shapes_valid']
        assert row['solid_counts'][0]==row['solid_counts'][1]>0
        assert finite(row['max_bbox_difference_mm'])<=1e-6
        assert len(row['source_brep_sha256'])==64 and row['source_brep_bytes']>0
        volume_limit=max(1e-6,max(abs(finite(v)) for v in row['volumes_mm3'])*1e-9)
        assert row['allowed_each_direction_volume_mm3']==volume_limit
        assert all(0<=finite(v)<=volume_limit for v in row['directed_difference_volumes_mm3'])
        assert abs(sum(row['directed_difference_volumes_mm3'])-finite(row['symmetric_difference_volume_mm3']))<1e-12
        area_limit=max(1e-5,max(abs(finite(v)) for v in row['surface_areas_mm2'])*1e-9)
        assert row['allowed_surface_area_difference_mm2']==area_limit
        assert 0<=finite(row['surface_area_difference_mm2'])<=area_limit
        for direction in ('source_boundary_to_recovered_boundary','recovered_boundary_to_source_boundary'):
            boundary=row[direction]
            assert boundary['within_tolerance']
            assert boundary['sampling']['unique_points']>0 and boundary['sampling']['faces']>0
            error=finite(boundary['maximum_sampled_distance_mm'])
            assert 0<=error<=1e-5
            max_boundary=max(max_boundary,error)
        if 'comparison_reused_from' in row:
            original=seen[(row['comparison_reused_from']['candidate'],row['comparison_reused_from']['reference'])]
            assert row['source_brep_sha256']==original['source_brep_sha256']
            assert row['source_brep_bytes']==original['source_brep_bytes']
            assert row['recovered_step']==original['recovered_step']
            for field in ('symmetric_difference_volume_mm3','source_boundary_to_recovered_boundary',
                          'recovered_boundary_to_source_boundary'):
                assert row[field]==original[field]
        seen[key]=row
    assert set(seen)==set(expected)
    assert len(seen)==report['source_definitions_checked']==index['source_instances_checked']==61
    assert len(index['models'])==report['source_model_ids']==22
    assert report['recovered_variants_checked']==len(report['recovered_model_hashes'])==22
    reused=sum('comparison_reused_from' in row for row in report['results'])
    assert reused==report['exact_brep_duplicate_comparisons']
    assert len(seen)-reused==report['full_boolean_boundary_comparisons']
    controls=report['controls']
    positive=controls['identical_asymmetric_positive']
    negative=controls['equal_bbox_volume_rotated_asymmetric_negative']
    assert controls['controls_passed'] and positive['passed'] and not negative['passed']
    assert finite(negative['max_bbox_difference_mm'])<1e-10
    assert abs(negative['volumes_mm3'][0]-negative['volumes_mm3'][1])<1e-10
    assert finite(negative['symmetric_difference_volume_mm3'])>1
    assert max(negative[direction]['maximum_sampled_distance_mm'] for direction in
               ('source_boundary_to_recovered_boundary','recovered_boundary_to_source_boundary'))>.1
    result={'passed':True,'receipt_file':str(path.relative_to(ROOT)),'receipt_sha256':sha(path),
            'source_definitions_checked':len(seen),'model_ids':len(index['models']),
            'source_and_model_hashes_current':True,'fresh_geometry_kernel_run_performed':False,
            'full_boolean_boundary_comparisons_in_receipt':report['full_boolean_boundary_comparisons'],
            'exact_serialized_brep_duplicates_in_receipt':reused,
            'maximum_sampled_boundary_distance_mm':max_boundary,
            'manufacturing_ready':False,'kicad_placement_qualified':False}
    output=ROOT/'audit/author-model-geometry-receipt-validation.json'
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    main()
