"""FAT16 through actual redirector callbacks, including fixed-root deletion."""
import ctypes as C
import unittest
import test_rw_redirector as common
from fat16_fixture import prepare


class Fat16RedirectorTests(unittest.TestCase):
    library_name="fat16-rwredir"
    memory=common.WritableRedirectorTests.memory
    put=common.WritableRedirectorTests.put
    get=common.WritableRedirectorTests.get
    pointer=common.WritableRedirectorTests.pointer
    path=common.WritableRedirectorTests.path
    call=common.WritableRedirectorTests.call
    opened=common.WritableRedirectorTests.opened
    first=common.WritableRedirectorTests.first
    created=common.WritableRedirectorTests.created
    write=common.WritableRedirectorTests.write
    seek=common.WritableRedirectorTests.seek
    clean=common.WritableRedirectorTests.clean
    @classmethod
    def setUpClass(cls):
        common.WritableRedirectorTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):
        common.WritableRedirectorTests.tearDownClass.__func__(cls)
    def setUp(self):
        self.image=self.work/'fat16.img';self.layout=prepare(self.image)
        self.lib.test_reset()
        C.c_ubyte.in_dll(self.lib,'fs_required').value=0
        C.c_int.in_dll(self.lib,'sd_write_enabled').value=1
        C.c_int.in_dll(self.lib,'sd_verify_writes').value=1
        self.assertEqual(self.lib.rw_host_open(str(self.image).encode(),3),0)
        self.sda,self.cds,self.sfts,self.data=[self.memory(n) for n in range(1,5)]
        self.put(self.sda,0x10,0x1234)
        self.assertEqual(self.lib.media_mount(),0)
    def tearDown(self):
        self.lib.rw_host_close()
        C.c_ubyte.in_dll(self.lib,'fs_required').value=0
    def content(self,path):
        self.call(0x20,handled=False)
        return common.WritableRedirectorTests.content(self,path)
    def test_fixed_root_create_read_rename_delete(self):
        off=self.created();self.write(off,b'FAT16 DOS callbacks')
        self.call(6,di=off)
        self.assertEqual(self.content('NEW.BIN'),b'FAT16 DOS callbacks')
        self.path('S:\\NEW.BIN');self.call(0x13)
        self.path('S:\\NEW.BIN');self.call(0x16,param=0,error=2)
        self.clean()
    def test_card_info_format_policy_and_offline_reporting(self):
        for restriction in (0,16):
            C.c_ubyte.in_dll(self.lib,'fs_required').value=restriction
            self.assertEqual(self.lib.media_mount(),0)
            self.call(0,ax=0xd74f,bx=0x4f54,dx=0x524f,si=8,cx=32,es=4,di=4096)
            self.assertEqual(self.get(self.data,4096+28),39+(64 if restriction else 0))
        self.assertEqual(self.lib.media_unmount(),0)
        self.call(0,ax=0xd74f,bx=0x4f54,dx=0x524f,si=8,cx=32,es=4,di=4096)
        self.assertEqual(self.get(self.data,4096+28),66)
        C.c_ubyte.in_dll(self.lib,'fs_required').value=32
        self.assertEqual(self.lib.media_mount(),13)
        self.call(0,ax=0xd74f,bx=0x4f54,dx=0x524f,si=8,cx=32,es=4,di=4096)
        self.assertFalse(self.get(self.data,4096+28)&36)
