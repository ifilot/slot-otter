"""Resident sector retries through the independent SPI model, not a mocked writer."""
import binascii
import ctypes as C
import hashlib
import pathlib
import random
import tempfile
import unittest
from fixture import create, TEXT
from support import library


class Diagnostic(C.Structure):
    _fields_ = [(n, C.c_uint32) for n in ('lba', 'verified', 'transmissions', 'retries')] + [
        (n, C.c_uint16) for n in ('error', 'first_error', 'stage', 'r1', 'token', 'status',
                                 'attempts', 'poisoned', 'first_stage', 'first_r1',
                                 'first_token', 'first_status')]


class ResidentTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='otter-rwsd-')
        cls.work = pathlib.Path(cls.tmp.name)
        cls.lib = C.CDLL(str(library(cls.work, 'rwsd', [
            'SDRW.C', 'tests/HOSTRW.C', 'emulation/slot_model.c'], ['-std=c99'])))
        cls.lib.rw_host_open.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.sd_write_arm.argtypes = [C.c_uint32, C.c_uint32]
        cls.lib.sd_write.argtypes = [C.c_uint32, C.c_void_p]
        cls.lib.sd_read.argtypes = [C.c_uint32, C.c_void_p]
        cls.lib.sd_crc16.argtypes = [C.c_void_p, C.c_uint16]
        cls.lib.sd_crc16.restype = C.c_uint16
        cls.lib.rw_host_replace_on_reset.argtypes = [C.c_char_p]
        cls.lib.rw_host_mutate_on_reset.argtypes = [C.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.image = self.work / 'card.img'
        self.layout = create(self.image)
        self.payload = bytes(i % 251 for i in range(512))
        self.buffer = C.create_string_buffer(self.payload, 512)
        self.scratch = 2056
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1
        self.open()

    def tearDown(self):
        self.lib.rw_host_close()

    def open(self, flags=3):
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), flags), 0)
        self.assertEqual(self.lib.sd_init(), 0)

    @property
    def diag(self):
        return Diagnostic.in_dll(self.lib, 'sd_diag')

    def commands(self):
        return C.c_uint.in_dll(self.lib, 'rw_host_writes').value

    def arm(self):
        self.assertEqual(self.lib.sd_write_arm(self.scratch, self.scratch + 1), 0)

    def digest(self):
        return hashlib.sha256(self.image.read_bytes()).digest()

    def sector(self, lba=None):
        with self.image.open('rb') as f:
            f.seek((self.scratch if lba is None else lba) * 512)
            return f.read(512)

    def assert_stopped(self):
        count = self.commands()
        before = self.digest()
        diagnostic = bytes(self.diag)
        self.assertNotEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.assertEqual(self.lib.sd_read(self.scratch, self.buffer), 21)
        self.assertEqual(count, self.commands())
        self.assertEqual(before, self.digest())
        self.assertEqual(bytes(self.diag), diagnostic, 'preserve failure evidence after poison')
        self.assertTrue(self.diag.poisoned)

    def test_crc_vectors_and_independent_oracle(self):
        self.assertEqual(self.lib.sd_crc16(b'123456789', 9), 0x31c3)
        for payload in (bytes(512), bytes([255])*512, self.payload):
            self.assertEqual(self.lib.sd_crc16(payload, 512), binascii.crc_hqx(payload, 0))

    def test_crc_all_single_bytes_and_variable_packet_lengths(self):
        for value in range(256):
            payload = bytes([value])
            self.assertEqual(self.lib.sd_crc16(payload, 1), binascii.crc_hqx(payload, 0))
        generator = random.Random(8088)
        for count in (0, 1, 2, 6, 16, 31, 255, 511, 512, 513, 1024, 65535):
            payload = bytes(generator.randrange(256) for _ in range(count))
            self.assertEqual(self.lib.sd_crc16(payload, count), binascii.crc_hqx(payload, 0), count)

    def test_shared_scratch_input_restored_after_recovery(self):
        self.arm()
        scratch = (C.c_uint8 * 512).in_dll(self.lib, 'sd_scratch')
        C.memmove(scratch, self.payload, 512)
        self.lib.rw_host_config(8, 1)
        self.lib.rw_host_mutate_on_reset(scratch)
        self.assertEqual(self.lib.sd_write(self.scratch, scratch), 0)
        self.assertEqual(self.sector(), self.payload)
        self.assertEqual(bytes(scratch), self.payload)
        self.assertEqual((self.diag.attempts, self.diag.retries), (2, 1))
        packets = bytes((C.c_uint8 * (514 * 8)).in_dll(self.lib, 'rw_host_packets'))
        self.assertEqual(packets[:512], self.payload)
        self.assertEqual(packets[:514], packets[514:1028])

    def test_readonly_initialization_and_crc_checked_read(self):
        before = self.digest()
        out = C.create_string_buffer(512)
        self.assertEqual(self.lib.sd_read(self.layout['data'] + 2, out), 0)
        self.assertTrue(out.raw.startswith(TEXT))
        self.assertEqual(self.commands(), 0)
        self.assertEqual(before, self.digest())
        failed_lba = self.layout['data'] + 100
        self.lib.rw_host_config(10, failed_lba)
        self.assertEqual(self.lib.sd_read(failed_lba, out), 30)
        self.assertEqual(self.diag.error, 102)
        self.assertEqual(self.diag.lba, failed_lba)

    def test_default_readonly_and_disarmed_guard(self):
        before = self.digest()
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 5)
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 0
        self.assertEqual(self.lib.sd_write_arm(self.scratch, self.scratch+1), 5)
        self.assertEqual(self.commands(), 0)
        self.assertEqual(before, self.digest())

    def test_range_fence_and_invalid_arm(self):
        self.arm()
        for lba in (0, self.scratch-1, self.scratch+1, 0xffffffff):
            self.assertEqual(self.lib.sd_write(lba, self.buffer), 5)
        for start, end in ((1, 1), (2, 1), (0xffffffff, 0)):
            self.assertEqual(self.lib.sd_write_arm(start, end), 13)
        self.assertEqual(self.commands(), 0)

    def test_success_exact_sector_crc_and_no_neighbors_changed(self):
        self.arm()
        before = self.image.read_bytes()
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        after = self.image.read_bytes()
        offset = self.scratch*512
        self.assertEqual(after[:offset], before[:offset])
        self.assertEqual(after[offset:offset+512], self.payload)
        self.assertEqual(after[offset+512:], before[offset+512:])
        self.assertEqual((self.diag.attempts, self.diag.verified, self.commands()), (1, 1, 1))
        packet = bytes((C.c_uint8*514).in_dll(self.lib, 'rw_host_packets'))
        self.assertEqual(packet[:512], self.payload)
        self.assertEqual(int.from_bytes(packet[512:], 'big'), binascii.crc_hqx(self.payload, 0))

    def test_transient_mismatch_reinitializes_then_retries_identical_packet(self):
        self.arm()
        self.lib.rw_host_config(8, 1)
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.assertEqual(self.sector(), self.payload)
        self.assertEqual((self.diag.attempts, self.diag.retries, self.diag.first_error), (2, 1, 105))
        self.assertEqual(self.diag.first_stage, 17)
        self.assertEqual(self.diag.first_token, 254)
        self.assertFalse(self.diag.poisoned)
        packets = bytes((C.c_uint8*(514*8)).in_dll(self.lib, 'rw_host_packets'))
        self.assertEqual(packets[:514], packets[514:1028])
        lbas = (C.c_uint32*8).in_dll(self.lib, 'rw_host_lbas')
        self.assertEqual(list(lbas[:2]), [self.scratch]*2)
        self.assertGreater(C.c_uint.in_dll(self.lib, 'rw_host_resets').value, 1)

    def test_retry_snapshot_survives_callers_buffer_change(self):
        self.arm()
        self.lib.rw_host_config(8, 1)
        self.lib.rw_host_mutate_on_reset(self.buffer)
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.assertEqual(self.buffer.raw, b'\x73'*512)
        self.assertEqual(self.sector(), self.payload)

    def test_transient_rejection_and_status_error_recover(self):
        for option, error in ((2, 103), (5, 104)):
            with self.subTest(option=option):
                self.open()
                self.arm()
                self.lib.rw_host_config(option, 1)
                self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
                self.assertEqual(self.diag.attempts, 2)
                self.assertEqual(self.diag.first_error, error)
                self.assertEqual(self.sector(), self.payload)

    def test_transient_wire_crc_error_completes_rejection_then_resets(self):
        self.arm()
        self.lib.rw_host_flip_crc(1)
        self.lib.rw_host_config(28,64)
        self.lib.rw_host_config(27,7)
        self.assertEqual(self.lib.sd_write(self.scratch,self.buffer),0)
        self.assertEqual(self.sector(),self.payload)
        self.assertEqual((self.diag.first_error,self.diag.first_stage),(102,324))
        self.assertEqual(self.diag.attempts,2)

    def test_wire_crc_rejection_without_sector_recovery_stops(self):
        self.arm()
        self.lib.rw_host_flip_crc(1)
        self.lib.rw_host_config(27,2)
        before=self.digest()
        self.assertEqual(self.lib.sd_write(self.scratch,self.buffer),29)
        self.assertEqual(self.commands(),1)
        self.assertEqual(self.diag.first_error,102)
        self.assertEqual(self.diag.error,101)
        self.assertEqual(before,self.digest())
        self.assert_stopped()

    def test_persistent_mismatch_stops_after_three_total_attempts(self):
        self.arm()
        self.lib.rw_host_repeat(8, 1)
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 29)
        self.assertEqual((self.commands(), self.diag.attempts, self.diag.retries), (3, 3, 2))
        self.assertEqual((self.diag.first_error, self.diag.error), (105, 105))
        self.assert_stopped()

    def test_persistent_rejection_stops_after_three_total_attempts(self):
        self.arm()
        self.lib.rw_host_repeat(2, 1)
        before = self.digest()
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 29)
        self.assertEqual((self.commands(), self.diag.attempts), (3, 3))
        self.assertEqual(self.diag.first_error, 103)
        self.assertEqual(before, self.digest())
        self.assert_stopped()

    def test_failed_read_access_after_reset_prevents_another_write(self):
        self.arm()
        self.lib.rw_host_config(10, self.scratch)
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 29)
        self.assertEqual(self.commands(), 1)
        self.assertEqual(self.diag.first_error, 102)
        self.assert_stopped()

    def test_changed_identity_on_recovery_never_writes_replacement(self):
        other = self.work / 'replacement.img'
        create(other)
        before = hashlib.sha256(other.read_bytes()).digest()
        self.arm()
        self.lib.rw_host_config(8, 1)
        self.lib.rw_host_replace_on_reset(str(other).encode())
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 21)
        self.assertEqual(self.commands(), 1)
        self.assertEqual(before, hashlib.sha256(other.read_bytes()).digest())
        self.assertEqual(self.diag.first_error, 105)
        self.assert_stopped()

    def test_absent_card_on_recovery_stops(self):
        self.arm()
        self.lib.rw_host_config(8, 1)
        self.lib.rw_host_replace_on_reset(b'')
        self.assertNotEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.assertEqual(self.commands(), 1)
        self.assert_stopped()

    def test_busy_forever_and_removal_stop_without_second_write(self):
        for option in (3, 7):
            with self.subTest(option=option):
                self.open()
                self.arm()
                self.lib.rw_host_config(option, 1)
                self.assertNotEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
                self.assertEqual(self.commands(), 1)
                self.assertEqual(self.diag.first_error, 101)
                self.assert_stopped()

    def test_reset_without_crc_support_prevents_retry(self):
        self.arm()
        self.lib.rw_host_config(8, 1)
        self.lib.rw_host_config(6, 1)
        self.assertNotEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.assertEqual(self.commands(), 1)
        self.assertEqual(self.diag.first_error, 105)
        self.assertEqual(self.diag.error, 102)
        self.assert_stopped()

    def test_explicit_remount_clears_poison_and_disarms(self):
        self.arm()
        self.lib.rw_host_repeat(8, 1)
        self.assertNotEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.lib.rw_host_repeat(0, 0)
        self.assertEqual(self.lib.sd_init(), 0)
        self.assertFalse(self.diag.poisoned)
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 5)
        self.arm()
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 0)

    def test_cold_start_delayed_byte_completion_and_ready_cmd55(self):
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), 15), 0)
        self.lib.rw_host_timing(3)
        self.lib.rw_host_config(23, 1)
        self.lib.rw_host_config(24, 3)
        self.assertEqual(self.lib.sd_init(), 0)
        self.arm()
        self.assertEqual(self.lib.sd_write(self.scratch, self.buffer), 0)
        self.assertEqual(self.sector(), self.payload)
        self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_unfinished').value, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
