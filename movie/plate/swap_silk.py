"""Blender 4.5: replace the front silkscreen of a saved board scene with the
mesh extracted by extract_silk.py, aligned board-to-board, keeping the scene's
existing ink material, lights, cameras and hardware.

blender --background scene.blend --python swap_silk.py -- silk.blend
"""
import sys

import bpy
from mathutils import Vector

silk_blend = sys.argv[sys.argv.index('--') + 1]


def bbox(o):
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def area(o):
    lo, hi = bbox(o)
    return (hi[0] - lo[0]) * (hi[1] - lo[1])


meshes = [o for o in bpy.data.objects if o.type == 'MESH']
old = [o for o in meshes if any(s.material and s.material.name.startswith('PCB material (0.9608')
                                for s in o.material_slots)]
assert len(old) == 1, [o.name for o in old]
old = old[0]
ink = old.material_slots[0].material
bodies = [o for o in meshes if 'bracket' not in o.name.lower() and 0.0012 < bbox(o)[1][2] - bbox(o)[0][2] < 0.0020]
body = max(bodies, key=area)
blo, bhi = bbox(body)

with bpy.data.libraries.load(silk_blend, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n.startswith('Front silkscreen')]
new = dst.objects[0]
for coll in old.users_collection:
    coll.objects.link(new)
bpy.context.view_layer.update()      # evaluate the appended object's transform before reading it
nlo, nhi = list(new['board_lo']), list(new['board_hi'])
size_old = (bhi[0] - blo[0], bhi[1] - blo[1])
size_new = (nhi[0] - nlo[0], nhi[1] - nlo[1])
assert all(abs(a - b) < 2e-5 for a, b in zip(size_old, size_new)), (size_old, size_new)
delta = Vector((blo[0] - nlo[0], blo[1] - nlo[1], 0.0))
new.location += delta
new.data.materials.clear()
new.data.materials.append(ink)
olo, ohi = bbox(old)
print('old silk', [round(v * 1000, 3) for v in olo], [round(v * 1000, 3) for v in ohi])
bpy.context.view_layer.update()
nlo2, nhi2 = bbox(new)
print('new silk', [round(v * 1000, 3) for v in nlo2], [round(v * 1000, 3) for v in nhi2])
name = old.name
bpy.data.objects.remove(old, do_unlink=True)
new.name = name
for k in ('board_lo', 'board_hi'):
    del new[k]
bpy.ops.wm.save_mainfile()
import os
if os.path.exists(bpy.data.filepath + '1'):
    os.remove(bpy.data.filepath + '1')     # no .blend1 backup next to the tracked scene
print('saved', bpy.data.filepath)
