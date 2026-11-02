from pathlib import Path
import collections, hashlib, json, shutil, subprocess
root=Path('outputs/microduck-assets').resolve()
repos=[]
for repo in sorted([*(root/'upstream').iterdir(),*(root/'community').iterdir()]):
    if not (repo/'.git').exists():
        continue
    repos.append({'name':repo.name,'url':subprocess.check_output(['git','-C',str(repo),'remote','get-url','origin'],text=True).strip(),
                  'commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
                  'status':subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip()})
files=[]; lfs=[]
for path in sorted(root.rglob('*')):
    if not path.is_file() or '.git' in path.relative_to(root).parts or path.name=='asset-manifest.json':
        continue
    if path.name.endswith('.lck') or path.name.startswith('~$'):
        continue
    content=path.read_bytes()
    if content.startswith(b'version https://git-lfs.github.com/spec/v1'):
        lfs.append(str(path.relative_to(root)))
    files.append({'path':str(path.relative_to(root)).replace('\\','/'),'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
meshes=json.loads((root/'audit/mesh-inventory.json').read_text())
assembly=json.loads((root/'editing/solidworks/assembly-mm.json').read_text())
blender=json.loads((root/'audit/blender-validation.json').read_text())
for i in range(3):
    expected=blender['dimensions_m'][i]*1000
    actual=assembly['assembly_bounds_mm'][1][i]-assembly['assembly_bounds_mm'][0][i]
    assert abs(expected-actual)<0.01,(expected,actual)
drc=json.loads((root/'audit/Robot_HAT-drc.json').read_text())
erc=json.loads((root/'audit/Robot_HAT-erc.json').read_text())
erc_entries=[v for sheet in erc.get('sheets',[]) for v in sheet.get('violations',[])]
manifest={'audit_date':'2026-10-27','repositories':repos,'files':files,'unresolved_lfs_pointers':lfs,
          'counts':{'source_STL':len(meshes),'rigid_link_STL':len(assembly['parts']),'blender_visual_instances':blender['visual_mesh_instances']},
          'cross_format_bounds_tolerance_mm':0.01,
          'drc':dict(collections.Counter(v['type'] for v in drc.get('violations',[]))),
          'erc':dict(collections.Counter(v['type'] for v in erc_entries)),
          'critical_gaps':['Original Pollen source CAD and original production IMU electronics still not obtained; community alternatives are separate.',
                           'Paired routed KiCad projects and component-model review files exist; source-history ambiguity, DRC findings and full circuit/physical qualification remain unresolved.',
                           'Oscillator fit envelope is datasheet-derived, not the exact original detail CAD.',
                           'Manufacturing and community-CAD-to-simulation/policy compatibility remain unverified.'],
          'licenses':{'microduck_rl_code_and_MJCF':'Apache-2.0; see upstream LICENSE',
                      'microduck_rl_STL_and_mesh_derivatives':'Pollen Robotics CC BY-NC-SA 4.0; see LICENSE-MODELS.md',
                      'Robot_HAT':'Apache-2.0; see upstream LICENSE',
                      'lib_KiCAD':'No top-level license located during audit; preserve provenance and verify terms before redistribution.',
                      'NVIDIA_USD':'Official Isaac Sim asset source; vendor asset terms apply, not automatically the Pollen mesh license.'}}
closure=root/'audit/gap-closure.json'
if closure.exists():
    manifest['gap_closure']=json.loads(closure.read_text(encoding='utf-8'))
manifest['routed_recovery']={'status_report':'ROUTED-PCB-RECOVERY.txt','manufacturing_ready':False,'validation':[]}
for path in sorted((root/'editing').glob('kicad-*/*/validation.json')):
    if 'routed' in str(path) or 'engineering' in str(path):
        manifest['routed_recovery']['validation'].append({'path':str(path.relative_to(root)).replace('\\','/'),'result':json.loads(path.read_text())})
for name,relative in [('software_stack','audit/pcb-tools/software-stack-result.json'),('isaac_training','simulation/validation-runs/2026-10-26_14-57-39_pcb_pipeline_baseline/validation.json')]:
    if (root/relative).exists():manifest.setdefault('latest_validation',{})[name]=json.loads((root/relative).read_text())
manifest.setdefault('latest_validation',{}).update(status_report='END-TO-END-STATUS.txt',full_physical_reproduction_verified=False)
paired=root/'editing/paired-validation-summary.json'
if paired.exists():
    manifest['paired_editing']={'status_report':'KICAD-PAIRED-PROJECTS.txt','projects':json.loads(paired.read_text()),'libraries':[json.loads(p.read_text()) for p in sorted((root/'editing/kicad-paired').glob('*/library-validation.json'))],'manufacturing_ready':False}
transient=root/'audit/pcb-tools/ti-buffer-transient/results.json'
if transient.exists():manifest['latest_validation']['ti_buffer_transient']=json.loads(transient.read_text())
package=root/'audit/pcb-tools/ti-buffer-package/results.json'
if package.exists():manifest['latest_validation']['ti_buffer_package']=json.loads(package.read_text())
copper=root/'editing/copper-engineering-validation.json'
if copper.exists():
    manifest['copper_engineering']={'status_report':'COPPER-CONSOLIDATION.txt','validation':json.loads(copper.read_text()),'source_minima_projects':[{'candidate':p.parent.name,'drc_counts':json.loads(p.read_text())['drc_counts']} for p in sorted((root/'editing/kicad-source-rules-projected').glob('*/source-minima-audit.json'))],'graphic_correction':json.loads((root/'editing/kicad-graphic-corrected/POGO_PIN_1V0A/graphic-restoration-audit.json').read_text()),'manufacturing_ready':False}
clearance=root/'editing/source-clearance-validation.json'
if clearance.exists():
    manifest['integrated_ecad_assets']={'status_report':'SOURCE-CLEARANCE-PROGRESS.txt','source_clearances':json.loads(clearance.read_text()),'silkscreen':json.loads((root/'audit/footprint-silkscreen-summary.json').read_text()),'component_instances':json.loads((root/'audit/author-step-component-validation.json').read_text()),'model_definitions':json.loads((root/'audit/author-model-definition-validation.json').read_text()),'manufacturing_ready':False}
model_integrity=root/'audit/kicad-model-integrity-validation.json'
if model_integrity.exists():
    integrity=json.loads(model_integrity.read_text())
    assert integrity['passed'] and len(integrity['candidates'])==5,'Complete all five model-project checks before packaging'
    manifest['pcb_model_projects']={'status_report':'MODEL-PLACEMENT-PROGRESS.txt',
        'geometry_integrity':integrity,
        'review_package':json.loads((root/'audit/pcb-model-review-package-validation.json').read_text()),
        'definition_geometry':json.loads((root/'audit/author-model-geometry-validation.json').read_text()),
        'hub_cache_repair':json.loads((root/'editing/cache-repair-validation.json').read_text()),
        'manufacturing_ready':False,'full_physical_reproduction_verified':False}
    distinct=set()
    for candidate in integrity['candidates']:
        info=json.loads((root/'editing/kicad-models-attached'/candidate['candidate']/'model-attachment-audit.json').read_text())
        distinct.update((info['base_candidate'],r['reference']) for r in info['models'])
    manifest['counts'].update(pcb_model_attachments=integrity['models_including_hypothesis'],
        distinct_placed_pcb_component_models=len(distinct),
        pcb_blender_review_files=len(list((root/'editing/kicad-models-attached').glob('*/assembly-review.blend'))))
    manifest['latest_validation']['current_editing_report']='MODEL-PLACEMENT-PROGRESS.txt'
(root/'asset-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({k:v for k,v in manifest.items() if k not in ('files','licenses')},indent=2))
