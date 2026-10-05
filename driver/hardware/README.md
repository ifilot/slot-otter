# Physical-hardware test kit

Read [MANUAL.md](MANUAL.md) for the human workflow. `build.py` produces a
37,465,088-byte MBR/FAT32 data image, a ZIP containing the image, the local DOS
kit and standalone source, and SHA-256 manifests in `dist/`. It does not write
physical devices or include a DOS operating system. The DOS runner is 8086
code built with Turbo C 2 and TASM; its transport uses the driver's real SD
implementation and never accesses emulator-only control ports.

`HWTEST.C` reuses `tests/PROBE.C`, adding a dual screen/local-file logger,
numbered checkpoints, errno/extended DOS error snapshots, fixture and resident
identity guards, raw transport checks before installation, mount interlocks,
offline/remount/search checks, and optional human-prompted `/SWAP` and `/STRESS`.
`RUNTEST.BAT` also runs a COM executable and DOS COPY, and `/EXTRA` checks their
local outputs. The TSR is installed manually after configuring LASTDRIVE;
it is not a CONFIG.SYS DEVICE executable.

Build using your own toolchain and installed DOSBox:

```
python3 driver/hardware/build.py
```

Validate with your own bootable MS-DOS floppy and the existing DOSBox-VirtIsa
Slot-otter adapter. The script uses private copies and extracts its EXEs from
the actual shipped image. It checks the FAT32 partition with `fsck.fat -n`,
compares extracted files, runs under booted MS-DOS with 1 MiB emulated RAM,
checks setup refusal, verifies COPY/EXEC and memory pressure, compares the DOS
MCB to 17,632 bytes, and hashes the card before/after.

```
python3 driver/hardware/validate.py --boot-image /path/to/dos.img --dosbox /path/to/adapter/dosbox
python3 driver/hardware/validate.py --fault tag --boot-image /path/to/dos.img --dosbox /path/to/adapter/dosbox
python3 driver/hardware/validate.py --fault data --boot-image /path/to/dos.img --dosbox /path/to/adapter/dosbox
```

The fault modes modify only the private image copy. A wrong marker must refuse
before mutations; a wrong data byte must report failure, its first byte offset
and ERRORLEVEL=1. These distinguish an effective test from one that merely
prints success. Hash checks still require zero changes by the DOS tests.

Validated on 2026-10-05 with MS-DOS 5.0 and 6.22: 17 PREP checks, 46 normal
checks, 5 COPY/EXEC verification checks, and 53 stress checks, all zero failures.
The two injected-fault tests passed on 6.22. The 46 host unit tests, 9 mutation
regressions and existing booted-DOS 6.22 swap/CLI/transport suite also passed.
This verifies DOS behavior in the card model, not physical ISA electrical timing.
The human-prompted physical removal/reinsertion test awaits real hardware.
