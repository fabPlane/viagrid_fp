"""Build the YKUSH-VG PCB on a Viagrid 9055 blank with KiCad 10's pcbnew API.

    PYTHONPATH=/opt/kicad10/lib/python3/dist-packages python3 build_pcb.py [--no-route]

Steps: outline + Viagrid vias -> footprints from the schematic netlist -> placement
(placement.py) -> routing (router.py, vias only at Viagrid sites) -> GND pours -> save.
"""
import json
import os
import subprocess
import sys
import tempfile

import pcbnew

from sexpr import parse, find, find1

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
SCH = os.path.join(ROOT, 'kicad', 'ykush_vg.kicad_sch')
OUT = os.environ.get('PCB_OUT') or os.path.join(ROOT, 'kicad', 'ykush_vg.kicad_pcb')
FPDIR = os.environ.get('KICAD10_FOOTPRINT_DIR', '/opt/kicad10/share/kicad/footprints')
CLI = os.environ.get('KICAD_CLI', '/opt/kicad10/bin/kicad-cli')

VG = json.load(open(os.path.join(ROOT, 'pcb', 'viagrid_9055.json')))
X0, Y0, X1, Y1 = VG['board_outline']

# Design rules (laser / etch on Viagrid). Grid-via copper is trimmed to VIA_D.
VIA_D, VIA_DRILL = 0.6, 0.2
GND = '/GND'
CLEARANCE = 0.15
TRACK = 0.25

mm = pcbnew.FromMM


def P(x, y):
    """Board-relative mm (origin = top-left of the 90x55 blank) -> VECTOR2I."""
    return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))


def netlist():
    """Components and nets straight from the schematic via kicad-cli."""
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'n.net')
        subprocess.run([CLI, 'sch', 'export', 'netlist', '--format', 'kicadsexpr', '-o', f, SCH],
                       check=True, capture_output=True)
        n = parse(open(f).read())
    comps = {}
    for c in find(find1(n, 'components'), 'comp'):
        ref = find1(c, 'ref')[1]
        comps[ref] = dict(value=find1(c, 'value')[1], footprint=find1(c, 'footprint')[1],
                          uuid=find1(c, 'tstamps')[1], pads={},
                          dnp=any(p[1] == 'dnp' for p in find(c, 'property')))
    for net in find(find1(n, 'nets'), 'net'):
        name = find1(net, 'name')[1]         # keep KiCad's '/NAME' so schematic parity holds
        for node in find(net, 'node'):
            r, pin = find1(node, 'ref')[1], find1(node, 'pin')[1]
            if r in comps:
                comps[r]['pads'][pin] = name
    return comps


def new_board():
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(2)
    ds = b.GetDesignSettings()
    ds.m_MinClearance = mm(CLEARANCE)
    ds.m_TrackMinWidth = mm(0.2)
    ds.m_ViasMinSize = mm(VIA_D)
    ds.m_MinThroughDrill = mm(VIA_DRILL)
    ds.m_CopperEdgeClearance = mm(0.3)
    # Viagrid via copper is laser-trimmed next to drilled peg holes; the plated barrel itself
    # stays >= 0.35 mm from any hole we drill, so 0.15 mm copper-to-hole is enough here.
    ds.m_HoleClearance = mm(0.15)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetClearance(mm(CLEARANCE))
    nc.SetTrackWidth(mm(TRACK))
    nc.SetViaDiameter(mm(VIA_D))
    nc.SetViaDrill(mm(VIA_DRILL))
    # outline
    pts = [(0, 0), (X1 - X0, 0), (X1 - X0, Y1 - Y0), (0, Y1 - Y0)]
    for i in range(4):
        s = pcbnew.PCB_SHAPE(b)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(P(*pts[i]))
        s.SetEnd(P(*pts[(i + 1) % 4]))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.05))
        b.Add(s)
    return b


def net(b, name):
    n = b.FindNet(name)
    if n is None:
        n = pcbnew.NETINFO_ITEM(b, name)
        b.Add(n)
    return n


def add_via(b, x, y, netname, d=VIA_D, drill=VIA_DRILL, abs_coords=False):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)) if abs_coords else P(x, y))
    v.SetWidth(mm(d))
    v.SetDrill(mm(drill))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetNet(net(b, netname))
    v.SetIsFree(True)
    b.Add(v)
    return v


def load_fp(libid):
    lib, name = libid.split(':')
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
    if fp is None:
        raise RuntimeError('footprint not found: ' + libid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def place_footprints(b, comps, placement):
    fps = {}
    for ref, c in sorted(comps.items()):
        if ref not in placement:
            raise KeyError(f'no placement for {ref}')
        x, y, rot = placement[ref][:3]
        side = placement[ref][3] if len(placement[ref]) > 3 else 'F'
        fp = load_fp(c['footprint'])
        fp.SetReference(ref)
        fp.SetValue(c['value'])
        fp.SetPath(pcbnew.KIID_PATH('/' + c['uuid']))
        b.Add(fp)
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(x, y))
        if c['dnp']:
            fp.SetDNP(True)
        for pad in fp.Pads():
            n = c['pads'].get(pad.GetNumber())
            if n:
                pad.SetNet(net(b, n))
        fps[ref] = fp
    return fps


def viagrid(b, used=None):
    """All 180 Viagrid vias (unused ones on GND for stitching) + plated mounting holes."""
    used = used or {}
    vias = []
    for x, y in VG['grid_vias']:
        vias.append(add_via(b, x, y, used.get((x, y), GND), abs_coords=True))
    for x, y in VG['mount_holes']:
        add_via(b, x, y, GND, d=VG['mount_hole']['pad'], drill=VG['mount_hole']['drill'], abs_coords=True)
    return vias


def gnd_pours(b):
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(b)
        z.SetLayer(layer)
        z.SetNet(net(b, GND))
        z.SetLocalClearance(mm(0.2))
        z.SetMinThickness(mm(0.2))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(mm(0.25))
        z.SetThermalReliefSpokeWidth(mm(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline()
        ol.NewOutline()
        for x, y in [(0.2, 0.2), (X1 - X0 - 0.2, 0.2), (X1 - X0 - 0.2, Y1 - Y0 - 0.2), (0.2, Y1 - Y0 - 0.2)]:
            ol.Append(mm(X0 + x), mm(Y0 + y))
        b.Add(z)
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())


def isolated_gnd_pads(b):
    """GND pads that the filled pours do not tie to the main ground (via DRC)."""
    import json
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, 'check.kicad_pcb')
        pcbnew.SaveBoard(tmp, b)
        rep = os.path.join(td, 'drc.json')
        subprocess.run([CLI, 'pcb', 'drc', '--format', 'json', '-o', rep, tmp], capture_output=True)
        d = json.load(open(rep))
    items = set()
    for u in d.get('unconnected_items', []):
        for it in u.get('items', []):
            desc = it.get('description', '')
            if '[/GND]' not in desc:
                continue
            if desc.startswith('Pad') and ' of ' in desc:
                items.add(('pad', desc.split(' of ')[1].split()[0], desc.split()[1]))
            elif desc.startswith('Zone') and 'F.Cu' in desc:
                items.add(('zone', round(it['pos']['x'], 2), round(it['pos']['y'], 2)))
    return sorted(items, key=str)


def refill(b):
    filler = pcbnew.ZONE_FILLER(b)
    filler.Fill(b.Zones())


def stitch_gnd(b, r):
    """Pour GND, then tie anything the pour leaves stranded (up to 4 rounds).
    Zones are refilled in place: removing zones from a board breaks KiCad 10's Python
    footprint wrappers."""
    import router
    if not len(list(b.Zones())):
        gnd_pours(b)
    else:
        refill(b)
    for _ in range(4):
        iso = isolated_gnd_pads(b)
        if not iso:
            break
        print(f'{len(iso)} GND items cut off from the pour: adding stubs')
        router.add_gnd_stubs(b, r, iso)
        refill(b)


def stitch_only():
    """Re-run only the GND pour/stitch step on the saved, routed board."""
    import router
    b = pcbnew.LoadBoard(OUT)
    r = router.Router.from_board(b, VG)
    stitch_gnd(b, r)
    b.BuildConnectivity()
    pcbnew.SaveBoard(OUT, b)
    tune_project_rules()
    print('saved', OUT)


def main():
    import placement
    if '--stitch-only' in sys.argv:
        return stitch_only()
    route = '--no-route' not in sys.argv
    b = new_board()
    comps = netlist()
    fps = place_footprints(b, comps, placement.PLACE)
    if route:
        import router
        r = router.route_board(b, fps, VG, P)
        stitch_gnd(b, r)
    else:
        viagrid(b)
        gnd_pours(b)
    b.BuildConnectivity()
    pcbnew.SaveBoard(OUT, b)
    add_jumper_groups()
    tune_project_rules()
    print('saved', OUT)


def add_jumper_groups():
    """Mark pads that are joined inside the part (router.JUMPER_GROUPS) as KiCad jumper pad
    groups, so DRC does not ask for copper between them. The Python API only exposes these
    read-only, so edit the saved file."""
    import router
    txt = open(OUT).read()
    out, pos = [], 0
    for value, groups in router.JUMPER_GROUPS.items():
        grp = '(jumper_pad_groups ' + ' '.join('(' + ' '.join(f'"{p}"' for p in gr) + ')' for gr in groups) + ')'
        while True:
            v = txt.find(f'(property "Value" "{value}"', pos)
            if v < 0:
                break
            start = txt.rfind('\n\t(footprint ', 0, v)
            dup = txt.find('(duplicate_pad_numbers_are_jumpers', start)
            eol = txt.find('\n', dup)
            nxt = txt[eol + 1:eol + 200]
            if 'jumper_pad_groups' not in nxt.split('\n')[0]:
                indent = txt[txt.rfind('\n', 0, dup) + 1:dup]
                txt = txt[:eol + 1] + indent + grp + '\n' + txt[eol + 1:]
            pos = v + 10
        pos = 0
    open(OUT, 'w').write(txt)


def tune_project_rules():
    """A Viagrid blank has no silkscreen, so silk checks are noise; say so in the project."""
    pro = OUT.replace('.kicad_pcb', '.kicad_pro')
    d = json.load(open(pro))
    sev = d['board']['design_settings'].setdefault('rule_severities', {})
    for k in ('silk_edge_clearance', 'silk_over_copper', 'silk_overlap'):
        sev[k] = 'ignore'
    with open(pro, 'w') as f:
        json.dump(d, f, indent=2)
        f.write('\n')


if __name__ == '__main__':
    main()
