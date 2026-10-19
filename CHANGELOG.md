# Release history

## 1.1.4 — Unreleased

- Revise the Slot-otter Forge layout: pour GND on both copper layers, stitch
  them with vias and route +5 V as traces. Regenerate the fabrication outputs.
- Add the OSHWA certification mark (UID NL000046) to the Forge silkscreen and
  the README, with the Open Source Licenses facts label.
- Ignore KiCad local history folders and increment OTTERSD/HWRT to 1.1.4.

## 1.1.3

- Fix DOS set-attributes requests on FAT16 and FAT32 directories when the
  caller omits the directory bit (issue #8). Preserve the entry type while
  updating read-only, hidden, system and archive flags.
- Add regression coverage for both formats and increment OTTERSD/HWRT to 1.1.3.

## 1.1.2

This release introduces CPLD revision 1.0 and versions the Slot-otter hardware
and DOS software together. OTTERSD and HWRT identify themselves as 1.1.2;
file-access behavior remains unchanged from 1.0.0, with optional foreground
feedback controls added to the private driver protocol.
Hardware revision numbers remain independent of the project release version.

- Show the driver version and operation messages during loading and controls,
  with throttled FAT-comparison progress on the console and plain redirected logs.
- Name the boards Slot-otter Classic and Slot-otter Forge; show both supported,
  functionally equivalent boards and DOS usage examples in the README.
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
