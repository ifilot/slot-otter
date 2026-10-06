# Unified hardware tester

The public test program is HWRT.EXE 0.2. It exercises OTTERWR 0.4 through DOS
APIs. RWCHILD.C is included into HWRT; seventeen private self-exec children
leave raw DOS handles/locks unclosed to test normal process termination.
No RWCHILD.EXE is distributed. All source is standalone under driver.

Use [driver/validate.py](../validate.py) as the qualification entry point and
[the hardware manual](MANUAL.md) for a per-card run. Default validation runs
host coverage/mutations, canonical builds and image/ZIP equality/fsck checks.
Full validation also boots DOS 5/6.22, exercises bounded fault recovery and
read-only/marker/authorization guards, and tests the exact released image.

The lower-level harness accepts normal, swap, drop, readonly, default-ro,
unmarked and no-erase modes. It modifies private copies only. Swap uses a
private emulator input wrapper; that control port is absent from HWRT.EXE.
Native verification compares independent file bytes and invokes fsck.fat -n.

Each log contains versions, cached card CID, capacity, source identifier,
phase/byte/cycle progress, BIOS timings, direct DOS errors and SD diagnostics.
Comment changes to tester sources can change its embedded source identifier;
release packaging must rebuild identically to the qualified executables.
Older dist/ and logs/ here preserve the earlier physical SanDisk baseline.
The current consolidated release is ../dist/.
