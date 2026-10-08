# Writable redirector ABI references

The original [Ralf Brown Interrupt List, release 61](https://www.cs.cmu.edu/~ralf/files.html)
is the authority for the undocumented DOS interfaces used here (INTERRUP.K,
tables 02606, 01687, 01690, 01641/01642/01643). Do not substitute DOSBox's
built-in DOS behavior for actual kernel validation.

- DOS 3 locks pass position in CX:DX and length in SI plus a stack word.
  DOS 4–6 use BL to distinguish lock/unlock and DS:DX to an eight-byte
  position/length record; CX is one. Unlock must match the original range.
- Create uses stack attributes and a create-new flag. Extended open instead
  uses the SDA action, mode, and attributes; DOS 5/6 have documented stack
  attribute and returned-action bugs. Callback action results remain correct.
- Rename's second canonical pathname is 128 bytes after the first pathname
  buffer. These buffers have different sizes from this driver's path limit.
- DOS owns SFT reference counts on open; the redirector decrements them on
  close. Commit flushes without decrementing them.
- File time updates arrive through the SFT. File creation dates use the SDA
  date and time derives from the BIOS tick count without reentering DOS.
- Ordinary DOS UNLINK rejects wildcards before reaching the redirector.
  FCB deletion (INT 21h/AH=13h) and COMMAND.COM DEL pass under booted DOS 5
  and 6.22, including a directory grown across cluster boundaries. The optional
  `/SERVER` probe using canonicalized INT 21h/AX=5D00h still returns error 3
  without a new redirector error; that experiment is not a validated path.

SFT offsets used for DOS 3.1-6.x (byte offsets, little endian):

| Offset | Field | Ownership |
|---|---|---|
| 0 | reference count, WORD | DOS initializes; redirector decrements on close |
| 2 | open mode, WORD | redirector stores validated DOS mode |
| 4 | attributes, BYTE | refreshed from directory metadata |
| 5 | device/network flags, WORD | remote drive and inheritance flags |
| 7 | device/DPB or redirector pointer, DWORD | unused here; initialized to zero |
| 11 | starting cluster, WORD | unused for remote FAT32; full cluster lives in driver state |
| 13, 15 | FAT time/date, WORDs | preserve pending DOS handle-time updates |
| 17 | file size, DWORD | synchronize all open SFTs when size changes |
| 21 | file position, DWORD | individual SFT position; duplicates share it |
| 25-31 | cluster/position fields | initialized; traversal lives in driver state |
| 32-42 | short filename | eleven-byte padded alias |
| 43 onward | sharing/process linkage | preserve DOS-owned fields on open |

The writable build's private INT 2Fh/AX=D74Fh query is for the test program and
installer. Discovery without the control signature returns AX=4F54h,
BX=524Fh, CX=zero-based drive, DX=online, SI=open SFT slots, DI=ISA base port.
BP=3 identifies the enhanced build; BP=2 is the older read-only build.
Discovery checks media presence and can take the driver offline.

Controls require BX=4F54h and DX=524Fh. CF indicates failure with a DOS error
in AX; otherwise AX is zero except for selectors with explicit AX results:

| SI | Operation | Successful results |
|---|---|---|
| 1 | unmount after flushing | fails while any resident file slot is open |
| 2 | initialize and remount in installed mode | also requires zero file slots |
| 4 | copy transport diagnostics | ES:DI writable buffer, CX at least 40; CX=40 |
| 5 | installed mode | BX=write enabled, CX=3 total sector attempts, DX=online, DI=post-write readback enabled |
| 6 | last callback failure | AX=11xx function, BX=DOS error before kernel mapping |
| 7 | observed private stack use | AX=used, BX=untouched prefix, CX=2048 |

Selector 4 rejects a buffer crossing the 16-bit offset boundary. Its fixed
40-byte layout and stage/counter meanings are in RWSD.H. Unmount preserves
transport diagnostics; remount clears them even when its initialization fails.
The last callback failure is sticky, so it can describe an earlier operation.
Stack scanning measures observed use of the A5 pattern, including IRQs during
callbacks; it does not prove the maximum possible stack demand.

Process/FCB termination callbacks 111Dh and 1122h currently chain. RBIL describes
the sharing PSP at SDA 1Ah (DOS 3) or 1Ch (DOS 4-6), distinct from the current
PSP at 10h. Normal DOS process exit is tested with seventeen child runs leaving
six handle-based files and one region lock unclosed. DOS close callbacks release
all resident slots and locks. Abnormal abort and FCB record-I/O handle lifetime
remain unqualified; do not infer them from the normal-exit result.

See the specific [write callback](https://fd.lod.bz/rbil/interrup/network/2f1109.html),
[rename callback](https://fd.lod.bz/rbil/interrup/network/2f1111.html), and
[extended open callback](https://fd.lod.bz/rbil/interrup/network/2f112e.html).

## Consolidated identity query (action 8)

The private D74Fh/OT/RO multiplex control uses SI=8, CX >=32 and ES:DI pointing
to a 32-byte DriverInfo. Far offsets at FFE0h and above are rejected. CF clear returns
CX=32. Fields are last LBA (U32), CID (16 bytes), version (U16,000Bh), resident
bytes, SD ticks, filesystem ticks, flags and ABI (U16,1). Flags: bit0 cached
identity valid, bit1 installed writable mode, bit2 online, bit3 post-write readback disabled. CID is zero when
invalid; capacity is meaningful only with valid identity. This cached query
performs no SD I/O and does not freshly authenticate a removed card.
Mount tick fields are U16 BIOS low-word deltas for short operations; midnight
reset or unusually long mounts can distort them. The older 40-byte action4
diagnostic layout is unchanged.

The action4 `verified` counter retains its completed-sector-call ABI meaning.
With flag bit3 set it does not certify sector readback. /NOVERIFY is fixed at
installation and does not disable command/data CRC or recovery reads.

## DOS disk-space geometry

[INT 2F/110Ch](https://fd.lod.bz/rbil/interrup/network/2f110c.html) returns
AL sectors per allocation unit, AH media ID, BX total units, CX bytes per
sector and DX available units. Total/free counts are only 16 bits. Version
0.9 doubles the reported allocation unit and halves both counts until the
total fits, keeping synthesized units at most 32 KiB. Counts round down, so
the result loses less than one logical unit when the volume is representable.
The FAT32 BPB, physical cluster size and allocator do not change. A 500 MiB
volume with 4 KiB physical clusters is reported using 8 KiB logical units.
Read-only mode reports total capacity but zero writable free units. The
legacy interface still saturates above approximately 2 GiB at that unit-size
ceiling; this is not an extended FAT32 disk-space API. Pre-existing 64 KiB
physical clusters retain their previous unit size rather than wrapping AL.

### Unload ABI (OTTERSD 0.10)

Private INT 2F AX=D74Fh, BX=4F54h, DX=524Fh, SI=9 returns CF clear,
AX=resident PSP, BX:CX=own vector offset:segment, DX:DI=previous vector
offset:segment, SI=000Ah. This query does not flush or mutate the drive.
SI=10 prepares detachment: verify the topmost INT 2F vector, reject open files
or a poisoned/lost dirty session, flush writable online media, take it offline, restore
all 51h (DOS 3) or 58h (DOS 4+) saved CDS bytes. CF/AX reports failure; commit
failure leaves the CDS and hook installed. The transient caller must verify
the current drive and DOS MCB ownership before SI=10, then restore the saved
vector and free the PSP allocation with INT 21/AH=49 only after returning.
Never call DOS or free the allocation on the resident interrupt stack. No
third-party hook may be bypassed. These operations are version-matched and
intended for the shipped /UNLOAD command, not a generic TSR chain editor.

### Fast-mount policy in 0.11

DriverInfo ABI 1 remains 32 bytes. Flags bit 4 (0010h) records the installed
/SKIPFATCHECK policy; other flag meanings are unchanged. Private unload query
SI=9 returns version SI=000Bh for this release. /SKIPFATCHECK skips only the
full mount scan. FAT sector zero is compared at mount and before clean/dirty
flag publication, modified FAT sectors remain compared, and rw_flush still
compares all mirrors for a dirty session. No policy control changes an already
resident instance. Read-only mounting does not perform the full scan.


### Dual-format status flags (OTTERSD 0.13)

DriverInfo ABI 1 remains 32 bytes. Flags 0020h identify a mounted FAT16 volume;
with mounted flag 0004h set and 0020h clear, the volume is FAT32. Offline volumes
have no reported type. Flags 0040h and 0080h record `/FAT16` and `/FAT32`
restrictions respectively; both clear means automatic detection. Restrictions
persist across unmounts, removals, and explicit remounts. No on-disk format
conversion occurs. The internal ROOT16 sentinel is FFFFFFFFh and never a data
cluster. FAT16 reserved/EOF entries normalize into the existing internal FAT32
marker range; writes serialize only the original two-byte FAT16 entries.
