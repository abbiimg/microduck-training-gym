from pathlib import Path
import collections,hashlib,json,re,sqlite3,subprocess
import pypdfium2
root=Path('outputs/microduck-assets').resolve()
native=root/'community/SolidWorks-XL330-v1.1/SolidWorks-XL330-v1.1'
cad_files=[p for p in native.rglob('*') if p.suffix.lower() in ('.sldprt','.sldasm') and not p.name.startswith('~$')]
archive=root/'community/releases/SolidWorks-XL330-v1.1.zip'
archive_hash=hashlib.sha256(archive.read_bytes()).hexdigest()
assert archive_hash=='51bf6f6d4c50e6f8469751102d43520ccf3d69184c30166b5439bdbbd9749a0c'
assert len(cad_files)==57
step=json.loads((root/'audit/community-step-validation.json').read_text(encoding='utf-8'))
assert len(step)==30 and all(p['valid'] and p['solids']==1 and p['sha256_matches_author'] for p in step)
components=json.loads((root/'audit/community-solidworks-components.json').read_text(encoding='utf-8'))
missing_refs=[c['path'] for c in components['components'] if not Path(c['path']).is_file()]
assert not missing_refs
board=root/'editing/kicad/Robot_HAT_reference/elec_RPI_Robot_HAT.kicad_pcb'
missing_models=[]
for ref in set(re.findall(r'\(model "([^"\n]+)"',board.read_text(encoding='utf-8'))):
    resolved=ref.replace('${KIPRJMOD}',str(board.parent)).replace('${KICAD10_3DMODEL_DIR}',r'C:\Program Files\KiCad\10.0\share\kicad\3dmodels')
    if not Path(resolved).is_file(): missing_models.append(ref)
assert not missing_models
electronics=[]
for path in (root/'community/microduck-replica/hardware').rglob('*.eprj2'):
    db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)
    integrity=db.execute('pragma integrity_check').fetchone()[0]; db.close()
    assert integrity=='ok'
    electronics.append({'file':str(path.relative_to(root)),'sqlite_integrity':integrity,'native_editor':'EasyEDA Pro V3','kicad_conversion':'not validated'})
manual=root/'community/microduck-replica-cad/安装说明书/microduck装配安装说明书.pdf'
pages=len(pypdfium2.PdfDocument(str(manual)))
repos=[]
for repo in sorted((root/'community').iterdir()):
    if not (repo/'.git').exists(): continue
    repos.append({'path':str(repo.relative_to(root)),
                  'url':subprocess.check_output(['git','-C',str(repo),'remote','get-url','origin'],text=True).strip(),
                  'commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
                  'changes':subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip()})
result={'date':'2026-10-26','status':'Expanded mixed-provenance design-study package; not original factory package or manufacturing qualification',
        'community_sources':repos,'native_CAD':{'source':'https://github.com/fanhao375/microduck-replica-cad/releases/tag/v1.1',
            'designer':'机械行者Robo','variant':'XL330 v1.1 (2026-09-15)','archive_sha256':archive_hash,
            'files':dict(collections.Counter(p.suffix.upper() for p in cad_files)),
            'solidworks_revision_tested':'34.4.1','opened_read_only':True,'configuration_for_reference_check':'2',
            'resolved_component_instances':len(components['components']),'missing_component_files':missing_refs,
            'representative_part':'trunk_base_躯干底座.SLDPRT','representative_part_result':'Imported solid body plus sketch; not a recovered original feature tree'},
        'reconstructed_STEP':{'parts':len(step),'locally_valid_single_solids':len(step),'author_hashes_matched':len(step),
                              'original_snapshot':'29e887ecfbf5d37144759e5a9f8a176dfb83d547','same_as_current_official_geometry':'not established'},
        'assembly_manual':{'path':str(manual.relative_to(root)),'pages':pages},
        'community_electronics':electronics,
        'oscillator':{'method':'Manufacturer datasheet-derived box envelope; not manufacturer detail CAD',
                      'source':'https://abracon.com/Oscillators/ASDMB.pdf','nominal_mm':[2.5,2.0,0.85],
                      'maximum_envelope_mm':[2.55,2.05,0.9],'missing_referenced_PCB_model_files':missing_models},
        'remaining':{'original_Pollen_source_CAD':'Requires original source access; not obtained',
                     'original_imu_to_dxl_electronics':'Not obtained; community reconstructions included',
                     'KiCad_IMU_conversion':'Current eprj2 SQLite source returned empty boards in installed native importer; rejected',
                     'BOM_variants':'Community XL330 reconstruction BOM and newer Feetech procurement list are different; do not merge as verified official BOM',
                     'manufacturing':'Hardware revision, tolerances, electrical qualification, harness and physical tests unresolved',
                     'simulation':'Community CAD is not automatically mapped to the tested Isaac Lab articulation or policy; requires a separate revisioned conversion and validation'},
        'preference_note':'SolidWorks adjusted swSTLDeviation during open. Closest restored readback 0.224997705 mm versus initial 0.229357798 mm; exact readback was quantized. See preference recovery report.'}
(root/'audit/gap-closure.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'native_files':result['native_CAD']['files'],'resolved_SW_instances':len(components['components']),
                  'valid_STEP':len(step),'manual_pages':pages,'electronics_projects':len(electronics),'missing_referenced_model_files':missing_models},indent=2))
