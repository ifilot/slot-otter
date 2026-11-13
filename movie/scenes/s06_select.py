"""S06 — Flashback: IN 333h set the /CS latch. Stays on the logic view."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.scene import Scene
from .common import finger, sig, cpu, leds_pip

LOGIC_VIEW = (122.0, 89.5, 78.0)


class Select(Scene):
    name = 's06_select'
    title = 'Flashback: selecting the card'
    duration = 9.0
    cam = CamPath((0, LOGIC_VIEW), (9, LOGIC_VIEW))
    captions = [
        (0.4, 4.2, 'Earlier, the driver selected the card by reading port 333h.'),
        (4.4, 8.6, 'The read is just a trigger: the latch now holds /CS low.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U3', 'U5', 'U12'], 0.62)
        sig(f, '~{RD}', ('J2', finger('~{RD}')), t, 0.3, 8.4, speed=45, t_dim=3.0)
        for a in ('A0', 'A1'):
            sig(f, a, ('J2', finger(a)), t, 0.3, 8.4, speed=45, t_dim=3.0)
        sig(f, 'Net-(U3A-E)', ('U2', '3'), t, 1.2, 8.4, speed=30, t_dim=3.0)
        sig(f, '~{SDCS_RESET}', ('U3', '7'), t, 1.8, 8.4, speed=30, t_dim=4.4)
        sig(f, '~{CS}', ('U5', '8'), t, 2.6, 8.4, speed=30)
        sig(f, 'CS', ('U5', '11'), t, 2.6, 8.4, speed=30, alpha=0.7)
        sig(f, 'Net-(D1-K)', ('U12', '4'), t, 3.4, 8.4, speed=30)
        f.outline('U5', C.focus, window(t, 2.4, 8.6, 0.4, 0.5), label='/CS latch', label_side='top')
        f.tag(*f.s.pad_xy('U5', '8'), '/CS = 0, held', C.spi, window(t, 3.0, 8.6, 0.4, 0.5), dx=170, dy=90,
              size=22, mono=True)
        f.tag(*f.s.pad_xy('U3', '14'), 'A1 A0 = 11', C.addr, window(t, 0.8, 4.4, 0.4, 0.5), dx=-170, dy=50,
              size=20, mono=True)
        f.tag(*f.s.pad_xy('U3', '7'), '/SDCS_RESET', C.ctrl, window(t, 2.0, 5.0, 0.4, 0.5), dx=170, dy=60,
              size=20, mono=True)
        f.dim(0.18)          # flashback: the whole picture is quieter

    def overlay(self, f, t):
        a = window(t, 0.0, 8.8, 0.4, 0.5)
        f.pill('EARLIER  ·  IN AL, 333h', 70, 84, 24, C.spi, a, bold=True, mono=True)
        cpu(f.ctx, ['MOV DX, 333h', 'IN  AL, DX'], 1, t, 0.0, 8.8, active_t=0.3, y=124)
        leds_pip(f, t, {'D1': prog(t, 3.6, 4.0)}, window(t, 2.8, 8.8, 0.5, 0.5), rect=(60, 600, 360, 203))


SCENE = Select()
