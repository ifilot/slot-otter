# Historical recovery investigation: OTTERSD 0.7-0.8

This is a historical diagnostic record. For current OTTERSD 1.0.0 / HWRT
1.0.0 developer deployment and testing, use [MANUAL.md](MANUAL.md). The commands, old
version numbers and pending conclusions below describe the investigation
at that time; they are not current deployment instructions.

A run reported a mounting failure with 0.7, described as "card not ready" with
/RW /NOVERIFY. A freshly formatted card also failed. The SD phase reported one
BIOS tick and the filesystem phase zero. This suggests an early SD-access
failure, but a zero duration can mean less than one 55-ms tick; the diagnostic
snapshot determines the actual failing command. Formatting changes filesystem
contents and cannot repair an SD-command or packet-transfer failure.

Version 0.8 restores the entire C SD transport from the last working 0.6
release, including packet transfer, CRC16 and command framing CRC7. The separate
filesystem traversal and far memory-copy improvements remain. The 0.7 assembly
SD transport is removed. Later evidence showed SD error=0, stage=17, LBA=0, R1=00 and token=FE on a
separately formatted FAT32 card, while the supplied whole-disk image mounted
successfully. This points to a format/layout or boot-sector validation rejection,
not a failed SD command/CRC for that sector read. The original transfer-code
regression diagnosis was premature; the precise rejected field and the version
used in the successful image run still need confirmation. The emulator models protocol/access ordering;
it cannot prove elapsed electrical settling time on a physical ISA bus.

## Copy and reboot

The later recovery checkpoint used OTTERSD.EXE 0.11 and HWRT.EXE 0.9
from the same kit. Those version numbers are historical.
Version 0.9 retains the 0.8 transport; its additional change is DOS capacity
reporting. The preserved 0.8 kit is historical evidence. Copy all KIT files
to a local hard disk or floppy. If using Navigator, boot without a resident
driver, copy the files, and exit Navigator completely. Reboot before installing
the new driver: replacing a file cannot replace the already resident 0.7 code.
Keep LASTDRIVE=S in CONFIG.SYS. Keep the card inserted.

## First check: read-only

From the local kit directory, run:

```
OTTERSD /DRIVE:S /PORT:330 /RO > INIT08.LOG
TYPE INIT08.LOG
OTTERSD /STATUS > STAT08.LOG
TYPE STAT08.LOG
```

A successful install reports "Card mounted." Then run DIR S:\ and open or
copy an existing file to the local disk. No SD writes are enabled in this mode.
Use the actual hexadecimal ISA port if it differs from 330.

If mounting fails, the new installer and /STATUS print:

```
SD: error=... stage=... LBA_hex=... R1=... token=... status=... poison=... attempts=...
```

Collect a remount attempt and the full non-writing tester report:

```
OTTERSD /MOUNT > MNT08.LOG
TYPE MNT08.LOG
HWRT /INFO /PORT:330
```

HWRT stops because the drive is offline, but saves RWINFO.LOG with the retained
SD snapshot and counters. Send INIT08.LOG, STAT08.LOG, MNT08.LOG and RWINFO.LOG,
plus CPU/speed, DOS version and card make/model. An ordinary freshly formatted
card has no RW.TAG test-image marker; after successful mounting, HWRT /INFO may
stop at that marker check. That is a test-fixture refusal, not a mounting error.

## Second check: verified writable mode

After a successful read-only check, unmount and reboot:

```
OTTERSD /UNMOUNT
```

Install after the reboot with verification enabled:

```
OTTERSD /DRIVE:S /PORT:330 /RW > INITRW08.LOG
TYPE INITRW08.LOG
OTTERSD /STATUS > STATRW08.LOG
```

Check mounting before any copy or write test. If it fails, repeat the diagnostic
collection above. Otherwise use MANUAL.md for the full expendable-image hardware
suite. /TEST and /STRESS require the supplied test image and /ERASE. Start with
a newly imaged spare card as directed there. Independently verify saved files
after unmount/reboot. Resume /NOVERIFY experiments only after this verified run.

## Diagnostic interpretation

- DOS error 21 is "not ready"; the resident SD fields give the finer reason.
- SD error 101 is timeout; stage identifies the unanswered command/wait.
- SD error 102 is CRC mismatch. Stage 10 is CID; stage 9 is CSD; stage 17 is
  sector-read data. R1=00 and token=FE mean the command and packet token arrived,
  but the packet bytes/checksum did not agree.
- SD error 106 is identity/initialization failure. Stage 0, R1=FF indicates no
  acceptable reset response; another stage may indicate a rejected command or
  incompatible response. Include all fields rather than interpreting it alone.
- /NOVERIFY skips only successful post-write readback. It changes none of these
  initialization or read checks. /MOUNT retries using the installed access mode.

## Follow-up: FAT32 card fails, supplied image mounts

FAT32 describes the volume filesystem, not its disk partition layout. The
mount routines are unchanged from 0.6. They accept a FAT32 superfloppy or the
first primary MBR partition tagged 0B, 0C, 1B or 1C (hexadecimal). GPT/protective
MBR and FAT32 logical partitions inside extended partitions are unsupported.
The boot-sector signature, 512-byte sector size and FAT32 geometry must pass
validation; malformed superfloppy fields can also reject at LBA 0.

SD error=0, stage=17, LBA=0, R1=00 and token=FE indicates the sector read itself
succeeded without a recorded SD error. If mounting then returns DOS error 13,
the filesystem/parser rejected its contents. This should not be reported as an
SD wake-up or write-verification failure. A zero filesystem tick count alone
does not establish whether that parser ran.

The supplied image mounting on the same card is a useful control. Keep a copy
of the separately formatted layout or record its partition details before any
more formatting. On Windows, these read-only PowerShell commands show the
layout. Replace N with the SD card's disk number from the first command:

```
Get-Disk | Format-Table Number,FriendlyName,PartitionStyle,LogicalSectorSize,Size
Get-Partition -DiskNumber N | Format-List PartitionNumber,DriveLetter,Type,MbrType,GptType,Offset,Size
```

References: Microsoft Learn Get-Disk and Get-Partition:
https://learn.microsoft.com/en-us/powershell/module/storage/get-disk
https://learn.microsoft.com/en-us/powershell/module/storage/get-partition

Send the SD card's output and the complete installer error, plus the executable
version used in both runs. FAT32 alone does not establish a supported layout;
a precise diagnosis requires the partition/boot-sector contents, not another
reformat or removal of CRC checks.
