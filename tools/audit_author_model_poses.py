"""Regenerate the read-only author STEP/source footprint pose audit.

Run from any directory with ordinary Python after recovering source replays and
component manifests. Writes only audit/model-pose-independent-review.json; no
KiCad board, STEP geometry or source snapshot is modified. This records pose
consistency, not physical fit or original vendor-model origin qualification.
"""
import json,math,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[1];h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
models=json.loads((r/'audit/placed-device-model-metadata.json').read_text());steps=json.loads((r/'audit/step-xcaf-identity-review.json').read_text())
boards=[];groups={}
for c in ['imu_to_dxl','imu_to_dxl_1V0A','wire_hub_1V0A','POGO_PIN_1V0A']:
 replay=r/'editing/recovered-community'/c/'replayed-project.json';d=json.loads(replay.read_text(encoding='utf-8'))
 rec=next(x for x in d['documents'] if x['head']['docType']=='PCB')['records'];refs={x['data']['parentId']:x['data']['value'] for x in rec if x['header']['type']=='ATTR' and x['data']['key']=='Designator'}
 attrs={}
 for x in rec:
  if x['header']['type']=='ATTR':attrs.setdefault(x['data']['parentId'],{})[x['data']['key']]=x['data']['value']
 cv=next(x['data'] for x in rec if x['header']['type']=='CANVAS');comps={refs[x['header']['id']]:dict(x['data'],source_id=x['header']['id']) for x in rec if x['header']['type']=='COMPONENT' and x['header']['id'] in refs}
 manpath=r/'recovered/author-step-components'/c/'component-manifest.json';man=json.loads(manpath.read_text());md={x['reference']:x for x in next(x for x in models if x['candidate']==c)['placed_device_models']}
 b=next(x for x in next(x for x in steps if x['candidate']==c)['records'] if x['referred_label'].startswith('Board~'))
 top=b['bounds_mm'][1][2];bottom=b['bounds_mm'][0][2];thickness_raw=sum(x['data'].get('thickness',0) for x in rec if x['header']['type']=='LAYER_PHYS');assert abs(top-thickness_raw/39.37)<1e-9 and bottom==0
 rows=[]
 for m in man['components']:
  s=comps[m['reference']];a=math.radians(s['angle']);co=round(math.cos(a),14);si=round(math.sin(a),14);bot=s['layerId']==2;assert s['layerId'] in(1,2)
  # Rz(a) * Rx(180) for bottom; y/z columns invert.
  R=[[co,-si,0],[si,co,0],[0,0,1]]
  if bot:
   for l in R:l[1]*=-1;l[2]*=-1
  o=[(s['x']-cv['originX'])/39.37,(s['y']-cv['originY'])/39.37,bottom if bot else top];T=m['instance_location_matrix']
  Q=[[sum(R[k][i]*T[k][j] for k in range(3)) for j in range(3)]+[sum(R[k][i]*(T[k][3]-o[k]) for k in range(3))] for i in range(3)]
  row={'reference':m['reference'],'source_component_id':s['source_id'],'source_xy_mil':[s['x'],s['y']],'source_angle_degrees':s['angle'],'source_layer':s['layerId'],'source_frame_rotation':R,'source_frame_origin_author_mm':o,'step_instance_matrix':T,'definition_to_source_footprint_frame_matrix':Q,'model_id':m['metadata_model_id'],'model_title':m['metadata_model_title'],'device_model_transform':md[m['reference']]['metadata']['3D Model Transform'],'placed_model_attribute_overrides':{k:v for k,v in attrs[s['source_id']].items() if k.startswith('3D Model')}}
  rows.append(row);groups.setdefault(row['model_id'],[]).append((c,row))
 missing=[]
 for ref in man['missing_references']:
  s=comps[ref];missing.append({'reference':ref,'source_component_id':s['source_id'],'device_model_metadata':md[ref]['metadata'],'placed_model_attribute_overrides':{k:v for k,v in attrs[s['source_id']].items() if k.startswith('3D Model')},'conclusion':'source placed title is explicitly empty; do not treat device default model metadata as evidence that instance should be exported'})
 boards.append({'candidate':c,'source_replay_sha256':h(replay),'source_component_manifest_sha256':h(manpath),'source_canvas_origin_mil':[cv['originX'],cv['originY']],'source_physical_stack_mil':thickness_raw,'source_physical_stack_mm_div39_37':thickness_raw/39.37,'source_physical_stack_mm_exact_mil':thickness_raw*.0254,'author_board_Z_mm':[bottom,top],'source_step_board_label':b['referred_label'],'placed_instances':rows,'missing_instances':missing})
group_reports=[]
for mid,members in sorted(groups.items()):
 q=members[0][1]['definition_to_source_footprint_frame_matrix'];rotmax=max(abs(row['definition_to_source_footprint_frame_matrix'][i][j]-q[i][j]) for _,row in members for i in range(3) for j in range(3));transmax=max(abs(row['definition_to_source_footprint_frame_matrix'][i][3]-q[i][3]) for _,row in members for i in range(3))
 group_reports.append({'model_id':mid,'model_title':members[0][1]['model_title'],'instances':len(members),'members':[[c,row['reference']] for c,row in members],'max_relative_rotation_matrix_delta':rotmax,'max_relative_translation_delta_mm':transmax,'common_matrix_within_1e_7':rotmax<1e-7 and transmax<1e-7,'representative_definition_to_source_footprint_frame_matrix':q})
report={'schema':'microduck-model-pose-review/v1','scope':'read-only source/author placement comparison; no native board edits or model attachments','candidate_count':len(boards),'placed_step_instances':sum(len(b['placed_instances']) for b in boards),'model_id_groups':len(group_reports),'author_coordinate_policy':'XY=(source coordinate-CANVAS origin)/39.37; Z author bottom0, author top=sum source LAYER_PHYS thickness/39.37. This is supported for all four assemblies by exact Board Z bounds. Source footprint frame is Rz(source angle), additionally Rx180 on bottom. Per-instance inverse frame matrices retain source model-specific offsets and rotations.','native_mapping_caution':'Native recovered PCB uses exact mil0.0254, while author exporter uses division39.37: global origin/scale are not one rigid transform. Map footprint origins exactly to current KiCad locations while preserving local model dimensions; declare this policy. Native exporter model Z datums must be calibrated against actual version and stackup, not inferred from nominal board thickness.','source_placed_model_override_warning':'Revised J3 has explicit empty placed 3D Model Title. Device model default remains populated but does not override this evidence. Missing placed source cannot be synthesized as exact recovery.','global_author_xy_to_exact_native_mechanical_frame':{'scale_xy':39.37*.0254,'translation_if_absolute_native_export_origin_mm':'source CANVAS origin*0.0254 with native3D X=KiCadX,Y=-KiCadY; add exporter chosen XY origin convention separately','is_rigid':False},'boards':boards,'per_model_relative_consistency':group_reports,'native_board_placement_qualified':False,'original_vendor_geometry_origin_qualified':False,'full_definition_brep_equivalence_qualified':False,'manufacturing_ready':False}
(r/'audit/model-pose-independent-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'boards':len(boards),'instances':report['placed_step_instances'],'groups':len(group_reports),'groups_consistent':sum(x['common_matrix_within_1e_7'] for x in group_reports),'max_rotation_delta':max(x['max_relative_rotation_matrix_delta'] for x in group_reports),'max_translation_delta_mm':max(x['max_relative_translation_delta_mm'] for x in group_reports)},indent=2))
for x in group_reports:
 if not x['common_matrix_within_1e_7']:print(x['model_title'],x['members'],x['max_relative_translation_delta_mm'],x['max_relative_rotation_matrix_delta'])


