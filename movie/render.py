#!/usr/bin/env python3
"""Render the Slot-otter Classic explainer.

    python render.py list
    python render.py check                               # camera continuity, caption timing
    python render.py voice                               # synthesise narration (Kokoro), report timing
    python render.py all --vo                            # voice-over cut -> build/voiceover/
    python render.py plate [--ppm 48] [--samples 256]     # photoreal plate via Blender
    python render.py still s04 4.5 [--res 1920x1080]     # one frame -> build/stills/
    python render.py contact s04 [--n 12]                # contact sheet across a scene
    python render.py preview s04                         # 960x540 @ 30 fps, fast
    python render.py scene s04                           # final quality, one scene
    python render.py all                                 # every scene + concatenated movie

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


def scenes():
    global _SCENES
    if _SCENES is None:
        pkg = importlib.import_module('scenes')
        _SCENES = [importlib.import_module(f'scenes.{m}').SCENE for m in pkg.ORDER]
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


def render_frame(job):
    import cairo
    idx, t, w, h = job
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.scale(w / W, h / H)
    scenes()[idx].render(_STAGE, ctx, t)
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
    for sc in scenes():
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
    for sc in scenes():
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
    for sc in scenes():
        tot_s += sc.duration
        tot_v += sc.length
        slow = max(sc.vo.rates) if sc.vo.rates else 1.0
        print(f'{sc.name:18s} {sc.duration:6.1f} s -> {sc.length:6.1f} s   max slow-down x{slow:.2f}')
    print(f'total {tot_s:.1f} s -> {tot_v:.1f} s ({int(tot_v // 60)}:{tot_v % 60:04.1f})')


def cmd_script(a):
    """Regenerate the Captions / Voice-over blocks in SCRIPT.md from the code."""
    import re
    from scenes.narration import NARRATION
    path = os.path.join(HERE, 'SCRIPT.md')
    doc = open(path, encoding='utf-8').read()
    for sc in scenes():
        lines = [f'**Captions** ({sc.duration:g} s silent cut)']
        lines += [f'- {t0:.1f}–{t1:.1f} — *{txt}*' for t0, t1, txt in sc.captions] or ['- none']
        nar = NARRATION.get(sc.name, [])
        lines += ['', '**Voice-over** (scene time → spoken)']
        lines += [f'- {t:.1f} — "{spoken}"' for t, _sub, spoken in nar] or ['- none']
        block = '\n'.join(lines)
        doc, n = re.subn(rf'<!-- captions:{sc.name} -->.*?<!-- /captions -->',
                         f'<!-- captions:{sc.name} -->\n{block}\n<!-- /captions -->', doc, flags=re.S)
        if not n:
            print(f'warning: no marker for {sc.name} in SCRIPT.md')
    total = sum(sc.duration for sc in scenes())
    doc = re.sub(r'\*\*Silent cut\*\*: captions only, about [^.]*\.',
                 f'**Silent cut**: captions only, {int(total // 60)} min {total % 60:.0f} s.', doc)
    open(path, 'w', encoding='utf-8').write(doc)
    print(f'updated {path}')


def cmd_list(a):
    total = 0
    for i, s in enumerate(scenes()):
        print(f'{i + 1:2d}  {s.name:22s} {s.duration:6.1f} s   {s.title}')
        total += s.duration
    print(f'    total {total:.1f} s = {int(total // 60)}:{total % 60:04.1f}')


def cmd_check(a):
    """Camera continuity across scene cuts and caption overlap within scenes."""
    ok = True
    sc = scenes()
    for x, y in zip(sc, sc[1:]):
        v0, v1 = x.view(x.duration), y.view(0.0)
        d = max(abs(v0.cx - v1.cx), abs(v0.cy - v1.cy)) * W / v1.w
        dz = abs(v0.w / v1.w - 1)
        flag = d > 0.5 or dz > 0.001
        ok &= not flag
        print(f'{x.name:18s} -> {y.name:18s} jump {d:5.2f} px  zoom {dz * 100:5.2f} %  {"<-- check" if flag else "ok"}')
    for s_ in sc:
        cs = sorted(s_.captions)
        for (a0, a1, _), (b0, b1, _) in zip(cs, cs[1:]):
            if b0 < a1:
                ok = False
                print(f'{s_.name}: captions overlap at {b0:.1f} s')
        for c0, c1, txt in cs:
            words = len(txt.split())
            if c1 - c0 < words / 3.2:
                print(f'{s_.name}: caption at {c0:.1f} s is short for {words} words ({c1 - c0:.1f} s)')
    print('all good' if ok else 'issues found')


def cmd_still(a):
    if a.vo:
        setup_vo()
    _init()
    w, h = parse_res(a.res)
    idx = find(a.scene)
    for t in a.t:
        data = render_frame((idx, float(t), w, h))
        path = os.path.join(BUILD, 'stills', f'{scenes()[idx].name}{"_vo" if a.vo else ""}_{float(t):06.2f}.png')
        save_png(data, w, h, path)
        print(path)


def cmd_contact(a):
    from PIL import Image
    if a.vo:
        setup_vo()
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


def _ffmpeg(out, w, h, fps, crf, preset, threads):
    return subprocess.Popen(
        ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'bgra', '-s', f'{w}x{h}',
         '-r', str(fps), '-i', '-', '-c:v', 'libx264', '-preset', preset, '-crf', str(crf), '-pix_fmt', 'yuv420p',
         '-threads', str(threads), '-movflags', '+faststart', out], stdin=subprocess.PIPE)


def _encode_part(job):
    """Render a contiguous run of frames straight into its own ffmpeg."""
    idx, k0, k1, t0, fps, w, h, out, crf, preset, threads, counter = job
    ff = _ffmpeg(out, w, h, fps, crf, preset, threads)
    for k in range(k0, k1):
        ff.stdin.write(render_frame((idx, t0 + k / fps, w, h)))
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
    sc = scenes()[idx]
    t1 = sc.length if t1 is None else t1
    n = int(round((t1 - t0) * fps))
    parts_dir = os.path.join(os.path.dirname(out), '.parts')
    os.makedirs(parts_dir, exist_ok=True)
    nparts = max(1, min(jobs, n // max(1, fps)))           # at least ~1 s per part
    bounds = [round(i * n / nparts) for i in range(nparts + 1)]
    counter = mp.get_context('fork').Value('i', 0)
    threads = max(1, (os.cpu_count() or 4) // nparts)
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
    if any(p.exitcode for p in procs):
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
    if a.vo:
        setup_vo()
    idx = find(a.scene)
    sc = scenes()[idx]
    out = os.path.join(BUILD, 'preview', f'{sc.name}{"_vo" if a.vo else ""}.mp4')
    encode(idx, out, 960, 540, 30, a.jobs, 23, 'veryfast', a.start, a.end)


def cmd_scene(a):
    if a.vo:
        setup_vo()
    idx = find(a.scene)
    w, h = parse_res(a.res)
    out = os.path.join(VO_DIR if a.vo else BUILD, 'scenes', f'{scenes()[idx].name}.mp4')
    encode(idx, out, w, h, a.fps, a.jobs, a.crf, 'slow')


def cmd_all(a):
    w, h = parse_res(a.res)
    man = setup_vo() if a.vo else None
    root = VO_DIR if a.vo else BUILD
    outs = []
    for idx, sc in enumerate(scenes()):
        out = os.path.join(root, 'scenes', f'{sc.name}.mp4')
        if a.skip_existing and os.path.exists(out):
            print(f'{sc.name}: exists, skipped')
        else:
            encode(idx, out, w, h, a.fps, a.jobs, a.crf, 'slow')
        outs.append(out)
    lst = os.path.join(root, 'scenes', 'concat.txt')
    with open(lst, 'w') as f:
        for o in outs:
            f.write(f"file '{os.path.abspath(o)}'\n")
    if not a.vo:
        final = os.path.join(BUILD, 'slot-otter-classic.mp4')
        subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                               '-c', 'copy', '-movflags', '+faststart', final])
    else:
        wav = os.path.join(VO_DIR, 'narration.wav')
        mix_narration(man, wav)
        final = os.path.join(VO_DIR, 'slot-otter-classic-voiceover.mp4')
        subprocess.check_call(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst,
                               '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                               '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k',
                               '-shortest', '-movflags', '+faststart', final])
    print(f'-> {final}')


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
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('list')
    sub.add_parser('check')
    sub.add_parser('voice', help='synthesise the narration and report voice-over timing')
    sub.add_parser('script', help='regenerate caption/voice-over blocks in SCRIPT.md')
    s = sub.add_parser('still')
    s.add_argument('scene')
    s.add_argument('t', nargs='+')
    s.add_argument('--vo', action='store_true', help='voice-over timing (t is output time)')
    s.add_argument('--res', default=f'{W}x{H}')
    s = sub.add_parser('contact')
    s.add_argument('scene')
    s.add_argument('--vo', action='store_true')
    s.add_argument('--n', type=int, default=12)
    jobs = max(1, os.cpu_count() or 4)
    s = sub.add_parser('preview')
    s.add_argument('scene')
    s.add_argument('--vo', action='store_true')
    s.add_argument('--jobs', type=int, default=jobs)
    s.add_argument('--start', type=float, default=0.0)
    s.add_argument('--end', type=float, default=None)
    for name in ('scene', 'all'):
        s = sub.add_parser(name)
        if name == 'scene':
            s.add_argument('scene')
        else:
            s.add_argument('--skip-existing', action='store_true')
        s.add_argument('--vo', action='store_true', help='voice-over cut -> build/voiceover/')
        s.add_argument('--res', default=f'{W}x{H}')
        s.add_argument('--fps', type=int, default=FPS)
        s.add_argument('--crf', type=int, default=16)
        s.add_argument('--jobs', type=int, default=jobs)
    s = sub.add_parser('plate')
    s.add_argument('--ppm', type=float, default=48, help='plate pixels per board millimetre')
    s.add_argument('--samples', type=int, default=256)
    s.add_argument('--device', default='auto', choices=['auto', 'GPU', 'CPU'])
    a = p.parse_args()
    {'list': cmd_list, 'check': cmd_check, 'voice': cmd_voice, 'script': cmd_script, 'still': cmd_still, 'contact': cmd_contact, 'preview': cmd_preview, 'scene': cmd_scene,
     'all': cmd_all, 'plate': cmd_plate}[a.cmd](a)


if __name__ == '__main__':
    main()
