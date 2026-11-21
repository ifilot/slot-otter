"""S04 — The card edge: OUT 330h, 51h appears on the ISA fingers."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel
from otter.scene import Scene
from .common import finger, bits, bracket, finger_bit, cpu, PORT, TX_BYTE, IOW_FINGER, IOR_FINGER

EDGE_VIEW = (117.0, 108.7, 88.0)
ADDR = [f'A{i}' for i in range(9, -1, -1)]       # A9..A0
DATA = [f'DB{i}' for i in range(7, -1, -1)]      # DB7..DB0


T_CMD, T_BUS, T_IOW = 6.4, 13.8, 17.2      # narration lines 2-4
END = 28.4


class Edge(Scene):
    name = 's04_edge'
    title = 'The card edge'
    duration = 29.0
    cam = CamPath((0, 'FULL'), (3.2, EDGE_VIEW), (29, EDGE_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['J2'], 0.6 * prog(t, 2.0, 3.5))
        ga = window(t, T_BUS - 0.4, END, 0.7, 0.5)
        # the edge runs the other way round from the panel (A9 … A0): say so
        f.later(lambda fr: (bracket(fr, [finger(d) for d in DATA], 'D0 → D7', C.data, ga,
                                    sub='data · mirrored: D0 on the left'),
                            bracket(fr, [finger(a) for a in ADDR], 'A0 → A9', C.addr, ga,
                                    sub='address · mirrored: A0 on the left')))
        av = [(PORT >> (9 - i)) & 1 for i in range(10)]
        dv = bits(TX_BYTE)
        items = []
        for i, (a_name, v) in enumerate(zip(ADDR, av)):
            ai = prog(t, T_BUS + i * 0.08, T_BUS + 0.4 + i * 0.08)
            if v:
                f.pads_glow([('J2', finger(a_name))], C.addr, ai)
            items.append((finger(a_name), v, C.addr, ai))
        for i, (d_name, v) in enumerate(zip(DATA, dv)):
            ai = prog(t, T_BUS + 0.9 + i * 0.08, T_BUS + 1.3 + i * 0.08)
            if v:
                f.pads_glow([('J2', finger(d_name))], C.data, ai)
            items.append((finger(d_name), v, C.data, ai))
        f.later(lambda fr: [finger_bit(fr, p, v, col, a, size=30) for p, v, col, a in items])

        # rear-side strobes: ghosts drawn exactly over their fingers, labelled as the B side
        ra = prog(t, T_IOW, T_IOW + 0.8)
        if ra > 0:
            iow_low = prog(t, T_IOW + 0.8, T_IOW + 1.2)
            act = prog(t, T_IOW + 3.0, T_IOW + 3.6)
            f.later(lambda fr: self.rear(fr, ra, iow_low, act))

    def rear(self, f, ra, iow_low, act):
        f.back_pads([('J2', IOW_FINGER), ('J2', IOR_FINGER)], C.text, ra * 0.9,
                    lit={('J2', IOW_FINGER)} if iow_low > 0.5 else None, lit_color=C.ctrl)
        p = f.s.board.pad('J2', IOW_FINGER)
        q = f.s.board.pad('J2', IOR_FINGER)
        f._tag(p.x, p.y - p.h / 2, '/IOW = 0: write' if act > 0.5 else '/IOW = 0', C.ctrl, ra, 80, -95, 22,
               True, True, True, True, None)
        f._tag(q.x, q.y - q.h / 2, '/IOR = 1', C.dim_text, ra, -80, -95, 22, True, True, True, True, None)
        # the ghosts are the rear (B) fingers: a small bracket under them says so
        bracket(f, [IOR_FINGER, IOW_FINGER], 'rear side (B)', C.text, ra, size=18)
        # the slash note sits right above the /IOW label, slash over slash
        sx, sy = f.sxy(p.x, p.y - p.h / 2)
        lab = '/IOW = 0: write' if act > 0.5 else '/IOW = 0'
        bx, by, _tw, _pw, ph = f._pill_geom(lab, sx + 80 + 10, sy - 95 - 11, 22, 'left', True, True)
        f.pill('/ = active when low (0 V)', bx, by - ph - 10, 20, C.ctrl, ra * act, mono=True)

    def overlay(self, f, t):
        cpu(f.ctx, ['MOV DX, 330h', 'MOV AL, 51h', 'OUT DX, AL'], 2, t, 1.0, END, active_t=1.2)
        ctx = f.ctx
        a = window(t, T_CMD, END, 0.6, 0.6)
        if a > 0:
            b = prog(t, T_BUS, T_BUS + 0.6)
            panel(ctx, 1380, 60, 480, 168 + 112 * b, a)
            text(ctx, 'data  (D7 … D0)', 1406, 100, 18, C.dim_text, a, bold=True)
            text(ctx, '0101 0001', 1406, 142, 32, C.data, a, mono=True, bold=True)
            text(ctx, '= 51h', 1680, 142, 32, C.text, a, mono=True)
            text(ctx, 'SD command: read one block', 1406, 182, 19, C.data, a, italic=True)
            text(ctx, 'address  (A9 … A0)', 1406, 236, 18, C.dim_text, a * b, bold=True)
            text(ctx, '11 0011 0000', 1406, 278, 32, C.addr, a * b, mono=True, bold=True)
            text(ctx, '= 330h', 1680, 278, 32, C.text, a * b, mono=True)


SCENE = Edge()
