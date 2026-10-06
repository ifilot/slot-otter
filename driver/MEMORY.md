# Consolidated resident memory

OTTERWR 0.4 retains **36,624 bytes (35.8 KiB)** including the PSP, in both /RO
and /RW modes. The reviewed baseline was 39,888 bytes; the net reduction is
**3,264 bytes (8.2%)**, including new card/version/timing diagnostics.

| Change | Effect |
|---|---|
| Far installer in discarded INITTAIL/INITDATA | Releases installer code and strings |
| Shared filesystem comparison/transport readback scratch | Removes one 512-byte buffer |
| Bytewise table-free CRC16 | Reduces CRC work and code versus bitwise loop |
| New identity/timing query and retained far gates | Small resident cost included above |
| Stack and capacities | 2,048-byte private stack, 16 handles and 32 searches retained |

BOOT uses normal Turbo C startup and explicit far gates to retained near code.
INSTALL uses original DGROUP but lives beyond _BSSEND; code/data classes are
transformed only after checking every generated call. Installer literals and
argv do not escape into callbacks. The build proves released segments lie
inside the temporary 8 KiB heap reserve, below the 2 KiB startup stack, and that
all reservations fit DGROUP. keep() restores CRT vectors before DOS releases
the installer. Native tests overwrite all free DOS memory and then exercise
callbacks/remount/EXEC; checking only EXE size or the MAP is insufficient.

Ordinary close no longer reads both complete FATs. Twenty closes on the kit's
547-sector FATs formerly read 21,940 sectors; the regression now requires fewer
than 240. Each sector store remains CRC/exact-readback verified. Full mount,
explicit commit and unmount retain complete enabled mirror comparisons. A
single-FAT volume skips a nonexistent comparison. It still checks flags and
all relevant mount geometry.

Startup retains mandatory bulk I/O and identity checks. Faster CRC reduces CPU
work; physical improvements must be measured on the next hardware run using
INSTALL.LOG and HWRT mount/phase timing. Emulator timing is not a prediction
for a 286/8088 or a particular SD card. A carefully measured assembly receive
loop or custom startup are future opportunities; neither was introduced here.

The history below describes the archived, smaller read-only driver only.
It is not the current /RO mode or the consolidated build's regression ceiling.

# Archived read-only measurements

Measurements use booted MS-DOS 5.0 and 6.22 with 1 MiB emulated RAM. The integration
probe reads the actual DOS MCB allocation and checks it against installer output;
executable file size is not a substitute for this measurement.

| Build | Resident DOS allocation | Change |
| --- | ---: | ---: |
| Mount/unmount implementation before reductions | 27,360 bytes | baseline |
| Installer output through DOS handle writes | 23,056 bytes | -4,304 bytes |
| Reclaim startup heap/stack at `_BSSEND` | 20,080 bytes | -2,976 bytes |
| Read SD payload into cache, discard CRC separately | 19,552 bytes | -528 bytes |
| Remove unused environment copying; bounded port/options parser | 18,208 bytes | -1,344 bytes |
| Measured `-d -Z` compilation | 18,064 bytes | -144 bytes |
| Minimal ordinary exit and compact resident state | 17,632 bytes | -432 bytes |
| Total reduction | | **9,728 bytes (35.6%)** |

The first reduction replaces installer/control `printf`/`puts` and stream cleanup
with bounded numeric formatting, INT 21h handle writes and explicit standard
handle closes. Redirection still works; inherited redirected output is closed
before staying resident. This removes unused stdio formatting, stream operations
and related data from the linked TSR. Resident filesystem behavior, both sector
caches, 16 open slots, 32 search slots, and stack sizes are unchanged.

Before the first change, 34 host tests, coverage measurements, eight mutation checks and
DOS 5.0/6.22 integration including free-memory overwrite checks passed. The current
suite has 46 host tests and additionally verifies linker-layout rejection and
actual assembly transport guards/deselection. Both DOS versions pass with every
free DOS block overwritten, including fragmented environment allocations. See [tests](tests/README.md) for repeatable commands.

The second step adds a zero-length marker to Turbo C's `_BSSEND` segment.
The build checks the marker against all static code/data/library segments and the
private stack. Installation retains through that boundary plus paragraph alignment
and the PSP, releasing the startup heap and stack. `keep()` is retained because it
restores Turbo C's interrupt vectors before DOS terminates the installer. Startup
still receives its original stack and nonzero heap allocation; they are reclaimed
only after installation.

The SD step removes the 514-byte intermediate buffer and its payload copy. CMD17
stores 512 bytes into the invalidated cache and consumes the two CRC bytes without
storing them. A successful-read bug was also fixed: DX previously remained at
`base+1`, so `sdclose` addressed the wrong chip-select port. The new DOS probe
reproduced that failure and now passes destination-guard and chip-select checks.

Three independent read-only reviews covered resident layout, code/library size,
and correctness risks. Their recommendations were reconciled with the regression
results; edits and validation remained with the primary agent.

The second investigation used seven independent read-only reviewers, coordinated
in parallel batches because the environment permits three concurrent reviewers:

| Review | Reconciled finding |
| --- | --- |
| Minimal assembly startup | Feasible, but bootstrap replacement needs explicit BSS, stack, argv and termination tests; deferred |
| Environment/runtime dependencies | Override unused environment copying and atexit processing; preserve low-level vector restoration |
| Resident linker layout | Object reordering cannot release MAIN: near calls and shared CODE/DGROUP require an explicit architecture |
| Port/options parser | Use bounded 16-bit arithmetic and ASCII case conversion; reject negative wraparound |
| Compiler options | Measure `-d`, `-Z`, and their combination independently; preserve 8088 cdecl ABI |
| Resident state | Remove redundant open epochs and unused volume fields; share path/entry scratch after path consumption |
| Correctness and validation | Add EXEC tests for a large inherited environment, ERRORLEVEL, vectors and command-tail extremes |

`CRT.C` suppresses unused environment copying and delegates ordinary exit directly
to the CRT low-level exit. Turbo C's default argument parser still uses the original
DOS environment for argv[0], and low-level exit/keep still restore startup interrupt
vectors. The program has no environment consumers, atexit registrations or stdio
cleanup. The linked map no longer includes the allocator, strtoul/strupr/ctype or
atexit machinery. The build rejects reintroduction of unused runtime libraries.
The original startup heap/stack sizes stay unchanged and remain reclaimed at TSR
termination. Do not set `_heaplen=0`: Turbo C interprets that as permission to
expand DGROUP toward 64 KiB.

`PORT.C` accepts positive hexadecimal values, optional `+`/`0x` prefixes, leading
ASCII whitespace and leading zeros. It checks overflow before shifting a 16-bit
value and keeps the existing port range/alignment requirements. Negative inputs
that previously wrapped through strtoul are deliberately rejected. Every 16-bit
value is checked by the native suite; the parser and option conversion have 100%
line and branch-outcome coverage. Actual DOS tests include malformed and overflowing
ports, lowercase options, quotes and tabs.

Compiler measurements on the 18,208-byte intermediate build:

| C compilation flags | Predicted retained allocation from verified MAP |
| --- | ---: |
| `-O` | 18,208 bytes |
| `-O -d` | 18,192 bytes |
| `-O -Z` | 18,080 bytes |
| `-O -d -Z` | 18,064 bytes |

Both flags were adopted after the final build passed actual DOS tests. No 80186
flag, speed preference or calling-convention change was enabled.

The final state changes keep capacities intact. Open-file epochs are redundant:
reads pass the ready gate and mounting refuses every open reference, including
stale duplicated handles. Search epochs remain intact because searches can survive
without open files. Lookup finishes consuming the path before writing its output,
allowing the 80-byte path and 32-byte entry buffers to share storage. Busy dispatch
protection remains; aliasing, nested paths and repeated stale-reference closes have
regression tests. Unused volume start/total/FAT-size/boot-label fields and their
assignments were removed; mount geometry validation and directory volume labels
remain unchanged.

The final 17,632-byte allocation is independently confirmed by DOS MCB inspection
on both MS-DOS 5.0 and 6.22, with every free block overwritten during callbacks.
CLIPROBE executes children with a 10 KiB inherited environment and checks ordinary
and TSR termination, ERRORLEVEL, INT 0/4/5/6 restoration, and complete freeing of
ordinary child allocations. The default regression ceiling is now 17,632 bytes.

Remaining opportunities:

1. Custom assembly startup could remove remaining C bootstrap/environment scanning
   and unused floating-point workspace. Previous estimates included allocator and
   exit machinery now removed; remeasure before assigning a remaining saving.
   Maintain DS=SS=DGROUP, bounded argv lifetime, BSS clearing, DOS exit semantics
   and interrupt-vector policy. Keep the current filesystem in C.
2. A separately linked resident image or carefully designed assembly installer
   could release installation-only code and strings. Moving MAIN.OBJ is insufficient:
   all small-model functions and libc calls are near, and shared data follows CODE.
   A split image needs relocation/allocation ownership and complete rollback tests.
3. Search epochs could be replaced by explicit serial invalidation, but the clearing,
   wrap handling and validation code offsets some of the 128-byte data saving.
   Retain the current 32-bit counters until that tradeoff is measured and tested.
4. Measure resident stack high-water usage under deep paths, errors and nested timer
   interrupts before changing the private 2 KiB reserve. ENTRY enables interrupts
   on that stack; native host coverage cannot establish an 8088 bound.

Cache or handle/search capacity reductions would trade performance or functionality
for RAM. Both sector caches, 16 file slots, 32 search slots and the private stack
remain intact. Actually running Dune II on physical hardware is not part of the
validation performed so far.

## Writable executable measurement

The writable goal keeps OTTERFS unchanged and builds OTTERWR separately. CRC
snapshot/readback, FAT mutation state, sharing/locks and diagnostics add resident
code/data. Strong transport/filesystem/callback and mutation gates preceded the
new memory reduction.

| Build | Resident bytes including PSP | Evidence |
|---|---:|---|
| Original OTTERFS | 17,632 | rebuilt EXE identical to published executable |
| OTTERWR before mode-exclusive handle union | 40,080 | linker and genuine DOS MCB |
| OTTERWR with handle union | 39,888 | 192-byte saving; host/native regression |

RO file cursors and RW directory metadata share storage in each open-file slot.
The installed access mode cannot change on remount, so those states never need
to coexist. Search state, sixteen file/lock slots, CRC snapshot/readback buffers
and the 2 KiB private stack retain their capacities.

Native DOS 5/6.22 memory pressure, segmented writes, directory operations,
process-exit cleanup and fresh-boot verification pass. The highest observed
callback stack use is 524 bytes in the tested runs. IRQ handlers also consume
that stack; keep 2 KiB until physical 8088/deeper IRQ scenarios justify a smaller
reserve. The host adapter does not run C on the real callback stack.

Further candidates include streaming verification to avoid a second sector
buffer or relocating installation-only code beyond the resident boundary. Those
require separate correctness/layout evidence and are not part of this release.
Use the smaller read-only executable when conventional memory matters more than
writing support. Dune II and physical 5150 execution remain unqualified.
