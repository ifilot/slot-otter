"""S06 — What does the CPU want? The '139 turns A1/A0 + read/write into one action."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.scene import Scene
from otter import widgets as wg
from .common import finger, sig, lit

LOGIC_VIEW = (122.0, 89.5, 78.0)
# narration: question 1.0, decoder 6.4, write 330h 12.6, read 330h 18.8, housekeeping 22.2
T_DEC, T_WR, T_RD, T_HK = 6.4, 12.6, 18.8, 22.2
END = 24.9
ROWS = [
    ['330h', "fetch the card's reply", 'send a byte'],
    ['331h', 'read + 8 clocks', '8 clocks'],
    ['332h', 'chip select off', '–'],
    ['333h', 'chip select on', '–'],
]


class Registers(Scene):
    name = 's06_registers'
    title = 'What does the CPU want?'
    duration = 25.5
    cam = CamPath((0, (106.0, 92.0, 64.0)), (3.2, LOGIC_VIEW), (25.5, LOGIC_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U2', 'U3'], 0.62 * prog(t, 1.5, 3.0))
        lit(f, '~{PORTSEL}', t, -1.0, END, t_dim=T_DEC)
        sig(f, '~{WR}', ('J2', finger('~{WR}')), t, 0.8, END, speed=34, t_dim=T_DEC)
        sig(f, 'Net-(U3B-E)', ('U2', '6'), t, 3.0, END, speed=25, t_dim=T_WR)
        for a in ('A0', 'A1'):
            sig(f, a, ('J2', finger(a)), t, T_DEC - 0.4, END, speed=34, alpha=0.25, width=0.7)
        sig(f, '~{SER_WR}', ('U3', '12'), t, T_WR + 0.4, END, speed=30, t_dim=T_RD)
        # the read: /IOR through the '32's other gate into the read half of the '139,
        # whose output 1Y0 (/RQ_SER_RD) asks for the card's reply
        sig(f, '~{RD}', ('J2', finger('~{RD}')), t, T_RD - 0.2, END, speed=34)
        sig(f, 'Net-(U3A-E)', ('U2', '3'), t, T_RD + 0.2, END, speed=25)
        sig(f, '~{RQ_SER_RD}', ('U3', '4'), t, T_RD + 0.5, END, speed=30, color=C.data)
        ti = window(t, 1.0, T_DEC, 0.5, 0.5)
        f.tag(*f.s.pad_xy('U2', '4'), 'addressed', C.ctrl, ti, dx=-170, dy=-70, size=20)
        f.tag(*f.s.pad_xy('U2', '5'), '/IOW: write', C.ctrl, ti, dx=-150, dy=80, size=20, mono=True)
        tb = window(t, T_DEC + 0.6, T_RD, 0.5, 0.6)
        f.tag(*f.s.pad_xy('U3', '14'), 'A1 = 0, A0 = 0', C.addr, tb, dx=-190, dy=40, size=20, mono=True)
        tc = window(t, T_WR + 0.6, END, 0.5, 0.6) * (1 - 0.65 * prog(t, T_RD, T_RD + 0.5))
        f.tag(*f.s.pad_xy('U3', '12'), 'action: send a byte', C.ctrl, tc, dx=110, dy=-80, size=22)
        td = window(t, T_RD + 0.6, END, 0.5, 0.6)
        # pinned where 1Y0's track runs up through the clear gap between U5 and U3
        f.tag(f.s.pad_xy('U3', '4')[0], 93.0, 'action: fetch the reply', C.data, td, dx=-150, dy=0, size=22)
        f.outline('U2', C.focus, window(t, 0.8, T_DEC, 0.5, 0.6), label_alpha=0.0)
        f.outline('U3', C.focus, window(t, T_DEC, T_RD, 0.5, 0.6), label='74HCT139 · decoder', label_side='right')

    def overlay(self, f, t):
        a = window(t, T_DEC + 0.6, END, 0.6, 0.6)
        hw = prog(t, T_WR, T_WR + 0.5)
        hr = prog(t, T_RD, T_RD + 0.5)
        dim = 1 - 0.55 * prog(t, T_WR, T_WR + 0.6) * (1 - prog(t, T_HK, T_HK + 0.6))
        # compact and high enough to clear U8's '74HCT688' lettering below it
        wg.table(f.ctx, 70, 110, ['port', 'IN  (read, /IOR)', 'OUT  (write, /IOW)'], ROWS, a,
                 col_w=[110, 330, 260], row_h=42, reveal=(t - T_DEC - 1.0) * 1.6,
                 highlight=[(0, 2, hw, C.ctrl), (0, 1, hr, C.data)], row_alpha=[1, dim, dim, dim])


SCENE = Registers()
