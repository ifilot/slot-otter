# Resident memory

The current **OTTERSD 1.0.0** allocation is **42,896 bytes (41.9 KiB)** including
the PSP, in both `/RO` and `/RW`. The increase over 0.14 is 3,408 bytes for read
caches, per-handle cursor state and their code. The private stack remains
2,048 bytes, with 16 open handles and 32 directory searches. `/UNLOAD` reclaims
the complete resident allocation when its existing safety conditions are met.

The current qualification ceiling is 45,000 bytes. Exact measured layout and
native memory-pressure evidence are retained in `driver/dist/build` and
`driver/dist/EVIDENCE`. The sections below record earlier releases; their
sizes, ceilings and pending hardware statements apply to those versions.

# Historical layout: OTTERSD 0.8

OTTERSD 0.8 retains **36,944 bytes (36.1 KiB)** including the PSP, in both /RO
and /RW modes. The reviewed baseline was 39,888 bytes; the net reduction is
**2,944 bytes (7.4%)**, including new card/version/timing diagnostics.

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
than 240. Default sector stores remain CRC/exact-readback verified. Full mount,
explicit commit and unmount retain complete enabled mirror comparisons. A
single-FAT volume skips a nonexistent comparison. It still checks flags and
all relevant mount geometry.

Startup retains mandatory bulk I/O and identity checks. Faster CRC reduces CPU
work; physical improvements must be measured on the next hardware run using
INSTALL.LOG and HWRT mount/phase timing. Emulator timing is not a prediction
for a 286/8088 or a particular SD card. Version 0.8 restores the proven 0.6 C
SD transport and table-free C CRC16 after a physical mounting failure was reported with
0.7. Assembly now accelerates normalized far memory copying only. Physical
confirmation of this recovery build remains pending.

Historical memory investigations and the earlier driver names are preserved
in the pre-OTTERSD source archive outside driver. The rename, version change
and folder consolidation preserve the current resident layout and capacities.
The actual DOS MCB and linker allocation are rechecked for the new release.

The 0.6 copy-performance iteration cost 160 bytes relative to 0.5. It adds the
readback policy/query and reuses the existing reader FAT buffer for writable
traversals. Linear cycle/count validation replaces repeated scans; no new cache
buffer, heap or writeback queue is retained. Stack/handle/search capacities are
unchanged. See PERFORMANCE.md for measured traffic and genuine-DOS XCOPY gates.

The 0.7 speed iteration costs a further 208 bytes, with no new resident buffer,
lookup table or persistent cursor. The full proof supplies logical EOF;
overwrite traversal retains a cursor only on the private stack within a call.
The resident remains below the existing 37,000-byte qualification ceiling.

The 0.8 recovery build retains 36,944 bytes, 48 fewer than 0.7 and 160 more than
0.6. SD transfer/CRC assembly and command CRC7 shortcuts are removed. The new
installer/control diagnostic formatting is entirely in released installer
segments; the resident diagnostic ABI and all buffers/capacities are unchanged.

## DOS capacity reporting in 0.9

The logical disk-space formatter adds 112 resident bytes relative to 0.8,
for a measured allocation of 37,056 bytes including PSP. It adds no cache or
persistent buffer. Its local counts and unit size use the existing private
callback stack. The build/layout and genuine DOS memory-pressure gates
check this allocation; the regression ceiling is now 37,100 bytes.

## Full unloading in 0.10

Measured resident allocation is 37,408 bytes: 352 bytes more than 0.9. The
additional state is the original 88-byte DOS CDS and five words recording the
resident PSP and interrupt vectors, plus a one-byte latch for a lost dirty
session. The private query and flush/restore phase
remain resident; option parsing, DOS memory validation, vector detachment and
memory release are in the discarded installer tail. No cache or stack grows.
The regression ceiling is 37,440 bytes.

`OTTERSD /UNLOAD` releases the entire allocation, whereas `/UNMOUNT` retains it.
The separate transient caller frees the TSR only after its interrupt callback
has returned and INT 2F has been restored. Open files, a later chain hook,
invalid DOS memory ownership, the current SD drive, failed commits and lost
dirty sessions prevent
unloading. Genuine DOS tests compare all CDS bytes, the original vector, total
free memory and largest executable block over repeated unload/reload cycles;
an unrelated allocated block above the TSR must survive. Physical Dune II
qualification still depends on the user's DOS configuration.

## Fast mounting in 0.11

Resident allocation is 37,568 bytes including PSP, 160 more than 0.10. The
installed policy adds one byte and no cache, heap or stack allocation. The
retained code adds the flag query and first-FAT-sector comparison used when
skipping the mount scan. Option parsing, warnings and status text stay in the
discarded installer tail. The regression ceiling is 37,600 bytes; /UNLOAD
continues to reclaim the entire resident allocation.

## Portable CPU improvements in 0.12

Resident allocation is 38,368 bytes, 800 more than 0.11. The CRC16 and CRC7
tables use 768 bytes; geometry state and code changes account for the net
remainder. No data/FAT cache, heap, stack, or handle capacity grows. The release
ceiling is 38,400 bytes. All code still targets the 8088, and `/UNLOAD` reclaims
the complete allocation before running a game.


## Dual FAT16/FAT32 support in 0.13

Resident allocation is 39,456 bytes including PSP: 1,088 bytes above 0.12.
The formats share all sector buffers, transport, allocation and redirector code.
FAT16 adds entry-width branches and a bounded fixed-root scan, not a second
filesystem implementation or extra sector buffers. Both formats remain in RAM
regardless of the optional loader format restriction. `/UNLOAD` still reclaims
the whole resident allocation when its existing safety conditions are met.

## File allocation in 0.14

Resident allocation is 39,488 bytes including PSP, 32 bytes above 0.13.
Allocation now selects whether a cluster must be cleared: directory clusters
are cleared, ordinary file clusters are initialized only as bytes become
visible. No additional cache, buffer or retained allocation proof is added.

## Read caches in 0.15

Resident allocation is 42,896 bytes including PSP: 3,408 bytes above 0.14.
The FAT cache grows from one sector to four; two directory sectors are added
separately from the existing payload buffer. The sixteen open-file slots gain
read cursors and generation stamps. The remaining increase is cache and cursor
code. The regression ceiling is now 45,000 bytes; 8088 compatibility, the
2,048-byte callback stack and the unload layout checks are unchanged.
