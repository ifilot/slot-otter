"""FAT16 correctness through the production writer and independent DOS tools."""
import ctypes as C
import struct
import subprocess
import unittest
import test_rw_fs as common
from fat16_fixture import prepare
from fixture import entry, BIG, TEXT
from test_fs import FileCursor

ROOT=0xffffffff


class Fat16Tests(unittest.TestCase):
    library_name="fat16-rwfs"
    @classmethod
    def setUpClass(cls):
        common.ResidentFilesystemTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):
        common.ResidentFilesystemTests.tearDownClass.__func__(cls)
    error=common.ResidentFilesystemTests.error
    lookup=common.ResidentFilesystemTests.lookup
    def content(self,path):
        self.assertEqual(self.lib.rw_flush(),0,self.error())
        return common.ResidentFilesystemTests.content(self,path)
    finish=common.ResidentFilesystemTests.finish
    def setUp(self):
        self.image=self.work/'fat16.img'
        self.layout=prepare(self.image,resident=True)
        C.c_ubyte.in_dll(self.lib,'fs_required').value=0
        C.c_ubyte.in_dll(self.lib,'rw_skip_fat_check').value=0
        C.c_int.in_dll(self.lib,'sd_write_enabled').value=1
        C.c_int.in_dll(self.lib,'sd_verify_writes').value=1
        self.open()
    def open(self):
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.assertEqual(self.lib.sd_init(),0)
        self.assertEqual(self.lib.rw_mount(),0,self.error())
    def tearDown(self):
        self.lib.rw_host_close()
        C.c_ubyte.in_dll(self.lib,'fs_required').value=0
    def create_file(self,name='NEW.BIN',parent=ROOT):
        f=common.File()
        self.assertEqual(self.lib.rw_create(parent,name.encode(),C.byref(f)),0,self.error())
        return f
    def disk_write(self,offset,value):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:disk.seek(offset);disk.write(value)
        self.open()
    def test_read_fixtures_and_fixed_root_parent(self):
        for name,data in [('README.TXT',TEXT),('SUBDIR/INNER.TXT',TEXT),('BIG.BIN',BIG),('HIGH.TXT',b'HIGH\n')]:
            f=self.lookup(name.replace('/','\\'))
            buf=C.create_string_buffer(len(data));done=C.c_uint16()
            # Use bounded chunks; fs_read's DOS count is 16 bits.
            actual=bytearray();cursor=FileCursor(f.first,f.first,0)
            for offset in range(0,len(data),4096):
                n=min(4096,len(data)-offset)
                self.assertEqual(self.lib.fs_read(C.byref(cursor),offset,buf,n,C.byref(done)),0)
                actual+=buf.raw[:done.value]
            self.assertEqual(actual,data)
        self.assertEqual(self.lookup('SUBDIR\\..\\README.TXT').parent,ROOT)
        self.finish()
    def test_create_append_overwrite_resize_move_delete(self):
        d=common.File();self.assertEqual(self.lib.rw_mkdir(ROOT,b'NEWDIR',C.byref(d)),0,self.error())
        f=self.create_file();payload=bytes(i%251 for i in range(40000))
        self.assertEqual(self.lib.rw_append(C.byref(f),payload,len(payload)),0,self.error())
        self.assertEqual(self.lib.rw_overwrite(C.byref(f),16380,b'abcdefgh',8),0)
        expected=payload[:16380]+b'abcdefgh'+payload[16388:]
        self.assertEqual(self.content('NEW.BIN'),expected)
        self.assertEqual(self.lib.rw_resize(C.byref(f),50000),0,self.error())
        self.assertEqual(self.content('NEW.BIN'),expected+bytes(10000))
        self.assertEqual(self.lib.rw_truncate(C.byref(f),17000),0,self.error())
        self.assertEqual(self.lib.rw_rename(C.byref(f),b'NEWDIR\\MOVED.BIN'),0,self.error())
        self.assertEqual(self.content('NEWDIR/MOVED.BIN'),expected[:17000])
        self.assertEqual(self.lib.rw_rename(C.byref(f),b'BACK.BIN'),0,self.error())
        self.assertEqual(self.lib.rw_delete(C.byref(f)),0,self.error())
        self.assertEqual(self.lib.rw_rmdir(C.byref(d)),0,self.error())
        self.finish()
    def test_fat16_reserved_directory_high_word_is_preserved(self):
        f=self.lookup('README.TXT')
        self.disk_write(f.lba*512+f.offset+20,b'\x34\x12')
        f=self.lookup('README.TXT');self.assertEqual(f.first,4)
        self.assertEqual(self.lib.rw_append(C.byref(f),b'X',1),0,self.error())
        with self.image.open('rb') as disk:
            disk.seek(f.lba*512+f.offset+20);self.assertEqual(disk.read(2),b'\x34\x12')
        self.assertEqual(self.content('README.TXT'),TEXT+b'X')
        self.finish()
    def test_root_full_fails_without_allocating_then_reuses_deleted(self):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:
            disk.seek(self.layout['root_lba']*512)
            disk.write(b''.join(entry('F%07d.TXT'%i,32) for i in range(512)))
        self.open();before=self.image.read_bytes()
        f=common.File();self.assertEqual(self.lib.rw_create(ROOT,b'FULL.TXT',C.byref(f)),-1)
        self.assertEqual(self.error(),39);self.assertEqual(self.image.read_bytes(),before)
        self.disk_write(self.layout['root_lba']*512+511*32,b'\xe5')
        f=self.create_file('REUSE.TXT');self.assertEqual(f.offset,480)
        self.assertEqual(f.lba,self.layout['root_lba']+31)
        self.assertEqual(self.lib.rw_append(C.byref(f),b'last slot',9),0,self.error())
        self.assertEqual(self.content('REUSE.TXT'),b'last slot')
    def test_last_root_end_marker_never_writes_beyond_root(self):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:
            disk.seek(self.layout['root_lba']*512)
            disk.write(b''.join(entry('F%07d.TXT'%i,32) for i in range(511))+bytes(32))
            disk.seek(self.layout['data']*512);disk.write(b'untouched'+bytes(503))
        self.open();self.create_file('LAST.TXT')
        with self.image.open('rb') as disk:
            disk.seek(self.layout['data']*512);self.assertEqual(disk.read(9),b'untouched')
        self.assertEqual(self.lib.rw_flush(),0)
    def test_clean_flags_use_fat16_bits_and_keep_mirrors(self):
        self.create_file()
        with self.image.open('rb') as disk:
            disk.seek((self.layout['start']+1)*512+2)
            self.assertEqual(struct.unpack('<H',disk.read(2))[0],0x7fff)
        self.finish()
        with self.image.open('rb') as disk:
            disk.seek((self.layout['start']+1)*512+2)
            self.assertEqual(struct.unpack('<H',disk.read(2))[0],0xffff)
    def test_dirty_and_error_flag_reject_mount_without_writes(self):
        for flags in (0x7fff,0xbfff):
            self.lib.rw_host_close()
            with self.image.open('r+b') as disk:
                for lba in (self.layout['start']+1,self.layout['start']+1+self.layout['fatsz']):
                    disk.seek(lba*512+2);disk.write(struct.pack('<H',flags))
            self.lib.rw_host_open(str(self.image).encode(),3);self.lib.sd_init()
            before=C.c_uint.in_dll(self.lib,'rw_host_writes').value
            self.assertEqual(self.lib.rw_mount(),-1);self.assertEqual(self.error(),13)
            self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,before)
    def test_format_restrictions_and_card_format_changes(self):
        for bits,ok in ((16,True),(32,False),(0,True)):
            C.c_ubyte.in_dll(self.lib,'fs_required').value=bits
            self.assertEqual(self.lib.rw_mount(),0 if ok else -1)
            if not ok:self.assertEqual(self.error(),13)
        self.lib.rw_host_close();common.builder.prepare(self.image)
        self.lib.rw_host_open(str(self.image).encode(),3);self.lib.sd_init()
        C.c_ubyte.in_dll(self.lib,'fs_required').value=16
        self.assertEqual(self.lib.rw_mount(),-1)
        C.c_ubyte.in_dll(self.lib,'fs_required').value=32
        self.assertEqual(self.lib.rw_mount(),0,self.error())
    def test_superfloppy_and_total16_geometry(self):
        self.lib.rw_host_close()
        self.layout=prepare(self.image,spc=4,total_sectors=32768,partitioned=False)
        self.open();f=self.create_file();self.assertEqual(self.lib.rw_append(C.byref(f),b'DATA',4),0)
        self.assertEqual(self.lib.rw_flush(),0)
        self.assertEqual(subprocess.check_output(['mtype','-i',str(self.image),'::NEW.BIN']),b'DATA')
    def test_free_count_is_physical_cluster_count(self):
        count=C.c_uint32();self.assertEqual(self.lib.rw_free_space(C.byref(count)),0)
        with self.image.open('rb') as disk:
            disk.seek((self.layout['start']+1)*512);fat=disk.read(self.layout['fatsz']*512)
        expected=sum(struct.unpack_from('<H',fat,c*2)[0]==0 for c in range(2,self.layout['clusters']+2))
        self.assertEqual(count.value,expected)
        f=self.create_file();self.lib.rw_append(C.byref(f),b'X',1)
        self.assertEqual(self.lib.rw_free_space(C.byref(count)),0);self.assertEqual(count.value,expected-1)
        self.finish()

    def test_reserved_bad_free_and_cyclic_links_refuse_writes(self):
        for value in (0,1,0xfff0,0xfff7,100):
            self.lib.rw_host_close();self.layout=prepare(self.image)
            with self.image.open('r+b') as disk:
                for base in (self.layout['start']+1,self.layout['start']+1+self.layout['fatsz']):
                    disk.seek(base*512+200);disk.write(struct.pack('<H',value))
            self.open();f=self.lookup('BIG.BIN')
            before=C.c_uint.in_dll(self.lib,'rw_host_writes').value
            self.assertEqual(self.lib.rw_append(C.byref(f),b'X',1),-1)
            self.assertEqual(self.error(),13)
            self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,before)

    def test_removal_stops_fixed_root_create_without_writes(self):
        self.lib.rw_host_replace.argtypes=[C.c_char_p]
        self.assertEqual(self.lib.rw_host_replace(b''),0)
        before=C.c_uint.in_dll(self.lib,'rw_host_writes').value
        f=common.File();self.assertEqual(self.lib.rw_create(ROOT,b'ABSENT.BIN',C.byref(f)),-1)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,before)

    def test_forged_fixed_root_slot_and_reserved_sectors_are_rejected(self):
        for lba,offset in ((self.layout['root_lba']-1,0),(self.layout['start'],0),
                           (self.layout['root_lba'],1),(self.layout['root_lba'],512)):
            f=self.lookup('README.TXT');f.lba=lba;f.offset=offset
            before=C.c_uint.in_dll(self.lib,'rw_host_writes').value
            self.assertEqual(self.lib.rw_append(C.byref(f),b'X',1),-1)
            self.assertEqual(self.error(),13)
            self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,before)

    def test_invalid_bpb_rejected_before_writes(self):
        for offset,value in ((17,b'\0\0'),(17,b'\x01\x02'),(22,b'\x01\0'),
                             (13,b'\x03'),(19,b'\x10\0')):
            self.lib.rw_host_close();self.layout=prepare(self.image)
            with self.image.open('r+b') as disk:
                disk.seek(self.layout['start']*512+offset);disk.write(value)
            self.lib.rw_host_open(str(self.image).encode(),3);self.lib.sd_init()
            self.assertEqual(self.lib.rw_mount(),-1)
            self.assertEqual(self.error(),13)
            self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)

    def test_fixed_root_mirror_mismatch_and_fast_mount_safety(self):
        self.lib.rw_host_close()
        with self.image.open('r+b') as disk:
            disk.seek((self.layout['start']+1+self.layout['fatsz'])*512+4)
            disk.write(b'\x01')
        self.lib.rw_host_open(str(self.image).encode(),3);self.lib.sd_init()
        self.assertEqual(self.lib.rw_mount(),-1)
        C.c_ubyte.in_dll(self.lib,'rw_skip_fat_check').value=1
        self.assertEqual(self.lib.rw_mount(),-1)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,0)

    def test_two_byte_fat_store_preserves_neighbor_entry(self):
        f=self.create_file()
        with self.image.open('rb') as disk:
            disk.seek((self.layout['start']+1)*512)
            original=disk.read(self.layout['fatsz']*512)
        self.assertEqual(self.lib.rw_append(C.byref(f),b'X',1),0,self.error())
        self.assertEqual(self.lib.rw_flush(),0)
        expected=bytearray(original)
        struct.pack_into('<H',expected,2,struct.unpack_from('<H',expected,2)[0]|0x8000)
        struct.pack_into('<H',expected,f.first*2,0xffff)
        with self.image.open('rb') as disk:
            for lba in (self.layout['start']+1,self.layout['start']+1+self.layout['fatsz']):
                disk.seek(lba*512)
                self.assertEqual(disk.read(len(expected)),expected)
        self.finish()
