"""Prefer placed component overrides over reader device-library defaults."""
import argparse,sys,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--reader',type=Path,required=True);a=p.parse_args()
sys.path.insert(0,str(a.reader.resolve()))
import lceda_reader as r
root=Path(__file__).resolve().parents[1]
for folder in (root/'editing/recovered-community').iterdir():
    if not folder.is_dir():continue
    db=r.Epro2DB(str(folder/(folder.name+'.epro2')))
    defaults=json.loads((folder/'components.json').read_text(encoding='utf-8'))
    bom=json.loads((folder/'bom.json').read_text(encoding='utf-8'))
    default_bom={ref.strip():row for row in bom for ref in row['designators'].split(',')}
    attrs={}
    for sheet in db.sheets():
        if sheet[3]!=1:continue
        for c in r.parse_sheet(db,sheet[0])['components']:
            if c.get('designator'):attrs[c['designator']]=c['attrs']
    effective=[]
    for c in defaults:
        ref=c['designator'];v=attrs.get(ref,{});b=default_bom.get(ref,{})
        effective.append({'reference':ref,
          'value':v.get('Value') or None,
          'manufacturer_part':v.get('Manufacturer Part') or c.get('device'),
          'supplier_part':v.get('Supplier Part') or b.get('supplier_part'),
          'device_library_part':c.get('device'),
          'device_library_description':c.get('description'),
          'instance_override':bool(v.get('Manufacturer Part') and v['Manufacturer Part']!=c.get('device')),
          'source':'recovered placed-component attributes with device defaults fallback'})
    (folder/'instance-attributes.json').write_text(json.dumps(attrs,indent=2,ensure_ascii=False),encoding='utf-8')
    (folder/'effective-bom.json').write_text(json.dumps(effective,indent=2,ensure_ascii=False),encoding='utf-8')
    print(folder.name,'components',len(effective),'overrides',sum(x['instance_override'] for x in effective))
