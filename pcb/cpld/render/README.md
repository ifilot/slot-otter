# Slot-otter Forge Blender studio render

`slot-otter-cpld-rev1.blend` is an editable studio scene containing the Forge
revision 1.0 PCB and component geometry, printed bracket, mounting screws, surface materials,
camera and area lights. It is
self-contained; the copper textures are packed into the scene, and rendering
does not require external textures or HDR images.
The default orthographic camera looks straight down, with the ISA edge horizontal.
A second camera, `SD socket rear camera`, looks toward the socket from outside
the bracket and above the board.
The PNG background is transparent; the scene has no floor plane.
The DIP switch is posed at the default address **330h**: switches 1, 2, 5
and 6 are ON; 3, 4, 7 and 8 are OFF. `set_dip_switches.py` applies this pose
when rebuilding the scene, including the matching actuator recess surfaces.

The scene uses the actual KiCad VRML export. The simplified CPLD/socket and
resistor-array models are described in [the model sources](../components/3d/README.md).
The assembled-board reference photo guides the yellow-brown FR4, cream bracket,
red DIP switch, tan ceramic capacitors, dark packages and silver terminals.
Materials and lighting are illustrative and do not specify a manufacturing finish.
The PLCC44 socket molding has a dark brown finish, with a separate material
from the black CPLD package and resistor arrays.

KiCad VRML omits soldermask-covered copper. `render_copper.py` exports complete
native front/back copper plots from KiCad, including filled zones, clearances,
thermal reliefs, tracks, pads and vias. It rasterizes them at 8192 pixels wide
in the board's coordinate frame. The Blender script packs these coverage maps
into the mask material, using color, roughness and subtle relief to distinguish
copper from clearance areas beneath the green soldermask. Existing VRML mask
openings, exposed pads and silk retain their geometry. This replaces the earlier
segment-only approximation; no copper is added to or removed from the PCB.

Render the saved scene with Blender 4 or later:

```sh
blender --background pcb/cpld/render/slot-otter-cpld-rev1.blend \
  --python-expr "import bpy; bpy.ops.render.render(write_still=True)"
```

The output path is stored relative to the scene and points to
`img/slot-otter-cpld-rev1-blender.png` in the repository. The scene uses Cycles
with 128 samples and denoising. Select a supported GPU in Blender preferences
for faster rendering.

Render the additional socket-side image using the second camera:

```sh
blender --background pcb/cpld/render/slot-otter-cpld-rev1.blend \
  --python-expr "import bpy; s=bpy.context.scene; s.camera=bpy.data.objects['SD socket rear camera']; s.render.filepath='//../../../img/slot-otter-cpld-rev1-socket.png'; bpy.ops.render.render(write_still=True)"
```

This view uses the release bracket and shows the SD socket from the external
connector side. Both PNGs have transparent backgrounds.

The main README also includes a 2000 × 700 letterbox front view, facing the
SD-card slot from slightly above. Generate it without changing the saved scene:

```sh
blender --background pcb/cpld/render/slot-otter-cpld-rev1.blend \
  --python pcb/cpld/render_front.py -- --output img/slot-otter-cpld-rev1-front.png
```

To rebuild the scene after updating the PCB, export and import its geometry:

```sh
python3 pcb/cpld/render_copper.py --output copper-render
kicad-cli pcb export vrml --units m --force --output cpld-render.wrl pcb/cpld/cpld.kicad_pcb
blender --background --factory-startup --python pcb/cpld/render_blender.py -- \
  --input cpld-render.wrl --copper copper-render --output img/slot-otter-cpld-rev1-blender.png \
  --scene pcb/cpld/render/slot-otter-cpld-rev1.blend --width 2000 --samples 128
```

The copper-export helper requires KiCad 10, Pillow and `rsvg-convert`; use
`--kicad-cli /path/to/kicad-cli` when necessary. The Blender regeneration script
requires the `io_scene_x3d` and `io_mesh_stl` importers
included with Blender 4.0; install equivalent importers in newer Blender
versions if they are not bundled. The saved scene can be rendered without that importer. `cpld-render.wrl`
and `copper-render/` are temporary exports and can be deleted after importing. Builds without
OpenImageDenoise fall back to rendering without denoising.

The script uses GPL-3.0-or-later. The PCB-derived scene follows the project's
CERN-OHL-S-2.0 hardware licensing; the rendered documentation image uses
CC-BY-SA-4.0. See the repository [licensing statement](../../../LICENSE.md).

The bracket comes from `bracket/bracket-release-card.stl` in its original
millimetre units. The script aligns its mounting slots with PCB holes H1/H2
without changing the mesh. The bracket's 64.5 mm mounting pitch differs from
the PCB's vertical hole spacing by about 0.067 mm; this render is not a
mechanical fit qualification. Use `--no-bracket` to render the board alone, or `--bracket /path/to/model.stl` for a replacement
mesh using the same coordinate frame. The original STL files are unchanged.

Two illustrative silver M3 × 14 Phillips countersunk screws enter H1/H2 from
the bottom/solder side, with their drive recesses facing down. Continuous
threaded shanks (0.5 mm pitch) run through the bracket and PCB to chamfered
M3 Nyloc-style nuts on the top/component side. The nuts have metal hex bases,
rounded collars and visible off-white nylon locking inserts. Their illustrative
dimensions are 5.5 mm across flats and 4 mm overall height, following the
[M3 Type T Nyloc dimensions](https://www.westfieldfasteners.co.uk/Datasheets/Nut_HexNy_M.pdf).
The screw tips extend through the inserts and beyond the nuts. The heads
are positioned against the bracket's existing underside seats. No washers are
added. These parts are render geometry and do not add parts to the manufacturing
BOM or qualify the mechanical fit.

To refresh just the fasteners in either saved card scene:

```sh
blender --background pcb/cpld/render/slot-otter-cpld-rev1.blend \
  --python-exit-code 1 --python pcb/cpld/update_mounting_hardware.py
```

For Classic, use `pcb/release/render/slot-otter-discrete.blend` as the input.
This saves the scene in place, retaining the PCB, bracket, textures and cameras.
