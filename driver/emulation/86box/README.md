# Slot-otter in 86Box

This source adapter adds an 8-bit ISA Slot-otter card to the IBM 5150 (both
motherboard revisions) and IBM XT machine initializers. It uses the register
directions documented in the card schematic, an SDHC SPI command model, and a
raw FAT32 image opened **read-only**. It does not model the electrical timing of
the card's clock-generation circuit.

The adapter is compiled into a separate 86Box build. It is not a runtime plugin
and does not add a selectable card to the stock 86Box UI. The integration script
validates its patch locations and can be run repeatedly without duplicate hooks.

From this project's root, with your own 86Box source checkout:

```sh
python3 driver/emulation/86box/install.py /path/to/86Box
```

Build that checkout following [86Box's build instructions](https://86box.readthedocs.io/en/latest/dev/buildguide.html).
The installer copies all three required C/header files; the resulting emulator
does not depend on this repository at runtime. API compilation was checked
against the official 86Box source headers. A complete 86Box boot has not yet been
validated here; the same card model has protocol tests and a DOSBox adapter for
testing it with actual DOS.

With 86Box closed, add this section to the machine's configuration file:

```ini
[Slot-otter]
base = 0330
image = /absolute/path/to/card.img
```

An empty image setting represents an absent card; OTTERFS still installs offline.
The shared model supports CMD10 CID checks and a socket replacement API, but this
adapter does not yet expose runtime insertion/ejection controls in the 86Box UI. Configure an IBM PC 5150,
8088 at 4.77 MHz, CGA or MDA, and 640 KiB RAM including ISA memory expansion.
Start with MS-DOS 6.22 to match the validated DOS tests; then try DOS 3.1/3.3.
Use your own BIOS ROMs and bootable DOS images. Load `OTTERFS` as described in
[the driver README](../../README.md).

For a memory-constrained test, reduce conventional RAM to 256 KiB and measure
the free memory after DOS and the driver load. No EMS or XMS is required by the
driver. A 256 KiB configuration is a test target, not a verified minimum.

Run `tests/PROBE.C` (compiled to `PROBE.EXE`) and test `DIR`, `TYPE`, binary `COPY`
and `HELLO.COM` using the image made by `tests/fixture.py`. Compare the image's
SHA-256 before and after the run. Port `0330` must not be shared with an MPU-401
or another emulated ISA device.

The device API is documented by [86Box](https://86box.readthedocs.io/en/latest/dev/api/device.html).
