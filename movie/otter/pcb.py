"""Minimal KiCad 7-10 .kicad_pcb reader for the movie.

Extracts what the x-ray view and the signal animations need: board outline,
footprints (position, rotation, pads, fab outline), tracks, vias and filled
zones. Coordinates are KiCad millimetres (x right, y down).
"""
from __future__ import annotations

import math
import os
import pickle
import re
from dataclasses import dataclass, field


# --------------------------------------------------------------------------
# S-expression parsing
# --------------------------------------------------------------------------
_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


def parse_sexpr(text: str):
    stack = [[]]
    for m in _TOKEN.finditer(text):
        tok = m.group(0)
        if tok == '(':
            stack.append([])
        elif tok == ')':
            node = stack.pop()
            stack[-1].append(node)
        elif tok[0] == '"':
            stack[-1].append(Str(tok[1:-1].replace('\\"', '"')))
        else:
            stack[-1].append(tok)
    return stack[0][0]


class Str(str):
    """Quoted string token (distinguishes "1" from the atom 1)."""


def head(node):
    return node[0] if isinstance(node, list) and node else None


def children(node, name):
    return [c for c in node[1:] if isinstance(c, list) and c and c[0] == name]


def child(node, name):
    for c in node[1:]:
        if isinstance(c, list) and c and c[0] == name:
            return c
    return None


def nums(node, n=None):
    vals = [float(v) for v in node[1:] if not isinstance(v, list)]
    return vals if n is None else vals[:n]


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------
@dataclass
class Pad:
    ref: str
    name: str
    x: float
    y: float
    w: float
    h: float
    angle: float          # absolute degrees (KiCad, counter-clockwise on screen)
    shape: str            # rect, roundrect, circle, oval, custom
    kind: str             # smd, thru_hole, np_thru_hole, connect
    layers: tuple
    net: str
    drill: float = 0.0

    @property
    def front(self):
        return any(l in ('F.Cu', '*.Cu') for l in self.layers)

    @property
    def back(self):
        return any(l in ('B.Cu', '*.Cu') for l in self.layers)

    def contains(self, px, py, tol=0.05):
        a = math.radians(self.angle)
        dx, dy = px - self.x, py - self.y
        lx = dx * math.cos(a) - dy * math.sin(a)
        ly = dx * math.sin(a) + dy * math.cos(a)
        return abs(lx) <= self.w / 2 + tol and abs(ly) <= self.h / 2 + tol


@dataclass
class Footprint:
    ref: str
    value: str
    lib: str
    x: float
    y: float
    angle: float
    layer: str
    pads: list = field(default_factory=list)
    fab: list = field(default_factory=list)      # list of polylines (list of (x, y))
    bbox: tuple = (0, 0, 0, 0)                   # body bbox (from fab, else pads)

    @property
    def center(self):
        x0, y0, x1, y1 = self.bbox
        return ((x0 + x1) / 2, (y0 + y1) / 2)

    def pad(self, name):
        for p in self.pads:
            if p.name == str(name):
                return p
        raise KeyError(f'{self.ref} has no pad {name}')


@dataclass
class Segment:
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    layer: str
    net: str


@dataclass
class Via:
    x: float
    y: float
    size: float
    drill: float
    net: str


@dataclass
class Zone:
    net: str
    layer: str
    polygons: list        # list of list of (x, y)


@dataclass
class Board:
    outline: list          # list of closed polylines
    bbox: tuple
    footprints: dict
    segments: list
    vias: list
    zones: list
    edge_lines: list       # raw Edge.Cuts polylines (for stroking)

    def fp(self, ref):
        return self.footprints[ref]

    def pad(self, ref, name):
        return self.footprints[ref].pad(name)

    def net_segments(self, net):
        return [s for s in self.segments if s.net == net]

    def net_pads(self, net):
        return [p for f in self.footprints.values() for p in f.pads if p.net == net]


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def rot(x, y, deg):
    """Rotate a footprint-local point the way KiCad does (y down, CCW on screen)."""
    a = math.radians(deg)
    return (x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a))


def arc_points(start, mid, end, n=24):
    (x1, y1), (x2, y2), (x3, y3) = start, mid, end
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        return [start, end]
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    a1 = math.atan2(y1 - uy, x1 - ux)
    a2 = math.atan2(y2 - uy, x2 - ux)
    a3 = math.atan2(y3 - uy, x3 - ux)

    def norm(a):
        while a < 0:
            a += 2 * math.pi
        return a
    # choose direction that passes through mid
    ccw_13 = norm(a3 - a1)
    ccw_12 = norm(a2 - a1)
    sweep = ccw_13 if ccw_12 <= ccw_13 else ccw_13 - 2 * math.pi
    return [(ux + r * math.cos(a1 + sweep * i / n), uy + r * math.sin(a1 + sweep * i / n))
            for i in range(n + 1)]


def chain(polylines, tol=0.01):
    """Join open polylines that share endpoints into longer ones."""
    lines = [list(p) for p in polylines]
    out = []
    while lines:
        cur = lines.pop(0)
        changed = True
        while changed:
            changed = False
            for i, l in enumerate(lines):
                def close(a, b):
                    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol
                if close(cur[-1], l[0]):
                    cur += l[1:]
                elif close(cur[-1], l[-1]):
                    cur += l[::-1][1:]
                elif close(cur[0], l[-1]):
                    cur = l + cur[1:]
                elif close(cur[0], l[0]):
                    cur = l[::-1] + cur[1:]
                else:
                    continue
                lines.pop(i)
                changed = True
                break
        out.append(cur)
    return out


def _graphic_polyline(g, transform=None):
    """Turn gr_/fp_ line, rect, arc, circle, poly into a polyline."""
    kind = g[0].split('_', 1)[1]
    pts = []
    if kind == 'line':
        pts = [tuple(nums(child(g, 'start'))), tuple(nums(child(g, 'end')))]
    elif kind == 'rect':
        (x0, y0), (x1, y1) = nums(child(g, 'start')), nums(child(g, 'end'))
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    elif kind == 'arc':
        pts = arc_points(tuple(nums(child(g, 'start'))), tuple(nums(child(g, 'mid'))),
                         tuple(nums(child(g, 'end'))))
    elif kind == 'circle':
        cx, cy = nums(child(g, 'center'))
        ex, ey = nums(child(g, 'end'))
        r = math.hypot(ex - cx, ey - cy)
        pts = [(cx + r * math.cos(2 * math.pi * i / 32), cy + r * math.sin(2 * math.pi * i / 32))
               for i in range(33)]
    elif kind == 'poly':
        pts = [tuple(nums(xy)) for xy in children(child(g, 'pts'), 'xy')]
        if pts:
            pts.append(pts[0])
    if transform:
        pts = [transform(*p) for p in pts]
    return pts


# --------------------------------------------------------------------------
# Loader
# --------------------------------------------------------------------------
def load(path: str, cache_dir: str | None = None) -> Board:
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        st = os.stat(path)
        key = os.path.join(cache_dir, f'pcb-{int(st.st_mtime)}-{st.st_size}.pickle')
        if os.path.exists(key):
            with open(key, 'rb') as f:
                return pickle.load(f)
    board = _load(path)
    if cache_dir:
        with open(key, 'wb') as f:
            pickle.dump(board, f)
    return board


def _net_name(node):
    n = child(node, 'net')
    if n is None:
        return ''
    # KiCad 10: (net "NAME"); older: (net 12 "NAME")
    for v in n[1:]:
        if isinstance(v, Str):
            return str(v)
    return ''


def _load(path: str) -> Board:
    with open(path, encoding='utf-8') as f:
        root = parse_sexpr(f.read())

    # Edge cuts
    edge = []
    for g in root[1:]:
        if isinstance(g, list) and g and g[0] in ('gr_line', 'gr_arc', 'gr_rect', 'gr_circle', 'gr_poly'):
            layer = child(g, 'layer')
            if layer and layer[1] == 'Edge.Cuts':
                edge.append(_graphic_polyline(g))
    outline = chain(edge)
    xs = [p[0] for l in outline for p in l]
    ys = [p[1] for l in outline for p in l]
    bbox = (min(xs), min(ys), max(xs), max(ys))

    # Footprints
    fps = {}
    for fnode in children(root, 'footprint'):
        lib = str(fnode[1])
        fx, fy, *fa = nums(child(fnode, 'at'))
        fang = fa[0] if fa else 0.0
        layer = str(child(fnode, 'layer')[1])
        ref = value = ''
        for prop in children(fnode, 'property'):
            if prop[1] == 'Reference':
                ref = str(prop[2])
            elif prop[1] == 'Value':
                value = str(prop[2])
        if not ref:  # KiCad 6 style
            for t in children(fnode, 'fp_text'):
                if t[1] == 'reference':
                    ref = str(t[2])
                elif t[1] == 'value':
                    value = str(t[2])

        def to_board(lx, ly, fx=fx, fy=fy, fang=fang):
            rx, ry = rot(lx, ly, fang)
            return (fx + rx, fy + ry)

        fp = Footprint(ref, value, lib, fx, fy, fang, layer)
        for pnode in children(fnode, 'pad'):
            name = str(pnode[1])
            kind = str(pnode[2])
            shape = str(pnode[3])
            px, py, *pa = nums(child(pnode, 'at'))
            pang = pa[0] if pa else fang
            w, h = nums(child(pnode, 'size'), 2)
            layers = tuple(str(l) for l in child(pnode, 'layers')[1:])
            drill = 0.0
            dn = child(pnode, 'drill')
            if dn is not None:
                dv = [v for v in dn[1:] if not isinstance(v, list) and v != 'oval']
                if dv:
                    drill = float(dv[0])
            bx, by = to_board(px, py)
            fp.pads.append(Pad(ref, name, bx, by, w, h, pang, shape, kind, layers, _net_name(pnode), drill))

        for g in fnode[1:]:
            if isinstance(g, list) and g and g[0] in ('fp_line', 'fp_rect', 'fp_arc', 'fp_circle', 'fp_poly'):
                lay = child(g, 'layer')
                if lay and lay[1] in ('F.Fab', 'B.Fab'):
                    fp.fab.append(_graphic_polyline(g, to_board))
        fp.fab = chain(fp.fab)
        pts = [p for l in fp.fab for p in l]
        if not pts:
            pts = [(p.x + dx, p.y + dy) for p in fp.pads for dx in (-p.w / 2, p.w / 2) for dy in (-p.h / 2, p.h / 2)]
        if pts:
            fp.bbox = (min(p[0] for p in pts), min(p[1] for p in pts),
                       max(p[0] for p in pts), max(p[1] for p in pts))
        else:
            fp.bbox = (fx, fy, fx, fy)
        key = ref if ref not in fps else f'{ref}@{fx:.1f},{fy:.1f}'
        fps[key] = fp

    # Tracks
    segs = []
    for s in children(root, 'segment'):
        (x0, y0), (x1, y1) = nums(child(s, 'start')), nums(child(s, 'end'))
        segs.append(Segment(x0, y0, x1, y1, nums(child(s, 'width'))[0], str(child(s, 'layer')[1]), _net_name(s)))
    for a in children(root, 'arc'):
        pts = arc_points(tuple(nums(child(a, 'start'))), tuple(nums(child(a, 'mid'))), tuple(nums(child(a, 'end'))), 8)
        w = nums(child(a, 'width'))[0]
        lay = str(child(a, 'layer')[1])
        for p, q in zip(pts, pts[1:]):
            segs.append(Segment(p[0], p[1], q[0], q[1], w, lay, _net_name(a)))
    vias = []
    for v in children(root, 'via'):
        x, y = nums(child(v, 'at'), 2)
        vias.append(Via(x, y, nums(child(v, 'size'))[0], nums(child(v, 'drill'))[0], _net_name(v)))

    zones = []
    for z in children(root, 'zone'):
        net = _net_name(z)
        polys = []
        for fpoly in children(z, 'filled_polygon'):
            lay = child(fpoly, 'layer')
            pts = [tuple(nums(xy)) for xy in children(child(fpoly, 'pts'), 'xy')]
            if pts:
                polys.append((str(lay[1]) if lay else '', pts))
        by_layer = {}
        for lay, pts in polys:
            by_layer.setdefault(lay, []).append(pts)
        for lay, pl in by_layer.items():
            zones.append(Zone(net, lay, pl))

    return Board(outline, bbox, fps, segs, vias, zones, edge)
