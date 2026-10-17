#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Create a render-only board copy with the shared socket and array models."""
import argparse
from pathlib import Path
import re


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--models', help='KiCad-native path to pcb/cpld/components/3d')
    args = parser.parse_args()
    source = Path(__file__).with_name('isa-sdcard.kicad_pcb')
    models = args.models or (source.parent.parent / 'cpld/components/3d').resolve().as_posix()
    models = models.replace('\\', '/')
    text = source.read_text().replace('${KICAD9_3DMODEL_DIR}', '${KICAD10_3DMODEL_DIR}')
    blocks = re.split(r'(?=\n\t\(footprint )', text)
    for index, block in enumerate(blocks):
        if '(property "Reference" "J1"' in block:
            model = f'''\n\t\t(model "{models}/MicroSD_Socket.step"
\t\t\t(offset (xyz 0 0 0))
\t\t\t(scale (xyz 1 1 1))
\t\t\t(rotate (xyz -90 0 0))
\t\t)'''
            block = block.replace('\n\t\t(embedded_fonts no)', model + '\n\t\t(embedded_fonts no)', 1)
        if '"Resistor_SMD:R_Array_Convex_4x0612"' in block:
            block = re.sub(r'\(model "[^"]+"',
                           lambda _: f'(model "{models}/R_Array_Convex_4x0612.wrl"', block)
        blocks[index] = block
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(''.join(blocks))


if __name__ == '__main__':
    main()
