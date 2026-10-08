"""Exercise the production FAT32 reader through a read-only host transport."""
import ctypes as C
import pathlib
import random
import struct
import subprocess
import tempfile
import unittest
from support import library
from fixture import create, TEXT, BIG, RESERVED, FATSZ

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FileCursor(C.Structure):
    _fields_ = [("first", C.c_uint32), ("cluster", C.c_uint32), ("index", C.c_uint32)]


class DirCursor(C.Structure):
    _fields_ = [("cluster", C.c_uint32), ("slot", C.c_uint16), ("hops", C.c_uint16)]


class FilesystemTests(unittest.TestCase):
    def test_selective_store_invalidation_preserves_unrelated_cache(self):
        self.lib.fs_fat_entry.argtypes = [C.c_uint32]
        self.lib.fs_fat_entry.restype = C.c_uint32
        self.lib.fs_invalidate_sector.argtypes = [C.c_uint32]
        reads = C.c_uint.in_dll(self.lib, 'reads')
        fat_lba = self.layout['start'] + RESERVED
        data_lba = self.layout['data'] + 2

        def read_data():
            self.assertEqual(self.read(FileCursor(4, 4, 0), 0, len(TEXT)), TEXT)

        def read_fat():
            self.assertEqual(self.lib.fs_fat_entry(4), 0x0fffffff)

        read_data()
        read_fat()
        before = reads.value
        self.lib.fs_invalidate_sector(data_lba + 100)
        read_data()
        read_fat()
        self.assertEqual(reads.value, before)
        self.lib.fs_invalidate_sector(data_lba)
        read_fat()
        self.assertEqual(reads.value, before)
        read_data()
        self.assertEqual(reads.value, before + 1)
        self.lib.fs_invalidate_sector(fat_lba)
        read_data()
        self.assertEqual(reads.value, before + 1)
        read_fat()
        self.assertEqual(reads.value, before + 2)

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="otterfs-tests-")
        cls.work = pathlib.Path(cls.tmp.name)
        so = library(cls.work, "fat32", ["FAT32.C", "tests/HOSTSD.C"])
        cls.lib = C.CDLL(str(so))
        cls.lib.test_open.argtypes = [C.c_char_p]
        cls.lib.fs_lookup.argtypes = [C.c_char_p, C.c_void_p]
        cls.lib.fs_next.argtypes = [C.POINTER(DirCursor), C.c_void_p]
        cls.lib.fs_read.argtypes = [C.POINTER(FileCursor), C.c_uint32, C.c_void_p,
                                   C.c_uint16, C.POINTER(C.c_uint16)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.image = self.work / "card.img"
        self.layout = create(self.image)
        self.mount()

    def mount(self):
        self.assertEqual(self.lib.test_open(str(self.image).encode()), 0)
        self.assertEqual(self.lib.fs_mount(), 0)

    def lookup(self, path):
        e = C.create_string_buffer(32)
        self.assertEqual(self.lib.fs_lookup(path.encode(), e), 0, path)
        return e.raw

    def read(self, cursor, offset, count):
        buf = C.create_string_buffer(count)
        done = C.c_uint16()
        result = self.lib.fs_read(C.byref(cursor), offset, buf, count, C.byref(done))
        self.assertEqual(result, 0)
        self.assertEqual(done.value, count)
        return buf.raw

    def patch(self, offset, content):
        with self.image.open("r+b") as f:
            f.seek(offset)
            f.write(content)
        self.lib.fs_invalidate()

    def test_paths_and_high_clusters(self):
        self.assertEqual(self.lookup("S:\\SUBDIR\\INNER.TXT")[28:32], struct.pack("<I", len(TEXT)))
        self.assertEqual(self.lookup("S:\\SUBDIR\\..\\README.TXT")[:11], b"README  TXT")
        self.lookup("S:\\")
        self.lookup("S:\\SUBDIR\\")
        self.assertEqual(self.read(FileCursor(66000, 0, 0), 0, 5), b"HIGH\n")

    def test_fragmentation_seek_and_large_reads(self):
        cursor = FileCursor(100, 0, 0)
        self.assertEqual(self.read(cursor, 0, 65535), BIG[:65535])
        self.assertEqual(self.read(cursor, 65535, 4465), BIG[65535:])
        self.assertEqual(self.read(cursor, 511, 1600), BIG[511:2111])
        self.assertEqual(self.read(FileCursor(5, 0, 0), 0, 1000), bytes(i % 251 for i in range(1000)))

    def test_directory_chain_and_independent_searches(self):
        a, b = DirCursor(2, 0, 0), DirCursor(3, 0, 0)
        e = C.create_string_buffer(32)
        names = []
        while self.lib.fs_next(C.byref(a), e) == 0:
            names.append(e.raw[:11])
            self.lib.fs_next(C.byref(b), e)
        self.assertIn(b"HELLO   COM", names)
        self.assertEqual(len(names), 9)

    def test_superfloppy_active_fat_and_multi_sector_clusters(self):
        for partitioned, active, spc in [(False, False, 1), (True, True, 1), (True, False, 8)]:
            create(self.image, partitioned, active, spc)
            self.mount()
            self.lookup("S:\\HELLO.COM")
            self.assertEqual(self.read(FileCursor(100, 0, 0), 4000, 12000), BIG[4000:16000])

    def test_io_error_does_not_return_stale_cache(self):
        self.lookup("S:\\README.TXT")
        C.c_uint32.in_dll(self.lib, "fault_lba").value = self.layout["data"] + 2
        cursor, done, buf = FileCursor(4, 0, 0), C.c_uint16(), C.create_string_buffer(40)
        self.assertEqual(self.lib.fs_read(C.byref(cursor), 0, buf, 10, C.byref(done)), -1)
        self.assertEqual(done.value, 0)
        self.assertEqual(C.c_uint16.in_dll(self.lib, "fs_error").value, 30)

    def test_bad_chain_and_partial_read(self):
        self.patch((self.layout["start"] + RESERVED) * 512 + 100 * 4, struct.pack("<I", 0x0FFFFFF7))
        cursor, done, buf = FileCursor(100, 0, 0), C.c_uint16(), C.create_string_buffer(1024)
        self.assertEqual(self.lib.fs_read(C.byref(cursor), 0, buf, 1024, C.byref(done)), -1)
        self.assertEqual(done.value, 512)
        self.assertEqual(C.c_uint16.in_dll(self.lib, "fs_error").value, 13)
        self.assertEqual(self.lib.fs_read(C.byref(cursor), 512, buf, 512, C.byref(done)), -1)
        self.assertEqual(done.value, 0, "retry must not treat a failed chain hop as completed")

    def test_bad_boot_sectors(self):
        for offset, value in [(11, b"\0\0"), (13, b"\x03"), (16, b"\0"),
                              (36, struct.pack("<I", 1)), (44, struct.pack("<I", 1)),
                              (510, b"\0\0")]:
            create(self.image)
            self.lib.test_open(str(self.image).encode())
            self.patch(self.layout["start"] * 512 + offset, value)
            self.assertEqual(self.lib.fs_mount(), -1, offset)

    def test_deterministic_random_reads_with_interleaved_cache_use(self):
        rng = random.Random(0x5150)
        for spc in (1, 2, 8, 128):
            create(self.image, spc=spc)
            self.mount()
            a, b = FileCursor(100, 0, 0), FileCursor(4, 0, 0)
            for _ in range(80):
                offset = rng.randrange(len(BIG))
                count = rng.randrange(1, min(len(BIG) - offset, 4096) + 1)
                self.assertEqual(self.read(a, offset, count), BIG[offset:offset + count])
                self.lookup("S:\\HIGH.TXT")  # displace data cache between reads
                self.assertEqual(self.read(b, 0, len(TEXT)), TEXT)

    def test_fat_fault_retry_and_positive_dos_error_propagation(self):
        cursor, done, buf = FileCursor(100, 100, 0), C.c_uint16(), C.create_string_buffer(512)
        fat_lba = self.layout["start"] + RESERVED
        C.c_uint32.in_dll(self.lib, "fault_lba").value = fat_lba
        C.c_int.in_dll(self.lib, "fault_code").value = 21
        self.assertEqual(self.lib.fs_read(C.byref(cursor), 512, buf, 512, C.byref(done)), -1)
        self.assertEqual((done.value, cursor.index, cursor.cluster), (0, 0, 100))
        self.assertEqual(C.c_uint16.in_dll(self.lib, "fs_error").value, 21)
        C.c_uint32.in_dll(self.lib, "fault_lba").value = 0xffffffff
        self.assertEqual(self.read(cursor, 512, 512), BIG[512:1024])
        self.lib.fs_invalidate()
        C.c_uint32.in_dll(self.lib, "fault_lba").value = self.layout["data"] + 98
        C.c_int.in_dll(self.lib, "fault_code").value = 30
        self.assertEqual(self.lib.fs_read(C.byref(cursor), 0, buf, 512, C.byref(done)), -1)
        self.assertEqual(done.value, 0)
        C.c_uint32.in_dll(self.lib, "fault_lba").value = 0xffffffff
        self.assertEqual(self.read(cursor, 0, 512), BIG[:512])

    def test_invalid_and_premature_chain_end_never_advance_file_cursor(self):
        for value in (0, 1, 70002, 0x0ffffff7, 0x0fffffff):
            create(self.image); self.mount()
            self.patch((self.layout["start"] + RESERVED) * 512 + 100 * 4,
                       struct.pack("<I", value))
            cursor, done, buf = FileCursor(100, 100, 0), C.c_uint16(), C.create_string_buffer(1)
            for _ in range(2):
                self.assertEqual(self.lib.fs_read(C.byref(cursor), 512, buf, 1, C.byref(done)), -1)
                self.assertEqual((done.value, cursor.cluster, cursor.index), (0, 100, 0))
        for first, position in ((0, 0), (1, 0), (70002, 0), (100, 70000 * 512)):
            done, buf = C.c_uint16(), C.create_string_buffer(1)
            cursor = FileCursor(first, first, 0)
            self.assertEqual(self.lib.fs_read(C.byref(cursor), position, buf, 1, C.byref(done)), -1)
            self.assertEqual(done.value, 0)

    def test_directory_end_invalid_cluster_and_cycle_bound(self):
        e = C.create_string_buffer(32)
        self.assertEqual(self.lib.fs_next(C.byref(DirCursor(0, 0, 0)), e), 1)
        self.assertEqual(self.lib.fs_next(C.byref(DirCursor(1, 0, 0)), e), -1)
        self.assertEqual(self.lib.fs_next(C.byref(DirCursor(2, 16, 65535)), e), -1)
        # Loop root's FAT chain, with only deleted entries: scanning must terminate.
        self.patch((self.layout["start"] + RESERVED) * 512 + 2 * 4, struct.pack("<I", 2))
        self.patch(self.layout["data"] * 512, (b"\xe5" + bytes(31)) * 16)
        cursor = DirCursor(2, 0, 0)
        self.assertEqual(self.lib.fs_next(C.byref(cursor), e), -1)
        self.assertEqual(C.c_uint16.in_dll(self.lib, "fs_error").value, 13)
        self.assertEqual(cursor.hops, 65535)

    def test_mount_geometry_and_partition_rejections(self):
        cases = [(14, b"\0\0"), (16, b"\0"), (13, b"\0"), (13, b"\x81"),
                 (17, b"\x01\0"), (22, b"\x01\0"), (42, b"\x01\0"),
                 (40, b"\x82\0"), (32, struct.pack("<I", 0)),
                 (32, struct.pack("<I", 1000)), (32, struct.pack("<I", 0xffffffff)),
                 (36, struct.pack("<I", 0xffffffff)), (44, struct.pack("<I", 70002))]
        for offset, value in cases:
            create(self.image); self.lib.test_open(str(self.image).encode())
            self.patch(self.layout["start"] * 512 + offset, value)
            self.assertEqual(self.lib.fs_mount(), -1, (offset, value))
            self.assertEqual(C.c_uint16.in_dll(self.lib, "fs_error").value, 13)
        for offset, value in [(510, b"\0\0"), (450, b"\x07"),
                              (454, bytes(4)), (458, bytes(4)),
                              (454, struct.pack("<I", 0xfffffff0))]:
            create(self.image); self.lib.test_open(str(self.image).encode())
            self.patch(offset, value)
            self.assertEqual(self.lib.fs_mount(), -1, offset)

    def test_invalidation_forces_fresh_data_and_fat(self):
        self.assertEqual(self.read(FileCursor(4, 4, 0), 0, 1), b"H")
        self.patch((self.layout["data"] + 2) * 512, b"Z")
        self.assertEqual(self.read(FileCursor(4, 4, 0), 0, 1), b"Z")
        self.assertEqual(self.read(FileCursor(100, 100, 0), 0, 1024), BIG[:1024])
        self.patch((self.layout["start"] + RESERVED) * 512 + 100 * 4, bytes(4))
        cursor, done, buf = FileCursor(100, 100, 0), C.c_uint16(), C.create_string_buffer(1)
        self.assertEqual(self.lib.fs_read(C.byref(cursor), 512, buf, 1, C.byref(done)), -1)
        self.assertEqual(done.value, 0)

    def test_lookup_output_can_alias_fully_consumed_path(self):
        for name in ("S:\\README.TXT", "S:\\SUBDIR\\INNER.TXT", "S:\\", "S:\\.",
                     "S:\\SUBDIR\\..", "S:\\SUBDIR\\..\\HIGH.TXT"):
            expected = self.lookup(name)
            buffer = C.create_string_buffer(name.encode(), 80)
            self.assertEqual(self.lib.fs_lookup(buffer, buffer), 0, name)
            self.assertEqual(buffer.raw[:32], expected)

    def test_names_and_wildcards(self):
        pattern = C.create_string_buffer(11)
        for name, expected in [(b"*.*", b"???????????"), (b"*.TXT", b"????????TXT"),
                               (b"readme.txt", b"README  TXT")]:
            self.assertEqual(self.lib.fs_pattern(name, pattern, 1), 0)
            self.assertEqual(pattern.raw, expected)
        for name in [b"TOOLONGXX.TXT", b"FILE.EXTX", b"A:B", b"", b"*.TXT"]:
            self.assertEqual(self.lib.fs_pattern(name, pattern, 0), -1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
