"""Behavioral guards for CRC tables and bounded chain-audit identity checks."""
import ctypes as C
from pathlib import Path
import random
import shutil
import tempfile
import unittest

from support import ROOT, library
import test_rw_fs as filesystem
from test_fs import FileCursor


def remainder(value, polynomial):
    """Independent polynomial division, not the driver's table algorithm."""
    while value.bit_length() >= polynomial.bit_length():
        value ^= polynomial << (value.bit_length() - polynomial.bit_length())
    return value


class PerformanceGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='otter-perf-guards-')
        cls.work = Path(cls.tmp.name)
        # Interpose only in this test library; the shipped driver has no hook.
        fat = (ROOT / 'FAT32.C').read_text()
        marker = 'U32 fs_fat_entry(U32 c) {'
        assert fat.count(marker) == 1
        fat = fat.replace(marker, 'static U32 raw_entry(U32 c) {')
        fat += '''
static unsigned hook_step,hook_when;
static const char *hook_path;
extern int rw_host_replace(const char *path);
void test_hook(unsigned when,const char *path) {
  hook_step=0; hook_when=when; hook_path=path;
}
U32 fs_fat_entry(U32 c) {
  U32 result=raw_entry(c);
  if (hook_when && ++hook_step==hook_when) {
    hook_when=0; rw_host_replace(hook_path);
  }
  return result;
}
'''
        (cls.work / 'FAT32.C').write_text(fat)
        writer = (ROOT / 'RWFS.C').read_text() + '''
int test_chain(U32 c) {
  U32 count;
  fs_invalidate(); return chain_length(c,&count,0,0);
}
'''
        (cls.work / 'RWFS.C').write_text(writer)
        cls.lib = C.CDLL(str(library(cls.work, 'performance', [
            'SDRW.C', str(cls.work / 'RWFS.C'), str(cls.work / 'FAT32.C'),
            'tests/HOSTRW.C', 'tests/emulation/slot_model.c'], ['-std=c99'])))
        cls.lib.test_hook.argtypes = [C.c_uint, C.c_char_p]
        cls.lib.test_chain.argtypes = [C.c_uint32]
        cls.lib.rw_host_open.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.rw_lookup.argtypes = [C.c_char_p, C.c_void_p]
        cls.lib.rw_create.argtypes = [C.c_uint32, C.c_char_p, C.c_void_p]
        cls.lib.rw_append.argtypes = [C.c_void_p, C.c_void_p, C.c_uint16]
        cls.lib.rw_read.argtypes = [C.c_void_p, C.c_uint32, C.c_void_p,
                                   C.c_uint16, C.c_void_p]
        cls.lib.fs_read.argtypes = [C.c_void_p, C.c_uint32, C.c_void_p,
                                   C.c_uint16, C.c_void_p]
        cls.lib.sd_crc16.argtypes = [C.c_void_p, C.c_uint16]
        cls.lib.sd_crc16.restype = C.c_uint16
        cls.lib.sd_test_crc7.argtypes = [C.c_void_p]
        cls.lib.sd_test_crc7.restype = C.c_uint8

    @classmethod
    def tearDownClass(cls):
        cls.lib.rw_host_close()
        cls.tmp.cleanup()

    def test_exhaustive_two_byte_crc16(self):
        for value in range(65536):
            packet = value.to_bytes(2, 'big')
            self.assertEqual(self.lib.sd_crc16(packet, 2),
                             remainder(value << 16, 0x11021), value)

    def test_varied_command_crc7(self):
        rng = random.Random(0x1207)
        for command in range(64):
            for unused in range(512):
                packet = bytes([64 | command]) + rng.getrandbits(32).to_bytes(4, 'big')
                expected = (remainder(int.from_bytes(packet, 'big') << 7, 0x89) << 1) | 1
                self.assertEqual(self.lib.sd_test_crc7(packet), expected, packet.hex())

    def test_mid_audit_removal_and_replacement_never_accept_cached_proof(self):
        case = filesystem.ResidentFilesystemTests()
        case.work, case.lib = self.work, self.lib
        for replacement in (False, True):
            for step in (1, 2):
                with self.subTest(replacement=replacement, link=step):
                    case.setUp()
                    try:
                        file = case.lookup('FRAG.BIN')
                        before = case.image.read_bytes()
                        target = b''
                        other = self.work / 'replacement.img'
                        if replacement:
                            shutil.copyfile(case.image, other)
                            with other.open('r+b') as stream:
                                stream.seek(2048 * 512 + 67)
                                stream.write(b'NEWW')
                            replacement_before = other.read_bytes()
                            target = str(other).encode()
                        writes = C.c_uint.in_dll(self.lib, 'rw_host_writes').value
                        self.lib.test_hook(step, target)
                        self.assertNotEqual(self.lib.test_chain(file.first), 0)
                        self.assertEqual(case.error(), 21)
                        self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_writes').value, writes)
                        self.assertEqual(case.image.read_bytes(), before)
                        if replacement:
                            self.assertEqual(other.read_bytes(), replacement_before)
                    finally:
                        self.lib.test_hook(0, b'')
                        case.tearDown()

    def test_all_cluster_sizes_read_and_append_across_64k_boundary(self):
        case = filesystem.ResidentFilesystemTests()
        case.work, case.lib = self.work, self.lib
        payload = bytes(i % 251 for i in range(65538))
        for spc in (1, 2, 4, 8, 16, 32, 64, 128):
            with self.subTest(sectors_per_cluster=spc):
                case.image = self.work / 'geometry.img'
                # Large geometries use sparse files; never read the whole image.
                filesystem.builder.prepare(case.image, spc=spc)
                C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1
                C.c_int.in_dll(self.lib, 'sd_verify_writes').value = 1
                C.c_ubyte.in_dll(self.lib, 'rw_skip_fat_check').value = 0
                self.assertEqual(self.lib.rw_host_open(str(case.image).encode(), 3), 0)
                try:
                    self.assertEqual(self.lib.sd_init(), 0)
                    self.assertEqual(self.lib.rw_mount(), 0)
                    file = case.create_file('BOUND.BIN')
                    self.assertEqual(self.lib.rw_append(C.byref(file), payload[:65535], 65535), 0)
                    self.assertEqual(self.lib.rw_append(C.byref(file), payload[65535:], 3), 0)
                    self.assertEqual(case.content('BOUND.BIN'), payload)
                    for position in (511, spc * 512 - 1, 65534):
                        length = min(4, len(payload) - position)
                        output, done = C.create_string_buffer(length), C.c_uint16()
                        self.assertEqual(self.lib.rw_read(C.byref(file), position,
                                         output, length, C.byref(done)), 0)
                        self.assertEqual(done.value, length)
                        self.assertEqual(output.raw, payload[position:position + length])
                        cursor = FileCursor(file.first, file.first, 0)
                        self.lib.fs_invalidate()
                        self.assertEqual(self.lib.fs_read(C.byref(cursor), position,
                                         output, length, C.byref(done)), 0)
                        self.assertEqual(done.value, length)
                        self.assertEqual(output.raw, payload[position:position + length])
                    self.assertEqual(self.lib.rw_flush(), 0)
                finally:
                    self.lib.rw_host_close()
