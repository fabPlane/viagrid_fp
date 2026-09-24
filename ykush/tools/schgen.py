"""Tiny KiCad 7 schematic writer.

Every pin is connected by a net label placed on the pin tip (no wires). That keeps
the generated sheet easy to diff and review. ERC treats label-on-pin as a connection.
"""
import uuid as _uuid

import kilib
from sexpr import Sym, dump

S = Sym
FONT = [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]


def uid():
    return str(_uuid.uuid4())


def eff(justify=None, hide=False):
    e = [S('effects'), [S('font'), [S('size'), 1.27, 1.27]]]
    if justify:
        e.append([S('justify')] + [S(j) for j in justify.split()])
    if hide:
        e.append(S('hide'))
    return e


def custom_ic(libid, pins_left, pins_right, pins_top=(), pins_bottom=(), footprint='',
              ref='U', value=None, desc=''):
    """Build a rectangular lib symbol. pins_*: [(number, name, etype)]."""
    name = libid.split(':')[1]
    n = max(len(pins_left), len(pins_right), 1)
    h = (n + 1) * 2.54
    w = 2.54 * max(8, (max([len(p[1]) for p in pins_left + pins_right] + [4]) + 2) // 2 * 2)
    wt = max(len(pins_top), len(pins_bottom)) * 2.54 + 5.08
    w = max(w, wt)
    top = h / 2
    top = round(top / 2.54) * 2.54
    body = [S('symbol'), f'{name}_0_1',
            [S('rectangle'), [S('start'), -w / 2, top], [S('end'), w / 2, top - h],
             [S('stroke'), [S('width'), 0.254], [S('type'), S('default')]],
             [S('fill'), [S('type'), S('background')]]]]
    pinsym = [S('symbol'), f'{name}_1_1']

    def pin(num, pname, et, x, y, ang):
        pinsym.append([S('pin'), S(et), S('line'), [S('at'), x, y, ang], [S('length'), 2.54],
                       [S('name'), pname, eff()], [S('number'), num, eff()]])

    for i, (num, pname, et) in enumerate(pins_left):
        pin(num, pname, et, -w / 2 - 2.54, top - 2.54 * (i + 1), 0)
    for i, (num, pname, et) in enumerate(pins_right):
        pin(num, pname, et, w / 2 + 2.54, top - 2.54 * (i + 1), 180)
    for i, (num, pname, et) in enumerate(pins_top):
        pin(num, pname, et, -w / 2 + 2.54 * (i + 1), top + 2.54, 270)
    for i, (num, pname, et) in enumerate(pins_bottom):
        pin(num, pname, et, -w / 2 + 2.54 * (i + 1), top - h - 2.54, 90)
    return [S('symbol'), libid, [S('in_bom'), S('yes')], [S('on_board'), S('yes')],
            [S('property'), 'Reference', ref, [S('at'), 0, top + 1.27, 0], eff()],
            [S('property'), 'Value', value or name, [S('at'), 0, top - h - 1.27, 0], eff()],
            [S('property'), 'Footprint', footprint, [S('at'), 0, 0, 0], eff(hide=True)],
            [S('property'), 'Datasheet', '', [S('at'), 0, 0, 0], eff(hide=True)],
            [S('property'), 'ki_description', desc, [S('at'), 0, 0, 0], eff(hide=True)],
            body, pinsym]


class Sheet:
    def __init__(self, project, title, paper='A2'):
        self.project = project
        self.title = title
        self.paper = paper
        self.root = uid()
        self.libs = {}
        self.items = []
        self.parts = []

    def lib(self, libid, custom=None):
        if libid not in self.libs:
            self.libs[libid] = custom if custom is not None else kilib.load(libid)
        return self.libs[libid]

    def add(self, ref, libid, value, at, nets, footprint='', fields=None, nc=(), dnp=False):
        """nets: {pin_number: net_name}. Pins listed in nc get a no-connect flag.
        Any pin not in nets/nc raises, so nothing is silently left floating."""
        sym = self.lib(libid)
        if not footprint:
            footprint = next((x[2] for x in sym if isinstance(x, list) and x[:2] == ['property', 'Footprint']), '')
        X, Y = at
        pl = kilib.pins(sym)
        nums = {p[0] for p in pl}
        missing = nums - set(nets) - set(nc)
        extra = (set(nets) | set(nc)) - nums
        if missing or extra:
            raise ValueError(f'{ref}: unassigned pins {sorted(missing)} unknown {sorted(extra)}')
        vertical2 = len(pl) == 2 and all(p[3] == 0 for p in pl)
        fx, fy, fj = (2.54, 1.27, 'left') if vertical2 else (0, 3, None)
        if ref.startswith('#'):
            fx, fy, fj = 0, 3, None
        inst = [S('symbol'), [S('lib_id'), libid], [S('at'), X, Y, 0], [S('unit'), 1],
                [S('in_bom'), S('yes')], [S('on_board'), S('yes')], [S('dnp'), S('yes' if dnp else 'no')],
                [S('uuid'), uid()],
                [S('property'), 'Reference', ref, [S('at'), X + fx, Y - fy, 0], eff(fj)],
                [S('property'), 'Value', value, [S('at'), X + fx, Y + fy, 0], eff(fj)],
                [S('property'), 'Footprint', footprint, [S('at'), X, Y, 0], eff(hide=True)]]
        for k, v in (fields or {}).items():
            inst.append([S('property'), k, v, [S('at'), X, Y, 0], eff(hide=True)])
        for p in pl:
            inst.append([S('pin'), p[0], [S('uuid'), uid()]])
        inst.append([S('instances'), [S('project'), self.project,
                                      [S('path'), '/' + self.root, [S('reference'), ref], [S('unit'), 1]]]])
        self.items.append(inst)
        done = set()
        for num, pname, et, px, py, ang in pl:
            x, y = round(X + px, 2), round(Y - py, 2)
            if (x, y) in done:
                continue  # stacked pins (e.g. USB-C VBUS) share one label
            done.add((x, y))
            if num in nc:
                self.items.append([S('no_connect'), [S('at'), x, y], [S('uuid'), uid()]])
            else:
                self.label(nets[num], x, y, (ang + 180) % 360)
        self.parts.append(dict(ref=ref, lib=libid, value=value, footprint=footprint,
                               fields=fields or {}, nets=nets, dnp=dnp))

    def label(self, net, x, y, ang=0):
        just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[ang]
        self.items.append([S('label'), net, [S('at'), x, y, ang], eff(just), [S('uuid'), uid()]])

    def flag(self, net, at):
        """PWR_FLAG on a net, to tell ERC the rail is driven."""
        n = len([p for p in self.parts if p['lib'] == 'power:PWR_FLAG']) + 1
        self.add(f'#FLG{n:02d}', 'power:PWR_FLAG', 'PWR_FLAG', at, {'1': net})

    def text(self, s, at, size=1.8):
        self.items.append([S('text'), s, [S('at'), at[0], at[1], 0],
                           [S('effects'), [S('font'), [S('size'), size, size]], [S('justify'), S('left')]],
                           [S('uuid'), uid()]])

    def write(self, path):
        doc = [S('kicad_sch'), [S('version'), S('20230121')], [S('generator'), S('eeschema')],
               [S('uuid'), self.root], [S('paper'), self.paper],
               [S('title_block'), [S('title'), self.title], [S('rev'), 'A'],
                [S('comment'), 1, 'Generated by tools/make_schematic.py - edit the script, not this file']],
               [S('lib_symbols')] + list(self.libs.values())]
        doc += self.items
        doc.append([S('sheet_instances'), [S('path'), '/', [S('page'), '1']]])
        with open(path, 'w') as f:
            f.write(dump(doc) + '\n')

    def nets(self):
        out = {}
        for p in self.parts:
            if p['ref'].startswith('#'):
                continue
            for pin, n in p['nets'].items():
                out.setdefault(n, []).append(f"{p['ref']}.{pin}")
        return out
