"""Fabrication outputs for a Viagrid build, into ../fab/.

    PYTHONPATH=/opt/kicad10/lib/python3/dist-packages python3 export_fab.py

- copper_top.dxf / copper_bottom.dxf : for LightBurn (UV laser) per the Viagrid docs
- gerbers/ + drill                   : for chemical etching masks, or a normal PCB order
- holes_to_drill.csv                 : ONLY the holes you drill yourself (Viagrid vias are
                                       already in the blank)
- positions.csv                      : component placement (pick and place)
- preview_top.png / preview_bottom.png
"""
import csv
import json
import os
import shutil
import subprocess

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
PCB = os.path.join(ROOT, 'kicad', 'ykush_vg.kicad_pcb')
FAB = os.path.join(ROOT, 'fab')
CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')
VG = json.load(open(os.path.join(ROOT, 'pcb', 'viagrid_9055.json')))
X0, Y0 = VG['board_outline'][:2]


def cli(*args):
    subprocess.run([CLI, *args], check=True, capture_output=True)


def main():
    shutil.rmtree(FAB, ignore_errors=True)
    os.makedirs(os.path.join(FAB, 'gerbers'))
    cli('pcb', 'export', 'gerbers', '--layers', 'F.Cu,B.Cu,F.Mask,B.Mask,Edge.Cuts',
        '--no-protel-ext', '-o', os.path.join(FAB, 'gerbers') + '/', PCB)
    cli('pcb', 'export', 'drill', '-o', os.path.join(FAB, 'gerbers') + '/', PCB)
    for layer, name in (('F.Cu', 'copper_top'), ('B.Cu', 'copper_bottom')):
        cli('pcb', 'export', 'dxf', '--layers', f'{layer},Edge.Cuts', '--output-units', 'mm',
            '--mode-single', '-o', os.path.join(FAB, name + '.dxf'), PCB)
    cli('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both',
        '-o', os.path.join(FAB, 'positions.csv'), PCB)

    # holes you drill yourself: every pad hole (THT + NPTH); Viagrid vias are pre-made
    b = pcbnew.LoadBoard(PCB)
    rows = []
    for fp in b.GetFootprints():
        for pad in fp.Pads():
            if pad.GetAttribute() not in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                continue
            d = pad.GetDrillSize()
            c = pad.GetPosition()
            slot = d.x != d.y
            rows.append(dict(ref=fp.GetReference(), pad=pad.GetNumber() or '(peg)',
                             x_mm=round(pcbnew.ToMM(c.x) - X0, 3), y_mm=round(pcbnew.ToMM(c.y) - Y0, 3),
                             drill_mm=round(pcbnew.ToMM(min(d.x, d.y)), 2),
                             slot_len_mm=round(pcbnew.ToMM(max(d.x, d.y)), 2) if slot else '',
                             note='slot' if slot else ''))
    with open(os.path.join(FAB, 'holes_to_drill.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r['ref'], str(r['pad']))))

    for layers, name in (('F.Cu,Edge.Cuts', 'preview_top'), ('B.Cu,Edge.Cuts', 'preview_bottom')):
        subprocess.run(['python3', os.path.join(HERE, 'render.py'), PCB, os.path.join(FAB, name + '.png'), layers],
                       check=True, capture_output=True, env=dict(os.environ, DPI='200'))
        os.remove(os.path.join(FAB, name + '.svg'))
    print(f'{len(rows)} holes to drill; outputs in {FAB}')


if __name__ == '__main__':
    main()
