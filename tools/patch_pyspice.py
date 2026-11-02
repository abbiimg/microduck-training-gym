from pathlib import Path
import hashlib, json
root = Path('/home/workbench/robotics/pcb-tools')
p = root/'venv/lib/python3.12/site-packages/PySpice/Spice/NgSpice/Shared.py'
before = p.read_bytes()
old = "            if content.startswith('Warning:'):"
new = "            if content.startswith('Warning:') or content.strip() == 'Using SPARSE 1.3 as Direct Linear Solver':"
assert before.decode().count(old) == 1
backup = root/'downloads/PySpice-1.5-Shared.py.original'
assert not backup.exists()
backup.write_bytes(before)
after = before.decode().replace(old, new).encode()
p.write_bytes(after)
(root/'pyspice-compatibility.json').write_text(json.dumps({
    'issue': 'https://github.com/PySpice-org/PySpice/issues/379',
    'change': 'Classify only exact SPARSE solver informational stderr as non-fatal',
    'before_sha256': hashlib.sha256(before).hexdigest(),
    'after_sha256': hashlib.sha256(after).hexdigest(),
    'original': str(backup),
}, indent=2))
