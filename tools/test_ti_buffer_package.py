"""Bounded physical-pin mapped logic tests of an authored TI-model wrapper.

This is a source-port/functional review, not full-package analog qualification
or whole-PCB simulation. VCC is fixed at 3.3 V and enables stay within 0..VCC.
"""
from pathlib import Path
import collections,hashlib,json,re,subprocess

root=Path(__file__).resolve().parents[1]
source=root/'editing/recovered-community/imu_to_dxl_1V0A'
model=root/'electrical-models/ti-sn74lvc2g241/SN74LVC2G241.cir'
wrapper=model.with_name('SN74LVC2G241_DCU_review.lib')
dest=root/'audit/pcb-tools/ti-buffer-package';dest.mkdir(parents=True,exist_ok=True)
model_hash=hashlib.sha256(model.read_bytes()).hexdigest()
assert model_hash=='a6e6bd3e0b2656e797fe4a7bfd5b58cbb474d71f065b94698d4d02de91fb3d63'
pinmap=json.loads((source/'pinmap-0.json').read_text(encoding='utf-8'))
components={c['designator']:c for c in pinmap}
bom={c['reference']:c for c in json.loads((source/'effective-bom.json').read_text(encoding='utf-8'))}
expected={'1':'DE','2':'MCU_TX','3':'MCU_RX','4':'GND','5':'DXL_DATA','6':'DXL_DATA','7':'RX_EN','8':'3.3V'}
actual={str(p['number']):p['net'] for p in components['U3']['pins']}
assert actual==expected,(actual,expected)
assert bom['U3']['manufacturer_part']=='SN74LVC2G241DCUR'
resistors={'R4':{'1':'3.3V','2':'DE'},'R5':{'1':'3.3V','2':'DXL_DATA'},'R7':{'1':'RX_EN','2':'3.3V'},'R6':{'1':'DXL_DATA','2':'DXL_BUS'}}
for ref,pins in resistors.items():
    assert {str(p['number']):p['net'] for p in components[ref]['pins']}==pins,ref
    value=bom[ref]['value'].replace('\u03a9','').replace(' ','').lower()
    assert value==('0r' if ref=='R6' else '10k'),(ref,value)

# Independently verify the saved native physical pad numbers/nets, not just the
# generic recovered symbol. No geometry or board file is changed.
import pcbnew as k
board_path=root/'editing/kicad-paired/imu_to_dxl_1V0A/imu_to_dxl_1V0A.kicad_pcb'
board=k.LoadBoard(str(board_path));assert board
footprint=next(fp for fp in board.GetFootprints() if fp.GetReference()=='U3')
native={p.GetNumber():p.GetNetname().removeprefix('/') for p in footprint.Pads()}
assert native==expected,(native,expected)

nodes={'DE':'de','MCU_TX':'mcu_tx','MCU_RX':'mcu_rx','GND':'0','DXL_DATA':'dxl_data','RX_EN':'rx_en','3.3V':'vcc'}
ports=' '.join(nodes[expected[str(i)]] for i in range(1,9))
# Voltage sources stand in for MCU outputs/external bus data. They are mocks,
# not a CPU timing model. None oppose an enabled transmitter in these tests.
cases=[
 {'name':'tx_low','de':0,'rx':0,'tx':0,'checks':{'dxl_data':'low','dxl_bus':'low'}},
 {'name':'tx_high','de':0,'rx':0,'tx':3.3,'bus_down':10000,'checks':{'dxl_data':'high','dxl_bus':'high'}},
 {'name':'tx_disabled_pullup','de':3.3,'rx':0,'tx':0,'checks':{'dxl_data':'high'}},
 {'name':'tx_disabled_pulldown','de':3.3,'rx':0,'tx':3.3,'bus_down':100,'checks':{'dxl_data':'low'}},
 {'name':'rx_low','de':3.3,'rx':3.3,'tx':3.3,'external':0,'cpu_pull':'vcc','checks':{'mcu_rx':'low'}},
 {'name':'rx_high','de':3.3,'rx':3.3,'tx':0,'external':3.3,'cpu_pull':'0','checks':{'mcu_rx':'high'}},
 {'name':'rx_disabled_pullup','de':3.3,'rx':0,'tx':0,'external':0,'cpu_pull':'vcc','checks':{'mcu_rx':'high'}},
 {'name':'rx_disabled_pulldown','de':3.3,'rx':0,'tx':0,'external':3.3,'cpu_pull':'0','checks':{'mcu_rx':'low'}},
 {'name':'both_disabled','de':3.3,'rx':0,'tx':0,'bus_down':100,'cpu_pull':'vcc','checks':{'dxl_data':'low','mcu_rx':'high'}},
 {'name':'reset_bias_txoff_rxon','de':None,'rx':None,'tx':0,'cpu_pull':'0','checks':{'de':'high','rx_en':'high','dxl_data':'high','mcu_rx':'high'}},
 {'name':'tx_rx_loop_low','de':0,'rx':3.3,'tx':0,'cpu_pull':'vcc','checks':{'dxl_data':'low','dxl_bus':'low','mcu_rx':'low'}},
 {'name':'tx_rx_loop_high','de':0,'rx':3.3,'tx':3.3,'cpu_pull':'0','checks':{'dxl_data':'high','dxl_bus':'high','mcu_rx':'high'}},
]
results=[]
for case in cases:
    for enable in ['de','rx']:
        assert case[enable] is None or 0<=case[enable]<=3.3
    elements=[f'Vcpu_tx mcu_tx 0 {case["tx"]}']
    if case['de'] is not None:elements.append(f'Vcpu_de de 0 {case["de"]}')
    if case['rx'] is not None:elements.append(f'Vcpu_rx_en rx_en 0 {case["rx"]}')
    if 'external' in case:elements.append(f'Vexternal dxl_bus 0 {case["external"]}')
    if 'bus_down' in case:elements.append(f'Rbus_test_load dxl_bus 0 {case["bus_down"]}')
    if 'cpu_pull' in case:elements.append(f'Rcpu_test_load mcu_rx {case["cpu_pull"]} 10k')
    else:elements.append('Rcpu_test_load mcu_rx 0 10k')
    deck=dest/(case['name']+'.cir')
    deck.write_text(f'''Authored fixed-supply package functional test: {case['name']}
.include "{model.resolve()}"
.include "{wrapper.resolve()}"
Vcc vcc 0 3.3
* Recovered physical U3 pin order 1..8. Pins 5/6 share DXL_DATA.
XU3 {ports} SN74LVC2G241_DCU_REVIEW
R4 vcc de 10k
R5 vcc dxl_data 10k
R7 rx_en vcc 10k
* Placed R6=0R modeled as a zero-volt link/current probe; boundary retained.
VR6 dxl_data dxl_bus 0
{chr(10).join(elements)}
.op
.control
run
print v(dxl_data) v(dxl_bus) v(mcu_rx) v(de) v(rx_en)
quit
.endc
.end
''')
    run=subprocess.run(['ngspice','-D','ngbehavior=ps','-b',str(deck)],capture_output=True,text=True,timeout=45)
    (dest/(case['name']+'.log')).write_text(run.stdout+run.stderr)
    assert run.returncode==0,(case['name'],run.stdout,run.stderr)
    values={node:float(value) for node,value in re.findall(r'v\(([^)]+)\)\s*=\s*([-+\deE.]+)',run.stdout)}
    checks=[]
    for node,level in case['checks'].items():
        assert node in values,(case['name'],node,run.stdout)
        voltage=values[node];passed=voltage<.3 if level=='low' else voltage>3
        checks.append({'node':node,'expected':level,'voltage':voltage,'passed':passed})
    results.append({'case':case['name'],'checks':checks,'passed':all(c['passed'] for c in checks)})
report={
 'vendor_model_sha256':model_hash,'wrapper_sha256':hashlib.sha256(wrapper.read_bytes()).hexdigest(),
 'datasheet':'https://www.ti.com/lit/ds/symlink/sn74lvc2g241.pdf',
 'scope':'authored eight-port logical review wrapper using two unchanged vendor active-high stages and ideal algebraic TX-enable inversion; fixed 3.3 V, enables within 0..VCC; DC logic/high-Z functional tests with fixed-voltage CPU/bus mocks',
 'source_u3_pinmap_checked':actual,'native_u3_pad_nets_checked':native,
 'resistor_pinmaps_checked':resistors,'placed_r6_value':'0R; ideal zero-volt link keeps DXL_DATA/DXL_BUS boundary',
 'physical_pin_assignment_reviewed':True,'source_to_wrapper_port_mapping_tested':True,
 'ideal_tx_enable_inversion':True,'chip_enable_timing_verified':False,
 'physical_input_capacitance_verified':False,'package_supply_current_verified':False,
 'power_off_verified':False,'backdrive_verified':False,'whole_pcb_simulation':False,
 'physical_hardware_tested':False,'manufacturing_ready':False,
 'limitations':['No eight-pin TI-qualified analog model is claimed.','Ideal inverter isolates physical DE input from vendor enable capacitance/impedance; no physical inversion delay.','VCC-DE becomes negative for DE>VCC; power-off/back-drive/overvoltage cases are outside this wrapper scope.','Two channel power models do not qualify shared package ICC.','Test pull loads are fixture values, not measured MCU/harness parasitics.'],
 'cases':results,'checks_passed':sum(c['passed'] for r in results for c in r['checks']),
 'checks_total':sum(len(r['checks']) for r in results),'all_passed':all(r['passed'] for r in results)}
(dest/'results.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'cases':len(results),'checks_passed':report['checks_passed'],'checks_total':report['checks_total'],'all_passed':report['all_passed'],'whole_pcb_simulation':False},indent=2))
assert report['all_passed']
