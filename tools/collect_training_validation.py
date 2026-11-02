from pathlib import Path
import json,shutil,hashlib,re
import torch,onnx
import imageio.v2 as imageio
import numpy as np
root=Path(__file__).resolve().parents[1]
run=Path('/home/workbench/robotics/IsaacLab/logs/rsl_rl/microduck_velocity_flat_backlash/2026-10-26_14-57-39_pcb_pipeline_baseline')
dest=root/'simulation/validation-runs'/run.name
dest.mkdir(parents=True,exist_ok=True)
checkpoint=torch.load(run/'model_9.pt',map_location='cpu',weights_only=False)
actor=torch.jit.load(str(run/'exported/policy.pt'),map_location='cpu').eval()
with torch.inference_mode(): actions=actor(torch.zeros(1,61))
assert tuple(actions.shape)==(1,14) and torch.isfinite(actions).all()
model=onnx.load(str(run/'exported/policy.onnx'),load_external_data=True)
onnx.checker.check_model(model)
onnx.save_model(model,str(dest/'policy.onnx'),save_as_external_data=False)
onnx.checker.check_model(onnx.load(str(dest/'policy.onnx')))
for name in ['model_9.pt','run.json']:
    shutil.copy2(run/name,dest/name)
shutil.copytree(run/'params',dest/'params',dirs_exist_ok=True)
shutil.copy2(run/'exported/policy.pt',dest/'policy.pt')
log=(root/'audit/pcb-tools/isaac-flat-integration.log').read_text(encoding='utf-8')
nan_values=[float(x) for x in re.findall(r'Episode_Termination/nan_state:\s*([\d.]+)',log)]
assert nan_values and max(nan_values)==0
result={'task':'IsaacContrib-Velocity-Flat-MicroDuck','physics':'newton_mjwarp','preset':'backlash',
 'num_envs':128,'requested_iterations':10,'checkpoint_iteration':checkpoint.get('iter'),
 'checkpoint_keys':list(checkpoint),'seed':42,'run_directory':str(run),
 'training_seconds':102.47,'max_reported_nan_termination':max(nan_values),
 'jit_inference_input':[1,61],'jit_inference_output':list(actions.shape),
 'self_contained_onnx_valid':True,'policy_quality':'integration-only; final success_rate 0.0 and fell_over 1.0',
 'physical_hardware_tested':False,'cad_electronics_variant_equivalence_verified':False,
 'checkpoint_sha256':hashlib.sha256((dest/'model_9.pt').read_bytes()).hexdigest()}
video=run/'videos/play/clip_model_9_0000.mp4'
if video.exists():
    shutil.copy2(video,dest/'playback.mp4')
    reader=imageio.get_reader(str(video))
    count=reader.count_frames();frame=reader.get_data(count//2)
    assert count==150 and float(np.std(frame))>1
    imageio.imwrite(dest/'playback-preview.png',frame)
    result['video']={'frames':count,'width':frame.shape[1],'height':frame.shape[0],'pixel_std':float(np.std(frame))}
    reader.close()
(dest/'validation.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
