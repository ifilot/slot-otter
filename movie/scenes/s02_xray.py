"""S02 — Photo cross-fades to the x-ray board; functional blocks introduce themselves."""
from otter.anim import prog, window
from otter.camera import CamPath, drift, shot
from otter.config import C
from otter.scene import Scene
from .common import BLOCKS


class XRay(Scene):
    name = 's02_xray'
    title = 'The x-ray'
    duration = 12.0
    cam = CamPath((0, 'FULL'), (12, 'FULL'))
    captions = [
        (3.2, 9.8, 'No microcontroller, no firmware: fourteen 74-series chips, an oscillator and a regulator.'),
    ]

    def view(self, t):
        return drift(shot('FULL'), t, t1=self.duration)

    def draw(self, f, t):
        x = prog(t, 0.2, 2.8, 'smooth')
        f.board(photo=1 - x, xray=x, chip_labels=x)
        for i, (label, col, refs, anchor, side) in enumerate(BLOCKS):
            t0 = 3.0 + 0.55 * i
            a = prog(t, t0, t0 + 0.6)
            # the newest block is bright, earlier ones step back
            cur = 1.0 - 0.7 * prog(t, t0 + 0.55, t0 + 0.9)
            keep = cur * (1 - prog(t, 9.4, 10.6)) + 0.2 * prog(t, 9.4, 10.6)
            for r in refs:
                f.outline(r, C.focus, a * keep * 0.85, pad=0.5, width=1.6)
            la = window(t, t0 + 0.2, 10.4, 0.5, 0.8) * (0.55 + 0.45 * cur)
            if la > 0:
                f.later(lambda fr, label=label, anchor=anchor, side=side, la=la: self.label(fr, label, anchor, side,
                                                                                             la))

    @staticmethod
    def label(f, label, anchor, side, a):
        x0, y0, x1, y1 = f.box_s(anchor, 0.5)
        if side == 'top':
            f.pill(label, (x0 + x1) / 2, y0 - 22, 21, C.focus, a, align='center')
        elif side == 'right':
            f.pill(label, x1 + 24, (y0 + y1) / 2, 21, C.focus, a)
        else:
            f.pill(label, (x0 + x1) / 2, y1 + 22, 21, C.focus, a, align='center')


SCENE = XRay()
