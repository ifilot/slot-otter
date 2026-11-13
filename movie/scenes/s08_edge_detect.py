"""S08 — Wait for the CPU to let go: the 74HC74 edge detector makes /CLKSTART."""
from otter.anim import prog, window, breathe
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import mix
from otter.scene import Scene
from otter import widgets as wg
from .common import sig

NEAR_VIEW = (130.0, 95.0, 60.0)
WIDE_VIEW = (126.0, 80.0, 140.0)
RELEASE = 4.3     # /SER_WR rises (16 MHz ticks); flip-flop edges at integer ticks
TICK_S = 0.62     # seconds per tick in the diagram
DIAG_T0 = 6.0


def ser_wr(m):
    return 0 if m < RELEASE else 1


def q2(m):        # strobe as seen by the second flip-flop
    return 0 if m < 6 else 1


def pulse(m):
    return ser_wr(m) and not q2(m)


class EdgeDetect(Scene):
    name = 's08_edge_detect'
    title = 'Wait for the CPU to let go'
    duration = 20.0
    cam = CamPath((0, (150.0, 90.5, 84.0)), (3.0, NEAR_VIEW), (12.4, NEAR_VIEW), (15.4, WIDE_VIEW), (20, WIDE_VIEW))
    captions = [
        (0.8, 5.8, 'Clocking must wait until the CPU releases /IOW. Only then is the byte final.'),
        (6.0, 12.4, 'Two flip-flops follow the strobe one to two ticks late. "Released" AND "not yet seen" gives a short pulse.'),
        (12.8, 19.2, 'The pulse starts at the release, lasts about 100 ns, and becomes /CLKSTART.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U13', 'U10'], 0.6 * (prog(t, 2.0, 3.5) - prog(t, 12.2, 13.2)))
        f.spotlight(['U13', 'U11', 'U2', 'U12', 'U1'], 0.55 * prog(t, 13.2, 14.8))
        clk = window(t, 4.0, 19.6, 0.6, 0.6) * breathe(t * 3, 1.0, 0.35, 0.7)
        f.net('16MHz', C.clock, clk * (1 - 0.5 * prog(t, 12.4, 13.0)), width=0.7)
        sw = 1 - prog(t, DIAG_T0 + RELEASE * TICK_S, DIAG_T0 + RELEASE * TICK_S + 0.4)
        f.net('~{SER_WR}', C.ctrl, window(t, -1, 19.6, 0.3, 0.5) * sw)
        f.outline('U13', C.focus, window(t, 4.0, 12.4, 0.5, 0.6), label='74HC74 · two D flip-flops',
                  label_side='left')
        hops = [('Net-(U13B-~{Q})', ('U13', '8'), 13.2), ('Net-(U11-Pad11)', ('U11', '11'), 14.2),
                ('Net-(U12-Pad1)', ('U2', '8'), 14.8), ('Net-(U11-Pad1)', ('U12', '2'), 15.3),
                ('~{CLKSTART}', ('U11', '3'), 15.8)]
        for net, src, t0 in hops:
            sig(f, net, src, t, t0, 19.4, speed=40)
        g = window(t, 14.4, 19.4, 0.4, 0.5)
        f.tag(*f.s.pad_xy('U2', '8'), 'OR', C.ctrl, g, dx=110, dy=0, size=20, mono=True)
        f.tag(*f.s.pad_xy('U12', '2'), 'NOT', C.ctrl, g, dx=-110, dy=0, size=20, mono=True)
        f.tag(*f.s.pad_xy('U11', '11'), 'AND', C.ctrl, window(t, 13.4, 19.4, 0.4, 0.5), dx=120, dy=40, size=20,
              mono=True)
        f.tag(*f.s.pad_xy('U11', '3'), 'AND', C.ctrl, g, dx=-130, dy=40, size=20, mono=True)
        f.tag(*f.s.pad_xy('U1', '5'), '/CLKSTART', C.ctrl, window(t, 15.8, 19.4, 0.5, 0.6), dx=-170, dy=70,
              size=22, mono=True)
        f.outline('U1', C.focus, window(t, 15.8, 19.4, 0.5, 0.6))
        f.tag(*f.s.pad_xy('U13', '2'), '/SER_WR (from /IOW)', C.ctrl, window(t, 0.8, 6.4, 0.5, 0.5), dx=-200,
              dy=-60, size=20, mono=True)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, 5.6, 12.8, 0.6, 0.6)
        cursor = (t - DIAG_T0) / TICK_S
        rows = [('16 MHz', C.clock, wg.square(1.0)),
                ('/IOW strobe', C.ctrl, ser_wr),
                ('seen by FF 2', mix(C.ctrl, C.dim_text, 0.5), q2),
                ('pulse', C.ctrl, pulse)]
        wg.timing(ctx, 1000, 170, 640, rows, -0.5, 8.5, cursor=cursor, alpha=a, row_h=58, label_w=170,
                  title='edge detector (U13 + U11)', marks=[(RELEASE, 'CPU releases', C.ctrl)])


SCENE = EdgeDetect()
