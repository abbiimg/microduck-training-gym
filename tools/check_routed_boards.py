"""Bounded KiCad DRC of recovered candidates; never edits or refills boards."""
from pathlib import Path
import subprocess,json,collections
root=Path(__file__).resolve().parents[1]
results=[]
for tree in ['kicad-routed','kicad-routed-transition-hypothesis']:
    for board in sorted((root/'editing'/tree).glob('*/*.kicad_pcb')):
        output=board.with_name('drc.json')
        try:
            run=subprocess.run(['/usr/bin/kicad-cli','pcb','drc','--format','json','--output',str(output),str(board)],capture_output=True,text=True,timeout=90)
            result={'tree':tree,'candidate':board.stem,'returncode':run.returncode,'stdout':run.stdout,'stderr':run.stderr}
            if run.returncode==0 and output.exists():
                report=json.loads(output.read_text())
                result.update(violation_counts=dict(collections.Counter(v['type'] for v in report['violations'])),unconnected=len(report['unconnected_items']),violations=len(report['violations']))
        except subprocess.TimeoutExpired:result={'tree':tree,'candidate':board.stem,'error':'DRC timed out after 90 seconds'}
        results.append(result)
        print(json.dumps(result),flush=True)
(root/'editing/routed-drc-summary.json').write_text(json.dumps(results,indent=2))
