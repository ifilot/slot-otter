# Slot-otter real-hardware test manual (kit v1)

Use an expendable SDHC/SDXC card (4 GB or larger), your Slot-otter ISA card,
a bootable MS-DOS machine, and writable local storage (hard disk or floppy).
The target is an 8088/8086 with conventional DOS memory; no EMS or XMS is
required. MS-DOS 5.0 and 6.22 have been exercised in the emulator. DOS 3.1-6.x
is the intended range; other versions still need validation. A 5150 with
640 KiB conventional memory is a suitable target. Extra RAM above 640 KiB
is not automatically usable by DOS. The test program needs more temporary
memory than the 17,632-byte resident driver, including a 70,000-byte far
allocation for the segment-crossing test. A memory allocation failure is
reported separately from its subsequent read check.

This is an initial physical-hardware test kit. Emulator tests do not prove
ISA electrical timing or your hardware's behavior. Keep important files on
other media, save work, and use a clean boot for the first attempt.

## 1. Prepare the test card on your modern computer

1. Download/extract OTTERHW.ZIP. It contains OTTERHW.IMG, KIT, and source.
   SHA256.TXT beside the archive gives SHA-256 hashes of the archive and image.
   KIT/FILES.SHA gives hashes of the individual kit files.
2. Write OTTERHW.IMG as a RAW DISK IMAGE to the WHOLE expendable SD card.
   Select the SD card carefully: imaging replaces its partition table and
   destroys existing data. Do not write to your PC's disk, do not just copy
   the .IMG as a file, and do not write it into an existing partition.
3. Verify the written bytes against the image using your imaging tool's
   verification function, if available. The image is about 36 MiB, with an
   MBR and one small FAT32 partition; the remaining card capacity is unused.
   Do not resize or reformat the partition. Do not run filesystem repair.
4. Safely eject the card. Its root has README.TXT, BIG.BIN, FRAG.BIN,
   HIGH.TXT, EMPTY.TXT, HIDDEN.TXT, HELLO.COM, SUBDIR, KIT.TAG, and KIT.
   The deliberate fragmentation and high cluster number are test fixtures.
   KIT.TAG identifies this card before any write-denial tests run.

The image is DATA ONLY. It contains no MS-DOS operating system or boot files.
Use your own installed MS-DOS. You do not boot the PC from this SD image.

## 2. Copy the kit using the navigator, before installing OTTERFS

1. Start your PC in its existing DOS setup with NO resident OTTERFS.
2. Insert the prepared test SD into the Slot-otter slot.
3. Run your existing navigator application. Open the SD's KIT directory.
4. Create C:\OTTERTST on LOCAL storage (or A:\OTTERTST on a writable floppy).
   Copy ALL files from KIT into that local directory:

   OTTERFS.EXE  HWTEST.EXE  RUNTEST.BAT  CONFIG.TXT  MANUAL.TXT  FILES.SHA

5. Exit navigator completely. Do not run it while OTTERFS is mounted: it
   changes card protocol state outside the resident driver's control.
6. Change to the LOCAL kit directory. All tests and all logs run there.
   Do not run HWTEST or RUNTEST from the SD's S: drive. Keep enough free
   local disk space for logs and a 70,000-byte copied file (200 KiB minimum
   recommended). Copying off the card must leave its fixtures untouched.
7. Before installing the TSR, run (330 is hexadecimal):

   HWTEST /PREP /PORT:330

   This checks initialization, presence/identity, MBR/BPB, repeated raw
   sector reads, and buffer guards. It creates PREP.LOG locally. It uses
   real Slot-otter ports only, and refuses if OTTERFS is already resident.
   If it fails, STOP here and send PREP.LOG. Check card insertion, card
   format, ISA card, jumpers and port conflicts before trying installation.

## 3. Prepare CONFIG.SYS and reboot

1. Check that S: is unused by local disks, network software, SUBST and other
   drivers. This kit tests S: specifically. If S: is occupied, do not install
   this kit on S:; report the conflict so the test can be adapted.
2. Back up your current CONFIG.SYS and AUTOEXEC.BAT on the local boot disk.
   Keep a bootable recovery floppy available. Edit CONFIG.SYS and merge:

   LASTDRIVE=S
   FILES=40
   BUFFERS=10

   Use LASTDRIVE=Z if already needed by your setup. Retain essential device
   lines for your boot disk. Ensure FILES is at least 40. CONFIG.TXT is a
   reference snippet, NOT a replacement for your complete CONFIG.SYS.
3. OTTERFS.EXE is a TSR, not a DEVICE driver. Do NOT add DEVICE=OTTERFS.EXE
   to CONFIG.SYS. For this first test, install it manually after reboot.
   A clean boot without other optional TSRs is preferable for diagnosis.
4. Reboot normally with the test SD inserted. At the DOS prompt, switch
   to the local kit directory:

   C:
   CD \OTTERTST

   Substitute A: if you copied the kit to a floppy.
5. Install and inspect:

   OTTERFS /DRIVE:S /PORT:330 > INSTALL.LOG
   TYPE INSTALL.LOG
   OTTERFS /STATUS > STATUS.LOG
   TYPE STATUS.LOG

   Expected status: S: mounted, 0 open files, port 330. The resident size
   should be 17,632 bytes. Installation errors usually mean an unavailable
   drive letter, insufficient LASTDRIVE, unsupported DOS, or no usable SD.
   An empty slot may install successfully but stay offline: insert the
   prepared card and use OTTERFS /MOUNT before testing.
   Use your card's actual port instead of 330 in BOTH OTTERFS and HWTEST.
   RUNTEST.BAT uses default 330; edit its HWTEST lines to add /PORT:xxx if
   your jumper setting differs. Never experiment with arbitrary I/O ports.

## 4. Run the automatic suite

1. From the LOCAL kit directory, run:

   RUNTEST

2. Expect numbered PASS lines, followed by HARDWARE RESULT: 0 failures.
   The batch then runs S:\HELLO.COM and DOS COPY, and uses HWTEST /EXTRA
   to verify their output. Expect ALL AUTOMATED TESTS PASSED at the end.
3. Keep HWTEST.LOG, EXEC.LOG, COPY.LOG, EXTRA.LOG, INSTALL.LOG, STATUS.LOG,
   and PREP.LOG. The COM program should produce EXEC OK. COPIED.BIN must
   contain 70,000 bytes with the exact generated pattern; /EXTRA checks it.
4. The suite checks exact content and EOF, fragmented/large files, backwards
   seeks, independent searches, a directory spanning clusters, attributes,
   relative paths, empty files, high clusters, crossing a 64 KiB buffer
   boundary, 16 open slots, slot reuse, independent positions, rejected
   writes/create/truncate/delete/rename/mkdir/rmdir/attribute updates, and
   timestamp non-persistence. It then checks open-handle mount interlocks,
   offline reads, remount, stale searches, and current-directory reset.

WARNING: write-denial tests actually ATTEMPT mutations against the supplied
fixtures and expect rejection. A broken driver could damage the test image.
Only use the expendable test card. Successful tests should not write the SD.

Each log line is flushed immediately. The last visible numbered checkpoint
helps identify a hang. FAIL lines include errno, DOS error and extended DOS
error/class/action/locus. These snapshots can be stale for logical/content
failures; interpret them alongside the checkpoint. The runner handles DOS
critical errors by choosing FAIL rather than waiting at Abort/Retry prompts.

HWTEST returns ERRORLEVEL 0 for success, 1 for failed checks, and 2 when setup
is refused or the local log cannot be created/written. A WARNING/SKIP line means that named test was not exercised; report it.
DOS 3.1 may not support expanding the process handle table, so the full
16-slot capacity check can be skipped even with FILES=40. A stopped or incomplete
log is NOT a pass. Only the final HARDWARE RESULT line is authoritative;
an earlier RESULT line covers the reused filesystem portion alone.

## 5. Optional memory-pressure test (after automatic tests pass)

Save work. Close other programs. From local storage, run:

   HWTEST /STRESS /PORT:330

This reruns filesystem checks, locates the handler's actual resident DOS
memory block, allocates EVERY remaining free DOS block and overwrites it,
unmounts/remounts and reads while that memory is occupied, then frees it.
It detects memory incorrectly released by the TSR. It creates STRESS.LOG.
The expected resident MCB size is 17,632 bytes. Do this on the clean test
session, with a recovery boot disk; an implementation bug may crash DOS.
No SD write commands are issued by this stress step.

## 6. Optional physical empty-slot and reinsertion test

From local storage, run:

   HWTEST /SWAP /PORT:330

The program reruns filesystem checks, closes files, verifies mount interlocks,
and UNMOUNTS before asking you to remove the card. Remove it ONLY at the
explicit prompt. Press ENTER when the slot is empty. The empty-slot mount
must fail without hanging and the driver must remain offline. Reinsert the
SAME test card at the next prompt, then press ENTER. Remount, card identity,
old-search invalidation and directory reset must pass. Keep SWAP.LOG.

For a different-card test, use a second card imaged with the same image.
At the reinsertion prompt, insert that second prepared card instead; the
fixture must pass after an explicit mount. Label both cards. Record which
card was used. This verifies controlled replacement, not surprise removal.

Normal card changes: close all files on S:, move your current drive to a
local drive, run OTTERFS /UNMOUNT, remove/replace the card, then run OTTERFS
/MOUNT. Mount/unmount with live files returns access denied. Do not remove
the card during a read. Presence/identity checks detect missing/changed media,
but removal and reinsertion of the identical card entirely between checks
cannot be detected. Always unmount first, including before using navigator.
The driver remains installed after /UNMOUNT; reboot to remove the TSR.

## 7. What to send back, and recovery

On failure, do not keep retrying mutation tests. Preserve all local .LOG
files. Send them unchanged, plus:

- PC model and CPU; installed RAM and conventional free memory if known.
- Exact DOS version, CONFIG.SYS and AUTOEXEC.BAT (omit private information).
- Slot-otter hardware revision and port jumper setting.
- SD brand/model/capacity, which card, image SHA-256 and imaging method.
- Commands run, whether navigator exited, and whether the card was swapped.
- First FAIL, final result, or last visible line/photo if the machine hung.
- Whether a clean reboot reproduces the issue.

Useful errors: 2=file not found, 3=path not found, 4=too many files,
5=access denied (also DOS can translate offline errors to 5),
8=insufficient memory, 18=no more search results, 21=not ready, 30=read error.
A denied mount with files open is expected. Denial without open files is not.
A local log error means check local disk space/write protection, not SD writes.

If hung, photograph the screen, reboot from local/recovery media, and copy
out the logs before rerunning. Restore the saved CONFIG.SYS/AUTOEXEC.BAT if
needed. OTTERFS installed manually will disappear on reboot. Re-image the
expendable card after any failure of a write-denial check. To check that the
card stayed byte-identical, read back only the first IMAGE-SIZE bytes on your
modern computer and compare their SHA-256 to OTTERHW.IMG; hashing the entire
larger physical card is a different comparison. Do not let the modern OS
write metadata to the card before this comparison.

## Rebuilding the kit

All project source is under driver, independent of src. From the repository:

   python3 driver/hardware/build.py

Supply your own Turbo C 2/TASM via TOOLCHAIN_DIR, DOSBox via DOSBOX_BIN if
needed. Proprietary compiler binaries and MS-DOS are not redistributed.
The build emits driver/hardware/dist/OTTERHW.IMG, OTTERHW.ZIP, KIT and hashes.
The shared PROBE.C is also used by the existing booted-MS-DOS regressions.
