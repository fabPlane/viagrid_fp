"""Minimal KiCad S-expression reader/writer."""
import re

_TOK = re.compile(r'\s*(?:(\()|(\))|("(?:[^"\\]|\\.)*")|([^\s()"]+))')


class Sym(str):
    """Unquoted atom."""


def parse(text):
    stack, cur = [], []
    pos = 0
    while True:
        m = _TOK.match(text, pos)
        if not m or m.end() == pos:
            break
        pos = m.end()
        o, c, q, a = m.groups()
        if o:
            stack.append(cur)
            cur = []
        elif c:
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif q is not None:
            cur.append(q[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(a))
    return cur[0]


def dump(node, indent=0):
    if not isinstance(node, list):
        if isinstance(node, Sym):
            return str(node)
        if isinstance(node, (int, float)):
            return fmt_num(node)
        return '"' + str(node).replace('\\', '\\\\').replace('"', '\\"') + '"'
    simple = all(not isinstance(x, list) for x in node)
    if simple:
        return '(' + ' '.join(dump(x) for x in node) + ')'
    pad = '  ' * (indent + 1)
    parts = [dump(node[0])]
    for x in node[1:]:
        parts.append('\n' + pad + dump(x, indent + 1) if isinstance(x, list) else dump(x))
    return '(' + ' '.join(parts) + ')'


def fmt_num(v):
    s = f'{v:.4f}'.rstrip('0').rstrip('.')
    return '0' if s == '-0' else s


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


def find1(node, key):
    r = find(node, key)
    return r[0] if r else None
