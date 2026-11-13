"""S05 — Which register? '32 qualifies the strobe, '139 decodes A1/A0."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.scene import Scene
from otter import widgets as wg
from .common import finger, sig, lit

LOGIC_VIEW = (122.0, 89.5, 78.0)
ROWS = [
    ['330h', 'read received byte', 'load byte + 8 clocks'],
    ['331h', 'read byte + 8 clocks', '8 clocks (sends FFh)'],
    ['332h', 'release /CS', '(MISO pull, unused)'],
    ['333h', 'assert /CS', '(MISO pull, unused)'],
]


class Registers(Scene):
    name = 's05_registers'
    title = "Which register? '32 + '139"
    duration = 24.0
    cam = CamPath((0, (106.0, 92.0, 64.0)), (3.2, LOGIC_VIEW), (24, LOGIC_VIEW))
    captions = [
        (1.0, 6.4, 'Both signals are active low, so an OR gate means "this card AND write".'),
        (7.0, 12.6, 'A1 and A0 select one of four actions. Reads and writes each have their own decoder.'),
        (13.0, 16.6, 'OUT 330h: load a byte and send it.'),
        (17.0, 23.4, 'A NAND latch remembers whether the SD card is selected.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U2', 'U3', 'U5'], 0.62 * prog(t, 1.5, 3.0))
        lit(f, '~{PORTSEL}', t, -1.0, 23.0, t_dim=6.6)
        sig(f, '~{WR}', ('J2', finger('~{WR}')), t, 0.8, 23.0, speed=34, t_dim=6.6)
        sig(f, 'Net-(U3B-E)', ('U2', '6'), t, 3.0, 23.0, speed=25, t_dim=12.8)
        for a in ('A0', 'A1'):
            sig(f, a, ('J2', finger(a)), t, 5.0, 23.0, speed=34, alpha=0.25, width=0.7)
        sig(f, '~{SER_WR}', ('U3', '12'), t, 13.0, 23.0, speed=30, t_dim=16.8)
        ti = window(t, 1.0, 6.6, 0.5, 0.5)
        f.tag(*f.s.pad_xy('U2', '4'), '/PORTSEL', C.ctrl, ti, dx=-170, dy=-70, size=20, mono=True)
        f.tag(*f.s.pad_xy('U2', '5'), '/IOW', C.ctrl, ti, dx=-150, dy=80, size=20, mono=True)
        tb = window(t, 7.2, 16.6, 0.5, 0.6)
        f.tag(*f.s.pad_xy('U3', '14'), 'A1 = 0, A0 = 0', C.addr, tb, dx=-190, dy=40, size=20, mono=True)
        tc = window(t, 13.2, 23.0, 0.5, 0.6)
        f.tag(*f.s.pad_xy('U3', '12'), '/SER_WR', C.ctrl, tc, dx=110, dy=-80, size=22, mono=True)
        f.outline('U2', C.focus, window(t, 0.8, 6.6, 0.5, 0.6), label='74HCT32 · OR gates', label_side='right')
        f.outline('U3', C.focus, window(t, 5.0, 16.6, 0.5, 0.6), label='74HCT139 · decoder', label_side='right')
        f.outline('U5', C.focus, window(t, 17.0, 23.4, 0.5, 0.6), label='74HC00 · /CS latch', label_side='right')

    def overlay(self, f, t):
        a = window(t, 7.0, 23.4, 0.6, 0.6)
        hl = prog(t, 13.0, 13.5) * (1 - prog(t, 17.0, 17.5))
        hl2 = prog(t, 17.0, 17.5)
        wg.table(f.ctx, 70, 130, ['port', 'IN  (read, /IOR)', 'OUT  (write, /IOW)'], ROWS, a,
                 col_w=[110, 300, 300], reveal=(t - 7.4) * 1.6,
                 highlight=(0, 2, hl) if hl >= hl2 else (3, 1, hl2), hl_color=C.ctrl)


SCENE = Registers()
