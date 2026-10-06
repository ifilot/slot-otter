> Historical implementation/kit record. The current consolidated driver,
> tester and release procedure are described in [driver README](../README.md).

# Standalone SD write investigation

`WTTEST.EXE` runs directly against Slot-otter, independently of DOS drive I/O
and the resident driver. All source stays under `driver`; nothing uses `src`.
The resident OTTERFS remains read-only, with its 17,632-byte allocation and
existing hardware baseline preserved. [MANUAL.md](MANUAL.md) describes the
separate marked image, opt-in modes, local logs and future hardware procedure.
No physical-card writing or 8088/5150 testing is performed by the build/tests.

## Current revision: v1.7

Hardware baseline: v1.6 NORMAL completed 111 checks and 1420 verified writes on
both SanDisk and Intenso. The tester reports successful fresh-boot VERIFY for
both. Their later CRCONLY logs show all pre-fault patterns passing, followed by
CRC rejection and clean CMD13/CID recovery, then different failures: Intenso
received no CMD17 data token; SanDisk accepted a correct-CRC 96 write but twice
read the original zeros. Both stopped before filesystem allocations.

v1.7 isolates the probes with /WRITE /CMDCRC and /WRITE /DATACRC. Each omits the
other error type and CRC-OFF, checks original scratch data immediately after
status/CID recovery, verifies a write that changes every byte, runs all sixteen
patterns and restores the original before the complete filesystem suite.
CRCONLY now qualifies access/patterns after the command probe before sending
the data probe. Unexpected post-probe data or read timeout poisons the session.

The transport previously deselected immediately on a CRC-rejection token.
It now observes bounded readiness while still selected, records rejected-data
busy samples and reports stage 324 on completion/timeout. Raw command CRC,
TX/RX, response bytes and data rejection/completion are logged before recovery
can replace transport state. Failed reads add first-32 token samples, poll count
and BIOS ticks. A rejected token alone never proves the scratch data unchanged.
PROGRESS lines expose large-file append and verification work between checkpoints.

These changes address a completion gap and improve diagnosis; they do not yet
establish the physical root cause or successful hardware CRC-error recovery.
The resident driver remains read-only. MANUAL.md describes the per-card,
per-mode fresh-image procedure and separate log names.

    python3 driver/write/validate.py --probe command --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe data --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe data --profile crc-reject-busy --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe data --profile data-read --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --probe data --profile data-discard --boot-image DOS.img --dosbox MODEL_DOSBOX

Model option PROBE_FAULT distinguishes command/data-triggered read timeouts,
accepted-but-unprogrammed writes, and CRC-valid changed readback. REJECT_BUSY
injects delayed or endless rejection completion; a fixture fails subsequent
reads if CS releases before rejected busy finishes. These reproduce/control
observables, not analog signals or a claimed real-card cause. Production models
remain read-only unless explicit writable flags are set.

Validation of v1.7: all 145 host tests (99 write plus 46 existing), unchanged
coverage floors, and 51 mutation checks (42 write plus 9 existing) passed.
Booted MS-DOS 5 with 1 MiB RAM passed 31 cases, including 26 invalid CLI
combinations, full single/combined-probe suites, strict eight-sector clusters,
independently triggered command/data read failures and discarded writes,
rejected-busy completion/timeout, untouched opposite-probe fixtures, normal
CRC/OFF controls, late busy, FSInfo hint handling and filesystem failures.
Every successful write case passed independent fsck/content/protected-cluster
checks and a fresh-boot VERIFY whose card hash stayed unchanged. Booted MS-DOS
6.22 also passed full DATACRC, independent checks and fresh-boot VERIFY with
1 MiB RAM. The packaged executable is the binary used for these DOS checks.
Physical v1.7 CRC-probe qualification remains the next hardware step.

## v1.6 baseline and validation

The v1.5 logs identify two separate issues: Intenso stopped at CMD55 with
non-error R1=00; SanDisk /CRCONLY accepted an FF write with clean status but
returned 508 zero bytes and four FF bytes twice, with valid received CRC.
The latter occurred after deliberate CRC-error probes, so CRC-OFF alone cannot
explain it. At that point neither card had completed filesystem write qualification.

v1.6 accepts CMD55 ready/idle (00/01), still requires ACMD41 readiness and valid
OCR/CID/CSD, and logs bounded initialization command history. Every raw pattern
now changes the last verified payload. All sixteen patterns run before any
negative probe; after negative probes, bounded status/CID recovery precedes a
second changing-pattern pass. Unexpected recovery status remains a poisoned
stop. Both raw passes must succeed before filesystem metadata changes.

The new /WRITE /NORMAL mode keeps CRC enabled and runs all ordinary raw and
filesystem tests without intentional bad CRCs or CRC-OFF transitions. Start
hardware qualification with NORMAL, preserve its logs, then use a fresh image
for /WRITE /CRCONLY to isolate error-probe recovery. See MANUAL.md for the exact
SanDisk/Intenso procedure and log names. /NORMAL, /CRCONLY and /NOCRC are mutually
exclusive; NORMAL and CRCONLY require WRITE.

Software validation: 131 host tests (85 write plus 46 existing) passed with all
coverage gates; 44 mutations (35 write plus 9 existing) were detected by test
assertions. Booted MS-DOS 5 with 1 MiB RAM passed 23 cases, including sixteen
invalid CLI combinations, normal/default/CRCONLY/NOCRC, strict eight-sector
clusters, CMD55-ready with repeated idle ACMD41, expected/unexpected recovery
status, corruption before/after negative probes, cold startup, FSInfo hints,
OFF-discard controls and late-busy safe stops. Successful writes passed
independent fsck/content/protected-cluster checks and fresh-boot read-only
VERIFY. Booted MS-DOS 6.22 cold INFO also passed with 1 MiB RAM and an unchanged
card image. Subsequent hardware NORMAL runs passed on both cards, with fresh-boot VERIFY
reported successful by the tester; combined CRC-error tests failed as documented
in the current v1.7 section. Model fixtures reproduce
observables rather than identifying the electrical/card root cause.

    python3 driver/write/validate.py --normal --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --crc-only --profile ready-cmd55 --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --crc-only --profile ff-before --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --crc-only --profile ff-after --boot-image DOS.img --dosbox MODEL_DOSBOX

## Safety and protocol decisions

The default `/INFO` mode performs initialization and identification only.
`/WRITE` requires a fresh marked WRITE.IMG, matching serial, geometry, marker,
clean-state flags, FAT mirrors and backups; it also requires confirmation unless
`/BATCH` is explicitly selected. An installed OTTERFS is refused before card
I/O, including an unmounted driver. Existing WTEST trees refuse another write
run, so each card/run starts from a newly imaged expendable card.

In default, /NORMAL and /CRCONLY modes, WSD.C sends correct CRC7 on all commands and enables CRC with CMD59 before
ACMD41. Reads verify CRC16. CMD24 sends correct CRC16 on every normal data
block, checks its data response, waits for busy completion, checks CMD13 R2,
and verifies all 512 bytes through a separate CRC-checked readback. Bounds and
BIOS-tick plus iteration limits cover polling. CID is rechecked before writes.
An uncertain/rejected normal write poisons the session: subsequent writes fail
without another CMD24. A failing local log also disarms writes immediately. No silent retry can obscure an accepted-but-timed-out
write. Accepted-write counts do not claim successful verification after a fault.

Bad CRCs are injected only into a reserved scratch sector with its own narrow
write fence. CRC-OFF accepts-versus-rejects behavior is reported, while CID
checks and readback happen with CRC enabled in these modes. Cards refusing CRC-OFF skip
that diagnostic and continue CRC-enabled testing; cards refusing CRC-ON are
refused for writes. The explicit /NOCRC alternative instead keeps command CRC7 and incoming CRC16
verification but sends dummy write CRC bytes and does not enable card CRC checks.

WFS.C restricts creation to its WTEST subtree and writes to the allowed FAT32
partition, excluding the MBR and boot/backup boot. New clusters are reserved,
zeroed and then linked. Data precedes published sizes; truncation/deletion
publishes the shorter/removed entry before freeing chains. FAT mirrors are
checked and updated; primary/backup FSInfo hints become UNKNOWN rather than
stale. FAT clean flags clear before allocations and set only after successful
verification. These ordering rules limit damage but do NOT make FAT32 updates
atomic: interrupted or failed operations may leak clusters, overallocate a
chain, or leave FAT copies different. No repair is attempted. Re-image on error.

## Coverage of the write suite

- CMD24 raw patterns, CRC rejection/policy, busy/status/verified readback.
- New root/nested folders, dot/parent entries, directory growth across clusters.
- Files of 0, 1, 511, 512, 513, 4096 and 70000 bytes, with exact size/data/EOF.
- Partial-sector append, cross-sector overwrite and preserved adjacent bytes.
- Truncation, zero-length release, cluster reuse, deletion and rmdir interlocks.
- New allocation above cluster/sector 65535 and sector-distinct test patterns.
- Interleaved allocations producing a deliberately fragmented new file.
- Duplicate/out-of-tree refusal, full-volume refusal and corrupt-chain refusal.
- Existing fixtures, protected original clusters and fresh-boot persistence.

Successful default runs have 177 checks for one-sector clusters and 289 for
eight-sector clusters. CRCONLY has 153, CMDCRC/DATACRC have 132, NORMAL and NOCRC
have 111, and CRC-OFF refusal has 173 with WARNING/SKIP (one-sector clusters).
A nonzero saved scratch may require an extra seed check. Each successful run
has a further 18 fresh read-only verification checks.
No test claims to certify full-card capacity, wear life or power-loss recovery.

## Reproduce development validation

```
python3 driver/write/build.py
python3 driver/tests/run.py --coverage /tmp/otter-coverage --mutations
python3 driver/write/validate.py --boot-image /path/to/DOS.img --dosbox /path/to/model/dosbox
python3 driver/write/validate.py --profile strict --spc 8 --boot-image /path/to/DOS.img --dosbox /path/to/model/dosbox
```

The emulator adapter/model must be rebuilt with the current sources in
`driver/emulation`. Writes are explicitly opt-in (`OTTER_MODEL_WRITE`); the
model and both adapters otherwise remain read-only. `validate.py` sets its own
private profile environment and uses private disk copies. It extracts the DOS
EXE from the shipped image, boots actual MS-DOS, uses `mtools` to independently
check exact contents, invokes `fsck.fat -n`, compares every originally allocated
data cluster, restarts the emulator/card for `/VERIFY`, and hashes the card to
prove verification issued no block writes. It never modifies the supplied DOS
boot image. Own Turbo C/MS-DOS copies are required; they are not redistributed.

Profiles: `tolerant`, `strict`, `slow`, `fixed-crc`, `reject`, `timeout`, `status`,
`corrupt`, `read-crc`, `no-crc`, `drop`, `resident`, `wrong-tag`, `cold-start`. Strict also
requires CRC enabled before ACMD41. Fault counts deliberately trigger failures
partway through filesystem operations, where stopping matters. Partial metadata
is expected on some injected failures; independent repair is never run.

Host tests include 99 write tests plus the existing 46 tests. Forty-two write
mutation probes show that tests detect wrong transmitted CRC, late CRC initialization, omitted CRC/status/fence/readback checks,
a missing FAT mirror, missing published sizes, leaked deleted clusters, omitted
board-latch initialization, omitted CMD0 startup retries, masked preflight CRC
errors, an overbroad FSInfo exception, a missing explicit hint opt-in, a pre-CMD0 ready
gate, missing startup clocks and immediate RX sampling;
the previous nine mutation probes are retained. Model coverage is merged across
its protocol and write-transport libraries without reducing the old 95%/80%
floors. Initial writer gates are 80% lines/65% branch outcomes for both WSD/WFS;
coverage measures host builds, while DOS integration exercises the DOS-only CLI.

Development runs on 2026-10-05 passed under booted MS-DOS 5.0 and 6.22 with
1 MiB emulated RAM, including strict CRC, both cluster sizes, busy delay, CRC-OFF
refusal and the fault/guard profiles. Existing read-only hardware-kit and
swap/CLI/transport emulator regressions also passed with the extended model.
These are emulator results; electrical behavior and real-card variations
remain for your later opt-in hardware runs.

## Earlier revisions and hardware feedback

The following sections retain the investigation and validation history. Current
hardware instructions are in MANUAL.md and the v1.6 section above.

### Cold-start correction after hardware feedback

A real SanDisk card required HWTEST/PREP before WTTEST/INFO. The first fix
(pull-latch setup and reset retries) did not fully resolve hardware cold start.
Three independent read-only reviews identified a pre-CMD0 wait for SPI-ready
that working HWTEST assembly does not impose. CMD0 now transmits regardless of
pre-reset MISO, while normal commands retain readiness waits. The exact working
clock train is reproduced: OUT base FF once, then twelve OUT base+1 pulse-only
operations (104 clocks including the load/pulse). Selected trailing clocks
precede CS release, followed by deselected clocks. Two nonclocking RX reads
space autonomous bursts before sampling/retriggering; this is conservative
I/O spacing, not a measured clock-divider or electrical timing guarantee.

The common C transport now runs against a register-level host bridge, avoiding
separate test implementations of byte/select/startup operations. New tests use
a native/nonready card that drives MISO low until a valid CMD0 after startup
clocks, plus transaction-delayed byte completion. Removing the CMD0 exception,
clock train or settling reads fails targeted mutation tests. Reset packets sent,
initial sampled MISO and transport phase are logged separately. The explicit
writable emulator model starts cold for every fresh DOS boot. No uncertain
block write is retried. Real electrical validation of this second fix is pending.

    python3 driver/write/validate.py --info --boot-image DOS.img --dosbox MODEL_DOSBOX

## FSInfo failure diagnosis

Hardware logs in logs/ show SanDisk initialization succeeds, followed by a
preflight error 107 at backup FSInfo LBA 2055 with zero accepted writes. /DIAG
now produces WDIAG.LOG with the preflight subcheck, independent sector/CRC
results, signatures, free/next hints, byte differences and both sector dumps.
The old combined read/comparison check masked transport errors as guard errors;
boot and FSInfo reads now retain the actual error code. The card's precise
discrepancy is still pending a diagnostic run.

/WRITE /ALLOWHINTS is an explicit exception only for valid FSInfo copies whose
sole differences lie in cached hints at bytes 488..495. The full preflight still
checks the marked image, boot/FAT mirrors, clean state and signatures. The
writer scans the FAT and invalidates both hints before allocation. Host tests
exercise the entire write suite after this exception and prove CRC failures,
invalid signatures and nonhint/boot/FAT/marker differences still stop writes.

    python3 driver/write/validate.py --diagnostic --profile fsinfo-mismatch --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --allow-hints --profile fsinfo-mismatch --boot-image DOS.img --dosbox MODEL_DOSBOX

The first is a read-only diagnosis of intentionally mismatched hints; the second
runs the full write suite, independent content/FAT checks and fresh-boot VERIFY.

## v1.3 CRC strategies and write failure evidence

Normal scratch qualification now precedes deliberate bad-CRC probes. /CRCONLY
keeps CRC enabled and omits CRC-OFF characterization; /NOCRC resets into the
default SPI CRC-OFF state without CMD59 and sends dummy FFFF write-data CRC
bytes, while still generating valid command CRC7 and checking received CRC16.
Both modes run the same allocation/directory/file and independent readback
tests. CRCONLY has 116 checks and NOCRC 113 for one-sector clusters, followed
by the usual 18 fresh verification checks. No automatic fallback is permitted
after an uncertain write. The default mode still characterizes CRC enforcement.

Write diagnostics snapshot the original CMD24 R1/data-response token, CMD13
status, transmitted/calculated CRC and requested policy. A CRC-valid mismatch
logs byte offsets and full expected/actual payloads, recognizes unchanged
original scratch data, and performs one additional read to characterize
stability. The first mismatch remains a hard failure even if the repeat matches.
Emulated accepted-but-unprogrammed CRC-OFF writes reproduce these observables;
this is a diagnostic fixture, not proof of the physical card's root cause.

    python3 driver/write/validate.py --crc-only --profile ignore-off --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --no-crc --profile tolerant --boot-image DOS.img --dosbox MODEL_DOSBOX
    python3 driver/write/validate.py --no-crc --profile strict-data --boot-image DOS.img --dosbox MODEL_DOSBOX

Windows is not a single SPI CRC reference: Microsoft documents native SD host
controllers and a separate USB mass-storage path for USB readers. Reader/host
hardware handles the card-facing bus, so the OS documentation does not establish
a universal SPI CMD59 policy.
https://learn.microsoft.com/en-us/windows-hardware/drivers/sd/sd-card-driver-stack

The SD physical-layer specification distinguishes native SD CRC protection from
optional SPI checking; CMD0/CMD8 still require valid CRC and SPI read blocks
include CRC16. SPI data framing retains the two CRC bytes when checks are off.
Sections 7.2.2--7.2.4 and 4.5, SD Association specification mirrored by NXP:
https://community.nxp.com/pwmxy87654/attachments/pwmxy87654/kinetis/28816/1/Simplified_Physical_Layer_Spec_3.01.pdf
NXP's SPI driver exposes CRC protection disabled by default:
https://mcuxpresso.nxp.com/api_doc/dev/4552/a00043.html

This alternative does not certify cards' electrical behavior or silent CRC
enforcement quirks. Hardware CRC-OFF qualification is pending a fresh opt-in run.

## v1.4 three-reviewer audit

The audit corrected conflicting /INFO modes, masked marker read failures,
zero-error CID/CSD rejection, overwritten initialization timeouts, and stale
logical verification errors. Requested mode/options are logged before card
initialization. Read-only verification names WVERIFY.LOG and VERIFY RESULT.
Write response history records every polled byte (up to the 100-poll limit).
A fully clocked CRC-failed read retains both CRCs and an UNTRUSTED payload dump;
these bytes never qualify verification. Repeat reads never clear a first failure.
An uncertain bad-CRC probe poisons the session too; only an explicit CRC-rejection
token allows that deliberate probe to continue.

Tests add independent Python CRC oracles, rejected/missing register commands,
delayed/missing/invalid read and write tokens, CMD13 R1 rejection, late busy
assertion, BIOS tick wrap/frozen tick limits, marker read faults, and repeat
CRC failure. Host coverage also gates the diagnostic suite (85% lines / 60%
branch outcomes); DOS-only CLI checks run against the compiled executable:

    python3 driver/write/validate.py --cli-checks --boot-image DOS.img --dosbox MODEL_DOSBOX

Additional DOS profiles: response-delay, missing-response, invalid-response,
status-r1 and late-busy. Successful profiles still require independent fsck,
mtools content verification and a fresh read-only verification process.

This establishes software behavior under modeled faults. Electrical timing,
actual card/controller quirks and power-loss robustness still require physical
hardware qualification; an uncertain write remains a hard stop with no repair.

Validation of v1.4: 113 host tests passed (67 write tests plus 46 existing
regressions), with all coverage floors satisfied; 34 mutation probes were
detected (25 write plus 9 existing). Booted MS-DOS 5 passed 13 invalid CLI
combinations and ten write profiles: default, strict/eight-sector clusters,
CRCONLY/ignore-off, NOCRC, NOCRC/strict-data rejection, missing response, invalid
response, CMD13 R1 rejection, late busy and delayed response. Successful write
profiles passed independent filesystem checks and fresh read-only verification.
Booted MS-DOS 6.22 also passed cold INFO/NOCRC with 1 MiB RAM and an unchanged
card image. This revision has not yet been qualified on physical hardware.

## v1.5 CRC-off controls and per-write busy evidence

The real v1.4 SanDisk log passed valid-CRC baseline writes/restoration, then
observed acceptance E5 and clean status for an invalid-CRC OFF write whose
readback twice matched the original zero sector. v1.5 inserts a valid-CRC OFF
positive control and restoration before that negative probe. Both controls
use the same ON/OFF identity and readback transitions. This separates a
general CRC-off failure from behavior tied to the invalid CRC. The default
command WTTEST /WRITE /ALLOWHINTS /PORT:330 exercises the new controls.

Successful baseline/control transactions now retain a WRITE TRACE in the log,
including each write's busy/status-ready samples, poll counts, BIOS ticks and
CMD13 transmit RX bytes. New fault tests exposed the possibility of accepting
busy zeros as status when busy asserted late: post-response readiness now
requires two idle bytes, and busy during CMD13 transmission is a poisoned
safe stop. Tests prove that a late-busy programming error is actually reported.
This is a modeled software defect, not proof of the cause on physical hardware.

The ignore-off profile discards all OFF writes and fails the positive control.
The new ignore-off-bad profile preserves valid OFF writes, discards only bad-CRC
OFF writes, and uses E5 acceptance to reproduce the narrower hardware
observables. Each failure remains fenced, poisoned and diagnostic-only after
the stop; no write retry or metadata repair is attempted.

    python3 driver/write/validate.py --profile ignore-off-bad --boot-image DOS.img --dosbox MODEL_DOSBOX

Host tests: 121 total (75 write plus 46 existing); 39 targeted mutation probes
(30 write plus 9 existing). The v1.5 hardware logs prompted the v1.6 investigation above.

Validation of v1.5 completed: all 121 host tests, coverage floors and 39
mutation probes passed. Booted MS-DOS 5 passed twelve write profiles (including
both OFF-discard cases, late-busy programming error and late command
interference), thirteen invalid CLI combinations, independent fsck/content
checks and fresh read-only verification of successful runs. Booted MS-DOS 6.22
INFO also passed with 1 MiB RAM and an unchanged card image. Those v1.5 artifacts have been superseded by the current v1.6 kit.
