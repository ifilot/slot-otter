"""S10 — Into the 3.3 V world: regulator, the four SPI wires, and how the
74LVC125 level shifter works in both directions."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel, set_color, arrow
from otter.scene import Scene
from .common import sig, lit

CLOCK_VIEW = (118.0, 64.0, 80.0)
SD_VIEW = (162.0, 58.5, 50.0)
# (J1 pad, card pin name, signal, net at J1, colour)
LANES = [('2', 'DAT3', '/CS', 'CS_LLS', C.spi), ('3', 'CMD', 'MOSI', 'DI_LLS', C.data),
         ('5', 'CLK', 'SCK', 'SCK_LLS', C.clock), ('7', 'DAT0', 'MISO', 'D0_LLS', C.spi)]
# narration: 3.3 V 0.6, the buffer 7.0, MISO back 20.2, chip select 26.4
T_IN, T_OUT, T_CS = 7.0, 20.2, 26.4
END = 33.9
V5 = C.power                      # 5 V logic
V33 = C.spi                       # 3.3 V logic


class SpiWires(Scene):
    name = 's10_spi_wires'
    title = 'Into the 3.3 V world'
    duration = 34.5
    cam = CamPath((0, CLOCK_VIEW), (3.0, SD_VIEW), (34.5, SD_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U16', 'U21', 'J1', 'R8', 'R9', 'R10', 'R11'], 0.55 * prog(t, 1.5, 3.0))
        lit(f, '+3V3', t, 2.0, None, color=V33, alpha=0.6, t_dim=6.0)
        a = window(t, 2.6, END, 0.5, 0.3)
        f.outline('U16', C.focus, a * (1 - 0.6 * prog(t, 6.0, 6.6)), label='regulator 5 V → 3.3 V',
                  label_side='left')
        f.outline('U21', C.focus, a, label='74LVC125 · runs on 3.3 V', label_side='left',
                  label_alpha=1 - prog(t, T_IN - 0.8, T_IN - 0.4))
        f.outline('J1', C.focus, a, pad=0.3, label='microSD socket', label_side='top')
        for i, (pad, pin, signame, net, col) in enumerate(LANES):
            t0 = T_IN + 0.6 + 0.9 * i
            if t < T_OUT:
                dim = 0.45 if net == 'D0_LLS' else 1.0
            elif t < T_CS:
                dim = 1.0 if net == 'D0_LLS' else 0.45
            else:
                dim = 1.0 if net == 'CS_LLS' else 0.45
            src = ('J1', '7') if net == 'D0_LLS' else ('U21', {'CS_LLS': '8', 'DI_LLS': '3', 'SCK_LLS': '6'}[net])
            sig(f, net, src, t, t0, None, speed=30, color=col, alpha=dim)
            if net == 'D0_LLS':
                sig(f, 'Net-(R8-Pad2)', ('R8', '2'), t, t0 + 0.5, None, speed=30, color=col, alpha=dim)
                sig(f, 'MISO', ('U21', '11'), t, t0 + 0.9, None, speed=30, color=col, alpha=dim)
            la = window(t, t0, END, 0.4, 0.3)
            f.tag(*f.s.pad_xy('J1', pad), f'{signame:<4s} → {pin}' if net != 'D0_LLS' else f'{pin} → {signame}',
                  col, la * (0.5 + 0.5 * dim), dx=-150, dy=0, size=20, mono=True)

    def overlay(self, f, t):
        a = window(t, T_IN - 0.4, END, 0.6, 0.3)
        if a <= 0:
            return
        ctx = f.ctx
        # top-left, clear of U21 (x > 635) and U16 (y > 405)
        x, y, w, h = 40, 28, 580, 350
        panel(ctx, x, y, w, h, a)
        text(ctx, '74LVC125: four buffers, powered at 3.3 V', x + 26, y + 38, 22, C.text, a, bold=True)
        text(ctx, 'inputs tolerate 5 V; outputs swing 0 – 3.3 V', x + 26, y + 66, 18, C.dim_text, a)
        bx = x + 290
        text(ctx, '5 V side', bx - 105, y + 98, 16, C.dim_text, a, align='center', italic=True)
        text(ctx, 'card side', bx + 140, y + 98, 16, C.dim_text, a, align='center', italic=True)
        rows = [('/CS', 'DAT3', 130), ('MOSI', 'CMD', 182), ('SCK', 'CLK', 234), ('MISO', 'DAT0', 286)]   # evenly spaced
        for sig_, pin, dy in rows:
            yy = y + dy
            back = sig_ == 'MISO'
            if t < T_OUT:
                on = 0.0 if back else 1.0
            elif t < T_CS:
                on = 1.0 if back else 0.0
            else:
                on = 1.0 if sig_ == '/CS' else 0.0
            ra = a * (0.35 + 0.65 * on)
            # buffer triangle
            ctx.new_path()
            if not back:
                ctx.move_to(bx - 22, yy - 20)
                ctx.line_to(bx + 22, yy)
                ctx.line_to(bx - 22, yy + 20)
            else:
                ctx.move_to(bx + 22, yy - 20)
                ctx.line_to(bx - 22, yy)
                ctx.line_to(bx + 22, yy + 20)
            ctx.close_path()
            set_color(ctx, C.chip, ra)
            ctx.fill_preserve()
            ctx.set_line_width(2)
            set_color(ctx, C.focus, ra)
            ctx.stroke()
            text(ctx, sig_, x + 26, yy, 20, C.text, ra, mono=True, bold=True, valign='middle')
            text(ctx, pin, x + w - 22, yy, 18, C.dim_text, ra, mono=True, align='right', valign='middle')
            if not back:
                f.pill('5 V', bx - 105, yy, 18, V5, ra, align='center', mono=True)
                arrow(ctx, bx - 78, yy, bx - 26, yy, V5, 3, 10, ra)
                arrow(ctx, bx + 26, yy, bx + 110, yy, V33, 3, 10, ra)
                f.pill('3.3 V', bx + 140, yy, 18, V33, ra, align='center', mono=True)
            else:
                f.pill('3.3 V', bx - 125, yy, 18, V33, ra, align='center', mono=True)
                arrow(ctx, bx - 26, yy, bx - 84, yy, V33, 3, 10, ra)
                arrow(ctx, bx + 110, yy, bx + 26, yy, V33, 3, 10, ra)
                f.pill('3.3 V', bx + 140, yy, 18, V33, ra, align='center', mono=True)
        # notes share the bottom line: the 595 note fades out before the /CS note fades in
        ca = a * prog(t, T_CS + 0.4, T_CS + 1.0)
        text(ctx, '/CS already low: set once at start-up (IN 333h)', x + 26, y + h - 24, 18, C.spi, ca, bold=True)
        ha = a * prog(t, T_OUT, T_OUT + 0.6) * (1 - prog(t, T_CS, T_CS + 0.4))
        text(ctx, 'the 595 reads anything above 2 V as a 1', x + 26, y + h - 24, 18, C.ok, ha, bold=True)


SCENE = SpiWires()
