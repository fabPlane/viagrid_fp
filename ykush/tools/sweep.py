"""Route the board with several parameter sets in parallel and keep the best result.

    PYTHONPATH=/opt/kicad10/lib/python3/dist-packages python3 sweep.py
Score = unconnected items * 10 + real DRC errors (dangling vias / starved thermals ignored).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.join(HERE, '..', 'kicad')
CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')
VARIANTS = [
    dict(PRES_GROWTH='1.5', HIST_W='1.0', BCU_MULT='2.0'),
    dict(PRES_GROWTH='1.3', HIST_W='2.0', BCU_MULT='1.5'),
    dict(PRES_GROWTH='1.8', HIST_W='0.5', BCU_MULT='2.5'),
    dict(PRES_GROWTH='1.4', HIST_W='1.5', BCU_MULT='1.2'),
]
IGNORE = {'via_dangling', 'starved_thermal', 'silk_edge_clearance', 'silk_over_copper', 'silk_overlap'}


def score(pcb):
    with tempfile.TemporaryDirectory() as td:
        # DRC needs the project file next to the board for our rule settings
        b = os.path.join(td, 'ykush_vg.kicad_pcb')
        shutil.copy(pcb, b)
        shutil.copy(os.path.join(KDIR, 'ykush_vg.kicad_pro'), os.path.join(td, 'ykush_vg.kicad_pro'))
        out = os.path.join(td, 'd.json')
        subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '-o', out, b], capture_output=True)
        d = json.load(open(out))
    errs = [v['type'] for v in d['violations'] if v['type'] not in IGNORE]
    return len(d['unconnected_items']) * 10 + len(errs), len(d['unconnected_items']), errs


def main():
    iters = os.environ.get('ROUTE_ITERS', '30')
    procs = []
    work = tempfile.mkdtemp(prefix='sweep_')
    for i, v in enumerate(VARIANTS):
        out = os.path.join(work, f'v{i}.kicad_pcb')
        env = dict(os.environ, **v, ROUTE_ITERS=iters, PCB_OUT=out)
        log = open(os.path.join(work, f'v{i}.log'), 'w')
        procs.append((i, out, subprocess.Popen([sys.executable, os.path.join(HERE, 'build_pcb.py')],
                                               env=env, stdout=log, stderr=subprocess.STDOUT)))
    results = []
    for i, out, p in procs:
        p.wait()
        if os.path.exists(out):
            s = score(out)
            results.append((s[0], i, out, s))
            print(f'variant {i} {VARIANTS[i]}: score {s[0]} (unconnected {s[1]}, errors {s[2]})')
        else:
            print(f'variant {i} failed; see {work}/v{i}.log')
    if results:
        best = min(results)
        shutil.copy(best[2], os.path.join(KDIR, 'ykush_vg.kicad_pcb'))
        print(f'kept variant {best[1]} -> kicad/ykush_vg.kicad_pcb (logs in {work})')


if __name__ == '__main__':
    main()
