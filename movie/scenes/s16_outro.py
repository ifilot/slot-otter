"""S16 — Outro: x-ray back to photo, end card, fade to black."""
import cairo

from otter.anim import prog
from otter.camera import CamPath
from otter.config import C, W, H
from otter.draw import text
from otter.scene import Scene


class Outro(Scene):
    name = 's16_outro'
    title = 'Outro'
    duration = 15.5
    cam = CamPath((0, 'FULL'), (15.5, 'WIDE'), e='smooth')

    def draw(self, f, t):
        x = 1 - prog(t, 0.0, 3.0, 'smooth')
        f.board(photo=1 - x, xray=x, chip_labels=1 - prog(t, 0.0, 1.4, 'smooth'))
        f.dim(0.84 * prog(t, 3.0, 4.4))

    def overlay(self, f, t):
        ctx = f.ctx
        # the end card stays up until the fade to black (post) takes it with the board
        a = prog(t, 3.4, 4.4, 'smooth')
        if a <= 0:
            return
        # a soft dark ground behind the text block, so it never sits on silkscreen or pins
        ctx.save()
        ctx.translate(W / 2, H / 2 + 15)
        ctx.scale(1.0, 0.3)
        g = cairo.RadialGradient(0, 0, 0, 0, 0, 760)
        g.add_color_stop_rgba(0.0, 0.01, 0.015, 0.03, 0.8 * a)
        g.add_color_stop_rgba(0.62, 0.01, 0.015, 0.03, 0.7 * a)
        g.add_color_stop_rgba(1.0, 0.01, 0.015, 0.03, 0.0)
        ctx.set_source(g)
        ctx.rectangle(-W, -H * 4, 2 * W, H * 8)
        ctx.fill()
        ctx.restore()
        text(ctx, 'Slot-otter', W / 2, H / 2 - 50, 92, C.text, a, align='center', bold=True)
        text(ctx, 'github.com/ifilot/slot-otter', W / 2, H / 2 + 20, 34, C.data, a, align='center', mono=True)
        text(ctx, 'Hardware CERN-OHL-S-2.0  ·  Software GPL-3.0-or-later  ·  This video CC-BY-SA-4.0', W / 2,
             H / 2 + 90, 22, (0.78, 0.82, 0.86, 1), a, align='center')

    def post(self, f, t):
        f.fade_black(prog(t, 13.9, 15.5, 'smooth'))


SCENE = Outro()
