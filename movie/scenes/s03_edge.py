"""S03 — The card edge: OUT 330h, 51h appears on the ISA fingers."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel
from otter.scene import Scene
from .common import finger, bits, bracket, finger_bit, cpu, PORT, TX_BYTE, IOW_FINGER, IOR_FINGER

EDGE_VIEW = (117.0, 108.7, 88.0)
ADDR = [f'A{i}' for i in range(9, -1, -1)]       # A9..A0
DATA = [f'DB{i}' for i in range(7, -1, -1)]      # DB7..DB0


class Edge(Scene):
    name = 's03_edge'
    title = 'The card edge'
    duration = 26.0
    cam = CamPath((0, 'FULL'), (3.2, EDGE_VIEW), (26, EDGE_VIEW))
    captions = [
        (1.0, 5.6, 'The CPU executes one instruction: write the byte 51h to I/O port 330h.'),
        (6.0, 9.8, 'For a moment the bus carries an address and a byte…'),
        (10.0, 13.6, '51h is not random: it starts the SD command "read one block".'),
        (13.8, 17.6, '…and a "write" strobe, /IOW, on the back of the card.'),
        (17.8, 21.6, 'A slash means "active low": /IOW acts when its wire is at 0 V.'),
        (21.8, 25.6, 'AEN low means the CPU, not DMA, is driving the bus.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['J2'], 0.6 * prog(t, 2.0, 3.5))
        ga = window(t, 4.0, 26.5, 0.7, 0.5)
        f.later(lambda fr: (bracket(fr, [finger(d) for d in DATA], 'D0 … D7', C.data, ga, sub='data'),
                            bracket(fr, [finger('AEN')], 'AEN', C.addr, ga),
                            bracket(fr, [finger(a) for a in ADDR], 'A0 … A9', C.addr, ga,
                                    sub='address (the card uses these ten)')))
        av = [(PORT >> (9 - i)) & 1 for i in range(10)]
        dv = bits(TX_BYTE)
        items = []
        for i, (a_name, v) in enumerate(zip(ADDR, av)):
            ai = prog(t, 6.0 + i * 0.12, 6.4 + i * 0.12)
            if v:
                f.pads_glow([('J2', finger(a_name))], C.addr, ai)
            items.append((finger(a_name), v, C.addr, ai))
        for i, (d_name, v) in enumerate(zip(DATA, dv)):
            ai = prog(t, 10.0 + i * 0.12, 10.4 + i * 0.12)
            if v:
                f.pads_glow([('J2', finger(d_name))], C.data, ai)
            items.append((finger(d_name), v, C.data, ai))
        items.append((finger('AEN'), 0, C.addr, prog(t, 21.8, 22.4)))
        f.later(lambda fr: [finger_bit(fr, p, v, col, a, size=30) for p, v, col, a in items])

        # rear-side strobes: ghosts drawn exactly over their fingers, labelled as the B side
        ra = prog(t, 13.8, 14.6)
        if ra > 0:
            iow_low = prog(t, 14.6, 15.0)
            f.later(lambda fr: self.rear(fr, ra, iow_low))

    def rear(self, f, ra, iow_low):
        f.back_pads([('J2', IOW_FINGER), ('J2', IOR_FINGER)], C.text, ra * 0.9,
                    lit={('J2', IOW_FINGER)} if iow_low > 0.5 else None, lit_color=C.ctrl)
        p = f.s.board.pad('J2', IOW_FINGER)
        q = f.s.board.pad('J2', IOR_FINGER)
        f._tag(p.x, p.y - p.h / 2, '/IOW = 0', C.ctrl, ra, 80, -95, 22, True, True, True, True, None)
        f._tag(q.x, q.y - q.h / 2, '/IOR = 1', C.dim_text, ra, -80, -95, 22, True, True, True, True, None)
        x, y = f.sxy((p.x + q.x) / 2, p.y - p.h / 2)
        f.pill('rear side (B) of the edge', x, y - 175, 20, C.text, ra, align='center', bold=False)

    def overlay(self, f, t):
        cpu(f.ctx, ['MOV DX, 330h', 'MOV AL, 51h', 'OUT DX, AL'], 2, t, 1.0, 25.4, active_t=1.2)
        ctx = f.ctx
        a = window(t, 6.4, 25.4, 0.6, 0.6)
        if a > 0:
            b = prog(t, 10.0, 10.6)
            panel(ctx, 1420, 60, 440, 150 + 112 * b, a)
            text(ctx, 'address  (A9 … A0)', 1446, 100, 18, C.dim_text, a, bold=True)
            text(ctx, '11 0011 0000', 1446, 142, 32, C.addr, a, mono=True, bold=True)
            text(ctx, '= 330h', 1700, 142, 32, C.text, a, mono=True)
            text(ctx, 'data  (D7 … D0)', 1446, 212, 18, C.dim_text, a * b, bold=True)
            text(ctx, '0101 0001', 1446, 254, 32, C.data, a * b, mono=True, bold=True)
            text(ctx, '= 51h', 1700, 254, 32, C.text, a * b, mono=True)


SCENE = Edge()
