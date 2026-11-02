"""Create separate paired KiCad editing projects with recovered local libraries.

Does not overwrite recovered boards/schematics. Run under the PCB WSL Python.
"""
from pathlib import Path
import re,json,copy,subprocess,xml.etree.ElementTree as ET,hashlib
import pcbnew as k
class Atom(str):pass
def parse(text):
    tokens=re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text);stack=[];root=None
    for token in tokens:
        if token=='(':
            row=[]
            if stack:stack[-1].append(row)
            else:assert root is None;root=row
            stack.append(row)
        elif token==')':stack.pop()
        else:stack[-1].append(json.loads(token) if token.startswith('"') else Atom(token))
    assert not stack
    return root
def dump(value):
    if isinstance(value,list):return '('+' '.join(dump(v) for v in value)+')'
    return str(value) if isinstance(value,Atom) else json.dumps(value,ensure_ascii=False)
def rows(node,key):return [r for r in node if isinstance(r,list) and r and r[0]==key]
def one(node,key):return next(iter(rows(node,key)),None)
root=Path(__file__).resolve().parents[1]
summaries=[]
for original in sorted((root/'editing/kicad-routed').glob('*/*.kicad_pcb')):
    name=original.stem
    source=root/'editing/kicad-engineering'/name/original.name if name=='wire_hub_1V0A' else original
    dest=root/'editing/kicad-paired'/name;dest.mkdir(parents=True,exist_ok=True)
    library=dest/'RecoveredLayout.pretty';library.mkdir(exist_ok=True)
    schsource=root/'editing/kicad-recovered'/name/(name+'.kicad_sch')
    ast=parse(schsource.read_text(encoding='utf-8'));sheet=one(ast,'uuid')[1]
    symbols={one(s,'property')[2]:s for s in rows(ast,'symbol')}
    board=k.LoadBoard(str(source));refs={fp.GetReference():fp for fp in board.GetFootprints()}
    audit={'candidate':name,'parent_board':str(source.relative_to(root)),'parent_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'parent_schematic_sha256':hashlib.sha256(schsource.read_bytes()).hexdigest(),'paired':[],'excluded_offboard_symbols':[],'board_only_footprints':[],'net_changes':[],'manufacturing_ready':False,'source_history_interpretation':'literal typed replay; hub uses explicit engineering net repair'}
    for ref,symbol in symbols.items():
        prop=next(iter([p for p in rows(symbol,'property') if p[1]=='Footprint']),None)
        if ref not in refs:
            assert name=='POGO_PIN_1V0A' and ref=='CN2',(name,ref)
            one(symbol,'on_board')[1]=Atom('no')
            audit['excluded_offboard_symbols'].append({'reference':ref,'reason':'source component is outside active PCB perimeter; kept in schematic, explicitly excluded from board'})
            continue
        ident='RecoveredLayout:'+ref
        if prop:prop[2]=ident
        else:symbol.append([Atom('property'),'Footprint',ident,[Atom('at'),*one(symbol,'at')[1:]],[Atom('effects'),[Atom('font'),[Atom('size'),Atom('1'),Atom('1')]],[Atom('hide'),Atom('yes')]]])
        fp=refs[ref];path='/'+sheet+'/'+one(symbol,'uuid')[1]
        fp.SetValue(next(p[2] for p in rows(symbol,'property') if p[1]=='Value'))
        for prop in rows(symbol,'property'):
            if prop[1] in ['Reference','Value','Footprint']:continue
            field=fp.GetField(prop[1])
            if field is None:
                field=k.PCB_FIELD(fp,k.FIELD_T_USER,prop[1]);fp.Add(field)
            field.SetText(prop[2]);field.SetVisible(False)
        fp.SetPath(k.KIID_PATH(path));fp.SetFPID(k.LIB_ID('RecoveredLayout',ref))
        audit['paired'].append({'reference':ref,'path':path,'footprint':ident})
        libfp=k.FOOTPRINT(fp);libfp.SetPosition(k.VECTOR2I(0,0));libfp.SetPath(k.KIID_PATH());libfp.SetReference('REF**')
        for pad in libfp.Pads():pad.SetNetCode(0)
        plugin=k.PCB_IO_MGR.FindPlugin(k.PCB_IO_MGR.KICAD_SEXP)
        plugin.FootprintSave(str(library),libfp)
    for ref,fp in refs.items():
        if ref not in symbols:
            assert ref=='SOURCE_BOARD_PADS'
            fp.SetAttributes(fp.GetAttributes()|k.FP_BOARD_ONLY|k.FP_EXCLUDE_FROM_BOM|k.FP_EXCLUDE_FROM_POS_FILES)
            audit['board_only_footprints'].append(ref)
    lib=copy.deepcopy(one(ast,'lib_symbols'));lib[0]=Atom('kicad_symbol_lib');lib[1:1]=[[Atom('version'),Atom('20250114')],[Atom('generator'),'recovered_pairing']]
    for sym in rows(lib,'symbol'):sym[1]=sym[1].split(':',1)[-1]
    (dest/'Recovered.kicad_sym').write_text(dump(lib)+'\n',encoding='utf-8')
    (dest/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "Recovered") (type "KiCad") (uri "${KIPRJMOD}/Recovered.kicad_sym") (options "") (descr "Recovered generic review symbols")))\n')
    (dest/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "RecoveredLayout") (type "KiCad") (uri "${KIPRJMOD}/RecoveredLayout.pretty") (options "") (descr "Recovered source pad geometry, per-instance footprints")))\n')
    schematic=dest/(name+'.kicad_sch');schematic.write_text(dump(ast)+'\n',encoding='utf-8')
    (dest/(name+'.kicad_pro')).write_text(json.dumps({'meta':{'filename':name+'.kicad_pro','version':1}},indent=2))
    netlist=dest/'paired-netlist.xml'
    subprocess.run(['/usr/bin/kicad-cli','sch','export','netlist','--format','kicadxml','--output',str(netlist),str(schematic)],check=True,capture_output=True,text=True,timeout=60)
    xml=ET.parse(netlist);nets={}
    for n in xml.findall('./nets/net'):
        for p in n.findall('node'):
            net=n.get('name')
            # XML unescapes slashes inside pin names; KiCad's internal netlist
            # uses {slash} there. Hierarchical separators remain literal '/'.
            if net.startswith('unconnected-('):net=net.replace('/','{slash}')
            nets[p.get('ref'),p.get('pin')]=net
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            desired=nets.get((fp.GetReference(),pad.GetNumber()))
            if desired and desired!=pad.GetNetname():
                old=pad.GetNetname()
                if desired.startswith('unconnected-(') and not old:
                    target=k.NETINFO_ITEM(board,desired);board.Add(target);pad.SetNet(target)
                    reason='KiCad singleton name for an electrically unconnected schematic pin; not a source no-connect declaration; no physical connection added'
                else:
                    assert old.removeprefix('/')==desired.removeprefix('/') or (name=='imu_to_dxl' and desired.removeprefix('/')=='RECOVERED_UNNAMED_1' and old=='$1N175'),(name,fp.GetReference(),pad.GetNumber(),desired,old)
                    pad.GetNet().SetNetname(desired)
                    reason='match schematic hierarchical net name; connectivity unchanged'
                audit['net_changes'].append({'reference':fp.GetReference(),'pad':pad.GetNumber(),'from':old,'to':desired,'reason':reason})
    output=dest/original.name;k.PCB_IO_MGR.Save(k.PCB_IO_MGR.KICAD_SEXP,str(output),board)
    reopened=k.LoadBoard(str(output))
    for row in audit['paired']:
        fp=next(f for f in reopened.GetFootprints() if f.GetReference()==row['reference'])
        assert fp.GetPath().AsString()==row['path'];assert fp.GetFPID().GetLibItemName()==row['reference']
        assert plugin.FootprintLoad(str(library),row['reference'])
    (dest/'pairing-audit.json').write_text(json.dumps(audit,indent=2))
    (dest/'README.txt').write_text('Paired recovered KiCad editing copy. Read ../../../KICAD-PAIRED-PROJECTS.txt. Generic passive symbols and static cached copper are not electrically/manufacturing qualified. Do not refill zones. Preserve this copy before an interactive schematic-to-PCB update. Eight IMU floating-pin singleton names are not source no-connect declarations. Generation overwrites this folder.\n')
    summaries.append({'candidate':name,'paired':len(audit['paired']),'offboard':len(audit['excluded_offboard_symbols']),'net_changes':len(audit['net_changes'])})
print(json.dumps(summaries,indent=2))
