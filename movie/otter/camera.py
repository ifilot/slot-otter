"""Orthographic 2D camera over board millimetres.

A view is (cx, cy, w): centre in KiCad mm and the visible width in mm.
Zoom is interpolated in log space so zooming feels uniform.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .anim import ease, clamp
from .config import W, H

# Named shots, KiCad mm (y down). See SCRIPT.md, "Named camera shots".
SHOTS = {
    'FULL':   (131.0, 84.0, 186.0),
    'WIDE':   (131.0, 84.0, 215.0),
    'EDGE':   (120.0, 114.0, 80.0),
    'DECODE': (98.0, 92.0, 42.0),
    'LOGIC':  (131.0, 88.0, 46.0),
    'BUS':    (152.0, 90.0, 44.0),
    'TIMING': (126.0, 76.0, 60.0),
    'CLOCK':  (124.0, 57.0, 44.0),
    'SDSIDE': (164.0, 58.0, 36.0),
    'LEDS':   (86.0, 50.0, 18.0),
    'SHIFT':  (160.0, 74.0, 56.0),
    'READ':   (140.0, 102.0, 72.0),
}


@dataclass
class View:
    cx: float
    cy: float
    w: float

    @property
    def scale(self):          # design px per mm
        return W / self.w

    def to_screen(self, x, y):
        s = self.scale
        return (W / 2 + (x - self.cx) * s, H / 2 + (y - self.cy) * s)

    def to_world(self, sx, sy):
        s = self.scale
        return (self.cx + (sx - W / 2) / s, self.cy + (sy - H / 2) / s)

    def apply(self, ctx):
        """Set the cairo matrix so drawing happens in board mm."""
        s = self.scale
        ctx.translate(W / 2, H / 2)
        ctx.scale(s, s)
        ctx.translate(-self.cx, -self.cy)

    def world_rect(self):
        x0, y0 = self.to_world(0, 0)
        x1, y1 = self.to_world(W, H)
        return (x0, y0, x1, y1)


def shot(v):
    if isinstance(v, str):
        return View(*SHOTS[v])
    if isinstance(v, View):
        return v
    return View(*v)


def blend(a: View, b: View, u: float) -> View:
    la, lb = math.log(a.w), math.log(b.w)
    w = math.exp(la + (lb - la) * u)
    # Keep the zoom and pan coherent: pan follows the zoom so the move does
    # not swing wide when zooming in and out at the same time.
    if abs(lb - la) > 1e-6:
        k = (w - a.w) / (b.w - a.w)
    else:
        k = u
    k = clamp(0.5 * k + 0.5 * u, 0.0, 1.0)
    return View(a.cx + (b.cx - a.cx) * k, a.cy + (b.cy - a.cy) * k, w)


class CamPath:
    """CamPath((0, 'FULL'), (3, 'EDGE'), (10, 'EDGE'), (14, (100, 90, 40), 'out'))."""

    def __init__(self, *keys, e='in_out'):
        self.keys = [(k[0], shot(k[1]), k[2] if len(k) > 2 else e) for k in keys]

    def __call__(self, t) -> View:
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0, _), (t1, v1, e1) in zip(ks, ks[1:]):
            if t <= t1:
                return blend(v0, v1, ease(e1)((t - t0) / (t1 - t0)) if t1 > t0 else 1.0)
        return ks[-1][1]

    @property
    def start(self):
        return self.keys[0][1]

    @property
    def end(self):
        return self.keys[-1][1]


def drift(view: View, t: float, amount=0.004, period=23.0, t1=None, ramp=2.0) -> View:
    """Very slow breathing so static shots never look frozen. The offset is
    zero at t = 0 and (with t1 = scene duration) at t = t1, so consecutive
    scenes join without a jump."""
    env = clamp(t / ramp)
    if t1 is not None:
        env *= clamp((t1 - t) / ramp)
    env = env * env * (3 - 2 * env)
    a = 2 * math.pi * t / period
    k = amount * env
    return View(view.cx + view.w * k * math.sin(a), view.cy + view.w * k * 0.6 * math.sin(a * 0.7),
                view.w * (1 - k * 0.5 * math.sin(a * 0.5)))
