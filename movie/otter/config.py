"""Global settings: design resolution, palette, fonts, paths."""
import os

# All screen-space layout is authored in 1920x1080 "design pixels" and
# scaled to the output resolution at render time.
W, H = 1920, 1080
FPS = 60

HERE = os.path.dirname(os.path.abspath(__file__))
MOVIE = os.path.dirname(HERE)
REPO = os.path.dirname(MOVIE)
BUILD = os.path.join(MOVIE, 'build')
PCB_FILE = os.path.join(REPO, 'pcb', 'release', 'isa-sdcard.kicad_pcb')
PLATE_PNG = os.path.join(BUILD, 'plate', 'plate.png')
PLATE_JSON = os.path.join(BUILD, 'plate', 'plate.json')

FONT = 'Inter'
FONT_MONO = 'DejaVu Sans Mono'


def hexrgb(h, a=1.0):
    h = h.lstrip('#')
    return (int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, a)


class C:
    """Palette (RGBA tuples)."""
    bg = hexrgb('#0a0f1a')
    bg2 = hexrgb('#111a2b')
    text = hexrgb('#e8eef6')
    dim_text = hexrgb('#a3b2c4')
    focus = hexrgb('#e8eef6')
    panel = hexrgb('#0d1522', 0.985)
    panel_edge = hexrgb('#2b3d55')

    # x-ray board
    board = hexrgb('#0d1a24')
    board_edge = hexrgb('#3b5a6c')
    pour = hexrgb('#11232f')
    trace_f = hexrgb('#2f5d70')
    trace_b = hexrgb('#1b3644')
    pad = hexrgb('#7a95a2')
    chip = hexrgb('#121a22')
    chip_edge = hexrgb('#4a6274')
    chip_text = hexrgb('#a9bccb')

    # signal families
    addr = hexrgb('#ffb547')
    data = hexrgb('#4fd8ff')
    ctrl = hexrgb('#ff5d8f')
    clock = hexrgb('#a8f05a')
    spi = hexrgb('#b28dff')
    power = hexrgb('#ff7a6b')
    ok = hexrgb('#6ee7a8')
    bad = hexrgb('#ff6b6b')
    white = (1, 1, 1, 1)
