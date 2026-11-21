"""S14 — A whole sector: 512 bytes stream along the same path, ever faster."""
import math

from otter.anim import prog, window
from otter.camera import CamPath, drift, shot
from otter.config import C, W, H
from otter.draw import text, panel, rounded_rect, set_color
from otter.scene import Scene
from otter import widgets as wg
from .common import chain_path, finger, LED_VIEW, U7_OUT, U9_A, U9_B

K = 0.4545            # bytes(t) = (exp(K*tau) - 1) / K, reaches 512 at tau = 12 s
# narration: one byte / a sector 0.2, every byte 9.0, a file 19.4
T0, T1 = 9.0, 19.4
T_RATE, T_FILE, END = 15.8, 19.4, 26.6
# serial: card -> R8 -> 74LVC125 -> MISO -> 595 serial input
SERIAL = [('D0_LLS', ('J1', '7'), ('R8', '1')), ('Net-(R8-Pad2)', ('R8', '2'), ('U21', '12')),
          ('MISO', ('U21', '11'), ('U7', '14'))]
# parallel: 595 outputs D0..D7 -> 245 -> bus fingers DB0..DB7
PARALLEL = [[(f'D{i}', ('U7', U7_OUT[f'D{i}']), ('U9', U9_B[f'D{i}'])),
             (f'DB{i}', ('U9', U9_A[f'DB{i}']), ('J2', finger(f'DB{i}')))] for i in range(8)]
# the sector's first bytes (FAT boot sector: jump, OEM name), then stand-in data
HEAD = [0xEB, 0x3C, 0x90] + list(b'MSDOS5.0')
_PATHS = {}
# (bytes, caption, colour, [(active from, to), ...]): lit as the narration names them
# ("512 of them" 4.0, "the command" 6.3, "the replies" 7.2, "a checksum" 7.9)
STRIP = [('51 00 00 08 00 E5', 'command', C.data, [(6.2, 7.1)]), ('FF … 00', 'OK', C.spi, [(7.1, 7.9)]),
         ('FF … FE', 'data starts', C.spi, [(7.4, 7.9)]), ('512 data bytes', 'sector', C.spi, [(3.9, 5.2), (T0, T1)]),
         ('CRC16', 'check', C.spi, [(7.9, 8.8), (T1, T1 + 1.2)])]
# The strip sits above the board only while the camera holds SECTOR_VIEW: during the
# zooms in and out the board's top edge would run through it.
STRIP_IN, STRIP_OUT = 3.5, 23.6
SECTOR_VIEW = (131.0, 81.0, 200.0)


def nbytes(t):
    if t >= T1:
        return 512.0
    tau = max(t - T0, 0.0)
    return min(512.0, (math.exp(K * tau) - 1) / K * 512.0 / ((math.exp(K * (T1 - T0)) - 1) / K))


def byte(j):
    if j < len(HEAD):
        return HEAD[j]
    return (j * 2654435761 >> 13) & 0xFF


def paths(stage):
    if id(stage) not in _PATHS:
        _PATHS[id(stage)] = (chain_path(stage, SERIAL), [chain_path(stage, p) for p in PARALLEL])
    return _PATHS[id(stage)]


# Speeds: a bit on the serial wire (MISO) moves eight times as fast as a byte on
# the eight parallel data lines. Parallel speed grows during the sector.
RATIO = 8.0
V0, ACC = 14.0, 7.0          # parallel speed (mm/s) = V0 + ACC * (t - T0)
PAR_TIME = 1.0               # rough seconds a byte spends on the data lines (for thinning)
MAX_IN_FLIGHT = 22           # bytes drawn at once on the data lines


def par_speed(t):
    return V0 + ACC * max(0.0, t - T0)


def travelled(ts, t):
    """Distance (mm) covered at parallel speed between ts and t."""
    a, b = max(ts - T0, 0.0), max(t - T0, 0.0)
    return V0 * (t - ts) + ACC / 2 * (b * b - a * a)


def rate(t):
    """Bytes per second arriving at time t."""
    scale = 512.0 / ((math.exp(K * (T1 - T0)) - 1) / K)
    return scale * math.exp(K * max(0.0, min(t, T1) - T0))


def spawn_time(j):
    """Scene time at which byte j (0-based) starts."""
    scale = 512.0 / ((math.exp(K * (T1 - T0)) - 1) / K)
    return T0 + math.log(1 + K * j / scale) / K


class Sector(Scene):
    name = 's14_sector'
    title = 'A whole sector'
    duration = 27.0
    cam = CamPath((0, (138.0, 104.0, 86.0)), (3.5, SECTOR_VIEW), (23.6, SECTOR_VIEW), (26.6, 'FULL'), (27, 'FULL'))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        ser, par = paths(f.s)
        n = int(nbytes(t))
        if T0 <= t < T1 + 3.5:
            fade = 1 - prog(t, T1 + 2.0, T1 + 3.5)
            # thin the drawn bytes as the rate grows (powers of two, so a byte
            # that is drawn stays drawn)
            stride = 1
            while rate(t) * PAR_TIME / stride > MAX_IN_FLIGHT:
                stride *= 2
            j = 0
            while j <= n:
                ts = spawn_time(j)
                if ts <= t:
                    s_ = travelled(ts, t) * RATIO          # serial distance: eight times as far
                    if (s_ - ser.length) / RATIO <= max(p.length for p in par) + 10:
                        self.byte_comets(f, ser, par, s_, byte(j), fade)
                j += stride
        # closing caption: the paths stay lit, with calm byte pulses on them
        ga = window(t, T1 + 1.0, 27.5, 1.0, 0.6)
        if ga > 0:
            from otter.draw import glow_stroke, polyline
            with f.world() as c:
                for pl, col in [(ser, C.spi)] + [(p, C.data) for p in par]:
                    glow_stroke(c, lambda cc, pl=pl: polyline(cc, pl.pts), col, f.px(2.6), 0.4 * ga, glow=0.8,
                                halo=f.px(6))
            span = ser.length + RATIO * max(p.length for p in par)      # serial-distance units
            for k in range(2):
                s_ = ((t - T1 - 1.0) * RATIO * 12.0 + k * span / 2) % span
                self.byte_comets(f, ser, par, s_, HEAD[k], ga)

    @staticmethod
    def byte_comets(f, ser, par, s_, value, alpha):
        """One byte: a single comet on the serial path (MISO); past the 595 it
        continues as eight comets, one per data line (0 bits dim), at 1/8 of
        the serial speed. `s_` is the distance travelled at serial speed."""
        if s_ <= ser.length + 10:
            f.comet(ser, s_, C.spi, length=10, width=1.5, alpha=alpha)
        dp = (s_ - ser.length) / RATIO
        if dp > 0:
            for i, p in enumerate(par):
                bit = (value >> i) & 1
                f.comet(p, dp, C.data, length=8, width=1.2 if bit else 0.8, alpha=alpha * (1.0 if bit else 0.25))

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, 0.2, END, 0.6, 0.6)
        sa = window(t, STRIP_IN, STRIP_OUT, 0.5, 0.6)
        from otter.draw import font, text_width
        font(ctx, 22, True, True)
        widths = [text_width(ctx, seg[0]) + 40 for seg in STRIP]
        x = (W - (sum(widths) + 18 * (len(widths) - 1))) / 2
        y = 34
        for i, ((s_, lab, col, spans), w) in enumerate(zip(STRIP, widths)):
            ai = sa * prog(t, STRIP_IN + i * 0.2, STRIP_IN + 0.5 + i * 0.2)
            active = any(p0 <= t < p1 for p0, p1 in spans)
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
        na = window(t, T_RATE, END, 0.6, 0.6)
        text(ctx, '≈ 38 KB/s', 70, 230, 44, C.clock, na, bold=True)
        text(ctx, "including the PC's own work", 70, 262, 18, C.dim_text, na)
        fa = window(t, T_FILE + 0.6, END, 0.6, 0.6)
        text(ctx, 'a file = a list of sectors', 70, 320, 24, C.text, fa, bold=True)
        # MISO blinks while the sector streams in
        miso = (1.0 if (t * 5.0) % 1.0 < 0.55 else 0.12) if T0 <= t < T1 + 0.4 else 0.0
        led_inset(f, {'D1': 1.0, 'D2': 0.0, 'D3': miso}, window(t, T0, T1 + 1.0, 0.6, 0.6))


def led_inset(f, states, alpha, rect=(40, 600, 340, 191), crop_w=226):
    """The status-LED picture-in-picture (as common.leds_pip), cropped on the
    right to just the LEDs and their labels."""
    if alpha <= 0:
        return
    from otter.camera import View
    from otter.stage import Frame
    x, y, w, h = rect
    ctx = f.ctx
    panel(ctx, x - 8, y - 40, crop_w + 16, h + 48, alpha, r=14, fill=(0.04, 0.06, 0.1, 1.0))
    ctx.save()
    rounded_rect(ctx, x, y, crop_w, h, 10)
    ctx.clip()
    ctx.translate(x, y)
    ctx.scale(w / W, h / H)
    ctx.push_group()
    sub = Frame(f.s, ctx, View(*LED_VIEW), f.t, deferred=False)
    sub.background()
    sub.board(xray=1.0, chip_labels=0.0)
    for ref, col in (('D1', C.ok), ('D2', C.spi), ('D3', C.spi)):
        sub.led(ref, col, states.get(ref, 0.0))
    ctx.pop_group_to_source()
    ctx.paint_with_alpha(alpha)
    ctx.restore()
    text(ctx, 'status LEDs', x + 6, y - 14, 18, C.dim_text, alpha, bold=True)
    sv = View(*LED_VIEW)
    for ref, lab in (('D1', '/CS'), ('D2', 'MOSI'), ('D3', 'MISO')):
        x0, y0, x1, y1 = f.s.board.fp(ref).bbox
        px, py = sv.to_screen(x1 + 0.6, (y0 + y1) / 2)
        on = states.get(ref, 0.0) > 0.5
        f.pill(lab, x + px * w / W, y + py * h / H, 19, C.text if on else C.dim_text, alpha, mono=True,
               clamp_safe=False)


SCENE = Sector()
