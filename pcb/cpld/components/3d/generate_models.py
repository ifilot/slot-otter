#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate editable, simplified VRML package models for the CPLD PCB.

Dimensions in mm follow the PCB's fabrication outlines and pad positions.
These are visualization models, not manufacturer mechanical CAD.
KiCad's VRML convention uses 2.54 mm per coordinate unit.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BLACK = (0.055, 0.055, 0.06)
CHIP = (0.12, 0.12, 0.13)
METAL = (0.65, 0.67, 0.70)


def box(center, size, color):
    xyz = ' '.join(f'{v / 2.54:.6f}' for v in center)
    dimensions = ' '.join(f'{v / 2.54:.6f}' for v in size)
    rgb = ' '.join(map(str, color))
    return (f'Transform {{ translation {xyz} children [ Shape {{ appearance '
            f'Appearance {{ material Material {{ diffuseColor {rgb} '
            f'specularColor 0.25 0.25 0.25 shininess 0.25 }} }} '
            f'geometry Box {{ size {dimensions} }} }} ] }}\n')


def save(name, shapes):
    (ROOT / name).write_text('#VRML V2.0 utf8\n'
                            '# SPDX-License-Identifier: CERN-OHL-S-2.0\n'
                            '# Simplified visualization model; dimensions in 0.1 inch.\n'
                            + ''.join(shapes))


def main():
    # PLCC44 socket outline: x [-13.02, 10.48], y [-5.4, 18.1].
    # VRML Y is opposite to footprint Y. Package center is (-1.27, -6.35).
    cx, cy = -1.27, -6.35
    socket = [box((cx, cy, 0.8), (23.5, 23.5, 1.6), BLACK)]
    for dx, dy, sx, sy in [(-10.5, 0, 2.5, 23.5), (10.5, 0, 2.5, 23.5),
                           (0, -10.5, 18.5, 2.5), (0, 10.5, 18.5, 2.5)]:
        socket.append(box((cx + dx, cy + dy, 4.0), (sx, sy, 4.8), BLACK))
    socket.append(box((cx, cy, 4.8), (16.6, 16.6, 3.0), CHIP))
    for i in range(11):
        pitch = (i - 5) * 1.27
        for x, y, sx, sy in [(pitch, -8.65, 0.55, 0.7), (pitch, 8.65, 0.55, 0.7),
                              (-8.65, pitch, 0.7, 0.55), (8.65, pitch, 0.7, 0.55)]:
            socket.append(box((cx + x, cy + y, 4.9), (sx, sy, 1.2), METAL))
    socket.append(box((cx - 6.5, cy + 6.5, 6.32), (0.8, 0.8, 0.03), (0.75, 0.75, 0.75)))
    save('PLCC44_socket_populated.wrl', socket)

    # The two arrays share the same 1.6 x 3.2 mm F.Fab body outline.
    resistor = [box((0, 0, 0.3), (1.6, 3.2, 0.6), BLACK)]
    for y in [-1.27, -0.4, 0.4, 1.27]:
        for x in [-0.7, 0.7]:
            resistor.append(box((x, y, 0.30), (0.3, 0.42, 0.62), METAL))
    save('R_Array_Convex_4x0612.wrl', resistor)


if __name__ == '__main__':
    main()
