"""Load symbols from the KiCad stock libraries (resolving `extends`) and list pins."""
import copy
import os
from sexpr import parse, find, find1, Sym

LIBDIR = os.environ.get('KICAD_SYMBOL_DIR', '/usr/share/kicad/symbols')
_cache = {}


def _lib(name):
    if name not in _cache:
        with open(os.path.join(LIBDIR, name + '.kicad_sym')) as f:
            _cache[name] = parse(f.read())
    return _cache[name]


def load(libid):
    """Return a lib_symbols entry named 'Lib:Name', flattened (no extends)."""
    lib, name = libid.split(':')
    root = _lib(lib)
    syms = {s[1]: s for s in find(root, 'symbol')}
    s = copy.deepcopy(syms[name])
    ext = find1(s, 'extends')
    if ext:
        base = copy.deepcopy(syms[ext[1]])
        # derived symbol overrides properties; graphics/pins come from base
        props = {p[1]: p for p in find(s, 'property')}
        out = [Sym('symbol'), name]
        for x in base[2:]:
            if isinstance(x, list) and x[0] == 'property' and x[1] in props:
                out.append(props.pop(x[1]))
            elif isinstance(x, list) and x[0] == 'symbol':
                x[1] = x[1].replace(ext[1], name, 1)
                out.append(x)
            else:
                out.append(x)
        out.extend(props.values())
        s = out
    s[1] = libid
    return s


def pins(sym):
    """[(number, name, etype, x, y, angle)] for unit 1 / common units."""
    res = []
    for sub in find(sym, 'symbol'):
        unit = sub[1].rsplit('_', 2)[-2]
        if unit not in ('0', '1'):
            continue
        for p in find(sub, 'pin'):
            at = find1(p, 'at')
            name = find1(p, 'name')[1]
            num = find1(p, 'number')[1]
            res.append((num, name, str(p[1]), float(at[1]), float(at[2]), int(float(at[3]))))
    return res


if __name__ == '__main__':
    import sys
    for a in sys.argv[1:]:
        s = load(a)
        fp = [p[2] for p in find(s, 'property') if p[1] == 'Footprint']
        print('==', a, fp)
        for p in sorted(pins(s), key=lambda p: (len(p[0]), p[0])):
            print('   ', *p)
