"""Inventory netlist components without inventing electrical-model coverage."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
tree = ET.parse(root/'audit/Robot_HAT-netlist.xml')
connections = {}
for net in tree.findall('./nets/net'):
    for node in net.findall('node'):
        connections.setdefault(node.get('ref'), []).append({
            'pin': node.get('pin'), 'net': net.get('name'),
            'pin_function': node.get('pinfunction'), 'pin_type': node.get('pintype')})
components = []
for c in tree.findall('./components/comp'):
    components.append({
        'reference': c.get('ref'), 'value': c.findtext('value'),
        'footprint': c.findtext('footprint'),
        'fields': {f.get('name'): f.text for f in c.findall('./fields/field')},
        'pins': connections.get(c.get('ref'), []),
        'electrical_model': None,
        'model_pin_mapping_verified': False,
        'electrical_acceptance': 'unverified',
        'note': 'ERC/DRC and Gerber export do not establish component behavior.'})
result = {
    'candidate': 'official-Robot-HAT-reference',
    'source': 'audit/Robot_HAT-netlist.xml',
    'component_count': len(components),
    'model_covered_components': 0,
    'components': components,
    'candidates': [
        {'id': 'official-Robot-HAT-reference', 'native_kicad': True,
         'fabrication_ready': False, 'electrical_simulation_complete': False},
        {'id': 'community-Feetech-IMU', 'native_kicad': False,
         'host_firmware_checks': {'protocol': 104, 'imu_scenarios': 16, 'control_table': 32, 'bus_integration': 24},
         'host_checks_passed': True, 'cpu_execution_emulated': False,
         'physical_electrical_validation': False,
         'xl330_protocol_compatibility': 'not established; firmware implements Feetech SCS'},
        {'id': 'community-XL330-native-CAD', 'mechanical_assembly_resolved': True,
         'matching_full_electronics_and_firmware': 'unverified'}]}
target=root/'audit/pcb-tools/component-coverage.json'
target.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(f'{len(components)} netlist components inventoried; 0 electrical models qualified.')
