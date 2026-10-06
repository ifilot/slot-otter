# Consolidated driver checkpoint

The working baseline is commit `74d8499030f68f6284927c52e38c492d6ed862d5`.
Its executable, linker map and file hashes are retained in
`/tmp/otter-consolidation-baseline-20261006`. Original released kits and hardware
logs remain unchanged. The SanDisk DOS 6.22 run passed 43 identification,
278 functional and 62 verification checks, with 1,777 verified sector writes
and no retries. That evidence applies to the baseline, not future builds.

## Required completion gates

1. One canonical writable/read-only driver build and consistent interface.
2. One clear hardware tester, with card/version identification, timings,
   useful progress and a documented per-card procedure.
3. Measured startup phases and reductions in repeated verification work.
4. Measured resident savings without reducing stack or handle capacities.
5. Regression, coverage, mutation and injected-failure gates.
6. Booted DOS 5/6.22, private-stack/all-free-memory overwrite, persistence,
   independent file comparison and read-only filesystem checks.
7. Final image, binaries, source and manual, with the actual image validated.

Three read-only reviewers cover layout, performance and qualification. Root is
the sole source editor. Physical 8088 testing remains deferred. The next
consolidated release requires a new hardware run on each card.

## Implementation and measurements

OTTERWR 0.4 is the canonical driver. Its /RO and /RW modes use the same
36,624-byte resident allocation, versus the reviewed 39,888-byte baseline:
3,264 bytes saved (8.2%). Installer code/strings are released in explicit far
segments; filesystem comparison and transport readback share 512 bytes while
frozen expected write data remains separate. Stack and capacities are retained.

HWRT 0.2 is the single public tester. It self-executes its private child mode,
records cached card CID/capacity/version/ABI and progress/phase/total timings,
and stops with existing strong DOS/transport diagnostics. No companion EXE is
required. Canonical builds and qualification use build.sh and validate.py.

CRC16 uses an independently checked, table-free byte update. Full writable
mount comparison remains. Ordinary close persists verified data/metadata but
leaves the volume dirty; full explicit commit/unmount checks mirrors before
publishing clean state. Online remount first flushes the existing dirty session.
The twenty-close test fell from 21,940 reads to fewer than 240; single-FAT
mounts skip the nonexistent mirror comparison without skipping other preflight.

A reproducible booted-DOS startup comparison at the same nominal fixed emulator
cycles measured 41 BIOS ticks for the baseline and 38 for this build. This is
a modest emulated improvement, not a prediction for the physical 30-second
mount. SD/filesystem phase timings now allow the next hardware run to identify
the actual cost. Bulk I/O, settling reads and per-sector identity checks remain.
A specialized assembly receive loop is a measured future opportunity, not an
unvalidated shortcut introduced into this release.

Three follow-up read-only audits found no new transport/close/tail defect.
Applied feedback includes generated-call allowlisting, startup address-space
and paragraph-rounding bounds, a shared exhaustively tested parser, explicit
/RO/conflict tests, stale-kit rejection, accurate mode memory metadata and a
single local-log commit for the card identity line. Root alone edited sources.

Qualification runs and their exact outcomes are recorded under
`driver/dist/EVIDENCE/QUALIFICATION.JSON`. The final image is tested under both
DOS kernels and against independent contents/fsck. Original released kits,
logs and legacy read-only binary are hash-audited in EVIDENCE/BASELINE.JSON.
The current kit still requires a fresh physical run on each card.
