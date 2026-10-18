#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Export complete KiCad copper plots as registered Blender soldermask textures.

Requires KiCad 10, rsvg-convert and Pillow. No board geometry is modified.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
from PIL import Image, ImageOps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcb', type=Path, default=Path(__file__).with_name('cpld.kicad_pcb'))
    parser.add_argument('--kicad-cli', default='kicad-cli')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--width', type=int, default=8192)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    windows_cli = args.kicad_cli.lower().endswith('.exe') and os.name != 'nt'

    def native(path):
        if windows_cli:
            return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip()
        return str(path)

    # Use the same Edge.Cuts frame as the populated VRML's soldermask meshes.
    text = args.pcb.read_text()
    edges = [b for b in re.findall(r'\n\t\(gr_(?:line|arc|rect)\n.*?\n\t\)', text, re.S)
             if '(layer "Edge.Cuts")' in b]
    points = [tuple(map(float, p)) for b in edges
              for p in re.findall(r'\((?:start|end|mid) ([\d.-]+) ([\d.-]+)\)', b)]
    left, top = min(p[0] for p in points), min(p[1] for p in points)
    width = max(p[0] for p in points)-left
    height = max(p[1] for p in points)-top
    # Full-page plots retain PCB coordinates: cropping is independent of any
    # layer-specific bounding box or KiCad's fitted-page margins.
    subprocess.run([args.kicad_cli, 'pcb', 'export', 'svg', '--layers', 'F.Cu,B.Cu',
                    '--mode-multi', '--page-size-mode', '1', '--exclude-drawing-sheet',
                    '--black-and-white', '--drill-shape-opt', '2',
                    '--output', native(output), native(args.pcb.resolve())], check=True)
    for layer in ('F_Cu', 'B_Cu'):
        svg = output / f'{args.pcb.stem}-{layer}.svg'
        source = svg.read_text()
        source, count = re.subn(
            r'width="[^\"]+" height="[^\"]+" viewBox="[^\"]+"',
            f'width="{width}mm" height="{height}mm" viewBox="{left} {top} {width} {height}"',
            source, count=1)
        if count != 1:
            raise RuntimeError('Cannot locate KiCad SVG viewport')
        svg.write_text(source)
        png = subprocess.check_output(['rsvg-convert', '--width', str(args.width), str(svg)])
        image = Image.open(io.BytesIO(png)).convert('RGBA')
        # Copper plots are black on transparent; white drill knockouts must
        # remain empty. A white backing makes both cases unambiguous.
        white = Image.new('RGBA', image.size, 'white')
        coverage = ImageOps.invert(Image.alpha_composite(white, image).convert('L'))
        coverage.save(output / f'{layer}.png')
        print(f'{layer}: {coverage.width}x{coverage.height}; full copper plot including filled zones')
    (output/'frame.json').write_text(json.dumps(
        {'left_mm':left,'top_mm':top,'width_mm':width,'height_mm':height}, indent=2)+'\n')


if __name__ == '__main__':
    main()
