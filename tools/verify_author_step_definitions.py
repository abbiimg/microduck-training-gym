"""Verify exact-source definition asset coverage without claiming pose equivalence."""
from pathlib import Path
import json,hashlib,struct
root=Path(__file__).resolve().parents[1]
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
rel=lambda value:root/value.replace('\\','/')
index=json.loads((root/'recovered/author-step-model-definitions/model-definition-index.json').read_text())
metadata=json.loads((root/'audit/placed-device-model-metadata.json').read_text())
ids={m['metadata']['3D Model'] for board in metadata for m in board['placed_device_models']}
assert index['source_model_ids']==len(ids)==22 and index['source_instances_checked']==61
assert {m['model_id'] for m in index['models']}==ids
assert not index['full_brep_equivalence_proven'] and index['canonical_equivalence'].startswith('metric-only; unqualified')
assert not index['kicad_attachment_performed'] and not index['revised_imu_J3_placement_recovered'] and not index['manufacturing_ready']
for source in index['sources']:assert digest(rel(source['source_step']))==source['sha256']
variants=0;instances=0
for model in index['models']:
    assert not model['full_brep_equivalence_proven'] and model['canonical_equivalence'].startswith('metric-only; unqualified')
    for variant in model['variants']:
        variants+=1;assert variant['metrics']['valid'] and variant['metrics']['solids']>0
        assert variant['step_roundtrip']['metrics_agree']
        assert digest(rel(variant['step_file']))==variant['step_sha256']
        stl=rel(variant['stl_file']);assert digest(stl)==variant['stl_sha256']
        data=stl.read_bytes();assert len(data)>=84 and len(data)==84+50*struct.unpack_from('<I',data,80)[0]
        for instance in variant['instances']:
            instances+=1;ref=instance['reference']
            assert instance['source_instance_label']==ref and instance['source_definition_label'].startswith(ref+'~')
            assert digest(rel(instance['source_step']))==instance['source_step_sha256']
            assert instance['comparison_to_variant_representative']['metrics_agree']
assert variants==index['definition_variants']==22 and instances==61
summary={'metadata_model_ids_covered':len(ids),'device_metadata_records':sum(len(b['placed_device_models']) for b in metadata),'source_instances_checked':instances,'definition_variants':variants,'step_and_stl_hashes_and_stl_lengths_verified':True,'canonical_equivalence':'metric-only; unqualified','full_brep_equivalence_proven':False,'kicad_attachment_performed':False,'revised_imu_J3_placement_recovered':False,'manufacturing_ready':False}
(root/'audit/author-model-definition-validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
