"""Cairo drawing primitives shared by the board layers and the widgets."""
from __future__ import annotations

import math

import cairo

from .config import FONT, FONT_MONO, C


def rgba(c, a=1.0):
    return (c[0], c[1], c[2], (c[3] if len(c) > 3 else 1.0) * a)


def mix(c1, c2, u):
    return tuple(a + (b - a) * u for a, b in zip(rgba(c1), rgba(c2)))


def lighten(c, u=0.5):
    return mix(c, (1, 1, 1, rgba(c)[3]), u)


def set_color(ctx, c, a=1.0):
    ctx.set_source_rgba(*rgba(c, a))


def rounded_rect(ctx, x, y, w, h, r):
    r = max(0.0, min(r, w / 2, h / 2))
    ctx.new_sub_path()
    ctx.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    ctx.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    ctx.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    ctx.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    ctx.close_path()


def polyline(ctx, pts):
    if not pts:
        return
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)


def glow_stroke(ctx, build_path, color, width, alpha=1.0, glow=1.0, core=True, halo=None):
    """Stroke a path several times for a soft neon look. `build_path(ctx)`
    must (re)create the path; widths are in current user units. `halo` sets
    the glow radius in user units (default: proportional to width)."""
    if alpha <= 0:
        return
    ctx.save()
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)
    if glow > 0:
        for k, a in ((1.0, 0.07), (0.55, 0.13), (0.25, 0.25)):
            build_path(ctx)
            if halo is None:
                ctx.set_line_width(width * (1 + 6 * k * glow))
            else:
                ctx.set_line_width(width + 2 * halo * k * glow)
            set_color(ctx, color, a * alpha)
            ctx.stroke()
    build_path(ctx)
    ctx.set_line_width(width)
    set_color(ctx, color, alpha)
    ctx.stroke()
    if core:
        build_path(ctx)
        ctx.set_line_width(width * 0.4)
        set_color(ctx, lighten(color, 0.6), alpha)
        ctx.stroke()
    ctx.restore()


def glow_dot(ctx, x, y, r, color, alpha=1.0):
    if alpha <= 0:
        return
    g = cairo.RadialGradient(x, y, 0, x, y, r * 4)
    c = rgba(color)
    g.add_color_stop_rgba(0, 1, 1, 1, alpha)
    g.add_color_stop_rgba(0.18, c[0], c[1], c[2], 0.9 * alpha)
    g.add_color_stop_rgba(0.45, c[0], c[1], c[2], 0.25 * alpha)
    g.add_color_stop_rgba(1, c[0], c[1], c[2], 0)
    ctx.set_source(g)
    ctx.new_path()
    ctx.arc(x, y, r * 4, 0, 2 * math.pi)
    ctx.fill()


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------
def font(ctx, size, bold=False, mono=False, italic=False):
    ctx.select_font_face(FONT_MONO if mono else FONT,
                         cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL,
                         cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(size)


def text_width(ctx, s):
    return ctx.text_extents(s).x_advance


def text(ctx, s, x, y, size=24, color=C.text, alpha=1.0, align='left', valign='baseline',
         bold=False, mono=False, italic=False):
    """Draw text; align in {left, center, right}; valign in {baseline, middle, top}."""
    if alpha <= 0 or not s:
        return 0
    font(ctx, size, bold, mono, italic)
    ext = ctx.text_extents(s)
    fe = ctx.font_extents()
    w = ext.x_advance
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    if valign == 'middle':
        y += (fe[0] - fe[1]) / 2 * 0.92
    elif valign == 'top':
        y += fe[0] * 0.8
    set_color(ctx, color, alpha)
    ctx.move_to(x, y)
    ctx.show_text(s)
    ctx.new_path()          # show_text leaves a current point; never let it leak into the next arc
    return w


def wrap(ctx, s, max_w, size, bold=False):
    font(ctx, size, bold)
    words, lines, cur = s.split(' '), [], ''   # split on plain spaces only: NBSP keeps '1 µs' together
    for wd in words:
        t = (cur + ' ' + wd).strip()
        if text_width(ctx, t) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


def panel(ctx, x, y, w, h, alpha=1.0, r=18, fill=C.panel, edge=C.panel_edge, shadow=True):
    if alpha <= 0:
        return
    if shadow:
        for i, a in ((18, 0.10), (10, 0.12), (4, 0.15)):
            rounded_rect(ctx, x - i * 0.3, y + i * 0.5, w + i * 0.6, h + i * 0.6, r + i)
            ctx.set_source_rgba(0, 0, 0, a * alpha)
            ctx.fill()
    rounded_rect(ctx, x, y, w, h, r)
    set_color(ctx, fill, alpha)
    ctx.fill_preserve()
    ctx.set_line_width(1.5)
    set_color(ctx, edge, alpha)
    ctx.stroke()


def arrow(ctx, x0, y0, x1, y1, color, width=3, head=12, alpha=1.0):
    if alpha <= 0:
        return
    ang = math.atan2(y1 - y0, x1 - x0)
    set_color(ctx, color, alpha)
    ctx.set_line_width(width)
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.move_to(x0, y0)
    ctx.line_to(x1 - head * 0.6 * math.cos(ang), y1 - head * 0.6 * math.sin(ang))
    ctx.stroke()
    ctx.move_to(x1, y1)
    ctx.line_to(x1 - head * math.cos(ang - 0.45), y1 - head * math.sin(ang - 0.45))
    ctx.line_to(x1 - head * math.cos(ang + 0.45), y1 - head * math.sin(ang + 0.45))
    ctx.close_path()
    ctx.fill()
