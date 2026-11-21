"""S09 — Exactly eight clocks: the '00 latch releases the '163 counter."""
import math

from otter.anim import prog, window, breathe, Schedule
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel, glow_dot
from otter.scene import Scene
from otter import widgets as wg
from .common import sig, chain_path

CLOCK_VIEW = (118.0, 64.0, 80.0)
# narration: oscillator + counter 0.6, 0-1-0-1 9.0, stops 19.4, two edges 25.4, hook 32.6
T_RUN, T_STOP, T_EDGES, T_HOOK = 9.0, 19.4, 25.4, 32.6
# 0..15 at 1.6 ticks/s (10.4-19.8 s), so "fifteen" lands on the stop line; hold at 15
# through "...stops itself: eight clock pulses", then the clearing tick (24.5 s): silence
T_CNT = 10.4
TICKS = Schedule(T_CNT, [(15 / 1.6, 1.6), (4.225, 0.0), (0.5, 2.0)])
T15, TCLR = TICKS.scene_time(15.0), TICKS.end
END = 37.4
SCK_HOPS = [('CLK', ('U4', '14'), ('R10', '1')), ('Net-(R10-Pad2)', ('R10', '2'), ('U21', '5')),
            ('SCK_LLS', ('U21', '6'), ('J1', '5'))]


def count(m):
    if m < 0 or m >= 16:
        return 0
    return int(math.floor(m))


class Counter(Scene):
    name = 's09_counter'
    title = 'Exactly eight clocks'
    duration = 38.0
    cam = CamPath((0, (126.0, 80.0, 140.0)), (3.0, CLOCK_VIEW), (38, CLOCK_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U4', 'U1', 'X1'], 0.6 * prog(t, 1.5, 3.0))
        m = TICKS(t)
        running = T_CNT <= t < TCLR
        c = count(m)
        sig(f, '~{CLKSTART}', ('U11', '3'), t, 0.0, 2.0, speed=50)
        run = prog(t, 1.4, 1.8) * (1 - prog(t, T15 + 0.9, T15 + 1.2))
        f.net('Net-(U4-~{MR})', C.ctrl, run)
        f.tag(*f.s.pad_xy('U4', '1'), 'run', C.ctrl, window(t, 1.6, T15 + 1.2, 0.4, 0.4), dx=-130,
              dy=-60, size=20)
        f.net('16MHz', C.clock, window(t, 2.0, END, 0.6, 0.6) * breathe(t * 3, 1.0, 0.35, 0.7), width=0.7)
        f.net('CLK', C.clock, (1.0 if (c & 1) and running else 0.0) * window(t, 9.4, TCLR + 0.4, 0.1, 0.2))
        tc = window(t, T15, TCLR, 0.2, 0.15)
        sig(f, 'CLKSTOP', ('U4', '15'), t, T15, TCLR + 0.2, speed=40)
        sig(f, '~{CLKSTOP}', ('U1', '8'), t, T15 + 0.5, TCLR + 0.2, speed=40)
        f.tag(*f.s.pad_xy('U4', '15'), 'stop at 15', C.ctrl, tc, dx=120, dy=-60, size=22)
        f.outline('U1', C.focus, window(t, 0.6, T_RUN, 0.5, 0.5), label='start / stop latch', label_side='bottom')
        f.outline('X1', C.clock, window(t, 1.0, T_RUN, 0.5, 0.5), label='16 MHz oscillator', label_side='top')
        # the hook: SCK heads off toward the SD card, which lives at 3.3 V
        ha = window(t, T_HOOK, self.duration + 1.0, 0.8, 0.6)
        if ha > 0:
            sp = chain_path(f.s, SCK_HOPS)
            for k in range(3):
                d = ((t - T_HOOK) * 45 + k * sp.length / 3) % (sp.length + 10)
                f.comet(sp, d, C.clock, length=9, alpha=ha, width=1.8)
            f.tag(*f.s.pad_xy('U21', '5'), 'on to the SD card: 3.3 V', C.spi,
                  window(t, T_HOOK + 1.5, self.duration + 1.0, 0.6, 0.6), dx=-150, dy=60, size=20)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, T_RUN - 0.6, END, 0.6, 0.6)
        if a <= 0:
            return
        m = TICKS(t)
        c = count(m) if t >= T_CNT else 0
        x, y = 60, 585            # panel ends at 845, clear of the subtitle band
        panel(ctx, x, y, 1800, 260, a)
        wg.chip_title(ctx, '74HC163', '4-bit counter, 16 MHz', x + 30, y + 50, a, C.text, 28)
        bits4 = [(c >> (3 - i)) & 1 for i in range(4)]
        wg.lamps(ctx, x + 60, y + 145, bits4, ['Q3', 'Q2', 'Q1', 'Q0'], C.clock, a, r=22, gap=66)
        text(ctx, f'{c:2d}', x + 440, y + 160, 64, C.clock if c else C.dim_text, a, mono=True, bold=True,
             align='right')
        text(ctx, 'count', x + 456, y + 160, 18, C.dim_text, a)
        tca = window(t, T15, TCLR, 0.2, 0.15)
        if tca > 0:
            ctx.new_path()
            ctx.arc(x + 470, y + 210, 12, 0, 6.2832)
            ctx.set_source_rgba(*C.ctrl[:3], tca)
            ctx.fill()
            glow_dot(ctx, x + 470, y + 210, 8, C.ctrl, tca)
            text(ctx, 'stop', x + 492, y + 217, 20, C.ctrl, tca, bold=True)
        # after the clear the oscillator keeps running: the plot continues into silence
        # during the hold the plot creeps on to 15.5 so the stop row shows high
        if t < T_CNT:
            cursor = -0.5
        elif t < TCLR:
            cursor = max(m, min(15.5, 15.0 + max(0.0, t - T15) * 1.25))
        else:
            cursor = min(17.4, 16 + (t - TCLR) * 2.0)

        def q0(mm):
            return count(mm) & 1 if 0 <= mm < 16 else 0

        def tcf(mm):
            return 1 if count(mm) == 15 and 0 <= mm < 16 else 0
        rows = [('16 MHz', C.clock, wg.square(1.0)), ('Q0 = SCK', C.clock, q0), ('stop', C.ctrl, tcf)]
        ea = prog(t, T_EDGES, T_EDGES + 0.6) * (1 - prog(t, T_HOOK, T_HOOK + 0.6))
        marks = [(1.0, 'up', C.clock, ea), (2.0, 'down', C.clock, ea)]
        ty, rh = y + 40, 50
        wg.timing(ctx, x + 600, ty, 920, rows, -1.0, 17.5, cursor=cursor, alpha=a, row_h=rh, label_w=160,
                  reveal=True, marks=marks, mark_space=True)
        # counters sit in the timing panel's mark row, right of the up/down marks
        my = ty + rh * len(rows) + 24
        rises = sum(1 for k in range(16) if k % 2 == 1 and m >= k) if t >= T_CNT else 0
        ta = a * prog(t, T_RUN + 1.0, T_RUN + 1.4) * (1 - ea)
        text(ctx, f'SCK pulses: {rises}', x + 1000, my, 20, C.clock, ta, bold=True)
        tb = a * prog(t, 16.6, 17.2) * (1 - ea)
        text(ctx, '16 ticks → 8 pulses', x + 1240, my, 20, C.text, tb, bold=True)


SCENE = Counter()
