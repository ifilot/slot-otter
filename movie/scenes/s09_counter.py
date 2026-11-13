"""S09 — Exactly eight clocks: the '00 latch releases the '163 counter."""
import math

from otter.anim import prog, window, breathe, Schedule
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel, glow_dot
from otter.scene import Scene
from otter import widgets as wg
from .common import sig

CLOCK_VIEW = (118.0, 64.0, 80.0)
# 0..15 at 2 ticks/s (4.0-11.5 s), hold at 15 for 1.5 s, then the clearing tick (13.5 s)
TICKS = Schedule(4.0, [(7.5, 2.0), (1.5, 0.0), (0.5, 2.0)])
T15, TCLR = 11.5, 13.5


def count(m):
    if m < 0 or m >= 16:
        return 0
    return int(math.floor(m))


class Counter(Scene):
    name = 's09_counter'
    title = 'Exactly eight clocks'
    duration = 26.0
    cam = CamPath((0, (126.0, 80.0, 140.0)), (3.0, CLOCK_VIEW), (26, CLOCK_VIEW))
    captions = [
        (0.6, 4.0, '/CLKSTART sets a latch, which releases a 4-bit counter.'),
        (4.2, 11.4, "The counter's lowest bit flips on every 16 MHz tick: an 8 MHz clock, called SCK."),
        (11.6, 15.6, 'At 15, "terminal count" resets the latch; the counter clears and stops.'),
        (16.0, 20.0, 'Eight clock pulses, then silence. One byte takes one microsecond.'),
        (20.4, 25.6, 'The last NAND gate inverts the clock: the 165 shifts on the falling edge.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U4', 'U1', 'X1'], 0.6 * prog(t, 1.5, 3.0))
        m = TICKS(t)
        running = 4.0 <= t < TCLR
        c = count(m)
        sig(f, '~{CLKSTART}', ('U11', '3'), t, 0.0, 2.0, speed=50)
        run = prog(t, 1.4, 1.8) * (1 - prog(t, T15 + 0.9, T15 + 1.2))
        f.net('Net-(U4-~{MR})', C.ctrl, run)
        f.tag(*f.s.pad_xy('U4', '1'), '/MR = 1: count', C.ctrl, window(t, 1.6, T15 + 1.2, 0.4, 0.4), dx=-130,
              dy=-60, size=20, mono=True)
        f.net('16MHz', C.clock, window(t, 2.0, 25.6, 0.6, 0.6) * breathe(t * 3, 1.0, 0.35, 0.7), width=0.7)
        f.net('CLK', C.clock, (1.0 if (c & 1) and running else 0.0) * window(t, 3.8, TCLR + 0.4, 0.1, 0.2))
        tc = window(t, T15, TCLR, 0.2, 0.15)
        sig(f, 'CLKSTOP', ('U4', '15'), t, T15, TCLR + 0.2, speed=40)
        sig(f, '~{CLKSTOP}', ('U1', '8'), t, T15 + 0.5, TCLR + 0.2, speed=40)
        f.tag(*f.s.pad_xy('U4', '15'), 'TC = 1', C.ctrl, tc, dx=120, dy=-60, size=22, mono=True)
        f.outline('U1', C.focus, window(t, 0.6, 4.0, 0.5, 0.5), label='NAND set/reset latch', label_side='bottom')
        ia = window(t, 20.4, 25.6, 0.5, 0.6)
        f.net('~{CLK}', C.clock, ia * 0.8)
        f.tag(*f.s.pad_xy('U1', '11'), '/CLK (inverted SCK)', C.clock, ia, dx=-200, dy=60, size=20, mono=True)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, 3.6, 25.6, 0.6, 0.6)
        if a <= 0:
            return
        m = TICKS(t)
        c = count(m) if t >= 4.0 else 0
        x, y = 60, 610
        panel(ctx, x, y, 1800, 300, a)
        wg.chip_title(ctx, '74HC163', '4-bit counter, 16 MHz', x + 30, y + 52, a, C.text, 28)
        bits4 = [(c >> (3 - i)) & 1 for i in range(4)]
        wg.lamps(ctx, x + 60, y + 160, bits4, ['Q3', 'Q2', 'Q1', 'Q0'], C.clock, a, r=22, gap=66)
        text(ctx, f'{c:2d}', x + 440, y + 175, 64, C.clock if c else C.dim_text, a, mono=True, bold=True,
             align='right')
        text(ctx, 'count', x + 456, y + 175, 18, C.dim_text, a)
        tca = window(t, T15, TCLR, 0.2, 0.15)
        if tca > 0:
            ctx.new_path()
            ctx.arc(x + 470, y + 230, 12, 0, 6.2832)
            ctx.set_source_rgba(*C.ctrl[:3], tca)
            ctx.fill()
            glow_dot(ctx, x + 470, y + 230, 8, C.ctrl, tca)
            text(ctx, 'TC', x + 492, y + 237, 20, C.ctrl, tca, mono=True, bold=True)
        # after the clear the oscillator keeps running: the plot continues into silence
        cursor = (m if t < TCLR else min(17.4, 16 + (t - TCLR) * 2.0)) if t >= 4.0 else -0.5

        def q0(mm):
            return count(mm) & 1 if 0 <= mm < 16 else 0

        def tcf(mm):
            return 1 if count(mm) == 15 and 0 <= mm < 16 else 0
        rows = [('16 MHz', C.clock, wg.square(1.0)), ('Q0 = SCK', C.clock, q0), ('TC', C.ctrl, tcf)]
        wg.timing(ctx, x + 600, y + 50, 920, rows, -1.0, 17.5, cursor=cursor, alpha=a, row_h=58, label_w=160,
                  reveal=True)
        rises = sum(1 for k in range(16) if k % 2 == 1 and m >= k) if t >= 4.0 else 0
        ta = a * prog(t, 4.6, 5.0)
        text(ctx, f'SCK rising edges: {rises}', x + 760, y + 272, 20, C.clock, ta, bold=True)
        tb = a * prog(t, 16.0, 16.6)
        text(ctx, '16 ticks × 62.5 ns = 1 µs per byte', x + 1180, y + 272, 20, C.text, tb, bold=True)


SCENE = Counter()
