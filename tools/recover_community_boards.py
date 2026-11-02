"""Recover local design data via a pinned, separately acquired reader.
Reader code is not bundled: no explicit redistribution license was found.
"""
import argparse, contextlib, hashlib, importlib, io, json, shutil, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--reader',type=Path,required=True)
p.add_argument('--assets',type=Path,default=Path(__file__).resolve().parents[1])
a=p.parse_args()
sys.path.insert(0,str(a.reader.resolve()))
r=importlib.import_module('lceda_reader')
out=a.assets/'editing/recovered-community'
out.mkdir(exist_ok=True)
summary=[]
for source in sorted((a.assets/'community/microduck-replica/hardware').rglob('*.eprj2')):
    target=out/source.stem
    target.mkdir(exist_ok=True)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    # Reader opens SQLite read-only; retain its recovered archive outside its
    # automatically deleted temporary directory. No editor process is involved.
    recovered=r._decrypt_new_eprj2(str(source))
    archive=target/(source.stem+'.epro2')
    shutil.copy2(recovered,archive)
    common=[sys.executable,str(a.reader/'lceda_reader.py'),'--eprj',str(archive),'--json']
    for command in ['list','components','netlist','bom','pcbsch','docs']:
        run=subprocess.run(common+[command],capture_output=True,text=True)
        (target/(command+'.stderr.txt')).write_text(run.stderr,encoding='utf-8')
        if run.returncode: raise RuntimeError(command+': '+run.stderr+run.stdout)
        data=json.loads(run.stdout)
        (target/(command+'.json')).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    db=r.Epro2DB(str(archive))
    sheets=[s for s in db.sheets() if s[3]==1]
    for index,sheet in enumerate(sheets):
        run=subprocess.run(common+['pinmap',sheet[1]],capture_output=True,text=True)
        if run.returncode: raise RuntimeError(run.stderr+run.stdout)
        (target/f'pinmap-{index}.json').write_text(json.dumps(json.loads(run.stdout),indent=2,ensure_ascii=False),encoding='utf-8')
    pcb=[]
    for uuid,title in db.pcb_docs():
        records=db._docs[uuid]
        # Preserve raw reader backend records for subsequent documented import.
        (target/(uuid+'-pcb-records.json')).write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
        pcb.append({'uuid':uuid,'title':title})
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    comps=json.loads((target/'components.json').read_text())
    item={'source':str(source.relative_to(a.assets)),'source_sha256':before,
          'archive':str(archive.relative_to(a.assets)), 'schematic_component_count':len(comps),
          'schematic_sheets':len(sheets),'pcbs':pcb,'source_unchanged':True,
          'native_kicad_verified':False}
    summary.append(item)
(out/'recovery-summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps(summary,indent=2,ensure_ascii=False))
