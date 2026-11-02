from pathlib import Path
import copy, json, re, shutil, sys, zipfile
root=Path(sys.argv[1]).resolve()
source=root/'upstream/elec_RPI_Robot_HAT'
lib=root/'upstream/lib_KiCAD'
dest=root/'editing/kicad/Robot_HAT_reference'
dest.mkdir(parents=True,exist_ok=True)
for path in source.glob('*.kicad_*'):
    shutil.copy2(path,dest/path.name)
shutil.copy2(source/'LICENSE',dest/'UPSTREAM-LICENSE')
def parse(text):
    tokens=iter(re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',text))
    def value(tok):
        if tok!='(':
            return tok
        values=[]
        for item in tokens:
            if item==')':
                return values
            values.append(value(item))
        raise ValueError('Unclosed S-expression')
    return value(next(tokens))
def dump(value):
    return '('+' '.join(map(dump,value))+')' if isinstance(value,list) else value
symbols={}
conflicts=[]
for file in sorted(dest.glob('*.kicad_sch')):
    tree=parse(file.read_text(encoding='utf-8'))
    cached=next((item for item in tree if isinstance(item,list) and item[0]=='lib_symbols'),[])
    for symbol in cached[1:]:
        full=json.loads(symbol[1])
        if ':' not in full:
            print('Unqualified cached symbol:',file.name,full)
            continue
        prefix,name=full.split(':',1)
        local=copy.deepcopy(symbol); local[1]=json.dumps(name)
        previous=symbols.setdefault(prefix,{})
        if name in previous and dump(previous[name]) != dump(local):
            conflicts.append(full)
        else:
            previous[name]=local
symbol_dir=dest/'libraries/symbols'; symbol_dir.mkdir(parents=True,exist_ok=True)
for prefix,values in symbols.items():
    (symbol_dir/(prefix+'.kicad_sym')).write_text('(kicad_symbol_lib (version 20241209) (generator microduck_asset_prep)\n'+'\n'.join(dump(s) for s in values.values())+'\n)',encoding='utf-8')
(dest/'sym-lib-table').write_text('(sym_lib_table\n'+''.join(f' (lib (name "{p}")(type "KiCad")(uri "${{KIPRJMOD}}/libraries/symbols/{p}.kicad_sym")(options "")(descr "Extracted from upstream schematic cache"))\n' for p in sorted(symbols))+')\n')
board=dest/'elec_RPI_Robot_HAT.kicad_pcb'
text=board.read_text(encoding='utf-8')
text=text.replace('${KICAD_USER_LIB}','${KIPRJMOD}/../../../upstream/lib_KiCAD')
text=text.replace('${KICAD_USER_3DMOD}','${KIPRJMOD}/../../../upstream/lib_KiCAD/3d_models')
text=text.replace('${KICAD9_3DMODEL_DIR}','${KICAD10_3DMODEL_DIR}')
proxy=root/'reconstructed/oscillator/ASDMB_datasheet_max_envelope.step'
if proxy.is_file() and (proxy.parent/'provenance.json').is_file():
    (dest/'models').mkdir(exist_ok=True)
    shutil.copy2(proxy,dest/'models'/proxy.name)
    text=text.replace('${KICAD10_3DMODEL_DIR}/Oscillator.3dshapes/Oscillator_SMD_Abracon_ASDMB-4Pin_2.5x2.0mm.step','${KIPRJMOD}/models/'+proxy.name)
board.write_text(text,encoding='utf-8')
footprints={}
missing_fp=[]
std=Path(r'C:\Program Files\KiCad\10.0\share\kicad')
for full in sorted(set(re.findall(r'\(footprint "([^"\n]+)"',text))):
    prefix,name=full.split(':',1)
    if prefix in ('Library_Pollen','Lib_Pollen'):
        path=lib/'Footprints/Lib_Pollen.pretty'
        uri='${KIPRJMOD}/../../../upstream/lib_KiCAD/Footprints/Lib_Pollen.pretty'
    elif prefix=='LCSC_parts_lib':
        path=lib/'LCSC_parts/easyeda2kicad.pretty'
        uri='${KIPRJMOD}/../../../upstream/lib_KiCAD/LCSC_parts/easyeda2kicad.pretty'
    else:
        path=std/'footprints'/(prefix+'.pretty')
        uri='${KICAD10_FOOTPRINT_DIR}/'+prefix+'.pretty'
    footprints[prefix]=uri
    if not (path/(name+'.kicad_mod')).exists():
        missing_fp.append(full)
(dest/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{p}")(type "KiCad")(uri "{uri}")(options "")(descr "MicroDuck asset package mapping"))\n' for p,uri in sorted(footprints.items()))+')\n')
missing_models=[]; model_paths=[]
for value in sorted(set(re.findall(r'\(model "([^"\n]+)"',text))):
    expanded=value.replace('${KIPRJMOD}',str(dest)).replace('${KICAD10_3DMODEL_DIR}',str(std/'3dmodels'))
    model_paths.append({'reference':value,'resolved':expanded,'exists':Path(expanded).is_file()})
    if not Path(expanded).is_file():
        missing_models.append(value)
project=dest/'elec_RPI_Robot_HAT.kicad_pro'
config=json.loads(project.read_text())
config.setdefault('text_variables',{}).update({'KICAD_USER_LIB':'${KIPRJMOD}/../../../upstream/lib_KiCAD','KICAD_USER_3DMOD':'${KIPRJMOD}/../../../upstream/lib_KiCAD/3d_models'})
project.write_text(json.dumps(config,indent=2))
production=root/'editing/solidworks/Robot_HAT_reference_STEP'; production.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(next((source/'production').glob('*STEP.zip'))) as archive:
    for info in archive.infolist():
        if info.is_dir():
            continue
        target=production/Path(info.filename).name
        target.write_bytes(archive.read(info))
audit={'symbol_libraries':len(symbols),'cached_symbols_extracted':sum(map(len,symbols.values())),
       'symbol_cache_conflicts':sorted(set(conflicts)),'missing_footprints':missing_fp,
       'missing_3d_models':missing_models,'model_paths':model_paths,
       'board_identity':'Pollen RPI Robot HAT D1 reference; not established as exact alpha/production MicroDuck electronics',
       'changes':'Working copy only: project library tables, cached symbol libraries, local 3D paths. Copper and schematic circuits preserved.'}
(root/'audit/kicad-dependencies.json').write_text(json.dumps(audit,indent=2))
print(json.dumps({k:v for k,v in audit.items() if k!='model_paths'},indent=2))
