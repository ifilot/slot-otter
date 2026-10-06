"""Resident mutations through CRC/retry transport and independent FAT tooling."""
import ctypes as C
import importlib.util
import pathlib
import struct
import subprocess
import tempfile
import unittest
from fixture import create, TEXT, BIG
from support import library, ROOT

spec=importlib.util.spec_from_file_location('resident_fixture_build',ROOT/'write/build.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class File(C.Structure):
    _fields_ = [(n, C.c_uint32) for n in ('first', 'last', 'size', 'lba', 'parent')] + [
        (n, C.c_uint16) for n in ('offset', 'time', 'date')] + [
        (n, C.c_uint8) for n in ('directory', 'attr')]


class ResidentFilesystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='otter-rwfs-')
        cls.work = pathlib.Path(cls.tmp.name)
        cls.lib = C.CDLL(str(library(cls.work, 'rwfs', [
            'SDRW.C', 'RWFS.C', 'FAT32.C', 'tests/HOSTRW.C',
            'emulation/slot_model.c'], ['-std=c99'])))
        cls.lib.rw_host_open.argtypes = [C.c_char_p, C.c_uint]
        cls.lib.rw_lookup.argtypes = [C.c_char_p, C.POINTER(File)]
        for name in ('rw_create', 'rw_mkdir'):
            getattr(cls.lib, name).argtypes = [C.c_uint32, C.c_char_p, C.POINTER(File)]
        cls.lib.rw_append.argtypes = [C.POINTER(File), C.c_void_p, C.c_uint16]
        cls.lib.rw_overwrite.argtypes = [C.POINTER(File), C.c_uint32, C.c_void_p, C.c_uint16]
        cls.lib.rw_truncate.argtypes = [C.POINTER(File), C.c_uint32]
        cls.lib.rw_metadata.argtypes = [C.POINTER(File), C.c_uint8, C.c_uint16, C.c_uint16]
        cls.lib.rw_write.argtypes = [C.POINTER(File), C.c_uint32, C.c_void_p,
                                     C.c_uint16, C.POINTER(C.c_uint16)]
        cls.lib.rw_resize.argtypes = [C.POINTER(File), C.c_uint32]
        cls.lib.rw_rename.argtypes = [C.POINTER(File), C.c_char_p]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.image = self.work/'card.img'
        self.layout = builder.prepare(self.image)
        C.c_int.in_dll(self.lib, 'sd_write_enabled').value = 1
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), 3), 0)
        self.assertEqual(self.lib.sd_init(), 0)
        self.assertEqual(self.lib.rw_mount(), 0)

    def tearDown(self):
        self.lib.rw_host_close()

    def error(self):
        return C.c_uint16.in_dll(self.lib, 'fs_error').value

    def lookup(self, path):
        f=File()
        self.assertEqual(self.lib.rw_lookup(path.encode(), C.byref(f)), 0, (path, self.error()))
        return f

    def create_file(self, name='NEW.BIN', parent=2):
        f=File()
        self.assertEqual(self.lib.rw_create(parent, name.encode(), C.byref(f)), 0, self.error())
        return f

    def finish(self):
        self.assertEqual(self.lib.rw_flush(), 0, self.error())
        partition=self.work/'partition.img'
        with self.image.open('rb') as disk:
            disk.seek(2048*512)
            partition.write_bytes(disk.read())
        result=subprocess.run(['fsck.fat', '-n', str(partition)],capture_output=True,text=True)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)

    def content(self, path):
        return subprocess.check_output(['mtype','-i',str(self.image)+'@@1048576','::'+path])

    def test_mount_and_lookup_do_not_write(self):
        f=self.lookup('README.TXT')
        self.assertEqual(f.size,len(TEXT))
        self.assertEqual((f.lba,f.offset),(self.layout['data'],32))
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)
        self.assertEqual(self.lib.rw_flush(),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)

    def test_clean_preflight_read_errors_remain_transport_errors(self):
        before=self.image.read_bytes()
        f=File()
        self.lib.rw_host_config(10,2048+32)
        self.assertNotEqual(self.lib.rw_create(2,b'NEW.BIN',C.byref(f)),0)
        self.assertEqual(self.error(),30)
        self.assertEqual(self.image.read_bytes(),before)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)

    def test_rmdir_scan_preserves_read_error(self):
        d=File()
        self.assertEqual(self.lib.rw_mkdir(2,b'EMPTY',C.byref(d)),0)
        self.assertEqual(self.lib.rw_flush(),0)
        before=self.image.read_bytes()
        self.lib.rw_host_config(10,self.layout['data']+d.first-2)
        self.assertNotEqual(self.lib.rw_rmdir(C.byref(d)),0)
        self.assertEqual(self.error(),30)
        self.assertEqual(self.image.read_bytes(),before)

    def test_new_root_file_roundtrip_and_originals_preserved(self):
        before=self.image.read_bytes()
        f=self.create_file()
        payload=bytes(i%251 for i in range(1025))
        self.assertEqual(self.lib.rw_append(C.byref(f),payload,len(payload)),0,self.error())
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),payload)
        self.assertEqual(self.content('README.TXT'),TEXT)
        self.assertEqual(self.content('BIG.BIN'),BIG)
        after=self.image.read_bytes()
        self.assertEqual(after[:2048*512],before[:2048*512])
        for sector in (2048,2054):
            self.assertEqual(after[sector*512:(sector+1)*512],before[sector*512:(sector+1)*512])

    def test_append_existing_file_and_partial_sector_overwrite(self):
        f=self.lookup('README.TXT')
        self.assertEqual(self.lib.rw_append(C.byref(f),b'NEXT',4),0,self.error())
        self.assertEqual(self.lib.rw_overwrite(C.byref(f),2,b'CHANGED',7),0,self.error())
        self.finish()
        self.assertEqual(self.content('README.TXT'),TEXT[:2]+b'CHANGED'+TEXT[9:]+b'NEXT')

    def test_truncate_existing_fragmented_file_then_append(self):
        f=self.lookup('BIG.BIN')
        self.assertEqual(self.lib.rw_truncate(C.byref(f),513),0,self.error())
        self.assertEqual(self.lib.rw_append(C.byref(f),b'APPEND',6),0,self.error())
        self.finish()
        self.assertEqual(self.content('BIG.BIN'),BIG[:513]+b'APPEND')

    def test_delete_existing_file_frees_chain(self):
        f=self.lookup('HIGH.TXT')
        self.assertEqual(self.lib.rw_delete(C.byref(f)),0,self.error())
        self.finish()
        self.assertNotEqual(self.lib.rw_lookup(b'HIGH.TXT',C.byref(f)),0)
        self.assertEqual(self.error(),2)

    def test_nested_directories_and_rmdir_interlock(self):
        d=File()
        self.assertEqual(self.lib.rw_mkdir(2,b'NEWDIR',C.byref(d)),0,self.error())
        f=self.create_file('CHILD.BIN',d.first)
        self.assertEqual(self.lib.rw_append(C.byref(f),b'DATA',4),0)
        self.assertNotEqual(self.lib.rw_rmdir(C.byref(d)),0)
        self.assertEqual(self.error(),5)
        self.assertEqual(self.lib.rw_delete(C.byref(f)),0)
        self.assertEqual(self.lib.rw_rmdir(C.byref(d)),0)
        self.finish()

    def test_create_duplicate_and_invalid_names_do_not_mutate(self):
        f=File()
        before=self.image.read_bytes()
        for name, error in ((b'README.TXT',80),(b'..',13),(b'*.TXT',3)):
            self.assertNotEqual(self.lib.rw_create(2,name,C.byref(f)),0)
            self.assertEqual(self.error(),error)
        self.assertEqual(self.image.read_bytes(),before)


    def test_readonly_attribute_enforced_and_timestamp_persists(self):
        f=self.lookup('README.TXT')
        self.assertEqual(self.lib.rw_metadata(C.byref(f),0x21,0x7440,0x5d45),0,self.error())
        self.assertNotEqual(self.lib.rw_append(C.byref(f),b'X',1),0)
        self.assertEqual(self.error(),5)
        self.assertNotEqual(self.lib.rw_delete(C.byref(f)),0)
        self.assertEqual(self.error(),5)
        self.finish()
        f=self.lookup('README.TXT')
        self.assertEqual((f.attr,f.time,f.date),(0x21,0x7440,0x5d45))
        self.assertEqual(self.content('README.TXT'),TEXT)

    def test_directory_growth(self):
        for i in range(30):
            self.create_file(f'F{i:02}.BIN')
        self.finish()
        for i in range(30):
            self.lookup(f'F{i:02}.BIN')

    def test_reopen_appends_beyond_cluster_boundary(self):
        f=self.create_file()
        self.assertEqual(self.lib.rw_append(C.byref(f),b'A'*512,512),0)
        f=self.lookup('NEW.BIN')
        self.assertEqual(f.last,0)
        self.assertEqual(self.lib.rw_append(C.byref(f),b'B'*513,513),0,self.error())
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),b'A'*512+b'B'*513)

    def test_mirror_mismatch_refuses_mount_without_writes(self):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:
            disk.seek((2048+32+547)*512+100)
            disk.write(b'BAD!')
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertNotEqual(self.lib.rw_mount(),0)
        self.assertEqual(self.error(),13)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)

    def test_mirror_inconsistency_during_dirty_session_stops_later_mutations(self):
        self.create_file()
        with self.image.open('r+b') as disk:
            disk.seek((2048+32+547)*512+100)
            disk.write(b'BAD!')
        self.assertNotEqual(self.lib.rw_flush(), 0)
        self.assertEqual(self.error(), 13)
        count = C.c_uint.in_dll(self.lib, 'rw_host_writes').value
        self.assertNotEqual(self.lib.rw_create(2, b'AGAIN.BIN', C.byref(File())), 0)
        self.assertEqual(self.error(), 21)
        self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_writes').value, count)

    def test_backup_boot_geometry_mismatch_refuses_mount_before_writes(self):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:
            disk.seek(2054*512+13); disk.write(b'\x08')
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(), 3), 0)
        self.assertEqual(self.lib.sd_init(), 0)
        self.assertNotEqual(self.lib.rw_mount(), 0)
        self.assertEqual(self.error(), 13)
        self.assertEqual(C.c_uint.in_dll(self.lib, 'rw_host_writes').value, 0)

    def test_free_count_tracks_allocation_and_release(self):
        free=C.c_uint32()
        self.assertEqual(self.lib.rw_free_space(C.byref(free)),0)
        original=free.value
        f=self.create_file()
        self.assertEqual(self.lib.rw_append(C.byref(f),b'X'*1025,1025),0)
        self.assertEqual(self.lib.rw_free_space(C.byref(free)),0)
        self.assertEqual(free.value,original-3)
        self.assertEqual(self.lib.rw_delete(C.byref(f)),0)
        self.assertEqual(self.lib.rw_free_space(C.byref(free)),0)
        self.assertEqual(free.value,original)
        self.finish()

    def test_eight_sector_clusters(self):
        self.lib.rw_host_close()
        self.layout=builder.prepare(self.image,spc=8)
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.rw_mount(),0)
        f=self.create_file()
        data=bytes(i%251 for i in range(8193))
        self.assertEqual(self.lib.rw_append(C.byref(f),data,len(data)),0,self.error())
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),data)

    def test_active_fat_leaves_inactive_copy_untouched(self):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:
            for sector in (2048,2054):
                disk.seek(sector*512+40)
                disk.write(struct.pack('<H',0x81))
            disk.seek((2048+32)*512)
            inactive=disk.read(547*512)
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.rw_mount(),0)
        f=self.create_file()
        self.assertEqual(self.lib.rw_append(C.byref(f),b'ACTIVE',6),0,self.error())
        self.assertEqual(self.lib.rw_flush(),0,self.error())
        with self.image.open('rb') as disk:
            disk.seek((2048+32)*512)
            self.assertEqual(disk.read(547*512),inactive)
        self.assertEqual(self.content('NEW.BIN'),b'ACTIVE')

    def test_superfloppy_boot_sector_stays_intact(self):
        self.lib.rw_host_close()
        with self.image.open('rb') as disk:
            disk.seek(2048*512)
            contents=bytearray(disk.read(self.layout['total']*512))
        for sector in (0,6):
            struct.pack_into('<I',contents,sector*512+28,0)
        self.image.write_bytes(contents)
        boot=bytes(contents[:512])
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.rw_mount(),0)
        f=self.create_file()
        self.assertEqual(self.lib.rw_append(C.byref(f),b'SUPER',5),0,self.error())
        self.assertEqual(self.lib.rw_flush(),0,self.error())
        self.assertEqual(self.image.read_bytes()[:512],boot)
        self.assertEqual(subprocess.check_output(['mtype','-i',str(self.image),'::NEW.BIN']),b'SUPER')
        result=subprocess.run(['fsck.fat','-n',str(self.image)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_transient_metadata_mismatch_retries_same_sector_and_finishes(self):
        self.lib.rw_host_config(8,2)
        f=self.create_file()
        self.assertEqual(self.lib.rw_append(C.byref(f),b'RETRY',5),0,self.error())
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),b'RETRY')

    def test_persistent_metadata_failure_stops_subsequent_mutations(self):
        self.lib.rw_host_repeat(8,1)
        f=File()
        self.assertNotEqual(self.lib.rw_create(2,b'FAIL.BIN',C.byref(f)),0)
        self.assertEqual(self.error(),29)
        count=C.c_uint.in_dll(self.lib,'rw_host_writes').value
        self.assertEqual(count,3)
        self.assertNotEqual(self.lib.rw_create(2,b'AGAIN.BIN',C.byref(f)),0)
        self.assertNotEqual(self.lib.rw_flush(),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,count)

    def set_fat(self, cluster, value):
        with self.image.open('r+b') as disk:
            for base in (2048+32,2048+32+547):
                disk.seek(base*512+cluster*4)
                disk.write(struct.pack('<I',value))
        self.lib.fs_invalidate()

    def write(self, f, pos, data, expected=0):
        done=C.c_uint16(0xaaaa)
        result=self.lib.rw_write(C.byref(f),pos,data,len(data),C.byref(done))
        self.assertEqual(result,expected,self.error())
        return done.value

    def test_write_past_eof_zeros_gap_and_overwrite_append_combination(self):
        f=self.create_file()
        self.assertEqual(self.write(f,0,b'FIRST'),5)
        self.assertEqual(self.write(f,1500,b'TAIL'),4)
        self.assertEqual(self.write(f,1502,b'OVERWRITE'),9)
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),b'FIRST'+bytes(1495)+b'TAOVERWRITE')

    def test_zero_length_write_truncates_and_extends_with_zeros(self):
        f=self.create_file()
        self.assertEqual(self.write(f,0,b'ORIGINAL'),8)
        self.assertEqual(self.write(f,3,b''),0)
        self.assertEqual(self.write(f,1025,b''),0)
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),b'ORI'+bytes(1022))
        self.assertEqual(self.write(f,0,b''),0)
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),b'')
        self.assertEqual(f.first,0)

    def test_max_dos_write_count_and_reopen(self):
        f=self.create_file()
        data=bytes(i%251 for i in range(65535))
        self.assertEqual(self.write(f,0,data),65535)
        f=self.lookup('NEW.BIN')
        self.assertEqual(self.write(f,65535,b'TAIL'),4)
        self.finish()
        self.assertEqual(self.content('NEW.BIN'),data+b'TAIL')

    def test_overflow_write_and_forged_directory_location_refuse_without_writes(self):
        f=self.lookup('README.TXT')
        before=self.image.read_bytes()
        self.assertEqual(self.write(f,0xffffffff,b'X',expected=-1),0)
        self.assertEqual(self.error(),13)
        for lba,offset in ((0,0),(2048,0),(f.lba,65535),(f.lba,1)):
            bad=File.from_buffer_copy(bytes(f)); bad.lba=lba; bad.offset=offset
            self.assertNotEqual(self.lib.rw_metadata(C.byref(bad),32,0,0),0)
            self.assertEqual(self.error(),5 if lba==0 else 13)
        self.assertEqual(self.image.read_bytes(),before)

        # An otherwise plausible directory record at an unaligned address
        # must never become a metadata write target.
        bad=File.from_buffer_copy(bytes(f))
        bad.lba=self.layout['data']+1600; bad.offset=1
        e=bytearray(32); e[:11]=b'FORGED  TXT'; e[11]=f.attr
        struct.pack_into('<H',e,20,f.first>>16)
        struct.pack_into('<H',e,26,f.first&65535)
        struct.pack_into('<I',e,28,f.size)
        with self.image.open('r+b') as disk:
            disk.seek(bad.lba*512+1); disk.write(e)
        before=self.image.read_bytes()
        self.assertNotEqual(self.lib.rw_metadata(C.byref(bad),32,0,0),0)
        self.assertEqual(self.error(),13)
        self.assertEqual(self.image.read_bytes(),before)

    def test_corrupt_and_short_chains_refuse_overwrite_before_mutation(self):
        f=self.lookup('BIG.BIN')
        for value in (0,f.first,0x0fffffff):
            with self.subTest(value=value):
                self.set_fat(f.first,value)
                before=self.image.read_bytes()
                self.assertNotEqual(self.lib.rw_overwrite(C.byref(f),0,b'X',1),0)
                self.assertEqual(self.error(),13)
                self.assertEqual(self.image.read_bytes(),before)

    def test_preallocated_empty_and_tail_clusters_are_reused(self):
        f=self.lookup('FRAG.BIN')
        before=C.c_uint32.in_dll(self.lib,'rw_allocated').value
        self.assertEqual(self.lib.rw_append(C.byref(f),b'X'*25,25),0,self.error())
        self.assertEqual(C.c_uint32.in_dll(self.lib,'rw_allocated').value,before+1)
        self.finish()
        self.assertEqual(self.content('FRAG.BIN'),bytes(i%251 for i in range(1000))+b'X'*25)
        f=self.create_file('EMPTY2.BIN')
        self.set_fat(1502,0x0fffffff)
        with self.image.open('r+b') as disk:
            disk.seek(f.lba*512+f.offset+26); disk.write(struct.pack('<H',1502))
        self.lib.fs_invalidate(); f=self.lookup('EMPTY2.BIN')
        before=C.c_uint32.in_dll(self.lib,'rw_allocated').value
        self.assertEqual(self.lib.rw_append(C.byref(f),b'EMPTY',5),0,self.error())
        self.assertEqual(f.first,1502)
        self.assertEqual(C.c_uint32.in_dll(self.lib,'rw_allocated').value,before)
        self.finish()

    def test_rename_same_directory_and_move_file_preserve_data(self):
        f=self.lookup('README.TXT')
        self.assertEqual(self.lib.rw_rename(C.byref(f),b'RENAMED.TXT'),0,self.error())
        self.assertNotEqual(self.lib.rw_lookup(b'README.TXT',C.byref(File())),0)
        self.assertEqual(self.lib.rw_rename(C.byref(f),b'SUBDIR\\MOVED.TXT'),0,self.error())
        self.assertEqual(f.parent,self.lookup('SUBDIR').first)
        self.finish()
        self.assertEqual(self.content('SUBDIR/MOVED.TXT'),TEXT)
        self.assertEqual(self.content('SUBDIR/INNER.TXT'),TEXT)

    def test_rename_duplicates_and_readonly_refused_without_mutation(self):
        f=self.lookup('README.TXT')
        before=self.image.read_bytes()
        self.assertEqual(self.lib.rw_rename(C.byref(f),b'readme.txt'),0)
        self.assertNotEqual(self.lib.rw_rename(C.byref(f),b'BIG.BIN'),0)
        self.assertEqual(self.error(),80)
        self.assertNotEqual(self.lib.rw_rename(C.byref(f),b'MISSING\\NEW.TXT'),0)
        self.assertEqual(self.error(),3)
        self.assertEqual(self.image.read_bytes(),before)
        self.assertEqual(self.lib.rw_metadata(C.byref(f),33,f.time,f.date),0)
        before=self.image.read_bytes()
        self.assertNotEqual(self.lib.rw_rename(C.byref(f),b'NO.TXT'),0)
        self.assertEqual(self.error(),5)
        self.assertEqual(self.image.read_bytes(),before)

    def test_move_directory_updates_parent_and_refuses_descendant(self):
        source=File(); target=File(); nested=File()
        self.assertEqual(self.lib.rw_mkdir(2,b'SOURCE',C.byref(source)),0)
        self.assertEqual(self.lib.rw_mkdir(2,b'TARGET',C.byref(target)),0)
        self.assertEqual(self.lib.rw_mkdir(source.first,b'NESTED',C.byref(nested)),0)
        before=self.image.read_bytes()
        self.assertNotEqual(self.lib.rw_rename(C.byref(source),b'SOURCE\\NESTED\\LOOP'),0)
        self.assertEqual(self.error(),5)
        self.assertEqual(self.image.read_bytes(),before)
        self.assertEqual(self.lib.rw_rename(C.byref(source),b'TARGET\\MOVED'),0,self.error())
        self.finish()
        self.assertEqual(self.lookup('TARGET\\MOVED\\..').first,target.first)
        self.lookup('TARGET\\MOVED\\NESTED')

    def test_partial_disk_full_publishes_only_completed_bytes(self):
        f=self.create_file()
        self.assertEqual(self.lib.rw_append(C.byref(f),b'X',1),0)
        with self.image.open('r+b') as disk:
            disk.seek((2048+32)*512); fat=bytearray(disk.read(547*512))
            for c in range(2,70002):
                if struct.unpack_from('<I',fat,c*4)[0]==0:
                    struct.pack_into('<I',fat,c*4,0x0ffffff7)
            for base in (2048+32,2048+32+547):
                disk.seek(base*512); disk.write(fat)
        self.lib.fs_invalidate()
        done=self.write(f,1,b'A'*512,expected=-1)
        self.assertEqual((done,f.size,self.error()),(511,512,39))
        self.assertEqual(self.lookup('NEW.BIN').size,512)
        self.assertEqual(self.lib.rw_flush(),0)
        self.assertEqual(self.content('NEW.BIN'),b'X'+b'A'*511)

    def root_entries(self):
        entries=[]
        cluster=2
        with self.image.open('rb') as disk:
            while cluster<0x0ffffff8:
                disk.seek((self.layout['data']+(cluster-2)*self.layout['spc'])*512)
                data=disk.read(self.layout['spc']*512)
                for off in range(0,len(data),32):
                    entries.append(((self.layout['data']+(cluster-2)*self.layout['spc'])*512+off,
                                    data[off:off+32]))
                disk.seek((2048+32)*512+cluster*4)
                cluster=struct.unpack('<I',disk.read(4))[0]&0x0fffffff
        return entries

    def install_long_name(self):
        local=self.work/'long.txt'; local.write_bytes(b'LONG NAME CONTENT')
        subprocess.run(['mcopy','-i',str(self.image)+'@@1048576',str(local),
                        '::Long filename for an alias.txt'],check=True)
        self.lib.fs_invalidate()
        entries=self.root_entries()
        for i,(offset,e) in enumerate(entries):
            if e[0] not in (0,229) and e[11]!=15 and e[:4]==b'LONG':
                name=e[:8].decode().rstrip() + '.' + e[8:11].decode().rstrip()
                positions=[]
                j=i-1
                while j>=0 and entries[j][1][11]==15 and entries[j][1][0]!=229:
                    positions.append(entries[j][0]); j-=1
                self.assertGreater(len(positions),0)
                return self.lookup(name),positions
        self.fail('mtools did not create a long name and short alias')

    def assert_lfn_erased(self, positions):
        with self.image.open('rb') as disk:
            for offset in positions:
                disk.seek(offset)
                self.assertEqual(disk.read(1),b'\xe5')

    def test_delete_short_alias_erases_associated_long_name_entries(self):
        f,positions=self.install_long_name()
        self.assertEqual(self.lib.rw_delete(C.byref(f)),0,self.error())
        self.assert_lfn_erased(positions)
        self.finish()

    def test_rename_short_alias_erases_associated_long_name_entries(self):
        f,positions=self.install_long_name()
        self.assertEqual(self.lib.rw_rename(C.byref(f),b'RENAMED.TXT'),0,self.error())
        self.assert_lfn_erased(positions)
        self.finish()
        self.assertEqual(self.content('RENAMED.TXT'),b'LONG NAME CONTENT')

    def test_create_at_end_marker_does_not_expose_stale_entries(self):
        d=File()
        self.assertEqual(self.lib.rw_mkdir(2,b'NEWDIR',C.byref(d)),0)
        with self.image.open('r+b') as disk:
            lba=self.layout['data']+d.first-2
            disk.seek(lba*512+96)
            stale=bytearray(32); stale[:11]=b'STALE   BIN'; stale[11]=32
            disk.write(stale)
        self.lib.fs_invalidate()
        f=self.create_file('FRESH.BIN',d.first)
        self.assertNotEqual(self.lib.rw_lookup(b'NEWDIR\\STALE.BIN',C.byref(File())),0)
        self.assertEqual(self.error(),2)
        self.finish()

    def test_dot_prefixed_non_dot_entry_blocks_rmdir(self):
        d=File()
        self.assertEqual(self.lib.rw_mkdir(2,b'NEWDIR',C.byref(d)),0)
        with self.image.open('r+b') as disk:
            disk.seek((self.layout['data']+d.first-2)*512+64)
            e=bytearray(32); e[:11]=b'.ILLEGAL   '; e[11]=32
            disk.write(e)
        self.lib.fs_invalidate()
        before=self.image.read_bytes()
        self.assertNotEqual(self.lib.rw_rmdir(C.byref(d)),0)
        self.assertEqual(self.error(),5)
        self.assertEqual(self.image.read_bytes(),before)

    def restart_fixture(self):
        self.lib.rw_host_close()
        self.layout=builder.prepare(self.image)
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.rw_mount(),0)

    def operation_with_flush(self):
        f=File()
        if self.lib.rw_create(2,b'NEW.BIN',C.byref(f)): return -1
        if self.lib.rw_append(C.byref(f),b'SECTOR',6): return -1
        return self.lib.rw_flush()

    def test_removal_at_every_write_stage_stops_all_following_mutations(self):
        # Includes dirty flags, both FSInfo copies, directory publication,
        # both allocation FAT copies, initialized data, content and clean flags.
        self.assertEqual(self.operation_with_flush(),0)
        stages=C.c_uint.in_dll(self.lib,'rw_host_writes').value
        self.assertGreaterEqual(stages,12)
        for stage in range(1,stages+1):
            with self.subTest(stage=stage):
                self.restart_fixture()
                self.lib.rw_host_config(7,stage)
                self.assertNotEqual(self.operation_with_flush(),0)
                before=C.c_uint.in_dll(self.lib,'rw_host_writes').value
                f=File()
                self.assertNotEqual(self.lib.rw_create(2,b'AGAIN.BIN',C.byref(f)),0)
                self.assertNotEqual(self.lib.rw_flush(),0)
                self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,before)

    def test_transient_mismatch_at_every_metadata_stage_preserves_consistency(self):
        self.assertEqual(self.operation_with_flush(),0)
        stages=C.c_uint.in_dll(self.lib,'rw_host_writes').value
        for stage in range(1,stages+1):
            with self.subTest(stage=stage):
                self.restart_fixture()
                self.lib.rw_host_config(8,stage)
                self.assertEqual(self.operation_with_flush(),0,self.error())
                self.assertEqual(self.content('NEW.BIN'),b'SECTOR')
                self.finish()

    def test_long_name_sequence_crossing_directory_fat_boundary(self):
        f,positions=self.install_long_name()
        self.assertEqual(len(positions),3)
        alias=self.image.read_bytes()[f.lba*512+f.offset:f.lba*512+f.offset+11]
        name=alias[:8].decode().rstrip()+'.'+alias[8:].decode().rstrip()
        with self.image.open('r+b') as disk:
            fragments=[]
            for offset in sorted(positions):
                disk.seek(offset); fragments.append(disk.read(32))
                disk.seek(offset); disk.write(b'\xe5')
            disk.seek(f.lba*512+f.offset); short=disk.read(32)
            disk.seek(f.lba*512+f.offset); disk.write(b'\xe5')
            # Make the old free slots ordinary empty files, so the LFN starts
            # at the last two entries of cluster 2 and continues in cluster 10.
            root=self.layout['data']*512
            for slot in range(8,14):
                e=bytearray(32); e[:11]=f'F{slot:02}     BIN'.encode(); e[11]=32
                disk.seek(root+slot*32); disk.write(e)
            second=(self.layout['data']+8)*512
            disk.seek(second); old=disk.read(128)
            disk.seek(second+64); disk.write(old+bytes(32))
            new_positions=[root+14*32,root+15*32,second]
            for offset,e in zip(new_positions,fragments):
                disk.seek(offset); disk.write(e)
            disk.seek(second+32); disk.write(short)
        self.lib.fs_invalidate(); f=self.lookup(name)
        self.assertEqual(self.lib.rw_delete(C.byref(f)),0,self.error())
        self.assert_lfn_erased(new_positions)
        self.finish()


if __name__=='__main__':
    unittest.main(verbosity=2)
