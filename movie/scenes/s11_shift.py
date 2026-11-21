"""S11 — Bits out, bits in (centrepiece). The SPI ring in slow motion."""
from otter.anim import prog, window, breathe, smooth, clamp, Schedule
from otter.camera import CamPath, drift
from otter.config import C, W
from otter.draw import text, rounded_rect, set_color, polyline
from otter.netflow import Polyline
from otter.scene import Scene
from otter import widgets as wg
from .common import SpiRing, chain_path, leds_pip, TX_BYTE, bits

SHIFT_VIEW = (158.0, 70.0, 64.0)
REPLAY_VIEW = (152.0, 72.6, 104.0)    # replay framing (U21 and U1 fully in frame); s12 starts here
REPLAY_FRAME = REPLAY_VIEW
# narration: now 0.4, clock up 4.4, clock down 11.6, ones 20.0, swap 25.4, one microsecond 38.6
T_UP, T_DOWN, T_ONES, T_SWAP, T_US = 4.4, 11.6, 20.0, 25.4, 39.4
T_SWAP2 = 32.2         # "...SPI simply swaps two bytes" (second half of the 25.4 line)
C0 = 3.0                                                                     # first clock
CYCLES = Schedule(C0, [(8.0, 1 / 4.0), (4.0, 1 / 2.0), (3.2, 1 / 0.8)])      # 8 cycles, ends 18.2 s
P_END = 38.2           # the ring panel leaves; then the replay on the real copper
END = 43.0
RING = SpiRing(TX_BYTE, 0xFF)

MOSI_HOPS = [('MOSI', ('U6', '9'), ('R9', '1')), ('Net-(R9-Pad2)', ('R9', '2'), ('U21', '2')),
             ('DI_LLS', ('U21', '3'), ('J1', '3'))]
SCK_HOPS = [('CLK', ('U4', '14'), ('R10', '1')), ('Net-(R10-Pad2)', ('R10', '2'), ('U21', '5')),
            ('SCK_LLS', ('U21', '6'), ('J1', '5'))]
MISO_HOPS = [('D0_LLS', ('J1', '7'), ('R8', '1')), ('Net-(R8-Pad2)', ('R8', '2'), ('U21', '12')),
             ('MISO', ('U21', '11'), ('U7', '14'))]


class Shift(Scene):
    name = 's11_shift'
    title = 'Bits out, bits in'
    duration = 43.5
    cam = CamPath((0, (162.0, 58.5, 50.0)), (3.0, SHIFT_VIEW), (P_END - 0.4, SHIFT_VIEW), (P_END + 2.6, REPLAY_FRAME),
                  (43.5, REPLAY_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        pa = window(t, 0.3, P_END, 0.8, 0.8)
        # synchronised board activity behind the panel
        c = CYCLES(t)
        ph = c % 1.0
        running = C0 <= t < CYCLES.end
        if running:
            n = int(c)
            f.net('CLK', C.clock, 1.0 if ph < 0.5 else 0.15)
            f.net('MOSI', C.spi, 1.0 if bits(TX_BYTE)[n] else 0.2)
            f.net('MISO', C.spi, 1.0)
        # replay on the board after the panel: comets along the real copper
        ra = window(t, P_END - 0.2, END, 0.8, 0.6)
        if ra > 0:
            mp = chain_path(f.s, MOSI_HOPS)
            sp = chain_path(f.s, SCK_HOPS)
            qp = chain_path(f.s, MISO_HOPS)
            period = 1.6
            for k in range(8):
                tt = (t - P_END - k * period / 8) % period
                f.comet(mp, tt * 70, C.data, length=8, alpha=ra * (1.0 if bits(TX_BYTE)[k] else 0.35), width=1.6)
                f.comet(sp, tt * 70, C.clock, length=6, alpha=ra * 0.8, width=1.4)
                f.comet(qp, tt * 70, C.spi, length=8, alpha=ra, width=1.6)
            f.tag(*f.s.pad_xy('J1', '3'), 'MOSI → card', C.data, ra, dx=-160, dy=-60, size=20)
            f.tag(*f.s.pad_xy('U7', '14'), 'MISO → 595', C.spi, ra, dx=160, dy=-40, size=20)
            f.tag(*f.s.pad_xy('J1', '5'), 'SCK', C.clock, ra, dx=-160, dy=50, size=20, mono=True)
        f.dim(0.78 * pa)

    def overlay(self, f, t):
        ctx = f.ctx
        pa = window(t, 0.3, P_END, 0.8, 0.8)
        c = CYCLES(t) if t >= C0 else -0.4
        RING.draw(ctx, c, pa, legend=window(t, C0, P_END, 0.5, 0.5),
                  title='OUT 330h, 51h   ·   eight clocks')
        self.ones(ctx, t, pa)
        self.swap(ctx, t, pa)
        sa = pa * prog(t, T_SWAP, T_SWAP + 0.8)
        text(ctx, 'card received 51h', 130, 600, 22, C.spi, sa, bold=True)
        text(ctx, 'and sent FFh', 130, 630, 20, C.dim_text, sa)
        ra = window(t, P_END - 0.2, END, 0.8, 0.6)
        n = int(min(7, max(0, ((t - P_END) % 1.6) / 0.2)))
        mosi_low = 1.0 - bits(TX_BYTE)[n]
        leds_pip(f, t, {'D1': 1.0, 'D2': mosi_low, 'D3': 0.0}, ra, rect=(60, 600, 360, 203))
        ua = window(t, T_US, END, 0.6, 0.6)
        text(ctx, '8 clocks = 1 µs', W - 70, 560, 40, C.clock, ua, bold=True, align='right')

    @staticmethod
    def miso_lane():
        cx, cy, cw, ch = RING.CARD
        r595_right = RING.X165 + 8 * (RING.CELL + RING.GAP)
        return Polyline([(cx - 6, cy + ch * 0.6), (cx - 40, cy + ch * 0.6), (cx - 40, RING.ROW2 + 110),
                         (r595_right + 60, RING.ROW2 + 110), (r595_right + 60, RING.ROW2),
                         (r595_right + 6, RING.ROW2)])

    def ones(self, ctx, t, pa):
        """'...it simply answers with ones': 1s stream along MISO into the 595, whose cells glow."""
        oa = pa * window(t, T_ONES, T_SWAP + 0.4, 0.6, 0.6)
        if oa <= 0:
            return
        lane = self.miso_lane()
        g = breathe(t, 1.2, 0.35, 1.0)
        ctx.save()
        polyline(ctx, lane.pts)
        ctx.set_line_width(9)
        set_color(ctx, C.spi, 0.25 * oa * g)
        ctx.stroke()
        ctx.restore()
        for k in range(4):
            u = ((t - T_ONES) / 3.2 + k / 4) % 1.0
            fa = clamp(u / 0.08) * clamp((1 - u) / 0.08)
            px, py = lane.at(lane.length * u)
            wg.bit_cell(ctx, px, py, 30, 1, C.spi, oa * fa)
        x0 = RING.X165 - 12
        w = 8 * (RING.CELL + RING.GAP) - RING.GAP + 24
        rounded_rect(ctx, x0, RING.ROW2 - RING.CELL / 2 - 10, w, RING.CELL + 74, 14)   # cells and QH..QA
        ctx.set_line_width(3)
        set_color(ctx, C.spi, oa * g)
        ctx.stroke()
        text(ctx, 'nothing to say yet: all ones', 130, 600, 22, C.spi, oa * (1 - prog(t, T_SWAP - 0.6, T_SWAP)),
             bold=True)

    @staticmethod
    def swap(ctx, t, pa):
        """'SPI simply swaps two bytes': 51h rides MOSI to the card while FFh rides MISO to the 595."""
        wa = pa * window(t, T_SWAP2, P_END, 0.4, 0.6)
        if wa <= 0:
            return
        u = smooth(clamp((t - T_SWAP2 - 0.2) / 2.2))
        cx, cy, cw, ch = RING.CARD
        # 51h: from the 165 along MOSI into the card
        x51 = 1130 + (cx + cw - 70 - 1130) * u
        y51 = RING.ROW1 - 60 + (cy + 40 - (RING.ROW1 - 60)) * u
        wg.byte_card(ctx, x51, y51, 0x51, C.data, wa, size=30)
        # FFh: from the card along MISO toward the 595 (stops at the lane's last corner)
        lane = Shift.miso_lane()
        corner = lane.length - (RING.ROW2 + 110 - RING.ROW2) - 54
        px, py = lane.at(corner * u)
        wg.byte_card(ctx, px, py, 0xFF, C.spi, wa, size=30)
        ta = wa * prog(t, T_SWAP2 + 1.0, T_SWAP2 + 1.6)
        text(ctx, 'same 8 clocks:', 745, 520, 20, C.dim_text, ta, align='center')
        text(ctx, 'bytes swapped', 745, 548, 22, C.text, ta, align='center', bold=True)


SCENE = Shift()
