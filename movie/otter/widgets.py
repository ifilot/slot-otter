"""Screen-space widgets (design px, 1920x1080)."""
from __future__ import annotations

import math
import re

import cairo

from .anim import clamp, prog, window
from .config import W, H, C
from .draw import (rgba, set_color, rounded_rect, text, font, text_width, wrap, panel, lighten, mix, glow_dot,
                   arrow)


# --------------------------------------------------------------------------
# Captions and titles
# --------------------------------------------------------------------------
def caption(ctx, s, alpha, y=H - 92, size=31, max_w=1360):
    if alpha <= 0 or not s:
        return
    s = curly(s)
    lines = wrap(ctx, s, max_w, size)
    if len(lines) == 2:                       # balance: no orphan word on the second line
        words = s.split(' ')
        font(ctx, size)
        best = min(range(1, len(words)), key=lambda k: max(text_width(ctx, ' '.join(words[:k])),
                                                           text_width(ctx, ' '.join(words[k:]))))
        lines = [' '.join(words[:best]), ' '.join(words[best:])]
    lh = size * 1.38
    font(ctx, size)
    tw = max(text_width(ctx, ln) for ln in lines)
    h = lh * len(lines) + size * 0.7
    yy = y - h + (1 - alpha) * 8
    rounded_rect(ctx, W / 2 - tw / 2 - 30, yy, tw + 60, h, 16)
    ctx.set_source_rgba(0.02, 0.035, 0.07, 0.72 * alpha)
    ctx.fill()
    for i, ln in enumerate(lines):
        text(ctx, ln, W / 2, yy + size * 0.35 + lh * (i + 0.5), size, C.text, alpha, align='center',
             valign='middle')


def curly(s):
    """Typographic quotes and apostrophes."""
    s = re.sub(r'"(?=\w)', '\u201c', s)
    s = s.replace('"', '\u201d')
    return re.sub(r"(?<=\w)'(?=\w)", '\u2019', s)


def captions(ctx, cues, t):
    for t0, t1, s in cues:
        a = window(t, t0, t1, 0.45, 0.45)
        if a > 0:
            caption(ctx, s, a)


def title_block(ctx, title, subtitle, alpha, x=120, y=150):
    if alpha <= 0:
        return
    text(ctx, title, x, y + (1 - alpha) * 10, 76, C.text, alpha, bold=True)
    ctx.rectangle(x, y + 28, 120 * alpha, 4)
    set_color(ctx, C.data, alpha)
    ctx.fill()
    if subtitle:
        lines = wrap(ctx, subtitle, 760, 30)
        for i, ln in enumerate(lines):
            text(ctx, ln, x, y + 82 + i * 42, 30, C.dim_text, alpha)


def chip_title(ctx, part, role, x, y, alpha, color=C.text, size=34):
    """Big part name + role line (e.g. '74HCT688' / '8-bit comparator')."""
    if alpha <= 0:
        return
    text(ctx, part, x, y, size, color, alpha, bold=True, mono=True)
    text(ctx, role, x, y + size * 0.95, size * 0.62, C.dim_text, alpha)


def tag_line(ctx, s, x, y, alpha, color=C.dim_text, size=22, italic=True):
    text(ctx, s, x, y, size, color, alpha, italic=italic)


# --------------------------------------------------------------------------
# CPU listing
# --------------------------------------------------------------------------
def cpu_card(ctx, lines, x, y, alpha, active=None, active_amt=1.0, header='8088 CPU', extra=None, w=360):
    if alpha <= 0:
        return
    lh = 40
    h = 64 + lh * len(lines) + (46 if extra else 0)
    panel(ctx, x, y, w, h, alpha)
    text(ctx, header, x + 22, y + 36, 18, C.dim_text, alpha, bold=True)
    for i, ln in enumerate(lines):
        yy = y + 70 + i * lh
        if active == i and active_amt > 0:
            rounded_rect(ctx, x + 10, yy - 27, w - 20, 36, 8)
            set_color(ctx, C.data, 0.18 * alpha * active_amt)
            ctx.fill()
            text(ctx, '>', x + 20, yy, 24, C.data, alpha * active_amt, mono=True, bold=True)
        text(ctx, ln, x + 46, yy, 24, C.text if active == i else C.dim_text, alpha, mono=True)
    if extra:
        text(ctx, extra[0], x + 46, y + h - 26, 24, extra[1] if len(extra) > 1 else C.ok, alpha, mono=True,
             bold=True)


# --------------------------------------------------------------------------
# Bits
# --------------------------------------------------------------------------
def bit_cell(ctx, x, y, s, v, color, alpha=1.0, glow=0.0):
    """One bit token, centred at x, y, size s. v in (0, 1, None)."""
    if alpha <= 0:
        return
    r = s * 0.18
    rounded_rect(ctx, x - s / 2, y - s / 2, s, s, r)
    if v == 1:
        set_color(ctx, color, alpha)
        ctx.fill()
        text(ctx, '1', x, y, s * 0.55, C.bg, alpha, align='center', valign='middle', mono=True, bold=True)
    elif v == 0:
        set_color(ctx, C.bg, 0.6 * alpha)
        ctx.fill_preserve()
        ctx.set_line_width(2.5)
        set_color(ctx, color, alpha)
        ctx.stroke()
        text(ctx, '0', x, y, s * 0.55, color, alpha, align='center', valign='middle', mono=True, bold=True)
    else:
        ctx.set_line_width(2)
        ctx.set_dash([5, 4])
        set_color(ctx, C.dim_text, 0.6 * alpha)
        ctx.stroke()
        ctx.set_dash([])
        text(ctx, '?', x, y, s * 0.5, C.dim_text, 0.7 * alpha, align='center', valign='middle', mono=True)
    if glow > 0:
        glow_dot(ctx, x, y, s * 0.35, color, glow * 0.6 * alpha)


def register(ctx, x, y, bits, color, alpha=1.0, cell=58, gap=10, title=None, labels=None, sub=None,
             slots=True, shift=0.0, incoming=None, direction=1, highlight=None, title_color=None):
    """Row of bit tokens over fixed slots.

    bits      list of 0/1/None, index 0 drawn leftmost.
    shift     0..1: tokens are moving one position in `direction` (+1 = right).
    incoming  value entering from the opposite side while shifting.
    highlight index of a slot to outline.
    Returns the slot centre x positions.
    """
    n = len(bits)
    pitch = cell + gap
    xs = [x + cell / 2 + i * pitch for i in range(n)]
    if alpha <= 0:
        return xs
    if title:
        text(ctx, title, x, y - cell / 2 - 18, 22, title_color or C.text, alpha, bold=True, mono=True)
    if slots:
        for i, cx in enumerate(xs):
            rounded_rect(ctx, cx - cell / 2 - 4, y - cell / 2 - 4, cell + 8, cell + 8, cell * 0.2)
            ctx.set_source_rgba(1, 1, 1, 0.04 * alpha)
            ctx.fill()
    if highlight is not None:
        cx = xs[highlight]
        rounded_rect(ctx, cx - cell / 2 - 7, y - cell / 2 - 7, cell + 14, cell + 14, cell * 0.24)
        ctx.set_line_width(2.5)
        set_color(ctx, lighten(color, 0.4), alpha)
        ctx.stroke()
    off = shift * pitch * direction
    ctx.save()
    ctx.rectangle(x - 6, y - cell, n * pitch - gap + 12, cell * 2)
    ctx.clip()
    for i, v in enumerate(bits):
        a = alpha
        nx = xs[i] + off
        if (direction > 0 and i == n - 1) or (direction < 0 and i == 0):
            a *= 1 - shift
        bit_cell(ctx, nx, y, cell, v, color, a)
    if shift > 0 and incoming is not None:
        ex = (xs[0] - pitch if direction > 0 else xs[-1] + pitch) + off
        bit_cell(ctx, ex, y, cell, incoming, color, alpha * shift)
    ctx.restore()
    if labels:
        for cx, lb in zip(xs, labels):
            text(ctx, lb, cx, y + cell / 2 + 26, 17, C.dim_text, alpha, align='center', mono=True)
    if sub:
        text(ctx, sub, x, y + cell / 2 + (58 if labels else 34), 19, C.dim_text, alpha, italic=True)
    return xs


def byte_card(ctx, x, y, value, color, alpha=1.0, size=40, label=None):
    """Rounded card with a hex byte (e.g. '51h'), centred at x, y."""
    if alpha <= 0:
        return
    s = value if isinstance(value, str) else f'{value:02X}h'
    font(ctx, size, True, True)
    tw = text_width(ctx, s)
    w, h = tw + size, size * 1.6
    rounded_rect(ctx, x - w / 2, y - h / 2, w, h, 12)
    set_color(ctx, color, 0.16 * alpha)
    ctx.fill_preserve()
    ctx.set_line_width(2.5)
    set_color(ctx, color, alpha)
    ctx.stroke()
    text(ctx, s, x, y, size, lighten(color, 0.3), alpha, align='center', valign='middle', mono=True, bold=True)
    if label:
        text(ctx, label, x, y + h / 2 + 26, 18, C.dim_text, alpha, align='center')


def bits_of(byte):
    """MSB first list."""
    return [(byte >> (7 - i)) & 1 for i in range(8)]


# --------------------------------------------------------------------------
# Timing diagram
# --------------------------------------------------------------------------
def timing(ctx, x, y, w, rows, t0, t1, cursor=None, alpha=1.0, row_h=46, label_w=170, reveal=True,
           grid=None, title=None, marks=()):
    """rows: list of (label, color, fn) where fn(model_t) -> 0/1 (or None to skip).
    Draws model time t0..t1 over width w. With reveal, only up to the cursor."""
    if alpha <= 0:
        return
    h = row_h * len(rows) + 30 + (34 if title else 0) + (34 if marks else 0)
    panel(ctx, x - 20, y - 20 - (34 if title else 0), w + label_w + 40, h + 10, alpha)
    if title:
        text(ctx, title, x, y - 18, 20, C.dim_text, alpha, bold=True)
    gx = x + label_w
    sx = lambda m: gx + (m - t0) / (t1 - t0) * w  # noqa: E731
    if grid:
        m = math.ceil(t0 / grid) * grid
        while m <= t1:
            ctx.move_to(sx(m), y)
            ctx.line_to(sx(m), y + row_h * len(rows))
            ctx.set_source_rgba(1, 1, 1, 0.05 * alpha)
            ctx.set_line_width(1)
            ctx.stroke()
            m += grid
    end = t1 if (cursor is None or not reveal) else max(t0, min(t1, cursor))
    for i, (label, color, fn) in enumerate(rows):
        yy = y + i * row_h
        text(ctx, label, x, yy + row_h * 0.55, 19, color, alpha, mono=True, valign='middle')
        hi, lo = yy + row_h * 0.2, yy + row_h * 0.8
        ctx.new_path()
        steps = max(2, int((end - t0) / (t1 - t0) * w / 1.5))
        prev = None
        for k in range(steps + 1):
            m = t0 + (end - t0) * k / steps
            v = fn(m)
            yv = hi if v else lo
            px = sx(m)
            if prev is None:
                ctx.move_to(px, yv)
            else:
                if yv != prev:
                    ctx.line_to(px, prev)
                ctx.line_to(px, yv)
            prev = yv
        ctx.set_line_width(2.6)
        ctx.set_line_join(cairo.LINE_JOIN_MITER)
        set_color(ctx, color, alpha)
        ctx.stroke()
    for (mt, lab, col) in marks:
        if mt <= end:
            ctx.move_to(sx(mt), y - 4)
            ctx.line_to(sx(mt), y + row_h * len(rows))
            ctx.set_dash([4, 4])
            set_color(ctx, col, 0.7 * alpha)
            ctx.set_line_width(1.5)
            ctx.stroke()
            ctx.set_dash([])
            text(ctx, lab, sx(mt), y + row_h * len(rows) + 22, 16, col, alpha, align='center')
    if cursor is not None and t0 <= cursor <= t1:
        cx = sx(cursor)
        ctx.move_to(cx, y - 6)
        ctx.line_to(cx, y + row_h * len(rows) + 2)
        ctx.set_source_rgba(1, 1, 1, 0.55 * alpha)
        ctx.set_line_width(1.5)
        ctx.stroke()


def square(period, start=0.0, high_first=True):
    def f(m):
        if m < start:
            return 0
        ph = ((m - start) / period) % 1.0
        return 1 if (ph < 0.5) == high_first else 0
    return f


def steps(transitions, initial=0):
    """transitions: sorted list of (model_t, level)."""
    def f(m):
        v = initial
        for tt, lv in transitions:
            if m >= tt:
                v = lv
            else:
                break
        return v
    return f


# --------------------------------------------------------------------------
# Table
# --------------------------------------------------------------------------
def table(ctx, x, y, cols, rows, alpha=1.0, col_w=None, row_h=46, reveal=None, highlight=None,
          hl_color=C.data, head_color=C.dim_text, size=21, mono_cols=(0,)):
    """reveal: number of body rows visible (float, fractional fades in).
    highlight: (row, col) cell to glow."""
    if alpha <= 0:
        return
    col_w = col_w or [200] * len(cols)
    tw = sum(col_w)
    n = len(rows)
    panel(ctx, x - 20, y - 20, tw + 40, row_h * (n + 1) + 30, alpha)
    cx = x
    for j, c in enumerate(cols):
        text(ctx, c, cx + 10, y + row_h * 0.6, size * 0.85, head_color, alpha, bold=True)
        cx += col_w[j]
    ctx.move_to(x, y + row_h)
    ctx.line_to(x + tw, y + row_h)
    ctx.set_source_rgba(1, 1, 1, 0.15 * alpha)
    ctx.set_line_width(1)
    ctx.stroke()
    for i, r in enumerate(rows):
        ra = alpha * (clamp(reveal - i) if reveal is not None else 1.0)
        if ra <= 0:
            continue
        yy = y + row_h * (i + 1)
        cx = x
        for j, cell in enumerate(r):
            if highlight and highlight[0] == i and highlight[1] == j:
                hl = highlight[2] if len(highlight) > 2 else 1.0
                rounded_rect(ctx, cx + 2, yy + 4, col_w[j] - 4, row_h - 8, 8)
                set_color(ctx, hl_color, 0.22 * ra * hl)
                ctx.fill_preserve()
                ctx.set_line_width(2)
                set_color(ctx, hl_color, ra * hl)
                ctx.stroke()
            text(ctx, cell, cx + 10, yy + row_h * 0.62, size, C.text, ra, mono=j in mono_cols, bold=j in mono_cols)
            cx += col_w[j]


# --------------------------------------------------------------------------
# Misc
# --------------------------------------------------------------------------
def lamps(ctx, x, y, bits, labels, color, alpha=1.0, r=22, gap=64):
    """Row of round lamps (counter bits). bits MSB first."""
    if alpha <= 0:
        return
    for i, (b, lb) in enumerate(zip(bits, labels)):
        cx = x + i * gap
        ctx.new_path()
        ctx.arc(cx, y, r, 0, 2 * math.pi)
        set_color(ctx, color if b else C.bg, alpha if b else 0.8 * alpha)
        ctx.fill_preserve()
        ctx.set_line_width(2.5)
        set_color(ctx, color, alpha)
        ctx.stroke()
        if b:
            glow_dot(ctx, cx, y, r * 0.5, color, 0.6 * alpha)
        text(ctx, lb, cx, y + r + 26, 17, C.dim_text, alpha, align='center', mono=True)


def check(ctx, x, y, ok, alpha=1.0, size=26):
    if alpha <= 0:
        return
    col = C.ok if ok else C.bad
    ctx.set_line_width(4)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    set_color(ctx, col, alpha)
    if ok:
        ctx.move_to(x - size * 0.4, y)
        ctx.line_to(x - size * 0.1, y + size * 0.3)
        ctx.line_to(x + size * 0.45, y - size * 0.35)
    else:
        ctx.move_to(x - size * 0.35, y - size * 0.35)
        ctx.line_to(x + size * 0.35, y + size * 0.35)
        ctx.move_to(x + size * 0.35, y - size * 0.35)
        ctx.line_to(x - size * 0.35, y + size * 0.35)
    ctx.stroke()


def note(ctx, s, x, y, alpha, w=520, size=23, color=C.text, accent=C.data):
    """Small panel with wrapped text and an accent bar."""
    if alpha <= 0:
        return
    lines = wrap(ctx, s, w - 50, size)
    h = len(lines) * size * 1.4 + 34
    panel(ctx, x, y, w, h, alpha, r=14)
    ctx.rectangle(x + 14, y + 16, 4, h - 32)
    set_color(ctx, accent, alpha)
    ctx.fill()
    for i, ln in enumerate(lines):
        text(ctx, ln, x + 32, y + 17 + size * 1.4 * (i + 0.72), size, color, alpha)
    return h
