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
the startup stack/heap and explicit far installer tail after installation.
BOOT gates are the only external far targets permitted in installer assembly;
local far frames must also be verified before linking. PORTBODY.H shares the
parser implementation between retained test utilities and the far installer.

Verified sector writes do not make FAT operations atomic. Mount preflight is
not a complete consistency scan. Any claim about recovery, memory use, or a
DOS API must distinguish host tests, actual booted DOS and physical hardware.

For a comments-only pass, retain a pre-edit build and compare rebuilt EXE files
byte for byte. Run the regression suite as well. Formatting changes are kept
small so an invariant explanation remains easy to review separately from a
behavior change.


FASTIO.ASM uses a near small-model C call for normalized far memory copying.
Its source and destination must be normalized before each <=512-byte chunk;
neither offset may wrap. The helper preserves BX/SI/DI/BP/DS/ES, clears DF and
leaves interrupts enabled. Native tests check odd tails, source preservation,
segments and register contracts with deliberately broken assembly variants.

The SD transport in SDRW.C is the complete 0.6 C implementation restored after
a physical regression in 0.7. Its OUT plus settling/sample reads must not be
compressed into assembly without an elapsed-time contract and physical proof.
An emulator that counts accesses cannot establish electrical settling time.
The C CRC is tested against independent host and native bitwise oracles.
