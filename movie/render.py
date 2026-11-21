#!/usr/bin/env python3
"""Render the Slot-otter Classic explainer.

One timeline: the narration (scenes/narration.py) sets the pace. Both cuts
share the same pictures; the silent cut is the voice-over cut without audio
(subtitles burned in).

    python render.py list
    python render.py voice                               # synthesise narration (Kokoro), report timing
    python render.py check                               # camera continuity, label collisions
    python render.py all                                 # silent + voice-over cut -> build/
    python render.py all --clean --res 3840x2160         # 4K voice-over cut without burned-in subtitles
    python render.py publish                             # 1080p + 4K, SRT/VTT, chapters, teaser -> build/publish/
    python render.py plate [--ppm 48] [--samples 256]     # photoreal plate via Blender
    python render.py still s04 4.5 [--res 1920x1080]     # one frame -> build/stills/
    python render.py contact s04 [--n 12]                # contact sheet across a scene
    python render.py preview s04                         # 960x540 @ 30 fps, fast
    python render.py scene s04                           # final quality, one scene

Scene ids accept 's04', '4' or a module name such as 's04_comparator'.
"""
from __future__ import annotations

import argparse
import glob
import importlib
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from otter.config import W, H, FPS, BUILD, REPO, PCB_FILE, PLATE_PNG, PLATE_JSON  # noqa: E402

VO_DIR = os.path.join(BUILD, 'voiceover')
VOICE = os.environ.get('OTTER_VOICE', 'af_heart')
VOICE_SPEED = float(os.environ.get('OTTER_VOICE_SPEED', '0.92'))

_STAGE = None
_SCENES = None
_TIMED = False


def scenes(timed=True):
    """The scenes in order. With `timed`, the narration timing is attached
    (every render follows the narration; needs `render.py voice` first)."""
    global _SCENES, _TIMED
    if _SCENES is None:
        pkg = importlib.import_module('scenes')
        _SCENES = [importlib.import_module(f'scenes.{m}').SCENE for m in pkg.ORDER]
    if timed and not _TIMED:
        _TIMED = True
        setup_vo()
    return _SCENES


def find(sid):
    sid = str(sid)
    for i, s in enumerate(scenes()):
        if sid in (s.name, s.name.split('_')[0]) or sid == str(i + 1) or sid.lstrip('s0') == s.name[1:3].lstrip('0'):
            return i
    raise SystemExit(f'unknown scene {sid!r}; try `render.py list`')


def _init():
    """Load the stage once. Workers are forked after this, so they inherit
    it copy-on-write instead of reloading (Python 3.14 defaults to
    'forkserver', which would reload the plate in every worker)."""
    global _STAGE
    if _STAGE is None:
        from otter.stage import Stage
        _STAGE = Stage()


def pool(n):
    import multiprocessing as mp
    _init()
    scenes()
    return mp.get_context('fork').Pool(n)


EXTRA = {}          # non-movie scenes (teaser), addressed by string key


def scene_for(key):
    return EXTRA[key] if isinstance(key, str) else scenes()[key]


XFADE = 0.8        # seconds: every cut dissolves from the previous scene's last frame


_FRAMES_DRAWN = 0


def render_frame(job):
    import cairo
    import gc
    from otter.anim import ease
    global _FRAMES_DRAWN
    # Drawing leaves reference cycles that keep whole frame-sized cairo surfaces alive
    # until Python's occasional full collection: at 4K a worker grew by ~2.6 GB per 120
    # frames and 20 workers ran the machine out of memory. Collecting every 10 frames
    # keeps a worker within a few hundred MB (and is slightly faster).
    _FRAMES_DRAWN += 1
    if _FRAMES_DRAWN % 10 == 0:
        gc.collect()
    idx, t, w, h = job
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(w / W, h / H)
    sc = scene_for(idx)
    sc.render(_STAGE, ctx, t)
    if isinstance(idx, int) and idx > 0 and t < XFADE:
        # Cross-dissolve: whatever the previous scene still shows at its end
        # (spotlights, dimming, labels) fades out instead of popping off. It is
        # drawn through this scene's camera, so a camera move here does not ghost.
        prev = scenes()[idx - 1]
        u = ease('smooth')(t / XFADE)
        under = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        c2 = cairo.Context(under)
        c2.scale(w / W, h / H)
        prev.render(_STAGE, c2, prev.length, view=sc.view(sc.scene_time(t)), captions=False)
        under.flush()
        ctx.save()
        ctx.identity_matrix()
        ctx.set_source_surface(under, 0, 0)
        ctx.paint_with_alpha(1 - u)
        ctx.restore()
    surf.flush()
    return bytes(surf.get_data())


def save_png(data, w, h, path):
    import cairo
    surf = cairo.ImageSurface.create_for_data(bytearray(data), cairo.FORMAT_ARGB32, w, h)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    surf.write_to_png(path)


def parse_res(s):
    w, h = s.lower().split('x')
    return int(w), int(h)


# --------------------------------------------------------------------------
def narration_jobs():
    from scenes.narration import NARRATION
    jobs = []
    for sc in scenes(timed=False):
        for i, (_t, _sub, spoken) in enumerate(NARRATION.get(sc.name, [])):
            jobs.append({'id': f'{sc.name}.{i}', 'text': spoken, 'voice': VOICE, 'speed': VOICE_SPEED})
    return jobs


def setup_vo():
    """Attach voice-over timing to every scene (needs `render.py voice` first)."""
    import json
    from scenes.narration import NARRATION, subtitle
    from otter.voiceover import VoTiming
    man_path = os.path.join(VO_DIR, 'lines', 'manifest.json')
    if not os.path.exists(man_path):
        raise SystemExit('no narration audio yet: run `render.py voice` first')
    man = json.load(open(man_path))
    for sc in scenes(timed=False):
        lines = NARRATION.get(sc.name, [])
        durs = []
        for i, (_t, _sub, spoken) in enumerate(lines):
            m = man.get(f'{sc.name}.{i}')
            if not m or m['text'] != spoken or m['voice'] != VOICE or m['speed'] != VOICE_SPEED:
                raise SystemExit(f'{sc.name}.{i}: narration audio is stale: run `render.py voice`')
            durs.append(m['duration'])
        if lines:
            subs = [(t, subtitle(sc.name, i), spoken) for i, (t, _sub, spoken) in enumerate(lines)]
            sc.vo = VoTiming(sc.duration, subs, durs)
        else:
            from otter.voiceover import VoTiming as V
            sc.vo = V(sc.duration, [(sc.duration, '', '')], [0.0])
            sc.vo.cues, sc.vo.clips = [], []
    return man


def mix_narration(man, out_wav):
    """Place every line at its voice-over time and write one track."""
    import wave
    import numpy as np
    sr = 24000

    def read_wav(path):
        with wave.open(path, 'rb') as w:
            assert w.getframerate() == sr and w.getsampwidth() == 2 and w.getnchannels() == 1, path
            return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0
    total = sum(sc.length for sc in scenes())
    track = np.zeros(int(total * sr) + sr, np.float32)
    off = 0.0
    for sc in scenes():
        for t0, i in sc.vo.clips:
            m = man[f'{sc.name}.{i}']
            audio = read_wav(os.path.join(VO_DIR, 'lines', m['file']))
            k = int(round((off + t0) * sr))
            track[k:k + len(audio)] += audio[:len(track) - k]
        off += sc.length
    peak = float(np.max(np.abs(track))) or 1.0
    pcm = (np.clip(track / peak * 0.89, -1, 1) * 32767).astype(np.int16)
    with wave.open(out_wav, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return total


def cmd_voice(a):
    """Synthesise the narration (Kokoro, in .venv-tts) and report the timing."""
    import json
    os.makedirs(os.path.join(VO_DIR, 'lines'), exist_ok=True)
    jobs_path = os.path.join(VO_DIR, 'jobs.json')
    with open(jobs_path, 'w') as f:
        json.dump(narration_jobs(), f, indent=1)
    py = os.path.join(HERE, '.venv-tts', 'bin', 'python')
    subprocess.check_call([py, os.path.join(HERE, 'voice', 'tts.py'), jobs_path, os.path.join(VO_DIR, 'lines')])
    setup_vo()
    tot_s = tot_v = 0.0
    for sc in scenes(timed=False):
        tot_s += sc.duration
        tot_v += sc.length
        slow = max(sc.vo.rates) if sc.vo.rates else 1.0
        print(f'{sc.name:18s} {sc.duration:6.1f} s -> {sc.length:6.1f} s   max slow-down x{slow:.2f}')
    print(f'total {tot_s:.1f} s -> {tot_v:.1f} s ({int(tot_v // 60)}:{tot_v % 60:04.1f})')


def cmd_script(a):
    """Regenerate the narration blocks in SCRIPT.md from scenes/narration.py."""
    import re
    from scenes.narration import NARRATION
    path = os.path.join(HERE, 'SCRIPT.md')
    doc = open(path, encoding='utf-8').read()
    for sc in scenes():
        nar = NARRATION.get(sc.name, [])
        lines = [f'**Narration** (scene time; {sc.duration:g} s of animation, {sc.length:.1f} s on screen)']
        for t, written, spoken in nar:
            lines.append(f'- {t:.1f} — {written or "*(title card)*"}')
            lines.append(f'  - spoken: "{spoken}"')
        if not nar:
            lines.append('- none')
        block = '\n'.join(lines)
        doc, n = re.subn(rf'<!-- narration:{sc.name} -->.*?<!-- /narration -->',
                         f'<!-- narration:{sc.name} -->\n{block}\n<!-- /narration -->', doc, flags=re.S)
        if not n:
            print(f'warning: no marker for {sc.name} in SCRIPT.md')
    total = sum(sc.length for sc in scenes())
    doc = re.sub(r'\*\*Length\*\*: [^.]*\.', f'**Length**: {int(total // 60)} min {total % 60:.0f} s.', doc)
    open(path, 'w', encoding='utf-8').write(doc)
    print(f'updated {path}')


def _ts(t, sep=','):
    h, r = divmod(max(0.0, t), 3600)
    m, sec = divmod(r, 60)
    return f'{int(h):02d}:{int(m):02d}:{int(sec):02d}{sep}{int(round((sec % 1) * 1000)) % 1000:03d}'


def cue_list():
    """Absolute (t_in, t_out, text) for the whole movie."""
    from otter.widgets import curly
    out, off = [], 0.0
    for sc in scenes():
        for t0, t1, txt in sc.vo.cues:
            out.append((off + t0, off + t1, curly(txt).replace('\u00a0', ' ')))
        off += sc.length
    return out


def cmd_subtitles(a):
    pub = os.path.join(BUILD, 'publish')
    os.makedirs(pub, exist_ok=True)
    cues = cue_list()
    base = os.path.join(pub, 'slot-otter-classic')
    with open(base + '.srt', 'w', encoding='utf-8') as f:
        for i, (t0, t1, txt) in enumerate(cues, 1):
            f.write(f'{i}\n{_ts(t0)} --> {_ts(t1)}\n{txt}\n\n')
    with open(base + '.vtt', 'w', encoding='utf-8') as f:
        f.write('WEBVTT\n\n')
        for t0, t1, txt in cues:
            f.write(f'{_ts(t0, ".")} --> {_ts(t1, ".")}\n{txt}\n\n')
    print(f'{base}.srt / .vtt  ({len(cues)} cues)')


def cmd_chapters(a):
    """YouTube chapters: first at 0:00, each at least 10 s (short scenes merge into the previous)."""
    pub = os.path.join(BUILD, 'publish')
    os.makedirs(pub, exist_ok=True)
    chapters, off = [], 0.0
    for sc in scenes():
        if chapters and sc.length < 10.0:
            off += sc.length
            continue
        chapters.append((off, sc.title))
        off += sc.length
    path = os.path.join(pub, 'chapters.txt')
    with open(path, 'w', encoding='utf-8') as f:
        for t, title in chapters:
            f.write(f'{int(t // 60)}:{int(t % 60):02d} {title}\n')
    print(path)
    print(open(path, encoding='utf-8').read())


class Teaser:
    """The SPI ring's eight clocks, without captions, with a title line."""
    name = 'teaser'
    T0, T1 = 2.4, 19.2

    def __init__(self):
        self.src = scenes()[find('s11')]
        self.length = self.T1 - self.T0

    def render(self, stage, ctx, t):
        from otter.anim import window
        from otter.draw import text
        from otter.config import C
        self.src.show_captions = False
        self.src.render(stage, ctx, self.T0 + t)
        a = window(t, 0.0, self.length, 0.6, 0.6)
        text(ctx, 'Slot-otter Classic', W / 2, H - 120, 40, C.text, a, align='center', bold=True)
        text(ctx, 'eight clocks: how SPI swaps two bytes', W / 2, H - 72, 26, C.dim_text, a, align='center')


def cmd_teaser(a):
    pub = os.path.join(BUILD, 'publish')
    os.makedirs(pub, exist_ok=True)
    EXTRA['teaser'] = Teaser()
    out = os.path.join(pub, 'teaser.mp4')
    encode('teaser', out, 1920, 1080, 60, a.jobs, 16, 'slow')
    gif = os.path.join(pub, 'teaser.gif')
    subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-i', out, '-vf',
                           'fps=15,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];'
                           '[b][p]paletteuse=dither=bayer:bayer_scale=4', gif])
    print(f'-> {gif} ({os.path.getsize(gif) / 1e6:.1f} MB)')


def cmd_publish(a):
    """Everything for a YouTube release, collected in build/publish/."""
    import shutil as sh
    from types import SimpleNamespace as NS
    pub = os.path.join(BUILD, 'publish')
    os.makedirs(pub, exist_ok=True)
    base = dict(skip_existing=a.skip_existing, fps=FPS, crf=16, jobs=a.jobs)
    runs = [NS(clean=False, res=f'{W}x{H}', **base),      # silent + voice-over, subtitles burned in
            NS(clean=True, res='3840x2160', **base)]     # 4K voice-over, subtitles as files
    for r in runs:
        for sc in scenes():
            sc.show_captions = True
        for final in cmd_all(r):
            sh.copy2(final, os.path.join(pub, os.path.basename(final)))
    cmd_subtitles(a)
    cmd_chapters(a)
    cmd_teaser(a)
    print(f'publish set in {pub}')


def cmd_list(a):
    total = 0
    for i, s in enumerate(scenes()):
        print(f'{i + 1:2d}  {s.name:22s} {s.length:6.1f} s   {s.title}')
        total += s.length
    print(f'    total {total:.1f} s = {int(total // 60)}:{total % 60:04.1f}')


def cmd_check(a):
    """Camera continuity across scene cuts and label collisions."""
    ok = True
    sc = scenes()
    for x, y in zip(sc, sc[1:]):
        v0, v1 = x.view(x.duration), y.view(0.0)
        d = max(abs(v0.cx - v1.cx), abs(v0.cy - v1.cy)) * W / v1.w
        dz = abs(v0.w / v1.w - 1)
        flag = d > 0.5 or dz > 0.001
        ok &= not flag
        print(f'{x.name:18s} -> {y.name:18s} jump {d:5.2f} px  zoom {dz * 100:5.2f} %  {"<-- check" if flag else "ok"}')
    ok &= check_cuts(sc, a.jobs)
    ok &= check_labels(sc, a.step, a.jobs)
    print('all good' if ok else 'issues found')


def _frame_px(job):
    import numpy as np
    idx, t, w, h = job
    return np.frombuffer(render_frame(job), np.uint8).reshape(h, w, 4)[:, :, :3].astype(np.int16)


def check_cuts(sc, jobs, w=480, h=270):
    """Compare the last frame of each scene with the first frame of the next
    (captions off): anything that pops on or off, or a jump in brightness,
    shows up as changed pixels."""
    import numpy as np
    keep = [s_.show_captions for s_ in sc]
    for s_ in sc:
        s_.show_captions = False
    pairs = [(i, s_.length - 1 / FPS) for i, s_ in enumerate(sc[:-1])]
    jobs_ = [(i, t, w, h) for i, t in pairs] + [(i + 1, 0.0, w, h) for i, _ in pairs]
    with pool(jobs) as p:
        res = p.map(_frame_px, jobs_)
    for s_, k in zip(sc, keep):
        s_.show_captions = k
    n = len(pairs)
    ok = True
    for j, (i, _) in enumerate(pairs):
        a_, b_ = res[j], res[n + j]
        diff = np.abs(a_ - b_).max(axis=2)
        changed = float((diff > 24).mean()) * 100          # % of pixels that visibly change
        luma = float(b_.mean() - a_.mean())
        flag = changed > 0.5 or abs(luma) > 1.0
        ok &= not flag
        print(f'{sc[i].name:18s} |  {sc[i + 1].name:18s} changed {changed:5.2f} %  brightness {luma:+5.2f}  '
              f'{"<-- pops" if flag else "ok"}')
    return ok


def _label_boxes(job):
    """Render a small frame and return the label/panel boxes in design px."""
    import cairo
    from otter import draw
    idx, t, w, h = job
    draw.LOG = []
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(w / W, h / H)
    scene_for(idx).render(_STAGE, ctx, t)
    k = W / w
    out = [(kind, tuple(v * k for v in box), name) for kind, box, name, _ in draw.LOG]
    draw.LOG = None
    return out


def _overlap(a, b, m=2.0):
    return min(a[2], b[2]) - max(a[0], b[0]) > m and min(a[3], b[3]) - max(a[1], b[1]) > m


def _inside(a, b):
    return a[0] >= b[0] - 1 and a[1] >= b[1] - 1 and a[2] <= b[2] + 1 and a[3] <= b[3] + 1


def _seg_hits(seg, box, m=3.0):
    """Does the segment pass through the box (shrunk by m)?"""
    x0, y0, x1, y1 = seg
    bx0, by0, bx1, by1 = box[0] + m, box[1] + m, box[2] - m, box[3] - m
    if bx1 <= bx0 or by1 <= by0:
        return False
    t0, t1 = 0.0, 1.0
    for p, q in ((-(x1 - x0), x0 - bx0), (x1 - x0, bx1 - x0), (-(y1 - y0), y0 - by0), (y1 - y0, by1 - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        r = q / p
        if p < 0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


def check_labels(sc, step, jobs):
    """Sample every scene and report labels that collide with each other or
    sit (partly) under a panel."""
    jobs_ = [(i, k * step, 480, 270) for i, s_ in enumerate(sc) for k in range(int(s_.length / step) + 1)]
    with pool(jobs) as p:
        res = p.map(_label_boxes, jobs_, chunksize=4)
    hits = {}
    for (i, t, _, _), boxes in zip(jobs_, res):
        for x, (ka, ba, na) in enumerate(boxes):
            for kb, bb, nb in boxes[x + 1:]:
                if (ka, kb) in (('line', 'pill'), ('pill', 'line')):
                    seg, box = (ba, bb) if ka == 'line' else (bb, ba)
                    if na != nb and _seg_hits(seg, box):
                        hits.setdefault((i, f'{ka}:{na}', f'{kb}:{nb}'), []).append(t)
                    continue
                if 'line' in (ka, kb):
                    continue
                if not _overlap(ba, bb):
                    continue
                if ka == 'panel' and kb == 'pill' and _inside(bb, ba):
                    continue          # label drawn on top of its panel
                if 'outline' in (ka, kb):
                    o, q = (ba, bb) if ka == 'outline' else (bb, ba)
                    if 'panel' in (ka, kb) or _inside(q, o) or \
                            any(k == 'panel' and _inside(q, b) for k, b, _ in boxes):
                        continue      # only labels straddling an outline's border
                if ka == 'panel' and kb == 'panel':
                    continue
                hits.setdefault((i, f'{ka}:{na}', f'{kb}:{nb}'), []).append(t)
    for (i, a_, b_), ts in sorted(hits.items(), key=lambda kv: (kv[0][0], kv[1][0])):
        print(f'{sc[i].name}: {a_!r} x {b_!r}  {ts[0]:.1f}-{ts[-1]:.1f} s')
    if not hits:
        print('labels: no collisions')
    return not hits


def cmd_still(a):
    _init()
    w, h = parse_res(a.res)
    idx = find(a.scene)
    for t in a.t:
        data = render_frame((idx, float(t), w, h))
        path = os.path.join(BUILD, 'stills', f'{scenes()[idx].name}_{float(t):06.2f}.png')
        save_png(data, w, h, path)
        print(path)


def cmd_contact(a):
    from PIL import Image
    _init()
    idx = find(a.scene)
    sc = scenes()[idx]
    n = a.n
    cols = 4
    tw, th = 640, 360
    times = [sc.length * (i + 0.5) / n for i in range(n)]
    sheet = Image.new('RGB', (cols * tw, ((n + cols - 1) // cols) * th), (0, 0, 0))
    with pool(min(n, os.cpu_count() or 4)) as p:
        frames = p.map(render_frame, [(idx, t, tw, th) for t in times])
    from PIL import ImageDraw
    for i, (t, data) in enumerate(zip(times, frames)):
        im = Image.frombuffer('RGBA', (tw, th), data, 'raw', 'BGRA', 0, 1).convert('RGB')
        ImageDraw.Draw(im).text((8, 6), f'{sc.name} t={t:.2f}s', fill=(255, 255, 0))
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    path = os.path.join(BUILD, 'stills', f'{sc.name}_contact.png')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.save(path)
    print(path)


ENCODER = os.environ.get('OTTER_ENCODER', 'auto')     # auto | nvenc | x264 (render.py --encoder)
_NVENC = None


def use_nvenc():
    """Encode on the GPU (NVENC) when this machine can, else with x264 on the CPU.
    'auto' probes once with a tiny test encode: ffmpeg may list h264_nvenc
    even where no NVIDIA card or driver is present."""
    global _NVENC
    if ENCODER == 'x264':
        return False
    if _NVENC is None:
        try:
            r = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                                'color=c=black:s=256x256:r=30:d=0.2', '-c:v', 'h264_nvenc', '-f', 'null', '-'],
                               capture_output=True, timeout=30)
            _NVENC = r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            _NVENC = False
        if ENCODER == 'nvenc' and not _NVENC:
            raise SystemExit('--encoder nvenc: no usable NVENC encoder on this machine')
    return _NVENC


NVENC_CQ_OFFSET = int(os.environ.get('OTTER_NVENC_CQ_OFFSET', '3'))   # NVENC CQ = x264 CRF + offset
# GPU encoder sessions per render. Kept low on purpose so the GPU stays usable for other work
# (GeForce caps sessions at 12; 10 parallel 4K sessions ran out of encoder memory under WSL).
# Each session is fed by several drawing processes, so all CPU cores still draw.
NVENC_SESSIONS = int(os.environ.get('OTTER_NVENC_SESSIONS', '4'))


_ANNOUNCED = set()
_USE_GPU = False      # set by encode() for the current render, inherited by its workers


def gpu_for(w, h):
    """NVENC only where it measured faster. Drawing the frames (cairo, CPU) dominates:
    at 1080p x264 beats the session-capped GPU path (50.7 s vs 58.6 s for S10), at 4K
    the GPU wins (6 s of S10: 72 s with x264, 54 s with 4 GPU sessions; higher SSIM/PSNR).
    --encoder nvenc forces the GPU at any size, --encoder x264 never uses it."""
    if ENCODER == 'x264':
        return False
    if ENCODER == 'nvenc':
        return use_nvenc()
    return w * h > 2 * W * H and use_nvenc()


def _ffmpeg(out, w, h, fps, crf, preset, threads):
    if _USE_GPU:
        # BGRA goes to the GPU as is (colour conversion happens on the GPU, not in swscale).
        return subprocess.Popen(
            ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{w}x{h}',
             '-r', str(fps), '-i', '-', '-c:v', 'h264_nvenc', '-preset', 'p7', '-tune', 'hq', '-profile:v', 'high',
             '-rc', 'vbr', '-cq', str(crf + NVENC_CQ_OFFSET), '-b:v', '0', '-bf', '3', '-b_ref_mode', 'middle',
             '-spatial-aq', '1', '-temporal-aq', '1', '-rc-lookahead', '32',
             '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    return subprocess.Popen(
        ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{w}x{h}',
         '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-preset', preset, '-crf', str(crf), '-pix_fmt', 'yuv420p',
         '-threads', str(threads), '-rc-lookahead', '30' if w * h > 2 * W * H else '40',
         '-movflags', '+faststart', out], stdin=subprocess.PIPE)


def _encode_part(job):
    """Render a contiguous run of frames straight into its own ffmpeg."""
    idx, k0, k1, t0, fps, w, h, out, crf, preset, threads, counter = job
    ff = _ffmpeg(out, w, h, fps, crf, preset, threads)
    frames = [(idx, t0 + k / fps, w, h) for k in range(k0, k1)]
    if _USE_GPU and threads > 1:
        # Few GPU sessions: each part keeps `threads` drawing processes busy and
        # feeds their frames, in order, to its one encoder, so all cores still draw.
        # At most 2 frames per drawer in flight: Pool.imap would let the drawers run
        # ahead of a slower encoder and pile up finished 4K frames (33 MB each) in RAM
        # until the machine runs out of memory.
        import multiprocessing as mp
        import itertools
        from collections import deque
        with mp.get_context('fork').Pool(threads) as dp:
            todo = iter(frames)
            # islice, not zip(todo, range(n)): zip pulls one extra frame from `todo` and drops it
            pending = deque(dp.apply_async(render_frame, (fr,)) for fr in itertools.islice(todo, 2 * threads))
            while pending:
                data = pending.popleft().get()
                nxt = next(todo, None)
                if nxt is not None:
                    pending.append(dp.apply_async(render_frame, (nxt,)))
                ff.stdin.write(data)
                with counter.get_lock():
                    counter.value += 1
    else:
        for fr in frames:
            ff.stdin.write(render_frame(fr))
            with counter.get_lock():
                counter.value += 1
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError(f'ffmpeg failed for {out}')
    return out


def encode(idx, out, w, h, fps, jobs, crf, preset, t0=0.0, t1=None):
    """Segment-parallel encode: each worker owns a slice of the scene and an
    ffmpeg process; the slices are joined losslessly with the concat demuxer."""
    import multiprocessing as mp
    sc = scene_for(idx)
    t1 = sc.length if t1 is None else t1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    n = int(round((t1 - t0) * fps))
    parts_dir = os.path.join(os.path.dirname(out), '.parts')
    os.makedirs(parts_dir, exist_ok=True)
    global _USE_GPU
    _USE_GPU = gpu_for(w, h)
    if (w, h, _USE_GPU) not in _ANNOUNCED:
        _ANNOUNCED.add((w, h, _USE_GPU))
        print(f'encoder at {w}x{h}: {"h264_nvenc (GPU)" if _USE_GPU else "libx264 (CPU)"}', flush=True)
    if _USE_GPU:
        nparts = max(1, min(jobs, NVENC_SESSIONS, n // max(1, fps)))   # one GPU session per part
        threads = max(1, jobs // nparts)                               # drawing processes per part
    else:
        if w * h > 2 * W * H:
            jobs = min(jobs, 8)                            # 4K: each x264 + frame buffers needs GBs
        nparts = max(1, min(jobs, n // max(1, fps)))       # at least ~1 s per part
        threads = max(1, (os.cpu_count() or 4) // nparts)  # x264 threads per part
    bounds = [round(i * n / nparts) for i in range(nparts + 1)]
    counter = mp.get_context('fork').Value('i', 0)
    jobs_ = [(idx, bounds[i], bounds[i + 1], t0, fps, w, h,
              os.path.join(parts_dir, f'{sc.name}.{i:03d}.mp4'), crf, preset, threads, counter)
             for i in range(nparts)]
    start = time.time()
    _init()
    scenes()
    ctx = mp.get_context('fork')
    procs = [ctx.Process(target=_encode_part, args=(j,)) for j in jobs_]
    for p in procs:
        p.start()
    while any(p.is_alive() for p in procs):
        time.sleep(0.5)
        el = time.time() - start
        print(f'\r{sc.name}: {counter.value}/{n} frames  {el:5.1f} s  ({counter.value / max(el, 1e-6):.1f} fps)',
              end='', flush=True)
    failed = [j for p, j in zip(procs, jobs_) if p.exitcode]
    if failed and _USE_GPU:
        # A GPU encoder can run out of resources under load (seen under WSL with many
        # 4K sessions): redo just those parts, one at a time, instead of failing the render.
        print(f'\n{sc.name}: {len(failed)} part(s) failed on the GPU; retrying them one at a time', flush=True)
        for j in failed:
            p = ctx.Process(target=_encode_part, args=(j,))
            p.start()
            p.join()
            if p.exitcode:
                raise SystemExit(f'{sc.name}: part {os.path.basename(j[7])} failed again')
    elif failed:
        raise SystemExit(f'\n{sc.name}: a render worker failed')
    lst = os.path.join(parts_dir, f'{sc.name}.txt')
    with open(lst, 'w') as f:
        for j in jobs_:
            f.write(f"file '{os.path.abspath(j[7])}'\n")
    subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                           '-c', 'copy', '-movflags', '+faststart', out])
    for j in jobs_:
        os.remove(j[7])
    os.remove(lst)
    print(f'\n-> {out}')
    return out


def cmd_preview(a):
    idx = find(a.scene)
    sc = scenes()[idx]
    out = os.path.join(BUILD, 'preview', f'{sc.name}.mp4')
    encode(idx, out, 960, 540, 30, a.jobs, 23, 'veryfast', a.start, a.end)


def variant(a, w, h):
    """Output naming: 1080p keeps the plain names; other sizes and clean renders get a suffix."""
    suffix = ('' if (w, h) == (W, H) else f'-{h}p') + ('-clean' if getattr(a, 'clean', False) else '')
    if getattr(a, 'clean', False):
        for sc in scenes():
            sc.show_captions = False
    return BUILD, suffix


def cmd_scene(a):
    idx = find(a.scene)
    w, h = parse_res(a.res)
    root, suffix = variant(a, w, h)
    out = os.path.join(root, 'scenes' + suffix, f'{scenes()[idx].name}.mp4')
    encode(idx, out, w, h, a.fps, a.jobs, a.crf, 'slow')


def cmd_all(a):
    """Every scene, then the cuts: silent (no audio) and voice-over share the
    same frames; a --clean render only makes the voice-over cut."""
    import json
    w, h = parse_res(a.res)
    root, suffix = variant(a, w, h)
    crf = a.crf if (w, h) == (W, H) else max(a.crf, 18)
    outs = []
    for idx, sc in enumerate(scenes()):
        out = os.path.join(root, 'scenes' + suffix, f'{sc.name}.mp4')
        if a.skip_existing and os.path.exists(out):
            print(f'{sc.name}: exists, skipped')
        else:
            encode(idx, out, w, h, a.fps, a.jobs, crf, 'slow')
        outs.append(out)
    lst = os.path.join(root, 'scenes' + suffix, 'concat.txt')
    with open(lst, 'w') as f:
        for o in outs:
            f.write(f"file '{os.path.abspath(o)}'\n")
    finals = []
    if not getattr(a, 'clean', False):
        final = os.path.join(BUILD, f'slot-otter-classic{suffix}.mp4')
        subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                               '-c', 'copy', '-movflags', '+faststart', final])
        finals.append(final)
    man = json.load(open(os.path.join(VO_DIR, 'lines', 'manifest.json')))
    wav = os.path.join(VO_DIR, 'narration.wav')
    mix_narration(man, wav)
    final = os.path.join(BUILD, f'slot-otter-classic-voiceover{suffix}.mp4')
    subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                           '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                           '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k',
                           '-shortest', '-movflags', '+faststart', final])
    finals.append(final)
    for fn in finals:
        print(f'-> {fn}')
    return finals


def find_blender():
    if os.environ.get('BLENDER'):
        return os.environ['BLENDER']
    cands = sorted(glob.glob('/opt/blender-*/blender'), reverse=True)
    return cands[0] if cands else (shutil.which('blender') or 'blender')


def cmd_plate(a):
    blender = find_blender()
    blend = os.path.join(REPO, 'pcb', 'release', 'render', 'slot-otter-discrete.blend')
    script = os.path.join(HERE, 'plate', 'render_plate.py')
    cmd = [blender, '--background', blend, '--python', script, '--', '--pcb', PCB_FILE, '--output', PLATE_PNG,
           '--json', PLATE_JSON, '--ppm', str(a.ppm), '--samples', str(a.samples), '--device', a.device]
    print(' '.join(cmd))
    subprocess.check_call(cmd)


def main():
    global ENCODER
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--encoder', choices=['auto', 'nvenc', 'x264'], default=ENCODER,
                   help='video encoder: auto = NVENC on the GPU when available, else x264 (env OTTER_ENCODER)')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    s = sub.add_parser('check')
    s.add_argument('--step', type=float, default=0.25, help='label-collision sampling step (s)')
    s.add_argument('--jobs', type=int, default=max(1, os.cpu_count() or 4))
    sub.add_parser('voice', help='synthesise the narration and report voice-over timing')
    sub.add_parser('script', help='regenerate the narration blocks in SCRIPT.md')
    sub.add_parser('subtitles', help='SRT/VTT -> build/publish/')
    sub.add_parser('chapters', help='YouTube chapter list -> build/publish/')
    s = sub.add_parser('teaser', help='SPI-ring teaser mp4 + gif -> build/publish/')
    s.add_argument('--jobs', type=int, default=max(1, os.cpu_count() or 4))
    s = sub.add_parser('publish', help='1080p + 4K renders, subtitles, chapters, teaser -> build/publish/')
    s.add_argument('--jobs', type=int, default=max(1, os.cpu_count() or 4))
    s.add_argument('--skip-existing', action='store_true')
    s = sub.add_parser('still')
    s.add_argument('scene')
    s.add_argument('t', nargs='+')
    s.add_argument('--res', default=f'{W}x{H}')
    s = sub.add_parser('contact')
    s.add_argument('scene')
    s.add_argument('--n', type=int, default=12)
    jobs = max(1, os.cpu_count() or 4)
    s = sub.add_parser('preview')
    s.add_argument('scene')
    s.add_argument('--jobs', type=int, default=jobs)
    s.add_argument('--start', type=float, default=0.0)
    s.add_argument('--end', type=float, default=None)
    for name in ('scene', 'all'):
        s = sub.add_parser(name)
        if name == 'scene':
            s.add_argument('scene')
        else:
            s.add_argument('--skip-existing', action='store_true')
        s.add_argument('--clean', action='store_true', help='no burned-in captions (use the subtitle files)')
        s.add_argument('--res', default=f'{W}x{H}')
        s.add_argument('--fps', type=int, default=FPS)
        s.add_argument('--crf', type=int, default=16)
        s.add_argument('--jobs', type=int, default=jobs)
    s = sub.add_parser('plate')
    s.add_argument('--ppm', type=float, default=48, help='plate pixels per board millimetre')
    s.add_argument('--samples', type=int, default=256)
    s.add_argument('--device', default='auto', choices=['auto', 'GPU', 'CPU'])
    a = p.parse_args()
    ENCODER = a.encoder
    {'list': cmd_list, 'check': cmd_check, 'voice': cmd_voice, 'script': cmd_script,
     'subtitles': cmd_subtitles, 'chapters': cmd_chapters, 'teaser': cmd_teaser, 'publish': cmd_publish, 'still': cmd_still, 'contact': cmd_contact, 'preview': cmd_preview, 'scene': cmd_scene,
     'all': cmd_all, 'plate': cmd_plate}[a.cmd](a)


if __name__ == '__main__':
    main()
