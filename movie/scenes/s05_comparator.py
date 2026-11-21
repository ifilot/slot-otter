"""S05 — Is this for me? The 74HCT688 compares A9..A2 with the DIP switch."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel, arrow, set_color, rounded_rect
from otter.scene import Scene
from otter import widgets as wg
from .common import finger, sig, PORT

DECODE_VIEW = (106.0, 92.0, 64.0)
SWITCH_VALUES = ['200', '100', '80', '40', '20', '10', '8', '4']
SW_ON = [1, 1, 0, 0, 1, 1, 0, 0]          # 330h
# narration: question 0.6, address 6.6, switch 16.8, match 22.0, other 25.4, four ports 28.8
T_ADDR, T_SW, T_MATCH, T_PORTS = 6.6, 16.8, 22.0, 28.8
MIS0, MIS1 = 25.4, 28.6                     # "what if 300h" inset
END = 36.0


class Comparator(Scene):
    name = 's05_comparator'
    title = 'Is this for me?'
    duration = 37.0
    cam = CamPath((0, (117.0, 108.7, 88.0)), (3.2, DECODE_VIEW), (37, DECODE_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U8', 'SW1', 'RN1', 'RN3'], 0.62 * prog(t, 1.5, 3.0))
        mism = window(t, MIS0, MIS1, 0.4, 0.4)
        for i in range(2, 10):
            a = f'A{i}'
            hi = (PORT >> i) & 1
            sig(f, a, ('J2', finger(a)), t, T_ADDR + (9 - i) * 0.08, END, speed=28,
                alpha=(1.0 if hi else 0.22) * (1 - 0.6 * mism), width=0.8 if hi else 0.6, t_dim=T_MATCH)
        sa = prog(t, T_SW, T_SW + 0.8)
        for i in range(8):
            if SW_ON[i]:
                net = f.s.board.pad('SW1', str(i + 1)).net
                f.net(net, C.addr, 0.7 * sa * prog(t, T_SW + 0.4 + i * 0.1, T_SW + 0.8 + i * 0.1)
                      * (1 - 0.65 * prog(t, T_MATCH, T_MATCH + 0.6)),
                      width=0.8)
        # /PORTSEL stays lit to the cut, like its tag: S06 opens with it lit
        sig(f, '~{PORTSEL}', ('U8', '19'), t, T_MATCH, None, speed=30, alpha=1 - mism)
        if sa > 0:
            f.later(lambda fr: self.switches(fr, sa))
        if t > T_MATCH:
            f.tag(*f.s.pad_xy('U8', '19'), 'card addressed', C.ctrl, prog(t, T_MATCH + 0.2, T_MATCH + 0.8)
                  * (1 - mism), dx=0, dy=-60, size=22)
        f.dim(0.45 * mism)

    def switches(self, f, a):
        """Slide switches over SW1 (drawn above the tracks). Pins 1-8 (bottom
        row) go to the comparator, pins 9-16 (top row) to 5 V: ON is up."""
        ctx = f.ctx
        with f.world() as c:
            x0, y0, x1, y1 = f.s.board.fp('SW1').bbox
            rounded_rect(c, x0 + 0.6, y0 + 0.4, x1 - x0 - 1.2, y1 - y0 - 0.8, 0.6)
            c.set_source_rgba(0.09, 0.05, 0.06, 0.96 * a)
            c.fill()
            for i in range(8):
                p1 = f.s.board.pad('SW1', str(i + 1))
                p2 = f.s.board.pad('SW1', str(16 - i))
                cx = p1.x
                top, bot = p2.y + 1.3, p1.y - 1.3
                w = 1.5
                rounded_rect(c, cx - w / 2, top, w, bot - top, 0.25)
                c.set_source_rgba(0.02, 0.03, 0.05, a)
                c.fill()
                on = SW_ON[i]
                kh = (bot - top) * 0.42
                ky = top + 0.25 if on else bot - 0.25 - kh
                rounded_rect(c, cx - w / 2 + 0.2, ky, w - 0.4, kh, 0.2)
                set_color(c, C.addr if on else C.dim_text, a)
                c.fill()
        # legend strip above the switch
        p16 = f.s.board.pad('SW1', '16')
        p9 = f.s.board.pad('SW1', '9')
        lx0, ly = f.sxy(p16.x - 1.4, p16.y - 1.6)
        lx1, _ = f.sxy(p9.x + 1.4, p9.y)
        rounded_rect(ctx, lx0, ly - 62, lx1 - lx0, 56, 8)
        ctx.set_source_rgba(0.025, 0.04, 0.075, 0.9 * a)
        ctx.fill()
        for i in range(8):
            p2 = f.s.board.pad('SW1', str(16 - i))
            x, _ = f.sxy(p2.x, p2.y)
            on = SW_ON[i]
            text(ctx, SWITCH_VALUES[i], x, ly - 38, 19, C.addr if on else C.dim_text, a, align='center', mono=True,
                 bold=on)
            text(ctx, f'A{9 - i}', x, ly - 15, 16, C.dim_text, a, align='center', mono=True)
        text(ctx, 'hex', lx0 - 10, ly - 38, 16, C.dim_text, a, align='right', italic=True)
        x, y = f.sxy(p16.x - 2.0, p16.y + 1.2)
        text(ctx, 'ON', x, y, 18, C.addr, a, align='right', mono=True, bold=True)
        text(ctx, 'OFF', x, y + 4.8 * f.view.scale, 18, C.dim_text, a, align='right', mono=True, bold=True)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, T_ADDR + 2.4, END - 0.4, 0.6, 0.6)
        if a <= 0:
            return
        x, y = 1130, 120
        panel(ctx, x - 30, y - 50, 760, 470, a)
        mism = window(t, MIS0, MIS1, 0.4, 0.4)
        wg.chip_title(ctx, '74HCT688', '8-bit equality comparator', x, y, a * (1 - mism), C.text, 30)
        text(ctx, 'What if: OUT 300h', x, y, 30, C.bad, a * mism, bold=True)
        p_bits = [(PORT >> (9 - i)) & 1 for i in range(8)]
        alt = [(0x300 >> (9 - i)) & 1 for i in range(8)]
        cur = [alt[i] if mism > 0.5 else p_bits[i] for i in range(8)]
        lab = [f'A{9 - i}' for i in range(8)]
        cell, gap = 48, 8
        xs = wg.register(ctx, x + 150, y + 130, cur, C.addr, a, cell=cell, gap=gap, labels=None)
        text(ctx, 'P', x + 10, y + 130, 24, C.addr, a, mono=True, bold=True, valign='middle')
        text(ctx, 'address', x + 40, y + 130, 18, C.dim_text, a, valign='middle')
        # A1 and A0 are on the bus too, but the comparator never sees them
        b = window(t, T_PORTS, END - 0.4, 0.6, 0.6)
        ga = a * b
        if ga > 0:
            gx = [xs[-1] + (cell + gap) * k + 6 for k in (1, 2)]
            for k, cx in enumerate(gx):
                wg.bit_cell(ctx, cx, y + 130, cell, (PORT >> (1 - k)) & 1, C.dim_text, 0.75 * ga)
                text(ctx, f'A{1 - k}', cx, y + 84, 16, C.dim_text, ga, align='center', mono=True)
            text(ctx, 'not compared', (gx[0] + gx[1]) / 2, y + 210, 17, C.dim_text, ga, align='center',
                 valign='middle', italic=True)
        qa = a * prog(t, T_SW + 0.6, T_SW + 1.2)
        wg.register(ctx, x + 150, y + 210, SW_ON, C.addr, qa, cell=cell, gap=gap)
        text(ctx, 'Q', x + 10, y + 210, 24, C.addr, qa, mono=True, bold=True, valign='middle')
        text(ctx, 'switch', x + 40, y + 210, 18, C.dim_text, qa, valign='middle')
        for i, cx in enumerate(xs):
            text(ctx, lab[i], cx, y + 84, 16, C.dim_text, a, align='center', mono=True)
            ca = prog(t, T_SW + 1.6 + i * 0.3, T_SW + 1.9 + i * 0.3)
            wg.check(ctx, cx, y + 280, cur[i] == SW_ON[i], a * ca)
        allok = prog(t, T_MATCH, T_MATCH + 0.5) * (1 - mism)
        text(ctx, 'all equal', x + 150, y + 350, 22, C.ok, a * allok, bold=True)
        arrow(ctx, x + 270, y + 342, x + 350, y + 342, C.ctrl, 3, 12, a * allok)
        text(ctx, 'card addressed', x + 362, y + 350, 22, C.ctrl, a * allok, bold=True)
        text(ctx, 'two bits differ: not for us', x + 150, y + 350, 22, C.bad, a * mism, bold=True)
        text(ctx, '330h  331h  332h  333h', x + 150, y + 400, 24, C.text, a * b, mono=True, bold=True)


SCENE = Comparator()
