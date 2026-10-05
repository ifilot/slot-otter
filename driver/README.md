# OTTERFS: standalone read-only FAT32 driver

`OTTERFS.EXE` makes a Slot-otter SD card available as a DOS drive letter. Ordinary
DOS programs can list directories, read and seek files, copy files to local
disks, and run executables directly from the card. It is a resident filesystem
redirector; MSCDEX and a CONFIG.SYS device driver are not needed.

All its source is in this directory. The SD assembly was copied from the
navigator and adapted here; neither compilation nor execution depends on `src`
or OTTERNAV. The two programs have separate builds and state.

## Load the driver

Add to `CONFIG.SYS`, then reboot:

```dos
LASTDRIVE=S
```

Load from the command line or `AUTOEXEC.BAT`:

```dos
OTTERFS /DRIVE:S /PORT:330
DIR S:\
TYPE S:\README.TXT
COPY /B S:\FILE.BIN C:\FILE.BIN
```

Choose an unused drive letter from C through Z. `/PORT:` is hexadecimal and
defaults to `330`; it must match the card's hardware configuration.
Optional `+` and `0x` prefixes and leading zeros are accepted; negative and
overflowing port values are rejected. The driver
prints its resident memory consumption. Repeated installation is rejected.

Target: an 8088/8086 and MS/PC-DOS 3.1 through 6.x. There are no 286 instructions,
EMS, XMS, DMA, or interrupt-line requirements. The current build retains 17,632
bytes (17.2 KiB) of conventional RAM under DOS 5.0 and 6.22. Both are tested
with actual booted DOS and 1 MiB of emulated RAM. DOS 3.x/4.x layout
support is implemented but has not been tested on those kernels or real 8088
hardware. FreeDOS, Windows DOS boxes, and later DOS versions are not validated.
See [memory measurements and next opportunities](MEMORY.md) for the 9,728-byte
reduction and how the DOS allocation is checked under memory pressure.

Use SDHC/SDXC media with a FAT32 volume and 512-byte sectors. The first FAT32
primary MBR partition is mounted; FAT32 superfloppies are also supported. GPT,
extended-partition traversal, SDSC byte addressing, FAT16, exFAT, and long-name
APIs are not implemented. Files with long names are accessible through their
8.3 aliases. Names use ASCII case folding and preserve existing OEM bytes.

The driver has 16 resident open-file slots; DOS's own `FILES=` and process handle
limits can reduce that number. There are 32 independent resident directory search
cursors. Starting more searches evicts the oldest; resuming an evicted search
returns no more files. DOS's search data contains a cookie and mount generation
check, so an old search cannot resume against a replacement card.

## Read-only behavior and lifetime

There is no SD write command in the executable. Creation, truncation, writes,
deletion, rename, directory mutation, and attribute writes are denied. DOS can
accept a handle timestamp change in its own SFT memory; closing and reopening
the file restores the card's unchanged timestamp. Read locks are harmless
no-ops because the filesystem is immutable. Reported writable free space is zero;
legacy disk information caps the reported cluster count at 65535.

The driver installs even when the slot is empty or the card cannot be mounted.
The drive letter remains registered and accesses fail while it is offline.
To swap cards:

```dos
OTTERFS /UNMOUNT
REM Remove the old card and insert the replacement.
OTTERFS /MOUNT
OTTERFS /STATUS
```

Close all files on the drive first. Both `/UNMOUNT` and `/MOUNT` refuse while
resident file handles remain open, including handles inherited by other programs.
Unmounting clears sector caches and geometry, invalidates searches, resets the
DOS drive's current directory to its root, and releases the card. Unmounting an
already offline drive succeeds. Mounting reinitializes SD and validates FAT32
from scratch; failure leaves the drive offline. The TSR itself remains loaded
until reboot.

Unexpected removal or replacement is checked before filesystem requests and
physical sector reads, including requests that can otherwise use cached data.
The transport checks the socket's weak MISO pull latch and compares the card's
16-byte CID using read-only CMD10. A missing card, changed identity, or transport
failure takes the drive offline. Close stale handles and use `/MOUNT` to recover;
a replacement is never mounted automatically. Checks add SPI traffic to each
request. The DOS callback reports not ready (21); DOS 5/6 can translate this into
access denied (5) for a file read. `/STATUS` checks media and shows mounted/offline
state, open file count, and port.

Always unmount before removal or running OTTERNAV. Removing and reinserting the
same card between checks cannot be detected by CID, especially if its contents
were changed elsewhere. After finishing with OTTERNAV, `/MOUNT` reloads the
filesystem. The absence probe follows the schematic but still needs electrical
validation on real hardware. This driver does not add a BIOS disk or support
booting from the card; direct disk utilities such as CHKDSK are outside its API.

Sector errors propagate to DOS. The SD command response and data token are
checked; the returned data CRC is consumed but not verified by the DOS reader.
Corrupt cluster values are rejected, and directory scans have a finite traversal
bound (65535 cluster transitions). This first version does not provide full
network sharing semantics or every legacy FCB/IOCTL interface.

## Build

In DOS, put Turbo C 2.0 and TASM 2.x on PATH, enter this directory, and run:

```dos
MAKE
```

On Linux with DOSBox and Python 3:

```sh
bash driver/build.sh
```

The script uses `../buildenv` as the default compiler installation. For a copied,
standalone driver directory, select an external toolchain instead:

```sh
TOOLCHAIN_DIR=/path/to/turbo-tools bash driver/build.sh
```

`DOSBOX_BIN` can override the compiler emulator. The build uses a fresh temporary
directory, explicitly links only this program's objects, and produces
`driver/OTTERFS.EXE` and its map. Source files passed to the old tools are
normalized to CRLF. Generated binaries and objects are ignored by Git.

## Tests and emulation

The [regression suite](tests/README.md) compiles the production redirector, FAT32
reader and card model, measures coverage, and checks nine deliberate regressions
in temporary source copies. It requires GCC and Python 3:

```sh
python3 driver/tests/run.py --coverage /tmp/otter-coverage --mutations
```

Tests cover fragmented files, high cluster numbers, active FAT selection,
superfloppies, directory chains, independent searches, large reads, malformed
volumes, I/O errors, the SPI response pipeline, schematic I/O directions, and
CRC generation and CID identity/replacement in the emulator.

For integration, supply your own bootable DOS floppy image, DOSBox-VirtIsa,
DOSBox for compilation, and mtools:

```sh
python3 driver/tests/integration.py \
  --boot-image /path/to/dos-boot.img \
  --dosbox /path/to/dosbox-virtisa
```

The harness boots **actual DOS**, bypassing DOSBox's built-in DOS replacement.
It modifies only a temporary copy of the boot floppy and leaves the original
alone. A generated FAT32 card image is attached through emulated ISA I/O.
The probe tests reads, seeks, searches, handle independence, segment boundaries,
and mutation attempts. The batch also runs DOS COPY and EXEC, checks duplicate
installation, compares copied file contents, and verifies an unchanged SD image
hash. Logs and images remain in the printed temporary directory.

The [86Box adapter](emulation/86box/README.md) adds the card to an IBM PC/XT
source build for testing with an emulated 4.77 MHz 8088. Its API compilation and
installation script were checked; a complete 86Box machine boot is still pending.
It shares a card model with the optional [DOSBox adapter](emulation/dosbox/isa.cpp),
which has been tested with booted DOS. To use that adapter, copy it to a separate
DOSBox-VirtIsa checkout's `src/isa/isa.cpp`, copy `slot_model.c` and `slot_model.h`
from `emulation` beside it, and add `src/isa/slot_model.c` to the CMake executable
sources. The original DOSBox-VirtIsa model lacks CMD10 and its chip-select/pull-latch
register directions differ from the schematic; use the supplied adapter.

To run the automated removal/replacement tests, additionally add
`target_compile_definitions(dosbox PRIVATE OTTER_MODEL_TEST)` to that separate
emulator build and pass `--swap` to the integration harness. This build exposes
**test-only** port `334`: `0` removes the card, `1` inserts the configured image,
`2` inserts `OTTER_TEST_IMAGE2`, and `3` inserts that second image already
initialized, which tests CID checking without relying on its power-up state.
Reading test port `334` reports the chip-select latch for the assembly probe.
`OTTER_TEST_EMPTY=1` starts with no card. These controls are absent from production
adapter builds. The harness configures them and verifies empty-slot installation,
CLI commands, open-handle refusal, cache/search invalidation, current-directory
reset, removal during a read, and a replacement with different cluster geometry.
These tests pass on booted MS-DOS 5.0 and 6.22 with 1 MiB emulated RAM.

The shared model implements `slot_model_replace()` for emulator socket controls;
its synthetic CID is stable per image path. The 86Box adapter currently has no
runtime socket UI; its empty-slot configuration is available for manual testing.

## Source layout and references

| File | Purpose |
| --- | --- |
| `MAIN.C` | Installation, options, DOS layout selection, drive registration |
| `CRT.C`, `PORT.C` | Minimal runtime hooks and bounded hexadecimal option parsing |
| `ENTRY.ASM` | 8086 interrupt bridge and private resident stack |
| `REDIR.C` | DOS redirector requests and per-open-file state |
| `FAT32.C` | Streaming directory/cluster reader and two sector caches |
| `SD.C`, `SDCMDS.ASM` | SD initialization and read-only ISA transport |
| `OTTER.H` | Shared types and interfaces |
| `tests/` | Generated fixture, host tests, real-DOS probe and harness |
| `emulation/` | Shared SD/ISA model and 86Box/DOSBox adapters |

DOS layouts and callbacks follow Ralf Brown's Interrupt List:
[SDA 3.x](https://fd.lod.bz/rbil/interrup/dos_kernel/215d06.html),
[SDA 4–6](https://fd.lod.bz/rbil/interrup/dos_kernel/215d0b.html),
[SFT/CDS](https://fd.lod.bz/rbil/interrup/dos_kernel/2152.html), and
[redirector reads](https://fd.lod.bz/rbil/interrup/network/2f1108.html).
Hardware register directions follow the notes in
`pcb/release/isa-sdcard.kicad_sch`. Source is GPL-3.0-or-later; the copied assembly
retains its original attribution to Ivo Filot.

Real-hardware test image and instructions: [hardware/MANUAL.md](hardware/MANUAL.md). Build the complete SD test kit with `python3 driver/hardware/build.py`.

Experimental standalone writes and emulator fault tests live in [write/README.md](write/README.md). They are not linked into the resident read-only driver.
