"""The board stage: photo plate, x-ray vector board, net highlights, spotlight.

`Stage` is loaded once per worker process (board, plate mipmaps, caches).
`Frame` wraps one cairo context + camera view + time and offers the drawing
calls scenes use.
"""
from __future__ import annotations

import json
import math
import os
import sys

import cairo

from . import pcb, netflow
from . import draw as draw_mod
from .anim import clamp
from .camera import View, shot
from .config import W, H, C, BUILD, PCB_FILE, PLATE_PNG, PLATE_JSON
from .draw import (rgba, set_color, rounded_rect, polyline, glow_stroke, glow_dot, text, font,
                   text_width, lighten, mix)

# Signal family per net name (used for default colours).
FAMILY = {}
for n in ['A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'AEN']:
    FAMILY[n] = C.addr
for i in range(8):
    FAMILY[f'D{i}'] = C.data
    FAMILY[f'DB{i}'] = C.data
for n in ['~{RD}', '~{WR}', '~{PORTSEL}', '~{SER_WR}', '~{SER_RD}', '~{RQ_SER_RD}', '~{SER_RD_AND_PULSE}',
          '~{PULSE}', '~{SDCS_SET}', '~{SDCS_RESET}', '~{SDOUT_SET}', '~{SDOUT_RESET}', 'Net-(U3A-E)',
          'Net-(U3B-E)']:
    FAMILY[n] = C.ctrl
for n in ['16MHz', 'CLK', '~{CLK}', 'SCK_LLS', 'Net-(R10-Pad2)']:      # lime: real clocks only
    FAMILY[n] = C.clock
for n in ['CLKSTOP', '~{CLKSTOP}', '~{CLKSTART}', 'Net-(U4-~{MR})', 'Net-(U1-Pad3)', 'Net-(U13B-~{Q})',
          'Net-(U10B-~{Q})', 'Net-(U11-Pad11)', 'Net-(U11-Pad8)', 'Net-(U12-Pad1)', 'Net-(U11-Pad1)']:
    FAMILY[n] = C.ctrl                                                      # rose: control, incl. derived pulses
for n in ['MOSI', 'MISO', 'CS', '~{CS}', 'CS_LLS', 'DI_LLS', 'D0_LLS', 'Net-(R9-Pad2)', 'Net-(R11-Pad2)',
          'Net-(R8-Pad2)', 'Net-(R1-Pad1)', 'Net-(D1-K)', 'Net-(D2-K)', 'Net-(D3-K)']:
    FAMILY[n] = C.spi
for n in ['VCC', '+3V3']:
    FAMILY[n] = C.power


def family(net):
    return FAMILY.get(net, C.data)


# --------------------------------------------------------------------------
class Plate:
    """Photoreal top-down render with known mm bounds, as cairo mipmaps."""

    def __init__(self, png, meta):
        from PIL import Image
        import numpy as np
        with open(meta) as f:
            m = json.load(f)
        self.x0, self.y0, self.x1, self.y1 = m['mm_bounds']
        img = Image.open(png).convert('RGBA')
        self.levels = []
        while True:
            a = np.asarray(img, dtype=np.float32) / 255.0
            rgb = a[..., :3] * a[..., 3:4]
            bgra = np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], a[..., 3]])
            buf = (bgra * 255 + 0.5).astype(np.uint8)
            h, w = buf.shape[:2]
            stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
            if stride != w * 4:
                pad = np.zeros((h, stride), np.uint8)
                pad[:, :w * 4] = buf.reshape(h, w * 4)
                buf = pad
            data = bytearray(buf.tobytes())
            surf = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, stride)
            self.levels.append((w, surf, data))
            if w <= 1024:
                break
            img = img.resize((w // 2, h // 2), Image.LANCZOS)

    def draw(self, ctx, view: View, alpha):
        if alpha <= 0:
            return
        need = view.scale * (self.x1 - self.x0) * _device_scale(ctx)   # device px across plate
        w, surf, _ = self.levels[0]
        for lw, ls, _d in self.levels:
            if lw >= need * 0.9:
                w, surf = lw, ls
        ctx.save()
        view.apply(ctx)
        ctx.translate(self.x0, self.y0)
        k = (self.x1 - self.x0) / w
        ctx.scale(k, k)
        ctx.set_source_surface(surf, 0, 0)
        ctx.get_source().set_filter(cairo.FILTER_GOOD)
        ctx.paint_with_alpha(alpha)
        ctx.restore()


def _device_scale(ctx):
    xx, yx, xy, yy, x0, y0 = ctx.get_matrix()
    return math.hypot(xx, yx)


# --------------------------------------------------------------------------
class Stage:
    def __init__(self):
        self.board = pcb.load(PCB_FILE, cache_dir=os.path.join(BUILD, 'cache'))
        self.plate = None
        if os.path.exists(PLATE_PNG) and os.path.exists(PLATE_JSON):
            self.plate = Plate(PLATE_PNG, PLATE_JSON)
        else:
            print('note: no photo plate found (run `render.py plate`); using the x-ray board for photo mode',
                  file=sys.stderr)
        self._graphs, self._flows, self._paths = {}, {}, {}

    # -- connectivity caches ------------------------------------------------
    def graph(self, net):
        if net not in self._graphs:
            self._graphs[net] = netflow.NetGraph(self.board, net)
        return self._graphs[net]

    def flow(self, net, sources):
        key = (net, tuple(sources))
        if key not in self._flows:
            self._flows[key] = netflow.Flow(self.graph(net), list(sources))
        return self._flows[key]

    def path(self, net, a, b):
        key = (net, a, b)
        if key not in self._paths:
            self._paths[key] = netflow.Polyline(self.graph(net).path(a, b))
        return self._paths[key]

    def pad_xy(self, ref, pad):
        p = self.board.pad(ref, pad)
        return (p.x, p.y)

    def fp_box(self, ref, pad=0.6):
        x0, y0, x1, y1 = self.board.fp(ref).bbox
        if ref.startswith('J2'):
            ps = self.board.fp(ref).pads
            x0, x1 = min(p.x - p.w / 2 for p in ps), max(p.x + p.w / 2 for p in ps)
            y0, y1 = min(p.y - p.h / 2 for p in ps), max(p.y + p.h / 2 for p in ps)
        elif ref.startswith('U') or ref.startswith('SW'):
            # include the pins
            ps = self.board.fp(ref).pads
            x0 = min([x0] + [p.x - p.w / 2 for p in ps])
            x1 = max([x1] + [p.x + p.w / 2 for p in ps])
            y0 = min([y0] + [p.y - max(p.w, p.h) / 2 for p in ps])
            y1 = max([y1] + [p.y + max(p.w, p.h) / 2 for p in ps])
        return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


# --------------------------------------------------------------------------
class Frame:
    # Safe area for screen-space labels (design px): clear of the frame edges
    # and of the caption band at the bottom.
    SAFE = (60, 60, W - 60, 870)

    def __init__(self, stage: Stage, ctx, view: View, t: float, deferred=True):
        self.s = stage
        self.ctx = ctx
        self.view = view
        self.t = t
        # Draw order for top-level frames: board -> nets/comets (draw calls) ->
        # chip bodies + part numbers -> shading (spotlight/dim) -> labels.
        # spotlight(), dim(), outline(), tag() and later() are queued and run by
        # flush(), so scenes can call them in any order.
        self.deferred = deferred
        self._xray = 0.0
        self._chip_labels = 1.0
        self._shade = []
        self._labels = []

    def later(self, fn):
        """Run fn(frame) in the label layer (above chips and shading)."""
        if self.deferred:
            self._labels.append(fn)
        else:
            fn(self)

    def flush(self):
        if self._xray > 0:
            self.chip_overlay(self._xray, self._chip_labels)
        for fn in self._shade:
            fn()
        for fn in self._labels:
            fn(self)
        self._shade, self._labels = [], []

    # -- helpers --------------------------------------------------------------
    def world(self):
        """Context manager: draw in board millimetres."""
        frame = self

        class _W:
            def __enter__(self_):
                frame.ctx.save()
                frame.view.apply(frame.ctx)
                return frame.ctx

            def __exit__(self_, *a):
                frame.ctx.restore()
        return _W()

    def px(self, n):
        """n design pixels expressed in mm at the current zoom."""
        return n / self.view.scale

    def sxy(self, x, y):
        return self.view.to_screen(x, y)

    def pad_s(self, ref, pad):
        return self.sxy(*self.s.pad_xy(ref, pad))

    def box_s(self, ref, pad=0.6):
        x0, y0, x1, y1 = self.s.fp_box(ref, pad)
        a, b = self.sxy(x0, y0)
        c, d = self.sxy(x1, y1)
        return (a, b, c, d)

    # -- background -------------------------------------------------------------
    # Full-frame radial gradients are slow in cairo; render them once per
    # output resolution and blit them afterwards.
    _cache = {}

    def _cached(self, key, build):
        xx, yx, xy, yy, x0, y0 = self.ctx.get_matrix()
        if yx or xy or x0 or y0:            # transformed (e.g. picture-in-picture): draw directly
            build(self.ctx)
            return
        k = (key, round(xx, 5), round(yy, 5))
        surf = Frame._cache.get(k)
        if surf is None:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(round(W * xx)), int(round(H * yy)))
            c = cairo.Context(surf)
            c.scale(xx, yy)
            build(c)
            Frame._cache[k] = surf
        self.ctx.save()
        self.ctx.identity_matrix()
        self.ctx.set_source_surface(surf, 0, 0)
        self.ctx.paint()
        self.ctx.restore()

    def background(self):
        def build(ctx):
            g = cairo.RadialGradient(W * 0.5, H * 0.45, 100, W * 0.5, H * 0.5, W * 0.75)
            g.add_color_stop_rgba(0, *rgba(C.bg2))
            g.add_color_stop_rgba(1, *rgba(C.bg))
            ctx.set_source(g)
            ctx.paint()
        self._cached('bg', build)

    def vignette(self, strength=0.55):
        def build(ctx):
            g = cairo.RadialGradient(W / 2, H / 2, H * 0.45, W / 2, H / 2, W * 0.72)
            g.add_color_stop_rgba(0, 0, 0, 0, 0)
            g.add_color_stop_rgba(1, 0, 0, 0, strength)
            ctx.set_source(g)
            ctx.paint()
        self._cached(('vig', strength), build)

    def caption_band(self, top=840, strength=0.82):
        """Soft dark gradient at the bottom so captions sit on a quiet ground."""
        def build(ctx):
            g = cairo.LinearGradient(0, top, 0, H)
            g.add_color_stop_rgba(0, 0, 0, 0, 0)
            g.add_color_stop_rgba(0.45, 0.01, 0.015, 0.03, strength * 0.75)
            g.add_color_stop_rgba(1, 0.01, 0.015, 0.03, strength)
            ctx.set_source(g)
            ctx.rectangle(0, top, W, H - top)
            ctx.fill()
        self._cached(('band', top, strength), build)

    def fade_black(self, alpha):
        if alpha > 0:
            self.ctx.set_source_rgba(0, 0, 0, clamp(alpha))
            self.ctx.paint()

    # -- board -----------------------------------------------------------------
    def board(self, photo=0.0, xray=0.0, chip_labels=1.0):
        if photo > 0:
            if self.s.plate:
                self.s.plate.draw(self.ctx, self.view, photo)
            else:
                self.xray(photo, solid=True)
        if xray > 0:
            self.xray(xray, chip_labels=chip_labels)
        self._xray = max(self._xray, xray)
        self._chip_labels = chip_labels

    def xray(self, alpha=1.0, solid=False, chip_labels=1.0):
        b = self.s.board
        ctx = self.ctx
        ctx.push_group()
        with self.world() as c:
            minw = self.px(1.1)
            # board body
            for o in b.outline:
                polyline(c, o)
                c.close_path()
            set_color(c, C.board if not solid else (0.05, 0.22, 0.14, 1))
            c.fill_preserve()
            c.set_line_width(max(0.25, self.px(1.5)))
            set_color(c, C.board_edge)
            c.stroke()
            # copper pours on outer layers (faint), teardrops as copper
            for z in b.zones:
                if z.layer not in ('F.Cu', 'B.Cu'):
                    continue
                big = z.net in ('GND', 'VCC', '+3V3')
                for poly in z.polygons:
                    polyline(c, poly)
                    c.close_path()
                if big:
                    set_color(c, C.pour, 0.55 if z.layer == 'F.Cu' else 0.3)
                else:
                    set_color(c, C.trace_f if z.layer == 'F.Cu' else C.trace_b)
                c.fill()
            c.set_line_cap(cairo.LINE_CAP_ROUND)
            for layer, col in (('B.Cu', C.trace_b), ('F.Cu', C.trace_f)):
                set_color(c, col)
                for sgm in b.segments:
                    if sgm.layer != layer:
                        continue
                    c.set_line_width(max(sgm.width, minw))
                    c.move_to(sgm.x0, sgm.y0)
                    c.line_to(sgm.x1, sgm.y1)
                    c.stroke()
            for v in b.vias:
                c.new_path()
                c.arc(v.x, v.y, v.size / 2, 0, 2 * math.pi)
                set_color(c, C.trace_f)
                c.fill()
                c.arc(v.x, v.y, v.drill / 2, 0, 2 * math.pi)
                set_color(c, C.board)
                c.fill()
            # pads (front side)
            for fp in b.footprints.values():
                for p in fp.pads:
                    if not p.front:
                        continue
                    self._pad_path(c, p)
                    set_color(c, C.pad, 0.85)
                    c.fill()
            # bodies (top-level frames draw them later, above the glowing nets)
            if not self.deferred:
                for ref, fp in b.footprints.items():
                    self._body(c, ref, fp, chip_labels)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)

    def chip_overlay(self, alpha, chip_labels=1.0):
        ctx = self.ctx
        ctx.push_group()
        with self.world() as c:
            for ref, fp in self.s.board.footprints.items():
                self._body(c, ref, fp, chip_labels)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)

    def _pad_path(self, c, p, grow=0.0):
        c.save()
        c.translate(p.x, p.y)
        c.rotate(-math.radians(p.angle))
        w, h = p.w + grow, p.h + grow
        if p.shape in ('circle',):
            c.new_sub_path()
            c.arc(0, 0, w / 2, 0, 2 * math.pi)
        elif p.shape == 'oval':
            rounded_rect(c, -w / 2, -h / 2, w, h, min(w, h) / 2)
        elif p.shape == 'roundrect':
            rounded_rect(c, -w / 2, -h / 2, w, h, min(w, h) * 0.25)
        else:
            c.rectangle(-w / 2, -h / 2, w, h)
        c.restore()

    def _body(self, c, ref, fp, chip_labels):
        if not fp.fab or ref.startswith(('H', 'REF', 'G', 'J2', 'TP')):
            return
        x0, y0, x1, y1 = fp.bbox
        w, h = x1 - x0, y1 - y0
        ic = ref.startswith(('U', 'X'))
        rounded_rect(c, x0, y0, w, h, min(w, h) * (0.08 if ic else 0.2))
        set_color(c, C.chip, 0.92 if ic else 0.7)
        c.fill_preserve()
        c.set_line_width(max(0.08, self.px(1.0)))
        set_color(c, C.chip_edge, 0.9)
        c.stroke()
        if ic:
            # pin-1 dot
            p1 = fp.pads[0] if fp.pads else None
            if p1 is not None:
                dx = min(max(p1.x, x0 + 0.8), x1 - 0.8)
                dy = min(max(p1.y, y0 + 0.8), y1 - 0.8)
                c.new_path()
                c.arc(dx, dy, min(w, h) * 0.07, 0, 2 * math.pi)
                set_color(c, C.chip_edge)
                c.fill()
            if chip_labels > 0:
                vertical = h > w * 1.3
                long_, short = (h, w) if vertical else (w, h)
                sz = min(short * 0.30, self.px(32))
                sz = max(sz, self.px(14))
                sz = min(sz, long_ * 0.86 / (0.62 * max(4, len(fp.value))))   # must fit the body
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                c.save()
                c.translate(cx, cy)
                if vertical:
                    c.rotate(-math.pi / 2)
                text(c, fp.value, 0, -sz * 0.05, size=sz, color=C.chip_text, alpha=chip_labels,
                     align='center', valign='middle', mono=True, bold=True)
                rsz = min(max(sz * 0.72, self.px(11)), self.px(20))
                if self.view.scale >= 14:      # reference designators only when they can be read
                    text(c, ref, 0, sz * 0.62 + rsz * 0.75, size=rsz, color=C.dim_text, alpha=chip_labels * 0.9,
                         align='center', valign='middle', mono=True)
                c.restore()

    # -- highlights --------------------------------------------------------------
    def spotlight(self, boxes, amount, feather=26, r=14, pad=10):
        """Dim everything except screen boxes (x0, y0, x1, y1). Boxes may be
        footprint refs (strings) or world boxes ('w', x0, y0, x1, y1)."""
        if amount <= 0:
            return
        if self.deferred:
            self._shade.append(lambda: self._spotlight(boxes, amount, feather, r, pad))
            return
        self._spotlight(boxes, amount, feather, r, pad)

    def _spotlight(self, boxes, amount, feather, r, pad):
        rects = []
        for bx in boxes:
            if isinstance(bx, str):
                rects.append(self.box_s(bx, 0.4))
            elif bx[0] == 'w':
                a, b_ = self.sxy(bx[1], bx[2])
                c_, d = self.sxy(bx[3], bx[4])
                rects.append((a, b_, c_, d))
            else:
                rects.append(bx)
        ctx = self.ctx
        n = 6
        for i in range(n):
            g = pad + feather * (i / (n - 1))
            ctx.rectangle(0, 0, W, H)
            for (x0, y0, x1, y1) in rects:
                rounded_rect(ctx, x0 - g, y0 - g, (x1 - x0) + 2 * g, (y1 - y0) + 2 * g, r + g * 0.5)
            ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            ctx.set_source_rgba(0.02, 0.03, 0.06, amount / n)
            ctx.fill()
        ctx.set_fill_rule(cairo.FILL_RULE_WINDING)

    def dim(self, amount):
        if amount <= 0:
            return

        def go():
            self.ctx.set_source_rgba(0.02, 0.03, 0.06, amount)
            self.ctx.paint()
        if self.deferred:
            self._shade.append(go)
        else:
            go()

    def _pill_geom(self, label, x, y, size, align, mono, bold, clamp_safe=True):
        """Text x, centre y, text width, plate width/height of a pill."""
        font(self.ctx, size, bold, mono)
        tw = text_width(self.ctx, label)
        bx = x - tw / 2 if align == 'center' else x if align == 'left' else x - tw
        pw, ph = tw + 20, size * 1.55
        if clamp_safe:
            sx0, sy0, sx1, sy1 = self.SAFE
            bx = min(max(bx, sx0 + 10), sx1 - tw - 10)
            y = min(max(y, sy0 + ph / 2), sy1 - ph / 2)
        return bx, y, tw, pw, ph

    def pill(self, label, x, y, size=20, color=C.text, alpha=1.0, align='left', mono=False, bold=True,
             clamp_safe=True):
        """Label on a dark plate. (x, y) is the anchor at the vertical centre."""
        if alpha <= 0:
            return (x, y, x, y)
        ctx = self.ctx
        bx, y, tw, pw, ph = self._pill_geom(label, x, y, size, align, mono, bold, clamp_safe)
        rounded_rect(ctx, bx - 10, y - ph / 2, pw, ph, 7)
        ctx.set_source_rgba(0.025, 0.04, 0.075, 0.95 * min(1.0, 2.0 * alpha))   # opaque until well into a fade
        ctx.fill_preserve()
        ctx.set_line_width(1.0)
        set_color(ctx, color, 0.35 * alpha)
        ctx.stroke()
        text(ctx, label, bx, y, size, color, alpha, mono=mono, bold=bold, valign='middle')
        box = (bx - 10, y - ph / 2, bx - 10 + pw, y + ph / 2)
        draw_mod.log_box('pill', ctx.user_to_device(box[0], box[1]) + ctx.user_to_device(box[2], box[3]), label,
                         alpha)
        return box

    def outline(self, ref_or_box, color, alpha=1.0, pad=0.5, label=None, label_side='top', width=2.0,
                label_size=20, label_alpha=1.0):
        """Glowing rounded outline around a footprint (screen space).
        label_alpha scales the label only (to retire it while the box stays)."""
        if alpha <= 0:
            return
        if self.deferred:
            self._labels.append(lambda f: f._outline(ref_or_box, color, alpha, pad, label, label_side, width,
                                                     label_size, label_alpha))
            return
        self._outline(ref_or_box, color, alpha, pad, label, label_side, width, label_size, label_alpha)

    def _outline(self, ref_or_box, color, alpha, pad, label, label_side, width, label_size, label_alpha=1.0):
        if isinstance(ref_or_box, str):
            x0, y0, x1, y1 = self.box_s(ref_or_box, pad)
        else:
            a, b_ = self.sxy(ref_or_box[0], ref_or_box[1])
            c_, d = self.sxy(ref_or_box[2], ref_or_box[3])
            x0, y0, x1, y1 = a, b_, c_, d
        ctx = self.ctx

        def path(c):
            rounded_rect(c, x0, y0, x1 - x0, y1 - y0, 10)
        glow_stroke(ctx, path, color, width, alpha, glow=0.8, core=False)
        draw_mod.log_box('outline', ctx.user_to_device(x0, y0) + ctx.user_to_device(x1, y1), label or '?', alpha)
        if label and alpha * label_alpha > 0:
            alpha *= label_alpha
            size = max(label_size, 20)
            if label_side == 'top':
                self.pill(label, (x0 + x1) / 2, y0 - size, size, color, alpha, align='center')
            elif label_side == 'bottom':
                self.pill(label, (x0 + x1) / 2, y1 + size, size, color, alpha, align='center')
            elif label_side == 'left':
                self.pill(label, x0 - 22, (y0 + y1) / 2, size, color, alpha, align='right')
            else:
                self.pill(label, x1 + 22, (y0 + y1) / 2, size, color, alpha, align='left')

    def chip_glow(self, ref, color, alpha=1.0):
        if alpha <= 0:
            return
        x0, y0, x1, y1 = self.s.board.fp(ref).bbox
        with self.world() as c:
            for g, a in ((1.6, 0.10), (0.8, 0.16), (0.3, 0.25)):
                rounded_rect(c, x0 - g, y0 - g, x1 - x0 + 2 * g, y1 - y0 + 2 * g, 0.6 + g)
                set_color(c, color, a * alpha)
                c.fill()

    def net(self, net, color=None, alpha=1.0, front=None, source=None, width=1.0, glow=1.0, pads=True,
            tail=None):
        """Light a net. With `source` (list of (ref, pad)) and `front` (mm of
        copper), the light propagates from the source along the tracks.
        With `tail`, only a comet of that length is drawn."""
        if alpha <= 0:
            return
        color = color or family(net)
        g = self.s.graph(net)
        minw = self.px(2.4) * width
        with self.world() as c:
            if front is None:
                spans = [(e[2], e[3], e[4], e[5]) for e in g.edges]
                reached = lambda p: True  # noqa: E731
                heads = []
            else:
                fl = self.s.flow(net, source)
                spans = list(fl.lit_spans(front, tail))
                heads = fl.heads(front) if front < fl.length + 0.01 else []

                def reached(p, fl=fl, front=front):
                    d = fl.dist.get(g.pad_key.get((p.ref, p.name)), math.inf)
                    return d <= front and (tail is None or d >= front - tail)
            for (p, q, w, lay) in spans:
                if lay == 'pad':
                    continue
                ww = max(w, minw) * (0.75 if lay == 'B.Cu' else 1.0)
                glow_stroke(c, lambda cc, p=p, q=q: (cc.move_to(*p), cc.line_to(*q)), color, ww,
                            alpha * (0.75 if lay == 'B.Cu' else 1.0), glow=glow, halo=self.px(6) * width)
            if pads:
                for p in g.pads:
                    if reached(p):
                        self._pad_path(c, p, grow=self.px(1.5))
                        set_color(c, lighten(color, 0.3), alpha * 0.95)
                        c.fill()
            for (hx, hy) in heads:
                glow_dot(c, hx, hy, self.px(4.5) * width, color, alpha)

    def comet(self, polyl, d, color, length=6.0, alpha=1.0, width=1.0, head=True):
        """Comet on a netflow.Polyline at copper distance d (mm)."""
        if alpha <= 0 or d < 0 or d > polyl.length + length:
            return
        pts = polyl.sub(d - length, d)
        with self.world() as c:
            if len(pts) >= 2:
                n = 5
                for i in range(n):
                    sub = polyl.sub(d - length * (1 - i / n), d - length * (1 - (i + 1) / n))
                    if len(sub) >= 2:
                        glow_stroke(c, lambda cc, s=sub: polyline(cc, s), color, self.px(3.0) * width,
                                    alpha * (i + 1) / n, glow=0.8, core=False, halo=self.px(8) * width)
            if head and d <= polyl.length:
                hx, hy = polyl.at(d)
                glow_dot(c, hx, hy, self.px(4.0) * width, color, alpha)

    def pads_glow(self, items, color, alpha=1.0, grow=2.0):
        """items: list of (ref, pad)."""
        if alpha <= 0:
            return
        with self.world() as c:
            for ref, pn in items:
                p = self.s.board.pad(ref, pn)
                for k, a in ((3.0, 0.15), (1.5, 0.3)):
                    self._pad_path(c, p, grow=self.px(grow * k * 2))
                    set_color(c, color, a * alpha)
                    c.fill()
                self._pad_path(c, p, grow=self.px(grow))
                set_color(c, lighten(color, 0.4), alpha)
                c.fill()

    def back_pads(self, items, color=C.dim_text, alpha=1.0, offset=(0.0, 0.0), lit=None, lit_color=None):
        """Ghost outlines of rear-side pads (e.g. ISA B-side fingers)."""
        if alpha <= 0:
            return
        with self.world() as c:
            for ref, pn in items:
                p = self.s.board.pad(ref, pn)
                c.save()
                c.translate(*offset)
                self._pad_path(c, p)
                c.restore()
                c.set_dash([self.px(5), self.px(4)])
                c.set_line_width(self.px(1.6))
                on = lit and (ref, pn) in lit
                set_color(c, (lit_color or color) if on else color, alpha)
                if on:
                    c.fill_preserve()
                c.stroke()
                c.set_dash([])

    def led(self, ref, color, alpha=1.0):
        if alpha <= 0:
            return
        x0, y0, x1, y1 = self.s.board.fp(ref).bbox
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        with self.world() as c:
            glow_dot(c, cx, cy, max(0.6, self.px(5)), color, alpha)

    # -- labels ------------------------------------------------------------------
    def tag(self, wx, wy, label, color=C.text, alpha=1.0, dx=0, dy=-40, size=20, mono=False, bold=True,
            dot=True, box=True, align=None):
        """Callout: a dot at a world point and a label offset in screen px."""
        if alpha <= 0:
            return
        if self.deferred:
            self._labels.append(lambda f: f._tag(wx, wy, label, color, alpha, dx, dy, size, mono, bold, dot, box,
                                                 align))
            return
        self._tag(wx, wy, label, color, alpha, dx, dy, size, mono, bold, dot, box, align)

    def _tag(self, wx, wy, label, color, alpha, dx, dy, size, mono, bold, dot, box, align):
        ctx = self.ctx
        if box:
            size = max(size, 20)
        sx, sy = self.sxy(wx, wy)
        lx, ly = sx + dx, sy + dy
        if dot:
            ctx.new_path()
            ctx.arc(sx, sy, 4, 0, 2 * math.pi)
            set_color(ctx, color, alpha)
            ctx.fill()
        if align is None:
            align = 'center' if abs(dx) < 1 else ('left' if dx > 0 else 'right')
        if box:
            # the plate may be pushed into the safe area: end the leader on it
            off = 10 if align == 'left' else -10 if align == 'right' else 0
            by = ly + (-size * 0.5 if dy < 0 else size * 0.5 if dy > 0 else 0)
            bx, by, tw, pw, ph = self._pill_geom(label, lx + off, by, size, align, mono, bold)
            lx = min(max(lx, bx - 10), bx - 10 + pw)
            ly = min(max(ly, by - ph / 2), by + ph / 2)
        if dx or dy:
            draw_mod.log_box('line', ctx.user_to_device(sx, sy) + ctx.user_to_device(lx, ly), label, alpha)
            ctx.move_to(sx, sy)
            ctx.line_to(lx, ly)
            ctx.set_line_width(1.5)
            set_color(ctx, color, alpha * 0.7)
            ctx.stroke()
        if not box:
            font(ctx, size, bold, mono)
            tw = text_width(ctx, label)
            bx = lx - tw / 2 if align == 'center' else lx if align == 'left' else lx - tw
            text(ctx, label, bx, ly, size, color, alpha, mono=mono, bold=bold, valign='middle')
            return
        self.pill(label, bx, by, size, color, alpha, align='left', mono=mono, bold=bold)

    def subview(self, rect, view, draw_fn, alpha=1.0, title=None):
        """Picture-in-picture: draw `draw_fn(frame)` with another view into rect."""
        if alpha <= 0:
            return
        x, y, w, h = rect
        ctx = self.ctx
        from .draw import panel
        panel(ctx, x - 8, y - 40, w + 16, h + 48, alpha, r=14, fill=(0.04, 0.06, 0.1, 1.0))
        ctx.save()
        rounded_rect(ctx, x, y, w, h, 10)
        ctx.clip()
        ctx.translate(x, y)
        ctx.scale(w / W, h / H)
        ctx.push_group()
        sub = Frame(self.s, ctx, shot(view), self.t, deferred=False)
        sub.background()
        draw_fn(sub)
        ctx.pop_group_to_source()
        ctx.paint_with_alpha(alpha)
        ctx.restore()
        if title:
            text(ctx, title, x + 6, y - 14, 18, C.dim_text, alpha, bold=True)
