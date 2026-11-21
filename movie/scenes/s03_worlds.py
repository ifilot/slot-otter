"""S03 — Two worlds: the PC talks in bytes (parallel), the SD card in bits (SPI).

Two schematic panels over the dimmed board, then the two worlds are mapped
onto the real card: card edge = bytes, microSD socket = bits.
"""
from otter.anim import prog, window, clamp
from otter.camera import CamPath, drift, shot
from otter.config import C, W
from otter.draw import text, panel, rounded_rect, set_color, glow_stroke, arrow
from otter.scene import Scene
from otter import widgets as wg
from .common import bits, TX_BYTE, RX_BYTE, LOGIC

# panel geometry (design px)
LX, RX, PY, PW, PH = 70, 1020, 150, 830, 600
# left panel: CPU and the ISA data wires
CPU_BOX = (LX + 30, PY + 170, 150, 300)
WIRE_X0, WIRE_X1 = LX + 250, LX + PW - 40
WIRE_Y0, WIRE_DY = PY + 210, 30
ADDR_Y = PY + 125
# right panel: four SPI lanes into the card
LANE_X0, LANE_X1 = RX + 170, RX + 550          # the card's left edge is LANE_X1
CARD = (RX + 550, PY + 120, 260, 420)           # wide enough for its 8-bit register in one row
REG_CELL, REG_GAP, REG_NIB = 26, 3, 8           # register cells: size, gap, extra gap between nibbles
LANES = [('/CS', PY + 190), ('SCK', PY + 280), ('MOSI', PY + 370), ('MISO', PY + 460)]
LANE_Y = {k: y for k, y in LANES}
SPACING = 56                                    # px between bits on a lane

# timeline (scene time; the narration lines start at these moments)
T_PC, T_BYTE = 4.4, 6.4                         # bytes: wires, then the byte travels
T_SPI, MOSI_T0 = 15.2, 16.2       # MOSI stream: start, seconds per bit
T_CLK = 21.8                                    # the clock lane is explained
T_MISO, MISO_T0 = 28.8, 29.4
T_CS = 34.4
T_JOB = 40.4
T_MAP = 45.8


# Speeds: a bit on an SPI wire moves eight times as fast as a byte on the
# parallel bus (same data rate, one wire instead of eight).
V_BYTE = 40.0                                   # px/s, the byte on the ISA wires
V_BIT = 8 * V_BYTE                              # px/s, bits on MOSI / MISO
P_BIT = SPACING / V_BIT                         # seconds between bits
TRAVEL = (LANE_X1 - LANE_X0) / V_BIT            # seconds for a bit to cross the lane
BURST = 3.2                                     # one byte (eight clocks) every BURST seconds
MOSI_BURSTS = [MOSI_T0 + i * BURST for i in range(4)]
MISO_BURSTS = [MISO_T0 + i * BURST for i in range(4)]


def burst_at(t, starts):
    """The latest burst start <= t (or None)."""
    cur = None
    for ts in starts:
        if t >= ts:
            cur = ts
    return cur


def reg_in(t):
    """How many bits of the first MOSI burst have reached the card's register.
    The later bursts carry the same byte, so the register stays full after it."""
    ts = MOSI_BURSTS[0]
    if t < ts + TRAVEL:
        return 0
    return min(8, int((t - ts - TRAVEL) / P_BIT) + 1)


T_REG_FULL = MOSI_BURSTS[0] + TRAVEL + 7 * P_BIT   # the eighth bit is in


class Worlds(Scene):
    name = 's03_worlds'
    title = 'Two worlds'
    duration = 52.0
    cam = CamPath((0, 'FULL'), (52, 'FULL'))

    def view(self, t):
        return drift(shot('FULL'), t, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        panels = window(t, 0.6, T_MAP + 1.2, 0.9, 1.0)
        f.dim(0.78 * panels)
        m = window(t, T_MAP + 0.8, 52.5, 0.8, 0.6)
        if m > 0:
            f.outline('J2', C.data, m, pad=0.6, label='bytes · ISA bus', label_side='right')
            f.outline('J1', C.spi, m, pad=0.4, label='bits · SPI', label_side='top')
            for ref in LOGIC:
                f.outline(ref, C.focus, 0.35 * m * prog(t, T_MAP + 1.6, T_MAP + 2.6), pad=0.4, width=1.4)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, 0.6, T_MAP + 1.2, 0.9, 1.0)
        if a <= 0:
            return
        self.pc_panel(ctx, t, a)
        self.spi_panel(ctx, t, a)
        ja = window(t, T_JOB, T_MAP + 1.2, 0.6, 0.8)
        if ja > 0:
            text(ctx, 'this card:', W / 2 - 150, 104, 30, C.dim_text, a * ja, align='right')
            text(ctx, 'bytes → bits → bytes', W / 2 - 130, 104, 40, C.text, a * ja, bold=True)

    # -- left: the PC -------------------------------------------------------
    @staticmethod
    def pc_panel(ctx, t, a):
        panel(ctx, LX, PY, PW, PH, a)
        text(ctx, 'PC', LX + 30, PY + 52, 30, C.text, a, bold=True)
        text(ctx, 'ISA bus: bytes, eight wires at once', LX + 30, PY + 84, 20, C.dim_text, a)
        x, y, w, h = CPU_BOX
        rounded_rect(ctx, x, y, w, h, 12)
        set_color(ctx, C.bg2, a)
        ctx.fill_preserve()
        ctx.set_line_width(2)
        set_color(ctx, C.panel_edge, a)
        ctx.stroke()
        text(ctx, 'CPU', x + w / 2, y + h / 2, 30, C.text, a, align='center', valign='middle', bold=True)
        wa = a * prog(t, T_PC, T_PC + 0.8)
        # address bus: one wide band
        rounded_rect(ctx, WIRE_X0 - 40, ADDR_Y - 18, WIRE_X1 - WIRE_X0 + 40, 36, 8)
        set_color(ctx, C.addr, 0.16 * wa)
        ctx.fill()
        text(ctx, 'address', WIRE_X0 - 30, ADDR_Y, 18, C.addr, wa, valign='middle', bold=True)
        aa = wa * prog(t, T_BYTE, T_BYTE + 0.6)
        text(ctx, '330h', WIRE_X1 - 10, ADDR_Y, 22, C.addr, aa, align='right', valign='middle', mono=True,
             bold=True)
        # eight data wires D7..D0
        dist = WIRE_X1 - WIRE_X0 - 150
        u = clamp((t - T_BYTE) * V_BYTE / dist)        # constant speed: 1/8 of a bit on SPI
        b = bits(TX_BYTE)
        for i in range(8):
            y_ = WIRE_Y0 + i * WIRE_DY
            text(ctx, f'D{7 - i}', WIRE_X0 - 30, y_, 16, C.dim_text, wa, valign='middle', mono=True)
            ctx.move_to(WIRE_X0, y_)
            ctx.line_to(WIRE_X1, y_)
            ctx.set_line_width(2)
            set_color(ctx, C.data, 0.45 * wa)
            ctx.stroke()
            if t >= T_BYTE:
                bx = WIRE_X0 + 20 + u * (WIRE_X1 - WIRE_X0 - 150)
                wg.bit_cell(ctx, bx, y_, 24, b[i], C.data, wa)
        ba = wa * prog(t, T_BYTE + dist / V_BYTE, T_BYTE + dist / V_BYTE + 0.6)
        wg.byte_card(ctx, WIRE_X1 - 70, WIRE_Y0 + 8 * WIRE_DY + 30, TX_BYTE, C.data, ba, size=30)

    # -- right: the SD card ---------------------------------------------------
    @staticmethod
    def spi_panel(ctx, t, a):
        pa = a * prog(t, T_SPI - 0.4, T_SPI + 0.6)
        panel(ctx, RX, PY, PW, PH, a)
        text(ctx, 'SD card', RX + 30, PY + 52, 30, C.text, a, bold=True)
        text(ctx, 'SPI: bits, one at a time', RX + 30, PY + 84, 20, C.dim_text, a)
        x, y, w, h = CARD
        rounded_rect(ctx, x, y, w, h, 14)
        set_color(ctx, C.bg2, a)
        ctx.fill_preserve()
        ctx.set_line_width(2)
        set_color(ctx, C.panel_edge, a)
        ctx.stroke()
        text(ctx, 'SD', x + w / 2, y + 60, 34, C.text, a, align='center', bold=True)
        # lane visibility: each lane comes forward when the narration names it
        lane_a = {'MOSI': pa,
                  'SCK': pa * (0.35 + 0.65 * prog(t, T_CLK, T_CLK + 0.6)),
                  'MISO': pa * (0.35 + 0.65 * prog(t, T_MISO, T_MISO + 0.6)),
                  '/CS': pa * (0.35 + 0.65 * prog(t, T_CS, T_CS + 0.6))}
        cols = {'MOSI': C.spi, 'SCK': C.clock, 'MISO': C.spi, '/CS': C.ctrl}
        for name, y_ in LANES:
            la = lane_a[name]
            text(ctx, name, RX + 30, y_, 22, cols[name], la, valign='middle', mono=True, bold=True)
            if name not in ('SCK', '/CS'):
                ctx.move_to(LANE_X0, y_)
                ctx.line_to(LANE_X1, y_)
                ctx.set_line_width(2)
                set_color(ctx, cols[name], 0.45 * la)
                ctx.stroke()
        # direction arrows
        arrow(ctx, LANE_X0 - 48, LANE_Y['MOSI'], LANE_X0 - 12, LANE_Y['MOSI'], C.spi, 2.5, 9, lane_a['MOSI'])
        arrow(ctx, LANE_X0 - 12, LANE_Y['MISO'], LANE_X0 - 48, LANE_Y['MISO'], C.spi, 2.5, 9, lane_a['MISO'])
        # /CS: a level, low
        y_ = LANE_Y['/CS']
        hi, lo = y_ - 14, y_ + 14
        ctx.move_to(LANE_X0, lo)
        ctx.line_to(LANE_X1, lo)
        ctx.set_line_width(2.6)
        set_color(ctx, C.ctrl, lane_a['/CS'])
        ctx.stroke()
        ca = pa * window(t, T_CS + 0.4, T_MAP + 1.2, 0.5, 0.6)
        text(ctx, 'low (0 V): listening', LANE_X0 + 10, hi - 4, 18, C.ctrl, ca, bold=True)
        # SCK: in every burst eight pulses travel towards the card; each rising
        # edge reaches the card together with a bit (MOSI) or sends one off (MISO)
        y_ = LANE_Y['SCK']
        hi, lo = y_ - 16, y_ + 16
        ctx.new_path()
        n, pts = 260, []
        starts = MOSI_BURSTS + MISO_BURSTS
        for j in range(n + 1):
            xx = LANE_X0 + (LANE_X1 - LANE_X0) * j / n
            high = False
            for ts in starts:
                kf = (t - ts - (xx - LANE_X0) / V_BIT) / P_BIT
                if 0 <= kf < 8 and (kf % 1.0) < 0.5:
                    high = True
                    break
            pts.append((xx, hi if high else lo))
        ctx.move_to(*pts[0])
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if y1 != y0:
                ctx.line_to(x1, y0)
            ctx.line_to(x1, y1)
        ctx.set_line_width(2.6)
        set_color(ctx, C.clock, lane_a['SCK'])
        ctx.stroke()
        # MOSI bits, burst after burst
        b = bits(TX_BYTE)
        for ts in MOSI_BURSTS:
            for k in range(8):
                xx = LANE_X0 + V_BIT * (t - ts - k * P_BIT)
                if LANE_X0 - 1 <= xx <= LANE_X1 and t >= ts + k * P_BIT:
                    wg.bit_cell(ctx, xx, LANE_Y['MOSI'], 30, b[k], C.spi, pa)
        # the card's own register: one row, filled MSB first (bit 7 leftmost,
        # as on the PC side); it keeps 51h once the first byte is in
        n_in = reg_in(t)
        row_w = 8 * REG_CELL + 7 * REG_GAP + REG_NIB
        rx = x + (w - row_w) / 2 + REG_CELL / 2
        for i in range(8):
            cx = rx + i * (REG_CELL + REG_GAP) + (REG_NIB if i >= 4 else 0)
            wg.bit_cell(ctx, cx, y + 130, REG_CELL, b[i] if i < n_in else None, C.spi, pa)
        ra = pa * prog(t, T_REG_FULL, T_REG_FULL + 0.4)
        text(ctx, '51h', x + w / 2, y + 182, 28, C.spi, ra, align='center', mono=True, bold=True)
        # MISO bits leave the card when their clock pulse arrives
        r = bits(RX_BYTE)
        for ts in MISO_BURSTS:
            for k in range(8):
                t_leave = ts + TRAVEL + k * P_BIT
                xx = LANE_X1 - V_BIT * (t - t_leave)
                if LANE_X0 <= xx <= LANE_X1 and t >= t_leave:
                    wg.bit_cell(ctx, xx, LANE_Y['MISO'], 30, r[k], C.spi, lane_a['MISO'])


SCENE = Worlds()
