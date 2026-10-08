# Developer 500 MiB FAT16 hardware-test image

For the empty END-USER image, use `dist/RELEASE/OTTERSD-FAT16-500MiB.zip`
and [INSTALLATION.md](INSTALLATION.md). The fixture below is for developers
and is not included in the public release.

`driver/dist/FAT16/OTTER16.IMG` contains a 500 MiB primary FAT16 partition
with 16 KiB clusters (32 sectors of 512 bytes each). The whole image is 501 MiB:
the partition begins at the 1 MiB boundary. This is a data card, not a DOS boot disk.

OTTERSD automatically detects FAT16 and FAT32. For this image use:

    OTTERSD /DRIVE:S /PORT:330 /RW /FAT16

`/FAT16` restricts mounting to FAT16; `/FAT32` restricts it to FAT32. Omit both
for automatic selection, including after a card swap. Neither option formats
or converts a card. Use the matching OTTERSD and HWRT files from this kit.

Follow the accompanying MANUAL.TXT for installation and the complete hardware
suite. Start with verified writes; `/NOVERIFY` deliberately weakens readback
protection. Save logs on the regular hard disk. Unmount before removing the
card or using Navigator. Re-image a disposable card before destructive tests.

This FAT16 volume has approximately 32,000 clusters, two roughly 63 KiB FATs,
and a fixed root directory with 512 entries. DOS reports its physical 16 KiB
allocation units directly. Subdirectories can grow; the root cannot grow. Long
Windows names consume additional root entries even though OTTERSD uses short
8.3 aliases. FAT16's larger clusters reduce FAT traffic for large files but
waste more space for small files. Sector transfers still use 512-byte blocks.

Windows can read this volume and copy files using its FAT support. Preserve
FAT16 if reformatting: FAT32 with 16 KiB clusters on 500 MiB has too few clusters
to be a valid FAT32 volume. The driver supports FAT16 volumes with 4,085 through
65,518 data clusters and rejects FAT12, GPT, and extended-partition layouts.
This image retains standard FAT16 geometry: one reserved sector, two FATs,
and 512 root entries. The data area is not separately padded to 1 MiB.

The original FAT32 images remain available and use the same dual-format
executables. The shipped test markers authorize writes only on disposable test
cards. Hardware results are required before claiming this new release is
qualified on a particular card or machine.


Reproduce emulation qualification after the main `validate.py --full` run:

    python3 driver/tests/large_kits.py --output /path/to/qualified-output \
      --dosbox /path/to/isa-model-dosbox \
      --boot-image /path/to/dos5.img --boot-image /path/to/dos622.img \
      --expand-media /path/to/licensed-expand-media.img --jobs 8

This builds both large formats and runs hardware-suite/persistence, unload,
verified and unverified XCOPY, read-only XCOPY, and DOS capacity checks on
private copies under both kernels. It bundles per-image evidence after success.
