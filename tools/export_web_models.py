# SPDX-License-Identifier: GPL-3.0-or-later
"""Export a saved card scene as a compact, upright GLB using Blender 4.5+.

blender --background card.blend --python-exit-code 1 --python tools/export_web_models.py -- --output card.glb
The source .blend is not modified. Copper coverage becomes a portable UV texture.
"""
import argparse
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    materials = {s.material for o in meshes for s in o.material_slots if s.material}
    for mat in materials:
        if not mat.use_nodes:
            continue
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        shader = nodes.get('Principled BSDF')
        if not shader:
            continue
        for link in list(links):
            if link.to_node == shader and link.to_socket.name in {'Normal', 'Roughness'}:
                links.remove(link)
        shader.inputs['Roughness'].default_value = max(shader.inputs['Roughness'].default_value, .55)
        shader.inputs['Coat Weight'].default_value = 0
        coverage = next((n for n in nodes if n.type == 'TEX_IMAGE' and n.image), None)
        if coverage is None:
            continue
        origin = Vector(next(n for n in nodes if n.type == 'VECT_MATH' and n.operation == 'SUBTRACT').inputs[1].default_value)
        span = Vector(next(n for n in nodes if n.type == 'VECT_MATH' and n.operation == 'DIVIDE').inputs[1].default_value)
        mix = next(n for n in nodes if n.type == 'MIX_RGB')
        image = coverage.image.copy()
        image.scale(1024, round(image.size[1] * 1024 / image.size[0]))
        pixels = np.empty(image.size[0]*image.size[1]*4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        amount = pixels.reshape(-1, 4)[:, :1]
        color = np.array(mix.inputs[1].default_value[:3]) + amount * (
            np.array(mix.inputs[2].default_value[:3]) - np.array(mix.inputs[1].default_value[:3]))
        # Store an sRGB image so glTF reproduces the original linear colors.
        color = np.where(color <= .0031308, color*12.92, 1.055*np.maximum(color, 0)**(1/2.4)-.055)
        rgba = np.ones((len(color), 4), dtype=np.float32)
        rgba[:, :3] = color
        baked = bpy.data.images.new('Web copper ' + mat.name, width=image.size[0], height=image.size[1], alpha=False)
        baked.colorspace_settings.name = 'sRGB'
        baked.pixels.foreach_set(rgba.ravel())
        baked.pack()
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = baked
        links.new(texture.outputs['Color'], shader.inputs['Base Color'])
        for obj in meshes:
            if any(s.material == mat for s in obj.material_slots):
                uv = obj.data.uv_layers.get('Copper UV') or obj.data.uv_layers.new(name='Copper UV')
                coords = []
                for loop in obj.data.loops:
                    point = obj.matrix_world @ obj.data.vertices[loop.vertex_index].co
                    coords.extend(((point.x-origin.x)/span.x, (point.y-origin.y)/span.y))
                uv.data.foreach_set('uv', coords)
                obj.data.uv_layers.active = uv
    bpy.ops.object.select_all(action='DESELECT')
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    # Joining preserves placements/materials while avoiding thousands of DOM-side nodes.
    bpy.ops.object.join()
    card = bpy.context.object
    card.name = 'Slot-otter card and bracket'
    card.matrix_world = Matrix.Rotation(math.pi/2, 4, 'X') @ card.matrix_world
    bpy.context.view_layer.update()
    points = [card.matrix_world @ Vector(p) for p in card.bound_box]
    center = Vector(tuple((min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)))
    card.location -= center
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(args.output.resolve()), export_format='GLB',
                              use_selection=True, export_apply=True, export_cameras=False,
                              export_lights=False, export_yup=True, export_image_format='AUTO',
                              export_draco_mesh_compression_enable=True,
                              export_draco_mesh_compression_level=6,
                              export_draco_position_quantization=14,
                              export_draco_normal_quantization=10,
                              export_draco_texcoord_quantization=12)
    print('Web model:', args.output, args.output.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
