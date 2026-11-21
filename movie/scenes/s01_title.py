"""S01 — Title and overview. Photo board, title card, then the card from a high
level: on the left the PC (an 8088/8086 that writes and reads bytes at I/O
ports), on the right the SD card (SPI: one bit at a time, with a clock), and the
card in the middle, bridging the two. Ends pushing in to the FULL shot of S02.
"""
from otter.anim import prog, window, clamp
from otter.camera import CamPath
from otter.config import C, W, H
from otter.draw import text, panel, rounded_rect, set_color, arrow
from otter.scene import Scene
from otter import widgets as wg
from .common import bits, TX_BYTE, RX_BYTE

# timeline (scene time; the narration lines start at these moments)
T_CARD = 6.0          # "It is an 8-bit ISA card ..."
T_PC = 16.0           # the PC side: I/O ports
T_OUT, T_IN = 23.8, 26.8          # OUT highlighted / IN highlighted
T_SD = 30.5           # the SD side: SPI
T_BRIDGE = 42.0       # the card in between
T_END = 53.5          # panels fade, camera pushes in
DURATION = 58.0

# panels (design px), either side of the card in the WIDE shot
LX, RX, PY, PW, PH = 36, 1494, 214, 392, 430
SD_GLYPH = (RX + 262, PY + 209, 96, 128)      # centred between the clock and data lines
LANE_X0, LANE_X1, LANE_Y = RX + 28, RX + 250, PY + 310
CLK_Y = PY + 236
BIT_P = 0.22          # seconds between bits on the SPI lane
BIT_V = 230.0         # px/s along the SPI lane
BYTE_V = 260.0        # px/s along the bus connector


def along(pts, u):
    """Point at fraction u (0..1) of the length of a polyline."""
    segs = [((x0, y0), (x1, y1), ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
            for (x0, y0), (x1, y1) in zip(pts, pts[1:])]
    d = clamp(u) * sum(s[2] for s in segs)
    for (x0, y0), (x1, y1), n in segs:
        if d <= n or n == 0:
            k = d / n if n else 0.0
            return x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
        d -= n
    return pts[-1]


def length(pts):
    return sum(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 for (x0, y0), (x1, y1) in zip(pts, pts[1:]))


def wire(ctx, pts, color, alpha, width=2.5):
    if alpha <= 0:
        return
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.set_line_width(width)
    set_color(ctx, color, 0.55 * alpha)
    ctx.stroke()


class Title(Scene):
    name = 's01_title'
    title = 'Title and overview'
    duration = DURATION
    cam = CamPath((0, 'WIDE'), (T_END + 0.5, 'WIDE'), (DURATION, 'FULL'), e='smooth')

    def draw(self, f, t):
        f.board(photo=1.0)
        f.dim(0.74 * (1 - prog(t, 5.6, 7.2)) + 0.25 * window(t, T_PC - 0.4, T_END + 1.0, 0.8, 1.0))
        # the two ends of the card light up when their side is introduced
        f.outline('J2', C.data, window(t, T_PC + 4.0, T_END, 0.6, 0.8), pad=0.6)
        f.outline('J1', C.spi, window(t, T_SD + 1.0, T_END, 0.6, 0.8), pad=0.4)

    def overlay(self, f, t):
        ctx = f.ctx
        # -- title card -------------------------------------------------------
        a = window(t, 1.4, 5.5, 1.0, 0.8)
        text(ctx, 'Slot-otter Classic', W / 2, H / 2 - 40 + (1 - a) * 10, 92, C.text, a, align='center', bold=True)
        ctx.rectangle(W / 2 - 70 * a, H / 2 - 4, 140 * a, 4)
        ctx.set_source_rgba(*C.data[:3], a)
        ctx.fill()
        text(ctx, 'How a byte reaches an SD card: 14 logic chips, eight clocks at a time.', W / 2, H / 2 + 52,
             32, (0.79, 0.83, 0.89, 1), a, align='center')
        # -- overview ---------------------------------------------------------
        pa = window(t, T_PC, T_END, 0.9, 1.0)
        if pa > 0:
            self.pc_side(f, t, pa)
        sa = window(t, T_SD, T_END, 0.9, 1.0)
        if sa > 0:
            self.sd_side(f, t, sa)
        ba = window(t, T_BRIDGE, T_END, 0.8, 1.0)
        if ba > 0:
            self.bridge(f, t, ba)

    # -- left: the PC and its I/O ports ---------------------------------------
    def pc_side(self, f, t, a):
        ctx = f.ctx
        panel(ctx, LX, PY, PW, PH, a)
        text(ctx, 'PC', LX + 26, PY + 50, 30, C.text, a, bold=True)
        text(ctx, '8088 / 8086 CPU', LX + 26, PY + 82, 20, C.dim_text, a)
        text(ctx, 'talks to hardware through I/O ports', LX + 26, PY + 132, 19, C.dim_text, a, italic=True)
        rows = [('OUT DX, AL', 'write a byte', T_OUT), ('IN  AL, DX', 'read a byte', T_IN)]
        for i, (code, what, ts) in enumerate(rows):
            y = PY + 196 + i * 58
            hl = prog(t, ts, ts + 0.4) * (1 - prog(t, ts + 3.6, ts + 4.0) if i == 0 else 1.0)
            if hl > 0:
                rounded_rect(ctx, LX + 14, y - 28, PW - 28, 40, 8)
                set_color(ctx, C.data, 0.18 * a * hl)
                ctx.fill()
            text(ctx, code, LX + 30, y, 23, C.text if hl > 0.5 else C.dim_text, a, mono=True)
            text(ctx, what, LX + 220, y, 19, C.data if hl > 0.5 else C.dim_text, a)
        text(ctx, 'port 330h', LX + 30, PY + 340, 20, C.addr, a * prog(t, T_OUT - 0.6, T_OUT), mono=True,
             bold=True)
        text(ctx, 'one byte at a time, eight bits wide', LX + 30, PY + 390, 18, C.dim_text,
             a * prog(t, T_OUT - 0.6, T_OUT))
        # the bus: from the panel down to the card edge
        x0, y0, x1, y1 = f.box_s('J2', 0.6)
        yb = (y0 + y1) / 2
        pts = [(LX + PW / 2, PY + PH), (LX + PW / 2, yb), (x0 - 6, yb)]
        wa = a * prog(t, T_PC + 3.0, T_PC + 4.0)
        wire(ctx, pts, C.data, wa, 3)
        text(ctx, 'ISA bus', LX + PW / 2 - 48, PY + PH + 46, 18, C.data, wa, align='right', bold=True)  # clear of the byte
        n = length(pts)
        # OUT: 51h travels to the card; IN: EBh travels back
        if self.in_flight(t, T_OUT, n / BYTE_V):
            u = (t - T_OUT) / (n / BYTE_V)
            wg.byte_card(ctx, *along(pts, u), TX_BYTE, C.data, a, size=24)
        if self.in_flight(t, T_IN, n / BYTE_V):
            u = 1 - (t - T_IN) / (n / BYTE_V)
            wg.byte_card(ctx, *along(pts, u), RX_BYTE, C.data, a, size=24)
        if t >= T_BRIDGE:                       # in the bridge: bytes go back and forth
            k = (t - T_BRIDGE) % 6.0
            if k < n / BYTE_V:
                wg.byte_card(ctx, *along(pts, k / (n / BYTE_V)), TX_BYTE, C.data, a, size=24)
            elif 3.0 <= k < 3.0 + n / BYTE_V:
                wg.byte_card(ctx, *along(pts, 1 - (k - 3.0) / (n / BYTE_V)), RX_BYTE, C.data, a, size=24)

    @staticmethod
    def in_flight(t, t0, dur):
        return t0 <= t <= t0 + dur

    # -- right: the SD card and SPI -------------------------------------------
    def sd_side(self, f, t, a):
        ctx = f.ctx
        panel(ctx, RX, PY, PW, PH, a)
        text(ctx, 'SD card', RX + 26, PY + 50, 30, C.text, a, bold=True)
        text(ctx, 'speaks SPI', RX + 26, PY + 82, 20, C.dim_text, a)
        text(ctx, 'one bit at a time, in step with a clock', RX + 26, PY + 132, 19, C.dim_text, a, italic=True)
        # the card glyph (notched corner)
        x, y, w, h = SD_GLYPH
        ctx.move_to(x, y)
        ctx.line_to(x + w - 26, y)
        ctx.line_to(x + w, y + 26)
        ctx.line_to(x + w, y + h)
        ctx.line_to(x, y + h)
        ctx.close_path()
        set_color(ctx, C.bg2, a)
        ctx.fill_preserve()
        ctx.set_line_width(2.5)
        set_color(ctx, C.spi, a)
        ctx.stroke()
        text(ctx, 'SD', x + w / 2, y + h / 2 + 4, 30, C.text, a, align='center', valign='middle', bold=True)
        # clock and data lane
        la = a * prog(t, T_SD + 1.0, T_SD + 2.0)
        text(ctx, 'clock', LANE_X0, CLK_Y - 30, 16, C.clock, la, bold=True)
        text(ctx, 'data', LANE_X0, LANE_Y - 30, 16, C.spi, la, bold=True)
        wire(ctx, [(LANE_X0, LANE_Y), (LANE_X1, LANE_Y)], C.spi, la)
        arrow(ctx, LANE_X1 - 6, LANE_Y, LANE_X1 + 6, LANE_Y, C.spi, 2.5, 9, la)
        run = t >= T_SD + 2.0
        k = (t - T_SD - 2.0) % 4.0 if run else -1.0
        # square wave: one period per bit while the byte is moving, flat otherwise
        hi, lo = CLK_Y - 12, CLK_Y + 12
        ctx.new_path()
        steps = 120
        pts = []
        for j in range(steps + 1):
            xx = LANE_X0 + (LANE_X1 - LANE_X0) * j / steps
            age = k - (xx - LANE_X0) / BIT_V            # when this point's signal left the panel edge
            high = 0 <= age < 8 * BIT_P and (age / BIT_P) % 1.0 < 0.5
            pts.append((xx, hi if high else lo))
        ctx.move_to(*pts[0])
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if y1 != y0:
                ctx.line_to(x1, y0)
            ctx.line_to(x1, y1)
        ctx.set_line_width(2.2)
        set_color(ctx, C.clock, la)
        ctx.stroke()
        b = bits(TX_BYTE)
        for i in range(8):
            xx = LANE_X0 + BIT_V * (k - i * BIT_P)
            if run and LANE_X0 + 15 <= xx <= LANE_X1 - 24:          # stop short of the arrowhead
                wg.bit_cell(ctx, xx, LANE_Y, 30, b[i], C.spi, la)
        text(ctx, 'MOSI, MISO, SCK, /CS: four wires', RX + 26, PY + 390, 18, C.dim_text, la)
        # the link to the card's socket
        x0, y0, x1, y1 = f.box_s('J1', 0.4)
        ym = (y0 + y1) / 2
        wire(ctx, [(x1 + 4, ym), (RX, ym)], C.spi, a * prog(t, T_SD + 1.0, T_SD + 2.0), 3)

    # -- the card in between --------------------------------------------------
    def bridge(self, f, t, a):
        ctx = f.ctx
        cx, cy = W / 2 - 10, 470
        panel(ctx, cx - 250, cy - 66, 500, 132, a)
        text(ctx, 'Slot-otter', cx, cy - 18, 30, C.text, a, align='center', bold=True)
        text(ctx, 'bytes', cx - 62, cy + 30, 26, C.data, a, align='right', bold=True)
        arrow(ctx, cx - 40, cy + 14, cx + 40, cy + 14, C.data, 2.5, 9, a)     # bytes -> bits
        arrow(ctx, cx + 40, cy + 30, cx - 40, cy + 30, C.spi, 2.5, 9, a)      # bits -> bytes
        text(ctx, 'bits', cx + 62, cy + 30, 26, C.spi, a, bold=True)


SCENE = Title()
