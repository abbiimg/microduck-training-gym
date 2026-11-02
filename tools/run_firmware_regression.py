"""Compile actual firmware host tests and run them without physical hardware."""
from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parents[1]
fw=root/'community/microduck-replica/hardware/imu_to_dxl/firmware'
out=Path('/home/workbench/robotics/pcb-tools/firmware-regression')
out.mkdir(exist_ok=True)
cases={
 'protocol':(['Tests/protocol_test.c','Core/Src/protocol.c'],['Core/Inc']),
 'imu':(['Tests/imu_test.c','Core/Src/imu.c','Drivers/LSM6DSV16X/lsm6dsv16x_reg.c'],['Tests/imu_board','Core/Inc','Drivers/LSM6DSV16X']),
 'control_table':(['Tests/control_table_test.c','Core/Src/control_table.c'],['Core/Inc'])}
results=[]
for name,(sources,includes) in cases.items():
    exe=out/name
    cmd=['gcc','-std=c11','-D__weak=',*[str(fw/s) for s in sources],
         *[x for inc in includes for x in ['-I',str(fw/inc)]],'-o',str(exe)]
    subprocess.run(cmd,check=True,capture_output=True,text=True)
    run=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
    results.append({'suite':name,'output':run.stdout.strip(),'passed':True})
target=root/'audit/pcb-tools/firmware-regression.json'
target.write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
