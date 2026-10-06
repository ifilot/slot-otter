# Writable resident driver goal

The authorized objective is writable SD-card support in the resident DOS
redirector, bounded verified sector retries, and a deployable DOS hardware
test kit. Source remains under `driver`, independent of `src`. Preserve the
read-only behavior, existing physical logs, and 8088 instruction target.

## Baseline and physical evidence

The resident read-only build retains 17,632 bytes. Standalone WTTEST v1.7
has 145 host tests, 51 mutation checks, and booted MS-DOS 5/6.22 validation.
Both physical cards pass the complete command-CRC rejection and filesystem
suite (132 checks). Data-CRC rejection leaves Intenso reads timing out and
SanDisk accepting a subsequent write without returning its new contents.
Clean CMD13 status and a matching CID alone do not prove recovery.
User confirms verification after reboot passed for ordinary writes.
Physical 8088 testing is deferred. Logs are evidence and must remain intact.
Source/binary/log baseline copied to `/tmp/otter-rw-baseline-20261005`.

## Required implementation and evidence

- Compact resident transport: correct command/data CRC, CRC-checked reads,
  busy/status validation, exact readback, three total attempts at most.
  Preserve target and a snapshot of the complete sector across retries.
  Reestablish identity/capacity/communication before another write attempt;
  latch failure if this cannot be established. Preserve first-error diagnostics.
- FAT32 mutations: checked mount geometry, guarded writes to mounted volume,
  FAT mirroring/active FAT handling, allocation/free/zeroing, directory growth,
  partial writes, gaps, truncate, create/delete, mkdir/rmdir, rename, attributes,
  timestamps. Metadata ordering and irreversible failures must be explicit.
- DOS redirector: access modes, create/open actions, file size/position,
  duplicate/reference lifetime, commit/close, sharing/locks, correct errors,
  searches/cache invalidation, disk space, safe unmount and media changes.
  Default read-only; writing explicitly enabled. No DOS calls in callbacks.
- Host unit and mutation tests covering boundary/error behavior, transient and
  persistent transport faults, each metadata stage, and recovery stop policy.
- Actual booted MS-DOS integration through INT 21h and standard DOS programs,
  independent content/FAT checking, reboot persistence, readonly regression,
  1 MiB RAM, resident layout/stack/memory-pressure checks and measurements.
- Custom human-facing DOS test program exercising the mounted driver through
  DOS APIs. Clear progress, local diagnostic logs, verification after reboot,
  card swapping, errors, and guarded destructive testing on an expendable image.
- Reproducible standalone kit: source, binaries, fresh SD image, checksum
  manifest, and instructions for SanDisk and Intenso. Artifact/source equality
  checked. State exactly what emulation proves and physical tests still need.

## Current validation checkpoint (2026-10-06)

- Resident `SDRW.C` freezes each sector and LBA, checks command/data CRC,
  selected busy completion, CMD13, identity and exact CRC-checked readback.
  Retry requires reset/CRC initialization, matching CID/capacity, write-protect
  checks and usable target reads. Maximum three total attempts; failure poisons
  and disarms. Public diagnostics report actual read LBA and preserve the first
  failure of the latest write. Nineteen transport tests and thirteen mutations.
- `RWFS.C` implements guarded FAT32/SFN mutations, mirror/active FAT handling,
  clean flags, FSInfo invalidation, backup BPB checks, allocation/zeroing,
  directory growth/end markers, LFN companion cleanup, partial disk-full writes,
  gap/resize/truncate, rename/moves and attributes/timestamps. Thirty-eight tests
  and nineteen mutations pass. Read errors remain transport errors through
  validation; dirty-session reads and mirror mismatch poison. This is not a
  transaction or global allocation/crosslink scan.
- `RWOPS.C` integrates validated access/create modes, bidirectional sharing,
  shared-size refresh, locks, duplicate lifetime, close cleanup, directory/file
  mutation, free space, wildcard deletion, and offline/remount behavior. Twenty-
  one callback tests and twelve mutations pass. BIOS time is sampled high/low/
  high to avoid a torn read. Diagnostic selectors export transport state,
  installed mode, sticky last callback error and observed private stack use.
- Full current host suite: 223 tests, 95 mutations and all coverage floors pass
  (`/tmp/otter-rw-current-gates.log`, `/tmp/otter-rw-current-coverage`). Strong
  tests were established before the handle-state memory reduction.
- Read-only original stays 17,632 bytes resident and byte-identical to the
  published executable. RW baseline reached 40,080 bytes with diagnostics and
  stable clock sampling. A mode-exclusive cursor/disk union saves 192 bytes:
  current RW allocation is 39,888 bytes including PSP. Linker/MCB checks agree;
  measured callback stack high-water is 524 of 2,048 bytes in the tested runs.
  Full free-DOS-memory overwrite/remount/read checks pass. Keep the stack size;
  this observation does not bound every physical IRQ or 8088 circumstance.
- Three read-only subagents reviewed transport, FAT and DOS comments/style;
  root alone edited. C89/8086 contracts and DOSREF/CODING docs are updated.
  Both comment-only passes produced byte-identical resident EXEs. Separate
  behavioral fixes and the memory union have their own regression evidence.
- Genuine DOS 5/6.22 success and recovery profiles pass, including CRC rejection,
  wrong readback, status failure, strict CRC and slow busy completion. Removal
  after first programming stops additional writes (the first sector can change);
  a pre-write read-CRC failure leaves all card bytes unchanged.
- Standard FCB wildcard deletion and COMMAND.COM DEL pass with grown directories.
  The optional canonicalized 5D00h server experiment remains error 3 without a
  new callback failure; it is not a supported/validated application path.
- Enhanced writer in read-only mode passes the original DOS 5 COPY/EXEC/swap
  suite with unchanged images (`/tmp/otter-rw-enhanced-ro-swap.log`).
- New `rwhardware/HWRT.C` uses DOS APIs only, explicit expendable-image/mode/
  local-log guards, full transport/error diagnostics, expected rejection reasons,
  and immediate stop on unexpected failure. RWCHILD exercises seventeen normal
  exits with six unclosed direct-DOS handles and a region lock. Directory moves,
  interleaved allocation, 70,000-byte and zero/FF files, stress, memory and fresh-
  boot exact verification pass in DOS 5/6.22 with independent content and fsck.
  Abnormal abort and FCB record-I/O lifetime remain explicitly unqualified.
- Native hardware tester guard/fault cases pass for missing /ERASE, read-only
  installation, missing image marker and card removal. Local logs are flushed
  and committed so checkpoints are available while the program runs. No claim
  is made that this prevents every reset/power-loss log failure.
- Candidate package creation verifies rebuilt binaries equal validated binaries,
  image KIT file equality, source ZIP equality and read-only fsck. A complete
  human manual describes Navigator copying, local CONFIG setup, SanDisk/Intenso
  runs, reboot verification, stress/memory/swap and diagnosis.

## Software completion gates

- Current-source DOS 5/6.22 hardware program and reboot suites pass with exact
  expected rejection reasons. The real interactive swap branches pass using a
  private emulator-input wrapper; production HWRT has no emulator controls.
- The actual candidate SD image passes the complete suite, stress/memory and
  fresh-boot verify. Independent mtools bytes and read-only fsck agree. Verify
  leaves the card image unchanged. Expected metadata/data fixtures remain intact.
- Final kit in `rwhardware/dist` is rebuilt from this source tree, checked equal
  to validated binaries, and checked for image/ZIP/source/hash consistency.
  The manual covers both physical card brands and the deferred 8088 scope.
- All thirteen original log hashes and original released read-only binary remain
  unchanged. No files under `src` or prior released images were replaced.
- Physical resident-write qualification is the next user test, not a software
  completion gate. Physical 8088/5150, abnormal abort/FCB record-I/O, DOS 3/4 and
  86Box machine validation remain unqualified as stated in the delivered manual.
