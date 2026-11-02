"""Bounded transient checks of unchanged TI single active-high buffer model."""
from pathlib import Path
import json,subprocess,re,hashlib
root=Path(__file__).resolve().parents[1]
model=root/'electrical-models/ti-sn74lvc2g241/SN74LVC2G241.cir'
dest=root/'audit/pcb-tools/ti-buffer-transient';dest.mkdir(parents=True,exist_ok=True)
cases=[('data_pulses','PULSE(0 3.3 100n 1n 1n 500n 1u)','3.3','0',
         [('high',300e-9,'high'),('low',800e-9,'low')]),
       ('enable_release','0','PULSE(0 3.3 1u 1n 1n 1u 4u)','3.3',
         [('disabled_initial',.8e-6,'high'),('enabled_low',1.5e-6,'low'),('released',3.8e-6,'high')])]
results=[]
for name,vin,oe,pull,samples in cases:
    deck=dest/(name+'.cir')
    measures='\n'.join(f'meas tran {label} FIND v(output) AT={time}' for label,time,expected in samples)
    deck.write_text(f'''TI vendor single-channel transient qualification
.include "{model.resolve()}"
Vcc vcc 0 3.3
Vin input 0 {vin}
Voe enable 0 {oe}
Vpull pull 0 {pull}
Xbuffer output input enable vcc 0 SN74LVC2G241
Rload output pull 10k
Cload output 0 30p
.tran 1n 4u
.control
run
{measures}
quit
.endc
.end
''')
    run=subprocess.run(['ngspice','-D','ngbehavior=ps','-b',str(deck)],capture_output=True,text=True,timeout=60)
    (dest/(name+'.log')).write_text(run.stdout+run.stderr)
    assert run.returncode==0,run.stderr
    for label,time,expected in samples:
        match=re.search(r'(?m)^'+label+r'\s*=\s*([-+\deE.]+)',run.stdout);assert match,run.stdout
        voltage=float(match[1]);passed=voltage<.3 if expected=='low' else voltage>3
        results.append({'case':name,'sample':label,'time_s':time,'voltage':voltage,'expected':expected,'passed':passed})
report={'model_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),'scope':'single TI active-high channel, 3.3 V, 30 pF and 10 kohm load, default ngspice temperature; functional pulse and enable/release checks','source':'https://www.ti.com/lit/zip/scem614','physical_pin_mapping_verified':False,'whole_pcb_simulation':False,'hardware_timing_verified':False,'samples':results}
(dest/'results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
assert all(r['passed'] for r in results)
