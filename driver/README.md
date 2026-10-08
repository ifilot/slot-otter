# OTTERSD: standalone DOS SD driver

The primary product is `OTTERSD.EXE` 1.0.0, its first stable release. The single executable supports verified
read/write operation with `/RW`, or read-only operation with `/RO` (the default).
The developer hardware tester is `HWRT.EXE` 1.0.0. Both programs and all source are
under `driver`; neither depends on Navigator or `src` after installation.

Version 0.15 retains sequential read cursors under `/RW`, caches four FAT
sectors and two directory sectors independently of the payload buffer, and
invalidates retained cursors before any filesystem store. Directory refreshes
still authenticate the card; mutation proofs still receive fresh evidence.
The resident allocation is 42,896 bytes including PSP, 3,408 above 0.14.
Raw-sector tools and Navigator require unmounting before changing the card.

Version 0.14 writes regular-file data directly into newly allocated clusters,
without first zeroing the whole cluster. File reads stop at EOF; gaps and
explicit extensions still receive zeros, and directory allocation still clears
its clusters. Write verification remains enabled by default. Resident memory
was 39,488 bytes including PSP, 32 bytes above 0.13.

Version 0.13 adds FAT16 alongside FAT32 with automatic detection. `/FAT16`
and `/FAT32` optionally restrict the installed driver's accepted format.
They do not format or convert media. The new [500 MiB FAT16 kit](docs/FAT16_IMAGE.md)
uses 16 KiB physical clusters; the existing FAT32 kits remain supported. The
0.13 resident allocation was 39,456 bytes including PSP, 1,088 more than 0.12.

Version 0.12 reduces repeated card-identity commands inside a complete chain
audit, authenticating both audit boundaries and retaining checks around writes.
CRC tables and validated cluster shifts reduce CPU work without changing the
8088 target or SPI pacing. Matching-sector cache invalidation avoids discarding
unrelated cached sectors. The driver retains 38,368 bytes, 800 more than 0.11.
Writes remain synchronous and verified by default. FSInfo handling is unchanged.
See [the implementation and test details](docs/PERFORMANCE.md#ottersd-012).

Version 0.9 scales DOS disk-space counts using larger logical allocation units,
so a 500 MiB volume with 4 KiB physical clusters is reported accurately.
Both total and free counts round down, with less than one logical unit lost.
The physical FAT32 geometry is unchanged. Synthesized units stop at 32 KiB;
volumes above approximately 2 GiB still saturate the legacy DOS interface.

Version 0.8 restored the complete 0.6 C SD transport after a reported mounting
failure with 0.7. The filesystem traversal improvements and
assembly far memory copies remain. Emulation checks the recovery build; physical
confirmation is pending. Later hardware evidence showed a separately formatted
FAT32 card failed at sector 0 while the supplied image mounted; a format/layout
rejection is now the leading explanation. See [recovery instructions](docs/RECOVERY.md).

Version 0.11 adds `/SKIPFATCHECK` for faster writable mounting. It skips the
full FAT-copy comparison at mount, while retaining a first-sector comparison,
geometry/backup/clean/error/FSInfo checks, comparisons before FAT mutations,
and full dirty-session commit checks. Strict mounting remains the default.
The option requires `/RW`; `/RO` already avoids the full mount comparison.
Use `/STATUS` or `HWRT /INFO` to record the policy. See the
[fast-mount instructions](docs/MANUAL.md#optional-faster-mounting).

Version 0.10 adds safe `/UNLOAD` to reclaim the entire resident allocation
before memory-hungry games. `/UNMOUNT` still keeps the driver for quick remounts.
See the [game/unload procedure](docs/MANUAL.md#reclaim-memory-before-running-a-game).

## Install and use

Merge these settings into your boot disk's CONFIG.SYS and reboot:

```dos
LASTDRIVE=S
FILES=40
BUFFERS=10
```

From a local disk, install on an unused letter:

```dos
OTTERSD /DRIVE:S /PORT:330 /RW
OTTERSD /STATUS
DIR S:\
```

`/PORT:` is hexadecimal and defaults to 330. Use `/RO` instead of `/RW` for
read-only access. Access mode is fixed at installation; reboot to change it.
This is a TSR filesystem redirector, not a CONFIG.SYS DEVICE driver or MSCDEX
extension. Repeated installation is rejected. Installation can leave the drive
offline when no usable card is present; insert a card and run `/MOUNT`.

Before card removal, reboot, or Navigator use:

```dos
OTTERSD /UNMOUNT
REM Only after successful unmount: remove/reinsert card or reboot.
OTTERSD /MOUNT
```

Close all applications/handles on S: first. Unmount commits and checks enabled
FAT mirrors before publishing a clean volume. Mount performs full preflight.
A failed mount/transport operation leaves the drive offline; the TSR remains
loaded. Old handles/searches cannot silently resume against a replacement card.

## Writes and durability

By default each written 512-byte sector receives a CRC, bounded busy/status checks,
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

`/RW /NOVERIFY` is an installation-only opt-in that omits post-write sector
readback and exact comparison. It keeps outgoing CRC, accepted-response checks,
busy completion, CMD13 status, card identity and bounded recovery (including its
CRC-checked read). It can acknowledge silently incorrect data. It requires /RW,
cannot be combined with /RO or a control command, and stays fixed until reboot.
Installer, /STATUS and HWRT report the policy. The legacy diagnostic `verified`
counter means completed sector calls in either mode.

The writer reuses the reader's existing FAT cache and checks card identity even
on hits. Fresh mutation validation and all sector stores invalidate caches.
Linear cycle detection checks complete chains without alternating distant FAT
sectors. Full-sector replacements avoid reading bytes they replace; partial
writes still merge the previous contents. Matching timestamps need no extra
metadata write. The complete validation walk also supplies logical EOF, and
overwrites walk forward within a call. Far memory copying uses 8086 assembly;
SD packets and CRC use the restored 0.6 C routines. No deferred writeback or
additional cache buffer is introduced.
See the [copy performance assessment](docs/PERFORMANCE.md).

Verified sector writes do not make multi-sector FAT operations transactional.
Mount checks geometry, capacity, backup boot, relevant FAT flags/mirrors and
FSInfo signatures; it does not perform a complete allocation/crosslink scan.

## Platform and scope

Target: 8088/8086 and MS/PC-DOS 3.1 through 6.x, SDHC/SDXC, FAT16/FAT32, 512-byte
sectors. No 286-only instructions, EMS, XMS, DMA or interrupt line are required.
The current allocation is **42,896 bytes** of conventional RAM including PSP,
in either access mode. The private callback stack remains 2,048 bytes; there
are 16 open-file slots and 32 search cursors. DOS FILES/process limits also
apply. DOS 5/6.22 with 1 MiB emulated RAM are the qualification kernels. Physical
5150/8088 and DOS 3/4 testing remain deferred; a 1 MiB 286 is the immediate target.

Files use short names or existing 8.3 aliases. Supported writes include creation,
overwrite/append, gap zeroing, truncate/extend, deletion, attributes/timestamps,
directory creation/removal and cross-directory moves. Handle sharing, duplicates
and region locks are implemented. GPT, extended partitions, SDSC, FAT12,
exFAT, LFN creation and general DOS server/network functions are outside scope.
Standard FCB wildcard deletion is tested; FCB record I/O/abort lifecycle is not.

## Build, qualify and test a card

Turbo C 2.0 and TASM 2 are supplied separately in `buildenv`, or through
TOOLCHAIN_DIR. DOSBOX_BIN chooses the compiler emulator. Python 3, GCC/gcov,
mtools and dosfstools support the host gates and packaging.

```sh
bash driver/build.sh /tmp/otter-build
python3 driver/validate.py --output /tmp/otter-check
python3 driver/validate.py --full --output driver/dist \
  --dosbox /path/to/dosbox-with-isa-model \
  --boot-image /path/to/dos5.img --boot-image /path/to/dos622.img
```

The first validation command runs host regression, coverage and mutation gates,
builds both programs and creates a candidate kit. `--full` additionally boots
actual DOS for read-only/CLI/EXEC/swap tests, write fault profiles, tester guards,
genuine licensed XCOPY from a BIOS hard drive at two cluster sizes/policies,
and the exact final image with stress/memory/reboot and independent contents/fsck
checks. Artifacts and complete gate logs are kept in the selected output.
Full XCOPY gates need XCOPY.EX_ in each boot image and EXPAND.EXE in one of them
or in --xcopy-expand-media. Boot/compiler images, XCOPY and emulator executables
are supplied separately and are not redistributed.

The small stress-image distributable is `driver/dist/OTTERSD.IMG` and `OTTERSD.ZIP`.
The alternative 500 MiB image with 4 KiB clusters is in `driver/dist/500M`;
see [large-image instructions](docs/LARGE_IMAGE.md). Follow the
[hardware manual](docs/MANUAL.md) for Navigator copying and a fresh per-card
run. HWRT records CID, capacity, versions, source identifier, timings, progress
and diagnostics. Save separate logs for every card; old successful runs do not
qualify the new binary. Original physical-card logs are kept in
`driver/logs/historical`; new per-card logs belong in `driver/logs/<card-name>`.
Old release snapshots and generated outputs are not kept in the source repository.

There are four functional subfolders: `docs` for the manual/ABI/memory notes,
`tests` for unit/native/fault tests and emulator/reference infrastructure,
`logs` for future per-card evidence, and `dist` for the current release.
`tests/kit_fixture.py` is the sole shared kit fixture builder. Legacy protocol
code is retained only as host regression/reference input in `tests/reference`;
it has no public build target or distributed executable.

## Source layout

| File | Responsibility |
|---|---|
| INSTALL.C / INSTALL.H | Far installation/control code, discarded after loading |
| BOOT.C / CRT.C | Retained bootstrap and CRT/far call gates |
| ENTRY.ASM | 8086 interrupt bridge, private stack, resident boundary |
| REDIR.C / RWOPS.C / RWDIR.C | DOS redirector, handles, locks and writable callbacks |
| FAT32.C / RWFS.C | Read traversal, writable FAT/directory operations |
| SDRW.C / RWSD.H | Identity, bounded recovery and verified sector transport |
| FASTIO.ASM | 8086 normalized far memory copies |
| PORTBODY.H | Shared bounded option parser, exhaustively tested |
| installer_segments.py / tests/layout.py | Discarded-segment and startup reserve proofs |
| HWRT.C / TESTCHLD.C | Single tester including private self-exec child mode |

See [memory measurements](docs/MEMORY.md), [source conventions](docs/CODING.md),
[DOS ABI notes](docs/DOSREF.md) and [consolidation record](docs/CONSOLIDATION.md).


## Public release packaging

Use [INSTALLATION.md](docs/INSTALLATION.md) for end-user instructions.
Nightwatch (https://github.com/ifilot/nightwatch) is the recommended file
manager. Navigator in ../src is legacy software.

`release.py` builds the public DOS ZIP, three installation floppy sizes,
and empty 500 MiB FAT16/FAT32 SD images. The recommended public image is
FAT16 with 16 KiB clusters. It never imports developer fixture builders.
Floppies and the DOS ZIP contain OTTERSD.EXE, user instructions, a CONFIG.SYS
example and the license; no HWRT or other test utilities are included.
Empty SD images contain no KIT directory, fixtures or authorization markers.

    python3 driver/release.py --driver /path/to/OTTERSD.EXE \
      --output /path/to/new-public-output

Generated local public assets can be placed under `driver/dist/RELEASE`.
The entire `driver/dist` directory is ignored by Git and is created by the
build/qualification tools; it is not supplied by cloning this repository.
The other generated dist files are
explicitly DEVELOPER hardware kits, with fixtures and HWRT; they are not GitHub
release downloads. The public builder refuses existing output directories and
checks each floppy's exact file allowlist, SD geometry, FAT mirrors, root
contents, backups/FSInfo and fsck results. SHA256.TXT identifies public assets.
GitHub Actions runs host coverage/mutations once as a reusable workflow, builds
the standalone binaries and uploads only release.py's public output. Tagged
releases require a tag matching RWSD.H's version, currently v1.0.0. OTTERNAV
is built separately and is attached as an optional legacy executable.

RWSD.H defines the displayed semantic version and the resident 16-bit version
ID: major in the high byte, minor/patch in the low nibbles. The query ABI and
structure sizes remain unchanged. Matching developer HWRT rejects old drivers.
