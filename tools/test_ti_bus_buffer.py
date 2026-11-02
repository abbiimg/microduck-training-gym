"""DC smoke tests of TI's unchanged single-channel SN74LVC2G241 model.

This is model qualification groundwork, not physical package or PCB validation.
"""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--model',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=True)
results=[]
for name,vin,oe,pull,expected in [
    ('enabled_low',0,3.3,3.3,'low'),('enabled_high',3.3,3.3,0,'high'),
    ('disabled_low_input_pullup',0,0,3.3,'high'),
    ('disabled_high_input_pulldown',3.3,0,0,'low')]:
    deck=a.output/(name+'.cir')
    deck.write_text(f'''TI buffer DC model test
.include "{a.model.resolve()}"
Vcc vcc 0 3.3
Vin input 0 {vin}
Voe enable 0 {oe}
Vpull pull 0 {pull}
Xbuffer output input enable vcc 0 SN74LVC2G241
Rload output pull 10k
.op
.control
run
print v(output)
quit
.endc
.end
''')
    run=subprocess.run(['ngspice','-D','ngbehavior=ps','-b',str(deck)],capture_output=True,text=True)
    (a.output/(name+'.log')).write_text(run.stdout+run.stderr)
    match=re.search(r'v\(output\)\s*=\s*([-+\deE.]+)',run.stdout)
    if run.returncode or not match:
        raise RuntimeError(run.stdout+run.stderr)
    voltage=float(match[1])
    passed=voltage<0.3 if expected=='low' else voltage>3.0
    results.append(dict(case=name,voltage=voltage,expected=expected,passed=passed))
report={'source':'https://www.ti.com/lit/zip/scem614',
        'model_sha256':hashlib.sha256(a.model.read_bytes()).hexdigest(),
        'scope':'single modeled active-high channel (2OE), 3.3V, DC, 10kohm load; ngspice default 27C',
        'physical_pin_mapping_verified':False,'pcb_connected_model':False,
        'cases':results}
(a.output/'results.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert all(r['passed'] for r in results)
