import bpy, json, sys, math, re
from pathlib import Path
from mathutils import Matrix, Vector

root=Path(sys.argv[sys.argv.index('--')+1]).resolve()
spec=json.loads((root/'audit/assembled-robot.json').read_text())
scene=bpy.context.scene
scene.unit_settings.system='METRIC'; scene.unit_settings.scale_length=1.0
# This script runs in a separate factory-startup background process.
for obj in list(scene.objects):
    bpy.data.objects.remove(obj,do_unlink=True)
def collection(name):
    col=bpy.data.collections.new(name); scene.collection.children.link(col); return col
visual=collection('MicroDuck_visuals'); body_col=collection('MicroDuck_rigid_link_frames')
collision=collection('MicroDuck_collision_meshes'); joint_col=collection('MicroDuck_joint_metadata')
def matrix(position,rotation):
    mat=Matrix(rotation).to_4x4(); mat.translation=Vector(position); return mat
meshes={}
for item in spec['meshes']:
    mesh=bpy.data.meshes.new(item['name']); mesh.from_pydata(item['vertices_m'],[],item['faces']); mesh.update()
    meshes[item['id']]=mesh
bodies={}
for body in spec['bodies']:
    obj=bpy.data.objects.new(body['name'],None); body_col.objects.link(obj)
    if body['parent_id'] in bodies:
        obj.parent=bodies[body['parent_id']]
    obj.matrix_world=matrix(body['position_m'],body['rotation']); obj.empty_display_size=0.008
    obj['source_body_id']=body['id']; obj['mass_kg']=body['mass_kg']
    obj['com_local_m']=body['com_local_m']; obj['inertia_principal_kg_m2']=body['inertia_principal_kg_m2']
    obj['inertia_quaternion_wxyz']=body['inertia_quaternion_wxyz']; bodies[body['id']]=obj
visual_objects=[]
for geom in spec['geoms']:
    if geom['type']!=7 or geom['mesh_id']<0:
        continue
    col=visual if geom['group']==2 else collision
    obj=bpy.data.objects.new(f"{bodies[geom['body_id']].name}__{geom['name']}",meshes[geom['mesh_id']])
    col.objects.link(obj); obj.parent=bodies[geom['body_id']]
    obj.matrix_world=matrix(geom['position_m'],geom['rotation'])
    obj['source_geom_id']=geom['id']; obj['source_mesh_id']=geom['mesh_id']; obj['mujoco_geom_group']=geom['group']
    if col==visual:
        material=bpy.data.materials.new('color_'+str(geom['id'])); material.diffuse_color=tuple(geom['rgba'])
        # Shared meshes may have differently colored instances: use object material slots.
        if not obj.data.materials:
            obj.data.materials.append(material)
        obj.material_slots[0].link='OBJECT'; obj.material_slots[0].material=material
        visual_objects.append(obj)
    else:
        obj.hide_render=True; obj.hide_set(True)
for joint in spec['joints']:
    obj=bpy.data.objects.new(joint['name'],None); joint_col.objects.link(obj)
    obj.parent=bodies[joint['body_id']]; obj.location=joint['position_body_m']; obj.empty_display_size=0.012
    obj['joint_definition']=json.dumps(joint); obj.empty_display_type='ARROWS'; obj.hide_render=True
scene['source_scene']=spec['source_scene']; scene['source_commit']=spec['source_commit']
scene['license']='Robot meshes: Pollen Robotics, CC BY-NC-SA 4.0; converted to Blender with MJCF STAND transforms.'
scene['limitations']='Editable mesh assembly with rigid-link frames and joint metadata; no CAD feature history or automatic physics/control rig.'
bpy.context.view_layer.update()
all_points=[obj.matrix_world@vertex.co for obj in visual_objects for vertex in obj.data.vertices]
low=Vector([min(p[i] for p in all_points) for i in range(3)])
high=Vector([max(p[i] for p in all_points) for i in range(3)])
center=(low+high)/2; size=high-low
cam_data=bpy.data.cameras.new('ReviewCamera'); cam=bpy.data.objects.new('ReviewCamera',cam_data); scene.collection.objects.link(cam)
cam.location=center+Vector((0.42,-0.46,0.24)); cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
cam_data.type='ORTHO'; cam_data.ortho_scale=max(size)*1.7; scene.camera=cam
engines=list(bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items)
workbench=next((e.identifier for e in engines if 'workbench' in e.name.lower() or 'workbench' in e.identifier.lower()),None)
if not workbench:
    try:
        scene.render.engine=''
    except TypeError as error:
        candidates=re.findall(r"'([^']+)'",str(error))
        workbench=next((name for name in candidates if 'workbench' in name.lower()),None)
    if not workbench:
        raise RuntimeError('Workbench renderer not registered: '+str([(e.identifier,e.name) for e in engines]))
scene.render.engine=workbench
scene.display.shading.light='STUDIO'; scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_shadows=True; scene.display.shading.show_cavity=True
scene.render.resolution_x=1000; scene.render.resolution_y=1000; scene.render.resolution_percentage=100
output=root/'editing/blender/MicroDuck-baseline.blend'
bpy.ops.wm.save_as_mainfile(filepath=str(output))
scene.render.filepath=str(root/'audit/MicroDuck-Blender-preview.png')
bpy.ops.render.render(write_still=True)
report={'blender_version':bpy.app.version_string,'body_frames':len(bodies),'visual_mesh_instances':len(visual_objects),
        'joint_metadata_objects':len(spec['joints']),'bounds_m':[list(low),list(high)],'dimensions_m':list(size),
        'source_pose':spec['pose'],'native_cad_feature_history':False,'automatic_joint_rig':False}
(root/'audit/blender-validation.json').write_text(json.dumps(report,indent=2))
print('MICRODUCK_BLENDER_PREPARED',json.dumps(report))
