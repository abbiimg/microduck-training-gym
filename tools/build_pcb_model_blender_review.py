"""Import a generated KiCad GLB in a separate factory-startup Blender process.

Does not connect to, clear, or overwrite the user's interactive Blender scene.
GLB uses metres. Preserve exact imported transforms; camera only is framed.
"""
import bpy,json,sys,hashlib,re
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
candidate=sys.argv[sys.argv.index('--')+1]
folder=root/'editing/kicad-models-attached'/candidate
source=folder/'assembly-review.glb'
assert source.is_file()
scene=bpy.context.scene
for obj in list(scene.objects):bpy.data.objects.remove(obj,do_unlink=True)
scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
bpy.ops.import_scene.gltf(filepath=str(source));bpy.context.view_layer.update()
meshes=[o for o in scene.objects if o.type=='MESH']
assert meshes and sum(len(o.data.vertices) for o in meshes)>0
points=[obj.matrix_world@Vector(c) for obj in meshes for c in obj.bound_box]
low=Vector([min(p[i] for p in points) for i in range(3)]);high=Vector([max(p[i] for p in points) for i in range(3)])
center=(low+high)/2;size=high-low;extent=max(size)
camdata=bpy.data.cameras.new('ComponentReviewCamera');cam=bpy.data.objects.new('ComponentReviewCamera',camdata);scene.collection.objects.link(cam)
bottom_view=candidate=='POGO_PIN_1V0A'
cam.location=center+Vector((1,-1,-1.1 if bottom_view else 1.1)).normalized()*extent*2
cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=extent*1.5;scene.camera=cam
camdata.clip_start=.00001;camdata.clip_end=10
try:scene.render.engine='BLENDER_WORKBENCH'
except TypeError as error:
    options=re.findall(r"'([^']+)'",str(error));scene.render.engine=next(x for x in options if 'WORKBENCH' in x)
scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
scene.display.shading.background_type='WORLD';scene.world.color=(.06,.07,.09)
scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
scene['provenance']='KiCad10.0.7 native assembly-review.glb; author component geometry re-framed per footprint; no parametric history recovered.'
scene['qualification']='Model placement/geometry review; board and component dimensions, electrical design, source revisions and physical fit remain unqualified.'
scene['source_glb_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.context.preferences.filepaths.save_version=0
dest=folder/'assembly-review.blend';bpy.ops.wm.save_as_mainfile(filepath=str(dest))
scene.render.filepath=str(folder/'assembly-review.png');bpy.ops.render.render(write_still=True)
report={'candidate':candidate,'blender_version':bpy.app.version_string,'source_glb':source.name,'source_glb_sha256':scene['source_glb_sha256'],
    'blend_file':dest.name,'blend_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'preview_file':'assembly-review.png',
    'preview_sha256':hashlib.sha256((folder/'assembly-review.png').read_bytes()).hexdigest(),
    'mesh_objects':len(meshes),'vertices':sum(len(o.data.vertices) for o in meshes),'unit_scale':1.0,'coordinate_units':'metres','camera_view':'bottom' if bottom_view else 'top',
    'imported_world_bounds_mm':[[v*1000 for v in low],[v*1000 for v in high]],'imported_world_dimensions_mm':[v*1000 for v in size],
    'import_transform_policy':'Native Blender glTF importer, no additional geometry translation/rotation/scale. Camera framed from actual transformed mesh bounds.',
    'objects':[{'name':obj.name,'vertices':len(obj.data.vertices),'matrix_world':[list(row) for row in obj.matrix_world]} for obj in meshes],
    'dimensions_qualified':False,'electrical_release_ready':False}
(folder/'blender-model-review.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PCB_MODEL_BLENDER_REVIEW',json.dumps({k:report[k] for k in ['candidate','mesh_objects','imported_world_dimensions_mm']}),flush=True)
