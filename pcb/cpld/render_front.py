# SPDX-License-Identifier: GPL-3.0-or-later
"""Render a saved board scene from the SD-slot side in a letterbox frame.

Run with Blender --background scene.blend --python render_front.py --
--output image.png. The saved source scene is not modified.
"""
import argparse
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    scene = bpy.context.scene
    scene.render.resolution_x = 2000
    scene.render.resolution_y = 700
    scene.render.resolution_percentage = 100
    # Face the bracket, slightly elevated to show the socket and board behind it.
    back = Vector((1, 0, .22)).normalized()
    right = Vector((0, 0, 1)).cross(back).normalized()
    up = back.cross(right).normalized()
    points = [obj.matrix_world @ Vector(point)
              for obj in scene.objects if obj.type == 'MESH'
              for point in obj.bound_box]
    xs = [point.dot(right) for point in points]
    ys = [point.dot(up) for point in points]
    target = right * ((min(xs) + max(xs)) / 2) + up * ((min(ys) + max(ys)) / 2)
    data = bpy.data.cameras.new('Letterbox front camera')
    camera = bpy.data.objects.new('Letterbox front camera', data)
    scene.collection.objects.link(camera)
    camera.rotation_euler = Matrix((right, up, back)).transposed().to_euler()
    camera.location = target + back * .3
    data.type = 'ORTHO'
    aspect = scene.render.resolution_x / scene.render.resolution_y
    data.ortho_scale = max(max(xs) - min(xs), (max(ys) - min(ys)) * aspect) * 1.12
    scene.camera = camera
    scene.render.filepath = str(args.output.resolve())
    bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
