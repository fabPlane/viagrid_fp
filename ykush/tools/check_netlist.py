"""Export the netlist with kicad-cli and compare it to the nets the generator intended."""
import os
import subprocess
import sys
import tempfile

from sexpr import parse, find, find1

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(HERE, '..', 'kicad')
cli = os.environ.get('KICAD_CLI', 'kicad-cli')

with tempfile.TemporaryDirectory() as td:
    out = os.path.join(td, 'n.net')
    subprocess.run([cli, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', out,
                    os.path.join(KDIR, 'ykush_vg.kicad_sch')], check=True, capture_output=True)
    n = parse(open(out).read())
kic = {}
for net in find(find1(n, 'nets'), 'net'):
    name = find1(net, 'name')[1].lstrip('/')
    nodes = sorted(f"{find1(x, 'ref')[1]}.{find1(x, 'pin')[1]}" for x in find(net, 'node')
                   if not find1(x, 'ref')[1].startswith('#'))
    if nodes and not name.startswith('unconnected-'):
        kic[name] = nodes
mine = {}
for line in open(os.path.join(KDIR, 'nets.txt')):
    k, v = line.split(':', 1)
    mine[k] = sorted(v.split())
bad = [k for k in sorted(set(kic) | set(mine)) if kic.get(k) != mine.get(k)]
for k in bad:
    print('MISMATCH', k, '\n  kicad:', kic.get(k), '\n  intended:', mine.get(k))
single = [k for k, v in mine.items() if len(v) < 2]
for k in single:
    print('SINGLE-PIN NET', k, mine[k])
print(f'{len(kic)} nets, {len(bad)} mismatches, {len(single)} single-pin nets')
sys.exit(1 if bad or single else 0)
