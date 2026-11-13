# Slot-otter Classic explainer movie

An animation of about five minutes that follows one byte from the ISA card edge
of Slot-otter Classic to the SD card and one byte back. It comes in two cuts that
share every frame: a **silent cut** with captions (`build/slot-otter-classic.mp4`)
and a **voice-over cut** with a calm narration and subtitles
(`build/voiceover/slot-otter-classic-voiceover.mp4`). Everything is
rendered programmatically from the repository's own design data:

- the **photo plate** is an orthographic Cycles render of
  `pcb/release/render/slot-otter-discrete.blend`;
- the **x-ray board** and every signal path are drawn from
  `pcb/release/isa-sdcard.kicad_pcb` (pulses follow the real copper, pad to pad).

[SCRIPT.md](SCRIPT.md) is the movie script: shots, timing, captions and the
netlist facts behind them. Each `scenes/sNN_*.py` implements section **SNN**.

## Setup

```sh
cd movie
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # pycairo needs libcairo2-dev
```

Also required: `ffmpeg`, the Inter and DejaVu Sans Mono fonts, and for the
plate a Blender 4.5 build with Cycles GPU support.

## Workflow

```sh
.venv/bin/python render.py plate            # once: photo plate (~13 min on an RTX 5090)
.venv/bin/python render.py list             # scenes and durations
.venv/bin/python render.py check            # camera continuity at cuts, caption overlap and reading speed
.venv/bin/python render.py still s04 13 17  # frames at t = 13 s and 17 s -> build/stills/
.venv/bin/python render.py contact s04      # 12-frame contact sheet of one scene
.venv/bin/python render.py preview s04      # 960x540 @ 30 fps for timing checks
.venv/bin/python render.py scene s04        # final 1920x1080 @ 60 fps -> build/scenes/
.venv/bin/python render.py all              # all scenes + build/slot-otter-classic.mp4
```

Voice-over cut:

```sh
.venv/bin/python render.py voice            # synthesise narration, report per-scene stretch
.venv/bin/python render.py still s11 10 --vo   # frames at voice-over time
.venv/bin/python render.py all --vo         # -> build/voiceover/slot-otter-classic-voiceover.mp4
.venv/bin/python render.py script           # regenerate the caption/voice-over blocks in SCRIPT.md
```

`all --skip-existing` re-encodes only scenes without an mp4, so after tuning
one scene delete its file (or run `scene` for it) and then rerun `all`.
Scene ids may be given as `s04`, `4` or the full module name.

Without a plate, photo mode falls back to a solid x-ray rendering, so scene
work can start before Blender has run.

### Voice-over

The narration is in `scenes/narration.py`: per scene, lines of
`(scene time, subtitle, spoken text)`. The subtitle is shown on screen, while the spoken
text spells out numbers and part names for the speech synthesiser ("three-thirty hex",
"seventy-four H-C-T six eighty-eight").

Speech is generated locally with [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)
(Apache-2.0) in a separate environment, because PyTorch has no Python 3.14 wheels:

```sh
uv venv --python 3.12 .venv-tts
VIRTUAL_ENV=.venv-tts uv pip install -r requirements-tts.txt \
    --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cu128
```

The spaCy English model is pinned in `requirements-tts.txt` because Kokoro's text front end
tries to download it with `pip`, and `uv` environments do not include `pip`.

PyTorch 2.7.1 with CUDA 12.8 supports RTX 50-series GPUs. The newest PyTorch wheel crashed
on import under WSL. The voice and pace can be set with `OTTER_VOICE` (default
`af_heart`) and `OTTER_VOICE_SPEED` (default 0.92). Every line is cached, so
`render.py voice` only synthesises lines that changed.

Timing (`otter/voiceover.py`): each line starts at its scene time. Where the
line plus a short pause does not fit before the next line, that stretch of
the scene plays slower. The rate is smoothed so animation and camera never
change speed abruptly, and the scene clock is never sped up. Subtitles follow
the speech. The audio track is loudness-normalised to −16 LUFS and muxed as AAC.

### Blender and the GPU

`render.py plate` uses `$BLENDER` or the newest `/opt/blender-*/blender`
before `blender` on the `PATH`. Distribution packages built `+dfsg`, such as
Ubuntu's `blender 4.0.2+dfsg`, have no CUDA/OptiX kernels and only offer
the CPU to Cycles, even when `nvidia-smi` sees the GPU. Use an official build
from blender.org instead; 4.5 LTS includes Blackwell (`sm_120`) kernels. The
saved scene was written by Blender 4.5.

The plate script leaves the `.blend` file unchanged. It matches the board
mesh's bounding box to the Edge.Cuts bounding box, so the plate's pixels map
linearly to KiCad millimetres, and writes the mapping to `build/plate/plate.json`.
Options: `--ppm` (pixels per mm, default 48), `--samples`, `--device`.

## Tuning a scene

Each scene is a pure function of time, so any frame renders on its own.

- `duration`, `captions` (`(t_in, t_out, text)`) and `cam` (a `CamPath` of
  `(t, view)` keys, where a view is `(centre_x_mm, centre_y_mm, visible_width_mm)`)
  sit at the top of each scene class.
- `draw(f, t)` paints in board space (board, nets, spotlights, tags);
  `overlay(f, t)` paints screen-space panels on 1920×1080 design pixels.
- Timing helpers in `otter/anim.py`: `prog(t, t0, t1)` (eased 0→1),
  `window(t, t0, t1, fade_in, fade_out)` (opacity envelope), `Schedule`
  (variable-speed model clock for slow motion).
- Signals: `sig(f, net, (ref, pad), t, t_start, t_off)` lets a net light up
  outward from a source pad along its copper; `f.comet(path, d, ...)` runs a
  pulse along a `chain_path` of several nets.
- Shared camera positions are defined in `otter/camera.py` (`SHOTS`); consecutive
  scenes start where the previous one ended.

## Layout

```
movie/
  SCRIPT.md            movie script (the source of truth for content)
  render.py            CLI: plate, list, still, contact, preview, scene, all
  plate/render_plate.py  Blender script for the photo plate
  otter/               small rendering engine
    pcb.py             .kicad_pcb reader (outline, footprints, pads, tracks, zones)
    netflow.py         copper graphs: pad-to-pad paths and propagation fronts
    stage.py           photo plate, x-ray board, net glow, spotlight, tags
    widgets.py         captions, bit registers, timing diagrams, tables
    camera.py, anim.py, draw.py, scene.py, config.py
  scenes/              one module per scene, order in scenes/__init__.py
  build/               generated output (git-ignored)
```

## Rendering performance

A frame takes 0.1–0.2 s on one core. `scene` and `all` split each scene into
contiguous slices and fork one worker per core. Each worker pipes its frames
into its own ffmpeg, and the slices are joined with the concat demuxer
without re-encoding. The full movie renders in about 9 minutes on a 20-thread CPU.
Workers are forked explicitly, because Python 3.14's default `forkserver` start method
would reload the photo plate in every worker.

## License

The scripts are GPL-3.0-or-later. The rendered video and the script text are
CC-BY-SA-4.0, like the rest of the documentation. See [LICENSE.md](../LICENSE.md).
