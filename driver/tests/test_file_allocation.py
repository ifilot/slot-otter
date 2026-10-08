"""Allocation into stale media: EOF, zero-fill, directories and wire budgets.

Exercise the production filesystem and verified SPI transport for both formats.
The backing sectors deliberately contain nonzero bytes before allocation.
"""
import ctypes as C
import struct
import unittest
import test_rw_fs as common
from fat16_fixture import prepare as fat16_prepare
from test_rw_transport import Diagnostic
from fixture import entry


class AllocationCases:
    @classmethod
    def setUpClass(cls):
        common.ResidentFilesystemTests.setUpClass.__func__(cls)
        cls.lib.rw_read.argtypes = [C.POINTER(common.File), C.c_uint32,
                                   C.c_void_p, C.c_uint16, C.POINTER(C.c_uint16)]

    @classmethod
    def tearDownClass(cls):
        common.ResidentFilesystemTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.image = self.work / 'stale.img'
        if self.bits == 16:
            self.layout = fat16_prepare(self.image, resident=True)
            self.parent = 0xffffffff
        else:
            self.layout = common.builder.prepare(self.image, spc=8, resident=True)
            self.parent = 2
        self.spc = 32 if self.bits == 16 else 8
        self.cluster_bytes = self.spc * 512
        C.c_ubyte.in_dll(self.lib, 'fs_required').value = 0
        C.c_ubyte.in_dll(self.lib, 'rw_skip_fat_check').value = 0
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1
        C.c_int.in_dll(self.lib, 'sd_verify_writes').value = 1
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), 3), 0)
        self.assertEqual(self.lib.sd_init(), 0)
        self.assertEqual(self.lib.rw_mount(), 0)
        # Poison several free clusters in allocation-scan order, leaving FAT
        # metadata untouched. This models deleted files and quick formats.
        fat_lba = self.layout['start'] + (1 if self.bits == 16 else 32)
        width = self.bits // 8
        with self.image.open('r+b') as disk:
            disk.seek(fat_lba * 512)
            fat = disk.read(self.layout['fatsz'] * 512)
            free = [c for c in range(2, len(fat) // width)
                    if int.from_bytes(fat[c*width:(c+1)*width], 'little') == 0][:8]
            self.assertEqual(len(free), 8)
            self.free = free
            for cluster in free:
                disk.seek(self.address(cluster))
                disk.write(b'\xa5' * self.cluster_bytes)

    def tearDown(self):
        self.lib.rw_host_close()

    error = common.ResidentFilesystemTests.error
    finish = common.ResidentFilesystemTests.finish

    def address(self, cluster):
        return (self.layout['data'] + (cluster - 2) * self.spc) * 512

    def raw_cluster(self, cluster):
        with self.image.open('rb') as disk:
            disk.seek(self.address(cluster))
            return disk.read(self.cluster_bytes)

    def create_file(self):
        f = common.File()
        self.assertEqual(self.lib.rw_create(self.parent, b'NEW.BIN', C.byref(f)), 0)
        return f

    def append(self, f, data):
        self.assertEqual(self.lib.rw_append(C.byref(f), data, len(data)), 0, self.error())

    def assert_content(self, f, expected):
        # A request larger than the file must return exactly its visible bytes
        # and preserve the destination beyond that count.
        buffer = C.create_string_buffer(b'?' * (len(expected) + 100))
        done = C.c_uint16()
        self.assertEqual(self.lib.rw_read(C.byref(f), 0, buffer,
                                        len(expected) + 100, C.byref(done)), 0)
        self.assertEqual(done.value, len(expected))
        self.assertEqual(buffer.raw[:done.value], expected)
        self.assertEqual(buffer.raw[done.value:done.value+100], b'?' * 100)
        self.assertEqual(self.lib.rw_read(C.byref(f), f.size, buffer, 100,
                                        C.byref(done)), 0)
        self.assertEqual(done.value, 0)

    def test_small_appends_leave_slack_untouched_and_bound_wire_work(self):
        for verify in (1, 0):
            with self.subTest(verify=verify):
                C.c_int.in_dll(self.lib, 'sd_verify_writes').value = verify
                f = self.create_file()
                slack = self.raw_cluster(self.free[0])
                commands = (C.c_uint32 * 64).in_dll(self.lib, 'rw_host_commands')
                before_reads, before_writes = commands[17], commands[24]
                self.append(f, b'A' * 512)
                # Only payload + mirrored FAT reservation + directory size.
                self.assertEqual(commands[24] - before_writes, 4)
                self.assertLessEqual(commands[17] - before_reads, 8)
                self.assertEqual(self.raw_cluster(f.first), b'A'*512 + slack[512:])
                self.append(f, b'B' * 17)
                self.assert_content(f, b'A'*512 + b'B'*17)
                self.assertEqual(self.raw_cluster(f.first)[529:], slack[529:])
                self.assertEqual(self.lib.rw_delete(C.byref(f)), 0)
        self.finish()

    def test_cluster_boundary_does_not_clear_future_file_bytes(self):
        f = self.create_file()
        self.append(f, b'A' * (self.cluster_bytes - 3))
        self.append(f, b'B' * 10)
        self.assert_content(f, b'A'*(self.cluster_bytes-3) + b'B'*10)
        self.assertEqual(self.raw_cluster(f.last), b'B'*7 + b'\xa5'*(self.cluster_bytes-7))
        self.finish()

    def test_gap_extension_truncation_and_reuse_initialize_visible_bytes(self):
        f = self.create_file()
        self.append(f, b'OLD' * 200)
        self.assertEqual(self.lib.rw_truncate(C.byref(f), 3), 0)
        pos = self.cluster_bytes + 23
        done = C.c_uint16()
        self.assertEqual(self.lib.rw_write(C.byref(f), pos, b'TAIL', 4, C.byref(done)), 0)
        self.assertEqual(done.value, 4)
        expected = b'OLD' + bytes(pos-3) + b'TAIL'
        self.assert_content(f, expected)
        self.assertEqual(self.lib.rw_resize(C.byref(f), pos+101), 0)
        self.assert_content(f, expected + bytes(97))
        first = f.first
        self.assertEqual(self.lib.rw_delete(C.byref(f)), 0)
        f = self.create_file()
        self.append(f, b'NEW')
        self.assertEqual(f.first, first)
        self.assert_content(f, b'NEW')
        self.finish()

    def test_directory_allocation_clears_stale_entries(self):
        f = common.File()
        self.assertEqual(self.lib.rw_mkdir(self.parent, b'NEWDIR', C.byref(f)), 0)
        self.assertEqual(f.first, self.free[0])
        self.assertEqual(self.raw_cluster(f.first)[64:], bytes(self.cluster_bytes-64))
        self.assertEqual(self.lib.rw_rmdir(C.byref(f)), 0, self.error())
        self.finish()

    def test_directory_growth_clears_new_cluster_before_linking(self):
        directory = common.File()
        self.assertEqual(self.lib.rw_mkdir(self.parent, b'NEWDIR', C.byref(directory)), 0)
        with self.image.open('r+b') as disk:
            disk.seek(self.address(directory.first) + 64)
            disk.write(b''.join(entry('F%07d.BIN' % i, 32)
                                for i in range(self.cluster_bytes//32 - 2)))
        self.lib.fs_invalidate()
        f = common.File()
        self.assertEqual(self.lib.rw_create(directory.first, b'LAST.BIN', C.byref(f)), 0)
        next_cluster = self.lib.rw_fat(directory.first)
        self.assertEqual(next_cluster, self.free[1])
        self.assertEqual(self.raw_cluster(next_cluster)[32:], bytes(self.cluster_bytes-32))
        self.finish()

    def test_failed_payload_verification_never_publishes_stale_bytes(self):
        f = self.create_file()
        writes = C.c_uint.in_dll(self.lib, 'rw_host_writes').value
        # Two mirrored FAT writes, then first data write. Its readback has a
        # persistent CRC fault, exercising all retries and the poisoned state.
        self.lib.rw_host_fault_after_write(writes+3, self.address(self.free[0])//512)
        self.assertEqual(self.lib.rw_append(C.byref(f), b'NEW', 3), -1)
        self.assertEqual(Diagnostic.in_dll(self.lib, 'sd_diag').poisoned, 1)
        with self.image.open('rb') as disk:
            disk.seek(f.lba*512 + f.offset)
            entry = disk.read(32)
        self.assertEqual(struct.unpack_from('<I', entry, 28)[0], 0)
        self.assertEqual(struct.unpack_from('<H', entry, 26)[0], 0)
        before = C.c_uint.in_dll(self.lib, 'rw_host_writes').value
        self.assertEqual(self.lib.rw_resize(C.byref(f), 100), -1)
        self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_writes').value, before)


class Fat16AllocationTests(AllocationCases, unittest.TestCase):
    bits = 16
    library_name = 'allocation-fat16'


class Fat32AllocationTests(AllocationCases, unittest.TestCase):
    bits = 32
    library_name = 'allocation-fat32'
