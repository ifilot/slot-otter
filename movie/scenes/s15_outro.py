"""S15 — Outro: x-ray back to photo, end card, fade to black."""
from otter.anim import prog, window
from otter.camera import CamPath
from otter.config import C, W, H
from otter.draw import text
from otter.scene import Scene


class Outro(Scene):
    name = 's15_outro'
    title = 'Outro'
    duration = 12.0
    cam = CamPath((0, 'FULL'), (12, 'WIDE'), e='smooth')
    captions = []

    def draw(self, f, t):
        x = 1 - prog(t, 0.0, 3.0, 'smooth')
        f.board(photo=1 - x, xray=x, chip_labels=1 - prog(t, 0.0, 1.4, 'smooth'))
        f.dim(0.74 * prog(t, 3.0, 4.4))

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, 3.4, 11.0, 1.0, 0.8)
        text(ctx, 'Slot-otter', W / 2, H / 2 - 50, 92, C.text, a, align='center', bold=True)
        text(ctx, 'github.com/ifilot/slot-otter', W / 2, H / 2 + 20, 34, C.data, a, align='center', mono=True)
        text(ctx, 'Hardware CERN-OHL-S-2.0  ·  Software GPL-3.0-or-later  ·  This video CC-BY-SA-4.0', W / 2,
             H / 2 + 90, 22, (0.78, 0.82, 0.86, 1), a, align='center')

    def post(self, f, t):
        f.fade_black(prog(t, 10.4, 12.0, 'smooth'))


SCENE = Outro()
