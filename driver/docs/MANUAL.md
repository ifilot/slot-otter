# OTTERSD: real hardware test

Use a spare SDHC/SDXC card. Writing the supplied image replaces its existing
partition and files. Keep a bootable recovery floppy and back up the PC's
CONFIG.SYS/AUTOEXEC.BAT. Run this procedure separately on SanDisk and Intenso,
starting with a newly imaged card each time. Physical 8088 testing remains
deferred; an 80286 with 1 MiB is the immediate hardware target.

This kit tests OTTERSD through DOS file APIs. It does not talk directly to the
ISA card and does not deliberately send invalid CRCs. Keep the earlier WTTEST
kit and logs separately; never run a raw card utility while this driver is
mounted. Compilation uses Turbo C/TASM; emulation testing boots genuine DOS.
Passing emulation does not qualify physical hardware.

Failed installation, /MOUNT and /STATUS print the retained SD diagnostic;
HWRT /INFO saves it to RWINFO.LOG even when the drive is offline.

## 1. Image and copy the kit using Navigator

Write OTTERSD.IMG as a whole-disk image to the spare card using your usual PC
image-writing tool. Select the correct removable device. Do not copy the IMG
file into an existing filesystem. The image contains a small FAT32 partition,
read fixtures, a root RW.TAG identity marker, and a KIT directory.

Boot the DOS PC without either resident driver installed. Use Navigator to
copy every file from KIT to a writable local directory, for example C:\OTTERSD
or A:\OTTERSD. Required files are OTTERSD.EXE, HWRT.EXE,
MANUAL.TXT, CONFIG.TXT, FILES.SHA and SOURCE.SHA. HWRT includes its own
process-exit child tests; no companion executable is needed. The OTTERSD.ZIP source/evidence archive is retained on your development PC.

Exit Navigator completely before installing the driver. The driver and
Navigator must not own the SD card at the same time. Keep the test card inserted.

## 2. Configure DOS, reboot, and install

Merge these settings into the local boot disk's existing CONFIG.SYS:

```
LASTDRIVE=S
FILES=40
BUFFERS=10
```

Preserve the other boot-disk settings. Do not use DEVICE=OTTERSD.EXE: this is a
TSR redirector executable. For this qualification run, install it manually
after each reboot. Remove any existing automatic OTTERFS/OTTERWR/OTTERSD installation
from AUTOEXEC.BAT for the duration of testing. S: must be unused.

Reboot. Change to the local kit directory and run:

```
OTTERSD /DRIVE:S /PORT:330 /RW > INSTALL.LOG
TYPE INSTALL.LOG
OTTERSD /STATUS > STATUS.LOG
TYPE STATUS.LOG
HWRT /INFO /PORT:330
```

Use the actual configured ISA base port instead of 330 if it differs; port
values are hexadecimal. Installation must report verified read/write and a
mounted card. Without /RW, OTTERSD installs read-only and write tests refuse
to proceed. Use /RO to select read-only explicitly. Both modes use the same consolidated
42,896-byte resident allocation. Use OTTERSD 1.0.0 and HWRT 1.0.0 from the SAME kit. Replace earlier executable
files in your local kit directory; update any old AUTOEXEC.BAT command names.

Keep the complete local directory for each card, and copy its logs to a
separate labelled directory before starting the next card. /INFO prints the
cached mounted CID, manufacturer/product/serial, capacity, driver/test versions
and mount phase timings. Compare those records when relaying logs. HWRT 1.0.0 also prints DOS SPACE:
the logical allocation-unit size, total/free counts and byte capacities.
The 500 MiB image uses 4 KiB physical clusters but reports 8 KiB logical
units to DOS, with free space rounded down by less than one logical unit.
Read-only mode reports zero writable free space.

Run HWRT from the local directory, never S:. It creates local logs itself;
do not redirect them onto the SD card. /INFO validates the image marker and
original read fixtures without writing the card. A local log failure stops
the test. DOS critical errors return FAIL instead of waiting at a prompt.

## 3. First write test

```
HWRT /TEST /ERASE /PORT:330
```

/ERASE is the explicit authorization to create/delete test files. It does not
format the disk. /TEST requires the supplied image marker and a writable,
mounted enhanced driver with no open resident files. An existing RWTEMP
directory stops the initial test: do not delete it and retry after a failure;
preserve the log, reboot and re-image the card.

Every checkpoint prints PASS or FAIL. Expected access/lock rejections can print
DOS ERROR lines followed by PASS; those lines are intentional negative tests.
Their function/AX records are the direct INT 21h results. C errno/DOS errno and
extended errors can be stale after direct interrupt calls or local logging.
The final HWRT RESULT must say PASS with ERRORLEVEL=0. The program stops at the
first unexpected failure, reports driver/transport details, and returns 1.
Setup/usage/local-log problems return 2.

The suite exercises file creation, boundary overwrite, append, zero gaps,
zero-length truncate/extension, duplicates and shared handles, region locks,
attributes/timestamps, directory creation/removal, cross-directory moves,
grown-directory wildcard deletion, 64 KiB-crossing buffers, process exit with
unclosed handles/locks, interleaved allocation/reclamation, 70,000-byte new
files, and all-zero/all-FF payloads. It preserves the original read fixtures.

Default writes are intentionally expensive: every 512-byte sector is CRC checked,
waited to completion, read back with CRC, and compared exactly. Mount/commit
also check FAT metadata. Large volumes and an 8088 can take considerable time.
PHASE and PROGRESS lines identify directory growth, child-exit cycles, cluster
allocation and streamed-file work. TIMING lines measure phases and total time.
Keep the last visible checkpoint if progress stops; do not reset merely because
a directory operation takes longer than a file read. Installation reports SD
and filesystem BIOS ticks separately. Mount timings are short-operation,
16-bit measurements: an hour-long mount or midnight rollover can distort them.
HWRT phase timing handles one midnight; keep individual runs below 24 hours.

Keep RWTEST.LOG, INSTALL.LOG and STATUS.LOG before rerunning anything.

## 4. Stress and memory checks

```
HWRT /STRESS /ERASE /PORT:330
HWRT /MEMORY /PORT:330
```

/STRESS first verifies existing results, then performs twenty cycles of
allocation, writing, exact readback, deletion and cluster reuse. It verifies
the permanent results and original fixtures again. Preserve RWSTRESS.LOG.

/MEMORY allocates and overwrites all free DOS memory, exercises the resident
driver while that memory is occupied, releases it, and verifies the files
again. Save work before this command. RWMEM.LOG reports the DOS resident MCB
and the observed private-stack use. Pattern scanning measures this run; it
does not prove a worst-case IRQ/stack bound on all machines.

## 5. Flush, reboot, and verify persistence

```
OTTERSD /UNMOUNT > UNMOUNT.LOG
TYPE UNMOUNT.LOG
```

Close every file/application using S: first. Ordinary close writes and verifies
its data/metadata, but deliberately keeps the volume dirty. Explicit commit or
unmount still compares full FAT mirrors before marking it clean. Do not reset
or remove the card after /STRESS until /UNMOUNT succeeds. A successful unmount
commits the volume and leaves it offline. Reboot without re-imaging the card. Install the
same executable and mode as in step 2, then run:

```
HWRT /VERIFY /PORT:330
```

/VERIFY checks the completion marker, exact saved data, exact EOFs and final
timestamp. It writes no SD data. Preserve RWVERIFY.LOG as the reboot result;
copy it to a separately named local file before later /VERIFY runs overwrite it.
On the modern PC, also inspect the created files and use a read-only filesystem
check before making repairs. A successful immediate readback is insufficient
evidence of persistence after reboot.

## 6. Empty slot and re-insertion

Only after a successful test and reboot verification:

```
HWRT /SWAP /PORT:330
```

Follow the displayed prompts. It unmounts first, asks you to remove the card,
checks that an empty-slot mount returns a bounded error, then asks you to
reinsert the SAME card. It explicitly remounts and verifies saved results.
RW.TAG is shared by kit images; it is not a unique physical-card identity.
Reinserting the same card is your responsibility during this step.
Preserve RWSWAP.LOG. Do not remove a mounted card during an ordinary write test.
Test the second brand separately with a fresh image and new local log copies.

## 7. Report results and failures

Return all logs, the card brand/model/capacity, DOS version, CPU/RAM, ISA port,
driver executable hash from FILES.SHA, CONFIG.SYS/AUTOEXEC.BAT, and the last
visible checkpoint. Label SanDisk and Intenso logs separately. HWRT includes
its source identifier and driver mode in each log.

The SD line reports diagnostic error, stage, absolute LBA, R1, response token,
status, poison and attempts. FIRST preserves the first failure of the latest
sector write, even if its retry succeeded; later writes replace that snapshot.
Counters are cumulative since the last mount. /MEMORY and /SWAP remount, so
their final counters can reset. LAST CALLBACK is sticky and may describe an
earlier expected rejection rather than the operation immediately before it.
verified counts verified 512-byte sector writes, including FAT and directory
metadata. transmissions counts payload transmissions; retries counts additional
attempts after successful recovery. These are not file-operation counts.
LBA/stage/R1 can reflect a later read while FIRST/attempts still belong to the
latest write. The fields are not necessarily one operation's atomic snapshot.
Fields from a diagnostic query with CF=1 are unavailable, not evidence of health.

| SD diagnostic | Meaning |
|---|---|
| 101 | timeout waiting for command/token/busy completion |
| 102 | received CRC mismatch or card rejected data CRC |
| 103 | command/data response rejected |
| 104 | nonzero card status after write |
| 105 | CRC-valid readback differs from intended sector |
| 106 | identity/initialization/recovery could not be established |
| 107 | unsupported capacity/address range |

Normal stages are SD command numbers. Stage 124 waits for the CMD24 data
response, 224 for accepted-write busy completion, 324 for CRC-rejection busy
completion. A readback mismatch usually has stage 17. Token FE means a data
packet arrived; CRC or exact-content validation can still fail. FF commonly
means no response/token. Clean R1/status alone does not prove write success.
Poison=1 blocks further sector reads and writes and takes the volume offline.
Three attempts means the initial attempt plus at most two
retries of the same frozen sector/LBA, only after identity and usable reads
have been reestablished. Failed verification can occur after a sector changed.

Do not repeatedly run write commands after a failure. Keep the log and card
contents for analysis. Verified sector writes are not a transaction: power
loss/removal can leave leaked clusters, duplicate rename entries or mismatched
FAT copies. The driver does not automatically repair such a volume and refuses
writable mounting of unclean volumes and inconsistencies detected by mount
preflight; it does not perform a global allocation/crosslink scan. Use a fresh expendable
image for the next write qualification run.

## Supported scope

DOS handle-based file operations and short aliases are the qualification target.
LFN creation, FAT12/16 SD volumes, SDSC cards, booting DOS from the SD card,
and general DOS server/network functions are outside this kit. Standard FCB
wildcard deletion is covered; FCB record-I/O/process-abort lifecycle is not
qualified. DOS 5 and 6.22 are the actual-kernel test targets. The resident source
retains older DOS ABI handling and 8086 instructions, but that is not equivalent
to physical 5150 or DOS 3 qualification.

## Optional copy-throughput comparison

Use the default verified mode for the first run. The new FAT cache reduces
repeated reads without removing write readback. Version 0.9 retains the
filesystem traversal and far-memory copy improvements, but restores the
complete 0.6 C SD transport after the reported physical 0.7 mounting failure.
Repeat the verified hardware run first; physical confirmation of the recovery
build is pending. For ordinary files, create a
fresh destination directory and use your DOS version's XCOPY, for example:

```
MD S:\COPY
XCOPY C:\SOURCE\*.* S:\COPY /S /E
OTTERSD /UNMOUNT
```

Time the copy separately from installation and unmount. Unmount still audits
complete enabled FAT mirrors. Check the copied files after reboot, preferably
also with an independent byte comparison on your modern PC. Record source byte
count, elapsed time, card/CID, cluster size, mode, and the full installation log.
DOS5 XCOPY can return 1 after traversing an empty directory even when files were
copied; the automated tests compare this against an HDD-only control and verify
every byte. An exit code alone is insufficient for that case.

For a separate readback-disabled experiment, successfully unmount, reboot, then
install with:

```
OTTERSD /DRIVE:S /PORT:330 /RW /NOVERIFY > INSTALL.LOG
OTTERSD /STATUS
```

This mode can miss silently incorrect writes. It retains CRC, response/busy,
CMD13 status, identity and bounded recovery checks, but does not automatically
read and compare each completed write. It is fixed for that installation;
/MOUNT does not change it. Use a spare card and independent comparison after
reboot. HWRT prints the policy, and /VERIFY still compares saved test data even
in this mode. Its legacy `verified` counter then counts completed sector calls,
not sector readbacks. A clean FAT audit does not verify the contents of files.

There is no additional cache buffer or deferred writeback. The test image uses
512-byte clusters to exercise allocation heavily; the automated XCOPY gates
also exercise 4 KiB clusters, which require fewer FAT updates. Reformatting a
card for larger clusters is a separate operation; it is not required to use
the filesystem improvements or /NOVERIFY.

## Reclaim memory before running a game

The installer releases its temporary code, heap and startup stack automatically.
OTTERSD 1.0.0 retains 42,896 bytes of conventional memory including its PSP.
`/UNMOUNT` makes the drive offline but does not reclaim that memory. `/UNLOAD`
commits any closed-file changes, restores the drive's original DOS state and
interrupt vector, and releases the entire resident memory block.

Install this kit's OTTERSD.EXE and HWRT.EXE on your local hard disk; reboot once
to replace an older resident driver. Run games from your hard disk after unloading.
Copy any required game files from S: first. Exit programs accessing S:, close SD
files, and change to a local drive. For example:

```
C:
CD \OTTERSD
MEM /C > BEFORE.LOG
OTTERSD /UNLOAD
IF ERRORLEVEL 1 ECHO Unload failed - read the message before proceeding
MEM /C > AFTER.LOG
CD \DUNE2
DUNE2
```

MEM is supplied by later MS-DOS versions, not this kit; omit those two lines if
it is unavailable. Compare its largest executable program size and conventional
free memory. Successful unload prints "resident memory released" and returns
ERRORLEVEL 0. `/STATUS` then reports "not resident" (ERRORLEVEL 1); S: is unavailable.
No reboot or `/UNMOUNT` is needed before a successful `/UNLOAD`.

After leaving the game, reload from the local kit directory using the original
installation options:

```
C:
CD \OTTERSD
OTTERSD /DRIVE:S /PORT:330 /RW
OTTERSD /STATUS
HWRT /INFO /PORT:330
```

Use `/RO` or `/RW /NOVERIFY` if that was your chosen policy. Reload initializes
the card and validates the filesystem again. `/MOUNT` cannot reload a driver
that has been removed from memory.

Unload refuses while S: is the current drive or any SD file is open, including
redirected output on S:. Run the command and store logs on the local disk. If a
later TSR hooks INT 2F, remove that TSR first using its own supported procedure,
or reboot; OTTERSD never cuts it out of the interrupt chain. Installing OTTERSD
last usually allows unloading first. A failed write commit, poisoned card session, or card removal before a dirty
session was committed leaves OTTERSD resident: preserve `/STATUS` diagnostics and reboot to
recover. Do not remove the card or force-free its memory after that warning.

For the first hardware unload check, perform the normal /INFO and /VERIFY
checks, record MEM output before/after unloading, run Dune II locally, then
reload and repeat /INFO and /VERIFY. Keep the two MEM logs and any refusal
messages. Unloading recovers OTTERSD's allocation; DOS buffers, LASTDRIVE data,
and other drivers remain. It cannot guarantee a game will fit if those other
allocations still leave insufficient memory. Genuine DOS tests independently
check total free memory and the largest executable block return to their exact
pre-install values over three install/unload cycles, with open-handle and later
hook refusals, plus independently verified committed file contents and FATs.

## Optional faster mounting

Use the installation-only option /SKIPFATCHECK with /RW:

```
OTTERSD /DRIVE:S /PORT:330 /RW /SKIPFATCHECK
OTTERSD /STATUS
HWRT /INFO /PORT:330
```

The default is a full comparison of enabled FAT copies before writable mounting.
/SKIPFATCHECK skips that scan at installation and later /MOUNT operations; it
still compares the first FAT sector because clean/error flags share that sector
with allocation entries. Geometry, card capacity/identity, backup boot, primary
clean/error flags and FSInfo checks remain. FAT sectors are compared before
modification; dirty-session commit, /UNMOUNT and /UNLOAD still compare the full
FATs before marking the volume clean. These operations can therefore still take
time after writes. An unmodified, clean session needs no full commit scan.

On the 500 MiB image, this avoids roughly 1 MiB of mount reads. The startup
message identifies the skipped comparison and prints a warning; /STATUS and
HWRT logs record the policy. Compare MOUNT TIMING filesystem_ticks for strict
and fast installations on the same clean card to measure your hardware gain.
Unload the previous instance before changing policy. The option survives
unmount/remount but must be supplied again after a complete /UNLOAD.

A mismatch outside the first FAT sector can now remain undetected at mount.
It will be detected if that FAT sector is modified or during a dirty-session
commit; some writes may already have occurred before this failure. A clean
flag alone does not prove that the two FATs agree. The driver does not repair
or choose a winning FAT. Use a checked, expendable card for the first test.
/SKIPFATCHECK does not permit dirty volumes or bypass filesystem-format checks.

/NOVERIFY and /SKIPFATCHECK are independent. Both can be supplied with /RW;
CRC/status checks remain, but /NOVERIFY also removes write readback. For the
first fast-mount hardware run, keep readback enabled and perform /INFO,
/TEST /ERASE, /VERIFY, then /UNLOAD and a fresh-boot /VERIFY. Save the local
logs, status output and mount timings. Never store these logs on S:.

/RO already skips the full comparison, so /RO /SKIPFATCHECK is rejected.
Duplicate /SKIPFATCHECK and combinations with /STATUS, /MOUNT, /UNMOUNT or
/UNLOAD are rejected. This is a load-time policy, not a command that alters a
running driver's policy. Updating this kit requires replacing both local
executables and unloading the old version with its matching old executable,
or rebooting once. No card reformat is necessary.


## FAT16 and format restrictions (0.13)

The same OTTERSD executable mounts FAT16 and FAT32 automatically. `/FAT16` or
`/FAT32` may be added to the installation command to require that format. Do
not combine them; they are installation options, not formatting commands.
`OTTERSD /STATUS` and `HWRT /INFO` report the mounted format and restriction.
A card of the wrong format remains offline; the restriction also applies
when subsequently mounting another card. Omit both options to allow either.

The alternative `driver/dist/FAT16/OTTER16.IMG` provides a 500 MiB FAT16
partition with 16 KiB clusters. Use its matching KIT and follow the same test
steps in this manual. FAT16 has a fixed 512-entry root directory on this image;
create subdirectories for larger collections. FAT32 retains its growing root.
An exhausted FAT16 root returns disk full without extending the root or FAT.
FAT16 does not have FAT32 FSInfo or backup BPB sectors; their byte offsets are
not interpreted as metadata. Mirror, CRC, clean/error-flag, identity and write
readback checks remain in force for both formats.

## Read caching (0.15)

Both modes cache four 512-byte FAT sectors and two 512-byte directory sectors,
separately from the one-sector file-data buffer. `/RW` now retains each open
handle's cluster cursor between read requests. Writes invalidate cursors before
attempting their sector stores and invalidate matching cached sectors. Shared
handles still refresh file metadata; backward seeks restart traversal as needed.
Card identity checks and CRC checks remain. Mutation preflight discards cached
evidence and reads fresh directory/FAT data. There is no deferred writeback.

Use the existing unmount procedure before Navigator or any raw-sector tool
changes the mounted card. There is no new cache option and no need to reformat.
