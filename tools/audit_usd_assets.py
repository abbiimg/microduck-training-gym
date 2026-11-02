from pathlib import Path
import json, sys
from pxr import Usd, UsdUtils, Sdf, UsdGeom, UsdPhysics
root=Path(sys.argv[1]).resolve()
results=[]
for path in sorted((root/'simulation/isaaclab').glob('*.usd')):
    layers,assets,unresolved=UsdUtils.ComputeAllDependencies(Sdf.AssetPath(str(path)))
    stage=Usd.Stage.Open(str(path))
    record={'file':str(path.relative_to(root)),'opened':bool(stage),'meters_per_unit':UsdGeom.GetStageMetersPerUnit(stage),
            'up_axis':str(UsdGeom.GetStageUpAxis(stage)),'layers':len(layers),'asset_dependencies':[str(a) for a in assets],
            'unresolved_dependencies':[str(a) for a in unresolved],
            'mesh_prims':sum(1 for p in stage.Traverse() if p.IsA(UsdGeom.Mesh)),
            'physics_joint_prims':sum(1 for p in stage.Traverse() if p.IsA(UsdPhysics.Joint))}
    results.append(record)
(root/'audit/usd-dependencies.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
