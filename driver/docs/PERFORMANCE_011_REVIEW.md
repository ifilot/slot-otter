# Performance review of OTTERSD 0.11

Reviewed on 2026-10-07 with three independent, read-only reviewers covering
filesystem work, SPI transport, and CPU instructions. The coordinating agent
alone created experimental source copies and ran the checks.

Scope: read/write performance and CPU variants. FSInfo/free-space caching,
FAT16 support, and changes to the shipped image geometry were excluded.
The released driver, tester, images, and ZIP kits have not been replaced.

## Recommended order

1. Reduce repeated CID commands during a single complete chain audit.
2. Replace general division/modulo by validated cluster shifts and masks;
   use CRC tables if the additional resident memory is acceptable.
3. Initialize newly allocated clusters directly with incoming file data,
   zeroing only bytes outside that data, before linking or publishing them.
4. Consider writable sequential cursors and a larger FAT cache only after
   defining their invalidation and external-change rules.
5. Reassess CPU-specific assembly and multi-block SPI after the above changes.

Items 1 and 2 have tested private prototypes. Item 3 is a design opportunity,
not an implemented or qualified optimization. None is a hardware speed claim.

## Measured command traffic

The existing performance harness appends 400 KiB using 100 callbacks of
4096 bytes, each with refresh, append, and metadata publication. Both versions
use the same fixtures, CRC policy, verified writes, and actual byte-level SPI
model. Four-KiB clusters mean eight 512-byte sectors per physical cluster.
These fixtures are not the exact shipped 500 MiB image.

| Four-KiB-cluster workload | Released 0.11 | Combined audit prototype |
|---|---:|---:|
| Append: CMD10 identity commands | 15,592 | 5,990 |
| Append: CMD17 sector reads | 3,295 | 3,295 |
| Append: CMD24 writes | 2,198 | 2,198 |
| Append: CMD13 status commands | 2,198 | 2,198 |
| Writable sequential read: CMD17 | 901 | 900 |
| Read-only sequential cursor: CMD17 | 801 | 801 |
| Overwrite last 4 KiB: CMD10 | 217 | 119 |

For the deliberately small 512-byte-cluster fixture, append CID commands fell
from 96,107 to 16,505. Sector read/write counts remained unchanged. CID traffic
is therefore an avoidable cost distinct from payload and verification traffic.
The writable reader is already close to the 800-sector payload minimum on the
four-KiB-cluster fixture; a substantial read speed gain needs CPU or transfer
improvements rather than simply a larger data cache.

The audit prototype checks identity at chain-audit entry and successful exit.
Physical FAT-cache misses still use authenticated sector reads. Public
`rw_fat()` retains its warm-cache identity check. Each mutation still begins
with fresh cache evidence; full-chain validation, surplus/cycle detection,
pre/post-write checks, retry recovery, and poisoning remain in place.

Targeted injection after either link of a two-link chain tested removal and
replacement while the FAT sector was cached. All four cases returned DOS
error 21 before any write; original and replacement images remained unchanged.
This does not prove detection of every possible physical hot-swap sequence.

Selective invalidation alone made little difference: on the small-cluster
overwrite fixture it saved seven reads, and on the four-KiB-cluster writable
read it saved one. It does not justify a broad caching rewrite by itself.

## CPU work without abandoning the 8088

The compiler emits 32-bit division/modulo helpers for variable cluster
geometry. Cluster sizes are already validated powers of two. A cached shift
and masks avoid those helpers, including on the original 8088 target. Masks
must use 32-bit arithmetic: 128 sectors per cluster represents 64 KiB.

CRC tables replace bit loops without changing SPI commands, checksums,
verification, retries, or the existing OUT/two-settling-IN/final-IN sequence.
The experiment uses a 512-byte CRC16 table and a 256-byte CRC7 table.

An isolated native benchmark booted genuine MS-DOS 5, normal emulator core,
fixed 5000 cycles, with no SD I/O. Checksums matched between versions:

| Primitive | Work | Baseline BIOS ticks | Candidate BIOS ticks |
|---|---|---:|---:|
| CRC16 | 262,144 bytes | 28 | 21 |
| CRC7 | 32,768 command frames | 58 | 13 |
| Cluster/sector arithmetic | 32,768 positions | 99 | 7 |

These are individual CPU workloads, not whole-copy speedups or cycle-accurate
5150 measurements. Combined CPU/cache changes used 38,320 resident bytes,
versus 37,568 released bytes. Adding audit-boundary checks brought the complete
prototype to 38,368 bytes: an 800-byte increase. It exceeds the current release
packaging ceiling and is deliberately not a replacement release.

Genuine DOS XCOPY of a 400 KiB file with verified writes took 81 ticks with
released 0.11, 80 with CPU/cache changes, and 79 with audit scoping added.
All performed 2,020 completed write transmissions with no retry or poison.
This small difference from one run per version does not establish a meaningful
end-to-end speedup. Card busy time, byte PIO, and synchronous verified writes
remain. Real-card timings are needed before advertising a throughput gain.

## Further write and cache opportunities

Allocation currently initializes a new cluster to zero before linking it,
then overwrites those sectors with file data. For a 400 KiB, aligned,
initially empty file, direct initialization could remove 800 zero writes and
their successful verification reads. That is about 36% of the 2,198 writes in
the synthetic four-KiB-cluster workload, not a measured prototype result.
Metadata, FAT mirrors, and final data writes would still be required.

The implementation must fill untouched tails and gaps with zeros and keep all
initialization before linking/publishing. Necessary new tests include failures
at every sector of initialization, partial appends, cluster boundaries,
fragmentation, truncate/re-extend, readback corruption, and removal. Avoid
requiring a full cluster-sized RAM buffer.

Writable sequential cursors could reduce walking from the first cluster on
successive reads. Larger FAT caches could help fragmented chains. Persistent
proofs must not hide same-card external FAT corruption, replacement, mutation,
or remount. Existing freshness tests prohibit simply retaining a successful
audit indefinitely. A write-back cache would also change when DOS receives
errors and when removal is safe; it is not the first recommendation.

CMD18/CMD25 multi-block transfers are deferred: they need stream-stop, busy,
partial-failure, retry, and replacement modeling. They do not remove byte-wide
PIO. Assembly transfer loops require physical timing tests on both cards and
the slowest supported CPU, even if the access-count emulator passes.

## CPU-specific executables

The best demonstrated changes above remain 8088-compatible. A 286 build can
reduce some instruction sequences, but does not eliminate the long arithmetic
helpers automatically. The current Turbo C compiler has no direct 386 code
generation mode; selected 386 assembly helpers are a possible later experiment.

A 386 can perform 32-bit arithmetic and wider memory copies in real mode, but
the conventional real-mode segment offset limit remains 64 KiB, as described
in the [Intel 80386 manual](https://www.read.seas.harvard.edu/~kohler/class/aosref/i386/s14_01.htm).
New helpers must preserve upper register halves as needed: the current entry
wrapper saves only 16-bit registers. They must also retain DX:AX long returns,
DF/IF, segments, odd-length copy tails, and far-buffer boundary behavior.

There is no demonstrated reason yet for a separate 486 executable. Measure
remaining CPU costs after the portable changes before maintaining additional
builds. No CPU-specific driver executable was qualified in this review.

## Validation and retained evidence

Both the CPU/cache prototype and complete audit prototype passed all 278
existing host tests. Independent polynomial-division oracles checked all
65,536 two-byte CRC16 inputs and 32,768 varied CRC7 frames. Boundary identities
covered all legal cluster sizes and 32-bit positions. The latter arithmetic
checks are not a native end-to-end 64-KiB-cluster volume test.

The CPU/cache prototype also passed native exhaustive CRC, copy guards,
register/segment/DF/IF checks, strict CRC card behavior, and three-access
settling. Both candidates passed real booted DOS XCOPY, nested/boundary files,
independent exact byte checks, fsck, and fresh-boot read-only copy-back. The
complete audit prototype additionally passed native card-drop and pre-mutation
read-fault gates, plus the four mid-audit injections described above.

Full release mutation coverage, every DOS/profile/geometry gate, exact shipped
500 MiB qualification, and physical-card performance qualification were not
repeated. The candidates are research snapshots, not deployment kits.

The temporary prototype snapshots and experiment outputs are not retained
in the source repository. This document records the historical findings;
current regression tests and qualification tools live under `driver/tests`.
