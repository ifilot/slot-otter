# Slot-otter Classic Blender render

`slot-otter-discrete.blend` contains the Slot-otter Classic board, its populated
components, printed bracket, illustrative mounting screws, studio lights and
cameras. It uses the same materials and rendering setup as the
[Forge scene](../../cpld/render/README.md). Copper textures are packed into the
scene. The output is a transparent 2000 × 1600 PNG with 128 Cycles samples.
The DIP switch shows **330h**, with switches 1, 2, 5 and 6 ON and the others
OFF, matching the default setup in the main README.

Render the saved scene from the repository root with Blender 4 or later:

```sh
blender --background pcb/release/render/slot-otter-discrete.blend \
  --python-expr "import bpy; bpy.ops.render.render(write_still=True)"
```

Render the 2000 × 700 letterbox front view used in the main README:

```sh
blender --background pcb/release/render/slot-otter-discrete.blend \
  --python pcb/cpld/render_front.py -- --output img/slot-otter-discrete-front.png
```

This camera faces the SD-card slot from slightly above and leaves the saved
scene unchanged.

To regenerate the geometry, use KiCad 10 and Blender 4.0 with its bundled
VRML and STL importers:

```sh
python3 pcb/release/prepare_render.py --output discrete-render.kicad_pcb
python3 pcb/cpld/render_copper.py --pcb pcb/release/isa-sdcard.kicad_pcb \
  --output discrete-copper
kicad-cli pcb export vrml --units m --force --output discrete-render.wrl \
  discrete-render.kicad_pcb
blender --background --factory-startup --python pcb/cpld/render_blender.py -- \
  --pcb pcb/release/isa-sdcard.kicad_pcb --input discrete-render.wrl \
  --copper discrete-copper --output img/slot-otter-discrete-blender.png \
  --scene pcb/release/render/slot-otter-discrete.blend --width 2000 --samples 128
```

The preparation helper writes a temporary copy without modifying the hardware
source. It attaches the shared socket model to the existing J1 footprint,
uses the shared 0612 resistor-array visualization for the 0612 footprints,
and resolves the older KiCad 9 library references through KiCad 10. When
exporting through Windows KiCad from WSL, pass `--models` with the Windows
path to `pcb/cpld/components/3d` and use Windows paths for the CLI's input and
output. The copper helper accepts `--kicad-cli` for that executable.

The temporary board, VRML and copper directory can be deleted after saving
the scene. Materials and screw geometry are illustrative; the original PCB
and bracket sources are unchanged. The render is not a mechanical fit check.
The PCB-derived scene uses CERN-OHL-S-2.0 and the documentation image uses
CC-BY-SA-4.0; see the [licensing statement](../../../LICENSE.md).
