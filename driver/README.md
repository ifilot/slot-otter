# OTTERWR: standalone DOS SD driver

The current driver is `OTTERWR.EXE` 0.4. The single executable supports verified
read/write operation with `/RW`, or read-only operation with `/RO` (the default).
The current hardware tester is `HWRT.EXE` 0.2. Both programs and all source are
under `driver`; neither depends on Navigator or `src` after installation.

## Install and use

Merge these settings into your boot disk's CONFIG.SYS and reboot:

```dos
LASTDRIVE=S
FILES=40
BUFFERS=10
```

From a local disk, install on an unused letter:

```dos
OTTERWR /DRIVE:S /PORT:330 /RW
OTTERWR /STATUS
DIR S:\
```

`/PORT:` is hexadecimal and defaults to 330. Use `/RO` instead of `/RW` for
read-only access. Access mode is fixed at installation; reboot to change it.
This is a TSR filesystem redirector, not a CONFIG.SYS DEVICE driver or MSCDEX
extension. Repeated installation is rejected. Installation can leave the drive
offline when no usable card is present; insert a card and run `/MOUNT`.

Before card removal, reboot, or Navigator use:

```dos
OTTERWR /UNMOUNT
REM Only after successful unmount: remove/reinsert card or reboot.
OTTERWR /MOUNT
```

Close all applications/handles on S: first. Unmount commits and checks enabled
FAT mirrors before publishing a clean volume. Mount performs full preflight.
A failed mount/transport operation leaves the drive offline; the TSR remains
loaded. Old handles/searches cannot silently resume against a replacement card.

## Writes and durability

Each written 512-byte sector receives a CRC, bounded busy/status checks,
CRC-checked readback and an exact comparison with the frozen intended bytes.
Recovery allows at most three total attempts at the same sector, only after
card identity and usable reads have been established. An unresolved failure
poisons the session and prevents further writes. CRC checks remain enabled.

Ordinary file close finishes verified data/metadata writes and releases its
handles/locks. It leaves the volume dirty instead of scanning both entire FATs
on every close. Explicit DOS commit, global flush and successful `/UNMOUNT`
still compare complete enabled mirrors before publishing clean state. Always
unmount successfully before shutdown/removal. An abruptly interrupted writable
session can require external inspection/repair; the driver refuses a dirty
volume and does not silently clear its dirty flag.

Verified sector writes do not make multi-sector FAT operations transactional.
Mount checks geometry, capacity, backup boot, relevant FAT flags/mirrors and
FSInfo signatures; it does not perform a complete allocation/crosslink scan.

## Platform and scope

Target: 8088/8086 and MS/PC-DOS 3.1 through 6.x, SDHC/SDXC, FAT32, 512-byte
sectors. No 286-only instructions, EMS, XMS, DMA or interrupt line are required.
The current allocation is **36,624 bytes** of conventional RAM including PSP,
in either access mode. The private callback stack remains 2,048 bytes; there
are 16 open-file slots and 32 search cursors. DOS FILES/process limits also
apply. DOS 5/6.22 with 1 MiB emulated RAM are the qualification kernels. Physical
5150/8088 and DOS 3/4 testing remain deferred; a 1 MiB 286 is the immediate target.

Files use short names or existing 8.3 aliases. Supported writes include creation,
overwrite/append, gap zeroing, truncate/extend, deletion, attributes/timestamps,
directory creation/removal and cross-directory moves. Handle sharing, duplicates
and region locks are implemented. GPT, extended partitions, SDSC, FAT12/16,
exFAT, LFN creation and general DOS server/network functions are outside scope.
Standard FCB wildcard deletion is tested; FCB record I/O/abort lifecycle is not.

## Build, qualify and test a card

Turbo C 2.0 and TASM 2 are supplied separately in `buildenv`, or through
TOOLCHAIN_DIR. DOSBOX_BIN chooses the compiler emulator. Python 3, GCC/gcov,
mtools and dosfstools support the host gates and packaging.

```sh
bash driver/build.sh /tmp/otter-build
python3 driver/rwhardware/build.py --output /tmp/otter-build
python3 driver/validate.py --output /tmp/otter-check
python3 driver/validate.py --full --output driver/dist \
  --dosbox /path/to/dosbox-with-isa-model \
  --boot-image /path/to/dos5.img --boot-image /path/to/dos622.img
```

The first validation command runs host regression, coverage and mutation gates,
builds both programs and creates a candidate kit. `--full` additionally boots
actual DOS for read-only/CLI/EXEC/swap tests, write fault profiles, tester guards,
and the exact final image with stress/memory/reboot and independent contents/fsck
checks. Artifacts and complete gate logs are kept in the selected output.
Boot/compiler images and emulator executables are not redistributed.

The distributable is `driver/dist/RESWRITE.IMG` and `RESWRITE.ZIP`. Follow the
[hardware manual](rwhardware/MANUAL.md) for Navigator copying and a fresh per-card
run. HWRT records CID, capacity, versions, source identifier, timings, progress
and diagnostics. Save separate logs for every card; old successful runs do not
qualify the new binary. The tested baseline and older hardware/write kits remain
archived in their existing directories. `build-rw.sh` is a compatibility alias;
`tests/legacy-build.sh` exists only for historical read-only comparisons.

## Source layout

| File | Responsibility |
|---|---|
| INSTALL.C / INSTALL.H | Far installation/control code, discarded after loading |
| BOOT.C / CRT.C | Retained bootstrap and CRT/far call gates |
| ENTRY.ASM | 8086 interrupt bridge, private stack, resident boundary |
| REDIR.C / RWOPS.C / RWDIR.C | DOS redirector, handles, locks and writable callbacks |
| FAT32.C / RWFS.C | Read traversal, writable FAT/directory operations |
| SDRW.C / RWSD.H | CRC, identity, bounded recovery and verified sector transport |
| PORTBODY.H | Shared bounded option parser, exhaustively tested |
| installer_segments.py / tests/layout.py | Discarded-segment and startup reserve proofs |
| rwhardware/HWRT.C / RWCHILD.C | Single tester including private self-exec child mode |

See [memory measurements](MEMORY.md), [source conventions](CODING.md),
[DOS ABI notes](DOSREF.md) and [consolidation record](CONSOLIDATION.md).
