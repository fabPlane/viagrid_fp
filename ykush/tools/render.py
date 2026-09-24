"""Render the routed board to PNG (F.Cu red, B.Cu blue) via kicad-cli SVG export."""
import os
import subprocess
import sys

import pymupdf

CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')
brd = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'kicad', 'ykush_vg.kicad_pcb')
out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/claude-0/board.png'
layers = sys.argv[3] if len(sys.argv) > 3 else 'F.Cu,B.Cu,Edge.Cuts,F.Fab'
svg = out.replace('.png', '.svg')
subprocess.run([CLI, 'pcb', 'export', 'svg', '--layers', layers, '--mode-single', '--fit-page-to-board',
                '--exclude-drawing-sheet', '-o', svg, brd], check=True, capture_output=True)
d = pymupdf.open(svg)
d[0].get_pixmap(dpi=int(os.environ.get('DPI', '220'))).save(out)
print(out)
