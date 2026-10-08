"""Production DOS dispatch + production FAT32, with simulated DOS memory only.

No reimplementation of the redirector: callbacks use the real dispatch(), real
filesystem and read-only images. The test adapter substitutes segmented pointers
and card presence, which require actual DOS/ISA integration in the other suite.
"""
import ctypes as C
import hashlib
import pathlib
import struct
import tempfile
import unittest
from fixture import create, TEXT, BIG
from support import library


class Registers(C.Structure):
    _fields_ = [(name, C.c_uint16) for name in
                "ax bx cx dx si di es ds bp ip cs flags param".split()]


class RedirectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="otter-redirector-tests-")
        cls.work = pathlib.Path(cls.tmp.name)
        cls.lib = C.CDLL(str(library(cls.work, "redirector",
                       ["FAT32.C", "tests/HOSTSD.C", "tests/HOSTRD.C"])))
        cls.lib.test_open.argtypes = [C.c_char_p]
        cls.lib.test_far_at.argtypes = [C.c_uint16, C.c_uint16]
        cls.lib.test_far_at.restype = C.POINTER(C.c_ubyte)
        cls.regs = Registers.in_dll(cls.lib, "regs")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.image = self.work / "card.img"
        self.layout = create(self.image)
        self.hash = hashlib.sha256(self.image.read_bytes()).digest()
        self.lib.test_reset()
        self.assertEqual(self.lib.test_open(str(self.image).encode()), 0)
        self.sda, self.cds, self.sfts, self.data = [self.memory(n) for n in range(1, 5)]
        self.assertEqual(self.lib.media_mount(), 0)

    def tearDown(self):
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).digest(), self.hash,
                         "resident callback wrote to the card")

    def memory(self, segment):
        return (C.c_ubyte * 65536).from_address(C.addressof(self.lib.test_far_at(segment, 0).contents))

    def put(self, memory, offset, value, size=2):
        memory[offset:offset + size] = value.to_bytes(size, "little")

    def get(self, memory, offset, size=2):
        return int.from_bytes(bytes(memory[offset:offset + size]), "little")

    def pointer(self, offset=0):
        self.put(self.sda, 12, offset); self.put(self.sda, 14, 4)

    def path(self, name):
        raw = name.encode() + b"\0"
        self.sda[0x9e:0x9e + len(raw)] = raw

    def call(self, fn, error=None, handled=True, **values):
        C.memset(C.addressof(self.regs), 0, C.sizeof(self.regs))
        self.regs.ax = 0x1100 | fn
        self.regs.es = 3
        self.regs.flags = 0x202  # retain unrelated interrupt flag
        for key, value in values.items():
            setattr(self.regs, key, value)
        before = bytes(self.regs)
        self.assertEqual(self.lib.dispatch(), int(handled))
        r = Registers.from_buffer_copy(bytes(self.regs))
        if handled:
            self.assertEqual(bool(r.flags & 1), error is not None)
            self.assertTrue(r.flags & 0x200)
            if error is not None:
                self.assertEqual(r.ax, error)
        else:
            self.assertEqual(bytes(r), before, "chained requests must retain registers")
        return r

    def opened(self, slot=0, name="S:\\README.TXT", mode=0, extended=False, action=1):
        off = slot * 64
        self.put(self.sfts, off, 1)
        self.sfts[off + 43:off + 64] = b"\xa5" * 21
        self.path(name)
        self.put(self.sda, 0x2e1, mode)
        self.sda[0x2dd] = action
        self.call(0x2e if extended else 0x16, di=off, param=mode)
        return off

    def test_open_sft_metadata_and_dos_owned_fields(self):
        off = self.opened(mode=0x80)
        self.assertEqual(self.get(self.sfts, 0), 1)
        self.assertEqual(self.get(self.sfts, 2), 0x80)
        self.assertEqual(self.sfts[4], 0x21)
        self.assertEqual(self.get(self.sfts, 5), 0xd012)
        self.assertEqual(self.get(self.sfts, 13), 0x6000)
        self.assertEqual(self.get(self.sfts, 15), 0x5821)
        self.assertEqual(self.get(self.sfts, 17, 4), len(TEXT))
        self.assertEqual(bytes(self.sfts[32:43]), b"README  TXT")
        self.assertEqual(bytes(self.sfts[43:64]), b"\xa5" * 21)
        self.call(6, di=off)

    def test_reads_eof_zero_count_and_independent_positions(self):
        a, b = self.opened(), self.opened(1)
        self.data[:40] = b"\xa5" * 40
        self.assertEqual(self.call(8, di=a, cx=100).cx, len(TEXT))
        self.assertEqual(bytes(self.data[:len(TEXT)]), TEXT)
        self.assertEqual(self.data[len(TEXT)], 0xa5)
        self.assertEqual(self.call(8, di=a, cx=10).cx, 0)
        self.assertEqual(self.call(8, di=b, cx=0).cx, 0)
        self.assertEqual(self.get(self.sfts, b + 21, 4), 0)
        self.assertEqual(self.call(8, di=b, cx=5).cx, 5)
        self.assertEqual(bytes(self.data[:5]), TEXT[:5])

    def test_large_fragmented_reads_and_backward_seek(self):
        off = self.opened(name="S:\\BIG.BIN")
        self.assertEqual(self.call(8, di=off, cx=65535).cx, 65535)
        self.assertEqual(bytes(self.data[:65535]), BIG[:65535])
        self.assertEqual(self.call(8, di=off, cx=10000).cx, 4465)
        self.assertEqual(bytes(self.data[:4465]), BIG[65535:])
        # DOS supplies absolute seeks in SFT; 1121h is seek relative to EOF.
        r = self.call(0x21, di=off, cx=0xffff, dx=0xfffe)
        self.assertEqual((r.dx << 16) | r.ax, len(BIG) - 2)
        self.assertEqual(self.call(8, di=off, cx=3).cx, 2)
        self.assertEqual(bytes(self.data[:2]), BIG[-2:])
        self.put(self.sfts, off + 21, 511, 4)
        self.assertEqual(self.call(8, di=off, cx=1024).cx, 1024)
        self.assertEqual(bytes(self.data[:1024]), BIG[511:1535])

    def test_seek_limits_and_unchanged_position_on_failure(self):
        off = self.opened()
        self.call(0x21, di=off, cx=0xffff, dx=0xffe7, error=1)  # -25
        self.assertEqual(self.get(self.sfts, 21, 4), 0)
        self.put(self.sfts, 17, 0xfffffff0, 4)
        self.call(0x21, di=off, dx=32, error=1)
        self.assertEqual(self.get(self.sfts, 21, 4), 0)
        r = self.call(0x21, di=off, dx=15)
        self.assertEqual((r.dx << 16) | r.ax, 0xffffffff)

    def test_read_only_open_actions_and_mutations(self):
        for mode in (1, 2, 3):
            self.path("S:\\README.TXT")
            self.call(0x16, param=mode, error=5)
        for action in (0, 2, 0x10, 0x12):
            self.path("S:\\README.TXT"); self.sda[0x2dd] = action
            self.call(0x2e, error=5)
        for action in (1, 0x11):
            off = self.opened(extended=True, action=action)
            self.call(6, di=off)
        for name, code in [("S:\\SUBDIR", 5), ("S:\\MISSING.TXT", 2)]:
            self.path(name); self.call(0x16, error=code)
        for fn in (1, 2, 3, 4, 0x0e, 0x11, 0x13, 0x17, 0x18):
            self.path("S:\\README.TXT"); self.call(fn, error=5)
        off = self.opened()
        self.assertEqual(self.call(9, di=off, cx=100, error=5).cx, 0)
        self.call(7, di=off); self.call(0x0a, di=off)
        self.call(0x0b, di=off, error=5); self.call(0x2d, di=off, error=5)

    def test_capacity_reference_counts_and_slot_reuse(self):
        offsets = [self.opened(i) for i in range(16)]
        self.path("S:\\README.TXT"); self.call(0x16, di=16 * 64, error=4)
        self.put(self.sfts, offsets[0], 2)
        self.call(6, di=offsets[0])
        self.assertEqual(self.lib.media_unmount(), 5)
        self.call(0x16, di=16 * 64, error=4)
        self.call(6, di=offsets[0])
        self.opened(16)
        for off in offsets[1:] + [16 * 64]:
            self.call(6, di=off)
        self.assertEqual(self.lib.media_unmount(), 0)
        self.call(7, di=16 * 64)  # commit remains harmless offline

    def test_chain_other_drives_and_unrecognized_functions(self):
        for fn in (1, 5, 0x0f, 0x16, 0x19, 0x2e):
            self.path("C:\\README.TXT"); self.call(fn, handled=False)
        for fn in (6, 7, 8, 9, 0x0a, 0x21, 0x2d):
            self.call(fn, handled=False)
        self.data[0] = 0x82; self.call(0x1c, handled=False)
        for fn in (0x1d, 0x1e, 0x1f, 0x20, 0x22, 0x23, 0x24, 0x25, 0x26, 0xff):
            self.call(fn, handled=False)
        self.call(0, ax=0x1200, handled=False)
        self.assertEqual(self.call(0).ax, 0x11ff)

    def test_paths_attributes_space_and_dos3_extended_open(self):
        for name, code in [("S:\\MISSING", 3), ("S:\\README.TXT", 3)]:
            self.path(name); self.call(5, error=code)
        self.path("S:\\SUBDIR"); self.call(5)
        self.path("S:\\README.TXT")
        r = self.call(0x0f)
        self.assertEqual((r.ax, r.bx, r.di, r.cx, r.dx), (0x21, 0, 24, 0x6000, 0x5821))
        self.path("S:\\" + "A" * 80); self.call(0x16, error=3)
        r = self.call(0x0c, es=2)
        self.assertEqual((r.ax, r.bx, r.cx, r.dx), (0xf802, 35000, 512, 0))
        self.call(0x0c, es=3, handled=False)
        C.c_ubyte.in_dll(self.lib, "dos_major").value = 3
        self.path("S:\\README.TXT"); self.call(0x2e, error=1)

    def first(self, offset, path="S:\\*.TXT", attr=0):
        self.pointer(offset); self.path(path); self.sda[0x24d] = attr
        self.call(0x19)
        return bytes(self.data[offset + 21:offset + 32])

    def test_search_filters_independence_and_dos_result_copy(self):
        self.assertEqual(self.first(8192), b"README  TXT")
        self.assertEqual(self.first(8256, "S:\\SUBDIR\\*.*", 16), b".          ")
        self.pointer(8192); self.call(0x1c)
        self.assertEqual(bytes(self.data[8192 + 21:8192 + 32]), b"EMPTY   TXT")
        self.assertEqual(bytes(self.sda[0x19e:0x19e + 21]), bytes(self.data[8192:8192 + 21]))
        self.assertEqual(bytes(self.sda[0x1b3:0x1b3 + 32]), bytes(self.data[8192 + 21:8192 + 53]))
        self.assertEqual(self.first(8320, "S:\\*.*", 8), b"OTTER TEST ")
        self.call(0x1c, error=18)
        self.assertEqual(self.first(8384, "S:\\HIDDEN.TXT", 2), b"HIDDEN  TXT")
        self.path("S:\\HIDDEN.TXT"); self.sda[0x24d] = 0; self.call(0x19, error=18)
        self.path("S:\\MISSING\\*.*"); self.call(0x19, error=3)
        self.path("S:\\"); self.call(0x19, error=3)

    def test_search_eviction_and_corrupt_cookie(self):
        self.first(8192)
        for i in range(32):
            self.first(8256 + i * 64)
        self.pointer(8192); self.call(0x1c, error=18)
        self.first(8192)
        original = bytes(self.data[8192:8192 + 21])
        for offset, value, size in ((13, 32, 2), (15, 0, 4), (19, 0, 2)):
            self.data[8192:8192 + 21] = original
            self.put(self.data, 8192 + offset, value, size)
            self.call(0x1c, error=18)

    def test_mount_generation_and_empty_slot_recovery(self):
        self.first(8192); self.cds[:10] = b"S:\\SUBDIR\0"
        self.assertEqual(self.lib.media_unmount(), 0)
        self.assertEqual(bytes(self.cds[:4]), b"S:\\\0")
        self.call(0x1c, error=21)
        self.assertEqual(self.lib.media_unmount(), 0)
        C.c_int.in_dll(self.lib, "test_present").value = 0
        self.assertEqual(self.lib.media_mount(), 21)
        self.path("S:\\README.TXT"); self.call(0x16, error=21)
        C.c_int.in_dll(self.lib, "test_present").value = 1
        self.assertEqual(self.lib.media_mount(), 0)
        self.call(0x1c, error=18)
        self.first(8256)

    def test_removal_and_identity_change_reject_cached_reads(self):
        for variable in ("test_present", "test_changed"):
            off = self.opened()
            self.call(8, di=off, cx=1)
            self.data[0] = 0xa5
            C.c_int.in_dll(self.lib, variable).value = 0 if variable == "test_present" else 1
            r = self.call(8, di=off, cx=1, error=21)
            self.assertEqual(r.cx, 0); self.assertEqual(self.data[0], 0xa5)
            self.assertEqual(C.c_ubyte.in_dll(self.lib, "media_online").value, 0)
            self.assertEqual(self.lib.media_mount(), 5)
            self.call(6, di=off)
            C.c_int.in_dll(self.lib, "test_present").value = 1
            self.assertEqual(self.lib.media_mount(), 0)

    def test_partial_read_transport_failure_offlines_and_preserves_progress(self):
        off = self.opened(name="S:\\BIG.BIN")
        C.c_uint32.in_dll(self.lib, "fault_lba").value = self.layout["data"] + 100
        C.c_int.in_dll(self.lib, "fault_code").value = 30
        self.data[:1024] = b"\xa5" * 1024
        r = self.call(8, di=off, cx=1024, error=30)
        self.assertEqual(r.cx, 512)
        self.assertEqual(bytes(self.data[:512]), BIG[:512])
        self.assertEqual(bytes(self.data[512:1024]), b"\xa5" * 512)
        self.assertEqual(self.get(self.sfts, 21, 4), 512)
        self.assertEqual(C.c_ubyte.in_dll(self.lib, "media_online").value, 0)
        self.call(6, di=off)

    def test_invalid_sft_transport_errors_and_failed_mounts(self):
        self.put(self.sfts, 5, 0xc012)
        self.assertEqual(self.call(8, cx=10, error=6).cx, 0)
        self.call(6)  # close an unknown zero-reference SFT safely
        C.c_uint32.in_dll(self.lib, "fault_lba").value = self.layout["data"]
        self.path("S:\\README.TXT"); self.call(0x16, error=30)
        self.assertEqual(C.c_ubyte.in_dll(self.lib, "media_online").value, 0)
        C.c_uint32.in_dll(self.lib, "fault_lba").value = 0
        self.assertEqual(self.lib.media_mount(), 30)
        self.assertEqual(C.c_ubyte.in_dll(self.lib, "media_online").value, 0)
        C.c_uint32.in_dll(self.lib, "fault_lba").value = 0xffffffff
        self.assertEqual(self.lib.media_mount(), 0)
        self.call(0x0c, es=2)
        C.c_int.in_dll(self.lib, "test_present").value = 0
        self.call(0x0c, es=2, error=21)
        self.call(9, cx=10, error=21)
        self.call(0x21, error=21)

    def test_duplicate_stale_references_block_remount_until_final_close(self):
        off = self.opened(name="S:\\SUBDIR\\INNER.TXT")
        self.put(self.sfts, off, 2)
        C.c_int.in_dll(self.lib, "test_changed").value = 1
        self.call(8, di=off, cx=1, error=21)
        self.assertEqual(self.lib.media_mount(), 5)
        self.call(6, di=off)
        self.assertEqual(self.lib.media_mount(), 5)
        self.call(8, di=off, cx=1, error=21)
        self.call(6, di=off)
        self.assertEqual(self.lib.media_mount(), 0)
        off = self.opened(name="S:\\SUBDIR\\..\\README.TXT")
        self.call(8, di=off, cx=len(TEXT))
        self.assertEqual(bytes(self.data[:len(TEXT)]), TEXT)

    def test_private_controls_query_flags_and_offline_close(self):
        r = self.call(0, ax=0xd74f)
        self.assertEqual((r.ax, r.bx, r.cx, r.dx, r.si, r.di, r.bp),
                         (0x4f54, 0x524f, 18, 1, 0, 0x330, 2))
        off = self.opened()
        for cmd in (1, 2):
            self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=cmd, error=5)
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=99, error=1)
        self.call(6, di=off)
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=1)
        self.assertEqual(self.call(0, ax=0xd74f).dx, 0)
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=2)
        self.assertEqual(self.call(0, ax=0xd74f).dx, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
