"""S13 — Back to the CPU: IN 330h enables the '595 and turns the '245 around."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, arrow
from otter.scene import Scene
from otter import widgets as wg
from .common import finger, sig, lit, cpu, bits, finger_bit, U7_OUT, U9_A, RX_BYTE

BUS_VIEW = (150.0, 90.5, 84.0)
READ_VIEW = (138.0, 104.0, 86.0)


# narration: read 330h 0.5, the 245 turns around 9.9, AL = EBh 16.9
END = 20.6


class Readback(Scene):
    name = 's13_readback'
    title = 'Back to the CPU'
    duration = 21.0
    cam = CamPath((0, (158.0, 70.0, 64.0)), (2.6, READ_VIEW), (21, READ_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U9', 'U7', 'U3', 'U11', 'J2'], 0.45 * prog(t, 1.5, 3.0))
        end = END
        sig(f, '~{RD}', ('J2', finger('~{RD}')), t, 0.4, end, speed=40)
        lit(f, '~{PORTSEL}', t, 0.4, end, alpha=0.6)
        sig(f, 'Net-(U3A-E)', ('U2', '3'), t, 1.6, end, speed=30)
        sig(f, '~{RQ_SER_RD}', ('U3', '4'), t, 2.2, end, speed=30)
        sig(f, '~{SER_RD}', ('U11', '6'), t, 3.0, end, speed=30)
        f.tag(*f.s.pad_xy('U7', '13'), '595 outputs on', C.ctrl, window(t, 4.6, 16.0, 0.4, 0.5), dx=-170,
              dy=-50, size=20)
        f.tag(*f.s.pad_xy('U9', '1'), 'read 330h', C.ctrl, window(t, 2.6, 16.0, 0.4, 0.5), dx=-170, dy=40,
              size=20)
        f.outline('U3', C.focus, window(t, 1.4, 5.2, 0.4, 0.5), label='read decoder', label_side='left')
        b = bits(RX_BYTE)
        for i in range(8):
            v = b[7 - i]
            al, w = (1.0, 1.0) if v else (0.22, 0.7)
            sig(f, f'D{i}', ('U7', U7_OUT[f'D{i}']), t, 6.4 + 0.05 * i, end, speed=24, alpha=al, width=w)
            sig(f, f'DB{i}', ('U9', U9_A[f'DB{i}']), t, 10.6 + 0.05 * i, end, speed=24, alpha=al, width=w)
            f.later(lambda fr, i=i, v=v: finger_bit(fr, finger(f'DB{i}'), v, C.data, window(t, 12.4 + 0.08 * i, end, 0.4, 0.6), size=34))
        # D0 is the leftmost finger: name the ends so the row reads EBh from right to left
        ea = window(t, 12.4 + 0.08 * 7, end, 0.4, 0.6)
        f.later(lambda fr: self.end_tags(fr, ea))
        # direction arrow flips
        da = window(t, 9.6, end, 0.5, 0.6)
        f.later(lambda fr: self.dir_arrow(fr, da))

    @staticmethod
    def end_tags(f, a):
        if a <= 0:
            return
        for name, align, dx in (('DB0', 'right', -32), ('DB7', 'left', 32)):
            p = f.s.board.pad('J2', finger(name))
            x, y = f.sxy(p.x, p.y - p.h / 2)
            f.pill('D' + name[-1], x + dx, y - 34, 19, C.data, a, align=align, mono=True)

    @staticmethod
    def dir_arrow(f, da):
        if da <= 0:
            return
        x0, y0, x1, y1 = f.box_s('U9', 0.6)
        arrow(f.ctx, x1 + 40, y0, x1 + 40, y1, C.data, 4, 16, da)
        f.pill('the gate: card → bus', x1 + 64, (y0 + y1) / 2, 20, C.data, da)

    def overlay(self, f, t):
        extra = ('AL = EBh', C.data) if t > 16.9 else None
        # below the 74HCT688's silkscreen at the frame's top-left, not half over it
        cpu(f.ctx, ['MOV DX, 330h', 'IN  AL, DX'], 1, t, 0.2, END, active_t=0.4, extra=extra, y=132)


SCENE = Readback()
