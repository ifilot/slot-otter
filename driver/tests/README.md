# Current consolidated test entry point

Run `python3 driver/validate.py` for host coverage/mutations, canonical driver
and tester builds and a candidate image. Add `--full --dosbox PATH` and two
`--boot-image PATH` arguments for DOS 5/6.22, faults, guards and final-image
qualification. See [driver README](../README.md). The commands below retain
legacy/internal development gates; `run.py --build` builds the archived RO
comparison only. Current releases always use driver/build.sh and validate.py.
PORTBODY.H is shared with INSTALL.C, so exhaustive port tests cover its body.

# Regression tests

Run the fast suite from any working directory with Python 3 and GCC:

```sh
python3 driver/tests/run.py --coverage /tmp/otter-coverage --mutations
```

The current combined suite has 223 tests and 95 mutation checks. It compiles the
production reader, writable transport/filesystem/redirector, standalone writer,
and card model. Tests take about 43 seconds without mutation checks on the
development machine. No DOS toolchain, copyrighted DOS image, emulator or third-party Python
package is required. The GitHub driver workflow runs coverage and mutation checks
on changes under `driver` and retains the coverage artifacts.

The host DOS adapter supplies simulated SDA/CDS/SFT/DTA memory and segmented
pointer translation. It substitutes card presence and sector transport, but uses
production dispatch and filesystem code. Every redirector test hashes the card
before and after to detect writes. State resets between tests.

Checks include:

- Register results and carry flags, chaining to other redirectors, preservation
  of DOS-owned SFT fields, extended-open actions, and denial of mutations.
- All 16 file slots, reference counts, closing stale handles, independent file
  positions, EOF, 65,535-byte reads, fragmented files and seek overflow.
- Independent searches, attribute filters, result copying to DOS memory, search
  cookie corruption, eviction and invalidation across mount generations.
- Empty slots, changed identity, current-directory reset, failed mounts,
  partial-read errors, preservation of completed bytes and offline recovery.
- Deterministic randomized reads across 1/2/8/128-sector clusters, active FATs,
  superfloppies, invalid geometry, invalid chains, bounded directory cycles,
  cache invalidation and recovery after injected FAT/data sector faults.
- SD protocol initialization, synchronous byte pipeline, CRC generation, CID
  stability/replacement, empty sockets, chip select and write rejection.

Coverage reports distinguish the standalone FAT32 library from the same reader
linked into the redirector test library. Do not add those percentages together.
The runner enforces floors for production code: FAT32 95% lines/80% branch
outcomes, redirector 99%/90%, model 95%/80%, port/options 100%/100%. JSON and annotated gcov files are saved
beside the text report. Host coverage excludes real segmented-pointer arithmetic,
SD electrical I/O and assembly; those need the actual-DOS integration tests.

Mutation checks change **temporary copies** of production sources and require
assertion failures after successful compilation. They check nine targeted
regressions: allowed writes, skipped removal checks, stale search generations,
lost reference counts, truncated reads, advancing a failed FAT hop, stale caches,
ignored active FAT selection, and allowing a remount with open handles. This is a sensitivity check, not an exhaustive
mutation score. Update the mutation locations if the implementation changes.

Before accepting a memory reduction, also build and run actual DOS:

```sh
python3 driver/tests/run.py --build \
  --dosbox /path/to/test-dosbox --swap \
  --boot-image /path/to/dos5.img \
  --boot-image /path/to/dos622.img
```

Use the supplied DOSBox ISA adapter built with `OTTER_MODEL_TEST` for `--swap`.
Also run `integration.py` without `--swap` to check installation with a card
already present. Integration requires mtools, Turbo C/TASM, stock DOSBox for
compilation, and your own bootable DOS images. Temporary images and logs are
retained for inspection; original boot images are untouched.

The real-DOS probe checks callback behavior, DOS COPY/EXEC, segment-boundary
reads, all open slots, card swaps, and read-only image hashes. It walks DOS's MCB
chain to measure the resident allocation independently of the installer's message.
It then allocates and overwrites every remaining DOS free block and runs
unmount/mount/read callbacks while that memory is occupied. This catches accesses
to discarded resident code/data that may otherwise fail only when a large program
loads. The harness checks the reported allocation against the MCB and saves
`memory.txt` for comparisons. The default resident ceiling is 17,632 bytes;
`--max-resident` explicitly changes that budget if needed. The baseline and reduced builds passed under
DOS 5.0 and 6.22 with 1 MiB emulated RAM. Physical 8088 and full 86Box verification
remain separate checks.

The build also validates `_resident_end` against the linker's `_BSSEND` marker,
checks that every static code/data/library segment and the private stack lies
below it, and rejects unsafe layouts. Host tests cover malformed linker maps.
The `--swap` integration run additionally executes `SDPROBE.C` against actual
`SD.C`/`SDCMDS.ASM` while OTTERFS is unmounted. It checks exact payload contents,
guard bytes after a 512-byte buffer, missing/out-of-range reads, and chip-select
deassertion using the adapter's test-only latch observation. The probe reproduced
the previous successful-read deselection bug before the fix.

The second memory round adds exhaustive checks of all 65,536 input port values,
malformed/prefixed/overflowing inputs, ASCII option case folding, scratch-buffer
aliasing, and stale duplicated-handle references. Linker checks reject unused
heap/stdio/parser/atexit dependencies in addition to validating memory boundaries.

`CLIPROBE.C` uses DOS EXEC with an explicitly constructed 10 KiB environment in a
16 KiB block. It checks ordinary and TSR termination types, ERRORLEVEL, quoted
and tab-separated lowercase arguments, invalid ports, and a 127-byte command tail.
It snapshots INT 0/4/5/6 and verifies their restoration after each child, then
checks ordinary child execution returns all free DOS allocation space. The free
space measurement includes free MCB headers so coalescing does not look like a
leak or a saving. CLIPROBE installs OTTERFS and unmounts it; the remainder of the
integration harness mounts or inserts the fixture as appropriate.

The standalone write suite adds CRC-checked direct-I/O transport and restricted
FAT32 mutation tests. See [../write/README.md](../write/README.md). Host gates
include WSD/WFS at 80% lines and 65% branch outcomes. Model counters are merged
across protocol/write libraries to retain its existing 95%/80% floor.
`--mutations` also runs the forty-two write sensitivity probes; CI installs mtools
and dosfstools for independent file-content and filesystem checks.

The standalone write suite now includes 99 host tests, independent CRC oracles,
packet/response fault injection and diagnostic evidence checks. WTEST diagnostics
are gated at 85% line coverage and 60% branch outcomes in addition to WSD/WFS.
Booted-DOS argument checks use `driver/write/validate.py --cli-checks`; these
exercise the compiled executable and reject 26 unsafe/invalid combinations
before initialization, with unchanged card hashes and no created card logs.


v1.6 adds CMD55-ready/delayed ACMD41 and bounded startup-trace tests, exact
SanDisk FF corruption fixtures before/after negative probes, normal-only full
filesystem qualification, and expected/unexpected/missing recovery status.
Tests enforce no metadata writes after raw corruption, no retry after poison,
clean recovery status, independent persistence and preserved first-failure data.


v1.7 isolates command/data CRC probes, tests access after each, logs probe
responses before recovery, and waits for rejected-data completion with CS
asserted. Fixtures reproduce command/data-triggered read failures or discarded
writes and detect early CS release. Tests cover nonzero original scratch,
read-token samples, progress logging and unexpected idle-plus-CRC responses.
Fresh-boot verification of the prior NORMAL hardware runs is user-confirmed.

The resident writer adds separate SDRW/RWFS/RWOPS coverage and sensitivity
checks. Current floors are 99% lines/75% branch outcomes for transport, 90%/66%
for RWFS, 95%/72% for RWOPS, and 88%/63% for the combined redirector. Identical
writer coverage graphs are merged across wire, filesystem and callback tests;
the reported percentages are not sums.

`rw_integration.py` boots genuine DOS on private images and runs DOS API checks,
segmented writes, locks, wildcard deletion, resident MCB/stack and memory-pressure
checks. Profiles cover strict CRC, slow busy completion, CRC rejection, corrupted
readback, status failure, removal and a read-CRC failure. Linker layout and
independent mtools/fsck content checking accompany the native tests.

The deployable resident-DOS tester and its fresh-boot/guard/fault harness are in
[../rwhardware/README.md](../rwhardware/README.md). The swap harness uses a private
input wrapper to operate the emulator's card-removal port; the physical HWRT
executable contains no such control. Human prompts are followed on real hardware.
