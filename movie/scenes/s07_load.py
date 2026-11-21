"""S07 — Two shift registers: the byte enters through the '245 and loads into
the '165; its mirror image, the '595, waits for bits from the card."""
from otter.anim import prog, window, smooth, clamp
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, arrow, panel
from otter.scene import Scene
from otter import widgets as wg
from .common import finger, sig, lit, cpu, bits, U9_B, TX_BYTE

LOGIC_VIEW = (122.0, 89.5, 78.0)
BUS_VIEW = (150.0, 90.5, 84.0)
# narration: gate 1.0, two registers 12.4, the 165 16.6, MOSI 29.2, the 595 36.6, clock? 46.8
T_TWO, T_165, T_MOSI, T_595, T_CLK = 12.4, 16.6, 29.2, 36.6, 46.8
T_LOAD = 25.2          # "While /IOW is still low, our byte is copied in"
END = 55.6


class Load(Scene):
    name = 's07_load'
    title = 'Two shift registers'
    duration = 56.5
    cam = CamPath((0, LOGIC_VIEW), (3.5, BUS_VIEW), (56.5, BUS_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U9', 'U6', 'U7', 'J2'], 0.6 * prog(t, 2.5, 4.0))
        lit(f, '~{PORTSEL}', t, 0.5, END, alpha=0.5, t_dim=4.0)
        b = bits(TX_BYTE)                     # D7..D0
        for i in range(8):
            v = b[7 - i]                      # Di
            al, w = (1.0, 0.9) if v else (0.22, 0.6)
            sig(f, f'DB{i}', ('J2', finger(f'DB{i}')), t, 3.5 + 0.05 * i, END, speed=24, alpha=al, width=w,
                t_dim=T_165)
            sig(f, f'D{i}', ('U9', U9_B[f'D{i}']), t, 4.7 + 0.05 * i, END, speed=24, alpha=al, width=w,
                t_dim=T_165)
        da = window(t, 1.2, T_TWO, 0.5, 0.6)
        f.later(lambda fr: self.dir_arrow(fr, da))
        two = window(t, T_TWO, T_165 + 1.0, 0.5, 0.6)
        f.outline('U6', C.focus, max(two, window(t, T_165, T_595, 0.5, 0.6)))
        f.outline('U7', C.focus, max(two, window(t, T_595, END, 0.5, 0.6)))
        sig(f, '~{SER_WR}', ('U3', '12'), t, T_LOAD - 0.6, T_MOSI, speed=40)
        f.tag(*f.s.pad_xy('U6', '1'), '/IOW low: load', C.ctrl, window(t, T_LOAD, T_MOSI, 0.4, 0.5), dx=-150,
              dy=40, size=20)
        ma = window(t, T_MOSI, END, 0.5, 0.6)
        f.net('MOSI', C.spi, ma * 0.5, width=0.8)
        f.tag(*f.s.pad_xy('U6', '9'), 'bit 7 → MOSI', C.spi, window(t, T_MOSI, T_595, 0.5, 0.6), dx=110, dy=-45,
              size=20)
        mi = window(t, T_595 + 3.0, END, 0.5, 0.6)
        f.net('MISO', C.spi, mi * 0.5, width=0.8)
        f.tag(*f.s.pad_xy('U7', '14'), 'MISO → bits in', C.spi, window(t, T_595 + 3.0, T_CLK, 0.5, 0.6), dx=-170,
              dy=70, size=20)
        ca = window(t, T_CLK + 2.0, END, 0.5, 0.6)
        f.tag(*f.s.pad_xy('U6', '2'), 'clock?', C.clock, ca, dx=-150, dy=-50, size=22)
        f.tag(*f.s.pad_xy('U7', '11'), 'clock?', C.clock, ca, dx=150, dy=70, size=22)

    @staticmethod
    def dir_arrow(f, da):
        if da <= 0:
            return
        x0, y0, x1, y1 = f.box_s('U9', 0.6)
        arrow(f.ctx, x1 + 40, y1, x1 + 40, y0, C.data, 4, 16, da)
        f.pill('the gate: bus → card', x1 + 64, (y0 + y1) / 2, 20, C.data, da)

    def overlay(self, f, t):
        ctx = f.ctx
        cpu(ctx, ['MOV DX, 330h', 'MOV AL, 51h', 'OUT DX, AL'], 2, t, 0.3, T_TWO, active_t=0.5, y=70)
        a = window(t, T_165, END, 0.6, 0.6)
        if a <= 0:
            return
        h5 = prog(t, T_595, T_595 + 0.8)
        # the 165 part ends above U10's label, the 595 part in the gap above U13
        panel(ctx, 50, 110, 640, 300 + 245 * h5, a)
        wg.chip_title(ctx, '74HC165', 'byte in at once, bits out one by one', 80, 160, a, C.text, 28)
        split = smooth(clamp((t - T_LOAD) / 1.2))
        bx, by = 600, 150
        wg.byte_card(ctx, bx, by, TX_BYTE, C.data, a * (1 - split * 0.6) * prog(t, T_165 + 1.0, T_165 + 1.6),
                     size=30)
        xs = [90 + 29 + i * 68 for i in range(8)]
        b = bits(TX_BYTE)
        ry = 330
        text(ctx, 'D7 … D0', 90, ry - 52, 18, C.dim_text, a, mono=True)
        wg.register(ctx, 90, ry, [None] * 8 if split < 1 else b, C.data, a, cell=58, gap=10,
                    labels=['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A'], slots=True,
                    highlight=0 if t > T_MOSI else None)
        if 0 < split < 1:
            for i, x in enumerate(xs):
                wg.bit_cell(ctx, bx + (x - bx) * split, by + (ry - by) * split, 58 * (0.6 + 0.4 * split), b[i],
                            C.data, a)
        # the mirror image: bits in one by one, byte out
        a5 = a * h5
        wg.chip_title(ctx, '74HCT595', 'bits in one by one, byte out at once', 80, 470, a5, C.text, 28)
        wg.register(ctx, 90, 556, [None] * 8, C.spi, a5, cell=58, gap=10, slots=True)
        text(ctx, 'empty: waiting for bits on MISO', 90, 620, 18, C.dim_text, a5, italic=True)


SCENE = Load()
