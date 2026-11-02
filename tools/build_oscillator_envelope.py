from pathlib import Path
import hashlib,json
import cadquery as cq
root=Path('outputs/microduck-assets').resolve()
out=root/'reconstructed/oscillator'
out.mkdir(parents=True,exist_ok=True)
variants={'ASDMB_nominal_package':(2.5,2.0,0.85),'ASDMB_datasheet_max_envelope':(2.55,2.05,0.90)}
records=[]
for name,dims in variants.items():
    shape=cq.Workplane('XY').box(*dims,centered=(True,True,False)).val()
    path=out/(name+'.step'); cq.exporters.export(shape,str(path))
    check=cq.importers.importStep(str(path)).val(); box=check.BoundingBox()
    assert check.isValid() and len(check.Solids())==1
    measured=[box.xlen,box.ylen,box.zlen]
    assert all(abs(a-b)<1e-6 for a,b in zip(dims,measured))
    records.append({'name':name,'dimensions_mm':measured,'valid_solid':True,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
pcb=root/'editing/kicad/Robot_HAT_reference/elec_RPI_Robot_HAT.kicad_pcb'
text=pcb.read_text(encoding='utf-8')
old='${KICAD10_3DMODEL_DIR}/Oscillator.3dshapes/Oscillator_SMD_Abracon_ASDMB-4Pin_2.5x2.0mm.step'
new='${KIPRJMOD}/models/ASDMB_datasheet_max_envelope.step'
if old in text:
    assert text.count(old)==1
    backup=root/'audit/Robot_HAT-before-oscillator-proxy.kicad_pcb'
    if not backup.exists(): backup.write_text(text,encoding='utf-8')
    after=text.replace(old,new)
    assert after.replace(new,old)==text
    pcb.write_text(after,encoding='utf-8')
import shutil
(pcb.parent/'models').mkdir(exist_ok=True)
shutil.copy2(out/'ASDMB_datasheet_max_envelope.step',pcb.parent/'models/ASDMB_datasheet_max_envelope.step')
metadata={'source':'https://abracon.com/Oscillators/ASDMB.pdf','revision':'I, initial release 2025-01-08','source_page':7,
          'type':'Datasheet-derived mechanical package/envelope; not original manufacturer detail CAD',
          'construction':'Boxes centered at footprint XY, seating plane Z=0. No undocumented pad thickness, chamfer, or internal structure invented.',
          'dimensions':records,'pcb_change':'Only the one missing 3D-model path was replaced. Copper, pads, nets, outline and footprints unchanged.',
          'limitations':['No solder standoff or assembly tolerance included','Actual selected component and hardware revision still require confirmation','Envelope does not establish electrical compatibility']}
(out/'provenance.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
print(json.dumps(metadata,indent=2))
