# Release history

## 1.1.0 — Unreleased

This release introduces CPLD revision 1.0 and versions the Slot-otter hardware
and DOS software together. OTTERSD and HWRT identify themselves as 1.1.0;
the driver protocol and file-access behavior remain unchanged from 1.0.0.
Hardware revision numbers remain independent of the project release version.

- Add the ATF1504AS-based PCB, matching CPLD logic, programming instructions
  and functional simulation vectors.
- Publish the schematic, fabrication ZIP, bill of materials, assembly data,
  manufacturing reports and tools to regenerate the hardware outputs.
- Update the component libraries, board artwork and product images, with
  editable component models and Blender render sources.
- Document project licensing and preserve third-party tool terms.
- Expand the hardware and driver documentation; retain the discrete-logic
  and prototype board sources for existing cards.
- Keep the fabrication ZIP synchronized with the generated Gerbers and drills.

The CPLD programming image requires the matching revision 1.0 PCB. Consult
the [hardware documentation](pcb/cpld/README.md) and
[CPLD timing and bring-up guidance](pcb/cpld/logic/README.txt) before use.
Functional simulation does not replace timing validation on the target PC.

## 1.0.0

First stable OTTERSD release, with FAT16/FAT32 support, read-only and verified
read/write access, installation floppies and empty SD-card images.
