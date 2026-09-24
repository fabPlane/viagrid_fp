"""Run KiCad DRC (with schematic parity) and print a short summary.

    python3 drc.py [board] [--details TYPE]
"""
import collections
import json
import os
import subprocess
import sys
import tempfile

CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')
HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
brd = args[0] if args else os.path.join(HERE, '..', 'kicad', 'ykush_vg.kicad_pcb')
detail = sys.argv[sys.argv.index('--details') + 1] if '--details' in sys.argv else None

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'drc.json')
    subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '--schematic-parity', '--severity-all',
                    '-o', out, brd], capture_output=True)
    rep = json.load(open(out))

for section in ('violations', 'unconnected_items', 'schematic_parity'):
    items = rep.get(section, [])
    c = collections.Counter(i['type'] for i in items)
    print(f'{section}: {len(items)}', dict(c))
    for i in items:
        if detail and i['type'] == detail:
            print('   ', i['description'], '|', ' / '.join(x.get('description', '') for x in i.get('items', [])))
