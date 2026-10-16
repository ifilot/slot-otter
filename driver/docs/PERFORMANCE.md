# Read/write performance assessment

## OTTERSD 0.12

The production build adopts the tested 0.11-review candidates: authentication
at both boundaries of a complete chain audit, byte CRC tables, power-of-two
cluster shifts/masks, and matching-sector cache invalidation. Public warm-cache
FAT access, fresh mutation proofs, full chain validation, pre/post-write checks,
frozen retry payloads, and error poisoning remain. Physical SPI pacing is
unchanged. There is no write-back cache or FSInfo/free-count caching change.

The 400 KiB synthetic append at four-KiB clusters performs 5,990 CID commands
instead of 15,592, with unchanged 3,295 reads and 2,198 writes. These are actual
model commands, not a hardware throughput prediction. The review's genuine
DOS XCOPY comparison was 81 versus 79 BIOS ticks, too small a single-run
difference to establish a substantial copy speedup.

The current target remains 8088/8086, real-mode DOS, with a single executable
for newer CPUs too. Resident allocation is 38,368 bytes. Separate CPU variants,
multi-block SPI, persistent writable cursors, and direct new-cluster payload
initialization remain future work; no untested zero-initialization shortcut
enters this release.

Permanent tests independently divide CRC polynomials, inject card removal and
replacement during cached audits, check selective cache invalidation, and
exercise reading/appending across 64 KiB at every supported cluster size.
Mutation tests require these guards to catch a missing exit check, bad CRC7,
truncated 64-KiB mask, and excessive identity traffic.

For a first hardware run, use matching OTTERSD 0.12/HWRT 0.10 from one kit.
Use verified `/RW` first, then `HWRT /INFO`, `HWRT /TEST /ERASE`, and fresh-boot
`HWRT /VERIFY` as described in MANUAL.md. Save each card's logs separately.
Compare a timed XCOPY of the same local 400 KiB file with the previous version,
on the same card and image, with the same verification/mount options. Record
elapsed time, DOS version, CPU, and card identity; separate install time from
copy time. The emulation result does not promise a physical improvement.

The historical [review](PERFORMANCE_011_REVIEW.md) and its archived sources
retain the experimental measurements before production promotion. Full current
release qualification is recorded in the distributed EVIDENCE directory.

## Earlier 0.6 iteration

The user measured roughly five minutes for a 400 KiB HDD-to-SD copy on physical
hardware. That observation does not identify the card programming time versus
CPU/ISA/metadata work; emulator seconds are not a hardware prediction.
Three read-only reviewers examined transport, filesystem and XCOPY testing.
Root alone changed files.

The old writable traversal bypassed the existing FAT cache and reread a whole
512-byte sector for each link. Each append validated the full growing chain,
then located EOF; updating metadata validated it again. The cycle check also
alternated distant slow/fast links, causing a one-sector cache to thrash.
Each received byte requires OUT plus two settling IN accesses and a final IN;
CRC calculation, command framing and identity checks add CPU/ISA work. There
is no intentional per-success BIOS-tick delay. Busy/status waits end when ready.

A host byte-level SPI measurement copied exactly 409600 bytes in one hundred
4096-byte appends with refresh and metadata publication on each call:

| Build | Sector reads | Sector writes |
|---|---:|---:|
| 0.5 | 250397 | 5003 |
| 0.6, readback enabled | 11550 | 5003 |

This is a 95.4% reduction in receives for that workload. It is not a throughput
multiplier: writes, CID commands, CPU costs and real card busy time remain.
Genuine DOS5 XCOPY at the same nominal fixed emulator cycles copied 400 KiB
in 634 BIOS ticks with 0.5 and 270 with 0.6. These preliminary comparative
runs are not physical speed measurements; complete qualification retains each
DOS/geometry/policy run's actual ticks and source/binary hashes.

The new traversal reuses FAT32.C's existing FAT buffer. Every writable FAT
lookup still authenticates media, including cache hits. Mutations begin with
fresh cache evidence; stores and mount/offline paths invalidate it. Brent cycle
detection counts and validates all links in a single forward traversal, with
constant memory. Aligned full-sector replacements omit the preimage receive;
partial writes preserve surrounding bytes. The DOS writer avoids an additional
metadata mutation when archive attribute and time/date already match. Writes
remain synchronous. No writeback queue or extra 512-byte cache was added.

From 0.14, regular-file allocation reserves a cluster without clearing its
contents. Appends write only incoming bytes before publishing the new file
size; bytes beyond EOF remain inaccessible through file reads. Gap writes and
explicit extensions initialize newly visible bytes to zero, including reused
clusters and truncated file tails. Directory allocation still clears clusters
before linking them because directories do not use a byte-size bound.
This removes one complete cluster write and, with verification enabled, one
complete cluster readback from each regular-file allocation. All payload writes
retain the selected verification policy. Smaller DOS write requests no longer
require initializing the rest of the allocated cluster.

/RW /NOVERIFY skips only successful post-write CMD17 readback and comparison.
It retains CRC, accepted response, busy completion, CMD13, identity, the armed
range, three total frozen-payload attempts and CRC-checked recovery reads.
Recovery can overwrite shared scratch; successful unverified retries explicitly
restore the frozen input. The option can acknowledge silently corrupted data:
an injected accepted/clean-status corruption passes this mode and fails later
independent comparison. Default mode detects it and retries/stops. CRC and
status alone cannot provide the same evidence as exact readback.

Native XCOPY tests use separately supplied licensed DOS tools on a private BIOS
FAT16 HDD. They copy a 400 KiB file, zero/sector/cluster/64 KiB boundary sizes,
30 files, nested and empty directories; check both policies and read-only
refusal; compare all bytes, timestamps/attributes; reboot and copy back; and
check the filesystem independently. DOS5's empty-directory traversal can leave
exit=1 on both HDD-only and SD copies; the tests require matching control codes
and exact independent contents rather than hiding arbitrary failures.

Remaining opportunities include reducing repeated full-chain work across DOS
calls and a measured assembly byte-transfer loop retaining settling accesses.
Both require further correctness/hardware evidence. Deferred writeback and
removing per-lookup media authentication are intentionally larger changes.


## Second audit, 0.7 / HWRT 0.5

Three read-only reviewers audited packet/CRC work, filesystem traversal and
DOS callbacks, then checked the implementation. Root alone edited sources.
The following records the historical 0.6 qualification and subsequent audit.
Old release ZIP snapshots are no longer stored in the source repository.

The selected changes preserve synchronous ordering and complete fresh proofs:

- Counted 8086 packet loops load the port and buffer once. Every transferred
  byte still performs one OUT and all three settling/sample IN accesses.
  Interrupts remain enabled and C's preserved registers remain intact.
- Table-free assembly CRC16 uses equivalent byte arithmetic instead of costly
  wide shifts. Zero-argument CMD10/CMD13 use their exact constant framing CRC7;
  other commands and arguments retain the general CRC7 routine.
- Normalized far memory copying uses REP MOVSW plus an odd-byte tail, preserving
  segment registers and handling the existing DOS buffers crossing 64 KiB.
- Full chain validation captures logical EOF while continuing through any
  surplus allocation. Append reuses this result instead of walking again.
- Overwrite locates its first cluster once and follows links only at boundaries.
  No position/proof survives the operation. The allocation scan supplies its
  fresh primary FAT sector to the existing mirror comparison/store logic.

A reproducible host workload in tests/performance.py counts actual SPI commands
for 100 x 4 KiB appends, reads and a final 4 KiB overwrite. Timed appends exclude
initial file creation; 4,998 sector writes remain in both builds at SPC1.

| 512-byte clusters | 0.6 | 0.7 |
|---|---:|---:|
| Append 400 KiB, identity commands (CMD10) | 136848 | 96107 |
| Append 400 KiB, sector reads (CMD17) | 11550 | 10310 |
| Final 4 KiB overwrite, identity commands | 7253 | 1639 |
| Final 4 KiB overwrite, sector reads | 81 | 32 |

Portable host tests use C transport/copy references, so these counts measure
filesystem work; they cannot measure native assembly speed. Preliminary actual
DOS5 XCOPY measured about 270 BIOS ticks for verified 0.6 and 177 for the new
transfer/traversal code at the same nominal emulator cycles. The release gates
retain the final build's timings for both directions and access modes. These
are emulator comparisons, not physical time predictions.

Native FASTTEST directly tests the actual assembly with all 65,536 two-byte
CRC vectors, packet lengths, odd addresses/counts, guard bytes and register/DF/IF
sentinels. It writes and restores a private reserved sector with strict CRC
and a three-register-access delayed burst model. Deliberately broken CRC,
odd-tail copying, reversed copy direction and receive settling must each fail. Ordinary resident DOS
API/fault/64-KiB-buffer and all-free-memory tests still run separately.
XCOPY now also reads back under the existing writable mount, with no SD writes,
before the fresh-boot read-only copy. Both filesystem images and file metadata
remain independently checked.

The resident allocation is 36,992 bytes, 208 more than 0.6, without new buffers
or tables. To retain the 37,000-byte ceiling, the lower-priority local LFN scan
cache is deferred. Persistent writable read cursors are also deferred: unlike
RO, RW currently refreshes metadata and restarts at the chain head on each read,
and same-size external FAT relinks require a clear invalidation contract.
Power-of-two geometry arithmetic and repeated path resolution remain possible
future work. Default exact readback, /NOVERIFY's limits and all media/recovery
checks are unchanged. Physical testing must confirm the tighter elapsed ISA
spacing despite preservation of every required I/O access.

## Recovery, 0.8 / HWRT 0.6

Real hardware failed to mount with 0.7, including a freshly formatted card.
The reported command was OTTERSD /DRIVE:S /PORT:330 /RW /NOVERIFY; the SD phase
reported one BIOS tick and the filesystem phase zero. The timing is consistent with an early initialization/identity-read failure,
but zero filesystem ticks can also mean less than one 55-ms tick. Exact
command/response diagnostics are still needed to distinguish the failing stage; tighter elapsed I/O spacing is a
hypothesis, not a demonstrated root cause. /NOVERIFY does not change any
initialization/read/CRC behavior and cannot explain this failure by itself.

Version 0.8 restores SDRW.C byte-for-byte from the last working 0.6 release:
C packet loops, C CRC16 and general command CRC7. FASTIO.ASM now contains only
far memory copying. The full-chain/logical-EOF, forward overwrite and allocation
sector reuse optimizations remain. No automatic speed probing or unverified
fallback write is introduced. This removes the entire suspect SD transport
change, rather than guessing how much additional delay to insert.

Failed installation and /MOUNT, plus /STATUS, now print the retained SD error,
stage, LBA in hexadecimal, R1, token, status, poison and attempts. These are
installer/control-only strings and code, released after execution. Native
regressions inject a missing CMD0 response, rejected CMD10 and corrupt CID CRC, with readback
both enabled and disabled, and require the same evidence through installation,
status, remount and HWRT /INFO without a single SD mutation.

The 0.7 release and its emulation measurements remain archived as historical
evidence; its assembly throughput gains do not apply to the recovery build.
The resident footprint is 36,944 bytes. Emulation qualification does not
confirm the physical fix; follow RECOVERY.md for a non-writing first check.

Later hardware evidence: the user reported a separately formatted FAT32 card
failing with SD error=0, stage=17, LBA=0, R1=00, token=FE, while the supplied
whole-disk image mounted successfully. The mount parser and writable preflight
are unchanged from 0.6. Format/layout or boot-sector validation is now the
leading explanation; GPT is a hypothesis pending partition inspection. The
early transfer-code regression diagnosis is withdrawn as unproven. Version
0.8 conservatively restores the known 0.6 transport and adds clearer retained
SD evidence; it does not claim to repair or support an unidentified layout.

## Read traversal and metadata caches, 0.15

The read path keeps one payload sector, four FAT sectors and two directory
sectors in separate synchronous caches. `/RW` retains a cursor per open handle.
Before any attempted filesystem store, a global 32-bit generation advances;
all retained cursors become stale, including other handles and other files.
An exhausted generation permanently disables retention to prevent wrap from
matching a dormant handle. Card changes invalidate the mounted filesystem.
Shared-file metadata still refreshes on each DOS request through the directory
cache with a current card-identity check. Matching sector stores invalidate
all copies of that sector before writing, even if a write subsequently fails.
Mutation proofs still discard caches and read fresh evidence. Cached read
positions are not retained write-validation proofs. Unmounting is required
before external raw-sector edits or Navigator changes the card.

For an exact 400 KiB file read through DOS callbacks in 4 KiB requests, the
archived 0.14 and candidate 0.15 use the same byte-level card model and fixtures:

| Work | 0.14 | 0.15 |
| --- | ---: | ---: |
| FAT16 / 16 KiB clusters: sector reads | 901 | 802 |
| FAT16: FAT lookups | 1,200 | 24 |
| FAT32 / 512-byte clusters: sector reads | 1,348 | 809 |
| FAT32: FAT lookups | 40,300 | 799 |

Neither run performs any SD writes. These counts demonstrate avoided work,
not hardware throughput; they do not remove payload transfer, CRC, card-identity
or destination-disk costs. Interleaved reads of files in two directories also
avoid repeated directory-sector transfers. Multi-block SD commands, read-ahead
and larger payload caches remain deferred.

Qualification defaults to eight independent emulator jobs and mutation groups.
The complete host suite runs once before mutation checks; standalone invocation
of mutations.py still runs it unless its caller supplies --skip-suite. Builds,
packaging and evidence publication remain ordered dependencies. Runtime tests
use the normal DOSBox core and a fixed 3,000,000-cycle execution budget, except for
the legacy read-only floppy harness and native CRC/ABI probe, which use
300,000 (the read-only harness formerly used 15,000).
DOS 6.22 exceeds this harness's 45-second boot deadline at 3,000,000; a
standalone run with a longer deadline passes, and 300,000 completes promptly. These budgets are not XT clock rates or cycle-exact
hardware timing. Fault models retain their register-access delays and
BIOS-tick timeout cases, which are exercised by the full validation run.

The public release integration harness also uses a 300,000-cycle budget.
It checks empty production volumes with the public floppy binary; its elapsed
time is qualification evidence, not a hardware throughput prediction.
