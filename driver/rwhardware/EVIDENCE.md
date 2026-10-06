# Consolidated qualification evidence

The current release is driver/dist, separate from the preserved earlier kit.
EVIDENCE/QUALIFICATION.JSON records actual gate outcomes and log hashes; its
full field must be true for actual-kernel/final-image qualification. Gate logs
and coverage counters accompany the release. Build equality proves the packaged
executables match those tested; final-image checks also compare KIT binaries.

The baseline physical SanDisk run passed INFO 43, TEST 278 and VERIFY 62,
with 1,777 verified sectors/transmissions and no retries. That evidence applies
to the earlier 39,888-byte binary, not this consolidation. Original hardware
logs/releases remain unchanged. No new physical card or 8088 is yet qualified.

Required current gates include host regression/coverage/behavioral mutations;
DOS 5 and 6.22 read-only CLI/EXEC/copy/empty-slot/swap; strict CRC, slow busy,
recoverable corruption/rejection/status, removal and pre-write CRC faults;
tester /RO and default-RO/marker/ERASE guards; seventeen self-exec children;
all-free-memory overwrite; fresh-boot exact verification without image writes;
and independent mtools file comparison/fsck.fat -n on the distributed image.

The single-FAT shortcut and deferred-close behavior have explicit I/O-count and
failure tests. Full commit/unmount must still detect corruption of an untouched
mirror sector; abrupt dirty remount must refuse further writes. Shared scratch
has a recovery-mutation test proving frozen expected payload survives.

Qualification does not cover physical electrical behavior, power-loss atomicity,
FCB record I/O/abnormal abort, DOS 3/4 kernels or a physical 5150. The next card
run follows MANUAL.md and must save brand/model/CID and separate logs.
