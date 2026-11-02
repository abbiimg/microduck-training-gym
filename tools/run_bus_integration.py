"""Run upstream bus acceptance on Linux without changing its source or assertions."""
import argparse
from pathlib import Path
import runpy
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--assets', type=Path, default=Path(__file__).resolve().parents[1])
parser.add_argument('--build-dir', type=Path, required=True)
args = parser.parse_args()
firmware = args.assets/'community/microduck-replica/hardware/imu_to_dxl/firmware'
args.build_dir.mkdir(parents=True, exist_ok=True)
library = args.build_dir.resolve()/'bus_sim_shim.so'
sources = [firmware/s for s in ['Tests/bus_sim_shim.c', 'Core/Src/protocol.c', 'Core/Src/control_table.c']]
subprocess.run(['gcc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
                '-I',str(firmware/'Core/Inc'),*[str(s) for s in sources],'-o',str(library)],check=True)
namespace = runpy.run_path(str(firmware/'Tests/bus_sim_test.py'))
# The only replaced function is the Windows/MSVC build step. All test behavior
# and production controller/firmware sources remain those of the pinned repo.
namespace['main'].__globals__['build_dll'] = lambda: str(library)
raise SystemExit(namespace['main']())
