# OTTERSD driver

This directory contains the source, build scripts and tests for `OTTERSD.EXE`,
the DOS driver for the Slot-otter card, and `HWRT.EXE`, its developer
hardware tester. It is self-contained: nothing here depends on the
legacy Navigator in `../src`.

This document is for developers. End users should follow the
[installation guide](docs/INSTALLATION.md), which is also shipped as
`README.TXT` in the public downloads.

## Contents

- [Overview](#overview)
- [Command-line reference](#command-line-reference)
- [Platform and scope](#platform-and-scope)
- [Design](#design)
- [Source layout](#source-layout)
- [Building and testing](#building-and-testing)
- [Releasing](#releasing)

## Overview

OTTERSD is a TSR filesystem redirector. It hooks the DOS network-redirector
interface (INT 2Fh), so it is started as an ordinary program, for example from
AUTOEXEC.BAT, rather than loaded with `DEVICE=` in CONFIG.SYS. Once installed,
it reads the FAT16 or FAT32 volume on the SD card and serves DOS file requests
for the chosen drive letter. A single executable handles both file systems,
read-only and verified read/write access.

CONFIG.SYS needs a LASTDRIVE at or beyond the chosen letter. The tested
configuration is:

```dos
LASTDRIVE=S
FILES=40
BUFFERS=10
```

## Command-line reference

Install from a local disk, never from the SD drive itself:

```dos
OTTERSD /DRIVE:S /PORT:330 /RW
```

| Option | Meaning |
| --- | --- |
| `/DRIVE:x` | Drive letter to provide (C to Z). Required at installation. |
| `/PORT:hhh` | Card base port in hexadecimal, matching the DIP switch. Default 330. |
| `/RO` | Read-only access. This is the default. |
| `/RW` | Read/write access with read-back verification of every sector. |
| `/NOVERIFY` | With `/RW`: skip the read-back. See [Write verification](#write-verification). |
| `/SKIPFATCHECK` | With `/RW`: faster mount. See [Mounting](#mounting). |
| `/FAT16`, `/FAT32` | Accept only that file system. Without either, it is detected automatically. |

The access mode and options are fixed at installation; reboot or `/UNLOAD`
to change them. A second installation is rejected. If no usable card is
present, the driver stays loaded with the drive offline.

Control commands operate on the installed driver:

| Command | Effect |
| --- | --- |
| `OTTERSD /STATUS` | Report version, mode, policies and the last SD diagnostic. |
| `OTTERSD /UNMOUNT` | Commit and check the FAT copies, mark the volume clean and take the drive offline. Required before removing the card, rebooting or using Navigator. |
| `OTTERSD /MOUNT` | Bring the drive online again after inserting a card. |
| `OTTERSD /UNLOAD` | Remove the driver completely and free its memory. |

`/UNMOUNT` and `/UNLOAD` refuse to run while files on the SD drive are open.
`/UNLOAD` must also be run from another drive, and it refuses if a TSR loaded
later has hooked INT 2Fh after OTTERSD, if DOS memory ownership is not as
expected, or if a commit fails. A failed mount or transport operation leaves
the drive offline with the TSR still loaded. Handles and searches opened
before that point cannot resume against a different card.

## Platform and scope

- **CPU:** 8088/8086 or later. No 286 instructions, EMS, XMS, DMA or IRQ line are used.
- **DOS:** MS/PC-DOS 3.1 through 6.x. DOS 5 and 6.22 with 1 MiB of emulated RAM
  are the qualification kernels. DOS 3/4 and a physical 5150/8088 are not yet
  tested; a 286 with 1 MiB is the current hardware target.
- **Media:** SDHC/SDXC with 512-byte sectors; FAT16 or FAT32 in the first
  primary MBR partition, or as a superfloppy.
- **Memory:** 42,896 bytes of conventional memory including the PSP, in either
  access mode. Validation and packaging fail above 45,000 bytes. Resources include a
  2,048-byte private stack, 16 open-file slots and 32 search cursors. DOS
  FILES and process limits also apply.

File names are DOS 8.3 names or the 8.3 aliases of existing long names.
Supported operations include creating, overwriting, appending, truncating
and extending files; deleting files; attributes and timestamps; creating and
removing directories; and moving across directories. Handle sharing,
duplicate handles and region locks are implemented. Standard FCB wildcard
deletion is tested; FCB record I/O and abort handling are not.

Not supported: GPT, extended partitions, SDSC cards, FAT12, exFAT, creating
long file names, and general DOS network-server functions.

## Design

### Write verification

By default, every 512-byte sector written goes through these checks: a CRC,
the card's accepted response, bounded busy and status waits, a CRC-checked
read-back, and an exact comparison with the intended data. The intended data
is held in a frozen copy for the duration of the write. A failed sector is
tried at most three times in total, and only after the card's identity and
usable reads have been re-established. If the failure cannot be resolved, the
session is poisoned and no further writes are accepted.

`/NOVERIFY` drops only the read-back and comparison. CRC, response, busy,
CMD13 status, identity and recovery checks remain. It can therefore
acknowledge data the card stored incorrectly, and must be chosen explicitly
at installation. The installer, `/STATUS` and HWRT report the active policy.
The diagnostic `verified` counter counts completed sector writes in both modes.

Writes are synchronous; there is no write-back cache. Verified sector writes
do not make multi-sector FAT updates transactional. Closing a file finishes
its data and directory writes but leaves the volume marked dirty, to avoid
comparing both complete FATs on every close. An explicit DOS commit, a global
flush and `/UNMOUNT` compare the FAT copies before marking the volume clean.
A volume left dirty by an interrupted session is refused at the next mount and
needs checking on another computer; the driver never clears the flag silently.

### Mounting

A full mount checks the geometry, capacity, backup boot sector, FAT flags,
FSInfo signatures and that all FAT copies match. It does not scan for
allocation errors or cross-linked files.

`/SKIPFATCHECK` skips the complete FAT comparison at mount and compares only
the first FAT sector. All other mount checks, the comparisons made before FAT
changes and the full commit checks remain. It requires `/RW`; `/RO` never
performs the full comparison.

### Caching and card changes

Reads use separate caches: one payload sector, four FAT sectors and two
directory sectors. Under `/RW`, each open handle also keeps its position in
the cluster chain, so sequential reads need not walk the chain from the start.
Every cached FAT access, including a cache hit, rechecks the card's identity.
Before any write, all retained positions are invalidated and any cached copy
of the sector being written is discarded. A write starts its own validation
from freshly read data rather than from cached results. Removing or replacing
the card invalidates the mounted file system. Cards must be unmounted before
raw-sector tools or Navigator change them.

### Allocation

Newly allocated clusters for regular files receive the incoming data directly,
without being zeroed first. File reads stop at the end of the file, so stale
bytes beyond it are never visible. Gaps and explicit extensions are filled
with zeros, and new directory clusters are cleared before they are linked.

### Disk-space reporting

The DOS free-space call uses 16-bit counts. To report large volumes, the
driver presents larger logical allocation units than the physical clusters,
up to 32 KiB, and rounds total and free counts down. The physical geometry is
unchanged. Volumes above about 2 GiB still exceed what the call can report.

## Source layout

| File | Responsibility |
| --- | --- |
| INSTALL.C / INSTALL.H | Installation and control commands; discarded after loading |
| BOOT.C / CRT.C | Retained bootstrap and CRT/far call gates |
| ENTRY.ASM | 8086 interrupt bridge, private stack and resident boundary |
| REDIR.C / RWOPS.C / RWDIR.C | DOS redirector, handles, locks and write callbacks |
| FAT32.C / RWFS.C / RWFS.H | FAT16/FAT32 reading, writing and directory operations |
| SDRW.C / RWSD.H | Card identity, recovery and verified sector transport; version number |
| FASTIO.ASM | 8086 far memory copy |
| PORTBODY.H | Shared, exhaustively tested option parser |
| HWRT.C / TESTCHLD.C | Hardware tester, including its self-exec child mode |
| installer_segments.py / tests/layout.py | Checks that installer segments are discarded and the startup reserve fits |

| Directory | Contents |
| --- | --- |
| `docs/` | [Installation guide](docs/INSTALLATION.md), [hardware test manual](docs/MANUAL.md), developer image notes ([FAT16](docs/FAT16_IMAGE.md), [FAT32](docs/LARGE_IMAGE.md)), [source conventions](docs/CODING.md) and [DOS ABI notes](docs/DOSREF.md) |
| `tests/` | Host, mutation, native DOS and XCOPY tests; see [tests/README.md](tests/README.md). `tests/reference/` holds earlier protocol code used only as test input; `tests/emulation/` holds the SD card model and emulator adapters. |
| `logs/` | Physical-card logs: `logs/historical/` for earlier runs, `logs/<card-name>/` for new ones |
| `dist/` | Generated build, kit and release output. Ignored by Git. |

## Building and testing

### Requirements

Turbo C 2.0 and TASM 2 are supplied separately, in `../buildenv` or the
directory named by `TOOLCHAIN_DIR`. `DOSBOX_BIN` selects the DOSBox used to
run the compiler. Python 3, GCC/gcov, mtools and dosfstools are needed for the
host tests and packaging.

### Build and validate

```sh
bash driver/build.sh /tmp/otter-build
python3 driver/validate.py --output /tmp/otter-check
python3 driver/validate.py --full --output driver/dist \
  --dosbox /path/to/dosbox-with-isa-model \
  --boot-image /path/to/dos5.img --boot-image /path/to/dos622.img
```

`build.sh` builds both programs. `validate.py` runs the host regression,
coverage and mutation tests, builds both programs and creates a candidate
developer kit.

`--full` also boots real DOS in an emulator with the
[DOSBox-VirtIsa](https://github.com/ifilot/dosbox-virtisa) ISA model. It runs:
- read-only, command-line, EXEC and card-swap tests;
- write-fault profiles and tester guards;
- XCOPY from a BIOS hard disk at two cluster sizes and with each write policy;
- stress, memory and reboot tests on the final image, with independent
  content comparison and fsck.

These tests need `XCOPY.EX_` in each boot image and `EXPAND.EXE` in one of
them, or in `--xcopy-expand-media`. Boot images, compiler images, XCOPY and
the emulator are not redistributed. Results, gate logs and
`EVIDENCE/QUALIFICATION.JSON` are written to the output directory.

Emulation does not qualify physical hardware.

### Testing on a real card

Validation produces developer kits with HWRT and test fixtures:
`dist/OTTERSD.IMG` (small FAT32 stress image) with `dist/OTTERSD.ZIP`, plus
500 MiB images in `dist/FAT16/` and `dist/500M/`. Follow the
[hardware test manual](docs/MANUAL.md) separately for each card. HWRT records
the card's CID, capacity, versions, source identifier, timings and
diagnostics. Save each card's logs under `logs/<card-name>/`. Results from an
earlier build do not carry over to a new one.

## Releasing

`release.py` builds the public downloads from a qualified `OTTERSD.EXE`:

```sh
python3 driver/release.py --driver /path/to/OTTERSD.EXE \
  --output /path/to/new-public-output
```

It produces:
- the DOS ZIP;
- 360 KiB, 720 KiB and 1.44 MiB installation floppies;
- empty 500 MiB FAT16 and FAT32 SD images, with FAT16 at 16 KiB clusters recommended;
- `SHA256.TXT`.

The ZIP and floppies contain only `OTTERSD.EXE`, `README.TXT` (from
[INSTALLATION.md](docs/INSTALLATION.md)), a CONFIG.SYS example and the
license. They include no HWRT, fixtures or test markers. The script never uses
the developer fixture builders. It refuses an existing output directory and
checks each floppy's file list, the SD geometry, FAT copies, root contents,
backup boot sector, FSInfo and fsck results. Local output can be placed in
`dist/RELEASE/`.

GitHub Actions runs the host and mutation tests, builds the binaries and
uploads only `release.py`'s output. A tagged release requires the tag to be
`v` followed by the version in RWSD.H. OTTERNAV is built separately and
attached as an optional legacy download.

RWSD.H defines the displayed version and a 16-bit resident version ID: the
major version in the high byte, and minor and patch in the two low nibbles.
HWRT refuses to work with a driver of a different version.
