"""S02 — Photo cross-fades to the x-ray. As the narration names them, the parts
are pointed at: the fourteen logic chips, the oscillator, the regulator. Then,
while the narration promises to meet every chip, the five groups light up in
their colours with a label saying what each does (S15 returns to them)."""
from otter.anim import prog, window
from otter.camera import CamPath, drift, shot
from otter.config import C
from otter.scene import Scene
from .common import SETS, LOGIC
from .s15_recap import set_label

# scene times (match the spoken words; see scenes/narration.py)
T_CHIPS = 9.0         # "... fourteen 74-series logic chips"
CHIP_SPREAD = 1.6     # the fourteen outlines appear one after another over this long
T_OSC = 11.3          # "an oscillator"
T_REG = 12.3          # "and a voltage regulator"
T_PARTS_OFF = 17.0    # the part labels make way for the groups
# what each group does (S15 names the groups themselves)
JOBS = ['listen to the bus', 'gate to the bus', 'bytes to bits', 'make the clock', 'bridge to 3.3 V']
SET_T = [18.6 + 1.3 * i for i in range(len(SETS))]
T_OUT = 26.8          # everything fades before the cut to S03


class XRay(Scene):
    name = 's02_xray'
    title = 'The x-ray'
    duration = 28.0
    cam = CamPath((0, 'FULL'), (28, 'FULL'))

    def view(self, t):
        return drift(shot('FULL'), t, t1=self.duration)

    def draw(self, f, t):
        x = prog(t, 0.2, 2.8, 'smooth')
        f.board(photo=1 - x, xray=x, chip_labels=x)
        out = 1 - prog(t, T_OUT, T_OUT + 1.0, 'smooth')
        # -- the parts the narration names -----------------------------------
        ca = window(t, T_CHIPS, T_PARTS_OFF, 0.5, 0.8)
        if ca > 0:
            # count them: the outlines sweep across the board column by column,
            # and the pill in the margin counts along
            order = sorted(LOGIC, key=lambda r: chip_key(f, r))
            shown = 0
            for i, r in enumerate(order):
                ti = T_CHIPS + CHIP_SPREAD * i / (len(order) - 1)
                ai = prog(t, ti, ti + 0.15)
                if ai > 0:
                    f.outline(r, C.focus, ca * ai, pad=0.5, width=2.0)
                if t >= ti:
                    shown = i + 1
            if shown:
                label = '1 logic chip' if shown == 1 else f'{shown} logic chips'
                f.later(lambda fr, a=ca, label=label: fr.pill(label, 205, 540, 24, C.text, a, align='center'))
        for ref, label, side, x_label, t0 in (('X1', 'oscillator · 16 MHz', 'top-left', 330, T_OSC),
                                              ('U16', 'regulator · 3.3 V', 'right', 1560, T_REG)):
            a = window(t, t0, T_PARTS_OFF, 0.5, 0.8)
            if a > 0:
                f.chip_glow(ref, C.focus, 0.4 * a)
                f.outline(ref, C.focus, a, pad=0.6, width=2.0)
                f.later(lambda fr, ref=ref, label=label, side=side, x_label=x_label, a=a:
                        callout(fr, ref, label, side, x_label, a))
        # -- the five groups, each with its job -------------------------------
        for (_name, color, refs, extra, anchor, side), label, t0 in zip(SETS, JOBS, SET_T):
            on = prog(t, t0, t0 + 0.6) * out
            if on <= 0:
                continue
            cur = 1.0 - 0.4 * prog(t, t0 + 1.4, t0 + 2.0)       # the newest group is brightest
            for r in refs:
                f.chip_glow(r, color, 0.5 * on * cur)
                f.outline(r, color, on * cur, pad=0.5, width=2.0)
            for r in extra:
                f.chip_glow(r, color, 0.3 * on * cur)
            f.later(lambda fr, label=label, color=color, anchor=anchor, side=side, a=on * (0.6 + 0.4 * cur):
                    set_label(fr, label, color, anchor, side, a))


def chip_key(f, ref):
    """Sweep order: column by column (left to right), top to bottom within a column."""
    x0, y0, x1, y1 = f.s.fp_box(ref, 0.0)
    return (round((x0 + x1) / 20), (y0 + y1) / 2)


def callout(f, ref, label, side, x_label, a):
    """Label in the margin beside the board, with a leader line to the part's edge.
    'top-left': the leader leaves the part's top-left corner and runs up-left
    through the clear space above the parts beside it."""
    x0, y0, x1, y1 = f.s.fp_box(ref, 0.6)
    if side == 'top-left':
        sx, sy = f.sxy(x0, y0)
        f._tag(x0, y0, label, C.text, a, x_label - sx, -45, 22, False, True, True, True, 'right')
        return
    wx, wy = (x0 if side == 'left' else x1), (y0 + y1) / 2
    sx, _sy = f.sxy(wx, wy)
    f._tag(wx, wy, label, C.text, a, x_label - sx, 0, 22, False, True, True, True, None)


SCENE = XRay()
