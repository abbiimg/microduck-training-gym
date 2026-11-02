"""Windows entry point for activation-free MicroDuck software checks.
Passing this suite is NOT a manufacturing or complete robot release.
"""
from pathlib import Path
import subprocess,json,sys,time,argparse
root=Path(__file__).resolve().parents[1]
def linux(p):
    p=Path(p).resolve()
    return '/mnt/'+p.drive[0].lower()+p.as_posix()[2:]
py='/home/workbench/robotics/pcb-tools/venv/bin/python'
def wsl(script,*args):return ['wsl','-d','NVIDIA-Workbench','--',py,linux(root/'tools'/script),*args]
steps={
 'kicad_connections':[sys.executable,str(root/'tools/verify_recovered_kicad.py')],
 'firmware_host':wsl('run_firmware_regression.py'),
 'controller_bus':wsl('run_bus_integration.py','--build-dir','/home/workbench/robotics/pcb-tools/bus-integration'),
 'buffer_model':wsl('test_ti_bus_buffer.py','--model',linux(root/'electrical-models/ti-sn74lvc2g241/SN74LVC2G241.cir'),'--output',linux(root/'audit/pcb-tools/ti-buffer')),
 'buffer_transient':wsl('test_ti_buffer_transient.py'),
 'buffer_package':wsl('test_ti_buffer_package.py'),
 'paired_projects':wsl('verify_paired_projects.py'),
 'recovered_libraries':wsl('verify_recovered_libraries.py'),
 'copper_engineering':wsl('verify_copper_engineering.py'),
 'source_clearances':[sys.executable,str(root/'tools/verify_source_clearances.py')],
 'integrated_silkscreen':wsl('verify_recovered_silkscreen.py'),
 'author_step_components':[sys.executable,str(root/'tools/verify_author_step_components.py')],
 'author_model_definitions':[sys.executable,str(root/'tools/verify_author_step_definitions.py')],
 'author_model_geometry':[sys.executable,str(root/'tools/verify_author_step_geometry_receipt.py')],
 'kicad_model_geometry':[sys.executable,str(root/'tools/verify_kicad_model_integrity.py')],
 'pcb_model_review':[sys.executable,str(root/'tools/verify_pcb_model_review_package.py')],
 'hub_cache_repair':wsl('verify_hub_cache_repair.py')}
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--only',action='append',choices=list(steps),help='Rerun selected stages; explicitly retain prior results for unchanged unselected stages')
args=parser.parse_args();selection=set(args.only or steps)
prior={}
if args.only:
    previous=json.loads((root/'audit/pcb-tools/software-stack-result.json').read_text())
    prior={r['step']:r for r in previous['software_checks']}
    assert set(steps)-selection<=set(prior),'No previous result exists for an unselected stage; run the full suite'
results=[]
for name,cmd in steps.items():
    if name not in selection:
        results.append({**prior[name],'retained_prior_result':True})
        continue
    start=time.time()
    run=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=300)
    (root/'audit/pcb-tools'/('stack-'+name+'.log')).write_text(run.stdout+run.stderr,encoding='utf-8')
    results.append({'step':name,'passed':run.returncode==0,'exit_code':run.returncode,'seconds':round(time.time()-start,2)})
    print(name,'PASS' if run.returncode==0 else 'FAIL',flush=True)
report={'software_checks':results,'software_checks_passed':all(x['passed'] for x in results),
 'stages_executed_this_invocation':[n for n in steps if n in selection],
 'prior_results_retained_for_unchanged_stages':[n for n in steps if n not in selection],
 'hardware_release_ready':False,
 'open_gates':['routed PCB source equivalence, DRC cleanup and regenerative copper rules','qualified component models and dimensions','eight pins lack source no-connect declarations; electrical review remains conditional',
               'physical power/timing/thermal tests','one consistent CAD/actuator/electronics/simulation variant',
               'policy quality and real-hardware validation']}
(root/'audit/pcb-tools/software-stack-result.json').write_text(json.dumps(report,indent=2))
raise SystemExit(0 if report['software_checks_passed'] else 1)
