"""Prepare strict replay inputs from locally recovered community archives.

Requires separately acquired alwaysmy/lceda-sch-reader pinned below. Never
changes vendor source projects. No EasyEDA client, account or activation needed.
"""
from pathlib import Path
import argparse,sys,json,zipfile,hashlib,subprocess
p=argparse.ArgumentParser();p.add_argument('--reader',type=Path,required=True);a=p.parse_args()
pin='da5b4d46565ced7ef63fd710229959d853fc70ab'
assert subprocess.check_output(['git','-C',str(a.reader),'rev-parse','HEAD'],text=True).strip()==pin,'Reader revision differs; review before replay'
sys.path.insert(0,str(a.reader.resolve()))
import lceda_pcb
root=Path(__file__).resolve().parents[1]
for folder in sorted((root/'editing/recovered-community').iterdir()):
    if not folder.is_dir():continue
    archive=folder/(folder.name+'.epro2')
    with zipfile.ZipFile(archive) as z:
        names=[n for n in z.namelist() if n.endswith('.epru')];assert len(names)==1
        lines=z.read(names[0]).decode('utf-8-sig').splitlines()
    kept=[];omitted=0
    for line in lines:
        if not line.strip():continue
        header=json.loads(line.partition('||')[0])
        if header['type']=='EDIT_HEAD':omitted+=1;continue
        kept.append(line)
    path=folder/'geometry-input.epru';path.write_text('\n'.join(kept)+'\n',encoding='utf-8')
    project=lceda_pcb.load_project(path)
    active=[d for d in project['documents'].values() if not d['deleted']]
    assert len([d for d in active if d['head']['docType']=='PCB'])==1
    clean={'source':project['source'],'documents':[{'head':d['head'],'records':d['records']} for d in active]}
    (folder/'replayed-project.json').write_text(json.dumps(clean,ensure_ascii=False),encoding='utf-8')
    audit={'reader_commit':pin,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'removed_edit_head_envelopes':omitted,'retained_lines':len(kept),'deleted_documents_excluded':len(project['documents'])-len(active),'strict_replay_source':project['source'],'activation_used':False}
    (folder/'replay-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(folder.name,omitted,'EDIT_HEAD records omitted; active document count',len(active))
