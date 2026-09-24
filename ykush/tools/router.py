"""Grid router for Viagrid boards.

A* on a 0.1 mm grid over two layers. The one rule that makes it a Viagrid router:
a track may change layer **only at one of the blank's pre-made vias**. Other rules:
  * SMD pads are reachable on F.Cu only.
  * THT pads are reachable on B.Cu only: holes drilled into a Viagrid blank are not
    plated, so you solder them from the bottom.
  * Unused Viagrid vias are real plated barrels. They are obstacles, and they are
    left on GND so they stitch the two pours together.
  * GND is not routed. It comes from the pours on both layers; route_gnd_stubs()
    patches pads the pour cannot reach.

The router is deliberately simple: it routes one net at a time in priority order and
rips up and retries nets that fail. That is enough for a board this size.
"""
import ctypes
import math
import os
import subprocess

import numpy as np
import pcbnew
from PIL import Image, ImageDraw
from scipy import ndimage

RES = 0.1                   # grid pitch, mm
CLR = 0.15                  # copper clearance, mm
EDGE_CLR = 0.3              # copper to board edge, mm
VIA_R = 0.3                 # trimmed Viagrid via copper radius, mm
VIA_COST = 3.0              # mm-equivalent cost of a layer change
BCU_MULT = 2.0              # B.Cu costs 2x per mm: keep the bottom mostly ground plane
ESCAPE = 0.6                # mm around unrouted pads of other nets ...
ESCAPE_MULT = 4.0           # ... that cost 4x to cross
TURN_COST = 0.25            # mm-equivalent cost of a 45-degree direction change
FREE, HARD, VFREE = 0, -1, -2

DIRS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]

# per-net track widths (mm); everything else uses DEFAULT_W
WIDTH = {
    '+5V_PORT': 0.8, 'EXT_5V_IN': 0.8, 'EXT_5V': 0.8, 'VBUS_UP': 0.6,
    'VBUS_P1': 0.6, 'VBUS_P2': 0.6, 'VBUS_P3': 0.6,
}
DEFAULT_W = 0.25
FALLBACK_W = (0.3, 0.25, 0.2)

# routing order: nets that must use the gap under the hub, then USB, then power and the rest
# (widest first, then shortest).
PRIORITY = ['XIN', 'XOUT', 'REXT', '+1V8', '+3V3', 'VBUSM',          # through the gap under the hub
            'UP_DM_A', 'UP_DP', 'UP_DM', 'CC1', 'CC2',                # USB-C
            'P1_DP', 'P1_DM', 'P2_DP', 'P2_DM', 'P3_DP', 'P3_DM',      # High-Speed port pairs
            'VBUS_UP', 'MCU_DP', 'MCU_DM']                            # FS link may use vias

mm = pcbnew.FromMM
tomm = pcbnew.ToMM

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIB = None


def _lib():
    """Build (if needed) and load the C A* core."""
    global _LIB
    if _LIB is None:
        src = os.path.join(_HERE, 'astar.c')
        so = os.path.join(_HERE, '_astar.so')
        if not os.path.exists(so) or os.path.getmtime(so) < os.path.getmtime(src):
            subprocess.run(['gcc', '-O2', '-shared', '-fPIC', '-o', so, src, '-lm'], check=True)
        _LIB = ctypes.CDLL(so)
        _LIB.astar.restype = ctypes.c_int
    return _LIB


def _p(a, t):
    return a.ctypes.data_as(ctypes.POINTER(t))


class Grid:
    def __init__(self, w_mm, h_mm, x0, y0):
        self.x0, self.y0 = x0, y0                     # absolute mm of board origin
        self.W = int(round(w_mm / RES)) + 1
        self.H = int(round(h_mm / RES)) + 1
        self.own = np.zeros((2, self.H, self.W), np.int32)
        self.vias = []                                # [(ix, iy, abs_x, abs_y)]
        self.via_net = {}                             # via index -> net code (claimed)
        edge = np.ones((self.H, self.W), bool)
        e = int(math.ceil(EDGE_CLR / RES))
        edge[e:-e, e:-e] = False
        self.edge = edge

    # --------------------------------------------------------------- raster helpers
    def cell(self, x_abs, y_abs):
        return int(round((x_abs - self.x0) / RES)), int(round((y_abs - self.y0) / RES))

    def _mask_poly(self, pts_abs):
        img = Image.new('1', (self.W, self.H), 0)
        # PIL pixel i covers [i, i+1); our cell i is centred on i*RES -> shift by half a pixel
        ImageDraw.Draw(img).polygon([((x - self.x0) / RES + 0.5, (y - self.y0) / RES + 0.5) for x, y in pts_abs],
                                    fill=1)
        return np.array(img, bool)

    def _mask_circle(self, cx, cy, r):
        yy, xx = np.ogrid[:self.H, :self.W]
        ix, iy = (cx - self.x0) / RES, (cy - self.y0) / RES
        return (xx - ix) ** 2 + (yy - iy) ** 2 <= (r / RES) ** 2

    def _mask_seg(self, a, b, w):
        img = Image.new('1', (self.W, self.H), 0)
        d = ImageDraw.Draw(img)
        pa = ((a[0] - self.x0) / RES + 0.5, (a[1] - self.y0) / RES + 0.5)
        pb = ((b[0] - self.x0) / RES + 0.5, (b[1] - self.y0) / RES + 0.5)
        r = w / 2 / RES
        d.line([pa, pb], fill=1, width=max(1, int(round(w / RES))))
        for p in (pa, pb):
            d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=1)
        return np.array(img, bool)

    def put(self, layer, mask, code):
        self.own[layer][mask] = code


def key(name):
    """'/NAME' (KiCad schematic net) -> 'NAME' for the tables above."""
    return name.lstrip('/')


def pad_polys(pad, layer):
    ps = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(ps, layer, 0, mm(0.005), pcbnew.ERROR_INSIDE)
    out = []
    for i in range(ps.OutlineCount()):
        o = ps.Outline(i)
        out.append([(tomm(o.CPoint(j).x), tomm(o.CPoint(j).y)) for j in range(o.PointCount())])
    return out


class Router:
    def __init__(self, board, vg):
        self.b = board
        x0, y0, x1, y1 = vg['board_outline']
        self.g = Grid(x1 - x0, y1 - y0, x0, y0)
        self.netcode = {}
        self.netname = {}
        self.pads = {}           # net -> [(pad, layers, mask_by_layer)]
        self.tracks = []         # (layer, (x,y), (x,y), width, net)
        self.failed = []
        self.pending = set()
        self._soft = None
        self._load(vg)

    def code(self, name):
        if name not in self.netcode:
            c = len(self.netcode) + 1
            self.netcode[name] = c
            self.netname[c] = name
        return self.netcode[name]

    def _load(self, vg):
        g = self.g
        for fp in self.b.GetFootprints():
            for pad in fp.Pads():
                name = pad.GetNetname()
                attr = pad.GetAttribute()
                if attr == pcbnew.PAD_ATTRIB_NPTH:
                    L, code = (0, 1), HARD
                elif attr == pcbnew.PAD_ATTRIB_PTH:
                    L, code = (0, 1), self.code(name) if name else HARD
                else:
                    L, code = (0,) if pad.IsOnLayer(pcbnew.F_Cu) else (1,), self.code(name) if name else HARD
                masks = {}
                for layer in L:
                    m = np.zeros((g.H, g.W), bool)
                    for poly in pad_polys(pad, pcbnew.F_Cu if layer == 0 else pcbnew.B_Cu):
                        m |= g._mask_poly(poly)
                    g.put(layer, m, code)
                    masks[layer] = m
                if attr in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                    # a drilled hole is an obstacle on both layers
                    ds = pad.GetDrillSize()
                    r = tomm(max(ds.x, ds.y)) / 2
                    c = pad.GetPosition()
                    hole = g._mask_circle(tomm(c.x), tomm(c.y), r)
                    for layer in (0, 1):
                        g.own[layer][hole & (g.own[layer] == FREE)] = HARD
                if name and key(name) != 'GND' and attr != pcbnew.PAD_ATTRIB_NPTH:
                    # THT holes on a Viagrid are not plated: reachable from B.Cu only
                    access = (1,) if attr == pcbnew.PAD_ATTRIB_PTH else L
                    self.pads.setdefault(name, []).append((pad, access, masks))
        for x, y in vg['grid_vias']:
            ix, iy = g.cell(x, y)
            m = g._mask_circle(x, y, VIA_R)
            for layer in (0, 1):
                g.own[layer][m & (g.own[layer] == FREE)] = VFREE
            g.vias.append((ix, iy, x, y))
        for x, y in vg['mount_holes']:
            m = g._mask_circle(x, y, 2.25)
            for layer in (0, 1):
                g.own[layer][m] = self.code('/GND')

    # --------------------------------------------------------------- routing one net
    def _blocked(self, code, hw):
        g = self.g
        blk, vok = [], []
        for layer in (0, 1):
            own = g.own[layer]
            foreign = (own != FREE) & (own != code)
            d = ndimage.distance_transform_edt(~foreign) * RES
            b = d < hw + CLR + RES * 0.5
            b |= ndimage.distance_transform_edt(~g.edge) * RES < hw + RES * 0.5
            b[g.edge] = True
            blk.append(b)
            # distance ignoring free vias (for deciding if a via can be claimed)
            f2 = foreign & (own != VFREE)
            vok.append(ndimage.distance_transform_edt(~f2) * RES)
        usable = []
        for vi, (ix, iy, x, y) in enumerate(g.vias):
            claimed = g.via_net.get(vi)
            if claimed not in (None, code):
                continue
            if all(vok[layer][iy, ix] >= VIA_R + CLR - 1e-6 for layer in (0, 1)):
                usable.append(vi)
                # this via is ours to claim: around it, block only for *other* copper
                thr = hw + CLR + RES * 0.5
                r = int(math.ceil((VIA_R + thr) / RES))
                yy, xx = np.ogrid[-r:r + 1, -r:r + 1]
                disc = (xx * xx + yy * yy) * RES * RES <= (VIA_R + thr) ** 2
                for layer in (0, 1):
                    sl = blk[layer][iy - r:iy + r + 1, ix - r:ix + r + 1]
                    vl = vok[layer][iy - r:iy + r + 1, ix - r:ix + r + 1]
                    sl[disc] = (vl < thr)[disc] | g.edge[iy - r:iy + r + 1, ix - r:ix + r + 1][disc]
        return blk, usable

    def _astar(self, code, blk, usable, src, goal, heur, mult=None):
        """src: list of (layer, iy, ix). goal: bool [2,H,W]. heur: [H,W] mm.
        Returns [(layer, iy, ix)] from src to goal, or None."""
        g = self.g
        H, W = g.H, g.W
        via_ok = np.zeros((H, W), np.uint8)
        for vi in usable:
            ix, iy = g.vias[vi][:2]
            via_ok[iy, ix] = 1
        blk8 = np.ascontiguousarray(np.stack(blk).astype(np.uint8))
        goal8 = np.ascontiguousarray(goal.astype(np.uint8))
        heur32 = np.ascontiguousarray(heur.astype(np.float32))
        srcarr = np.ascontiguousarray(np.array(src, np.int32).reshape(-1))
        cap = 200000
        out = np.zeros(cap, np.int32)
        if mult is None:
            mult = np.ones((2, H, W), np.float32)
        mult = np.ascontiguousarray(mult.astype(np.float32))
        n = _lib().astar(H, W, _p(blk8, ctypes.c_uint8), _p(via_ok, ctypes.c_uint8), _p(heur32, ctypes.c_float),
                         _p(goal8, ctypes.c_uint8), _p(srcarr, ctypes.c_int32), len(src),
                         ctypes.c_float(RES), ctypes.c_float(VIA_COST), ctypes.c_float(TURN_COST),
                         60000000, _p(out, ctypes.c_int32), cap, _p(mult, ctypes.c_float))
        if n < 0:
            return None, n
        HW = H * W
        return [(int(c) // HW, (int(c) % HW) // W, int(c) % W) for c in out[:n]], n

    def _mult(self, name):
        """Cost multipliers: B.Cu is expensive (keep it a ground plane) and so is the area
        right around pads of nets that are still unrouted (keep their escapes open)."""
        g = self.g
        m = np.ones((2, g.H, g.W), np.float32)
        m[1] *= BCU_MULT
        esc = np.zeros((2, g.H, g.W), bool)
        for other in self.pending:
            if other == name:
                continue
            for pad, access, masks in self.pads[other]:
                for layer in access:
                    esc[layer] |= masks[layer]
        r = int(round(ESCAPE / RES))
        st = ndimage.generate_binary_structure(2, 1)
        for layer in (0, 1):
            if esc[layer].any():
                grown = ndimage.binary_dilation(esc[layer], st, iterations=r)
                m[layer][grown] *= ESCAPE_MULT
        return m

    def _pad_cells(self, pad_entry, blk):
        pad, access, masks = pad_entry
        cells = []
        for layer in access:
            m = masks[layer] & ~blk[layer]
            ys, xs = np.nonzero(m)
            cells += [(layer, y, x) for y, x in zip(ys, xs)]
        if not cells:
            # pad interior fully blocked by neighbours at this width: use its centre
            c = pad.GetPosition()
            ix, iy = self.g.cell(tomm(c.x), tomm(c.y))
            for layer in access:
                blk[layer][iy, ix] = False
                cells.append((layer, iy, ix))
        return cells

    def route_net(self, name, width, soft=False):
        g = self.g
        code = self.code(name)
        pads = self.pads[name]
        hw = width / 2
        # start from the biggest pad
        order = sorted(range(len(pads)), key=lambda i: -pads[i][0].GetSize(pcbnew.F_Cu).x * pads[i][0].GetSize(pcbnew.F_Cu).y)
        tree = np.zeros((2, g.H, g.W), bool)
        first = pads[order[0]]
        for layer, m in first[2].items():
            if layer in first[1]:
                tree[layer] |= m
        todo = [pads[i] for i in order[1:]]
        new_tracks, new_vias = [], []
        self.last_cells = []
        while todo:
            blk, usable = self._blocked(code, hw)
            tsum = tree[0] | tree[1]
            heur = ndimage.distance_transform_edt(~tsum) * RES
            # nearest remaining pad first
            def dist(pe):
                c = pe[0].GetPosition()
                ix, iy = g.cell(tomm(c.x), tomm(c.y))
                return heur[iy, ix]
            todo.sort(key=dist)
            pe = todo.pop(0)
            src = self._pad_cells(pe, blk)
            goal = tree & ~np.stack(blk)
            if not goal.any():
                goal = tree
            mult = self._mult(name)
            if soft and self._soft is not None:
                others, hist, pres, _ = self._soft
                d = [ndimage.distance_transform_edt(~others[layer]) * RES if others[layer].any()
                     else np.full((g.H, g.W), 1e9) for layer in (0, 1)]
                for layer in (0, 1):
                    near = d[layer] < hw + CLR + RES * 0.5
                    mult[layer] += near * (1.0 + pres * 8.0) + hist[layer] * 2.0
            path, n = self._astar(code, blk, usable, src, goal, heur, mult)
            if path is None:
                return False, new_tracks, new_vias
            # commit path to grid + tree
            self.last_cells += path
            segs, vias = self._commit(path, code, width, pe[0])
            new_tracks += segs
            new_vias += vias
            for layer, m in pe[2].items():
                if layer in pe[1]:
                    tree[layer] |= m
            for (layer, iy, ix) in path:
                tree[layer, iy, ix] = True
            for vi in vias:
                ix, iy = g.vias[vi][:2]
                tree[0, iy, ix] = tree[1, iy, ix] = True
        return True, new_tracks, new_vias

    def _commit(self, path, code, width, start_pad):
        g = self.g
        pts = [(s[0], g.x0 + s[2] * RES, g.y0 + s[1] * RES) for s in path]
        # split into per-layer runs; layer change = via
        segs, vias = [], []
        run = [pts[0]]
        for p in pts[1:]:
            if p[0] != run[-1][0]:
                vi = next(i for i, v in enumerate(g.vias)
                          if abs(v[2] - p[1]) < RES / 2 + 1e-6 and abs(v[3] - p[2]) < RES / 2 + 1e-6)
                vias.append(vi)
                segs += self._runsegs(run, width)
                run = [p]
            else:
                run.append(p)
        segs += self._runsegs(run, width)
        # tie the path start to the pad centre (stays inside the pad)
        c = start_pad.GetPosition()
        first = pts[0]
        segs.insert(0, (first[0], (tomm(c.x), tomm(c.y)), (first[1], first[2]), min(width, self._pad_min(start_pad))))
        # a free via the path passes close to becomes part of this net (its barrel is real
        # copper); tie it to the track explicitly so it is never left floating next to it
        near = {}
        for (layer, iy, ix) in path:
            x, y = g.x0 + ix * RES, g.y0 + iy * RES
            for vi, v in enumerate(g.vias):
                if vi in vias or g.via_net.get(vi) not in (None, code):
                    continue
                d = math.hypot(v[2] - x, v[3] - y)
                if d < VIA_R + width / 2 + CLR and (vi not in near or d < near[vi][0]):
                    near[vi] = (d, layer, x, y)
        for vi, (d, layer, x, y) in near.items():
            vias.append(vi)
            if d > 1e-6:
                segs.append((layer, (x, y), (g.vias[vi][2], g.vias[vi][3]), min(width, 0.25)))
        for layer, a, b, w, in [(s[0], s[1], s[2], s[3]) for s in segs]:
            g.put(layer, g._mask_seg(a, b, w), code)
        for vi in vias:
            g.via_net[vi] = code
            x, y = g.vias[vi][2:]
            m = g._mask_circle(x, y, VIA_R)
            for layer in (0, 1):
                g.put(layer, m, code)
        return [(s[0], s[1], s[2], s[3], code) for s in segs], vias

    @staticmethod
    def _pad_min(pad):
        s = pad.GetSize(pcbnew.F_Cu)
        return max(0.15, min(tomm(s.x), tomm(s.y)))

    @staticmethod
    def _runsegs(run, width):
        """Collapse a grid path into straight segments."""
        if len(run) < 2:
            return []
        out = []
        a = run[0]
        prev = run[0]
        pdir = None
        for p in run[1:]:
            d = (round((p[1] - prev[1]) / RES), round((p[2] - prev[2]) / RES))
            if pdir is not None and d != pdir:
                out.append((a[0], (a[1], a[2]), (prev[1], prev[2]), width))
                a = prev
            pdir = d
            prev = p
        out.append((a[0], (a[1], a[2]), (prev[1], prev[2]), width))
        return out

    # --------------------------------------------------------------- whole board
    def _order(self):
        nets = [n for n in self.pads if len(self.pads[n]) > 1]
        span = {}
        for n in nets:
            xs = [tomm(p[0].GetPosition().x) for p in self.pads[n]]
            ys = [tomm(p[0].GetPosition().y) for p in self.pads[n]]
            span[n] = (max(xs) - min(xs)) + (max(ys) - min(ys))
        byk = {key(n): n for n in nets}
        return [byk[k] for k in PRIORITY if k in byk] + sorted(
            [n for n in nets if key(n) not in PRIORITY], key=lambda n: (-WIDTH.get(key(n), 0), span[n]))

    def run(self, iters=int(os.environ.get("ROUTE_ITERS", "30"))):
        """Negotiated-congestion routing (PathFinder): other nets' copper is a cost, not a
        wall, and cells that stay contested get more expensive every round."""
        order = self._order()
        g = self.g
        fixed_own = g.own.copy()
        hist = np.zeros((2, g.H, g.W), np.float32)
        routes = {}                  # net -> (segs, vias, copper mask [2,H,W], width)
        pres = 0.5
        for it in range(iters):
            self.pending = set(order)
            for n in order:
                # this net's view: fixed obstacles only; other nets' copper as cost
                g.own[:] = fixed_own
                g.via_net = {}
                others = np.zeros((2, g.H, g.W), bool)
                for m, r_ in routes.items():
                    if m != n:
                        others |= r_[2]
                w = WIDTH.get(key(n), DEFAULT_W)
                res = None
                for ww in [w] + [x for x in FALLBACK_W if x < w]:
                    self._soft = (others, hist, pres, ww)
                    ok, segs, vias = self.route_net(n, ww, soft=True)
                    if ok:
                        res = (segs, vias, ww)
                        break
                self.pending.discard(n)
                if res is None:
                    routes.pop(n, None)
                    continue
                segs, vias, ww = res
                cells = list(self.last_cells)
                cm = np.zeros((2, g.H, g.W), bool)
                for layer, a_, b_, wseg, code in segs:
                    cm[layer] |= g._mask_seg(a_, b_, wseg)
                for vi in vias:
                    x, y = g.vias[vi][2:]
                    m = g._mask_circle(x, y, VIA_R)
                    cm[0] |= m
                    cm[1] |= m
                routes[n] = (segs, vias, cm, ww, cells)
            # find conflicts: copper of two nets closer than the clearance
            conflicts, hot = self._conflicts(routes)
            missing = [n for n in order if n not in routes]
            print(f"iteration {it + 1}: {len(routes)}/{len(order)} routed, {len(conflicts)} nets in conflict {sorted(conflicts) if len(conflicts) < 16 else ''}"
                  f'{", unroutable: " + str(missing) if missing else ""}')
            if not conflicts and not missing:
                break
            hist += hot.astype(np.float32) * 1.0
            pres *= 1.5
        # legalise: drop conflicting nets (worst first) and reroute them strictly
        g.own[:] = fixed_own
        g.via_net = {}
        conflicts, _ = self._conflicts(routes)
        keep = {n: r for n, r in routes.items() if n not in conflicts}
        for n, (segs, vias, cm, w, cells) in keep.items():
            code = self.code(n)
            for layer, a_, b_, wseg, c in segs:
                g.put(layer, g._mask_seg(a_, b_, wseg), code)
            for vi in vias:
                g.via_net[vi] = code
                x, y = g.vias[vi][2:]
                m = g._mask_circle(x, y, VIA_R)
                g.put(0, m, code)
                g.put(1, m, code)
        self._soft = None
        redo = [n for n in order if n not in keep]
        self.pending = set(redo)
        self.failed = []
        for n in redo:
            ok = False
            for ww in [WIDTH.get(key(n), DEFAULT_W)] + [x for x in FALLBACK_W if x < WIDTH.get(key(n), DEFAULT_W)]:
                save = (g.own.copy(), dict(g.via_net))
                ok, segs, vias = self.route_net(n, ww)
                if ok:
                    keep[n] = (segs, vias, None, ww, None)
                    break
                g.own[:] = save[0]
                g.via_net = save[1]
            self.pending.discard(n)
            if not ok:
                self.failed.append(n)
        self.tracks = [s for n in keep for s in keep[n][0]]
        self.used_vias = {vi: n for n in keep for vi in keep[n][1]}
        print(f'final: {len(keep)}/{len(order)} routed; failed: {self.failed}')
        return self.failed

    def _conflicts(self, routes):
        """Nets whose centreline comes closer to another net's copper than the router's own
        clearance rule allows (same test the router uses for hard obstacles)."""
        g = self.g
        conflicts = set()
        hot = np.zeros((2, g.H, g.W), bool)
        allcm = np.zeros((2, g.H, g.W), np.int16)
        for r_ in routes.values():
            allcm += r_[2]
        for n, (segs, vias, cm, w, cells) in routes.items():
            if not cells:
                continue
            others = (allcm - cm) > 0
            thr = w / 2 + CLR + RES * 0.5 - 1e-6
            for layer in (0, 1):
                if not others[layer].any():
                    continue
                d = ndimage.distance_transform_edt(~others[layer]) * RES
                pts = [(y, x) for (L, y, x) in cells if L == layer]
                if not pts:
                    continue
                ys, xs = np.array(pts).T
                bad = d[ys, xs] < thr
                if bad.any():
                    conflicts.add(n)
                    hot[layer, ys[bad], xs[bad]] = True
        st = ndimage.generate_binary_structure(2, 1)
        for layer in (0, 1):
            hot[layer] = ndimage.binary_dilation(hot[layer], st, iterations=3)
        return conflicts, hot


def route_board(board, fps, vg, P):
    import build_pcb
    r = Router(board, vg)
    failed = r.run()
    for layer, a, b, w, code in r.tracks:
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(mm(b[0]), mm(b[1])))
        t.SetWidth(mm(w))
        t.SetLayer(pcbnew.F_Cu if layer == 0 else pcbnew.B_Cu)
        t.SetNet(build_pcb.net(board, r.netname[code]))
        board.Add(t)
    used = {}
    for vi, n in r.used_vias.items():
        x, y = r.g.vias[vi][2:]
        used[(x, y)] = n
    build_pcb.viagrid(board, used)
    r.board_vias = used
    return r


def _poly_raster(g, sps, idx):
    """Raster one outline (minus its holes) of a SHAPE_POLY_SET."""
    o = sps.Outline(idx)
    m = g._mask_poly([(tomm(o.CPoint(j).x), tomm(o.CPoint(j).y)) for j in range(o.PointCount())])
    for h in range(sps.HoleCount(idx)):
        ho = sps.Hole(idx, h)
        m &= ~g._mask_poly([(tomm(ho.CPoint(j).x), tomm(ho.CPoint(j).y)) for j in range(ho.PointCount())])
    return m


def add_gnd_stubs(board, r, items):
    """Tie GND copper the pours leave stranded (pads, or F.Cu pour islands) to the main F.Cu
    pour or to a free Viagrid via (on GND, stitched to both pours).
    items: [('pad', ref, num)] or [('zone', x_abs, y_abs)]."""
    import build_pcb
    g = r.g
    code = r.code(build_pcb.GND)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    # F.Cu pour outlines; the main one is the largest
    fpoly = None
    for z in board.Zones():
        if z.GetLayer() == pcbnew.F_Cu:
            fpoly = z.GetFilledPolysList(pcbnew.F_Cu)
    outlines = []
    if fpoly is not None:
        for i in range(fpoly.OutlineCount()):
            outlines.append((_poly_raster(g, fpoly, i), i))
        outlines.sort(key=lambda o: -o[0].sum())
    main = outlines[0][0] if outlines else np.zeros((g.H, g.W), bool)
    taken = set(r.used_vias)
    for it in items:
        if it[0] == 'pad':
            pad = next((p for p in fps[it[1]].Pads() if p.GetNumber() == it[2]), None)
            if pad is None or not pad.IsOnLayer(pcbnew.F_Cu):
                continue
            srcmask = np.zeros((g.H, g.W), bool)
            for poly in pad_polys(pad, pcbnew.F_Cu):
                srcmask |= g._mask_poly(poly)
            label, tie = f'{it[1]}.{it[2]}', pad
        else:
            ix, iy = g.cell(it[1], it[2])
            srcmask = next((m for m, _ in outlines[1:] if m[max(iy - 3, 0):iy + 4, max(ix - 3, 0):ix + 4].any()), None)
            if srcmask is None:
                continue
            label, tie = f'pour island at ({it[1] - g.x0:.1f}, {it[2] - g.y0:.1f})', None
        done = False
        for w in (0.3, 0.25, 0.2):
            blk, usable = r._blocked(code, w / 2)
            goal = np.zeros((2, g.H, g.W), bool)
            goal[0] = main & ~blk[0] & ~srcmask
            for vi in usable:
                if vi not in taken:
                    ix, iy = g.vias[vi][:2]
                    goal[0, iy, ix] = True
            heur = ndimage.distance_transform_edt(~goal[0]) * RES
            src = [(0, y, x) for y, x in zip(*np.nonzero(srcmask & ~blk[0]))]
            if not src or not goal.any():
                continue
            mult = np.ones((2, g.H, g.W), np.float32)
            mult[1] = 50.0                                       # stay on F.Cu
            path, n = r._astar(code, blk, [], src, goal, heur, mult)
            if path is None:
                continue
            if tie is not None:
                segs, vias = r._commit(path, code, w, tie)
            else:
                segs, vias = r._commit(path, code, w, _Pt(path[0], g))
            for layer, a, b_, ww, c in segs:
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(pcbnew.VECTOR2I(mm(a[0]), mm(a[1])))
                t.SetEnd(pcbnew.VECTOR2I(mm(b_[0]), mm(b_[1])))
                t.SetWidth(mm(ww))
                t.SetLayer(pcbnew.F_Cu if layer == 0 else pcbnew.B_Cu)
                t.SetNet(build_pcb.net(board, build_pcb.GND))
                board.Add(t)
            done = True
            break
        if not done:
            print(f'   could not tie {label} to GND')


class _Pt:
    """Minimal stand-in for a pad (position + size) when a stub starts in a pour island."""
    def __init__(self, cell, g):
        self._p = pcbnew.VECTOR2I(mm(g.x0 + cell[2] * RES), mm(g.y0 + cell[1] * RES))

    def GetPosition(self):
        return self._p

    def GetSize(self, layer):
        return pcbnew.VECTOR2I(mm(0.3), mm(0.3))
