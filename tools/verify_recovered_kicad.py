from pathlib import Path
import json,subprocess,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
cli='C:/Program Files/KiCad/10.0/bin/kicad-cli.exe'
report=[]
for project in sorted((root/'editing/kicad-recovered').iterdir()):
    if not project.is_dir():continue
    sch=project/(project.name+'.kicad_sch'); net=project/'kicad-netlist.xml'
    subprocess.run([cli,'sch','export','netlist','--format','kicadxml','-o',str(net),str(sch)],check=True)
    tree=ET.parse(net)
    actual={}
    for n in tree.findall('./nets/net'):
        for pin in n.findall('node'): actual[(pin.get('ref'),pin.get('pin'))]=n.get('name')
    expected=json.loads((project/'expected-pin-nets.json').read_text())
    errors=[];checked=0;unnamed=[]
    for ref,pp in expected.items():
        for number,name in pp.items():
            if name:
                checked+=1
                if actual.get((ref,number)) not in [name,'/'+name]:errors.append([ref,number,name,actual.get((ref,number))])
            else:unnamed.append([ref,number])
    assert len(tree.findall('./components/comp'))==len(expected)
    attrs=json.loads((root/'editing/recovered-community'/project.name/'instance-attributes.json').read_text(encoding='utf-8'))
    catalog={r['reference']:r for r in json.loads((project/'parts-catalog.json').read_text(encoding='utf-8'))} if (project/'parts-catalog.json').exists() else {}
    field_errors=[]
    for c in tree.findall('./components/comp'):
        ref=c.get('ref');value=attrs.get(ref,{}).get('Value')
        if value and c.findtext('value')!=value:field_errors.append([ref,'Value',value,c.findtext('value')])
        if ref in catalog and c.findtext('footprint')!=catalog[ref]['footprint']:field_errors.append([ref,'Footprint'])
    subprocess.run([cli,'sch','export','svg','-o',str(project/'preview'),str(sch)],check=True,capture_output=True)
    item={'project':project.name,'component_count':len(expected),'named_pins_checked':checked,
          'unnamed_source_pins':unnamed,'pin_net_mismatches':errors,
          'field_mismatches':field_errors,'kicad_cli_load_and_export':True,'electrical_review_only':True}
    report.append(item)
    assert not errors,errors[:5]
    assert not field_errors,field_errors[:5]
(root/'audit/pcb-tools/kicad-reconstruction-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
