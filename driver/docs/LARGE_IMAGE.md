# Developer 500 MiB FAT32 SD image

For the empty END-USER image, use `dist/RELEASE/OTTERSD-FAT32-500MiB.zip`
and [INSTALLATION.md](INSTALLATION.md). The fixture below is for developers
and is not included in the public release.

OTTER500.IMG contains one 500 MiB FAT32 partition at a 1 MiB offset in an MBR
disk image. The entire image is 501 MiB. It uses 512-byte sectors, 4 KiB
clusters (eight sectors), two FAT copies, FSInfo and a backup boot sector.
The data area begins at 2 MiB, so both the partition and data are 1 MiB aligned.
It is a data disk, not a bootable DOS disk. Extra capacity on a larger card
remains outside this partition.

The previous small image intentionally used 512-byte clusters to exercise
allocation heavily. A 400 KiB file needs 100 clusters with this image instead
of 800. This reduces FAT allocation and chain traversal work. Sector writes
still transfer 512 bytes, with CRC and default readback verification. Larger
clusters do not remove that cost. Small files can waste up to 4095 bytes each.
Mount and unmount compare complete FAT copies; their cost can increase with
this larger volume. Measure copying separately from mount/unmount.

Eight KiB clusters would put a 500 MiB volume below the FAT32 minimum of
65525 data clusters. Four KiB keeps this image unambiguously FAT32. Changing
the sector size is a different operation and is not supported by this driver.
OTTERSD 1.0.0 reports 8 KiB logical allocation units to DOS on this volume,
scaling total/free counts to fit the legacy 16-bit interface. The physical
clusters stay 4 KiB. DIR should report about 499 MiB free initially, allowing
for the FAT/reserved area and supplied files. Reported free space rounds down
by less than 8 KiB. Read-only mode reports zero writable free space.
The cluster-count rule is specified in Microsoft's FAT specification:
https://www.cs.fsu.edu/~cop4610t/assignments/project3/spec/fatspec.pdf (pages 14-15).

## First hardware run

1. Back up the spare card. Flash OTTER500.IMG to the entire card with your
   usual image-writing tool. This replaces the partition table and files.
   Do not copy the image as a file or reformat the partition afterwards.
2. Boot DOS with the driver absent. Use Navigator to copy every file in KIT
   to a local writable directory, such as C:\OTTERSD. Exit Navigator.
3. Ensure CONFIG.SYS contains LASTDRIVE=S, FILES=40 and BUFFERS=10. Reboot.
   Remove any automatic installation of an older driver for this test.
4. From the local kit directory, run:

```
OTTERSD /DRIVE:S /PORT:330 /RW > INSTALL.LOG
TYPE INSTALL.LOG
OTTERSD /STATUS > STATUS.LOG
HWRT /INFO /PORT:330
HWRT /TEST /ERASE /PORT:330
HWRT /STRESS /ERASE /PORT:330
HWRT /MEMORY /PORT:330
OTTERSD /UNMOUNT > UNMOUNT.LOG
```

Use the real ISA port if different. Start with default verified writes.
Reboot without re-imaging, install the same driver with /RW, then run
HWRT /VERIFY /PORT:330. Preserve all logs separately for each card. MANUAL.TXT
explains the tests, expected negative-test messages and failure diagnostics.

## Copy timing

After the test passes, choose a local source directory containing a known
400 KiB file. Create S:\COPY and time:

```
MD S:\COPY
XCOPY C:\SOURCE\*.* S:\COPY /S /E
OTTERSD /UNMOUNT
```

Record copying and unmount times separately. After reboot, compare every
copied byte against the source, preferably also on the modern PC. Record card,
DOS/CPU, source size, cluster size and driver mode with the logs. Use the same
files and card for comparisons with the small image. The image does not
promise a particular physical speedup; software emulation cannot measure
the real ISA/card timing.

## Rebuild and emulation

From the repository root, with Python 3, mtools and dosfstools installed:

```
python3 driver/image.py --output /tmp/otter500 --kit driver/dist/KIT
```

The builder keeps the supplied OTTERSD.EXE/HWRT.EXE unchanged. It includes
standalone driver sources, source/file hashes and filesystem-check evidence
in OTTER500.ZIP. --reuse-image adds evidence without changing an already
tested image. It refuses to replace an existing image by default.

To exercise the exact image with a separately supplied genuine DOS boot
disk, licensed XCOPY/EXPAND media and the ISA SD model emulator:

```
python3 driver/tests/hardware.py --dosbox MODEL_DOSBOX --boot-image DOS_BOOT \
  --driver KIT/OTTERSD.EXE --tester KIT/HWRT.EXE --image OTTER500.IMG
python3 driver/tests/xcopy.py --dosbox MODEL_DOSBOX --boot-image DOS_BOOT \
  --expand-media EXPAND_MEDIA --driver KIT/OTTERSD.EXE --spc 8 \
  --image OTTER500.IMG --mode verified
```

Both harnesses modify private copies. Passing them qualifies the emulated
filesystem/driver interaction, not physical hardware or Windows reformatting.
