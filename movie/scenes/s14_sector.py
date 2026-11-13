"""S14 — A whole sector: 512 bytes stream along the same path, ever faster."""
import math

from otter.anim import prog, window
from otter.camera import CamPath, drift, shot
from otter.config import C, W
from otter.draw import text, panel, rounded_rect, set_color
from otter.scene import Scene
from otter import widgets as wg
from .common import chain_path, leds_pip

K = 0.4545            # bytes(t) = (exp(K*tau) - 1) / K, reaches 512 at tau = 12 s
T0, T1 = 4.6, 15.0
PATH = [('D0_LLS', ('J1', '7'), ('R8', '1')), ('Net-(R8-Pad2)', ('R8', '2'), ('U21', '12')),
        ('MISO', ('U21', '11'), ('U7', '14')), ('D7', ('U7', '7'), ('U9', '11')), ('DB7', ('U9', '9'), ('J2', 'A02'))]
STRIP = [('51 00 00 08 00 E5', 'command', C.data, 0.6, 2.2), ('FF … 00', 'R1', C.spi, 2.2, 3.4),
         ('FF … FE', 'token', C.spi, 3.4, 4.6), ('512 data bytes', 'sector', C.spi, 4.6, 15.0),
         ('CRC16', 'check', C.spi, 15.0, 16.2)]
SECTOR_VIEW = (131.0, 81.0, 200.0)


def nbytes(t):
    if t >= T1:
        return 512.0
    tau = max(t - T0, 0.0)
    return min(512.0, (math.exp(K * tau) - 1) / K * 512.0 / ((math.exp(K * (T1 - T0)) - 1) / K))


def spawn_time(j):
    """Scene time at which byte j (0-based) starts."""
    scale = 512.0 / ((math.exp(K * (T1 - T0)) - 1) / K)
    return T0 + math.log(1 + K * j / scale) / K


class Sector(Scene):
    name = 's14_sector'
    title = 'A whole sector'
    duration = 22.0
    cam = CamPath((0, (138.0, 104.0, 86.0)), (3.5, SECTOR_VIEW), (19.0, SECTOR_VIEW), (22, 'FULL'))
    captions = [
        (0.2, 6.0, 'A complete read: six bytes out, a short wait, a start token, 512 data bytes and a checksum.'),
        (16.4, 21.4, 'Every one of them takes the path you have just seen.'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        path = chain_path(f.s, PATH)
        n = int(nbytes(t))
        speed = 90 + 40 * max(0, t - T0)
        if T0 <= t < T1 + 2.5:
            fade = 1 - prog(t, T1 + 1.0, T1 + 2.5)
            for j in range(max(0, n - 40), n + 1):
                ts = spawn_time(j)
                if ts > t:
                    continue
                d = (t - ts) * speed
                if d > path.length + 10:
                    continue
                f.comet(path, d, C.spi if d < path.length * 0.45 else C.data, length=10, width=1.5, alpha=fade)
        # closing caption: the path stays lit, with calm pulses on it
        ga = window(t, T1 + 1.0, 22.5, 1.0, 0.6)
        if ga > 0:
            from otter.draw import glow_stroke, polyline
            with f.world() as c:
                glow_stroke(c, lambda cc: polyline(cc, path.pts), C.spi, f.px(2.6), 0.45 * ga, glow=0.8,
                            halo=f.px(6))
            for k in range(2):
                d = ((t - T1 - 1.0) * 60 + k * path.length / 2) % path.length
                f.comet(path, d, C.data, length=10, width=1.5, alpha=ga)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, 0.2, 21.6, 0.6, 0.6)
        from otter.draw import font, text_width
        font(ctx, 22, True, True)
        widths = [text_width(ctx, seg[0]) + 40 for seg in STRIP]
        x = (W - (sum(widths) + 18 * (len(widths) - 1))) / 2
        y = 34
        for i, ((s_, lab, col, p0, p1), w) in enumerate(zip(STRIP, widths)):
            ai = a * prog(t, 0.4 + i * 0.35, 0.9 + i * 0.35)
            active = p0 <= t < p1
            k = 1.0 if active else 0.5
            rounded_rect(ctx, x, y, w, 50, 10)
            set_color(ctx, col, (0.24 if active else 0.1) * ai)
            ctx.fill_preserve()
            ctx.set_line_width(2.5 if active else 1.5)
            set_color(ctx, col, ai * k)
            ctx.stroke()
            text(ctx, s_, x + 20, y + 25, 22, col, ai * k, mono=True, bold=True, valign='middle')
            text(ctx, lab, x + w / 2, y + 76, 17, C.dim_text, ai * k, align='center')
            x += w + 18
        nb = int(nbytes(t)) if t >= T0 else 0
        ca = a * prog(t, T0 - 0.5, T0)
        text(ctx, f'{nb:3d} / 512', 1870, 230, 44, C.spi, ca, mono=True, bold=True, align='right')
        text(ctx, 'data bytes', 1870, 262, 18, C.dim_text, ca, align='right')
        na = window(t, T1, 21.6, 0.6, 0.6)
        wg.note(ctx, 'About 520 bursts of eight clocks. Each byte costs the driver four I/O cycles; the 1\u00a0µs burst '
                     'is the quick part. OTTERSD turns sectors into FAT files and a drive letter.',
                60, 170, na, w=330, size=21, accent=C.spi)
        k = int((t * 30)) % 8
        leds_pip(f, t, {'D1': 1.0, 'D2': 0.0, 'D3': 1.0 if (k * 37) % 5 < 2 else 0.0},
                 window(t, T0, T1 + 1.0, 0.6, 0.6), rect=(40, 600, 340, 191))


SCENE = Sector()
