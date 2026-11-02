import argparse
import json
from pathlib import Path
parser = argparse.ArgumentParser(description='Verify native Windows Isaac Sim physics and camera rendering.')
parser.add_argument('--output-dir', type=Path, required=True)
args, _ = parser.parse_known_args()
from isaacsim import SimulationApp

app = SimulationApp({'headless': True, 'width': 640, 'height': 480, 'multi_gpu': False})
try:
    import numpy as np
    from isaacsim.core.api import World
    from isaacsim.core.api.objects import DynamicCuboid
    import omni.replicator.core as rep
    from PIL import Image

    dest = args.output_dir.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    cube = world.scene.add(DynamicCuboid(prim_path='/World/TestCube', name='test_cube', position=np.array([0.,0.,1.]), size=0.2, color=np.array([0.9,0.4,0.1])))
    rep.create.light(light_type='Dome', intensity=1000)
    camera = rep.create.camera(position=(2,2,1.5), look_at=(0,0,0.2))
    product = rep.create.render_product(camera, (640,480))
    rgb = rep.AnnotatorRegistry.get_annotator('rgb')
    rgb.attach(product)
    world.reset()
    for _ in range(120):
        world.step(render=True)
    position = cube.get_world_pose()[0]
    print('CUBE_POSITION', position.tolist(), flush=True)
    assert 0.05 < position[2] < 0.2, 'Cube did not settle on ground'
    rep.orchestrator.step(rt_subframes=8)
    frame = rgb.get_data()
    print('RGB_SHAPE', frame.shape, flush=True)
    assert frame.size > 0 and frame.std() > 1, 'No useful rendered image'
    Image.fromarray(frame).save(dest / 'Windows-simulation.png')
    (dest / 'Windows-simulation-result.json').write_text(json.dumps({'physics_passed':True,'rendering_passed':True,'cube_position':position.tolist(),'image_shape':list(frame.shape)},indent=2))
    print('WINDOWS_SIMULATION_SMOKE_PASSED', flush=True)
finally:
    app.close()
