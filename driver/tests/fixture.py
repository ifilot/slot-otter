"""Generate a sparse, valid FAT32 SD image without third-party libraries."""
import pathlib
import struct

CLUSTERS = 70000
RESERVED = 32
FATSZ = (CLUSTERS + 2 + 127) // 128
TOTAL = RESERVED + 2 * FATSZ + CLUSTERS
BIG = bytes((i * 7 + 3) % 256 for i in range(70000))
TEXT = b"Hello from Slot-otter!\r\n"


def entry(name, attr, cluster=0, size=0):
    e = bytearray(32)
    if attr == 8:
        e[:11] = name.encode().ljust(11)
    elif name in (".", ".."):
        e[:11] = name.encode().ljust(11)
    else:
        base, _, ext = name.partition(".")
        e[:11] = base.encode().ljust(8) + ext.encode().ljust(3)
    e[11] = attr
    struct.pack_into("<H", e, 20, cluster >> 16)
    struct.pack_into("<HHH", e, 22, 0x6000, 0x5821, cluster & 65535)
    struct.pack_into("<I", e, 28, size)
    return e


def create(path, partitioned=True, active_fat=False, spc=1):
    start = 2048 if partitioned else 0
    total = RESERVED + 2 * FATSZ + CLUSTERS * spc
    data = start + RESERVED + 2 * FATSZ
    with open(path, "wb") as f:
        f.truncate((start + total) * 512)

        def sector(lba, content):
            f.seek(lba * 512)
            f.write(content.ljust(512, b"\0"))

        if start:
            mbr = bytearray(512)
            mbr[450] = 0x0C
            struct.pack_into("<II", mbr, 454, start, total)
            mbr[510:] = b"\x55\xaa"
            sector(0, mbr)
        boot = bytearray(512)
        boot[:3] = b"\xeb\x58\x90"
        boot[3:11] = b"OTTERFS "
        struct.pack_into("<H", boot, 11, 512)
        boot[13] = spc
        struct.pack_into("<H", boot, 14, RESERVED)
        boot[16] = 2
        boot[21] = 0xF8
        struct.pack_into("<II", boot, 28, start, total)
        struct.pack_into("<IHHIHH", boot, 36, FATSZ, 0x81 if active_fat else 0,
                         0, 2, 1, 6)
        boot[66] = 0x29
        boot[71:82] = b"OTTER TEST "
        boot[82:90] = b"FAT32   "
        boot[510:] = b"\x55\xaa"
        sector(start, boot)
        fat = bytearray(FATSZ * 512)

        def link(cluster, next_cluster=0x0FFFFFFF):
            struct.pack_into("<I", fat, cluster * 4, next_cluster)

        link(0, 0x0FFFFFF8)
        link(1)
        link(2, 10)
        for c in (3, 4, 5, 8, 9, 10, 66000):
            link(c)
        link(5, 8)
        big_count = (len(BIG) + 512 * spc - 1) // (512 * spc)
        for i in range(big_count):
            c = 100 + i * 2  # deliberately fragmented
            link(c, c + 2 if i + 1 < big_count else 0x0FFFFFFF)
            content = BIG[i * 512 * spc:(i + 1) * 512 * spc]
            f.seek((data + (c - 2) * spc) * 512)
            f.write(content.ljust(spc * 512, b"\0"))
        f.seek((start + RESERVED) * 512)
        f.write(bytes(len(fat)) if active_fat else fat)
        f.seek((start + RESERVED + FATSZ) * 512)
        f.write(fat)
        root = [entry("OTTER TEST", 8), entry("README.TXT", 0x20, 4, len(TEXT)),
                entry("SUBDIR", 16, 3), entry("FRAG.BIN", 0x20, 5, 1000),
                entry("EMPTY.TXT", 0x20), entry("BIG.BIN", 0x20, 100, len(BIG)),
                entry("HIGH.TXT", 0x20, 66000, 5), entry("HIDDEN.TXT", 2, 4, len(TEXT))]
        # Force the directory iterator to follow a FAT chain, ignoring LFN/deleted entries.
        while len(root) < 16 * spc:
            deleted = bytearray(32)
            deleted[0] = 0xE5
            root.append(deleted)
        root[8][0] = ord('L')
        root[8][11] = 0x0F
        f.seek(data * 512)
        f.write(b"".join(root))
        # Tiny 8086 COM executable: prints a marker then terminates.
        com = b"\xba\x0c\x01\xb4\x09\xcd\x21\xb8\x00\x4c\xcd\x21EXEC OK\r\n$"
        sector(data + 8 * spc, entry("HELLO.COM", 0x20, 9, len(com)))
        sector(data + 7 * spc, com)
        sector(data + 2 * spc, TEXT)
        sub = entry(".", 16, 3) + entry("..", 16) + entry("INNER.TXT", 0x20, 4, len(TEXT))
        sector(data + spc, sub)
        sector(data + 65998 * spc, b"HIGH\n")
        fragment = bytes(i % 251 for i in range(1000))
        for i, c in enumerate((5, 8)):
            sector(data + (c - 2) * spc, fragment[i * 512:(i + 1) * 512])
    return {"start": start, "data": data, "total": total, "spc": spc}


if __name__ == "__main__":
    import sys
    create(pathlib.Path(sys.argv[1]))
