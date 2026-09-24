"""Placement sanity checks + picture (courtyards, pads, Viagrid vias, ratsnest).

    PYTHONPATH=/opt/kicad10/lib/python3/dist-packages python3 viz.py [board] [out.png]
"""
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import pcbnew  # noqa: E402

from build_pcb import X0, Y0, VG, CLEARANCE, VIA_D  # noqa: E402

TOMM = pcbnew.ToMM


def pad_poly(pad, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(ps, layer, 0, pcbnew.FromMM(0.005), pcbnew.ERROR_INSIDE)
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        out.append([(TOMM(o.CPoint(j).x) - X0, TOMM(o.CPoint(j).y) - Y0) for j in range(o.PointCount())])
    return out


def courtyard(fp):
    for L in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
        c = fp.GetCourtyard(L)
        if c.OutlineCount():
            bb = c.BBox()
            return (TOMM(bb.GetX()) - X0, TOMM(bb.GetY()) - Y0, TOMM(bb.GetRight()) - X0, TOMM(bb.GetBottom()) - Y0)
    return None


def check(b):
    """Return list of problems: courtyard overlaps, pad/grid-via conflicts, off-board parts."""
    probs = []
    fps = list(b.GetFootprints())
    cys = {fp.GetReference(): courtyard(fp) for fp in fps}
    refs = sorted(cys)
    for i, a in enumerate(refs):
        A = cys[a]
        if A[0] < -0.6 or A[1] < -0.6 or A[2] > 90.5 or A[3] > 55.5:
            probs.append(f'{a} courtyard leaves the board {tuple(round(v, 2) for v in A)}')
        for bref in refs[i + 1:]:
            B = cys[bref]
            if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                probs.append(f'courtyard overlap {a} / {bref}')
    # pads vs grid vias: a via inside/near a pad must be same net (it becomes via-in-pad)
    import math
    vias = [(x - X0, y - Y0) for x, y in VG['grid_vias']]
    need = VIA_D / 2 + CLEARANCE
    for fp in fps:
        for pad in fp.Pads():
            netn = pad.GetNetname() or '(none)'
            for poly in pad_poly(pad, pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu):
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                for vx, vy in vias:
                    if min(xs) - need < vx < max(xs) + need and min(ys) - need < vy < max(ys) + need:
                        # distance from via centre to polygon (approx by bbox)
                        dx = max(min(xs) - vx, 0, vx - max(xs))
                        dy = max(min(ys) - vy, 0, vy - max(ys))
                        d = math.hypot(dx, dy)
                        if d < need - 1e-6:
                            probs.append(f'{fp.GetReference()}.{pad.GetNumber()} ({netn}) hits Viagrid via '
                                         f'({vx:.2f},{vy:.2f}) d={d:.2f}')
    return probs


def draw(b, out):
    fig, ax = plt.subplots(figsize=(18, 11.5))
    ax.add_patch(plt.Rectangle((0, 0), 89.9, 54.9, fill=False, lw=1.5))
    for x, y in VG['grid_vias']:
        ax.add_patch(plt.Circle((x - X0, y - Y0), VIA_D / 2, color='#d33', zorder=3))
    for x, y in VG['mount_holes']:
        ax.add_patch(plt.Circle((x - X0, y - Y0), 2.25, color='#999'))
    nets = {}
    for fp in b.GetFootprints():
        cy = courtyard(fp)
        if cy:
            ax.add_patch(plt.Rectangle((cy[0], cy[1]), cy[2] - cy[0], cy[3] - cy[1], fill=False,
                                       ec='#aaa', lw=0.6, ls='--'))
        p = fp.GetPosition()
        ax.text(TOMM(p.x) - X0, TOMM(p.y) - Y0, fp.GetReference(), fontsize=7, ha='center', va='center',
                color='#036', zorder=6, weight='bold')
        for pad in fp.Pads():
            col = '#c80' if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD else '#2a2'
            for poly in pad_poly(pad, pcbnew.F_Cu if pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu):
                ax.add_patch(plt.Polygon(poly, color=col, alpha=0.8, zorder=4))
            n = pad.GetNetname()
            if n and n != 'GND':
                c = pad.GetPosition()
                nets.setdefault(n, []).append((TOMM(c.x) - X0, TOMM(c.y) - Y0))
    # routed copper
    routed_nets = set()
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            c = t.GetPosition()
            if t.GetNetname() != 'GND':
                ax.add_patch(plt.Circle((TOMM(c.x) - X0, TOMM(c.y) - Y0), 0.3, color='#0a0', zorder=7))
            continue
        a, e = t.GetStart(), t.GetEnd()
        col = '#e22' if t.GetLayer() == pcbnew.F_Cu else '#22e'
        ax.plot([TOMM(a.x) - X0, TOMM(e.x) - X0], [TOMM(a.y) - Y0, TOMM(e.y) - Y0], color=col,
                lw=TOMM(t.GetWidth()) * 7.2, solid_capstyle='round', zorder=5, alpha=0.85)
        routed_nets.add(t.GetNetname())
    # ratsnest (MST per net) for nets with no copper yet
    import math
    for n, pts in nets.items():
        if n in routed_nets:
            continue
        inside, rest = [pts[0]], pts[1:]
        while rest:
            best = min(((a, r) for a in inside for r in rest), key=lambda ar: math.dist(*ar))
            ax.plot([best[0][0], best[1][0]], [best[0][1], best[1][1]], lw=0.5, color='#07f', zorder=5)
            inside.append(best[1])
            rest.remove(best[1])
    ax.set_xlim(-2, 92)
    ax.set_ylim(57, -2)
    ax.set_aspect('equal')
    ax.set_xticks(range(0, 91, 5))
    ax.set_yticks(range(0, 56, 5))
    ax.grid(True, alpha=0.2)
    plt.savefig(out, dpi=80, bbox_inches='tight')


if __name__ == '__main__':
    brd = sys.argv[1] if len(sys.argv) > 1 else '../kicad/ykush_vg.kicad_pcb'
    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/claude-0/place.png'
    b = pcbnew.LoadBoard(brd)
    for p in check(b):
        print(p)
    draw(b, out)
