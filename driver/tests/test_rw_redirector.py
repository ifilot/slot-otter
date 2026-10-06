"""Real writable DOS callbacks over the real SPI/card model and FAT writer."""
import ctypes as C
import pathlib
import subprocess
import tempfile
import unittest
import test_redirector as ro
import test_rw_fs as fs
from fixture import TEXT
from support import library


class WritableRedirectorTests(unittest.TestCase):
    memory = ro.RedirectorTests.memory
    put = ro.RedirectorTests.put
    get = ro.RedirectorTests.get
    pointer = ro.RedirectorTests.pointer
    path = ro.RedirectorTests.path
    call = ro.RedirectorTests.call
    opened = ro.RedirectorTests.opened
    first = ro.RedirectorTests.first

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='otter-rw-redirector-')
        cls.work = pathlib.Path(cls.tmp.name)
        cls.lib = C.CDLL(str(library(cls.work, 'rwredir', [
            'FAT32.C', 'RWFS.C', 'SDRW.C', 'tests/HOSTRW.C',
            'tests/HOSTRWD.C', 'emulation/slot_model.c'], ['-std=c99'])))
        cls.lib.rw_host_open.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.test_far_at.argtypes = [C.c_uint16, C.c_uint16]
        cls.lib.test_far_at.restype = C.POINTER(C.c_ubyte)
        cls.regs = ro.Registers.in_dll(cls.lib, 'regs')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.image = self.work/'card.img'
        self.layout = fs.builder.prepare(self.image)
        self.lib.test_reset()
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), 3), 0)
        self.sda, self.cds, self.sfts, self.data = [self.memory(n) for n in range(1, 5)]
        self.put(self.sda, 0x10, 0x1234)
        self.sda[0x30:0x34] = bytes((6, 10, 46, 0))  # 2026-10-06
        self.assertEqual(self.lib.media_mount(), 0)

    def tearDown(self):
        self.lib.rw_host_close()

    def created(self, name='S:\\NEW.BIN', slot=0, attr=0, new=False):
        off = slot*64
        self.put(self.sfts, off, 1)
        self.sfts[off+43:off+64] = b'\xa5'*21
        self.path(name)
        self.call(0x17, di=off, param=attr | (0x100 if new else 0))
        return off

    def write(self, off, data, error=None):
        self.pointer()
        self.data[:len(data)] = data
        return self.call(9, di=off, cx=len(data), error=error)

    def seek(self, off, pos):
        self.put(self.sfts, off+21, pos, 4)

    def content(self, path):
        return subprocess.check_output(['mtype', '-i', str(self.image)+'@@1048576', '::'+path])

    def clean(self):
        part = self.work/'part.img'
        with self.image.open('rb') as disk:
            disk.seek(2048*512)
            part.write_bytes(disk.read(self.layout['total']*512))
        check = subprocess.run(['fsck.fat', '-n', str(part)], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout+check.stderr)

    def test_create_write_commit_close_and_reopen(self):
        off = self.created()
        payload = bytes(i % 251 for i in range(1025))
        self.assertEqual(self.write(off, payload).cx, len(payload))
        self.assertEqual(self.get(self.sfts, off+21, 4), len(payload))
        self.assertEqual(self.get(self.sfts, off+17, 4), len(payload))
        self.assertEqual(bytes(self.sfts[43:64]), b'\xa5'*21)
        self.call(7, di=off)
        self.assertEqual(self.get(self.sfts, off), 1)
        self.call(6, di=off)
        off = self.opened(name='S:\\NEW.BIN')
        self.assertEqual(self.call(8, di=off, cx=2000).cx, len(payload))
        self.assertEqual(bytes(self.data[:len(payload)]), payload)
        self.call(6, di=off)
        self.assertEqual(self.content('NEW.BIN'), payload)
        self.clean()

    def test_access_modes_and_invalid_open_modes(self):
        for mode in (3, 8, 0x50, 0x70, 0x100):
            self.path('S:\\README.TXT')
            self.call(0x16, param=mode, error=12)
        off = self.opened()
        self.assertEqual(self.write(off, b'X', error=5).cx, 0)
        self.call(6, di=off)
        off = self.opened(mode=1)
        self.assertEqual(self.call(8, di=off, cx=1, error=5).cx, 0)
        self.write(off, b'X'); self.call(6, di=off)
        self.assertEqual(self.content('README.TXT'), b'X'+TEXT[1:])

    def test_clean_create_read_failure_offlines_without_writes(self):
        before=self.image.read_bytes()
        self.lib.rw_host_config(10,2048+32)
        self.path('S:\\NEW.BIN')
        self.call(0x17,param=0,error=30)
        self.assertEqual(C.c_ubyte.in_dll(self.lib,'media_online').value,0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)
        self.assertEqual(self.image.read_bytes(),before)

    def test_gap_zero_write_extension_truncate_and_seek_end(self):
        off = self.created()
        self.write(off, b'FIRST'); self.seek(off, 1025); self.write(off, b'LAST')
        self.seek(off, 3); self.write(off, b'')
        self.seek(off, 513); self.write(off, b'')
        r = self.call(0x21, di=off, cx=0xffff, dx=0xffff)
        self.assertEqual((r.dx<<16)|r.ax, 512)
        self.call(6, di=off)
        self.assertEqual(self.content('NEW.BIN'), b'FIR'+bytes(510))
        self.clean()

    def test_created_readonly_can_write_initial_handle_then_denies_new_writer(self):
        off = self.created(attr=1)
        self.write(off, b'INITIAL'); self.call(6, di=off)
        self.path('S:\\NEW.BIN'); self.call(0x16, param=1, error=5)
        self.call(0x13, error=5)
        off = self.opened(name='S:\\NEW.BIN')
        self.call(8, di=off, cx=7); self.call(6, di=off)
        self.assertEqual(self.content('NEW.BIN'), b'INITIAL')
        self.clean()

    def test_create_existing_truncate_new_only_and_extended_actions(self):
        self.path('S:\\README.TXT'); self.call(0x17, param=0x100, error=80)
        off = self.created('S:\\README.TXT')
        self.assertEqual(self.get(self.sfts, off+17, 4), 0)
        self.call(6, di=off)
        for name, action, branch in [('S:\\README.TXT', 1, 1),
                                    ('S:\\EXT.BIN', 0x11, 2),
                                    ('S:\\EXT.BIN', 0x12, 3)]:
            self.path(name); self.sda[0x2dd] = action
            self.put(self.sda, 0x2df, 2); self.put(self.sda, 0x2e1, 2)
            self.put(self.sfts, 0, 1)
            self.assertEqual(self.call(0x2e).cx, branch)
            self.write(0, b'EXT'); self.call(6)
        self.assertEqual(self.content('EXT.BIN'), b'EXT')
        self.clean()

    def test_shared_handles_refresh_first_cluster_size_and_preserve_positions(self):
        a = self.created()
        b = self.opened(1, 'S:\\NEW.BIN', mode=0x42)
        self.write(a, b'FIRST')
        self.assertEqual(self.get(self.sfts, b+17, 4), 5)
        self.assertEqual(self.get(self.sfts, b+21, 4), 0)
        self.seek(b, 5); self.write(b, b'SECOND')
        self.seek(a, 0); self.call(8, di=a, cx=20)
        self.assertEqual(bytes(self.data[:11]), b'FIRSTSECOND')
        self.seek(b, 2); self.write(b, b'')
        self.assertEqual(self.get(self.sfts, a+17, 4), 2)
        self.call(6, di=a); self.call(6, di=b)
        self.assertEqual(self.content('NEW.BIN'), b'FI')
        self.clean()

    def test_replace_updates_other_shared_sft_sizes_immediately(self):
        a = self.opened(mode=0x42)
        b = self.created('S:\\README.TXT', slot=1)
        self.assertEqual(self.get(self.sfts, a+17, 4), 0)
        self.write(b, b'REPLACED')
        self.assertEqual(self.get(self.sfts, a+17, 4), 8)
        self.call(6, di=a); self.call(6, di=b)
        self.assertEqual(self.content('README.TXT'), b'REPLACED')
        self.clean()

    def test_sharing_denial_both_directions_and_compatibility_processes(self):
        for old, new in [(0x10, 0x40), (0x20, 0x41), (0x32, 0x40),
                         (0x40, 0x11), (0x41, 0x20), (0x40, 0x31)]:
            with self.subTest(old=old, new=new):
                off = self.opened(mode=old)
                self.path('S:\\README.TXT'); self.call(0x16, di=64, param=new, error=32)
                self.call(6, di=off)
        a = self.opened(mode=2)
        self.put(self.sda, 0x10, 0x5678)
        self.path('S:\\README.TXT'); self.call(0x16, di=64, param=0x40, error=32)
        self.call(6, di=a)

    def lock(self, off, start, length, unlock=False, error=None):
        self.put(self.sda, 0x400, start, 4); self.put(self.sda, 0x404, length, 4)
        self.call(0x0a, di=off, ds=1, dx=0x400, cx=1, bx=int(unlock), error=error)

    def test_region_locks_guard_reads_writes_truncation_and_final_close(self):
        a = self.opened(mode=0x42); b = self.opened(1, mode=0x42)
        self.lock(a, 3, 4)
        self.seek(b, 2); self.call(8, di=b, cx=3, error=33)
        self.assertEqual(self.write(b, b'XYZ', error=33).cx, 0)
        self.seek(b, 2); self.write(b, b'', error=33)
        self.lock(b, 6, 3, error=33)
        self.lock(a, 3, 3, unlock=True, error=33)
        self.lock(a, 3, 4, unlock=True)
        self.lock(a, 0xfffffff0, 17, error=33)
        self.lock(a, 0, 0, error=33)
        self.lock(a, 3, 4)
        self.put(self.sfts, a, 2); self.call(6, di=a)
        self.seek(b, 3); self.call(8, di=b, cx=1, error=33)
        self.call(6, di=a)
        self.call(8, di=b, cx=1)
        self.call(6, di=b)

    def test_dos3_lock_stack_abi_and_invalid_dos4_requests(self):
        a = self.opened(mode=0x42)
        self.call(0x0a, di=a, cx=2, error=1)
        self.call(0x0a, di=a, cx=1, bx=2, error=1)
        C.c_ubyte.in_dll(self.lib, 'dos_major').value = 3
        self.call(0x0a, di=a, cx=0, dx=100, si=1, param=2)
        self.call(0x0b, di=a, cx=0, dx=100, si=1, param=3, error=33)
        self.call(0x0b, di=a, cx=0, dx=100, si=1, param=2)
        self.call(6, di=a)

    def test_directory_attributes_rename_delete_and_cwd_interlock(self):
        self.path('S:\\NEWDIR'); self.call(3)
        off = self.created('S:\\NEWDIR\\CHILD.BIN'); self.write(off, b'CHILD')
        self.path('S:\\NEWDIR\\CHILD.BIN'); self.call(0x13, error=32)
        self.call(6, di=off)
        self.path('S:\\NEWDIR'); self.call(1, error=5)
        self.path('S:\\NEWDIR\\CHILD.BIN')
        target=b'S:\\MOVED.BIN\0'; self.sda[0x11e:0x11e+len(target)] = target
        self.call(0x11)
        self.assertEqual(self.content('MOVED.BIN'), b'CHILD')
        self.path('S:\\MOVED.BIN'); self.call(0x0e, param=1)
        self.assertEqual(self.call(0x0f).ax, 1)
        self.call(0x13, error=5); self.call(0x0e, param=32); self.call(0x13)
        self.cds[:10] = b'S:\\NEWDIR\0'
        self.path('S:\\NEWDIR'); self.call(1, error=16)
        self.cds[:4] = b'S:\\\0'; self.call(1)
        self.assertEqual(self.lib.media_unmount(), 0)
        self.clean()

    def test_set_file_timestamp_via_sft_commit_persists(self):
        off = self.created()
        self.write(off, b'TIME')
        self.put(self.sfts, off+13, 0x7441); self.put(self.sfts, off+15, 0x5821)
        self.call(7, di=off)
        self.call(6, di=off)
        off = self.opened(name='S:\\NEW.BIN')
        self.assertEqual((self.get(self.sfts, off+13), self.get(self.sfts, off+15)),
                         (0x7441, 0x5821))
        self.call(6, di=off); self.clean()

    def test_disk_full_returns_short_write_and_published_prefix(self):
        off = self.created()
        with self.image.open('r+b') as disk:
            for base in (2048+32, 2048+32+547):
                disk.seek(base*512+2*4)
                disk.write((0x0fffffff).to_bytes(4, 'little')*70000)
                disk.seek(base*512+1600*4); disk.write(bytes(4))
        self.lib.fs_invalidate()
        self.assertEqual(self.write(off, b'X'*1024).cx, 512)
        self.assertEqual(self.get(self.sfts, 17, 4), 512)
        self.call(6, di=off)
        self.assertEqual(self.content('NEW.BIN'), b'X'*512)

    def test_persistent_write_fault_offlines_preserves_diagnostics_and_closes(self):
        off = self.created()
        self.lib.rw_host_repeat(8, 1)
        self.assertEqual(self.write(off, b'DATA', error=29).cx, 0)
        self.assertEqual(C.c_ubyte.in_dll(self.lib, 'media_online').value, 0)
        before = C.c_uint.in_dll(self.lib, 'rw_host_writes').value
        self.call(9, di=off, cx=1, error=21)
        self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_writes').value, before)
        self.assertEqual(self.lib.media_mount(), 5)
        self.call(6, di=off)
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=4, cx=40, es=4)
        self.assertEqual(self.get(self.data, 18), 105)  # exact readback mismatch
        self.assertEqual(self.get(self.data, 28), 3)  # bounded attempts
        self.assertNotEqual(self.get(self.data, 30), 0)  # poisoned

    def test_writable_search_attributes_controls_and_flush_chaining(self):
        self.first(8192, 'S:\\README.TXT')
        self.assertEqual(self.data[8192+32], 32)
        r = self.call(0, ax=0xd74f)
        self.assertEqual(r.bp, 3)
        r = self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=5)
        self.assertEqual((r.bx, r.cx, r.dx), (1, 3, 1))
        r = self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=7)
        self.assertEqual((r.ax, r.bx, r.cx), (0, 2048, 2048))
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=4, cx=39, error=1)
        off = self.created(); self.write(off, b'FLUSH')
        self.call(0x20, handled=False); self.clean(); self.call(6, di=off)
        r = self.call(0x0c, es=2)
        self.assertGreater(r.dx, 0)

    def test_wildcard_delete_across_grown_directory_preserves_other_files(self):
        for i in range(25):
            off = self.created(f'S:\\D{i:02}.BIN')
            self.write(off, b'PAYLOAD'); self.call(6, di=off)
        self.path('S:\\D???????.BIN'); self.call(0x13)
        self.assertEqual(self.content('README.TXT'), TEXT)
        self.path('S:\\D*.BIN'); self.call(0x13, error=2)
        self.assertEqual(self.lib.media_unmount(), 0)
        self.clean()

    def test_handle_and_lock_capacity_refuse_without_untracked_mutations(self):
        handles = [self.opened(i, mode=0x42) for i in range(16)]
        before = self.image.read_bytes()
        self.path('S:\\UNTRACK.BIN'); self.call(0x17, di=1024, error=4)
        self.assertEqual(self.image.read_bytes(), before)
        for i in range(16): self.lock(handles[0], i*10, 3)
        self.lock(handles[0], 1000, 3, error=36)
        self.call(6, di=handles[0])
        self.lock(handles[1], 1000, 3)
        for off in handles[1:]: self.call(6, di=off)

    def test_readonly_variant_of_writable_build_never_writes(self):
        self.assertEqual(self.lib.media_unmount(), 0)
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 0
        self.assertEqual(self.lib.media_mount(), 0)
        before = self.image.read_bytes()
        off = self.opened()
        self.assertEqual(self.call(8, di=off, cx=100).cx, len(TEXT))
        self.write(off, b'X', error=5); self.call(6, di=off)
        for fn in (1, 3, 0x0e, 0x11, 0x13, 0x17):
            self.path('S:\\README.TXT'); self.call(fn, error=5)
        self.assertEqual(self.image.read_bytes(), before)

    def test_card_removed_on_close_reports_failure_but_releases_reference(self):
        off = self.created(); self.write(off, b'COMMITTED DATA')
        self.lib.rw_host_replace.argtypes = [C.c_char_p]
        self.assertEqual(self.lib.rw_host_replace(None), 0)
        self.call(6, di=off, error=21)
        self.assertEqual(self.get(self.sfts, off), 0)
        self.assertEqual(C.c_ubyte.in_dll(self.lib, 'media_online').value, 0)
        self.assertEqual(self.lib.media_unmount(), 0)

    def test_crc_read_failure_returns_completed_prefix_and_actual_lba(self):
        off = self.opened(name='S:\\BIG.BIN')
        f = fs.File()
        self.assertEqual(self.lib.rw_lookup(b'S:\\BIG.BIN', C.byref(f)), 0)
        next_cluster = self.lib.rw_fat(f.first)
        failed_lba = self.layout['data']+next_cluster-2
        self.lib.rw_host_config(10, failed_lba)
        self.assertEqual(self.call(8, di=off, cx=1024, error=30).cx, 512)
        self.assertEqual(self.get(self.sfts, off+21, 4), 512)
        self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=4, cx=40, es=4, di=4096)
        self.assertEqual(self.get(self.data, 4096, 4), failed_lba)
        self.assertEqual(self.get(self.data, 4096+16), 102)
        r = self.call(0, ax=0xd74f, bx=0x4f54, dx=0x524f, si=6)
        self.assertEqual((r.ax, r.bx), (0x1108, 30))
        self.call(6, di=off)


if __name__ == '__main__':
    unittest.main(verbosity=2)
