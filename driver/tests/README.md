# Consolidated test infrastructure

Run `python3 driver/validate.py` to run host tests, coverage and mutations,
build OTTERSD.EXE and HWRT.EXE together, and package a candidate release.
Use `--full --dosbox PATH --boot-image DOS5 --boot-image DOS622` for actual DOS
read-only/CLI/EXEC/swap, write fault profiles, tester guards and final-image
stress/memory/reboot checks. All images are private copies. Physical testing
follows [the manual](../docs/MANUAL.md); the source tree is standalone from src.

- `kit_fixture.py`: one shared FAT32 image builder used by host/native/release
  tests; preserves known patterns, backup BPB and FSInfo. `fixture.py` supplies
  the basic fragmented read fixture. No old utility builder is imported.
- `emulation/`: shared card model and DOSBox/86Box adapters. Required for
  protocol/fault coverage; these are test tools, not resident code.
- `reference/`: historical CRC diagnostics and FAT routines compiled as host
  libraries to preserve independent regression/fault checks. Also contains the
  old read transport exercised by the native SDPROBE. These files have no
  standalone installer/build/package workflow and no released executables.
- `test_*.py`, `*_mutations.py`: production/reflection safety and mutation gates.
- `hardware.py`: native harness for the one public HWRT tester, including guards
  and a private emulator swap-input wrapper absent from the real executable.
- `integration.py`, `rw_integration.py`: internal DOS API/CLI/transport probes
  against the CURRENT OTTERSD executable. CLIPROBE uses a large inherited DOS
  environment and checks exit status, vector restoration and allocation cleanup.

`python3 driver/tests/run.py --coverage /tmp/coverage --mutations` runs host
checks alone. Its optional `--build` builds the canonical driver/tester pair.
PORTBODY.H is shared with the far installer; exhaustive tests cover its actual
parser. Coverage floors and behavioral mutation counts remain enforced.

Independent mtools comparisons and fsck.fat -n check images after DOS operations.
BIOS-tick timings describe emulation only; electrical/card and physical 8088
qualification require hardware. DOS boot images and compilers are supplied
separately and are not included in the release archive.

`xcopy.py` runs genuine DOS XCOPY against a private FAT16 BIOS hard drive and
modeled SD. A 400 KiB file, nested/empty directories, 30 boundary-sized files,
read-only refusal, both write policies and cluster sizes 1/8 are exercised.
The HDD-only tree control captures the DOS5 empty-directory exit-code behavior.
Independent comparisons include bytes, sizes, timestamps and attributes; a
fresh boot copies the large file back to the HDD without SD writes, followed
by fsck. XCOPYT.C captures BIOS ticks/counter deltas before unmount's audit.
Licensed XCOPY/EXPAND are supplied on the external DOS media, not distributed.


`fast_native.py` is a private emulation-only probe of FASTIO.ASM, using genuine
DOS, a licensed Turbo C/TASM toolchain and the OTTER_MODEL_TEST adapter. It
checks independent CRC vectors, ABI/segments/DF/IF and odd copy guards, then
writes/restores a reserved scratch sector of its private image with three-access
burst settling. CRC/transport now use the restored production C code.
--mutations proves broken odd-tail copying and reversed copy direction are
caught. These raw probes are not included in KIT or intended for mounted hardware.
`rw_integration.py --profile settle` checks the same delay in the resident DOS
API flow. Model ports 335/336 are test instrumentation, absent on the ISA card.
`performance.py --label LABEL` counts real command traffic at SPC1/8 with exact
contents and fsck; host elapsed seconds do not measure assembly or DOS throughput.
Native XCOPY additionally reads under the writable mount before unmount/reboot.

Initialization failure modes in hardware.py inject a missing CMD0 response or
rejected CMD10 or a corrupt CID packet CRC. validate.py runs all three with
write readback enabled and disabled;
installation, /STATUS, failed /MOUNT and offline HWRT /INFO must preserve the
same SD evidence and leave the entire card image unchanged. A count-based
settling model cannot reproduce every elapsed-time regression on ISA hardware.


FAT16 regressions are in test_fat16.py and test_fat16_redirector.py; the fixture
builder fat16_fixture.py produces fixed-root FAT16 without importing Navigator.
The host runner merges both formats' production-code coverage while keeping
library outputs separate, so repeated compilations cannot overwrite loaded
coverage notes. test_large_image.py independently checks the 500 MiB FAT16
geometry and all original read patterns. After full main-kit qualification,
large_kits.py builds/qualifies both 500 MiB kits under the supplied real DOS
kernels; see docs/FAT16_IMAGE.md for the reproducible command.

Public release safety is exercised by test_release.py: exact floppy allowlists,
empty FAT16/FAT32 images, mirrors, backups/FSInfo, geometry, ZIP integrity and
version/tag consistency. release_integration.py boots real DOS with the public
floppy binary and an empty public SD image, creates/copies a file, unloads,
then verifies persistence on a fresh read-only boot. Public image tests need
no authorization marker or hardware tester. These probes are developer-only.
