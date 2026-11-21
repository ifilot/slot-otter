#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the Slot-otter drawing sheet: KiCad's default title block with the
logo in a cell at the right of the comment rows (requires Pillow). The title
block keeps its standard 108 mm footprint, so it never covers sheet content.

    python3 tools/make_drawing_sheet.py --base <KiCad>/share/kicad/template/pagelayout_default.kicad_wks \
        --logo logo/slot-otter-logo-v1.png --output pcb/release/slot-otter-classic.kicad_wks
"""
import argparse
import io
from pathlib import Path

from PIL import Image

CELL_X = 20.0        # logo cell: from the right edge (2 mm) to this x, measured from the right
CELL_Y = (18.5, 34.0)  # between the "Sheet" row and the top of the title block
LOGO_MM = 14.0       # rendered logo size in mm
PPI = 300


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--base', required=True, type=Path)
    p.add_argument('--logo', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    base = a.base.read_text(encoding='utf-8').rstrip()
    assert base.endswith(')'), 'unexpected drawing sheet format'
    px = round(LOGO_MM / 25.4 * PPI)
    im = Image.open(a.logo).convert('RGBA')
    im.thumbnail((px, px), Image.LANCZOS)
    # black ink on transparent paper
    alpha = im.split()[3].point(lambda v: v)
    lum = im.convert('L')
    ink = Image.eval(lum, lambda v: 255 - v)
    mask = Image.composite(ink, Image.new('L', im.size, 0), alpha)
    out = Image.new('RGBA', im.size, (0, 0, 0, 0))
    out.putalpha(mask)
    buf = io.BytesIO()
    out.save(buf, 'PNG', dpi=(PPI, PPI), optimize=True)
    data = buf.getvalue()
    hexlines = [' '.join(f'{b:02X}' for b in data[i:i + 32]) for i in range(0, len(data), 32)]
    cx, cy = (2 + CELL_X) / 2, sum(CELL_Y) / 2
    bitmap = (f'    ( line (comment "logo cell") (start {CELL_X:g} {CELL_Y[1]:g}) (end {CELL_X:g} {CELL_Y[0]:g}) )\n'
              f'    ( bitmap (name "Slot-otter logo") (pos {cx:g} {cy:g}) (scale 1)\n'
              '      (pngdata\n' + ''.join(f'        (data "{h}")\n' for h in hexlines) + '      )\n    )\n')
    text = base[:-1].rstrip() + '\n' + bitmap + ')\n'
    a.output.write_text(text, encoding='utf-8')
    print(f'{a.output}: logo {out.size[0]}x{out.size[1]} px at {PPI} ppi ({len(data)} bytes)')


if __name__ == '__main__':
    main()
