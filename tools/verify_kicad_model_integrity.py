"""Fast hash-bound integrity check for completed heavy model-export validation.

Uses only Python's standard library. This does not repeat CAD Booleans: it
rejects stale receipts when any bound source, pose, model, board or export has
changed. Run verify_kicad_model_exports.py with CadQuery/OCP to refresh evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def verify(candidate):
    folder = ROOT/'editing/kicad-models-attached'/candidate
    auditpath = folder/'model-attachment-audit.json'
    receiptpath = folder/'model-export-validation.json'
    audit, receipt = read(auditpath), read(receiptpath)
    assert audit['attached'] and receipt['passed']
    assert receipt['attachment_audit_sha256'] == sha(auditpath)
    assert receipt['geometry_verifier_sha256'] == sha(ROOT/'tools/verify_kicad_model_exports.py')
    assert receipt['calibration_sha256'] == sha(ROOT/'audit/kicad-model-frame-calibration.json')
    calibration = read(ROOT/'audit/kicad-model-frame-calibration.json')
    assert audit['native_version'] == receipt['actual_native_version'] == calibration['native_version'] == '10.0.7'
    for name, digest in calibration['fixture_files'].items():
        assert sha(ROOT/name) == digest
    base = audit['base_candidate']
    assert sha(folder/(base+'.kicad_pcb')) == receipt['board_sha256'] == audit['board_sha256']
    assert sha(ROOT/audit['parent_board']) == audit['parent_board_sha256']
    for name, digest in audit['unchanged_project_files'].items():
        assert sha(folder/name) == digest
    assert receipt['pose_review_sha256'] == audit['pose_review_sha256'] == sha(ROOT/'audit/model-pose-independent-review.json')
    pose = next(x for x in read(ROOT/'audit/model-pose-independent-review.json')['boards'] if x['candidate'] == base)
    assert sha(ROOT/'editing/recovered-community'/base/'replayed-project.json') == pose['source_replay_sha256']
    manifestpath = ROOT/'recovered/author-step-components'/base/'component-manifest.json'
    assert sha(manifestpath) == audit['component_manifest_sha256'] == pose['source_component_manifest_sha256']
    manifest = read(manifestpath)
    assert sha(ROOT/manifest['source_step']) == manifest['source_step_sha256']
    refs = {x['reference'] for x in audit['models']}
    assert refs == {x['reference'] for x in receipt['models']} == {x['reference'] for x in pose['placed_instances']}
    assert receipt['models_verified'] == len(refs)
    for row in audit['models']:
        source_component = next(x for x in manifest['components'] if x['reference'] == row['reference'])
        expected_source = manifestpath.parent/source_component['step_file']
        assert (ROOT/row['source_placed_step']).resolve() == expected_source.resolve()
        assert row['source_placed_sha256'] == source_component['step_sha256']
        assert row['source_model_id'] == source_component['metadata_model_id']
        assert sha(ROOT/row['source_placed_step']) == row['source_placed_sha256']
        assert sha(folder/row['local_model_file']) == row['local_model_sha256']
        checked = next(x for x in receipt['models'] if x['reference'] == row['reference'])
        assert checked['source_model_id'] == row['source_model_id']
        assert checked['source_placed_sha256'] == row['source_placed_sha256']
        assert checked['local_model_sha256'] == row['local_model_sha256']
        assert checked['source_to_local_geometry']['passed'] and checked['local_to_native_export_geometry']['passed']
    for fmt in ['step','glb']:
        assert sha(folder/audit[fmt+'_export']['file']) == audit[fmt+'_export']['sha256'] == receipt[fmt+'_export_sha256']
    for name, digest in receipt['local_library_sha256'].items():
        assert sha(folder/name) == digest
    assert receipt['physical_fit_qualified'] is False and receipt['manufacturing_ready'] is False
    return {'candidate':candidate, 'models_verified':len(refs), 'geometry_receipt_sha256':sha(receiptpath), 'passed':True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', action='append')
    args = parser.parse_args()
    candidates = args.candidate or ['imu_to_dxl','imu_to_dxl_1V0A','imu_to_dxl_1V0A-transition-hypothesis','wire_hub_1V0A','POGO_PIN_1V0A']
    results = [verify(candidate) for candidate in candidates]
    summary = {'schema':'microduck-kicad-model-integrity/v1', 'passed':True,
               'verification':'Current hashes bound to completed CAD geometry checks; heavy Booleans not repeated',
               'candidates':results, 'models_including_hypothesis':sum(r['models_verified'] for r in results),
               'physical_fit_qualified':False,'manufacturing_ready':False}
    (ROOT/'audit/kicad-model-integrity-validation.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    receipts = [read(ROOT/'editing/kicad-models-attached'/candidate/'model-export-validation.json') for candidate in candidates]
    geometry_summary = {'schema':'microduck-kicad-model-export-suite/v1','passed':True,
                        'candidates':len(receipts),'models_verified_including_hypothesis':sum(r['models_verified'] for r in receipts),
                        'aggregation':'Current hash-checked per-project heavy CAD receipts',
                        'physical_fit_qualified':False,'manufacturing_ready':False,
                        'results':[{k:r[k] for k in ['candidate','models_verified','missing_models_preserved','step_export_sha256','glb_export_sha256','board_sha256','native_export_model_datums_mm']} for r in receipts]}
    (ROOT/'audit/kicad-model-export-validation.json').write_text(json.dumps(geometry_summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
