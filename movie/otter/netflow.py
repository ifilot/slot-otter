"""Signal propagation along the real copper of a net.

For a source pad, Dijkstra over the net's track segments gives the copper
distance to every point. A propagation 'front' (mm of copper travelled) can
then light the net progressively, or a short comet can run along it.
"""
from __future__ import annotations

import heapq
import math
from collections import defaultdict


def _key(x, y):
    return (round(x, 2), round(y, 2))


def _point_on_segment(px, py, s, tol=0.02):
    dx, dy = s.x1 - s.x0, s.y1 - s.y0
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return None
    u = ((px - s.x0) * dx + (py - s.y0) * dy) / L2
    if u <= 1e-6 or u >= 1 - 1e-6:
        return None
    qx, qy = s.x0 + u * dx, s.y0 + u * dy
    return u if math.hypot(px - qx, py - qy) < tol else None


class NetGraph:
    def __init__(self, board, net):
        self.net = net
        self.board = board
        self.pads = board.net_pads(net)
        segs = [s for s in board.net_segments(net) if s.layer in ('F.Cu', 'B.Cu', 'In1.Cu', 'In2.Cu')]

        # Split segments at T-junctions (endpoints landing mid-segment).
        ends = [(s.x0, s.y0) for s in segs] + [(s.x1, s.y1) for s in segs]
        split = []
        for s in segs:
            cuts = sorted({u for (px, py) in ends for u in [_point_on_segment(px, py, s)] if u is not None})
            pts = [(s.x0, s.y0)] + [(s.x0 + u * (s.x1 - s.x0), s.y0 + u * (s.y1 - s.y0)) for u in cuts] + [(s.x1, s.y1)]
            for p, q in zip(pts, pts[1:]):
                split.append((p, q, s.width, s.layer))
        self.edges = []          # (key_a, key_b, (xa, ya), (xb, yb), width, layer, length)
        self.adj = defaultdict(list)
        for p, q, w, lay in split:
            a, b = _key(*p), _key(*q)
            L = math.hypot(q[0] - p[0], q[1] - p[1])
            idx = len(self.edges)
            self.edges.append((a, b, p, q, w, lay, L))
            self.adj[a].append((b, L, idx))
            self.adj[b].append((a, L, idx))

        # Pads: node at the pad centre, joined to every track end inside it.
        self.pad_key = {}
        nodes = list(self.adj.keys())
        for pad in self.pads:
            pk = ('pad', pad.ref, pad.name)
            self.pad_key[(pad.ref, pad.name)] = pk
            c = _key(pad.x, pad.y)
            for n in nodes:
                if pad.contains(n[0], n[1], tol=0.1):
                    L = math.hypot(n[0] - pad.x, n[1] - pad.y)
                    idx = len(self.edges)
                    self.edges.append((pk, n, (pad.x, pad.y), n, 0.3, 'pad', L))
                    self.adj[pk].append((n, L, idx))
                    self.adj[n].append((pk, L, idx))
            if c not in self.adj:
                self.adj[pk]  # ensure exists

    def distances(self, sources):
        dist = {}
        pq = []
        for s in sources:
            k = self.pad_key[s] if isinstance(s, tuple) and len(s) == 2 and not isinstance(s[0], float) else _key(*s)
            dist[k] = 0.0
            heapq.heappush(pq, (0.0, id(k), k))
        while pq:
            d, _, u = heapq.heappop(pq)
            if d > dist.get(u, math.inf):
                continue
            for v, L, _ in self.adj[u]:
                nd = d + L
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    heapq.heappush(pq, (nd, id(v), v))
        return dist

    def path(self, a, b):
        """Polyline (list of points) along copper from pad a to pad b."""
        ka, kb = self.pad_key[a], self.pad_key[b]
        dist = {ka: 0.0}
        prev = {}
        pq = [(0.0, 0, ka)]
        cnt = 1
        while pq:
            d, _, u = heapq.heappop(pq)
            if u == kb:
                break
            if d > dist.get(u, math.inf):
                continue
            for v, L, idx in self.adj[u]:
                nd = d + L
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = (u, idx)
                    heapq.heappush(pq, (nd, cnt, v))
                    cnt += 1
        pa = self.board.pad(*a)
        pb = self.board.pad(*b)
        if kb not in prev:
            return [(pa.x, pa.y), (pb.x, pb.y)]
        pts = []
        k = kb
        while k != ka:
            u, idx = prev[k]
            e = self.edges[idx]
            p, q = (e[2], e[3]) if e[1] == k else (e[3], e[2])
            pts.append(q)
            k = u
        pts.append((pa.x, pa.y))
        pts.reverse()
        return pts


class Flow:
    """Propagation of a signal from one or more source pads over a net."""

    def __init__(self, graph: NetGraph, sources):
        self.g = graph
        self.dist = graph.distances(sources)
        reach = [d for d in self.dist.values() if d < math.inf]
        self.length = max(reach) if reach else 0.0

    def lit_spans(self, front, tail=None):
        """Yield (p, q, width, layer) sub-segments with copper distance in
        [front - tail, front] (tail None = everything behind the front)."""
        lo = -math.inf if tail is None else front - tail
        for a, b, p, q, w, lay, L in self.g.edges:
            da, db = self.dist.get(a, math.inf), self.dist.get(b, math.inf)
            if da == math.inf and db == math.inf:
                continue
            # distance at parameter u along the edge = min(da + uL, db + (1-u)L)
            # Light from each end independently.
            for d0, start, end in ((da, p, q), (db, q, p)):
                if d0 == math.inf or L <= 0:
                    continue
                u1 = min(1.0, (front - d0) / L)
                u0 = max(0.0, (lo - d0) / L) if tail is not None else 0.0
                # do not light beyond the meeting point of the two fronts
                other = db if start is p else da
                if other < math.inf:
                    umeet = clamp01((other + L - d0) / (2 * L))
                    u1 = min(u1, umeet)
                if u1 > u0:
                    yield (_lerp(start, end, u0), _lerp(start, end, u1), w, lay)

    def heads(self, front):
        """Points where the front currently is (for drawing bright heads)."""
        out = []
        for a, b, p, q, w, lay, L in self.g.edges:
            da, db = self.dist.get(a, math.inf), self.dist.get(b, math.inf)
            if da <= front < db and L > 0:
                out.append(_lerp(p, q, (front - da) / L))
            elif db <= front < da and L > 0:
                out.append(_lerp(q, p, (front - db) / L))
        return out


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _lerp(p, q, u):
    return (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)


class Polyline:
    """Arc-length parametrised polyline (for comets on a single path)."""

    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for p, q in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
        self.length = self.cum[-1]

    def at(self, d):
        d = max(0.0, min(self.length, d))
        for i in range(1, len(self.cum)):
            if d <= self.cum[i]:
                L = self.cum[i] - self.cum[i - 1]
                u = 0 if L == 0 else (d - self.cum[i - 1]) / L
                return _lerp(self.pts[i - 1], self.pts[i], u)
        return self.pts[-1]

    def sub(self, d0, d1):
        d0, d1 = max(0.0, d0), min(self.length, d1)
        if d1 <= d0:
            return []
        out = [self.at(d0)]
        for i, c in enumerate(self.cum):
            if d0 < c < d1:
                out.append(self.pts[i])
        out.append(self.at(d1))
        return out
