#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regenerate the README comparison-table previews (requires Pillow).

Run from any directory after updating the full-resolution renders in img/.
The README links these transparent, 600-pixel-wide WebP previews to the PNGs.
"""
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RENDERS = (
    'slot-otter-discrete-blender',
    'slot-otter-cpld-rev1-blender',
    'slot-otter-discrete-front',
    'slot-otter-cpld-rev1-front',
    'slot-otter-classic-mad5160',
    'slot-otter-mad5160',
)


def main():
    output = ROOT / 'img' / 'thumbnails'
    output.mkdir(exist_ok=True)
    for name in RENDERS:
        with Image.open(ROOT / 'img' / f'{name}.png') as image:
            image.thumbnail((600, 600), Image.Resampling.LANCZOS)
            image.save(output / f'{name}.webp', quality=82, method=6)


if __name__ == '__main__':
    main()
