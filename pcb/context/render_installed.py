# SPDX-License-Identifier: GPL-3.0-or-later
"""Combine a saved Slot-otter card with a populated mad5160 GLB in Blender 4.5+.

Run on the Forge or Classic .blend; see README.md for export and render commands.
All geometry uses metres. This is an illustrative assembly, not a fit qualification.
"""
import argparse
import os
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector


def bounds(objects):
    points = [o.matrix_world @ Vector(p) for o in objects for p in o.bound_box]
    return (Vector(tuple(min(p[i] for p in points) for i in range(3))),
            Vector(tuple(max(p[i] for p in points) for i in range(3))))


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def apply_finish(card, motherboard):
    """Brown XT laminate and subdued highlights across the installed assembly.

    Color reference: Mister rf's original IBM XT 5160 motherboard photograph:
    https://commons.wikimedia.org/wiki/File:IBM_XT_5160_motherboard.jpg
    """
    materials = {s.material for o in card + motherboard if o.type == 'MESH'
                 for s in o.material_slots if s.material and s.material.use_nodes}
    for mat in materials:
        shader = mat.node_tree.nodes.get('Principled BSDF')
        if shader is None:
            continue
        metal = shader.inputs['Metallic'].default_value
        shader.inputs['Roughness'].default_value = max(
            shader.inputs['Roughness'].default_value, .5 if metal > .5 else .7)
        shader.inputs['Specular IOR Level'].default_value = .22
        shader.inputs['Coat Weight'].default_value = 0
        for node in mat.node_tree.nodes:
            if node.type == 'MAP_RANGE':
                node.inputs['To Min'].default_value = .78
                node.inputs['To Max'].default_value = .68
    for obj in motherboard:
        if obj.type != 'MESH':
            continue
        if obj.data.name.startswith('render_soldermask'):
            for slot in obj.material_slots:
                mat = slot.material
                shader = mat.node_tree.nodes.get('Principled BSDF')
                shader.inputs['Base Color'].default_value = (.052, .026, .012, 1)
                for node in mat.node_tree.nodes:
                    if node.type == 'MIX_RGB':
                        node.inputs[1].default_value = (.025, .010, .006, 1)
                        node.inputs[2].default_value = (.052, .026, .012, 1)
        elif obj.data.name.startswith('render_PCB'):
            for slot in obj.material_slots:
                shader = slot.material.node_tree.nodes.get('Principled BSDF')
                shader.inputs['Base Color'].default_value = (.19, .095, .035, 1)
                shader.inputs['Alpha'].default_value = 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--motherboard', required=True, type=Path)
    parser.add_argument('--card-model', choices=('Forge', 'Classic'), default='Forge')
    parser.add_argument('--slot', choices=tuple(f'J{i}' for i in range(1, 9)), default='J4')
    parser.add_argument('--copper', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--width', default=2000, type=int)
    parser.add_argument('--samples', default=96, type=int)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.prepare_only and not args.scene:
        parser.error('--prepare-only requires --scene')
    scene = bpy.context.scene
    bpy.context.preferences.filepaths.save_version = 0
    card = [o for o in scene.objects if o.type == 'MESH']
    # Both saved card scenes share the ISA edge frame: PCB (135.5663, 79.1574) mm is
    # scene origin. ISA pad A1 is at PCB (155.302, 116.318) mm, A31 lies
    # 76.2 mm to its left. On mad5160 J1, A1 is (108.4326, 236.8441) mm;
    # connector centreline is 2.54 mm farther down the motherboard.
    # Reverse X, stand card Y upright, face components toward motherboard +Y.
    # Place the finger tips 6.5 mm above the motherboard's coordinate plane.
    # Native mad5160 connector footprint origins; row midpoint is +2.54 mm.
    slot_origins = {'J1': 236.8441, 'J2': 216.5169, 'J3': 196.1896,
                    'J4': 175.8623, 'J5': 155.5351, 'J6': 135.2078,
                    'J7': 114.8806, 'J8': 94.5533}
    slot_y = -(slot_origins[args.slot] + 2.54) * .001
    transform = Matrix(((-1, 0, 0, .1281683),
                        (0, 0, 1, slot_y),
                        (0, 1, 0, .0472166),
                        (0, 0, 0, 1)))
    # The saved copper shaders use scene-position coordinates. Transform
    # those coordinates back to the original flat card frame after posing it.
    for mat in {s.material for o in card for s in o.material_slots if s.material}:
        if not mat.use_nodes:
            continue
        links, nodes = mat.node_tree.links, mat.node_tree.nodes
        position_links = [link for link in links
                          if link.from_node.type == 'NEW_GEOMETRY'
                          and link.from_socket.name == 'Position']
        for link in position_links:
            original_socket, destination = link.from_socket, link.to_socket
            subtract = nodes.new('ShaderNodeVectorMath')
            subtract.operation = 'SUBTRACT'
            subtract.inputs[1].default_value = transform.translation
            rotate = nodes.new('ShaderNodeVectorRotate')
            rotate.rotation_type = 'EULER_XYZ'
            rotate.inputs['Rotation'].default_value = transform.to_3x3().transposed().to_euler()
            links.new(original_socket, subtract.inputs[0])
            links.new(subtract.outputs[0], rotate.inputs['Vector'])
            links.new(rotate.outputs[0], destination)
    card_collection = bpy.data.collections.new(f'Slot-otter {args.card_model} assembly')
    scene.collection.children.link(card_collection)
    for obj in card:
        world = transform @ obj.matrix_world
        obj.parent = None
        obj.matrix_world = world
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        card_collection.objects.link(obj)
    # Remove the original small studio lights and cameras.
    for obj in list(scene.objects):
        if obj.type in {'LIGHT', 'CAMERA'}:
            bpy.data.objects.remove(obj, do_unlink=True)
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.motherboard.resolve()), loglevel=40)
    motherboard = set(bpy.data.objects) - before
    mb_collection = bpy.data.collections.new('mad5160 motherboard')
    scene.collection.children.link(mb_collection)
    for obj in motherboard:
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        mb_collection.objects.link(obj)
    bpy.context.view_layer.update()
    for ref in ('J1', 'J8', 'U1', 'J9'):
        if ref not in bpy.data.objects:
            raise RuntimeError(f'Motherboard export is missing {ref}')
    print('Installed card bounds:', bounds(card))
    print(args.slot, 'connector bounds:', bounds([o for o in bpy.data.objects[args.slot].children_recursive
                                          if o.type == 'MESH']))
    meshes = [o for o in motherboard if o.type == 'MESH']
    # GLB uses the source board's white-mask/black-ink preview colors.
    # Use pale ink; apply_finish supplies the brown PCB and matte surfaces.
    for obj in meshes:
        if obj.data.name.startswith('render_silkscreen'):
            for slot in obj.material_slots:
                shader = slot.material.node_tree.nodes.get('Principled BSDF')
                shader.inputs['Base Color'].default_value = (.82, .79, .65, 1)
                shader.inputs['Roughness'].default_value = .65
    if args.copper:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cpld'))
        from render_blender import copper_material
        masks = [o for o in meshes if o.data.name.startswith('render_soldermask')]
        if len(masks) != 2:
            raise RuntimeError('Expected front and back soldermask meshes')
        mask_low, mask_high = bounds(masks)
        for obj in masks:
            layer = 'F.Cu' if bounds([obj])[1].z > .0008 else 'B.Cu'
            for slot in obj.material_slots:
                mat = slot.material
                mat.node_tree.nodes.get('Principled BSDF').inputs['Alpha'].default_value = 1
                bevel = mat.node_tree.nodes.new('ShaderNodeBevel')
                bevel.inputs['Radius'].default_value = .000025
                copper_material(mat, args.copper, layer, mask_low, mask_high, Vector((0, 0, 0)))
    apply_finish(card, list(motherboard))
    low, high = bounds(meshes + card)
    target = (low + high) / 2
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .03
    scene.render.resolution_x = args.width
    scene.render.resolution_y = round(args.width * .75)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.68, .73, .8, 1)
    background.inputs['Strength'].default_value = .45
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    data = bpy.data.cameras.new('Installed card overview')
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    back = Vector((-.65, 1, 1.35)).normalized()
    camera.location = target + back * .8
    look_at(camera, target)
    data.type = 'ORTHO'
    right = camera.rotation_euler.to_matrix() @ Vector((1, 0, 0))
    up = camera.rotation_euler.to_matrix() @ Vector((0, 1, 0))
    points = [o.matrix_world @ Vector(p) for o in meshes + card for p in o.bound_box]
    xs, ys = [p.dot(right) for p in points], [p.dot(up) for p in points]
    # Frame the projected extents, including the upright bracket.
    camera.location += right * ((min(xs) + max(xs)) / 2 - target.dot(right))
    camera.location += up * ((min(ys) + max(ys)) / 2 - target.dot(up))
    data.ortho_scale = max(max(xs)-min(xs), (max(ys)-min(ys))/ .75) * 1.12
    scene.camera = camera
    for name, offset, energy, size, color in (
            ('Warm softbox', (-.2, .15, .45), 7, .4, (1, .93, .85)),
            ('Cool fill', (.35, .1, .3), 4, .3, (.8, .9, 1)),
            ('Rear rim', (.1, -.4, .3), 5, .25, (1, .97, .9))):
        lamp = bpy.data.lights.new(name, 'AREA')
        lamp.energy, lamp.shape, lamp.size, lamp.color = energy, 'DISK', size, color
        obj = bpy.data.objects.new(name, lamp)
        scene.collection.objects.link(obj)
        obj.location = target + Vector(offset)
        look_at(obj, target)
    scene.unit_settings.system = 'METRIC'
    scene['motherboard_source'] = 'https://github.com/madcatse/mad5160'
    scene['motherboard_revision'] = 'bcaec68e9f62e65e4869585f8ae647f260c2ae55'
    scene['card_model'] = args.card_model
    scene['isa_slot'] = args.slot
    scene['assembly_note'] = f'Illustrative placement in {args.slot}; not a mechanical fit qualification.'
    scene.render.filepath = str(args.output.resolve())
    if args.scene:
        args.scene.parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = '//' + os.path.relpath(args.output.resolve(), args.scene.parent.resolve())
        bpy.ops.wm.save_as_mainfile(filepath=str(args.scene.resolve()), compress=True)
    if not args.prepare_only:
        bpy.ops.render.render(write_still=True)


if __name__ == '__main__':
    main()
