# Slot-otter CPLD revision 1.0

This is the current hardware design. Revision 1.0 uses an ATF1504AS
in a PLCC44 socket and the reassigned pinout in [logic/README.txt](logic/README.txt).
Do not use this programming image with an earlier PCB pinout.

## Design sources and licenses

Open `cpld.kicad_pro` in KiCad 10. The schematic is `cpld.kicad_sch` and the
PCB is `cpld.kicad_pcb`. Project libraries are registered through `fp-lib-table`
and `sym-lib-table`, with their files under `components/`.

Project-authored hardware uses CERN-OHL-S-2.0, software and CPLD logic use
GPL-3.0-or-later, and documentation uses CC-BY-SA-4.0. See the repository
[licensing statement](../../LICENSE.md) and [full license texts](../../LICENSES/).
The source location is https://github.com/ifilot/slot-otter .

The older [discrete-logic release](../release/README.md) and
[prototype](../prototype/README.md) are historical designs. Their component
references, manufacturing files and pinouts are not interchangeable with this board.

## Manufacturing and assembly

- [Schematic PDF](cpld.pdf) and [SVG](cpld.svg).
- [Bill of materials](production/bom.csv), including schematic supplier fields and datasheet links.
- [Placement positions](production/positions.csv), in millimetres, and [assembly references](production/designators.csv).
- [Gerbers and drill files](GERBERS/).
- [Generation manifest](production/manifest.json), [DRC](production/drc.json) and [ERC](production/erc.json).

Check `manufacturing_ready` and the reports before ordering. A generated export
is not manufacturing approval. A supplier field copied from the schematic is
not a purchasing validation; verify the exact package and part before assembly.
U1 needs both the ATF1504AS PLCC44 device and a compatible through-hole
PLCC44 socket. J2 is the integral ISA edge connector, not a separately
purchased connector. The bracket [STL sources](../../bracket/README.md) were authored as meshes for
earlier cards; check mechanical fit before using them with the CPLD layout.

Regenerate the outputs with KiCad 10 installed:

```sh
python3 pcb/cpld/export.py
```

Use `--kicad-cli /path/to/kicad-cli` when the executable is not on PATH.
The exporter refills and saves PCB copper zones, runs DRC/ERC, exports the
current schematic and board, and records source hashes. It exports both board
sides in the placement CSV; configure your assembler's origin and rotation
conventions before submitting it. The `.dsn` and `.ses` files are historical
routing snapshots, not revision 1.0 manufacturing inputs.

## CPLD build and bring-up

The [CUPL source](logic/slototter.pld), [build script](logic/build.cmd),
[functional-vector generator](logic/generate_vectors.py) and
[pinout and timing documentation](logic/README.txt) are the editable logic sources.
Run `logic/build.cmd test` on Windows with WinCUPL installed to compile, fit and
simulate; then run `logic/build.cmd` for an image without simulation vectors.
Generated programming files are under `logic/build/` and are ignored by Git.

The revision 1.0 board has no on-board JTAG connector; its JTAG pads are
unconnected. Program the CPLD in a compatible external PLCC44 adapter or
fixture before inserting it into U1's socket. Use a programmer supporting
ATF1504AS and the target's voltage; follow its adapter pinout and power
instructions. The reserved PLCC44 JTAG pins are 7 TDI, 13 TMS, 32 TCK and
38 TDO. Program the newly generated `logic/build/slototter.jed`, then use
the programmer's verify operation. Programmer-specific commands depend on
the selected programmer. Disconnect power before inserting or removing U1.
Follow the bring-up checks and timing limits in the logic
README before using the [DOS driver](../../driver/README.md) on this revision.
