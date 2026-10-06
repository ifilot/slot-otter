# Software qualification, 2026-10-06

These results qualify the software package for the next physical test. They do
not qualify the ISA electrical interface, either physical card with the resident
writer, or an 8088/5150. The physical read-only/standalone-writer logs are kept
unchanged in their existing directories.

| Gate | Result |
|---|---|
| Combined host regression | 223 tests pass |
| Mutation sensitivity | 95 behavioral mutations detected after successful compilation |
| Coverage | all old and resident-writer floors pass |
| Original read-only executable | rebuilt bytes identical; resident 17,632 bytes |
| Writable memory | 39,888 bytes incl PSP; linker allocation matches DOS MCB |
| Private callback stack | highest observed use 524/2,048 bytes |
| Three read-only comment reviewers | feedback applied by root; comment-only resident builds identical |
| DOS 5 and 6.22 HWRT /TEST | 278 checks pass per run |
| HWRT /STRESS | 221 checks pass; twenty allocation/write/verify/delete cycles |
| HWRT /MEMORY | 48 checks pass, including all-free-DOS-memory overwrite |
| Fresh-boot HWRT /VERIFY | 62 checks pass; entire card image unchanged |
| HWRT /SWAP under DOS 5 | 67 checks pass through private input wrapper |
| Actual candidate SD image | full program/stress/memory/reboot suite passes |
| Independent tools | exact file bytes via mtools; fsck.fat -n succeeds |

Native transport profiles pass for strict CRC/cold startup, slow busy completion,
one rejected CRC, one corrupted readback and one status error. Recovery statistics
show exactly one extra transmission/retry for each single recoverable write
fault. Some profile runs predate the 192-byte handle union; transport source is
unchanged, and the final layout is covered by the full native hardware suite.

Removal after programming reports poison and stops subsequent mutations; the
first target sector can change. A pre-write read-CRC fault produces zero payload
transmissions and no image changes. Hardware tester guards stop without card
mutations for a read-only installation, missing image marker and missing /ERASE.

Native rejection checks confirm the callback's reason and online state. On these
DOS kernels, the application often sees error 5 while the redirector correctly
reports lock reason 33 or sharing reason 32. A failed operation alone is not
treated as a successful lock/sharing test.

Normal process termination is tested with seventeen children, each leaving six
direct-DOS handles and one lock unclosed. Abnormal abort and FCB record-I/O are
not qualified. Standard FCB wildcard deletion and COMMAND.COM DEL pass across
grown directories. The optional server-interface experiment remains unqualified.

The original thirteen log hashes and original OTTERFS.EXE remain unchanged.
Resident comment changes were checked through full EXE equality before and after
both passes; separate behavior and memory changes have their own tests. The
tester embeds a generated source identifier, so its comment edits can intentionally
change that string; final package rebuilds must equal the validated executables.

`dist/EVIDENCE` contains retained native logs, coverage and host-gate output. Host
output includes intentionally failing card/test cases whose assertions pass;
the unittest result and mutation totals are the gate results. No bootable DOS
image, emulator binary or licensed compiler is redistributed.
