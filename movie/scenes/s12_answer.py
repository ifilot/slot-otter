"""S12 — The card answers: rest of CMD17, R1, data token, then EBh in slow motion."""
from otter.anim import prog, window, Schedule
from otter.camera import CamPath, drift
from otter.config import C
from otter.draw import text, panel
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
_t += 0.6
REPLY_START = _t
for r in (0xFF, 0x00, 0xFF, 0xFF, 0xFE):
    SEQ.append((_t, FAST, 0xFF, r))
    _t += FAST
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
    duration = 28.0
    cam = CamPath((0, (152.0, 75.7, 104.0)), (2.5, SHIFT_VIEW), (28, SHIFT_VIEW))
    captions = [
        (0.4, 5.4, 'Next comes the sector number, 2048, where a partition usually starts, then a checksum.'),
        (5.8, 8.8, 'To listen, the driver simply sends FFh.'),
        (9.0, 11.9, 'The card answers 00h (OK), then FEh (data starts now).'),
        (12.2, 21.6, "Out comes the sector's first byte, EBh, the start of a FAT boot sector."),
        (22.0, 27.4, "The byte now waits in the 595's output latch."),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.dim(0.78)

    def overlay(self, f, t):
        ctx = f.ctx
        a = window(t, -1, 27.6, 0.0, 0.6)
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
        sent = [s[2] for s in SEQ if t >= s[0] + s[1] * 0.98]
        got = [s[3] for s in SEQ if t >= s[0] + s[1] * 0.98]
        sent = [0x51] + sent
        got = [0xFF] + got
        x0 = 1150
        text(ctx, 'sent', x0, 300, 17, C.dim_text, a, bold=True)
        text(ctx, ' '.join(f'{b:02X}' for b in sent[-9:]), x0 + 90, 300, 20, C.data, a, mono=True)
        text(ctx, 'received', x0, 330, 17, C.dim_text, a, bold=True)
        text(ctx, ' '.join(f'{b:02X}' for b in got[-9:]), x0 + 90, 330, 20, C.spi, a, mono=True)
        la = a * window(t, REPLY_START + 2.0, REPLY_START + 3.9, 0.3, 0.4)
        text(ctx, 'R1 = 00h: no errors', 130, 610, 21, C.spi, la, bold=True)
        lb = a * window(t, REPLY_START + 5.0, SLOW_START + 1.4, 0.3, 0.4)
        text(ctx, 'FEh: data block starts', 130, 610, 21, C.spi, lb, bold=True)
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
            text(ctx, 'CMD17', 92, 256, 16, C.dim_text, ba * 0.6)
            text(ctx, 'sector 2048', 152, 256, 16, C.dim_text, ba)
            text(ctx, 'CRC7', 340, 256, 16, C.dim_text, ba)


SCENE = Answer()
