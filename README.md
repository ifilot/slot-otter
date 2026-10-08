# Slot-otter

[![Build and Release](https://github.com/ifilot/slot-otter/actions/workflows/build.yml/badge.svg)](https://github.com/ifilot/slot-otter/actions/workflows/build.yml)
![Version](https://img.shields.io/github/v/tag/ifilot/slot-otter?label=version)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

An 8-bit ISA card for accessing FAT16- or FAT32-formatted SD cards under MS-DOS.

![Slot-otter ISA card rendered](img/slot-otter-isa-card-rendered.png)

Slot-otter lets a DOS PC use an SD card as an ordinary drive. Fill the card
with files on a modern computer, insert it into your vintage PC, and copy or
run them from DOS. A working setup has three parts:

- the **Slot-otter card** in a free 8-bit ISA slot;
- the **OTTERSD driver** on the PC's hard drive, loaded at startup;
- an **SD card** with a FAT16 or FAT32 file system.

New users should read [How it works](#how-it-works) and
[Requirements](#requirements), then follow [Getting started](#getting-started)
step by step.

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Getting started](#getting-started)
  - [1. Set the port address](#1-set-the-port-address)
  - [2. Download the driver](#2-download-the-driver)
  - [3. Prepare an SD card](#3-prepare-an-sd-card)
  - [4. Install and load OTTERSD](#4-install-and-load-ottersd)
- [Using the card](#using-the-card)
  - [Changing or removing the SD card](#changing-or-removing-the-sd-card)
  - [Freeing memory for games](#freeing-memory-for-games)
  - [Write checks and read-only mode](#write-checks-and-read-only-mode)
  - [Browsing files with Nightwatch](#browsing-files-with-nightwatch)
- [Performance](#performance)
- [Hardware](#hardware)
- [Legacy Navigator](#legacy-navigator)
- [Development](#development)
- [License](#license)

## How it works

`OTTERSD` is the DOS driver for Slot-otter. It is usually started from
`AUTOEXEC.BAT`. It talks to the card over the ISA bus, reads the FAT16 or FAT32
file system on the SD card, and gives the card an ordinary drive letter such
as `S:`. From then on, DIR, COPY, XCOPY, games and other DOS programs use the
card like any other drive and never need to know it is an SD card.

A driver is needed because, on its own, MS-DOS can only use the storage the
PC's BIOS already supports, which means floppy drives and hard disks. Any
other storage device needs a small program that stays in memory and turns DOS
requests such as "open this file" or "list this directory" into commands the
hardware understands. CD-ROM drives are the familiar example. Before a `D:`
drive appears, `CONFIG.SYS` has to load the manufacturer's CD-ROM driver and
`AUTOEXEC.BAT` has to run `MSCDEX`. `OTTERSD` does both of those jobs in a single
program.

## Requirements

Check these before you start. The driver refuses cards or file systems it
cannot handle safely.

- **PC:** an 8088/8086 or later processor and a free 8-bit ISA slot.
- **DOS:** MS-DOS or PC-DOS 3.1 through 6.x.
- **Memory:** about 42 KiB of conventional memory while the driver is loaded.
  No EMS or XMS is needed.
- **SD card:** SDHC or SDXC, at least 501 MiB. Older SDSC cards (2 GB and
  smaller) are not supported.
- **File system:** FAT16 or FAT32 with standard 512-byte sectors on an MBR
  partition. FAT12, exFAT, GPT and extended partitions are not supported.
- **File names:** the usual DOS limit of eight characters for the name and
  three for the extension, such as `DUNE2.EXE`.

## Getting started

Setting up Slot-otter for the first time takes four steps. The first is done
on the card before it goes into the PC, the third on a modern computer, and
the rest under DOS.

1. Set the card's port address and install it in the PC.
2. Download the driver and copy it to the DOS hard drive.
3. Write an empty FAT16 or FAT32 image to an SD card and add your files.
4. Install and load OTTERSD.

### 1. Set the port address

The PC talks to expansion cards through I/O ports, small numbered addresses
that each card listens on. Slot-otter occupies four consecutive ports. The
driver needs to know where they start, and no other card in the PC may use
the same ones.

The base address is set with the 8-position DIP switch labelled **ADDR SEL**
(SW1). Each switch stands for one value. Switches that are ON add their
values together to give the base address; switches that are OFF add nothing.

| Switch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Value (hex) | 200 | 100 | 80 | 40 | 20 | 10 | 8 | 4 |
| **330h** (default) | ON | ON | OFF | OFF | ON | ON | OFF | OFF |
| **300h** | ON | ON | OFF | OFF | OFF | OFF | OFF | OFF |

For example, 330h = 200h + 100h + 20h + 10h, so switches 1, 2, 5 and 6 are ON.
The examples in this README and the driver documentation use 330h. Choose any
free address from 100h to 3FCh. Sound cards often use 330h for their MIDI
port, so pick another address, such as 300h, if your PC has one. Whatever you
choose, pass the same value to the driver with `/PORT:` in
[step 4](#4-install-and-load-ottersd).

With the PC switched off, insert the card into a free 8-bit ISA slot.

### 2. Download the driver

The driver is distributed as a ZIP for copying with a modern PC, as a bare
executable, and as floppy images for PCs that only have a floppy drive. Get
the [latest release](https://github.com/ifilot/slot-otter/releases/latest):

- [OTTERSD-DOS.zip](https://github.com/ifilot/slot-otter/releases/latest/download/OTTERSD-DOS.zip): driver, instructions and license.
- [OTTERSD.EXE](https://github.com/ifilot/slot-otter/releases/latest/download/OTTERSD.EXE): driver executable.
- [floppy_360k.img](https://github.com/ifilot/slot-otter/releases/latest/download/floppy_360k.img): 360 KiB, 5.25-inch DD.
- [floppy_720k.img](https://github.com/ifilot/slot-otter/releases/latest/download/floppy_720k.img): 720 KiB, 3.5-inch DD.
- [floppy_1440k.img](https://github.com/ifilot/slot-otter/releases/latest/download/floppy_1440k.img): 1.44 MiB, 3.5-inch HD.
- [SHA256.TXT](https://github.com/ifilot/slot-otter/releases/latest/download/SHA256.TXT): checksums for checking that downloads are intact.

Floppies contain only the driver, user instructions, configuration example
and license. They contain no testing utilities and are not boot disks.
Write them to physical floppies or use GoTek,
[BitstreamBeaver](https://github.com/ifilot/bitstream-beaver) or FlashFloppy.

### 3. Prepare an SD card

The easiest way to get a card in the right format is to write one of the
ready-made images to it on a modern PC. Both images contain an **empty,
formatted partition** with no files or folders. After writing one, copy your
files onto the card with the same PC.

**Recommended: [500 MiB FAT16, 16 KiB clusters](https://github.com/ifilot/slot-otter/releases/latest/download/OTTERSD-FAT16-500MiB.zip).**
This gives a useful balance of storage space and write speed. A cluster is
the unit of space the card assigns to a file. Larger clusters mean less
bookkeeping when growing a file, although small files take up more space.

An alternative [500 MiB FAT32 image with 4 KiB clusters](https://github.com/ifilot/slot-otter/releases/latest/download/OTTERSD-FAT32-500MiB.zip)
is also available.

Extract the ZIP and write its IMG to the **entire card**. This replaces existing
partitions and files: back up first and select the correct device. Do not copy
the IMG as a file or reformat the card afterwards. The image occupies 501 MiB,
including a small area before the 500 MiB partition. On a larger card, the
remaining space is unused by this image. These images hold your files; they
do not boot DOS.

A card that is already formatted FAT16 or FAT32 and meets the
[requirements](#requirements) can also be used without writing an image.

### 4. Install and load OTTERSD

The driver is copied to the hard drive and started like any other DOS program.
It must not be loaded from the SD drive it provides.

Copy OTTERSD.EXE to a directory on your DOS hard drive, such as `C:\OTTERSD`.
Choose an unused drive letter; this example uses `S:`. Add `LASTDRIVE=S` to
CONFIG.SYS (or keep an existing value of S or later), then reboot, insert the
SD card and load:

```dos
C:\OTTERSD\OTTERSD /DRIVE:S /PORT:330 /RW
```

`/PORT:330` must match the DIP-switch setting from
[step 1](#1-set-the-port-address). `/RW` enables writing with read-back checks.
Omit it or use `/RO` for read-only access. Once the driver reports that the
card is mounted, you can use commands such as `DIR S:\`.

Add the loading command to AUTOEXEC.BAT if you want it to run at startup.
Run OTTERSD as a program; do not add it as a `DEVICE=` line in CONFIG.SYS.
See the [installation guide](driver/docs/INSTALLATION.md) for the full setup
and available options.

## Using the card

Once loaded, the SD drive behaves like any other DOS drive. A few things
differ from a fixed hard disk, mainly because the card can be removed and the
driver can be unloaded.

### Changing or removing the SD card

**Always unmount before removing a card, and mount again after inserting one.**
Treat this like safely ejecting a card on your modern PC. DOS programs and
the driver can keep file data and information about the card in memory.
Removing or swapping a mounted card can lose changes or cause the driver
to use information belonging to the previous card, risking file corruption.

1. Finish copying and close any programs using the SD card. Return to a
   drive other than the SD card, such as `C:`.
2. Run `C:\OTTERSD\OTTERSD /UNMOUNT`. **Wait for it to succeed before
   removing the card.** If it reports an error, leave the card inserted
   and resolve the error first.
3. Remove the card and insert the card you want to use.
4. Run `C:\OTTERSD\OTTERSD /MOUNT` and wait for it to succeed before
   accessing the SD drive again.

Follow these steps even when reinserting the same card, especially after
changing its contents on another computer. Unmounting leaves the driver
loaded, so you do not need to reboot to change cards.

### Freeing memory for games

Some games need every kilobyte of conventional memory. The driver can be
removed from memory without rebooting: close programs using the SD card,
switch to your hard drive and run `C:\OTTERSD\OTTERSD /UNLOAD`. Run the
loading command again to bring the SD drive back.

### Write checks and read-only mode

With `/RW`, every block written to the card is read back and checked before
the write is reported as successful. With `/RO`, or without either option,
the card is mounted read-only and nothing on it can be changed. The access
mode is fixed when the driver is loaded; reboot to change it.

### Browsing files with Nightwatch

For browsing and copying files, we recommend
[Nightwatch](https://github.com/ifilot/nightwatch) together with OTTERSD.
Nightwatch is a separate project and is not bundled in these downloads.

## Performance

File-copy tests on an **80286 running at 20 MHz** gave these results:

| Direction | FAT16 card | FAT32 card |
| --- | --- | --- |
| To the SD card | 15 KiB/s | 10 KiB/s |
| From the SD card | 38 KiB/s | 38 KiB/s |

These are measured file-transfer speeds, not guaranteed speeds for every
system or card. FAT16 was faster when writing in these tests; reading was
equally fast with both formats. Speeds also depend on the CPU, the ISA bus
and the disk being copied to or from.

## Hardware

The KiCad design files for the card are in [pcb/release](pcb/release),
including the schematic as a [PDF](pcb/release/isa-sdcard.pdf) and the BOM
and placement files for assembly. The card is built from standard 74-series
logic. A 74HCT688 compares address lines A2 to A9 with the DIP-switch setting
described in [Set the port address](#1-set-the-port-address).

## Legacy Navigator

OTTERNAV remains available for users of the older software. It accesses the
card directly, without loading OTTERSD. Its source is under [src](src/README.MD), with a separate
[OTTERNAV.EXE download](https://github.com/ifilot/slot-otter/releases/latest/download/OTTERNAV.EXE).
It is not included on the OTTERSD floppies. Unmount OTTERSD before using Navigator
on the same card.

## Development

Standalone driver source, build scripts and regression tests live under
[driver](driver/README.md), together with the technical documentation.
Turbo C 2.0 and TASM 2 build the binaries.
[DOSBox-VirtIsa](https://github.com/ifilot/dosbox-virtisa) models the ISA interface;
real DOS kernels and hardware provide additional validation. Developer hardware
kits and test images are separate from public downloads. Disk images,
release packages and build outputs are generated by the tools and GitHub
Actions; they are not stored in the source repository.

## License

Slot-otter is released under the
[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0).
