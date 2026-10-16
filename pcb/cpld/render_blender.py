# SPDX-License-Identifier: GPL-3.0-or-later
"""Render KiCad's populated VRML export in Blender 4 with studio lighting.

Run with Blender, not regular Python. Geometry and markings come from KiCad.
The bracket is aligned to the PCB mounting holes without changing its mesh.
Lighting, camera, background and surface shading are set up here.
"""
import argparse
import math
import os
import re
from pathlib import Path
import sys
import bpy
import bmesh
import json
from mathutils import Matrix, Vector


def look_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def bounds(objects):
    points = [o.matrix_world @ Vector(p) for o in objects for p in o.bound_box]
    return (Vector(tuple(min(p[i] for p in points) for i in range(3))),
            Vector(tuple(max(p[i] for p in points) for i in range(3))))


def add_socket_camera(scene, assembly):
    """Frame the assembly from outside the bracket, with the socket visible."""
    data = bpy.data.cameras.new('SD socket rear camera')
    camera = bpy.data.objects.new('SD socket rear camera', data)
    scene.collection.objects.link(camera)
    back = Vector((.24, .10, .14)).normalized()
    right = Vector((0, 0, 1)).cross(back).normalized()
    up = back.cross(right).normalized()
    camera.rotation_euler = Matrix((right, up, back)).transposed().to_euler()
    points = [o.matrix_world @ Vector(p) for o in assembly for p in o.bound_box]
    xs, ys = [p.dot(right) for p in points], [p.dot(up) for p in points]
    target = right * ((min(xs)+max(xs))*.5) + up * ((min(ys)+max(ys))*.5)
    camera.location = target + back * .3
    data.type = 'ORTHO'
    aspect = scene.render.resolution_x / scene.render.resolution_y
    data.ortho_scale = max(max(xs)-min(xs), (max(ys)-min(ys))*aspect) * 1.15
    return camera


def add_mounting_screws(bracket, holes):
    """Illustrative silver M3 countersunk flat-head screws at the PCB holes."""
    material = bpy.data.materials.new('Brushed stainless mounting hardware')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.57, .60, .64, 1)
    shader.inputs['Metallic'].default_value = .95
    shader.inputs['Roughness'].default_value = .24
    hardware = []

    def revolved(name, profile, origin):
        vertices, faces = [], []
        sides = 96
        for radius, height in profile:
            for i in range(sides):
                angle = 2 * math.pi * i / sides
                vertices.append((radius * math.cos(angle), radius * math.sin(angle), height))
        for ring in range(len(profile)):
            next_ring = (ring + 1) % len(profile)
            for i in range(sides):
                j = (i + 1) % sides
                faces.append((ring*sides+i, ring*sides+j, next_ring*sides+j, next_ring*sides+i))
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        welded = bmesh.new()
        welded.from_mesh(mesh)
        bmesh.ops.remove_doubles(welded, verts=list(welded.verts), dist=1e-9)
        bmesh.ops.recalc_face_normals(welded, faces=list(welded.faces))
        welded.to_mesh(mesh)
        welded.free()
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = origin
        mesh.materials.append(material)
        for face in mesh.polygons:
            face.use_smooth = abs(face.normal.z) < .999
        hardware.append(obj)
        return obj

    inverse = bracket.matrix_world.inverted()
    direction = (inverse.to_3x3() @ Vector((0, 0, -1))).normalized()
    for number, (x, y) in enumerate(holes, 1):
        # Probe the flat ear surface outside its tapered screw seat. The
        # lowest hit avoids the taller bracket wall beside the mounting ear.
        heights = []
        for i in range(16):
            angle = i * math.tau / 16
            origin = Vector((x+.0036*math.cos(angle), y+.0036*math.sin(angle), .03))
            hit, point, normal, index = bracket.ray_cast(inverse @ origin, direction)
            if hit:
                heights.append((bracket.matrix_world @ point).z)
        if not heights:
            raise RuntimeError('Cannot locate bracket ear for mounting screw')
        head_top = min(heights) + .00001
        head = revolved(f'H{number} M3 countersunk flat-head Phillips screw',
                        [(0,-.0019),(.00145,-.0019),(.00315,-.0002),
                         (.00315,0),(0,0)], (x,y,head_top))
        # Cut an actual cross recess so it catches highlights and shadows.
        for angle in (math.radians(15 + number*17), math.radians(105 + number*17)):
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x,y,head_top-.0003))
            cutter = bpy.context.object
            cutter.dimensions = (.0035,.00065,.0012)
            cutter.rotation_euler.z = angle
            bpy.context.view_layer.objects.active = cutter
            bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
            modifier = head.modifiers.new('Phillips drive recess', 'BOOLEAN')
            modifier.operation = 'DIFFERENCE'
            modifier.object = cutter
            bpy.context.view_layer.objects.active = head
            bpy.ops.object.modifier_apply(modifier=modifier.name)
            bpy.data.objects.remove(cutter,do_unlink=True)
        bevel = head.modifiers.new('Soft machined edges','BEVEL')
        bevel.width, bevel.segments = .000035, 3
        revolved(f'H{number} M3 screw shank',
                 [(0,-.006),(.00145,-.006),(.00145,-.0018),(0,-.0018)], (x,y,head_top))
        print('Flush screw top (metres):',number,x,y,head_top)
    return hardware


def add_bracket(meshes, pcb, stl):
    """Align the older bracket's original mounting slots with H1/H2.

    STL millimetres: hole centres (Y=-7.22, Z=36.2/-28.3), PCB slot
    X=-7.15..-5.45 (centre -6.30). No bracket geometry is deformed.
    """
    text = pcb.read_text()
    holes = []
    for block in re.split(r'\n\t\(footprint ', text)[1:]:
        if re.search(r'\(property "Reference" "H[12]"', block):
            x, y = re.search(r'\(at ([\d.-]+) ([\d.-]+)', block).groups()
            holes.append((float(x), float(y)))
    if len(holes) != 2:
        raise RuntimeError('Expected H1 and H2 bracket mounting holes')
    edges = [block for block in re.findall(r'\n\t\(gr_(?:line|arc)\n.*?\n\t\)', text, re.S)
             if '(layer "Edge.Cuts")' in block]
    edge_points = [tuple(map(float, p)) for block in edges
                   for p in re.findall(r'\((?:start|end|mid) ([\d.-]+) ([\d.-]+)\)', block)]
    board_left = min(p[0] for p in edge_points)
    board_top = min(p[1] for p in edge_points)
    # Front/back solder-mask meshes share the PCB outline's X/Y frame.
    bodies = [o for o in meshes if any(slot.material and
              all(abs(c - expected) < 0.001 for c, expected in
                  zip(slot.material.diffuse_color[:3], (0.07843137, 0.2, 0.14117647)))
              for slot in o.material_slots)]
    if not bodies:
        raise RuntimeError('Cannot locate the KiCad board body for bracket alignment')
    body_low, body_high = bounds(bodies)
    print('Board mask bounds:', body_low[:], body_high[:])
    x_offset = body_low.x - board_left * 0.001
    y_offset = body_high.y + board_top * 0.001
    target = Vector((sum(h[0] for h in holes) * 0.0005 + x_offset,
                     -sum(h[1] for h in holes) * 0.0005 + y_offset, 0))
    bpy.ops.preferences.addon_enable(module='io_mesh_stl')
    bpy.ops.import_mesh.stl(filepath=str(stl.resolve()))
    bracket = bpy.context.object
    bracket.name = 'Release card bracket'
    # Local X -> board Z, Y -> board X, Z -> board Y; STL mm -> metres.
    bracket.matrix_world = Matrix(((0, .001, 0, target.x + .00722),
                                   (0, 0, .001, target.y - .00395),
                                   (.001, 0, 0, .00630), (0, 0, 0, 1)))
    material = bpy.data.materials.new('Cream printed bracket')
    material.use_nodes = True
    shader = material.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Base Color'].default_value = (.64, .57, .37, 1)
    shader.inputs['Roughness'].default_value = .55
    bracket.data.materials.clear()
    bracket.data.materials.append(material)
    # Report alignment error rather than silently scaling the mesh to fit.
    spacing = abs(holes[0][1] - holes[1][1])
    print('Bracket/PCB mounting pitch difference (mm):', abs(spacing - 64.5))
    bpy.context.view_layer.update()
    screw_centres = [(x*.001+x_offset,-y*.001+y_offset) for x,y in holes]
    return bracket, add_mounting_screws(bracket, screw_centres)


def copper_material(mat, directory, layer, low, high, center):
    """Shade the complete native copper plot through the existing mask mesh.

    The packed texture includes filled zones, clearances, thermal spokes,
    pads, vias and routing. Pad openings remain defined by the VRML mask.
    """
    frame = json.loads((directory / 'frame.json').read_text())
    width, height = high.x-low.x, high.y-low.y
    if abs(width-frame['width_mm']*.001) > .000001 or abs(height-frame['height_mm']*.001) > .000001:
        raise RuntimeError('Copper texture frame does not match the VRML board dimensions')
    image = bpy.data.images.load(str((directory / (layer.replace('.','_')+'.png')).resolve()), check_existing=False)
    image.name = 'Complete covered copper '+layer
    image.colorspace_settings.name = 'Non-Color'
    image.pack()
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    geometry = nodes.new('ShaderNodeNewGeometry')
    offset = nodes.new('ShaderNodeVectorMath'); offset.operation = 'SUBTRACT'
    offset.inputs[1].default_value = (low.x-center.x,low.y-center.y,0)
    scale = nodes.new('ShaderNodeVectorMath'); scale.operation = 'DIVIDE'
    scale.inputs[1].default_value = (width,height,1)
    texture = nodes.new('ShaderNodeTexImage'); texture.image = image
    texture.extension = 'CLIP'
    mix = nodes.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value = (.012,.045,.018,1)
    mix.inputs[2].default_value = (.025,.105,.046,1)
    shader = nodes.get('Principled BSDF')
    links.new(geometry.outputs['Position'],offset.inputs[0])
    links.new(offset.outputs[0],scale.inputs[0])
    links.new(scale.outputs[0],texture.inputs['Vector'])
    links.new(texture.outputs['Color'],mix.inputs[0])
    links.new(mix.outputs[0],shader.inputs['Base Color'])
    # A slight height/roughness change shows mask conforming to copper.
    # Keep it as shading: the board and its copper geometry remain untouched.
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = .25
    bump.inputs['Distance'].default_value = .000025
    links.new(texture.outputs['Color'],bump.inputs['Height'])
    bevel = next(n for n in nodes if n.type == 'BEVEL')
    links.new(bevel.outputs['Normal'],bump.inputs['Normal'])
    links.new(bump.outputs['Normal'],shader.inputs['Normal'])
    roughness = nodes.new('ShaderNodeMapRange')
    roughness.inputs['To Min'].default_value = .44
    roughness.inputs['To Max'].default_value = .32
    links.new(texture.outputs['Color'],roughness.inputs['Value'])
    links.new(roughness.outputs['Result'],shader.inputs['Roughness'])
    print('Packed complete copper plot:',layer,image.size[:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--scene', type=Path)
    parser.add_argument('--copper', required=True, type=Path, help='Directory generated by render_copper.py')
    parser.add_argument('--pcb', type=Path, default=Path(__file__).with_name('cpld.kicad_pcb'))
    parser.add_argument('--bracket', type=Path, default=Path(__file__).resolve().parents[2] / 'bracket/bracket-release-card.stl')
    parser.add_argument('--no-bracket', action='store_true')
    parser.add_argument('--width', type=int, default=1800)
    parser.add_argument('--samples', type=int, default=96)
    parser.add_argument('--prepare-only', action='store_true', help='Save the scene without rendering')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:])
    if args.prepare_only and not args.scene:
        parser.error('--prepare-only requires --scene')
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    bpy.ops.preferences.addon_enable(module='io_scene_x3d')
    bpy.ops.import_scene.x3d(filepath=str(args.input.resolve()))
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    # Blender's X3D importer maps the export to X/Z with Y upward. Restore
    # PCB X/Y orientation so lettering reads upright, with the ISA edge below.
    orient = Matrix.Rotation(math.pi, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X')
    transforms = {o: orient @ o.matrix_world.copy() for o in meshes}
    # Detach importer transform hierarchies while preserving world geometry.
    for o in meshes:
        o.parent = None
        o.matrix_world = transforms[o]
    bpy.context.view_layer.update()
    mask_meshes = [o for o in meshes if any(slot.material and
                   abs(slot.material.diffuse_color[1]-.2)<.0001 and
                   abs(slot.material.diffuse_color[0]-.07843137)<.0001
                   for slot in o.material_slots)]
    mask_low, mask_high = bounds(mask_meshes)
    bracket, hardware = (None, []) if args.no_bracket else add_bracket(meshes, args.pcb, args.bracket)
    assembly = meshes + ([bracket] if bracket else []) + hardware
    low, high = bounds(assembly)
    center = (low + high) / 2
    center.z = 0
    for o in assembly:
        o.location -= center
    bpy.context.view_layer.update()

    # Merge equivalent VRML materials and replace their preview shaders with
    # physically based shaders, with finishes guided by the assembled-board photo.
    materials = {}
    for obj in meshes:
        for slot in obj.material_slots:
            old = slot.material
            # Linked VRML mesh instances share material slots. Do not process
            # a replacement shader again: its viewport color defaults to gray.
            if old is None or old in materials.values():
                continue
            rgb = tuple(round(v, 4) for v in old.diffuse_color[:3])
            is_mask = abs(rgb[0]-.0784)<.0001 and abs(rgb[1]-.2)<.0001
            layer = 'F.Cu' if bounds([obj])[1].z > 0 else 'B.Cu'
            key = (rgb, layer if is_mask else None)
            if key not in materials:
                mat = bpy.data.materials.new('PCB material ' + str(rgb))
                mat.use_nodes = True
                shader = mat.node_tree.nodes.get('Principled BSDF')
                metal = 0.0
                roughness = 0.45
                color = rgb
                if rgb[0] > 0.65 and rgb[1] > 0.45 and rgb[2] < 0.35:
                    color, metal, roughness = (0.83, 0.59, 0.22), 1.0, 0.24
                elif max(rgb) - min(rgb) < 0.1 and 0.4 < min(rgb) < 0.9:
                    metal, roughness = 0.9, 0.27
                elif rgb[0] > 0.8 and rgb[1] > 0.75 and rgb[2] > 0.7:
                    # Warm silver terminals and white ceramic/ink are distinct
                    # in the KiCad material palette; only the former are metal.
                    if min(rgb) < 0.9:
                        metal, roughness = 0.9, 0.27
                    else:
                        roughness = 0.65
                elif rgb[1] > rgb[0] * 1.7 and rgb[1] > rgb[2] and rgb[1] < 0.3:
                    shader.inputs['Coat Weight'].default_value = 0.3
                    shader.inputs['Coat Roughness'].default_value = 0.24
                    roughness = 0.32
                elif max(rgb) < 0.3:
                    roughness = 0.48
                # Reference-photo finishes: yellow/brown FR4, red switch,
                # tan ceramics, black molded packages, silver metalwork.
                if rgb == (0.0, 0.0, 0.0):
                    color, metal, roughness = (.38,.25,.065),0,.62
                elif rgb == (.137,.402,.727):
                    color, metal, roughness = (.52,.018,.012),0,.4
                elif rgb == (.895,.891,.813):
                    color, metal, roughness = (.87,.85,.76),0,.5
                elif rgb in ((.379,.27,.215),(.859,.738,.496)):
                    color, metal, roughness = (.46,.31,.14),0,.6
                elif rgb == (.691,.664,.598):
                    color, metal, roughness = (.28,.25,.18),0,.65
                elif rgb in ((.148,.145,.145),(.12,.12,.13),(.055,.055,.06),(.082,.086,.094)):
                    color, metal, roughness = (.012,.013,.014),0,.53
                elif rgb == (.251,.251,.251):
                    color, metal, roughness = (.035,.036,.038),0,.48
                shader.inputs['Base Color'].default_value = (*color, 1)
                shader.inputs['Metallic'].default_value = metal
                shader.inputs['Roughness'].default_value = roughness
                # Shader bevel softens tiny package edges without editing CAD.
                bevel = mat.node_tree.nodes.new('ShaderNodeBevel')
                bevel.inputs['Radius'].default_value = 0.000025
                bevel.samples = 3
                mat.node_tree.links.new(bevel.outputs['Normal'], shader.inputs['Normal'])
                if is_mask:
                    copper_material(mat, args.copper, layer, mask_low, mask_high, center)
                materials[key] = mat
            slot.material = materials[key]

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.025
    scene.cycles.max_bounces = 8
    scene.render.resolution_x = args.width
    scene.render.resolution_y = round(args.width * 0.8)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.film_transparent = True
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (0.68, 0.73, 0.8, 1)
    background.inputs['Strength'].default_value = 0.35
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'

    def area(name, location, energy, size, color):
        data = bpy.data.lights.new(name, 'AREA')
        data.energy, data.shape, data.size, data.color = energy, 'DISK', size, color
        obj = bpy.data.objects.new(name, data)
        scene.collection.objects.link(obj)
        obj.location = location
        look_at(obj, (0, 0, 0))
    area('Large softbox', (-0.10, -0.06, 0.20), 0.12, 0.18, (1.0, 0.91, 0.82))
    area('Cool fill', (0.12, 0.04, 0.16), 0.07, 0.13, (0.80, 0.9, 1.0))
    area('Top rim', (-0.02, 0.16, 0.13), 0.09, 0.1, (1.0, 0.97, 0.90))

    data = bpy.data.cameras.new('Upright product camera')
    camera = bpy.data.objects.new('Upright product camera', data)
    scene.collection.objects.link(camera)
    camera.location = (0, 0, 0.25)
    look_at(camera, (0, 0, 0))
    data.type = 'ORTHO'
    data.ortho_scale = max(high.x - low.x, (high.y - low.y) * 1.25) * 1.18
    data.lens = 70
    scene.camera = camera
    add_socket_camera(scene, assembly)
    # All units are metres, as requested from KiCad's exporter.
    scene.unit_settings.system = 'METRIC'
    scene.render.filepath = str(args.output.resolve())
    if args.prepare_only:
        scene.render.filepath = '//' + os.path.relpath(args.output.resolve(), args.scene.parent.resolve())
        bpy.ops.wm.save_as_mainfile(filepath=str(args.scene.resolve()), compress=True)
        return
    try:
        bpy.ops.render.render(write_still=True)
    except RuntimeError as error:
        if 'OpenImageDenoiser' not in str(error):
            raise
        # Some distribution builds omit the optional denoiser.
        scene.cycles.use_denoising = False
        bpy.ops.render.render(write_still=True)
    if args.scene:
        scene.render.filepath = '//' + os.path.relpath(args.output.resolve(), args.scene.parent.resolve())
        bpy.ops.wm.save_as_mainfile(filepath=str(args.scene.resolve()), compress=True)


if __name__ == '__main__':
    main()
