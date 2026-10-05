# Standalone SD write test v1.7: hardware procedure

WTTEST uses the Slot-otter ISA card directly. Run from LOCAL DOS storage with
NO resident OTTERFS installed, even if it is unmounted. The resident driver
remains read-only. This kit contains no DOS or Turbo C distribution.
8088/5150 hardware qualification remains deferred.

## 1. Preserve previous evidence and prepare the new executable

Keep the existing SanDisk and Intenso logs. Use a spare SDHC/SDXC card with
nothing important on it. Raw-image the NEW WRITE.IMG onto the entire card;
this destroys previous contents. Do not resize, repair or reformat the volume.
Do not use OTTERHW.IMG. Each write run needs a fresh WRITE.IMG, even when a
previous run failed before creating files.

Use Navigator to copy KIT/WTTEST.EXE and KIT/WMANUAL.TXT to a local DOS folder,
overwriting the older executable. Exit Navigator completely. Boot without
OTTERFS. For a cold-start test, power the machine off and on after copying;
do not run Navigator, HWTEST /PREP or any card initializer before WTTEST.
Keep local disk space available for logs. No new CONFIG.SYS entry is needed.

## 2. Identify each card independently

    WTTEST /INFO /PORT:330

Adjust 330 to the hexadecimal port set by the ISA jumpers. The first log line
MUST say v1.7. INFO issues no block writes. Preserve WINFO.LOG with a separate
name for each card and run, e.g. SANINFO.LOG and INTINFO.LOG, before overwriting
it with another invocation. Record card brand/model/capacity, CPU/RAM, DOS
version and whether the start was cold or warmed by another utility.

INIT CMD records command, argument, R1 and transport error. The trace retains
its first 63 commands and its latest command if longer; omitted commands are
counted. Error=0 on a trace record means an R1 was received, not that card
identification necessarily succeeded. The subsequent FAIL/DETAIL contains the
validation error. CMD55 may legitimately return 00 or 01; ACMD41 must still
complete with 00, followed by valid OCR, CID and CSD. This fixes the strict
CMD55 check that blocked the v1.5 Intenso logs. It does not waive readiness,
capacity, incoming CRC or card identity checks.

If INFO fails, preserve its full log and stop that card's write testing. Do
not use HWTEST /PREP to conceal a cold-start failure in this iteration.

## 3. First qualify ordinary CRC-enabled writing

With a fresh image, from local DOS storage:

    WTTEST /WRITE /NORMAL /ALLOWHINTS /PORT:330

Type WRITE and ENTER only for this expendable card. NORMAL keeps CRC enabled
and sends correct command CRC7 and write CRC16. It injects NO bad command/data
CRC and performs NO CRC-OFF characterization. Incoming CRC16, identity, busy,
status, exact readback, image guards and filesystem checks remain mandatory.

ALLOWHINTS permits only valid FSInfo copies differing solely in cached
allocation hints at bytes 488..495. It never permits CRC/read failures, invalid
signatures, FAT/boot differences, an unmarked image or an existing WTEST tree.
Allocation scans the FAT and sets both hints UNKNOWN before filesystem changes.
DIAG is optional; hint-only DIAG failures do not prevent this explicit exception.

Watch PHASE and PATTERN lines. PRE-FAULT runs ZERO, FF, 55, AA and twelve mixed
patterns BEFORE any negative probes. A verified 96 seed makes ZERO change the
sector; each subsequent pattern changes the previous verified payload. An FF
write is therefore tested against different previous data. The original
scratch payload is saved and restored if all patterns succeed.

Then FILESYSTEM tests new root/nested directories, dot/parent entries,
directory growth, boundary-sized files (0/1/511/512/513/4096/70000 bytes), FAT
allocation/mirroring, partial append, cross-sector overwrite, truncation,
free/reuse, deletion, nonempty-directory refusal, fragmentation, allocation
above cluster 65535 and protected original fixtures. No filesystem metadata
writes start until the raw tests pass.

Preserve WRITE.LOG as e.g. SANNORM.LOG or INTNORM.LOG. Each WTTEST /WRITE
invocation overwrites WRITE.LOG. Require WRITE RESULT: 0 failures and ERRORLEVEL
0. If it passes, reboot without OTTERFS and run:

    WTTEST /VERIFY /PORT:330

Preserve WVERIFY.LOG separately. Require VERIFY RESULT: 0 failures, 18 checks,
accepted_writes=0. This verifies persistence through a fresh initialization.
Read the card back on the PC before its OS modifies it; inspect a saved image
with a read-only FAT checker. Do not repair a failing test image.

## 4. Isolate command and data CRC errors in separate runs

The previous NORMAL and fresh-boot VERIFY tests passed on both cards (VERIFY
reported by the tester). v1.6 combined CRCONLY then failed on both after error
injection despite clean status and matching CID. For this iteration use the
NEW v1.7 executable and fresh image for EACH independent run below. Ordinary
NORMAL qualification need not be repeated to investigate those existing results.

First, prepare a fresh expendable image and run:

    WTTEST /WRITE /CMDCRC /ALLOWHINTS /PORT:330

CMDCRC injects ONLY a bad CMD13 command CRC. It never injects bad data CRC and
never disables CRC. Preserve WRITE.LOG as SANCMD.LOG or INTCMD.LOG BEFORE
starting another run. Both cards need separate copies of their logs.

Then re-image the card, prepare the same local v1.7 utility, and run:

    WTTEST /WRITE /DATACRC /ALLOWHINTS /PORT:330

DATACRC injects ONLY a bad CMD24 data CRC. It never sends an intentionally bad
command CRC and never disables CRC. Preserve WRITE.LOG as SANDATA.LOG or
INTDATA.LOG. Do not run it directly on the CMDCRC result image. Both modes
require typing WRITE; each also runs the full filesystem suite if the isolated
probe and subsequent sector access succeed.

Each run performs this sequence:

1. PRE-FAULT: all sixteen normal changing patterns and scratch restoration.
2. The selected CRC probe. PROBE COMMAND preserves the sent/correct CRC7,
   command-transmission RX and raw response bytes. PROBE DATA RESULT and WRITE
   TRACE preserve the sent/correct CRC16, raw rejection token and completion
   wait BEFORE recovery replaces transport state. The data-rejection path
   keeps CS selected until a bounded readiness wait completes. A timeout is
   an error, not a successful rejection, and poisons the session.
3. Read status twice and verify CID. Clean status alone does not qualify
   recovery: ACCESS CHECK then reads the scratch sector and requires its
   saved payload to remain unchanged. Read errors and changed data are
   separately diagnosed; failure poisons/disarms writes and stops the suite.
4. AFTER-COMMAND-CRC or AFTER-DATA-CRC: write saved bytes xor 96, changing EVERY
   byte even if the original was nonzero; require exact CRC-checked readback.
   Then establish the 96 seed if needed, run all sixteen changing patterns,
   and restore the saved scratch payload. No silent write retry occurs.
5. FILESYSTEM: the same complete allocation/directory/file suite as NORMAL.

Successful single-probe runs on the supplied image have 132 checks (111 in
NORMAL). If successful, fresh-boot VERIFY is available as before; preserve its
log separately. Your earlier successful VERIFY results remain accepted.

If one isolated mode fails and the other passes, the failure is tied to that
probe's sequence. If both isolated modes pass, use a fresh image for the combined
comparison:

    WTTEST /WRITE /CRCONLY /ALLOWHINTS /PORT:330

CRCONLY now performs complete read/write/pattern qualification after the
command-error probe BEFORE attempting the data-error probe, then qualifies
again after the latter. It still omits CRC-OFF. Its expected total is 153 checks.
A failure in the first stage means the second probe was not attempted.

The completion wait is an implementation correction under test, not a claim
that the physical root cause is already resolved. Even two clean statuses and
a matching CID previously accompanied a missing read token or an accepted but
unchanged write. Preserve all first-failure evidence; no reset/retry masks it.

## 5. Other comparison modes, after the controlled runs

Default /WRITE also characterizes CRC-OFF. It first tests an OFF write with
valid data CRC, restores the original, then tests an invalid data CRC with the
same identity/readback CRC transitions. Refusal to disable CRC is WARNING/SKIP;
uncertain writes still stop. This is a separate fresh-image comparison.

    WTTEST /WRITE /ALLOWHINTS /PORT:330

NOCRC never sends CMD59; it uses CMD0's reset-default CRC-OFF state and sends
FFFF in the REQUIRED two-byte data CRC slot. Command CRC7 and incoming read
CRC16 are still verified. It omits all deliberate CRC errors. A card still
requiring data CRC will reject it; no fallback/retry occurs.

    WTTEST /INFO /NOCRC /PORT:330
    WTTEST /WRITE /NOCRC /ALLOWHINTS /PORT:330
    WTTEST /VERIFY /NOCRC /PORT:330

NORMAL, CRCONLY, CMDCRC, DATACRC and NOCRC are mutually exclusive. All except
NOCRC require WRITE. BATCH suppresses confirmation for emulator automation only; all image
and write fences still apply. INFO/DIAG/WRITE/VERIFY are exclusive operations.

## Relaying failures

Preserve the COMPLETE local log. Include OPTIONS, INIT TRACE, PHASE, PATTERN,
PROBE COMMAND/PROBE DATA RESULT, ACCESS CHECK, RECOVERY, the FAIL/DETAIL, WRITE TRACE, WRITE RESPONSE, WRITE BUSY, STATUS READY,
CMD13 TRANSMIT RX, all HEX dumps and final result. On a hang photograph the last
checkpoint. A missing final result is an incomplete run.

WRITE TRACE snapshots CMD24 acceptance, CMD13 status and sent/calculated CRC
independently of later reads. The upper three response-token bits are ignored:
E5 and 05 both mean acceptance. Acceptance and clean status alone do not prove
correct data; every normal write requires exact CRC-validated readback.
Mismatches log differing offsets plus all expected/actual bytes. One additional
READ diagnoses stability; it never clears a first failure or retries a write.
READ TOKEN TRACE records the first 32 token-wait bytes, poll count and BIOS
ticks on a failure. A missing token cannot prove whether stored data changed.
CRC-failed packets retain received/calculated CRC and an UNTRUSTED dump, which
is never used to qualify a write. Busy/readiness records are the first 32 sampled
bytes plus nonready counts and BIOS ticks; zero ticks can include busy polling.

The v1.5 SanDisk FF failure returned 508 zero bytes and four FF bytes, identically
on both reads with valid received CRC16. If that recurs, preserve the card before
re-imaging. A PC reader's independent read of absolute sector 2056 (byte offset
1,052,672) helps distinguish stored corruption from ISA read-path corruption.
Read it from a saved raw card image before allowing repair or filesystem changes;
relay the 512 bytes together with the DOS log. A matching PC sector confirms
stored bytes, but still does not identify the transport/card root cause.

ERRORLEVEL: 0 pass; 1 failed tests; 2 invalid setup/options/cancellation/log error.
Errors: 101 timeout; 102 CRC; 103 rejection; 104 programming/recovery status;
105 readback mismatch; 106 absent/changed/unsupported media; 107 safety guard;
108 no free clusters; 109 duplicate; 110 nonempty directory; 111 poisoned;
112 range; 113 local log failure. Stages: 0 reset, 55 initialization CMD55,
24 write command, 124 data response, 224 accepted-write busy, 324 rejected-data
completion, 13 status, 17 readback.

Do not remove the card or power off while writing. Failed/interrupted FAT updates
can leak clusters or leave FAT mirrors inconsistent; there is no atomicity,
repair or power-loss guarantee. After an ambiguous write, further writes are
poisoned and disarmed. Save evidence, then re-image before another write run.
The marker/fence is an operational safeguard, not a backup or security boundary.

Scope: marked primary FAT32, two mirrored FATs, short 8.3 names, 512-byte sectors,
prepared 1/8-sector clusters, single-block SDHC/SDXC commands. No arbitrary-volume
writer, resident-driver writes, long names, journaling or endurance certification.

## Development validation

    python3 driver/write/build.py
    python3 driver/tests/run.py --coverage /tmp/otter-coverage --mutations
    python3 driver/write/validate.py --normal --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe command --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe data --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe data --profile crc-reject-busy --boot-image DOS.img --dosbox MODEL_DOSBOX

Validation boots real MS-DOS from private copies and uses a private writable
WRITE.IMG. Successful runs undergo independent fsck.fat -n, mtools content checks
and a fresh read-only VERIFY whose image hash must stay unchanged. See README.md
for revision-specific results. Models do not reproduce physical electrical timing.

## Progress during long operations

PROGRESS: append reports written bytes every 4096 bytes and at completion;
PROGRESS: verify reports bytes checked every 8192 bytes for large files.
For BIG.BIN the denominator is 70000. These lines are flushed locally, so the
long operation after the smaller boundary files now has visible progress.
The normal PASS checkpoint still appears only after the whole operation passes.
