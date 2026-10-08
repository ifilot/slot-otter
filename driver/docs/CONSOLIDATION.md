# Current driver consolidation

The active programs are **OTTERSD.EXE 1.0.0** and developer **HWRT.EXE 1.0.0**. One
standalone `build.sh` builds both; neither depends on Navigator or `src`.
The driver supports FAT16 and FAT32, read-only and verified read/write modes,
optional write-readback suppression, optional mount-time FAT comparison
suppression, and guarded full unloading.

## Active tree

| Location | Purpose |
| --- | --- |
| Root C, H and ASM files | Driver, installer and single hardware tester |
| `docs/` | Deployment, implementation, measurements and historical reviews |
| `tests/` | Unit, mutation, native DOS, XCOPY and image qualification |
| `tests/reference/` | Independent historical routines still exercised by tests |
| `tests/emulation/` | Shared SD model and DOSBox/86Box adapters |
| `logs/` | User-supplied per-card hardware evidence |
| `dist/` | Developer qualification artifacts and public RELEASE assets |

There are no active `hardware/`, `write/`, `rwhardware/` or top-level
`emulation/` product folders, old executable targets or alternate driver builds.
The reference code is test input, not a second public program. Benchmark and
internal DOS probes remain useful tools and are not included in the DOS KIT.

## Public release 1.0.0

OTTERSD is the primary software product. Public packages in `dist/RELEASE`
contain only the driver and end-user instructions; SD images are empty.
The recommended image is 500 MiB FAT16 with 16 KiB clusters. OTTERNAV remains
legacy software; Nightwatch is the recommended file manager. See
[INSTALLATION.md](INSTALLATION.md). The testing products below are developer
kits and are not uploaded as GitHub release downloads.

## Developer kit

Resident allocation is **42,896 bytes including the PSP**, in both access
modes. The 2,048-byte private stack, 16 open handles and 32 searches remain.
Sequential writable-mode reads retain per-handle cluster positions. Four FAT
sectors and two directory sectors are cached independently of file payload.
Stores invalidate matching sectors and retained positions; mutation preflight
uses fresh evidence. Writes remain synchronous and verified by default.

Three images contain the same driver and tester binaries:

| Release directory | Image | Filesystem and physical cluster size |
| --- | --- | --- |
| `dist/` | `OTTERSD.IMG` | Small FAT32 stress fixture, 512-byte clusters |
| `dist/FAT16/` | `OTTER16.IMG` | 500 MiB FAT16, 16 KiB clusters |
| `dist/500M/` | `OTTER500.IMG` | 500 MiB FAT32, 4 KiB clusters |

Physical sectors remain 512 bytes. DOS capacity reporting may expose larger
logical allocation units; it does not alter the image's physical clusters.
Use [MANUAL.md](MANUAL.md) for deployment and the per-card test procedure.

## Validation and hardware feedback

The released 0.15 build passed 334 host tests, 145 behavioral mutations and
two native assembly mutations. The main qualification records 57 gates; the
two 500 MiB images each passed 14 additional exact-image DOS gates. They cover
DOS 5/6.22, faults, XCOPY, unload/reload, memory pressure, fresh-boot persistence,
byte comparisons and independent filesystem checking. Exact outcomes and
source/binary hashes are in each release's `EVIDENCE/QUALIFICATION.JSON`.
Independent native jobs and mutation groups default to eight workers.

The user reported that the 0.15 update is working smoothly on hardware.
That is useful feedback, but it does not supply new per-card log counts or
qualify an 8088/5150; that hardware run remains deferred. Preserve new card
logs separately under `logs/` and identify the binaries tested.

## Cleanup and release boundaries

Removed the stray `tests/PROBE.EXE`, `tests/PROBE.OBJ` and regenerable Python
bytecode caches. Historical versions previously presented as current in the
memory/recovery/evidence notes are now explicitly identified. Obsolete release
archives and superseded notes have been removed from the source repository.
Original physical-card logs remain under `logs/historical/`.

The preceding documentation-only cleanup changed no implementation files. The 1.0.0
promotion separately updates version IDs and release packaging; its outcomes
are recorded by the new qualification run.

`dist/` is an ignored, generated output directory, not part of the source
repository. Build and qualification tools recreate its images, binaries,
coverage and evidence records. GitHub Actions publishes public packages as
artifacts and release downloads. Keep evidence with the release it qualifies;
do not commit generated kits, disk images or historical ZIP snapshots.
