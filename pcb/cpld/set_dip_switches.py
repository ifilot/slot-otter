# SPDX-License-Identifier: GPL-3.0-or-later
"""Pose the documentation scene's DIP switch at the default ISA address 330h."""
import math

import bpy
from mathutils import Matrix, Vector


def bounds(obj):
    points = [obj.matrix_world @ Vector(p) for p in obj.bound_box]
    return (Vector(tuple(min(p[i] for p in points) for i in range(3))),
            Vector(tuple(max(p[i] for p in points) for i in range(3))))


def set_default_address():
    scene = bpy.context.scene
    if scene.get('DIP switch address') == '330h':
        return
    red_name = 'PCB material (0.137, 0.402, 0.727)'
    cream_name = 'PCB material (0.895, 0.891, 0.813)'
    red = [o for o in scene.objects if o.type == 'MESH'
           and any(s.material and s.material.name == red_name for s in o.material_slots)]
    if not red:
        raise RuntimeError('Cannot identify the DIP switch housing')
    extents = [bounds(o) for o in red]
    low = Vector(tuple(min(b[0][i] for b in extents) for i in range(3)))
    high = Vector(tuple(max(b[1][i] for b in extents) for i in range(3)))
    # KiCad exports the cream actuators and red recess surfaces as individual
    # faces. Rotate each complete channel to reverse its slide position while
    # retaining the original surfaces, including the exposed recess beneath it.
    channels = []
    for obj in scene.objects:
        if obj.type != 'MESH' or not any(
                s.material and s.material.name in (red_name, cream_name)
                for s in obj.material_slots):
            continue
        a, b = bounds(obj)
        if (a.x >= low.x - 1e-6 and b.x <= high.x + 1e-6
                and a.y >= low.y - 1e-6 and b.y <= high.y + 1e-6
                and a.z >= high.z - .00035 and b.x - a.x < .0015):
            channels.append((obj, a, b))
    cream = [(o, a, b) for o, a, b in channels
             if any(s.material and s.material.name == cream_name for s in o.material_slots)]
    first = (low.x + high.x - 7 * .00254) / 2
    def channel(a, b):
        return round(((a.x + b.x) / 2 - first) / .00254)
    if {channel(a, b) for o, a, b in cream} != set(range(8)):
        raise RuntimeError('Expected eight DIP actuators at 2.54 mm pitch')
    for number in range(1, 9):
        group = [(o, a, b) for o, a, b in channels
                 if channel(a, b) == number - 1]
        x = (min(a.x for o, a, b in group) + max(b.x for o, a, b in group)) / 2
        y = (min(a.y for o, a, b in group) + max(b.y for o, a, b in group)) / 2
        if number in (1, 2, 5, 6):
            pivot = Vector((x, y, 0))
            transform = (Matrix.Translation(pivot) @ Matrix.Rotation(math.pi, 4, 'Z')
                         @ Matrix.Translation(-pivot))
            for obj, a, b in group:
                obj.matrix_world = transform @ obj.matrix_world
        print(f'DIP switch {number}: {"ON" if number in (1, 2, 5, 6) else "OFF"}')
    scene['DIP switch address'] = '330h'
    bpy.context.view_layer.update()


if __name__ == '__main__':
    set_default_address()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
