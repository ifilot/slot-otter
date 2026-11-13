"""Circuit facts and helpers shared by the scenes.

Pin maps come from the netlist of pcb/release/isa-sdcard.kicad_pcb.
"""
from __future__ import annotations

import math

from otter.anim import prog, window, clamp, smooth, smoother, Schedule
from otter.config import C, W, H
from otter.draw import (text, rounded_rect, set_color, panel, lighten, glow_dot, arrow, font, text_width, polyline,
                        glow_stroke)
from otter.netflow import Polyline
from otter import widgets as wg

# ISA edge (J2). Front (A) side carries data and address, rear (B) side the strobes.
ADDR_FINGER = {f'A{i}': f'A{31 - i:02d}' for i in range(10)}        # A0 -> A31 ... A9 -> A22
DATA_FINGER = {f'DB{i}': f'A{9 - i:02d}' for i in range(8)}         # DB0 -> A09 ... DB7 -> A02
AEN_FINGER = 'A11'
IOW_FINGER, IOR_FINGER = 'B13', 'B14'


def finger(name):
    """J2 pad name for a bus signal (pads are 'A31', 'A02', ...)."""
    if name in ADDR_FINGER:
        p = ADDR_FINGER[name]
    elif name in DATA_FINGER:
        p = DATA_FINGER[name]
    elif name == 'AEN':
        p = AEN_FINGER
    elif name == '~{WR}':
        p = IOW_FINGER
    elif name == '~{RD}':
        p = IOR_FINGER
    else:
        raise KeyError(name)
    return p[0] + str(int(p[1:])).zfill(2)


# 74HCT688: P0..P7 = A2..A9, Q0..Q7 = switches.
U8_P = {f'A{i + 2}': str(pin) for i, pin in enumerate([2, 4, 6, 8, 11, 13, 15, 17])}
# 74HCT245: A side = DB0..7 on pins 2..9, B side = D0..7 on pins 18..11.
U9_A = {f'DB{i}': str(2 + i) for i in range(8)}
U9_B = {f'D{i}': str(18 - i) for i in range(8)}
# 74HC165 parallel inputs (A..H = D0..D7).
U6_IN = {'D0': '11', 'D1': '12', 'D2': '13', 'D3': '14', 'D4': '3', 'D5': '4', 'D6': '5', 'D7': '6'}
# 74HC595 outputs (QA..QH = D0..D7).
U7_OUT = {'D0': '15', 'D1': '1', 'D2': '2', 'D3': '3', 'D4': '4', 'D5': '5', 'D6': '6', 'D7': '7'}

PORT = 0x330
TX_BYTE = 0x51          # CMD17 start byte
RX_BYTE = 0xEB          # first byte of a FAT boot sector
CMD17 = [0x51, 0x00, 0x00, 0x08, 0x00, 0xE5]   # read block, LBA 2048, CRC7

BLOCKS = [
    # (label, colour, refs, label anchor ref, label side)
    ('Card edge', C.addr, ['J2'], 'J2', 'right'),
    ('Address match', C.addr, ['SW1', 'U8'], 'U8', 'top'),
    ('Register decode', C.ctrl, ['U2', 'U3', 'U5'], 'U2', 'top'),
    ('Data gate', C.data, ['U9'], 'U9', 'bottom'),
    ('Clock burst', C.clock, ['X1', 'U4', 'U1', 'U10', 'U13', 'U11', 'U12'], 'U4', 'top'),
    ('Shift registers', C.data, ['U6', 'U7'], 'U6', 'top'),
    ('3.3 V side', C.spi, ['U16', 'U21', 'J1'], 'U21', 'top'),
]


def bits(byte):
    return [(byte >> (7 - i)) & 1 for i in range(8)]


def focus(t, t_dim, level=0.35, fade=0.6):
    """1 until t_dim, then eases to `level`: earlier subjects step back."""
    if t_dim is None:
        return 1.0
    return 1.0 - (1.0 - level) * prog(t, t_dim, t_dim + fade, 'smooth')


def sig(f, net, src, t, t0, t_off=None, speed=40.0, color=None, alpha=1.0, width=1.0, fade=0.6, t_dim=None):
    """Propagate a net from source pad `src` starting at t0; step back to 35 %
    at t_dim; fade out at t_off."""
    if t < t0:
        return
    a = alpha * focus(t, t_dim)
    if t_off is not None:
        a *= 1 - prog(t, t_off, t_off + fade, 'smooth')
    if a <= 0:
        return
    f.net(net, color, a, front=(t - t0) * speed, source=[src], width=width)


def lit(f, net, t, t0, t_off=None, color=None, alpha=1.0, fade_in=0.4, fade=0.6, width=1.0, t_dim=None):
    """Light a whole net at once."""
    a = alpha * prog(t, t0, t0 + fade_in, 'smooth') * focus(t, t_dim)
    if t_off is not None:
        a *= 1 - prog(t, t_off, t_off + fade, 'smooth')
    if a > 0:
        f.net(net, color, a, width=width)


def chain_path(stage, hops):
    """Concatenate copper paths: hops = [(net, (ref, pad), (ref, pad)), ...]."""
    pts = []
    for net, a, b in hops:
        p = stage.path(net, a, b).pts
        pts += p if not pts else p[1:]
    return Polyline(pts)


def cpu(ctx, lines, active, t, t_in, t_out=None, extra=None, x=60, y=60, active_t=None, w=380):
    a = window(t, t_in, t_out if t_out is not None else 1e9, 0.6, 0.6)
    act = prog(t, active_t, active_t + 0.4) if active_t is not None else 0
    wg.cpu_card(ctx, lines, x, y, a, active=active if act > 0 else None, active_amt=act, extra=extra, w=w)


def bracket(f, pads, label, color, alpha, below=True, size=20, gap=14, sub=None):
    """Bracket under/over a group of J2 fingers with a label."""
    if alpha <= 0:
        return
    xs = [f.pad_s('J2', p)[0] for p in pads]
    p0 = f.s.board.pad('J2', pads[0])
    y_mm = p0.y + (p0.h / 2 if below else -p0.h / 2)
    _, y = f.sxy(p0.x, y_mm)
    y += gap if below else -gap
    x0, x1 = min(xs) - 8, max(xs) + 8
    ctx = f.ctx
    d = 8 if below else -8
    ctx.move_to(x0, y)
    ctx.line_to(x0, y + d)
    ctx.line_to(x1, y + d)
    ctx.line_to(x1, y)
    ctx.set_line_width(2)
    set_color(ctx, color, alpha)
    ctx.stroke()
    ty = y + d + (size + 6 if below else -10)
    text(ctx, label, (x0 + x1) / 2, ty, size, color, alpha, align='center', bold=True)
    if sub:
        text(ctx, sub, (x0 + x1) / 2, ty + (size + 2 if below else -size - 2), size * 0.8, C.dim_text, alpha,
             align='center', italic=True)


def finger_bit(f, pad, v, color, alpha, size=26, dy=-34, side='top'):
    """Small bit token drawn next to a J2 finger."""
    if alpha <= 0:
        return
    p = f.s.board.pad('J2', pad)
    x, y = f.sxy(p.x, p.y - p.h / 2 if side == 'top' else p.y + p.h / 2)
    wg.bit_cell(f.ctx, x, y + (dy if side == 'top' else -dy), size, v, color, alpha)


LED_VIEW = (86.6, 50.3, 13.5)


def leds_pip(f, t, states, alpha, rect=(1400, 100, 400, 225), photo=0.0):
    """Picture-in-picture of the status LEDs (D1 /CS, D2 MOSI, D3 MISO).
    states: dict ref -> brightness 0..1."""
    def draw(sub):
        sub.board(photo=photo, xray=1 - photo, chip_labels=0.0)
        for ref, col in (('D1', C.ok), ('D2', C.spi), ('D3', C.spi)):
            sub.led(ref, col, states.get(ref, 0.0))
    f.subview(rect, LED_VIEW, draw, alpha, title='status LEDs')
    if alpha <= 0:
        return
    # labels in screen space so they stay crisp and large
    x, y, w, h = rect
    from otter.camera import View
    sv = View(*LED_VIEW)
    for ref, lab in (('D1', '/CS'), ('D2', 'MOSI'), ('D3', 'MISO')):
        x0, y0, x1, y1 = f.s.board.fp(ref).bbox
        px, py = sv.to_screen(x1 + 0.6, (y0 + y1) / 2)
        on = states.get(ref, 0.0) > 0.5
        text(f.ctx, lab, x + px * w / W, y + py * h / H, 20, C.text if on else C.dim_text, alpha, mono=True,
             bold=True, valign='middle')


# --------------------------------------------------------------------------
# The SPI ring panel (S10, S11)
# --------------------------------------------------------------------------
class SpiRing:
    """Everything shifts left, so every register reads MSB first:

        [card] <- MOSI <- [74HC165] <- 1
          |
          +-> MISO ---------------------------+
                      [74HC595] <-------------+     -> latch
    """
    SCK_Y = 190
    ROW1 = 420
    ROW2 = 640
    X165 = 860
    CARD = (110, 320, 520, 230)       # x, y, w, h
    CELL, GAP = 58, 10
    CCELL, CGAP = 44, 8

    def __init__(self, tx, card_tx, card_rx_init=None, rx_init=None, latch_init=None):
        self.tx = bits(tx)
        self.card_tx = bits(card_tx)
        self.card_rx_init = card_rx_init or [None] * 8
        self.rx_init = rx_init or [None] * 8
        self.latch_init = latch_init

    # state after k rising / falling edges -----------------------------------
    def r165(self, kf):
        return self.tx[kf:] + [1] * kf

    def card_reg(self, kr):
        # card shift register holds what it will send; it fills with what it receives
        return (self.card_tx + self.tx)[kr:kr + 8]

    def r595(self, kr):
        return (self.rx_init + self.card_tx)[kr:kr + 8]

    def latch(self, kf):
        if kf == 0:
            return self.latch_init
        return self.r595(kf)

    # drawing ---------------------------------------------------------------------
    def draw(self, ctx, c, alpha, labels=1.0, ncycles=8, legend=1.0, title=None):
        """c = model time in SCK cycles (0..ncycles)."""
        if alpha <= 0:
            return
        panel(ctx, 50, 105, W - 100, 700, alpha, r=22)
        if title:
            text(ctx, title, 90, 150, 22, C.dim_text, alpha, bold=True)
        n = int(math.floor(clamp(c, 0, ncycles)))
        ph = c - n if c < ncycles else 0.0
        if c >= ncycles:
            n = ncycles
        running = 0 <= c < ncycles
        def win(a, b):
            return smooth(clamp((ph - a) / (b - a))) if running else 0.0
        CARD_W, R595_W, R165_W = (0.0, 0.40), (0.26, 0.46), (0.5, 0.85)
        card_u, r595_u, fall_u = win(*CARD_W), win(*R595_W), win(*R165_W)
        k_card = n + (1 if running and ph >= CARD_W[1] else 0)
        k_595 = n + (1 if running and ph >= R595_W[1] else 0)
        kf = n + (1 if running and ph >= R165_W[1] else 0)
        kr = k_595
        sck_high = running and ph < 0.5

        # SCK waveform
        x0, x1 = 560, 1500
        def sck(m):
            if m < 0 or m >= ncycles:
                return 0
            return 1 if (m % 1.0) < 0.5 else 0
        ctx.save()
        wg_t0, wg_t1 = -0.6, ncycles + 0.6
        sx = lambda m: x0 + (m - wg_t0) / (wg_t1 - wg_t0) * (x1 - x0)  # noqa: E731
        text(ctx, 'SCK', x0 - 30, self.SCK_Y + 4, 22, C.clock, alpha, align='right', mono=True, bold=True,
             valign='middle')
        hi, lo = self.SCK_Y - 22, self.SCK_Y + 22
        ctx.new_path()
        prev = None
        for k in range(0, 801):
            m = wg_t0 + (wg_t1 - wg_t0) * k / 800
            yv = hi if sck(m) else lo
            if prev is None:
                ctx.move_to(sx(m), yv)
            elif yv != prev:
                ctx.line_to(sx(m), prev)
                ctx.line_to(sx(m), yv)
            else:
                ctx.line_to(sx(m), yv)
            prev = yv
        ctx.set_line_width(2.5)
        set_color(ctx, C.clock, 0.35 * alpha)
        ctx.stroke()
        # bright part up to the cursor
        ctx.save()
        ctx.rectangle(x0 - 5, hi - 10, sx(c) - x0 + 5, lo - hi + 20)
        ctx.clip()
        ctx.new_path()
        prev = None
        for k in range(0, 801):
            m = wg_t0 + (wg_t1 - wg_t0) * k / 800
            yv = hi if sck(m) else lo
            if prev is None:
                ctx.move_to(sx(m), yv)
            elif yv != prev:
                ctx.line_to(sx(m), prev)
                ctx.line_to(sx(m), yv)
            else:
                ctx.line_to(sx(m), yv)
            prev = yv
        ctx.set_line_width(3)
        set_color(ctx, C.clock, alpha)
        ctx.stroke()
        ctx.restore()
        if wg_t0 <= c <= wg_t1:
            glow_dot(ctx, sx(c), hi if sck_high else lo, 5, C.clock, alpha)
        for i in range(ncycles):
            text(ctx, str(i + 1), sx(i + 0.25), lo + 28, 18, C.dim_text, alpha * 0.9, align='center', mono=True)
        ctx.restore()
        # legend
        if legend > 0:
            fall = running and ph >= 0.5
            rc, fc = (C.dim_text, C.clock) if fall else (C.clock, C.dim_text)
            text(ctx, 'rising edge: card and 595 sample', 1530, self.SCK_Y - 10, 19, rc, alpha * legend,
                 bold=not fall)
            text(ctx, 'falling edge: 165 shifts,', 1530, self.SCK_Y + 20, 19, fc, alpha * legend, bold=fall)
            text(ctx, '595 latches', 1530, self.SCK_Y + 44, 19, fc, alpha * legend, bold=fall)

        # card box
        cx, cy, cw, ch = self.CARD
        rounded_rect(ctx, cx, cy, cw, ch, 22)
        set_color(ctx, C.spi, 0.10 * alpha)
        ctx.fill_preserve()
        ctx.set_line_width(2.5)
        set_color(ctx, C.spi, alpha)
        ctx.stroke()
        text(ctx, 'SD card', cx + 24, cy + 42, 26, C.spi, alpha, bold=True)
        text(ctx, 'its own shift register', cx + 24, cy + 72, 17, C.dim_text, alpha * labels, italic=True)
        creg_x = cx + (cw - (8 * (self.CCELL + self.CGAP) - self.CGAP)) / 2
        card_now = self.card_reg(n)
        card_shift = card_u if running and ph < CARD_W[1] else 0.0
        incoming_card = self.tx[n] if running and n < 8 else None
        wg.register(ctx, creg_x, self.ROW1 + 40, card_now if card_shift > 0 else self.card_reg(k_card), C.spi,
                    alpha, cell=self.CCELL, gap=self.CGAP, shift=card_shift, incoming=incoming_card,
                    direction=-1)

        # 165
        r165 = self.r165(n) if running and R165_W[0] <= ph < R165_W[1] else self.r165(kf)
        xs165 = wg.register(ctx, self.X165, self.ROW1, r165, C.data, alpha, cell=self.CELL, gap=self.GAP,
                            title='74HC165  out', labels=['H', 'G', 'F', 'E', 'D', 'C', 'B', 'A'] if labels else None,
                            shift=fall_u if running and R165_W[0] <= ph < R165_W[1] else 0.0, incoming=1, direction=-1,
                            highlight=0)
        feed_x = self.X165 + 8 * (self.CELL + self.GAP) + 30
        text(ctx, '1', feed_x, self.ROW1, 26, C.data, alpha * 0.8, mono=True, bold=True, valign='middle')
        text(ctx, 'SER = 5 V', feed_x - 10, self.ROW1 + 50, 16, C.dim_text, alpha * labels)

        # MOSI lane
        lane_y = self.ROW1
        lx0, lx1 = self.X165 - 18, cx + cw + 12
        arrow(ctx, lx0, lane_y, lx1, lane_y, C.data, 3, 14, alpha * 0.8)
        text(ctx, 'MOSI', (lx0 + lx1) / 2, lane_y - 18, 20, C.data, alpha, align='center', mono=True, bold=True)
        if running and ph < CARD_W[1] and n < 8:
            u = smooth(clamp(ph / 0.30))
            tx_ = lx0 + (lx1 - lx0) * u
            wg.bit_cell(ctx, tx_, lane_y + 36, 34, self.tx[n], C.data, alpha * (1 - u * 0.4))

        # MISO lane: card left -> down -> right -> up -> into 595 right end
        r595_x = self.X165
        r595_right = r595_x + 8 * (self.CELL + self.GAP)
        lane = Polyline([(cx - 6, cy + ch * 0.6), (cx - 40, cy + ch * 0.6), (cx - 40, self.ROW2 + 110),
                         (r595_right + 60, self.ROW2 + 110), (r595_right + 60, self.ROW2),
                         (r595_right + 6, self.ROW2)])
        ctx.save()
        polyline(ctx, lane.pts[:-1])
        ctx.set_line_width(3)
        set_color(ctx, C.spi, 0.7 * alpha)
        ctx.stroke()
        ctx.restore()
        arrow(ctx, r595_right + 60, self.ROW2, r595_right + 4, self.ROW2, C.spi, 3, 14, 0.8 * alpha)
        text(ctx, 'MISO', (cx + r595_right) / 2, self.ROW2 + 142, 20, C.spi, alpha, align='center', mono=True,
             bold=True)
        if running and ph < R595_W[0] + 0.06 and n < 8:
            u = smooth(clamp(ph / (R595_W[0] + 0.04)))
            px, py = lane.at(lane.length * u)
            wg.bit_cell(ctx, px, py, 34, self.card_tx[n], C.spi, alpha)

        # 595
        r595 = self.r595(n) if running and ph < R595_W[1] else self.r595(k_595)
        wg.register(ctx, r595_x, self.ROW2, r595, C.spi, alpha, cell=self.CELL, gap=self.GAP,
                    title='74HC595  in', labels=['QH', 'QG', 'QF', 'QE', 'QD', 'QC', 'QB', 'QA'] if labels else None,
                    shift=r595_u if running and R595_W[0] < ph < R595_W[1] else 0.0,
                    incoming=self.card_tx[n] if running and n < 8 else None, direction=-1)

        # latch
        lv = self.latch(kf)
        flash = 0.0
        if running and R165_W[1] <= ph < 1.0:
            flash = 1 - (ph - R165_W[1]) / (1 - R165_W[1])
        lx, ly = 1660, self.ROW2 - 10
        if lv is None or any(v is None for v in lv):
            wg.byte_card(ctx, lx, ly, '??h', C.dim_text, alpha, size=40, label='595 output latch')
        else:
            val = sum(b << (7 - i) for i, b in enumerate(lv))
            # intermediate latch values are mechanically right but distracting: keep them quiet
            la = alpha * (0.45 if running and kf < ncycles else 1.0)
            wg.byte_card(ctx, lx, ly, val, C.spi, la, size=40, label='595 output latch')
        if flash > 0:
            glow_dot(ctx, lx, ly, 30, C.spi, flash * alpha)
        return dict(sck_high=sck_high, mosi=self.tx[min(n, 7)] if running else 1,
                    miso=self.card_tx[min(n, 7)] if running else 1, kr=kr, kf=kf)
