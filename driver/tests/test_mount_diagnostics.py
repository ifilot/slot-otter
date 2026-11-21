"""Reproduce writable mount refusals with CRC-valid sectors and no SD writes."""
import ctypes as C
import struct
import unittest

import fat16_fixture
import test_rw_fs as fs
import test_rw_redirector as redirector
from test_rw_transport import Diagnostic


class MountDiagnostic(C.Structure):
    _fields_ = [('lba', C.c_uint32), ('value', C.c_uint32),
                ('check', C.c_uint16), ('fat_bits', C.c_uint16)]


class MountDiagnosticTests(unittest.TestCase):
    library_name = 'mount-diagnostics'
    memory = redirector.WritableRedirectorTests.memory
    call = redirector.WritableRedirectorTests.call

    @classmethod
    def setUpClass(cls):
        redirector.WritableRedirectorTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        redirector.WritableRedirectorTests.tearDownClass.__func__(cls)

    def setUp(self):
        self.image = self.work / 'card.img'
        self.lib.test_reset()
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1
        C.c_ubyte.in_dll(self.lib, 'rw_skip_fat_check').value = 0

    def tearDown(self):
        self.lib.rw_host_close()

    def open(self):
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), 3), 0)

    def patch(self, lba, offset, data):
        with self.image.open('r+b') as disk:
            disk.seek(lba * 512 + offset)
            disk.write(data)

    def snapshot(self):
        return MountDiagnostic.from_buffer_copy(
            bytes(MountDiagnostic.in_dll(self.lib, 'mount_diag')))

    def query(self):
        out = self.memory(4)
        out[:16] = b'\xa5' * 16
        r = self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=13,
                      cx=12, es=4, di=2)
        self.assertEqual(r.cx, 12)
        self.assertEqual(bytes(out[:2]) + bytes(out[14:16]), b'\xa5' * 4)
        return MountDiagnostic.from_buffer_copy(bytes(out[2:14]))

    def test_fat16_dirty_and_error_flags_reproduce_photo_and_survive_offline(self):
        for value in (0x7fff, 0xbfff, 0x3fff):
            with self.subTest(value=hex(value)):
                layout = fat16_fixture.prepare(
                    self.image, spc=4, total_sectors=32768, partitioned=False)
                for lba in (1, 1 + layout['fatsz']):
                    self.patch(lba, 2, struct.pack('<H', value))
                before = self.image.read_bytes()
                self.open()
                self.lib.rw_feedback(1)
                self.assertEqual(self.lib.media_mount(), 13)
                self.lib.rw_feedback(0)
                sd = Diagnostic.in_dll(self.lib, 'sd_diag')
                self.assertEqual((sd.error, sd.stage, sd.lba, sd.r1, sd.token),
                                 (0, 17, 1, 0, 254))
                length = C.c_uint16.in_dll(self.lib, 'rw_feedback_length').value
                output = bytes((C.c_ubyte * 4096).in_dll(
                    self.lib, 'rw_feedback_output')[:length])
                self.assertIn(b'100%', output)
                self.assertEqual(C.c_ubyte.in_dll(self.lib, 'media_online').value, 0)
                d = self.query()
                self.assertEqual((d.check, d.fat_bits, d.lba, d.value), (6, 16, 1, value))
                self.assertEqual(bytes(d), bytes(self.query()), 'queries retain evidence')
                self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_writes').value, 0)
                C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 0
                self.assertEqual(self.lib.media_mount(), 0)
                self.assertEqual(self.query().check, 0, 'RO clears the previous refusal')
                self.assertEqual(self.image.read_bytes(), before)
                self.assertEqual(self.lib.media_unmount(), 0)
                self.lib.rw_host_close()
                C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1

    def test_fat32_flag_and_fsinfo_failures_remain_distinct(self):
        for check in (6, 7, 8):
            with self.subTest(check=check):
                layout = fs.builder.prepare(self.image)
                start = layout['start']
                if check == 6:
                    lba, value = start + 32, 0x07ffffff
                    for fat in (lba, lba + layout['fatsz']):
                        self.patch(fat, 4, struct.pack('<I', value))
                else:
                    lba, value = start + (1 if check == 7 else 7), 0x21444142
                    self.patch(lba, 0, b'BAD!')
                before = self.image.read_bytes()
                self.open()
                self.assertEqual(self.lib.media_mount(), 13)
                d = self.query()
                self.assertEqual((d.check, d.fat_bits, d.lba, d.value),
                                 (check, 32, lba, value))
                self.assertEqual(Diagnostic.in_dll(self.lib, 'sd_diag').error, 0)
                self.assertEqual(self.image.read_bytes(), before)
                self.lib.rw_host_close()

    def test_mirror_and_backup_boot_failures_identify_rejected_sector(self):
        for check in (4, 5):
            with self.subTest(check=check):
                layout = fs.builder.prepare(self.image)
                lba = layout['start'] + (6 if check == 4 else 32 + layout['fatsz'])
                self.patch(lba, 13 if check == 4 else 100, b'\x08')
                before = self.image.read_bytes()
                self.open()
                self.assertEqual(self.lib.media_mount(), 13)
                d = self.query()
                self.assertEqual((d.check, d.fat_bits, d.lba), (check, 32, lba))
                self.assertEqual(self.image.read_bytes(), before)
                self.lib.rw_host_close()

    def test_transport_failure_clears_previous_filesystem_rejection(self):
        layout = fs.builder.prepare(self.image)
        self.patch(layout['start'] + 1, 0, b'BAD!')
        self.open()
        self.assertEqual(self.lib.media_mount(), 13)
        self.assertEqual(self.query().check, 7)
        self.lib.rw_host_config(29, 11)  # Corrupt the CMD10 CID packet CRC.
        self.assertEqual(self.lib.media_mount(), 21)
        self.assertEqual(Diagnostic.in_dll(self.lib, 'sd_diag').error, 102)
        self.assertEqual(self.query().check, 0)

    def test_query_rejects_short_or_wrapping_buffers_without_overwriting(self):
        before = bytes(self.snapshot())
        for size, offset in ((11, 0), (12, 65524), (12, 65535)):
            self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=13,
                      cx=size, es=4, di=offset, error=1)
            self.assertEqual(bytes(self.snapshot()), before)

    # Dirty-volume recovery (OTTERSD /MOUNT /RECOVER, control command 3).
    def volume(self, bits):
        """Return (fat LBAs, entry-1 offset, width, clean bit) for a fresh image."""
        if bits == 16:
            layout = fat16_fixture.prepare(
                self.image, spc=4, total_sectors=32768, partitioned=False)
            first, offset, width, clean = 1, 2, '<H', 0x8000
        else:
            layout = fs.builder.prepare(self.image)
            first, offset, width, clean = layout['start'] + 32, 4, '<I', 0x08000000
        return [first, first + layout['fatsz']], offset, width, clean

    def entry1(self, lba, offset, width):
        with self.image.open('rb') as disk:
            disk.seek(lba * 512 + offset)
            return struct.unpack(width, disk.read(struct.calcsize(width)))[0]

    def recover_flag(self):
        return C.c_ubyte.in_dll(self.lib, 'rw_recover').value

    def info_flags(self):
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=8, cx=32, es=4, di=4096)
        return int.from_bytes(bytes(self.memory(4)[4096 + 28:4096 + 30]), 'little')

    def writes(self):
        return C.c_uint.in_dll(self.lib, 'rw_host_writes').value

    def test_recover_marks_dirty_volume_clean_in_every_fat_copy(self):
        for bits, request in ((16, dict(si=3)), (32, dict(si=11, cx=3, di=0))):
            with self.subTest(bits=bits):
                fats, offset, width, clean = self.volume(bits)
                original = self.entry1(fats[0], offset, width)
                self.assertTrue(original & clean)
                for lba in fats:
                    self.patch(lba, offset, struct.pack(width, original & ~clean))
                expected = None
                self.open()
                self.assertEqual(self.lib.media_mount(), 13, 'refused without /RECOVER')
                self.assertEqual(self.query().check, 6)
                self.assertEqual(self.writes(), 0)
                self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, **request)
                self.assertEqual(C.c_ubyte.in_dll(self.lib, 'media_online').value, 1)
                self.assertEqual(self.recover_flag(), 2)
                self.assertTrue(self.info_flags() & 256)
                self.assertEqual(self.writes(), 2, 'only FAT sector zero of each copy')
                self.assertEqual([self.entry1(lba, offset, width) for lba in fats],
                                 [original, original])
                expected = self.image.read_bytes()
                # One-shot: a later plain mount neither recovers nor reports it.
                self.assertEqual(self.lib.media_mount(), 0)
                self.assertEqual(self.recover_flag(), 0)
                self.assertFalse(self.info_flags() & 256)
                self.assertEqual(self.lib.media_unmount(), 0)
                self.assertEqual(self.image.read_bytes(), expected)
                self.lib.rw_host_close()

    def test_recover_refuses_io_error_and_mismatched_fat_without_writes(self):
        for bits in (16, 32):
            for case in ('io-error', 'mirror', 'mirror-skipfatcheck'):
                with self.subTest(bits=bits, case=case):
                    fats, offset, width, clean = self.volume(bits)
                    original = self.entry1(fats[0], offset, width)
                    value = original & ~clean
                    if case == 'io-error':
                        value &= ~(clean >> 1)
                    for lba in fats:
                        self.patch(lba, offset, struct.pack(width, value))
                    if case != 'io-error':
                        # Differ only in the last sector of the second copy, which
                        # the fast mount check alone would never read.
                        last = fats[1] + (fats[1] - fats[0]) - 1
                        self.patch(last, 500, b'\x5a')
                    C.c_ubyte.in_dll(self.lib, 'rw_skip_fat_check').value = (
                        case == 'mirror-skipfatcheck')
                    before = self.image.read_bytes()
                    self.open()
                    self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=3, error=13)
                    self.assertEqual(self.query().check, 6 if case == 'io-error' else 5)
                    self.assertEqual(self.recover_flag(), 0)
                    self.assertFalse(self.info_flags() & 256)
                    self.assertEqual(self.writes(), 0)
                    self.assertEqual(self.image.read_bytes(), before)
                    self.lib.rw_host_close()
                    C.c_ubyte.in_dll(self.lib, 'rw_skip_fat_check').value = 0

    def test_recover_on_clean_volume_changes_nothing(self):
        for bits in (16, 32):
            with self.subTest(bits=bits):
                self.volume(bits)
                before = self.image.read_bytes()
                self.open()
                self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=3)
                self.assertEqual(self.recover_flag(), 0)
                self.assertEqual(self.writes(), 0)
                self.assertEqual(self.lib.media_unmount(), 0)
                self.assertEqual(self.image.read_bytes(), before)
                self.lib.rw_host_close()

    def test_recover_requires_writable_driver(self):
        self.volume(32)
        self.open()
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 0
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=3)
        self.assertEqual(self.recover_flag(), 0)
        self.assertEqual(self.writes(), 0)
