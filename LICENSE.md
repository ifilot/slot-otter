# Slot-otter licensing

Copyright holders license their own Slot-otter contributions as follows.
Existing third-party notices and terms take precedence for third-party material.

| Material | License |
| --- | --- |
| Project-authored PCB schematics, layouts, custom symbols and footprints, and mechanical designs in `pcb/` and `bracket/` | [CERN-OHL-S-2.0](LICENSES/CERN-OHL-S-2.0.txt) |
| Project-authored software, assembly, CPLD logic, build scripts, test code and automation throughout the repository | [GPL-3.0-or-later](LICENSES/GPL-3.0-or-later.txt) |
| Project-authored written documentation, photographs and illustrations, including README files, manuals and schematic PDF/SVG exports | [CC-BY-SA-4.0](LICENSES/CC-BY-SA-4.0.txt) |
| PCB fabrication, BOM and placement exports | CERN-OHL-S-2.0, as outputs of the corresponding hardware design |

The software/CPLD license applies to `src/`, `driver/`, `testing/`, `tools/`,
`pcb/cpld/logic/`, repository build scripts and `.github/` automation, except
written documentation and third-party material. This statement also covers
project-authored files without individual SPDX headers. Hardware and mechanical
sources include the historical designs in `pcb/prototype/`, `pcb/release/` and
`bracket/`; historical status does not remove their open licensing.

The source location for project-authored hardware under CERN-OHL-S-2.0 is
https://github.com/ifilot/slot-otter . Preserve revision-specific sources when
sharing or manufacturing a modified design, as required by that license.

## Third party material and branding

Borland software under `buildenv/TC/` and `buildenv/TASM/` remains proprietary
and is bundled with permission obtained by the project maintainer. The licenses
above do not relicense it or grant additional rights to redistribute it.
Retain its supplied notices and comply with its applicable terms.

Third-party component and library material retains its existing terms.
KiCad library data is covered by its upstream license and design exception:
https://www.kicad.org/libraries/license/ .

These licenses grant only rights controlled by the respective licensors.
They do not grant trademark rights or imply endorsement of derivatives.
