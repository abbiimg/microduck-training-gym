import json
import subprocess
from pathlib import Path
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import u_V, u_kOhm

root = Path('/home/workbench/robotics/pcb-tools')
result = {}
circuit = Circuit('PCB tools divider smoke')
circuit.V('supply', 'vin', circuit.gnd, 5 @ u_V)
circuit.R('top', 'vin', 'mid', 1 @ u_kOhm)
circuit.R('bottom', 'mid', circuit.gnd, 1 @ u_kOhm)
op = circuit.simulator(temperature=25, nominal_temperature=25).operating_point()
voltage = float(op.nodes['mid'][0])
assert abs(voltage - 2.5) < 1e-6, voltage
result['pyspice_divider_voltage'] = voltage
for name, command in {
    'kibot': [str(root/'venv/bin/kibot'), '--version'],
    'kicad': ['kicad-cli', 'version'],
    'ngspice': ['ngspice', '--version'],
    'ruby': ['ruby', '--version'],
}.items():
    run = subprocess.run(command, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result[name] = run.stdout.strip()
import pytest_embedded, pytest_embedded_serial, pytest_embedded_jtag
result['pytest_embedded_imports'] = True
print(json.dumps(result, indent=2))
(root/'smoke-results.json').write_text(json.dumps(result, indent=2))
