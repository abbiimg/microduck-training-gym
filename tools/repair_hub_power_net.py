"""Create an explicit engineering copy correcting the hub BATTERY/Battery split."""
from pathlib import Path
import json,hashlib,subprocess
import pcbnew as k
root=Path(__file__).resolve().parents[1];name='wire_hub_1V0A'
source=root/'editing/kicad-routed'/name/(name+'.kicad_pcb')
dest=root/'editing/kicad-engineering'/name;dest.mkdir(parents=True,exist_ok=True)
b=k.LoadBoard(str(source));net=b.FindNet('Battery');assert net and net.GetNetname()=='Battery'
changed=[]
for zone in b.Zones():
    if zone.GetZoneName()=='Recovered a33f62a491f76b4a':
        assert zone.GetNetname()=='BATTERY'
        zone.SetNet(net);changed.append(zone.m_Uuid.AsString())
assert len(changed)==1,changed
output=dest/(name+'.kicad_pcb');k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(output),b)
audit=json.loads(source.with_name('conversion-audit.json').read_text())
audit['engineering_changes']=[{'source_primitive':'a33f62a491f76b4a','from_net':'BATTERY','to_net':'Battery','rationale':'case mismatch with all battery pads, tracks and recovered schematic; explicit engineering repair, not literal source recovery','native_uuids':changed}]
audit['unmodified_parent_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
(dest/'conversion-audit.json').write_text(json.dumps(audit,indent=2))
run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--format','json','--output',str(dest/'drc.json'),str(output)],capture_output=True,text=True,timeout=90)
assert run.returncode==0,run.stderr
report=json.loads((dest/'drc.json').read_text())
print(json.dumps({'candidate':name,'changed_zones':len(changed),'unconnected':len(report['unconnected_items']),'violations':len(report['violations']),'manufacturing_ready':False}))
