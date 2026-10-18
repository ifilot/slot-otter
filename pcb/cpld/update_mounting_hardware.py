# SPDX-License-Identifier: GPL-3.0-or-later
"""Refresh mounting hardware in a saved Forge or Classic Blender scene.

blender --background card.blend --python-exit-code 1 --python pcb/cpld/update_mounting_hardware.py
Only the illustrative fasteners are replaced. The loaded scene is saved in place.
"""
from pathlib import Path
import re
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_blender import add_mounting_screws


def refresh_mounting_hardware():
    bracket = bpy.data.objects.get('Release card bracket')
    heads = sorted((o for o in bpy.context.scene.objects
                    if re.fullmatch(r'H[12] M3 countersunk flat-head Phillips screw', o.name)),
                   key=lambda o: o.name)
    if bracket is None or len(heads) != 2:
        raise RuntimeError('Expected the saved card bracket and both existing screw heads')
    centers = [(o.matrix_world.translation.x, o.matrix_world.translation.y) for o in heads]
    old = [o for o in bpy.context.scene.objects if re.match(r'H[12] M3 ', o.name)]
    for obj in old:
        mesh = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for name in ('Brushed stainless mounting hardware', 'Nylon locking inserts'):
        material = bpy.data.materials.get(name)
        if material and material.users == 0:
            bpy.data.materials.remove(material)
    bpy.context.view_layer.update()
    hardware = add_mounting_screws(bracket, centers)
    bpy.context.scene['mounting_hardware'] = 'M3 x 14 underside heads, 0.5 mm pitch threads, rounded Nyloc top nuts'
    return hardware


if __name__ == '__main__':
    if not bpy.data.filepath:
        raise RuntimeError('Open a saved card scene before running this helper')
    refresh_mounting_hardware()
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
