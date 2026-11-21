"""Blender script: orthographic top-down 'plate' of Slot-otter Classic.

Run through `python render.py plate`, or directly:

    blender --background pcb/release/render/slot-otter-discrete.blend \
        --python movie/plate/render_plate.py -- --pcb pcb/release/isa-sdcard.kicad_pcb \
        --output movie/build/plate/plate.png --json movie/build/plate/plate.json

The saved scene is not modified. The board mesh's bounding box is matched to
the Edge.Cuts bounding box of the .kicad_pcb, so the plate's pixel grid maps
linearly onto KiCad millimetres; the mapping is written to the JSON file.
"""
import argparse
import json
import os
import re
import sys

import bpy
import mathutils


def args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument('--pcb', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--json', required=True)
    p.add_argument('--ppm', type=float, default=48.0)
    p.add_argument('--samples', type=int, default=256)
    p.add_argument('--device', default='auto')
    p.add_argument('--region', type=float, nargs=4, default=None,
                   help='x0 y0 x1 y1 in KiCad mm (default: board + bracket)')
    return p.parse_args(argv)


def edge_bbox(path):
    s = open(path, encoding='utf-8').read()
    xs, ys = [], []
    for m in re.finditer(r'\((gr_line|gr_arc|gr_rect)(.*?)\(layer "Edge\.Cuts"\)', s, re.S):
        for q in re.finditer(r'\((?:start|end|mid) ([-\d.]+) ([-\d.]+)\)', m.group(2)):
            xs.append(float(q.group(1)))
            ys.append(float(q.group(2)))
    return min(xs), min(ys), max(xs), max(ys)


def board_mesh_bbox():
    best = None
    for o in bpy.data.objects:
        if o.type != 'MESH' or 'bracket' in o.name.lower() or o.hide_render:
            continue
        bb = [o.matrix_world @ mathutils.Vector(c) for c in o.bound_box]
        mn = [min(v[i] for v in bb) for i in range(3)]
        mx = [max(v[i] for v in bb) for i in range(3)]
        if mx[2] - mn[2] > 0.0025:
            continue
        area = (mx[0] - mn[0]) * (mx[1] - mn[1])
        if best is None or area > best[0]:
            best = (area, mn, mx)
    return best[1], best[2]


def setup_device(scene, want):
    scene.render.engine = 'CYCLES'
    if want == 'CPU':
        scene.cycles.device = 'CPU'
        return 'CPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for kind in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type != 'CPU']
        if gpus:
            for d in prefs.devices:
                d.use = d.type != 'CPU'
            scene.cycles.device = 'GPU'
            return f'{kind}: ' + ', '.join(d.name for d in gpus)
    if want == 'GPU':
        raise SystemExit('No GPU device available to Cycles (is this a +dfsg distro build of Blender?)')
    scene.cycles.device = 'CPU'
    return 'CPU (no GPU found)'


def main():
    a = args()
    kx0, ky0, kx1, ky1 = edge_bbox(a.pcb)
    (bx0, by0, _), (bx1, by1, _) = board_mesh_bbox()
    sx = (bx1 - bx0) / (kx1 - kx0)
    sy = (by1 - by0) / (ky1 - ky0)
    print(f'plate: board {kx1 - kx0:.3f} x {ky1 - ky0:.3f} mm, blender scale {sx * 1000:.5f} / {sy * 1000:.5f} m/m')

    def to_blender(kx, ky):          # KiCad y grows down, Blender Y grows up
        return bx0 + (kx - kx0) * sx, by1 - (ky - ky0) * sy

    rx0, ry0, rx1, ry1 = a.region or (kx0 - 7.0, 14.0, 198.0, 144.0)
    res_x = int(round((rx1 - rx0) * a.ppm))
    res_y = int(round((ry1 - ry0) * a.ppm))
    rx1 = rx0 + res_x / a.ppm
    ry1 = ry0 + res_y / a.ppm

    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new('PlateOrtho')
    cam_data.type = 'ORTHO'
    cam_data.sensor_fit = 'HORIZONTAL'
    cam_data.ortho_scale = (rx1 - rx0) * sx
    cam_data.clip_start = 0.001
    cam_data.clip_end = 10.0
    cam = bpy.data.objects.new('PlateOrtho', cam_data)
    scene.collection.objects.link(cam)
    cx, cy = to_blender((rx0 + rx1) / 2, (ry0 + ry1) / 2)
    cam.location = (cx, cy, 0.5)
    cam.rotation_euler = (0.0, 0.0, 0.0)
    scene.camera = cam

    dev = setup_device(scene, a.device)
    print('plate: device', dev)
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.cycles.samples = a.samples
    scene.cycles.use_denoising = True
    scene.render.use_persistent_data = False
    scene.render.filepath = os.path.abspath(a.output)
    os.makedirs(os.path.dirname(scene.render.filepath), exist_ok=True)
    print(f'plate: {res_x} x {res_y} px, {a.ppm} px/mm, region {rx0:.2f},{ry0:.2f} - {rx1:.2f},{ry1:.2f} mm')
    bpy.ops.render.render(write_still=True)

    meta = {
        'mm_bounds': [rx0, ry0, rx1, ry1],
        'px': [res_x, res_y],
        'ppm': a.ppm,
        'samples': a.samples,
        'device': dev,
        'blend': bpy.data.filepath,
        'blender': bpy.app.version_string,
    }
    with open(a.json, 'w') as f:
        json.dump(meta, f, indent=2)
    print('plate: wrote', a.output, 'and', a.json)


main()
