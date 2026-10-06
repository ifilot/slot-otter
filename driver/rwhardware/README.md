# Writable resident hardware kit

HWRT.C exercises the resident driver through DOS APIs. RWCHILD.C tests DOS
termination with deliberately unclosed handle-based files/locks. Sources are
standalone under `driver`; nothing is imported from `src`.

Build the tester privately:

```
python3 driver/rwhardware/build.py --output /tmp/otter-hwrt
bash driver/build-rw.sh /tmp/otter-rw
```

Validate on a private copy of a user-supplied genuine DOS boot floppy:

```
python3 driver/rwhardware/validate.py --boot-image /path/to/dos.img \
  --dosbox /path/to/dosbox-with-isa-model \
  --driver /tmp/otter-rw/OTTERWR.EXE --tester /tmp/otter-hwrt/HWRT.EXE
```

The harness runs the hardware program, stress/memory modes, boots fresh DOS
again to verify persistence, checks no writes during reboot verification,
and compares file bytes with independent mtools and `fsck.fat -n`. Guard/fault
modes are `readonly`, `unmarked`, `no-erase` and `drop`. `swap` builds a private
input wrapper to exercise the real program's empty-slot/reinsertion branches;
its emulator port is absent from the physical executable. A simulated drop may
occur after programming the first target sector; further writes must stop.
Artifacts and full logs stay in a printed temporary directory.

The hardware [manual](MANUAL.md) describes Navigator copying, local setup,
commands, expected warnings/errors, logs and safe card removal. Package
publication is a separate step after current-source validation.

The tester embeds an identifier generated from its DOS sources. Comment edits
can change that identifier even when executable instructions are identical.
The resident comment reviews were validated by full EXE equality. Final tester
regression and fresh package build equality include its generated identifier.
