"""Time helpers: easing, keyframes, windows. Everything is a pure function of t
so any frame can be rendered on its own (parallel rendering, still previews)."""
from __future__ import annotations

import math


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, u):
    if isinstance(a, (tuple, list)):
        return type(a)(lerp(x, y, u) for x, y in zip(a, b))
    return a + (b - a) * u


# --------------------------------------------------------------------------
# Easing
# --------------------------------------------------------------------------
def linear(u):
    return u


def smooth(u):          # cubic in-out
    return u * u * (3 - 2 * u)


def smoother(u):        # quintic in-out (gentler start/stop)
    return u * u * u * (u * (u * 6 - 15) + 10)


def ease_out(u):
    return 1 - (1 - u) ** 3


def ease_in(u):
    return u ** 3


def ease_out_back(u, s=1.4):
    u -= 1
    return u * u * ((s + 1) * u + s) + 1


EASES = {
    'linear': linear, 'smooth': smooth, 'in_out': smoother, 'out': ease_out,
    'in': ease_in, 'back': ease_out_back,
}


def ease(name_or_fn):
    return EASES[name_or_fn] if isinstance(name_or_fn, str) else name_or_fn


def prog(t, t0, t1, e='in_out'):
    """0 before t0, 1 after t1, eased in between."""
    if t1 <= t0:
        return 1.0 if t >= t0 else 0.0
    return ease(e)(clamp((t - t0) / (t1 - t0)))


def window(t, t0, t1, fade_in=0.5, fade_out=0.5, e='smooth'):
    """Opacity envelope: fades in at t0, out at t1 (t1 = end of fade-out)."""
    if t < t0 or t > t1:
        return 0.0
    a = prog(t, t0, t0 + fade_in, e) if fade_in > 0 else 1.0
    b = 1.0 - prog(t, t1 - fade_out, t1, e) if fade_out > 0 else 1.0
    return min(a, b)


def pulse(t, period, duty=0.5):
    return 1.0 if (t % period) < period * duty else 0.0


def breathe(t, period=2.0, lo=0.6, hi=1.0):
    return lo + (hi - lo) * (0.5 - 0.5 * math.cos(2 * math.pi * t / period))


class Keys:
    """Piecewise keyframes: Keys((0, v0), (2, v1), (5, v2, 'out')).

    The optional third element is the easing used to arrive at that key.
    Values may be floats or tuples. Before the first / after the last key the
    value is held.
    """

    def __init__(self, *keys, e='in_out'):
        self.keys = sorted(((k[0], k[1], k[2] if len(k) > 2 else e) for k in keys), key=lambda k: k[0])

    def __call__(self, t):
        ks = self.keys
        if t <= ks[0][0]:
            return ks[0][1]
        for (t0, v0, _), (t1, v1, e1) in zip(ks, ks[1:]):
            if t <= t1:
                return lerp(v0, v1, ease(e1)((t - t0) / (t1 - t0)) if t1 > t0 else 1.0)
        return ks[-1][1]


class Schedule:
    """Variable-speed clock. Maps scene time to 'model' time (e.g. clock
    ticks) from a list of (t_scene, model_rate) segments, so slow motion
    and speed-ups are explicit. Rates are model units per second."""

    def __init__(self, t_start, segments):
        self.t_start = t_start
        self.segments = segments   # [(duration_s, rate), ...]

    def __call__(self, t):
        if t <= self.t_start:
            return 0.0
        tt, m = self.t_start, 0.0
        for dur, rate in self.segments:
            if t <= tt + dur:
                return m + (t - tt) * rate
            tt += dur
            m += dur * rate
        return m

    @property
    def end(self):
        return self.t_start + sum(d for d, _ in self.segments)

    def scene_time(self, model):
        """Inverse: scene time at which the model clock reaches `model`."""
        tt, m = self.t_start, 0.0
        for dur, rate in self.segments:
            if rate > 0 and model <= m + dur * rate:
                return tt + (model - m) / rate
            tt += dur
            m += dur * rate
        return tt
