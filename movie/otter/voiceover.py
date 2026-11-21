"""Voice-over timing: stretch each scene's clock where narration needs room.

Every narration line starts at a scene time t (of the silent cut). The
segment from one line to the next must hold the spoken line plus a short
pause; where it does not, that segment of the scene plays slower. The rate
is smoothed (Gaussian, sigma ~0.4 s) so animation and camera never change
speed abruptly, and then corrected iteratively until every line fits.
The scene clock is never sped up, so the silent cut's pacing is the floor.
"""
from __future__ import annotations

import math

import numpy as np

LEAD = 0.15      # speech starts this long after the line's scene time
GAP = 0.4        # pause after a line before the next one may start
TAIL = 0.9       # pause after the last line of a scene
SIGMA = 0.4      # rate smoothing (seconds of scene time)
DS = 1 / 200     # integration step (scene seconds)


def chunk(text, limit=78):
    """Split a subtitle at sentence ends into pieces of at most ~limit chars."""
    import re
    parts = [p for p in re.split(r'(?<=[.!?])\s+', text) if p]
    out = []
    for p in parts:
        if out and len(out[-1]) + 1 + len(p) <= limit:
            out[-1] += ' ' + p
        else:
            out.append(p)
    return out


class VoTiming:
    def __init__(self, scene_duration, lines, durations):
        """lines: [(t_scene, subtitle, spoken)], durations: seconds per line."""
        self.scene_duration = scene_duration
        n = len(lines)
        s = np.arange(0.0, scene_duration + DS, DS)
        starts = [l[0] for l in lines]
        bounds = starts + [scene_duration]
        need = [LEAD + d + (TAIL if i == n - 1 else GAP) for i, d in enumerate(durations)]
        k = [max(1.0, need[i] / max(1e-3, bounds[i + 1] - bounds[i])) for i in range(n)]
        kernel_x = np.arange(-3 * SIGMA, 3 * SIGMA + DS, DS)
        kernel = np.exp(-0.5 * (kernel_x / SIGMA) ** 2)
        kernel /= kernel.sum()
        for _ in range(12):
            r = np.ones_like(s)
            for i in range(n):
                r[(s >= bounds[i]) & (s < bounds[i + 1])] = k[i]
            pad = len(kernel) // 2
            rs = np.convolve(np.pad(r, pad, mode='edge'), kernel, mode='same')[pad:-pad]
            T = np.concatenate([[0.0], np.cumsum(rs[:-1]) * DS])
            ok = True
            for i in range(n):
                t0 = np.interp(starts[i] + LEAD, s, T)
                t1 = np.interp(bounds[i + 1], s, T)
                if t1 - t0 < need[i] - LEAD - 1e-3:
                    k[i] *= (need[i] - LEAD) / max(1e-3, t1 - t0) * 1.02
                    ok = False
            if ok:
                break
        self.s, self.T = s, T
        self.duration = float(T[-1])
        self.rates = k
        self.clips = []          # (t_vo_start, line index)
        self.cues = []           # (t_vo_in, t_vo_out, subtitle) for the caption renderer
        for i, (t_line, sub, _spoken) in enumerate(lines):
            t0 = float(np.interp(t_line + LEAD, s, T))
            self.clips.append((t0, i))
            if not sub:
                continue
            nxt = float(np.interp(bounds[i + 1], s, T))
            end = min(nxt - 0.05, t0 + durations[i] + 0.5)
            # long lines become sentence-sized chunks timed by their share of the characters
            chunks = chunk(sub)
            total = sum(len(c) for c in chunks)
            ta = t0
            for j, c in enumerate(chunks):
                tb = t0 + durations[i] * sum(len(x) for x in chunks[:j + 1]) / total
                self.cues.append((max(0.0, ta - (0.25 if j == 0 else 0.0)),
                                  end if j == len(chunks) - 1 else tb, c))
                ta = tb

    def scene_time(self, t_vo):
        return float(np.interp(t_vo, self.T, self.s))

    def vo_time(self, t_scene):
        return float(np.interp(t_scene, self.s, self.T))
