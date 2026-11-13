"""S01 — Title. Photo board, slow drift in, title over a dimmed board."""
from otter.anim import prog, window
from otter.camera import CamPath
from otter.config import C
from otter.scene import Scene
from otter import widgets as wg


class Title(Scene):
    name = 's01_title'
    title = 'Title'
    duration = 10.0
    cam = CamPath((0, 'WIDE'), (10, 'FULL'), e='smooth')
    captions = [
        (6.0, 9.9, 'An 8-bit ISA card that turns an SD card into an ordinary DOS drive.'),
    ]

    def draw(self, f, t):
        f.board(photo=1.0)
        f.dim(0.74 * (1 - prog(t, 5.6, 7.2)))

    def overlay(self, f, t):
        a = window(t, 1.4, 5.5, 1.0, 0.8)
        ctx = f.ctx
        from otter.draw import text
        from otter.config import W, H
        text(ctx, 'Slot-otter Classic', W / 2, H / 2 - 40 + (1 - a) * 10, 92, C.text, a, align='center', bold=True)
        ctx.rectangle(W / 2 - 70 * a, H / 2 - 4, 140 * a, 4)
        ctx.set_source_rgba(*C.data[:3], a)
        ctx.fill()
        text(ctx, 'How a byte reaches an SD card: 14 logic chips, eight clocks at a time.', W / 2, H / 2 + 52,
             32, (0.79, 0.83, 0.89, 1), a, align='center')

    def post(self, f, t):
        f.fade_black(1 - prog(t, 0.0, 1.6, 'smooth'))


SCENE = Title()
