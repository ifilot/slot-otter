"""Blender 4.0 (bundled X3D/VRML importer): import a KiCad VRML export and keep
only the front silkscreen mesh, oriented like render_blender.py does. Stores
the board body's bounding box on the object so the target scene can align it.

blender --background --factory-startup --python extract_silk.py -- in.wrl out.blend
"""
import math
import sys

import bpy
from mathutils import Matrix, Vector

src, dst = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.preferences.addon_enable(module='io_scene_x3d')
bpy.ops.import_scene.x3d(filepath=src)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
orient = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X')
mw = {o: orient @ o.matrix_world.copy() for o in meshes}
for o in meshes:
    o.parent = None
    o.matrix_world = mw[o]
bpy.context.view_layer.update()


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def is_ink(o):
    return any(s.material and all(abs(c - 0.9608) < 0.002 for c in s.material.diffuse_color[:3])
               for s in o.material_slots)


silk = [o for o in meshes if is_ink(o)]
assert silk, 'no silkscreen mesh found'
silk.sort(key=lambda o: -(bbox(o)[1][0] - bbox(o)[0][0]) * (bbox(o)[1][1] - bbox(o)[0][1]))
front = [o for o in silk if bbox(o)[0][2] > 0][0]
# board body: largest-area mesh that is about 1.6 mm thick
bodies = [o for o in meshes if 0.0012 < bbox(o)[1][2] - bbox(o)[0][2] < 0.0020]
body = max(bodies, key=lambda o: (bbox(o)[1][0] - bbox(o)[0][0]) * (bbox(o)[1][1] - bbox(o)[0][1]))
(lo, hi) = bbox(body)
front['board_lo'] = lo
front['board_hi'] = hi
front.name = 'Front silkscreen (KiCad VRML)'
for o in meshes:
    if o is not front:
        bpy.data.objects.remove(o, do_unlink=True)
print('silk', front.name, len(front.data.vertices), 'board', [round(v, 5) for v in lo], [round(v, 5) for v in hi])
bpy.ops.wm.save_as_mainfile(filepath=dst)
