"""S07 — Through the '245 gate and into the '165 (parallel load)."""
from otter.anim import prog, window, smooth, clamp
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, arrow, panel
from otter.scene import Scene
from otter import widgets as wg
from .common import finger, sig, lit, cpu, bits, U9_A, U9_B, U7_OUT, TX_BYTE

LOGIC_VIEW = (122.0, 89.5, 78.0)
BUS_VIEW = (150.0, 90.5, 84.0)


class Load(Scene):
    name = 's07_load'
    title = "Through the gate, into the '165"
    duration = 24.0
    cam = CamPath((0, LOGIC_VIEW), (3.5, BUS_VIEW), (24, BUS_VIEW))
    captions = [
        (1.0, 7.4, 'A 74HCT245 gates the bus into the card; DIR sets the direction.'),
        (9.0, 13.0, 'While /IOW is low, the 165 copies all eight bits at once.'),
        (13.4, 17.4, 'Bit 7 is already on MOSI, waiting for the first clock.'),
        (17.8, 23.4, 'Its serial input is tied to 5 V: once the byte is out, MOSI rests high.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U9', 'U6', 'U7', 'J2'], 0.6 * prog(t, 2.5, 4.0))
        lit(f, '~{PORTSEL}', t, 0.5, 23.0, alpha=0.5, t_dim=4.0)
        b = bits(TX_BYTE)                     # D7..D0
        for i in range(8):
            v = b[7 - i]                      # Di
            al, w = (1.0, 0.9) if v else (0.22, 0.6)
            sig(f, f'DB{i}', ('J2', finger(f'DB{i}')), t, 3.5 + 0.05 * i, 23.0, speed=24, alpha=al, width=w,
                t_dim=13.4)
            sig(f, f'D{i}', ('U9', U9_B[f'D{i}']), t, 4.7 + 0.05 * i, 23.0, speed=24, alpha=al, width=w,
                t_dim=13.4)
        da = window(t, 1.2, 23.0, 0.5, 0.6)
        f.later(lambda fr: self.dir_arrow(fr, da))
        sig(f, '~{SER_WR}', ('U3', '12'), t, 8.4, 13.0, speed=40)
        f.tag(*f.s.pad_xy('U6', '1'), 'SH/LD = 0: load', C.ctrl, window(t, 9.0, 13.2, 0.4, 0.5), dx=-150, dy=40,
              size=20, mono=True)
        f.tag(*f.s.pad_xy('U7', '13'), '595 outputs off', C.dim_text, window(t, 6.0, 12.8, 0.4, 0.5), dx=170,
              dy=30, size=20)
        ma = window(t, 13.2, 23.4, 0.5, 0.6)
        f.net('MOSI', C.spi, ma * 0.35, width=0.8)
        f.tag(*f.s.pad_xy('U6', '9'), 'QH → MOSI = 0', C.spi, ma, dx=230, dy=90, size=20, mono=True)
        f.tag(*f.s.pad_xy('U6', '10'), 'SER = 5 V', C.power, window(t, 17.8, 23.4, 0.5, 0.6), dx=-200, dy=100,
              size=20, mono=True)

    @staticmethod
    def dir_arrow(f, da):
        if da <= 0:
            return
        x0, y0, x1, y1 = f.box_s('U9', 0.6)
        arrow(f.ctx, x1 + 40, y1, x1 + 40, y0, C.data, 4, 16, da)
        f.pill('DIR = 1', x1 + 64, (y0 + y1) / 2 - 18, 20, C.ctrl, da, mono=True)
        f.pill('A → B: bus → card', x1 + 64, (y0 + y1) / 2 + 20, 18, C.dim_text, da, bold=False)

    def overlay(self, f, t):
        ctx = f.ctx
        cpu(ctx, ['MOV DX, 330h', 'MOV AL, 51h', 'OUT DX, AL'], 2, t, 0.3, 8.0, active_t=0.5, y=70)
        a = window(t, 8.0, 23.4, 0.6, 0.6)
        if a <= 0:
            return
        panel(ctx, 50, 110, 640, 340, a)
        wg.chip_title(ctx, '74HC165', 'parallel in, serial out', 80, 160, a, C.text, 28)
        split = smooth(clamp((t - 9.2) / 1.2))
        bx, by = 520, 160
        wg.byte_card(ctx, bx, by, TX_BYTE, C.data, a * (1 - split * 0.6), size=34)
        xs = [90 + 29 + i * 68 for i in range(8)]
        b = bits(TX_BYTE)
        ry = 340
        text(ctx, 'D7 … D0', 90, ry - 52, 18, C.dim_text, a, mono=True)
        wg.register(ctx, 90, ry, [None] * 8 if split < 1 else b, C.data, a, cell=58, gap=10,
                    labels=['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A'], slots=True,
                    highlight=0 if t > 13.2 else None)
        if 0 < split < 1:
            for i, x in enumerate(xs):
                wg.bit_cell(ctx, bx + (x - bx) * split, by + (ry - by) * split, 58 * (0.6 + 0.4 * split), b[i],
                            C.data, a)


SCENE = Load()
