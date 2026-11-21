"""S15 — Fourteen chips, five jobs: the five sets from S02 return, named and coloured.
As the narration names a chip (or a few), it lights in its set's colour and
gets a small label of its own; once the line is over those labels retire and
the set keeps its colour and its group pill."""
import math

from otter.anim import prog, window
from otter.camera import CamPath, drift, shot
from otter.config import C
from otter.draw import set_color
from otter import draw as draw_mod
from otter.scene import Scene
from .common import SETS

# scene time at which each set is named (matches the narration)
SET_T = [4.8, 16.4, 20.6, 27.2, 35.0]
T_ALL = 40.2       # "Fourteen chips, five jobs"

# Per set: the chips in the order the narration names them, as
# (refs, scene time of the word, label, placement). Word times are estimated
# from the narration audio (see scenes/narration.py, s15_recap).
ITEMS = [
    [(['U8'], 5.0, '688', 'above'),             # "The 688,
     (['U2'], 6.3, '32', 'right'),              #  the 32
     (['U3'], 7.3, '139', 'right'),             #  and the 139 listen to the bus ...
     (['U5'], 13.6, 'CS latch', 'right')],      #  ... a small latch next to them holds chip select."
    [(['U9'], 16.4, None, None)],
    [(['U6', 'U7'], 20.6, None, None)],
    [(['U13', 'U10'], 27.4, 'flip-flops', 'between'),     # "Two flip-flops,
     (['U4'], 28.3, 'counter', 'left'),                     #  a counter
     (['U11', 'U12', 'U1'], 29.0, 'gates', 'leaders')],    #  and a few gates make the clock"
    [(['U21'], 35.0, None, None)],
]
# the set's helpers (not logic chips): when they light
EXTRA_T = [5.0, None, None, 30.0, 35.0]          # SW1 with the 688; X1 at "... make the clock"
# when the newest set steps back to its softer level and its per-chip labels retire
SETTLE_T = [15.4, 19.8, 24.0, 34.4, 38.4]
LABEL_SIZE = 19


class Recap(Scene):
    name = 's15_recap'
    title = 'Fourteen chips, five jobs'
    duration = 45.0
    cam = CamPath((0, 'FULL'), (45, 'FULL'))

    def view(self, t):
        return drift(shot('FULL'), t, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.dim(0.35 * window(t, 0.4, 44.0, 1.0, 1.0))
        ghost = window(t, 0.6, 44.0, 0.8, 1.0)
        final = prog(t, T_ALL, T_ALL + 0.8)                     # "fourteen chips, five jobs": all bright
        for i, ((label, color, _refs, extra, anchor, side), t0) in enumerate(zip(SETS, SET_T)):
            ts = SETTLE_T[i]
            cur = 1.0 - 0.45 * prog(t, ts, ts + 0.8)            # newest set bright, then softer
            level = max(cur, final)
            for refs, tn, item_label, place in ITEMS[i]:
                on = prog(t, tn, tn + 0.5)
                pop = prog(t, tn, tn + 0.3) * (1 - prog(t, tn + 1.4, tn + 2.2))   # brief flare when named
                k = on * level
                for r in refs:
                    f.outline(r, C.focus, 0.3 * ghost * (1 - on), pad=0.5, width=1.4)
                    if k > 0:
                        f.chip_glow(r, color, 0.55 * k + 0.35 * pop)
                        f.outline(r, color, min(1.0, k + 0.3 * pop), pad=0.5, width=2.0 + 1.0 * pop)
                la = window(t, tn, ts + 0.6, 0.4, 0.6)
                if item_label and la > 0:
                    f.later(lambda fr, refs=refs, lb=item_label, place=place, color=color, la=la:
                            chip_label(fr, refs, lb, place, color, la))
            if EXTRA_T[i] is not None:
                ke = prog(t, EXTRA_T[i], EXTRA_T[i] + 0.6) * level
                for r in extra:
                    if ke > 0:
                        f.chip_glow(r, color, 0.4 * ke)
                        f.outline(r, color, 0.6 * ke, pad=0.5, width=1.6)
            on = prog(t, t0, t0 + 0.6)
            la = on * (0.6 + 0.4 * level) * window(t, t0, 44.2, 0.6, 0.8)
            if la > 0:
                f.later(lambda fr, label=label, color=color, anchor=anchor, side=side, la=la, i=i:
                        group_label(fr, i, label, color, anchor, side, la))


def group_label(f, i, label, color, anchor, side, a):
    if i == 3:
        # 'clock makers' sits above the 163, but starts right of the oscillator's outline
        x0, y0, _x1, _y1 = f.box_s(anchor, 0.5)
        f.pill(label, x0 + 10, y0 - 22, 21, color, a, align='left')
    else:
        set_label(f, label, color, anchor, side, a)


def _line(f, x0, y0, x1, y1, color, a, name):
    ctx = f.ctx
    draw_mod.log_box('line', ctx.user_to_device(x0, y0) + ctx.user_to_device(x1, y1), name, a)
    ctx.move_to(x0, y0)
    ctx.line_to(x1, y1)
    ctx.set_line_width(1.6)
    set_color(ctx, color, 0.75 * a)
    ctx.stroke()
    ctx.new_path()
    ctx.arc(x1, y1, 3.5, 0, 2 * math.pi)
    set_color(ctx, color, a)
    ctx.fill()


def chip_label(f, refs, label, place, color, a):
    """Small label for one named chip (or a few), just outside its outline."""
    boxes = [f.box_s(r, 0.5) for r in refs]
    x0, y0, x1, y1 = boxes[0]
    gap = 14
    if place == 'above':
        f.pill(label, (x0 + x1) / 2, y0 - gap - 14, LABEL_SIZE, color, a, align='center')
    elif place == 'right':
        f.pill(label, x1 + gap + 10, (y0 + y1) / 2, LABEL_SIZE, color, a, align='left')
    elif place == 'left':
        f.pill(label, x0 - gap - 28, (y0 + y1) / 2, LABEL_SIZE, color, a, align='right')
    elif place == 'between':
        # in the gap between two stacked chips, with a short tick to each
        (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = sorted(boxes, key=lambda b: b[1])
        cx, cy = (ax0 + ax1) / 2, (ay1 + by0) / 2
        x_l, y_t, x_r, y_b = _pill_box(f, label, cx, cy)
        for xx in (x_l + 14, x_r - 14):
            _line(f, xx, y_t, xx, ay1 + 1, color, a, label)
            _line(f, xx, y_b, xx, by0 - 1, color, a, label)
        f.pill(label, cx, cy, LABEL_SIZE, color, a, align='center')
    elif place == 'leaders':
        # one label in the gap between the chips, a leader line to each
        cx = (max(b[2] for b in boxes if b[0] < boxes[0][0]) + boxes[0][0]) / 2
        cy = (boxes[0][3] + min(b[1] for b in boxes if b[1] > boxes[0][3])) / 2
        x_l, y_t, x_r, y_b = _pill_box(f, label, cx, cy)
        for bx0, by0, bx1, by1 in boxes:
            if bx1 < x_l:                                   # chip to the lower left
                _line(f, x_l + 8, y_b, bx1 - 1, max(by0 + 8, y_b + 12), color, a, label)
            elif by1 < y_t - 60:                            # chip further up
                _line(f, (x_l + x_r) / 2, y_t, bx0 - 1, (by0 + by1) / 2, color, a, label)
            else:                                           # chip just above right
                _line(f, x_r - 8, y_t, bx0 - 1, by1 - 8, color, a, label)
        f.pill(label, cx, cy, LABEL_SIZE, color, a, align='center')


def _pill_box(f, label, cx, cy):
    """Plate box of a centred chip label (without drawing it)."""
    bx, y, _tw, pw, ph = f._pill_geom(label, cx, cy, LABEL_SIZE, 'center', False, True)
    return bx - 10, y - ph / 2, bx - 10 + pw, y + ph / 2


def set_label(f, label, color, anchor, side, a):
    x0, y0, x1, y1 = f.box_s(anchor, 0.5)
    if side == 'top':
        f.pill(label, (x0 + x1) / 2, y0 - 22, 21, color, a, align='center')
    elif side == 'bottom':
        f.pill(label, (x0 + x1) / 2, y1 + 22, 21, color, a, align='center')
    elif side == 'left':
        f.pill(label, x0 - 24, (y0 + y1) / 2, 21, color, a, align='right')
    else:
        f.pill(label, x1 + 24, (y0 + y1) / 2, 21, color, a)


SCENE = Recap()
