# Resident source conventions

The DOS sources target Turbo C 2.0's C89 subset and TASM's `.8086` instruction
set. Keep declarations at block starts, use `/* ... */` comments in C and `;`
comments in assembly, and retain explicit `far` pointers at DOS memory and
transfer boundaries. Modern Python and the host card model are test tools;
they need not imitate a 1980s compiler.

Use the existing U8/U16/U32 types when width is part of a disk format or DOS
ABI. DOS `int` is 16 bits. A far pointer's offset is also 16 bits; ordinary
pointer addition is insufficient for a transfer crossing offset FFFFh.
Keep unsigned arithmetic explicit where overflow, sector bounds or time
counter wrap is intentional.

Comments should explain contracts, ownership, ordering and unusual constraints.
Document which error survives a failure and which state is invalidated. Avoid
restating obvious assignments or turning measured evidence into a guarantee.
DOSREF.md records DOS structure offsets and the private diagnostic interface;
RWSD.H and RWFS.H describe the transport and filesystem contracts.

Resident callbacks must not call DOS, allocate memory, or print diagnostics.
The interrupt bridge provides a static stack and prevents nested use of shared
scratch. Installation code may use DOS before becoming resident. The linker
boundary includes all resident code/data and the private stack, and releases
the startup stack/heap after installation.

Verified sector writes do not make FAT operations atomic. Mount preflight is
not a complete consistency scan. Any claim about recovery, memory use, or a
DOS API must distinguish host tests, actual booted DOS and physical hardware.

For a comments-only pass, retain a pre-edit build and compare rebuilt EXE files
byte for byte. Run the regression suite as well. Formatting changes are kept
small so an invariant explanation remains easy to review separately from a
behavior change.
