"""Validate recovered physical pin numbers against imported KiCad pads."""
from pathlib import Path
import json
import pcbnew
root=Path(__file__).resolve().parents[1]
project=root/'editing/kicad-recovered/imu_to_dxl_1V0A'
bom=json.loads((root/'editing/recovered-community/imu_to_dxl_1V0A/effective-bom.json').read_text(encoding='utf-8'))
pinmap={c['designator']:c for c in json.loads((root/'editing/recovered-community/imu_to_dxl_1V0A/pinmap-0.json').read_text(encoding='utf-8'))}
catalog=[]
for row in bom:
    part=row['supplier_part']; data=json.loads((project/'.easyeda_cache'/(part+'.json')).read_text(encoding='utf-8'))['result']
    name=data['packageDetail']['title']
    library='C19702' if part=='C19702' else 'lcsc'
    path=project/'libs'/(library+'.pretty')/(name+'.kicad_mod')
    assert path.exists(),(part,path)
    fp=pcbnew.FootprintLoad(str(path.parent),name)
    pads=sorted({p.GetNumber() for p in fp.Pads() if p.GetNumber()})
    pins=sorted({str(p['number']) for p in pinmap[row['reference']]['pins']})
    missing=sorted(set(pins)-set(pads))
    models=[]
    for model in fp.Models():
        resolved=Path(model.m_Filename.replace('${KIPRJMOD}',str(project)))
        models.append({'path':model.m_Filename,'exists':resolved.exists()})
    catalog.append({**row,'footprint':library+':'+name,'pad_numbers':pads,'recovered_pin_numbers':pins,
                    'missing_pad_numbers':missing,'models':models,
                    'datasheet_dimensions_verified':False,'electrical_model_qualified':False})
    assert not missing,(part,missing)
(project/'parts-catalog.json').write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf-8')
(project/'sym-lib-table').write_text('(sym_lib_table (lib (name "lcsc") (type "KiCad") (uri "${KIPRJMOD}/libs/lcsc.kicad_sym") (options "") (descr "Imported candidates")) (lib (name "C19702") (type "KiCad") (uri "${KIPRJMOD}/libs/C19702.kicad_sym") (options "") (descr "Separate capacitor model")))')
(project/'fp-lib-table').write_text('(fp_lib_table (lib (name "lcsc") (type "KiCad") (uri "${KIPRJMOD}/libs/lcsc.pretty") (options "") (descr "Imported candidates")) (lib (name "C19702") (type "KiCad") (uri "${KIPRJMOD}/libs/C19702.pretty") (options "") (descr "Separate capacitor model")))')
print('Cataloged',len(catalog),'components /',len({x['supplier_part'] for x in catalog}),'part IDs; all recovered pin numbers have pads.')
