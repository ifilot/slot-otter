# OTTERSD 1.0.0

OTTERSD exposes the Slot-otter SD card as an ordinary DOS drive letter for
COPY, XCOPY, games and file managers. For browsing and copying files, we
recommend Nightwatch: https://github.com/ifilot/nightwatch

## Downloads and card preparation

OTTERSD-DOS.zip and the 360 KiB, 720 KiB and 1.44 MiB installation floppies
contain only OTTERSD.EXE, README.TXT, CONFIG.TXT and LICENSE.TXT. These are
data/install disks, not DOS boot disks.

Recommended: OTTERSD-FAT16-500MiB.zip, an empty 500 MiB FAT16 volume with
16 KiB clusters. Hardware trials showed faster writes than the earlier FAT32
configuration. Larger clusters reduce allocation/FAT work but use more space
for small files. Physical sectors remain 512 bytes.

Alternative: OTTERSD-FAT32-500MiB.zip, an empty 500 MiB FAT32 volume with
4 KiB clusters. Larger clusters at this capacity would produce too few
clusters for a valid FAT32 volume. Neither image contains files, directories,
utilities or markers. ZIP instructions/checksums are outside the SD filesystem.

Back up the card, extract the chosen ZIP and write its IMG to the ENTIRE
removable card with your image-writing tool. This replaces its partitions
and files: select the correct device carefully. Do not copy the IMG as a file
or reformat afterwards. You can copy files to the volume on Windows before
moving it to DOS. Use an SDHC/SDXC card at least 501 MiB in size: the whole
disk image includes a 1 MiB partition offset. Extra capacity on a larger
card remains outside the supplied partition. The SD images are not boot disks.
Install OTTERSD separately from the floppy or DOS ZIP.

## Install under DOS

1. Boot your existing DOS system. Copy the driver package to a local
   directory such as C:\OTTERSD. Do not load it from the SD drive it provides.
2. Merge these settings into CONFIG.SYS, preserving its other settings:

       LASTDRIVE=S
       FILES=40
       BUFFERS=10

3. Reboot, insert the card, and ensure S: is unused. Run:

       C:\OTTERSD\OTTERSD /DRIVE:S /PORT:330 /RW

   Port values are hexadecimal. Replace 330 with your configured ISA port.
   /RW enables writes and verifies them by reading back before reporting
   success. Use /RO instead for read-only access, also the default when
   neither option is supplied. FAT16/FAT32 detection is automatic.
4. Once the driver reports that the card is mounted, use DIR S:\, COPY,
   XCOPY, games or Nightwatch as you would with an ordinary DOS drive.
5. Add the loading command to AUTOEXEC.BAT for automatic installation.
   This is a TSR executable: do not use DEVICE=OTTERSD.EXE in CONFIG.SYS.
   Reboot when replacing an older resident driver.

Existing supported MBR volumes can also be used without imaging them.
/FAT16 or /FAT32 restricts mounting; neither formats or converts the card.

## Removal, replacement and memory

Close files and applications using the SD drive. Switch to the local disk
and unmount before removing the card:

    C:
    C:\OTTERSD\OTTERSD /UNMOUNT

Insert the replacement and run OTTERSD /MOUNT. /UNMOUNT keeps the driver
resident. To reclaim its approximately 42 KiB of conventional memory for a
game, run OTTERSD /UNLOAD after closing files and switching to a local drive.
Unloading flushes filesystem state and refuses unsafe conditions, including
open files or a later resident program hooking its interrupt chain.

Never use the legacy Navigator or raw-sector software on a mounted card.
Unmount first. OTTERSD /STATUS displays the current drive state.

## Performance options

Start with ordinary /RW. Installation-only options are:

- /SKIPFATCHECK: skip the full mirror comparison at mount. Modified FAT
  sectors and commit/unmount checks retain their comparisons.
- /NOVERIFY: skip successful post-write readback. CRC, status, identity and
  bounded recovery remain, but silent corruption can escape detection.

Read positions and metadata caches are automatic. Copy speed also depends
on CPU speed, the ISA interface and the destination disk.

## Requirements and diagnostics

Target: 8088/8086 or newer, MS/PC-DOS 3.1 through 6.x, Slot-otter ISA card,
SDHC/SDXC card, FAT16/FAT32 and 512-byte sectors. The driver uses approximately
42 KiB of conventional memory and needs no EMS or XMS. DOS 5 and 6.22 have
been tested in emulation; physical 8088/5150 testing remains pending.

Files use DOS short names or existing 8.3 aliases. GPT, extended partitions,
FAT12, exFAT, SDSC and long-name creation are unsupported. The supplied FAT16
root has 512 entries; subdirectories can grow. Windows long names consume
additional entries even when DOS uses their 8.3 aliases.

If installation fails, retain its complete output and run /STATUS. Report
version, DOS version, CPU/RAM, port, card model, filesystem, and the printed
DOS/SD error, stage, LBA, R1, token and poison fields. Do not keep retrying
writes after a failed or poisoned session.

Source and releases: https://github.com/ifilot/slot-otter
License: GNU GPL version 3 or later; see LICENSE.TXT.
