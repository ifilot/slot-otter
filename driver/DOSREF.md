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
| 5 | installed mode | BX=write enabled, CX=3 total sector attempts, DX=online |
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
to a 32-byte DriverInfo. Far offsets beyond FFE0h are rejected. CF clear returns
CX=32. Fields are last LBA (U32), CID (16 bytes), version (U16,0004h), resident
bytes, SD ticks, filesystem ticks, flags and ABI (U16,1). Flags: bit0 cached
identity valid, bit1 installed writable mode, bit2 online. CID is zero when
invalid; capacity is meaningful only with valid identity. This cached query
performs no SD I/O and does not freshly authenticate a removed card.
Mount tick fields are U16 BIOS low-word deltas for short operations; midnight
reset or unusually long mounts can distort them. The older 40-byte action4
diagnostic layout is unchanged.
