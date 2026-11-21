"""S08 — Wait for the CPU to let go: the 74HC74 edge detector makes /CLKSTART."""
from otter.anim import prog, window, breathe
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import mix, text
from otter.scene import Scene
from otter import widgets as wg
from .common import sig

NEAR_VIEW = (130.0, 95.0, 60.0)
WIDE_VIEW = (126.0, 80.0, 140.0)
RELEASE = 4.3     # /IOW rises (16 MHz ticks); flip-flop edges at integer ticks
TICK_S = 0.62     # seconds per tick in the diagram
# narration: too early 0.8, two flip-flops 9.0, start signal 18.6
T_FF, T_START = 9.0, 18.6
DIAG_T0 = 9.6
END = 21.9


def ser_wr(m):
    return 0 if m < RELEASE else 1


def q2(m):        # strobe as seen by the second flip-flop
    return 0 if m < 6 else 1


def pulse(m):
    return ser_wr(m) and not q2(m)


class EdgeDetect(Scene):
    name = 's08_edge_detect'
    title = 'Waiting for the CPU to let go'
    duration = 22.5
    cam = CamPath((0, (150.0, 90.5, 84.0)), (3.0, NEAR_VIEW), (17.6, NEAR_VIEW), (20.4, WIDE_VIEW),
                  (22.5, WIDE_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U13', 'U10'], 0.6 * (prog(t, 2.0, 3.5) - prog(t, 17.4, 18.4)))
        f.spotlight(['U13', 'U11', 'U2', 'U12', 'U1'], 0.55 * prog(t, 18.4, 20.0))
        clk = window(t, T_FF - 1.0, END, 0.6, 0.6) * breathe(t * 3, 1.0, 0.35, 0.7)
        f.net('16MHz', C.clock, clk * (1 - 0.5 * prog(t, T_START - 0.4, T_START + 0.2)), width=0.7)
        sw = 1 - prog(t, DIAG_T0 + RELEASE * TICK_S, DIAG_T0 + RELEASE * TICK_S + 0.4)
        # while the CPU still holds /IOW low, the net throbs gently (the frame is not dead)
        hold = 1 - prog(t, T_FF - 0.6, T_FF)
        throb = 1 - hold * (1 - breathe(t, 1.6, 0.55, 1.0))
        f.net('~{SER_WR}', C.ctrl, window(t, -1, END, 0.3, 0.5) * sw * throb)
        f.outline('U13', C.focus, window(t, T_FF, T_START - 0.6, 0.5, 0.6), label='two flip-flops',
                  label_side='left')
        hops = [('Net-(U13B-~{Q})', ('U13', '8'), T_START), ('Net-(U11-Pad11)', ('U11', '11'), T_START + 0.6),
                ('Net-(U12-Pad1)', ('U2', '8'), T_START + 1.0), ('Net-(U11-Pad1)', ('U12', '2'), T_START + 1.4),
                ('~{CLKSTART}', ('U11', '3'), T_START + 1.8)]
        # the pulse path stays lit to the cut; s09 picks it up at ~CLKSTART
        for net, src, t0 in hops:
            sig(f, net, src, t, t0, None, speed=40)
        hold_end = self.duration + 1.0
        f.tag(*f.s.pad_xy('U1', '5'), 'start pulse', C.ctrl, window(t, T_START + 0.8, hold_end, 0.5, 0.6), dx=-170,
              dy=70, size=22)
        f.outline('U1', C.focus, window(t, T_START + 0.8, hold_end, 0.5, 0.6))
        f.tag(*f.s.pad_xy('U13', '2'), '/IOW still low', C.ctrl, window(t, 0.8, T_FF, 0.5, 0.5),
              dx=-190, dy=40, size=20)

    def overlay(self, f, t):
        ctx = f.ctx
        # opening: /IOW held low, the cursor crawls while the 165 keeps loading
        ha = window(t, 1.2, T_FF + 0.2, 0.6, 0.6)
        if ha > 0:
            wg.timing(ctx, 1000, 170, 640, [('/IOW', C.ctrl, lambda m: 0)], 0.0, 8.0, cursor=min(8.0, t - 1.2),
                      alpha=ha, row_h=58, label_w=170, title='the CPU is still writing', mark_space=True)
            text(ctx, 'meanwhile the 165 keeps loading: it cannot shift yet', 1170, 252, 18, C.dim_text,
                 ha * prog(t, 2.2, 2.8), italic=True)
        a = window(t, T_FF - 0.2, T_START, 0.6, 0.6)
        cursor = (t - DIAG_T0) / TICK_S
        rows = [('16 MHz', C.clock, wg.square(1.0)),
                ('/IOW', C.ctrl, ser_wr),
                ('seen by FF 2', mix(C.ctrl, C.dim_text, 0.5), q2),
                ('pulse', C.ctrl, pulse)]
        wg.timing(ctx, 1000, 170, 640, rows, -0.5, 8.5, cursor=cursor, alpha=a, row_h=58, label_w=170,
                  title='waiting for /IOW to end', marks=[(RELEASE, 'CPU lets go', C.ctrl)])


SCENE = EdgeDetect()
