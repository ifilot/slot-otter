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


class Readback(Scene):
    name = 's13_readback'
    title = 'Back to the CPU'
    duration = 24.0
    cam = CamPath((0, (158.0, 70.0, 64.0)), (2.6, READ_VIEW), (24, READ_VIEW))
    captions = [
        (0.5, 5.0, 'The CPU reads port 330h. The read decoder pulls /SER_RD low.'),
        (5.2, 11.6, "The 595 drives the internal bus, and the 245 turns around to face the CPU."),
        (12.0, 15.8, 'EBh arrives in register AL.'),
        (16.2, 23.4, 'OTTERSD repeats this for every byte: send FFh, then read the answer.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U9', 'U7', 'U3', 'U11', 'J2'], 0.45 * prog(t, 1.5, 3.0))
        end = 23.4
        sig(f, '~{RD}', ('J2', finger('~{RD}')), t, 0.4, end, speed=40)
        lit(f, '~{PORTSEL}', t, 0.4, end, alpha=0.6)
        sig(f, 'Net-(U3A-E)', ('U2', '3'), t, 1.6, end, speed=30)
        sig(f, '~{RQ_SER_RD}', ('U3', '4'), t, 2.2, end, speed=30)
        sig(f, '~{SER_RD}', ('U11', '6'), t, 3.0, end, speed=30)
        f.tag(*f.s.pad_xy('U7', '13'), '/OE = 0: outputs on', C.ctrl, window(t, 4.6, 11.6, 0.4, 0.5), dx=-170,
              dy=-50, size=20, mono=True)
        f.tag(*f.s.pad_xy('U9', '1'), '/SER_RD = 0', C.ctrl, window(t, 2.6, 11.6, 0.4, 0.5), dx=-170, dy=40,
              size=20, mono=True)
        f.outline('U3', C.focus, window(t, 1.4, 5.2, 0.4, 0.5), label='read decoder', label_side='left')
        b = bits(RX_BYTE)
        for i in range(8):
            v = b[7 - i]
            al, w = (1.0, 1.0) if v else (0.22, 0.7)
            sig(f, f'D{i}', ('U7', U7_OUT[f'D{i}']), t, 5.6 + 0.05 * i, end, speed=24, alpha=al, width=w)
            sig(f, f'DB{i}', ('U9', U9_A[f'DB{i}']), t, 7.6 + 0.05 * i, end, speed=24, alpha=al, width=w)
            f.later(lambda fr, i=i, v=v: finger_bit(fr, finger(f'DB{i}'), v, C.data, window(t, 9.6 + 0.08 * i, end, 0.4, 0.6), size=34))
        # direction arrow flips
        da = window(t, 4.4, end, 0.5, 0.6)
        f.later(lambda fr: self.dir_arrow(fr, da))

    @staticmethod
    def dir_arrow(f, da):
        if da <= 0:
            return
        x0, y0, x1, y1 = f.box_s('U9', 0.6)
        arrow(f.ctx, x1 + 40, y0, x1 + 40, y1, C.data, 4, 16, da)
        f.pill('DIR = 0', x1 + 64, (y0 + y1) / 2 - 18, 20, C.ctrl, da, mono=True)
        f.pill('B → A: card → bus', x1 + 64, (y0 + y1) / 2 + 20, 18, C.dim_text, da, bold=False)

    def overlay(self, f, t):
        extra = ('AL = EBh', C.data) if t > 12.0 else None
        cpu(f.ctx, ['MOV DX, 330h', 'IN  AL, DX'], 1, t, 0.2, 16.0, active_t=0.4, extra=extra, y=70)
        wg.note(f.ctx, 'Per byte: OUT 330h, FFh starts the burst; two dummy reads give it time; IN 330h collects '
                       'the answer. 512 times per sector.', 60, 70, window(t, 16.4, 23.6, 0.6, 0.6), w=600,
                accent=C.data)


SCENE = Readback()
