import json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
project=root/'editing/kicad-recovered/imu_to_dxl_1V0A'
bom=json.loads((root/'editing/recovered-community/imu_to_dxl_1V0A/effective-bom.json').read_text(encoding='utf-8'))
ids=sorted({r['supplier_part'] for r in bom if r['supplier_part']} - {'C10430','C529334','C5267406'})
tool='/home/workbench/robotics/pcb-tools/venv/bin/easyeda2kicad'
with (root/'audit/pcb-tools/imu-part-import.log').open('w') as log:
    result=subprocess.run([tool,'--full','--lcsc_id',*ids,'--use-cache','--project-relative',
                           '--output',str(project/'libs/lcsc')],cwd=project,stdout=log,stderr=subprocess.STDOUT)
print('import exit',result.returncode,'requested',len(ids),'additional part IDs')
raise SystemExit(result.returncode)
