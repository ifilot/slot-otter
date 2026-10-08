"""Read traffic and cache coherence through actual DOS redirector callbacks."""
import ctypes as C
from pathlib import Path
import shutil
import tempfile
import unittest
import test_rw_redirector as common
import test_rw_fs as fs
from fat16_fixture import prepare
from support import ROOT


class ReadCacheCases:
    memory=common.WritableRedirectorTests.memory
    put=common.WritableRedirectorTests.put
    get=common.WritableRedirectorTests.get
    pointer=common.WritableRedirectorTests.pointer
    path=common.WritableRedirectorTests.path
    call=common.WritableRedirectorTests.call
    opened=common.WritableRedirectorTests.opened
    created=common.WritableRedirectorTests.created
    write=common.WritableRedirectorTests.write
    seek=common.WritableRedirectorTests.seek

    @classmethod
    def setUpClass(cls):
        # Count FAT lookups without adding instrumentation to resident code.
        cls.reader_tmp=tempfile.TemporaryDirectory(prefix='otter-read-walk-')
        cls.reader_source=str(Path(cls.reader_tmp.name)/'READFAT.C')
        text=(ROOT/'FAT32.C').read_text()
        assert text.count('U32 fs_fat_entry(U32 c) {')==1
        text=text.replace('U32 fs_fat_entry(U32 c) {','static U32 uncached_entry(U32 c) {')
        text+='\nU32 test_fat_calls;\nU32 fs_fat_entry(U32 c) {\n  ++test_fat_calls; return uncached_entry(c);\n}\n'
        Path(cls.reader_source).write_text(text)
        common.WritableRedirectorTests.setUpClass.__func__(cls)
        cls.lib.rw_lookup.argtypes=[C.c_char_p,C.POINTER(fs.File)]
        cls.lib.fs_fat_entry.argtypes=[C.c_uint32]
        cls.lib.fs_fat_entry.restype=C.c_uint32
        if hasattr(cls.lib,'fs_read_metadata'):
            cls.lib.fs_read_metadata.argtypes=[C.c_uint32,C.c_void_p]

    @classmethod
    def tearDownClass(cls):
        common.WritableRedirectorTests.tearDownClass.__func__(cls)
        cls.reader_tmp.cleanup()

    def setUp(self):
        self.image=self.work/'card.img'
        self.layout=(prepare(self.image) if self.bits==16 else fs.builder.prepare(self.image))
        self.lib.test_reset()
        if hasattr(self.lib,'rw_read_serial'):
            C.c_uint32.in_dll(self.lib,'rw_read_serial').value=1
        C.c_ubyte.in_dll(self.lib,'fs_required').value=0
        C.c_int.in_dll(self.lib,'sd_write_enabled').value=1
        C.c_int.in_dll(self.lib,'sd_verify_writes').value=1
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.sda,self.cds,self.sfts,self.data=[self.memory(n) for n in range(1,5)]
        self.put(self.sda,0x10,0x1234)
        self.assertEqual(self.lib.media_mount(),0)

    def tearDown(self):
        self.lib.rw_host_close()

    def read(self,off,count,expected,error=None):
        self.pointer();self.data[:count]=b'?'*count
        r=self.call(8,di=off,cx=count,error=error)
        self.assertEqual(bytes(self.data[:r.cx]),expected)
        return r

    def test_sequential_read_walk_and_metadata_budget(self):
        # FAT32 crosses seven FAT sectors; FAT16 exercises small writes inside
        # 16 KiB clusters. Both must walk each link once, not from the start.
        payload=bytes(i%251 for i in range(400*1024))
        off=self.created()
        for pos in range(0,len(payload),32768):self.write(off,payload[pos:pos+32768])
        self.call(6,di=off)
        off=self.opened(name='S:\\NEW.BIN')
        self.lib.fs_invalidate()
        calls=C.c_uint32.in_dll(self.lib,'test_fat_calls');calls.value=0
        before=C.c_uint.in_dll(self.lib,'rw_host_reads').value
        before_writes=C.c_uint.in_dll(self.lib,'rw_host_writes').value
        for pos in range(0,len(payload),4096):
            self.read(off,4096,payload[pos:pos+4096])
        sectors=(len(payload)+511)//512
        clusters=(len(payload)+self.layout.get('spc',1)*512-1)//(self.layout.get('spc',1)*512)
        self.assertLessEqual(calls.value,clusters)
        traffic=C.c_uint.in_dll(self.lib,'rw_host_reads').value-before
        self.assertLessEqual(traffic,sectors+(clusters+127)//128+2)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_writes').value,before_writes)


    def test_four_fat_sectors_survive_interleaved_lookups(self):
        width=self.bits//8;per_sector=512//width
        clusters=[2+i*per_sector for i in range(4)]
        self.lib.fs_invalidate()
        reads=C.c_uint.in_dll(self.lib,'rw_host_reads')
        for c in clusters:self.lib.fs_fat_entry(c)
        before=reads.value
        for unused in range(10):
            for c in clusters:self.lib.fs_fat_entry(c)
        self.assertEqual(reads.value,before)
        lba=self.layout['start']+(1 if self.bits==16 else 32)+1
        self.lib.fs_invalidate_sector(lba)
        for c in clusters:self.lib.fs_fat_entry(c)
        self.assertEqual(reads.value,before+1)

    def test_two_directory_sectors_survive_interleaved_file_reads(self):
        a=self.opened(name='S:\\README.TXT')
        b=self.opened(slot=1,name='S:\\SUBDIR\\INNER.TXT')
        self.read(a,1,b'H');self.read(b,1,b'H')
        before=C.c_uint.in_dll(self.lib,'rw_host_reads').value
        for unused in range(8):
            self.seek(a,0);self.read(a,1,b'H')
            self.seek(b,0);self.read(b,1,b'H')
        # Payload buffer alternates between two sectors; metadata stays cached.
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_reads').value-before,16)

    def test_shared_truncate_reallocation_and_backward_seek(self):
        a=self.created();payload=b'A'*20000+b'B'*20000
        self.write(a,payload)
        b=self.opened(slot=1,name='S:\\NEW.BIN',mode=0x40)
        self.read(b,22000,payload[:22000])
        self.seek(a,0);self.write(a,b'')
        self.write(a,b'NEW'*8000)
        self.seek(b,21000);self.read(b,6,b'NEWNEW')
        self.seek(b,1);self.read(b,5,b'EWNEW')
        self.seek(b,24000);self.read(b,1,b'')

    def test_cached_payload_and_metadata_are_invalidated_by_shared_overwrite(self):
        a=self.created();self.write(a,b'OLD DATA')
        b=self.opened(slot=1,name='S:\\NEW.BIN',mode=0x40)
        self.read(b,8,b'OLD DATA')
        self.seek(a,0);self.write(a,b'NEW')
        self.seek(b,0);self.read(b,8,b'NEW DATA')
        self.seek(a,8);self.write(a,b' TAIL')
        self.seek(b,8);self.read(b,10,b' TAIL')

    def test_tail_relinked_with_same_first_cluster_invalidates_retained_cursor(self):
        a=self.created();self.write(a,b'A'*40000)
        b=self.opened(slot=1,name='S:\\NEW.BIN',mode=0x40)
        self.read(b,18000,b'A'*18000)
        original=fs.File()
        self.assertEqual(self.lib.rw_lookup(b'NEW.BIN',C.byref(original)),0)
        original_first=original.first
        self.seek(a,5);self.write(a,b'')
        other=self.created('S:\\OTHER.BIN',slot=2)
        self.write(other,b'OTHER'*1700)
        replacement=bytes((i*13+23)%251 for i in range(24000))
        self.write(a,replacement)
        # The first allocation survives, but the retained tail position now
        # refers to a reclaimed/reused cluster. Reading continues forward.
        current=fs.File()
        self.assertEqual(self.lib.rw_lookup(b'NEW.BIN',C.byref(current)),0)
        self.assertEqual(current.first,original_first)
        self.read(b,100,replacement[17995:18095])

    def test_selective_directory_invalidation_preserves_other_cached_sector(self):
        first=self.layout.get('root_lba',self.layout['data'])
        second=self.layout['data']+(32 if self.bits==16 else 1)
        a,b=C.create_string_buffer(512),C.create_string_buffer(512)
        self.lib.fs_invalidate()
        self.assertEqual(self.lib.fs_read_metadata(first,a),0)
        self.assertEqual(self.lib.fs_read_metadata(second,b),0)
        changed=bytes([a.raw[0]^1])+a.raw[1:512]
        with self.image.open('r+b') as disk:
            disk.seek(first*512);disk.write(changed)
        before=C.c_uint.in_dll(self.lib,'rw_host_reads').value
        self.lib.fs_invalidate_sector(first)
        self.assertEqual(self.lib.fs_read_metadata(second,b),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_reads').value,before)
        self.assertEqual(self.lib.fs_read_metadata(first,a),0)
        self.assertEqual(a.raw[:512],changed)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_reads').value,before+1)

    def test_serial_wrap_disables_retention_without_recycling_old_cursors(self):
        a=self.created();self.write(a,b'A'*40000)
        b=self.opened(slot=1,name='S:\\NEW.BIN',mode=0x40)
        self.read(b,22000,b'A'*22000)
        serial=C.c_uint32.in_dll(self.lib,'rw_read_serial')
        serial.value=0xffffffff
        self.seek(a,0);self.write(a,b'NEW')
        self.assertEqual(serial.value,0)
        calls=C.c_uint32.in_dll(self.lib,'test_fat_calls')
        for unused in range(2):
            calls.value=0
            self.seek(b,21000);self.read(b,100,b'A'*100)
            self.assertGreater(calls.value,0)

    def test_failed_metadata_and_fat_reads_do_not_create_cache_hits(self):
        # Hit the public helpers directly so DOS offline() cannot conceal a
        # failed receive that accidentally leaves a valid cache tag.
        self.lib.fs_invalidate()
        fat_lba=self.layout['start']+(1 if self.bits==16 else 32)
        self.lib.rw_host_config(10,fat_lba)
        self.assertEqual(self.lib.fs_fat_entry(4),0)
        self.assertNotEqual(C.c_uint16.in_dll(self.lib,'fs_error').value,0)
        before=C.c_uint.in_dll(self.lib,'rw_host_reads').value
        self.lib.rw_host_config(10,0)
        self.assertNotEqual(self.lib.fs_fat_entry(4),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_reads').value,before+1)
        lba=self.layout.get('root_lba',self.layout['data'])
        self.lib.rw_host_config(10,lba)
        buffer=C.create_string_buffer(b'?'*512)
        self.assertEqual(self.lib.fs_read_metadata(lba,buffer),-1)
        self.assertEqual(buffer.raw[:512],b'?'*512)
        before=C.c_uint.in_dll(self.lib,'rw_host_reads').value
        self.lib.rw_host_config(10,0)
        self.assertEqual(self.lib.fs_read_metadata(lba,buffer),0)
        self.assertEqual(C.c_uint.in_dll(self.lib,'rw_host_reads').value,before+1)

    def test_cached_reads_still_detect_card_removal_and_replacement(self):
        for replacement in (False,True):
            with self.subTest(replacement=replacement):
                off=self.opened(name='S:\\README.TXT')
                self.read(off,1,b'H')
                self.seek(off,0)
                other=self.work/'other.img'
                if replacement:
                    shutil.copyfile(self.image,other)
                    with other.open('r+b') as disk:
                        disk.seek(self.layout['start']*512+(39 if self.bits==16 else 67))
                        disk.write(b'NEW!')
                    self.lib.rw_host_replace.argtypes=[C.c_char_p]
                    self.assertEqual(self.lib.rw_host_replace(str(other).encode()),0)
                else:
                    self.lib.rw_host_replace.argtypes=[C.c_char_p]
                    self.assertEqual(self.lib.rw_host_replace(b''),0)
                self.read(off,1,b'',error=21)
                self.call(6,di=off)
                self.lib.rw_host_close()
                self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
                self.assertEqual(self.lib.media_mount(),0)


class Fat16ReadCacheTests(ReadCacheCases,unittest.TestCase):
    bits=16
    library_name='readcache16'


class Fat32ReadCacheTests(ReadCacheCases,unittest.TestCase):
    bits=32
    library_name='readcache32'
