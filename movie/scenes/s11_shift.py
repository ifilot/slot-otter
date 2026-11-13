"""S11 — Bits out, bits in (centrepiece). The SPI ring in slow motion."""
from otter.anim import prog, window, Schedule
from otter.camera import CamPath, drift
from otter.config import C, W
from otter.draw import text
from otter.scene import Scene
from otter import widgets as wg
from .common import SpiRing, chain_path, leds_pip, TX_BYTE, bits

SHIFT_VIEW = (158.0, 70.0, 64.0)
REPLAY_VIEW = (152.0, 75.7, 104.0)
CYCLES = Schedule(2.0, [(6.0, 1 / 3.0), (3.0, 1 / 1.5), (2.4, 1 / 0.6)])     # 8 cycles, ends 13.4 s
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
    duration = 32.0
    cam = CamPath((0, (162.0, 58.5, 50.0)), (3.0, SHIFT_VIEW), (26.0, SHIFT_VIEW), (29.0, REPLAY_VIEW), (32, REPLAY_VIEW))
    captions = [
        (1.6, 8.0, 'On each rising edge the SD card reads a bit from MOSI, and the 595 a bit from MISO.'),
        (8.2, 13.6, 'On each falling edge the 165 moves the next bit into place. Most significant bit first.'),
        (14.0, 21.6, 'While a command goes out, the card has nothing to say: it answers with ones.'),
        (23.6, 31.4, 'Sending and receiving are the same eight clocks. SPI simply swaps two bytes.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        pa = window(t, 0.3, 22.6, 0.8, 0.8)
        # synchronised board activity behind the panel
        c = CYCLES(t)
        ph = c % 1.0
        running = 2.0 <= t < CYCLES.end
        if running:
            n = int(c)
            f.net('CLK', C.clock, 1.0 if ph < 0.5 else 0.15)
            f.net('MOSI', C.spi, 1.0 if bits(TX_BYTE)[n] else 0.2)
            f.net('MISO', C.spi, 1.0)
        # replay on the board after the panel: comets along the real copper
        ra = window(t, 22.4, 31.8, 0.8, 0.6)
        if ra > 0:
            mp = chain_path(f.s, MOSI_HOPS)
            sp = chain_path(f.s, SCK_HOPS)
            qp = chain_path(f.s, MISO_HOPS)
            period = 1.6
            for k in range(8):
                tt = (t - 22.6 - k * period / 8) % period
                f.comet(mp, tt * 70, C.data, length=8, alpha=ra * (1.0 if bits(TX_BYTE)[k] else 0.35), width=1.6)
                f.comet(sp, tt * 70, C.clock, length=6, alpha=ra * 0.8, width=1.4)
                f.comet(qp, tt * 70, C.spi, length=8, alpha=ra, width=1.6)
            f.tag(*f.s.pad_xy('J1', '3'), 'MOSI → card', C.data, ra, dx=-160, dy=-60, size=20)
            f.tag(*f.s.pad_xy('U7', '14'), 'MISO → 595', C.spi, ra, dx=160, dy=-40, size=20)
            f.tag(*f.s.pad_xy('J1', '5'), 'SCK', C.clock, ra, dx=-160, dy=50, size=20, mono=True)
        f.dim(0.78 * pa)

    def overlay(self, f, t):
        ctx = f.ctx
        pa = window(t, 0.3, 22.6, 0.8, 0.8)
        c = CYCLES(t) if t >= 2.0 else -0.4
        RING.draw(ctx, c, pa, legend=window(t, 2.0, 22.6, 0.5, 0.5),
                  title='OUT 330h, 51h   ·   SPI mode 0, MSB first')
        sa = pa * prog(t, 14.0, 14.8)
        text(ctx, 'card received 51h', 130, 600, 22, C.spi, sa, bold=True)
        text(ctx, 'and sent FFh', 130, 630, 20, C.dim_text, sa)
        ra = window(t, 22.4, 31.8, 0.8, 0.6)
        n = int(min(7, max(0, ((t - 22.6) % 1.6) / 0.2)))
        mosi_low = 1.0 - bits(TX_BYTE)[n]
        leds_pip(f, t, {'D1': 1.0, 'D2': mosi_low, 'D3': 0.0}, ra, rect=(60, 600, 360, 203))


SCENE = Shift()
