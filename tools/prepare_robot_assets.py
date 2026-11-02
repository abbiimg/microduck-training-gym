from pathlib import Path
import hashlib, json, shutil, subprocess, sys, xml.etree.ElementTree as ET
import mujoco
import numpy as np
import trimesh

root = Path(sys.argv[1]).resolve()
repo = root / 'upstream/microduck_rl'
robot = repo / 'src/mjlab_microduck/robot/microduck'
out = root / 'editing'
(out / 'solidworks/meshes_mm').mkdir(parents=True, exist_ok=True)
(out / 'blender').mkdir(parents=True, exist_ok=True)
(root / 'audit').mkdir(exist_ok=True)
model = mujoco.MjModel.from_xml_path(str(robot / 'scene_walk.xml'))
data = mujoco.MjData(model)
key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, 'STAND')
mujoco.mj_resetDataKeyframe(model, data, key)
mujoco.mj_forward(model, data)
name = lambda typ, i: mujoco.mj_id2name(model, typ, i) or f'unnamed_{i}'
meshes = []
for i in range(model.nmesh):
    va, vn = int(model.mesh_vertadr[i]), int(model.mesh_vertnum[i])
    fa, fn = int(model.mesh_faceadr[i]), int(model.mesh_facenum[i])
    meshes.append({'id':i,'name':name(mujoco.mjtObj.mjOBJ_MESH,i),
                   'vertices_m':model.mesh_vert[va:va+vn].tolist(),
                   'faces':model.mesh_face[fa:fa+fn].tolist()})
bodies = []
for i in range(1,model.nbody):
    bodies.append({'id':i,'name':name(mujoco.mjtObj.mjOBJ_BODY,i),'parent_id':int(model.body_parentid[i]),
                   'position_m':data.xpos[i].tolist(),'rotation':data.xmat[i].reshape(3,3).tolist(),
                   'mass_kg':float(model.body_mass[i]),'com_local_m':model.body_ipos[i].tolist(),
                   'inertia_principal_kg_m2':model.body_inertia[i].tolist(),
                   'inertia_quaternion_wxyz':model.body_iquat[i].tolist()})
geoms = []
for i in range(model.ngeom):
    if model.geom_bodyid[i] == 0:
        continue
    geoms.append({'id':i,'name':name(mujoco.mjtObj.mjOBJ_GEOM,i),'body_id':int(model.geom_bodyid[i]),
                  'type':int(model.geom_type[i]),'mesh_id':int(model.geom_dataid[i]),
                  'group':int(model.geom_group[i]),'position_m':data.geom_xpos[i].tolist(),
                  'rotation':data.geom_xmat[i].reshape(3,3).tolist(),'size_m':model.geom_size[i].tolist(),
                  'rgba':model.geom_rgba[i].tolist()})
joints=[]
for i in range(model.njnt):
    joints.append({'name':name(mujoco.mjtObj.mjOBJ_JOINT,i),'body_id':int(model.jnt_bodyid[i]),
                   'type':int(model.jnt_type[i]),'position_body_m':model.jnt_pos[i].tolist(),
                   'axis_body':model.jnt_axis[i].tolist(),'limited':bool(model.jnt_limited[i]),
                   'range':model.jnt_range[i].tolist()})
scene={'units':'m','up_axis':'Z','pose':'STAND keyframe from official scene_walk.xml',
       'source_commit':subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip(),
       'source_scene':str(robot/'scene_walk.xml'),'mujoco_version':mujoco.__version__,
       'meshes':meshes,'bodies':bodies,'geoms':geoms,'joints':joints,
       'actuators':[name(mujoco.mjtObj.mjOBJ_ACTUATOR,i) for i in range(model.nu)]}
(root/'audit/assembled-robot.json').write_text(json.dumps(scene))
audit=[]
for file in sorted((robot/'assets').glob('*.stl')):
    mesh=trimesh.load_mesh(file,process=False)
    mesh.apply_scale(1000)
    target=out/'solidworks/meshes_mm'/file.name
    mesh.export(target)
    diagnostic=trimesh.Trimesh(vertices=mesh.vertices,faces=mesh.faces,process=True)
    audit.append({'source':str(file.relative_to(root)), 'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                  'derivative':str(target.relative_to(root)), 'coordinate_units':'mm','scale_from_source':1000,
                  'bounds_mm':mesh.bounds.tolist(),'triangles':len(mesh.faces),
                  'watertight_after_trimesh_vertex_processing':bool(diagnostic.is_watertight), 'native_parametric_CAD':False})
(root/'audit/mesh-inventory.json').write_text(json.dumps(audit,indent=2))
shutil.copy2(repo/'LICENSE-MODELS.md',out/'solidworks/MESH-LICENSE.md')
links_dir=out/'solidworks/rigid_links_mm'; links_dir.mkdir(exist_ok=True)
assembled=[]; link_exports=[]
for body in bodies:
    components=[]
    body_matrix=np.eye(4); body_matrix[:3,:3]=body['rotation']; body_matrix[:3,3]=body['position_m']
    for geom in geoms:
        if geom['body_id']!=body['id'] or geom['group']!=2 or geom['type']!=7:
            continue
        item=meshes[geom['mesh_id']]
        mesh=trimesh.Trimesh(vertices=item['vertices_m'],faces=item['faces'],process=False)
        geom_matrix=np.eye(4); geom_matrix[:3,:3]=geom['rotation']; geom_matrix[:3,3]=geom['position_m']
        world=mesh.copy(); world.apply_transform(geom_matrix); assembled.append(world)
        mesh.apply_transform(np.linalg.inv(body_matrix)@geom_matrix); components.append(mesh)
    if components:
        mesh=trimesh.util.concatenate(components); mesh.apply_scale(1000)
        mesh.export(links_dir/(body['name']+'.stl'))
        transform=body_matrix.copy(); transform[:3,3]*=1000
        link_exports.append({'link':body['name'],'file':'rigid_links_mm/'+body['name']+'.stl',
                             'link_to_assembly_matrix_mm':transform.tolist()})
whole=trimesh.util.concatenate(assembled); whole.apply_scale(1000)
whole.export(out/'solidworks/MicroDuck-assembled-mm.stl')
(out/'solidworks/assembly-mm.json').write_text(json.dumps({'coordinate_units':'mm','up_axis':'Z',
 'pose':scene['pose'],'parts':link_exports,'assembly_bounds_mm':whole.bounds.tolist(),
 'limitations':'Faceted mesh references, not original parametric CAD. No native SolidWorks import or solid-body verification performed.'},indent=2))
print(json.dumps({'meshes_available':len(audit),'model_meshes':model.nmesh,'rigid_bodies':model.nbody-1,
                  'joints_including_free_root':model.njnt,'actuators':model.nu,'xml_load':'passed'}))
