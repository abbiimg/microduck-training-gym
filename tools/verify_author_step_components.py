"""Verify provenance/hashes of exact labeled author STEP component snapshots."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
digest=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
metadata={r['candidate']:r for r in json.loads((root/'audit/placed-device-model-metadata.json').read_text())}
expected_counts={'imu_to_dxl':29,'imu_to_dxl_1V0A':23,'wire_hub_1V0A':7,'POGO_PIN_1V0A':2};results=[];model_ids=set()
for name,count in expected_counts.items():
    folder=root/'recovered/author-step-components'/name
    manifest=json.loads((folder/'component-manifest.json').read_text());assert manifest['candidate']==name and manifest['recovered_references']==count
    assert manifest['missing_references']==(['J3'] if name=='imu_to_dxl_1V0A' else [])
    assert digest(root/manifest['source_step'].replace('\\','/'))==manifest['source_step_sha256']
    assert not manifest['kicad_placement_qualified'] and not manifest['new_parametric_history_recovered'] and not manifest['manufacturing_ready']
    md={r['reference']:r['metadata'] for r in metadata[name]['placed_device_models']};refs=set()
    for component in manifest['components']:
        ref=component['reference'];assert ref not in refs;refs.add(ref)
        assert component['source_definition_label'].startswith(ref+'~') and component['source_instance_label']==ref
        assert component['metadata_model_title']==md[ref]['3D Model Title'] and component['metadata_model_id']==md[ref]['3D Model']
        assert component['metadata_model_title'] in component['source_definition_label']
        assert component['valid'] and component['solids']>0 and component['volume_mm3']>0 and component['roundtrip_max_bbox_error_mm']<1e-5
        assert digest(folder/component['step_file'])==component['step_sha256']
        assert digest(folder/component['stl_file'])==component['stl_sha256']
        assert component['stl_units']=='unitless STL; stored numeric coordinates are millimetres'
        model_ids.add(component['metadata_model_id'])
    assert refs==set(md)-set(manifest['missing_references'])
    results.append({'candidate':name,'component_instances':count,'step_and_stl_hashes_verified':True,'source_step_unchanged':True,'missing_references':manifest['missing_references'],'kicad_placement_qualified':False})
summary={'source_assemblies':len(results),'recovered_component_instances':sum(r['component_instances'] for r in results),'step_files':61,'stl_files':61,'distinct_source_metadata_model_ids':len(model_ids),'coordinate_frame':'whole author PCB STEP world frame in mm, not footprint local','per_board':results,'manufacturing_ready':False}
(root/'audit/author-step-component-validation.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
