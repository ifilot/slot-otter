"""S12 — The card answers: rest of CMD17, R1, data token, then EBh in slow motion."""
from otter.anim import prog, window, Schedule
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, font, text_width, rounded_rect, set_color
from otter.scene import Scene
from otter import widgets as wg
from .common import SpiRing, CMD17, RX_BYTE, bits

SHIFT_VIEW = (158.0, 70.0, 64.0)

# (t_start, seconds per byte, byte sent, byte received)
FAST = 1.0
SEQ = []
_t = 0.6
for b in CMD17[1:]:
    SEQ.append((_t, FAST, b, 0xFF))
    _t += FAST
# narration: rest of the command 0.4, keeps sending FFh 7.5, OK / data 17.9, EBh 22.3, waits 31.2
POLL = 1.4
_t = 8.2
REPLY_START = _t
REPLY_IDX = (len(SEQ) + 6, len(SEQ) + 8)        # SEQ indices of the 00h (OK) and FEh (data token) replies
for r in (0xFF,) * 6 + (0x00, 0xFF, 0xFE):
    SEQ.append((_t, POLL, 0xFF, r))
    _t += POLL
_t += 0.6
SLOW_START = _t
SLOW = Schedule(SLOW_START, [(9.6, 1 / 1.2)])
SEQ.append((SLOW_START, 9.6, 0xFF, RX_BYTE))


def rings():
    out = []
    prev = 0xFF
    for t0, dur, tx, rx in SEQ:
        out.append((t0, dur, tx, rx, SpiRing(tx, rx, rx_init=bits(prev), latch_init=bits(prev))))
        prev = rx
    return out


RINGS = rings()


class Answer(Scene):
    name = 's12_answer'
    title = 'The card answers'
    duration = 35.5
    cam = CamPath((0, (152.0, 72.6, 104.0)), (2.5, SHIFT_VIEW), (35.5, SHIFT_VIEW))

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.dim(0.78)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, -1, 35.1, 0.0, 0.6)
        cur = RINGS[0]
        for r in RINGS:
            if t >= r[0]:
                cur = r
        t0, dur, tx, rx, ring = cur
        if t0 == SLOW_START:
            c = SLOW(t)
        else:
            c = min(8.0, (t - t0) / dur * 8.0) if t >= t0 else 0.0
        title = f'OUT 330h, {tx:02X}h' + ('   (listening)' if t >= REPLY_START - 0.3 else '')
        ring.draw(ctx, c, a, labels=1.0, legend=0.0, title=title)
        # byte log
        done = [s for s in SEQ if t >= s[0] + s[1] * 0.98]
        sent = [0x51] + [s[2] for s in done]
        got = [0xFF] + [s[3] for s in done]
        x0 = 1150
        text(ctx, 'sent', x0, 300, 17, C.dim_text, a, bold=True)
        text(ctx, ' '.join(f'{b:02X}' for b in sent[-9:]), x0 + 90, 300, 20, C.data, a, mono=True)
        text(ctx, 'received', x0, 330, 17, C.dim_text, a, bold=True)
        text(ctx, ' '.join(f'{b:02X}' for b in got[-9:]), x0 + 90, 330, 20, C.spi, a, mono=True)
        # the replies the narration names: their entries in the log are boxed,
        # and a caption sits at the end of the 'received' row
        font(ctx, 20, False, True)
        cw = text_width(ctx, 'FF ')                       # one log entry
        first = max(0, len(got) - 9)                      # index in `got` of the leftmost entry shown
        t_ok, t_fe = SEQ[REPLY_IDX[0]], SEQ[REPLY_IDX[1]]
        t_ok, t_fe = t_ok[0] + t_ok[1] * 0.98, t_fe[0] + t_fe[1] * 0.98
        for idx, t_in in zip(REPLY_IDX, (t_ok, t_fe)):
            ha = a * window(t, t_in, SLOW_START + 2.0, 0.3, 0.5)
            k = idx + 1 - first                           # position in the row
            if ha > 0 and 0 <= k < 9:
                bx = x0 + 90 + k * cw
                rounded_rect(ctx, bx - 5, 330 - 21, text_width(ctx, 'FF') + 10, 28, 5)
                ctx.set_line_width(2.0)
                set_color(ctx, C.spi, ha)
                ctx.stroke()
        la = a * window(t, t_ok, t_fe, 0.3, 0.3)
        f.pill('00h: OK', 1590, 321, 19, C.spi, la)
        lb = a * window(t, t_fe, SLOW_START + 2.0, 0.3, 0.5)
        f.pill('FEh: here comes the data', 1590, 321, 19, C.spi, lb)
        # the byte the card is about to send, from the moment it starts
        ea = a * window(t, SLOW_START - 0.2, SLOW.end + 0.6, 0.5, 0.6)
        if ea > 0:
            cx0, cy0, cw_, ch = SpiRing.CARD
            f.pill('sending EBh = 1110 1011', cx0 + cw_ / 2, cy0 + ch - 36, 20, C.spi, ea, align='center',
                   mono=True)
        fa = a * prog(t, SLOW.end, SLOW.end + 0.6)
        f.pill('EBh: first byte of the sector', 1660, 735, 20, C.spi, fa, align='center')
        ba = a * window(t, 0.4, 5.6, 0.4, 0.5)
        if ba > 0:
            cur = int((t - SEQ[0][0]) // FAST)          # index into 00 00 08 00 E5
            xs = [92, 140, 188, 236, 284, 340]
            for k, (bx, bt) in enumerate(zip(xs, ['51', '00', '00', '08', '00', 'E5'])):
                j = k - 1
                st = 0.4 if j < cur else (1.0 if j == cur else 0.75)
                text(ctx, bt, bx, 225, 26, C.data, ba * st, mono=True, bold=True)
                if j == cur:
                    ctx.rectangle(bx, 232, 32, 3)
                    ctx.set_source_rgba(*C.data[:3], ba)
                    ctx.fill()
            text(ctx, 'command', 108, 256, 16, C.dim_text, ba * 0.6, align='center')
            text(ctx, 'which block', 228, 256, 16, C.dim_text, ba, align='center')
            text(ctx, 'check', 356, 256, 16, C.dim_text, ba, align='center')


SCENE = Answer()
