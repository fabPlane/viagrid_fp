"""Finish a routed board: retry nets DRC still reports as unrouted, then re-stitch GND.

    PYTHONPATH=/opt/kicad10/lib/python3/dist-packages python3 finish.py
"""
import json
import os
import subprocess
import tempfile

import pcbnew

import build_pcb
import router


def unrouted_nets(board_path):
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, 'd.json')
        subprocess.run([build_pcb.CLI, 'pcb', 'drc', '--format', 'json', '-o', out, board_path],
                       capture_output=True)
        d = json.load(open(out))
    nets = set()
    for u in d['unconnected_items']:
        for it in u['items']:
            desc = it['description']
            if '[' in desc and '[/GND]' not in desc:
                nets.add(desc[desc.index('[') + 1:desc.index(']')])
    return sorted(nets)


def sync_pad_nets(b):
    """Apply pin-level net changes from the schematic; drop copper of nets that changed."""
    comps = build_pcb.netlist()
    changed = set()
    for fp in b.GetFootprints():
        c = comps.get(fp.GetReference())
        if not c:
            continue
        for pad in fp.Pads():
            want = c['pads'].get(pad.GetNumber(), '')
            if pad.GetNetname() != want and pad.GetNumber():
                changed |= {pad.GetNetname(), want} - {''}
                if want:
                    pad.SetNet(build_pcb.net(b, want))
                else:
                    pad.SetNetCode(0)
    changed = {n for n in changed if not n.startswith('unconnected-')}
    for t in list(b.GetTracks()):
        if t.GetNetname() in changed:
            if t.GetClass() == 'PCB_VIA':
                t.SetNet(build_pcb.net(b, build_pcb.GND))
            else:
                b.Remove(t)
    if changed:
        print('nets changed in schematic:', sorted(changed))
    return changed


def main():
    b = pcbnew.LoadBoard(build_pcb.OUT)
    if sync_pad_nets(b):
        pcbnew.SaveBoard(build_pcb.OUT, b)
        b = pcbnew.LoadBoard(build_pcb.OUT)
    todo = unrouted_nets(build_pcb.OUT)
    print('unrouted:', todo)
    r = router.Router.from_board(b, build_pcb.VG)
    board_vias = {}
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            p = t.GetPosition()
            board_vias[(round(pcbnew.ToMM(p.x), 3), round(pcbnew.ToMM(p.y), 3))] = t
    for name in todo:
        # the net's existing copper is already in the grid; route_net connects pad clusters
        for w in (0.25, 0.2):
            ok, segs, vias = r.route_net(name, w)
            if ok:
                break
        if not ok:
            print('  still unroutable:', name)
            continue
        for layer, a, e, ww, code in segs:
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(a[0]), pcbnew.FromMM(a[1])))
            t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(e[0]), pcbnew.FromMM(e[1])))
            t.SetWidth(pcbnew.FromMM(ww))
            t.SetLayer(pcbnew.F_Cu if layer == 0 else pcbnew.B_Cu)
            t.SetNet(build_pcb.net(b, name))
            b.Add(t)
        for vi in vias:
            x, y = r.g.vias[vi][2:]
            v = board_vias.get((round(x, 3), round(y, 3)))
            if v is not None:
                v.SetNet(build_pcb.net(b, name))
            r.used_vias[vi] = name
        print(f'  routed {name} ({len(segs)} segments, {len(vias)} vias)')
    build_pcb.stitch_gnd(b, r)
    b.BuildConnectivity()
    pcbnew.SaveBoard(build_pcb.OUT, b)
    build_pcb.add_jumper_groups()
    build_pcb.tune_project_rules()
    print('saved', build_pcb.OUT)


if __name__ == '__main__':
    main()
